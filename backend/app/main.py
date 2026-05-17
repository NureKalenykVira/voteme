from fastapi import FastAPI

from app.api.routers.health import router as health_router

app = FastAPI(
    title="VoteMe API",
    version="0.1.0",
    description="Backend API for VoteMe blockchain-oriented electronic voting platform.",
)

app.include_router(health_router)