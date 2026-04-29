#include "brain/router.hpp"

#include <algorithm>
#include <regex>

#include "brain/tool_definitions.hpp"

namespace brain {
namespace {
const std::vector<std::string> kTimePhrases = {"what time", "what's the time", "current time", "what day is it", "what's the date", "what date", "may gio", "bay gio la may gio", "hom nay ngay may"};
const std::vector<std::string> kWeatherPhrases = {"weather in", "weather for", "what's the weather", "how's the weather", "temperature in", "weather now", "weather today", "thoi tiet", "nhiet do", "thoi tiet o", "hom nay troi"};
const std::vector<std::string> kNewsPhrases = {"news", "headlines", "what's happening", "whats happening", "current events", "top stories", "tin tuc", "thoi su", "tin moi"};
const std::vector<std::string> kSystemPhrases = {"system status", "how are you doing", "how are you feeling", "your temperature", "cpu temp", "health check", "how's your health", "how you doing", "tinh trang he thong", "trang thai he thong", "suc khoe he thong"};
const std::vector<std::string> kJokePhrases = {"tell me a joke", "joke", "make me laugh", "something funny", "say something funny", "ke chuyen cuoi", "ke mot cau dua", "lam toi cuoi"};
const std::vector<std::string> kLocalPhrases = {"hello", "hi", "hey", "good morning", "good afternoon", "good evening", "how are you", "what's up", "who are you", "what are you", "what's your name", "thank you", "thanks", "bye", "goodbye", "see you", "good night", "help", "what can you do", "xin chao", "chao", "ban la ai", "cam on", "tam biet", "ban khoe khong"};
}  // namespace

Router::Router(OllamaClient client) : client_(std::move(client)) {}

std::string Router::ToLower(std::string value) {
  std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return value;
}

bool Router::IsLocalChat(const std::string& user_input) const {
  const std::string user_lower = ToLower(user_input);
  for (const auto& phrase : kLocalPhrases) {
    if (user_lower.find(phrase) != std::string::npos) return true;
  }
  size_t words = 0;
  bool in_word = false;
  for (char c : user_lower) {
    if (std::isspace(static_cast<unsigned char>(c))) {
      in_word = false;
    } else if (!in_word) {
      in_word = true;
      ++words;
    }
  }
  return words <= 3 && user_input.find('?') == std::string::npos;
}

std::string Router::ExtractNewsCategory(const std::string& user_input) const {
  const std::string lower = ToLower(user_input);
  if (lower.find("tech") != std::string::npos) return "technology";
  if (lower.find("cong nghe") != std::string::npos) return "technology";
  if (lower.find("sport") != std::string::npos) return "sports";
  if (lower.find("the thao") != std::string::npos) return "sports";
  if (lower.find("medical") != std::string::npos) return "health";
  if (lower.find("suc khoe") != std::string::npos) return "health";
  if (lower.find("kinh doanh") != std::string::npos) return "business";
  if (lower.find("giai tri") != std::string::npos) return "entertainment";
  if (lower.find("khoa hoc") != std::string::npos) return "science";
  for (const auto& c : {"business", "entertainment", "health", "science", "sports", "technology"}) {
    if (lower.find(c) != std::string::npos) return c;
  }
  return "";
}

std::string Router::ExtractLocation(const std::string& user_input, const std::string& response_text) const {
  std::smatch m;
  std::regex response_pattern(R"(location["\s=:]+["']*([^"'\\]\s,]+))", std::regex::icase);
  if (std::regex_search(response_text, m, response_pattern) && m.size() > 1) return m[1].str();

  const std::vector<std::regex> patterns = {
      std::regex(R"(weather (?:in|for|at) ([A-Za-z\s]+))"),
      std::regex(R"(in ([A-Za-z]+))"),
      std::regex(R"(thoi tiet (?:o|tai) ([\w\s]+))"),
      std::regex(R"(([A-Z][a-z]+(?:\s[A-Z][a-z]+)*))")};
  for (const auto& p : patterns) {
    if (std::regex_search(user_input, m, p) && m.size() > 1) {
      std::string loc = m[1].str();
      const std::string lower = ToLower(loc);
      if (lower != "the" && lower != "is" && lower != "it" && lower != "what" && lower != "how" && lower != "like") return loc;
    }
  }
  return "";
}

std::pair<ToolType, nlohmann::json> Router::DetectToolFromText(const std::string& user_input, const std::string& response_text) const {
  const std::string user_lower = ToLower(user_input);
  const std::string response_lower = ToLower(response_text);
  if (response_lower.find("get_current_time") != std::string::npos) return {ToolType::kTime, nlohmann::json::object()};
  if (response_lower.find("get_weather") != std::string::npos) return {ToolType::kWeather, {{"location", ExtractLocation(user_input, response_text)}}};
  if (response_lower.find("get_news") != std::string::npos) return {ToolType::kNews, {{"category", ExtractNewsCategory(user_input)}}};
  if (response_lower.find("get_system_status") != std::string::npos) return {ToolType::kSystemStatus, nlohmann::json::object()};
  if (response_lower.find("get_joke") != std::string::npos) return {ToolType::kJoke, nlohmann::json::object()};
  if (response_lower.find("cloud_handoff") != std::string::npos) return {ToolType::kCloud, {{"query", user_input}}};

  for (const auto& p : kTimePhrases) if (user_lower.find(p) != std::string::npos) return {ToolType::kTime, nlohmann::json::object()};
  for (const auto& p : kWeatherPhrases) if (user_lower.find(p) != std::string::npos) return {ToolType::kWeather, {{"location", ExtractLocation(user_input, "")}}};
  for (const auto& p : kNewsPhrases) if (user_lower.find(p) != std::string::npos) return {ToolType::kNews, {{"category", ExtractNewsCategory(user_input)}}};
  for (const auto& p : kJokePhrases) if (user_lower.find(p) != std::string::npos) return {ToolType::kJoke, nlohmann::json::object()};
  for (const auto& p : kSystemPhrases) if (user_lower.find(p) != std::string::npos) return {ToolType::kSystemStatus, nlohmann::json::object()};
  if (IsLocalChat(user_input)) return {ToolType::kNone, nlohmann::json::object()};
  return {ToolType::kCloud, {{"query", user_input}}};
}

RouterResult Router::Route(const std::string& user_input) {
  nlohmann::json messages = nlohmann::json::array();
  messages.push_back({{"role", "system"}, {"content", SystemPrompt()}});
  const size_t start = conversation_history_.size() > 8 ? (conversation_history_.size() - 8) : 0;
  for (size_t i = start; i < conversation_history_.size(); ++i) messages.push_back(conversation_history_[i]);
  messages.push_back({{"role", "user"}, {"content", user_input}});

  const ChatResponse response = client_.Chat(messages, &Tools());
  conversation_history_.push_back({{"role", "user"}, {"content", user_input}});

  if (response.is_tool_call && !response.tool_calls.empty()) {
    const auto& call = response.tool_calls.front();
    ToolType t = ToolType::kNone;
    if (call.name == "get_current_time") t = ToolType::kTime;
    else if (call.name == "get_weather") t = ToolType::kWeather;
    else if (call.name == "get_news") t = ToolType::kNews;
    else if (call.name == "get_system_status") t = ToolType::kSystemStatus;
    else if (call.name == "get_joke") t = ToolType::kJoke;
    else if (call.name == "cloud_handoff") t = ToolType::kCloud;
    RouterResult result;
    result.tool = t;
    result.response = "";
    result.arguments = call.arguments;
    return result;
  }

  auto [tool, args] = DetectToolFromText(user_input, response.content);
  if (tool == ToolType::kNone) {
    conversation_history_.push_back({{"role", "assistant"}, {"content", response.content}});
    RouterResult result;
    result.tool = ToolType::kNone;
    result.response = response.content;
    result.arguments = nlohmann::json::object();
    return result;
  }
  RouterResult result;
  result.tool = tool;
  result.response = "";
  result.arguments = args;
  return result;
}

void Router::ClearHistory() {
  conversation_history_ = nlohmann::json::array();
}

}  // namespace brain
