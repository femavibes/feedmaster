# backend/schemas.py

import datetime
import uuid
from typing import List, Optional, Dict, Any, Union, Literal, Annotated
from pydantic import BaseModel, Field, HttpUrl, AnyUrl, model_validator

# Import models to resolve type hints like models.AchievementType
from . import models

# --- NEW: Bluesky Facet Schemas ---
class FacetFeatureLink(BaseModel):
    """Schema for app.bsky.richtext.facet#link"""
    type: str = Field("app.bsky.richtext.facet#link", alias="$type")
    uri: str

class FacetFeatureMention(BaseModel):
    """Schema for app.bsky.richtext.facet#mention"""
    type: str = Field("app.bsky.richtext.facet#mention", alias="$type")
    did: str

class FacetFeatureTag(BaseModel):
    """Schema for app.bsky.richtext.facet#tag"""
    type: str = Field("app.bsky.richtext.facet#tag", alias="$type")
    tag: str

# Union of all possible facet features
FacetFeatureUnion = Union[FacetFeatureLink, FacetFeatureMention, FacetFeatureTag, Dict[str, Any]]

class FacetByteSlice(BaseModel):
    """Schema for the byte start and end of a facet."""
    byteStart: int
    byteEnd: int

class Facet(BaseModel):
    """Schema for a single Bluesky rich text facet."""
    index: FacetByteSlice
    features: List[FacetFeatureUnion]

# --- Existing Embed Schemas (unchanged for now, but keeping for context) ---
class LinkDetails(BaseModel):
    uri: str

class ImageDetail(BaseModel):
    """Schema for a single image, including its URL and alt text."""
    url: str
    alt: Optional[str] = None

class EmbedExternal(BaseModel):
    type: str = Field("$type", alias="$type")
    uri: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None

class EmbedImage(BaseModel):
    type: str = Field("$type", alias="$type")
    images: List[Dict[str, Any]]

class EmbedRecord(BaseModel):
    type: str = Field("$type", alias="$type")
    record: Dict[str, Any]

EmbedUnion = Union[EmbedExternal, EmbedImage, EmbedRecord, Dict[str, Any]]

# --- User Schemas (unchanged) ---
class UserBase(BaseModel):
    did: str = Field(..., description="Bluesky Decentralized Identifier (DID)")
    handle: str = Field(..., description="Bluesky handle (e.g., example.bsky.social)")
    display_name: Optional[str] = Field(None, description="User's display name")
    description: Optional[str] = Field(None, description="User's profile description or bio")
    # Changed from HttpUrl to str to prevent validation errors on malformed URLs from the API.
    # The frontend can handle invalid image URLs gracefully.
    avatar_url: Optional[str] = Field(None, description="URL to user's avatar image")
    last_updated: Optional[datetime.datetime] = Field(None, description="Timestamp when user was last updated")
    created_at: Optional[datetime.datetime] = Field(None, description="Timestamp when user profile was created on Bluesky")
    followers_count: Optional[int] = Field(0, description="Number of followers")
    following_count: Optional[int] = Field(0, description="Number of users this user is following")
    posts_count: Optional[int] = Field(0, description="Number of posts made by this user")
    is_active_for_polling: bool = Field(True, description="Whether the user's data is actively polled for updates")
    last_post_poll_timestamp: Optional[datetime.datetime] = Field(None, description="Timestamp of the last post poll for this user")
    last_profile_poll_timestamp: Optional[datetime.datetime] = Field(None, description="Timestamp of the last profile poll for this user")
    is_prominent: Optional[bool] = Field(False, description="Flag indicating if user is prominent")
    last_prominent_refresh_check: Optional[datetime.datetime] = Field(None, description="Timestamp of last prominent refresh check")

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    handle: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    last_updated: Optional[datetime.datetime] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None
    is_prominent: Optional[bool] = None
    last_prominent_refresh_check: Optional[datetime.datetime] = None
    is_active_for_polling: Optional[bool] = None
    last_post_poll_timestamp: Optional[datetime.datetime] = None
    last_profile_poll_timestamp: Optional[datetime.datetime] = None

