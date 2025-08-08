#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import engine, Base
from backend.models import GeoHashtagMapping, NewsDomain

async def create_tables():
    """Create the configuration tables"""
    async with engine.begin() as conn:
        # Create only the configuration tables
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        print("✅ Configuration tables created successfully!")

if __name__ == "__main__":
    asyncio.run(create_tables())