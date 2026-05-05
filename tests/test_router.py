#!/usr/bin/env python3
"""
Test the router and LLM integration.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from brain.ollama_client import OllamaClient
from brain.router import Router, ToolType


def test_router():
    """Test routing decisions."""
    
    client = OllamaClient(model="qwen2.5:1.5b")
    
    if not client.is_available():
        print("X Ollama not running!")
        print("  Start with: ollama serve")
        return False
    
    print("OK Ollama is running")
    
    router = Router(client)
    
    test_cases = [
        # (input, expected_tool)
        ("Hello, how are you?", ToolType.NONE),
        ("What time is it?", ToolType.TIME),
        ("What's the weather in London?", ToolType.WEATHER),
        ("Write me a poem about stars", ToolType.CLOUD),
        ("Tell me a joke", ToolType.JOKE),

        # Vietnamese coverage (no diacritics to match STT outputs reliably)
        ("Bay gio la may gio?", ToolType.TIME),
        ("Hom nay ngay may?", ToolType.TIME),
        ("Thoi tiet o Ha Noi the nao?", ToolType.WEATHER),
        ("Nhiet do hom nay bao nhieu?", ToolType.WEATHER),
        ("Cho toi tin tuc moi", ToolType.NEWS),
        ("Tinh trang he thong the nao?", ToolType.SYSTEM_STATUS),
        ("Ke chuyen cuoi di", ToolType.JOKE),
        ("Viet giup toi mot bai tho ve tinh yeu", ToolType.CLOUD),
    ]
    
    print("\nTesting router decisions...\n")
    
    passed = 0
    for user_input, expected in test_cases:
        result = router.route(user_input)
        status = "OK" if result.tool == expected else "X"
        if result.tool == expected:
            passed += 1
        
        print(f"{status} Input: '{user_input}'")
        print(f"   Expected: {expected.value}, Got: {result.tool.value}")
        if result.response:
            print(f"   Response: {result.response[:80]}...")
        print()
    
    print(f"Router test complete: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_router()
    sys.exit(0 if success else 1)
