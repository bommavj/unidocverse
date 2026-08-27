#!/usr/bin/env python3
"""
CLI entry point for the LangGraph LLM eval framework.

Usage:
  python run_eval.py                          # run full suite, auto provider
  python run_eval.py --model gemini-1.5-flash
  python run_eval.py --save-baseline          # snapshot as regression baseline
  python run_eval.py --baseline eval_baseline.json  # detect regressions
  python run_eval.py --tags llm,senior        # filter by tag
  python run_eval.py --category system_design # filter by category
"""
import argparse
import sys
import os
import yaml
from pathlib import Path

# ensure parent .env is loaded
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

from eval_graph import run_eval, build_eval_graph, TestCase, EvalState, SYSTEM_PROMPT


def filter_cases(tags: list[str] | None, category: str | None) -> list[TestCase]:
    """Load and optionally filter cases."""
    cases_path = Path(__file__).parent / "cases.yaml"
    raw = yaml.safe_load(cases_path.read_text())
    cases = [TestCase(**c) for c in raw["cases"]]

    if category:
        cases = [c for c in cases if c.category == category]
    if tags:
        tag_set = set(tags)
        cases = [c for c in cases if tag_set.intersection(c.tags)]

    if not cases:
        print("No cases matched the filters.")
        sys.exit(1)
    return cases


def main():
    parser = argparse.ArgumentParser(description="LangGraph LLM Eval")
    parser.add_argument("--model",          default="auto",  help="Model name or 'auto'")
    parser.add_argument("--save-baseline",  action="store_true")
    parser.add_argument("--baseline",       default=None,    help="Path to baseline JSON for regression check")
    parser.add_argument("--tags",           default=None,    help="Comma-separated tags to filter cases")
    parser.add_argument("--category",       default=None,    help="Filter by single category")
    parser.add_argument("--role",           default=None,    help="Custom role/system prompt override")
    args = parser.parse_args()

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else None

    # if filters are set, patch the graph to use a pre-filtered case list
    if tags or args.category:
        from langgraph.graph import StateGraph, END
        from eval_graph import _has_more_cases, node_aggregate, node_report, node_run_and_judge
        from eval_graph import EvalState

        filtered = filter_cases(tags, args.category)

        def patched_load(state):
            return {"cases": filtered, "current_idx": 0, "results": [], "errors": []}

        g = StateGraph(EvalState)
        g.add_node("load_cases",    patched_load)
        g.add_node("run_and_judge", node_run_and_judge)
        g.add_node("aggregate",     node_aggregate)
        g.add_node("report",        node_report)
        g.set_entry_point("load_cases")
        g.add_edge("load_cases", "run_and_judge")
        g.add_conditional_edges("run_and_judge", _has_more_cases, {
            "run_and_judge": "run_and_judge",
            "aggregate":     "aggregate",
        })
        g.add_edge("aggregate", "report")
        g.add_edge("report", END)
        graph = g.compile(checkpointer=None)

        final = graph.invoke(
            {
                "cases": [],
                "results": [],
                "current_idx": 0,
                "model_name": args.model,
                "role_prompt": args.role or SYSTEM_PROMPT,
                "baseline_path": args.baseline,
                "errors": [],
            },
            config={"recursion_limit": 200},
        )
        results = final.get("results", [])
    else:
        results = run_eval(
            model_name=args.model,
            role_prompt=args.role,
            baseline_path=args.baseline,
            save_as_baseline=args.save_baseline,
        )

    if args.save_baseline and (tags or args.category):
        from eval_graph import save_baseline
        save_baseline(results)

    # exit code signals CI pass/fail
    pass_rate = sum(1 for r in results if r.passed) / max(1, len(results))
    sys.exit(0 if pass_rate >= 0.7 else 1)


if __name__ == "__main__":
    main()
