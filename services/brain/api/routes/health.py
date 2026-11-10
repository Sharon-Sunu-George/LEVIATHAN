from fastapi import APIRouter, Depends
from api.dependencies.auth import require_local_auth
from core.config import settings
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health_check(authenticated: bool = Depends(require_local_auth)) -> HealthResponse:
    """Authenticated health check endpoint."""
    return HealthResponse(
        status="ok",
        service=settings.SERVICE_NAME,
        version=settings.VERSION,
    )

