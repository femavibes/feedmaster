# backend/api/v1/endpoints/profiles.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, tuple_
from typing import List, Optional
from backend import crud, schemas, models, profile_resolver 
from backend.database import get_db
from backend.services.profile_service import get_rarity_label

router = APIRouter()

def _create_safe_achievement_response(
    ach_model: models.Achievement, 
    rarity_percentage: float, 
    rarity_label: Optional[str], 
    rarity_tier: Optional[str]
) -> schemas.AchievementResponse:
    """
    Helper function to safely create an AchievementResponse, handling None values for rarity.
    """
    final_rarity_tier = rarity_tier
    if final_rarity_tier is None:
        # get_rarity_label from profile_service returns the tier name, e.g., "Bronze"
        final_rarity_tier = get_rarity_label(rarity_percentage)

    final_rarity_label = rarity_label
    if final_rarity_label is None:
        if ach_model.type == models.AchievementType.GLOBAL:
            final_rarity_label = f"{final_rarity_tier} (Global)"
        else:
            final_rarity_label = f"{final_rarity_tier} (in this feed)"

    return schemas.AchievementResponse(
        name=ach_model.name, description=ach_model.description, icon=ach_model.icon,
        rarity_percentage=rarity_percentage, rarity_label=final_rarity_label,
        rarity_tier=final_rarity_tier, type=ach_model.type
    )

@router.get("/{user_did}/details", response_model=schemas.ProfileDetails)
async def get_profile_details(user_did: str, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user(db, user_did=user_did)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

@router.get("/{user_did}/stats/{feed_id}", response_model=schemas.UserFeedStats)
async def get_user_stats_for_feed(user_did: str, feed_id: str, db: AsyncSession = Depends(get_db)):
    stats = await crud.get_user_feed_stats(db, user_did=user_did, feed_id=feed_id)
    if not stats:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User stats not found for this feed")
    return stats

@router.get("/{user_did}/achievements", response_model=List[schemas.UserAchievementResponse])
async def get_user_achievements_with_rarity(user_did: str, db: AsyncSession = Depends(get_db)):
    """
    Gets a user's achievements and enriches them with pre-calculated rarity data.
    The crud.get_user_achievements function handles patching per-feed rarity.
    This endpoint just formats the data for the API response.
    """
    user_achievements = await crud.get_user_achievements(db, user_did=user_did)

    response_data = []
    for ua in user_achievements:
        # The ua.achievement object has already been patched by the CRUD function
        # with the correct rarity data for its context (global or per-feed).
        ach = ua.achievement

        achievement_response = _create_safe_achievement_response(ach, 
            ach.rarity_percentage if ach.rarity_percentage is not None else 100.0, 
            ach.rarity_label, ach.rarity_tier)
        response_data.append(schemas.UserAchievementResponse(
            achievement=achievement_response,
            earned_at=ua.earned_at,
            feed_id=ua.feed_id,
            feed=ua.feed
        ))
    return response_data

@router.get("/{user_did}/achievements/in-progress", response_model=List[schemas.InProgressAchievementResponse])
async def get_user_in_progress_achievements(user_did: str, db: AsyncSession = Depends(get_db)):
    """
    Gets a user's in-progress achievements, including their current progress
    and the achievement's rarity.
    """
    # 1. Get raw in-progress data from the CRUD function
    in_progress_data = await crud.get_in_progress_achievements(db, user_did=user_did)

    # 2. Pre-fetch all necessary per-feed rarity data for efficiency
    per_feed_achievements_info = [
        (item['achievement'].id, item['feed'].id)
        for item in in_progress_data
        if item['achievement'].type == models.AchievementType.PER_FEED and item.get('feed')
    ]
    rarity_map = {}
    if per_feed_achievements_info:
        rarity_stmt = select(models.AchievementFeedRarity).where(
            tuple_(models.AchievementFeedRarity.achievement_id, models.AchievementFeedRarity.feed_id).in_(per_feed_achievements_info)
        )
        rarity_results = (await db.execute(rarity_stmt)).scalars().all()
        # Store the full rarity object for access to all its fields
        rarity_map = {(r.achievement_id, r.feed_id): r for r in rarity_results}

    # 3. Build the final response objects with rarity info
    response_list = []
    for item in in_progress_data:
        ach_model = item['achievement']
        feed_model = item.get('feed')
        
        # Default to the global values stored on the achievement model itself
        rarity_percentage = ach_model.rarity_percentage
        rarity_label = ach_model.rarity_label
        rarity_tier = ach_model.rarity_tier

        # If it's a per-feed achievement, try to find the specific rarity info
        # and override the defaults if found.
        if ach_model.type == models.AchievementType.PER_FEED and feed_model:
            feed_rarity_obj = rarity_map.get((ach_model.id, feed_model.id))
            if feed_rarity_obj:
                rarity_percentage = feed_rarity_obj.rarity_percentage
                rarity_label = feed_rarity_obj.rarity_label
                rarity_tier = feed_rarity_obj.rarity_tier
        
        # Safely handle a None rarity_percentage before passing it to the response model helper.
        safe_rarity_percentage = rarity_percentage if rarity_percentage is not None else 100.0

        achievement_response = _create_safe_achievement_response(
            ach_model, safe_rarity_percentage, rarity_label, rarity_tier
        )

        response_list.append(schemas.InProgressAchievementResponse.model_validate(item | {"achievement": achievement_response}))

    return response_list

@router.post("/resolve/{did}", status_code=status.HTTP_202_ACCEPTED)
async def request_profile_resolution(did: str, background_tasks: BackgroundTasks):
    """
    Accepts a request to resolve a user's profile in the background.
    """
    background_tasks.add_task(profile_resolver.trigger_profile_resolution, did)
    return {"message": "Profile resolution has been queued."}