# backend/aggregations/geo_aggregates.py

import json
import re
import os
from typing import Dict, Any, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
import logging

from .. import models, crud
from ..enums import Timeframe

logger = logging.getLogger(__name__)

# --- Load Geo-inference Data from JSON File ---
LOCATION_HASHTAG_MAP: Dict[str, Dict[str, Optional[str]]] = {}

# Get config directory from environment variable, with a fallback for local execution
CONFIG_DIR = os.getenv("CONFIG_DIR", "config")
MAP_FILE_PATH = os.path.join(CONFIG_DIR, 'geo_hashtags_mapping.json')

try:
    with open(MAP_FILE_PATH, 'r', encoding='utf-8') as f:
        LOCATION_HASHTAG_MAP = json.load(f)
    logger.info(f"Successfully loaded {len(LOCATION_HASHTAG_MAP)} geo hashtag mappings from {MAP_FILE_PATH}")
except FileNotFoundError:
    logger.error(f"Geo hashtag mapping file not found at {MAP_FILE_PATH}. Geo inference will not work. Please create it.")
except json.JSONDecodeError as e:
    logger.error(f"Error decoding JSON from {MAP_FILE_PATH}: {e}. Geo inference might be incomplete.")
except Exception as e:
    logger.error(f"An unexpected error occurred loading geo hashtag map: {e}")

# --- Helper Functions ---

def _get_location_from_hashtags(hashtags: Optional[List[str]]) -> Optional[Dict[str, str]]:
    """
    Infers a single best location (city, region, country) from a list of hashtags within a post.
    Prioritizes more specific locations.
    Returns None if:
    1. No location-indicating hashtags are found.
    2. Conflicting *city-level* locations are inferred from different hashtags in the same post.
    """
    if not hashtags:
        return None

    inferred_city = None
    inferred_region = None
    inferred_country = None

    # Track distinct cities found in this post's hashtags to detect conflicts
    distinct_cities_found_in_post: Set[str] = set()

    for tag in hashtags:
        # Enhanced Normalization:
        # 1. Convert to lowercase.
        # 2. Remove all non-alphanumeric characters (keeps a-z, 0-9).
        normalized_tag = re.sub(r'[^a-z0-9]', '', tag.lower())

        loc_data = LOCATION_HASHTAG_MAP.get(normalized_tag)

        if loc_data:
            current_tag_city = loc_data.get("city")
            current_tag_region = loc_data.get("region")
            current_tag_country = loc_data.get("country")

            # Add the specific city from this hashtag to our set of distinct cities found in this post
            if current_tag_city:
                distinct_cities_found_in_post.add(current_tag_city)
            
            # Prioritize the most specific inferred location for the return value
            # If we haven't found a city yet, and this tag has one, use it
            if current_tag_city and inferred_city is None: # Use 'is None' for explicit check
                inferred_city = current_tag_city
                inferred_region = current_tag_region # Update region/country to match specific city
                inferred_country = current_tag_country
            # If no city found yet, but this tag has a region, use it
            elif inferred_city is None and current_tag_region and inferred_region is None:
                inferred_region = current_tag_region
                inferred_country = current_tag_country # Update country to match specific region
            # If no city or region found yet, but this tag has a country, use it
            elif inferred_city is None and inferred_region is None and current_tag_country and inferred_country is None:
                inferred_country = current_tag_country

    # --- Conflict Resolution ---
    # If more than one *distinct* city was identified from the hashtags in this post,
    # then we cannot confidently infer a single location. Return None.
    if len(distinct_cities_found_in_post) > 1:
        logger.warning(f"Conflicting city hashtags found in post: {hashtags}. Inferred cities: {distinct_cities_found_in_post}. Returning None.")
        return None
    
    # If no conflict, return the most specific inferred location found
    if inferred_city or inferred_region or inferred_country:
        return {
            "city": inferred_city,
            "region": inferred_region,
            "country": inferred_country
        }
    return None # No location could be inferred from any hashtag


# --- Aggregate Calculation Functions ---

