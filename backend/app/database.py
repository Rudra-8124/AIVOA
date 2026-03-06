# ─────────────────────────────────────────────────────────────────
# database.py – Async SQLAlchemy engine, session factory, and base
#
# Pattern used: async context-managed sessions via AsyncSessionLocal.
# Each request gets its own session through the `get_db` dependency.
# ─────────────────────────────────────────────────────────────────

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# ── Engine ────────────────────────────────────────────────────────
# echo=True logs all SQL statements – helpful during development.
# Set pool_pre_ping=True to recover from dropped DB connections.
#
# Supabase Session Pooler (PgBouncer) requires:
#   - prepared_statement_cache_size=0  → disables asyncpg's prepared
#     statement cache (PgBouncer transaction mode doesn't support them)
#   - statement_cache_size=0           → same, for the raw connection
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    },
)

# ── Session factory ───────────────────────────────────────────────
# expire_on_commit=False keeps ORM objects usable after commit
# (important for returning data in async FastAPI responses).
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Declarative base ──────────────────────────────────────────────
# All ORM models inherit from this class.
class Base(DeclarativeBase):
    pass


# ── FastAPI dependency ────────────────────────────────────────────
async def get_db() -> AsyncSession:  # type: ignore[return]
    """
    Yield an async database session for use in FastAPI route dependencies.
    Automatically commits on success and rolls back on error.

    Usage in a router:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Table initialisation helper ───────────────────────────────────
async def init_db() -> None:
    """
    Create all tables that are registered on the Base metadata.
    Called once at application startup (lifespan handler in main.py).
    In production prefer Alembic migrations over this helper.
    """
    async with engine.begin() as conn:
        # Import models here so their metadata is registered before create_all
        from app.models import hcp, interaction, product, followup  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)
