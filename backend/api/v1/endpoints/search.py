# backend/api/v1/endpoints/search.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from backend import crud, schemas
from backend.database import get_db

router = APIRouter()

@router.get("", response_model=schemas.SearchResults)
async def search(
    q: str = Query(..., min_length=2, description="Search query for users and hashtags."),
    db: AsyncSession = Depends(get_db)
):
    """
    Searches for users by handle/display name and hashtags.
    The search is case-insensitive.
    """
    if not q:
        return schemas.SearchResults(users=[], hashtags=[])

    # Search both users and hashtags concurrently
    users = await crud.search_users(db=db, query=q, limit=10)
    hashtags = await crud.search_hashtags(db=db, query=q, limit=10)
    
    return schemas.SearchResults(users=users, hashtags=hashtags)
