#!/usr/bin/env python3
"""
Wake-word debug: prints live scores so you can tune threshold and verify audio.

Usage:
  source venv/bin/activate
  python tests/test_wake_debug.py
"""

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from config import Config
from senses.wake_word_detector import WakeWordDetector


def main() -> int:
    cfg = Config.load()
    print("Wake debug")
    print(f"- model: {cfg.wake_word_model}")
    print(f"- threshold: {cfg.wake_word_threshold}")
    print(f"- mic_name: {cfg.mic_name!r}")
    print(f"- mic_sample_rate: {cfg.mic_sample_rate}")
    print("Say the wake phrase now. Press Ctrl+C to stop.\n")

    detector = WakeWordDetector(
        model_path=cfg.wake_word_model,
        threshold=cfg.wake_word_threshold,
        mic_sample_rate=cfg.mic_sample_rate,
        mic_name=cfg.mic_name,
    )

    def _on_wake():
        print("\nDETECTED wake word!\n")

    detector.start(callback=_on_wake)
    try:
        while True:
            scores = detector.get_last_scores()
            if scores:
                best = max(scores.items(), key=lambda kv: kv[1])
                print(f"best={best[0]} score={best[1]:.3f}", end="\r", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        detector.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

