"""
Audio Manager - Handles microphone input and speaker output with muting.
"""

import re
import sounddevice as sd
import numpy as np
import wave
import subprocess
import shutil
import tempfile
import os
from threading import Lock
from typing import Optional

# Gives HDMI/USB DAC hardware time to lock before speech (reduces clipped first syllables).
PLAYBACK_LEAD_IN_MS = 80


PLAYBACK_TRY_ALSA_PULSE = (
    os.environ.get("JANSKY_ALSA_PULSE", "").strip().lower() in ("1", "true", "yes")
)


def _find_device_by_name(name_substring: str, kind: str) -> int:
    """Find a sounddevice device index by name substring.

    Args:
        name_substring: Partial device name to match (e.g. "USB PnP Sound Device")
        kind: "input" or "output"

    Returns:
        Device index, or raises RuntimeError if not found.
    """
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if name_substring.lower() in d["name"].lower() and d[channel_key] > 0:
            return i
    raise RuntimeError(
        "Audio device matching '{}' ({}) not found. Available: {}".format(
            name_substring, kind,
            [(i, d["name"]) for i, d in enumerate(devices)]
        )
    )


def _find_first_device(kind: str) -> int:
    """Pick the first input/output device with channels."""
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if d.get(channel_key, 0) > 0:
            return i
    raise RuntimeError(f"No {kind} audio device found by sounddevice. Devices: {[(i, d.get('name')) for i, d in enumerate(devices)]}")


def _find_alsa_card_by_name(name_substring: str) -> str:
    """Find ALSA card number by name, returns 'plughw:N,0' string."""
    if not name_substring:
        return "default"
    needle = name_substring.lower()
    try:
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if line.startswith("card ") and needle in line.lower():
                card_num = line.split(":")[0].replace("card ", "").strip()
                return "plughw:{},0".format(card_num)
    except Exception:
        pass
    return "default"


# Device name substrings for lookup
MIC_NAME = "USB PnP Sound Device"
SPEAKER_NAME = "UACDemoV1.0"


