# backend/models.py
#
# This file defines the SQLAlchemy ORM models that correspond to your PostgreSQL database tables.
# These models map directly to the `datamaster-prisma-schema` concepts.
 
import enum
from sqlalchemy import (Column, String, Boolean, DateTime, Text, ForeignKey, Integer, Float, UniqueConstraint, Index, Enum as SQLAlchemyEnum)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB # Ensure JSONB is imported
from sqlalchemy.orm import relationship, Mapped, mapped_column # Added Mapped, mapped_column for newer SQLAlchemy 2.0 style if desired
from sqlalchemy.sql import func
import uuid
from datetime import datetime, timezone

# Import the Base from your database configuration
from .database import Base

# --- User Model ---
# Corresponds to the User model in datamaster-prisma-schema
class User(Base):
    __tablename__ = "users" # Maps to the 'users' table

    # DID (Decentralized Identifier) is the unique primary key for a user on Bluesky.
    did = Column(String(255), primary_key=True, index=True)
    # User's handle (e.g., 'alice.bsky.social'). Should be unique.
    handle = Column(String(255), unique=True, index=True, nullable=False)
    # User's display name (can be different from handle, e.g., 'Alice').
    display_name = Column(String(255), nullable=True)
    # NEW: User's profile description/bio.
    description = Column(Text, nullable=True)
    # URL to the user's avatar image.
    avatar_url = Column(String, nullable=True) # Assuming URL can be longer than 255 chars
    # Timestamp when this profile was last updated from the Bluesky API.
    last_updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # NEW: Additional fields from Bluesky profile
    followers_count = Column(Integer, default=0)
    following_count = Column(Integer, default=0)
    posts_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=True) # When the user's DID was created

    # NEW: Flags for prominent users (set by aggregator, read by ingestion)
    is_prominent = Column(Boolean, default=False)
    last_prominent_refresh_check = Column(DateTime(timezone=True), nullable=True) # When this DID was last evaluated/marked for prominent refresh

    # Relationship to Post model: A user can have many posts.
    # IMPORTANT: Added 'lazy="raise_on_sql"' to prevent automatic loading that causes recursion.
    # You will explicitly load related posts when needed (e.g., using `selectinload`).
    posts = relationship("Post", back_populates="author", lazy="raise_on_sql")

    def __repr__(self):
        return f"<User(did='{self.did}', handle='{self.handle}')>"

