"""
Week 3 — Multi-step planning agent.

Same core loop as Week 2 (send -> check tool_calls -> execute -> feed back -> repeat),
but built for tasks that need SEVERAL steps toward one goal, not just one tool call.

Example task this week is designed for:
    "Research the current state of open-weight LLMs and write a 200-word
     summary with sources to report.md"

That requires: search (maybe more than once) -> synthesize -> write_file.
The model has to sequence these itself -- we just raise the round cap and give
it explicit planning instructions in the system prompt.

Run:
    python src/week3_agent.py
"""

import sys

import re

import requests
from rich.console import Console

from config import OLLAMA_BASE_URL, MODEL_NAME
from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

console = Console()

URL_PATTERN = re.compile(r"https?://[^\s)\]]+")

# Multi-step tasks legitimately need more rounds than a single tool lookup.
# Still capped -- an ungrounded model can loop forever without this.
MAX_TOOL_LOOPS = 8

PLANNING_SYSTEM_PROMPT = (
    "You are a research assistant that completes multi-step tasks using tools: "
    "calculator, read_file, write_file, and web_search.\n\n"
    "For any non-trivial request:\n"
    "1. Briefly state your plan in 1-2 sentences before acting.\n"
    "2. Use tools one step at a time to gather what you need. You may need to "
    "search more than once if the first results aren't enough.\n"
    "3. Once you have enough information, either answer directly or use "
    "write_file if the user asked you to save/write output. Compose your full, "
    "final synthesized answer FIRST -- then use write_file with that exact "
    "same text as the content. Never write a rough draft to a file and then "
    "give a better answer afterward in chat -- the file content and your "
    "final answer must match.\n"
    "4. Do not call a tool for things you already know or that don't need one.\n"
    "5. When you are done, give a clear final answer summarizing what you did.\n\n"
    "GROUNDING RULES (critical):\n"
    "- When you use web_search, your final answer and any file you write MUST "
    "be based ONLY on the actual search results returned -- not on what you "
    "already believe or assume about the topic. Do not blend in prior "
    "knowledge that isn't backed by the search results.\n"
    "- If the search results don't clearly answer the question, say so "
    "explicitly rather than filling the gap with a guess.\n"
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


def chat_with_tools(messages: list[dict]) -> dict:
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "stream": False,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["message"]


def run_agent_turn(messages: list[dict]) -> str:
    seen_urls = set()  # every URL that actually came back from a tool this turn

    for loop_count in range(MAX_TOOL_LOOPS):
        message = chat_with_tools(messages)
        tool_calls = message.get("tool_calls")

        # Some models put reasoning/plan text in `content` alongside the tool
        # call itself -- print it when present, it's useful transparency into
        # what the model is "thinking" before acting.
        if message.get("content"):
            console.print(f"[dim italic]  (model: {message['content'][:200]})[/dim italic]")

        if not tool_calls:
            messages.append(message)
            return message.get("content", "")

        messages.append(message)
        console.print(f"[dim]  (round {loop_count + 1}: {len(tool_calls)} tool call(s))[/dim]")

        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = call["function"].get("arguments", {})
            console.print(f"[yellow]  -> {fn_name}({fn_args})[/yellow]")

            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn is None:
                result = f"Error: unknown tool '{fn_name}'"
            else:
                try:
                    result = fn(**fn_args)
                except Exception as e:
                    result = f"Error running {fn_name}: {e}"

            # Record any real URLs this tool actually returned (mainly web_search)
            seen_urls.update(URL_PATTERN.findall(str(result)))

            # Safety net: if the model is writing a file, check any URLs it
            # included against URLs we've actually seen from tools. Prompt
            # instructions alone don't reliably stop fabrication -- this catches
            # it even when the prompt fails to.
            if fn_name == "write_file":
                written_content = fn_args.get("content", "")
                written_urls = set(URL_PATTERN.findall(written_content))
                fake_urls = written_urls - seen_urls
                if fake_urls:
                    console.print(
                        f"[bold red]  !! WARNING: file contains {len(fake_urls)} URL(s) "
                        f"not seen in any tool result (likely fabricated): {fake_urls}[/bold red]"
                    )
                if len(written_content.strip()) < 40:
                    console.print(
                        f"[bold red]  !! WARNING: write_file content is only "
                        f"{len(written_content.strip())} chars -- likely a placeholder, "
                        f"not real content: '{written_content}'[/bold red]"
                    )

            # Truncate what we print (not what we send to the model) so long
            # search/file results don't flood your terminal
            preview = str(result)[:150]
            console.print(f"[dim]     result: {preview}{'...' if len(str(result)) > 150 else ''}[/dim]")

            messages.append({"role": "tool", "content": str(result)})

    return f"(Stopped after {MAX_TOOL_LOOPS} rounds without a final answer. Task may be too complex or the model got stuck.)"


def main():
    console.print(f"[bold cyan]Research Agent — Week 3 (model: {MODEL_NAME}, multi-step)[/bold cyan]")
    console.print("Try: 'research the current state of open-weight LLMs and write a 150-word summary to report.md'\n")

    messages = [{"role": "system", "content": PLANNING_SYSTEM_PROMPT}]

    while True:
        try:
            user_input = console.input("[bold green]you>[/bold green] ")
        except (KeyboardInterrupt, EOFError):
            console.print("\nExiting.")
            break

        if user_input.strip().lower() in {"exit", "quit"}:
            break
        if not user_input.strip():
            continue

        messages.append({"role": "user", "content": user_input})

        try:
            answer = run_agent_turn(messages)
        except requests.exceptions.ConnectionError:
            console.print("[bold red]Could not reach Ollama.[/bold red] Is it running?")
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            console.print(f"[bold red]Ollama returned an error:[/bold red] {e}")
            sys.exit(1)

        console.print(f"\n[bold magenta]agent>[/bold magenta] {answer}\n")


if __name__ == "__main__":
    main()