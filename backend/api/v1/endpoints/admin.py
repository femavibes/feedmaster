# backend/api/v1/endpoints/admin.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text, cast, Float
from sqlalchemy.exc import IntegrityError
from typing import List, Dict, Callable, Awaitable, Any 
from backend import crud, schemas, models
from backend.database import get_db
import logging

# Import the aggregation functions to build a dispatcher
from backend.aggregations import (
    content_aggregates,
    user_aggregates,
    hashtag_aggregates,
    link_aggregates,
    geo_aggregates
)
from backend.enums import Timeframe

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Aggregation Function Dispatcher ---
# This maps the string names of aggregates to the actual calculation functions.
AGGREGATION_FUNCTIONS: Dict[str, Callable[[AsyncSession, str, Timeframe], Awaitable[Dict[str, Any]]]] = {
    "top_posts": content_aggregates.calculate_top_posts,
    "top_images": content_aggregates.calculate_top_images,
    "top_videos": content_aggregates.calculate_top_videos,
    "top_hashtags": hashtag_aggregates.calculate_top_hashtags,
    "top_users": user_aggregates.calculate_top_users,
    "top_posters_by_count": user_aggregates.calculate_top_posters_by_count,
    "top_mentions": user_aggregates.calculate_top_mentions,
    "longest_poster_streaks": user_aggregates.calculate_longest_poster_streaks,
    "active_poster_streaks": user_aggregates.calculate_active_poster_streaks,
    "first_time_posters": user_aggregates.calculate_first_time_posters,
    "top_links": link_aggregates.calculate_top_links,
    "top_domains": link_aggregates.calculate_top_domains,
    "top_link_cards": link_aggregates.calculate_top_cards,
    "top_news_link_cards": link_aggregates.calculate_top_news_cards,
    "top_cities": geo_aggregates.calculate_top_cities,
    "top_regions": geo_aggregates.calculate_top_regions,
    "top_countries": geo_aggregates.calculate_top_countries,
}

# It's good practice to protect admin routes. This is a placeholder for
# a real authentication dependency you would create.
async def get_admin_user():
    """
    Placeholder for a real admin authentication check. In a production app,
    this would verify an admin API key or a JWT token with an admin role.
    """
    pass

@router.get("/aggregates/definitions", response_model=List[str], dependencies=[Depends(get_admin_user)])
async def list_aggregate_definitions():
    """
    Returns a list of all implemented aggregate function names that can be recalculated.
    """
    # This provides a dynamic way for the frontend to know what aggregates are available.
    return sorted(list(AGGREGATION_FUNCTIONS.keys()))


async def run_and_store_aggregation(db: AsyncSession, feed_id: str, agg_name: str, timeframe: Timeframe):
    """
    A helper function to run a specific aggregation and store the result,
    using the same logic as the aggregator worker.
    """
    logger.info(f"Recalculating aggregate '{agg_name}' for feed '{feed_id}' with timeframe '{timeframe.value}'")

    # Use the dispatcher to find the correct calculation function
    agg_func = AGGREGATION_FUNCTIONS.get(agg_name)
    if not agg_func:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Aggregation '{agg_name}' is not implemented for recalculation.")

    # Run the calculation
    data_to_store = await agg_func(db, feed_id, timeframe)

    # Create the schema and store the result
    agg_schema = schemas.AggregateCreate(
        feed_id=feed_id, agg_name=agg_name, timeframe=timeframe.value, data_json=data_to_store
    )
    await crud.create_or_update_aggregate(db, agg_schema)
    logger.info(f"Successfully recalculated and stored aggregate '{agg_name}' for feed '{feed_id}'")
    
# Note: The prefix for this router is set in main.py.
# To keep things organized, we'll add sub-paths here.
@router.post("/aggregates/recalculate/{feed_id}/{agg_name}/{timeframe}", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(get_admin_user)])
async def trigger_recalculation(
    feed_id: str, agg_name: str, timeframe: Timeframe, db: AsyncSession = Depends(get_db)
):
    """Triggers an immediate recalculation of a specific aggregate."""
    await run_and_store_aggregation(db, feed_id, agg_name, timeframe)
    return {"message": f"Recalculation successful for {agg_name} on feed {feed_id}."}


# --- NEW ACHIEVEMENT ADMIN ENDPOINTS ---

@router.get("/achievements", response_model=List[schemas.AchievementAdminDetail], dependencies=[Depends(get_admin_user)])
async def list_all_achievements(db: AsyncSession = Depends(get_db)):
    """
    Lists all achievements in the system, both active and inactive,
    sorted logically by series and tier for clear presentation.
    """
    stmt = (
        select(models.Achievement)
        .order_by(
            models.Achievement.series_key,
            # This robustly sorts tiers by their numeric requirement,
            # e.g., 10 posts, then 50, then 250.
            cast(models.Achievement.criteria['value'], Float)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/achievements", response_model=schemas.AchievementAdminDetail, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_admin_user)])
async def create_new_achievement(
    achievement_create: schemas.AchievementCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new achievement, such as a new tier for an existing series.
    The `key` must be unique across all achievements.
    """
    try:
        new_achievement = await crud.create_achievement(db, achievement_create)
        return new_achievement
    except IntegrityError as e:
        # This catches the specific error from our CRUD function for duplicate keys
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An achievement with that key already exists. {e}"
        )
    except Exception as e:
        logger.error(f"Could not create achievement: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating the achievement."
        )

@router.put("/achievements/{achievement_id}", response_model=schemas.AchievementAdminDetail, dependencies=[Depends(get_admin_user)])
async def update_achievement(
    achievement_id: int,
    achievement_update: schemas.AchievementUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an achievement's properties, including its name, description,
    icon, and the editable values within its criteria.
    """
    achievement = await db.get(models.Achievement, achievement_id)
    if not achievement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")

    update_data = achievement_update.model_dump(exclude_unset=True)

    # The criteria is a JSON field, so we handle it carefully by merging changes.
    if 'criteria' in update_data and achievement.criteria and update_data['criteria']:
        updated_criteria = achievement.criteria.copy()
        updated_criteria.update(update_data['criteria'])
        update_data['criteria'] = updated_criteria

    stmt = (
        update(models.Achievement)
        .where(models.Achievement.id == achievement_id)
        .values(**update_data)
        .returning(models.Achievement)
    )
    
    result = await db.execute(stmt)
    await db.commit()
    updated_achievement = result.scalar_one()
    return updated_achievement

@router.patch("/achievements/{achievement_id}/toggle_active", response_model=schemas.AchievementAdminDetail, dependencies=[Depends(get_admin_user)])
async def toggle_achievement_activity(achievement_id: int, db: AsyncSession = Depends(get_db)):
    """
    Toggles the `is_active` status of an achievement.
    This is the recommended way to "delete" or "disable" an achievement.
    """
    achievement = await db.get(models.Achievement, achievement_id)
    if not achievement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")

    new_status = not achievement.is_active
    stmt = (
        update(models.Achievement)
        .where(models.Achievement.id == achievement_id)
        .values(is_active=new_status)
        .returning(models.Achievement)
    )
    
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one()