"""
LangGraph wiring for the multi-agent RE Elicitation pipeline — System 2 (V1).

Graph flow:
    planner → extractor → critic
                  ↑           |
                  └── revise ─┘  (if rejected + budget ok)
                              |
                            done → END

Usage:
    from src.systems.multi_agent.re_elicitation_graph import build_re_elicitation_graph, make_initial_state

    graph = build_re_elicitation_graph()
    result = graph.invoke(make_initial_state(project_id, use_case_description))
    requirements = result["final_requirements"]
"""
import os
from langgraph.graph import StateGraph, END

from src.schemas.graph_state import REElicitationState
from src.systems.multi_agent.nodes.re_elicitation.planner import re_elicitation_planner_node
from src.systems.multi_agent.nodes.re_elicitation.extractor import re_elicitation_extractor_node
from src.systems.multi_agent.nodes.re_elicitation.critic import re_elicitation_critic_node

MAX_ITERATIONS = int(os.getenv("RE_MAX_ITERATIONS", "3"))


def _route_after_critic(state: REElicitationState) -> str:
    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))
    budget_ok = (
        state.get("llm_calls", 0) < max_calls
        and state.get("total_tokens", 0) < max_tokens
        and state.get("iteration", 0) < MAX_ITERATIONS
    )
    if state.get("critique_approved", False) or not budget_ok:
        return "done"
    return "revise"


def _increment_iteration(state: REElicitationState) -> dict:
    return {"iteration": state.get("iteration", 0) + 1}


def _finalize_node(state: REElicitationState) -> dict:
    return {"final_requirements": state.get("draft_requirements", [])}


def build_re_elicitation_graph():
    g = StateGraph(REElicitationState)

    g.add_node("planner", re_elicitation_planner_node)
    g.add_node("extractor", re_elicitation_extractor_node)
    g.add_node("critic", re_elicitation_critic_node)
    g.add_node("increment", _increment_iteration)
    g.add_node("finalize", _finalize_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "extractor")
    g.add_edge("extractor", "critic")

    g.add_conditional_edges(
        "critic",
        _route_after_critic,
        {"revise": "increment", "done": "finalize"},
    )
    g.add_edge("increment", "extractor")
    g.add_edge("finalize", END)

    return g.compile()


def make_initial_state(project_id: str, use_case_description: str) -> REElicitationState:
    return {
        "project_id": project_id,
        "use_case_description": use_case_description,
        "plan": "",
        "domain": "",
        "sme_subject": "",
        "key_quality_attributes": [],
        "draft_requirements": [],
        "sme_requirements": [],
        "combined_requirements": [],
        "critique": None,
        "critique_approved": False,
        "final_requirements": [],
        "llm_calls": 0,
        "total_tokens": 0,
        "iteration": 0,
    }
