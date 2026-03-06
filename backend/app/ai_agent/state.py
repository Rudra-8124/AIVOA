# ─────────────────────────────────────────────────────────────────
# ai_agent/state.py – LangGraph AgentState definition
#
# TypedDict used as the graph's shared state object.
# Every node reads from and writes to this state.
#
# State lifecycle per request:
#   START → input_node → intent_node → entity_extraction_node
#         → tool_selector_node → tool_executor_node → responder_node → END
# ─────────────────────────────────────────────────────────────────

from typing import Optional, Any, List
from typing_extensions import TypedDict, Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class ExtractedEntities(TypedDict, total=False):
    """
    Strongly-typed container for all entities the agent can extract
    from a user's natural-language message.

    All fields are optional because partial extraction is valid —
    the agent will only use what is present.
    """
    # ── HCP identification ────────────────────────────────────────
    hcp_name: Optional[str]           # "Dr. Smith"
    hcp_specialty: Optional[str]      # "Cardiology"

    # ── Interaction core fields ───────────────────────────────────
    interaction_id: Optional[str]     # UUID string for edit/followup
    interaction_type: Optional[str]   # in_person | phone | email | virtual
    interaction_date: Optional[str]   # YYYY-MM-DD
    interaction_time: Optional[str]   # HH:MM

    # ── Content fields ────────────────────────────────────────────
    topics_discussed: Optional[List[str]]
    materials_shared: Optional[List[str]]
    samples_distributed: Optional[List[dict]]   # [{product_name, quantity}]
    sentiment: Optional[str]                    # positive | neutral | negative
    outcomes: Optional[str]
    followup_actions: Optional[List[str]]       # manually stated actions

    # ── Filter/query fields ───────────────────────────────────────
    from_date: Optional[str]          # YYYY-MM-DD range start
    to_date: Optional[str]            # YYYY-MM-DD range end

    # ── Edit-specific ─────────────────────────────────────────────
    field_to_edit: Optional[str]      # which field the rep wants to change
    new_value: Optional[str]          # the new value for that field


class AgentState(TypedDict):
    """
    Shared state passed between all nodes in the LangGraph graph.

    Fields
    ------
    messages            : Full conversation history (user + assistant turns).
                          add_messages reducer appends — required by LangGraph.
    session_id          : Identifies the ongoing chat session.
    raw_user_input      : The latest raw message string (extracted once).
    intent              : Classified intent:
                          log | edit | query_history | suggest_followup |
                          product_recommendation | chitchat
    intent_confidence   : Float 0-1 confidence of the intent classification.
    entities            : ExtractedEntities dict from the NL extraction node.
    hcp_context         : Resolved HCP record from DB (dict), if found.
    selected_tool       : Name of the tool the tool_selector chose.
    tool_input          : Final, validated input dict passed to the tool.
    tool_result         : Raw structured return value of the executed tool.
    action_taken        : Human-readable name of the tool that ran.
    confirmation_payload: Payload held pending user confirmation (HITL).
    requires_confirmation: True → agent is waiting for human yes/no.
    error               : Error message from any failed node.
    retry_count         : Number of extraction retries attempted.
    """

    messages:               Annotated[list[BaseMessage], add_messages]
    session_id:             str
    raw_user_input:         Optional[str]
    intent:                 Optional[str]
    intent_confidence:      Optional[float]
    entities:               Optional[ExtractedEntities]
    hcp_context:            Optional[dict]
    selected_tool:          Optional[str]
    tool_input:             Optional[dict]
    tool_result:            Optional[Any]
    action_taken:           Optional[str]
    confirmation_payload:   Optional[dict]
    requires_confirmation:  bool
    error:                  Optional[str]
    retry_count:            int
