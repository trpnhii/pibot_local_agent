#!/usr/bin/env python3
"""
Smoke test for Gemini cloud client.
"""

import sys
from pathlib import Path

# Add project root
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from brain.cloud_client import GeminiClient


def _read_env_value(env_path: Path, key: str) -> str:
    if not env_path.exists():
        return ""
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""


def test_gemini() -> bool:
    env_path = REPO_ROOT / ".env"
    api_key = _read_env_value(env_path, "GEMINI_API_KEY")
    if not api_key:
        print("SKIP Gemini (missing GEMINI_API_KEY in repo .env)")
        return True

    print("Testing Gemini client...")
    client = GeminiClient(
        api_key=api_key,
        soul_path=str(REPO_ROOT / "config" / "cloud_soul.md"),
        model="gemini-2.0-flash",
    )

    # Keep prompt short/cheap; verify non-empty output.
    prompt = "Tra loi bang tieng Viet: Hay noi 'OK' neu ban doc duoc tin nhan nay."
    try:
        text = client.chat(prompt, stream=False)
    except Exception as e:
        msg = str(e)
        # Quota/rate-limit is common on free tiers; treat as a skip.
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower():
            print("SKIP Gemini (quota/rate limit):", msg.splitlines()[0][:160])
            return True
        print("X Gemini request failed:", msg.splitlines()[0][:200])
        return False

    if not text.strip():
        print("X Gemini returned empty response")
        return False

    print("OK Gemini response:", text[:120].replace("\n", " "))
    return True


if __name__ == "__main__":
    ok = test_gemini()
    sys.exit(0 if ok else 1)

