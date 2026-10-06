from fastapi import APIRouter

from app.api.v1 import auth, config, health, internal, orgs, scans

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(config.router)
api_router.include_router(auth.router)
api_router.include_router(orgs.router)
api_router.include_router(scans.router)
api_router.include_router(internal.router)
