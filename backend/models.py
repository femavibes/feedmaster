# backend/models.py
#
# This file defines the SQLAlchemy ORM models that correspond to your PostgreSQL database tables.
# These models map directly to the `datamaster-prisma-schema` concepts.

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

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
    # URL to the user's avatar image.
    avatar_url = Column(String, nullable=True) # Assuming URL can be longer than 255 chars
    # Timestamp when this profile was last updated from the Bluesky API.
    last_updated = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())

    # Relationship to Post model: A user can have many posts.
    posts = relationship("Post", back_populates="author")

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
    text = Column(Text, nullable=False)
    # Timestamp when the post was originally created on Bluesky.
    created_at = Column(DateTime(timezone=True), nullable=False)
    # Timestamp when this post was ingested *into DataMaster* (first seen).
    ingested_at = Column(DateTime(timezone=True), default=func.now())

    # Foreign key to the User model via their DID.
    author_did = Column(String(255), ForeignKey("users.did"), nullable=False)
    author = relationship("User", back_populates="posts")

    # Boolean flags to indicate presence of certain features/embeds.
    has_image = Column(Boolean, default=False)
    has_video = Column(Boolean, default=false)
    has_link = Column(Boolean, default=False)
    has_quote = Column(Boolean, default=False)
    has_mention = Column(Boolean, default=False)

    # Extracted fields for easier access, derived from 'embeds' and 'rawRecord'
    image_url = Column(String, nullable=True)
    link_title = Column(String, nullable=True)
    link_description = Column(Text, nullable=True)
    link_thumbnail_url = Column(String, nullable=True)

    # JSON fields to store detailed metadata. Using SQLAlchemy's JSON type for PostgreSQL JSONB.
    hashtags = Column(JSON, nullable=True) # Array of strings: ["#tag1", "#tag2"]
    links = Column(JSON, nullable=True) # Array of objects: [{uri: "http://...", title: "...", description: "...", thumb: "..."}]
    mentions = Column(JSON, nullable=True) # Array of objects: [{did: "did:plc:...", handle: "@...", name: "..."}]
    embeds = Column(JSON, nullable=True) # More complex JSON structure for various embed types
    raw_record = Column(JSON, nullable=False) # Store the full raw AT Protocol record

    # Relationship to FeedPost model (the join table for many-to-many feeds)
    feed_inclusions = relationship("FeedPost", back_populates="post")

    def __repr__(self):
        return f"<Post(id='{self.id}', uri='{self.uri}', author_did='{self.author_did}')>"

# --- FeedPost Model (Join Table) ---
# Corresponds to the FeedPost model in datamaster-prisma-schema
class FeedPost(Base):
    __tablename__ = "feed_posts" # Maps to the 'feed_posts' table

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(PG_UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False)
    feed_id = Column(String(255), nullable=False) # The ID of the custom feed (from config)
    ingested_at = Column(DateTime(timezone=True), default=func.now()) # When this post was ingested for THIS feed

    # Relationships
    post = relationship("Post", back_populates="feed_inclusions")

    # Composite unique constraint for postId and feedId
    # This ensures a post is only linked to a specific feed once.
    __table_args__ = (
        # Unique constraint on a combination of columns
        # SQLAlchemy requires index creation for this composite unique constraint.
        # This will be handled by Alembic during migrations.
        # UniqueConstraint('post_id', 'feed_id', name='_post_feed_uc'),
        # Add explicit index for querying feed_id and ingested_at
        # Index('idx_feed_posts_feed_ingested', feed_id, ingested_at),
        # Add explicit index for querying post_id and ingested_at
        # Index('idx_feed_posts_post_ingested', post_id, ingested_at),
    )

    def __repr__(self):
        return f"<FeedPost(id='{self.id}', post_id='{self.post_id}', feed_id='{self.feed_id}')>"

# --- Aggregate Model ---
# Corresponds to the Aggregate model in datamaster-prisma-schema
class Aggregate(Base):
    __tablename__ = "aggregates" # Maps to the 'aggregates' table

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feed_id = Column(String(255), nullable=False) # Which feed this aggregate belongs to
    agg_name = Column(String(255), nullable=False) # Name of the aggregate (e.g., "topHashtags")
    timeframe = Column(String(50), nullable=False) # Time range (e.g., "day", "week", "month", "allTime")
    data_json = Column(JSON, nullable=False) # The actual aggregate data, stored as JSON
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now()) # Last time computed

    # Composite unique constraint for feedId, aggName, and timeframe
    __table_args__ = (
        # UniqueConstraint('feed_id', 'agg_name', 'timeframe', name='_feed_agg_timeframe_uc'),
    )

    def __repr__(self):
        return f"<Aggregate(feed_id='{self.feed_id}', agg_name='{self.agg_name}', timeframe='{self.timeframe}')>"

# IMPORTANT: You will need to run Alembic migrations to create these tables in your database.
# See Alembic setup instructions in a later step.
