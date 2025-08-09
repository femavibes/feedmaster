-- Database Optimization Migration
-- This script implements Option 1: JSON replacement of feed_posts table
-- Expected savings: ~280MB (75% database reduction)

-- Step 1: Add new columns to posts table
ALTER TABLE posts ADD COLUMN feed_data JSONB;
ALTER TABLE posts ADD COLUMN langs JSONB;

-- Step 2: Create index on feed_data for performance
CREATE INDEX idx_posts_feed_data_gin ON posts USING GIN (feed_data);

-- Step 3: Migrate data from feed_posts to posts.feed_data
-- This populates the feed_data column with JSON array of feed associations
UPDATE posts SET feed_data = (
    SELECT jsonb_agg(
        jsonb_build_object(
            'feed_id', fp.feed_id,
            'ingested_at', fp.ingested_at
        )
    )
    FROM feed_posts fp
    WHERE fp.post_id = posts.id
);

-- Step 4: Extract langs from raw_record where available
UPDATE posts 
SET langs = raw_record->'langs'
WHERE raw_record IS NOT NULL 
AND raw_record ? 'langs';

-- Step 5: Set feed_data to empty array for posts with no feed associations (shouldn't happen but safety)
UPDATE posts SET feed_data = '[]'::jsonb WHERE feed_data IS NULL;

-- Step 6: Make feed_data NOT NULL now that it's populated
ALTER TABLE posts ALTER COLUMN feed_data SET NOT NULL;

-- Step 7: Verify migration (these should return same counts)
-- SELECT COUNT(*) FROM feed_posts; -- Original count
-- SELECT COUNT(*) FROM posts, jsonb_array_elements(feed_data) AS feed_elem; -- New count

-- Step 8: Drop the feed_posts table (MAJOR SPACE SAVINGS!)
-- DROP TABLE feed_posts; -- Uncomment after verification

-- Step 9: Create raw_record cleanup job (to be run after 30 days)
-- UPDATE posts SET raw_record = NULL WHERE created_at < NOW() - INTERVAL '30 days';

-- Verification queries:
-- Check feed_data structure:
-- SELECT uri, feed_data FROM posts WHERE feed_data != '[]'::jsonb LIMIT 5;

-- Check langs extraction:
-- SELECT uri, langs FROM posts WHERE langs IS NOT NULL LIMIT 5;

-- Check space savings:
-- SELECT pg_size_pretty(pg_total_relation_size('posts')) as posts_size;