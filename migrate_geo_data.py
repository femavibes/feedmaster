#!/usr/bin/env python3

import asyncio
import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db
from backend.models import GeoHashtagMapping

async def migrate_geo_data():
    """Migrate geo hashtag data from JSON to database"""
    
    # Load JSON data
    with open('/app/config/geo_hashtags_mapping.json', 'r') as f:
        geo_data = json.load(f)
    
    print(f"Loading {len(geo_data)} geo hashtag mappings...")
    
    async for db in get_db():
        try:
            count = 0
            for hashtag, location in geo_data.items():
                mapping = GeoHashtagMapping(
                    hashtag=hashtag.lower(),
                    city=location.get('city'),
                    region=location.get('region'),
                    country=location['country']
                )
                await db.merge(mapping)
                count += 1
                
                if count % 100 == 0:
                    print(f"Processed {count} mappings...")
            
            await db.commit()
            print(f"✅ Successfully migrated {count} geo hashtag mappings to database!")
            
        except Exception as e:
            print(f"❌ Error migrating data: {e}")
            await db.rollback()
        finally:
            await db.close()
        break

if __name__ == "__main__":
    asyncio.run(migrate_geo_data())