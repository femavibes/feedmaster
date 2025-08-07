#!/usr/bin/env python3
"""
Script to sync feed metadata from Bluesky API
"""
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from backend.database import AsyncSessionLocal
from backend.services.bluesky_feed_service import BlueskyFeedService

async def main():
    logger.info("Starting feed metadata sync...")
    
    async with AsyncSessionLocal() as db:
        service = BlueskyFeedService()
        synced_count = await service.sync_all_feeds_metadata(db)
        
    logger.info(f"Feed metadata sync complete. Synced {synced_count} feeds.")

if __name__ == "__main__":
    asyncio.run(main())