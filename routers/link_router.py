from fastapi import APIRouter

from routers.v1.link_router import router as router_v1

router = APIRouter(prefix="/links", tags=["links"])

# V1 API endpoint'lerini include et
router.include_router(router_v1)