# backend/main.py
#
# This file serves as the main entry point for the FastAPI application.
# It sets up the API endpoints, handles dependencies, and integrates
# all other backend components (database, CRUD, schemas, auth, and worker).

import asyncio
import os
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Local imports
from .database import SessionLocal, engine, Base
from . import models, schemas, crud, auth_utils
from .aggregator_worker import run_worker as run_aggregator_worker, load_configurations, feeds_config as loaded_feeds_config # Import the worker function and configs

# --- FastAPI Application Setup ---

# Define the lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.
    This is where background tasks like the aggregator worker are started.
    """
    print("FastAPI application starting up...")

    # --- Database Initialization (for development/testing) ---
    # In a production environment, use Alembic for migrations (as discussed previously).
    # This ensures tables exist if running for the first time without migrations,
    # but does NOT handle schema changes or upgrades.
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables ensured (via create_all). Remember to use Alembic for production migrations.")
    except Exception as e:
        print(f"Error ensuring database tables: {e}")
        # Depending on criticality, you might want to exit here if DB is absolutely essential

    # --- Load Configuration Files ---
    try:
        load_configurations() # Load tiers and feeds configs into memory
        print("Configuration files loaded.")
    except Exception as e:
        print(f"Failed to load configurations: {e}. Exiting.")
        # If configs are critical for worker/API, raise error or exit
        raise

    # --- Start Aggregator Worker in a background task ---
    # We use asyncio.create_task to run the worker concurrently with the FastAPI app.
    print("Starting background Aggregator Worker...")
    app.state.aggregator_task = asyncio.create_task(run_aggregator_worker())
    print("Aggregator Worker task initiated.")

    yield # The application runs here

    # --- Shutdown Events ---
    print("FastAPI application shutting down...")
    if hasattr(app.state, 'aggregator_task') and not app.state.aggregator_task.done():
        print("Cancelling Aggregator Worker task...")
        app.state.aggregator_task.cancel()
        try:
            await app.state.aggregator_task
        except asyncio.CancelledError:
            print("Aggregator Worker task cancelled.")
        except Exception as e:
            print(f"Error during aggregator task cancellation: {e}")
    print("FastAPI application shut down.")


# Initialize FastAPI app with the lifespan context
app = FastAPI(
    title="Feedmaster Backend API",
    description="API for ingesting, aggregating, and serving content from Graze Contrails Feeds.",
    version="0.1.0",
    lifespan=lifespan # Attach the lifespan context manager
)

# --- CORS Middleware ---
# Configure CORS to allow your frontend (FeedMaster0.12.html) to communicate with the backend.
# In production, restrict `allow_origins` to your frontend's exact URL.
origins = [
    "http://localhost",
    "http://localhost:8000", # Default for uvicorn
    "http://localhost:3000", # Common for React/Vue dev servers
    "http://127.0.0.1:8000",
    "http://127.0.0.1:3000",
    # Add your deployed frontend URL here when available
    # "https://your-feedmaster-frontend.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allow all methods (GET, POST, PUT, DELETE, OPTIONS)
    allow_headers=["*"], # Allow all headers
)

# --- Dependency to get a SQLAlchemy DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- OAuth2 for token-based authentication (if needed for API protection) ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Authentication Utility Functions (from auth_utils.py) ---
async def get_current_user_did(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = auth_utils.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    did: str = payload.get("sub")
    if did is None:
        raise credentials_exception
    # In a real app, you might fetch the user from DB to ensure they exist/are active
    # db_user = crud.get_user(db, did) # Requires db session
    # if db_user is None:
    #     raise credentials_exception
    return did


# --- API Endpoints ---

@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint for the API.
    """
    return {"message": "Welcome to Feedmaster Backend API! Go to /docs for API documentation."}

