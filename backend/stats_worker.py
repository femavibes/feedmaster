# backend/stats_worker.py
#
# This background worker is responsible for periodically calculating user-level
# statistics and awarding achievements based on those stats. It runs independently
# of the real-time ingestion worker.

import asyncio
import os
import sys 
import logging
from datetime import datetime, timezone, timedelta
import operator as op
from typing import Dict, Any, List, Set

from sqlalchemy import select, func, text, update, delete, case, cast, Integer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

# Local imports
from backend.database import AsyncSessionLocal, Base, async_engine
from backend import models
# --- Import the centralized rarity definitions ---
from backend.achievements.definitions import get_rarity_tier_from_percentage
from backend.services import achievement_service

# --- Configuration ---
STATS_WORKER_INTERVAL_MINUTES = int(os.getenv("STATS_WORKER_INTERVAL_MINUTES", 15))
ACHIEVEMENT_RARITY_INTERVAL_HOURS = int(os.getenv("ACHIEVEMENT_RARITY_INTERVAL_HOURS", 24))

# --- Setup Logger ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False # Prevent log propagation to the root logger

# This block ensures that handlers are not added multiple times if the module is reloaded
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [StatsWorker] - %(message)s')

    # --- Setup Console Handler ---
    # This handler is always added so logs are visible in `docker compose logs`.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # --- Setup File Handler (optional) ---
    # This handler attempts to write to a file, but will not crash the worker on permission errors.
    try:
        # The WORKDIR in the Dockerfile is /app.
        LOGS_DIR = "/app/logs"
        os.makedirs(LOGS_DIR, exist_ok=True)
        
        file_handler = logging.FileHandler(os.path.join(LOGS_DIR, "stats_worker_logs.txt"))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        logger.info("File logging is enabled.")
    except PermissionError:
        logger.warning("Permission denied to create '/app/logs' directory. File logging is disabled for this session.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while setting up file logging: {e}", exc_info=True)

def _create_tiered_achievements(
    base_key: str,
    base_name: str,
    description_template: str,
    stat: str,
    ach_type: models.AchievementType,
    tiers: List[Dict[str, Any]],
    icon: str = None,
    is_repeatable: bool = True,
    agg_method: str = None,
    operator: str = '>='
) -> Dict[str, Any]:
    """
    Generates a dictionary of tiered achievement definitions to reduce boilerplate.
    """
    achievements = {}
    for tier_info in tiers:
        key = f"{base_key}_{tier_info['key_suffix']}"
        # Construct name, stripping extra space if suffix is empty
        name = f"{base_name} {tier_info.get('name_suffix', '')}".strip()
        value = tier_info['value']
        
        # Format description with comma-separated numbers for readability
        description = description_template.format(value=f"{value:,}")
        
        criteria = {'stat': stat, 'operator': operator, 'value': value}
        if agg_method:
            criteria['agg_method'] = agg_method

        achievements[key] = {
            'name': name,
            'description': description,
            'icon': icon,
            'type': ach_type,
            'is_repeatable': is_repeatable,
            'criteria': criteria,
            'series_key': base_key, # Add the series key for grouping
        }
    return achievements