# --- Post Model ---
# Corresponds to the Post model in datamaster-prisma-schema
class Post(Base):
    __tablename__ = "posts" # Maps to the 'posts' table

    # Unique identifier for the post within your system (UUID)
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The full AT URI of the post (e.g., 'at://did:plc:xyz/app.bsky.feed.post/abc')
    uri = Column(String(512), unique=True, index=True, nullable=False)
    # The CID (Content ID) of the post record.
    cid = Column(String(255), unique=True, nullable=False)
    # The actual text content of the post.
    text = Column(Text, nullable=True)
    # Timestamp when the post was originally created on Bluesky.
    created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    # Timestamp when this post was ingested *into DataMaster* (first seen).
    ingested_at = Column(DateTime(timezone=True), default=func.now())

    # Foreign key to the User model via their DID.
    author_did = Column(String(255), ForeignKey("users.did"), nullable=False, index=True)
    author = relationship("User", back_populates="posts") # Removed lazy="raise_on_sql" here as we often want to load author with post

    # Engagement counts (to be updated by aggregator worker)
    like_count = Column(Integer, default=0)
    repost_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0) # Sum of replies to this post
    quote_count = Column(Integer, default=0) # Sum of quotes of this post

    # NEW: Calculated engagement score - This was missing!
    engagement_score = Column(Float, default=0.0, index=True)

    # Boolean flags to indicate presence of certain features/embeds.
    has_image = Column(Boolean, default=False)
    has_link = Column(Boolean, default=False)
    has_quote = Column(Boolean, default=False)
    has_mention = Column(Boolean, default=False)

    # NEW: Alt text fields
    has_alt_text = Column(Boolean, default=False, index=True)

    # NEW: Video Embed
    has_video = Column(Boolean, default=False) # Keep this flag for easy filtering

    # Extracted fields for easier access, derived from 'embeds' and 'rawRecord'
    thumbnail_url = Column(String, nullable=True) # NEW: For video/link card thumbnails
    aspect_ratio_width = Column(Integer, nullable=True) # NEW: For video aspect ratio
    aspect_ratio_height = Column(Integer, nullable=True) # NEW: For video aspect ratio
    link_url = Column(String, nullable=True)
    link_title = Column(String, nullable=True)
    link_description = Column(Text, nullable=True)

    # JSON fields to store detailed metadata. Using SQLAlchemy's JSONB type for PostgreSQL JSONB.
    # These fields are crucial for storing list/dict data correctly from the start.
    hashtags = Column(JSONB, nullable=True)
    links = Column(JSONB, nullable=True)
    mentions = Column(JSONB, nullable=True)
    embeds = Column(JSONB, nullable=True)
    images = Column(JSONB, nullable=True) # NEW: To store a list of image objects [{url, alt}, ...]
    raw_record = Column(JSONB, nullable=False)

    # 👇️ NEW: Add the facets column as JSONB
    # This will directly store the 'facets' array from the Bluesky post record.
    # This is the most straightforward way to map it for Pydantic `from_attributes=True`.
    facets = Column(JSONB, nullable=True) 

    # NEW: Quoted Post Details (denormalized for easier access)
    quoted_post_uri = Column(String(512), nullable=True)
    quoted_post_cid = Column(String(255), nullable=True)
    quoted_post_author_did = Column(String(255), nullable=True)
    quoted_post_author_handle = Column(String(255), nullable=True)
    quoted_post_author_display_name = Column(String(255), nullable=True)
    quoted_post_text = Column(Text, nullable=True)
    quoted_post_like_count = Column(Integer, default=0)
    quoted_post_repost_count = Column(Integer, default=0)
    quoted_post_reply_count = Column(Integer, default=0)
    quoted_post_created_at = Column(DateTime(timezone=True), nullable=True)

    # --- Fields for Dynamic Polling System ---
    # NEW: Timestamp for the next scheduled poll. This drives the dynamic polling system.
    # It's nullable because inactive posts won't have a next poll time.
    next_poll_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # Flag to indicate if the post is still active in the battle royale / eligible for polling.
    is_active_for_polling = Column(Boolean, default=True, index=True)
    # NEW: JSON field to store feed associations directly
    feed_data = Column(JSONB, nullable=False, default=lambda: [])
    
    # NEW: Language detection from AT Protocol
    langs = Column(JSONB, nullable=True)

    __table_args__ = (
        # Add GIN indexes to the JSONB columns that are frequently queried.
        Index('ix_posts_hashtags_gin', hashtags, postgresql_using='gin'),
        Index('ix_posts_mentions_gin', mentions, postgresql_using='gin'),
        Index('ix_posts_embeds_gin', embeds, postgresql_using='gin'),
        Index('ix_posts_facets_gin', facets, postgresql_using='gin'),
        Index('ix_posts_links_gin', links, postgresql_using='gin'),
        Index('ix_posts_images_gin', images, postgresql_using='gin'),
        # Index for efficiently querying posts that are due for polling.
        Index('ix_posts_polling_queue', 'is_active_for_polling', 'next_poll_at'),
        # Index for efficiently querying posts by feed using JSON operations
        Index('ix_posts_feed_data_gin', feed_data, postgresql_using='gin'),
    )
    def __repr__(self):
        return f"<Post(id='{self.id}', uri='{self.uri}', author_did='{self.author_did}')>"


