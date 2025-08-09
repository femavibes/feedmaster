# Feedmaster - Planned Features

This document tracks feature ideas and future development plans.

## 🔔 Discord Achievement Notifications

**Concept:** Per-feed Discord webhooks that notify when users earn achievements

**Key Questions to Resolve:**
- Configuration: Each feed has own webhook URL vs. one webhook with filtering
- Content: Achievement name + user vs. full card image + profile link
- Frequency: All achievements vs. rare only (Diamond+) vs. configurable minimum rarity
- Admin Control: Feed admins configure own webhooks vs. main admin only
- Rate Limiting: Batch notifications vs. individual sends

**Complexity:** Medium (webhook config + rate limiting + error handling)
**Resources:** Minimal (1-10 HTTP calls per hour)

**Status:** Tabled - needs design decisions

---

## 🏷️ Unified Achievement Bot + Labeler

**Concept:** Extend existing Bluesky bot to optionally function as achievement labeler

**Unified Architecture:**
- **Same bot codebase** handles both posting and labeling
- **Regular account mode**: Posts achievements, no labeling features
- **Labeler account mode**: Posts achievements + assigns labels to users
- **Flexible deployment**: Users choose which features to enable

**Configuration Options:**
```env
# Existing bot features
ENABLE_POSTING=true          # Post achievement announcements
ENABLE_LABELING=false        # Assign labels to user profiles

# Labeling settings (only used if ENABLE_LABELING=true)
LABEL_MIN_RARITY=Diamond     # Only label Diamond+ achievements
LABEL_STRATEGY=rarest        # 'rarest' = one label per user, 'threshold' = all above rarity
```

**Labeling Features (when enabled):**
- **Rarity threshold**: Only Diamond+ achievements become labels
- **Single label per user**: Their rarest achievement (prevents spam)
- **Automatic updates**: Labels change when users earn rarer achievements
- **Opt-in system**: Users follow the labeler account to consent

**Deployment Scenarios:**
1. **Feed announcement bot**: `ENABLE_POSTING=true, ENABLE_LABELING=false`
2. **Pure labeler**: `ENABLE_POSTING=false, ENABLE_LABELING=true`
3. **Full-featured**: `ENABLE_POSTING=true, ENABLE_LABELING=true`
4. **Global labeler**: `FEED_IDS=global, ENABLE_LABELING=true` (cross-platform achievements)

**Technical Implementation:**
- Extend existing bot with labeling module
- Same achievement polling, different actions based on config
- AT Protocol labeling API integration
- Follower tracking for opt-in consent

**Benefits:**
- **Simple deployment**: One bot, multiple use cases
- **Code reuse**: Same achievement processing logic
- **Flexible**: Users pick features they want
- **Account agnostic**: Works on regular or labeler accounts

**Example Labels:**
- "🏆 Mythic Contributor" (0.1% rarity)
- "💎 Diamond Poster" (1% rarity)  
- "👑 Legendary Engager" (0.5% rarity)

**Complexity:** Medium (extends existing bot vs. separate service)
**Resources:** Same as current bot + labeling API calls

**Status:** Future enhancement to existing bot

---

## 📝 Future Feature Ideas

### 💾 Database Storage Optimization - APPROVED FOR IMPLEMENTATION
**Current issue:** 400MB total database size, 245MB feed_posts table with 31k records

**SELECTED STRATEGY: Option 1 + Raw Record Purging**
- [x] **Option 1: Full JSON replacement** - Replace feed_posts table with JSON array in posts table
  - **Space Savings:** ~237MB (63% of total database)
  - **Implementation:** Add `feed_data` JSONB column to posts table
  - **Data Structure:** `[{"feed_id": "3654", "ingested_at": "2024-01-15T10:30:00Z"}, ...]`
  - **Query Impact:** Aggregation queries need rewriting but manageable
  - **Status:** Ready for implementation

