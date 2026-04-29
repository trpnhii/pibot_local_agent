#include "brain/tools/weather_tool.hpp"

namespace brain::tools {

WeatherTool::WeatherTool(std::string api_key) : api_key_(std::move(api_key)) {}

std::string WeatherTool::GetWeather(const std::string& location) const {
  if (api_key_.empty()) return "Sorry, weather lookup is not configured.";
  return "Weather tool placeholder for " + location;
}

}  // namespace brain::tools
