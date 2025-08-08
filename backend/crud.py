# backend/crud.py

# This file contains the Create, Read, Update, and Delete (CRUD) operations
# for interacting with your database models using SQLAlchemy.
# These functions abstract the database logic away from your API endpoints.
from sqlalchemy import case, and_
import asyncio
from sqlalchemy import func, desc, or_, select, tuple_
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any, Sequence
import uuid
import logging
from datetime import datetime, timezone, timedelta
from pydantic import HttpUrl, BaseModel, AnyUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects import postgresql # Import for Postgres specific functions like insert
from sqlalchemy.orm import selectinload
from sqlalchemy import update
from backend import models, schemas
from backend.services import achievement_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Helper for timeframes ---
def get_time_boundary(timeframe: str) -> datetime:
    """Calculates the datetime boundary for a given timeframe."""
    now = datetime.now(timezone.utc)
    if timeframe == "1h":
        return now - timedelta(hours=1)
    elif timeframe == "6h":
        return now - timedelta(hours=6)
    elif timeframe == "1d":
        return now - timedelta(days=1)
    elif timeframe == "7d":
        return now - timedelta(days=7)
    elif timeframe == "30d":
        return now - timedelta(days=30)
    elif timeframe == "allTime":
        return datetime.min.replace(tzinfo=timezone.utc)
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

def _get_achievement_score_case(rarity_column):
    """Returns a reusable SQLAlchemy CASE statement for calculating achievement score."""
    return case(
        (rarity_column <= 0.1, 1000),
        (rarity_column <= 1, 500),
        (rarity_column <= 5, 200),
        (rarity_column <= 10, 100),
        (rarity_column <= 25, 50),
        (rarity_column <= 50, 20),
        else_=10
    )

# --- User CRUD Operations ---

async def get_user(db: AsyncSession, user_did: str) -> Optional[models.User]:
    """Retrieve a user by their DID asynchronously."""
    result = await db.execute(select(models.User).where(models.User.did == user_did))
    return result.scalar_one_or_none()

async def get_user_by_handle(db: AsyncSession, handle: str) -> Optional[models.User]:
    """Retrieve a user by their handle asynchronously."""
    result = await db.execute(select(models.User).where(models.User.handle == handle))
    return result.scalar_one_or_none()

# Batch user creation/update function
async def upsert_users_batch(db: AsyncSession, users: List[schemas.UserCreate]) -> List[models.User]:
    """
    Batch creates or updates users using PostgreSQL's ON CONFLICT (UPSERT).
    """
    if not users:
        return []

    # --- FIX: Sanitize and de-duplicate user data before upserting ---
    # This prevents IntegrityError when multiple unresolved profiles are assigned
    # the same placeholder handle (e.g., 'handle.invalid').
    processed_users_by_did: Dict[str, schemas.UserCreate] = {}
    for user in users:
        # Prioritize the latest user data for a given DID
        processed_users_by_did[user.did] = user

    users_to_insert = list(processed_users_by_did.values())

    # Now, within this de-duplicated list, ensure handles are unique for placeholders
    # This is a secondary de-duplication/sanitization step
    final_users_to_insert: List[schemas.UserCreate] = []
    seen_handles: set[str] = set()
    for user in users_to_insert:
        # Sanitize handle if it's missing or a known bad placeholder
        if not user.handle or user.handle == 'handle.invalid':
            user.handle = f"unknown.{user.did.split(':')[-1]}"
        
        # If the handle is already seen in this batch AND it's a placeholder, make it more unique
        if user.handle in seen_handles and user.handle.startswith("unknown."):
            user.handle = f"unknown.{user.did.split(':')[-1]}.{uuid.uuid4().hex[:8]}" # Add a random suffix
        
        seen_handles.add(user.handle)
        final_users_to_insert.append(user)

    # --- NEW: Proactively resolve handle conflicts before upserting ---
    # This logic prevents IntegrityErrors when a handle is reassigned from one DID to another.
    handles_in_batch = {user.handle for user in final_users_to_insert if user.handle and not user.handle.startswith("unknown.")}
    if handles_in_batch:
        # Find any existing users in the DB that have one of these handles but a DIFFERENT did.
        dids_in_batch = {user.did for user in final_users_to_insert}
        stmt = select(models.User).where(
            models.User.handle.in_(handles_in_batch),
            models.User.did.notin_(dids_in_batch)
        )
        conflicting_users_in_db = (await db.execute(stmt)).scalars().all()

        if conflicting_users_in_db:
            logger.info(f"Found {len(conflicting_users_in_db)} users in DB with handles that are now taken by other DIDs in the current batch. Updating old users to free up handles.")
            for old_user in conflicting_users_in_db:
                # The user's handle is now stale. We'll mark it as unknown to free it up for the new owner.
                # The periodic DID refresh scheduler will eventually re-resolve this user's correct new handle.
                new_placeholder_handle = f"unknown.{old_user.did.split(':')[-1]}"
                logger.info(f"User {old_user.did}'s handle '{old_user.handle}' is now taken. Changing to placeholder '{new_placeholder_handle}'.")
                old_user.handle = new_placeholder_handle
                old_user.last_updated = datetime.now(timezone.utc) # Mark as updated
            # Commit the changes to the stale users to free up the handles
            # before the main batch upsert is attempted. This resolves the race condition.
            await db.commit()

    # Prepare data for insertion
    insert_data = []
    for user in final_users_to_insert: # Use the sanitized and de-duplicated list
        avatar_url_str = str(user.avatar_url) if isinstance(user.avatar_url, HttpUrl) else user.avatar_url
        insert_data.append({
            "did": user.did,
            "handle": user.handle,
            "display_name": user.display_name,
            "description": user.description,
            "avatar_url": avatar_url_str,
            "last_updated": datetime.now(timezone.utc),
            "followers_count": user.followers_count if user.followers_count is not None else 0,
            "following_count": user.following_count if user.following_count is not None else 0,
            "posts_count": user.posts_count if user.posts_count is not None else 0,
            "created_at": user.created_at if user.created_at else datetime.now(timezone.utc),
            "is_prominent": user.is_prominent if user.is_prominent is not None else False,
            "last_prominent_refresh_check": user.last_prominent_refresh_check
        })
    logger.debug(f"DIDs in batch before insert: {[d['did'] for d in insert_data]}")

    # Define the ON CONFLICT clause for updating existing records
    # This assumes 'did' is a unique constraint, and we want to update on did conflict.
    insert_stmt = postgresql.insert(models.User.__table__).values(insert_data)
    on_conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[models.User.did], # Conflict on 'did'
        set_= {
            "handle": insert_stmt.excluded.handle, # Update handle if it changed
            "display_name": insert_stmt.excluded.display_name,
            "description": insert_stmt.excluded.description,
            "avatar_url": insert_stmt.excluded.avatar_url,
            "last_updated": datetime.now(timezone.utc), # Always update timestamp
            "followers_count": insert_stmt.excluded.followers_count,
            "following_count": insert_stmt.excluded.following_count,
            "posts_count": insert_stmt.excluded.posts_count,
            "created_at": insert_stmt.excluded.created_at, # Ensure the original creation date is updated
            "is_prominent": insert_stmt.excluded.is_prominent,
            # last_prominent_refresh_check should NOT be updated here to prevent accidental resets
            # It's specifically updated in the periodic_did_refresh_scheduler.
            # You might conditionally update it here if a schema.UserCreate explicitly provides it
            # For now, it's safer to leave it out of the upsert set unless explicitly needed for general updates.
        }
    )

    try:
        await db.execute(on_conflict_stmt)
        await db.commit()
        # Fetch the updated/inserted users to return
        dids = [user.did for user in users_to_insert] # Use the sanitized list
        stmt = select(models.User).where(models.User.did.in_(dids))
        return (await db.execute(stmt)).scalars().all()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to batch upsert users: {e}", exc_info=True)
        return []

