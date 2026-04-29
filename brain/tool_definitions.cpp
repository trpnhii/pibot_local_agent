#include "brain/tool_definitions.hpp"

namespace brain {

const nlohmann::json& Tools() {
  static const nlohmann::json kTools = nlohmann::json::parse(R"([
    {"type":"function","function":{"name":"get_current_time","description":"Get the current time and date. Use when user asks what time it is, what day it is, or current date.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"get_weather","description":"Get current weather information for a location. Use when user asks about weather, temperature, or conditions.","parameters":{"type":"object","properties":{"location":{"type":"string","description":"City name or location (e.g., 'London', 'New York', 'Tokyo'). If not specified, use 'current location'."}},"required":["location"]}}},
    {"type":"function","function":{"name":"get_news","description":"Get top news headlines. Use when user asks about news, headlines, or what's happening in the world.","parameters":{"type":"object","properties":{"category":{"type":"string","description":"News category: business, entertainment, health, science, sports, or technology. Leave empty for general news."}},"required":[]}}},
    {"type":"function","function":{"name":"get_system_status","description":"Get the assistant's system health status including CPU temperature, memory, uptime. Use when user asks how you are doing, system status, or health check.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"get_joke","description":"Tell a random joke. Use when user asks for a joke, wants to hear something funny, or asks you to make them laugh.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"cloud_handoff","description":"Hand off complex queries to cloud AI for better answers. Use for: creative writing, complex reasoning, coding questions, detailed explanations, anything requiring deep knowledge or nuanced responses.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"The full user query to send to cloud AI"}},"required":["query"]}}}
  ])");
  return kTools;
}

const std::string& SystemPrompt() {
  static const std::string kPrompt =
      "You are Jansky, a helpful voice assistant running on a Raspberry Pi. You have access to tools for specific tasks.\n\n"
      "You must understand both Vietnamese and English. If the user speaks Vietnamese, reply in Vietnamese.\n\n"
      "IMPORTANT RULES:\n"
      "1. For simple greetings, casual chat, and basic questions - respond directly without using tools\n"
      "2. For time/date questions - use get_current_time\n"
      "3. For weather questions - use get_weather\n"
      "4. For news/headlines questions - use get_news\n"
      "5. For system status or \"how are you doing\" questions about yourself - use get_system_status\n"
      "6. For jokes or humor requests - use get_joke\n"
      "7. For complex questions requiring detailed knowledge, creative tasks, or coding - use cloud_handoff\n\n"
      "Keep responses concise and conversational since they will be spoken aloud. Avoid long lists or complex formatting.";
  return kPrompt;
}

}  // namespace brain
