#pragma once

namespace ui {

enum class UIState { kIdle, kListening, kThinking, kSpeaking, kError };

class UIManager {
 public:
  UIManager(int width, int height, bool use_framebuffer);
  void Start();
  void Stop();
  void SetState(UIState state);

 private:
  int width_;
  int height_;
  bool use_framebuffer_;
  UIState state_ = UIState::kIdle;
};

}  // namespace ui