# --- Tier Definitions for Generated Achievements ---
ICEBREAKER_TIERS = [
    {'key_suffix': 'i', 'name_suffix': '', 'value': 1},
]
COMMUNITY_FAVORITE_TIERS = [
    {'key_suffix': 'i', 'name_suffix': '', 'value': 100},
]
FEED_EXPLORER_TIERS = [
    {'key_suffix': 'i', 'name_suffix': '', 'value': 3},
    # To add a new tier, you would just add a line here:
    # {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 10},
]
POWER_POSTER_TIERS = [
    {'key_suffix': 'i', 'name_suffix': 'I', 'value': 10},
    {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 50},
    {'key_suffix': 'iii', 'name_suffix': 'III', 'value': 250},
]
GLOBAL_ICON_TIERS = [
    {'key_suffix': 'i', 'name_suffix': 'I', 'value': 1000},
    {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 5000},
    {'key_suffix': 'iii', 'name_suffix': 'III', 'value': 25000},
    {'key_suffix': 'iv', 'name_suffix': 'IV', 'value': 100000},
    {'key_suffix': 'v', 'name_suffix': 'V', 'value': 250000},
    {'key_suffix': 'vi', 'name_suffix': 'VI', 'value': 1000000},
    {'key_suffix': 'vii', 'name_suffix': 'VII', 'value': 5000000},
]
IMAGE_POSTER_TIERS = [
    {'key_suffix': 'i', 'name_suffix': 'I', 'value': 1},
    {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 5},
    {'key_suffix': 'iii', 'name_suffix': 'III', 'value': 20},
    {'key_suffix': 'iv', 'name_suffix': 'IV', 'value': 100},
    {'key_suffix': 'v', 'name_suffix': 'V', 'value': 500},
    {'key_suffix': 'vi', 'name_suffix': 'VI', 'value': 1000},
    {'key_suffix': 'vii', 'name_suffix': 'VII', 'value': 5000},
]
VIDEO_POSTER_TIERS = [
    {'key_suffix': 'i', 'name_suffix': 'I', 'value': 1},
    {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 3},
    {'key_suffix': 'iii', 'name_suffix': 'III', 'value': 10},
    {'key_suffix': 'iv', 'name_suffix': 'IV', 'value': 50},
    {'key_suffix': 'v', 'name_suffix': 'V', 'value': 200},
    {'key_suffix': 'vi', 'name_suffix': 'VI', 'value': 500},
    {'key_suffix': 'vii', 'name_suffix': 'VII', 'value': 2000},
]
VIRAL_SENSATION_TIERS = [
    {'key_suffix': 'i', 'name_suffix': 'I', 'value': 25},
    {'key_suffix': 'ii', 'name_suffix': 'II', 'value': 100},
    {'key_suffix': 'iii', 'name_suffix': 'III', 'value': 500},
    {'key_suffix': 'iv', 'name_suffix': 'IV', 'value': 2500},
]

# --- Achievement Definitions ---
# This dictionary serves as the single source of truth for all achievements.
ACHIEVEMENT_DEFINITIONS = {
    # --- Generated Tiered Achievements ---
    # By using the generator for all achievements, we create a consistent structure.
    **_create_tiered_achievements(
        'icebreaker', 'Icebreaker', 'Made your first post in a feed. Welcome!',
        'post_count', models.AchievementType.PER_FEED, ICEBREAKER_TIERS,
        icon='👋', is_repeatable=True, operator='=='
    ),
    **_create_tiered_achievements(
        'community_favorite', 'Community Favorite', 'Received {value}+ likes on posts in a single feed.',
        'total_likes_received', models.AchievementType.PER_FEED, COMMUNITY_FAVORITE_TIERS,
        icon='❤️‍🔥', is_repeatable=True
    ),
    **_create_tiered_achievements(
        'feed_explorer', 'Feed Explorer', 'Posted in {value} different feeds.',
        'feed_count', models.AchievementType.GLOBAL, FEED_EXPLORER_TIERS,
        icon='🌍', is_repeatable=False, agg_method='count'
    ),
    **_create_tiered_achievements(
        'power_poster', 'Power Poster', 'Posted {value} times in a single feed.',
        'post_count', models.AchievementType.PER_FEED, POWER_POSTER_TIERS
    ),
    **_create_tiered_achievements(
        'global_likes', 'Global Icon', 'Received {value} likes in total across all feeds.',
        'total_likes_received', models.AchievementType.GLOBAL,
        GLOBAL_ICON_TIERS,
        icon='🌟', is_repeatable=False, agg_method='sum'
    ),
    **_create_tiered_achievements(
        'image_poster', "Image Poster", 'Include an image in {value} posts in a single feed.',
        'image_post_count', models.AchievementType.PER_FEED,
        IMAGE_POSTER_TIERS, icon='🖼️'
    ),
    **_create_tiered_achievements(
        'video_poster', 'Video Poster', 'Share {value} video posts in a single feed.',
        'video_post_count', models.AchievementType.PER_FEED, VIDEO_POSTER_TIERS, icon='🎬'
    ),
    **_create_tiered_achievements(
        'viral_sensation', 'Viral Sensation', 'A single post received {value}+ total likes & reposts in a feed.',
        'max_post_engagement', models.AchievementType.PER_FEED,
        VIRAL_SENSATION_TIERS, icon='🔥'
    ),

    # --- NEW GLOBAL VERSIONS OF PER-FEED ACHIEVEMENTS ---
    **_create_tiered_achievements(
        'global_power_poster', 'Power Poster', 'Posted {value} times in total across all feeds.',
        'post_count', models.AchievementType.GLOBAL, POWER_POSTER_TIERS,
        icon='✍️', is_repeatable=False, agg_method='sum'
    ),
    **_create_tiered_achievements(
        'global_image_poster', "Image Poster", 'Include an image in {value} posts in total across all feeds.',
        'image_post_count', models.AchievementType.GLOBAL, IMAGE_POSTER_TIERS,
        icon='📸', is_repeatable=False, agg_method='sum'
    ),
    **_create_tiered_achievements(
        'global_video_poster', 'Video Poster', 'Share {value} video posts in total across all feeds.',
        'video_post_count', models.AchievementType.GLOBAL, VIDEO_POSTER_TIERS,
        icon='🎥', is_repeatable=False, agg_method='sum'
    ),
    **_create_tiered_achievements(
        'global_viral_sensation', 'Viral Sensation', 'A single post received {value}+ total likes & reposts anywhere.',
        'max_post_engagement', models.AchievementType.GLOBAL, VIRAL_SENSATION_TIERS,
        icon='💥', is_repeatable=False, agg_method='max'
    ),
}

