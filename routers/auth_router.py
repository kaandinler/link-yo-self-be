from fastapi import APIRouter

from routers.v1.auth_router import router as router_v1

router = APIRouter(prefix="/auth", tags=["auth"])

# V1 API endpoint'lerini include et
router.include_router(router_v1)
