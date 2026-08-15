# BackEnd/application/main.py

""" main.py — FastAPI application entrypoint. """

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from application import database
from application import files_database
from application.config import CORS_ORIGINS
from application.routes_health import router as health_router
from application.routes_jobs import router as jobs_router
from application.routes_files import router as files_router
from application.routes_quota import router as quota_router
from application.routes_marketplaces import router as marketplaces_router
from application.storage import ensure_directories, migrate_existing_data

logger = logging.getLogger(__name__)


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

    yield


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