"""
Audio Manager - Handles microphone input and speaker output with muting.

HDMI / vc4 note: direct ``aplay -D plughw:…`` to the Pi's HDMI audio often resets
the display stack (HDMI + VNC drop). For vc4/hdmi speakers we skip that path and
use PortAudio (int16) or ``paplay`` when available.
"""

import os
import shutil
import subprocess
import wave
from threading import Lock
from typing import Optional

import numpy as np
import sounddevice as sd


def _find_device_by_name(name_substring: str, kind: str) -> int:
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if name_substring.lower() in d["name"].lower() and d[channel_key] > 0:
            return i
    raise RuntimeError(
        "Audio device matching '{}' ({}) not found. Available: {}".format(
            name_substring,
            kind,
            [(i, d["name"]) for i, d in enumerate(devices)],
        )
    )


def _find_first_device(kind: str) -> int:
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if d.get(channel_key, 0) > 0:
            return i
    raise RuntimeError(
        f"No {kind} audio device found by sounddevice. Devices: {[(i, d.get('name')) for i, d in enumerate(devices)]}"
    )


def _find_alsa_card_by_name(name_substring: str) -> str:
    if not name_substring:
        return "plughw:0,0"
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
    return "plughw:0,0"


def _hdmi_vc4_speaker_hint(name: str) -> bool:
    n = name.lower()
    return "hdmi" in n or "vc4" in n


def _find_output_sd_index(name_substring: str) -> Optional[int]:
    if not name_substring:
        return None
    try:
        return _find_device_by_name(name_substring, "output")
    except Exception:
        pass
    needle = name_substring.lower()
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_output_channels", 0) <= 0:
            continue
        if needle in (d.get("name") or "").lower():
            return i
    for kw in ("vc4hdmi", "vc4-hdmi", "hdmi", "vc4"):
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_output_channels", 0) <= 0:
                continue
            if kw in (d.get("name") or "").lower():
                return i
    try:
        return _find_first_device("output")
    except Exception:
        return None


