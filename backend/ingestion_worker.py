# backend/ingestion_worker.py
#
# This worker is solely responsible for:
# 1. Connecting to Graze Contrails WebSockets for configured feeds.
# 2. Receiving raw post data from the Contrails stream.
# 3. Resolving DIDs to user profiles (using the Bluesky API) with caching and
#    periodic refresh for active DIDs (including those identified as prominent by the aggregator).
# 4. Enriching post data by resolving embedded content (images, external links,
#    and now, importantly, **full quoted post details and video embeds**).
# 5. Saving fully enriched posts and updated user profiles to the database.

import asyncio
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
import websockets
import urllib.parse
from contextlib import asynccontextmanager

from backend.database import AsyncSessionLocal, get_db # Changed get_db to async
from backend import crud, schemas, models, profile_resolver # Import the new resolver
from backend.models import Base
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy import text, select, update # For raw SQL execution if needed

# Configuration constants
CONFIG_DIR = "config"
FEEDS_CONFIG_PATH = os.path.join(CONFIG_DIR, "feeds.json")

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variable for feeds configuration
feeds_config: List[schemas.FeedBase] = []

# Batching configuration
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100)) # Number of records per batch
BATCH_INTERVAL_SECONDS = int(os.getenv("BATCH_INTERVAL_SECONDS", 5)) # Time in seconds to wait before flushing a batch
# Queues for batching
post_batch_queue: asyncio.Queue[Tuple[schemas.PostCreate, str]] = asyncio.Queue()
feed_post_batch_queue: asyncio.Queue[schemas.FeedPostCreate] = asyncio.Queue()

# --- NEW HELPER FUNCTION ---
def resolve_bluesky_cdn_url(author_did: str, blob_data: Dict[str, Any]) -> Optional[str]:
    """
    Constructs a Bluesky CDN URL for an image blob based on its ref (CID) and mimeType.
    """
    if not isinstance(blob_data, dict) or blob_data.get('$type') != 'blob':
        logging.warning(f"Invalid blob_data format: {blob_data}")
        return None

    blob_ref = blob_data.get('ref')
    mime_type = blob_data.get('mimeType')

    if not isinstance(blob_ref, dict) or '$link' not in blob_ref:
        logging.warning(f"Blob reference missing '$link': {blob_ref}")
        return None

    if not mime_type:
        logging.warning(f"Blob mimeType missing for blob ref: {blob_ref}")
        mime_type = "image/jpeg" # Default to jpeg if mimeType is missing

    cid = blob_ref['$link']
    ext = mime_type.split('/')[-1] if '/' in mime_type else 'jpeg'
    if ext in ['image', 'svg+xml']:
        ext = 'jpeg'
    return f"https://cdn.bsky.app/img/feed_thumbnail/plain/{author_did}/{cid}@{ext}"

def _parse_image_embed(images_data: List[Dict[str, Any]], author_did: str) -> Dict[str, Any]:
    """
    Parses a list of image objects from an embed, creating a list of all image URLs
    with their corresponding alt text. Also returns a flag indicating if any image has alt text.
    """
    if not images_data:
        return {}

    images_list = []
    has_alt_text = False

    for img_data in images_data:
        image_url = None
        if blob := img_data.get('image'):
            image_url = resolve_bluesky_cdn_url(author_did, blob)
        elif fullsize_url := img_data.get('fullsize'):
            image_url = fullsize_url

        if image_url:
            alt_text = img_data.get('alt', '').strip()
            if alt_text:
                has_alt_text = True
            images_list.append({"url": image_url, "alt": alt_text or None})

    return {"has_image": bool(images_list), "images": images_list, "has_alt_text": has_alt_text}

