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

## 📝 Future Feature Ideas

*Add new ideas below as they come up...*
