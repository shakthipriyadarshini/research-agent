"""
Reusable check functions for evaluating agent runs.

Each check has the signature:
    check(trace: list[dict], final_answer: str, **kwargs) -> (passed: bool, detail: str)

trace is the structured event list returned by agent_core.run_agent_turn --
this is what lets checks be precise (e.g. "was write_file's content under 40
chars") instead of guessing from printed text.
"""


def tool_used(trace, final_answer, tool_name, **_):
    used = any(e["type"] == "tool_call" and e["name"] == tool_name for e in trace)
    return used, f"{tool_name} {'was' if used else 'was NOT'} called"


def tool_not_used(trace, final_answer, tool_name, **_):
    used = any(e["type"] == "tool_call" and e["name"] == tool_name for e in trace)
    return (not used), f"{tool_name} {'was' if used else 'was NOT'} called (should not be)"


def no_fabricated_urls(trace, final_answer, **_):
    bad = [e for e in trace if e.get("fabricated_urls")]
    return (len(bad) == 0), f"{len(bad)} write_file call(s) had fabricated URLs"


def no_placeholder_write(trace, final_answer, **_):
    bad = [e for e in trace if e.get("placeholder_warning")]
    return (len(bad) == 0), f"{len(bad)} write_file call(s) were placeholder-length"


def min_write_length(trace, final_answer, min_length, **_):
    writes = [e for e in trace if e["type"] == "tool_call" and e["name"] == "write_file"]
    if not writes:
        return False, "no write_file call found"
    content = writes[-1]["args"].get("content", "")
    ok = len(content.strip()) >= min_length
    return ok, f"last write_file content length = {len(content.strip())} (need >= {min_length})"


def answer_contains_any(trace, final_answer, keywords, **_):
    found = [k for k in keywords if k.lower() in final_answer.lower()]
    return (len(found) > 0), f"matched keywords: {found or 'none'}"


def search_before_write(trace, final_answer, **_):
    search_idx = next(
        (i for i, e in enumerate(trace) if e["type"] == "tool_call" and e["name"] == "web_search"), None
    )
    write_idx = next(
        (i for i, e in enumerate(trace) if e["type"] == "tool_call" and e["name"] == "write_file"), None
    )
    if search_idx is None or write_idx is None:
        return True, "search or write not both present -- check skipped"
    ok = search_idx < write_idx
    return ok, f"search at trace index {search_idx}, write at index {write_idx}"


def did_not_time_out(trace, final_answer, **_):
    ok = not final_answer.startswith("(Stopped after")
    detail = "completed within round limit" if ok else "hit MAX_TOOL_LOOPS without finishing"
    return ok, detail


def max_tool_calls(trace, final_answer, max_calls, **_):
    n = len([e for e in trace if e["type"] == "tool_call"])
    ok = n <= max_calls
    return ok, f"{n} tool call(s) used (limit: {max_calls})"


CHECK_REGISTRY = {
    "tool_used": tool_used,
    "tool_not_used": tool_not_used,
    "no_fabricated_urls": no_fabricated_urls,
    "no_placeholder_write": no_placeholder_write,
    "min_write_length": min_write_length,
    "answer_contains_any": answer_contains_any,
    "search_before_write": search_before_write,
    "did_not_time_out": did_not_time_out,
    "max_tool_calls": max_tool_calls,
}