def _resample_int16_mono(mono: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    if src_sr == dst_sr or src_sr <= 0 or dst_sr <= 0:
        return mono.astype(np.int16).reshape(-1)
    x = np.arange(len(mono), dtype=np.float64)
    n_dst = max(1, int(round(len(mono) * dst_sr / src_sr)))
    x_new = np.linspace(0, len(mono) - 1, n_dst)
    y = np.interp(x_new, x, mono.astype(np.float64))
    return np.clip(np.round(y), -32768, 32767).astype(np.int16)


MIC_NAME = "USB PnP Sound Device"
SPEAKER_NAME = "UACDemoV1.0"


class AudioManager:
    """Manages microphone input and speaker output with muting."""

    def __init__(
        self,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        channels: int = 1,
        dtype: str = "int16",
        mic_name: str = "",
        speaker_name: str = "",
        enable_local_speaker: bool = True,
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.channels = channels
        self.dtype = dtype
        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

        env_off = os.environ.get("JANSKY_DISABLE_SPEAKER", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self._speaker_enabled = bool(enable_local_speaker) and not env_off
        self._speaker_warned = False

        effective_mic_name = (mic_name or os.getenv("JANSKY_MIC_NAME") or MIC_NAME).strip()
        effective_speaker_name = (
            speaker_name or os.getenv("JANSKY_SPEAKER_NAME") or SPEAKER_NAME
        ).strip()

        try:
            self.mic_device = (
                _find_device_by_name(effective_mic_name, "input")
                if effective_mic_name
                else _find_first_device("input")
            )
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

        self.speaker_alsa = (
            _find_alsa_card_by_name(effective_speaker_name)
            if effective_speaker_name
            else _find_alsa_card_by_name(SPEAKER_NAME)
        )
        self._speaker_name = effective_speaker_name
        self._hdmi_output = _hdmi_vc4_speaker_hint(effective_speaker_name)
        self.speaker_sd_index = _find_output_sd_index(effective_speaker_name)

        print("    Mic: device {} ({})".format(self.mic_device, effective_mic_name or "auto"))
        print(
            "    Speaker: {} ({}){}".format(
                self.speaker_alsa,
                effective_speaker_name or "auto",
                " [HDMI-safe playback]" if self._hdmi_output else "",
            )
        )
        if not self._speaker_enabled:
            print("    Local speaker: disabled (no WAV output; set enable_local_speaker true to hear)")

    def mute(self):
        with self._mute_lock:
            self.is_muted = True

    def unmute(self):
        with self._mute_lock:
            self.is_muted = False

    def _normalize(self, audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
        peak = np.max(np.abs(audio.astype(np.float64)))
        if peak < 50:
            return audio
        gain = (target_peak * 32767) / peak
        return np.clip(audio.astype(np.float64) * gain, -32768, 32767).astype(np.int16)

    def record_until_silence(
        self,
        silence_threshold: float = 0.01,
        silence_duration: float = 1.5,
        max_duration: float = 30.0,
    ) -> Optional[np.ndarray]:
        if self.is_muted:
            return None

        self._audio_buffer = []
        self._recording = True
        silence_samples = 0
        silence_samples_needed = int(silence_duration * self.mic_sample_rate / 4096)
        max_samples = int(max_duration * self.mic_sample_rate / 4096)
        total_samples = 0

        def callback(indata, frames, time, status):
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
            callback=callback,
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
        decimated = normalized[::3]
        return decimated

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def _read_wav_mono_int16(self, filepath: str) -> tuple[int, np.ndarray]:
        with wave.open(filepath, "rb") as wf:
            rate = wf.getframerate()
            nch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).copy()
            if nch > 1:
                arr = arr.reshape(-1, nch)[:, 0]
            else:
                arr = arr.reshape(-1)
        return rate, arr

    def _play_paplay(self, filepath: str) -> bool:
        pap = shutil.which("paplay")
        if not pap:
            return False
        try:
            subprocess.run([pap, filepath], check=True, capture_output=True, text=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError):
            return False

    def _play_portaudio_int16(self, mono_i16: np.ndarray, sample_rate: int) -> bool:
        """Single open, int16 — best chance with vc4 HDMI without resetting the display."""
        devices: list[Optional[int]] = []
        if self.speaker_sd_index is not None:
            devices.append(self.speaker_sd_index)
        devices.append(None)

        for out_sr in (48000, 44100, int(sample_rate)):
            if out_sr <= 0:
                continue
            pcm = (
                _resample_int16_mono(mono_i16, int(sample_rate), out_sr)
                if out_sr != int(sample_rate)
                else mono_i16.reshape(-1).astype(np.int16)
            )
            for ch in (2, 1):
                if ch == 2:
                    buf = np.ascontiguousarray(np.column_stack((pcm, pcm)))
                else:
                    buf = np.ascontiguousarray(pcm.reshape(-1, 1))
                for dev in devices:
                    try:
                        with sd.OutputStream(
                            samplerate=out_sr,
                            channels=ch,
                            dtype="int16",
                            device=dev,
                            latency="high",
                        ) as stream:
                            stream.write(buf)
                        return True
                    except Exception:
                        continue
        return False

    def play_wav(self, filepath: str):
        self.mute()
        try:
            if not self._speaker_enabled:
                if not self._speaker_warned:
                    print("(speaker disabled — enable_local_speaker or unset JANSKY_DISABLE_SPEAKER)")
                    self._speaker_warned = True
                return

            if self._hdmi_output:
                if self._play_paplay(filepath):
                    return
                rate, mono = self._read_wav_mono_int16(filepath)
                if self._play_portaudio_int16(mono, rate):
                    return
                print(
                    "Playback error: HDMI audio failed. Try USB speakers/headphones, "
                    "or set enable_local_speaker to false while using VNC."
                )
                return

            aplay = shutil.which("aplay")
            if aplay:
                try:
                    subprocess.run(
                        [aplay, "-D", self.speaker_alsa, filepath],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    return
                except subprocess.CalledProcessError as e:
                    err = (e.stderr or e.stdout or "").strip()
                    if err:
                        print(f"aplay failed: {err}")

            rate, mono = self._read_wav_mono_int16(filepath)
            if self._play_portaudio_int16(mono, rate):
                return
            sd.play(mono, rate, device=self.speaker_sd_index)
            sd.wait()
        except Exception as e:
            print(f"Playback error: {e}")
        finally:
            self.unmute()

    def play_audio(self, audio: np.ndarray):
        self.mute()
        try:
            if not self._speaker_enabled:
                return
            pcm = np.asarray(audio, dtype=np.int16).reshape(-1)
            if self._hdmi_output:
                if self._play_portaudio_int16(pcm, self.sample_rate):
                    return
                print("Playback error: HDMI PortAudio failed for play_audio.")
                return
            sd.play(pcm, self.sample_rate, device=self.speaker_sd_index)
            sd.wait()
        finally:
            self.unmute()