class UserPublic(UserBase):
    model_config = {'from_attributes': True}

class Post(BaseModel): # Declared early to avoid circular import errors
    model_config = {'from_attributes': True, 'arbitrary_types_allowed': True}

class User(UserBase):
    model_config = {'from_attributes': True}

class Mention(BaseModel):
    did: str = Field(..., description="DID of the mentioned user")
    handle: Optional[str] = Field(None, description="Handle of the mentioned user")
    display_name: Optional[str] = Field(None, description="Display name of the mentioned user")

# --- Post Schemas (Crucial Changes Here) ---
class PostBase(BaseModel):
    uri: str = Field(..., description="Bluesky URI of the post")
    cid: str = Field(..., description="CID of the post content")
    text: Optional[str] = Field(None, description="Full text content of the post")
    author_did: str = Field(..., description="DID of the post's author")
    created_at: datetime.datetime = Field(..., description="Timestamp when the post was created")
    ingested_at: Optional[datetime.datetime] = Field(None, description="Timestamp when post was ingested")
    
    has_image: Optional[bool] = False
    has_video: Optional[bool] = False
    has_alt_text: Optional[bool] = False
    has_link: Optional[bool] = False
    has_quote: Optional[bool] = False
    has_mention: Optional[bool] = False
    
    thumbnail_url: Optional[str] = None
    aspect_ratio_width: Optional[int] = None
    aspect_ratio_height: Optional[int] = None
    link_url: Optional[str] = None
    link_title: Optional[str] = None
    link_description: Optional[str] = None
    
    # These derived lists are still useful for search/filtering, but `facets` is for rendering
    hashtags: Optional[List[str]] = None
    links: Optional[List[LinkDetails]] = None
    mentions: Optional[List[Mention]] = None
    images: Optional[List[ImageDetail]] = None # NEW: To hold a list of image objects
    
    embeds: Optional[EmbedUnion] = None
    raw_record: Dict[str, Any] = Field(..., description="Raw post record JSON")

    # 👇️ NEW: Add the facets field
    facets: Optional[List[Facet]] = Field(None, description="List of rich text facets for the post content")

    quoted_post_uri: Optional[str] = None
    quoted_post_cid: Optional[str] = None
    quoted_post_author_did: Optional[str] = None
    quoted_post_author_handle: Optional[str] = None
    quoted_post_author_display_name: Optional[str] = None
    quoted_post_text: Optional[str] = None
    quoted_post_like_count: Optional[int] = 0
    quoted_post_repost_count: Optional[int] = 0
    quoted_post_reply_count: Optional[int] = 0
    quoted_post_created_at: Optional[datetime.datetime] = None

    like_count: int = Field(0, description="Number of likes on the post")
    repost_count: int = Field(0, description="Number of reposts of the post")
    reply_count: int = Field(0, description="Number of replies to the post")
    quote_count: int = Field(0, description="Number of quotes of the post")
    engagement_score: float = Field(0.0, description="Calculated engagement score for the post")
    is_active_for_polling: bool = Field(True, description="Whether the post's engagement is actively polled")
    next_poll_at: Optional[datetime.datetime] = Field(None, description="Timestamp for the next scheduled poll")

class PostCreate(PostBase):
    feed_data: Optional[List[Dict[str, Any]]] = Field(None, description="JSON array of feed associations")

class PostUpdate(BaseModel):
    # ... all other fields ...
    # 👇️ NEW: Add facets here too for updates if needed
    facets: Optional[List[Facet]] = None
    images: Optional[List[ImageDetail]] = None

# Post schema with relationship to User
class Post(PostBase):
    id: uuid.UUID # Post ID from the database
    author: Optional[UserPublic] = None
    model_config = {'from_attributes': True}

class PostListResponse(BaseModel):
    posts: List[Post]
    total: int
    page: int
    size: int

class PostPublic(PostBase):
    id: uuid.UUID
    author: Optional[UserPublic] = None
    model_config = {'from_attributes': True}

