import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, String, text, select
from sqlalchemy.orm import selectinload # Import selectinload
from sqlalchemy.dialects.postgresql import JSONB # Import JSONB type for direct JSONB operations

from .. import models, schemas, crud
from ..config import settings
from ..enums import Timeframe

logger = logging.getLogger(__name__)

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

async def _calculate_top_media_posts(
    db: AsyncSession,
    feed_id: str,
    timeframe: Timeframe,
    media_filter: Any,
    media_type: str
) -> Dict[str, Any]:
    """
    A generic helper to calculate top posts based on a specific media filter (e.g., for images or videos).
    """
    logger.info(f"Calculating top {media_type} for feed {feed_id}, timeframe {timeframe.value}...")
    
    calculated_engagement_score = (
        (func.coalesce(models.Post.like_count, 0) * settings.LIKE_WEIGHT) +
        (func.coalesce(models.Post.repost_count, 0) * settings.REPOST_WEIGHT) +
        (func.coalesce(models.Post.reply_count, 0) * settings.REPLY_WEIGHT)
    ).label("calculated_engagement_score")

    time_boundary = crud.get_time_boundary(timeframe.value)
    
    stmt = select(models.Post, calculated_engagement_score).join(models.FeedPost, models.Post.id == models.FeedPost.post_id).filter(
        models.FeedPost.feed_id == feed_id,
        media_filter
    )
    
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_boundary)
 
    stmt = stmt.order_by(
        calculated_engagement_score.desc(),
        models.Post.created_at.desc()
    ).limit(50)
    stmt = stmt.options(selectinload(models.Post.author))
    top_media_results = (await db.execute(stmt)).all()

    top_media_data = {"top": []}
    for p, engagement_score in top_media_results:
        # Start with the thumbnail from the DB
        thumbnail_url = str(p.thumbnail_url) if p.thumbnail_url else None

        # If it's a video and the thumbnail is missing, try to construct it on-the-fly.
        if media_type == "videos" and not thumbnail_url and p.has_video:
            embed = p.raw_record.get('embed', {})
            video_embed = None
            if embed.get('$type') == 'app.bsky.embed.video':
                video_embed = embed
            elif embed.get('$type') == 'app.bsky.embed.recordWithMedia' and embed.get('media', {}).get('$type') == 'app.bsky.embed.video':
                video_embed = embed.get('media')
            
            if video_embed:
                video_blob = video_embed.get('video')
                if video_blob and video_blob.get('ref', {}).get('$link'):
                    video_cid = video_blob['ref']['$link']
                    thumbnail_url = f"https://video.cdn.bsky.app/hls/{p.author_did}/{video_cid}/thumbnail.jpg"

        # Extract image URLs from raw_record for images
        images_data = []
        if p.has_image and p.raw_record.get('embed', {}).get('$type') == 'app.bsky.embed.images':
            embed_images = p.raw_record['embed'].get('images', [])
            for img in embed_images:
                if img.get('image', {}).get('ref', {}).get('$link'):
                    cid = img['image']['ref']['$link']
                    images_data.append({
                        "url": f"https://cdn.bsky.app/img/feed_thumbnail/plain/{p.author_did}/{cid}@jpeg",
                        "alt": img.get('alt', '')
                    })

        post_data = {
            "type": "post_card",
            "uri": p.uri,
            "cid": p.cid,
            "author_did": p.author_did,
            "text": p.text,
            "engagement_score": engagement_score,
            "like_count": p.like_count,
            "repost_count": p.repost_count,
            "reply_count": p.reply_count,
            "quote_count": p.quote_count,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "embeds": _serialize_datetime_objects(p.embeds),
            "has_image": p.has_image,
            "has_video": p.has_video,
            "images": images_data if images_data else None,
            "thumbnail_url": thumbnail_url, # Use the potentially newly constructed URL
            "aspect_ratio_width": p.aspect_ratio_width,
            "aspect_ratio_height": p.aspect_ratio_height,
            "link_url": str(p.link_url) if p.link_url else None,
            "link_title": p.link_title,
            "link_description": p.link_description,
            "quoted_post_uri": p.quoted_post_uri,
            "quoted_post_text": p.quoted_post_text,
            "quoted_post_author_handle": p.quoted_post_author_handle,
            "author": p.author.display_name if p.author and p.author.display_name else p.author.handle if p.author else "Unknown",
            "avatar": p.author.avatar_url if p.author and p.author.avatar_url else "",
            "post_url": f"https://bsky.app/profile/{p.author.handle}/post/{p.uri.split('/')[-1]}" if p.author else None
        }
        top_media_data["top"].append(post_data)

    logger.info(f"Top {media_type} for feed {feed_id}, timeframe {timeframe.value} calculated.")
    return _serialize_datetime_objects({"top": top_media_data["top"]})

