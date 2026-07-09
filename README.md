# 🛟 Crypto CS Copilot

A production-style **multi-agent RAG customer-support assistant** for a crypto
exchange, built with **Claude (Anthropic API)** and **Streamlit** — including
prompt engineering, tool-calling agents, safety guardrails, and an automated
**evaluation pipeline** (LLM-as-judge + deterministic metrics).

> Portfolio project demonstrating end-to-end LLM engineering for
> customer-service scenarios: retrieval, orchestration, safety, and evals.

## Architecture

```
 user message
      │
      ▼
┌─────────────────┐   deterministic regex filters:
│ input guardrails│   prompt injection, credential phishing
└─────────────────┘
      │
      ▼
┌─────────────────┐   Claude Haiku, few-shot classification
│     Router      │   → kb_question / account_security /
└─────────────────┘     escalation / off_topic / unsafe
      │
      ├── kb_question ────────► SupportAgent
      ├── account_security ──► SecurityAgent      each agent runs a
      ├── escalation ────────► EscalationAgent    tool-calling loop
      ├── off_topic ─────────► canned redirect    (Claude Sonnet)
      └── unsafe ────────────► canned refusal
      │
      │        tools: search_knowledge_base (RAG over markdown KB,
      │        TF-IDF retrieval) · get_fee_schedule · create_support_ticket
      ▼
┌─────────────────┐   blocks credential requests,
│ output guardrail│   appends financial-advice disclaimer
└─────────────────┘
      │
      ▼
 answer + full trace (intent, retrieved chunks, tool calls,
 guardrail flags, hidden chain-of-thought, token usage)
```

**Shared memory** (`AgentContext`) carries conversation history, retrieved
chunks, and created tickets across turns so any agent sees what previous
agents did. The orchestrator is hand-rolled (~150 lines) to keep control flow
inspectable; the topology maps 1:1 to a LangGraph `StateGraph` (router as
conditional edge, agents as nodes, `AgentContext` as graph state) if you
prefer a framework.

## Features → skills demonstrated

| Feature | Where |
|---|---|
| RAG over multi-doc knowledge base with citations | `src/retrieval.py` |
| Prompt engineering: XML structure, few-shot routing, CoT, grounding contract | `src/prompts.py` |
| Multi-agent orchestration: router → specialists, shared memory, task decomposition | `src/agents.py` |
| Anthropic tool-calling loop (parallel tool use supported) | `src/agents.py`, `src/tools.py` |
| Guardrails: injection/credential filters, semantic unsafe routing, output post-filter | `src/guardrails.py` |
| Eval pipeline: routing accuracy, topic recall, LLM-as-judge groundedness / relevance / safety / hallucination rate | `src/evaluation.py`, `run_eval.py` |
| Human feedback loop (👍/👎 → JSONL for judge calibration) | `app.py` |
| Observability: per-turn agent trace UI, token usage, latency | `app.py` |

## Quick start

```bash
git clone https://github.com/<you>/crypto-cs-copilot
cd crypto-cs-copilot
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py
```

Run the evaluation suite from the CLI:

```bash
python run_eval.py            # full: deterministic + LLM-as-judge
python run_eval.py --no-judge # fast: deterministic metrics only
```

Outputs `evals/results.json` and `evals/report.md`.

## Deploy to Streamlit Community Cloud

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select
   the repo, main file `app.py`.
3. In app **Settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
4. Deploy. (Users can also paste their own key in the sidebar, so you can
   ship without a funded key.)

## Design notes

- **Retrieval:** markdown KB chunked per `##` section; TF-IDF (1–2 grams,
  sublinear tf) cosine retrieval. Chosen deliberately for a zero-dependency
  demo that boots instantly on Streamlit's free tier; the `Retriever`
  backend interface swaps cleanly to dense embeddings (Voyage/BGE) + a vector
  DB, or a hybrid BM25+dense with reciprocal-rank fusion, for production scale.
- **Two-model split:** Haiku routes (cheap, low latency), Sonnet answers.
  This mirrors production cost engineering — ~90% of routing tokens at ~1/10
  the price.
- **Grounding contract:** agents must search before answering, cite
  sections inline, and say "not in the docs" rather than guess; the judge
  measures exactly this (groundedness + hallucination rate).
- **Safety layering:** regex pre-filters are free and deterministic (catch
  obvious injection), the router adds semantic coverage, and the output
  filter is a last line of defense — no single point of failure.
- **Evals as a first-class artifact:** the same suite runs from CLI (CI-able)
  and the UI; human 👍/👎 feedback is logged to calibrate the judge over time.

## Scaling to production (roadmap)

- Dense/hybrid retrieval with a vector DB (pgvector/Milvus) and reranker.
- Self-hosted inference via **vLLM** (continuous batching, paged attention)
  or **SGLang** (RadixAttention prefix caching — big win for shared agent
  system prompts) on multi-GPU, with the Anthropic API kept for frontier
  reasoning tiers.
- Streaming responses; semantic caching of frequent questions.
- Multilingual eval sets (EN/中文) and per-language prompt variants.
- DPO on thumbs-down transcripts; SFT on golden agent traces.

## Repo layout

```
app.py                 Streamlit UI (chat / evaluation / KB inspector)
run_eval.py            CLI eval runner
src/
  agents.py            router + specialist agents + tool loop (orchestrator)
  prompts.py           prompt library (documented techniques)
  retrieval.py         chunking + TF-IDF retriever (swappable backend)
  tools.py             tool schemas + executors (KB search, fees, tickets)
  guardrails.py        input/output safety filters
  evaluation.py        eval pipeline + LLM-as-judge + report writer
  config.py            models, retrieval params, paths
data/knowledge_base/   6 markdown help-center docs (34 chunks)
evals/test_cases.json  15 labeled cases incl. adversarial & injection probes
```

*Fictional exchange documentation written for this demo; not affiliated with
any exchange.*
