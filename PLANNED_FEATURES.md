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

### Database Storage Optimization Options
**Current issue:** 245MB feed_posts table with 31k records, avg 1.07 feeds per post

- [ ] **Option 1: Full JSON replacement** - Replace feed_posts table with JSON array in posts table. Saves ~243MB (99% reduction) but makes aggregation queries harder
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

### 🚀 Scaling for Thousands of Users
**Current Capacity**: ~10-20 concurrent users comfortably, ~50-100 with slowdown
**Target**: Scale to thousands/tens of thousands of users

**Limiting Factors (in order of impact):**
1. **Database Connection Pool** - Currently ~10 connections, each user query blocks a connection
2. **No HTTP Caching** - Every user generates fresh database queries for same data
3. **Single API Server** - One FastAPI process handling all requests
4. **Database Query Performance** - Complex joins without proper indexing
5. **No CDN** - Static assets served from origin server

**Scaling Solutions:**
- [ ] **HTTP Response Caching** - Cache posts/aggregates for 2-5 minutes (10x capacity improvement)
- [ ] **Database Connection Pooling** - Increase to 50-100 connections with pgbouncer
- [ ] **Redis Caching Layer** - Cache frequent queries (user profiles, hashtag searches)
- [ ] **API Server Scaling** - Multiple FastAPI instances behind load balancer
- [ ] **Database Read Replicas** - Separate read/write databases
- [ ] **CDN Implementation** - CloudFlare for static assets and API caching
- [ ] **Database Indexing** - Add indexes for common query patterns
- [ ] **Background Job Queue** - Move heavy operations (mention processing) to background

**Quick Wins for 10x Capacity:**
1. Add HTTP caching headers (2 hours work, 10x improvement)
2. Increase database connections (30 minutes work, 3x improvement)
3. Add Redis for user/hashtag caching (4 hours work, 5x improvement)

**Status**: Critical for public launch

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

**Database change made on 2025-08-08**: Updated existing feeds from base URL to complete URL format. If this breaks ingestion, REVERT IMMEDIATELY using above SQL.
