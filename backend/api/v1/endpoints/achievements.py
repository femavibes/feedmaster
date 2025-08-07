from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc, text
from backend.database import get_db
from backend import models, crud
from backend.image_generator import card_generator
from datetime import datetime
from typing import Optional, List
import os

router = APIRouter()

@router.get("/{user_did}/{achievement_identifier}", response_class=HTMLResponse)
async def get_achievement_share_page(
    user_did: str,
    achievement_identifier: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a shareable HTML page for a specific user's achievement.
    """
    try:
        # Get user info
        user = await crud.get_user(db, user_did)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user achievements
        user_achievements = await crud.get_user_achievements(db, user_did)
        
        # Find the specific achievement by ID or name
        target_achievement = None
        for ua in user_achievements:
            if (str(ua.achievement.id) == achievement_identifier or 
                ua.achievement.name.replace(' ', '_').lower() == achievement_identifier.lower() or
                ua.achievement.name == achievement_identifier):
                target_achievement = ua
                break
        
        if not target_achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")
        
        # Simple analytics: log the page view (you could store this in database)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Achievement share page viewed: {user.handle} - {target_achievement.achievement.name}")
        
        # Generate the HTML page with rich meta tags
        achievement = target_achievement.achievement
        feed_context = f" in {target_achievement.feed.name}" if target_achievement.feed else ""
        
        rarity_tier = achievement.rarity_tier or "Bronze"
        rarity_icon = {
            'Mythic': '✨',
            'Legendary': '👑', 
            'Diamond': '💠',
            'Platinum': '💿',
            'Gold': '🥇',
            'Silver': '🥈',
            'Bronze': '🥉'
        }.get(rarity_tier, '🏅')
        
        title = f"{rarity_icon} {user.display_name or user.handle} earned {achievement.name}!"
        description = f"{achievement.description} • {rarity_tier} rarity ({achievement.rarity_percentage:.2f}% of users){feed_context}"
        
        # Generate achievement card image
        card_path = await card_generator.generate_card(
            user.avatar_url or 'https://via.placeholder.com/400x400',
            achievement.name,
            user.display_name or user.handle,
            rarity_tier
        )
        
        # Use generated card as og:image with aggressive cache busting
        import time
        cache_bust = int(time.time())  # Changes every second
        # Use HTTPS for public URLs
        base_url = str(request.base_url).replace('http://', 'https://')
        card_url = f"{base_url}achievement/{user_did}/{achievement_identifier}/card.png?t={cache_bust}&massive=true"
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    
    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{request.url}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{card_url}">
    <meta property="og:site_name" content="Feedmaster">
    
    <!-- Twitter -->
    <meta property="twitter:card" content="summary_large_image">
    <meta property="twitter:url" content="{request.url}">
    <meta property="twitter:title" content="{title}">
    <meta property="twitter:description" content="{description}">
    <meta property="twitter:image" content="{card_url}">
    
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #2b2d31 0%, #1e1f23 100%);
            color: #dcddde;
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .achievement-card {{
            background: #313338;
            border: 1px solid #404249;
            border-radius: 16px;
            padding: 2rem;
            max-width: 500px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
        }}
        .user-info {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .avatar {{
            width: 60px;
            height: 60px;
            border-radius: 50%;
            border: 2px solid #404249;
        }}
        .user-details h2 {{
            margin: 0;
            color: #fff;
        }}
        .user-details p {{
            margin: 0;
            color: #949ba4;
        }}
        .achievement-icon {{
            font-size: 4rem;
            margin-bottom: 1rem;
        }}
        .achievement-name {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #fff;
            margin-bottom: 0.5rem;
        }}
        .achievement-description {{
            color: #b5bac1;
            margin-bottom: 1.5rem;
            line-height: 1.4;
        }}
        .rarity-badge {{
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 2rem;
        }}
        .rarity-bronze {{ background-color: #cd7f32; }}
        .rarity-silver {{ background-color: #c0c0c0; color: #333; }}
        .rarity-gold {{ background-color: #ffd700; color: #333; }}
        .rarity-platinum {{ background-color: #e5e4e2; color: #333; }}
        .rarity-diamond {{ background-color: #b9f2ff; color: #333; }}
        .rarity-legendary {{ background-color: #9400d3; }}
        .rarity-mythic {{
            background: linear-gradient(45deg, #ff00ff, #ff9900, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff);
            background-size: 400% 400%;
            animation: gradient 3s ease infinite;
        }}
        .explore-btn {{
            background: linear-gradient(135deg, #5865f2, #7289da);
            color: white;
            border: none;
            padding: 1rem 2rem;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            transition: transform 0.2s ease;
        }}
        .explore-btn:hover {{
            transform: translateY(-2px);
        }}
        .branding {{
            margin-top: 2rem;
            color: #72767d;
            font-size: 0.9rem;
        }}
        @keyframes gradient {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
    </style>
</head>
<body>
    <div class="achievement-card">
        <div class="user-info">
            <img src="{user.avatar_url or 'https://via.placeholder.com/60'}" alt="Avatar" class="avatar">
            <div class="user-details">
                <h2>{user.display_name or user.handle}</h2>
                <p>@{user.handle}</p>
            </div>
        </div>
        
        <div class="achievement-icon">{rarity_icon}</div>
        <div class="achievement-name">{achievement.name}</div>
        <div class="achievement-description">{achievement.description}</div>
        
        <div class="rarity-badge rarity-{rarity_tier.lower()}">
            {rarity_tier} • {achievement.rarity_percentage:.2f}% of users
        </div>
        
        <a href="https://feedmaster.fema.monster" class="explore-btn">
            🚀 Explore Feedmaster
        </a>
        
        <div class="branding">
            powered by feedmaster
        </div>
    </div>
</body>
</html>
        """
        
        return HTMLResponse(content=html_content)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_did}/{achievement_identifier}/card.png", response_class=FileResponse)
