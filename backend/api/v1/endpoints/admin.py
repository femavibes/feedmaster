"""
Master admin endpoints for platform management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from pydantic import BaseModel

from backend.database import get_db
from backend.auth import require_master_admin, generate_api_key
from backend.models import (
    Feed, ApiKey, ApiKeyType, FeedApplication, ApplicationStatus,
    User, Post, UserAchievement, FeedPost, UserStats
)

router = APIRouter()

# Pydantic models for requests/responses
class CreateFeedRequest(BaseModel):
    feed_id: str
    websocket_url: str
    owner_did: Optional[str] = None
    tier: str = "bronze"
    name: Optional[str] = None

class UpdateFeedRequest(BaseModel):
    owner_did: Optional[str] = None
    tier: Optional[str] = None
    is_active: Optional[bool] = None
    contrails_websocket_url: Optional[str] = None

class CreateApiKeyRequest(BaseModel):
    owner_did: str
    expires_days: Optional[int] = None
    feed_permissions: Optional[List[dict]] = None

class UpdateApiKeyPermissionsRequest(BaseModel):
    feed_permissions: List[dict]

class ReviewApplicationRequest(BaseModel):
    status: str  # "approved" or "rejected"
    tier: str = "bronze"
    notes: Optional[str] = None

# Feed Management
@router.get("/feeds")
async def list_feeds(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """List all feeds with owner and stats"""
    stmt = select(Feed).order_by(Feed.created_at.desc())
    result = await db.execute(stmt)
    feeds = result.scalars().all()
    
    # Get comprehensive feed stats
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
        
        # Recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_posts_stmt = select(func.count()).select_from(
            select(Post.id).join_from(Post, FeedPost).where(
                FeedPost.feed_id == feed.id,
                FeedPost.ingested_at >= week_ago
            ).subquery()
        )
        recent_posts = (await db.execute(recent_posts_stmt)).scalar() or 0
        
        feed_data.append({
            "id": feed.id,
            "name": feed.name,
            "owner_did": feed.owner_did,
            "tier": feed.tier,
            "is_active": feed.is_active,
            "contrails_websocket_url": feed.contrails_websocket_url,
            "post_count": post_count,
            "user_count": user_count,
            "achievement_count": achievement_count,
            "recent_posts_7d": recent_posts,
            "created_at": feed.created_at,
            "updated_at": feed.updated_at
        })
    
    return {"feeds": feed_data}

@router.post("/feeds")
async def create_feed(
    request: CreateFeedRequest,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Create a new feed"""
    # Check if feed already exists
    existing = await db.execute(select(Feed).where(Feed.id == request.feed_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Feed already exists")
    
    feed = Feed(
        id=request.feed_id,
        name=request.name or f"Feed {request.feed_id}",
        contrails_websocket_url=request.websocket_url,
        owner_did=request.owner_did,
        tier=request.tier,
        is_active=True
    )
    
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    
    return {"message": "Feed created", "feed": {"id": feed.id, "tier": feed.tier}}

@router.put("/feeds/{feed_id}")
async def update_feed(
    feed_id: str,
    request: UpdateFeedRequest,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Update feed settings"""
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()
    
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    if request.owner_did is not None:
        feed.owner_did = request.owner_did
    if request.tier is not None:
        feed.tier = request.tier
    if request.is_active is not None:
        feed.is_active = request.is_active
    if request.contrails_websocket_url is not None:
        feed.contrails_websocket_url = request.contrails_websocket_url
    
    feed.updated_at = datetime.now(timezone.utc)
    await db.commit()
    
    return {"message": "Feed updated"}

@router.delete("/feeds/{feed_id}")
async def delete_feed(
    feed_id: str,
    hard_delete: bool = Query(False, description="Permanently delete vs soft delete"),
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Delete or deactivate a feed"""
    stmt = select(Feed).where(Feed.id == feed_id)
    result = await db.execute(stmt)
    feed = result.scalar_one_or_none()
    
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    
    if hard_delete:
        # Hard delete: Remove all related data
        from sqlalchemy import delete
        
        # Delete feed posts (join table)
        await db.execute(delete(FeedPost).where(FeedPost.feed_id == feed_id))
        
        # Delete user achievements for this feed
        await db.execute(delete(UserAchievement).where(UserAchievement.feed_id == feed_id))
        
        # Delete user stats for this feed
        await db.execute(delete(UserStats).where(UserStats.feed_id == feed_id))
        
        # Delete aggregates for this feed
        from backend.models import Aggregate
        await db.execute(delete(Aggregate).where(Aggregate.feed_id == feed_id))
        
        # Finally delete the feed itself
        await db.delete(feed)
        message = "Feed permanently deleted"
    else:
        feed.is_active = False
        message = "Feed deactivated"
    
    await db.commit()
    return {"message": message}

# API Key Management
@router.get("/api-keys")
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """List all API keys"""
    stmt = select(ApiKey).order_by(ApiKey.created_at.desc())
    result = await db.execute(stmt)
    keys = result.scalars().all()
    
    return {
        "api_keys": [
            {
                "id": key.id,
                "key_type": key.key_type.value,
                "owner_did": key.owner_did,
                "expires_at": key.expires_at,
                "is_active": key.is_active,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at
            }
            for key in keys
        ]
    }

@router.post("/api-keys")
async def create_api_key(
    request: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Generate a new API key for a feed owner"""
    raw_key, key_hash = generate_api_key()
    
    expires_at = None
    if request.expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_days)
    
    api_key = ApiKey(
        key_hash=key_hash,
        key_type=ApiKeyType.FEED_OWNER,
        owner_did=request.owner_did,
        expires_at=expires_at,
        is_active=True
    )
    
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)
    
    # Add feed permissions if provided
    if request.feed_permissions:
        from backend.models import FeedPermission
        for perm in request.feed_permissions:
            feed_perm = FeedPermission(
                api_key_id=api_key.id,
                feed_id=perm['feed_id'],
                permission_level=perm['permission_level']
            )
            db.add(feed_perm)
        await db.commit()
    
    return {
        "message": "API key created",
        "api_key": raw_key,  # Only returned once!
        "expires_at": expires_at
    }

@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Revoke an API key"""
    stmt = select(ApiKey).where(ApiKey.id == key_id)
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.is_active = False
    await db.commit()
    
    return {"message": "API key revoked"}

@router.get("/api-keys/{key_id}/permissions")
async def get_api_key_permissions(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get feed permissions for an API key"""
    from backend.models import FeedPermission
    
    stmt = select(FeedPermission).where(FeedPermission.api_key_id == key_id)
    result = await db.execute(stmt)
    permissions = result.scalars().all()
    
    return {
        "permissions": [
            {
                "feed_id": perm.feed_id,
                "permission_level": perm.permission_level,
                "is_active": getattr(perm, 'is_active', True),
                "created_at": perm.created_at
            }
            for perm in permissions
        ]
    }

@router.put("/api-keys/{key_id}/permissions")
async def update_api_key_permissions(
    key_id: int,
    request: UpdateApiKeyPermissionsRequest,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Update feed permissions for an API key"""
    from backend.models import FeedPermission
    from sqlalchemy import delete
    
    # Verify API key exists
    api_key_stmt = select(ApiKey).where(ApiKey.id == key_id)
    api_key = (await db.execute(api_key_stmt)).scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Delete existing permissions
    delete_stmt = delete(FeedPermission).where(FeedPermission.api_key_id == key_id)
    await db.execute(delete_stmt)
    
    # Add new permissions
    for perm in request.feed_permissions:
        feed_perm = FeedPermission(
            api_key_id=key_id,
            feed_id=perm['feed_id'],
            permission_level=perm['permission_level']
        )
        db.add(feed_perm)
    
    await db.commit()
    
    return {"message": "Permissions updated successfully"}

@router.put("/api-keys/{key_id}/permissions/{feed_id}")
async def update_single_permission(
    key_id: int,
    feed_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Update a single feed permission"""
    from backend.models import FeedPermission
    
    stmt = select(FeedPermission).where(
        FeedPermission.api_key_id == key_id,
        FeedPermission.feed_id == feed_id
    )
    permission = (await db.execute(stmt)).scalar_one_or_none()
    
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    if 'permission_level' in request:
        permission.permission_level = request['permission_level']
    if 'is_active' in request:
        permission.is_active = request['is_active']
    
    await db.commit()
    return {"message": "Permission updated"}

@router.delete("/api-keys/{key_id}/permissions/{feed_id}")
async def delete_single_permission(
    key_id: int,
    feed_id: str,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Delete a single feed permission"""
    from backend.models import FeedPermission
    from sqlalchemy import delete
    
    stmt = delete(FeedPermission).where(
        FeedPermission.api_key_id == key_id,
        FeedPermission.feed_id == feed_id
    )
    result = await db.execute(stmt)
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    return {"message": "Permission deleted"}

@router.post("/api-keys/{key_id}/permissions")
async def add_single_permission(
    key_id: int,
    request: dict,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Add a single feed permission"""
    from backend.models import FeedPermission
    
    # Check if permission already exists
    existing_stmt = select(FeedPermission).where(
        FeedPermission.api_key_id == key_id,
        FeedPermission.feed_id == request['feed_id']
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    permission = FeedPermission(
        api_key_id=key_id,
        feed_id=request['feed_id'],
        permission_level=request['permission_level'],
        is_active=True
    )
    
    db.add(permission)
    await db.commit()
    
    return {"message": "Permission added"}

# Application Management
@router.get("/applications")
async def list_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """List feed applications"""
    stmt = select(FeedApplication).order_by(FeedApplication.applied_at.desc())
    
    if status:
        stmt = stmt.where(FeedApplication.status == ApplicationStatus(status))
    
    result = await db.execute(stmt)
    applications = result.scalars().all()
    
    return {
        "applications": [
            {
                "id": app.id,
                "applicant_did": app.applicant_did,
                "applicant_handle": app.applicant_handle,
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

@router.put("/applications/{app_id}")
async def review_application(
    app_id: int,
    request: ReviewApplicationRequest,
    db: AsyncSession = Depends(get_db),
    admin_key: ApiKey = Depends(require_master_admin)
):
    """Approve or reject a feed application"""
    stmt = select(FeedApplication).where(FeedApplication.id == app_id)
    result = await db.execute(stmt)
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    application.status = ApplicationStatus(request.status)
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewed_by = admin_key.owner_did or "master_admin"
    application.notes = request.notes
    
    # If approved, create the feed
    if request.status == "approved":
        feed = Feed(
            id=application.feed_id,
            name=f"Feed {application.feed_id}",
            contrails_websocket_url=application.websocket_url,
            owner_did=application.applicant_did,
            tier=request.tier,
            is_active=True
        )
        db.add(feed)
    
    await db.commit()
    
    return {"message": f"Application {request.status}"}

# Platform Stats
@router.get("/stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get platform statistics"""
    # Count feeds by tier
    feeds_stmt = select(Feed.tier, func.count()).group_by(Feed.tier)
    feeds_result = await db.execute(feeds_stmt)
    feeds_by_tier = dict(feeds_result.all())
    
    # Total counts
    total_feeds = sum(feeds_by_tier.values())
    total_users = (await db.execute(select(func.count()).select_from(User))).scalar()
    total_posts = (await db.execute(select(func.count()).select_from(Post))).scalar()
    total_achievements = (await db.execute(select(func.count()).select_from(UserAchievement))).scalar()
    
    # Pending applications
    pending_apps = (await db.execute(
        select(func.count()).select_from(FeedApplication).where(
            FeedApplication.status == ApplicationStatus.PENDING
        )
    )).scalar()
    
    return {
        "feeds": {
            "total": total_feeds,
            "by_tier": feeds_by_tier
        },
        "users": total_users,
        "posts": total_posts,
        "achievements": total_achievements,
        "pending_applications": pending_apps
    }

# User Management
@router.get("/users")
async def list_users(
    limit: int = Query(50, description="Number of users to return"),
    search: Optional[str] = Query(None, description="Search by handle or DID"),
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """List platform users with stats"""
    stmt = select(User).order_by(User.posts_count.desc()).limit(limit)
    
    if search:
        stmt = stmt.where(
            User.handle.ilike(f"%{search}%") | 
            User.did.ilike(f"%{search}%") |
            User.display_name.ilike(f"%{search}%")
        )
    
    result = await db.execute(stmt)
    users = result.scalars().all()
    
    # Get achievement counts for each user
    user_data = []
    for user in users:
        achievement_count_stmt = select(func.count()).where(
            UserAchievement.user_did == user.did
        )
        achievement_count = (await db.execute(achievement_count_stmt)).scalar() or 0
        
        user_data.append({
            "did": user.did,
            "handle": user.handle,
            "display_name": user.display_name,
            "posts_count": user.posts_count,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "achievement_count": achievement_count,
            "is_prominent": user.is_prominent,
            "created_at": user.created_at,
            "last_updated": user.last_updated
        })
    
    return {"users": user_data}

@router.get("/users/{user_did}/details")
async def get_user_details(
    user_did: str,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get detailed user information"""
    # Get user
    user_stmt = select(User).where(User.did == user_did)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user achievements
    achievements_stmt = select(UserAchievement).where(
        UserAchievement.user_did == user_did
    ).order_by(UserAchievement.earned_at.desc()).limit(20)
    achievements = (await db.execute(achievements_stmt)).scalars().all()
    
    # Get user stats per feed
    stats_stmt = select(UserStats).where(UserStats.user_did == user_did)
    stats = (await db.execute(stats_stmt)).scalars().all()
    
    return {
        "user": {
            "did": user.did,
            "handle": user.handle,
            "display_name": user.display_name,
            "description": user.description,
            "posts_count": user.posts_count,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "is_prominent": user.is_prominent,
            "created_at": user.created_at,
            "last_updated": user.last_updated
        },
        "recent_achievements": [
            {
                "achievement_id": ach.achievement_id,
                "feed_id": ach.feed_id,
                "earned_at": ach.earned_at,
                "context": ach.context
            }
            for ach in achievements
        ],
        "feed_stats": [
            {
                "feed_id": stat.feed_id,
                "post_count": stat.post_count,
                "total_likes_received": stat.total_likes_received,
                "max_post_engagement": stat.max_post_engagement,
                "first_post_at": stat.first_post_at,
                "latest_post_at": stat.latest_post_at
            }
            for stat in stats
        ]
    }

@router.put("/users/{user_did}/prominent")
async def toggle_user_prominent(
    user_did: str,
    prominent: bool = Query(..., description="Set prominent status"),
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Toggle user prominent status"""
    user_stmt = select(User).where(User.did == user_did)
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_prominent = prominent
    await db.commit()
    
    return {"message": f"User {'marked as prominent' if prominent else 'removed from prominent'}"}

@router.delete("/users/{user_did}/achievements")
async def clear_user_achievements(
    user_did: str,
    feed_id: Optional[str] = Query(None, description="Clear achievements for specific feed only"),
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Clear user achievements"""
    from sqlalchemy import delete
    
    if feed_id:
        stmt = delete(UserAchievement).where(
            UserAchievement.user_did == user_did,
            UserAchievement.feed_id == feed_id
        )
        message = f"Achievements cleared for user in feed {feed_id}"
    else:
        stmt = delete(UserAchievement).where(UserAchievement.user_did == user_did)
        message = "All achievements cleared for user"
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {"message": message, "deleted_count": result.rowcount}

# System Health
@router.get("/health")
async def get_system_health(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get system health metrics"""
    now = datetime.now(timezone.utc)
    
    # Recent activity
    hour_ago = now - timedelta(hours=1)
    day_ago = now - timedelta(days=1)
    
    posts_last_hour = (await db.execute(
        select(func.count()).select_from(Post).where(Post.ingested_at >= hour_ago)
    )).scalar()
    
    posts_last_day = (await db.execute(
        select(func.count()).select_from(Post).where(Post.ingested_at >= day_ago)
    )).scalar()
    
    achievements_last_day = (await db.execute(
        select(func.count()).select_from(UserAchievement).where(UserAchievement.earned_at >= day_ago)
    )).scalar()
    
    # Feed activity
    active_feeds = (await db.execute(
        select(func.count()).select_from(Feed).where(Feed.is_active == True)
    )).scalar()
    
    return {
        "system_status": "healthy",
        "timestamp": now,
        "activity": {
            "posts_last_hour": posts_last_hour,
            "posts_last_day": posts_last_day,
            "achievements_last_day": achievements_last_day
        },
        "feeds": {
            "active_count": active_feeds
        }
    }

# Configuration Management
from backend.models import GeoHashtagMapping, NewsDomain

@router.get("/config/geo-hashtags")
async def get_geo_hashtags(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get all geo hashtag mappings"""
    result = await db.execute(select(GeoHashtagMapping))
    mappings = result.scalars().all()
    return {
        hashtag.hashtag: {
            "city": hashtag.city,
            "region": hashtag.region,
            "country": hashtag.country
        }
        for hashtag in mappings
    }

@router.post("/config/geo-hashtags")
async def add_geo_hashtag(
    hashtag: str,
    city: Optional[str] = None,
    region: Optional[str] = None,
    country: str = None,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Add or update geo hashtag mapping"""
    mapping = GeoHashtagMapping(
        hashtag=hashtag.lower(),
        city=city,
        region=region,
        country=country
    )
    await db.merge(mapping)
    await db.commit()
    return {"message": "Geo hashtag mapping saved"}

@router.delete("/config/geo-hashtags/{hashtag}")
async def delete_geo_hashtag(
    hashtag: str,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Delete geo hashtag mapping"""
    result = await db.execute(select(GeoHashtagMapping).where(GeoHashtagMapping.hashtag == hashtag))
    mapping = result.scalar_one_or_none()
    if mapping:
        await db.delete(mapping)
        await db.commit()
    return {"message": "Geo hashtag mapping deleted"}

@router.get("/config/news-domains")
async def get_news_domains(
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Get all news domains"""
    result = await db.execute(select(NewsDomain).order_by(NewsDomain.domain))
    domains = result.scalars().all()
    return [domain.domain for domain in domains]

class AddDomainRequest(BaseModel):
    domain: str

@router.post("/config/news-domains")
async def add_news_domain(
    request: AddDomainRequest,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Add news domain"""
    domain_obj = NewsDomain(domain=request.domain.lower())
    await db.merge(domain_obj)
    await db.commit()
    return {"message": "News domain added"}

@router.delete("/config/news-domains/{domain}")
async def delete_news_domain(
    domain: str,
    db: AsyncSession = Depends(get_db),
    _: ApiKey = Depends(require_master_admin)
):
    """Delete news domain"""
    result = await db.execute(select(NewsDomain).where(NewsDomain.domain == domain))
    domain_obj = result.scalar_one_or_none()
    if domain_obj:
        await db.delete(domain_obj)
        await db.commit()
    return {"message": "News domain deleted"}