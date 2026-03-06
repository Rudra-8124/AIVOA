# ─────────────────────────────────────────────────────────────────
# models/product.py – Pharmaceutical Product ORM model
#
# Stores the product catalogue used for recommendations and
# sample tracking inside interactions.
# ─────────────────────────────────────────────────────────────────

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Product(Base):
    """
    A pharmaceutical product in the sales catalogue.

    Columns
    -------
    id           : UUID primary key.
    name         : Product brand/generic name (required).
    category     : Therapeutic category (e.g. Cardiology, Oncology).
    indication   : Clinical indication / approved use.
    key_messages : JSONB array of key marketing/clinical messages.
    created_at   : Creation timestamp.
    """

    __tablename__ = "products"

    # ── Primary key ───────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # ── Product details ───────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    indication: Mapped[str | None] = mapped_column(Text, nullable=True)

    # JSONB stores flexible list: ["Reduces LDL by 50%", "Once-daily dosing"]
    key_messages: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # ── Audit timestamp ───────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} name='{self.name}'>"
