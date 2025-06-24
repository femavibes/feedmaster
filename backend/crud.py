# backend/crud.py
#
# This file contains the Create, Read, Update, and Delete (CRUD) operations
# for interacting with your database models using SQLAlchemy.
# These functions abstract the database logic away from your API endpoints.

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import uuid

# Import your SQLAlchemy models
from . import models, schemas

# --- User CRUD Operations ---

def get_user(db: Session, user_did: str) -> Optional[models.User]:
    """Retrieve a user by their DID."""
    return db.query(models.User).filter(models.User.did == user_did).first()

def get_user_by_handle(db: Session, handle: str) -> Optional[models.User]:
    """Retrieve a user by their handle."""
    return db.query(models.User).filter(models.User.handle == handle).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    """Create a new user in the database."""
    db_user = models.User(
        did=user.did,
        handle=user.handle,
        display_name=user.display_name,
        avatar_url=user.avatar_url
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_did: str, user_update: schemas.UserCreate) -> Optional[models.User]:
    """Update an existing user's details."""
    db_user = db.query(models.User).filter(models.User.did == user_did).first()
    if db_user:
        for key, value in user_update.model_dump(exclude_unset=True).items():
            setattr(db_user, key, value)
        db_user.last_updated = func.now() # Update timestamp on change
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_did: str) -> Optional[models.User]:
    """Delete a user from the database."""
    db_user = db.query(models.User).filter(models.User.did == user_did).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user


# --- Post CRUD Operations ---

def get_post(db: Session, post_id: uuid.UUID) -> Optional[models.Post]:
    """Retrieve a post by its UUID."""
    return db.query(models.Post).filter(models.Post.id == post_id).first()

def get_post_by_uri(db: Session, post_uri: str) -> Optional[models.Post]:
    """Retrieve a post by its AT URI."""
    return db.query(models.Post).filter(models.Post.uri == post_uri).first()

def create_post(db: Session, post: schemas.PostCreate) -> models.Post:
    """Create a new post in the database."""
    db_post = models.Post(
        uri=post.uri,
        cid=post.cid,
        text=post.text,
        created_at=post.created_at,
        author_did=post.author_did,
        has_image=post.has_image,
        has_video=post.has_video,
        has_link=post.has_link,
        has_quote=post.has_quote,
        has_mention=post.has_mention,
        image_url=post.image_url,
        link_title=post.link_title,
        link_description=post.link_description,
        link_thumbnail_url=post.link_thumbnail_url,
        hashtags=post.hashtags,
        links=post.links,
        mentions=post.mentions,
        embeds=post.embeds,
        raw_record=post.raw_record
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

def get_posts(db: Session, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """Retrieve a list of posts with pagination."""
    return db.query(models.Post).offset(skip).limit(limit).all()

def get_posts_by_author(db: Session, author_did: str, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """Retrieve posts by a specific author DID with pagination."""
    return db.query(models.Post).filter(models.Post.author_did == author_did).offset(skip).limit(limit).all()


# --- FeedPost CRUD Operations ---

def get_feed_post(db: Session, feed_post_id: uuid.UUID) -> Optional[models.FeedPost]:
    """Retrieve a feed post entry by its UUID."""
    return db.query(models.FeedPost).filter(models.FeedPost.id == feed_post_id).first()

def create_feed_post(db: Session, feed_post: schemas.FeedPostCreate) -> models.FeedPost:
    """Create a new entry linking a post to a feed."""
    db_feed_post = models.FeedPost(
        post_id=feed_post.post_id,
        feed_id=feed_post.feed_id
    )
    db.add(db_feed_post)
    # Handle potential UniqueConstraint violation if a post is already in a feed
    try:
        db.commit()
        db.refresh(db_feed_post)
        return db_feed_post
    except Exception as e:
        db.rollback()
        # You might want to log the error or raise a more specific exception
        print(f"Error creating feed post: {e}")
        return None # Or raise HTTPException for FastAPI


def get_feed_posts_for_feed(db: Session, feed_id: str, skip: int = 0, limit: int = 100) -> List[models.FeedPost]:
    """Retrieve all feed posts for a given feed ID."""
    # This will load FeedPost objects, which contain post_id.
    # To get the actual posts, you'd need to join or load them separately.
    return db.query(models.FeedPost)\
        .filter(models.FeedPost.feed_id == feed_id)\
        .order_by(models.FeedPost.ingested_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()

def get_posts_for_feed(db: Session, feed_id: str, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """
    Retrieve actual Post objects for a given feed ID, ordered by ingestion time.
    Uses a join to efficiently get posts associated with a feed.
    """
    return db.query(models.Post)\
        .join(models.FeedPost, models.Post.id == models.FeedPost.post_id)\
        .filter(models.FeedPost.feed_id == feed_id)\
        .order_by(models.FeedPost.ingested_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()


# --- Aggregate CRUD Operations ---

def get_aggregate(db: Session, feed_id: str, agg_name: str, timeframe: str) -> Optional[models.Aggregate]:
    """Retrieve a specific aggregate by its identifying attributes."""
    return db.query(models.Aggregate).filter(
        models.Aggregate.feed_id == feed_id,
        models.Aggregate.agg_name == agg_name,
        models.Aggregate.timeframe == timeframe
    ).first()

def create_or_update_aggregate(
    db: Session,
    aggregate_data: schemas.AggregateCreate
) -> models.Aggregate:
    """
    Creates a new aggregate or updates an existing one based on feed_id, agg_name, and timeframe.
    """
    db_aggregate = db.query(models.Aggregate).filter(
        models.Aggregate.feed_id == aggregate_data.feed_id,
        models.Aggregate.agg_name == aggregate_data.agg_name,
        models.Aggregate.timeframe == aggregate_data.timeframe
    ).first()

    if db_aggregate:
        # Update existing aggregate
        db_aggregate.data_json = aggregate_data.data_json
        db_aggregate.updated_at = func.now() # SQLAlchemy's onupdate will handle this, but explicit here too.
    else:
        # Create new aggregate
        db_aggregate = models.Aggregate(
            feed_id=aggregate_data.feed_id,
            agg_name=aggregate_data.agg_name,
            timeframe=aggregate_data.timeframe,
            data_json=aggregate_data.data_json
        )
        db.add(db_aggregate)

    db.commit()
    db.refresh(db_aggregate)
    return db_aggregate

def get_aggregates_for_feed(db: Session, feed_id: str) -> List[models.Aggregate]:
    """Retrieve all aggregates for a given feed ID."""
    return db.query(models.Aggregate).filter(models.Aggregate.feed_id == feed_id).all()

def delete_aggregate(db: Session, agg_id: uuid.UUID) -> Optional[models.Aggregate]:
    """Delete an aggregate by its UUID."""
    db_aggregate = db.query(models.Aggregate).filter(models.Aggregate.id == agg_id).first()
    if db_aggregate:
        db.delete(db_aggregate)
        db.commit()
    return db_aggregate
