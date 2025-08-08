import json
import os
from typing import List, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
import json

from backend import crud, schemas
from backend.schemas import AggregateData
from backend.database import get_db
from backend.enums import Timeframe

router = APIRouter()

# --- Pydantic Models for API Response ---
# These models ensure the API response is structured correctly and documented automatically.

class Feed(BaseModel):
    id: str
    name: str
    icon: str
    avatar_url: Optional[str] = None
    like_count: Optional[int] = 0
    bluesky_description: Optional[str] = None

class FeedListResponse(BaseModel):
    feeds: List[Feed]

# A simpler response model for the main feed view
class SimplePostListResponse(BaseModel):
    posts: List[schemas.Post]

# --- API Endpoint ---

@router.get(
    "/",
    response_model=FeedListResponse,
    summary="Get List of Available Feeds",
    description="Reads the configured feeds from the database and returns them in a format suitable for the frontend.",
)
async def get_available_feeds(db: AsyncSession = Depends(get_db)):
    """
    This endpoint provides the list of all feeds the application is configured to monitor.
    It reads from the database and derives an 'icon' for the frontend from the
    first letter of the feed's name.
    """
    db_feeds = await crud.get_feeds(db)
    # Filter to only active feeds for public API
    active_feeds = [feed for feed in db_feeds if feed.is_active]
    # Sort feeds by order field, fallback to id if order is None
    sorted_feeds = sorted(active_feeds, key=lambda f: (f.order or 999, f.id))
    formatted_feeds = [
        {
            "id": feed.id, 
            "name": feed.name, 
            "icon": feed.avatar_url or feed.name[0].upper(),
            "avatar_url": feed.avatar_url,
            "like_count": feed.like_count or 0,
            "bluesky_description": feed.bluesky_description
        }
        for feed in sorted_feeds
    ]
    
    response_data = {"feeds": formatted_feeds}
    
    return response_data


