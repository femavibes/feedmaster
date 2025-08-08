# backend/cache.py
import redis
import json
import os
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    db=0,
    decode_responses=True
)

class Cache:
    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            value = redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    @staticmethod
    def set(key: str, value: Any, expire_seconds: int = 600) -> bool:
        """Set value in cache with expiration"""
        try:
            redis_client.setex(key, expire_seconds, json.dumps(value, default=str))
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete key from cache"""
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    def exists(key: str) -> bool:
        """Check if key exists in cache"""
        try:
            return redis_client.exists(key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

# Cache key generators
def user_search_key(query: str) -> str:
    return f"user_search:{query.lower()}"

def hashtag_search_key(query: str) -> str:
    return f"hashtag_search:{query.lower()}"

def user_profile_key(user_did: str) -> str:
    return f"user_profile:{user_did}"