#include "senses/wake_word_detector.hpp"

namespace senses {

WakeWordDetector::WakeWordDetector(std::string model_path, double threshold, int mic_sample_rate)
    : model_path_(std::move(model_path)), threshold_(threshold), mic_sample_rate_(mic_sample_rate) {}

void WakeWordDetector::Start(const std::function<void()>& /*callback*/) {}
void WakeWordDetector::Stop() {}
void WakeWordDetector::Pause() { paused_ = true; }
void WakeWordDetector::Resume() { paused_ = false; }

}  // namespace senses
