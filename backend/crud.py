from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
from typing import Optional, List

from . import models, schemas
from passlib.context import CryptContext # For password hashing

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- Password Utilities ---
def get_password_hash(password: str) -> str:
    """Hashes a plain text password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

# --- User CRUD Operations ---

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password, tier=user.tier)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Feed CRUD Operations ---

def get_feed(db: Session, feed_id: int):
    # Eagerly load the owner to get the tier easily
    return db.query(models.Feed).options(joinedload(models.Feed.owner)).filter(models.Feed.id == feed_id).first()

def get_feed_by_name(db: Session, name: str):
    # Eagerly load the owner to get the tier easily
    return db.query(models.Feed).options(joinedload(models.Feed.owner)).filter(models.Feed.name == name).first()


def get_feeds(db: Session, skip: int = 0, limit: int = 100):
    # Eagerly load the owner for all feeds
    return db.query(models.Feed).options(joinedload(models.Feed.owner)).offset(skip).limit(limit).all()

def get_user_feeds(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    # Eagerly load the owner for user's feeds
    return db.query(models.Feed).options(joinedload(models.Feed.owner)).filter(models.Feed.user_id == user_id).offset(skip).limit(limit).all()

def create_user_feed(db: Session, feed: schemas.FeedCreate, user_id: int):
    db_feed = models.Feed(
        name=feed.name,
        title=feed.title,
        description=feed.description,
        user_id=user_id,
        contrails_ws_url=feed.contrails_ws_url,
        bluesky_feed_uri=feed.bluesky_feed_uri,
        configuration=feed.configuration.model_dump() if feed.configuration else None
    )
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    return db_feed

def update_feed(db: Session, db_feed: models.Feed, feed_update: schemas.FeedUpdate):
    for key, value in feed_update.model_dump(exclude_unset=True).items():
        if key == "configuration" and value is not None:
            # Handle nested Pydantic model for configuration
            db_feed.configuration = value.model_dump()
        else:
            setattr(db_feed, key, value)
    db.add(db_feed)
    db.commit()
    db.refresh(db_feed)
    return db_feed

def delete_feed(db: Session, feed_id: int):
    db_feed = db.query(models.Feed).filter(models.Feed.id == feed_id).first()
    if db_feed:
        db.delete(db_feed)
        db.commit()
        return True
    return False

# --- FeedData CRUD Operations ---

def create_feed_data(db: Session, feed_data: schemas.FeedDataCreate, feed_id: int):
    db_feed_data = models.FeedData(
        feed_id=feed_id,
        aggregate_type=feed_data.aggregate_type,
        data=feed_data.data,
        timestamp=feed_data.timestamp
    )
    db.add(db_feed_data)
    db.commit()
    db.refresh(db_feed_data)
    return db_feed_data

def get_feed_data(db: Session, feed_id: int, aggregate_type: Optional[str] = None, since_timestamp: Optional[datetime] = None, limit: int = 100) -> List[models.FeedData]:
    query = db.query(models.FeedData).filter(models.FeedData.feed_id == feed_id)
    if aggregate_type:
        query = query.filter(models.FeedData.aggregate_type == aggregate_type)
    if since_timestamp:
        query = query.filter(models.FeedData.timestamp >= since_timestamp)
    # Order by timestamp descending to get most recent data
    query = query.order_by(models.FeedData.timestamp.desc())
    return query.limit(limit).all()

# --- UserProfileCache CRUD Operations ---

def get_user_profile_cache(db: Session, did: str):
    return db.query(models.UserProfileCache).filter(models.UserProfileCache.did == did).first()

def create_or_update_user_profile_cache(db: Session, profile: schemas.UserProfileCacheCreate, high_priority: bool = False):
    db_profile = db.query(models.UserProfileCache).filter(models.UserProfileCache.did == profile.did).first()
    current_time = datetime.now(timezone.utc)
    if db_profile:
        # Update existing
        db_profile.handle = profile.handle
        db_profile.display_name = profile.display_name
        db_profile.avatar_url = profile.avatar_url
        db_profile.last_updated = current_time
        if high_priority:
            db_profile.last_updated_high_priority = current_time
    else:
        # Create new
        db_profile = models.UserProfileCache(
            did=profile.did,
            handle=profile.handle,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            last_updated=current_time,
            last_updated_high_priority=current_time if high_priority else None
        )
        db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile

# --- PostMetadataCache CRUD Operations ---

def get_post_metadata_cache(db: Session, post_uri: str):
    return db.query(models.PostMetadataCache).filter(models.PostMetadataCache.post_uri == post_uri).first()

def create_or_update_post_metadata_cache(db: Session, post_data: schemas.PostMetadataCacheCreate):
    db_post = db.query(models.PostMetadataCache).filter(models.PostMetadataCache.post_uri == post_data.post_uri).first()
    current_time = datetime.now(timezone.utc)
    if db_post:
        # Update existing
        db_post.post_link = post_data.post_link
        db_post.original_poster_did = post_data.original_poster_did
        db_post.original_poster_handle = post_data.original_poster_handle
        db_post.original_poster_display_name = post_data.original_poster_display_name
        db_post.original_poster_avatar_url = post_data.original_poster_avatar_url
        db_post.media_type = post_data.media_type
        db_post.media_url = post_data.media_url
        db_post.thumbnail_url = post_data.thumbnail_url
        db_post.post_text = post_data.post_text
        db_post.last_resolved_at = current_time
    else:
        # Create new
        db_post = models.PostMetadataCache(
            post_uri=post_data.post_uri,
            post_link=post_data.post_link,
            original_poster_did=post_data.original_poster_did,
            original_poster_handle=post_data.original_poster_handle,
            original_poster_display_name=post_data.original_poster_display_name,
            original_poster_avatar_url=post_data.original_poster_avatar_url,
            media_type=post_data.media_type,
            media_url=post_data.media_url,
            thumbnail_url=post_data.thumbnail_url,
            post_text=post_data.post_text,
            last_resolved_at=current_time
        )
        db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

