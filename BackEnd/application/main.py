# BackEnd/application/main.py
""" main.py — FastAPI application entrypoint. """
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application import database
from application import files_database
from application import quota_service
from application.config import CORS_ORIGINS
from application.routes_health import router as health_router
from application.routes_jobs import router as jobs_router
from application.routes_files import router as files_router
from application.routes_quota import router as quota_router
from application.routes_marketplaces import router as marketplaces_router
from application.storage import ensure_directories, migrate_existing_data

logger = logging.getLogger(__name__)


async def periodic_quota_maintenance():
    """
    Lightweight background task that runs approximately every hour.
    This is a maintenance optimization — correctness does not depend on it.
    """
    while True:
        await asyncio.sleep(3600)  # 1 hour
        try:
            quota_service.check_and_reset_quota()
            logger.info("[QUOTA] Hourly maintenance check completed")
        except Exception as e:
            logger.exception("[QUOTA] Hourly maintenance error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Step 1: Create all required centralized directories
    ensure_directories()
    logger.info("Centralized storage directories verified/created.")

    # Step 2: Migrate existing data from legacy location
    migration_performed = migrate_existing_data()
    if migration_performed:
        logger.info("Data migration from legacy location completed.")
    else:
        logger.info("No legacy data migration needed.")

    # Step 3: Initialise the main database (jobs + quota)
    database.init_db()
    logger.info("Main database (app.db) initialised.")

    # Step 4: Initialise the files database
    files_database.init_files_db()
    logger.info("Files database (files.db) initialised.")

    # Step 5: CRITICAL — Immediate quota check on startup
    # This ensures that if the backend was offline for >24 hours,
    # the quota is reset before any requests are served.
    try:
        quota_service.check_and_reset_quota()
        logger.info("[QUOTA] Startup quota check completed")
    except Exception as e:
        logger.exception("[QUOTA] Startup quota check failed: %s", e)

    # Step 6: Start the periodic maintenance task
    maintenance_task = asyncio.create_task(periodic_quota_maintenance())
    logger.info("[QUOTA] Hourly maintenance task started")

    try:
        yield
    finally:
        # Clean shutdown
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass
        logger.info("[QUOTA] Hourly maintenance task cancelled")


app = FastAPI(
    title="Amazon Listing Scraper — API",
    description=(
        "Local backend that accepts scraping jobs from the TanStack frontend, "
        "orchestrates the ScraperEngine, and returns job status and output files."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(files_router)
app.include_router(quota_router)
app.include_router(marketplaces_router)