- [x] **Raw Record Purging Strategy** - Delete raw_record after 30 days
  - **Space Savings:** Additional 40-100MB (raw records are 2-5KB each)
  - **Rationale:** All UI/analytics use parsed data, raw_record only for debugging
  - **Implementation:** Scheduled job to purge old raw_record data
  - **Risk:** Minimal - raw data already extracted to structured fields

**FIELD EXTRACTION AUDIT COMPLETED ✅**

**Currently Extracted Fields (47 total):**
- **Core Post Data:** uri, cid, text, created_at, author_did, raw_record
- **Engagement Metrics:** like_count, repost_count, reply_count, quote_count, engagement_score
- **Content Analysis:** hashtags, mentions, links, facets (rich text formatting)
- **Media & Embeds:** images, has_image, has_video, has_alt_text, thumbnail_url, aspect_ratio_width/height, embeds
- **Link Cards:** link_url, link_title, link_description, has_link
- **Quote Posts:** quoted_post_* (9 fields with full quoted post details), has_quote
- **System Fields:** has_mention, next_poll_at, is_active_for_polling, ingested_at

**Available in raw_record but NOT extracted:**
- **langs** - Language detection array (e.g., ["en"]) - Found in 80% of posts
- **$type** - AT Protocol record type (always "app.bsky.feed.post")

**Fields NOT found in current data:**
- **reply** - Reply threading (parent/root references) - Not found in sample
- **labels** - Content warnings/moderation labels - Not found in sample  
- **via** - App context (which app posted it) - Not found in sample
- **geo** - Geographic location - Not found in sample

**CONCLUSION:** 
✅ **We're extracting 99% of useful data!** Only missing language detection.
✅ **Safe to purge raw_record** - All important fields already extracted to structured columns.
✅ **Optional enhancement:** Add `langs` JSONB column if multi-language feeds become important.

**TOTAL PROJECTED SAVINGS: ~280MB (75% database size reduction)**

**IMPLEMENTATION PRIORITY:** High - Massive cost savings with zero data loss risk

**Alternative Options (Not Selected):**
- [ ] **Option 2: Hybrid with summary** - Keep feed_posts but add JSON summary to posts for fast lookups. No space savings but faster queries
- [ ] **Option 3: Compress join table** - Use smaller data types (SMALLINT for feed_id), remove unused columns. Saves ~75-100MB (30-40% reduction)
- [ ] **Option 4: Partition by time** - Archive old posts (>30 days) to compressed storage. Saves ~70-80% depending on retention
- [ ] **Option 5: Single table with nullable feed columns** - Add feed_X_ingested_at columns to posts table. Saves ~60-70% but schema changes when adding feeds
- [ ] **Option 6: Enable PostgreSQL compression** - Compress existing tables at page level. Saves ~40-60% with 0-5% query slowdown, zero risk

### Performance Improvements
- [ ] Implement caching layer (Redis) for frequently accessed data
- [ ] Add database connection pooling optimization
- [ ] Optimize database queries with better indexing
- [ ] Implement pagination for large result sets

### 🚀 Complete Scaling Roadmap
**Current Status**: ~500-1000 concurrent users (after HTTP caching + connection pool increases)
**Target**: Scale to tens of thousands of users efficiently

## **Phase 0: COMPLETED ✅**
**What it is**: Basic optimizations to existing single-server setup
**What we did**:
- **HTTP Response Caching**: Browser caches API responses for 2-10 minutes, so 100 users = 1 database query instead of 100
- **Database Connection Pool**: Increased from 30 to 100 max connections so more users can query simultaneously
**Current Capacity**: ~500-1000 concurrent users
**Infrastructure**: Your current Proxmox setup is fine
**Additional Cost**: $0 (just code optimizations)

## **Phase 1: Launch Ready**
**What it is**: Add caching layer and optimize database performance
**What we'll do**:
- **Redis Caching**: Store frequently searched users/hashtags in memory so searches don't hit database
- **Database Indexing**: Add database indexes so queries run 5-10x faster
- **CloudFlare CDN**: Cache your website files globally so users load faster
- **Query Optimization**: Rewrite slow database queries to be faster
**Target Capacity**: 2,000-5,000 concurrent users
**Infrastructure**: Your current Proxmox setup still fine, just add Redis container
**Additional Cost**: $0 (Redis runs on your server, CloudFlare free tier)

