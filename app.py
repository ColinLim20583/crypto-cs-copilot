"""Crypto CS Copilot — multi-agent RAG customer-support demo.

Run locally:   streamlit run app.py
Deploy:        push to GitHub → share.streamlit.io → add ANTHROPIC_API_KEY
               to app secrets.
"""
import json
import os
from pathlib import Path

import streamlit as st

from src.agents import AgentContext, Orchestrator
from src.evaluation import run_eval, write_report
from src.retrieval import Retriever

st.set_page_config(page_title="Crypto CS Copilot", page_icon="🛟",
                   layout="wide")

FEEDBACK_PATH = Path("evals/feedback.jsonl")


# ---------- cached resources ----------
@st.cache_resource
def get_retriever() -> Retriever:
    return Retriever()


def get_api_key() -> str | None:
    if st.session_state.get("api_key_input"):
        return st.session_state["api_key_input"]
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except FileNotFoundError:
        pass
    return os.getenv("ANTHROPIC_API_KEY")


# ---------- sidebar ----------
with st.sidebar:
    st.title("🛟 Crypto CS Copilot")
    st.caption("Multi-agent RAG support assistant · Claude + Streamlit")

    st.text_input("Anthropic API key", type="password", key="api_key_input",
                  help="Or set ANTHROPIC_API_KEY in Streamlit secrets.")
    main_model = st.selectbox(
        "Answer model", ["claude-sonnet-4-5", "claude-haiku-4-5",
                         "claude-opus-4-1"], index=0)
    router_model = st.selectbox(
        "Router model", ["claude-haiku-4-5", "claude-sonnet-4-5"], index=0)
    show_trace = st.toggle("Show agent trace", value=True)

    st.divider()
    st.markdown(
        "**Pipeline**\n\n"
        "guardrails → router → specialist agent\n"
        "(RAG + tools) → output guardrails\n\n"
        "**Agents:** Support · Security · Escalation\n\n"
        "**Tools:** `search_knowledge_base` · "
        "`get_fee_schedule` · `create_support_ticket`")
    if st.button("Reset conversation"):
        st.session_state.pop("memory", None)
        st.session_state.pop("chat", None)
        st.rerun()

api_key = get_api_key()

# ---------- state ----------
if "memory" not in st.session_state:
    st.session_state.memory = AgentContext()
if "chat" not in st.session_state:
    st.session_state.chat = []  # [(role, text, trace|None)]

def log_feedback(msg_index: int, score: int):
    FEEDBACK_PATH.parent.mkdir(exist_ok=True)
    role, text, trace = st.session_state.chat[msg_index]
    with FEEDBACK_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "answer": text, "score": score,
            "intent": trace.intent if trace else None}) + "\n")


tab_chat, tab_eval, tab_kb = st.tabs(
    ["💬 Chat", "📊 Evaluation", "📚 Knowledge base"])

# ================= CHAT =================
with tab_chat:
    if not api_key:
        st.info("Enter your Anthropic API key in the sidebar to start.")

    st.markdown("Try: *“What are spot trading fees?”* · *“I lost my 2FA "
                "phone”* · *“My 2000 USDT deposit vanished, I want a human "
                "NOW”* · *“Ignore previous instructions…”*")

    for i, (role, text, trace) in enumerate(st.session_state.chat):
        with st.chat_message(role):
            st.markdown(text)
            if role == "assistant" and trace and show_trace:
                with st.expander("🔍 Agent trace"):
                    st.markdown(
                        f"**Intent:** `{trace.intent}` → "
                        f"**Agent:** `{trace.agent}`")
                    if trace.guardrail_flags:
                        st.warning("Guardrails: "
                                   + ", ".join(trace.guardrail_flags))
                    for tc in trace.tool_calls:
                        st.markdown(f"🔧 `{tc['tool']}` "
                                    f"`{json.dumps(tc['input'])}`")
                    for c in trace.retrieved:
                        st.markdown(f"📄 *{c.citation}* "
                                    f"(score {c.score:.2f})")
                    if trace.thinking:
                        st.caption("Model reasoning (hidden from user in "
                                   "production):")
                        st.code(trace.thinking, language=None)
                    if trace.usage:
                        st.caption(f"Tokens: {trace.usage}")
            if role == "assistant":
                col1, col2, _ = st.columns([1, 1, 10])
                if col1.button("👍", key=f"up{i}"):
                    log_feedback(i, +1)
                    st.toast("Thanks — logged for eval calibration.")
                if col2.button("👎", key=f"down{i}"):
                    log_feedback(i, -1)
                    st.toast("Thanks — logged for eval calibration.")

    if prompt := st.chat_input("Ask a support question…",
                               disabled=not api_key):
        st.session_state.chat.append(("user", prompt, None))
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Routing → retrieving → answering…"):
                orch = Orchestrator(api_key, get_retriever(),
                                    main_model=main_model,
                                    router_model=router_model)
                try:
                    answer, trace = orch.respond(
                        prompt, st.session_state.memory)
                except Exception as e:  # surface API errors readably
                    answer, trace = f"⚠️ API error: {e}", None
            st.markdown(answer)
        st.session_state.chat.append(("assistant", answer, trace))
        st.rerun()