class AudioManager:
    """Manages microphone input and speaker output with muting."""

    def __init__(
        self,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        channels: int = 1,
        dtype: str = 'int16',
        mic_name: str = "",
        speaker_name: str = "",
        speaker_alsa_device: str = "",
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.channels = channels
        self.dtype = dtype
        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

        # Resolve device indices at init time
        effective_mic_name = (mic_name or os.getenv("JANSKY_MIC_NAME") or MIC_NAME).strip()
        effective_speaker_name = (speaker_name or os.getenv("JANSKY_SPEAKER_NAME") or SPEAKER_NAME).strip()

        try:
            self.mic_device = _find_device_by_name(effective_mic_name, "input") if effective_mic_name else _find_first_device("input")
        except Exception as e:
            devices = sd.query_devices()
            raise RuntimeError(
                "Mic device not found.\n"
                f"- Tried name contains: '{effective_mic_name}'\n"
                f"- sounddevice devices: {[(i, d.get('name'), d.get('max_input_channels')) for i, d in enumerate(devices)]}\n"
                "Fix:\n"
                "1) Plug in a USB microphone\n"
                "2) Run: python -c \"import sounddevice as sd; print(list(enumerate(sd.query_devices())))\"\n"
                "3) Set `mic_name` in config/config.json to a substring of your mic device name.\n"
            ) from e

        alsa_override = (
            (speaker_alsa_device or os.getenv("JANSKY_SPEAKER_ALSA") or "").strip()
        )
        if alsa_override:
            self.speaker_alsa = alsa_override
        else:
            self.speaker_alsa = (
                _find_alsa_card_by_name(effective_speaker_name)
                if effective_speaker_name
                else _find_alsa_card_by_name(SPEAKER_NAME)
            )
        self.speaker_sd_index = None
        if effective_speaker_name:
            try:
                self.speaker_sd_index = _find_device_by_name(effective_speaker_name, "output")
            except Exception:
                pass
        print("    Mic: device {} ({})".format(self.mic_device, effective_mic_name or "auto"))
        print("    Speaker ALSA: {} (name match: {})".format(self.speaker_alsa, effective_speaker_name or "auto"))

    def mute(self):
        """Mute microphone input (during TTS playback)."""
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        """Unmute microphone input."""
        with self._mute_lock:
            self.is_muted = False

    def _normalize(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        """Apply gain normalization for weak USB mics."""
        peak = np.max(np.abs(audio.astype(np.float64)))
        if peak < 50:
            return audio
        gain = (target_peak * 32767) / peak
        return np.clip(audio.astype(np.float64) * gain, -32768, 32767).astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        max_duration: float = 30.0
    ) -> Optional[np.ndarray]:
        """
        Record audio until silence is detected.
        Records at mic_sample_rate (48kHz), then decimates to target sample_rate (16kHz).
        """
        if self.is_muted:
            return None

        self._audio_buffer = []
        self._recording = True
        silence_samples = 0
        silence_samples_needed = int(silence_duration * self.mic_sample_rate / 4096)
        max_samples = int(max_duration * self.mic_sample_rate / 4096)
        total_samples = 0

        def callback(indata, frames, time, status):
            if status:
                pass  # Ignore non-fatal overflow on USB mic
            if self.is_muted or not self._recording:
                return
            self._audio_buffer.append(indata.copy())

        stream = sd.InputStream(
            device=self.mic_device,
            samplerate=self.mic_sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            blocksize=4096,
            latency="high",
            callback=callback
        )
        stream.start()

        try:
            while self._recording and total_samples < max_samples:
                sd.sleep(100)
                total_samples += 1

                if len(self._audio_buffer) > 0:
                    recent = self._audio_buffer[-1]
                    rms = np.sqrt(np.mean(recent.astype(np.float32) ** 2)) / 32768
                    if rms < silence_threshold:
                        silence_samples += 1
                        if silence_samples >= silence_samples_needed:
                            break
                    else:
                        silence_samples = 0
        finally:
            stream.stop()
            stream.close()

        self._recording = False

        if len(self._audio_buffer) == 0:
            return None

        raw_audio = np.concatenate(self._audio_buffer, axis=0).flatten()
        normalized = self._normalize(raw_audio)
        # Decimate from 48kHz to 16kHz (exact factor of 3)
        decimated = normalized[::3]
        return decimated

    def _read_wav_int16(self, filepath: str) -> tuple[int, np.ndarray]:
        with wave.open(filepath, "rb") as wf:
            rate = wf.getframerate()
            nchan = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).copy()
            if nchan > 1:
                arr = arr.reshape(-1, nchan)
        return rate, arr

    def _prepend_lead_in(self, sample_rate: int, audio: np.ndarray) -> np.ndarray:
        n = int(sample_rate * PLAYBACK_LEAD_IN_MS / 1000)
        if n <= 0:
            return audio
        if audio.ndim == 1:
            pad = np.zeros(n, dtype=np.int16)
            return np.concatenate((pad, audio))
        nch = audio.shape[1]
        pad = np.zeros((n, nch), dtype=np.int16)
        return np.vstack((pad, audio))

    def _write_wav_int16(self, filepath: str, sample_rate: int, audio: np.ndarray) -> None:
        nchan = 1 if audio.ndim == 1 else audio.shape[1]
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(nchan)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(np.ascontiguousarray(audio).tobytes())

    def _alsa_playback_device_order(self) -> list[str]:
        """Try explicit card first: Pi OS Lite often breaks 'default' (error 524) without PipeWire plugins."""
        candidates: list[str] = [self.speaker_alsa, "sysdefault", "default"]
        if PLAYBACK_TRY_ALSA_PULSE:
            candidates.append("pulse")
        seen: set[str] = set()
        out: list[str] = []
        for d in candidates:
            if d and d not in seen:
                seen.add(d)
                out.append(d)
        return out

    def _sd_play(self, sample_rate: int, audio: np.ndarray) -> None:
        sd.play(audio, sample_rate, device=self.speaker_sd_index)
        sd.wait()

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        """Save audio array to WAV file."""
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def play_wav(self, filepath: str):
        """Play a WAV file through speakers."""
        self.mute()
        try:
            rate, audio = self._read_wav_int16(filepath)
            audio = self._prepend_lead_in(rate, audio)
            fd, tmp_path = tempfile.mkstemp(prefix="jansky_play_", suffix=".wav")
            os.close(fd)
            try:
                self._write_wav_int16(tmp_path, rate, audio)
                if shutil.which("aplay"):
                    for dev in self._alsa_playback_device_order():
                        try:
                            subprocess.run(
                                ["aplay", "-D", dev, tmp_path],
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                            return
                        except subprocess.CalledProcessError as e:
                            err = (e.stderr or e.stdout or "").strip()
                            if err:
                                print(f"aplay -D {dev} failed: {err}")

                self._sd_play(rate, audio)
            except Exception as e:
                print(f"Playback error: {e}")
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        """Play audio array through speakers."""
        self.mute()
        try:
            pcm = np.asarray(audio, dtype=np.int16)
            pcm = self._prepend_lead_in(self.sample_rate, pcm)
            self._sd_play(self.sample_rate, pcm)
        finally:
            self.unmute()
