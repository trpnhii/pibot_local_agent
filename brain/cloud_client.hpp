#pragma once

#include <string>

namespace brain {

class KimiClient {
 public:
  KimiClient(std::string api_key, std::string soul_path = "");
  std::string Chat(const std::string& query, bool stream = false) const;

 private:
  std::string api_key_;
  std::string soul_prompt_;
};

}  // namespace brain
