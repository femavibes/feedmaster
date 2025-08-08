"""
Authentication utilities for API key management
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .database import get_db
from .models import ApiKey, ApiKeyType

security = HTTPBearer()

def generate_api_key() -> Tuple[str, str]:
    """
    Generate a new API key and return (raw_key, hashed_key)
    Raw key is given to user, hashed key is stored in database
    """
    raw_key = f"fm_{''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz0123456789') for _ in range(32))}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key

def hash_api_key(raw_key: str) -> str:
    """Hash an API key for database storage"""
    return hashlib.sha256(raw_key.encode()).hexdigest()

async def get_api_key_from_db(db: AsyncSession, key_hash: str) -> Optional[ApiKey]:
    """Get API key from database by hash"""
    stmt = select(ApiKey).where(
        ApiKey.key_hash == key_hash,
        ApiKey.is_active == True
    )
    result = await db.execute(stmt)
    api_key = result.scalar_one_or_none()
    
    # Check if key is expired
    if api_key and api_key.expires_at:
        if datetime.now(timezone.utc) > api_key.expires_at:
            return None
    
    return api_key

async def authenticate_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> ApiKey:
    """
    Authenticate API key from Authorization header
    Returns the ApiKey object if valid
    """
    if not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    key_hash = hash_api_key(credentials.credentials)
    api_key = await get_api_key_from_db(db, key_hash)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key"
        )
    
    # Update last used timestamp
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    
    return api_key

async def require_master_admin(api_key: ApiKey = Depends(authenticate_api_key)) -> ApiKey:
    """Require master admin API key"""
    if api_key.key_type != ApiKeyType.MASTER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master admin access required"
        )
    return api_key

async def require_feed_owner(api_key: ApiKey = Depends(authenticate_api_key)) -> ApiKey:
    """Require feed owner API key"""
    if api_key.key_type != ApiKeyType.FEED_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Feed owner access required"
        )
    return api_key

async def require_any_auth(api_key: ApiKey = Depends(authenticate_api_key)) -> ApiKey:
    """Require any valid API key"""
    return api_key