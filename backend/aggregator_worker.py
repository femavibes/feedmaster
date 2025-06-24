import os
import asyncio
import websockets
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Import SQLAlchemy components for worker's own DB session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Import models, crud, schemas for database interaction and data validation
import models
import crud
import schemas

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - AGGREGATOR - %(levelname)s - %(message)s')

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/feedmaster_db")
BLUESKY_FIREHOSE_URL = "wss://bsky.social/xrpc/com.atproto.sync.subscribeRepos"

# Tier-based polling intervals (in minutes) for aggregate calculation
TIER_POLLING_RATES = {
    "silver": 60,   # Every hour
    "gold": 15,     # Every 15 minutes
    "platinum": 5   # Every 5 minutes
}

# Define the tier hierarchy for comparison
TIER_ORDER = {
    'silver': 1,
    'gold': 2,
    'platinum': 3
}

# Define which aggregate types are available at which tier (minTier)
# This list is mirrored in the frontend admin for display/selection.
ALL_AGGREGATE_TYPES_METADATA = [
    {'id': 'topHashtags', 'name': 'Top Hashtags', 'minTier': 'silver'},
    {'id': 'topMentions', 'name': 'Top Mentions', 'minTier': 'silver'},
    {'id': 'topPosters', 'name': 'Top Posters', 'minTier': 'silver'},
    {'id': 'topUserImages', 'name': 'Top User Images', 'minTier': 'silver'},
    {'id': 'topUserVideos', 'name': 'Top User Videos', 'minTier': 'silver'},
    {'id': 'topUserShortVideos', 'name': 'Top User Short Videos', 'minTier': 'silver'},
    {'id': 'sentimentAnalysis', 'name': 'Sentiment Analysis Score', 'minTier': 'gold'},
    {'id': 'geoDistribution', 'name': 'Geographical Distribution', 'minTier': 'gold'},
    {'id': 'predictiveTrends', 'name': 'Predictive Trends', 'minTier': 'platinum'},
    # Add other aggregate types here
]


# In-memory storage for the last time each feed's aggregates were calculated
# This helps the scheduler know when to re-run for each feed.
last_aggregation_run: Dict[int, datetime] = {} # {feed_id: datetime_object}

# --- Database Setup for Worker ---
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db_worker() -> Session:
    """Provides a database session for the worker operations."""
    db = SessionLocal()
    try:
        return db
    except Exception as e:
        logging.error(f"Error getting DB session for worker: {e}")
        raise
    # Note: Session needs to be closed manually by the caller in long-running loops or with `finally`

# --- Bluesky Public API Endpoints (copied from initial backend-app-py) ---
BLUESKY_GET_ACTOR_PROFILE_API_URL = 'https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile'
BLUESKY_GET_POSTS_API_URL = 'https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts'

