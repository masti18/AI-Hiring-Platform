"""LangGraph hiring pipeline skeleton.

Full node implementations land in later milestones. This file establishes the
stateful graph shape with config-driven auto-gates.
"""

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents.gates import gate1_post_sourcing_node, gate2_post_ai_call_node
from app.agents.state import HiringGraphState


async def intake_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "intake_complete"}


async def source_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "sourcing_complete", "candidates": state.get("candidates", [])}


async def ai_call_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "ai_call_complete", "call_evaluations": state.get("call_evaluations", [])}


async def offer_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "offer_ready"}


def _route_gate1(state: HiringGraphState) -> Literal["ai_call", "await_human", "reject"]:
    decision = state.get("gate1") or {}
    action = decision.get("action", "auto_approve")
    if action == "auto_approve":
        return "ai_call"
    if action == "await_human":
        return "await_human"
    return "reject"


def _route_gate2(state: HiringGraphState) -> Literal["offer", "await_human", "reject"]:
    decision = state.get("gate2") or {}
    action = decision.get("action", "auto_approve")
    if action == "auto_approve":
        return "offer"
    if action == "await_human":
        return "await_human"
    return "reject"


async def await_human_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "awaiting_human"}


async def reject_node(state: HiringGraphState) -> dict[str, Any]:
    return {"status": "rejected"}


def build_hiring_graph() -> StateGraph:
    graph = StateGraph(HiringGraphState)

    # Node names must not collide with HiringGraphState keys (LangGraph constraint).
    graph.add_node("intake_brief", intake_node)
    graph.add_node("source_candidates", source_node)
    graph.add_node("gate1_checkpoint", gate1_post_sourcing_node)
    graph.add_node("run_ai_call", ai_call_node)
    graph.add_node("gate2_checkpoint", gate2_post_ai_call_node)
    graph.add_node("write_offer", offer_node)
    graph.add_node("await_human_review", await_human_node)
    graph.add_node("reject_run", reject_node)

    graph.set_entry_point("intake_brief")
    graph.add_edge("intake_brief", "source_candidates")
    graph.add_edge("source_candidates", "gate1_checkpoint")
    graph.add_conditional_edges(
        "gate1_checkpoint",
        _route_gate1,
        {
            "ai_call": "run_ai_call",
            "await_human": "await_human_review",
            "reject": "reject_run",
        },
    )
    graph.add_edge("run_ai_call", "gate2_checkpoint")
    graph.add_conditional_edges(
        "gate2_checkpoint",
        _route_gate2,
        {
            "offer": "write_offer",
            "await_human": "await_human_review",
            "reject": "reject_run",
        },
    )
    graph.add_edge("write_offer", END)
    graph.add_edge("await_human_review", END)
    graph.add_edge("reject_run", END)

    return graph


def compile_hiring_graph():
    return build_hiring_graph().compile()
