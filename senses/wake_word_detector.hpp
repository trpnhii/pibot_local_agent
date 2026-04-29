#pragma once

#include <atomic>
#include <functional>
#include <string>

namespace senses {

class WakeWordDetector {
 public:
  WakeWordDetector(std::string model_path, double threshold, int mic_sample_rate);
  void Start(const std::function<void()>& callback);
  void Stop();
  void Pause();
  void Resume();

 private:
  std::string model_path_;
  double threshold_;
  int mic_sample_rate_;
  std::atomic<bool> paused_{false};
};

}  // namespace senses