# --- Remaining Schemas (unchanged) ---
class FeedBase(BaseModel):
    id: str = Field(..., description="Unique identifier for the feed (e.g., Contrails Feed ID)")
    name: str = Field(..., description="Display name of the feed")
    description: Optional[str] = Field(None, description="Description of the feed")
    contrails_websocket_url: Optional[AnyUrl] = Field(None, description="The Contrails WebSocket URL for this feed")
    bluesky_at_uri: Optional[str] = Field(None, description="The Bluesky AT URI for the feed generator")
    tier: str = Field(..., description="Tier of the feed (e.g., 'gold', 'silver', 'bronze')")
    order: Optional[int] = Field(None, description="Display order for frontend navigation")
    avatar_url: Optional[str] = Field(None, description="Feed avatar/icon from Bluesky")
    like_count: Optional[int] = Field(0, description="Feed likes from Bluesky")
    bluesky_description: Optional[str] = Field(None, description="Description from Bluesky")
    last_bluesky_sync: Optional[datetime.datetime] = Field(None, description="When feed metadata was last synced")
    last_aggregated_at: Optional[datetime.datetime] = Field(None, description="Timestamp of the last aggregation run for this feed")

class FeedCreate(FeedBase):
    pass

class FeedUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    contrails_websocket_url: Optional[AnyUrl] = None
    bluesky_at_uri: Optional[str] = None
    tier: Optional[str] = None
    order: Optional[int] = None
    avatar_url: Optional[str] = None
    like_count: Optional[int] = None
    bluesky_description: Optional[str] = None
    last_bluesky_sync: Optional[datetime.datetime] = None
    last_aggregated_at: Optional[datetime.datetime] = None

class Feed(FeedBase):
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {'from_attributes': True}

class FeedsConfig(FeedBase):
    model_config = {'from_attributes': True}

class FeedPostBase(BaseModel):
    post_id: uuid.UUID = Field(..., description="UUID of the post")
    feed_id: str = Field(..., description="ID of the feed")
    relevance_score: Optional[float] = Field(0.0, description="Score indicating post relevance to the feed")
    ingested_at: Optional[datetime.datetime] = Field(None, description="Timestamp when the post was added to this feed")

class FeedPostCreate(FeedPostBase):
    pass

class FeedPost(FeedPostBase):
    id: uuid.UUID = Field(..., description="Unique ID for the feed-post relationship")
    model_config = {'from_attributes': True}

class TopLinkCard(BaseModel):
    type: Literal["link_card"] = "link_card"
    uri: str  # The Bluesky post URI containing the link card
    title: str
    description: str
    image: Optional[str] = None
    url: str  # The external URL of the link card
    count: Optional[int] = Field(None, description="The number of times this link has appeared, for aggregated views.")

# This is the existing model for top posts, no changes needed here.
class TopPostCard(BaseModel):
    type: Literal["post_card"] = "post_card"
    uri: str
    text: str
    author: str
    avatar: str
    created_at: Union[datetime.datetime, str]
    like_count: int
    repost_count: int
    reply_count: int
    quote_count: int
    post_url: str # The URL of the post
    images: Optional[List[ImageDetail]] = None
    thumbnail_url: Optional[str] = None
    has_image: Optional[bool] = None
    has_video: Optional[bool] = None

# --- NEW: Schemas for different aggregation result types ---
# These models define the structure for each type of data your aggregator can produce.

class TopUser(BaseModel):
    """Schema for top users, posters, or mentions."""
    type: Literal["user"] = "user"
    did: str
    handle: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    count: int
    first_post_at: Optional[str] = None

class TopHashtag(BaseModel):
    """Schema for top hashtags."""
    type: Literal["hashtag"] = "hashtag"
    hashtag: str
    count: int

class TopDomain(BaseModel):
    """Schema for top domains from links."""
    type: Literal["domain"] = "domain"
    domain: str
    count: int

class TopLink(BaseModel):
    """Schema for top links (by URI)."""
    type: Literal["link"] = "link"
    uri: str
    count: int

class TopGeoItem(BaseModel):
    """A generic schema for geo-based aggregations (cities, regions, countries)."""
    type: Literal["geo"] = "geo"
    region: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    count: int

