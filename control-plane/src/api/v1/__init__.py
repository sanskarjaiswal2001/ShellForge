"""API v1 routers."""

from fastapi import APIRouter

from src.api.v1 import (
    audit,
    auth,
    compliance,
    health,
    organizations,
    policies,
    sandboxes,
    scim,
    users,
)

router = APIRouter(prefix="/api/v1")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(scim.router)
router.include_router(sandboxes.router)
router.include_router(policies.router)
router.include_router(audit.router)
router.include_router(compliance.router)
