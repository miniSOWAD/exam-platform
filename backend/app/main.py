from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router

logger = logging.getLogger("examflow.database_migrations")
BACKEND_ROOT = Path(__file__).resolve().parent.parent


def upgrade_database_schema() -> None:
    """Apply all pending Alembic migrations before the API accepts requests.

    FastAPI Cloud deployments may launch ``app.main:app`` directly and skip the
    Dockerfile command. Without this startup step, newer ORM fields (notably
    ``exams.paper`` from migration 0005) can make even GET /exams return HTTP 500.
    """
    if not settings.auto_migrate:
        logger.warning(
            "Automatic database migrations are disabled (AUTO_MIGRATE=false). "
            "Deployments must run `alembic upgrade head` before serving traffic."
        )
        return

    alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    logger.info("Checking database schema and applying pending ExamFlow migrations...")
    command.upgrade(alembic_config, "head")
    logger.info("Database schema is up to date (Alembic head).")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migration I/O is blocking; keep it off the ASGI event loop. A migration
    # failure must stop startup rather than leave the app serving 500s on every
    # database-backed endpoint. env.py serializes concurrent PostgreSQL startups.
    await asyncio.to_thread(upgrade_database_schema)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.3.2",
    description="Online examination platform API",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(router, prefix="/api/v1")
