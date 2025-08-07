# backend/achievements/definitions.py
#
# This file serves as the central source of truth for achievement rarity tiers.
# It defines the names, labels, and percentage thresholds for each tier.
# A background process should use these definitions to periodically update the
# rarity_tier and rarity_label for all achievements in the database.

from typing import List, Dict, TypedDict


class RarityTier(TypedDict):
    name: str      # Clean, machine-readable name (e.g., "Gold")
    label: str     # User-facing display name (e.g., "Gold")
    threshold: float # The upper bound percentage for this tier (e.g., 10.0 for 10%)


# The list must be ordered from most rare (lowest percentage) to least rare.
RARITY_TIERS: List[RarityTier] = [
    {"name": "Mythic",    "label": "Mythic",    "threshold": 0.1},
    {"name": "Legendary", "label": "Legendary", "threshold": 1.0},
    {"name": "Diamond",   "label": "Diamond",   "threshold": 2.0},
    {"name": "Platinum",  "label": "Platinum",  "threshold": 5.0},
    {"name": "Gold",      "label": "Gold",      "threshold": 10.0},
    {"name": "Silver",    "label": "Silver",    "threshold": 25.0},
    {"name": "Bronze",    "label": "Bronze",    "threshold": 100.0},
]


def get_rarity_tier_from_percentage(percentage: float) -> RarityTier:
    """Determines the rarity tier based on a given percentage."""
    for tier in RARITY_TIERS:
        if percentage <= tier["threshold"]:
            return tier
    return RARITY_TIERS[-1] # Default to the last tier (Bronze)