async def get_all_prominent_user_dids(db: AsyncSession) -> set[str]:
    """Retrieves a set of all user DIDs currently marked as prominent."""
    stmt = select(models.User.did).where(models.User.is_prominent == True)
    result = await db.execute(stmt)
    return set(result.scalars().all())

async def set_user_prominence_batch(db: AsyncSession, dids: List[str], is_prominent: bool):
    """Sets the is_prominent flag for a list of user DIDs in a single batch."""
    if not dids:
        return
    
    update_stmt = (
        update(models.User)
        .where(models.User.did.in_(dids))
        .values(is_prominent=is_prominent)
    )
    await db.execute(update_stmt)
    # The calling function is responsible for the transaction commit.

async def create_placeholder_users_batch(db: AsyncSession, dids: List[str]):
    """
    Ensures user records exist for a list of DIDs, creating placeholders if necessary.
    Uses ON CONFLICT DO NOTHING to be efficient and avoid overwriting existing profiles.
    """
    if not dids:
        return

    insert_data = [
        {
            "did": did,
            "handle": f"unknown.{did.split(':')[-1]}", # Unique placeholder handle
            "display_name": "Unknown",
            "last_updated": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc)
        }
        for did in dids
    ]

    insert_stmt = postgresql.insert(models.User.__table__).values(insert_data)
    on_conflict_stmt = insert_stmt.on_conflict_do_nothing(
        index_elements=[models.User.did]
    )
    await db.execute(on_conflict_stmt)

async def get_stale_user_dids_from_list(db: AsyncSession, dids: List[str]) -> List[str]:
    """
    From a given list of DIDs, returns a sub-list of those whose profiles
    are considered stale (last updated > 24 hours ago).
    This is used to trigger a profile refresh for an active user.
    """
    if not dids:
        return []
    
    # A user's profile is considered stale if it hasn't been updated in 24 hours.
    # We also exclude users with 'unknown' handles, as they are handled by the main
    # scheduler and will be resolved shortly anyway.
    time_boundary = datetime.now(timezone.utc) - timedelta(hours=24)
    
    stmt = select(models.User.did).where(
        models.User.did.in_(dids),
        models.User.last_updated < time_boundary,
        ~models.User.handle.like('unknown.%')
    )
    return (await db.execute(stmt)).scalars().all()


# Refactored create_user to use upsert_users_batch for consistency
async def create_user(db: AsyncSession, user: schemas.UserCreate) -> Optional[models.User]:
    """
    Create a new user in the database.
    This now calls the batch upsert function for single user creation.
    """
    result = await upsert_users_batch(db, [user])
    return result[0] if result else None

async def update_user(db: AsyncSession, user_did: str, user_update: schemas.UserUpdate) -> Optional[models.User]:
    """Update an existing user's details asynchronously."""
    db_user = await get_user(db, user_did) # Await get_user
    if db_user:
        update_data = user_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'avatar_url' and isinstance(value, HttpUrl):
                setattr(db_user, key, str(value))
            elif hasattr(db_user, key):
                setattr(db_user, key, value)
        await db.commit() # Await commit
        await db.refresh(db_user) # Await refresh
    return db_user

async def delete_user(db: AsyncSession, user_did: str) -> Optional[models.User]:
    """Delete a user from the database asynchronously."""
    db_user = await get_user(db, user_did) # Await get_user
    if db_user:
        await db.delete(db_user) # Await delete
        await db.commit() # Await commit
    return db_user

