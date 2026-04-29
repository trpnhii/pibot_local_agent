#include "audio/tts_engine.hpp"

namespace audio {

PiperTTS::PiperTTS(std::string model_path) : model_path_(std::move(model_path)) {}

std::string PiperTTS::Synthesize(const std::string& /*text*/, const std::string& output_path) const {
  if (!output_path.empty()) {
    return output_path;
  }
  return "tts_output.wav";
}

}  // namespace audio
