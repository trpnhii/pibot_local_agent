#pragma once

#include <string>

namespace brain::tools {

class NewsTool {
 public:
  explicit NewsTool(std::string api_key);
  std::string GetNews(const std::string& category) const;

 private:
  std::string api_key_;
};

}  // namespace brain::tools
