#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace audio {

class WhisperSTT {
 public:
  WhisperSTT(std::string whisper_path, std::string model_path, std::string language = "en", int threads = 4);
  std::string Transcribe(const std::string& wav_path) const;
  std::string TranscribeAudioArray(const std::vector<int16_t>& audio, int sample_rate = 16000) const;

 private:
  std::string whisper_path_;
  std::string model_path_;
  std::string language_;
  int threads_;
};

}  // namespace audio
