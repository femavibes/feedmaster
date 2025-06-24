# backend/aggregator_worker.py
#
# This is the core background worker responsible for:
# 1. Listening to Graze Contrails WebSockets, one per configured feed.
# 2. Resolving DIDs to user profiles (using the Bluesky API).
# 3. Ingesting and processing posts, saving them to the database.
# 4. Running tier-based and feed-based aggregation tasks.
#
# This worker is designed to run continuously in the background.

import asyncio
import json
import os
import httpx # For making HTTP requests to external APIs (e.g., Bluesky)
import websockets # For connecting to WebSockets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
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
TIERS_CONFIG_PATH = os.path.join(CONFIG_DIR, "tiers.json")
FEEDS_CONFIG_PATH = os.path.join(CONFIG_DIR, "feeds.json")

# Bluesky API endpoint for profile resolution
BLUESKY_API_BASE_URL = os.getenv("BLUESKY_API_BASE_URL", "https://api.bsky.app/xrpc")
# PROFILE_RESOLVE_ENDPOINT = f"{BLUESKY_API_BASE_URL}/com.atproto.repo.getRecord" # Example, typically uses resolveHandle or getProfile

# Graze Contrails WebSocket Base URL
GRAZE_CONTRAILS_WS_BASE_URL = os.getenv("GRAZE_CONTRAILS_WS_BASE_URL", "wss://contrails.graze.social") # ASSUMPTION!

# Polling interval for the worker to check for new data / run aggregations
# This will primarily be for checking aggregation schedule, as WebSocket is real-time
WORKER_POLLING_INTERVAL_SECONDS = int(os.getenv("WORKER_POLLING_INTERVAL_SECONDS", 5)) # Check every 5 seconds for aggregation triggers
AGGREGATION_INTERVAL_MINUTES = int(os.getenv("AGGREGATION_INTERVAL_MINUTES", 5)) # Run aggregations every 5 minutes

# --- In-memory Configuration Storage ---
# These will be loaded once at startup
tiers_config: List[schemas.TierConfig] = []
feeds_config: List[schemas.FeedsConfig] = []

def load_configurations():
    """Loads tier and feed configurations from JSON files."""
    global tiers_config, feeds_config
    try:
        with open(TIERS_CONFIG_PATH, 'r') as f:
            tiers_data = json.load(f)
            tiers_config = [schemas.TierConfig(**tier) for tier in tiers_data]
        print(f"Loaded {len(tiers_config)} tier configurations.")

        with open(FEEDS_CONFIG_PATH, 'r') as f:
            feeds_data = json.load(f)
            feeds_config = [schemas.FeedsConfig(**feed) for feed in feeds_data]
        print(f"Loaded {len(feeds_config)} feed configurations.")
    except FileNotFoundError as e:
        print(f"Error loading configuration file: {e}. Please ensure '{CONFIG_DIR}' exists and contains 'tiers.json' and 'feeds.json'.")
        raise # Re-raise to stop worker if configs are critical
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in configuration file: {e}")
        raise # Re-raise if config is malformed


# --- Profile Resolution Logic (Uses Bluesky API) ---
async def resolve_profile(db: Session, did: str) -> Optional[models.User]:
    """
    Resolves a Bluesky DID to a user profile (handle, display name, avatar_url).
    Checks cache first, then fetches from Bluesky API if not found or outdated.
    """
    db_user = crud.get_user(db, did)
    if db_user and (datetime.now(timezone.utc) - db_user.last_updated) < timedelta(hours=24):
        # Cache hit and not too old, return cached profile
        return db_user

    print(f"Resolving profile for DID: {did} (fetching or refreshing)")
    async with httpx.AsyncClient() as client:
        try:
            # Use app.bsky.actor.getProfile for full profile data
            # Bluesky API expects 'actor' parameter for DID or handle
            response = await client.get(f"{BLUESKY_API_BASE_URL}/app.bsky.actor.getProfile?actor={did}")
            response.raise_for_status() # Raise an exception for bad status codes
            profile_data = response.json()

            handle = profile_data.get('handle', f"unknown.bsky.social_{did[:8]}")
            display_name = profile_data.get('displayName')
            avatar_url = profile_data.get('avatar')

            user_data = schemas.UserCreate(
                did=did,
                handle=handle,
                display_name=display_name,
                avatar_url=avatar_url
            )
            if db_user:
                # Update existing user
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
            return db_user # Return existing (possibly outdated) if update failed
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
        print(f"Contrails data for feed {feed_id} missing 'post' key: {contrails_data}")
        return

    uri = raw_post_record.get('uri')
    cid = raw_post_record.get('cid')
    author_did = raw_post_record.get('author')
    record = raw_post_record.get('record', {}) # The actual AT Protocol record content
    text = record.get('text', '')
    created_at_str = record.get('createdAt')

    if not all([uri, cid, author_did, text, created_at_str]):
        print(f"Skipping malformed post record from Contrails for feed {feed_id}: {uri}")
        return

    # Check if post already exists in our general 'posts' table
    existing_post = crud.get_post_by_uri(db, uri)
    if existing_post:
        # If post already exists, just link it to this specific feed if not already linked
        # print(f"Post {uri} already ingested. Ensuring linkage to feed {feed_id}.")
        feed_post_data = schemas.FeedPostCreate(post_id=existing_post.id, feed_id=feed_id)
        crud.create_feed_post(db, feed_post_data) # This will handle duplicates
        return

    print(f"Ingesting new post from Contrails for feed {feed_id}: {uri} by {author_did}")

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
        # Link the post to this specific feed
        feed_post_data = schemas.FeedPostCreate(post_id=db_post.id, feed_id=feed_id)
        crud.create_feed_post(db, feed_post_data) # This handles duplicate linkages


