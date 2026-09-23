"""
Week 3 — Multi-step planning agent (interactive CLI).

All the actual loop logic now lives in agent_core.py. This file is just the
terminal UI: it prints events as they happen and drives the input loop.

Run:
    python src/week3_agent.py
"""

import sys

import requests
from rich.console import Console

from config import MODEL_NAME
from agent_core import run_agent_turn, PLANNING_SYSTEM_PROMPT

console = Console()


def print_event(event: dict):
    """Rich-formatted printing for each event type -- matches the original CLI output."""
    etype = event["type"]

    if etype == "model_note":
        console.print(f"[dim italic]  (model: {event['content'][:200]})[/dim italic]")

    elif etype == "round":
        console.print(f"[dim]  (round {event['round']}: {event['n_calls']} tool call(s))[/dim]")

    elif etype == "tool_call":
        console.print(f"[yellow]  -> {event['name']}({event['args']})[/yellow]")
        preview = event["result"][:150]
        suffix = "..." if len(event["result"]) > 150 else ""
        console.print(f"[dim]     result: {preview}{suffix}[/dim]")

    elif etype == "warning":
        console.print(f"[bold red]  !! WARNING: {event['message']}[/bold red]")


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
            answer, _trace = run_agent_turn(messages, on_event=print_event)
        except requests.exceptions.ConnectionError:
            console.print("[bold red]Could not reach Ollama.[/bold red] Is it running?")
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            console.print(f"[bold red]Ollama returned an error:[/bold red] {e}")
            sys.exit(1)

        console.print(f"\n[bold magenta]agent>[/bold magenta] {answer}\n")


if __name__ == "__main__":
    main()