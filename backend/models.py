from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # Tier can be 'silver', 'gold', 'platinum'
    tier = Column(String, default="silver", nullable=False) # Store the user's current tier

    # Relationship to feeds owned by this user
    feeds = relationship("Feed", back_populates="owner")

class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False) # Name for the feed (e.g., 'home', 'star')
    title = Column(String, nullable=False) # Display title (e.g., "Home Feed", "Starred Content")
    description = Column(String, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False) # Owner of the feed
    
    # Configuration JSON from the admin UI (which aggregates to display, their order)
    configuration = Column(JSON, nullable=True) 
    
    # Contrails and Bluesky specific details for the *backend aggregator*
    contrails_ws_url = Column(String, nullable=True)
    bluesky_feed_uri = Column(String, nullable=True) # E.g., at://did:plc:xyz/app.bsky.feed.generator/myfeed

    # Relationship back to the owner (User)
    owner = relationship("User", back_populates="feeds")

    # Relationship to the aggregate data generated for this feed
    # cascade="all, delete-orphan" means if a Feed is deleted, its FeedData also deletes
    feed_data = relationship("FeedData", back_populates="feed", cascade="all, delete-orphan")

class FeedData(Base):
    __tablename__ = "feed_data"

    id = Column(Integer, primary_key=True, index=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"), nullable=False)
    aggregate_type = Column(String, nullable=False, index=True) # e.g., 'topHashtags', 'sentimentAnalysis'
    data = Column(JSON, nullable=False) # The actual aggregated data (e.g., {"count": 123}, {"hashtags": [...]})
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # When this data was last updated

    # Relationship back to the parent Feed
    feed = relationship("Feed", back_populates="feed")

class UserProfileCache(Base):
    __tablename__ = "user_profile_cache"

    id = Column(Integer, primary_key=True, index=True)
    did = Column(String, unique=True, nullable=False, index=True)
    handle = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_updated_high_priority = Column(DateTime(timezone=True), nullable=True) # For frequent updates

class PostMetadataCache(Base):
    __tablename__ = "post_metadata_cache"

    id = Column(Integer, primary_key=True, index=True)
    post_uri = Column(String, unique=True, nullable=False, index=True)
    post_link = Column(String, nullable=True) # URL to the post on bsky.app
    original_poster_did = Column(String, nullable=False, index=True)
    original_poster_handle = Column(String, nullable=True)
    original_poster_display_name = Column(String, nullable=True)
    original_poster_avatar_url = Column(String, nullable=True)
    media_type = Column(String, nullable=False) # 'image', 'video', 'short_video', 'text_only', 'external_link'
    media_url = Column(String, nullable=True) # Direct URL for embeddable media
    thumbnail_url = Column(String, nullable=True)
    post_text = Column(String, nullable=True)
    last_resolved_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