@app.post("/token", response_model=schemas.Token, tags=["Authentication"])
async def login_for_access_token(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Endpoint for users to "log in" and receive an access token.
    For Bluesky DIDs, this might involve verifying the DID against a registered list,
    or a more complex challenge-response if you integrate with Bluesky's auth flow.
    For this simple setup, it creates a token for any provided DID, assuming
    it's an authenticated request from a trusted source or a user registering.
    In a real system, you would verify the user's identity (e.g., app password).
    """
    # For Feedmaster, if DIDs are from Bluesky, authentication is external.
    # This endpoint can be used to *issue* an internal session token for a DID
    # that has been "registered" or authorized to use your API.
    # For now, let's just issue a token for the provided DID.
    # In a more secure setup, you might check if this DID is allowed to access.

    # Here, we assume the `user_login.did` is what we're authenticating.
    # In a real scenario, you might have an 'app password' for the DID
    # or some other form of proof of ownership.
    # For now, we'll just create a dummy user if not exists and issue a token.

    db_user = crud.get_user(db, user_login.did)
    if not db_user:
        # If user doesn't exist, create a basic placeholder.
        # In a real system, this would be a more robust user registration.
        # We don't have handle/display_name here, so we default.
        print(f"User DID {user_login.did} not found, creating placeholder for token issuance.")
        db_user = crud.create_user(db, schemas.UserCreate(
            did=user_login.did,
            handle=f"user-{user_login.did.split(':')[-1][:8]}.bsky.social"
        ))
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user for token issuance."
            )

    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(
        data={"sub": user_login.did}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/users/me/", response_model=schemas.UserPublic, tags=["Users"])
async def read_users_me(current_user_did: str = Depends(get_current_user_did), db: Session = Depends(get_db)):
    """
    Get information about the current authenticated user.
    """
    db_user = crud.get_user(db, current_user_did)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return db_user

@app.get("/users/{user_did}", response_model=schemas.UserPublic, tags=["Users"])
async def read_user(user_did: str, db: Session = Depends(get_db)):
    """
    Get information about a specific user by their DID.
    """
    db_user = crud.get_user(db, user_did)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return db_user

@app.get("/feeds", response_model=List[schemas.FeedsConfig], tags=["Feeds"])
async def get_available_feeds():
    """
    Get a list of all configured feeds.
    """
    return loaded_feeds_config # Returns the feeds loaded from config/feeds.json

@app.get("/feeds/{feed_id}/posts", response_model=schemas.PostListResponse, tags=["Feeds", "Posts"])
async def get_posts_for_feed(
    feed_id: str,
    skip: int = 0,
    limit: int = 20, # Limit for typical feed pagination
    db: Session = Depends(get_db),
    # Require authentication for accessing feeds
    # current_user_did: str = Depends(get_current_user_did)
):
    """
    Retrieve posts for a specific feed, with pagination.
    """
    # First, check if the requested feed_id is valid based on loaded configurations
    if not any(f.id == feed_id for f in loaded_feeds_config):
        raise HTTPException(status_code=404, detail=f"Feed with ID '{feed_id}' not found.")

    posts = crud.get_posts_for_feed(db, feed_id=feed_id, skip=skip, limit=limit)
    # For response_model, we need to load author details for each post if UserPublic is nested
    # Pydantic's from_attributes=True often handles this if relationship is loaded
    # However, you might need to eagerly load or manually populate 'author' if it's not working automatically.
    # Example for manual population if needed:
    # posts_with_authors = []
    # for post in posts:
    #     if post.author: # Assuming post.author relationship is loaded by SQLAlchemy
    #         post_schema = schemas.PostPublic.model_validate(post, from_attributes=True)
    #         post_schema.author = schemas.UserPublic.model_validate(post.author, from_attributes=True)
    #         posts_with_authors.append(post_schema)
    #     else:
    #         posts_with_authors.append(schemas.PostPublic.model_validate(post, from_attributes=True))

    total_posts_in_feed = db.query(models.FeedPost).filter(models.FeedPost.feed_id == feed_id).count()

    return schemas.PostListResponse(
        posts=posts, # Pydantic will convert if from_attributes=True is set
        total=total_posts_in_feed,
        page=skip // limit + 1,
        size=len(posts)
    )


@app.get("/feeds/{feed_id}/aggregates/{agg_name}", response_model=schemas.AggregateInDB, tags=["Feeds", "Aggregates"])
async def get_feed_aggregate(
    feed_id: str,
    agg_name: str,
    timeframe: str = "24h", # Default timeframe for now, could be dynamic
    db: Session = Depends(get_db),
    # current_user_did: str = Depends(get_current_user_did) # Example: require auth
):
    """
    Retrieve specific aggregated data for a feed (e.g., top hashtags).
    """
    # First, check if the requested feed_id is valid based on loaded configurations
    if not any(f.id == feed_id for f in loaded_feeds_config):
        raise HTTPException(status_code=404, detail=f"Feed with ID '{feed_id}' not found.")

    aggregate = crud.get_aggregate(db, feed_id, agg_name, timeframe)
    if aggregate is None:
        raise HTTPException(status_code=404, detail=f"Aggregate '{agg_name}' for feed '{feed_id}' in timeframe '{timeframe}' not found.")
    return aggregate


# --- Admin/Internal Endpoints (Require Authentication) ---

# Example: Get all posts (consider pagination/filtering for large datasets)
@app.get("/admin/posts/", response_model=List[schemas.PostPublic], tags=["Admin"])
async def read_all_posts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_did: str = Depends(get_current_user_did) # Requires authentication
):
    """
    Retrieve all posts (admin access only).
    """
    # In a real app, you'd check if current_user_did has admin privileges
    print(f"Admin user {current_user_did} accessing all posts.")
    posts = crud.get_posts(db, skip=skip, limit=limit)
    return posts

# Example: Get all users (admin access only)
@app.get("/admin/users/", response_model=List[schemas.UserPublic], tags=["Admin"])
async def read_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user_did: str = Depends(get_current_user_did) # Requires authentication
):
    """
    Retrieve all users (admin access only).
    """
    print(f"Admin user {current_user_did} accessing all users.")
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users


# --- Main execution block for Uvicorn ---
if __name__ == "__main__":
    # Ensure the config directory exists for local testing
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Create dummy config files if they don't exist for easy local testing
    if not os.path.exists(TIERS_CONFIG_PATH):
        with open(TIERS_CONFIG_PATH, 'w') as f:
            json.dump([{"id": "test-tier", "name": "Test Tier", "description": "Desc", "min_followers": 0, "min_posts_daily": 0, "min_reputation_score": 0.0}], f, indent=2)
    if not os.path.exists(FEEDS_CONFIG_PATH):
        with open(FEEDS_CONFIG_PATH, 'w') as f:
            json.dump([{"id": "home", "name": "Home", "description": "Home feed", "criteria": {}}, {"id": "tech-news", "name": "Tech News", "description": "Tech feed", "criteria": {"keywords": ["#tech"]}}], f, indent=2)

    # Note: Uvicorn automatically discovers `app` when run from the command line
    # (e.g., `uvicorn main:app --reload`).
    # This `if __name__ == "__main__":` block is primarily for direct script execution,
    # or for setting up specific Uvicorn run configurations.
    uvicorn.run(app, host="0.0.0.0", port=8000)
