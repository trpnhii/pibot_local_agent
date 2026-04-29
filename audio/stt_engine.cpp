#include "audio/stt_engine.hpp"

#include <sstream>

namespace audio {

WhisperSTT::WhisperSTT(std::string whisper_path, std::string model_path, std::string language, int threads)
    : whisper_path_(std::move(whisper_path)), model_path_(std::move(model_path)), language_(std::move(language)), threads_(threads) {}

std::string WhisperSTT::Transcribe(const std::string& wav_path) const {
  std::ostringstream out;
  out << "[stt placeholder] " << wav_path;
  return out.str();
}

std::string WhisperSTT::TranscribeAudioArray(const std::vector<int16_t>& /*audio*/, int /*sample_rate*/) const {
  return "";
}

}  // namespace audio