# --- NEW: A Union type to allow any of the above in the 'top' field ---
TopItemUnion = Union[TopPostCard, TopLinkCard, TopUser, TopHashtag, TopDomain, TopGeoItem, TopLink]

class AggregateData(BaseModel):
    # These fields are now more specific, improving validation.
    hashtags: Optional[List[TopHashtag]] = None
    posters: Optional[List[TopUser]] = None
    users: Optional[List[TopUser]] = None
    mentions: Optional[List[TopUser]] = None
    # The `links` field here refers to simple link aggregation (just URI and count)
    links: Optional[List[TopLink]] = None 
    streaks: Optional[List[Dict[str, Any]]] = None
    domains: Optional[List[TopDomain]] = None
    # 👇️ THIS IS THE MAIN FIX: The 'top' field is now a discriminated union.
    # Pydantic will use the 'type' field to determine which model to use for validation.
    top: Optional[List[Annotated[TopItemUnion, Field(discriminator="type")]]] = None
    news_cards: Optional[List[TopLinkCard]] = None
    cards: Optional[List[TopLinkCard]] = None

class AggregateBase(BaseModel):
    feed_id: str = Field(..., description="ID of the feed this aggregate belongs to")
    agg_name: str = Field(..., description="Name of the aggregate (e.g., 'top_posts', 'top_hashtags')")
    timeframe: str = Field(..., description="Timeframe of the aggregate (e.g., '24h', '7d', 'allTime')")
    data_json: AggregateData = Field(..., description="JSON data representing the aggregate results")

class AggregateCreate(AggregateBase):
    pass

class Aggregate(AggregateBase):
    id: uuid.UUID = Field(..., description="Unique ID for the aggregate record")
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {'from_attributes': True}

