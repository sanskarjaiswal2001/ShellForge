"""API v1 routers."""

from fastapi import APIRouter

from src.api.v1 import auth, audit, health, organizations, scim, users

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(scim.router)
router.include_router(audit.router)
