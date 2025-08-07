# backend/add_initial_feeds.py
import asyncio
import os
import json
from dotenv import load_dotenv
import logging
from sqlalchemy.ext.asyncio import AsyncSession

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Local imports
from backend import crud, schemas
from backend.database import AsyncSessionLocal, async_engine, Base


async def add_initial_feeds(db: AsyncSession):
    """
    Adds initial feed configurations to the database from a JSON file asynchronously.
    Feeds are added only if they do not already exist (based on 'id').
    This version correctly uses the data directly from feeds.json.
    """
    feeds_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'feeds.json')

    try:
        with open(feeds_json_path, 'r') as f:
            initial_feeds_data = json.load(f)
        logger.info(f"Loaded {len(initial_feeds_data)} feeds from {feeds_json_path}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"CRITICAL: Could not load or parse feeds.json: {e}. No feeds will be added.")
        return

    for feed_data in initial_feeds_data:
        if 'id' not in feed_data:
            logger.warning(f"Skipping feed due to missing 'id': {feed_data}")
            continue

        feed_id = str(feed_data["id"])

        try:
            existing_feed = await crud.get_feed_by_id(db, feed_id)
            if not existing_feed:
                feed_in = schemas.FeedCreate(**feed_data)
                await crud.create_feed(db, feed_in)
                logger.info(f"Successfully ADDED feed: {feed_data.get('name', feed_id)} (ID: {feed_id})")
            else:
                # Feed exists, so update it to ensure data from feeds.json is current.
                logger.info(f"Feed '{feed_data.get('name', feed_id)}' (ID: {feed_id}) already exists. Updating it...")
                feed_update_data = schemas.FeedUpdate(**feed_data)
                await crud.update_feed(db, feed_id, feed_update_data)
                logger.info(f"Successfully UPDATED feed: {feed_data.get('name', feed_id)} (ID: {feed_id})")
        except Exception as e:
            logger.error(f"Error processing feed '{feed_data.get('name', feed_id)}': {e}", exc_info=True)

async def main():
    logger.info("Initializing database and adding initial feeds...")
    async with AsyncSessionLocal() as db:
        try:
            await add_initial_feeds(db)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.critical(f"A critical error occurred during initial feed setup: {e}", exc_info=True)
    logger.info("Initial feed setup process complete.")

if __name__ == "__main__":
    asyncio.run(main())