# backend/config.py
from pydantic_settings import BaseSettings

class EngagementSettings(BaseSettings):
    LIKE_WEIGHT: int = 1
    REPOST_WEIGHT: int = 2
    REPLY_WEIGHT: int = 3

settings = EngagementSettings()