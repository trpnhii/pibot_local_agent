#pragma once

#include <nlohmann/json.hpp>

#include <string>
#include <vector>

namespace brain {

struct ToolCall {
  std::string name;
  nlohmann::json arguments = nlohmann::json::object();
};

struct ChatResponse {
  std::string content;
  std::vector<ToolCall> tool_calls;
  bool is_tool_call = false;
};

class OllamaClient {
 public:
  explicit OllamaClient(std::string model = "qwen2.5:1.5b", std::string base_url = "http://localhost:11434");

  ChatResponse Chat(const nlohmann::json& messages, const nlohmann::json* tools = nullptr) const;
  bool IsAvailable() const;

 private:
  std::string model_;
  std::string base_url_;
};

}  // namespace brain
