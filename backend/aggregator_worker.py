# backend/aggregator_worker.py
#
# This is the core background worker responsible for:
# 1. Listening to a data source (e.g., a mock Bluesky "firehose").
# 2. Resolving DIDs to user profiles (using the profile resolution logic).
# 3. Ingesting and processing posts, saving them to the database.
# 4. Running tier-based and feed-based aggregation tasks.
#
# This worker is designed to run continuously in the background.

import asyncio
import json
import os
import httpx # For making HTTP requests to external APIs (e.g., Bluesky)
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from dotenv import load_dotenv

# Local imports
from . import models, schemas, crud
from .database import SessionLocal, engine, Base # Import Base and engine for table creation (for dev/testing, see note below)

# Load environment variables (e.g., for Bluesky API endpoint, if applicable)
load_dotenv()

# --- Configuration ---
# Path to your config files
CONFIG_DIR = os.getenv("CONFIG_DIR", "config")
TIERS_CONFIG_PATH = os.path.join(CONFIG_DIR, "tiers.json")
FEEDS_CONFIG_PATH = os.path.join(CONFIG_DIR, "feeds.json")

# Mock Bluesky API endpoint for profile resolution (replace with real if available)
BLUESKY_API_BASE_URL = os.getenv("BLUESKY_API_BASE_URL", "https://api.bsky.app/xrpc")
PROFILE_RESOLVE_ENDPOINT = f"{BLUESKY_API_BASE_URL}/com.atproto.repo.getRecord" # Example, typically uses resolveHandle or getProfile

# Polling interval for the worker to check for new data / run aggregations
WORKER_POLLING_INTERVAL_SECONDS = int(os.getenv("WORKER_POLLING_INTERVAL_SECONDS", 10)) # Every 10 seconds for mock firehose
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
        # Exit or raise error if critical configs are missing
        exit(1) # Or handle gracefully depending on desired behavior
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in configuration file: {e}")
        exit(1)


# --- Profile Resolution Logic (Similar to backend-profile-resolver) ---
async def resolve_profile(db: Session, did: str) -> Optional[models.User]:
    """
    Resolves a Bluesky DID to a user profile (handle, display name, avatar_url).
    Checks cache first, then fetches from Bluesky API if not found or outdated.
    """
    db_user = crud.get_user(db, did)
    if db_user:
        # Simple cache hit, return cached profile
        # TODO: Add logic to refresh if profile is too old (e.g., 24 hours)
        # For now, always return cached if exists.
        return db_user

    print(f"Resolving new profile for DID: {did}")
    # Mock Bluesky API call. In a real scenario, you'd call
    # `https://api.bsky.app/xrpc/com.atproto.identity.resolveHandle` or
    # `https://api.bsky.app/xrpc/app.bsky.actor.getProfile`
    # For now, let's just create a dummy user or make a mock HTTP call.

    # Example: Mocking a successful Bluesky API response
    # In a real app, you would make an actual HTTP request to Bluesky API
    # async with httpx.AsyncClient() as client:
    #     try:
    #         # Example: Using getProfile
    #         response = await client.get(f"{BLUESKY_API_BASE_URL}/app.bsky.actor.getProfile?actor={did}")
    #         response.raise_for_status() # Raise an exception for bad status codes
    #         profile_data = response.json()
    #         handle = profile_data.get('handle', f"unknown.bsky.social_{did[:8]}")
    #         display_name = profile_data.get('displayName')
    #         avatar_url = profile_data.get('avatar')
    #     except httpx.HTTPStatusError as e:
    #         print(f"HTTP error resolving profile {did}: {e.response.status_code} - {e.response.text}")
    #         handle = f"error.bsky.social_{did[:8]}" # Fallback handle
    #         display_name = None
    #         avatar_url = None
    #     except httpx.RequestError as e:
    #         print(f"Network error resolving profile {did}: {e}")
    #         handle = f"network_error.bsky.social_{did[:8]}"
    #         display_name = None
    #         avatar_url = None

    # For demonstration, let's create a simple mock user
    handle = f"user-{did.split(':')[-1][:8]}.bsky.social"
    display_name = f"User {did.split(':')[-1][:4]}"
    avatar_url = f"https://example.com/avatars/{did.split(':')[-1][:8]}.jpg"


    user_data = schemas.UserCreate(
        did=did,
        handle=handle,
        display_name=display_name,
        avatar_url=avatar_url
    )
    return crud.create_user(db, user_data)