async def seed_achievements(db: AsyncSession):
    """
    Ensures all achievements from ACHIEVEMENT_DEFINITIONS exist in the database.
    This function runs on worker startup and will only *add* new achievements
    if their `key` is not already in the database. It will NOT update existing
    achievements, as those are now managed via the admin UI.
    """
    logger.info("Syncing achievement definitions with the database...")

    # Get all existing achievement keys from the database to avoid creating duplicates.
    existing_achievements_result = await db.execute(select(models.Achievement))
    existing_achievements_map = {ach.key: ach for ach in existing_achievements_result.scalars().all()}

    # Iterate through code definitions and add any that are missing from the DB.
    for key, definition in ACHIEVEMENT_DEFINITIONS.items():
        existing_ach = existing_achievements_map.get(key)

        if existing_ach is None:
            logger.info(f"Creating new achievement from definition: {key}")
            new_achievement = models.Achievement(
                key=key,
                name=definition['name'],
                description=definition['description'],
                icon=definition.get('icon'),
                type=definition['type'],
                is_repeatable=definition['is_repeatable'],
                criteria=definition.get('criteria'),
                series_key=definition.get('series_key')
            )
            db.add(new_achievement)

    await db.commit()
    logger.info("Achievement sync complete.")


async def update_all_user_stats(db: AsyncSession, since: datetime | None) -> tuple[Set[str], datetime | None]:
    """
    Calculates and upserts user statistics based on post activity.

    If `since` is None, it performs a full, comprehensive rebuild of all stats from scratch.
    If `since` is a datetime, it performs a fast, incremental update, processing only
    posts created after that time and adding the new stats to the existing records.

    Returns:
        A tuple containing:
        - A set of user DIDs whose stats were updated.
        - The timestamp of the latest post processed in this run.
    """
    logger.info(f"Starting user stats update for posts since {since or 'the beginning'}...")
    stats_query = (
        select(
            models.Post.author_did,
            models.FeedPost.feed_id,
            func.count(models.Post.id).label("post_count"),
            func.sum(models.Post.like_count).label("total_likes_received"),
            func.sum(models.Post.repost_count).label("total_reposts_received"),
            func.sum(models.Post.reply_count).label("total_replies_received"),
            func.sum(models.Post.quote_count).label("total_quotes_received"),
            func.sum(cast(models.Post.has_image, Integer)).label("image_post_count"),
            func.sum(cast(models.Post.has_video, Integer)).label("video_post_count"),
            func.max(models.Post.like_count + models.Post.repost_count).label("max_post_engagement"),
            func.min(models.Post.created_at).label("first_post_at"),
            func.max(models.Post.created_at).label("latest_post_at"),
        )
        .join(models.FeedPost, models.Post.id == models.FeedPost.post_id)
    )

    if since:
        stats_query = stats_query.where(models.Post.created_at > since)

    stats_query = stats_query.group_by(models.Post.author_did, models.FeedPost.feed_id)

    result = await db.execute(stats_query)
    stats_mappings = result.mappings().all()

    if not stats_mappings:
        logger.info("No new post activity found to update stats.")
        return set(), None

    # Convert RowMapping to a plain dict and rename 'author_did' to 'user_did'
    # to match the column names in the UserStats model. This is required by the DB driver.
    stats_to_upsert = [
        {
            "user_did": row['author_did'],
            "feed_id": row['feed_id'],
            "post_count": row['post_count'],
            "total_likes_received": row['total_likes_received'],
            "total_reposts_received": row['total_reposts_received'],
            "total_replies_received": row['total_replies_received'],
            "total_quotes_received": row['total_quotes_received'],
            "image_post_count": row['image_post_count'],
            "video_post_count": row['video_post_count'],
            "max_post_engagement": row['max_post_engagement'],
            "first_post_at": row['first_post_at'],
            "latest_post_at": row['latest_post_at'],
        }
        for row in stats_mappings
    ]

    new_latest_timestamp = max(row['latest_post_at'] for row in stats_to_upsert)

    logger.info(f"Found {len(stats_to_upsert)} user/feed stat records to process in batches.")

    # Batch the upsert operation to stay under PostgreSQL's parameter limit (65535)
    batch_size = 500  # A safe batch size (500 records * 9 columns = 4500 parameters)
    for i in range(0, len(stats_to_upsert), batch_size):
        batch = stats_to_upsert[i:i + batch_size]
        
        logger.info(f"Processing batch {i//batch_size + 1}/{(len(stats_to_upsert) + batch_size - 1)//batch_size} ({len(batch)} records)")
        
        upsert_stmt = pg_insert(models.UserStats).values(batch)

        if since:
            # Incremental update: Add new stats to existing stats.
            on_conflict_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=['user_did', 'feed_id'],
                set_={
                    'post_count': models.UserStats.post_count + upsert_stmt.excluded.post_count,
                    'total_likes_received': models.UserStats.total_likes_received + upsert_stmt.excluded.total_likes_received,
                    'total_reposts_received': models.UserStats.total_reposts_received + upsert_stmt.excluded.total_reposts_received,
                    'total_replies_received': models.UserStats.total_replies_received + upsert_stmt.excluded.total_replies_received,
                    'total_quotes_received': models.UserStats.total_quotes_received + upsert_stmt.excluded.total_quotes_received,
                    'image_post_count': models.UserStats.image_post_count + upsert_stmt.excluded.image_post_count,
                    'video_post_count': models.UserStats.video_post_count + upsert_stmt.excluded.video_post_count,
                    'max_post_engagement': func.greatest(models.UserStats.max_post_engagement, upsert_stmt.excluded.max_post_engagement),
                    'latest_post_at': upsert_stmt.excluded.latest_post_at,
                    'last_updated': func.now(),
                }
            )
        else:
            # Full rebuild: Replace existing stats with the newly calculated values.
            on_conflict_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=['user_did', 'feed_id'],
                set_={
                    'post_count': upsert_stmt.excluded.post_count,
                    'total_likes_received': upsert_stmt.excluded.total_likes_received,
                    'total_reposts_received': upsert_stmt.excluded.total_reposts_received,
                    'total_replies_received': upsert_stmt.excluded.total_replies_received,
                    'total_quotes_received': upsert_stmt.excluded.total_quotes_received,
                    'image_post_count': upsert_stmt.excluded.image_post_count,
                    'video_post_count': upsert_stmt.excluded.video_post_count,
                    'max_post_engagement': upsert_stmt.excluded.max_post_engagement,
                    'latest_post_at': upsert_stmt.excluded.latest_post_at,
                    'last_updated': func.now(),
                }
            )
        await db.execute(on_conflict_stmt)

    await db.commit()
    logger.info("User stats update complete.")
    return {stat['user_did'] for stat in stats_to_upsert}, new_latest_timestamp


