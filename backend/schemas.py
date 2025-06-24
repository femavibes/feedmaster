from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime

# --- Authentication Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# --- User Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    tier: Optional[str] = "silver" # Default tier

class UserResponse(UserBase):
    id: int
    tier: str

    class Config:
        from_attributes = True

# --- Feed Configuration Schemas (for backend to store, from admin frontend) ---
# This schema defines how the admin frontend would send config to the backend.
# The `configuration` JSON in the Feed model will store this.
class AggregateConfig(BaseModel):
    id: str # e.g., 'topHashtags'
    order: int # The display order chosen by the feedmaker
    # Add other display specific options if needed, e.g., 'chartType', 'limit'

class FeedConfiguration(BaseModel):
    # This represents the JSON structure saved in models.Feed.configuration
    display_aggregates: List[AggregateConfig] = []
    # Add other feed-level configurations chosen by the admin
    # e.g., a custom background color, specific filters etc.

# --- Feed Schemas (Frontend facing, and for internal backend use) ---
class FeedBase(BaseModel):
    name: str # Internal feed name (e.g., 'home', 'star')
    title: str # Display title (e.g., "Home Feed")
    description: Optional[str] = None
    
    # Contrails and Bluesky specific details - for the backend to use
    contrails_ws_url: Optional[str] = None # E.g., the specific URL for a custom feed
    bluesky_feed_uri: Optional[str] = None # E.g., at://did:plc:xyz/app.bsky.feed.generator/myfeed

    # The actual configuration for display, set by the admin frontend
    configuration: Optional[FeedConfiguration] = None # Use the nested schema

class FeedCreate(FeedBase):
    pass # No extra fields for creation

class FeedUpdate(FeedBase):
    pass # No extra fields for update

class FeedResponse(FeedBase):
    id: int
    user_id: int
    owner_tier: Optional[str] = None # Include owner's tier for frontend logic

    class Config:
        from_attributes = True

# --- FeedData Schemas (Actual aggregated data) ---
# This is the data that the aggregator worker calculates and the frontend consumes.
class FeedDataBase(BaseModel):
    aggregate_type: str
    data: Dict[str, Any] # Flexible dict to hold varying aggregate structures
    timestamp: datetime

class FeedDataCreate(FeedDataBase):
    pass

class FeedDataResponse(FeedDataBase):
    id: int
    feed_id: int

    class Config:
        from_attributes = True

# --- UserProfileCache Schemas ---
class UserProfileCacheBase(BaseModel):
    did: str
    handle: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None

class UserProfileCacheCreate(UserProfileCacheBase):
    pass

class UserProfileCacheResponse(UserProfileCacheBase):
    id: int
    last_updated: datetime
    last_updated_high_priority: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- PostMetadataCache Schemas ---
class PostMetadataCacheBase(BaseModel):
    post_uri: str
    post_link: Optional[str] = None
    original_poster_did: str
    original_poster_handle: Optional[str] = None
    original_poster_display_name: Optional[str] = None
    original_poster_avatar_url: Optional[HttpUrl] = None
    media_type: str # 'image', 'video', 'short_video', 'text_only', 'external_link'
    media_url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None
    post_text: Optional[str] = None

class PostMetadataCacheCreate(PostMetadataCacheBase):
    pass

class PostMetadataCacheResponse(PostMetadataCacheBase):
    id: int
    last_resolved_at: datetime

    class Config:
        from_attributes = True

