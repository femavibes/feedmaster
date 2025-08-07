# backend/aggregations/link_aggregates.py
import logging
import json
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
import os
from typing import List, Dict, Any
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import literal_column
from sqlalchemy import text, select, func, or_, cast
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from .. import models
from .. import crud
from ..enums import Timeframe

logger = logging.getLogger(__name__)

# --- Load News Domains from JSON File ---
NEWS_DOMAINS: set[str] = set()
# Get config directory from environment variable, with a fallback for local execution
CONFIG_DIR = os.getenv("CONFIG_DIR", "config")
NEWS_DOMAINS_FILE_PATH = os.path.join(CONFIG_DIR, 'news_domains.json')

try:
    with open(NEWS_DOMAINS_FILE_PATH, 'r', encoding='utf-8') as f: # Corrected variable name
        NEWS_DOMAINS = set(json.load(f))
    logger.info(f"Successfully loaded {len(NEWS_DOMAINS)} news domains from {NEWS_DOMAINS_FILE_PATH}")
except Exception as e:
    logger.error(f"Could not load news domains from {NEWS_DOMAINS_FILE_PATH}. 'top_news_cards' will be empty. Error: {e}")


async def calculate_top_links(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top external links shared in posts for a given feed and timeframe.
    This version queries the pre-processed 'links' column for simplicity and robustness.
    """
    logger.info(f"Calculating top links for feed '{feed_id}', timeframe '{timeframe.value}'...")
    time_boundary = crud.get_time_boundary(timeframe.value)
    limit = 50 # Standardized limit

    # Unnest the 'links' JSONB array. Each element is an object like {"uri": "..."}.
    link_element = func.jsonb_array_elements(models.Post.links).alias('link_element')

    # Build the base query
    query = select(
        link_element.column.op('->>')('uri').label('link_uri'),
        func.count().label('link_count')
    ).select_from(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).join(
        link_element, literal_column('TRUE')
    ).where(
        (models.FeedPost.feed_id == feed_id) &
        (models.Post.has_link == True)
    )
    # Conditionally apply the time filter, which is cleaner for the 'allTime' case
    if timeframe.value != "allTime":
        query = query.where(models.FeedPost.ingested_at >= time_boundary)
    # Apply grouping, ordering, and limit
    query = query.group_by('link_uri').order_by(func.count().desc()).limit(limit)
    try:
        result = await db.execute(query)
        top_links = [{"type": "link", "uri": row.link_uri, "count": row.link_count} for row in result.all()]
        logger.info(f"Top links for feed {feed_id}, timeframe {timeframe.value} calculated: {len(top_links)} results.")
        return {"links": top_links}
    except Exception as e:
        logger.error(f"Error calculating top links for feed {feed_id}: {e}", exc_info=True)
        return {"links": []}

async def calculate_top_domains(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top domains from links shared in posts for a given feed and timeframe.
    Uses Python URL parsing for reliable domain extraction.
    """
    logger.info(f"Calculating top domains for feed '{feed_id}', timeframe '{timeframe.value}'...")
    time_boundary = crud.get_time_boundary(timeframe.value)
    limit = 50

    # Get all links first, then process in Python
    link_element = func.jsonb_array_elements(models.Post.links).alias('link_element')
    
    query = select(
        link_element.column.op('->>')('uri').label('link_uri')
    ).select_from(models.Post).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).join(
        link_element, literal_column('TRUE')
    ).where(
        (models.FeedPost.feed_id == feed_id) &
        (models.Post.has_link == True)
    )
    
    if timeframe.value != "allTime":
        query = query.where(models.FeedPost.ingested_at >= time_boundary)
    
    try:
        result = await db.execute(query)
        links = [row.link_uri for row in result.all()]
        logger.info(f"Found {len(links)} links for domain extraction")
        
        # Extract domains using Python
        from urllib.parse import urlparse
        from collections import Counter
        
        domains = []
        for link in links:
            try:
                parsed = urlparse(link)
                domain = parsed.netloc.lower()
                if domain.startswith('www.'):
                    domain = domain[4:]
                if domain:
                    domains.append(domain)
            except Exception as e:
                logger.debug(f"Failed to parse URL {link}: {e}")
                continue
        
        logger.info(f"Extracted {len(domains)} domains from {len(links)} links")
        
        # Count domains and get top results
        domain_counts = Counter(domains)
        top_domains_data = [
            {"type": "domain", "domain": domain, "count": count}
            for domain, count in domain_counts.most_common(limit)
        ]
        
        logger.info(f"Top 5 domains: {list(domain_counts.most_common(5))}")
        logger.info(f"Calculated top domains for feed '{feed_id}', timeframe '{timeframe.value}': {len(top_domains_data)} results.")
        return {"domains": top_domains_data}
        
    except Exception as e:
        logger.error(f"Error calculating top domains for feed {feed_id}: {e}", exc_info=True)
        return {"domains": []}

