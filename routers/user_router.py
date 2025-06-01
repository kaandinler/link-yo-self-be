from fastapi import APIRouter

from routers.v1.user_router import router as router_v1

router = APIRouter(prefix="/users", tags=["users"])

# V1 API endpoint'lerini include et
router.include_router(router_v1)
