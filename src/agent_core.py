"""
Core agent loop -- shared by the interactive CLI (week3_agent.py) and the
eval harness (evals/run_evals.py).

Why this file exists: Weeks 1-3 had the loop logic and the terminal printing
tangled together inside week3_agent.py. That's fine for a single script, but
it means the eval harness would've had to either duplicate the loop (bug-prone
-- fixes could drift out of sync) or scrape printed text to figure out what
happened (fragile). Instead, this module returns a structured trace of what
happened, and callers decide what to do with it: the CLI prints it nicely,
the eval harness runs automated checks against it.

Public API:
    run_agent_turn(messages, on_event=None) -> (final_answer: str, trace: list[dict])
"""

import re

import requests

from config import OLLAMA_BASE_URL, MODEL_NAME
from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

URL_PATTERN = re.compile(r"https?://[^\s)\]]+")
# Detects the model writing something like `write_file("x", "y")` as plain
# text instead of actually invoking the tool -- a real, observed failure mode.
PSEUDO_CALL_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(name) for name in TOOL_FUNCTIONS.keys()) + r")\s*\("
)
MAX_TOOL_LOOPS = 8
MAX_PSEUDO_CALL_RETRIES = 2  # cap on how many times we nudge a pseudo-call before giving up

PLANNING_SYSTEM_PROMPT = (
    "You are a research assistant that completes multi-step tasks using tools: "
    "calculator, read_file, write_file, and web_search.\n\n"
    "For any non-trivial request:\n"
    "1. Briefly state your plan in 1-2 sentences before acting.\n"
    "2. Use tools one step at a time to gather what you need. You may need to "
    "search more than once if the first results aren't enough.\n"
    "3. Once you have enough information, either answer directly or use "
    "write_file if the user asked you to save/write output. Only call "
    "write_file when the user's CURRENT request explicitly asks you to "
    "write, save, or output to a named file -- do not call write_file for "
    "tasks that only ask you to summarize, explain, or answer a question. "
    "If the current request does ask for a file, you MUST call write_file "
    "before giving your final answer -- do not just describe the content in "
    "chat and skip the file. Compose your full, final synthesized answer "
    "FIRST -- then use write_file with that exact same text as the content. "
    "Never write a rough draft to a file and then give a better answer "
    "afterward in chat -- the file content and your final answer must "
    "match.\n"
    "4. Do not call a tool for things you already know or that don't need one.\n"
    "5. When you are done, give a clear final answer summarizing what you did.\n\n"
    "GROUNDING RULES (critical):\n"
    "- When you use web_search, your final answer and any file you write MUST "
    "be based ONLY on the actual search results returned -- not on what you "
    "already believe or assume about the topic. Do not blend in prior "
    "knowledge that isn't backed by the search results.\n"
    "- If the search results don't clearly answer the question, say so "
    "explicitly rather than filling the gap with a guess.\n"
    "- NEVER invent specific details (exact quantities, ingredients, numbers, "
    "names, dates) that are not actually present in the search results, even "
    "if a plausible-sounding answer would satisfy the user. It is always "
    "better to say the information isn't available than to guess "
    "confidently.\n"
    "- NEVER invent a URL. Only include a URL if it appears character-for-"
    "character in a tool result you actually received in this conversation. "
    "If you don't have a real URL from a tool result, write 'no source URL "
    "available' instead of making one up.\n"
    "- When forming a search query based on content from a file or earlier in "
    "the conversation, use specific keywords from that content (names, dates, "
    "topics) -- never search a single generic word like 'deadline' or 'report' "
    "on its own.\n"
    "- Write the content of write_file AFTER you have seen the search results, "
    "reflecting what they actually said -- never write generic/textbook-style "
    "definitions instead of the retrieved information. File content should be "
    "substantive, not a placeholder word.\n\n"
    "Never describe a tool call as text -- always use a real tool call."
)


def chat_with_tools(messages: list[dict], temperature: float | None = None) -> dict:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "tools": TOOL_SCHEMAS,
        "stream": False,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}

    response = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=240)
    response.raise_for_status()
    return response.json()["message"]


def run_agent_turn(messages: list[dict], on_event=None, temperature: float | None = None) -> tuple[str, list[dict]]:
    """
    Runs the tool-calling loop for one user turn.

    on_event(dict), if given, is called for each notable event (a tool call,
    a warning, a model "thinking out loud" note) so a caller can display or
    log progress without this function knowing anything about the display.

    temperature: pass a low value (e.g. 0.1) for more deterministic behavior
    during evals. Leave as None for the interactive CLI's normal behavior.

    Returns (final_answer, trace) where trace is the full list of events --
    this is what the eval harness runs its checks against.
    """

    def emit(event):
        if on_event:
            on_event(event)

    seen_urls = set()
    trace = []
    pseudo_call_retries = 0

    for loop_count in range(MAX_TOOL_LOOPS):
        message = chat_with_tools(messages, temperature=temperature)
        tool_calls = message.get("tool_calls")

        if message.get("content"):
            emit({"type": "model_note", "content": message["content"]})

        if not tool_calls:
            content = message.get("content", "")
            if content and PSEUDO_CALL_PATTERN.search(content) and pseudo_call_retries < MAX_PSEUDO_CALL_RETRIES:
                # Model wrote something like `write_file("x", "y")` as plain
                # text instead of using the real tool-calling mechanism.
                # Nudge it and let it retry -- but only up to a cap, so a
                # model that keeps failing this doesn't burn the entire round
                # budget on retries instead of ever finishing.
                pseudo_call_retries += 1
                emit({
                    "type": "warning",
                    "message": f"model wrote a tool call as text instead of calling it -- "
                               f"retrying ({pseudo_call_retries}/{MAX_PSEUDO_CALL_RETRIES})",
                })
                messages.append(message)
                messages.append({
                    "role": "user",
                    "content": (
                        "You wrote a tool call as plain text instead of actually invoking it. "
                        "Use the real tool-calling mechanism now, not text that looks like a "
                        "function call."
                    ),
                })
                continue

            messages.append(message)
            return content, trace

        messages.append(message)
        emit({"type": "round", "round": loop_count + 1, "n_calls": len(tool_calls)})

        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = call["function"].get("arguments", {})

            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn is None:
                result = f"Error: unknown tool '{fn_name}'"
            else:
                try:
                    result = fn(**fn_args)
                except Exception as e:
                    result = f"Error running {fn_name}: {e}"

            seen_urls.update(URL_PATTERN.findall(str(result)))

            event = {
                "type": "tool_call",
                "name": fn_name,
                "args": fn_args,
                "result": str(result),
            }

            # Safety-net checks, attached directly to the event so the eval
            # harness can key off them without re-deriving the logic.
            if fn_name == "write_file":
                written_content = fn_args.get("content", "")
                written_urls = set(URL_PATTERN.findall(written_content))
                fake_urls = written_urls - seen_urls
                if fake_urls:
                    event["fabricated_urls"] = list(fake_urls)
                    emit({"type": "warning", "message": f"fabricated URLs: {fake_urls}"})
                if len(written_content.strip()) < 40:
                    event["placeholder_warning"] = True
                    emit({
                        "type": "warning",
                        "message": f"placeholder content ({len(written_content.strip())} chars)",
                    })

            trace.append(event)
            emit(event)

            messages.append({"role": "tool", "content": str(result)})

    return (
        f"(Stopped after {MAX_TOOL_LOOPS} rounds without a final answer.)",
        trace,
    )