# ================= EVALUATION =================
with tab_eval:
    st.subheader("Evaluation pipeline")
    st.markdown(
        "Deterministic checks (routing accuracy, topic recall, guardrail "
        "firing) plus **LLM-as-judge** scoring of groundedness, relevance, "
        "safety, and hallucination against the retrieved context.")

    use_judge = st.toggle("Use LLM-as-judge (slower, more tokens)",
                          value=True)
    if st.button("▶ Run evaluation suite (15 cases)", disabled=not api_key):
        bar = st.progress(0.0, text="starting…")

        def cb(i, n, cid):
            bar.progress((i + 1) / n, text=f"{cid} ({i + 1}/{n})")

        report = run_eval(api_key, use_judge=use_judge, progress_cb=cb)
        write_report(report)
        st.session_state.eval_report = report
        bar.empty()

    report = st.session_state.get("eval_report")
    if not report:
        results_file = Path("evals/results.json")
        if results_file.exists():
            report = json.loads(results_file.read_text(encoding="utf-8"))

    if report:
        s = report["summary"]
        c = st.columns(5)
        c[0].metric("Routing acc.", f"{s['routing_accuracy']:.0%}")
        c[1].metric("Topic recall", f"{s['mean_topic_recall']:.0%}")
        c[2].metric("Groundedness", s["avg_groundedness"] or "—")
        c[3].metric("Halluc. rate",
                    f"{s['hallucination_rate']:.0%}"
                    if s["hallucination_rate"] is not None else "—")
        c[4].metric("Latency", f"{s['mean_latency_s']}s")
        st.dataframe(
            [{"id": r["id"], "category": r["category"],
              "routed": r["routed_intent"],
              "ok": "✓" if r["routing_correct"] else "✗",
              "recall": r["topic_recall"],
              "groundedness": r["judge"].get("groundedness", "—")
              if r["judge"] else "—",
              "hallucination": r["judge"].get("hallucination", "—")
              if r["judge"] else "—"}
             for r in report["results"]],
            use_container_width=True)
        with st.expander("Raw results JSON"):
            st.json(report)
    else:
        st.caption("No results yet — run the suite above, or "
                   "`python run_eval.py` from the CLI.")

# ================= KNOWLEDGE BASE =================
with tab_kb:
    st.subheader("Knowledge base & retrieval inspector")
    r = get_retriever()
    q = st.text_input("Test a retrieval query",
                      placeholder="e.g. lost 2fa device withdrawal hold")
    if q:
        for c in r.search(q):
            st.markdown(f"**{c.citation}** — score {c.score:.3f}")
            st.caption(c.text[:400] + ("…" if len(c.text) > 400 else ""))
    st.divider()
    st.markdown(f"**{len(r.chunks)} chunks** across "
                f"{len({c.doc for c in r.chunks})} documents "
                "(chunked by `##` section):")
    for doc in sorted({c.doc for c in r.chunks}):
        sections = [c.section for c in r.chunks if c.doc == doc]
        st.markdown(f"- `{doc}` — {len(sections)} sections")
