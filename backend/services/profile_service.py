# backend/services/profile_service.py

from typing import Optional
# Import the centralized definitions to ensure consistency
from backend.achievements.definitions import get_rarity_tier_from_percentage, RARITY_TIERS

def get_rarity_label(rarity_percentage: Optional[float]) -> str:
    """
    Converts a rarity percentage into a human-readable label using the
    centralized rarity tier definitions.
    """
    if rarity_percentage is None:
        # Default to the least rare tier's name if percentage is unknown
        return RARITY_TIERS[-1]["name"]
    
    # Get the full tier object and return its name (the clean label, e.g., "Gold")
    tier = get_rarity_tier_from_percentage(rarity_percentage)
    return tier["name"]