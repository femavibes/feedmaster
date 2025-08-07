import httpx
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from backend import crud, models

logger = logging.getLogger(__name__)

class BlueskyFeedService:
    def __init__(self, base_url: str = "https://bsky.app"):
        self.base_url = base_url
        
    async def fetch_feed_metadata(self, at_uri: str) -> Optional[Dict[str, Any]]:
        """Fetch feed metadata from Bluesky API using AT URI"""
        try:
            async with httpx.AsyncClient() as client:
                # Extract the feed generator URI parts
                # Format: at://did:plc:xyz/app.bsky.feed.generator/feedname
                parts = at_uri.replace("at://", "").split("/")
                if len(parts) != 3:
                    logger.error(f"Invalid AT URI format: {at_uri}")
                    return None
                    
                did, collection, rkey = parts
                
                # Use Bluesky's public API to get feed generator info
                url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getFeedGenerator"
                params = {"feed": at_uri}
                
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                feed_view = data.get("view", {})
                
                return {
                    "name": feed_view.get("displayName", ""),
                    "description": feed_view.get("description", ""),
                    "avatar_url": feed_view.get("avatar", ""),
                    "like_count": feed_view.get("likeCount", 0),
                    "creator_did": feed_view.get("creator", {}).get("did", ""),
                    "creator_handle": feed_view.get("creator", {}).get("handle", "")
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch feed metadata for {at_uri}: {e}")
            return None
    
    async def sync_feed_metadata(self, db: AsyncSession, feed_id: str) -> bool:
        """Sync feed metadata from Bluesky for a specific feed"""
        try:
            feed = await crud.get_feed_by_id(db, feed_id)
            if not feed or not feed.bluesky_at_uri:
                logger.warning(f"Feed {feed_id} not found or missing bluesky_at_uri")
                return False
                
            metadata = await self.fetch_feed_metadata(feed.bluesky_at_uri)
            if not metadata:
                return False
                
            # Update feed with Bluesky metadata
            from backend.schemas import FeedUpdate
            
            update_data = {
                "avatar_url": metadata.get("avatar_url"),
                "like_count": metadata.get("like_count", 0),
                "bluesky_description": metadata.get("description"),
                "last_bluesky_sync": datetime.now(timezone.utc)
            }
            
            # If we don't have a local name, use the Bluesky display name
            if not feed.name or feed.name == feed_id:
                update_data["name"] = metadata.get("name", feed_id)
            
            feed_update = FeedUpdate(**update_data)
            await crud.update_feed(db, feed_id, feed_update)
            await db.commit()
            
            logger.info(f"Successfully synced metadata for feed {feed_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync metadata for feed {feed_id}: {e}")
            return False
    
    async def sync_all_feeds_metadata(self, db: AsyncSession) -> int:
        """Sync metadata for all feeds that have bluesky_at_uri"""
        feeds = await crud.get_feeds(db)
        synced_count = 0
        
        for feed in feeds:
            if feed.bluesky_at_uri:
                if await self.sync_feed_metadata(db, feed.id):
                    synced_count += 1
                    
        logger.info(f"Synced metadata for {synced_count}/{len(feeds)} feeds")
        return synced_count