# --- Feed Model (Re-included as it's a dependency for FeedPost and Aggregate) ---
class Feed(Base):
    """
    SQLAlchemy model for storing feed configurations.
    """
    __tablename__ = "feeds"

    # IMPORTANT: The 'id' here will directly store your 4-digit Graze Contrails ID
    # This matches your existing feeds.json structure and simplifies mapping.
    id = Column(String(255), primary_key=True, index=True) # e.g., "3654"

    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)
    
    # Re-added this column as it's generated by add_initial_feeds.py and stored in the DB
    contrails_websocket_url = Column(String, nullable=True) # This should match your feeds.json key

    bluesky_at_uri = Column(String, nullable=True) # AT URI of the feed on Bluesky (e.g., for feed generators)
    tier = Column(String(50), nullable=True) # e.g., "free", "silver", "gold"
    order = Column(Integer, nullable=True) # Display order for frontend navigation
    
    # Bluesky feed metadata (fetched from API)
    avatar_url = Column(String, nullable=True) # Feed avatar/icon from Bluesky
    like_count = Column(Integer, default=0) # Feed likes from Bluesky
    bluesky_description = Column(Text, nullable=True) # Description from Bluesky (separate from local description)
    last_bluesky_sync = Column(DateTime(timezone=True), nullable=True) # When feed metadata was last synced
    
    last_aggregated_at = Column(DateTime(timezone=True), nullable=True) # When this feed was last fully aggregated

    # Admin system fields
    owner_did = Column(String(255), nullable=True, index=True)  # DID of feed owner
    tier = Column(String(50), nullable=False, default='bronze')  # bronze, silver, gold
    is_active = Column(Boolean, nullable=False, default=True)
    
    # NEW: Timestamps for auditing - added timezone.utc for consistency
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    aggregates = relationship("Aggregate", back_populates="feed_config", lazy="raise_on_sql") # Link to the Aggregate model
    user_achievements = relationship("UserAchievement", back_populates="feed", lazy="raise_on_sql")
    
    def __repr__(self):
        return f"<Feed(id='{self.id}', name='{self.name}')>"


# FeedPost model removed - feed associations now stored in posts.feed_data JSON column

# --- Aggregate Model (Renamed from FeedAggregateResult, consistent with your file) ---
class Aggregate(Base):
    __tablename__ = "aggregates" # Maps to the 'aggregates' table

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_id = Column(String(255), ForeignKey("feeds.id"), nullable=False)
    agg_name = Column(String(255), nullable=False) # Name of the aggregate (e.g., "topHashtags")
    timeframe = Column(String(50), nullable=False) # Time range (e.g., "day", "week", "month", "allTime")
    data_json = Column(JSONB, nullable=False) # The actual aggregate data, stored as JSONB
    created_at = Column(DateTime(timezone=True), default=func.now()) # <-- Confirmed this is correct
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now()) # Last time computed

    # Relationship back to the Feed config
    feed_config = relationship("Feed", back_populates="aggregates")

    __table_args__ = (
        UniqueConstraint('feed_id', 'agg_name', 'timeframe', name='_feed_agg_timeframe_uc'), # Uncommented
    )

    def __repr__(self):
        return f"<Aggregate(feed_id='{self.feed_id}', agg_name='{self.agg_name}', timeframe='{self.timeframe}')>"

# --- NEW MODELS FOR PROFILES AND ACHIEVEMENTS ---

class AchievementType(enum.Enum):
    GLOBAL = "global"
    PER_FEED = "per_feed"

class Achievement(Base):
    __tablename__ = 'achievements'

    id = Column(Integer, primary_key=True)
    key = Column(String, nullable=False, unique=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    icon = Column(String, nullable=True)
    type = Column(SQLAlchemyEnum(AchievementType), nullable=False, default=AchievementType.PER_FEED)
    is_repeatable = Column(Boolean, nullable=False, default=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default='true', index=True) # For soft-deleting
    custom_for_feed_id = Column(String, nullable=True)
    series_key = Column(String, nullable=True, index=True) # For grouping tiered achievements
    criteria = Column(JSONB, nullable=True)
    rarity_percentage = Column(Float, nullable=False, default=100.0)
    rarity_tier = Column(String, nullable=True) # e.g., "Gold", "Silver"
    rarity_label = Column(String, nullable=True) # e.g., "Gold", "Silver (in this feed)"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserAchievement(Base):
    __tablename__ = 'user_achievements'

    id = Column(Integer, primary_key=True)
    user_did = Column(String, nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey('achievements.id'), nullable=False, index=True)
    feed_id = Column(String, ForeignKey('feeds.id'), nullable=True, index=True)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())
    context = Column(JSONB)
    
    # Add relationships
    achievement = relationship("Achievement")
    feed = relationship("Feed", back_populates="user_achievements")
    __table_args__ = (
        UniqueConstraint('user_did', 'achievement_id', 'feed_id', name='uq_user_achievement_per_feed'),
    )

