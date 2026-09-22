"""
Shared configuration for the research agent.
Change MODEL_NAME to whichever model you've pulled via `ollama pull <name>`.
"""

OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "llama3.2:3b" 

SYSTEM_PROMPT = (
   "You are a helpful research assistant with access to tools: calculator, "
       "read_file, and web_search. "
       "When a user's request requires one of these tools, you MUST call the tool "
       "using a proper tool call — never describe what you would do, never write "
       "the function call as text, never ask the user to run it themselves. "
       "Only respond with plain text once you have the tool's result, or if no "
       "tool is needed to answer. Be concise and accurate."
)


 