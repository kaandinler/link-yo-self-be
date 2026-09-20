from fastapi import APIRouter

from routers.v1.social_account_router import router as router_v1

router = APIRouter(prefix="/social-accounts", tags=["social-accounts"])

# V1 API endpoint'lerini include et
router.include_router(router_v1)
