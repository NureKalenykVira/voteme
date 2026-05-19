from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.audit import router as audit_router
from app.api.routers.auth import router as auth_router
from app.api.routers.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title="VoteMe API",
    version="0.1.0",
    description="Backend API for VoteMe blockchain-oriented electronic voting platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router, prefix="/auth")
app.include_router(audit_router, prefix="/audit")
