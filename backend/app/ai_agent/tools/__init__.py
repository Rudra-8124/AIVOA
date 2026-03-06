# ai_agent/tools/__init__.py
# Convenience re-export of all LangChain tool callables.

from app.ai_agent.tools.log_interaction import log_interaction_tool
from app.ai_agent.tools.edit_interaction import edit_interaction_tool
from app.ai_agent.tools.fetch_hcp_history import fetch_hcp_history_tool
from app.ai_agent.tools.suggest_followup import suggest_followup_tool
from app.ai_agent.tools.product_recommendation import product_recommendation_tool

# List consumed by create_react_agent / bind_tools
ALL_TOOLS = [
    log_interaction_tool,
    edit_interaction_tool,
    fetch_hcp_history_tool,
    suggest_followup_tool,
    product_recommendation_tool,
]

__all__ = [
    "log_interaction_tool",
    "edit_interaction_tool",
    "fetch_hcp_history_tool",
    "suggest_followup_tool",
    "product_recommendation_tool",
    "ALL_TOOLS",
]
