#!/usr/bin/env python3

import json
import urllib.request
import urllib.parse
import sys

API_KEY = "fm_a1f025a32hvfx6ue7aq6pv083e18tweu"
BASE_URL = "http://localhost:8000/api/v1/admin"

def make_request(url, method="GET"):
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {API_KEY}")
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode()
    except Exception as e:
        return f"Error: {e}"

def migrate_geo_hashtags():
    with open('/root/feedmaster/config/geo_hashtags_mapping.json', 'r') as f:
        geo_data = json.load(f)
    
    print(f"Migrating {len(geo_data)} geo hashtag mappings...")
    success_count = 0
    
    for hashtag, location in geo_data.items():
        params = {
            'hashtag': hashtag,
            'country': location['country']
        }
        
        if location.get('city'):
            params['city'] = location['city']
        if location.get('region'):
            params['region'] = location['region']
        
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/config/geo-hashtags?{query_string}"
        
        result = make_request(url, "POST")
        if "message" in result:
            print(f"✓ {hashtag}")
            success_count += 1
        else:
            print(f"✗ {hashtag}: {result}")
    
    print(f"Successfully migrated {success_count}/{len(geo_data)} geo hashtags")

def migrate_news_domains():
    with open('/root/feedmaster/config/news_domains.json', 'r') as f:
        domains_data = json.load(f)
    
    print(f"\nMigrating {len(domains_data)} news domains...")
    success_count = 0
    
    for domain in domains_data:
        params = {'domain': domain}
        query_string = urllib.parse.urlencode(params)
        url = f"{BASE_URL}/config/news-domains?{query_string}"
        
        result = make_request(url, "POST")
        if "message" in result:
            print(f"✓ {domain}")
            success_count += 1
        else:
            print(f"✗ {domain}: {result}")
    
    print(f"Successfully migrated {success_count}/{len(domains_data)} news domains")

if __name__ == '__main__':
    migrate_geo_hashtags()
    migrate_news_domains()
    print("\nMigration complete!")