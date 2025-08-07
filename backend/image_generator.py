import hashlib
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import httpx
import logging

logger = logging.getLogger(__name__)

class AchievementCardGenerator:
    def __init__(self, cache_dir: str = "/tmp/achievement_cards"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_key(self, user_avatar_url: str, achievement_name: str, user_name: str) -> str:
        """Generate cache key based on inputs"""
        content = f"{user_avatar_url}:{achievement_name}:{user_name}:v16_PERFECT"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        return os.path.join(self.cache_dir, f"{cache_key}.png")
    
    async def _download_avatar(self, avatar_url: str) -> Image.Image:
        """Download and process user avatar"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(avatar_url, timeout=10)
                response.raise_for_status()
                avatar = Image.open(BytesIO(response.content)).convert('RGBA')
                return avatar.resize((160, 160), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"Failed to download avatar {avatar_url}: {e}")
            # Return default avatar
            avatar = Image.new('RGBA', (160, 160), (64, 68, 75, 255))
            draw = ImageDraw.Draw(avatar)
            draw.ellipse([0, 0, 160, 160], fill=(100, 100, 100, 255))
            return avatar
    
    def _create_gradient_background(self, width: int, height: int) -> Image.Image:
        """Create gradient background"""
        img = Image.new('RGB', (width, height))
        draw = ImageDraw.Draw(img)
        
        # Create gradient from dark blue to purple
        for y in range(height):
            ratio = y / height
            r = int(43 + (88 - 43) * ratio)  # 43 -> 88
            g = int(45 + (101 - 45) * ratio)  # 45 -> 101
            b = int(49 + (242 - 49) * ratio)  # 49 -> 242
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        return img
    
    def _get_font(self, size: int):
        """Get font with multiple fallbacks"""
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ]
        
        for font_path in font_paths:
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue
        
        # If all fail, use default but make it MUCH bigger
        logger.warning(f"All fonts failed, using default with size {size * 3}")
        try:
            return ImageFont.load_default(size * 3)
        except:
            return ImageFont.load_default()
    
    async def generate_card(self, user_avatar_url: str, achievement_name: str, user_name: str, rarity_tier: str) -> str:
        """Generate achievement card and return file path"""
        cache_key = self._get_cache_key(user_avatar_url, achievement_name, user_name)
        cache_path = self._get_cache_path(cache_key)
        
        # Return cached version if exists
        if os.path.exists(cache_path):
            return cache_path
        
        # Create new card
        width, height = 1200, 630
        img = self._create_gradient_background(width, height)
        draw = ImageDraw.Draw(img)
        
        # Download and add user avatar
        avatar = await self._download_avatar(user_avatar_url)
        
        # Make avatar circular
        mask = Image.new('L', (160, 160), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, 160, 160], fill=255)
        
        # Create circular avatar
        circular_avatar = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        
        # Add white border around avatar
        border_size = 6
        border_avatar = Image.new('RGBA', (160 + border_size * 2, 160 + border_size * 2), (255, 255, 255, 255))
        border_mask = Image.new('L', (160 + border_size * 2, 160 + border_size * 2), 0)
        border_draw = ImageDraw.Draw(border_mask)
        border_draw.ellipse([0, 0, 160 + border_size * 2, 160 + border_size * 2], fill=255)
        border_avatar.putalpha(border_mask)
        
        # Paste bordered avatar
        img.paste(border_avatar, (width // 2 - 86, height // 2 - 86), border_avatar)
        img.paste(circular_avatar, (width // 2 - 80, height // 2 - 80), circular_avatar)
        
        # Add "feedmaster" text at top
        title_font = self._get_font(36)
        title_text = "feedmaster"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text((width // 2 - title_width // 2, 50), title_text, fill=(255, 255, 255), font=title_font)
        
        # Add achievement name
        achievement_font = self._get_font(14)
        achievement_bbox = draw.textbbox((0, 0), achievement_name, font=achievement_font)
        achievement_width = achievement_bbox[2] - achievement_bbox[0]
        draw.text((width // 2 - achievement_width // 2, height - 220), achievement_name, fill=(255, 255, 255), font=achievement_font)
        
        # Add user name
        user_font = self._get_font(12)
        user_bbox = draw.textbbox((0, 0), user_name, font=user_font)
        user_width = user_bbox[2] - user_bbox[0]
        draw.text((width // 2 - user_width // 2, height - 155), user_name, fill=(220, 221, 222), font=user_font)
        
        # Add rarity badge
        rarity_colors = {
            'Mythic': (255, 0, 255),
            'Legendary': (148, 0, 211),
            'Diamond': (185, 242, 255),
            'Platinum': (229, 228, 226),
            'Gold': (255, 215, 0),
            'Silver': (192, 192, 192),
            'Bronze': (205, 127, 50)
        }
        rarity_color = rarity_colors.get(rarity_tier, (205, 127, 50))
        
        rarity_font = self._get_font(10)
        rarity_text = f"{rarity_tier} Achievement"
        rarity_bbox = draw.textbbox((0, 0), rarity_text, font=rarity_font)
        rarity_width = rarity_bbox[2] - rarity_bbox[0]
        rarity_height = rarity_bbox[3] - rarity_bbox[1]
        
        # Draw rarity badge background - properly sized
        badge_padding = 6
        badge_x = width // 2 - rarity_width // 2 - badge_padding
        badge_y = height - 50 - rarity_height - badge_padding
        draw.rounded_rectangle([badge_x, badge_y, badge_x + rarity_width + (badge_padding * 2), badge_y + rarity_height + (badge_padding * 2)], 
                             radius=8, fill=rarity_color)
        draw.text((width // 2 - rarity_width // 2, height - 50 - rarity_height), rarity_text, fill=(0, 0, 0), font=rarity_font)
        
        # Save to cache
        img.save(cache_path, 'PNG', optimize=True)
        logger.info(f"Generated achievement card: {cache_path}")
        
        return cache_path

# Global instance
card_generator = AchievementCardGenerator()