def _parse_quoted_post_details(record_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Parses the details of a quoted post from its embed record."""
    if not record_data:
        return {}

    quoted_post_value = record_data.get('value', {})
    author_profile = quoted_post_value.get('author', {})
    
    created_at = None
    if created_at_str := quoted_post_value.get("createdAt"):
        try:
            parsed_time = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            # Validate against future timestamps for quoted posts too
            current_time = datetime.now(timezone.utc)
            if parsed_time <= current_time + timedelta(minutes=5):  # Allow 5 min clock skew
                created_at = parsed_time
        except (ValueError, TypeError):
            pass # Ignore parsing errors

    return {
        "quoted_post_uri": record_data.get('uri'),
        "quoted_post_cid": record_data.get('cid'),
        "quoted_post_author_did": author_profile.get('did'),
        "quoted_post_author_handle": author_profile.get('handle'),
        "quoted_post_author_display_name": author_profile.get('displayName'),
        "quoted_post_text": quoted_post_value.get('text'),
        "quoted_post_like_count": quoted_post_value.get('likeCount', 0),
        "quoted_post_repost_count": quoted_post_value.get('repostCount', 0),
        "quoted_post_reply_count": quoted_post_value.get('replyCount', 0),
        "quoted_post_created_at": created_at,
    }

def _parse_video_embed(video_embed_data: Dict[str, Any], author_did: str) -> Dict[str, Any]:
    """
    Parses a video embed, extracting aspect ratio and thumbnail URL.
    It prioritizes an explicit 'thumb' blob but falls back to constructing
    a URL from the main video blob if 'thumb' is not present.
    """
    if not video_embed_data:
        return {}

    results = {
        "has_video": False,
        "thumbnail_url": None,
        "aspect_ratio_width": None,
        "aspect_ratio_height": None,
    }

    video_blob = video_embed_data.get('video')
    if not (video_blob and video_blob.get('$type') == 'blob'):
        return results
    
    results["has_video"] = True

    if thumb_blob := video_embed_data.get('thumb'):
        results["thumbnail_url"] = resolve_bluesky_cdn_url(author_did, thumb_blob)
    elif video_ref := video_blob.get('ref'):
        if video_cid := video_ref.get('$link'):
            results["thumbnail_url"] = f"https://video.cdn.bsky.app/hls/{author_did}/{video_cid}/thumbnail.jpg"

    if aspect_ratio := video_embed_data.get('aspectRatio'):
        results["aspect_ratio_width"] = aspect_ratio.get('width')
        results["aspect_ratio_height"] = aspect_ratio.get('height')
            
    return results

# --- Helper function for database session ---
# This async context manager will provide a clean async session for any async function
@asynccontextmanager
async def get_async_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# --- Config Management ---
async def load_configurations():
    """Loads feed configurations from a JSON file or the database."""
    global feeds_config
    
    # Prioritize database feeds if available, otherwise fall back to file
    try:
        async with AsyncSessionLocal() as db:
            db_feeds = await crud.get_all_feeds(db)
        
        if db_feeds:
            # Convert model objects to Pydantic schemas for consistency
            feeds_config = [schemas.FeedsConfig.from_orm(f) for f in db_feeds]
            logger.info(f"Loaded {len(feeds_config)} feed configurations from database.")
            return
    except Exception as e:
        logger.warning(f"Could not load feeds from database at startup: {e}. Falling back to file.")

    if os.path.exists(FEEDS_CONFIG_PATH):
        with open(FEEDS_CONFIG_PATH, 'r') as f:
            file_configs = json.load(f)
            # Use FeedsConfig which doesn't require created_at/updated_at,
            # avoiding the Pydantic validation error. It inherits from FeedBase.
            feeds_config = [schemas.FeedsConfig(**cfg) for cfg in file_configs]
            logger.info(f"Loaded {len(feeds_config)} feed configurations from file: {FEEDS_CONFIG_PATH}")
    else:
        logger.warning(f"No feeds.json found at {FEEDS_CONFIG_PATH} and no feeds in DB. No feeds will be processed.")


# --- Data Processing Functions ---

async def process_firehose_message(message: Dict[str, Any], feed_id: str):
    """
    Processes a single firehose message, extracts relevant data,
    and adds it to respective batch queues.
    """
    # Contrails format: 'commit' object and top-level 'did'
    commit_data = message.get("commit")
    author_did = message.get("did")

    if not commit_data or not author_did:
        logger.debug(f"Contrails data for feed {feed_id} missing 'commit' key or top-level 'did'.")
        return

    # The post content is inside the 'record'
    post_record = commit_data.get("record", {})
    if post_record.get("$type") != "app.bsky.feed.post":
        return  # Not a post record

    cid = commit_data.get("cid")
    rkey = commit_data.get("rkey")
    uri = f"at://{author_did}/app.bsky.feed.post/{rkey}" if author_did and rkey else None
    created_at_str = post_record.get("createdAt")
    text = post_record.get("text", "")

    if not all([uri, cid, created_at_str]):
        logger.info(f"Skipping malformed post from Contrails for feed {feed_id}: Missing required fields.")
        return

    # Parse created_at with timezone awareness and validate against future timestamps
    try:
        # Python's fromisoformat can fail on >6 microsecond digits.
        # This safely truncates the fractional part before parsing.
        if '.' in created_at_str:
            main_part, fractional_part = created_at_str.split('.', 1)
            # Remove Z, truncate, and re-add timezone info
            fractional_part = fractional_part.rstrip('Z')
            truncated_fractional = fractional_part[:6]
            reformatted_str = f"{main_part}.{truncated_fractional}+00:00"
            created_at = datetime.fromisoformat(reformatted_str)
        else:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        
        # Validate against future timestamps (AT Protocol allows any timestamp)
        current_time = datetime.now(timezone.utc)
        if created_at > current_time + timedelta(minutes=5):  # Allow 5 min clock skew
            logger.warning(f"Rejecting post {uri} with future timestamp: {created_at} (current: {current_time})")
            return
            
    except (ValueError, TypeError):
        logger.warning(f"Could not parse created_at timestamp: {post_record.get('createdAt')} for post {uri}")
        return

    # Image, Video, Link, Quote, Mention detection
    has_image = False
    has_video = False
    has_link = False
    has_quote = False
    has_mention = False
    image_details = {}
    video_details = {}
    link_url = None
    link_title = None
    link_description = None
    thumbnail_url = None # Initialize to handle posts without link cards
    hashtags = []
    links = [] # List of LinkDetails
    link_uris_seen = set() # Keep track of URIs to avoid duplicates
    mentions = [] # List of Mentions
    embeds = None
    quoted_post_details = {}

    # --- Capture raw facets ---
    facets = post_record.get("facets")

    # Process facets for links and mentions
    if facets and isinstance(facets, list):
        for facet in facets:
            for feature in facet.get("features", []):
                feature_type = feature.get("$type")
                if feature_type == "app.bsky.richtext.facet#link":
                    has_link = True
                    link_uri = feature["uri"]
                    if link_uri not in link_uris_seen:
                        links.append(schemas.LinkDetails(uri=link_uri))
                        link_uris_seen.add(link_uri)
                    # If link_url is not already set by a rich embed, use the facet URI.
                    if not link_url:
                        link_url = link_uri
                elif feature_type == "app.bsky.richtext.facet#mention":
                    has_mention = True
                    mentions.append(schemas.Mention(did=feature["did"]))
                elif feature_type == "app.bsky.richtext.facet#tag":
                    if "tag" in feature:
                        hashtags.append(feature["tag"])

    # --- REVISED EMBED PARSING LOGIC ---
    if "embed" in post_record:
        embed_data = post_record["embed"]
        embeds = embed_data # Store raw embed data

        # Log the embed if a link is detected, to debug missing card data
        if has_link:
            logger.info(f"Link detected for post {uri}. Inspecting embed: {json.dumps(embed_data)}")

        embed_type = embed_data.get('$type')
        if embed_type == 'app.bsky.embed.external':
            external_embed = embed_data.get('external')
            if external_embed:
                has_link = True
                link_url = external_embed.get('uri')
                link_title = external_embed.get('title')
                link_description = external_embed.get('description')
                # NEW: Use the consolidated thumbnail_url field
                thumb_data = external_embed.get('thumb')
                if isinstance(thumb_data, dict) and thumb_data.get('$type') == 'blob': # This is now only for link cards
                    thumbnail_url = resolve_bluesky_cdn_url(author_did, thumb_data)
                elif isinstance(thumb_data, str):
                    thumbnail_url = thumb_data
                if link_url and link_url not in link_uris_seen:
                    links.append(schemas.LinkDetails(uri=link_url))
                    link_uris_seen.add(link_url)
        elif embed_type == 'app.bsky.embed.record':
            has_quote = True
            if record_data := embed_data.get('record'):
                quoted_post_details = _parse_quoted_post_details(record_data)
        elif embed_type == 'app.bsky.embed.recordWithMedia':
            has_quote = True
            # The 'record' field of a recordWithMedia is itself a record embed.
            record_embed = embed_data.get('record')
            if record_embed and record_embed.get('$type') == 'app.bsky.embed.record':
                if record_data := record_embed.get('record'):
                    quoted_post_details = _parse_quoted_post_details(record_data)
            media = embed_data.get('media')
            if media:
                media_type = media.get('$type')
                # This block now only handles non-image media types
                if media_type == 'app.bsky.embed.external':
                    external_media = media.get('external')
                    if external_media:
                        has_link = True
                        link_url = external_media.get('uri')
                        link_title = external_media.get('title')
                        link_description = external_media.get('description')
                        # NEW: Use the consolidated thumbnail_url field
                        thumb_data = external_media.get('thumb')
                        if isinstance(thumb_data, dict) and thumb_data.get('$type') == 'blob': # This is now only for link cards
                            thumbnail_url = resolve_bluesky_cdn_url(author_did, thumb_data)
                        elif isinstance(thumb_data, str):
                            thumbnail_url = thumb_data
                        if link_url and link_url not in link_uris_seen:
                            links.append(schemas.LinkDetails(uri=link_url))
                            link_uris_seen.add(link_url)
        
        # --- Centralized Video Parsing ---
        video_to_parse = None
        if embed_type == 'app.bsky.embed.video':
            video_to_parse = embed_data
        elif embed_type == 'app.bsky.embed.recordWithMedia' and embed_data.get('media', {}).get('$type') == 'app.bsky.embed.video':
            video_to_parse = embed_data.get('media')

        if video_to_parse:
            video_details = _parse_video_embed(video_to_parse, author_did)

        # --- Centralized Image Parsing ---
        # This runs after the main embed logic to handle both direct image embeds
        # and images within a recordWithMedia embed.
        images_to_parse = []
        if embed_type == 'app.bsky.embed.images':
            images_to_parse = embed_data.get('images', [])
        elif embed_type == 'app.bsky.embed.recordWithMedia':
            media = embed_data.get('media', {})
            if media.get('$type') == 'app.bsky.embed.images':
                images_to_parse = media.get('images', [])
        
        if images_to_parse:
            image_details = _parse_image_embed(images_to_parse, author_did)
            has_image = image_details.get('has_image', False)

    # Prepare PostCreate schema
    post_schema = schemas.PostCreate(
        uri=uri,
        cid=cid,
        text=text,
        created_at=created_at,
        author_did=author_did,
        **image_details, # Unpacks has_image, images, and has_alt_text
        has_video=video_details.get('has_video', False),
        has_link=has_link,
        has_quote=has_quote,
        has_mention=has_mention,
        thumbnail_url=video_details.get('thumbnail_url') or thumbnail_url, # Prioritize video thumb, fallback to link card thumb
        aspect_ratio_width=video_details.get('aspect_ratio_width'),
        aspect_ratio_height=video_details.get('aspect_ratio_height'),
        link_url=link_url,
        link_title=link_title,
        link_description=link_description,
        hashtags=hashtags,
        links=links,
        mentions=mentions,
        embeds=embeds,
        facets=facets,
        raw_record=post_record, # Store the raw record
        # Defaulting engagement scores and polling fields for new posts
        like_count=0,
        repost_count=0,
        reply_count=0,
        quote_count=0,
        engagement_score=0.0,
        # Set the initial poll time for 5 minutes from now.
        next_poll_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        is_active_for_polling=True,
        quoted_post_uri=quoted_post_details.get('quoted_post_uri'),
        quoted_post_cid=quoted_post_details.get('quoted_post_cid'),
        quoted_post_author_did=quoted_post_details.get('quoted_post_author_did'),
        quoted_post_author_handle=quoted_post_details.get('quoted_post_author_handle'),
        quoted_post_author_display_name=quoted_post_details.get('quoted_post_author_display_name'),
        quoted_post_text=quoted_post_details.get('quoted_post_text'),
        quoted_post_like_count=quoted_post_details.get('quoted_post_like_count', 0),
        quoted_post_repost_count=quoted_post_details.get('quoted_post_repost_count', 0),
        quoted_post_reply_count=quoted_post_details.get('quoted_post_reply_count', 0),
        quoted_post_created_at=quoted_post_details.get('quoted_post_created_at')
    )
    await post_batch_queue.put((post_schema, feed_id))
    # This block was causing a SyntaxError due to `elif` without a preceding `if`.
    # The original intent was likely to handle different message types.
    # Since the `process_firehose_message` function is designed to process
    # 'commit' messages (which are posts), and other message types are
    # currently filtered out or not explicitly handled, this `elif`
    # is out of place.
    # If you intend to handle other message types (like 'handle_change'),
    # you need to introduce a top-level `if` statement to check `message.get("type")`
    # or similar, and then use `elif` for subsequent types.
    # For now, commenting out the problematic `elif` to fix the syntax error.
    # If `event_type` is meant to be derived from `message`, that derivation
    # needs to happen before this conditional block.
    # elif event_type == "handle_change":
        # Handle DID changes, update user table
        # did = message.get("did")
        # new_handle = message.get("handle")
        # logger.info(f"Handle change for DID {did}: new handle is {new_handle}. Triggering profile refresh.")
        # pass
    # else:
    #     logger.debug(f"Received unknown message type: {event_type}")

# --- Batch Processing Workers ---

async def _flush_post_batch(batch: List[Tuple[schemas.PostCreate, str]]):
    """Helper function to de-duplicate, upsert, and link a batch of posts."""
    if not batch:
        return

    # 1. De-duplicate posts by CID and collect all associated feed_ids
    unique_posts_with_feeds: Dict[str, Tuple[schemas.PostCreate, List[str]]] = {}
    for post_schema, feed_id in batch:
        if post_schema.cid not in unique_posts_with_feeds:
            unique_posts_with_feeds[post_schema.cid] = (post_schema, [feed_id])
        else:
            unique_posts_with_feeds[post_schema.cid][1].append(feed_id)

    posts_to_upsert = [post_schema for post_schema, _ in unique_posts_with_feeds.values()]

    async with get_async_db_session() as db:
        # 2. Ensure all authors for the unique posts exist
        author_dids_in_batch = {p.author_did for p in posts_to_upsert}
        if author_dids_in_batch:
            # Check for existing, stale users who just posted and need a refresh.
            dids_to_refresh = await crud.get_stale_user_dids_from_list(db, list(author_dids_in_batch))
            if dids_to_refresh:
                logger.info(f"Found {len(dids_to_refresh)} stale users who just posted. Triggering profile refresh.")
                await profile_resolver.resolve_and_update_profiles(db, dids_to_refresh)

            # Create placeholders for any genuinely new users. This is safe because
            # it uses ON CONFLICT DO NOTHING and won't overwrite existing profiles.
            await crud.create_placeholder_users_batch(db, list(author_dids_in_batch))

        # 3. Upsert the de-duplicated posts
        inserted_posts = await crud.upsert_posts_batch(db, posts_to_upsert)
        logger.info(f"Flushed batch of {len(posts_to_upsert)} unique posts to DB (from {len(batch)} queue items).")
        
        # 4. Link posts to all their respective feeds
        inserted_posts_map = {p.cid: p for p in inserted_posts}
        for cid, (post_schema, feed_ids) in unique_posts_with_feeds.items():
            p = inserted_posts_map.get(cid)
            if p:
                for feed_id in feed_ids:
                    feed_post_batch_queue.put_nowait(schemas.FeedPostCreate(
                        post_id=p.id,
                        feed_id=feed_id,
                        relevance_score=1.0, # Default score
                        ingested_at=datetime.now(timezone.utc)
                    ))
            else:
                logger.warning(f"Could not find post with CID {cid} in upserted batch, can't link to feeds {feed_ids}.")


async def post_batch_worker():
    """Periodically flushes the post batch queue to the database."""
    current_batch: List[Tuple[schemas.PostCreate, str]] = []
    while True:
        try:
            post_tuple = await asyncio.wait_for(post_batch_queue.get(), timeout=BATCH_INTERVAL_SECONDS)
            current_batch.append(post_tuple)

            if len(current_batch) >= BATCH_SIZE:
                await _flush_post_batch(current_batch)
                current_batch = [] # Reset batch
            
        except asyncio.TimeoutError:
            if current_batch:
                await _flush_post_batch(current_batch)
                current_batch = [] # Reset batch
        except Exception as e:
            logger.error(f"Error in post batch worker: {e}", exc_info=True)
            current_batch = []

async def feed_post_batch_worker():
    """Periodically flushes the feed_post batch queue to the database."""
    current_batch: List[schemas.FeedPostCreate] = []
    while True:
        try:
            feed_post = await asyncio.wait_for(feed_post_batch_queue.get(), timeout=BATCH_INTERVAL_SECONDS)
            current_batch.append(feed_post)

            if len(current_batch) >= BATCH_SIZE:
                async with get_async_db_session() as db:
                    await crud.create_feed_posts_batch(db, current_batch)
                current_batch = []
        except asyncio.TimeoutError:
            if current_batch:
                async with get_async_db_session() as db:
                    await crud.create_feed_posts_batch(db, current_batch)
                current_batch = []
        except Exception as e:
            logger.error(f"Error in feed_post batch worker: {e}", exc_info=True)
            current_batch = []

# --- WebSocket Listener ---

async def listen_to_contrails_feed(feed_id: str, websocket_url: str):
    """
    Connects to a Contrails WebSocket feed and processes messages.
    Handles reconnections automatically.
    """
    logger.info(f"Starting listener for feed '{feed_id}' at {websocket_url}")
    while True:
        try:
            async with websockets.connect(websocket_url, ping_interval=20, ping_timeout=20) as websocket:
                logger.info(f"Successfully connected to feed '{feed_id}'")
                while True:
                    message_json = await websocket.recv()
                    message = json.loads(message_json)
                    await process_firehose_message(message, feed_id)
        except websockets.exceptions.ConnectionClosedOK:
            logger.info(f"WebSocket connection for feed '{feed_id}' closed gracefully. Reconnecting...")
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection for feed '{feed_id}' closed unexpectedly: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in WebSocket listener for feed '{feed_id}': {e}", exc_info=True)
            logger.info(f"Attempting to reconnect feed '{feed_id}' in 10 seconds...")
            await asyncio.sleep(10)

# --- NEW: Periodic DID Refresh  ---

async def periodic_did_refresh_scheduler():
    """
    Periodically finds users with placeholder data and refreshes prominent user profiles.
    """
    logging.info("Starting Periodic DID Refresh Scheduler...")
    PROMINENT_DID_REFRESH_INTERVAL_MINUTES = int(os.getenv("PROMINENT_DID_REFRESH_INTERVAL_MINUTES", 30))
    
    DID_REFRESH_CHECK_INTERVAL_SECONDS = int(os.getenv("DID_REFRESH_CHECK_INTERVAL_SECONDS", 60)) # Check every 1 minute

    while True:
        async with get_async_db_session() as db: # Use async session
            try:
                now_utc = datetime.now(timezone.utc)
                prominent_refresh_threshold = now_utc - timedelta(minutes=PROMINENT_DID_REFRESH_INTERVAL_MINUTES)

                # 1. Get prominent users due for a refresh
                prominent_users_stmt = select(models.User.did).where(
                    (models.User.is_prominent == True) &
                    ((models.User.last_prominent_refresh_check == None) | (models.User.last_prominent_refresh_check < prominent_refresh_threshold)))
                prominent_dids_to_refresh = (await db.execute(prominent_users_stmt)).scalars().all()

                # 2. Get users with placeholder handles (limit to a batch to avoid overwhelming the API)
                placeholder_users_stmt = select(models.User.did).where(models.User.handle.like('unknown.%')).limit(100)
                placeholder_dids_to_refresh = (await db.execute(placeholder_users_stmt)).scalars().all()

                # 3. Get a small batch of regular users who haven't been updated in a while (e.g., > 7 days)
                general_staleness_threshold = now_utc - timedelta(days=30)
                stale_users_stmt = select(models.User.did).where(
                    (models.User.last_updated < general_staleness_threshold) &
                    (models.User.is_prominent == False) # Don't re-process prominent users here
                ).limit(50) # Limit to a small batch to slowly work through the backlog
                stale_dids_to_refresh = (await db.execute(stale_users_stmt)).scalars().all()

                # Combine all DIDs and de-duplicate
                dids_to_refresh = set(prominent_dids_to_refresh) | set(placeholder_dids_to_refresh) | set(stale_dids_to_refresh)

                if dids_to_refresh:
                    logger.info(f"Found {len(dids_to_refresh)} user profiles to refresh ({len(prominent_dids_to_refresh)} prominent, {len(placeholder_dids_to_refresh)} placeholders, {len(stale_dids_to_refresh)} stale).")
                    await profile_resolver.resolve_and_update_profiles(db, list(dids_to_refresh))

                    # Update the last_prominent_refresh_check timestamp for the prominent users we processed
                    if prominent_dids_to_refresh:
                        update_stmt = (
                            update(models.User)
                            .where(models.User.did.in_(prominent_dids_to_refresh))
                            .values(last_prominent_refresh_check=now_utc)
                        )
                        await db.execute(update_stmt)
                        await db.commit()
            except Exception as e:
                logging.error(f"Error during periodic DID refresh check: {e}", exc_info=True)
                await db.rollback() # Await rollback
        await asyncio.sleep(DID_REFRESH_CHECK_INTERVAL_SECONDS)

# --- Main Worker Loop Orchestrator ---
async def run_worker():
    """
    The main asynchronous orchestrator for the ingestion worker.
    It loads configurations and starts WebSocket listeners for each configured feed.
    """
    logging.info("Starting Ingestion Worker Orchestrator...")

    # Ensure the config directory exists and contains dummy configs for local testing
    os.makedirs(CONFIG_DIR, exist_ok=True)
    if not os.path.exists(FEEDS_CONFIG_PATH):
        logging.info(f"Creating dummy feeds.json at {FEEDS_CONFIG_PATH}")
        with open(FEEDS_CONFIG_PATH, 'w') as f:
            json.dump([
                {
                    "id": "home-feed-graze",
                    "name": "Graze Home Feed",
                    "description": "The default home feed from Graze Contrails.",
                    "contrails_websocket_base_url": "wss://api.graze.social/app/contrail",
                    "bluesky_at_uri": "at://did:plc:lptjvw6ut224kwrj7ub3sqbe/app.bsky.feed.generator/aaaotfjzjplna",
                    "tier": "silver"
                },
                {
                    "id": "tech-news-graze",
                    "name": "Graze Tech News",
                    "description": "Tech news feed curated by Contrails.",
                    "contrails_websocket_base_url": "wss://api.graze.social/app/contrail",
                    "bluesky_at_uri": "at://did:plc:lptjvw6ut224kwrj7ub3sqbe/app.bsky.feed.generator/aaaic34mdicfg",
                    "tier": "gold"
                }
            ], f, indent=2)

    await load_configurations() # This is now an async function

    # --- Start batch processing workers ---
    batch_worker_tasks = [
        asyncio.create_task(post_batch_worker()),
        asyncio.create_task(feed_post_batch_worker()),
    ]

    # --- Start WebSocket listeners for each feed ---
    listener_tasks = []
    if not feeds_config:
        logging.info("No feeds configured. Ingestion Worker will not listen to any feeds.")
    else:
        for feed_conf in feeds_config:
            base_url = feed_conf.contrails_websocket_url
            at_uri = feed_conf.bluesky_at_uri
            websocket_url = f"{base_url}?feed={urllib.parse.quote_plus(str(at_uri))}"
            listener_tasks.append(asyncio.create_task(listen_to_contrails_feed(feed_conf.id, websocket_url)))

    # --- Start the periodic DID refresh scheduler ---
    scheduler_task = asyncio.create_task(periodic_did_refresh_scheduler())

    # --- Run all tasks concurrently ---
    # Gather all tasks including batch workers, listeners, and scheduler
    await asyncio.gather(*batch_worker_tasks, *listener_tasks, scheduler_task)


async def main() -> None:
    """Main entry point to set up and run the worker."""
    # For local development/testing:
    # Ensure tables exist if running worker directly.
    # In production, use Alembic for migrations.
    try:
        from backend.database import async_engine, Base

        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured.")
    except Exception as e:
        logger.critical(f"Could not connect to DB or create tables: {e}. Worker cannot start.", exc_info=True)
        return  # Exit if DB connection fails

    # Now that DB is confirmed, run the main worker logic
    await run_worker()


if __name__ == "__main__":
    asyncio.run(main())
