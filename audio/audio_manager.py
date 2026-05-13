"""
Audio Manager - Handles microphone input and speaker output with muting.
"""

import os
import shutil
import subprocess
import tempfile
import wave
from threading import Lock
from typing import Optional

import numpy as np
import sounddevice as sd

# Gives HDMI/USB DAC hardware time to lock before speech (reduces clipped first syllables).
PLAYBACK_LEAD_IN_MS = 80

PLAYBACK_TRY_ALSA_PULSE = os.environ.get("JANSKY_ALSA_PULSE", "").strip().lower() in (
    "1",
    "true",
    "yes",
)

# When set, append these after the primary chain (for broken "default" on Pi Lite).
PLAYBACK_TRY_ALSA_EXTRA = os.environ.get("JANSKY_ALSA_TRY_EXTRA", "").strip().lower() in (
    "1",
    "true",
    "yes",
)


def _find_device_by_name(name_substring: str, kind: str) -> int:
    """Find a sounddevice device index by name substring."""
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
    """Pick the first input/output device with channels."""
    devices = sd.query_devices()
    channel_key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(devices):
        if d.get(channel_key, 0) > 0:
            return i
    raise RuntimeError(
        f"No {kind} audio device found by sounddevice. Devices: {[(i, d.get('name')) for i, d in enumerate(devices)]}"
    )


def _find_alsa_card_by_name(name_substring: str) -> str:
    """Find ALSA card by name; returns 'plughw:N,0'. Fallback plughw:0,0 on Pi-like setups."""
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


def _hdmi_vc4_name_hint(name: str) -> bool:
    n = name.lower()
    return "hdmi" in n or "vc4" in n


def _alsa_card_is_hdmi_vc4(speaker_alsa: str) -> bool:
    """True if plughw:N,* points at a card whose aplay listing is HDMI / vc4."""
    if not speaker_alsa.startswith("plughw:"):
        return False
    try:
        card_part = speaker_alsa.split(",")[0]
        card_num = int(card_part.replace("plughw:", "").strip())
    except (ValueError, IndexError):
        return False
    try:
        result = subprocess.run(
            ["aplay", "-l"], capture_output=True, text=True, check=True
        )
        prefix = "card {}:".format(card_num)
        for line in result.stdout.splitlines():
            if line.startswith(prefix):
                low = line.lower()
                return "hdmi" in low or "vc4" in low
    except Exception:
        pass
    return False


def _find_output_sd_index(name_substring: str) -> Optional[int]:
    """PortAudio output index: match config substring, then common Pi HDMI aliases."""
    if name_substring:
        try:
            return _find_device_by_name(name_substring, "output")
        except Exception:
            pass
        needle = name_substring.lower()
        devices = sd.query_devices()
        for i, d in enumerate(devices):
            if d.get("max_output_channels", 0) <= 0:
                continue
            dn = (d.get("name") or "").lower()
            if needle in dn:
                return i
        for kw in ("vc4hdmi", "vc4-hdmi", "hdmi", "vc4"):
            for i, d in enumerate(devices):
                if d.get("max_output_channels", 0) <= 0:
                    continue
                if kw in (d.get("name") or "").lower():
                    return i
    try:
        return _find_first_device("output")
    except Exception:
        return None


