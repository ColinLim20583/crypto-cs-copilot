"""Tool definitions and executors exposed to the agents (Anthropic tool-use).

`create_support_ticket` and `get_fee_schedule` are mocked with realistic
behavior; in production they would hit the ticketing system and fee service.
"""
from __future__ import annotations

import json
import random
import string
from typing import Any

FEE_SCHEDULE = {
    "spot": {"VIP0": {"maker": 0.10, "taker": 0.10},
             "VIP1": {"maker": 0.09, "taker": 0.10},
             "VIP2": {"maker": 0.08, "taker": 0.10},
             "VIP3": {"maker": 0.042, "taker": 0.06}},
    "usdm_futures": {"VIP0": {"maker": 0.02, "taker": 0.05}},
    "coinm_futures": {"VIP0": {"maker": 0.01, "taker": 0.05}},
    "token_discount_pct": 25,
}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "search_knowledge_base",
        "description": ("Search the help-center knowledge base. Returns the "
                        "most relevant documentation sections with citations. "
                        "Call before answering any factual question."),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string",
                                     "description": "search query"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_fee_schedule",
        "description": ("Get the exact current trading fee schedule "
                        "(maker/taker % by product and VIP tier)."),
        "input_schema": {
            "type": "object",
            "properties": {"product": {
                "type": "string",
                "enum": ["spot", "usdm_futures", "coinm_futures", "all"]}},
            "required": ["product"],
        },
    },
    {
        "name": "create_support_ticket",
        "description": ("Create a support ticket for a human specialist. Use "
                        "when the issue is case-specific, funds are at risk, "
                        "or the user asks for a human."),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "category": {"type": "string",
                             "enum": ["deposit", "withdrawal", "kyc",
                                      "security", "trading", "other"]},
                "priority": {"type": "string",
                             "enum": ["normal", "high", "urgent"]},
            },
            "required": ["summary", "category", "priority"],
        },
    },
]


def execute_tool(name: str, args: dict, retriever, memory) -> str:
    """Dispatch a tool call. `memory` is the shared AgentContext."""
    if name == "search_knowledge_base":
        chunks = retriever.search(args["query"])
        memory.retrieved.extend(chunks)
        return retriever.format_context(chunks)

    if name == "get_fee_schedule":
        product = args.get("product", "all")
        data = FEE_SCHEDULE if product == "all" else {
            product: FEE_SCHEDULE.get(product, {}),
            "token_discount_pct": FEE_SCHEDULE["token_discount_pct"]}
        return json.dumps(data)

    if name == "create_support_ticket":
        ticket_id = "CS-" + "".join(random.choices(string.digits, k=8))
        ticket = {"ticket_id": ticket_id, **args, "status": "open",
                  "sla_hours": {"urgent": 2, "high": 12, "normal": 24}[
                      args.get("priority", "normal")]}
        memory.tickets.append(ticket)
        return json.dumps(ticket)

    return json.dumps({"error": f"unknown tool {name}"})
