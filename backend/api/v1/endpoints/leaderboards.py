# backend/api/v1/endpoints/leaderboards.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend import crud, schemas
from backend.database import get_db

router = APIRouter()

@router.get("/global", response_model=List[schemas.LeaderboardEntry])
async def get_global_leaderboard(db: AsyncSession = Depends(get_db)):
    """
    Returns the global leaderboard, ranking users by a weighted achievement score.
    """
    leaderboard_data = await crud.get_global_leaderboard(db, limit=100)
    
    response = []
    for i, row in enumerate(leaderboard_data):
        user_model, achievement_score = row
        response.append(schemas.LeaderboardEntry(
            rank=i + 1,
            user=user_model,
            score=achievement_score or 0
        ))
    return response

@router.get("/feeds", response_model=List[schemas.FeedForLeaderboard])
async def list_feeds_with_leaderboards(db: AsyncSession = Depends(get_db)):
    """
    Returns a list of all feeds that have leaderboards (i.e., at least one
    achievement has been earned in them). This allows for dynamic discovery
    of available leaderboards.
    """
    feeds = await crud.get_feeds_with_leaderboards(db)
    return feeds

@router.get("/feed/{feed_id}", response_model=List[schemas.LeaderboardEntry])
async def get_leaderboard_for_feed(feed_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns the leaderboard for a specific feed, ranking users by a weighted
    achievement score based on rarity within that feed.
    """
    leaderboard_data = await crud.get_feed_leaderboard(db, feed_id=feed_id, limit=100)
    
    response = []
    for i, row in enumerate(leaderboard_data):
        user_model, achievement_score = row
        response.append(schemas.LeaderboardEntry(
            rank=i + 1,
            user=user_model,
            score=achievement_score or 0
        ))
    return response