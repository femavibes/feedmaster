# backend/polling_worker.py
#
# This worker is solely responsible for periodically polling the Bluesky API
# for updated engagement metrics for posts that are active in the "battle royale".

import json
import asyncio
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
# Use AsyncSession from sqlalchemy.ext.asyncio for async operations
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, and_, select

from dotenv import load_dotenv

# Load environment variables
import httpx
load_dotenv()

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Local imports
from backend import crud, models
from backend.database import AsyncSessionLocal

# --- Configuration Constants ---
# How often the polling worker runs its loop to check for posts to poll (in seconds)
WORKER_LOOP_INTERVAL_SECONDS = int(os.getenv("POLLING_WORKER_LOOP_INTERVAL_SECONDS", "30"))

# Bluesky API Configuration
BLUESKY_API_BASE_URL = os.getenv("BLUESKY_API_BASE_URL", "https://public.api.bsky.app")

# The maximum number of post URIs to send in a single getPosts API call
GET_POSTS_BATCH_SIZE = 25
POLLING_WORKER_BATCH_LIMIT = int(os.getenv("POLLING_WORKER_BATCH_LIMIT", "200"))

# --- Polling Schedule Configuration from File ---
CONFIG_DIR = "config"
POLLING_CONFIG_PATH = os.path.join(CONFIG_DIR, "polling_config.json")
polling_config = {}
# NEW: Global to track the last modification time of the config file
config_last_modified_time = 0

def load_polling_config():
    """Loads the polling schedule from a JSON file, creating a default if it doesn't exist."""
    global polling_config, config_last_modified_time
    default_config = {
      "deactivation_rules": {
        "hard_stop_hours": 168.0,
        "initial_check_age_hours": 0.5,
        "initial_check_score": 0,
        "second_check_age_hours": 1.0,
        "second_check_score_threshold": 3
      },
      "polling_tiers": [
        {"description": "Hour 1 to Day 1", "max_age_hours": 24.0, "interval_hours": 2.0},
        {"description": "Day 1 to Day 2", "max_age_hours": 48.0, "interval_hours": 6.0},
        {"description": "Day 2 to Day 3", "max_age_hours": 72.0, "interval_hours": 12.0},
        {"description": "Day 3 to Day 7", "max_age_hours": 168.0, "interval_hours": 24.0}
      ]
    }
    
    try:
        if os.path.exists(POLLING_CONFIG_PATH):
            with open(POLLING_CONFIG_PATH, 'r') as f:
                polling_config = json.load(f)
            logger.info(f"Successfully loaded polling schedule from {POLLING_CONFIG_PATH}")
            # Update the modification time after a successful load
            config_last_modified_time = os.path.getmtime(POLLING_CONFIG_PATH)
        else:
            logger.warning(f"No polling_config.json found. Creating a default one at {POLLING_CONFIG_PATH}")
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(POLLING_CONFIG_PATH, 'w') as f:
                json.dump(default_config, f, indent=2)
            polling_config = default_config
            if os.path.exists(POLLING_CONFIG_PATH):
                config_last_modified_time = os.path.getmtime(POLLING_CONFIG_PATH)
    except Exception as e:
        logger.error(f"Error loading or creating polling config, falling back to default: {e}")
        polling_config = default_config


# --- Helper Functions ---
def calculate_engagement_score(like_count: int, repost_count: int, reply_count: int) -> int:
    """Calculates an engagement score for a post based on defined point system."""
    # Point system: 1 point for a like, 2 for a repost, 3 for a reply
    score = (like_count * 1) + (repost_count * 2) + (reply_count * 3)
    return score

