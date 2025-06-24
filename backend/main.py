import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta, datetime, timezone
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware # Import CORS middleware

from . import models, schemas, crud, auth_utils
from .database import engine, get_db

# Load environment variables
load_dotenv()

# Create all database tables (if they don't exist)
# This will be run on FastAPI app startup
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FeedMaster Backend API",
    description="API for managing users, feeds, and aggregate data for FeedMaster.",
    version="1.0.0",
)

# Configure CORS (Cross-Origin Resource Sharing)
# This is crucial for your frontend (running on one origin) to make requests
# to your backend (running on a different origin, e.g., localhost:8000).
origins = [
    "http://localhost",
    "http://localhost:3000", # Example if your frontend runs on React dev server
    "http://localhost:5000", # Example if your frontend runs on another port
    # Add the production URL of your frontend here when deployed
    # e.g., "https://your-feedmaster-frontend.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"], # Allows all headers (including Authorization)
)


# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- Authentication Endpoints ---

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.get_user_by_username(db, username=form_data.username)
    if not user or not auth_utils.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth_utils.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_utils.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.UserResponse)
async def read_users_me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return current_user

# --- User Endpoints (Admin or Self-Management) ---

@app.post("/users/", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/{user_id}", response_model=schemas.UserResponse)
def read_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this user's profile")
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return db_user

# --- Feed Endpoints ---
# These endpoints are for managing feeds (create, read, update, delete).
# The actual feed content/aggregates are retrieved via separate /api/feed_data/{feed_id} below.

@app.post("/users/me/feeds/", response_model=schemas.FeedResponse, status_code=status.HTTP_201_CREATED)
def create_feed_for_current_user(feed: schemas.FeedCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    return crud.create_user_feed(db=db, feed=feed, user_id=current_user.id)

@app.get("/users/me/feeds/", response_model=List[schemas.FeedResponse])
def read_feeds_for_current_user(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    feeds = crud.get_user_feeds(db, user_id=current_user.id, skip=skip, limit=limit)
    # Map to schema that includes owner_tier for frontend convenience
    return [schemas.FeedResponse(owner_tier=feed.owner.tier, **feed.model_dump()) for feed in feeds]


@app.get("/feeds/{feed_id}", response_model=schemas.FeedResponse)
def read_feed(feed_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    db_feed = crud.get_feed(db, feed_id=feed_id)
    if db_feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    if db_feed.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this feed")
    # Include owner's tier
    return schemas.FeedResponse(owner_tier=db_feed.owner.tier, **db_feed.model_dump())

@app.get("/feeds/by-name/{feed_name}", response_model=schemas.FeedResponse)
def read_feed_by_name(feed_name: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    db_feed = crud.get_feed_by_name(db, name=feed_name)
    if db_feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    if db_feed.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this feed")
    # Include owner's tier
    return schemas.FeedResponse(owner_tier=db_feed.owner.tier, **db_feed.model_dump())


@app.put("/feeds/{feed_id}", response_model=schemas.FeedResponse)
def update_feed(feed_id: int, feed: schemas.FeedUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    db_feed = crud.get_feed(db, feed_id=feed_id)
    if db_feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    if db_feed.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this feed")
    updated_feed = crud.update_feed(db=db, db_feed=db_feed, feed_update=feed)
    return schemas.FeedResponse(owner_tier=updated_feed.owner.tier, **updated_feed.model_dump())


@app.delete("/feeds/{feed_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feed(feed_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    db_feed = crud.get_feed(db, feed_id=feed_id)
    if db_feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feed not found")
    if db_feed.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this feed")
    if not crud.delete_feed(db=db, feed_id=feed_id):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not delete feed")
    return {"message": "Feed deleted successfully"}

# --- Feed Data Endpoints (for the main FeedMaster frontend to consume) ---

@app.get("/api/feed_data/{feed_name}", response_model=Dict[str, Any])
def get_feed_data_for_frontend(feed_name: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth_utils.get_current_user)):
    """
    Returns all necessary data for a specific feed, including its main content
    and all its stats categories, formatted for the FeedMaster frontend.
    """
    db_feed = crud.get_feed_by_name(db, name=feed_name)
    if db_feed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feed '{feed_name}' not found")
    
    # Ensure current user owns or has access to this feed
    # For now, only owner can access. You might extend this later.
    if db_feed.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access data for this feed")

    # Fetch the most recent aggregate data for this feed
    # We fetch ALL data for this feed, and let the frontend (or an admin-defined config)
    # filter and order it. We'll fetch a reasonable limit for each type.
    
    # In a real system, you might fetch specific aggregate types,
    # or the latest N entries for each type. For simplicity, we get all.
    all_raw_feed_data = crud.get_feed_data(db, feed_id=db_feed.id, limit=50) # Get up to 50 latest data points

    # Organize raw data by aggregate_type for easier processing
    organized_data = {}
    for item in all_raw_feed_data:
        if item.aggregate_type not in organized_data:
            organized_data[item.aggregate_type] = []
        organized_data[item.aggregate_type].append(item.data) # Store the JSON data directly

    # Construct the response in the format the frontend expects (similar to feedsData in old HTML)
    # The frontend will apply its `ALL_AGGREGATE_TYPES_METADATA` and `feed.configuration`
    # to filter and order these.
    
    # Frontend's `contentHtml` will be `db_feed.description` for now, or dynamically generated.
    # Frontend will also dynamically generate feed title/description from `db_feed.title`, `db_feed.description`.
    
    response_data = {
        "id": db_feed.name, # Use feed name as ID for frontend
        "title": db_feed.title,
        "description": db_feed.description,
        "owner_tier": current_user.tier, # Pass the tier of the user viewing it
        "configuration": db_feed.configuration, # Pass the feed's saved configuration to frontend

        "statsCategories": []
    }

    # Iterate through all possible aggregate types and fill in data if available
    # The frontend will then filter these based on `response_data.configuration`
    # and its own `ALL_AGGREGATE_TYPES_METADATA`.
    for agg_type_meta in auth_utils.ALL_AGGREGATE_TYPES_METADATA: # Use ALL_AGGREGATE_TYPES_METADATA from auth_utils
        agg_id = agg_type_meta['id']
        agg_name = agg_type_meta['name']

        if agg_id in organized_data:
            # We take the *most recent* entry for each aggregate type for simplicity.
            # In a more complex system, you might average, sum, etc. over a time window.
            most_recent_data_point = organized_data[agg_id][0] # Assuming first is most recent due to timestamp desc order
            response_data["statsCategories"].append({
                "type": agg_id,
                "title": agg_name, # Frontend can use this
                "data": most_recent_data_point # This holds the actual aggregate data (e.g., {"items": [...]})
            })
    
    return response_data

# --- Public Endpoints (No Auth Required) ---
# These endpoints could be for public feed directories if you later build one.
# For now, let's keep them auth-gated or limit to basic info.

# Example: Get basic public feeds info (no sensitive data)
@app.get("/api/public/feeds/", response_model=List[schemas.FeedResponse])
def get_public_feeds(db: Session = Depends(get_db)):
    # This endpoint could list feeds marked as 'public' in their config
    # For now, it lists all feeds without user authentication.
    # IMPORTANT: Adjust security rules based on your actual public/private data
    # Currently, `read_feeds` is internal to current_user.
    # You'd need to modify `crud.get_feeds` or add a new `get_public_feeds`
    # in crud that doesn't filter by user.
    # For now, let's just return a placeholder.
    # This endpoint can be removed or secured if not needed.
    return [] # No public feeds by default in current CRUD
