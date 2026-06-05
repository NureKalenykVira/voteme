import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.cloudinary_client import init_cloudinary
from app.api.routers.admin import router as admin_router
from app.api.routers.audit import router as audit_router
from app.api.routers.auth import router as auth_router
from app.api.routers.elections import router as elections_router
from app.api.routers.elections import voter_router as whitelist_router
from app.api.routers.elections import vote_router as voting_router
from app.api.routers.health import router as health_router
from app.core.config import settings
from app.middleware.maintenance import MaintenanceMiddleware
from app.scheduler import get_scheduler
from app.scheduler.voting_scheduler import catch_up_on_boot, schedule_tick

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_cloudinary()

    try:
        await catch_up_on_boot()
    except Exception:
        logger.exception("catch_up_on_boot crashed at startup")

    scheduler = get_scheduler()
    schedule_tick()
    if not scheduler.running:
        scheduler.start()

    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=True)


app = FastAPI(
    title="VoteMe API",
    version="0.1.0",
    description="Backend API for VoteMe blockchain-oriented electronic voting platform.",
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registered after CORS so CORS stays the outermost layer.
app.add_middleware(MaintenanceMiddleware)

os.makedirs("uploads/backups", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(health_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(audit_router, prefix="/audit")
app.include_router(admin_router, prefix="/admin")
app.include_router(elections_router, prefix="/elections")
app.include_router(whitelist_router, prefix="/elections")
app.include_router(voting_router, prefix="/elections")
