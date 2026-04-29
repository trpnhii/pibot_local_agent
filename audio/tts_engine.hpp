#pragma once

#include <string>

namespace audio {

class PiperTTS {
 public:
  explicit PiperTTS(std::string model_path);
  std::string Synthesize(const std::string& text, const std::string& output_path = "") const;

 private:
  std::string model_path_;
};

}  // namespace audio