async def calculate_top_posts(
    db: AsyncSession,
    feed_id: str,
    timeframe: Timeframe
) -> Dict[str, Any]:
    logger.info(f"Calculating top posts for feed {feed_id}, timeframe {timeframe.value}...")
    
    calculated_engagement_score = (
        (func.coalesce(models.Post.like_count, 0) * settings.LIKE_WEIGHT) +
        (func.coalesce(models.Post.repost_count, 0) * settings.REPOST_WEIGHT) +
        (func.coalesce(models.Post.reply_count, 0) * settings.REPLY_WEIGHT)
    ).label("calculated_engagement_score")

    time_boundary = crud.get_time_boundary(timeframe.value)
    
    stmt = select(models.Post, calculated_engagement_score).join(models.FeedPost, models.Post.id == models.FeedPost.post_id).filter(
        models.FeedPost.feed_id == feed_id,
        # models.Post.is_active_for_polling == True # Removed this filter
    )
    
    # FIX: Change from models.Post.created_at to models.FeedPost.ingested_at
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_boundary)

    stmt = stmt.order_by(
        calculated_engagement_score.desc(),
        models.Post.created_at.desc()
    ).limit(50)
    # Eagerly load the author relationship
    stmt = stmt.options(selectinload(models.Post.author))
    top_posts_results = (await db.execute(stmt)).all()

    top_posts_data = {
        "top": [
            {
                "type": "post_card",
                "uri": p.uri,
                "cid": p.cid,
                "author_did": p.author_did,
                "text": p.text,
                "engagement_score": engagement_score,
                "like_count": p.like_count,
                "repost_count": p.repost_count,
                "reply_count": p.reply_count,
                "quote_count": p.quote_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "embeds": _serialize_datetime_objects(p.embeds),
                "has_image": p.has_image,
                "has_video": p.has_video,
                "images": _serialize_datetime_objects(p.images), # NEW: Return the list of image objects
                "thumbnail_url": str(p.thumbnail_url) if p.thumbnail_url else None,
                "aspect_ratio_width": p.aspect_ratio_width,
                "aspect_ratio_height": p.aspect_ratio_height,
                "link_url": str(p.link_url) if p.link_url else None,
                "link_title": p.link_title,
                "link_description": p.link_description,
                "quoted_post_uri": p.quoted_post_uri,
                "quoted_post_text": p.quoted_post_text,
                "quoted_post_author_handle": p.quoted_post_author_handle,
                # Add the missing fields for TopPostCard
                "author": p.author.display_name if p.author and p.author.display_name else p.author.handle if p.author else "Unknown",
                "avatar": p.author.avatar_url if p.author and p.author.avatar_url else "",
                "post_url": f"https://bsky.app/profile/{p.author.handle}/post/{p.uri.split('/')[-1]}" if p.author else None
            } for p, engagement_score in top_posts_results
        ]
    }

    logger.info(f"Top posts for feed {feed_id}, timeframe {timeframe.value} calculated.")
    return _serialize_datetime_objects({"top": top_posts_data["top"]})

async def calculate_top_videos(
    db: AsyncSession,
    feed_id: str,
    timeframe: Timeframe
) -> Dict[str, Any]:
    # The ingestion worker already sets a `has_video` flag.
    # Querying this boolean is much more efficient and reliable than
    # parsing the JSONB `embeds` column on the fly.
    video_filter = (models.Post.has_video == True)
    return await _calculate_top_media_posts(db, feed_id, timeframe, video_filter, "videos")

async def calculate_top_images(
    db: AsyncSession,
    feed_id: str,
    timeframe: Timeframe
) -> Dict[str, Any]:
    # The ingestion worker already sets a `has_image` flag.
    # Querying this boolean is much more efficient and reliable than
    # parsing the JSONB `embeds` column on the fly.
    image_filter = (models.Post.has_image == True)
    return await _calculate_top_media_posts(db, feed_id, timeframe, image_filter, "images")