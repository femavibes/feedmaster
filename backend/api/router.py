# backend/api/router.py
from fastapi import APIRouter

# This is the central router for the entire API.
# Other routers for specific features (like profiles, admin, feeds)
# should be included here.
#
# For example, if you create routers in subdirectories, you would import
# them relatively like this:
#
# from .v1.endpoints import profiles_router, admin_router
#
# api_router.include_router(profiles_router, prefix="/api/v1/profiles", tags=["Profiles"])
# api_router.include_router(admin_router, prefix="/admin", tags=["Admin"])

api_router = APIRouter()

@api_router.get("/api/v1/health", tags=["Health Check"])
async def health_check():
    """A simple endpoint to confirm the API is running."""
    return {"status": "ok"}
