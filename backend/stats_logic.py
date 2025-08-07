# backend/stats_logic.py

import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from backend import models, crud

logger = logging.getLogger(__name__)

async def update_achievement_rarity(db: AsyncSession):
    """
    Calculates and stores the rarity percentage ONLY for GLOBAL achievements.
    PER_FEED achievement rarity is calculated dynamically by the API.
    """
    logger.info("Starting achievement rarity update for GLOBAL achievements...")
    
    try:
        # Get all achievements defined as GLOBAL
        global_achievements_stmt = select(models.Achievement).where(
            models.Achievement.type == models.AchievementType.GLOBAL
        )
        global_achievements = (await db.execute(global_achievements_stmt)).scalars().all()

        if not global_achievements:
            logger.info("No GLOBAL achievements found to update.")
            return

        # Get the total number of users in the system once
        total_users = await crud.count_total_users(db)
        if total_users == 0:
            logger.warning("Total user count is 0. Skipping rarity calculation.")
            return

        updated_count = 0
        for achievement in global_achievements:
            # Count how many unique users have earned this specific global achievement
            earners_count = await crud.count_users_with_global_achievement(db, achievement.id) 
            
            # Calculate rarity
            rarity = (earners_count / total_users) * 100 if total_users > 0 else 100.0
            
            # Update the achievement record in the database
            update_stmt = (
                update(models.Achievement)
                .where(models.Achievement.id == achievement.id)
                .values(rarity_percentage=rarity)
            )
            await db.execute(update_stmt)
            updated_count += 1
            logger.debug(f"Updated rarity for GLOBAL achievement '{achievement.name}' to {rarity:.2f}%")

        await db.commit()
        logger.info(f"Successfully updated rarity for {updated_count} GLOBAL achievements.")

    except Exception as e:
        logger.error(f"An error occurred during achievement rarity update: {e}", exc_info=True)
        await db.rollback()