class AggregateInDB(AggregateBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = {'from_attributes': True}

# --- NEW SCHEMAS FOR PROFILE API ---

class ProfileDetails(BaseModel):
    did: str
    handle: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    avatar_url: Optional[str] = None
    followers_count: Optional[int] = None
    following_count: Optional[int] = None
    posts_count: Optional[int] = None

    model_config = {'from_attributes': True}


class UserFeedStats(BaseModel):
    user_did: str
    feed_id: str
    post_count: int
    total_likes_received: int
    total_reposts_received: int
    total_replies_received: int
    total_quotes_received: int
    first_post_at: Optional[datetime.datetime] = None
    latest_post_at: Optional[datetime.datetime] = None

    model_config = {'from_attributes': True}


class Achievement(BaseModel):
    name: str
    description: str
    icon: Optional[str] = None
    rarity_percentage: float

    model_config = {'from_attributes': True}


class UserAchievement(BaseModel):
    achievement: Achievement
    earned_at: datetime.datetime
    feed_id: Optional[str] = None

    model_config = {'from_attributes': True}


class PostForProfile(BaseModel):
    uri: str
    text: Optional[str] = None
    created_at: datetime.datetime
    like_count: int
    repost_count: int
    reply_count: int
    quote_count: int

    model_config = {'from_attributes': True}

class RecentPostsResponse(BaseModel):
    posts: List[PostForProfile]

class HashtagPostListResponse(BaseModel):
    posts: List[Post]
    total: int

class AchievementResponse(BaseModel):
    name: str
    description: str
    icon: Optional[str] = None
    rarity_percentage: float
    rarity_label: str
    rarity_tier: Optional[str] = None
    type: models.AchievementType

    model_config = {'from_attributes': True}

class FeedForAchievement(BaseModel):
    id: str
    name: str
    model_config = {'from_attributes': True}


class UserAchievementResponse(BaseModel):
    achievement: AchievementResponse
    earned_at: datetime.datetime
    feed_id: Optional[str] = None
    feed: Optional[FeedForAchievement] = None

# NEW: Schema for achievements a user is currently working towards.
class InProgressAchievementResponse(BaseModel):
    achievement: AchievementResponse
    current_value: Union[int, float]
    required_value: Union[int, float]
    progress_percentage: float
    feed: Optional[FeedForAchievement] = None

    model_config = {'from_attributes': True}


# --- NEW: Schemas for Admin Achievement Management ---

# A schema for the editable parts of the criteria object
class AchievementCriteriaUpdate(BaseModel):
    value: Optional[Union[int, float]] = None

# A schema for updating an achievement from the admin page
class AchievementUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    criteria: Optional[AchievementCriteriaUpdate] = None
    is_active: Optional[bool] = None

# NEW: A schema for creating a new achievement (e.g., a new tier in a series)
class AchievementCreate(BaseModel):
    key: str = Field(..., description="Unique key for the achievement (e.g., 'global_likes_viii')")
    name: str = Field(..., description="Display name of the achievement (e.g., 'Global Icon VIII')")
    description: str = Field(..., description="Description of the achievement.")
    icon: Optional[str] = Field(None, description="Icon for the achievement.")
    type: models.AchievementType = Field(..., description="The type of achievement, which determines the logic for awarding it.")
    series_key: str = Field(..., description="The key for the series this achievement belongs to (e.g., 'global_likes').")
    criteria: Dict[str, Any] = Field(..., description="The criteria for earning the achievement (e.g., {'value': 10000000}).")
    is_repeatable: bool = Field(False, description="Whether this achievement can be earned multiple times.")
    is_active: bool = Field(True, description="Whether this achievement is currently active and can be earned.")

# A full schema for viewing all achievement details in the admin UI
class AchievementAdminDetail(BaseModel):
    id: int
    key: str
    name: str
    description: str
    icon: Optional[str] = None
    type: models.AchievementType
    is_repeatable: bool
    is_active: bool
    series_key: Optional[str] = None # For grouping tiered achievements
    criteria: Optional[dict] = None # Show the raw JSON criteria
    rarity_percentage: float

    class Config:
        from_attributes = True

class HashtagResult(BaseModel):
    hashtag: str
    count: int

class SearchResults(BaseModel):
    users: List[UserPublic] = []
    hashtags: List[HashtagResult] = []

class LeaderboardEntry(BaseModel):
    """Represents a single user's entry on a leaderboard."""
    rank: int
    user: UserPublic
    score: int # The user's score, e.g., total achievements earned.

    model_config = {'from_attributes': True}

class FeedForLeaderboard(BaseModel):
    """A slimmed-down Feed schema for listing available leaderboards."""
    id: str
    name: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    did: Optional[str] = None

class UserLogin(BaseModel):
    did: str = Field(..., description="Bluesky Decentralized Identifier (DID) for login")

# --- NEW SCHEMAS FOR POLLING CONFIG MANAGER ---

class PollingDeactivationRules(BaseModel):
    hard_stop_hours: float
    first_poll_age_hours: float
    second_poll_age_hours: float
    third_poll_age_hours: float
    fourth_poll_age_hours: float
    fourth_poll_elimination_score: int
    fifth_poll_age_hours: float
    fifth_poll_elimination_score_threshold: int

class PollingTier(BaseModel):
    description: str
    max_age_hours: float
    interval_hours: float

class PollingConfig(BaseModel):
    deactivation_rules: PollingDeactivationRules
    polling_tiers: List[PollingTier]

# Pydantic v2 requires model_rebuild() for forward references
User.model_rebuild()
Post.model_rebuild()
Feed.model_rebuild()
FeedPost.model_rebuild()
PostListResponse.model_rebuild()
PostPublic.model_rebuild()
FeedsConfig.model_rebuild()

# Rebuild new models as well
ProfileDetails.model_rebuild()
UserFeedStats.model_rebuild()
Achievement.model_rebuild()
UserAchievement.model_rebuild()
AchievementResponse.model_rebuild()
UserAchievementResponse.model_rebuild()
InProgressAchievementResponse.model_rebuild() # Rebuild the new in-progress schema
AchievementCreate.model_rebuild() # Rebuild the new create schema
AchievementAdminDetail.model_rebuild() # Rebuild the new admin schema
FeedForAchievement.model_rebuild()
LeaderboardEntry.model_rebuild()
FeedForLeaderboard.model_rebuild()
SearchResults.model_rebuild()
PollingConfig.model_rebuild()
