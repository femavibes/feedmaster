from datetime import datetime, timedelta
from typing import Optional

def get_start_time(timeframe: str) -> Optional[datetime]:
    """
    Calculates the start time based on a given timeframe string.
    Returns a datetime object for the start time, or None for 'allTime'.
    """
    now = datetime.utcnow()
    
    time_deltas = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    
    if timeframe in time_deltas:
        return now - time_deltas[timeframe]
    elif timeframe == "allTime":
        return Nonecd
    
    # Default to 1 day if an unknown timeframe is provided.
    return now - timedelta(days=1)