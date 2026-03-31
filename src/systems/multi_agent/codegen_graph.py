"""
LangGraph wiring for the multi-agent Code Generation pipeline.

Graph flow:
    planner → extractor → critic → coder → test_runner
                                      ↑          |
                                      └─ repair ─┘  (if tests fail and budget ok)
                                                 |
                                               done → END

Usage:
    from src.systems.multi_agent.codegen_graph import build_codegen_graph

    graph = build_codegen_graph()
    initial_state = make_initial_state(record)
    result = graph.invoke(initial_state)
    final_code = result["final_code"]
    test_result = result["test_result"]
"""
import os
from langgraph.graph import StateGraph, END

from src.schemas.graph_state import CodeGenGraphState
from src.systems.multi_agent.nodes.planner import codegen_planner_node
from src.systems.multi_agent.nodes.extractor import codegen_extractor_node
from src.systems.multi_agent.nodes.critic import codegen_critic_node
from src.systems.multi_agent.nodes.coder import coder_node
from src.systems.multi_agent.nodes.test_runner import test_runner_node, should_repair


def _route_after_critic(state: CodeGenGraphState) -> str:
    """If critic approved, go straight to coder. If not approved and budget ok, loop back."""
    max_calls = int(os.getenv("MAX_LLM_CALLS_PER_TASK", "10"))
    max_tokens = int(os.getenv("MAX_TOKENS_PER_TASK", "8000"))
    budget_ok = (
        state.get("llm_calls", 0) < max_calls
        and state.get("total_tokens", 0) < max_tokens
    )
    # Always proceed to coder (critic is advisory here)
    return "code"


def build_codegen_graph() -> StateGraph:
    g = StateGraph(CodeGenGraphState)

    g.add_node("planner", codegen_planner_node)
    g.add_node("extractor", codegen_extractor_node)
    g.add_node("critic", codegen_critic_node)
    g.add_node("coder", coder_node)
    g.add_node("test_runner", test_runner_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "extractor")
    g.add_edge("extractor", "critic")
    g.add_conditional_edges("critic", _route_after_critic, {"code": "coder"})
    g.add_edge("coder", "test_runner")

    g.add_conditional_edges(
        "test_runner",
        should_repair,
        {"repair": "coder", "done": END},
    )

    return g.compile()


def make_initial_state(record: dict) -> CodeGenGraphState:
    return {
        "record": record,
        "plan": "",
        "constraints": [],
        "draft_code": None,
        "critique": None,
        "critique_approved": False,
        "final_code": None,
        "test_result": None,
        "repair_iteration": 0,
        "llm_calls": 0,
        "total_tokens": 0,
    }
