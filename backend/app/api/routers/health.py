from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    response_model=HealthResponse,
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")