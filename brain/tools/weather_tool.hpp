#pragma once

#include <string>

namespace brain::tools {

class WeatherTool {
 public:
  explicit WeatherTool(std::string api_key);
  std::string GetWeather(const std::string& location) const;

 private:
  std::string api_key_;
};

}  // namespace brain::tools
