from fastapi import APIRouter

from app.providers.factory import provider_info

router = APIRouter(prefix="/api/v1", tags=["settings"])


@router.get("/settings/providers")
def get_providers():
    return provider_info()
