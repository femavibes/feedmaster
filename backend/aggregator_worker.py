# backend/aggregator_worker.py
#
# This is the core background worker responsible for:
# 1. Periodically running feed-based aggregation tasks.
# 2. Calculating and storing various aggregates (e.g., top posts, top hashtags, trends).
#
# This worker relies on other services (e.g., an ingestion worker, polling worker) to populate the
# 'users', 'posts', and 'feed_posts' tables. It primarily reads from these tables
# and writes to the 'aggregates' table, and reads/filters posts based on the 'is_active_for_polling' flag.

import asyncio
import json # Keep this import, might be needed elsewhere, but not for data_json directly
import os
import uuid
from datetime import datetime, timezone, timedelta
# CHANGED: Import AsyncSession and Awaitable for proper async type hints
from backend.enums import Timeframe
from typing import Dict, Any, List, Optional, Set, Callable, Awaitable 
# CHANGED: Use AsyncSession instead of Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, cast, String, and_
import logging
import sys
from urllib.parse import urlparse # For extracting domains from URLs

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Local imports
from backend import models, schemas, crud
# CHANGED: Import AsyncSessionLocal and async_engine (assuming database.py was updated)
from backend.database import AsyncSessionLocal, async_engine, Base # For dev/testing table creation, remove for production

# --- Configuration ---
WORKER_POLLING_INTERVAL_SECONDS = int(os.getenv("AGGREGATOR_WORKER_POLLING_INTERVAL_SECONDS", 300)) # Default to 5 minutes

# --- Aggregation Definitions (functions to calculate aggregates) ---
# These functions should be defined elsewhere (e.g., content_aggregates.py, user_aggregates.py)
# and take (db: AsyncSession, feed_id: str, timeframe: str) as arguments.
# They should return the calculated aggregate data (e.g., a list of dicts)
# For example, in backend/aggregations/content_aggregates.py:
# async def calculate_top_posts(db: AsyncSession, feed_id: str, timeframe: str) -> List[Dict[str, Any]]: ...


