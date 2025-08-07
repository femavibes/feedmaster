import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, text, select, distinct # Import text to use raw SQL fragments if needed
from sqlalchemy.dialects import postgresql # Import for postgresql specific functions if needed
import logging

from .. import models, crud
from ..enums import Timeframe

logger = logging.getLogger(__name__)

async def calculate_top_hashtags(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top hashtags based on their frequency within posts in a given timeframe,
    leveraging PostgreSQL's JSONB functions for efficient aggregation.
    Ensures each unique post's hashtag contributes only once per feed per timeframe.
    """
    logger.info(f"Calculating top hashtags for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    # Construct the query to perform aggregation directly in PostgreSQL
    # Using func.jsonb_array_elements_text to unnest the array
    # and func.lower for case-insensitive counting.
    # We join with FeedPost and filter by feed_id and ingested_at.    
    hashtag_elements = func.lower(func.jsonb_array_elements_text(models.Post.hashtags)).label('hashtag')
    stmt = select(
        hashtag_elements,
        func.count(distinct(models.Post.id)).label('count')
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id # JOIN with FeedPost
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.hashtags.isnot(None)
    )
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)
    stmt = stmt.group_by(
        hashtag_elements
    ).order_by(
        func.count(distinct(models.Post.id)).desc()
    ).limit(50)
    top_hashtags_results = (await db.execute(stmt)).all()

    top_hashtags_data = []
    for hashtag, count in top_hashtags_results:
        top_hashtags_data.append({
            "type": "hashtag",
            "hashtag": hashtag,
            "count": count
        })
    
    logger.info(f"Calculated top hashtags for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_hashtags_data)} results.")
    
    return {"hashtags": top_hashtags_data}