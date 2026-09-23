# Eval Harness

Automated, repeatable tests for the agent -- replaces manually running prompts
and eyeballing terminal output.

## Run
```bash
python evals/run_evals.py
```

## How it works
- `test_cases.json` -- each case is a prompt + a list of checks it must pass.
  These cases were built directly from real failures found during manual
  testing in Weeks 2-3 (hallucinated definitions, fabricated citations,
  placeholder file writes, unnecessary tool calls).
- `checks.py` -- small, reusable, rule-based check functions (e.g. "was this
  tool called", "does the file contain a fabricated URL", "is the answer
  non-empty"). Each check is independent and composable across test cases.
- `run_evals.py` -- runs every case through `agent_core.run_agent_turn`
  (the same core loop the interactive CLI uses), applies the checks, and
  writes:
  - `results/results_<timestamp>.json` -- full machine-readable results
  - `results/latest_report.md` -- human-readable summary, safe to paste
    straight into the main README

## Why rule-based checks (not just "looks good to me")
Rule-based checks can't catch everything (e.g. subtle semantic hallucination
that doesn't fabricate a URL or under-write a file) -- but they reliably catch
the concrete failure modes found in this project: fabricated citations,
placeholder outputs, wrong/missing tool calls, infinite loops, and timeouts.
That's a deliberate scope choice: cheap, fast, deterministic checks first;
LLM-as-judge checks (for subtler semantic grounding) are a natural next
extension, not implemented here yet.

## Extending
Add a new case to `test_cases.json` with a prompt + checks (reusing
`checks.py` functions, or adding a new one). No code changes needed for a new
test case that reuses existing checks.