async def award_achievements_for_users(db: AsyncSession, user_dids: Set[str]):
    """
    Checks for and awards new achievements for a given set of users.
    This function handles both per-feed and global achievements.
    """
    if not user_dids:
        return
    logger.info(f"Checking achievements for {len(user_dids)} users.")

    # 1. Pre-fetch all necessary data in bulk to avoid N+1 query issues.
    active_achievements_stmt = select(models.Achievement).where(models.Achievement.is_active == True)
    all_stats_stmt = select(models.UserStats).where(models.UserStats.user_did.in_(user_dids))
    all_earned_stmt = select(models.UserAchievement).where(models.UserAchievement.user_did.in_(user_dids))

    # Execute queries sequentially on the same session to avoid concurrency errors.
    achievements_res = await db.execute(active_achievements_stmt)
    stats_res = await db.execute(all_stats_stmt)
    earned_res = await db.execute(all_earned_stmt)

    # 2. Organize the fetched data into dictionaries for efficient lookups.
    all_achievements = achievements_res.scalars().all()
    per_feed_achievements = [ach for ach in all_achievements if ach.type == models.AchievementType.PER_FEED]
    global_achievements = [ach for ach in all_achievements if ach.type == models.AchievementType.GLOBAL]

    stats_by_user = {}
    for stat in stats_res.scalars().all():
        stats_by_user.setdefault(stat.user_did, []).append(stat)

    earned_by_user = {}
    for earned in earned_res.scalars().all():
        earned_by_user.setdefault(earned.user_did, set()).add((earned.achievement_id, earned.feed_id))

    # 3. Iterate through users and check achievements using the pre-fetched data.
    for user_did in user_dids:
        user_stats_records = stats_by_user.get(user_did, [])
        earned_map = earned_by_user.get(user_did, set())

        if not user_stats_records:
            continue # Skip users with no stats

        # --- 1. Check PER_FEED achievements ---
        for stats_record in user_stats_records:
            for achievement_db_obj in per_feed_achievements:
                if (achievement_db_obj.id, stats_record.feed_id) in earned_map:
                    continue

                if achievement_service.check_achievement_criteria(achievement_db_obj, stats_record):
                    logger.info(f"Awarding PER_FEED achievement '{achievement_db_obj.key}' to user {user_did} for feed {stats_record.feed_id}")
                    new_award = models.UserAchievement(
                        user_did=user_did,
                        achievement_id=achievement_db_obj.id,
                        feed_id=stats_record.feed_id
                    )
                    db.add(new_award)
                    earned_map.add((achievement_db_obj.id, stats_record.feed_id))

        # --- 2. Check GLOBAL achievements ---
        for achievement_db_obj in global_achievements:
            if (achievement_db_obj.id, None) in earned_map:
                continue

            if achievement_service.check_achievement_criteria(achievement_db_obj, user_stats_records):
                logger.info(f"Awarding GLOBAL achievement '{achievement_db_obj.key}' to user {user_did}")
                new_award = models.UserAchievement(
                    user_did=user_did,
                    achievement_id=achievement_db_obj.id,
                    feed_id=None # Global achievements have no feed_id
                )
                db.add(new_award)
                earned_map.add((achievement_db_obj.id, None))

    # Commit all newly awarded achievements for all processed users at once.
    await db.commit()


