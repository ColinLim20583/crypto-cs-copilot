"""Multi-agent orchestration.

Pattern: router → specialist agent → guardrails, with shared memory.

    user message
        │
        ▼
  [input guardrails]  deterministic filters
        │
        ▼
     [Router]         Haiku, few-shot intent classification
        │
        ├── kb_question      → SupportAgent   (RAG + fee tool)
        ├── account_security → SecurityAgent  (RAG + ticket tool)
        ├── escalation       → EscalationAgent(RAG + ticket tool)
        ├── off_topic        → canned redirect
        └── unsafe           → canned refusal
        │
        ▼
  [output guardrails] credential/advice filters
        │
        ▼
      answer + trace (routing, retrieval, tool calls, flags)

Shared memory (`AgentContext`) carries conversation history, retrieved
chunks, and created tickets across turns, so any agent can see what a
previous agent already did. Equivalent LangGraph topology is documented in
the README; this hand-rolled orchestrator keeps the dependency surface
minimal and the control flow inspectable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from . import prompts
from .config import (MAIN_MODEL, MAX_TOKENS, MAX_TOOL_TURNS, ROUTER_MODEL,
                     TEMPERATURE)
from .guardrails import check_input, check_output
from .retrieval import Chunk, Retriever
from .tools import TOOL_SPECS, execute_tool

INTENTS = {"kb_question", "account_security", "escalation",
           "off_topic", "unsafe"}

AGENT_FOR_INTENT = {
    "kb_question": ("SupportAgent", prompts.SUPPORT_AGENT_SYSTEM),
    "account_security": ("SecurityAgent", prompts.SECURITY_AGENT_SYSTEM),
    "escalation": ("EscalationAgent", prompts.ESCALATION_AGENT_SYSTEM),
}


@dataclass
class AgentContext:
    """Shared memory across agents and turns."""
    history: list[dict] = field(default_factory=list)   # chat transcript
    retrieved: list[Chunk] = field(default_factory=list)
    tickets: list[dict] = field(default_factory=list)


@dataclass
class TurnTrace:
    intent: str = ""
    agent: str = ""
    guardrail_flags: list[str] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    retrieved: list[Chunk] = field(default_factory=list)
    thinking: str = ""
    usage: dict = field(default_factory=dict)


class Orchestrator:
    def __init__(self, api_key: str, retriever: Retriever | None = None,
                 main_model: str = MAIN_MODEL,
                 router_model: str = ROUTER_MODEL):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.retriever = retriever or Retriever()
        self.main_model = main_model
        self.router_model = router_model

    # ---------- router ----------
    def route(self, message: str) -> str:
        resp = self.client.messages.create(
            model=self.router_model, max_tokens=10, temperature=0,
            system=prompts.ROUTER_SYSTEM,
            messages=[{"role": "user", "content": message}],
        )
        intent = resp.content[0].text.strip().lower()
        return intent if intent in INTENTS else "kb_question"

    # ---------- specialist agent with tool loop ----------
    def run_agent(self, system: str, memory: AgentContext,
                  trace: TurnTrace) -> str:
        messages = list(memory.history)
        for _ in range(MAX_TOOL_TURNS):
            resp = self.client.messages.create(
                model=self.main_model, max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE, system=system,
                tools=TOOL_SPECS, messages=messages,
            )
            trace.usage = {
                "input_tokens": trace.usage.get("input_tokens", 0)
                + resp.usage.input_tokens,
                "output_tokens": trace.usage.get("output_tokens", 0)
                + resp.usage.output_tokens,
            }
            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content
                               if b.type == "text")
                return text

            # execute every tool call in this assistant turn
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                output = execute_tool(block.name, block.input,
                                      self.retriever, memory)
                trace.tool_calls.append(
                    {"tool": block.name, "input": block.input,
                     "output_preview": output[:400]})
                results.append({"type": "tool_result",
                                "tool_use_id": block.id, "content": output})
            messages.append({"role": "user", "content": results})
        return ("I wasn't able to finish resolving this automatically — "
                "I've noted the details; please try rephrasing or ask for "
                "a human agent.")

    # ---------- public entrypoint ----------
    def respond(self, message: str,
                memory: AgentContext) -> tuple[str, TurnTrace]:
        trace = TurnTrace()

        gr = check_input(message)
        trace.guardrail_flags += gr.flags
        if not gr.allowed:
            trace.intent, trace.agent = "blocked", "guardrail"
            memory.history += [
                {"role": "user", "content": message},
                {"role": "assistant", "content": gr.message}]
            return gr.message, trace

        trace.intent = self.route(message)

        if trace.intent == "off_topic":
            answer, trace.agent = prompts.OFF_TOPIC_REPLY, "canned"
        elif trace.intent == "unsafe":
            answer, trace.agent = prompts.UNSAFE_REPLY, "canned"
        else:
            trace.agent, system = AGENT_FOR_INTENT[trace.intent]
            memory.history.append({"role": "user", "content": message})
            n_before = len(memory.retrieved)
            raw = self.run_agent(system, memory, trace)
            trace.retrieved = memory.retrieved[n_before:]
            trace.thinking, answer = split_thinking(raw)
            answer, out_flags = check_output(answer, message)
            trace.guardrail_flags += out_flags
            memory.history.append({"role": "assistant", "content": answer})
            return answer, trace

        memory.history += [
            {"role": "user", "content": message},
            {"role": "assistant", "content": answer}]
        return answer, trace


def split_thinking(text: str) -> tuple[str, str]:
    """Separate <thinking> content from the user-facing answer."""
    m = re.search(r"<thinking>(.*?)</thinking>", text, re.S)
    thinking = m.group(1).strip() if m else ""
    answer = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S).strip()
    return thinking, answer or text.strip()
