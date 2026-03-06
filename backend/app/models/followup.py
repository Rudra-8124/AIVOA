# ─────────────────────────────────────────────────────────────────
# models/followup.py – Follow-up Action ORM model
#
# Stores follow-up tasks generated either manually by a rep or
# automatically suggested by the LangGraph AI agent.
# ─────────────────────────────────────────────────────────────────

import uuid
import enum
from datetime import datetime, date, timezone

from sqlalchemy import Text, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FollowupStatusEnum(str, enum.Enum):
    """Lifecycle state of a follow-up action."""
    pending   = "pending"
    completed = "completed"
    cancelled = "cancelled"


class FollowupAction(Base):
    """
    A single follow-up task linked to an interaction and HCP.

    Columns
    -------
    id                  : UUID primary key.
    interaction_id      : FK → interactions.id (required).
    hcp_id              : FK → hcps.id (required, denormalised for fast queries).
    action_description  : What the rep needs to do.
    due_date            : Target completion date.
    status              : ENUM – pending / completed / cancelled.
    suggested_by_ai     : True when created by the AI agent.
    created_at          : Creation timestamp.
    """

    __tablename__ = "followup_actions"

    # ── Primary key ───────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Foreign keys ──────────────────────────────────────────────
    interaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hcp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hcps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Task fields ───────────────────────────────────────────────
    action_description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[FollowupStatusEnum] = mapped_column(
        SAEnum(FollowupStatusEnum, name="followupstatus_enum", create_type=True),
        nullable=False,
        default=FollowupStatusEnum.pending,
        server_default="pending",
    )

    # ── AI provenance flag ────────────────────────────────────────
    suggested_by_ai: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Audit timestamp ───────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────────────
    interaction: Mapped["Interaction"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Interaction",
        back_populates="followup_actions",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<FollowupAction id={self.id} status={self.status} "
            f"interaction_id={self.interaction_id}>"
        )