async def calculate_top_cities(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top cities based on location-indicating hashtags in posts.
    Note: This function processes data in Python after fetching from DB,
    due to complex string/JSONB processing and external mapping.
    For better performance, consider pre-calculating inferred locations in the ingestion pipeline.
    Ensures each unique post is counted once for a city.
    """
    logger.info(f"Calculating top cities for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    stmt = select(models.Post.id, models.Post.hashtags).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.hashtags.isnot(None), # Ensure hashtags field is not null
        func.jsonb_array_length(models.Post.hashtags) > 0 # Ensure it's not an empty JSON array
    ).distinct(models.Post.id)
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)
    posts_data = (await db.execute(stmt)).all()

    city_counts: Dict[str, int] = {}
    for post_id, post_hashtags in posts_data: # Unpack post ID and hashtags directly
        try:
            # Safely handle post_hashtags which might be a JSON string or already a Python list/object
            hashtags_list = post_hashtags
            if isinstance(hashtags_list, str):
                hashtags_list = json.loads(hashtags_list)
            
            if not isinstance(hashtags_list, list):
                logger.warning(f"Hashtags for post ID {post_id} is not a list after parsing. Type: {type(hashtags_list)}. Skipping.")
                continue

            inferred_location = _get_location_from_hashtags(hashtags_list)
            if inferred_location and inferred_location.get("city"):
                city = inferred_location["city"]
                city_counts[city] = city_counts.get(city, 0) + 1
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode hashtags JSON for post ID {post_id}: {post_hashtags}")
            continue
        except Exception as e:
            logger.error(f"Error processing hashtags for post ID {post_id}: {e}")
            continue

    sorted_cities = sorted(city_counts.items(), key=lambda item: item[1], reverse=True)[:50]

    top_cities_data = []
    for city, count in sorted_cities:
        top_cities_data.append({"type": "geo", "city": city, "count": count})

    logger.info(f"Calculated top cities for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_cities_data)} results.")
    return {"top": top_cities_data}


async def calculate_top_regions(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top regions (states/provinces) based on location-indicating hashtags in posts.
    Note: This function processes data in Python after fetching from DB,
    due to complex string/JSONB processing and external mapping.
    For better performance, consider pre-calculating inferred locations in the ingestion pipeline.
    Ensures each unique post is counted once for a region.
    """
    logger.info(f"Calculating top regions for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    stmt = select(models.Post.id, models.Post.hashtags).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.hashtags.isnot(None),
        func.jsonb_array_length(models.Post.hashtags) > 0
    ).distinct(models.Post.id)
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)
    posts_data = (await db.execute(stmt)).all()

    region_counts: Dict[str, int] = {}
    for post_id, post_hashtags in posts_data: # Unpack post ID and hashtags directly
        try:
            hashtags_list = post_hashtags
            if isinstance(hashtags_list, str):
                hashtags_list = json.loads(hashtags_list)

            if not isinstance(hashtags_list, list):
                logger.warning(f"Hashtags for post ID {post_id} is not a list after parsing. Type: {type(hashtags_list)}. Skipping.")
                continue

            inferred_location = _get_location_from_hashtags(hashtags_list)
            if inferred_location and inferred_location.get("region"):
                region = inferred_location["region"]
                region_counts[region] = region_counts.get(region, 0) + 1
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode hashtags JSON for post ID {post_id}: {post_hashtags}")
            continue
        except Exception as e:
            logger.error(f"Error processing hashtags for post ID {post_id}: {e}")
            continue

    sorted_regions = sorted(region_counts.items(), key=lambda item: item[1], reverse=True)[:50]

    top_regions_data = []
    for region, count in sorted_regions:
        top_regions_data.append({"type": "geo", "region": region, "count": count})

    logger.info(f"Calculated top regions for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_regions_data)} results.")
    return {"top": top_regions_data}


async def calculate_top_countries(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top countries based on location-indicating hashtags in posts.
    Note: This function processes data in Python after fetching from DB,
    due to complex string/JSONB processing and external mapping.
    For better performance, consider pre-calculating inferred locations in the ingestion pipeline.
    Ensures each unique post is counted once for a country.
    """
    logger.info(f"Calculating top countries for feed '{feed_id}', timeframe '{timeframe.value}'...")

    time_threshold = crud.get_time_boundary(timeframe.value)

    stmt = select(models.Post.id, models.Post.hashtags).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).where(
        models.FeedPost.feed_id == feed_id,
        models.Post.hashtags.isnot(None),
        func.jsonb_array_length(models.Post.hashtags) > 0
    ).distinct(models.Post.id)
    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_threshold)
    posts_data = (await db.execute(stmt)).all()

    country_counts: Dict[str, int] = {}
    for post_id, post_hashtags in posts_data: # Unpack post ID and hashtags directly
        try:
            hashtags_list = post_hashtags
            if isinstance(hashtags_list, str):
                hashtags_list = json.loads(hashtags_list)

            if not isinstance(hashtags_list, list):
                logger.warning(f"Hashtags for post ID {post_id} is not a list after parsing. Type: {type(hashtags_list)}. Skipping.")
                continue

            inferred_location = _get_location_from_hashtags(hashtags_list)
            if inferred_location and inferred_location.get("country"):
                country = inferred_location["country"]
                country_counts[country] = country_counts.get(country, 0) + 1
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode hashtags JSON for post ID {post_id}: {post_hashtags}")
            continue
        except Exception as e:
            logger.error(f"Error processing hashtags for post ID {post_id}: {e}")
            continue

    sorted_countries = sorted(country_counts.items(), key=lambda item: item[1], reverse=True)[:50]

    top_countries_data = []
    for country, count in sorted_countries:
        top_countries_data.append({"type": "geo", "country": country, "count": count})

    logger.info(f"Calculated top countries for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_countries_data)} results.")
    return {"top": top_countries_data}
