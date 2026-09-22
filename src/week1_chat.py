"""
Week 1 — Basic local chat loop.

Goal: talk to a local, open-weight model via Ollama's API with zero frameworks,
so you understand exactly what a "chat" request/response looks like before
adding tool-calling and agent loops in later weeks.

Run:
    python src/week1_chat.py

Prereqs:
    - Ollama installed and running (it runs as a background service after install)
    - Model pulled: `ollama pull llama3.2`
"""

import sys
import requests
from rich.console import Console
from rich.markdown import Markdown

from config import OLLAMA_BASE_URL, MODEL_NAME, SYSTEM_PROMPT

console = Console()


def chat(messages: list[dict]) -> str:
    """
    Send the full conversation history to Ollama and return the assistant's reply.
    Ollama's /api/chat endpoint expects: {"model": ..., "messages": [...], "stream": False}
    """
    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "stream": False,
        },
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def main():
    console.print(f"[bold cyan]Research Agent — Week 1 (model: {MODEL_NAME})[/bold cyan]")
    console.print("Type your message, or 'exit' to quit.\n")

    # Ollama has no memory between calls — we resend the full history each time.
    # This is the same pattern you'll see later when calling any LLM API.
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
            reply = chat(messages)
        except requests.exceptions.ConnectionError:
            console.print(
                "[bold red]Could not reach Ollama.[/bold red] "
                "Is it running? Try `ollama serve` or just open the Ollama app."
            )
            sys.exit(1)
        except requests.exceptions.HTTPError as e:
            console.print(f"[bold red]Ollama returned an error:[/bold red] {e}")
            console.print(f"Did you run `ollama pull {MODEL_NAME}`?")
            sys.exit(1)

        messages.append({"role": "assistant", "content": reply})
        console.print("[bold magenta]agent>[/bold magenta]", end=" ")
        console.print(Markdown(reply))
        console.print()


if __name__ == "__main__":
    main()
