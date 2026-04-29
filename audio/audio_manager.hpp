#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace audio {

class AudioManager {
 public:
  AudioManager(int sample_rate = 16000, int mic_sample_rate = 48000);
  std::vector<int16_t> RecordUntilSilence(double silence_duration = 1.5, double max_duration = 15.0) const;
  void PlayWav(const std::string& filepath) const;

 private:
  int sample_rate_;
  int mic_sample_rate_;
};

}  // namespace audio
