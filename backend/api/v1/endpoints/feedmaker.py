"""
Feedmaker dashboard endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.auth import require_feed_owner
from backend.models import (
    Feed, ApiKey, FeedApplication, ApplicationStatus,
    User, Post, UserAchievement, FeedPost, UserStats
)

router = APIRouter()

# Pydantic models
class FeedApplicationRequest(BaseModel):
    feed_id: str
    websocket_url: str
    description: Optional[str] = None

# Authentication & Profile
@router.get("/profile")
async def get_feedmaker_profile(
    api_key: ApiKey = Depends(require_feed_owner),
    db: AsyncSession = Depends(get_db)
):
    """Get feedmaker profile and owned feeds"""
    # Get owned feeds
    feeds_stmt = select(Feed).where(
        Feed.owner_did == api_key.owner_did,
        Feed.is_active == True
    )
    feeds_result = await db.execute(feeds_stmt)
    feeds = feeds_result.scalars().all()
    
    # Get feed stats
    feed_data = []
    for feed in feeds:
        # Post count
        post_count_stmt = select(func.count()).select_from(
            select(Post.id).join_from(Post, FeedPost).where(
                FeedPost.feed_id == feed.id
            ).subquery()
        )
        post_count = (await db.execute(post_count_stmt)).scalar() or 0
        
        # User count
        user_count_stmt = select(func.count(func.distinct(UserStats.user_did))).where(
            UserStats.feed_id == feed.id
        )
        user_count = (await db.execute(user_count_stmt)).scalar() or 0
        
        # Achievement count
        achievement_count_stmt = select(func.count()).where(
            UserAchievement.feed_id == feed.id
        )
        achievement_count = (await db.execute(achievement_count_stmt)).scalar() or 0
        
        feed_data.append({
            "id": feed.id,
            "name": feed.name,
            "tier": feed.tier,
            "post_count": post_count,
            "user_count": user_count,
            "achievement_count": achievement_count,
            "created_at": feed.created_at,
            "last_aggregated_at": feed.last_aggregated_at
        })
    
    return {
        "owner_did": api_key.owner_did,
        "feeds": feed_data,
        "total_feeds": len(feed_data)
    }

# Feed Analytics
@router.get("/feeds/{feed_id}/analytics")
async def get_feed_analytics(
    feed_id: str,
    days: int = Query(30, description="Number of days for analytics"),
    api_key: ApiKey = Depends(require_feed_owner),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed analytics for a specific feed"""
    # Verify ownership
    feed_stmt = select(Feed).where(
        Feed.id == feed_id,
        Feed.owner_did == api_key.owner_did
    )
    feed = (await db.execute(feed_stmt)).scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found or not owned")
    
    since_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Daily post counts
    daily_posts_stmt = select(
        func.date(FeedPost.ingested_at).label('date'),
        func.count().label('posts')
    ).where(
        FeedPost.feed_id == feed_id,
        FeedPost.ingested_at >= since_date
    ).group_by(
        func.date(FeedPost.ingested_at)
    ).order_by('date')
    
    daily_posts = await db.execute(daily_posts_stmt)
    daily_data = [{"date": str(row.date), "posts": row.posts} for row in daily_posts]
    
    # Top users
    top_users_stmt = select(
        UserStats.user_did,
        User.handle,
        User.display_name,
        UserStats.post_count,
        UserStats.total_likes_received
    ).join(
        User, UserStats.user_did == User.did
    ).where(
        UserStats.feed_id == feed_id
    ).order_by(
        UserStats.post_count.desc()
    ).limit(10)
    
    top_users_result = await db.execute(top_users_stmt)
    top_users = [
        {
            "did": row.user_did,
            "handle": row.handle,
            "display_name": row.display_name,
            "post_count": row.post_count,
            "likes_received": row.total_likes_received
        }
        for row in top_users_result
    ]
    
    return {
        "feed_id": feed_id,
        "feed_name": feed.name,
        "daily_posts": daily_data,
        "top_users": top_users,
        "period_days": days
    }

# Applications
@router.get("/applications")
async def get_my_applications(
    api_key: ApiKey = Depends(require_feed_owner),
    db: AsyncSession = Depends(get_db)
):
    """Get feedmaker's applications"""
    stmt = select(FeedApplication).where(
        FeedApplication.applicant_did == api_key.owner_did
    ).order_by(FeedApplication.applied_at.desc())
    
    result = await db.execute(stmt)
    applications = result.scalars().all()
    
    return {
        "applications": [
            {
                "id": app.id,
                "feed_id": app.feed_id,
                "websocket_url": app.websocket_url,
                "description": app.description,
                "status": app.status.value,
                "applied_at": app.applied_at,
                "reviewed_at": app.reviewed_at,
                "notes": app.notes
            }
            for app in applications
        ]
    }

@router.post("/applications")
async def submit_application(
    request: FeedApplicationRequest,
    api_key: ApiKey = Depends(require_feed_owner),
    db: AsyncSession = Depends(get_db)
):
    """Submit new feed application"""
    # Check if feed ID already exists
    existing_feed = await db.execute(select(Feed).where(Feed.id == request.feed_id))
    if existing_feed.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Feed ID already exists")
    
    # Check for pending application with same feed ID
    existing_app = await db.execute(
        select(FeedApplication).where(
            and_(
                FeedApplication.feed_id == request.feed_id,
                FeedApplication.status == ApplicationStatus.PENDING
            )
        )
    )
    if existing_app.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Pending application already exists for this feed ID")
    
    application = FeedApplication(
        applicant_did=api_key.owner_did,
        feed_id=request.feed_id,
        websocket_url=request.websocket_url,
        description=request.description,
        status=ApplicationStatus.PENDING
    )
    
    db.add(application)
    await db.commit()
    await db.refresh(application)
    
    return {
        "message": "Application submitted successfully",
        "application_id": application.id
    }

# Feed Settings (future paid features)
@router.get("/feeds/{feed_id}/settings")
async def get_feed_settings(
    feed_id: str,
    api_key: ApiKey = Depends(require_feed_owner),
    db: AsyncSession = Depends(get_db)
):
    """Get feed settings (placeholder for future features)"""
    # Verify ownership
    feed_stmt = select(Feed).where(
        Feed.id == feed_id,
        Feed.owner_did == api_key.owner_did
    )
    feed = (await db.execute(feed_stmt)).scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found or not owned")
    
    return {
        "feed_id": feed_id,
        "tier": feed.tier,
        "available_features": {
            "custom_achievements": feed.tier in ["silver", "gold", "platinum"],
            "custom_aggregates": feed.tier in ["gold", "platinum"],
            "advanced_analytics": feed.tier == "platinum"
        },
        "message": "Custom features coming soon!"
    }