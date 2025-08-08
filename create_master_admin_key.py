#!/usr/bin/env python3
"""
Script to create a master admin API key
Run this once to generate your admin key
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import AsyncSessionLocal
from backend.auth import generate_api_key
from backend.models import ApiKey, ApiKeyType

async def create_master_admin_key():
    """Create a master admin API key"""
    async with AsyncSessionLocal() as db:
        # Check if master admin key already exists
        from sqlalchemy import select
        existing = await db.execute(
            select(ApiKey).where(ApiKey.key_type == ApiKeyType.MASTER_ADMIN)
        )
        if existing.scalar_one_or_none():
            print("❌ Master admin key already exists!")
            return
        
        # Generate new key
        raw_key, key_hash = generate_api_key()
        
        api_key = ApiKey(
            key_hash=key_hash,
            key_type=ApiKeyType.MASTER_ADMIN,
            owner_did=None,  # Master admin has no DID
            expires_at=None,  # Never expires
            is_active=True
        )
        
        db.add(api_key)
        await db.commit()
        
        print("✅ Master admin API key created!")
        print(f"🔑 API Key: {raw_key}")
        print("\n⚠️  IMPORTANT: Save this key securely - it won't be shown again!")
        print("💡 Add this to your .env file:")
        print(f"MASTER_ADMIN_API_KEY={raw_key}")

if __name__ == "__main__":
    asyncio.run(create_master_admin_key())