async def calculate_top_cards(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top link cards from all domains.
    """
    logger.info(f"Calculating top link cards for feed '{feed_id}', timeframe '{timeframe.value}'.")
    time_boundary = crud.get_time_boundary(timeframe.value)
    limit = 50

    stmt = select(
        models.Post.uri,
        models.Post.link_url,
        models.Post.link_title,
        models.Post.link_description,
        models.Post.thumbnail_url,
        func.count(func.distinct(models.Post.id)).label('count')
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).filter(
        models.FeedPost.feed_id == feed_id,
        models.Post.has_link == True,
        models.Post.link_url.isnot(None), # Ensure there's a link card to show
        models.Post.link_title.isnot(None) # Ensure there's a title to avoid validation errors
    )

    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_boundary)

    stmt = stmt.group_by(
        models.Post.uri, models.Post.link_url, models.Post.link_title, models.Post.link_description, models.Post.thumbnail_url
    ).order_by(func.count(func.distinct(models.Post.id)).desc()).limit(limit)

    result = await db.execute(stmt)
    cards = [{
        "type": "link_card",
        "uri": row.uri,
        "url": row.link_url,
        "title": row.link_title or "",
        "description": row.link_description or "",
        "image": row.thumbnail_url,
        "count": row.count
    } for row in result.all()]

    logger.info(f"Top link cards for feed {feed_id}, timeframe {timeframe.value} calculated: {len(cards)} results.")
    return {"top": cards}

async def calculate_top_news_cards(db: AsyncSession, feed_id: str, timeframe: Timeframe) -> Dict[str, Any]:
    """
    Calculates the top link cards that are from a known list of news domains.
    """
    logger.info(f"Calculating top news link cards for feed '{feed_id}', timeframe '{timeframe.value}'. NEWS_DOMAINS count: {len(NEWS_DOMAINS)}.")
    time_boundary = crud.get_time_boundary(timeframe.value)
    limit = 50

    if not NEWS_DOMAINS:
        logger.warning("NEWS_DOMAINS set is empty. Cannot calculate top news link cards.")
        return {"news_cards": []}

    logger.debug(f"NEWS_DOMAINS count inside calculate_top_news_cards: {len(NEWS_DOMAINS)}")

    # Define the regex pattern to extract the domain from a URI.
    domain_regex = '^(?:https?://)?(?:[^@\n]+@)?(?:www\.)?([^:/\n?]+)'

    # Use LIKE patterns to match news domains in URLs
    if not NEWS_DOMAINS:
        logger.warning("NEWS_DOMAINS set is empty. Cannot calculate top news link cards.")
        return {"news_cards": []}
    
    # Create filter for all news domains
    news_domain_filters = [models.Post.link_url.like(f'%{domain}%') for domain in NEWS_DOMAINS]
    news_domain_filter = or_(*news_domain_filters)

    stmt = select(
        models.Post.uri,
        models.Post.link_url,
        models.Post.link_title,
        models.Post.link_description,
        models.Post.thumbnail_url,
        func.count(func.distinct(models.Post.id)).label('count')
    ).join(
        models.FeedPost, models.Post.id == models.FeedPost.post_id
    ).filter(
        models.FeedPost.feed_id == feed_id,
        models.Post.has_link == True,
        models.Post.link_url.isnot(None),
        news_domain_filter
    )

    if timeframe.value != "allTime":
        stmt = stmt.where(models.FeedPost.ingested_at >= time_boundary)

    stmt = stmt.group_by(
        models.Post.uri, models.Post.link_url, models.Post.link_title, models.Post.link_description, models.Post.thumbnail_url
    ).order_by(func.count(func.distinct(models.Post.id)).desc()).limit(limit)

    result = await db.execute(stmt)
    news_cards = [{
        "type": "link_card",
        "uri": row.uri,
        "url": row.link_url,
        "title": row.link_title or "",
        "description": row.link_description or "",
        "image": row.thumbnail_url,
        "count": row.count
    } for row in result.all()]

    logger.info(f"Top news link cards for feed {feed_id}, timeframe {timeframe.value} calculated: {len(news_cards)} results.")
    return {"top": news_cards}