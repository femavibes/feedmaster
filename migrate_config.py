#!/usr/bin/env python3

import json
import requests
import sys

def migrate_data():
    # Read JSON files
    with open('/root/feedmaster/config/geo_hashtags_mapping.json', 'r') as f:
        geo_data = json.load(f)
    
    with open('/root/feedmaster/config/news_domains.json', 'r') as f:
        domains_data = json.load(f)
    
    base_url = 'http://localhost:8000/api/v1'
    
    print(f"Migrating {len(geo_data)} geo hashtag mappings...")
    
    # Migrate geo hashtags
    for hashtag, location in geo_data.items():
        payload = {
            'hashtag': hashtag,
            'city': location.get('city'),
            'region': location.get('region'),
            'country': location['country']
        }
        
        try:
            response = requests.post(f'{base_url}/config/geo-hashtags', json=payload)
            if response.status_code == 200:
                print(f"✓ Added geo mapping: {hashtag}")
            else:
                print(f"✗ Failed to add {hashtag}: {response.status_code}")
        except Exception as e:
            print(f"✗ Error adding {hashtag}: {e}")
    
    print(f"\nMigrating {len(domains_data)} news domains...")
    
    # Migrate news domains
    for domain in domains_data:
        payload = {'domain': domain}
        
        try:
            response = requests.post(f'{base_url}/config/news-domains', json=payload)
            if response.status_code == 200:
                print(f"✓ Added domain: {domain}")
            else:
                print(f"✗ Failed to add {domain}: {response.status_code}")
        except Exception as e:
            print(f"✗ Error adding {domain}: {e}")
    
    print("\nMigration complete!")

if __name__ == '__main__':
    migrate_data()