#include "brain/tools/news_tool.hpp"

namespace brain::tools {

NewsTool::NewsTool(std::string api_key) : api_key_(std::move(api_key)) {}

std::string NewsTool::GetNews(const std::string& category) const {
  if (api_key_.empty()) return "Sorry, news lookup is not configured.";
  if (category.empty()) return "News tool placeholder for general headlines.";
  return "News tool placeholder for " + category + ".";
}

}  // namespace brain::tools