async def update_achievement_rarity(db: AsyncSession):
    """
    Recalculates and updates rarity for both GLOBAL and PER_FEED achievements.
    - GLOBAL rarity is stored on the achievements table.
    - PER_FEED rarity is stored in the new achievement_feed_rarity table.
    """
    logger.info("Updating all achievement rarities...")

    # --- Part 1: GLOBAL Achievement Rarity ---
    logger.info("Calculating GLOBAL achievement rarity...")
    total_users_stmt = select(func.count(models.User.did))
    total_users = (await db.execute(total_users_stmt)).scalar_one()

    if total_users > 0:
        global_achievements_stmt = select(models.Achievement).where(models.Achievement.type == models.AchievementType.GLOBAL)
        global_achievements = (await db.execute(global_achievements_stmt)).scalars().all()

        for ach in global_achievements:
            # Correctly count distinct users who have earned the achievement
            earners_stmt = select(func.count(models.UserAchievement.user_did.distinct())).where(
                models.UserAchievement.achievement_id == ach.id
            )
            total_earners = (await db.execute(earners_stmt)).scalar_one()
            rarity_percentage = (total_earners / total_users) * 100

            # Get the tier object from our definitions
            rarity_tier_obj = get_rarity_tier_from_percentage(rarity_percentage)
            new_tier_name = rarity_tier_obj["name"]
            new_label = f"{rarity_tier_obj['label']} (Global)" # Add context for global achievements

            # Update all rarity fields in the database
            update_stmt = update(models.Achievement).where(models.Achievement.id == ach.id).values(
                rarity_percentage=rarity_percentage,
                rarity_tier=new_tier_name,
                rarity_label=new_label
            )
            await db.execute(update_stmt)
        logger.info(f"Updated rarity for {len(global_achievements)} GLOBAL achievements.")
    else:
        logger.warning("No users found, skipping GLOBAL rarity calculation.")

    # --- Part 2: PER_FEED Achievement Rarity ---
    logger.info("Calculating PER_FEED achievement rarity...")
    # Get total unique posters for every feed from the UserStats table. This is our denominator.
    total_posters_per_feed_stmt = (
        select(
            models.UserStats.feed_id,
            func.count(models.UserStats.user_did.distinct()).label("total_posters")
        ).group_by(models.UserStats.feed_id)
    )
    total_posters_map = {row.feed_id: row.total_posters for row in await db.execute(total_posters_per_feed_stmt)}

    if not total_posters_map:
        logger.info("No feed activity found, skipping PER_FEED rarity calculation.")
        await db.commit()
        logger.info("Achievement rarity update complete.")
        return

    # Get total unique earners for every (achievement, feed) pair. This is our numerator.
    earners_per_feed_stmt = (
        select(
            models.UserAchievement.achievement_id,
            models.UserAchievement.feed_id,
            func.count(models.UserAchievement.user_did.distinct()).label("earner_count")
        )
        .join(models.Achievement, models.Achievement.id == models.UserAchievement.achievement_id)
        .where(models.Achievement.type == models.AchievementType.PER_FEED)
        .where(models.UserAchievement.feed_id.isnot(None))
        .group_by(models.UserAchievement.achievement_id, models.UserAchievement.feed_id)
    )
    earners_result = await db.execute(earners_per_feed_stmt)

    rarity_data_to_insert = []
    for row in earners_result.mappings().all():
        feed_id = row['feed_id']
        total_posters = total_posters_map.get(feed_id, 0)
        rarity_percentage = (row['earner_count'] / total_posters) * 100 if total_posters > 0 else 100.0

        # Get the tier object from our definitions
        rarity_tier_obj = get_rarity_tier_from_percentage(rarity_percentage)
        new_tier_name = rarity_tier_obj["name"]
        # For per-feed, the label includes context which the frontend expects
        new_label = f"{rarity_tier_obj['label']} (in this feed)"

        rarity_data_to_insert.append({
            "achievement_id": row['achievement_id'],
            "feed_id": feed_id,
            "rarity_percentage": rarity_percentage,
            "rarity_tier": new_tier_name,
            "rarity_label": new_label
        })

    if rarity_data_to_insert:
        logger.info(f"Found {len(rarity_data_to_insert)} PER_FEED rarity records to upsert.")
        
        # Use ON CONFLICT DO UPDATE (upsert) for efficiency and safety.
        # This avoids deleting the whole table and only updates what's necessary.
        upsert_stmt = pg_insert(models.AchievementFeedRarity).values(rarity_data_to_insert)
        
        on_conflict_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=['achievement_id', 'feed_id'],
            set_={
                'rarity_percentage': upsert_stmt.excluded.rarity_percentage,
                'rarity_tier': upsert_stmt.excluded.rarity_tier,
                'rarity_label': upsert_stmt.excluded.rarity_label,
                'last_updated': func.now()
            }
        )
        await db.execute(on_conflict_stmt)

    await db.commit()
    logger.info("Achievement rarity update complete.")


