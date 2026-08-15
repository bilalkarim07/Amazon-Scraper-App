"""
main.py — FastAPI application entrypoint.

Start with:
    uv run uvicorn application.main:app --reload --port 8000
(run from the BackEnd/ directory)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application import database
from application.config import CORS_ORIGINS
from application.routes_health import router as health_router
from application.routes_jobs import router as jobs_router
from application.routes_files import router as files_router
from application.routes_quota import router as quota_router
from application.routes_marketplaces import router as marketplaces_router
from application.storage import ensure_directories, migrate_existing_data

# Set up logging
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown hooks
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Step 1: Create all required centralized directories (Database/, Files/, Jobs/)
    ensure_directories()
    logger.info("Centralized storage directories verified/created.")

    # Step 2: Migrate existing data from the old project‑relative location,
    #         if any, to the new centralized storage.
    migration_performed = migrate_existing_data()
    if migration_performed:
        logger.info("Data migration from legacy location completed.")
    else:
        logger.info("No legacy data migration needed.")

    # Step 3: Initialise the database (creates tables if needed).
    #         This will use the new centralized database path.
    database.init_db()
    logger.info("Database initialised.")

    yield
    # Shutdown: nothing to clean up in Phase 1


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Amazon Listing Scraper — API",
    description=(
        "Local backend that accepts scraping jobs from the TanStack frontend, "
        "orchestrates the ScraperEngine, and returns job status and output files."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow the TanStack dev server to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(files_router)
app.include_router(quota_router)
app.include_router(marketplaces_router)