"""
Public endpoints that don't require authentication
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone

from backend.database import get_db
from backend.models import GeoHashtagMapping, FeedApplication, ApplicationStatus

router = APIRouter()

class FeedApplicationCreate(BaseModel):
    applicant_did: str
    applicant_handle: str
    applicant_name: str = None
    applicant_email: str = None
    feed_id: str
    description: str

@router.get("/geo-hashtags")
async def get_public_geo_hashtags(db: AsyncSession = Depends(get_db)):
    """Get all geo hashtag mappings for public display"""
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

@router.post("/applications")
async def submit_feed_application(
    application: FeedApplicationCreate,
    db: AsyncSession = Depends(get_db)
):
    """Submit a new feed application"""
    try:
        # Construct websocket URL from feed ID
        websocket_url = f"wss://api.graze.social/app/contrail?feed=at://did:plc:lptjvw6ut224kwrj7ub3sqbe/app.bsky.feed.generator/{application.feed_id}"
        
        # Create new application
        new_application = FeedApplication(
            applicant_did=application.applicant_did,
            applicant_handle=application.applicant_handle,
            feed_id=application.feed_id,
            websocket_url=websocket_url,
            description=application.description,
            status=ApplicationStatus.PENDING,
            applied_at=datetime.now(timezone.utc)
        )
        
        db.add(new_application)
        await db.commit()
        await db.refresh(new_application)
        
        return {
            "success": True,
            "message": "Application submitted successfully",
            "application_id": new_application.id
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to submit application: {str(e)}")

@router.get("/applications/{application_id}")
async def get_application_status(
    application_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get status of a specific application"""
    result = await db.execute(
        select(FeedApplication).where(FeedApplication.id == application_id)
    )
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    return {
        "id": application.id,
        "applicant_handle": application.applicant_handle,
        "feed_name": application.feed_name,
        "status": application.status,
        "applied_at": application.applied_at,
        "reviewed_at": application.reviewed_at,
        "notes": application.notes
    }