# --- Post Processing & Ingestion ---
async def process_and_ingest_post(db: Session, raw_post_record: Dict[str, Any]):
    """
    Processes a raw Bluesky AT Protocol post record, extracts relevant data,
    resolves author profile, and saves the post to the database.
    """
    uri = raw_post_record.get('uri')
    cid = raw_post_record.get('cid')
    author_did = raw_post_record.get('author')
    record = raw_post_record.get('record', {})
    text = record.get('text', '')
    created_at_str = record.get('createdAt')

    if not all([uri, cid, author_did, text, created_at_str]):
        print(f"Skipping malformed post record: {raw_post_record.get('uri', 'N/A')}")
        return

    # Check if post already exists
    existing_post = crud.get_post_by_uri(db, uri)
    if existing_post:
        # print(f"Post {uri} already ingested. Skipping.")
        return # Skip if already exists

    print(f"Ingesting new post: {uri} by {author_did}")

    # Resolve author profile (will cache if new)
    await resolve_profile(db, author_did) # Ensure user exists in DB

    # Parse created_at datetime
    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00')) # Handle 'Z' for UTC

    # Extracting embedded content (simplified for demonstration)
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
    
    # A more robust parser would go here
    # For now, let's do a very basic hashtag extraction
    for word in text.split():
        if word.startswith('#') and len(word) > 1:
            hashtags.append(word.lower())

    # Mock embeds logic (you'd parse `record.embed` in real data)
    mock_embeds = raw_post_record.get('record', {}).get('embed', {})
    if mock_embeds and mock_embeds.get('$type') == 'app.bsky.embed.images#view':
        has_image = True
        # image_url = mock_embeds['images'][0]['fullsize'] if mock_embeds.get('images') else None # Example
        image_url = f"https://example.com/images/{uuid.uuid4()}.jpg" # Mock URL
    elif mock_embeds and mock_embeds.get('$type') == 'app.bsky.embed.external#view':
        has_link = True
        link_data = mock_embeds.get('external', {})
        link_title = link_data.get('title')
        link_description = link_data.get('description')
        link_thumbnail_url = link_data.get('thumb')
        if link_data.get('uri'):
            links.append({"uri": link_data['uri'], "title": link_title, "description": link_description, "thumb": link_thumbnail_url})

    # Mock mentions logic (you'd parse `record.facets` for mentions in real data)
    # For simplicity, if text contains "@user", mock a mention.
    if '@' in text:
        has_mention = True
        # In a real app, you'd resolve DID from handle for mentions and get the user's display name
        mentions.append({"did": "did:plc:mockdid", "handle": "@mockuser", "name": "Mock User"})


    post_data = schemas.PostCreate(
        uri=uri,
        cid=cid,
        text=text,
        created_at=created_at,
        author_did=author_did,
        has_image=has_image,
        has_video=has_video, # This would need more sophisticated embed parsing
        has_link=has_link,
        has_quote=has_quote, # This would need more sophisticated embed parsing
        has_mention=has_mention,
        image_url=image_url,
        link_title=link_title,
        link_description=link_description,
        link_thumbnail_url=link_thumbnail_url,
        hashtags=hashtags if hashtags else None, # Store as None if empty list
        links=links if links else None,
        mentions=mentions if mentions else None,
        embeds=mock_embeds if mock_embeds else None,
        raw_record=raw_post_record # Store full raw record for completeness
    )

    db_post = crud.create_post(db, post_data)
    if db_post:
        # Now, link the post to relevant feeds based on config
        await link_post_to_feeds(db, db_post)


async def link_post_to_feeds(db: Session, post: models.Post):
    """
    Links an ingested post to relevant feeds based on the feeds configuration and post content.
    """
    # In a real application, you'd apply the `criteria` from feeds_config
    # (e.g., keywords, included_tiers, min_likes) to filter which posts
    # belong to which feeds.

    # For demonstration, link all posts to the "home" feed and any feed
    # that matches a hashtag or keyword in the post text.
    feed_ids_to_link = set()
    feed_ids_to_link.add("home") # Always include in a default 'home' feed

    # Simple keyword/hashtag matching
    post_text_lower = post.text.lower()
    for feed_conf in feeds_config:
        if feed_conf.criteria and feed_conf.criteria.get('keywords'):
            feed_keywords = [k.lower() for k in feed_conf.criteria['keywords']]
            if any(keyword in post_text_lower for keyword in feed_keywords):
                feed_ids_to_link.add(feed_conf.id)
        # TODO: Add logic for 'include_tiers', 'min_likes', 'min_reposts' etc.
        # This would require fetching author's tier, post likes/reposts.

    for feed_id in feed_ids_to_link:
        # Check if FeedPost already exists for this post and feed to prevent duplicates
        # The unique constraint in models.py (when enabled) handles this at DB level
        # but a pre-check can reduce transaction overhead.
        # This logic is simplified for now. crud.create_feed_post handles rollback on error.
        feed_post_data = schemas.FeedPostCreate(post_id=post.id, feed_id=feed_id)
        crud.create_feed_post(db, feed_post_data)


