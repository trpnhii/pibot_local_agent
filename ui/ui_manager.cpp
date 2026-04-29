#include "ui/ui_manager.hpp"

namespace ui {

UIManager::UIManager(int width, int height, bool use_framebuffer)
    : width_(width), height_(height), use_framebuffer_(use_framebuffer) {}

void UIManager::Start() {}
void UIManager::Stop() {}
void UIManager::SetState(UIState state) { state_ = state; }

}  // namespace ui
