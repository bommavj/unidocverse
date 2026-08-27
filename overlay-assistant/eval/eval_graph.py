"""
LangGraph-based LLM Evaluation Framework
Pipeline: load_cases → run_and_judge (loop) → aggregate → report
"""
from __future__ import annotations

import os
import time
import json
import yaml
from pathlib import Path
from typing import Any, TypedDict, Annotated
from dataclasses import dataclass, field, asdict

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# ─────────────────────────── data types ───────────────────────────

@dataclass
class TestCase:
    id: str
    category: str
    question: str
    expected_keywords: list[str]
    min_score: int
    tags: list[str]


@dataclass
class EvalResult:
    case_id: str
    category: str
    question: str
    answer: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    judge_score: int
    judge_rationale: str
    keyword_hits: list[str]
    keyword_misses: list[str]
    passed: bool


class EvalState(TypedDict):
    cases: list[TestCase]
    results: Annotated[list[EvalResult], lambda a, b: a + b]
    current_idx: int
    model_name: str
    role_prompt: str
    baseline_path: str | None
    errors: list[str]


# ────────────────────────── LLM provider ──────────────────────────

def _build_llm(model_name: str = "auto"):
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key   = os.getenv("GROQ_API_KEY", "")

    if model_name == "auto":
        if gemini_key:
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
            provider = "gemini"
        elif groq_key:
            model_name = os.getenv("GROQ_MODEL", "groq/compound-mini")
            provider = "groq"
        else:
            model_name = os.getenv("OLLAMA_MODEL", "mistral:latest")
            provider = "ollama"
    elif "gemini" in model_name:
        provider = "gemini"
    elif any(x in model_name for x in ["llama", "mixtral", "groq"]):
        provider = "groq"
    else:
        provider = "ollama"

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=gemini_key,
            temperature=0.3,
            max_output_tokens=800,
        ), model_name, provider

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model_name,
            groq_api_key=groq_key,
            temperature=0.3,
            max_tokens=800,
        ), model_name, provider

    from langchain_ollama import ChatOllama
    return ChatOllama(model=model_name, temperature=0.3), model_name, provider


def _build_judge_llm():
    """Always prefer Groq for judging — avoids burning the model-under-test's quota."""
    groq_key   = os.getenv("GROQ_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")

    if groq_key:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="groq/compound-mini",
            groq_api_key=groq_key,
            temperature=0.0,
            max_tokens=200,
        )
    if gemini_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            google_api_key=gemini_key,
            temperature=0.0,
            max_output_tokens=200,
        )
    from langchain_ollama import ChatOllama
    return ChatOllama(model=os.getenv("OLLAMA_MODEL", "mistral:latest"), temperature=0.0)


def _token_cost(provider: str, in_tok: int, out_tok: int) -> float:
    rates = {
        "gemini": (0.075, 0.30),
        "groq":   (0.05,  0.08),
        "ollama": (0.0,   0.0),
    }
    i_rate, o_rate = rates.get(provider, (0.0, 0.0))
    return (in_tok * i_rate + out_tok * o_rate) / 1_000_000


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ──────────────────────────── prompts ─────────────────────────────

SYSTEM_PROMPT = (
    "You are a senior software engineer (8+ years) being interviewed at FAANG.\n"
    "Answer like you are speaking in a real interview. Structure every answer as:\n"
    "1. Clear definition\n"
    "2. How it works with technical depth\n"
    "3. Real production example (tools, scale, infra, numbers)\n"
    "4. Key trade-offs\n"
    "Be concrete, not generic. Keep answers under 250 words."
)

JUDGE_SYSTEM = (
    "You are an expert technical interviewer evaluating candidate answers.\n"
    "Score 1-5 where:\n"
    "  5=excellent: production-depth, concrete numbers, clear trade-offs\n"
    "  4=good: solid with minor gaps\n"
    "  3=acceptable: covers basics, lacks depth or examples\n"
    "  2=weak: vague or generic\n"
    "  1=poor: wrong or irrelevant\n"
    "Respond ONLY as valid JSON: {\"score\": <1-5>, \"rationale\": \"<1-2 sentences>\"}"
)


# ──────────────────────────── graph nodes ─────────────────────────

def node_load_cases(state: EvalState) -> dict:
    cases_path = Path(__file__).parent / "cases.yaml"
    raw = yaml.safe_load(cases_path.read_text())
    cases = [TestCase(**c) for c in raw["cases"]]
    return {"cases": cases, "current_idx": 0, "results": [], "errors": []}