# --- Mock Firehose Listener ---
async def mock_bluesky_firehose_listener():
    """
    A mock function that simulates listening to the Bluesky firehose.
    In a real application, this would be a WebSocket client connecting to the AT Protocol firehose.
    For demonstration, it yields dummy post data periodically.
    """
    counter = 0
    while True:
        counter += 1
        now = datetime.now(timezone.utc)
        mock_did = f"did:plc:mockauthor{counter}"
        mock_handle = f"mockuser{counter}.bsky.social"
        mock_uri = f"at://{mock_did}/app.bsky.feed.post/mockpost{counter}"
        mock_cid = f"bafyreig{counter}abcdefghijklmnopqrstuvwxyz"

        # Simulate a post with some variability
        if counter % 5 == 0: # Every 5th post has a hashtag
            text = f"This is a mock post number {counter} from {mock_handle} about #mockdata and #fastapi. #bluesky"
        elif counter % 7 == 0: # Every 7th post has a mock image embed
             text = f"Here's a cool image for post {counter} by {mock_handle}!"
             embed = {
                 "$type": "app.bsky.embed.images#view",
                 "images": [
                     {"alt": "A cool image", "fullsize": f"https://example.com/images/mock_image_{counter}.jpg"}
                 ]
             }
        elif counter % 11 == 0: # Every 11th post has a mock link embed
            text = f"Check out this interesting link for post {counter}: https://example.com/article/{counter}"
            embed = {
                "$type": "app.bsky.embed.external#view",
                "external": {
                    "uri": f"https://example.com/article/{counter}",
                    "title": f"Mock Article {counter}",
                    "description": f"A description for mock article {counter} on {mock_handle}'s blog.",
                    "thumb": f"https://example.com/thumbs/mock_thumb_{counter}.jpg"
                }
            }
        else:
            text = f"Hello from mock Bluesky firehose! This is post {counter} by {mock_handle}."
            embed = None

        mock_post_record = {
            "uri": mock_uri,
            "cid": mock_cid,
            "author": mock_did,
            "record": {
                "$type": "app.bsky.feed.post",
                "text": text,
                "createdAt": now.isoformat().replace('+00:00', 'Z'), # ISO 8601 with Z for UTC
                "embed": embed # Add mock embed if present
            },
            # In a real firehose, there's more metadata like 'seq', 'takedown', etc.
        }
        yield mock_post_record
        await asyncio.sleep(WORKER_POLLING_INTERVAL_SECONDS) # Simulate delay


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

        # --- Example Aggregation: Top Hashtags ---
        # Get posts for this feed from the last 24 hours
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
        top_n = 10 # Configurable
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
        # - Daily Post Count
        # - etc.
        # Each would involve querying `models.Post` and `models.FeedPost` and then
        # processing the data before saving to `models.Aggregate`.


# --- Main Worker Loop ---
async def run_worker():
    """
    The main asynchronous loop for the aggregator worker.
    It continuously listens for new posts and periodically triggers aggregations.
    """
    print("Starting Aggregator Worker...")
    load_configurations() # Load configs once at startup

    # Initial database setup (for development/testing convenience)
    # In production, use Alembic migrations (as discussed)
    # Base.metadata.create_all(bind=engine)
    # print("Database tables ensured (via create_all). In production, use Alembic migrations.")

    last_aggregation_run = datetime.now(timezone.utc) - timedelta(minutes=AGGREGATION_INTERVAL_MINUTES * 2) # Force first run

    async for raw_post_record in mock_bluesky_firehose_listener():
        db = SessionLocal() # Get a new session for each post/batch
        try:
            await process_and_ingest_post(db, raw_post_record)

            # Check if it's time to run aggregations
            now = datetime.now(timezone.utc)
            if (now - last_aggregation_run).total_seconds() >= AGGREGATION_INTERVAL_MINUTES * 60:
                await run_aggregations(db)
                last_aggregation_run = now
        except Exception as e:
            print(f"Error in worker loop: {e}")
            db.rollback() # Rollback transaction on error
        finally:
            db.close()

if __name__ == "__main__":
    # Ensure the config directory exists for local testing
    os.makedirs(CONFIG_DIR, exist_ok=True)
    # Create dummy config files if they don't exist for easy local testing
    # In a real scenario, these would be managed by your deployment process
    if not os.path.exists(TIERS_CONFIG_PATH):
        with open(TIERS_CONFIG_PATH, 'w') as f:
            json.dump([{"id": "test-tier", "name": "Test Tier", "description": "Desc", "min_followers": 0, "min_posts_daily": 0, "min_reputation_score": 0.0}], f, indent=2)
    if not os.path.exists(FEEDS_CONFIG_PATH):
        with open(FEEDS_CONFIG_PATH, 'w') as f:
            json.dump([{"id": "home", "name": "Home", "description": "Home feed", "criteria": {}}], f, indent=2)


    # Run the worker
    asyncio.run(run_worker())
