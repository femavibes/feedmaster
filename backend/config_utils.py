# backend/config_utils.py
import json
import os
from typing import Dict, Any
import logging
from backend import schemas

CONFIG_DIR = "config"
POLLING_CONFIG_PATH = os.path.join(CONFIG_DIR, "polling_config.json")
logger = logging.getLogger(__name__)

def get_polling_config() -> Dict[str, Any]:
    """Reads the polling configuration from the JSON file."""
    if not os.path.exists(POLLING_CONFIG_PATH):
        logger.error(f"Polling config file not found at {POLLING_CONFIG_PATH}")
        return {}
    with open(POLLING_CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_polling_config(config_data: schemas.PollingConfig) -> None:
    """Saves the polling configuration to the JSON file."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(POLLING_CONFIG_PATH, 'w') as f:
        json.dump(config_data.model_dump(), f, indent=2)
    logger.info(f"Successfully saved polling configuration to {POLLING_CONFIG_PATH}")