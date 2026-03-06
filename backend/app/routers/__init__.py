# routers/__init__.py
from app.routers.interactions import router as interactions_router
from app.routers.interactions import plural_router as interactions_plural_router
from app.routers.hcp import router as hcp_router
from app.routers.agent import router as agent_router

__all__ = ["interactions_router", "interactions_plural_router", "hcp_router", "agent_router"]
