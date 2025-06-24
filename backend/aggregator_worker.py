# backend/aggregator_worker.py
#
# This is the core background worker responsible for:
# 1. Listening to Graze Contrails WebSockets, one per configured feed.
# 2. Resolving DIDs to user profiles (using the Bluesky API) with a "stale trick" and
#    enhanced refresh for prominent users.
# 3. Ingesting and processing posts, saving them to the database, and linking to feeds.
# 4. Running feed-based aggregation tasks.
#
# This worker is designed to run continuously in the background.

import asyncio
import json
import os
import httpx # For making HTTP requests to external APIs (e.g., Bluesky)
import websockets # For connecting to WebSockets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

# Local imports
from . import models, schemas, crud
from .database import SessionLocal, engine, Base # Import Base and engine for table creation (for dev/testing, see note below)

# Load environment variables (e.g., for Bluesky API endpoint)
load_dotenv()

# --- Configuration ---
# Path to your config files
CONFIG_DIR = os.getenv("CONFIG_DIR", "config")
# tiers.json is no longer used for user tiers, so its path is removed.
FEEDS_CONFIG_PATH = os.path.join(CONFIG_DIR, "feeds.json")

# Bluesky API endpoint for profile resolution
BLUESKY_API_BASE_URL = os.getenv("BLUESKY_API_BASE_URL", "https://api.bsky.app/xrpc")

# Worker polling interval for checking aggregation schedule and retrying WebSocket connections
WORKER_POLLING_INTERVAL_SECONDS = int(os.getenv("WORKER_POLLING_INTERVAL_SECONDS", 5))

# Default aggregation interval. This can be overridden by feed tiers.
DEFAULT_AGGREGATION_INTERVAL_MINUTES = int(os.getenv("AGGREGATION_INTERVAL_MINUTES", 5))

# How often to force-refresh profiles for top/prominent users (e.g., TopPosters, TopMentions)
# This is separate from the general 24hr stale check.
PROMINENT_DID_REFRESH_INTERVAL_MINUTES = int(os.getenv("PROMINENT_DID_REFRESH_INTERVAL_MINUTES", 30))
# Keep track of DIDs that need frequent refresh and their next refresh time
frequent_refresh_dids: Dict[str, datetime] = {}
PROMINENT_DIDS_TOP_N = 50 # Top N users in relevant aggregates to frequently refresh

# --- In-memory Configuration Storage ---
# This will be loaded once at startup
feeds_config: List[schemas.FeedsConfig] = []

def load_configurations():
    """Loads feed configurations from JSON file."""
    global feeds_config
    try:
        with open(FEEDS_CONFIG_PATH, 'r') as f:
            feeds_data = json.load(f)
            # Ensure HttpUrl is parsed correctly for contrails_websocket_url
            feeds_config = [schemas.FeedsConfig(**feed) for feed in feeds_data]
        print(f"Loaded {len(feeds_config)} feed configurations.")
    except FileNotFoundError as e:
        print(f"Error loading configuration file: {e}. Please ensure '{CONFIG_DIR}' exists and contains 'feeds.json'.")
        raise # Re-raise to stop worker if configs are critical
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in configuration file: {e}")
        raise # Re-raise if config is malformed
    except Exception as e:
        print(f"Error loading and parsing configurations: {e}")
        raise


