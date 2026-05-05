#!/usr/bin/env python3
"""
List Gemini models available for the current GEMINI_API_KEY.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))


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


def main() -> int:
    api_key = _read_env_value(REPO_ROOT / ".env", "GEMINI_API_KEY")
    if not api_key:
        print("Missing GEMINI_API_KEY in repo .env")
        return 1

    try:
        from google import genai  # pylint: disable=import-error,no-name-in-module
    except Exception as e:
        print("Gemini SDK not installed. Install with: pip install google-genai")
        print("Error:", str(e).splitlines()[0])
        return 1

    client = genai.Client(api_key=api_key)
    print("Models that support generateContent:\n")
    try:
        for m in client.models.list():
            name = getattr(m, "name", "") or ""
            supported = getattr(m, "supported_actions", None) or getattr(m, "supported_methods", None) or []
            if "generateContent" in supported:
                print("-", name.replace("models/", ""))
    except Exception as e:
        msg = str(e)
        print("Failed to list models:", msg.splitlines()[0][:220])
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

