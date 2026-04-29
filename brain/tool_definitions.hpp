#pragma once

#include <nlohmann/json.hpp>
#include <string>

namespace brain {

const nlohmann::json& Tools();
const std::string& SystemPrompt();

}  // namespace brain