# --- Profile Resolution Logic (Uses Bluesky API) ---
async def resolve_profile(db: Session, did: str, force_refresh: bool = False) -> Optional[models.User]:
    """
    Resolves a Bluesky DID to a user profile (handle, display name, avatar_url).
    Checks cache first with a 24-hour stale trick.
    'force_refresh' can bypass the stale check for prominent DIDs.
    """
    db_user = crud.get_user(db, did)
    now_utc = datetime.now(timezone.utc)

    if db_user:
        # Check for general stale trick (24 hours)
        if not force_refresh and (now_utc - db_user.last_updated) < timedelta(hours=24):
            return db_user # Cache hit and not stale

        # Check for prominent DID frequent refresh
        if did in frequent_refresh_dids and now_utc < frequent_refresh_dids[did]:
            # This DID is in the frequent refresh queue, but its next refresh time hasn't arrived yet
            return db_user

    print(f"Resolving profile for DID: {did} (fetching or refreshing, force_refresh={force_refresh})")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BLUESKY_API_BASE_URL}/app.bsky.actor.getProfile?actor={did}")
            response.raise_for_status() # Raise an exception for bad status codes
            profile_data = response.json()

            handle = profile_data.get('handle', f"unknown.bsky.social_{did[:8]}")
            display_name = profile_data.get('displayName')
            avatar_url = profile_data.get('avatar')
            followers_count = profile_data.get('followersCount')
            following_count = profile_data.get('followsCount')
            posts_count = profile_data.get('postsCount')
            created_at_str = profile_data.get('createdAt')
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) if created_at_str else None


            user_data = schemas.UserCreate(
                did=did,
                handle=handle,
                display_name=display_name,
                avatar_url=avatar_url,
                followers_count=followers_count,
                following_count=following_count,
                posts_count=posts_count,
                created_at=created_at
            )
            if db_user:
                # Update existing user, also updates last_updated timestamp
                return crud.update_user(db, did, user_data)
            else:
                # Create new user
                return crud.create_user(db, user_data)

        except httpx.HTTPStatusError as e:
            print(f"HTTP error resolving profile {did}: {e.response.status_code} - {e.response.text}")
            # Fallback for errors: create a basic user entry to avoid repeated API calls for failures
            if not db_user: # Only create if not already in DB
                user_data = schemas.UserCreate(
                    did=did,
                    handle=f"error.bsky.social_{did[:8]}", # Indicate error
                    display_name=None,
                    avatar_url=None
                )
                return crud.create_user(db, user_data)
            # If there's an error and user exists, just return existing stale data.
            # Don't update last_updated to avoid immediate re-attempt if it's a persistent error.
            return db_user
        except httpx.RequestError as e:
            print(f"Network error resolving profile {did}: {e}")
            if not db_user:
                user_data = schemas.UserCreate(
                    did=did,
                    handle=f"network_error.bsky.social_{did[:8]}",
                    display_name=None,
                    avatar_url=None
                )
                return crud.create_user(db, user_data)
            return db_user


