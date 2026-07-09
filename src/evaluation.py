"""Evaluation pipeline.

Two layers, mirroring production LLM-quality practice:
1. Deterministic checks — routing accuracy, expected-topic keyword recall,
   guardrail firing on unsafe cases. Fast, free, run on every commit.
2. LLM-as-judge — Claude scores groundedness, relevance, safety and flags
   hallucination against the actually-retrieved context. The judge returns
   strict JSON; parse failures are recorded, not silently dropped.

Human feedback hooks: every Streamlit answer has 👍/👎 which appends to
`evals/feedback.jsonl`, so judge scores can be calibrated against humans.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import anthropic

from . import prompts
from .agents import AgentContext, Orchestrator
from .config import EVALS_DIR, JUDGE_MODEL


@dataclass
class CaseResult:
    id: str
    category: str
    question: str
    answer: str
    routed_intent: str
    routing_correct: bool
    topic_recall: float
    guardrail_flags: list[str]
    judge: dict = field(default_factory=dict)
    latency_s: float = 0.0


def topic_recall(answer: str, topics: list[str]) -> float:
    hits = sum(1 for t in topics if t.lower() in answer.lower())
    return round(hits / len(topics), 2) if topics else 1.0


def judge_answer(client: anthropic.Anthropic, question: str,
                 context: str, answer: str) -> dict:
    user = (f"<question>{question}</question>\n"
            f"<retrieved_context>{context or 'NONE'}</retrieved_context>\n"
            f"<answer>{answer}</answer>")
    resp = client.messages.create(
        model=JUDGE_MODEL, max_tokens=300, temperature=0,
        system=prompts.JUDGE_SYSTEM,
        messages=[{"role": "user", "content": user}])
    text = resp.content[0].text.strip()
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {"parse_error": text[:200]}
    except json.JSONDecodeError:
        return {"parse_error": text[:200]}


def run_eval(api_key: str,
             cases_path: Path = EVALS_DIR / "test_cases.json",
             use_judge: bool = True,
             progress_cb=None) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    orch = Orchestrator(api_key)
    judge_client = anthropic.Anthropic(api_key=api_key)
    results: list[CaseResult] = []

    for i, case in enumerate(cases):
        if progress_cb:
            progress_cb(i, len(cases), case["id"])
        memory = AgentContext()  # fresh conversation per case
        t0 = time.time()
        answer, trace = orch.respond(case["question"], memory)
        latency = time.time() - t0

        routed_ok = (trace.intent == case["category"]
                     or (case["category"] == "unsafe"
                         and trace.intent in ("unsafe", "blocked")))
        r = CaseResult(
            id=case["id"], category=case["category"],
            question=case["question"], answer=answer,
            routed_intent=trace.intent, routing_correct=routed_ok,
            topic_recall=topic_recall(answer, case["expected_topics"]),
            guardrail_flags=trace.guardrail_flags,
            latency_s=round(latency, 2))
        if use_judge and trace.agent not in ("canned", "guardrail"):
            context = orch.retriever.format_context(trace.retrieved)
            r.judge = judge_answer(judge_client, case["question"],
                                   context, answer)
        results.append(r)

    return summarize(results)


def summarize(results: list[CaseResult]) -> dict:
    judged = [r for r in results if r.judge and "parse_error" not in r.judge]

    def avg(key):
        vals = [r.judge[key] for r in judged if key in r.judge]
        return round(sum(vals) / len(vals), 2) if vals else None

    summary = {
        "n_cases": len(results),
        "routing_accuracy": round(
            sum(r.routing_correct for r in results) / len(results), 2),
        "mean_topic_recall": round(
            sum(r.topic_recall for r in results) / len(results), 2),
        "judged_cases": len(judged),
        "avg_groundedness": avg("groundedness"),
        "avg_relevance": avg("relevance"),
        "avg_safety": avg("safety"),
        "hallucination_rate": (round(
            sum(bool(r.judge.get("hallucination")) for r in judged)
            / len(judged), 2) if judged else None),
        "citation_rate": (round(
            sum(bool(r.judge.get("cites_sources")) for r in judged)
            / len(judged), 2) if judged else None),
        "mean_latency_s": round(
            sum(r.latency_s for r in results) / len(results), 2),
    }
    return {"summary": summary, "results": [asdict(r) for r in results]}


def write_report(report: dict, out_dir: Path = EVALS_DIR) -> Path:
    out_dir.mkdir(exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    s = report["summary"]
    lines = ["# Evaluation Report", "",
             f"- Cases: {s['n_cases']}",
             f"- Routing accuracy: {s['routing_accuracy']:.0%}",
             f"- Mean topic recall: {s['mean_topic_recall']:.0%}",
             f"- Groundedness (1-5): {s['avg_groundedness']}",
             f"- Relevance (1-5): {s['avg_relevance']}",
             f"- Safety (1-5): {s['avg_safety']}",
             f"- Hallucination rate: {s['hallucination_rate']}",
             f"- Citation rate: {s['citation_rate']}",
             f"- Mean latency: {s['mean_latency_s']}s", ""]
    for r in report["results"]:
        lines += [f"## {r['id']} ({r['category']})",
                  f"**Q:** {r['question']}",
                  f"**Routed:** {r['routed_intent']} "
                  f"({'✓' if r['routing_correct'] else '✗'}) · "
                  f"topic recall {r['topic_recall']:.0%} · "
                  f"{r['latency_s']}s",
                  f"**Judge:** {json.dumps(r['judge'], ensure_ascii=False)}",
                  ""]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