def node_run_and_judge(state: EvalState) -> dict:
    """Run the model on the current case, then immediately judge it."""
    idx = state["current_idx"]
    case = state["cases"][idx]
    role_prompt = state.get("role_prompt") or SYSTEM_PROMPT

    llm, model_name, provider = _build_llm(state.get("model_name", "auto"))

    # ── model call ──
    t0 = time.perf_counter()
    try:
        response = llm.invoke([
            SystemMessage(content=role_prompt),
            HumanMessage(content=case.question),
        ])
        answer = response.content
        latency_ms = (time.perf_counter() - t0) * 1000
        usage = getattr(response, "usage_metadata", None) or {}
        in_tok  = usage.get("input_tokens",  _approx_tokens(role_prompt + case.question))
        out_tok = usage.get("output_tokens", _approx_tokens(answer))
    except Exception as exc:
        answer = f"ERROR: {exc}"
        latency_ms = (time.perf_counter() - t0) * 1000
        in_tok = out_tok = 0

    cost = _token_cost(provider, in_tok, out_tok)

    # ── keyword check ──
    answer_lower = answer.lower()
    hits   = [kw for kw in case.expected_keywords if kw.lower() in answer_lower]
    misses = [kw for kw in case.expected_keywords if kw.lower() not in answer_lower]

    # ── LLM judge (dedicated LLM to avoid burning model quota) ──
    judge_score = 0
    judge_rationale = ""
    try:
        judge_llm = _build_judge_llm()
        judge_resp = judge_llm.invoke([
            SystemMessage(content=JUDGE_SYSTEM),
            HumanMessage(content=(
                f"Question: {case.question}\n\n"
                f"Candidate Answer:\n{answer}\n\n"
                f"Missing concepts: {misses or 'none'}"
            )),
        ])
        raw = judge_resp.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw)
        judge_score     = int(parsed.get("score", 1))
        judge_rationale = parsed.get("rationale", "")
    except Exception as exc:
        ratio = len(hits) / max(1, len(case.expected_keywords))
        judge_score     = max(1, round(ratio * 5))
        judge_rationale = f"Auto-scored (judge error: {exc})"

    result = EvalResult(
        case_id=case.id,
        category=case.category,
        question=case.question,
        answer=answer,
        latency_ms=round(latency_ms, 1),
        input_tokens=in_tok,
        output_tokens=out_tok,
        cost_usd=round(cost, 6),
        judge_score=judge_score,
        judge_rationale=judge_rationale,
        keyword_hits=hits,
        keyword_misses=misses,
        passed=judge_score >= case.min_score,
    )

    return {
        "results": [result],
        "current_idx": idx + 1,
    }


def node_aggregate(state: EvalState) -> dict:
    results = state["results"]
    if not results:
        return {"_metrics": {}}

    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
    avg_score   = sum(r.judge_score for r in results) / total
    avg_lat     = sum(r.latency_ms  for r in results) / total
    total_cost  = sum(r.cost_usd    for r in results)

    by_cat: dict[str, dict] = {}
    for r in results:
        d = by_cat.setdefault(r.category, {"pass": 0, "total": 0, "scores": []})
        d["total"] += 1
        d["scores"].append(r.judge_score)
        if r.passed:
            d["pass"] += 1

    metrics = {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total * 100, 1),
        "avg_score": round(avg_score, 2),
        "avg_latency_ms": round(avg_lat, 1),
        "total_cost_usd": round(total_cost, 5),
        "total_input_tokens":  sum(r.input_tokens  for r in results),
        "total_output_tokens": sum(r.output_tokens for r in results),
        "by_category": {
            cat: {
                "pass_rate": round(v["pass"] / v["total"] * 100, 1),
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 2),
            }
            for cat, v in by_cat.items()
        },
    }

    baseline_path = state.get("baseline_path")
    if baseline_path:
        metrics["regression"] = _check_regression(results, baseline_path)

    return {"_metrics": metrics}


