from enum import Enum

class Timeframe(str, Enum):
    HOUR = "1h"
    SIX_HOUR = "6h"
    DAY = "1d"
    WEEK = "7d"
    MONTH = "30d"
    ALL_TIME = "allTime"