# --- Post Processing & Ingestion (Adapted for Contrails) ---
async def process_and_ingest_post(db: Session, feed_id: str, contrails_data: Dict[str, Any]):
    """
    Processes data received from a Graze Contrails WebSocket for a specific feed.
    Assumes `contrails_data` is a dictionary containing post-like information.
    """
    # Assuming Contrails data provides a 'post' key with the necessary details
    # This structure is an ASSUMPTION based on common API patterns.
    # You'll need to adjust this parsing based on the actual Contrails payload.
    raw_post_record = contrails_data.get('post')
    if not raw_post_record:
        # print(f"Contrails data for feed {feed_id} missing 'post' key or invalid format (perhaps a heartbeat or system message): {contrails_data}")
        return

    uri = raw_post_record.get('uri')
    cid = raw_post_record.get('cid')
    author_did = raw_post_record.get('author')
    record = raw_post_record.get('record', {}) # The actual AT Protocol record content
    text = record.get('text', '')
    created_at_str = record.get('createdAt')

    if not all([uri, cid, author_did, text, created_at_str]):
        print(f"Skipping malformed post record from Contrails for feed {feed_id}: Missing required fields in {uri if uri else 'unknown URI'}")
        return

    # Check if post already exists in our general 'posts' table
    existing_post = crud.get_post_by_uri(db, uri)
    if existing_post:
        # If post already exists, just link it to this specific feed if not already linked
        feed_post_data = schemas.FeedPostCreate(post_id=existing_post.id, feed_id=feed_id)
        # crud.create_feed_post handles the unique constraint, so no explicit check needed here
        try:
            crud.create_feed_post(db, feed_post_data)
            # print(f"Post {uri} already exists, linked to feed {feed_id}.")
        except Exception as e:
            # This catch is mostly for unique constraint violations if not handled inside crud.create_feed_post
            # print(f"Could not link existing post {uri} to feed {feed_id}: {e}")
            pass # Already linked or other integrity error
        return

    # print(f"Ingesting new post from Contrails for feed {feed_id}: {uri} by {author_did}")

    # Resolve author profile (will cache or update if new/stale)
    await resolve_profile(db, author_did) # Ensure user exists in DB

    # Parse created_at datetime
    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) # Handle 'Z' for UTC

    # Extracting embedded content (simplified for demonstration, based on AT Protocol structure)
    has_image = False
    has_video = False
    has_link = False
    has_quote = False
    has_mention = False
    image_url = None
    link_title = None
    link_description = None
    link_thumbnail_url = None
    hashtags = []
    links = []
    mentions = []

    # Basic hashtag extraction from text
    for word in text.split():
        if word.startswith('#') and len(word) > 1:
            hashtags.append(word.lower())

    # Example parsing for common embeds in 'record.embed'
    embed_data = record.get('embed')
    if embed_data:
        embed_type = embed_data.get('$type')
        if embed_type == 'app.bsky.embed.images#main' and embed_data.get('images'):
            has_image = True
            # Assuming first image's fullsize is what we want
            image_url = embed_data['images'][0].get('fullsize') if embed_data['images'] else None
        elif embed_type == 'app.bsky.embed.external#main' and embed_data.get('external'):
            has_link = True
            external_data = embed_data['external']
            link_uri = external_data.get('uri')
            link_title = external_data.get('title')
            link_description = external_data.get('description')
            link_thumbnail_url = external_data.get('thumb')
            if link_uri:
                links.append({"uri": link_uri, "title": link_title, "description": link_description, "thumb": link_thumbnail_url})
        # TODO: Add more embed types like video, quote, record (repost/quote post)

    # Parsing for mentions from 'record.facets' (if available and parsed by Contrails)
    facets = record.get('facets')
    if facets:
        for facet in facets:
            if facet.get('$type') == 'app.bsky.richtext.facet#mention' and facet.get('features'):
                for feature in facet['features']:
                    if feature.get('$type') == 'app.bsky.richtext.facet#mention' and feature.get('did'):
                        has_mention = True
                        # In a real app, you'd try to get the handle/name from your local user cache or resolve it
                        mentions.append({"did": feature['did'], "handle": None, "name": None}) # Handle/name can be resolved later

    post_data = schemas.PostCreate(
        uri=uri,
        cid=cid,
        text=text,
        created_at=created_at,
        author_did=author_did,
        has_image=has_image,
        has_video=has_video,
        has_link=has_link,
        has_quote=has_quote,
        has_mention=has_mention,
        image_url=image_url,
        link_title=link_title,
        link_description=link_description,
        link_thumbnail_url=link_thumbnail_url,
        hashtags=hashtags if hashtags else None,
        links=links if links else None,
        mentions=mentions if mentions else None,
        embeds=embed_data if embed_data else None, # Store full embed data
        raw_record=record # Store the full AT Protocol record (not the whole Contrails payload)
    )

    db_post = crud.create_post(db, post_data)
    if db_post:
        # Link the post to this specific feed it came from
        feed_post_data = schemas.FeedPostCreate(post_id=db_post.id, feed_id=feed_id)
        crud.create_feed_post(db, feed_post_data) # This handles duplicate linkages


