# backend/profile_resolver.py

import httpx
import logging
from datetime import datetime
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from backend import crud, schemas
from backend.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def resolve_and_update_profiles(db: AsyncSession, dids: List[str]):
    """
    Fetches full user profiles from the Bluesky API for a list of DIDs and updates the database.
    """
    if not dids:
        return

    # Bluesky API allows fetching up to 25 profiles at once
    batch_size = 25
    users_to_update = []

    for i in range(0, len(dids), batch_size):
        batch_dids = dids[i:i+batch_size]
        try:
            async with httpx.AsyncClient(base_url="https://public.api.bsky.app", verify=True) as client:
                response = await client.get("/xrpc/app.bsky.actor.getProfiles", params={"actors": batch_dids}, timeout=30)
                response.raise_for_status()
                profiles_data = response.json().get("profiles", [])

                for profile in profiles_data:
                    created_at_dt = None
                    if profile.get("createdAt"):
                        try:
                            created_at_dt = datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
                        except (ValueError, TypeError):
                            pass
                    
                    user_schema = schemas.UserCreate(
                        did=profile["did"],
                        handle=profile["handle"],
                        display_name=profile.get("displayName"),
                        avatar_url=profile.get("avatar"),
                        followers_count=profile.get("followersCount", 0),
                        following_count=profile.get("followsCount", 0),
                        posts_count=profile.get("postsCount", 0),
                        created_at=created_at_dt,
                    )
                    users_to_update.append(user_schema)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error resolving profiles for DIDs {batch_dids}: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error resolving profiles for DIDs {batch_dids}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error resolving profiles for DIDs {batch_dids}: {e}", exc_info=True)

    if users_to_update:
        await crud.upsert_users_batch(db, users_to_update)
        logger.info(f"Successfully resolved and updated {len(users_to_update)} user profiles.")


async def trigger_profile_resolution(did: str):
    """
    A wrapper function for background tasks to resolve a single user profile.
    It creates its own database session to ensure it's valid for the
    duration of the background task.
    """
    logger.info(f"Background task started: resolving profile for {did}")
    try:
        async with AsyncSessionLocal() as db:
            await resolve_and_update_profiles(db, [did])
        logger.info(f"Background task finished for {did}")
    except Exception as e:
        logger.error(f"Error in background profile resolution for {did}: {e}", exc_info=True)