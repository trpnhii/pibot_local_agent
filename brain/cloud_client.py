"""
Cloud API client for Gemini (Google AI).
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path
import os


class GeminiClient:
    """Client for Gemini API.

    Keeps a similar interface to the old Moonshot client:
      - chat(query, stream=False) -> str
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        soul_path: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key required (set GEMINI_API_KEY)")
        self.model = model
        
        # Load cloud soul/personality
        self.soul_prompt = ""
        if soul_path and Path(soul_path).exists():
            self.soul_prompt = Path(soul_path).read_text(encoding="utf-8")
    
    def chat(
        self,
        query: str,
        stream: bool = False,
    ) -> str:
        if stream:
            raise NotImplementedError("Streaming not implemented for Gemini client in this repo.")

        # Prefer the new official SDK. Keep import inside method so repo can run without it.
        try:
            from google import genai  # pylint: disable=import-error,no-name-in-module
        except Exception as e:
            raise RuntimeError(
                "Gemini SDK not installed. Install with: pip install google-genai"
            ) from e

        client = genai.Client(api_key=self.api_key)

        prompt = query
        if self.soul_prompt:
            prompt = f"{self.soul_prompt}\n\nUser: {query}"

        resp = client.models.generate_content(
            model=self.model,
            contents=prompt,
        )
        text = getattr(resp, "text", None)
        if not text:
            raise RuntimeError("Gemini returned empty response")
        return text.strip()


# Backwards-compatible alias (old name used across the repo)
KimiClient = GeminiClient
