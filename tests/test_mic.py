#!/usr/bin/env python3
"""
Mic smoke test: record audio, print levels, save WAV, optionally play back.

Usage:
  source venv/bin/activate
  python tests/test_mic.py --seconds 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

# Add project root
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import Config


def _pick_input_device(name_substring: str) -> int:
    devices = sd.query_devices()
    if name_substring:
        for i, d in enumerate(devices):
            if name_substring.lower() in str(d.get("name", "")).lower() and d.get("max_input_channels", 0) > 0:
                return i
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            return i
    raise RuntimeError(f"No input devices found: {[(i, d.get('name')) for i, d in enumerate(devices)]}")


def _write_wav(path: Path, audio_i16: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio_i16.tobytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--out", type=str, default="recordings/mic_test.wav")
    parser.add_argument("--no-playback", action="store_true")
    args = parser.parse_args()

    cfg = Config.load()
    mic_name = (cfg.mic_name or os.getenv("JANSKY_MIC_NAME") or "").strip()
    sample_rate = int(cfg.mic_sample_rate)

    device = _pick_input_device(mic_name)
    dev_info = sd.query_devices(device)
    print("Mic test")
    print(f"- device_index: {device}")
    print(f"- device_name:  {dev_info.get('name')}")
    print(f"- sample_rate:  {sample_rate}")
    print(f"- seconds:      {args.seconds}")
    print("Recording... speak now.")

    audio = sd.rec(
        int(args.seconds * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        device=device,
        blocking=False,
    )

    start = time.time()
    last_print = 0.0
    while True:
        elapsed = time.time() - start
        if elapsed >= args.seconds:
            break
        if elapsed - last_print >= 0.5:
            last_print = elapsed
            # RMS of the most recent chunk (best-effort).
            n = int(min(elapsed * sample_rate, audio.shape[0]))
            tail = audio[max(0, n - int(0.5 * sample_rate)) : n]
            if tail.size:
                rms = float(np.sqrt(np.mean(tail.astype(np.float32) ** 2)) / 32768.0)
                peak = float(np.max(np.abs(tail.astype(np.float32))) / 32768.0)
                print(f"  level rms={rms:.4f} peak={peak:.4f}")
        time.sleep(0.05)

    sd.wait()

    audio_i16 = np.asarray(audio).reshape(-1).astype(np.int16)
    out_path = REPO_ROOT / args.out
    _write_wav(out_path, audio_i16, sample_rate)
    print(f"Saved: {out_path}")

    # Basic sanity check
    rms_all = float(np.sqrt(np.mean(audio_i16.astype(np.float32) ** 2)) / 32768.0)
    print(f"Overall RMS: {rms_all:.4f}")
    if rms_all < 0.002:
        print("WARNING: audio level is very low. Check mic selection/gain.")

    if not args.no_playback:
        print("Playing back (Ctrl+C to stop)...")
        try:
            sd.play(audio_i16.astype(np.float32) / 32768.0, sample_rate)
            sd.wait()
        except Exception as e:
            print(f"Playback failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

