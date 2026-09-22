"""
Week 2 — Tool-calling agent loop (kept as-is for reference/progression).
Note: Week 3 onward refactors this loop into agent_core.py for reuse
across the CLI and eval harness — see src/agent_core.py.
"""






"""
Week 2 — Tool-calling agent loop.

Pattern:
    1. Send conversation + tool schemas to the model
    2. If the model responds with tool_calls -> execute each one -> append results
       as "tool" role messages -> call the model again
    3. If the model responds with plain content -> that's the final answer, stop
    4. Cap the number of loop iterations so a confused model can't loop forever

Run:
    python src/week2_agent.py

Note: not all models handle tool-calling reliably. Recommended for this week:
    MODEL_NAME = "llama3.2:3b"   (in config.py) — officially supports tool calling.
    llama3.2:1b's tool-calling is weak/inconsistent — fine for Week 1 chat speed,
    not ideal for testing this loop.
"""

import json
import sys

import requests
from rich.console import Console

from config import OLLAMA_BASE_URL, MODEL_NAME, SYSTEM_PROMPT
from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS

console = Console()

MAX_TOOL_LOOPS = 5  # safety cap: stop after this many tool-call rounds per user turn


def chat_with_tools(messages: list[dict]) -> dict:
    """Call Ollama's /api/chat with tool schemas attached. Returns the raw message dict."""
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
    """
    Handles one full user turn, including any number of tool-call round trips.
    Returns the final text answer.
    """
    for loop_count in range(MAX_TOOL_LOOPS):
        message = chat_with_tools(messages)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # No tool call requested -> this is the final answer
            messages.append(message)
            return message.get("content", "")

        # Model wants to call one or more tools. Record its request, then execute each.
        messages.append(message)
        console.print(f"[dim]  (round {loop_count + 1}: model requested {len(tool_calls)} tool call(s))[/dim]")

        for call in tool_calls:
            fn_name = call["function"]["name"]
            fn_args = call["function"].get("arguments", {})

            console.print(f"[yellow]  -> calling {fn_name}({fn_args})[/yellow]")

            fn = TOOL_FUNCTIONS.get(fn_name)
            if fn is None:
                result = f"Error: unknown tool '{fn_name}'"
            else:
                try:
                    result = fn(**fn_args)
                except Exception as e:
                    result = f"Error running {fn_name}: {e}"

            # Feed the tool's result back as a "tool" role message so the model can use it
            messages.append({"role": "tool", "content": str(result)})

    return "(Stopped: too many tool-call rounds without a final answer. Try rephrasing.)"


def main():
    console.print(f"[bold cyan]Research Agent — Week 2 (model: {MODEL_NAME}, tools enabled)[/bold cyan]")
    console.print("Try things like: 'what is 47 * 89?' or 'search for the latest ollama release'\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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

        console.print(f"[bold magenta]agent>[/bold magenta] {answer}\n")


if __name__ == "__main__":
    main()