@router.get(
    "/{feed_id}/posts",
    response_model=SimplePostListResponse,
    summary="Get Recent Posts for a Feed",
    description="Retrieves the most recent posts ingested for a specific feed, with author details.",
)
async def get_recent_posts_for_feed(
    feed_id: str,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    posts = await crud.get_posts_for_feed(db, feed_id=feed_id, limit=limit, skip=skip)
    return {"posts": posts}


@router.get(
    "/{feed_id}/aggregates",
    response_model=schemas.Aggregate,
    summary="Get a Specific Aggregate for a Feed",
    description="Retrieves a pre-calculated aggregate (e.g., top hashtags, top users) for a specific feed and timeframe.",
)
async def get_feed_aggregate(
    feed_id: str,
    agg_name: str = Query(..., description="Name of the aggregate to retrieve"),
    timeframe: str = Query("1d", description="Timeframe for aggregates (1h, 6h, 1d, 7d, 30d, allTime)"),
    db: AsyncSession = Depends(get_db),
):
    aggregate = await crud.get_aggregate(db, feed_id=feed_id, agg_name=agg_name, timeframe=timeframe)
    if not aggregate:
        raise HTTPException(status_code=404, detail=f"Aggregate '{agg_name}' for feed '{feed_id}' with timeframe '{timeframe}' not found.")

    

    
        aggregate.data_json = schemas.AggregateData(**aggregate.data_json) # Use the explicitly imported AggregateData

    return aggregate

@router.get(
    "/{feed_id}/posts/by_author/{author_did}",
    response_model=SimplePostListResponse,
    summary="Get Posts by Author in Feed",
    description="Retrieves posts by a specific author within a feed.",
)
async def get_posts_by_author_in_feed(
    feed_id: str,
    author_did: str,
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    posts = await crud.get_posts_by_author_in_feed(db, feed_id=feed_id, author_did=author_did, limit=limit, skip=skip)
    return {"posts": posts}

@router.get(
    "/{feed_id}/posts/by_hashtag/{hashtag}",
    response_model=SimplePostListResponse,
    summary="Get Posts by Hashtag in Feed",
    description="Retrieves posts containing a specific hashtag within a feed.",
)
async def get_posts_by_hashtag_in_feed(
    feed_id: str,
    hashtag: str,
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    posts = await crud.get_posts_by_hashtag_in_feed(db, feed_id=feed_id, hashtag=hashtag, limit=limit, skip=skip)
    return {"posts": posts}

@router.get(
    "/{feed_id}/hashtag/{hashtag}/analytics",
    summary="Get Hashtag Analytics",
    description="Retrieves analytics and insights for a specific hashtag within a feed.",
)
async def get_hashtag_analytics(
    feed_id: str,
    hashtag: str,
    db: AsyncSession = Depends(get_db),
):
    analytics = await crud.get_hashtag_analytics(db, feed_id=feed_id, hashtag=hashtag)
    return analytics

@router.get(
    "/{feed_id}/aggregates_all",
    response_model=Dict[str, Any],
    summary="Get All Aggregates for a Feed and Timeframe",
    description="Retrieves all available aggregates for a specific feed and timeframe in a single call.",
)
async def get_all_feed_aggregates(
    feed_id: str,
    timeframe: str = Query("1d", description="Timeframe for aggregates (1h, 6h, 1d, 7d, 30d, allTime)"),
    db: AsyncSession = Depends(get_db),
):
    # List of all aggregates to fetch
    aggregate_names = [
        "top_posts",
        "top_hashtags",
        "top_users",
        "top_posters_by_count", # Use this for Top Posters
        "top_mentions",
        "top_domains",
        "top_countries",
        "top_regions",
        "top_cities",
        "top_videos",
        "top_images",
        "top_links",
        "top_link_cards",
        "top_news_link_cards",
        "longest_poster_streaks",
        "active_poster_streaks",
        "first_time_posters",
    ]

    response_data = {}

    for agg_name in aggregate_names:
        # For streaks, always use allTime regardless of requested timeframe
        agg_timeframe = "allTime" if "streak" in agg_name else timeframe
        aggregate = await crud.get_aggregate(db, feed_id=feed_id, agg_name=agg_name, timeframe=agg_timeframe)
        if aggregate and aggregate.data_json:
            # Apply schema validation like the individual endpoint does
            validated_data = schemas.AggregateData(**aggregate.data_json)
            
            # Explicitly extract the nested list for each aggregate type
            if agg_name == "top_hashtags":
                response_data[agg_name] = validated_data.hashtags or []
            elif agg_name == "top_posters_by_count":
                response_data[agg_name] = validated_data.posters or []
            elif agg_name == "top_links":
                response_data[agg_name] = validated_data.links or []
            elif agg_name == "longest_poster_streaks" or agg_name == "active_poster_streaks":
                response_data[agg_name] = validated_data.streaks or []
            elif agg_name == "first_time_posters":
                response_data[agg_name] = [item.model_dump() for item in (validated_data.top or [])] if validated_data.top else []
            elif agg_name == "top_news_link_cards":
                response_data[agg_name] = [item.model_dump() for item in (validated_data.top or [])] if validated_data.top else []
            elif agg_name == "top_link_cards":
                response_data[agg_name] = [item.model_dump() for item in (validated_data.top or [])] if validated_data.top else []
            elif agg_name == "top_users":
                response_data[agg_name] = validated_data.users or []
            elif agg_name == "top_mentions":
                response_data[agg_name] = validated_data.mentions or []
            elif agg_name == "top_domains":
                response_data[agg_name] = [item.model_dump() for item in (validated_data.domains or [])] if validated_data.domains else []
            # For other 'top' aggregates, assume they are directly under 'top' key or are flat
            elif agg_name in ["top_posts", "top_countries", "top_regions", "top_cities", "top_videos",
                            "top_images"]:
                response_data[agg_name] = [item.model_dump() for item in (validated_data.top or [])] if validated_data.top else []
            else:
                # Fallback for any other aggregates, just pass the data_json as is
                response_data[agg_name] = aggregate.data_json

    return response_data