def get_next_poll_schedule(post_uri: str, post_age_hours: float, engagement_score: int) -> Optional[timedelta]:
    """
    Determines the timedelta for the next poll based on post age and score.
    Logs the decision-making process for clarity.
    Returns None if the post should be deactivated.
    """
    rules = polling_config.get("deactivation_rules", {})
    tiers = polling_config.get("polling_tiers", [])

    # Hard stop for posts older than 7 days (168 hours)
    hard_stop_hours = rules.get("hard_stop_hours", 168.0)
    if post_age_hours > hard_stop_hours:
        logger.info(f"SCHEDULER: Deactivating {post_uri}. Reason: Post is older than hard stop limit of {hard_stop_hours}h ({post_age_hours:.2f}h).")
        return None

    # --- NEW: Aggressive Early Polling Logic ---
    first_poll_age = rules.get("first_poll_age_hours", 0.084)    # ~5m
    second_poll_age = rules.get("second_poll_age_hours", 0.167)  # ~10m
    third_poll_age = rules.get("third_poll_age_hours", 0.334)   # ~20m
    fourth_poll_age = rules.get("fourth_poll_age_hours", 0.5)    # 30m
    fifth_poll_age = rules.get("fifth_poll_age_hours", 1.0)      # 1h

    # Poll 1 (~5 mins) -> schedule for 10 mins (no elimination)
    if post_age_hours <= first_poll_age:
        next_poll_delta = timedelta(hours=second_poll_age) - timedelta(hours=post_age_hours)
        logger.debug(f"SCHEDULER: Rescheduling {post_uri}. Reason: 5-min poll passed. Next poll in {next_poll_delta}.")
        return next_poll_delta

    # Poll 2 (~10 mins) -> schedule for 20 mins (no elimination)
    if post_age_hours <= second_poll_age:
        next_poll_delta = timedelta(hours=third_poll_age) - timedelta(hours=post_age_hours)
        logger.debug(f"SCHEDULER: Rescheduling {post_uri}. Reason: 10-min poll passed. Next poll in {next_poll_delta}.")
        return next_poll_delta

    # Poll 3 (~20 mins) -> schedule for 30 mins (no elimination)
    if post_age_hours <= third_poll_age:
        next_poll_delta = timedelta(hours=fourth_poll_age) - timedelta(hours=post_age_hours)
        logger.debug(f"SCHEDULER: Rescheduling {post_uri}. Reason: 20-min poll passed. Next poll in {next_poll_delta}.")
        return next_poll_delta

    # Poll 4 (~30 mins) -> ELIMINATE if score is 0, else schedule for 1 hour
    if post_age_hours <= fourth_poll_age:
        elim_score = rules.get("fourth_poll_elimination_score", 0)
        if engagement_score == elim_score:
            logger.info(f"SCHEDULER: Deactivating {post_uri}. Reason: 30-min check failed (score == {elim_score}).")
            return None
        next_poll_delta = timedelta(hours=fifth_poll_age) - timedelta(hours=post_age_hours)
        logger.debug(f"SCHEDULER: Rescheduling {post_uri}. Reason: 30-min poll passed. Next poll in {next_poll_delta}.")
        return next_poll_delta

    # Poll 5 (~1 hour) -> ELIMINATE if score <= 3, else fall through to tiers
    if post_age_hours <= fifth_poll_age:
        elim_threshold = rules.get("fifth_poll_elimination_score_threshold", 3)
        if engagement_score <= elim_threshold:
            logger.info(f"SCHEDULER: Deactivating {post_uri}. Reason: 1-hour check failed (score <= {elim_threshold}). Score: {engagement_score}.")
            return None
        # If it passes, it falls through to the tiered schedule below.

    # Tiered polling schedule for survivors
    for tier in tiers:
        if post_age_hours <= tier.get("max_age_hours", 0):
            interval = tier.get("interval_hours", 24.0)
            next_poll_delta = timedelta(hours=interval)
            logger.debug(f"SCHEDULER: Rescheduling {post_uri}. Reason: Tier '{tier.get('description', 'N/A')}' ({post_age_hours:.2f}h <= {tier.get('max_age_hours')}h). Next poll in {next_poll_delta}.")
            return next_poll_delta

    # This case should not be reached if the last tier's max_age_hours matches the hard_stop_hours.
    # It's a safety net.
    logger.warning(f"SCHEDULER: Post {post_uri} fell through all scheduling tiers. Deactivating as a precaution.")
    return None

# --- Core Polling Logic ---
async def get_posts_engagement_data(post_uris: List[str]) -> Dict[str, Any]:
    """
    Fetches engagement data for a list of post URIs from the Bluesky API using getPosts.
    Returns a dictionary mapping URI to its full post details.
    """
    if not post_uris:
        return {}

    try:
        async with httpx.AsyncClient(base_url=BLUESKY_API_BASE_URL) as client:
            params = {"uris": post_uris}
            logger.info(f"Fetching engagement for {len(post_uris)} posts.")
            # The base URL should point to the XRPC endpoint (e.g., https://public.api.bsky.app/xrpc)
            # The method name is the path from there.
            # The original code had a hardcoded /xrpc, causing a duplicate path.
            response = await client.get("/app.bsky.feed.getPosts", params=params, timeout=20)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            data = response.json()
            # The 'posts' array contains the full details for each requested URI
            # We'll map them by URI for easy lookup
            post_details_map = {post['uri']: post for post in data.get('posts', [])}
            return post_details_map
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching posts: {e.response.status_code} - {e.response.text}")
        return {}
    except httpx.RequestError as e:
        logger.error(f"Request error fetching posts: {e}")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred during get_posts_engagement_data: {e}", exc_info=True)
        return {}