class AchievementFeedRarity(Base):
    __tablename__ = 'achievement_feed_rarity'
    
    # Composite primary key ensures one rarity entry per achievement per feed
    achievement_id: Mapped[int] = mapped_column(ForeignKey('achievements.id'), primary_key=True)
    feed_id: Mapped[str] = mapped_column(ForeignKey('feeds.id'), primary_key=True)
    
    rarity_percentage: Mapped[float] = mapped_column(Float, nullable=False, server_default='100.0')
    rarity_tier: Mapped[str] = mapped_column(String, nullable=True)
    rarity_label: Mapped[str] = mapped_column(String, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now()
    )

    # Optional relationships if you need to navigate from rarity back to achievement/feed
    # achievement: Mapped["Achievement"] = relationship()
    # feed: Mapped["Feed"] = relationship()

class UserStats(Base):
    __tablename__ = 'user_stats'

    user_did = Column(String, primary_key=True, index=True)
    feed_id = Column(String, primary_key=True, index=True)
    post_count = Column(Integer, nullable=False, default=0)
    total_likes_received = Column(Integer, nullable=False, default=0)
    image_post_count = Column(Integer, nullable=False, default=0, server_default='0')
    video_post_count = Column(Integer, nullable=False, default=0, server_default='0')
    max_post_engagement = Column(Integer, nullable=False, default=0, server_default='0')
    total_reposts_received = Column(Integer, nullable=False, default=0)
    total_replies_received = Column(Integer, nullable=False, default=0)
    total_quotes_received = Column(Integer, nullable=False, default=0)
    first_post_at = Column(DateTime(timezone=True))
    latest_post_at = Column(DateTime(timezone=True))
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# --- ADMIN SYSTEM MODELS ---

class ApiKeyType(enum.Enum):
    MASTER_ADMIN = "master_admin"
    FEED_OWNER = "feed_owner"

class ApiKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_type = Column(SQLAlchemyEnum(ApiKeyType), nullable=False)
    owner_did = Column(String(255), nullable=True, index=True)  # NULL for master admin keys
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<ApiKey(id={self.id}, type={self.key_type.value}, owner={self.owner_did})>"

class ApplicationStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class FeedApplication(Base):
    __tablename__ = 'feed_applications'
    
    id = Column(Integer, primary_key=True)
    applicant_did = Column(String(255), nullable=False, index=True)
    applicant_handle = Column(String(255), nullable=True)  # Bluesky handle for human readability
    feed_id = Column(String(255), nullable=False)
    websocket_url = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(SQLAlchemyEnum(ApplicationStatus), nullable=False, default=ApplicationStatus.PENDING)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String(255), nullable=True)  # DID of admin who reviewed
    notes = Column(Text, nullable=True)  # Admin notes
    
    def __repr__(self):
        return f"<FeedApplication(id={self.id}, feed_id={self.feed_id}, status={self.status.value})>"
# --- CONFIGURATION MODELS ---

class GeoHashtagMapping(Base):
    __tablename__ = 'geo_hashtag_mappings'
    
    hashtag = Column(String(255), primary_key=True, index=True)
    city = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    country = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<GeoHashtagMapping(hashtag='{self.hashtag}', country='{self.country}')>"

class NewsDomain(Base):
    __tablename__ = 'news_domains'
    
    domain = Column(String(255), primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<NewsDomain(domain='{self.domain}')>"

class FeedPermission(Base):
    __tablename__ = 'feed_permissions'
    
    id = Column(Integer, primary_key=True)
    api_key_id = Column(Integer, ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False, index=True)
    feed_id = Column(String(50), ForeignKey('feeds.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_level = Column(String(20), nullable=False, default='viewer')
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    api_key = relationship("ApiKey")
    feed = relationship("Feed")
    
    __table_args__ = (
        UniqueConstraint('api_key_id', 'feed_id', name='unique_api_key_feed'),
    )
    
    def __repr__(self):
        return f"<FeedPermission(api_key_id={self.api_key_id}, feed_id='{self.feed_id}', level='{self.permission_level}')>"