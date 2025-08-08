#!/usr/bin/env python3
"""
Script to migrate news domains from JSON file to database
"""
import json
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
from backend.models import NewsDomain

async def migrate_news_domains():
    # Load domains from JSON file
    with open('config/news_domains.json', 'r') as f:
        domains = json.load(f)
    
    print(f"Found {len(domains)} domains to migrate")
    
    # Get database session
    async for db in get_db():
        success_count = 0
        for domain in domains:
            try:
                news_domain = NewsDomain(domain=domain.lower())
                await db.merge(news_domain)
                success_count += 1
                print(f"✓ Added {domain}")
            except Exception as e:
                print(f"✗ Error adding {domain}: {e}")
        
        await db.commit()
        print(f"\nMigration complete: {success_count}/{len(domains)} domains added")
        break

if __name__ == "__main__":
    asyncio.run(migrate_news_domains())