async def poll_and_update_posts():
    """
    Main loop for the polling worker. Queries for active posts due for refresh,
    batches them, fetches data, and updates the database.
    """
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(timezone.utc)

            posts_to_poll = await crud.get_posts_due_for_poll(db, limit=POLLING_WORKER_BATCH_LIMIT)

            if not posts_to_poll:
                logger.info("No posts due for polling in this cycle.")
                return

            logger.info(f"Found {len(posts_to_poll)} posts due for polling. Preparing to poll and evaluate.")

            # Batch the URIs for efficient API calls
            post_uris_batches = [
                [post.uri for post in posts_to_poll[i:i + GET_POSTS_BATCH_SIZE]]
                for i in range(0, len(posts_to_poll), GET_POSTS_BATCH_SIZE)
            ]

            posts_to_update_in_db = []
            deactivated_count = 0

            for batch_num, uris_batch in enumerate(post_uris_batches):
                logger.info(f"Polling batch {batch_num + 1}/{len(post_uris_batches)} with {len(uris_batch)} URIs.")
                fetched_data = await get_posts_engagement_data(uris_batch)

                # Find the corresponding post objects from our DB for this batch
                batch_post_objects = [p for p in posts_to_poll if p.uri in uris_batch]

                for post_obj in batch_post_objects:
                    api_post_details = fetched_data.get(post_obj.uri)

                    if not api_post_details:
                        logger.warning(f"Post {post_obj.uri} not in API response (deleted?). Deactivating.")
                        post_obj.is_active_for_polling = False
                        post_obj.next_poll_at = None
                        deactivated_count += 1
                    else:
                        # Update engagement counts and score
                        post_obj.like_count = api_post_details.get('likeCount', 0)
                        post_obj.repost_count = api_post_details.get('repostCount', 0)
                        post_obj.reply_count = api_post_details.get('replyCount', 0)
                        post_obj.engagement_score = calculate_engagement_score(
                            post_obj.like_count, post_obj.repost_count, post_obj.reply_count
                        )

                        # Determine next poll schedule
                        post_age_hours = (now - post_obj.created_at).total_seconds() / 3600
                        next_schedule = get_next_poll_schedule(post_obj.uri, post_age_hours, post_obj.engagement_score)

                        if next_schedule is None:
                            post_obj.is_active_for_polling = False
                            post_obj.next_poll_at = None
                            deactivated_count += 1
                        else:
                            post_obj.next_poll_at = now + next_schedule

                    posts_to_update_in_db.append(post_obj)

                # Implement a small delay between batches to be respectful of API rate limits
                await asyncio.sleep(1) # 1 second delay between batches

            if posts_to_update_in_db:
                db.add_all(posts_to_update_in_db)
                await db.commit()
                logger.info(f"Bulk updated {len(posts_to_update_in_db)} posts. Deactivated {deactivated_count} posts this cycle.")
            else:
                logger.info("No posts to update in database after all batches processed.")

        except Exception as e:
            logger.error(f"Error in poll_and_update_posts: {e}", exc_info=True)
            await db.rollback()


async def run_polling_worker():
    """
    Orchestrates the continuous polling process.
    """
    logger.info("Starting Bluesky engagement polling worker...")
    load_polling_config() # Initial load at startup
    while True:
        # Check for config file changes before running the cycle
        try:
            if os.path.exists(POLLING_CONFIG_PATH):
                current_mtime = os.path.getmtime(POLLING_CONFIG_PATH)
                if current_mtime > config_last_modified_time:
                    logger.info("Detected change in polling_config.json. Reloading configuration...")
                    load_polling_config()
        except Exception as e:
            logger.error(f"Error checking for config file updates: {e}", exc_info=True)

        await poll_and_update_posts()
        logger.info(f"Polling cycle complete. Waiting {WORKER_LOOP_INTERVAL_SECONDS} seconds for next cycle.")
        await asyncio.sleep(WORKER_LOOP_INTERVAL_SECONDS)


if __name__ == "__main__":
    # Run the polling worker
    asyncio.run(run_polling_worker())