def _resample_int16_linear(audio: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Linear resample for int16 mono/stereo (HDMI often wants 48000 Hz; Piper may be 22050)."""
    if src_sr == dst_sr or src_sr <= 0 or dst_sr <= 0:
        return audio
    a = np.asarray(audio, dtype=np.float64)
    n_src = a.shape[0]
    n_dst = max(1, int(round(n_src * dst_sr / src_sr)))
    x_old = np.arange(n_src, dtype=np.float64)
    x_new = np.linspace(0, n_src - 1, n_dst)
    if a.ndim == 1:
        out = np.interp(x_new, x_old, a)
    else:
        cols = [np.interp(x_new, x_old, a[:, c]) for c in range(a.shape[1])]
        out = np.column_stack(cols)
    return np.clip(np.round(out), -32768, 32767).astype(np.int16)


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
        speaker_alsa_device: str = "",
        playback_sounddevice_only: bool = False,
    ):
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.channels = channels
        self.dtype = dtype
        self.is_muted = False
        self._mute_lock = Lock()
        self._recording = False
        self._audio_buffer = []

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

        alsa_override = (
            speaker_alsa_device or os.getenv("JANSKY_SPEAKER_ALSA") or ""
        ).strip()
        self._alsa_explicit = bool(alsa_override)
        if alsa_override:
            self.speaker_alsa = alsa_override
        else:
            self.speaker_alsa = (
                _find_alsa_card_by_name(effective_speaker_name)
                if effective_speaker_name
                else _find_alsa_card_by_name(SPEAKER_NAME)
            )

        self.speaker_sd_index = _find_output_sd_index(effective_speaker_name)

        force_aplay = os.environ.get("JANSKY_FORCE_APLAY", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        env_sd_only = os.environ.get("JANSKY_PLAYBACK_SOUNDDEVICE_ONLY", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        auto_hdmi = _hdmi_vc4_name_hint(effective_speaker_name) or _alsa_card_is_hdmi_vc4(
            self.speaker_alsa
        )
        self._skip_aplay = (not force_aplay) and (
            playback_sounddevice_only
            or env_sd_only
            or auto_hdmi
        )

        print("    Mic: device {} ({})".format(self.mic_device, effective_mic_name or "auto"))
        print(
            "    Speaker ALSA: {} (PortAudio name: {})".format(
                self.speaker_alsa, effective_speaker_name or "auto"
            )
        )
        if self._skip_aplay:
            print(
                "    Playback: PortAudio only (no aplay) — avoids vc4/HDMI display glitches"
            )

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
        """
        Prefer direct plughw first. Do not open 'default'/'pulse' before hardware on Pi Lite
        (avoids error 524 and missing pulse plugin). Explicit config: only that device.
        """
        if self._alsa_explicit:
            return [self.speaker_alsa] if self.speaker_alsa else []

        primary = [self.speaker_alsa] if self.speaker_alsa else []
        extra: list[str] = []
        if PLAYBACK_TRY_ALSA_EXTRA:
            extra.extend(["sysdefault", "default"])
            if PLAYBACK_TRY_ALSA_PULSE:
                extra.append("pulse")

        seen: set[str] = set()
        out: list[str] = []
        for d in primary + extra:
            if d and d not in seen:
                seen.add(d)
                out.append(d)
        return out

    def _playback_output_dev_dict(self) -> dict:
        try:
            if self.speaker_sd_index is not None:
                return sd.query_devices(self.speaker_sd_index)
            return sd.query_devices(kind="output")
        except Exception:
            return {}

    def _playback_output_max_channels(self) -> int:
        d = self._playback_output_dev_dict()
        return max(1, int(d.get("max_output_channels") or 1))

    def _playback_output_samplerate(self) -> Optional[float]:
        d = self._playback_output_dev_dict()
        r = d.get("default_samplerate")
        return float(r) if r else None

    def _to_float32_normalized(self, audio: np.ndarray) -> np.ndarray:
        """PortAudio ALSA often rejects int16 (-9994); normalize to float32 [-1, 1]."""
        a = np.asarray(audio)
        if a.dtype == np.float32:
            return np.clip(a, -1.0, 1.0)
        if np.issubdtype(a.dtype, np.integer):
            if a.dtype == np.int16:
                return (a.astype(np.float32) / 32768.0).clip(-1.0, 1.0)
            info = np.iinfo(a.dtype)
            denom = float(max(abs(info.min), info.max))
            return np.clip(a.astype(np.float32) / denom, -1.0, 1.0)
        return np.clip(a.astype(np.float32), -1.0, 1.0)

    def _try_output_stream_write(
        self,
        buffer: np.ndarray,
        sample_rate: int,
        channels: int,
        dtype_str: str,
        device: Optional[int],
    ) -> bool:
        """Explicit dtype avoids PaLinuxAlsa -9994 (format negotiation) on vc4 HDMI."""
        try:
            with sd.OutputStream(
                samplerate=int(sample_rate),
                channels=channels,
                dtype=dtype_str,
                device=device,
                latency="high",
            ) as stream:
                stream.write(np.ascontiguousarray(buffer))
            return True
        except Exception:
            return False

    def _sd_play(self, sample_rate: int, audio: np.ndarray) -> None:
        pcm = np.asarray(audio)
        if pcm.dtype != np.int16:
            pcm = np.clip(
                np.round(self._to_float32_normalized(pcm) * 32767.0),
                -32768,
                32767,
            ).astype(np.int16)
        if pcm.ndim > 1:
            pcm = pcm[:, 0].copy()

        target_sr = self._playback_output_samplerate()
        base_sr = int(sample_rate)
        rates: list[int] = []
        for r in (base_sr, int(target_sr) if target_sr else 0, 48000, 44100, 32000, 22050):
            if r > 0 and r not in rates:
                rates.append(r)

        max_ch = self._playback_output_max_channels()
        channel_opts = [1] + ([2] if max_ch >= 2 else [])

        devices_to_try: list[Optional[int]] = []
        if self.speaker_sd_index is not None:
            devices_to_try.append(self.speaker_sd_index)
        devices_to_try.append(None)

        last_err: Optional[Exception] = None
        for out_sr in rates:
            pcm_r = (
                _resample_int16_linear(pcm, base_sr, out_sr)
                if out_sr != base_sr
                else pcm
            )
            mono = pcm_r.reshape(-1)

            for ch in channel_opts:
                m_norm = mono.astype(np.float32) / 32768.0
                if ch == 2:
                    buf_i16 = np.ascontiguousarray(
                        np.column_stack((mono, mono)).astype(np.int16)
                    )
                    buf_f32 = np.ascontiguousarray(np.column_stack((m_norm, m_norm)))
                else:
                    buf_i16 = np.ascontiguousarray(mono.astype(np.int16))
                    buf_f32 = np.ascontiguousarray(m_norm)

                for device in devices_to_try:
                    # int16 first — Raspberry Pi HDMI often only exposes S16_LE
                    if self._try_output_stream_write(
                        buf_i16, out_sr, ch, "int16", device
                    ):
                        return
                    if self._try_output_stream_write(
                        buf_f32, out_sr, ch, "float32", device
                    ):
                        return

                    try:
                        sd.play(buf_f32, out_sr, device=device)
                        sd.wait()
                        return
                    except Exception as e:
                        last_err = e

        if last_err:
            raise RuntimeError(f"PortAudio playback failed: {last_err}") from last_err
        raise RuntimeError("PortAudio playback failed: no working format/device")

    def save_to_wav(self, audio: np.ndarray, filepath: str):
        with wave.open(filepath, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    def play_wav(self, filepath: str):
        self.mute()
        try:
            rate, audio = self._read_wav_int16(filepath)
            audio = self._prepend_lead_in(rate, audio)

            if self._skip_aplay:
                self._sd_play(rate, audio)
                return

            fd, tmp_path = tempfile.mkstemp(prefix="jansky_play_", suffix=".wav")
            os.close(fd)
            failures: list[str] = []
            try:
                self._write_wav_int16(tmp_path, rate, audio)
                aplay_bin = shutil.which("aplay")
                if aplay_bin:
                    for dev in self._alsa_playback_device_order():
                        try:
                            subprocess.run(
                                [aplay_bin, "-D", dev, tmp_path],
                                check=True,
                                capture_output=True,
                                text=True,
                            )
                            return
                        except subprocess.CalledProcessError as e:
                            err = (e.stderr or e.stdout or "").strip()
                            if err:
                                failures.append(f"{dev}: {err}")
                if failures:
                    print(
                        "aplay failed (using PortAudio fallback). "
                        + " | ".join(failures[:4])
                    )
                self._sd_play(rate, audio)
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
        self.mute()
        try:
            pcm = np.asarray(audio, dtype=np.int16)
            pcm = self._prepend_lead_in(self.sample_rate, pcm)
            self._sd_play(self.sample_rate, pcm)
        finally:
            self.unmute()
