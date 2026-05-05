"""
Tool definitions for Qwen2.5 function calling.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time and date. (VI: lấy giờ và ngày hiện tại) Use when user asks what time/date it is / 'mấy giờ' / 'hôm nay ngày mấy'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather information for a location. (VI: tra thời tiết/nhiệt độ) Use when user asks about weather, temperature, conditions / 'thời tiết' / 'nhiệt độ'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g., 'London', 'New York', 'Tokyo'). VI: tên thành phố/địa điểm. If not specified, use default location."
                    }
                },
                "required": ["location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Get top news headlines. (VI: lấy tin tức nổi bật) Use when user asks about news/headlines / 'tin tức' / 'thời sự'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: business, entertainment, health, science, sports, or technology. VI: chủ đề tin. Leave empty for general news."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Get the assistant's system health status (CPU temp, memory, uptime). (VI: trạng thái hệ thống) Use when user asks system status / 'trạng thái hệ thống' / 'bạn khỏe không'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_joke",
            "description": "Tell a random joke. (VI: kể chuyện cười) Use when user asks for a joke / 'kể chuyện cười' / 'làm tôi cười'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cloud_handoff",
            "description": "Hand off complex queries to cloud AI for better answers. (VI: chuyển câu hỏi khó lên cloud) Use for creative writing, complex reasoning, coding, deep knowledge, nuanced responses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The full user query to send to cloud AI"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# System prompt for the router
SYSTEM_PROMPT = """You are Jansky, a helpful voice assistant running on a Raspberry Pi. You have access to tools for specific tasks.
You must understand both Vietnamese and English. If the user speaks Vietnamese, reply in Vietnamese.

IMPORTANT RULES:
1. For simple greetings, casual chat, and basic questions - respond directly without using tools
2. For time/date questions - use get_current_time
3. For weather questions - use get_weather
4. For news/headlines questions - use get_news
5. For system status or "how are you doing" questions about yourself - use get_system_status
6. For jokes or humor requests - use get_joke
7. For complex questions requiring detailed knowledge, creative tasks, or coding - use cloud_handoff

Keep responses concise and conversational since they will be spoken aloud. Avoid long lists or complex formatting."""
