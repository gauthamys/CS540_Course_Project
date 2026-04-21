"""
LangGraph wiring for the multi-agent Requirements Engineering pipeline.

Graph flow:
    planner → extractor → critic
                 ↑           |
                 └── revise ─┘  (if critique not approved and budget ok)
                             |
                           done → END

Usage:
    from src.systems.multi_agent.re_graph import build_re_graph

    graph = build_re_graph()
    initial_state = {
        "record": record_dict,
        "dataset": "nice",
        "plan": "",
        "draft_prediction": None,
        "critique": None,
        "critique_approved": False,
        "final_prediction": None,
        "llm_calls": 0,
        "total_tokens": 0,
        "iteration": 0,
    }
    result = graph.invoke(initial_state)
    prediction = result["final_prediction"]
"""
import os
from langgraph.graph import StateGraph, END

from src.schemas.graph_state import REGraphState
from src.systems.multi_agent.nodes.re_classification.planner import re_planner_node
from src.systems.multi_agent.nodes.re_classification.extractor import re_extractor_node
from src.systems.multi_agent.nodes.re_classification.critic import re_critic_node


def _route_after_critic(state: REGraphState) -> str:
    """Route to 'revise' or 'done' based on critic approval and budget."""
    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))

    budget_ok = (
        state.get("llm_calls", 0) < max_calls
        and state.get("total_tokens", 0) < max_tokens
    )
    if state.get("critique_approved", False) or not budget_ok:
        return "done"
    return "revise"


def _finalize_node(state: REGraphState) -> dict:
    """Copy draft_prediction to final_prediction."""
    return {"final_prediction": state.get("draft_prediction")}


def build_re_graph() -> StateGraph:
    g = StateGraph(REGraphState)

    g.add_node("planner", re_planner_node)
    g.add_node("extractor", re_extractor_node)
    g.add_node("critic", re_critic_node)
    g.add_node("finalize", _finalize_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "extractor")
    g.add_edge("extractor", "critic")

    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"revise": "extractor", "done": "finalize"},
    )
    g.add_edge("finalize", END)

    return g.compile()


def make_initial_state(record: dict) -> REGraphState:
    return {
        "record": record,
        "dataset": record.get("source", "unknown"),
        "plan": "",
        "draft_prediction": None,
        "critique": None,
        "critique_approved": False,
        "final_prediction": None,
        "llm_calls": 0,
        "total_tokens": 0,
        "iteration": 0,
    }
