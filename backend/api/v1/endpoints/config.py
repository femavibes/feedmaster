# backend/api/v1/endpoints/config.py
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any
from backend import schemas
from backend.config_utils import get_polling_config, save_polling_config

router = APIRouter()

@router.get("/polling", response_model=schemas.PollingConfig)
def read_polling_config():
    """
    Retrieve the current polling configuration.
    """
    config = get_polling_config()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Polling configuration file not found.")
    return config

@router.post("/polling", status_code=status.HTTP_204_NO_CONTENT)
def update_polling_config(config: schemas.PollingConfig):
    """
    Update the polling configuration.
    """
    try:
        save_polling_config(config)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to save configuration: {str(e)}")
    return