# --- Aggregation Logic ---
async def run_aggregations(db: Session):
    """
    Runs various aggregation tasks based on feed configurations and updates the database.
    This function will be called periodically by the main worker loop.
    """
    print(f"\n--- Running Aggregations at {datetime.now()} ---")
    for feed_conf in feeds_config:
        feed_id = feed_conf.id
        print(f"  Aggregating for Feed: '{feed_id}'")

        # --- Example Aggregation: Top Hashtags (last 24 hours) ---
        # Get posts for this feed that were *created* in the last 24 hours
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

        # Sort hashtags by count (descending) and take top N
        top_n = 10 # Configurable, or from feed_conf if specified
        sorted_hashtags = sorted(hashtag_counts.items(), key=lambda item: item[1], reverse=True)[:top_n]
        top_hashtags_data = [{"hashtag": h, "count": c} for h, c in sorted_hashtags]

        # Save/Update aggregate in DB
        agg_data = schemas.AggregateCreate(
            feed_id=feed_id,
            agg_name="topHashtags", # Matches what frontend might expect
            timeframe="24h",
            data_json={"top": top_hashtags_data}
        )
        crud.create_or_update_aggregate(db, agg_data)
        print(f"    - Updated topHashtags for '{feed_id}' ({len(top_hashtags_data)} unique hashtags in last 24h)")

        # TODO: Implement other aggregations:
        # - Top Links
        # - Top Mentions
        # - Most Active Users
        # - Daily Post Count (for this feed)
        # - etc.
        # Each would involve querying `models.Post` and `models.FeedPost` and then
        # processing the data before saving to `models.Aggregate`.


# --- WebSocket Listener for a Single Contrails Feed ---
async def listen_to_contrails_feed(feed_id: str):
    """
    Establishes and maintains a WebSocket connection to a specific Graze Contrails feed.
    Receives messages and passes them for processing.
    """
    ws_url = f"{GRAZE_CONTRAILS_WS_BASE_URL}/feeds/{feed_id}" # ASSUMPTION for Contrails URL structure
    print(f"Attempting to connect to Contrails feed: {ws_url}")

    while True:
        try:
            async with websockets.connect(ws_url) as websocket:
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
    load_configurations() # Load configs once at startup

    # Ensure the config directory exists and contains dummy configs for local testing
    # In a real scenario, these would be managed by your deployment process
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(TIERS_CONFIG_PATH) or not os.path.exists(FEEDS_CONFIG_PATH):
        print("Creating dummy config files for local testing. Make sure your actual configs are in 'config/' directory.")
        if not os.path.exists(TIERS_CONFIG_PATH):
            with open(TIERS_CONFIG_PATH, 'w') as f:
                json.dump([{"id": "test-tier", "name": "Test Tier", "description": "Desc", "min_followers": 0, "min_posts_daily": 0, "min_reputation_score": 0.0}], f, indent=2)
        if not os.path.exists(FEEDS_CONFIG_PATH):
            with open(FEEDS_CONFIG_PATH, 'w') as f:
                json.dump([{"id": "home", "name": "Home", "description": "Home feed", "criteria": {}}, {"id": "tech-news", "name": "Tech News", "description": "Tech feed", "criteria": {"keywords": ["#tech"]}}], f, indent=2)


    # --- Start WebSocket listeners for each feed ---
    # Create a list of tasks, one for each feed listener
    listener_tasks = []
    if not feeds_config:
        print("No feeds configured. Worker will only run aggregations if scheduled.")
    else:
        for feed_conf in feeds_config:
            listener_tasks.append(asyncio.create_task(listen_to_contrails_feed(feed_conf.id)))

    # --- Schedule periodic aggregations ---
    async def aggregation_scheduler():
        while True:
            db = SessionLocal()
            try:
                await run_aggregations(db)
            except Exception as e:
                print(f"Error during scheduled aggregation: {e}")
                db.rollback()
            finally:
                db.close()
            await asyncio.sleep(AGGREGATION_INTERVAL_MINUTES * 60) # Wait for the next aggregation interval

    scheduler_task = asyncio.create_task(aggregation_scheduler())

    # --- Run all tasks concurrently ---
    # This will run the WebSocket listeners and the aggregation scheduler in parallel
    await asyncio.gather(*listener_tasks, scheduler_task)


if __name__ == "__main__":
    # For local development/testing:
    # It's good practice to ensure tables exist if running worker directly,
    # but for production/deployment, Alembic migrations are preferred.
    # Base.metadata.create_all(bind=engine)
    # print("Database tables ensured (via create_all for local testing). In production, use Alembic migrations.")

    # Run the worker orchestrator
    asyncio.run(run_worker())