async def get_achievement_card_image(
    user_did: str,
    achievement_identifier: str,
    v: str = None,  # Cache busting parameter
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the generated achievement card image.
    """
    try:
        # Get user info
        user = await crud.get_user(db, user_did)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user achievements
        user_achievements = await crud.get_user_achievements(db, user_did)
        
        # Find the specific achievement
        target_achievement = None
        for ua in user_achievements:
            if (str(ua.achievement.id) == achievement_identifier or 
                ua.achievement.name.replace(' ', '_').lower() == achievement_identifier.lower() or
                ua.achievement.name == achievement_identifier):
                target_achievement = ua
                break
        
        if not target_achievement:
            raise HTTPException(status_code=404, detail="Achievement not found")
        
        # Generate card image
        card_path = await card_generator.generate_card(
            user.avatar_url or 'https://via.placeholder.com/400x400',
            target_achievement.achievement.name,
            user.display_name or user.handle,
            target_achievement.achievement.rarity_tier or "Bronze"
        )
        
        return FileResponse(card_path, media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent")
async def get_recent_achievements(
    feed_ids: str = Query(..., description="Comma-separated feed IDs"),
    since: Optional[datetime] = Query(None, description="ISO datetime to get achievements since"),
    limit: int = Query(50, description="Maximum number of achievements to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent achievements for specified feeds.
    Used by bots to poll for new achievements.
    """
    try:
        # Parse feed IDs
        feed_id_list = [fid.strip() for fid in feed_ids.split(',') if fid.strip()]
        
        if not feed_id_list:
            raise HTTPException(status_code=400, detail="At least one feed_id required")
        
        # Simple query using raw SQL for reliability
        since_clause = ""
        params = {"feed_ids": tuple(feed_id_list), "limit": limit}
        
        if since:
            since_clause = "AND ua.earned_at >= :since"
            params["since"] = since
        
        query = f"""
        SELECT 
            ua.id,
            ua.user_did,
            u.handle as user_handle,
            u.display_name as user_display_name,
            a.name as achievement_name,
            a.description as achievement_description,
            COALESCE(afr.rarity_tier, a.rarity_tier) as rarity_tier,
            COALESCE(afr.rarity_percentage, a.rarity_percentage) as rarity_percentage,
            ua.feed_id,
            f.name as feed_name,
            ua.earned_at
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        JOIN users u ON ua.user_did = u.did
        LEFT JOIN feeds f ON ua.feed_id = f.id
        LEFT JOIN achievement_feed_rarity afr ON (a.id = afr.achievement_id AND ua.feed_id = afr.feed_id)
        WHERE ua.feed_id = ANY(:feed_ids)
        {since_clause}
        ORDER BY ua.earned_at DESC
        LIMIT :limit
        """
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        # Format response
        achievements = []
        for row in rows:
            achievements.append({
                "id": row.id,
                "user_did": row.user_did,
                "user_handle": row.user_handle,
                "user_display_name": row.user_display_name,
                "achievement_name": row.achievement_name,
                "achievement_description": row.achievement_description,
                "rarity_tier": row.rarity_tier,
                "rarity_percentage": float(row.rarity_percentage) if row.rarity_percentage else 0.0,
                "feed_id": row.feed_id,
                "feed_name": row.feed_name,
                "earned_at": row.earned_at.isoformat(),
                "share_url": f"https://feedmaster.fema.monster/achievement/{row.user_did}/{row.achievement_name}"
            })
        
        return {
            "achievements": achievements,
            "count": len(achievements),
            "feed_ids": feed_id_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))