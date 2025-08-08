#!/bin/bash

# First, let's test if we can access the admin endpoints without auth
echo "Testing admin endpoint access..."
curl -X GET "http://localhost:8000/api/v1/admin/config/geo-hashtags" 2>/dev/null | head -20

echo -e "\n\nMigrating geo hashtag mappings..."

# Sample of geo hashtags - adding a few key ones
curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=nyc&city=New%20York%20City&region=New%20York&country=USA" \
  -H "Authorization: Bearer fm_a1f025a32hvfx6ue7aq6pv083e18tweu"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=la&city=Los%20Angeles&region=California&country=USA"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=london&city=London&region=England&country=United%20Kingdom"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=paris&city=Paris&region=%C3%8Ele-de-France&country=France"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=tokyo&city=Tokyo&region=Tokyo%20Prefecture&country=Japan"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=usa&country=USA"

curl -X POST "http://localhost:8000/api/v1/admin/config/geo-hashtags?hashtag=canada&country=Canada"

echo -e "\n\nMigrating news domains..."

# Sample of news domains
curl -X POST "http://localhost:8000/api/v1/admin/config/news-domains?domain=nytimes.com"

curl -X POST "http://localhost:8000/api/v1/admin/config/news-domains?domain=washingtonpost.com"

curl -X POST "http://localhost:8000/api/v1/admin/config/news-domains?domain=bbc.com"

curl -X POST "http://localhost:8000/api/v1/admin/config/news-domains?domain=reuters.com"

curl -X POST "http://localhost:8000/api/v1/admin/config/news-domains?domain=cnn.com"

echo -e "\n\nMigration complete!"