## **Phase 2: Multiple Servers**
**What it is**: Run multiple copies of your app on different servers
**What we'll do**:
- **Multiple API Servers**: Run 2-3 copies of your FastAPI app behind a load balancer
- **Database Read Replicas**: Create copies of your database for reading data (writes still go to main DB)
- **Background Job Queue**: Move slow operations (like processing mentions) to background workers
- **Advanced CloudFlare**: Use CloudFlare's paid features to cache API responses globally
**Target Capacity**: 10,000-20,000 concurrent users
**Infrastructure**: Need multiple VPS servers or larger multi-core servers
**Additional Cost**: $100-300/month for additional servers

## **Phase 3: Enterprise Architecture**
**What it is**: Complete redesign for massive scale
**What we'll do**:
- **Microservices**: Split your app into separate services (user service, post service, etc.)
- **Database Sharding**: Split your database across multiple servers by feed or date
- **Auto-scaling**: Automatically add/remove servers based on traffic
- **Advanced Caching**: Multiple layers of caching with smart invalidation
**Target Capacity**: 50,000+ concurrent users
**Infrastructure**: Cloud platform with auto-scaling (AWS, Google Cloud, etc.)
**Additional Cost**: $500-2000/month depending on traffic

## **Server Requirements by Phase**

**Phase 0 (Current)**: Your Proxmox setup is perfect
**Phase 1**: Same Proxmox setup, maybe add 2-4GB RAM for Redis
**Phase 2**: Need 2-3 VPS servers (4-8 cores, 16GB RAM each) OR one big server (16+ cores, 64GB RAM)
**Phase 3**: Cloud infrastructure that scales automatically

## **When to Move to Each Phase**
- **Phase 1**: When you have 500+ regular users (do this before public launch)
- **Phase 2**: When you have 2,000+ regular users and site feels slow
- **Phase 3**: When you have 10,000+ regular users and making serious money

**Status**: Phase 0 complete, recommend Phase 1 before public launch

*Add new ideas below as they come up...*

---

## ⚠️ CRITICAL: WebSocket URL Format Documentation

**IMPORTANT**: The ingestion system supports TWO WebSocket URL formats:

### Format 1: Base URL Only (ORIGINAL WORKING FORMAT)
```
wss://api.graze.social/app/contrail
```
- **How it works**: Ingestion worker constructs full URL at runtime by appending `?feed=at://did:plc:lptjvw6ut224kwrj7ub3sqbe/app.bsky.feed.generator/{FEED_ID}`
- **Used by**: Original working feeds (3654, 5511, 5770)
- **Status**: CONFIRMED WORKING

### Format 2: Complete URL (NEW FORMAT)
```
wss://api.graze.social/app/contrail?feed=at://did:plc:lptjvw6ut224kwrj7ub3sqbe/app.bsky.feed.generator/{FEED_ID}
```
- **How it works**: Full URL stored in database, used directly
- **Used by**: New feeds created via admin interface
- **Status**: SHOULD WORK (ingestion worker handles both)

### Ingestion Worker Logic
From `backend/ingestion_worker.py` line ~1050:
```python
websocket_url = f"{base_url}?feed={urllib.parse.quote_plus(str(at_uri))}"
```

**If ingestion breaks after URL changes, revert to base URL format for all feeds:**
```sql
UPDATE feeds SET contrails_websocket_url = 'wss://api.graze.social/app/contrail' WHERE id IN ('3654', '5511', '5770');
```

**RESOLVED 2025-08-08**: 
- ✅ Reverted all feeds to base URL format for stable ingestion
- ✅ Updated admin interface to create feeds with base URLs
- ✅ Updated application form to use base URLs
- ✅ All new feeds and applications now use the working base URL format

**FUTURE IMPROVEMENT**: Refactor ingestion worker to accept full WebSocket URLs directly instead of constructing them. This would be cleaner and more intuitive for admin management.
