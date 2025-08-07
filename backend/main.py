from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
import os

# Import all the endpoint routers directly.
# Note that we are using 'config' instead of the empty 'config_manager'.
from .api.v1.endpoints import (
    admin,
    achievements,
    feeds,
    leaderboards,
    profiles,
    search,
    config,
)

# --- App Setup ---
app = FastAPI(
    title="Feedmaster API",
    description="API for serving feed data, stats, and managing achievements.",
    version="1.0.0",
    # Disable automatic redirect to trailing slash to prevent HTTP redirects
    redirect_slashes=False,
)

# --- CORS Middleware ---
# This is crucial for allowing the frontend (served as static files or from a
# different origin) to communicate with the backend API. Using "*" for origins
# is permissive and suitable for development but should be restricted to the
# actual frontend domain in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allows all origins for development
        "https://feedmaster.fema.monster",  # Your Cloudflare domain
        "http://localhost:5173",  # Vite dev server
        "http://192.168.0.184:8000",  # Local server
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Temporary Debugging Endpoint ---
@app.get("/debug/read-feeds-json", include_in_schema=False)
async def debug_read_feeds_json():
    """A temporary endpoint to test if feeds.json is readable from within the container."""
    import json
    import os
    config_dir = os.getenv("CONFIG_DIR", "config")
    feeds_file_path = os.path.join(config_dir, "feeds.json")
    if not os.path.exists(feeds_file_path):
        return JSONResponse(status_code=404, content={"error": "File not found", "path_checked": feeds_file_path})
    try:
        with open(feeds_file_path, "r") as f:
            content = json.load(f)
        return {"success": True, "content": content}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# --- API Routes ---
# Include all routers directly with their full path prefix.
app.include_router(achievements.router, prefix="/api/v1/achievements", tags=["Achievements"])
app.include_router(achievements.router, prefix="/achievement", tags=["Achievement Pages"])
app.include_router(feeds.router, prefix="/api/v1/feeds", tags=["Feeds"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(leaderboards.router, prefix="/api/v1/leaderboards", tags=["Leaderboards"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["Profiles"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
app.include_router(config.router, prefix="/api/v1/config_manager", tags=["Config Manager"])

# --- Frontend Serving ---
# Define the path to the frontend directory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_TEST_DIR = os.path.join(PROJECT_ROOT, "frontendtest")
FRONTEND_VUE_DIR = os.path.join(PROJECT_ROOT, "frontend", "dist")

# --- Static Files Mount ---
# This allows serving JS, CSS, etc. from the frontend directory.
app.mount("/static", StaticFiles(directory=FRONTEND_TEST_DIR), name="static")

# Mount Vue.js assets if available
if os.path.exists(FRONTEND_VUE_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_VUE_DIR, "assets")),
        name="vue-assets",
    )

# --- Explicit Routes for HTML Pages ---
# This is the most reliable way to serve the frontend pages. It ensures that
# paths like `/leaderboards` correctly serve `leaderboard.html`.

@app.get("/old-admin", tags=["Frontend"], response_class=FileResponse, include_in_schema=False)
async def serve_admin_page():
    """Serves the main achievement management page."""
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "admin.html"))

@app.get("/old-admin/aggregates", tags=["Frontend"], response_class=FileResponse, include_in_schema=False)
async def serve_aggregates_admin_page():
    """Serves the aggregate management page."""
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "aggregates_admin.html"))

@app.get("/old-leaderboards", tags=["Frontend"], response_class=FileResponse, include_in_schema=False)
async def serve_leaderboards_page():
    """Serves the leaderboards page."""
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "leaderboard.html"))

@app.get("/old-config_manager", tags=["Frontend"], response_class=FileResponse, include_in_schema=False)
async def serve_config_manager_page():
    """Serves the polling configuration manager page."""
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "config_manager.html"))

@app.get("/testpage", tags=["Frontend"], response_class=FileResponse, include_in_schema=False)
async def serve_test_page():
    """Serves the dynamic data testing page."""
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "testpage.html"))

# --- Vue.js SPA Routes ---
# These must be defined LAST to avoid catching API routes

@app.get("/", response_class=FileResponse, include_in_schema=False)
async def serve_vue_app_root():
    """Serves the Vue.js app at the root path."""
    if os.path.exists(FRONTEND_VUE_DIR):
        index_path = os.path.join(FRONTEND_VUE_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    # Fallback to old leaderboards page
    return FileResponse(os.path.join(FRONTEND_TEST_DIR, "leaderboard.html"))

# Specific Vue routes
@app.get("/feed/{feed_id}", response_class=FileResponse, include_in_schema=False)
async def serve_vue_feed_route(feed_id: str):
    """Serves Vue app for feed routes."""
    if os.path.exists(FRONTEND_VUE_DIR):
        index_path = os.path.join(FRONTEND_VUE_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/leaderboard", response_class=FileResponse, include_in_schema=False)
async def serve_vue_leaderboard_route():
    """Serves Vue app for leaderboard route."""
    if os.path.exists(FRONTEND_VUE_DIR):
        index_path = os.path.join(FRONTEND_VUE_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/admin", response_class=FileResponse, include_in_schema=False)
async def serve_vue_admin_route():
    """Serves Vue app for admin route."""
    if os.path.exists(FRONTEND_VUE_DIR):
        index_path = os.path.join(FRONTEND_VUE_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not found")