# --- Helper Functions for Bluesky API Interaction (as in previous backend-app-py) ---
async def fetch_bluesky_actor_profile_details(actor_identifier: str) -> Dict[str, Any]:
    """Fetches Bluesky actor (user) profile details."""
    try:
        # Use asyncio.to_thread for blocking HTTP requests in async context
        response = await asyncio.to_thread(requests.get, f"{BLUESKY_GET_ACTOR_PROFILE_API_URL}?actor={actor_identifier}")
        response.raise_for_status()
        profile_data = response.json()
        return {
            "handle": profile_data.get('handle'),
            "displayName": profile_data.get('displayName'),
            "avatar": profile_data.get('avatar'),
            "description": profile_data.get('description')
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Bluesky actor profile for {actor_identifier}: {e}")
        return {}

def generate_bluesky_post_link(post_uri: str) -> Optional[str]:
    """Generates a human-readable Bluesky app link for a given AT URI."""
    try:
        parts = post_uri.split('/')
        if len(parts) >= 5 and parts[0] == 'at:' and parts[2] == 'app.bsky.feed.post':
            did = parts[1]
            rkey = parts[4]
            return f"https://bsky.app/profile/{did}/post/{rkey}"
        logging.warning(f"Could not parse Bluesky URI for link generation: {post_uri}")
        return None
    except Exception as e:
        logging.error(f"Error generating Bluesky post link for {post_uri}: {e}")
        return None

async def fetch_bluesky_post_details(post_uri: str) -> Dict[str, Any]:
    """Fetches Bluesky post details and extracts media info."""
    try:
        response = await asyncio.to_thread(requests.get, f"{BLUESKY_GET_POSTS_API_URL}?uris={post_uri}")
        response.raise_for_status()
        posts_data = response.json()

        if not posts_data or not posts_data.get('posts'):
            logging.warning(f"No posts found for URI: {post_uri}")
            return {}

        post = posts_data['posts'][0]
        record = post.get('record', {})
        author = post.get('author', {})
        
        post_text = record.get('text', '')
        media_type = 'text_only'
        media_url = None
        thumbnail_url = None
        
        bluesky_post_link = generate_bluesky_post_link(post_uri)

        embed = record.get('embed')
        if embed:
            if embed.get('$type') == 'app.bsky.embed.images#view':
                if embed.get('images'):
                    media_type = 'image'
                    media_url = embed['images'][0].get('fullsize') or embed['images'][0].get('thumb')
                    thumbnail_url = embed['images'][0].get('thumb')
            elif embed.get('$type') == 'app.bsky.embed.video#view':
                # Native Bluesky video: Public API does not expose direct playable URL
                media_url = None 
                thumbnail_url = None # Not directly exposed for this embed type
                video_metadata = embed.get('video', {})
                aspect_ratio = video_metadata.get('aspectRatio')
                width = aspect_ratio.get('width') if aspect_ratio else None
                height = aspect_ratio.get('height') if aspect_ratio else None

                if width and height:
                    ratio = height / width
                    if ratio >= (16 / 9) * 0.9: # Approximately 9:16 or taller
                        media_type = 'short_video'
                    else:
                        media_type = 'video'
                else:
                    media_type = 'video'
                logging.debug(f"Detected native Bluesky video. Type: {media_type}, AR: {width}x{height}")

            elif embed.get('$type') == 'app.bsky.embed.external#view':
                external = embed.get('external', {})
                external_uri = external.get('uri')
                if external_uri and any(domain in external_uri for domain in ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com']):
                    media_type = 'video'
                    media_url = external_uri
                    thumbnail_url = external.get('thumb')
                elif external.get('thumb'):
                    media_type = 'image'
                    media_url = external.get('thumb')
                    thumbnail_url = external.get('thumb')
            elif embed.get('$type') == 'app.bsky.embed.recordWithMedia#view':
                media_embed_part = embed.get('media')
                if media_embed_part:
                    if media_embed_part.get('$type') == 'app.bsky.embed.images#view':
                        if media_embed_part.get('images'):
                            media_type = 'image'
                            media_url = media_embed_part['images'][0].get('fullsize') or media_embed_part['images'][0].get('thumb')
                            thumbnail_url = media_embed_part['images'][0].get('thumb')
                    elif media_embed_part.get('$type') == 'app.bsky.embed.external#view':
                        external = media_embed_part.get('external', {})
                        external_uri = external.get('uri')
                        if external_uri and any(domain in external_uri for domain in ['youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com']):
                            media_type = 'video'
                            media_url = external_uri
                            thumbnail_url = external.get('thumb')
                        elif external.get('thumb'):
                            media_type = 'image'
                            media_url = external.get('thumb')
                            thumbnail_url = external.get('thumb')

        return {
            "post_uri": post_uri,
            "post_link": bluesky_post_link,
            "post_text": post_text,
            "original_poster_did": author.get('did'),
            "original_poster_handle": author.get('handle'),
            "original_poster_display_name": author.get('displayName'),
            "original_poster_avatar_url": author.get('avatar'),
            "media_type": media_type,
            "media_url": media_url,
            "thumbnail_url": thumbnail_url,
        }
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Bluesky post details for {post_uri}: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error processing post response for {post_uri}: {e}")
        return {}

# --- Contrails Listener ("Worker 1") ---

# In-memory store for raw incoming data relevant to aggregation
# This would be more sophisticated in a real app (e.g., Kafka, Redis Streams)
# For simplicity, we'll collect recent URIs/DIDs.
raw_data_buffer = {
    "posts": [], # list of {uri, did, text, media_type, engagement_score}
    "likes": [], # list of {subject_uri, liker_did}
    "reposts": [], # list of {subject_uri, reposter_did}
    "follows": [] # list of {actor_did, target_did}
}
BUFFER_RETENTION_SECONDS = max(TIER_POLLING_RATES.values()) * 60 + 300 # Keep data for longest polling + 5 min buffer

async def parse_and_buffer_message(message: bytes, db_session: Session):
    """
    Parses a raw message from Contrails and buffers relevant data
    after resolving DIDs and post metadata.
    """
    try:
        # AT Protocol messages are CBOR encoded, then framed.
        # This is a *highly simplified placeholder* for parsing.
        # A real implementation would use a library like `atproto.xrpc_sync_client`
        # or implement a full AT Protocol lexer/parser.
        # For now, we assume we can extract basic post info for demonstration.

        # Simulate parsing to extract a post_uri and author DID
        # In reality, this involves iterating `repo_ops` in `commit` messages
        # and checking for `app.bsky.feed.post` records.
        
        # Dummy data for demonstration
        if b'app.bsky.feed.post' in message:
            # This is a very crude way to detect a post, will fail often.
            # Replace with proper AT Protocol parsing!
            sample_post_uri = f"at://did:plc:sample{datetime.now().timestamp()}/app.bsky.feed.post/dummy"
            sample_author_did = f"did:plc:sample_user{datetime.now().second}"
            
            # Resolve and cache the author's profile
            profile_data = await fetch_bluesky_actor_profile_details(sample_author_did)
            if profile_data:
                profile_schema = schemas.UserProfileCacheCreate(
                    did=sample_author_did,
                    handle=profile_data.get('handle'),
                    display_name=profile_data.get('displayName'),
                    avatar_url=profile_data.get('avatar')
                )
                crud.create_or_update_user_profile_cache(db_session, profile_schema)
                logging.debug(f"Cached profile for {sample_author_did}.")

            # Resolve and cache post metadata
            post_details = await fetch_bluesky_post_details(sample_post_uri)
            if post_details:
                post_schema = schemas.PostMetadataCacheCreate(
                    post_uri=post_details.get('post_uri'),
                    post_link=post_details.get('post_link'),
                    original_poster_did=post_details.get('original_poster_did'),
                    original_poster_handle=post_details.get('original_poster_handle'),
                    original_poster_display_name=post_details.get('original_poster_display_name'),
                    original_poster_avatar_url=post_details.get('original_poster_avatar_url'),
                    media_type=post_details.get('media_type'),
                    media_url=post_details.get('media_url'),
                    thumbnail_url=post_details.get('thumbnail_url'),
                    post_text=post_details.get('post_text')
                )
                crud.create_or_update_post_metadata_cache(db_session, post_schema)
                logging.debug(f"Cached post metadata for {sample_post_uri}.")

                # Add to buffer for later aggregation
                raw_data_buffer["posts"].append({
                    "uri": post_details["post_uri"],
                    "did": post_details["original_poster_did"],
                    "media_type": post_details["media_type"],
                    "timestamp": datetime.now(timezone.utc),
                    "text": post_details["post_text"]
                })
        
        # Simulate processing other types of events like likes, reposts, follows
        # This would require deeper parsing of AT Protocol messages.
        # For demo, just log if it's a "commit"
        if b'op":1' in message[:8]: # Crude check for commit header
            logging.debug(f"Raw Contrails commit received: {message[:100]}...") # Log first 100 bytes
        
        # Clean up old data from buffer
        now = datetime.now(timezone.utc)
        for key in raw_data_buffer:
            raw_data_buffer[key] = [
                item for item in raw_data_buffer[key]
                if (now - item["timestamp"]).total_seconds() < BUFFER_RETENTION_SECONDS
            ]

    except Exception as e:
        logging.error(f"Error parsing or buffering Contrails message: {e}")

async def listen_to_contrails(db_session: Session):
    """Worker 1: Connects to the Bluesky Firehose and continuously listens for messages."""
    logging.info("Worker 1: Connecting to Bluesky Firehose...")
    while True:
        try:
            async with websockets.connect(BLUESKY_FIREHOSE_URL, ping_interval=None) as websocket:
                logging.info("Worker 1: Connected to Bluesky Firehose. Listening for events...")
                while True:
                    try:
                        message = await websocket.recv()
                        # Process message in a non-blocking way
                        await parse_and_buffer_message(message, db_session)
                    except websockets.exceptions.ConnectionClosed:
                        logging.warning("Worker 1: Bluesky Firehose connection closed. Reconnecting...")
                        break
                    except Exception as e:
                        logging.error(f"Worker 1: Error receiving from websocket: {e}. Reconnecting in 5s...")
                        await asyncio.sleep(5)
                        break
        except Exception as e:
            logging.error(f"Worker 1: Failed to connect to Bluesky Firehose: {e}. Retrying in 10s...")
            await asyncio.sleep(10)

# --- Aggregate Calculator ("Worker 2") ---

async def calculate_aggregates_for_feed(feed_db_obj: models.Feed, db_session: Session):
    """
    Worker 2 Helper: Calculates and stores aggregates for a single feed based on its tier
    and available data in the raw_data_buffer and cache tables.
    """
    feed_id = feed_db_obj.id
    feed_name = feed_db_obj.name
    feed_tier = feed_db_obj.owner.tier # Access tier from the relationship

    logging.info(f"Worker 2: Calculating aggregates for feed '{feed_name}' (ID: {feed_id}, Tier: {feed_tier})...")

    # --- Implement Actual Aggregation Logic Here ---
    # This is the most complex part of the backend. It needs to:
    # 1. Query the `raw_data_buffer` (or ideally, a more persistent stream/queue)
    #    and the `UserProfileCache`/`PostMetadataCache` tables for relevant data
    #    within the last polling interval for this feed's tier.
    # 2. Perform the actual counts/calculations for each aggregate type.
    # 3. Apply tier-based filtering for which aggregates to compute.

    # Example: Top Hashtags
    # Get recent posts from buffer, count hashtags
    recent_posts = [p for p in raw_data_buffer["posts"] if (datetime.now(timezone.utc) - p["timestamp"]).total_seconds() <= (TIER_POLLING_RATES.get(feed_tier, TIER_POLLING_RATES["silver"]) * 60)]
    hashtags_count = {}
    for post in recent_posts:
        # Very crude hashtag detection for demo
        for word in post["text"].split():
            if word.startswith('#') and len(word) > 1:
                hashtag = word.lower()
                hashtags_count[hashtag] = hashtags_count.get(hashtag, 0) + 1
    
    top_hashtags = sorted(hashtags_count.items(), key=lambda item: item[1], reverse=True)[:5]
    if top_hashtags:
        feed_data_entry = schemas.FeedDataCreate(
            aggregate_type="topHashtags",
            data={"items": [{"name": h[0], "count": h[1]} for h in top_hashtags]},
            timestamp=datetime.now(timezone.utc)
        )
        crud.create_feed_data(db_session, feed_data_entry, feed_id)
        logging.info(f"Worker 2: Stored 'topHashtags' for feed {feed_name}.")

    # Example: Top Posters
    posters_count = {}
    for post in recent_posts:
        poster_did = post["did"]
        posters_count[poster_did] = posters_count.get(poster_did, 0) + 1
    top_posters = sorted(posters_count.items(), key=lambda item: item[1], reverse=True)[:5]
    if top_posters:
        # For display, frontend will resolve DID to get handle/avatar
        feed_data_entry = schemas.FeedDataCreate(
            aggregate_type="topPosters",
            data={"items": [{"did": p[0], "count": p[1]} for p in top_posters]},
            timestamp=datetime.now(timezone.utc)
        )
        crud.create_feed_data(db_session, feed_data_entry, feed_id)
        logging.info(f"Worker 2: Stored 'topPosters' for feed {feed_name}.")


    # Example: Top User Images / Videos (using post_uri for engagement count)
    image_posts = [p for p in recent_posts if p["media_type"] == "image"]
    video_posts = [p for p in recent_posts if p["media_type"] == "video"]
    short_video_posts = [p for p in recent_posts if p["media_type"] == "short_video"]

    # This 'engagement_score' for posts would come from parsing likes/reposts/comments in Contrails
    # For now, let's just count posts themselves.
    def get_top_media_posts(media_list: List[Dict[str, Any]], agg_type_name: str):
        # In a real system, you'd get actual engagement for these posts
        # For demo, assume each post is 1 engagement.
        media_agg = [{"post_uri": p["uri"], "engagement_score": 1} for p in media_list]
        # Sort by engagement_score (which is 1 for now)
        media_agg_sorted = sorted(media_agg, key=lambda x: x["engagement_score"], reverse=True)[:5]
        if media_agg_sorted:
            feed_data_entry = schemas.FeedDataCreate(
                aggregate_type=agg_type_name,
                data={"items": media_agg_sorted},
                timestamp=datetime.now(timezone.utc)
            )
            crud.create_feed_data(db_session, feed_data_entry, feed_id)
            logging.info(f"Worker 2: Stored '{agg_type_name}' for feed {feed_name}.")

    get_top_media_posts(image_posts, "topUserImages")
    get_top_media_posts(video_posts, "topUserVideos")
    get_top_media_posts(short_video_posts, "topUserShortVideos")

    # Example: Sentiment Analysis (Gold/Platinum tier only)
    sentiment_aggregate_meta = next((agg for agg in ALL_AGGREGATE_TYPES_METADATA if agg['id'] == 'sentimentAnalysis'), None)
    if sentiment_aggregate_meta and TIER_ORDER.get(feed_tier, 0) >= TIER_ORDER[sentiment_aggregate_meta['minTier']]:
        # Simulate sentiment analysis on recent posts
        # In a real scenario, you'd send text to an NLP service or use a local model.
        # For demo, just static data.
        sentiment_data = {"positive_score": 0.75, "negative_score": 0.10, "neutral_score": 0.15}
        feed_data_entry = schemas.FeedDataCreate(
            aggregate_type="sentimentAnalysis",
            data={"score_breakdown": sentiment_data},
            timestamp=datetime.now(timezone.utc)
        )
        crud.create_feed_data(db_session, feed_data_entry, feed_id)
        logging.info(f"Worker 2: Stored 'sentimentAnalysis' for feed {feed_name}.")
    else:
        logging.info(f"Worker 2: Sentiment Analysis skipped for tier {feed_tier} for feed {feed_name}.")

    logging.info(f"Worker 2: Finished calculating aggregates for feed '{feed_name}'.")


async def aggregate_worker_loop():
    """Worker 2: Main loop for the aggregate calculation worker."""
    logging.info("Worker 2: Starting aggregate calculation worker loop...")
    
    while True:
        db = get_db_worker() # Get a fresh DB session for each loop iteration
        try:
            active_feeds = crud.get_feeds(db) # Get active feeds and their owner (for tier)
            current_time = datetime.now(timezone.utc)

            for feed_db_obj in active_feeds:
                # Ensure the owner relationship is loaded for tier access
                if not hasattr(feed_db_obj, 'owner') or not feed_db_obj.owner:
                    logging.warning(f"Feed {feed_db_obj.name} (ID: {feed_db_obj.id}) has no associated owner. Skipping aggregation.")
                    continue
                
                feed_id = feed_db_obj.id
                feed_tier = feed_db_obj.owner.tier # Get tier from associated User model
                
                last_run_time = last_aggregation_run.get(feed_id, datetime.min.replace(tzinfo=timezone.utc))
                
                polling_minutes = TIER_POLLING_RATES.get(feed_tier, TIER_POLLING_RATES["silver"])
                
                if (current_time - last_run_time) >= timedelta(minutes=polling_minutes):
                    logging.info(f"Worker 2: Triggering aggregate calculation for feed ID {feed_id} (Tier: {feed_tier})...")
                    await calculate_aggregates_for_feed(feed_db_obj, db)
                    last_aggregation_run[feed_id] = current_time # Update last run time
                else:
                    logging.debug(f"Worker 2: Feed ID {feed_id} (Tier: {feed_tier}) not due for aggregation yet. Next run in approx. {int((last_run_time + timedelta(minutes=polling_minutes) - current_time).total_seconds() / 60)} minutes.")
            
            # Determine the shortest polling interval to sleep for
            min_sleep_seconds = min(TIER_POLLING_RATES.values()) * 60
            logging.debug(f"Worker 2: Sleeping for {min_sleep_seconds} seconds until next check...")
            await asyncio.sleep(min_sleep_seconds)

        except Exception as e:
            logging.critical(f"Worker 2: Critical error in aggregate worker loop: {e}")
            await asyncio.sleep(60) # Sleep longer on critical error before retrying
        finally:
            db.close() # Ensure DB session is closed after each iteration

# --- Main Entry Point for the Aggregator Worker ---
async def main():
    # Ensure database tables are created before starting workers
    models.Base.metadata.create_all(bind=engine)
    logging.info("Database tables ensured to exist for worker.")
    
    # The Contrails listener and Aggregate Calculator will run concurrently.
    # We need to create separate DB sessions for each concurrent task if they are
    # long-running and operate independently, to avoid issues with shared session state
    # across async tasks.
    
    # Or, if they truly share state/transaction, manage it carefully.
    # For simplicity of demonstration, let's create two separate DB sessions that
    # are managed within their respective async functions.
    
    # We'll pass a session that each coroutine manages (opens/closes as needed).
    # For `listen_to_contrails`, it opens/closes connection within its `async with websockets.connect` loop.
    # For `aggregate_worker_loop`, it opens/closes session for each outer loop iteration.

    # Start both workers
    await asyncio.gather(
        listen_to_contrails(get_db_worker()), # Pass a fresh session for the listener
        aggregate_worker_loop() # The loop itself manages its session
    )

if __name__ == "__main__":
    asyncio.run(main())
