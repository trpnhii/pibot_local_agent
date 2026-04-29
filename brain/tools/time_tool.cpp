#include "brain/tools/time_tool.hpp"

#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

namespace brain::tools {

std::string GetCurrentTime() {
  const auto now = std::chrono::system_clock::now();
  const std::time_t raw = std::chrono::system_clock::to_time_t(now);
  std::tm tm{};
#if defined(_WIN32)
  localtime_s(&tm, &raw);
#else
  localtime_r(&raw, &tm);
#endif
  std::ostringstream out;
  out << "It is " << std::put_time(&tm, "%I:%M %p on %A, %B %d.");
  return out.str();
}

}  // namespace brain::tools
