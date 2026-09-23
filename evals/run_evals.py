"""
Week 4 — Eval harness.

Runs a fixed set of test prompts through the agent, applies automated checks
to each result, and reports pass/fail per test case -- turning "I manually
tried some prompts and read the output" into a repeatable, scored process.

Run:
    python evals/run_evals.py

Outputs:
    evals/results/results_<timestamp>.json   -- full structured results
    evals/results/latest_report.md           -- markdown summary (paste into README)
"""

import argparse
import json
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from rich.console import Console
from rich.table import Table

from agent_core import run_agent_turn, PLANNING_SYSTEM_PROMPT
from checks import CHECK_REGISTRY

console = Console()

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Low (not zero) temperature for evals: reduces run-to-run randomness so a
# case's pass/fail is a signal about the agent, not about sampling luck.
# The interactive CLI keeps the model's default temperature.
EVAL_TEMPERATURE = 0.1


def run_single_case_once(case: dict) -> dict:
    messages = [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": case["prompt"]},
    ]

    start = time.time()
    final_answer, trace = run_agent_turn(messages, temperature=EVAL_TEMPERATURE)
    duration = time.time() - start

    check_results = []
    for check in case["checks"]:
        fn_name = check["fn"]
        kwargs = {k: v for k, v in check.items() if k != "fn"}
        fn = CHECK_REGISTRY[fn_name]
        passed, detail = fn(trace=trace, final_answer=final_answer, **kwargs)
        check_results.append({"check": fn_name, "kwargs": kwargs, "passed": passed, "detail": detail})

    all_passed = all(c["passed"] for c in check_results)

    return {
        "final_answer": final_answer,
        "n_tool_calls": len([e for e in trace if e["type"] == "tool_call"]),
        "duration_sec": round(duration, 1),
        "checks": check_results,
        "passed": all_passed,
    }


def run_case(case: dict, n_runs: int) -> dict:
    """Runs a case n_runs times and aggregates into a pass rate, not a single bool."""
    runs = []
    for _ in range(n_runs):
        try:
            runs.append(run_single_case_once(case))
        except Exception as e:
            runs.append({
                "final_answer": "", "n_tool_calls": 0, "duration_sec": 0,
                "checks": [{"check": "execution", "kwargs": {}, "passed": False, "detail": str(e)}],
                "passed": False,
            })

    n_passed = sum(1 for r in runs if r["passed"])
    return {
        "id": case["id"],
        "category": case["category"],
        "prompt": case["prompt"],
        "n_runs": n_runs,
        "n_passed": n_passed,
        "pass_rate": round(n_passed / n_runs, 2),
        "runs": runs,
    }


def write_markdown_report(results: list[dict], n_runs: int, path: Path):
    total_passed = sum(r["n_passed"] for r in results)
    total_runs = sum(r["n_runs"] for r in results)
    lines = [
        "# Eval Results",
        "",
        f"**{total_passed}/{total_runs} runs passed across {len(results)} test cases** "
        f"({n_runs} run(s) per case; run at {time.strftime('%Y-%m-%d %H:%M:%S')})",
        "",
        "| Test ID | Category | Pass rate |",
        "|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['id']} | {r['category']} | {r['n_passed']}/{r['n_runs']} ({r['pass_rate']:.0%}) |")

    lines.append("")
    lines.append("## Details")
    for r in results:
        lines.append(f"\n### {r['id']} -- {r['n_passed']}/{r['n_runs']} passed")
        lines.append(f"Prompt: *{r['prompt']}*\n")
        for i, run in enumerate(r["runs"]):
            status = "PASS" if run["passed"] else "FAIL"
            lines.append(f"\n**Run {i + 1} — {status}** ({run['duration_sec']}s, {run['n_tool_calls']} tool calls)")
            for c in run["checks"]:
                mark = "x" if c["passed"] else " "
                lines.append(f"- [{mark}] `{c['check']}` -- {c['detail']}")
            if not run["passed"]:
                lines.append(f"  - answer: *{run['final_answer'][:300]}*")

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run the agent eval suite.")
    parser.add_argument(
        "--runs", type=int, default=2,
        help="Number of times to run each test case (default 2). Higher = more reliable "
             "pass-rate signal, but takes longer. Use 1 for a quick check, 3-5 for a report "
             "you'd actually cite in a README.",
    )
    args = parser.parse_args()
    n_runs = args.runs

    cases = json.loads(TEST_CASES_PATH.read_text())
    console.print(
        f"[bold cyan]Running {len(cases)} eval cases x {n_runs} run(s) each "
        f"against {SRC_DIR}...[/bold cyan]\n"
    )

    results = []
    for case in cases:
        console.print(f"[bold]{case['id']}[/bold] ({case['category']}) -- {case['prompt'][:70]}")
        result = run_case(case, n_runs)
        results.append(result)

        rate_color = "green" if result["pass_rate"] == 1.0 else ("yellow" if result["pass_rate"] > 0 else "red")
        console.print(
            f"  [{rate_color}]{result['n_passed']}/{result['n_runs']} passed "
            f"({result['pass_rate']:.0%})[/{rate_color}]"
        )
        for i, run in enumerate(result["runs"]):
            if not run["passed"]:
                console.print(f"    [dim]run {i + 1} failed checks:[/dim]")
                for c in run["checks"]:
                    if not c["passed"]:
                        console.print(f"      [red]x[/red] {c['check']}: {c['detail']}")
                preview = run["final_answer"][:200]
                console.print(f"      [dim]answer: {preview}{'...' if len(run['final_answer']) > 200 else ''}[/dim]")
        console.print()

    table = Table(title="Eval Summary")
    table.add_column("ID")
    table.add_column("Category")
    table.add_column("Pass rate")
    for r in results:
        rate_color = "green" if r["pass_rate"] == 1.0 else ("yellow" if r["pass_rate"] > 0 else "red")
        table.add_row(r["id"], r["category"], f"[{rate_color}]{r['n_passed']}/{r['n_runs']}[/{rate_color}]")
    console.print(table)

    total_passed = sum(r["n_passed"] for r in results)
    total_runs = sum(r["n_runs"] for r in results)
    console.print(f"\n[bold]{total_passed}/{total_runs} runs passed across {len(results)} test cases[/bold]")

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    json_path = RESULTS_DIR / f"results_{timestamp}.json"
    json_path.write_text(json.dumps(results, indent=2))

    md_path = RESULTS_DIR / "latest_report.md"
    write_markdown_report(results, n_runs, md_path)

    console.print(f"\nSaved: {json_path}")
    console.print(f"Saved: {md_path}  (paste this into your README)")


if __name__ == "__main__":
    main()