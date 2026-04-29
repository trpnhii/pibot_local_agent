#include "brain/cloud_client.hpp"

#include <fstream>
#include <sstream>

namespace brain {

KimiClient::KimiClient(std::string api_key, std::string soul_path) : api_key_(std::move(api_key)) {
  if (!soul_path.empty()) {
    std::ifstream in(soul_path);
    std::ostringstream ss;
    ss << in.rdbuf();
    soul_prompt_ = ss.str();
  }
}

std::string KimiClient::Chat(const std::string& query, bool /*stream*/) const {
  if (api_key_.empty()) {
    return "Sorry, cloud AI is not configured.";
  }
  if (!soul_prompt_.empty()) {
    return "Cloud response (C++ placeholder): " + query;
  }
  return "Cloud response: " + query;
}

}  // namespace brain
