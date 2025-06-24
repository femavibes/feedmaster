# backend/schemas.py
#
# This file defines the Pydantic models (schemas) for validating and
# serializing data. These schemas are used for API request/response bodies
# and for data validation when interacting with the database.

from pydantic import BaseModel, EmailStr, Field, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# --- User Schemas (for content authors) ---
class UserBase(BaseModel):
    did: str = Field(..., example="did:plc:abcdef1234567890abcdef12", description="Decentralized Identifier (DID) of the user")
    handle: Optional[str] = Field(None, example="johndoe.bsky.social", description="Bluesky handle of the user")
    display_name: Optional[str] = Field(None, example="John Doe", description="Display name of the user")
    avatar_url: Optional[HttpUrl] = Field(None, example="https://example.com/avatars/johndoe.jpg", description="URL to the user's avatar image")
    bio: Optional[str] = Field(None, example="I am a human.", description="User's biography")
    followers_count: Optional[int] = Field(0, example=123, description="Number of followers the user has")
    following_count: Optional[int] = Field(0, example=45, description="Number of users this user is following")
    posts_count: Optional[int] = Field(0, example=500, description="Total number of posts made by the user")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the user's profile was created on Bluesky")
    last_updated: Optional[datetime] = Field(None, description="Timestamp when the user's profile was last updated in our system")

class UserCreate(UserBase):
    # For creation, DID is mandatory, others are optional.
    # We might not have all details initially, the worker will enrich.
    pass

class UserPublic(UserBase):
    # This schema is for responses, includes DB-generated fields like id
    id: int
    # Add config for ORM mode
    model_config = {
        "from_attributes": True
    }

# --- Post Schemas ---
class PostBase(BaseModel):
    uri: str = Field(..., example="at://did:plc:xyz/app.bsky.feed.post/abc123def456", description="The AT URI of the post")
    cid: str = Field(..., example="bafyreihm4e7r5f...", description="The CID (Content ID) of the post record")
    text: str = Field(..., example="This is a post on Bluesky.", description="The main text content of the post")
    created_at: datetime = Field(..., description="Timestamp when the post was created on Bluesky")
    author_did: str = Field(..., example="did:plc:abcdef1234567890abcdef12", description="DID of the post author")

    has_image: Optional[bool] = False
    has_video: Optional[bool] = False
    has_link: Optional[bool] = False
    has_quote: Optional[bool] = False
    has_mention: Optional[bool] = False

    image_url: Optional[HttpUrl] = Field(None, example="https://example.com/post_image.jpg")
    link_title: Optional[str] = None
    link_description: Optional[str] = None
    link_thumbnail_url: Optional[HttpUrl] = None

    hashtags: Optional[List[str]] = None # e.g., ["#bluesky", "#python"]
    links: Optional[List[Dict[str, Any]]] = None # e.g., [{"uri": "...", "title": "..."}]
    mentions: Optional[List[Dict[str, Any]]] = None # e.g., [{"did": "...", "handle": "...", "name": "..."}]
    embeds: Optional[Dict[str, Any]] = None # Raw embed JSON structure
    raw_record: Optional[Dict[str, Any]] = Field(None, description="The full raw AT Protocol record of the post")

class PostCreate(PostBase):
    pass

class PostInDB(PostBase):
    id: int
    last_processed_at: Optional[datetime] = None # When our worker last processed/updated it
    # Config for ORM mode
    model_config = {
        "from_attributes": True
    }

class PostPublic(PostInDB):
    author: Optional[UserPublic] = Field(None, description="Details of the post author")
    # This is for output, should include author details.
    # Pydantic's from_attributes=True usually handles loading relationship if configured correctly in models.

# --- FeedPost Schemas (Link table between Post and Feed) ---
class FeedPostBase(BaseModel):
    post_id: int
    feed_id: str = Field(..., example="tech-news")
    # You could add a 'rank' or 'score' here specific to this feed if needed
    # score: Optional[float] = 0.0

class FeedPostCreate(FeedPostBase):
    pass

class FeedPostInDB(FeedPostBase):
    id: int
    added_at: datetime # When this post was added to this feed in our DB
    # Config for ORM mode
    model_config = {
        "from_attributes": True
    }


# --- Feeds Configuration Schemas ---
class FeedsConfig(BaseModel):
    id: str = Field(..., example="tech-news", description="Unique identifier for the feed (corresponds to Contrails feed ID)")
    name: str = Field(..., example="Tech News Feed", description="Human-readable name for the feed")
    description: Optional[str] = Field(None, example="Curated feed for technology news.")
    contrails_websocket_url: HttpUrl = Field(..., example="wss://contrails.graze.social/feeds/tech-news-feed", description="The direct WebSocket URL for this feed on Graze Contrails.")
    tier: str = Field(..., example="silver", description="The tier of this feed (e.g., silver, gold, platinum), impacting access to aggregates or processing priority.")

class FeedsConfigInDB(FeedsConfig):
    # If you were to store this config in the DB, it would have an ID
    model_config = {
        "from_attributes": True
    }

# --- Aggregate Schemas ---
class AggregateBase(BaseModel):
    feed_id: str = Field(..., example="tech-news", description="The ID of the feed this aggregate belongs to")
    agg_name: str = Field(..., example="topHashtags", description="Name of the aggregate (e.g., topHashtags, mostActiveUsers)")
    timeframe: str = Field(..., example="24h", description="Timeframe of the aggregate (e.g., 24h, 7d, 30d)")
    data_json: Dict[str, Any] = Field(..., description="The actual aggregated data in JSON format")

class AggregateCreate(AggregateBase):
    pass

class AggregateInDB(AggregateBase):
    id: int
    last_updated: datetime = Field(..., description="Timestamp when this aggregate was last updated")
    model_config = {
        "from_attributes": True
    }

# --- Authentication Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    did: Optional[str] = None # The subject of the token, which is the user's DID

class UserLogin(BaseModel):
    did: str = Field(..., example="did:plc:abcdef1234567890abcdef12", description="Bluesky DID for authentication (for feedmakers)")
    # Potentially add password/app_password if you implemented that security layer
    # password: str

# --- API Response Schemas ---
class PostListResponse(BaseModel):
    posts: List[PostPublic]
    total: int
    page: int
    size: int