async def run_stats_worker():
    """Main loop for the stats and achievements worker."""
    logger.info("Starting Feedmaster Stats & Achievements worker...")
    # last_processed_timestamp tracks the high-water mark for incremental updates.
    # It's initialized to None to trigger a full historical rebuild on the first run.
    last_processed_timestamp: datetime | None = None
    last_rarity_update = datetime.min.replace(tzinfo=timezone.utc)

    async with AsyncSessionLocal() as db:
        await seed_achievements(db)

    while True:
        logger.info(f"Starting stats worker cycle. Processing posts since: {last_processed_timestamp or 'Beginning of time'}")
        async with AsyncSessionLocal() as db:
            try:
                updated_dids, new_timestamp = await update_all_user_stats(db, last_processed_timestamp)
                if new_timestamp:
                    last_processed_timestamp = new_timestamp
                await award_achievements_for_users(db, updated_dids)

                if datetime.now(timezone.utc) - last_rarity_update > timedelta(hours=ACHIEVEMENT_RARITY_INTERVAL_HOURS):
                    await update_achievement_rarity(db)
                    last_rarity_update = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Error during stats worker cycle: {e}", exc_info=True)
                await db.rollback()

        logger.info(f"Stats worker cycle complete. Waiting {STATS_WORKER_INTERVAL_MINUTES} minutes for next cycle.")
        await asyncio.sleep(STATS_WORKER_INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    asyncio.run(run_stats_worker())