# Define a placeholder/mock for aggregation functions if they are not yet implemented
# This allows the worker to run without crashing, but aggregates will not be calculated.
# CHANGED: timeframe: str to timeframe: Timeframe
async def mock_calculate_aggregate(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    logger.warning(f"Aggregation function not implemented for feed_id={feed_id}, timeframe={timeframe.value}. Returning empty data.")
    return {"top": []} # Return a dictionary with a "top" key to match expected output structure


# Using a dictionary to map aggregate names to their corresponding functions
# Declared with a specific type hint for clarity
# CHANGED: The function signature in the type hint now expects a Timeframe enum
AGGREGATION_FUNCTIONS: Dict[str, Callable[[AsyncSession, str, Timeframe], Awaitable[Dict[str, Any]]]] = {}


# Populate AGGREGATION_FUNCTIONS with actual functions if they exist, otherwise use mock
try:
    from .aggregations import (
        content_aggregates,
        user_aggregates,
        hashtag_aggregates,
        link_aggregates,
        geo_aggregates # Import the new geo_aggregates module
    )

    AGGREGATION_FUNCTIONS["top_posts"] = content_aggregates.calculate_top_posts
    AGGREGATION_FUNCTIONS["top_images"] = content_aggregates.calculate_top_images # Changed to snake_case
    AGGREGATION_FUNCTIONS["top_videos"] = content_aggregates.calculate_top_videos # Changed to snake_case
    
    AGGREGATION_FUNCTIONS["top_hashtags"] = hashtag_aggregates.calculate_top_hashtags
    
    AGGREGATION_FUNCTIONS["top_users"] = user_aggregates.calculate_top_users
    AGGREGATION_FUNCTIONS["top_posters_by_count"] = user_aggregates.calculate_top_posters_by_count # Changed to snake_case
    AGGREGATION_FUNCTIONS["top_mentions"] = user_aggregates.calculate_top_mentions
    AGGREGATION_FUNCTIONS["longest_poster_streaks"] = user_aggregates.calculate_longest_poster_streaks
    AGGREGATION_FUNCTIONS["active_poster_streaks"] = user_aggregates.calculate_active_poster_streaks
    AGGREGATION_FUNCTIONS["first_time_posters"] = user_aggregates.calculate_first_time_posters

    AGGREGATION_FUNCTIONS["top_links"] = link_aggregates.calculate_top_links
    AGGREGATION_FUNCTIONS["top_domains"] = link_aggregates.calculate_top_domains
    AGGREGATION_FUNCTIONS["top_link_cards"] = link_aggregates.calculate_top_cards
    AGGREGATION_FUNCTIONS["top_news_link_cards"] = link_aggregates.calculate_top_news_cards
    

    # --- ADDED GEO AGGREGATIONS ---
    AGGREGATION_FUNCTIONS["top_cities"] = geo_aggregates.calculate_top_cities # Changed to snake_case
    AGGREGATION_FUNCTIONS["top_regions"] = geo_aggregates.calculate_top_regions # Changed to snake_case
    AGGREGATION_FUNCTIONS["top_countries"] = geo_aggregates.calculate_top_countries # Changed to snake_case
    # --- END ADDED GEO AGGREGATIONS ---

except ImportError as e:
    logger.warning(f"Could not import all aggregation modules: {e}. Using mock aggregation functions for some or all.")
    # Fallback to mock for all if any import fails or specifically for missing ones
    all_expected_aggregations = [
        "top_posts", "top_images", "top_videos", "top_hashtags", "top_users", # Changed to snake_case
        "top_posters_by_count", "top_mentions", "longest_poster_streaks", "active_poster_streaks", "first_time_posters", "top_links", # Changed to snake_case
        "top_domains", "top_link_cards", "top_news_link_cards", # Changed to snake_case
        # --- ADDED GEO AGGREGATIONS TO FALLBACK LIST ---
        "top_cities", "top_regions", "top_countries" # Changed to snake_case
        # --- END ADDED ---
    ]
    for agg_name in all_expected_aggregations:
        if agg_name not in AGGREGATION_FUNCTIONS: # Only assign mock if it wasn't successfully imported
            AGGREGATION_FUNCTIONS[agg_name] = mock_calculate_aggregate

def _extract_dids_from_result(data: Any, found_dids: set):
    """
    Recursively traverses a nested data structure (dicts and lists)
    and extracts all strings that look like a DID.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            # Check if the key indicates a DID and the value is a valid DID string
            if key in ('did', 'author_did') and isinstance(value, str) and value.startswith('did:'):
                found_dids.add(value)
            # Recurse into nested structures
            elif isinstance(value, (dict, list)):
                _extract_dids_from_result(value, found_dids)
    elif isinstance(data, list):
        for item in data:
            _extract_dids_from_result(item, found_dids)


# --- Aggregation Schedule Configuration (Moved to module level) ---
STANDARD_TIME_INTERVALS = {
    "1h": 60,       # 1 minute (temporarily reduced for testing)
    "6h": 60,       # 1 minute (temporarily reduced for testing)
    "1d": 60,       # 1 minute (temporarily reduced for testing)
    "7d": 86400,    # 1 day
    "30d": 86400,   # 1 day
    "allTime": 86400, # 1 day
}

SCHEDULE_GROUPS = {
    "all_timeframes": [
        "top_posts", "top_images", "top_videos", "top_hashtags", "top_users",
        "top_posters_by_count", "top_mentions", "top_links", "top_domains",
        "top_link_cards", "top_news_link_cards", "top_cities", "top_regions", "top_countries",
        "first_time_posters",
    ],
    "all_time_only": [
        "longest_poster_streaks", "active_poster_streaks",
    ],
}

def _build_aggregation_schedule() -> List[tuple]:
    """Builds the aggregation schedule list from the configuration."""
    schedule = []
    for agg_name in SCHEDULE_GROUPS["all_timeframes"]:
        for timeframe, interval in STANDARD_TIME_INTERVALS.items():
            schedule.append((agg_name, timeframe, interval))
    for agg_name in SCHEDULE_GROUPS["all_time_only"]:
        schedule.append((agg_name, "allTime", STANDARD_TIME_INTERVALS["allTime"]))
    return schedule

# Build the schedule once at module startup.
AGGREGATION_SCHEDULE = _build_aggregation_schedule()

# CHANGED: db: Session to db: AsyncSession, and added 'async'
async def run_aggregations(db: AsyncSession):
    """
    Main function to run scheduled aggregations for all active feeds.
    """
    logger.info("Starting new aggregation cycle...")

    # --- Prominence Management ---
    # 1. Get the current set of all prominent users at the start of the cycle.
    try:
        initial_prominent_dids = await crud.get_all_prominent_user_dids(db)
        logger.info(f"Found {len(initial_prominent_dids)} users currently marked as prominent.")
    except Exception as e:
        logger.error(f"Could not fetch initial prominent DIDs: {e}", exc_info=True)
        initial_prominent_dids = set()

    # This set will collect all user DIDs that appear in any "top" list during this cycle.
    newly_identified_prominent_dids = set()
    # --- End Prominence Management ---

    # Get all active feed IDs from the database to avoid passing full ORM objects
    # into the loop, which can cause issues with detached instances and lead to
    # the 'MissingGreenlet' error.
    from sqlalchemy import select, update
    feed_ids_stmt = select(models.Feed.id)
    feed_ids = (await db.execute(feed_ids_stmt)).scalars().all()

    logger.info(f"Retrieved feeds for aggregation: {feed_ids}")
    if not feed_ids:
        logger.info("No feeds found to aggregate. Waiting for next cycle.")
        return

    for feed_id in feed_ids:
        # Add validation for feed_id
        if not feed_id or str(feed_id) == '0':
            logger.warning(f"Skipping aggregation for feed with invalid ID: {feed_id}.")
            continue

        for agg_definition_name, timeframe_name, min_interval in AGGREGATION_SCHEDULE:
            aggregate_full_name = f"{feed_id}-{agg_definition_name}-{timeframe_name}"

            # --- ADD THIS NEW LOGGING HERE ---
            logger.info(f"Checking schedule for '{aggregate_full_name}'. Min interval: {min_interval}s.")
            # --- END NEW LOGGING ---

            try:
                # Retrieve the last computed aggregate record
                aggregate_record = await crud.get_aggregate_by_name(db, name=aggregate_full_name) # CHANGED: Added await

                # Check if aggregation is due
                now = datetime.now(timezone.utc)
                should_run_aggregation = True
                if aggregate_record and aggregate_record.updated_at:
                    time_since_last_aggregation = (now - aggregate_record.updated_at).total_seconds()
                    if time_since_last_aggregation < min_interval:
                        should_run_aggregation = False
                        logger.debug(f"Skipping aggregation '{aggregate_full_name}': not due yet. Last run {int(time_since_last_aggregation)}s ago.")

                if should_run_aggregation:
                    logger.info(f"Running aggregation '{aggregate_full_name}' for feed '{feed_id}' with timeframe '{timeframe_name}'") # Log with string name
                    agg_func = AGGREGATION_FUNCTIONS.get(agg_definition_name) # Changed from aggregation_definitions to AGGREGATION_FUNCTIONS
                    if agg_func:
                        # Convert the timeframe string from the schedule into a Timeframe enum member
                        try:
                            timeframe_enum = Timeframe(timeframe_name)
                        except ValueError:
                            logger.error(f"Invalid timeframe string '{timeframe_name}' in schedule for '{agg_definition_name}'. Skipping.")
                            continue
                        
                        result_data = await agg_func(db, feed_id, timeframe_enum)
                        
                        # --- Prominence Management: Extract DIDs from results ---
                        # This robustly finds all DIDs in the result data, regardless of structure.
                        _extract_dids_from_result(result_data, newly_identified_prominent_dids)

                        # Store or update the aggregate result
                        aggregate_create_schema = schemas.AggregateCreate(
                            feed_id=feed_id,
                            agg_name=agg_definition_name,
                            timeframe=timeframe_name,
                            data_json=result_data
                        )
                        await crud.create_or_update_aggregate(db, aggregate_create_schema) # CHANGED: Added await
                        logger.info(f"Successfully aggregated '{aggregate_full_name}' for feed '{feed_id}'.")
                    else:
                        # This should ideally not be hit if AGGREGATION_FUNCTIONS is correctly populated
                        logger.warning(f"No aggregation function found for '{agg_definition_name}'. Skipping.")

                    # Update the feed's last_aggregated_at timestamp
                    update_stmt = (
                        update(models.Feed)
                        .where(models.Feed.id == feed_id)
                        .values(last_aggregated_at=datetime.now(timezone.utc))
                    )
                    await db.execute(update_stmt)
                    await db.commit() # CHANGED: Added await

            except Exception as e:
                logger.error(f"Error aggregating for feed {feed_id}, aggregate {agg_definition_name}, timeframe {timeframe_name}: {e}", exc_info=True)
                await db.rollback() # CHANGED: Added await

    # --- Prominence Management: Update database after all aggregations are done ---
    try:
        dids_to_make_prominent = newly_identified_prominent_dids - initial_prominent_dids
        dids_to_remove_prominence = initial_prominent_dids - newly_identified_prominent_dids

        if dids_to_make_prominent:
            logger.info(f"Marking {len(dids_to_make_prominent)} new users as prominent.")
            await crud.set_user_prominence_batch(db, list(dids_to_make_prominent), is_prominent=True)
        
        if dids_to_remove_prominence:
            logger.info(f"Removing prominence from {len(dids_to_remove_prominence)} users.")
            await crud.set_user_prominence_batch(db, list(dids_to_remove_prominence), is_prominent=False)
        
        if dids_to_make_prominent or dids_to_remove_prominence:
            await db.commit()
            logger.info("Successfully updated user prominence.")
    except Exception as e:
        logger.error(f"Failed to update user prominence: {e}", exc_info=True)
        await db.rollback()
    logger.info("Aggregation cycle complete.")


async def start_aggregator_worker():
    logger.info("Starting Feedmaster Aggregator worker...")
    
    # In production, use Alembic for migrations.
    # Base.metadata.create_all(bind=engine) # Uncomment for local dev/testing if needed
    
    while True:
        # CHANGED: Use async with for AsyncSessionLocal
        async with AsyncSessionLocal() as db_agg:
            try:
                await run_aggregations(db_agg) # CHANGED: Added await
            except Exception as e:
                logger.error(f"Error during scheduled aggregation: {e}", exc_info=True)
                # Rollback is handled within run_aggregations, but if an error occurs
                # outside that function (e.g., during db_agg creation), this handles it.
                await db_agg.rollback() # CHANGED: Added await
            finally:
                # db_agg is automatically closed by async with, so no explicit db_agg.close() needed here
                pass
                
        logger.info(f"Aggregator cycle complete. Waiting {WORKER_POLLING_INTERVAL_SECONDS} seconds for next cycle.")
        await asyncio.sleep(WORKER_POLLING_INTERVAL_SECONDS)


if __name__ == "__main__":
    # In production, use Alembic for migrations.
    # Base.metadata.create_all(bind=engine) # Uncomment for local dev/testing if needed
    
    # To run the worker
    asyncio.run(start_aggregator_worker())
