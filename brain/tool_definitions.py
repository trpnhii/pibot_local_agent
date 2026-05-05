"""
Tool definitions for Qwen2.5 function calling.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time and date. Use when user asks what time/date it is.",
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
            "description": "Get current weather information for a location. Use when user asks about weather, temperature, or conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name or location (e.g., 'London', 'New York', 'Tokyo'). If not specified, use default location."
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
            "description": "Get top news headlines. Use when user asks about news, headlines, or what's happening.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "News category: business, entertainment, health, science, sports, or technology. Leave empty for general news."
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
            "description": "Get the assistant's system health status (CPU temp, memory, uptime). Use when user asks system status or health check.",
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
            "description": "Tell a random joke. Use when user asks for a joke or something funny.",
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
            "description": "Hand off complex queries to cloud AI for better answers. Use for creative writing, complex reasoning, coding, deep knowledge, nuanced responses.",
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
Reply in English.

IMPORTANT RULES:
1. For simple greetings, casual chat, and basic questions - respond directly without using tools
2. For time/date questions - use get_current_time
3. For weather questions - use get_weather
4. For news/headlines questions - use get_news
5. For system status or "how are you doing" questions about yourself - use get_system_status
6. For jokes or humor requests - use get_joke
7. For complex questions requiring detailed knowledge, creative tasks, or coding - use cloud_handoff

Keep responses concise and conversational since they will be spoken aloud. Avoid long lists or complex formatting."""
