"""
Audio Manager - Handles microphone input and speaker output with muting.
"""

import re
import sounddevice as sd
import numpy as np
import wave
import subprocess
from threading import Lock
from typing import Optional
import os


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

        self.speaker_alsa = _find_alsa_card_by_name(effective_speaker_name) if effective_speaker_name else _find_alsa_card_by_name(SPEAKER_NAME)
        self.speaker_sd_index = None
        if effective_speaker_name:
            try:
                self.speaker_sd_index = _find_device_by_name(effective_speaker_name, "output")
            except Exception:
                pass
        print("    Mic: device {} ({})".format(self.mic_device, effective_mic_name or "auto"))
        print("    Speaker: {} ({})".format(self.speaker_alsa, effective_speaker_name or "auto"))

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

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        """Save audio array to WAV file."""
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def _play_wav_sounddevice(self, filepath: str) -> None:
        """Play WAV via PortAudio (fallback when aplay/ALSA fails)."""
        with wave.open(filepath, "rb") as wf:
            rate = wf.getframerate()
            nchan = wf.getnchannels()
            frames = wf.readframes(wf.getnframes())
            audio_data = np.frombuffer(frames, dtype=np.int16)
            if nchan > 1:
                audio_data = audio_data.reshape(-1, nchan)
            sd.play(audio_data, rate, device=self.speaker_sd_index)
            sd.wait()

    def play_wav(self, filepath: str):
        """Play a WAV file through speakers."""
        self.mute()
        try:
            devices = []
            for d in (self.speaker_alsa, "default", "sysdefault"):
                if d not in devices:
                    devices.append(d)

            for dev in devices:
                try:
                    subprocess.run(
                        ["aplay", "-D", dev, filepath],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    return
                except FileNotFoundError:
                    break
                except subprocess.CalledProcessError as e:
                    err = (e.stderr or e.stdout or "").strip()
                    if err:
                        print(f"aplay -D {dev} failed: {err}")

            try:
                self._play_wav_sounddevice(filepath)
            except Exception as e:
                print("Playback error: {}".format(e))
        except Exception as e:
            print("Playback error: {}".format(e))
        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        """Play audio array through speakers."""
        self.mute()
        try:
            sd.play(audio, self.sample_rate, device=self.speaker_sd_index)
            sd.wait()
        finally:
            self.unmute()
