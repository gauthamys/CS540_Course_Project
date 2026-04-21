"""
LangGraph wiring for the V2 multi-agent Code Generation pipeline.

Extends the original graph with a Test Critic node that runs only when
all tests pass. The critic evaluates test sufficiency and, if unsatisfied,
appends new edge-case tests and re-runs the test runner. If the augmented
tests expose a bug the graph routes back to the Coder for repair.

Graph flow:
    planner → extractor → critic → coder → test_runner_v2
                                      ↑          |
                                      |     pass  └──→ test_critic
                                      |                    |
                                      |      insufficient  └──→ test_runner_v2
                                      |                              |
                                      └─ repair (fail) ─────────────┘
                                                         done → END

Budget guards prevent any loop from running forever.

Usage:
    from src.systems.multi_agent.codegen_graph_v2 import build_codegen_graph_v2

    graph = build_codegen_graph_v2()
    result = graph.invoke(make_initial_state(record))
    final_code   = result["final_code"]
    test_result  = result["test_result"]
    augmented    = result["augmented_test_code"]   # enriched suite if critic ran
"""
import os
from langgraph.graph import StateGraph, END

from src.schemas.graph_state import CodeGenGraphStateV2
from src.systems.multi_agent.nodes.codegen.planner import codegen_planner_node
from src.systems.multi_agent.nodes.codegen.extractor import codegen_extractor_node
from src.systems.multi_agent.nodes.codegen.critic import codegen_critic_node
from src.systems.multi_agent.nodes.codegen.coder import coder_node
from src.systems.multi_agent.nodes.codegen.test_runner import (
    test_runner_v2_node,
    should_repair_or_critique,
)
from src.systems.multi_agent.nodes.codegen.test_critic import test_critic_node, should_augment


def _route_after_critic(state: CodeGenGraphStateV2) -> str:
    """Critic is advisory — always proceed to coder."""
    return "code"


def build_codegen_graph_v2() -> StateGraph:
    g = StateGraph(CodeGenGraphStateV2)

    g.add_node("planner", codegen_planner_node)
    g.add_node("extractor", codegen_extractor_node)
    g.add_node("critic", codegen_critic_node)
    g.add_node("coder", coder_node)
    g.add_node("test_runner", test_runner_v2_node)
    g.add_node("test_critic", test_critic_node)

    g.set_entry_point("planner")
    g.add_edge("planner", "extractor")
    g.add_edge("extractor", "critic")
    g.add_conditional_edges("critic", _route_after_critic, {"code": "coder"})
    g.add_edge("coder", "test_runner")

    # After test_runner: pass → test_critic | fail → repair or done
    g.add_conditional_edges(
        "test_runner",
        should_repair_or_critique,
        {"critique": "test_critic", "repair": "coder", "done": END},
    )

    # After test_critic: insufficient → re-run tests | sufficient → done
    g.add_conditional_edges(
        "test_critic",
        should_augment,
        {"augment": "test_runner", "done": END},
    )

    return g.compile()


def make_initial_state(record: dict) -> CodeGenGraphStateV2:
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
        "augmented_test_code": None,
        "test_critique": None,
        "test_critique_approved": False,
        "test_critique_iteration": 0,
        "llm_calls": 0,
        "total_tokens": 0,
    }