# --- Aggregation Logic ---
async def run_aggregations(db: Session):
    """
    Runs various aggregation tasks based on feed configurations and updates the database.
    This function will be called periodically by the main worker loop.
    Also identifies prominent DIDs for more frequent refresh.
    """
    print(f"\n--- Running Aggregations at {datetime.now()} ---")
    prominent_dids_for_refresh: Set[str] = set()

    for feed_conf in feeds_config:
        feed_id = feed_conf.id
        feed_tier = feed_conf.tier
        print(f"  Aggregating for Feed: '{feed_id}' (Tier: {feed_tier})")

        # Determine aggregation interval based on tier (example logic)
        # This is a placeholder; actual tier-based logic could be more complex
        current_agg_interval_minutes = DEFAULT_AGGREGATION_INTERVAL_MINUTES
        if feed_tier == "gold":
            current_agg_interval_minutes = max(1, DEFAULT_AGGREGATION_INTERVAL_MINUTES // 2) # e.g., 2.5 min
        elif feed_tier == "platinum":
            current_agg_interval_minutes = max(1, DEFAULT_AGGREGATION_INTERVAL_MINUTES // 5) # e.g., 1 min

        # Retrieve last aggregate run time for this feed and agg_name
        last_agg_run = crud.get_aggregate(db, feed_id, "topHashtags", "24h") # Assuming this is a common one
        if last_agg_run and (datetime.now(timezone.utc) - last_agg_run.last_updated) < timedelta(minutes=current_agg_interval_minutes):
            print(f"    - Skipping aggregations for '{feed_id}' as it was recently updated ({last_agg_run.last_updated}).")
            continue # Skip if too soon based on tier

        # --- Example Aggregation: Top Hashtags (last 24 hours) ---
        time_24h_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_posts = db.query(models.Post)\
            .join(models.FeedPost, models.Post.id == models.FeedPost.post_id)\
            .filter(models.FeedPost.feed_id == feed_id)\
            .filter(models.Post.created_at >= time_24h_ago)\
            .all()

        hashtag_counts: Dict[str, int] = {}
        for post in recent_posts:
            if post.hashtags:
                for hashtag in post.hashtags:
                    hashtag_counts[hashtag] = hashtag_counts.get(hashtag, 0) + 1

        top_hashtags_data = sorted(hashtag_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        agg_data = schemas.AggregateCreate(
            feed_id=feed_id,
            agg_name="topHashtags",
            timeframe="24h",
            data_json={"top": [{"hashtag": h, "count": c} for h, c in top_hashtags_data]}
        )
        crud.create_or_update_aggregate(db, agg_data)
        print(f"    - Updated topHashtags for '{feed_id}' ({len(top_hashtags_data)} unique hashtags in last 24h)")


        # --- Example Aggregation: Top Posters (last 24 hours) ---
        # Identify top authors for this feed
        top_posters_query = db.query(
            models.Post.author_did,
            func.count(models.Post.id).label('post_count')
        ).join(models.FeedPost, models.Post.id == models.FeedPost.post_id)\
        .filter(models.FeedPost.feed_id == feed_id)\
        .filter(models.Post.created_at >= time_24h_ago)\
        .group_by(models.Post.author_did)\
        .order_by(func.count(models.Post.id).desc())\
        .limit(PROMINENT_DIDS_TOP_N).all() # Limit to top N for prominent DIDs

        top_posters_data = []
        for did, count in top_posters_query:
            user_profile = crud.get_user(db, did) # Get latest user profile from DB
            if user_profile:
                top_posters_data.append({
                    "did": did,
                    "handle": user_profile.handle,
                    "display_name": user_profile.display_name,
                    "avatar_url": str(user_profile.avatar_url) if user_profile.avatar_url else None,
                    "post_count": count
                })
                # Add to set for frequent refresh
                prominent_dids_for_refresh.add(did)

        agg_data_posters = schemas.AggregateCreate(
            feed_id=feed_id,
            agg_name="topPosters",
            timeframe="24h",
            data_json={"top": top_posters_data}
        )
        crud.create_or_update_aggregate(db, agg_data_posters)
        print(f"    - Updated topPosters for '{feed_id}' ({len(top_posters_data)} top posters)")


        # --- Example Aggregation: Top Mentioned Users (last 24 hours) ---
        top_mentions_query = db.query(
            func.jsonb_array_elements_text(models.Post.mentions).label('mention_json')
        ).join(models.FeedPost, models.Post.id == models.FeedPost.post_id)\
        .filter(models.FeedPost.feed_id == feed_id)\
        .filter(models.Post.created_at >= time_24h_ago)\
        .filter(models.Post.mentions.isnot(None))\
        .all()

        mentioned_dids: Dict[str, int] = {}
        for row in top_mentions_query:
            try:
                mention_data = json.loads(row.mention_json.replace("'", "\"")) # Assuming stringified JSON in DB
                did = mention_data.get('did')
                if did:
                    mentioned_dids[did] = mentioned_dids.get(did, 0) + 1
            except (json.JSONDecodeError, AttributeError):
                continue # Skip malformed mention data

        top_mentioned_data = []
        sorted_mentioned_dids = sorted(mentioned_dids.items(), key=lambda item: item[1], reverse=True)[:PROMINENT_DIDS_TOP_N]

        for did, count in sorted_mentioned_dids:
            user_profile = crud.get_user(db, did)
            if user_profile:
                top_mentioned_data.append({
                    "did": did,
                    "handle": user_profile.handle,
                    "display_name": user_profile.display_name,
                    "avatar_url": str(user_profile.avatar_url) if user_profile.avatar_url else None,
                    "mention_count": count
                })
                prominent_dids_for_refresh.add(did)

        agg_data_mentions = schemas.AggregateCreate(
            feed_id=feed_id,
            agg_name="topMentions",
            timeframe="24h",
            data_json={"top": top_mentioned_data}
        )
        crud.create_or_update_aggregate(db, agg_data_mentions)
        print(f"    - Updated topMentions for '{feed_id}' ({len(top_mentioned_data)} top mentioned users)")


    # --- Manage Prominent DIDs for Frequent Refresh ---
    now_utc = datetime.now(timezone.utc)
    dids_to_remove = []

    # Update refresh schedule for newly identified prominent DIDs
    for did in prominent_dids_for_refresh:
        frequent_refresh_dids[did] = now_utc + timedelta(minutes=PROMINENT_DID_REFRESH_INTERVAL_MINUTES)
        # print(f"  Scheduling frequent refresh for {did} until {frequent_refresh_dids[did]}")

    # Identify DIDs no longer prominent or whose frequent refresh time has passed
    for did, refresh_until in frequent_refresh_dids.items():
        if did not in prominent_dids_for_refresh and now_utc > refresh_until:
            dids_to_remove.append(did)
            # print(f"  Removing {did} from frequent refresh list (no longer prominent or time expired)")

    for did in dids_to_remove:
        frequent_refresh_dids.pop(did)

    print(f"--- Aggregations Finished. {len(frequent_refresh_dids)} DIDs in frequent refresh queue. ---")


# --- WebSocket Listener for a Single Contrails Feed ---
async def listen_to_contrails_feed(feed_id: str, websocket_url: str):
    """
    Establishes and maintains a WebSocket connection to a specific Graze Contrails feed.
    Receives messages and passes them for processing.
    """
    print(f"Attempting to connect to Contrails feed: {feed_id} at {websocket_url}")

    while True:
        try:
            async with websockets.connect(websocket_url) as websocket:
                print(f"Connected to Contrails feed: {feed_id}")
                while True:
                    try:
                        message = await websocket.recv()
                        # Assuming messages are JSON strings
                        contrails_data = json.loads(message)
                        db = SessionLocal()
                        try:
                            await process_and_ingest_post(db, feed_id, contrails_data)
                        finally:
                            db.close()
                    except websockets.exceptions.ConnectionClosedOK:
                        print(f"Contrails feed {feed_id} connection closed cleanly.")
                        break # Exit inner loop to re-attempt connection
                    except websockets.exceptions.ConnectionClosed as e:
                        print(f"Contrails feed {feed_id} connection closed with error: {e}")
                        break
                    except json.JSONDecodeError:
                        print(f"Received non-JSON message from {feed_id}: {message[:100]}...")
                    except Exception as e:
                        print(f"Error processing message from {feed_id}: {e}")

        except (websockets.exceptions.WebSocketException, ConnectionRefusedError) as e:
            print(f"Connection failed for Contrails feed {feed_id}: {e}. Retrying in {WORKER_POLLING_INTERVAL_SECONDS} seconds...")
        except Exception as e:
            print(f"Unexpected error for Contrails feed {feed_id}: {e}. Retrying in {WORKER_POLLING_INTERVAL_SECONDS} seconds...")

        await asyncio.sleep(WORKER_POLLING_INTERVAL_SECONDS) # Wait before retrying connection


# --- Main Worker Loop Orchestrator ---
async def run_worker():
    """
    The main asynchronous orchestrator for the aggregator worker.
    It loads configurations, starts WebSocket listeners for each feed,
    and periodically triggers aggregation tasks.
    """
    print("Starting Aggregator Worker Orchestrator...")

    # Ensure the config directory exists and contains dummy configs for local testing
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Create dummy config files if they don't exist for easy local testing
    # Note: tiers.json is no longer used for user tiers, so it's not created here.
    if not os.path.exists(FEEDS_CONFIG_PATH):
        print(f"Creating dummy feeds.json at {FEEDS_CONFIG_PATH}")
        with open(FEEDS_CONFIG_PATH, 'w') as f:
            json.dump([
                {
                    "id": "home-feed-graze",
                    "name": "Graze Home Feed",
                    "description": "The default home feed from Graze Contrails.",
                    "contrails_websocket_url": "wss://contrails.graze.social/feeds/home-feed-graze",
                    "tier": "silver"
                },
                {
                    "id": "tech-news-graze",
                    "name": "Graze Tech News",
                    "description": "Tech news feed curated by Contrails.",
                    "contrails_websocket_url": "wss://contrails.graze.social/feeds/tech-news-graze",
                    "tier": "gold"
                }
            ], f, indent=2)

    # Load configurations after potentially creating dummy files
    load_configurations()


    # --- Start WebSocket listeners for each feed ---
    listener_tasks = []
    if not feeds_config:
        print("No feeds configured. Worker will only run aggregations if scheduled.")
    else:
        for feed_conf in feeds_config:
            # Pass both feed_id and the specific websocket_url from config
            listener_tasks.append(asyncio.create_task(listen_to_contrails_feed(feed_conf.id, str(feed_conf.contrails_websocket_url))))

    # --- Schedule periodic aggregations and prominent DID refresh ---
    async def aggregation_and_refresh_scheduler():
        while True:
            db = SessionLocal()
            try:
                await run_aggregations(db) # This now includes prominent DID identification
            except Exception as e:
                print(f"Error during scheduled aggregation: {e}")
                db.rollback()
            finally:
                db.close()

            # Separate loop for force-refreshing prominent DIDs
            for did, next_refresh_time in list(frequent_refresh_dids.items()): # Iterate over a copy
                now_utc = datetime.now(timezone.utc)
                if now_utc >= next_refresh_time:
                    db_refresh = SessionLocal()
                    try:
                        print(f"Force-refreshing prominent DID: {did}")
                        await resolve_profile(db_refresh, did, force_refresh=True)
                        frequent_refresh_dids[did] = now_utc + timedelta(minutes=PROMINENT_DID_REFRESH_INTERVAL_MINUTES)
                    except Exception as e:
                        print(f"Error force-refreshing DID {did}: {e}")
                        db_refresh.rollback()
                    finally:
                        db_refresh.close()
            
            await asyncio.sleep(WORKER_POLLING_INTERVAL_SECONDS) # Check frequently for both aggregations and refreshes

    scheduler_task = asyncio.create_task(aggregation_and_refresh_scheduler())

    # --- Run all tasks concurrently ---
    # This will run the WebSocket listeners and the aggregation/refresh scheduler in parallel
    await asyncio.gather(*listener_tasks, scheduler_task)


if __name__ == "__main__":
    # For local development/testing:
    # It's good practice to ensure tables exist if running worker directly,
    # but for production/deployment, Alembic migrations are preferred.
    # Base.metadata.create_all(bind=engine)
    # print("Database tables ensured (via create_all for local testing). In production, use Alembic migrations.")

    # Run the worker orchestrator
    asyncio.run(run_worker())
