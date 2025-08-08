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

*Add new ideas below as they come up...*
