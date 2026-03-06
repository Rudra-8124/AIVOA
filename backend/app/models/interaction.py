# ─────────────────────────────────────────────────────────────────
# models/interaction.py – Interaction ORM model
#
# Records a single sales-rep ↔ HCP interaction event.
# Stores both structured fields AND the raw natural-language input
# from the AI chat interface so nothing is ever lost.
# ─────────────────────────────────────────────────────────────────

import uuid
import enum
from datetime import datetime, date, time, timezone

from sqlalchemy import (
    String,
    Text,
    Date,
    Time,
    DateTime,
    Boolean,
    ForeignKey,
    Enum as SAEnum,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Python enums (mirrored as PostgreSQL ENUM types) ──────────────

class InteractionTypeEnum(str, enum.Enum):
    """Channel through which the interaction took place."""
    in_person = "in_person"
    phone     = "phone"
    email     = "email"
    virtual   = "virtual"


class SentimentEnum(str, enum.Enum):
    """Overall sentiment of the interaction as assessed by the rep / AI."""
    positive = "positive"
    neutral  = "neutral"
    negative = "negative"


# ── ORM Model ─────────────────────────────────────────────────────

class Interaction(Base):
    """
    A single logged interaction between a sales rep and an HCP.

    Columns
    -------
    id                  : UUID primary key.
    hcp_id              : FK → hcps.id (required).
    interaction_type    : ENUM – in_person / phone / email / virtual.
    interaction_date    : Calendar date of the meeting.
    interaction_time    : Optional time-of-day.
    topics_discussed    : PostgreSQL TEXT[] array of topic strings.
    materials_shared    : TEXT[] array of material names/URLs.
    samples_distributed : JSONB array [{product_id, quantity}].
    sentiment           : ENUM – positive / neutral / negative.
    outcomes            : Free-text outcome summary.
    notes               : Additional free-form notes.
    raw_input           : Original natural-language text entered by rep.
    extracted_by_ai     : True when fields were populated by the AI agent.
    created_at / updated_at : Audit timestamps.
    """

    __tablename__ = "interactions"

    # ── Primary key ───────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Foreign key ───────────────────────────────────────────────
    hcp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hcps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Core structured fields ────────────────────────────────────
    interaction_type: Mapped[InteractionTypeEnum] = mapped_column(
        SAEnum(InteractionTypeEnum, name="interactiontype_enum", create_type=True),
        nullable=False,
        default=InteractionTypeEnum.in_person,
    )
    interaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    interaction_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # ── Array / JSON fields (PostgreSQL-native) ────────────────────
    # ARRAY(Text) stores a list of topic strings directly in the column
    topics_discussed: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    materials_shared: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    # JSONB for flexible sample records: [{product_id: str, quantity: int}]
    samples_distributed: Mapped[list[dict] | None] = mapped_column(
        JSONB, nullable=True
    )

    # ── Sentiment & outcomes ──────────────────────────────────────
    sentiment: Mapped[SentimentEnum | None] = mapped_column(
        SAEnum(SentimentEnum, name="sentiment_enum", create_type=True),
        nullable=True,
    )
    outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── AI provenance fields ──────────────────────────────────────
    raw_input: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Original natural-language text from the rep",
    )
    extracted_by_ai: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ── Audit timestamps ──────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────────────
    hcp: Mapped["HCP"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "HCP",
        back_populates="interactions",
        lazy="select",
    )
    followup_actions: Mapped[list["FollowupAction"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "FollowupAction",
        back_populates="interaction",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<Interaction id={self.id} hcp_id={self.hcp_id} "
            f"date={self.interaction_date} type={self.interaction_type}>"
        )
