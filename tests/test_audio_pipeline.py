#!/usr/bin/env python3
"""
Test the complete audio pipeline.
"""

import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_tts():
    """Test text-to-speech."""
    try:
        from audio.tts_engine import PiperTTS
        from audio.audio_manager import AudioManager
        from config import Config
    except ModuleNotFoundError as e:
        print(f"SKIP TTS (missing dependency): {e}")
        return True
    
    print("Testing TTS...")
    
    try:
        cfg = Config.load()
        tts = PiperTTS(model_path=cfg.piper_voice)
        text = "Xin chào! Mình là Jansky, trợ lý của bạn." if cfg.assistant_language.startswith("vi") else "Hello! I am Jansky, your personal assistant."
        audio_path = tts.synthesize(text)
        
        audio = AudioManager()
        audio.play_wav(audio_path)
        print("OK TTS working")
        return True
    except Exception as e:
        print(f"X TTS failed: {e}")
        return False


def test_stt():
    """Test speech-to-text."""
    try:
        from audio.audio_manager import AudioManager
        from audio.stt_engine import WhisperSTT
        from config import Config
    except ModuleNotFoundError as e:
        print(f"SKIP STT (missing dependency): {e}")
        return True
    
    print("\nTesting STT...")
    print("Speak now... (recording for up to 10 seconds)")
    
    try:
        audio = AudioManager()
        recording = audio.record_until_silence(max_duration=10.0)
        
        if recording is None or len(recording) == 0:
            print("X No audio recorded")
            return False
        
        cfg = Config.load()
        stt = WhisperSTT(whisper_path=cfg.whisper_path, model_path=cfg.whisper_model, language=cfg.stt_language)
        text = stt.transcribe_audio_array(recording)
        print(f"OK Transcribed: {text}")
        return True
    except Exception as e:
        print(f"X STT failed: {e}")
        return False


def test_round_trip():
    """Test full round-trip: speak -> transcribe -> speak back."""
    try:
        from audio.audio_manager import AudioManager
        from audio.tts_engine import PiperTTS
        from audio.stt_engine import WhisperSTT
        from config import Config
    except ModuleNotFoundError as e:
        print(f"SKIP Round-trip (missing dependency): {e}")
        return True
    
    print("\nTesting round-trip...")
    print("Say something, I'll repeat it back...")
    
    try:
        audio = AudioManager()
        cfg = Config.load()
        tts = PiperTTS(model_path=cfg.piper_voice)
        stt = WhisperSTT(whisper_path=cfg.whisper_path, model_path=cfg.whisper_model, language=cfg.stt_language)
        
        # Record
        recording = audio.record_until_silence()
        if recording is None:
            print("X No audio recorded")
            return False
        
        # Transcribe
        text = stt.transcribe_audio_array(recording)
        print(f"You said: {text}")
        
        # Speak back
        response = f"Bạn nói: {text}" if cfg.assistant_language.startswith("vi") else f"You said: {text}"
        audio_path = tts.synthesize(response)
        audio.play_wav(audio_path)
        
        print("OK Round-trip complete")
        return True
    except Exception as e:
        print(f"X Round-trip failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    results.append(("TTS", test_tts()))
    results.append(("STT", test_stt()))
    results.append(("Round-trip", test_round_trip()))
    
    print("\n" + "="*40)
    print("Results:")
    for name, passed in results:
        status = "OK PASS" if passed else "X FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    sys.exit(0 if all_passed else 1)
