# ─────────────────────────────────────────────────────────────────
# ai_agent/graph.py – LangGraph StateGraph assembly (v2)
#
# Topology (linear with one conditional branch):
#
#   START
#     → input_node
#     → intent_node
#     → entity_extraction_node
#     → tool_selector_node
#     → [should_run_tool?]
#           ├─ YES → tool_executor_node → responder_node → END
#           └─ NO  → responder_node → END
#
# Design decisions:
# - One tool_executor_node replaces 5 bridge nodes → less graph complexity
# - Conditional branch is a binary yes/no (has tool vs chitchat)
# - get_compiled_graph() is lru_cache'd so the graph is compiled once
# ─────────────────────────────────────────────────────────────────

import logging
from functools import lru_cache

from langgraph.graph import StateGraph, START, END

from app.ai_agent.state import AgentState
from app.ai_agent.nodes import (
    input_node,
    intent_node,
    entity_extraction_node,
    tool_selector_node,
    tool_executor_node,
    responder_node,
    should_run_tool,
)

logger = logging.getLogger(__name__)


# ── Graph builder ─────────────────────────────────────────────────

def build_graph():
    """
    Construct and compile the LangGraph StateGraph.

    Full topology:
      START
        → input_node              (extract raw message, reset fields)
        → intent_node             (LLM: classify intent)
        → entity_extraction_node  (LLM: extract entities from message)
        → tool_selector_node      (logic: pick tool + build tool_input)
        → [should_run_tool]
              ├─ "tool_executor_node" → tool_executor_node
              │                            → responder_node → END
              └─ "responder_node"    → responder_node → END
    """
    graph = StateGraph(AgentState)

    # ── Register all 6 nodes ──────────────────────────────────────
    graph.add_node("input_node",              input_node)
    graph.add_node("intent_node",             intent_node)
    graph.add_node("entity_extraction_node",  entity_extraction_node)
    graph.add_node("tool_selector_node",      tool_selector_node)
    graph.add_node("tool_executor_node",      tool_executor_node)
    graph.add_node("responder_node",          responder_node)

    # ── Linear edges (always traverse) ───────────────────────────
    graph.add_edge(START,                      "input_node")
    graph.add_edge("input_node",               "intent_node")
    graph.add_edge("intent_node",              "entity_extraction_node")
    graph.add_edge("entity_extraction_node",   "tool_selector_node")

    # ── Conditional edge: run tool OR go straight to responder ───
    graph.add_conditional_edges(
        "tool_selector_node",
        should_run_tool,
        {
            "tool_executor_node": "tool_executor_node",
            "responder_node":     "responder_node",
        },
    )

    # ── After tool execution, always go to responder ─────────────
    graph.add_edge("tool_executor_node", "responder_node")

    # ── Responder always terminates the graph ────────────────────
    graph.add_edge("responder_node", END)

    compiled = graph.compile()
    logger.info(
        "[graph] Compiled StateGraph: 6 nodes, 1 conditional edge"
    )
    return compiled


@lru_cache(maxsize=1)
def get_compiled_graph():
    """
    Return the singleton compiled LangGraph.
    Built once on first call; subsequent calls return the cached object.
    Thread-safe due to Python GIL + lru_cache.
    """
    return build_graph()
