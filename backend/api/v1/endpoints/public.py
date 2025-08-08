"""
Public endpoints that don't require authentication
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database import get_db
from backend.models import GeoHashtagMapping

router = APIRouter()

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