async def search_users(db: AsyncSession, query: str, limit: int = 10) -> Sequence[models.User]:
    """Searches for users by handle or display name with optional Redis caching."""
    if not query or len(query) < 2:
        return []
    
    # Try cache first (with fallback if Redis unavailable)
    try:
        from backend.cache import Cache, user_search_key
        cache_key = user_search_key(f"{query}:{limit}")
        cached_result = Cache.get(cache_key)
        if cached_result:
            return [models.User(**user_data) for user_data in cached_result]
    except Exception as e:
        logger.warning(f"Cache unavailable for user search: {e}")
    
    # Query database
    search_query = f"%{query}%"
    stmt = (
        select(models.User)
        .where(
            or_(
                models.User.handle.ilike(search_query),
                models.User.display_name.ilike(search_query),
            )
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    # Try to cache result (with fallback if Redis unavailable)
    try:
        user_dicts = [{
            'did': user.did,
            'handle': user.handle,
            'display_name': user.display_name,
            'avatar_url': user.avatar_url,
            'description': user.description
        } for user in users]
        Cache.set(cache_key, user_dicts, 600)
    except Exception as e:
        logger.warning(f"Failed to cache user search results: {e}")
    
    return users

async def search_hashtags(db: AsyncSession, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Searches for hashtags by partial match with optional Redis caching."""
    if not query or len(query) < 2:
        return []
    
    # Try cache first (with fallback if Redis unavailable)
    try:
        from backend.cache import Cache, hashtag_search_key
        cache_key = hashtag_search_key(f"{query}:{limit}")
        cached_result = Cache.get(cache_key)
        if cached_result:
            return cached_result
    except Exception as e:
        logger.warning(f"Cache unavailable for hashtag search: {e}")
    
    # Remove # prefix if present
    clean_query = query.lstrip('#').lower()
    search_pattern = f"%{clean_query}%"
    
    # Use a subquery to unnest hashtags first, then filter
    hashtag_subquery = select(
        func.lower(func.jsonb_array_elements_text(models.Post.hashtags)).label('hashtag'),
        models.Post.id.label('post_id')
    ).where(
        models.Post.hashtags.isnot(None)
    ).subquery()
    
    stmt = select(
        hashtag_subquery.c.hashtag,
        func.count(func.distinct(hashtag_subquery.c.post_id)).label('count')
    ).where(
        hashtag_subquery.c.hashtag.ilike(search_pattern)
    ).group_by(
        hashtag_subquery.c.hashtag
    ).order_by(
        func.count(func.distinct(hashtag_subquery.c.post_id)).desc()
    ).limit(limit)
    
    result = await db.execute(stmt)
    hashtags = [{
        'hashtag': hashtag,
        'count': count
    } for hashtag, count in result.all()]
    
    # Try to cache result (with fallback if Redis unavailable)
    try:
        Cache.set(cache_key, hashtags, 900)
    except Exception as e:
        logger.warning(f"Failed to cache hashtag search results: {e}")
    
    return hashtags

# --- NEW CRUD FUNCTIONS FOR PROFILES ---

async def get_user_feed_stats(db: AsyncSession, user_did: str, feed_id: str) -> Optional[models.UserStats]:
    """Retrieve a user's statistics for a specific feed. If no stats exist, calculate basic stats on-the-fly."""
    stmt = select(models.UserStats).where(
        models.UserStats.user_did == user_did,
        models.UserStats.feed_id == feed_id
    )
    result = await db.execute(stmt)
    existing_stats = result.scalar_one_or_none()
    
    if existing_stats:
        return existing_stats
    
    # If no stats exist, check if user has posts in this feed and create basic stats
    posts_stmt = select(
        func.count(models.Post.id).label('post_count'),
        func.sum(models.Post.like_count).label('total_likes_received'),
        func.sum(models.Post.repost_count).label('total_reposts_received'),
        func.sum(models.Post.reply_count).label('total_replies_received'),
        func.sum(models.Post.quote_count).label('total_quotes_received'),
        func.min(models.Post.created_at).label('first_post_at'),
        func.max(models.Post.created_at).label('latest_post_at')
    ).select_from(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.Post.author_did == user_did,
        models.FeedPost.feed_id == feed_id
    )
    
    posts_result = await db.execute(posts_stmt)
    row = posts_result.first()
    
    if not row or not row.post_count:
        return None
    
    # Create a temporary UserStats object (not saved to DB)
    temp_stats = models.UserStats(
        user_did=user_did,
        feed_id=feed_id,
        post_count=row.post_count or 0,
        total_likes_received=row.total_likes_received or 0,
        total_reposts_received=row.total_reposts_received or 0,
        total_replies_received=row.total_replies_received or 0,
        total_quotes_received=row.total_quotes_received or 0,
        first_post_at=row.first_post_at,
        latest_post_at=row.latest_post_at
    )
    
    return temp_stats

async def get_user_achievements(db: AsyncSession, user_did: str) -> Sequence[models.UserAchievement]:
    """
    Gets a user's achievements, intelligently fetching per-feed rarity data
    and sorting by the true rarity (rarest first).
    """
    # Step 1: Fetch all of the user's earned achievements without sorting yet.
    stmt = select(models.UserAchievement).options(
        selectinload(models.UserAchievement.achievement),
        selectinload(models.UserAchievement.feed)
    ).where(
        models.UserAchievement.user_did == user_did
    )
    result = await db.execute(stmt)
    user_achievements = list(result.scalars().all())

    # Step 2: Identify which achievements are per-feed and need their rarity data patched.
    per_feed_lookups = []
    for ua in user_achievements:
        if ua.achievement and ua.achievement.type == models.AchievementType.PER_FEED and ua.feed_id:
            per_feed_lookups.append((ua.achievement_id, ua.feed_id))

    # Step 3: If there are any per-feed achievements, fetch their specific rarities in one batch.
    if per_feed_lookups:
        rarity_stmt = select(models.AchievementFeedRarity).where(
            tuple_(models.AchievementFeedRarity.achievement_id, models.AchievementFeedRarity.feed_id).in_(per_feed_lookups)
        )
        rarity_results = await db.execute(rarity_stmt)
        rarity_map = {(r.achievement_id, r.feed_id): r for r in rarity_results.scalars().all()}

        # Step 4: Patch the original achievement objects with the correct per-feed rarity data.
        for ua in user_achievements:
            if ua.achievement and ua.achievement.type == models.AchievementType.PER_FEED and ua.feed_id:
                feed_rarity = rarity_map.get((ua.achievement_id, ua.feed_id))
                if feed_rarity:
                    ua.achievement.rarity_percentage = feed_rarity.rarity_percentage
                    ua.achievement.rarity_tier = feed_rarity.rarity_tier
                    ua.achievement.rarity_label = feed_rarity.rarity_label

    # Step 5: Now that all rarity data is correct, sort the list in Python.
    user_achievements.sort(key=lambda ua: ua.achievement.rarity_percentage if ua.achievement and ua.achievement.rarity_percentage is not None else 100.0)

    return user_achievements

async def get_posts_by_author_for_feed(db: AsyncSession, feed_id: str, author_did: str, limit: int = 5) -> Sequence[models.Post]:
    """Retrieve the most recent posts by a specific author within a specific feed."""
    stmt = select(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.author_did == author_did
    ).order_by(
        desc(models.Post.created_at)
    ).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_posts_by_author_in_feed(db: AsyncSession, feed_id: str, author_did: str, limit: int = 10, skip: int = 0) -> Sequence[models.Post]:
    """Retrieve posts by a specific author within a specific feed with pagination."""
    stmt = select(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.author_did == author_did
    ).options(
        selectinload(models.Post.author)
    ).order_by(
        desc(models.Post.created_at)
    ).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_posts_by_hashtag_in_feed(db: AsyncSession, feed_id: str, hashtag: str, limit: int = 20, skip: int = 0) -> Sequence[models.Post]:
    """Retrieve posts containing a specific hashtag within a specific feed with pagination."""
    stmt = select(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        or_(
            models.Post.hashtags.op('@>')([hashtag]),
            models.Post.hashtags.op('@>')([hashtag.lower()]),
            models.Post.hashtags.op('@>')([hashtag.capitalize()])
        )
    ).options(
        selectinload(models.Post.author)
    ).order_by(
        desc(models.Post.created_at)
    ).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_hashtag_analytics(db: AsyncSession, feed_id: str, hashtag: str) -> Dict[str, Any]:
    """Get comprehensive analytics for a hashtag in a feed."""
    # Get total usage count and engagement stats
    stats_stmt = select(
        func.count(models.Post.id).label('total_posts'),
        func.avg(models.Post.like_count).label('avg_likes'),
        func.avg(models.Post.repost_count).label('avg_reposts'),
        func.sum(models.Post.like_count).label('total_likes'),
        func.sum(models.Post.repost_count).label('total_reposts')
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        or_(
            models.Post.hashtags.op('@>')([hashtag]),
            models.Post.hashtags.op('@>')([hashtag.lower()]),
            models.Post.hashtags.op('@>')([hashtag.capitalize()])
        )
    )
    
    # Get top users who use this hashtag
    top_users_stmt = select(
        models.User.handle,
        models.User.display_name,
        models.User.did,
        func.count(models.Post.id).label('usage_count')
    ).join(
        models.Post, models.User.did == models.Post.author_did
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        or_(
            models.Post.hashtags.op('@>')([hashtag]),
            models.Post.hashtags.op('@>')([hashtag.lower()]),
            models.Post.hashtags.op('@>')([hashtag.capitalize()])
        )
    ).group_by(
        models.User.did, models.User.handle, models.User.display_name
    ).order_by(
        desc('usage_count')
    ).limit(5)
    
    # Execute queries
    stats_result = await db.execute(stats_stmt)
    stats_row = stats_result.first()
    
    top_users_result = await db.execute(top_users_stmt)
    top_users = [{
        'handle': row.handle,
        'display_name': row.display_name,
        'did': row.did,
        'usage_count': row.usage_count
    } for row in top_users_result.all()]
    
    return {
        'hashtag': hashtag,
        'total_posts': stats_row.total_posts or 0,
        'avg_likes': round(float(stats_row.avg_likes or 0), 1),
        'avg_reposts': round(float(stats_row.avg_reposts or 0), 1),
        'total_engagement': (stats_row.total_likes or 0) + (stats_row.total_reposts or 0),
        'top_users': top_users
    }

async def get_in_progress_achievements(db: AsyncSession, user_did: str) -> List[Dict[str, Any]]:
    """
    Calculates and returns a list of achievements a user is currently making progress towards
    but has not yet earned. The results are sorted by progress percentage.
    """
    # 1. Fetch all necessary data in parallel for efficiency
    active_achievements_stmt = select(models.Achievement).where(models.Achievement.is_active == True)
    user_stats_stmt = select(models.UserStats).where(models.UserStats.user_did == user_did)
    earned_achievements_stmt = select(models.UserAchievement).where(models.UserAchievement.user_did == user_did)

    # Execute queries sequentially on the same session to avoid concurrency errors.
    active_achievements_res = await db.execute(active_achievements_stmt)
    user_stats_records_res = await db.execute(user_stats_stmt)
    earned_achievements_res = await db.execute(earned_achievements_stmt)

    all_active_achievements = active_achievements_res.scalars().all()
    user_stats_records = user_stats_records_res.scalars().all()
    earned_achievements_records = earned_achievements_res.scalars().all()

    # 2. Create a lookup map for achievements the user has already earned for O(1) checks
    earned_map = {(ach.achievement_id, ach.feed_id) for ach in earned_achievements_records}

    # 3. Create a map of feeds the user has posted in for easy lookup
    feed_ids_in_stats = {stat.feed_id for stat in user_stats_records}
    if not feed_ids_in_stats:
        feeds_map = {}
    else:
        feeds_map_stmt = select(models.Feed).where(models.Feed.id.in_(feed_ids_in_stats))
        feeds_map = {feed.id: feed for feed in (await db.execute(feeds_map_stmt)).scalars().all()}

    in_progress_list = []

    # 4. Iterate through all active achievements to find ones not yet earned
    for ach in all_active_achievements:
        criteria = ach.criteria
        if not isinstance(criteria, dict): continue

        required_value = criteria.get('value')
        if not (isinstance(required_value, (int, float)) and required_value > 0):
            continue

        if ach.type == models.AchievementType.PER_FEED:
            for stats_record in user_stats_records:
                if (ach.id, stats_record.feed_id) in earned_map: continue

                current_value = achievement_service.get_current_value_for_achievement(ach, stats_record)
                if 0 < current_value < required_value:
                    in_progress_list.append({
                        "achievement": ach, "current_value": current_value, "required_value": required_value,
                        "progress_percentage": min((current_value / required_value) * 100, 100.0),
                        "feed": feeds_map.get(stats_record.feed_id)
                    })
        elif ach.type == models.AchievementType.GLOBAL:
            if (ach.id, None) in earned_map: continue

            current_value = achievement_service.get_current_value_for_achievement(ach, user_stats_records)
            if 0 < current_value < required_value:
                in_progress_list.append({
                    "achievement": ach, "current_value": current_value, "required_value": required_value,
                    "progress_percentage": min((current_value / required_value) * 100, 100.0), "feed": None
                })

    # 5. Sort the list by progress percentage, descending
    in_progress_list.sort(key=lambda x: x['progress_percentage'], reverse=True)

    return in_progress_list

# --- NEW CRUD FUNCTIONS FOR LEADERBOARDS ---

async def get_global_leaderboard(db: AsyncSession, limit: int = 100) -> List[Any]:
    """
    Retrieves the global leaderboard, ranking users by a weighted achievement score.
    Rarer achievements contribute more to the score.
    Returns a list of tuples, where each is (User object, total_score).
    """
    score_calculation = case(
        (
            models.Achievement.type == models.AchievementType.GLOBAL,
            _get_achievement_score_case(models.Achievement.rarity_percentage)
        ),
        (
            models.Achievement.type == models.AchievementType.PER_FEED,
            # Use feed-specific rarity, but default to 10 points if no rarity entry exists
            func.coalesce(_get_achievement_score_case(models.AchievementFeedRarity.rarity_percentage), 10)
        ),
        else_=0
    )

    stmt = (
        select(
            models.User,
            func.sum(score_calculation).label("total_score")
        )
        .join(models.UserAchievement, models.User.did == models.UserAchievement.user_did)
        .join(models.Achievement, models.UserAchievement.achievement_id == models.Achievement.id)
        .outerjoin(
            models.AchievementFeedRarity,
            and_(
                models.UserAchievement.achievement_id == models.AchievementFeedRarity.achievement_id,
                models.UserAchievement.feed_id == models.AchievementFeedRarity.feed_id
            )
        )
        .group_by(models.User.did)
        .order_by(func.sum(score_calculation).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.all()

async def get_feed_leaderboard(db: AsyncSession, feed_id: str, limit: int = 100) -> List[Any]:
    """
    Retrieves the leaderboard for a specific feed, ranking users by a weighted
    achievement score based on rarity within that feed.
    """
    score_calculation = _get_achievement_score_case(models.AchievementFeedRarity.rarity_percentage)

    stmt = (
        select(
            models.User,
            func.sum(score_calculation).label("total_score")
        )
        .join(models.UserAchievement, models.User.did == models.UserAchievement.user_did)
        .join(
            models.AchievementFeedRarity,
            and_(
                models.UserAchievement.achievement_id == models.AchievementFeedRarity.achievement_id,
                models.UserAchievement.feed_id == models.AchievementFeedRarity.feed_id
            )
        )
        .where(models.UserAchievement.feed_id == feed_id) # Filter for the specific feed
        .group_by(models.User.did)
        .order_by(func.sum(score_calculation).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.all()

async def get_feeds_with_leaderboards(db: AsyncSession) -> Sequence[models.Feed]:
    """Retrieves a list of feeds that have at least one achievement earned."""
    subquery = select(models.UserAchievement.feed_id.distinct()).where(models.UserAchievement.feed_id.isnot(None)).scalar_subquery()
    stmt = select(models.Feed).where(models.Feed.id.in_(subquery)).order_by(models.Feed.name)
    result = await db.execute(stmt)
    return result.scalars().all()

# --- NEW CRUD FUNCTIONS FOR DYNAMIC RARITY CALCULATION ---

async def create_achievement(db: AsyncSession, achievement: schemas.AchievementCreate) -> models.Achievement:
    """Creates a new achievement in the database."""
    # Check for key uniqueness to provide a better error message
    existing_achievement_stmt = select(models.Achievement).where(models.Achievement.key == achievement.key)
    existing_achievement = (await db.execute(existing_achievement_stmt)).scalar_one_or_none()
    if existing_achievement:
        # This is a more specific error that can be caught in the endpoint
        raise IntegrityError(f"Achievement with key '{achievement.key}' already exists.", params=None, orig=None)

    # The AchievementCreate schema matches the model fields, so we can unpack it directly.
    db_achievement = models.Achievement(**achievement.model_dump())
    db.add(db_achievement)
    await db.commit()
    await db.refresh(db_achievement)
    return db_achievement


async def count_total_users(db: AsyncSession) -> int:
    """Counts the total number of users in the database."""
    result = await db.execute(select(func.count(models.User.did)))
    return result.scalar_one()

async def count_users_with_global_achievement(db: AsyncSession, achievement_id: int) -> int:
    """Counts how many unique users have earned a specific GLOBAL achievement."""
    stmt = select(func.count(func.distinct(models.UserAchievement.user_did))).where(
        models.UserAchievement.achievement_id == achievement_id
    )
    result = await db.execute(stmt)
    return result.scalar_one()

async def count_total_posters_in_feed(db: AsyncSession, feed_id: str) -> int:
    """Counts the total number of unique users who have posted in a specific feed."""
    # UserStats is the most reliable source for users active in a feed.
    stmt = select(func.count(models.UserStats.user_did)).where(
        models.UserStats.feed_id == feed_id
    )
    result = await db.execute(stmt)
    return result.scalar_one()

async def count_users_with_achievement_in_feed(db: AsyncSession, achievement_id: int, feed_id: str) -> int:
    """Counts how many unique users have earned a specific achievement within a specific feed."""
    stmt = select(func.count(func.distinct(models.UserAchievement.user_did))).where(
        models.UserAchievement.achievement_id == achievement_id,
        models.UserAchievement.feed_id == feed_id
    )
    result = await db.execute(stmt)
    return result.scalar_one()

# --- Post CRUD Operations ---

async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Optional[models.Post]:
    """Retrieve a post by its UUID asynchronously."""
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    return result.scalar_one_or_none()

async def get_post_by_uri(db: AsyncSession, post_uri: str) -> Optional[models.Post]:
    """Retrieve a post by its AT URI asynchronously."""
    result = await db.execute(select(models.Post).where(models.Post.uri == post_uri))
    return result.scalar_one_or_none()

# Batch post creation/update function
async def upsert_posts_batch(db: AsyncSession, posts: List[schemas.PostCreate]) -> List[models.Post]:
    """
    Batch creates or updates posts using PostgreSQL's ON CONFLICT (UPSERT).
    This handles new posts and updates existing ones (e.g., if engagement scores change).
    """
    if not posts:
        return []

    insert_data = []
    for post in posts:
        link_url_str = str(post.link_url) if isinstance(post.link_url, HttpUrl) else post.link_url
        thumbnail_url_str = str(post.thumbnail_url) if isinstance(post.thumbnail_url, HttpUrl) else post.thumbnail_url

        processed_links = [link_item.model_dump() if isinstance(link_item, BaseModel) else link_item for link_item in post.links] if post.links else []
        processed_mentions = [mention_item.model_dump() if isinstance(mention_item, BaseModel) else mention_item for mention_item in post.mentions] if post.mentions else []
        processed_embeds = post.embeds.model_dump() if isinstance(post.embeds, BaseModel) else post.embeds
        processed_images = [image.model_dump() for image in post.images] if post.images else []
        processed_facets = [facet_item.model_dump() if isinstance(facet_item, BaseModel) else facet_item for facet_item in post.facets] if post.facets else []

        insert_data.append({
            "uri": post.uri,
            "cid": post.cid,
            "text": post.text,
            "created_at": post.created_at,
            "ingested_at": datetime.now(timezone.utc),
            "author_did": post.author_did,
            "has_image": post.has_image,
            "has_alt_text": post.has_alt_text,
            "has_video": post.has_video if post.has_video is not None else False,
            "has_link": post.has_link,
            "has_quote": post.has_quote,
            "has_mention": post.has_mention,
            "images": processed_images,
            "link_url": link_url_str,
            "link_title": post.link_title,
            "link_description": post.link_description,
            "thumbnail_url": thumbnail_url_str,
            "aspect_ratio_width": post.aspect_ratio_width,
            "aspect_ratio_height": post.aspect_ratio_height,
            "hashtags": post.hashtags,
            "links": processed_links,
            "mentions": processed_mentions,
            "embeds": processed_embeds,
            "raw_record": post.raw_record,
            "like_count": post.like_count if post.like_count is not None else 0,
            "repost_count": post.repost_count if post.repost_count is not None else 0,
            "reply_count": post.reply_count if post.reply_count is not None else 0,
            "quote_count": post.quote_count if post.quote_count is not None else 0,
            "engagement_score": post.engagement_score if post.engagement_score is not None else 0.0,
            "next_poll_at": post.next_poll_at,
            "is_active_for_polling": post.is_active_for_polling if post.is_active_for_polling is not None else True,
            "quoted_post_uri": post.quoted_post_uri,
            "quoted_post_cid": post.quoted_post_cid,
            "quoted_post_author_did": post.quoted_post_author_did,
            "quoted_post_author_handle": post.quoted_post_author_handle,
            "quoted_post_author_display_name": post.quoted_post_author_display_name,
            "quoted_post_text": post.quoted_post_text,
            "quoted_post_like_count": post.quoted_post_like_count if post.quoted_post_like_count is not None else 0,
            "quoted_post_repost_count": post.quoted_post_repost_count if post.quoted_post_repost_count is not None else 0, # Corrected typo
            "quoted_post_reply_count": post.quoted_post_reply_count if post.quoted_post_reply_count is not None else 0,
            "quoted_post_created_at": post.quoted_post_created_at,
            "facets": processed_facets # Added facets
        })

    # ON CONFLICT DO UPDATE on 'uri' (assuming uri is unique and the primary way to identify a post)
    insert_stmt = postgresql.insert(models.Post.__table__).values(insert_data)
    on_conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[models.Post.cid], # Conflict on 'cid' for consistency with worker de-duplication
        set_= {
            "uri": insert_stmt.excluded.uri, # Update URI if it changed
            "text": insert_stmt.excluded.text,
            "ingested_at": datetime.now(timezone.utc), # Update ingestion timestamp
            "has_image": insert_stmt.excluded.has_image,
            "has_alt_text": insert_stmt.excluded.has_alt_text,
            "has_video": insert_stmt.excluded.has_video,
            "has_link": insert_stmt.excluded.has_link,
            "has_quote": insert_stmt.excluded.has_quote,
            "has_mention": insert_stmt.excluded.has_mention,
            "images": insert_stmt.excluded.images,
            "link_url": insert_stmt.excluded.link_url,
            "link_title": insert_stmt.excluded.link_title,
            "link_description": insert_stmt.excluded.link_description,
            "thumbnail_url": insert_stmt.excluded.thumbnail_url,
            "aspect_ratio_width": insert_stmt.excluded.aspect_ratio_width,
            "aspect_ratio_height": insert_stmt.excluded.aspect_ratio_height,
            "hashtags": insert_stmt.excluded.hashtags,
            "links": insert_stmt.excluded.links,
            "mentions": insert_stmt.excluded.mentions,
            "embeds": insert_stmt.excluded.embeds,
            "raw_record": insert_stmt.excluded.raw_record,
            "like_count": insert_stmt.excluded.like_count,
            "repost_count": insert_stmt.excluded.repost_count,
            "reply_count": insert_stmt.excluded.reply_count,
            "quote_count": insert_stmt.excluded.quote_count,
            "engagement_score": insert_stmt.excluded.engagement_score,
            "next_poll_at": insert_stmt.excluded.next_poll_at,
            "is_active_for_polling": insert_stmt.excluded.is_active_for_polling,
            "quoted_post_uri": insert_stmt.excluded.quoted_post_uri,
            "quoted_post_cid": insert_stmt.excluded.quoted_post_cid,
            "quoted_post_author_did": insert_stmt.excluded.quoted_post_author_did,
            "quoted_post_author_handle": insert_stmt.excluded.quoted_post_author_handle,
            "quoted_post_author_display_name": insert_stmt.excluded.quoted_post_author_display_name,
            "quoted_post_text": insert_stmt.excluded.quoted_post_text,
            "quoted_post_like_count": insert_stmt.excluded.quoted_post_like_count,
            "quoted_post_repost_count": insert_stmt.excluded.quoted_post_repost_count,
            "quoted_post_reply_count": insert_stmt.excluded.quoted_post_reply_count,
            "quoted_post_created_at": insert_stmt.excluded.quoted_post_created_at,
            "facets": insert_stmt.excluded.facets # Added facets
        }
    )

    try:
        await db.execute(on_conflict_stmt)
        await db.commit()
        # Fetch the updated/inserted posts to return, using the same key as the conflict
        cids = [post.cid for post in posts]
        stmt = select(models.Post).where(models.Post.cid.in_(cids))
        return (await db.execute(stmt)).scalars().all()
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to batch upsert posts: {e}", exc_info=True)
        return []

# Refactored create_post to use upsert_posts_batch for consistency
async def create_post(db: AsyncSession, post: schemas.PostCreate) -> Optional[models.Post]:
    """
    Create a new post in the database.
    This now calls the batch upsert function for single post creation.
    """
    result = await upsert_posts_batch(db, [post])
    return result[0] if result else None


async def update_post(db: AsyncSession, post_uri: str, post_update: schemas.PostUpdate) -> Optional[models.Post]:
    """Update an existing post's details asynchronously."""
    db_post = await get_post_by_uri(db, post_uri) # Await get_post_by_uri
    if db_post:
        update_data = post_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key in ['thumbnail_url', 'link_url'] and isinstance(value, HttpUrl):
                setattr(db_post, key, str(value))
            elif key == 'links' and value is not None:
                processed_links = [link_item.model_dump() if isinstance(link_item, BaseModel) else link_item for link_item in value]
                setattr(db_post, key, processed_links)
            elif key == 'mentions' and value is not None:
                processed_mentions = [mention_item.model_dump() if isinstance(mention_item, BaseModel) else mention_item for mention_item in value]
                setattr(db_post, key, processed_mentions)
            elif key == 'embeds' and value is not None:
                processed_embeds = value.model_dump() if isinstance(value, BaseModel) else value
                setattr(db_post, key, processed_embeds)
            elif key == 'facets' and value is not None: # Added handling for facets
                processed_facets = [facet_item.model_dump() if isinstance(facet_item, BaseModel) else facet_item for facet_item in value]
                setattr(db_post, key, processed_facets)
            elif key == 'images' and value is not None:
                processed_images = [image.model_dump() for image in value]
                setattr(db_post, key, processed_images)
            elif key in ['hashtags', 'raw_record', 'embeds'] and value is not None:
                setattr(db_post, key, value)
            elif hasattr(db_post, key):
                setattr(db_post, key, value)
                
        await db.commit() # Await commit
        await db.refresh(db_post) # Await refresh
    return db_post

async def get_posts(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """Retrieve a list of posts with pagination asynchronously."""
    stmt = select(models.Post).offset(skip).limit(limit)
    return (await db.execute(stmt)).scalars().all()

async def get_posts_by_author(db: AsyncSession, author_did: str, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """Retrieve posts by a specific author DID with pagination asynchronously."""
    stmt = select(models.Post).where(models.Post.author_did == author_did).offset(skip).limit(limit)
    return (await db.execute(stmt)).scalars().all()

async def delete_post(db: AsyncSession, post_id: uuid.UUID) -> Optional[models.Post]:
    """Delete a post from the database asynchronously."""
    db_post = await get_post(db, post_id) # Await get_post
    if db_post:
        await db.delete(db_post) # Await delete
        await db.commit() # Await commit
    return db_post

async def get_posts_due_for_poll(db: AsyncSession, limit: int = 100) -> List[models.Post]:
    """
    Retrieves a batch of posts that are active and due for polling,
    ordered by their scheduled poll time.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(models.Post)
        .where(
            models.Post.is_active_for_polling == True,
            models.Post.next_poll_at <= now,
        )
        .order_by(models.Post.next_poll_at.asc()) # Poll the most overdue first
        .limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()

# --- Feed CRUD Operations (UPDATED) ---

async def create_feed(db: AsyncSession, feed: schemas.FeedCreate) -> models.Feed:
    """Create a new feed asynchronously."""
    # Convert AnyUrl to string before passing to the model constructor
    websocket_url_str = str(feed.contrails_websocket_url) if feed.contrails_websocket_url else None

    db_feed = models.Feed(
        id=feed.id,
        name=feed.name,
        description=feed.description,
        contrails_websocket_url=websocket_url_str,
        bluesky_at_uri=feed.bluesky_at_uri,
        tier=feed.tier,
        last_aggregated_at=feed.last_aggregated_at
    )
    db.add(db_feed)
    await db.commit() # Await commit
    await db.refresh(db_feed) # Await refresh
    return db_feed

async def get_feed_by_id(db: AsyncSession, feed_id: str) -> Optional[models.Feed]:
    """Retrieve a feed by its string ID asynchronously."""
    result = await db.execute(select(models.Feed).where(models.Feed.id == feed_id))
    return result.scalar_one_or_none()

async def get_feeds(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Feed]:
    """Retrieve a list of feeds with pagination asynchronously."""
    stmt = select(models.Feed).offset(skip).limit(limit)
    return (await db.execute(stmt)).scalars().all()

async def get_all_feeds(db: AsyncSession) -> List[models.Feed]:
    """Retrieves all feed configurations from the database asynchronously."""
    # This function must retrieve ALL feeds, without a limit, as full objects.
    stmt = select(models.Feed)
    return (await db.execute(stmt)).scalars().all()

async def update_feed(db: AsyncSession, feed_id: str, feed_update: schemas.FeedUpdate) -> Optional[models.Feed]:
    """Update an existing feed's details asynchronously."""
    db_feed = await get_feed_by_id(db, feed_id) # Await get_feed_by_id
    if db_feed:
        update_data = feed_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(db_feed, key):
                # Convert Pydantic URL types to strings before setting on the model
                if isinstance(value, (HttpUrl, AnyUrl)):
                    setattr(db_feed, key, str(value))
                else:
                    setattr(db_feed, key, value)
        await db.commit() # Await commit
        await db.refresh(db_feed) # Await refresh
    return db_feed

async def delete_feed(db: AsyncSession, feed_id: str) -> Optional[models.Feed]:
    """Delete a feed from the database asynchronously."""
    db_feed = await get_feed_by_id(db, feed_id) # Await get_feed_by_id
    if db_feed:
        await db.delete(db_feed) # Await delete
        await db.commit() # Await commit
    return db_feed

# --- FeedPost CRUD Operations ---
# Note: feed_id is now a string type

async def get_feed_post(db: AsyncSession, feed_post_id: uuid.UUID) -> Optional[models.FeedPost]:
    """Retrieve a feed post entry by its UUID asynchronously."""
    result = await db.execute(select(models.FeedPost).where(models.FeedPost.id == feed_post_id))
    return result.scalar_one_or_none()

# Batch feed post creation
async def create_feed_posts_batch(db: AsyncSession, feed_posts: List[schemas.FeedPostCreate]) -> List[models.FeedPost]:
    """
    Batch creates new entries linking posts to feeds.
    Uses ON CONFLICT DO NOTHING to handle duplicates efficiently.
    """
    if not feed_posts:
        return []

    insert_data = []
    for fp in feed_posts:
        insert_data.append({
            "post_id": fp.post_id,
            "feed_id": fp.feed_id,
            "relevance_score": fp.relevance_score if fp.relevance_score is not None else 0,
            "ingested_at": fp.ingested_at if fp.ingested_at else datetime.now(timezone.utc)
        })

    # ON CONFLICT DO NOTHING (assuming a unique constraint on (post_id, feed_id))
    insert_stmt = postgresql.insert(models.FeedPost.__table__).values(insert_data)
    on_conflict_stmt = insert_stmt.on_conflict_do_nothing(
        index_elements=[models.FeedPost.post_id, models.FeedPost.feed_id] # Conflict on this composite key
    )

    try:
        await db.execute(on_conflict_stmt)
        await db.commit()
        # It's difficult to get the *newly inserted* objects directly with ON CONFLICT DO NOTHING
        # unless you use RETURNING, which is more complex with batch operations.
        # For simplicity, we'll just return an empty list or fetch by IDs if necessary,
        # but the primary goal is efficient insertion.
        # If you need the objects returned, you'd have to query for them by (post_id, feed_id)
        # after the batch insert, filtering by the input list.
        # For now, this function is about efficient insertion.
        logger.info(f"Successfully attempted to batch insert {len(feed_posts)} feed posts.")
        return [] # Or implement fetching logic if crucial to get the ORM objects back.
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to batch create feed posts: {e}", exc_info=True)
        return []

# Refactored create_feed_post to use batch function
async def create_feed_post(db: AsyncSession, feed_post: schemas.FeedPostCreate) -> Optional[models.FeedPost]:
    """
    Create a new entry linking a post to a feed.
    This now calls the batch creation function for a single feed post.
    """
    await create_feed_posts_batch(db, [feed_post])
    # Since batch create with ON CONFLICT DO NOTHING doesn't easily return the object,
    # we'll fetch it if it exists.
    # Note: This might still result in fetching an existing one even if it was just inserted
    # in the batch. If precise new object return is critical, adjust upsert logic.
    result = await db.execute(
        select(models.FeedPost).where(
            (models.FeedPost.post_id == feed_post.post_id) & (models.FeedPost.feed_id == feed_post.feed_id)
        )
    )
    return result.scalar_one_or_none()


async def get_feed_posts_for_feed(db: AsyncSession, feed_id: str, skip: int = 0, limit: int = 100) -> List[models.FeedPost]:
    """Retrieve all feed posts for a given feed ID asynchronously."""
    stmt = (
        select(models.FeedPost)
        .where(models.FeedPost.feed_id == feed_id)
        .order_by(models.FeedPost.ingested_at.desc())
        .offset(skip).limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()

async def get_posts_for_feed(db: AsyncSession, feed_id: str, skip: int = 0, limit: int = 100) -> List[models.Post]:
    """
    Retrieve actual Post objects for a given feed ID, ordered by ingestion time asynchronously.
    Uses a join to efficiently get posts associated with a feed.
    """
    stmt = (
        select(models.Post)
        .join(models.FeedPost.__table__, models.Post.id == models.FeedPost.post_id)
        .where(models.FeedPost.feed_id == feed_id)
        .options(selectinload(models.Post.author)) # Eagerly load the author relationship
        .order_by(models.FeedPost.ingested_at.desc())
        .offset(skip).limit(limit)
    )
    return (await db.execute(stmt)).scalars().all()

# --- Aggregate CRUD Operations ---

async def get_aggregate(db: AsyncSession, feed_id: str, agg_name: str, timeframe: str) -> Optional[models.Aggregate]:
    """Retrieve a specific aggregate by its identifying attributes asynchronously."""
    result = await db.execute(select(models.Aggregate).where(
        (models.Aggregate.feed_id == feed_id) &
        (models.Aggregate.agg_name == agg_name) &
        (models.Aggregate.timeframe == timeframe)
    ))
    agg = result.scalar_one_or_none()
    # FIX: Handle legacy records where created_at might be NULL.
    # If created_at is None, fall back to updated_at to prevent Pydantic validation errors.
    if agg and agg.created_at is None and agg.updated_at is not None:
        logger.warning(f"Aggregate {agg.id} has NULL created_at. Falling back to updated_at value.")
        agg.created_at = agg.updated_at

    return agg

async def get_aggregate_by_name(db: AsyncSession, name: str) -> Optional[models.Aggregate]:
    """
    Retrieves a specific aggregate by its composite name string asynchronously.
    The name is expected to be in the format 'feed_id-agg_name-timeframe'.
    """
    try:
        parts = name.split('-', 2)
        if len(parts) == 3:
            feed_id, agg_name, timeframe = parts
            return await get_aggregate(db, feed_id, agg_name, timeframe)
        else:
            logger.error(f"Invalid aggregate name format: '{name}'. Expected 'feed_id-agg_name-timeframe'.")
            return None
    except Exception as e:
        logger.error(f"Error parsing aggregate name '{name}': {e}", exc_info=True)
        return None

def _serialize_datetime_objects(obj):
    """Recursively convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _serialize_datetime_objects(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime_objects(item) for item in obj]
    else:
        return obj

async def create_or_update_aggregate(
    db: AsyncSession,
    aggregate_data: schemas.AggregateCreate
) -> models.Aggregate:
    """
    Creates a new aggregate or updates an existing one based on feed_id, agg_name, and timeframe.
    Uses PostgreSQL's ON CONFLICT (UPSERT) for efficiency.
    """
    # Ensure data_json is a serializable dictionary. If it's a Pydantic model, dump it.
    json_data = (
        aggregate_data.data_json.model_dump()
        if isinstance(aggregate_data.data_json, BaseModel)
        else aggregate_data.data_json
    )
    
    # Apply comprehensive datetime serialization to ensure no datetime objects remain
    json_data = _serialize_datetime_objects(json_data)

    insert_stmt = postgresql.insert(models.Aggregate.__table__).values(
        id=uuid.uuid4(),
        feed_id=aggregate_data.feed_id,
        agg_name=aggregate_data.agg_name,
        timeframe=aggregate_data.timeframe,
        data_json=json_data,
        created_at=func.now(),
        updated_at=func.now()
    )

    on_conflict_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[
            models.Aggregate.feed_id,
            models.Aggregate.agg_name,
            models.Aggregate.timeframe,
        ],
        set_= {
            "data_json": insert_stmt.excluded.data_json,
            "updated_at": func.now(),  # Explicitly update timestamp
        },
    )

    try:
        await db.execute(on_conflict_stmt)
        await db.commit()

        # Explicitly fetch the aggregate after the upsert to ensure the full object is returned.
        updated_aggregate = await get_aggregate(
            db,
            feed_id=aggregate_data.feed_id,
            agg_name=aggregate_data.agg_name,
            timeframe=aggregate_data.timeframe,
        )
        if not updated_aggregate:
            raise Exception("Failed to retrieve aggregate after upsert operation.")
        return updated_aggregate

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create/update aggregate: {e}", exc_info=True)
        raise  # Re-raise if aggregate creation/update is critical

async def get_aggregates_for_feed(db: AsyncSession, feed_id: str) -> List[models.Aggregate]:
    """Retrieve all aggregates for a given feed ID asynchronously."""
    stmt = select(models.Aggregate).where(models.Aggregate.feed_id == feed_id)
    return (await db.execute(stmt)).scalars().all()

async def delete_aggregate(db: AsyncSession, agg_id: uuid.UUID) -> Optional[models.Aggregate]:
    """Delete an aggregate by its UUID asynchronously."""
    # For now, directly query by ID
    result = await db.execute(select(models.Aggregate).where(models.Aggregate.id == agg_id))
    db_aggregate = result.scalar_one_or_none()

    if db_aggregate:
        await db.delete(db_aggregate)
        await db.commit()
    return db_aggregate

# --- NEW AGGREGATION FUNCTIONS (made asynchronous) ---

async def get_top_posts_for_feed(
    db: AsyncSession,
    feed_id: str,
    timeframe: str,
    limit: int = 50
) -> List[models.Post]:
    """
    Retrieves the top posts for a given feed and timeframe, ordered by engagement score asynchronously.
    Only includes posts that are still active for polling.
    """
    time_boundary = get_time_boundary(timeframe)
    
    query = select(models.Post) \
        .join(models.FeedPost.__table__, models.Post.id == models.FeedPost.post_id) \
        .where(
            (models.FeedPost.feed_id == feed_id) &
            (models.FeedPost.feed_id == feed_id) &
            (models.Post.is_active_for_polling == True)
        )
    if timeframe != "allTime":
        query = query.where(models.FeedPost.ingested_at >= time_boundary)
    
    query = query.order_by(desc(models.Post.engagement_score)).limit(limit)
    query = query.options(selectinload(models.Post.author)) # Eagerly load author to prevent async errors
    
    stmt = query
    return (await db.execute(stmt)).scalars().all()

async def get_top_hashtags_for_feed(
    db: AsyncSession,
    feed_id: str,
    timeframe: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Retrieves the top hashtags for a given feed and timeframe by performing
    aggregation directly in the database for high performance. This leverages
    the GIN index on the 'hashtags' JSONB column.
    """
    time_boundary = get_time_boundary(timeframe)

    # This function unnests the JSONB array of hashtags into a text column
    # that we can group and count.
    hashtag_cte = func.jsonb_array_elements_text(models.Post.hashtags).alias('hashtag')

    # The main query now joins on the unnested hashtags, groups by them, and counts them.
    # The syntax for selecting the unnested value is `hashtag_cte.c.value`.
    query = select(
        hashtag_cte.c.value.label('hashtag_name'),
        func.count().label('hashtag_count')
    ).select_from(models.Post) \
        .join(models.FeedPost, models.Post.id == models.FeedPost.post_id) \
        .join(hashtag_cte, True) \
        .where(
            (models.FeedPost.feed_id == feed_id) &
            (models.Post.is_active_for_polling == True)
        )
    if timeframe != "allTime":
        query = query.where(models.FeedPost.ingested_at >= time_boundary)
    
    query = query.group_by('hashtag_name').order_by(desc('hashtag_count')).limit(limit)

    result = await db.execute(query)
    return [{"hashtag": tag, "count": count} for tag, count in result.all()]

async def get_top_users_for_feed(
    db: AsyncSession,
    feed_id: str,
    timeframe: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Retrieves the top users for a given feed and timeframe, based on their posts' engagement asynchronously.
    Considers posts that are still active for polling.
    """
    time_boundary = get_time_boundary(timeframe)

    # Calculate total engagement score per author for posts within the timeframe and feed
    query = select(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        func.sum(models.Post.engagement_score).label('total_engagement_score')
    ) \
    .join(models.Post.__table__, models.User.did == models.Post.author_did) \
    .join(models.FeedPost.__table__, models.Post.id == models.FeedPost.post_id) \
    .where(
        (models.FeedPost.feed_id == feed_id) &
        (models.Post.is_active_for_polling == True)
    )
    if timeframe != "allTime":
        query = query.where(models.FeedPost.ingested_at >= time_boundary)
    
    query = query.group_by(models.User.did, models.User.handle, models.User.display_name) \
    .order_by(desc('total_engagement_score')) \
    .limit(limit)
    
    result = await db.execute(query)
    result_list = []
    for user_did, user_handle, user_display_name, total_engagement_score in result:
        result_list.append({
            "did": user_did,
            "handle": user_handle,
            "display_name": user_display_name,
            "total_engagement_score": total_engagement_score
        })
    return result_list

async def get_top_posters_by_count_for_feed(
    db: AsyncSession,
    feed_id: str,
    timeframe: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Retrieves the top posters by count for a given feed and timeframe
    from the pre-calculated aggregates asynchronously.
    """
    aggregate = await get_aggregate(db, feed_id, "top_posters_by_count", timeframe)
    if aggregate and aggregate.data_json:
        return aggregate.data_json.get("posters", [])[:limit]
    return []