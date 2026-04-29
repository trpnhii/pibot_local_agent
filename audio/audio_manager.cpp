#include "audio/audio_manager.hpp"

#include <iostream>

namespace audio {

AudioManager::AudioManager(int sample_rate, int mic_sample_rate) : sample_rate_(sample_rate), mic_sample_rate_(mic_sample_rate) {}

std::vector<int16_t> AudioManager::RecordUntilSilence(double /*silence_duration*/, double /*max_duration*/) const {
  // Hardware capture should be plugged in with PortAudio/miniaudio for full parity.
  return {};
}

void AudioManager::PlayWav(const std::string& filepath) const {
  std::cout << "[audio] play wav: " << filepath << "\n";
}

}  // namespace audio
