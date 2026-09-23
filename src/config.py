"""
Shared configuration for the research agent.
"""

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2:3b"

# Simple system prompt, used by week1/week2. Week 3+ uses PLANNING_SYSTEM_PROMPT
# in agent_core.py instead (more detailed, tool-use + grounding rules).
SYSTEM_PROMPT = (
    "You are a helpful research assistant. Be concise and accurate. "
    "If you don't know something, say so instead of guessing."
)
 