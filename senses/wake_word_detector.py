"""
Wake word detection using openWakeWord.
"""

import numpy as np
import sounddevice as sd
from queue import Queue, Empty
from typing import Callable, Optional
from threading import Thread, Event
from pathlib import Path

try:
    from openwakeword.model import Model
    import openwakeword
    OPENWAKEWORD_AVAILABLE = True
except ImportError:
    OPENWAKEWORD_AVAILABLE = False


MIC_NAME = "USB PnP Sound Device"


def _find_mic_device(name_substring: str) -> int:
    """Find an input mic device index by name substring."""
    devices = sd.query_devices()
    for i, d in enumerate(devices):
        if name_substring.lower() in d["name"].lower() and d["max_input_channels"] > 0:
            return i
    raise RuntimeError(
        "Mic '{}' not found. Available: {}".format(
            name_substring, [(i, d["name"]) for i, d in enumerate(devices)]
        )
    )


def _find_bundled_model(name: str) -> str:
    """Find a bundled openWakeWord model by name."""
    pkg_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    for f in pkg_dir.glob("{}*.onnx".format(name)):
        return str(f)
    raise FileNotFoundError("Bundled model {} not found in {}".format(name, pkg_dir))


class WakeWordDetector:
    """Detects wake word using openWakeWord."""

    def __init__(
        self,
        model_path: str = "",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        mic_sample_rate: int = 48000,
        mic_name: str = "",
        inference_framework: str = "onnx",
        gain_target_peak: float = 0.9
    ):
        if not OPENWAKEWORD_AVAILABLE:
            raise RuntimeError("openwakeword not installed. Run: pip install openwakeword")

        self.threshold = threshold
        self.sample_rate = sample_rate
        self.mic_sample_rate = mic_sample_rate
        self.gain_target_peak = gain_target_peak
        # openWakeWord expects 80ms chunks at 16kHz = 1280 samples.
        self.chunk_samples_16k = int(self.sample_rate * 0.08)
        self.mic_chunk_size = max(256, int(self.mic_sample_rate * 0.08))

        # Resolve mic device by name (survives USB re-enumeration)
        effective_mic_name = (mic_name or MIC_NAME).strip()
        self.mic_device = _find_mic_device(effective_mic_name)
        print("    Wake word mic: device {} ({}, {} Hz)".format(self.mic_device, effective_mic_name, self.mic_sample_rate))

        # Use custom model if provided, otherwise fall back to built-in hey_jarvis
        use_custom = (
            model_path
            and Path(model_path).exists()
        )

        if use_custom:
            self.model = Model(wakeword_model_paths=[model_path])
        else:
            jarvis_path = _find_bundled_model("hey_jarvis")
            self.model = Model(wakeword_model_paths=[jarvis_path])

        self._running = False
        self._stop_event = Event()
        self._resume_event = Event()
        self._thread: Optional[Thread] = None
        self._callback: Optional[Callable] = None
        self._paused = False
        self._audio_queue: Queue = Queue()
        self._gain = 4.0
        self._last_scores = {}

    def get_last_scores(self) -> dict:
        """Return last wake-word scores (for debugging)."""
        return dict(self._last_scores)

    def start(self, callback: Callable[[], None]):
        """Start listening for wake word."""
        self._callback = callback
        self._running = True
        self._paused = False
        self._stop_event.clear()
        self._resume_event.set()

        self._thread = Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listening."""
        self._running = False
        self._stop_event.set()
        self._resume_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def pause(self):
        """Pause detection and release the mic stream."""
        self._paused = True
        self._resume_event.clear()

    def resume(self):
        """Resume detection (reopens mic stream)."""
        self._paused = False
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except Empty:
                break
        self._resume_event.set()

    def _normalize(self, audio: np.ndarray) -> np.ndarray:
        """Apply adaptive gain normalization for weak USB mics."""
        peak = np.max(np.abs(audio))
        if peak < 50:
            return audio.astype(np.int16)
        target = self.gain_target_peak * 32767
        desired_gain = target / peak
        # Cap gain to avoid clipping distortion on speech
        desired_gain = min(desired_gain, 15.0)
        self._gain = 0.3 * desired_gain + 0.7 * self._gain
        self._gain = min(self._gain, 15.0)
        gained = np.clip(audio * self._gain, -32768, 32767)
        return gained.astype(np.int16)

    def _resample_to_16k(self, audio_i16: np.ndarray) -> np.ndarray:
        """Resample int16 mono audio from mic_sample_rate to 16k."""
        if self.mic_sample_rate == self.sample_rate:
            out = audio_i16
        else:
            x = audio_i16.astype(np.float32)
            n_in = x.shape[0]
            n_out = self.chunk_samples_16k
            if n_in <= 1:
                return np.zeros((n_out,), dtype=np.int16)
            t_in = np.linspace(0.0, 1.0, num=n_in, endpoint=False)
            t_out = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            y = np.interp(t_out, t_in, x).astype(np.float32)
            out = np.clip(y, -32768, 32767).astype(np.int16)

        # Ensure exact length the model expects.
        if out.shape[0] != self.chunk_samples_16k:
            if out.shape[0] > self.chunk_samples_16k:
                out = out[: self.chunk_samples_16k]
            else:
                out = np.pad(out, (0, self.chunk_samples_16k - out.shape[0]))
        return out

    def _listen_loop(self):
        """Main listening loop - reopens stream after each pause/resume cycle."""
        while self._running:
            self._resume_event.wait()
            if not self._running:
                break

            while not self._audio_queue.empty():
                try:
                    self._audio_queue.get_nowait()
                except Empty:
                    break

            def audio_callback(indata, frames, time_info, status):
                self._audio_queue.put(bytes(indata))

            try:
                stream = sd.RawInputStream(
                    device=self.mic_device,
                    samplerate=self.mic_sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self.mic_chunk_size,
                    latency="high",
                    callback=audio_callback
                )
                stream.start()
            except Exception as e:
                print("Wake word stream error: {}".format(e))
                if self._running:
                    self._stop_event.wait(timeout=1.0)
                continue

            detected = False
            while self._running and not self._paused:
                try:
                    raw = self._audio_queue.get(timeout=0.1)
                except Empty:
                    continue

                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
                normalized = self._normalize(audio)
                frame_16k = self._resample_to_16k(normalized)

                predictions = self.model.predict(frame_16k)
                self._last_scores = predictions

                for model_name, score in predictions.items():
                    if score >= self.threshold:
                        print("Wake word detected! ({}, score: {:.3f})".format(
                            model_name, score))
                        detected = True
                        break

                if detected:
                    break

            # Close stream BEFORE callback to free USB mic for recording
            stream.stop()
            stream.close()

            if detected and self._callback:
                self._paused = True
                self._resume_event.clear()
                self.model.reset()
                self._callback()
