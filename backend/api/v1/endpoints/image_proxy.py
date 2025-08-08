"""
Image proxy endpoint to bypass CORS issues with Bluesky CDN
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
import httpx
import asyncio
from urllib.parse import urlparse
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache for images (simple in-memory cache)
image_cache = {}
CACHE_DURATION = 300  # 5 minutes

@router.get("/image-proxy")
async def proxy_image(url: str = Query(..., description="Image URL to proxy")):
    """
    Proxy images from Bluesky CDN to bypass CORS issues
    """
    # Validate URL is from allowed domains
    parsed_url = urlparse(url)
    allowed_domains = ['cdn.bsky.app', 'bsky.app']
    
    if parsed_url.netloc not in allowed_domains:
        raise HTTPException(status_code=400, detail="URL not from allowed domain")
    
    # Check cache first
    if url in image_cache:
        cached_data, cached_headers = image_cache[url]
        return Response(content=cached_data, headers=cached_headers)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Prepare headers for response
            headers = {
                "Content-Type": response.headers.get("content-type", "image/jpeg"),
                "Cache-Control": "public, max-age=300",
                "Access-Control-Allow-Origin": "*"
            }
            
            # Cache the response
            image_cache[url] = (response.content, headers)
            
            # Simple cache cleanup (remove old entries)
            if len(image_cache) > 1000:
                # Remove oldest 100 entries
                keys_to_remove = list(image_cache.keys())[:100]
                for key in keys_to_remove:
                    del image_cache[key]
            
            return Response(content=response.content, headers=headers)
            
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch image {url}: {e}")
        raise HTTPException(status_code=404, detail="Image not found")
    except Exception as e:
        logger.error(f"Unexpected error fetching image {url}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")