def node_report(state: EvalState) -> dict:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    results: list[EvalResult] = state["results"]
    metrics: dict = state.get("_metrics") or {}

    table = Table(title="LLM Eval Results", box=box.ROUNDED, show_lines=True)
    table.add_column("ID",       style="dim",    width=8)
    table.add_column("Category", style="cyan",   width=14)
    table.add_column("Score",    justify="center", width=7)
    table.add_column("Pass",     justify="center", width=5)
    table.add_column("Latency",  justify="right",  width=9)
    table.add_column("KW",       justify="center", width=6)
    table.add_column("Rationale", width=55)

    for r in results:
        color = "green" if r.judge_score >= 4 else "yellow" if r.judge_score == 3 else "red"
        table.add_row(
            r.case_id,
            r.category,
            f"[{color}]{r.judge_score}/5[/{color}]",
            "✅" if r.passed else "❌",
            f"{r.latency_ms:.0f}ms",
            f"{len(r.keyword_hits)}/{len(r.keyword_hits)+len(r.keyword_misses)}",
            r.judge_rationale[:80],
        )

    console.print(table)
    console.print(f"\n[bold]Summary[/bold]")
    console.print(f"  Pass rate  : [green]{metrics.get('pass_rate', 0)}%[/green]  ({metrics.get('passed')}/{metrics.get('total')})")
    console.print(f"  Avg score  : {metrics.get('avg_score', 0):.2f}/5")
    console.print(f"  Avg latency: {metrics.get('avg_latency_ms', 0):.0f}ms")
    console.print(f"  Total cost : ${metrics.get('total_cost_usd', 0):.5f}")
    console.print(f"  Tokens     : ↑{metrics.get('total_input_tokens',0)} ↓{metrics.get('total_output_tokens',0)}")

    regression = (metrics.get("regression") or [])
    if regression:
        console.print(f"\n[red bold]⚠ REGRESSION[/red bold]")
        for item in regression:
            console.print(f"  {item}")

    if "by_category" in metrics:
        console.print("\n[bold]By Category[/bold]")
        for cat, v in metrics["by_category"].items():
            bar = "█" * max(1, int(v["pass_rate"] / 20))
            console.print(f"  {cat:<16} {bar:<6} {v['pass_rate']}%  avg {v['avg_score']:.1f}/5")

    report_path = Path(__file__).parent / "eval_report.json"
    report_path.write_text(json.dumps({
        "metrics": metrics,
        "results": [asdict(r) for r in results],
    }, indent=2))
    console.print(f"\nReport → [cyan]{report_path}[/cyan]")
    return {}


# ─────────────────────── regression helpers ───────────────────────

def _check_regression(results: list[EvalResult], baseline_path: str, threshold: float = 0.5) -> list[str]:
    p = Path(baseline_path)
    if not p.exists():
        return []
    try:
        old_scores = {r["case_id"]: r["judge_score"] for r in json.loads(p.read_text()).get("results", [])}
    except Exception:
        return []
    return [
        f"{r.case_id}: {old_scores[r.case_id]} → {r.judge_score}  (-{old_scores[r.case_id] - r.judge_score})"
        for r in results
        if r.case_id in old_scores and (old_scores[r.case_id] - r.judge_score) >= threshold
    ]


def save_baseline(results: list[EvalResult], path: str = "eval_baseline.json") -> None:
    p = Path(__file__).parent / path
    p.write_text(json.dumps({"results": [asdict(r) for r in results]}, indent=2))
    print(f"Baseline saved → {p}")


# ───────────────────────── routing logic ──────────────────────────

def _has_more_cases(state: EvalState) -> str:
    return "run_and_judge" if state["current_idx"] < len(state["cases"]) else "aggregate"


# ─────────────────────────── build graph ──────────────────────────

def build_eval_graph() -> Any:
    g = StateGraph(EvalState)

    g.add_node("load_cases",   node_load_cases)
    g.add_node("run_and_judge", node_run_and_judge)
    g.add_node("aggregate",    node_aggregate)
    g.add_node("report",       node_report)

    g.set_entry_point("load_cases")
    g.add_edge("load_cases", "run_and_judge")
    g.add_conditional_edges("run_and_judge", _has_more_cases, {
        "run_and_judge": "run_and_judge",
        "aggregate":     "aggregate",
    })
    g.add_edge("aggregate", "report")
    g.add_edge("report", END)

    return g.compile(checkpointer=None)


# ──────────────────────────── public API ──────────────────────────

def run_eval(
    model_name: str = "auto",
    role_prompt: str | None = None,
    baseline_path: str | None = None,
    save_as_baseline: bool = False,
) -> list[EvalResult]:
    graph = build_eval_graph()
    final = graph.invoke(
        {
            "cases": [],
            "results": [],
            "current_idx": 0,
            "model_name": model_name,
            "role_prompt": role_prompt or SYSTEM_PROMPT,
            "baseline_path": baseline_path,
            "errors": [],
        },
        config={"recursion_limit": 200},
    )
    results: list[EvalResult] = final.get("results", [])
    if save_as_baseline:
        save_baseline(results)
    return results
