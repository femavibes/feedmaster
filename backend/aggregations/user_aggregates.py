# backend/user_aggregates.py

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, text, select, cast, Date, case
from sqlalchemy.sql.expression import literal_column

from .. import models, crud
from ..config import settings
from backend.enums import Timeframe

logger = logging.getLogger(__name__)


def _format_user_data_from_row(row: Any, extra_data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to format user data from a SQLAlchemy result row and merge extra data."""
    user_data = {
        "type": "user",
        "did": row.did,
        "handle": row.handle,
        "display_name": row.display_name,
        "avatar_url": str(row.avatar_url) if row.avatar_url else None,
    }
    user_data.update(extra_data)
    return user_data


async def _calculate_streaks_base_query(db: AsyncSession, feed_id: str):
    """
    A base helper that generates the core logic for identifying and calculating
    the length of all posting streaks for all users in a feed using efficient SQL.
    """
    # Step 1: Get distinct post dates for each user in the feed.
    # This is the most basic unit of our calculation.
    user_daily_posts = select(
        models.Post.author_did,
        cast(models.FeedPost.ingested_at, Date).label('post_date')
    ).distinct().join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id
    ).cte('user_daily_posts')

    # Step 2: Use the LAG window function to find the gap in days from the previous post.
    daily_gaps = select(
        user_daily_posts.c.author_did,
        user_daily_posts.c.post_date,
        (user_daily_posts.c.post_date - func.lag(user_daily_posts.c.post_date, 1, user_daily_posts.c.post_date).over(
            partition_by=user_daily_posts.c.author_did,
            order_by=user_daily_posts.c.post_date
        )).label('gap')
    ).cte('daily_gps')

    # Step 3: Identify the start of a new streak. A gap > 1 day means a new streak begins.
    # We create a 'streak_id' by doing a running sum of these "new streak" flags.
    streak_groups = select(
        daily_gaps.c.author_did,
        daily_gaps.c.post_date,
        func.sum(case((daily_gaps.c.gap > 1, 1), else_=0)).over(
            partition_by=daily_gaps.c.author_did,
            order_by=daily_gaps.c.post_date
        ).label('streak_id')
    ).cte('streak_groups')

    # Step 4: Calculate the length and last post date of each streak.
    streak_lengths = select(
        streak_groups.c.author_did,
        streak_groups.c.streak_id,
        func.count().label('streak_length'),
        func.max(streak_groups.c.post_date).label('last_post_date')
    ).group_by(
        streak_groups.c.author_did,
        streak_groups.c.streak_id
    ).cte('streak_lengths')

    return streak_lengths


async def calculate_longest_poster_streaks(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the all-time longest posting streaks for users in a feed.
    This shows the historical best for each user. The timeframe parameter is ignored.
    """
    logger.info(f"Calculating all-time longest poster streaks for feed '{feed_id}'...")
    streak_lengths_cte = await _calculate_streaks_base_query(db, feed_id)

    # From all calculated streaks, find the maximum streak length for each user.
    longest_streaks_subquery = select(
        streak_lengths_cte.c.author_did,
        func.max(streak_lengths_cte.c.streak_length).label('longest_streak')
    ).group_by(
        streak_lengths_cte.c.author_did
    ).subquery('longest_streaks_subquery')

    # Final query to join with user info and order by the longest streak.
    stmt = select(
        longest_streaks_subquery.c.author_did.label('did'),
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url,
        longest_streaks_subquery.c.longest_streak
    ).join(
        models.User, longest_streaks_subquery.c.author_did == models.User.did
    ).order_by(
        longest_streaks_subquery.c.longest_streak.desc()
    ).limit(50)

    result = await db.execute(stmt)
    streaks = [
        _format_user_data_from_row(row, {"longest_streak": row.longest_streak})
        for row in result.all() if row.longest_streak > 1
    ]
    return {"streaks": streaks}


async def calculate_active_poster_streaks(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the currently active posting streaks for users in a feed.
    A streak is "active" if the user posted today or yesterday. The timeframe parameter is ignored.
    """
    logger.info(f"Calculating currently active poster streaks for feed '{feed_id}'...")
    streak_lengths_cte = await _calculate_streaks_base_query(db, feed_id)

    # Final query to join with user info, but this time we filter for active streaks.
    stmt = select(
        streak_lengths_cte.c.author_did.label('did'),
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url,
        streak_lengths_cte.c.streak_length.label('current_streak')
    ).join(
        models.User, streak_lengths_cte.c.author_did == models.User.did
    ).where(
        # A streak is active if its last post was today or yesterday.
        streak_lengths_cte.c.last_post_date >= cast(func.now(), Date) - text("INTERVAL '1 day'")
    ).order_by(
        streak_lengths_cte.c.streak_length.desc()
    ).limit(50)

    result = await db.execute(stmt)
    streaks = [
        _format_user_data_from_row(row, {"longest_streak": row.current_streak})
        for row in result.all() if row.current_streak > 1
    ]
    return {"streaks": streaks}

async def calculate_first_time_posters(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Finds users who made their first post to a specific feed within the given timeframe.
    """
    logger.info(f"Calculating first-time posters for feed '{feed_id}', timeframe '{timeframe.value}'...")
    time_boundary = crud.get_time_boundary(timeframe.value)

    # Step 1: CTE to find the absolute first time each user was ingested into this feed.
    first_post_cte = select(
        models.Post.author_did,
        func.min(models.FeedPost.ingested_at).label('first_post_time')
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id
    ).group_by(
        models.Post.author_did
    ).cte('first_post_cte')

    # Step 2: Join this with the users table and filter for those whose first post is within our window.
    stmt = select(
        models.User,
        first_post_cte.c.first_post_time
    ).join(
        first_post_cte, models.User.did == first_post_cte.c.author_did
    ).where(
        first_post_cte.c.first_post_time >= time_boundary
    ).order_by(
        first_post_cte.c.first_post_time.desc()
    ).limit(50)

    result = await db.execute(stmt)
    new_posters = [
        _format_user_data_from_row(user, {"count": 1, "first_post_at": first_post_time.isoformat()})
        for user, first_post_time in result.all()
    ]

    return {"top": new_posters}

async def calculate_top_users(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates top users using drop-lowest weighted scoring: excludes each user's worst post,
    then applies weighted average × ln(post_count + 1) to balance quality and quantity.
    """
    logger.info(f"Calculating top users for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_boundary = crud.get_time_boundary(timeframe.value)

    # Get all posts with engagement scores for each user
    engagement_score = (
        (func.coalesce(models.Post.like_count, 0) * settings.LIKE_WEIGHT) +
        (func.coalesce(models.Post.repost_count, 0) * settings.REPOST_WEIGHT) +
        (func.coalesce(models.Post.reply_count, 0) * settings.REPLY_WEIGHT)
    )
    
    stmt = select(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url,
        engagement_score.label('post_score')
    ).join(
        models.Post, models.User.did == models.Post.author_did
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id
    )

    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_boundary)

    result = (await db.execute(stmt)).all()

    # Group posts by user and calculate drop-lowest weighted scores
    from collections import defaultdict
    import math
    
    user_posts = defaultdict(list)
    user_info = {}
    
    for row in result:
        user_posts[row.did].append(row.post_score)
        user_info[row.did] = {
            'did': row.did,
            'handle': row.handle,
            'display_name': row.display_name,
            'avatar_url': row.avatar_url
        }
    
    user_scores = []
    for did, scores in user_posts.items():
        original_count = len(scores)
        ln_bonus = math.log(original_count + 1)
        
        # Calculate score with all posts
        all_posts_avg = sum(scores) / len(scores) if scores else 0
        all_posts_score = all_posts_avg * ln_bonus
        
        # Calculate score without lowest post (if more than 1 post)
        if len(scores) > 1:
            scores_without_lowest = scores.copy()
            scores_without_lowest.remove(min(scores_without_lowest))
            without_lowest_avg = sum(scores_without_lowest) / len(scores_without_lowest)
            without_lowest_score = without_lowest_avg * ln_bonus
            
            # Use whichever score is higher
            weighted_score = max(all_posts_score, without_lowest_score)
        else:
            weighted_score = all_posts_score
        
        user_scores.append({
            **user_info[did],
            'weighted_score': weighted_score
        })
    
    # Sort by weighted score and take top 50
    user_scores.sort(key=lambda x: x['weighted_score'], reverse=True)
    top_users_data = [
        _format_user_data_from_row(type('Row', (), user), {"count": int(user['weighted_score'])})
        for user in user_scores[:50]
    ]
    
    logger.info(f"Calculated top users for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_users_data)} results.")
    return {"users": top_users_data}


async def calculate_top_posters_by_count(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top posters based on the number of posts they made within a given timeframe for a specific feed.
    This version uses a single, efficient query to join user data with post data.
    """
    logger.info(f"Calculating top posters by count for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    stmt = select(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url,
        func.count(func.distinct(models.Post.id)).label('post_count')
    ).join(
        models.Post, models.User.did == models.Post.author_did
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id
    )

    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)

    stmt = stmt.group_by(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url
    ).order_by(func.count(func.distinct(models.Post.id)).desc()).limit(50)

    result = (await db.execute(stmt)).all()

    top_posters_data = [
        _format_user_data_from_row(row, {"count": row.post_count})
        for row in result
    ]
    logger.info(f"Calculated top posters by count for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_posters_data)} results.")
    return {"posters": top_posters_data}


# --- UPDATED calculate_top_mentions function ---
async def calculate_top_mentions(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top mentioned users within a given timeframe for a specific feed
    by performing the aggregation directly in the database.
    Ensures each unique post contributes at most once to a mentioned user's count.
    This version uses a single, efficient query to join user data with post data.
    """
    logger.info(f"Calculating top mentions for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    # Alias for the unnested mention object from the JSONB column
    mention_element_alias = func.jsonb_array_elements(models.Post.mentions).alias("mention_element")

    # Expression to extract the 'did' from the unnested JSON object
    mention_did_expression = mention_element_alias.column.op('->>')('did')

    stmt = select(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url,
        func.count(func.distinct(models.Post.id)).label('mention_count')
    ).select_from(
        models.Post
    ).join(
        mention_element_alias,
        literal_column('TRUE') # Lateral join to unnest the array
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).join(
        models.User, models.User.did == mention_did_expression # Join with users table on the extracted DID
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.mentions.isnot(None),
        func.jsonb_array_length(models.Post.mentions) > 0,
        mention_did_expression.isnot(None)
    )

    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)

    stmt = stmt.group_by(
        models.User.did,
        models.User.handle,
        models.User.display_name,
        models.User.avatar_url
    ).order_by(
        func.count(func.distinct(models.Post.id)).desc()
    ).limit(50)

    result = (await db.execute(stmt)).all()

    top_mentions_data = [
        _format_user_data_from_row(row, {"count": row.mention_count})
        for row in result
    ]
    logger.info(f"Calculated top mentions for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_mentions_data)} results.")
    return {"mentions": top_mentions_data}