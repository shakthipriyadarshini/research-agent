# Research Agent (Local, Open-Weight, Agentic)

A locally-run research agent built on open-weight LLMs (via [Ollama](https://ollama.com)).
Goal: given a task like "research X and summarize with sources," the agent plans,
calls tools (web search, file reading), and produces a grounded answer — entirely on-device.

This repo follows a 6-week build plan. Each week's code lives in `src/` and builds on the last.

## Why this project
- No cloud API dependency — everything runs on open-weight models locally
- Demonstrates agentic patterns (planning, tool use, evaluation) rather than a single prompt-response wrapper
- Includes an eval harness — most student projects skip this, it's the main differentiator

## Setup

1. Install [Ollama](https://ollama.com/download)
2. Pull a small model:
   ```bash
   ollama pull llama3.2
   ```
3. Install Python deps:
   ```bash
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

## Week 1 — Basic local chat (this milestone)

Run:
```bash
python src/week1_chat.py
```

This is a CLI chat loop talking to your local Ollama model. It's intentionally minimal —
no frameworks yet — so you understand exactly what's happening before adding LangGraph
or tool-calling abstractions in later weeks.

## Roadmap

- [x] Week 1 — Basic local chat via Ollama API
- [ ] Week 2 — Tool use / function calling (web search, file reader, calculator)
- [ ] Week 3 — Multi-step planning loop (plan → act → observe → repeat)
- [ ] Week 4 — Reliability + eval harness (success rate on a fixed task set)
- [ ] Week 5 — Simple UI (Streamlit) + deploy demo
- [ ] Week 6 — Polish, README architecture diagram, writeup

## Project structure
```
research-agent/
├── README.md
├── requirements.txt
├── src/
│   ├── week1_chat.py      # Week 1: basic chat loop
│   ├── config.py          # model name, API base URL, constants
│   └── (later weeks add here: tools.py, agent.py, evals.py)
└── evals/                 # (Week 4) task set + results
```
## Known Limitations (found via automated evals)

- **File-write compliance after verbal answers (~0% pass rate on `grounded_search_and_write`)**:
  when a task requires both answering a question AND saving output to a file,
  llama3.2:3b reliably answers correctly but often skips the actual write_file
  call — sometimes writing pseudo-code text instead of invoking the tool.
  Tried: explicit compliance instructions, narrowed trigger conditions, and a
  code-level pseudo-call detector with bounded retries. None fully closed the
  gap. Likely requires a larger model or stricter structured-output mode.
- **Eval suite**: 13/16 runs passed across 8 test cases (2 runs/case), using
  rule-based checks derived from real failures found during development.
  See `evals/README.md` for methodology and `evals/results/latest_report.md`
  for the latest scored run.