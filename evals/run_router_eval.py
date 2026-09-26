"""Measure how often the assistant turns a question into the right query.

Each case in router_cases.jsonl has a question, the expected tool and the
expected arguments. A case passes when the tool matches, the resolved date
range matches, category and payment_method match (both must be unset when the
case doesn't list them), and any tool-specific argument the case lists
(group_by, order_by, limit) matches. Periods are compared as resolved date
ranges, so "month 2026-08" and "custom 2026-08-01..2026-08-31" both count.

Only the planning step is evaluated, so no database is needed.

    python -m evals.run_router_eval --baseline                 # old keyword router
    python -m evals.run_router_eval --model llama3.1:8b        # needs Ollama running
    python -m evals.run_router_eval --baseline --model llama3.2:3b --model llama3.1:8b --out evals/results.md
"""
import argparse
import json
import statistics
import time
from datetime import date
from pathlib import Path

from app.ai import PlanningError, plan
from app.ai_tools import ToolArgError, parse_tool_call, resolve_dates
from app.llm import LLMError, OllamaClient
from evals.keyword_baseline import keyword_plan

# Fixed so that relative periods ("last month") have a single right answer.
TODAY = date(2026, 9, 15)
CATEGORIES = ["Bills", "Entertainment", "Food", "Rent", "Shopping", "Transport"]
CASES = Path(__file__).with_name("router_cases.jsonl")
TOOL_FIELDS = ("group_by", "order_by", "limit")


def load_cases(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def date_range(args) -> str:
    start, end = resolve_dates(args, TODAY)
    return f"{start or '...'} to {end or '...'}"


def mismatches(case: dict, call) -> list[str]:
    """Return what the call got wrong; empty means the case passed."""
    if call.name != case["tool"]:
        return [f"tool {call.name} != {case['tool']}"]
    expected = parse_tool_call(case["tool"], case["args"], CATEGORIES).args
    actual = call.args
    problems = []
    got, want = date_range(actual), date_range(expected)
    if got != want:
        problems.append(f"dates {got} != {want}")
    for field in ("category", "payment_method"):
        if getattr(actual, field) != getattr(expected, field):
            problems.append(f"{field} {getattr(actual, field)!r} != {getattr(expected, field)!r}")
    for field in TOOL_FIELDS:
        if field in case["args"] and getattr(actual, field) != getattr(expected, field):
            problems.append(f"{field} {getattr(actual, field)!r} != {getattr(expected, field)!r}")
    return problems


def evaluate(name: str, planner, cases: list[dict]) -> dict:
    passed, tool_ok, retries, latencies, failures = 0, 0, 0, [], []
    for case in cases:
        start = time.perf_counter()
        try:
            call, attempts = planner(case["question"])
        except (PlanningError, ToolArgError) as exc:
            failures.append((case["question"], f"no valid tool call: {exc}"))
            latencies.append(time.perf_counter() - start)
            continue
        latencies.append(time.perf_counter() - start)
        retries += attempts > 1
        tool_ok += call.name == case["tool"]
        problems = mismatches(case, call)
        if problems:
            failures.append((case["question"], "; ".join(problems)))
        else:
            passed += 1
    n = len(cases)
    return {
        "name": name, "cases": n, "passed": passed,
        "exact": passed / n, "tool": tool_ok / n, "retries": retries,
        "p50": statistics.median(latencies), "p95": sorted(latencies)[max(0, round(0.95 * n) - 1)],
        "failures": failures,
    }


def baseline_planner(question: str):
    tool, args = keyword_plan(question)
    return parse_tool_call(tool, args, CATEGORIES), 1


def llm_planner(model: str):
    client = OllamaClient(model=model)
    return lambda question: plan(question, TODAY, CATEGORIES, client)


def report(results: list[dict]) -> str:
    lines = [
        f"Router eval: {results[0]['cases']} questions, today fixed to {TODAY}, run on {date.today()}.",
        "",
        "| Router | Exact match | Right tool | Needed retry | p50 latency | p95 latency |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['name']} | {r['exact']:.0%} ({r['passed']}/{r['cases']}) | {r['tool']:.0%} "
            f"| {r['retries']} | {r['p50']:.2f}s | {r['p95']:.2f}s |"
        )
    for r in results:
        if r["failures"]:
            lines += ["", f"### Failures: {r['name']}", ""]
            lines += [f"- {q}: {why}" for q, why in r["failures"]]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", action="store_true", help="evaluate the old keyword router")
    parser.add_argument("--model", action="append", default=[], help="Ollama model to evaluate (repeatable)")
    parser.add_argument("--cases", type=Path, default=CASES)
    parser.add_argument("--out", type=Path, help="also write the report to this markdown file")
    args = parser.parse_args()
    if not args.baseline and not args.model:
        parser.error("pass --baseline and/or at least one --model")

    cases = load_cases(args.cases)
    results = []
    if args.baseline:
        results.append(evaluate("keyword baseline", baseline_planner, cases))
    for model in args.model:
        try:
            results.append(evaluate(model, llm_planner(model), cases))
        except LLMError as exc:
            raise SystemExit(f"{model}: {exc}")
    text = report(results)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
