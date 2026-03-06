# models/__init__.py
# Convenience re-exports so "from app.models import HCP" works cleanly.

from app.models.hcp import HCP
from app.models.interaction import Interaction, InteractionTypeEnum, SentimentEnum
from app.models.product import Product
from app.models.followup import FollowupAction, FollowupStatusEnum

__all__ = [
    "HCP",
    "Interaction",
    "InteractionTypeEnum",
    "SentimentEnum",
    "Product",
    "FollowupAction",
    "FollowupStatusEnum",
]
