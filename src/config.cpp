#include "config.hpp"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>

#include <nlohmann/json.hpp>

namespace {

std::string Trim(const std::string& input) {
  const auto first = std::find_if_not(input.begin(), input.end(), [](unsigned char c) {
    return std::isspace(c) != 0;
  });
  const auto last = std::find_if_not(input.rbegin(), input.rend(), [](unsigned char c) {
    return std::isspace(c) != 0;
  }).base();
  if (first >= last) {
    return "";
  }
  return std::string(first, last);
}

void SetEnvVar(const std::string& key, const std::string& value) {
#if defined(_WIN32)
  _putenv_s(key.c_str(), value.c_str());
#else
  setenv(key.c_str(), value.c_str(), 1);
#endif
}

std::string GetEnvOr(const char* name, const std::string& fallback) {
  const char* value = std::getenv(name);
  return value != nullptr ? std::string(value) : fallback;
}

void LoadEnvFile(const std::string& path) {
  std::ifstream env_file(path);
  std::string line;
  while (std::getline(env_file, line)) {
    line = Trim(line);
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const auto split_pos = line.find('=');
    if (split_pos == std::string::npos) {
      continue;
    }
    const std::string key = Trim(line.substr(0, split_pos));
    const std::string value = Trim(line.substr(split_pos + 1));
    if (!key.empty()) {
      SetEnvVar(key, value);
    }
  }
}

void ApplyJsonIfPresent(const nlohmann::json& data, Config& config) {
  auto set_string = [&data](const char* key, std::string& field) {
    if (data.contains(key) && data[key].is_string()) {
      field = data[key].get<std::string>();
    }
  };
  auto set_int = [&data](const char* key, int& field) {
    if (data.contains(key) && data[key].is_number_integer()) {
      field = data[key].get<int>();
    }
  };
  auto set_bool = [&data](const char* key, bool& field) {
    if (data.contains(key) && data[key].is_boolean()) {
      field = data[key].get<bool>();
    }
  };
  auto set_double = [&data](const char* key, double& field) {
    if (data.contains(key) && data[key].is_number()) {
      field = data[key].get<double>();
    }
  };

  set_string("project_root", config.project_root);
  set_string("assets_path", config.assets_path);
  set_string("piper_voice", config.piper_voice);
  set_string("whisper_path", config.whisper_path);
  set_string("whisper_model", config.whisper_model);
  set_string("chat_model", config.chat_model);
  set_string("wake_word_model", config.wake_word_model);
  set_double("wake_word_threshold", config.wake_word_threshold);
  set_int("mic_sample_rate", config.mic_sample_rate);
  set_int("target_sample_rate", config.target_sample_rate);
  set_string("local_location", config.local_location);
  set_string("openweather_api_key", config.openweather_api_key);
  set_string("moonshot_api_key", config.moonshot_api_key);
  set_string("newsapi_key", config.newsapi_key);
  set_string("local_soul_path", config.local_soul_path);
  set_string("cloud_soul_path", config.cloud_soul_path);
  set_int("display_width", config.display_width);
  set_int("display_height", config.display_height);
  set_bool("use_framebuffer", config.use_framebuffer);
  set_bool("enable_streaming_tts", config.enable_streaming_tts);
  set_bool("enable_ui", config.enable_ui);
}

}  // namespace

Config Config::Load(const std::optional<std::string>& config_path) {
  Config config;

  // Keep Python parity: default config path is project_root/config/config.json.
  std::string resolved_config_path =
      config_path.has_value() ? *config_path : (config.project_root + "/config/config.json");

  if (std::filesystem::exists(resolved_config_path)) {
    std::ifstream config_file(resolved_config_path);
    nlohmann::json data = nlohmann::json::parse(config_file, nullptr, true, true);
    ApplyJsonIfPresent(data, config);
  }

  // Keep Python parity: .env resolved from config.project_root after JSON is applied.
  const std::string env_path = config.project_root + "/.env";
  if (std::filesystem::exists(env_path)) {
    LoadEnvFile(env_path);
  }

  // Env vars override all previous sources.
  config.openweather_api_key = GetEnvOr("OPENWEATHER_API_KEY", config.openweather_api_key);
  config.moonshot_api_key = GetEnvOr("MOONSHOT_API_KEY", config.moonshot_api_key);
  config.newsapi_key = GetEnvOr("NEWSAPI_KEY", config.newsapi_key);

  return config;
}

std::string Config::ToDebugString() const {
  std::ostringstream out;
  out << "Config{\n";
  out << "  project_root: " << project_root << "\n";
  out << "  assets_path: " << assets_path << "\n";
  out << "  piper_voice: " << piper_voice << "\n";
  out << "  whisper_path: " << whisper_path << "\n";
  out << "  whisper_model: " << whisper_model << "\n";
  out << "  chat_model: " << chat_model << "\n";
  out << "  wake_word_model: " << wake_word_model << "\n";
  out << "  wake_word_threshold: " << wake_word_threshold << "\n";
  out << "  mic_sample_rate: " << mic_sample_rate << "\n";
  out << "  target_sample_rate: " << target_sample_rate << "\n";
  out << "  local_location: " << local_location << "\n";
  out << "  local_soul_path: " << local_soul_path << "\n";
  out << "  cloud_soul_path: " << cloud_soul_path << "\n";
  out << "  display_width: " << display_width << "\n";
  out << "  display_height: " << display_height << "\n";
  out << "  use_framebuffer: " << (use_framebuffer ? "true" : "false") << "\n";
  out << "  enable_streaming_tts: " << (enable_streaming_tts ? "true" : "false") << "\n";
  out << "  enable_ui: " << (enable_ui ? "true" : "false") << "\n";
  out << "  openweather_api_key_set: " << (!openweather_api_key.empty() ? "yes" : "no") << "\n";
  out << "  moonshot_api_key_set: " << (!moonshot_api_key.empty() ? "yes" : "no") << "\n";
  out << "  newsapi_key_set: " << (!newsapi_key.empty() ? "yes" : "no") << "\n";
  out << "}\n";
  return out.str();
}
