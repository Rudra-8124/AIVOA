# ─────────────────────────────────────────────────────────────────
# main.py – FastAPI application entry point
#
# Responsibilities:
#   1. Create and configure the FastAPI app instance
#   2. Register middleware (CORS, logging)
#   3. Register all API routers
#   4. Run DB initialisation on startup via lifespan handler
#   5. Provide a health-check endpoint
# ─────────────────────────────────────────────────────────────────

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if settings.APP_ENV == "production" else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan handler (startup / shutdown) ─────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Startup:
      - Create all DB tables that are not yet present.
        (In production, use Alembic migrations instead.)

    Shutdown:
      - Dispose the SQLAlchemy engine connection pool gracefully.
    """
    logger.info("🚀  AIVOA backend starting up …")
    await init_db()
    logger.info("✅  Database tables verified / created.")
    yield
    # ── Shutdown ──────────────────────────────────────────────────
    from app.database import engine
    await engine.dispose()
    logger.info("🛑  Database connection pool disposed. Bye!")


# ── FastAPI app factory ───────────────────────────────────────────

app = FastAPI(
    title="AIVOA – AI CRM HCP Interaction Logger",
    description=(
        "AI-first CRM module for pharmaceutical sales representatives. "
        "Log, edit, and analyse HCP interactions using structured forms "
        "or a conversational AI chat interface powered by LangGraph + Groq."
    ),
    version="1.0.0",
    docs_url="/docs",      # Swagger UI
    redoc_url="/redoc",    # ReDoc UI
    lifespan=lifespan,
)


# ── CORS middleware ────────────────────────────────────────────────
# Allow the React frontend (Vite dev server) and any configured origins.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Register routers ──────────────────────────────────────────────

from app.routers.interactions import router as interactions_router
from app.routers.interactions import plural_router as interactions_plural_router
from app.routers.hcp import router as hcp_router
from app.routers.agent import router as agent_router

# All routes are prefixed with /api for clean separation from static assets
app.include_router(interactions_router,        prefix="/api")
app.include_router(interactions_plural_router, prefix="/api")
app.include_router(hcp_router,                 prefix="/api")
app.include_router(agent_router,               prefix="/api")


# ── Health check ──────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
async def health_check() -> dict:
    """
    Simple liveness probe.
    Returns 200 OK with basic environment info when the service is running.
    """
    return {
        "status": "ok",
        "app": "AIVOA",
        "version": "1.0.0",
        "environment": settings.APP_ENV,
        "llm_model": settings.LLM_MODEL,
    }


# ── Dev server entry point ────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=(settings.APP_ENV == "development"),
        log_level="debug" if settings.APP_ENV == "development" else "info",
    )
