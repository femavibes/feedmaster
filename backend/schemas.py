# backend/schemas.py
#
# This file defines Pydantic models for data validation and serialization.
# These models are used to ensure the structure and types of data
# for requests coming into your API and responses going out.

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

# --- Base Schemas (common configurations) ---
# Pydantic's ConfigDict can be used for configuration for a model class.
# from_attributes = True is important for SQLAlchemy models to work with Pydantic.
# It tells Pydantic to read data from ORM attributes, not just dict keys.
# alias_generator and populate_by_name can be useful for field name mapping (e.g., camelCase to snake_case)
# but for now, we'll keep it simple with direct attribute access.
class Config:
    from_attributes = True
    populate_by_name = True # Allow population by field name and alias

# --- User Schemas ---
class UserBase(BaseModel):
    did: str = Field(..., max_length=255)
    handle: str = Field(..., max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    avatar_url: Optional[str] = None # No max length on URL

class UserCreate(UserBase):
    # For user creation, we might include a password if this was a local user system.
    # For Bluesky DIDs, this is handled externally.
    pass

class UserPublic(UserBase):
    # Schema for public display of user information
    last_updated: datetime

    model_config = ConfigDict(from_attributes=True) # Apply Pydantic configuration

class UserInDB(UserPublic):
    # Schema for internal use, might include sensitive info or just link to ORM object
    # In this case, it's similar to UserPublic but indicates it's from the DB
    pass


# --- Post Schemas ---
class PostBase(BaseModel):
    uri: str = Field(..., max_length=512)
    cid: str = Field(..., max_length=255)
    text: str
    created_at: datetime
    author_did: str = Field(..., max_length=255) # Author's DID
    has_image: bool = False
    has_video: bool = False
    has_link: bool = False
    has_quote: bool = False
    has_mention: bool = False
    image_url: Optional[str] = None
    link_title: Optional[str] = Field(None, max_length=255)
    link_description: Optional[str] = None
    link_thumbnail_url: Optional[str] = None
    hashtags: Optional[List[str]] = None
    links: Optional[List[Dict[str, Any]]] = None # List of dicts for link embeds
    mentions: Optional[List[Dict[str, Any]]] = None # List of dicts for mentions
    embeds: Optional[Dict[str, Any]] = None # Full raw embeds JSON
    raw_record: Dict[str, Any] # Full raw AT Protocol record JSON

class PostCreate(PostBase):
    # When creating a post, we include all base fields
    pass

class PostInDB(PostBase):
    # Schema for posts retrieved from the database, including auto-generated fields
    id: uuid.UUID
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PostPublic(PostInDB):
    # Schema for public display of post information
    # Potentially nested UserPublic here if we want author details embedded
    author: Optional[UserPublic] = None # Will be loaded by SQLAlchemy relationship

    model_config = ConfigDict(from_attributes=True)


# --- FeedPost Schemas (for the join table) ---
class FeedPostBase(BaseModel):
    post_id: uuid.UUID
    feed_id: str = Field(..., max_length=255)

class FeedPostCreate(FeedPostBase):
    pass

class FeedPostInDB(FeedPostBase):
    id: uuid.UUID
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Aggregate Schemas ---
class AggregateBase(BaseModel):
    feed_id: str = Field(..., max_length=255)
    agg_name: str = Field(..., max_length=255)
    timeframe: str = Field(..., max_length=50)
    data_json: Dict[str, Any] # The actual aggregated data (e.g., {"trending_topics": ["#bluesky", ...]})

class AggregateCreate(AggregateBase):
    pass

class AggregateInDB(AggregateBase):
    id: uuid.UUID
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Authentication Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    did: Optional[str] = None

class UserLogin(BaseModel):
    did: str # For Bluesky, DID is the identifier for login
    # Potentially an app password or token if a separate auth layer is built
    # For now, assuming DID is the main identifier for internal mapping.

# If you were to implement email/password auth
class UserAuth(BaseModel):
    email: EmailStr
    password: str

# --- Tier and Feed Configuration Schemas ---
# These are for reading your config files, not for database models.

class TierConfig(BaseModel):
    id: str
    name: str
    description: str
    min_followers: int
    min_posts_daily: int
    min_reputation_score: float # Placeholder for a reputation metric

class FeedsConfig(BaseModel):
    id: str
    name: str
    description: str
    # You might add criteria for feeds here, e.g., list of included DIDs, keywords, etc.
    criteria: Optional[Dict[str, Any]] = None

class SystemConfig(BaseModel):
    tiers: List[TierConfig]
    feeds: List[FeedsConfig]

# You can also define API response structures, e.g., a list of posts
class PostListResponse(BaseModel):
    posts: List[PostPublic]
    total: int
    page: int
    size: int
