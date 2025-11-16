# File: api/security.py

import time
from collections import defaultdict
from fastapi import Security, HTTPException, status, Request, Depends
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from core.config import settings
from database import models as db_models
from database.models import get_db

# --- In-memory storage for rate limiting ---
# { "api_key_string": [timestamp1, timestamp2, ...], ... }
# defaultdict(list) means if a key doesn't exist, it's created with an empty list
request_timestamps = defaultdict(list)


# ==============================================================================
# MASTER KEY VERIFICATION (No Changes Here)
# ==============================================================================
master_key_scheme = APIKeyHeader(name="X-Master-Key", scheme_name="MasterKeyAuth", auto_error=False)

async def verify_master_key(request: Request, api_key: str = Security(master_key_scheme)):
    # ... (this function is unchanged)
    if settings.MASTER_IP and request.client.host != settings.MASTER_IP:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden.")
    if api_key is None or api_key != settings.MASTER_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing Master Key")
    return True

# ==============================================================================
# REGULAR API KEY VERIFICATION (Updated with Rate Limiting Logic)
# ==============================================================================
user_api_key_scheme = APIKeyHeader(name="X-API-Key", scheme_name="UserAPIKeyAuth", auto_error=False)

async def verify_api_key(
    api_key: str = Security(user_api_key_scheme),
    db: Session = Depends(get_db)
):
    """
    Checks if a user API key is valid AND enforces the per-minute rate limit.
    """
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API Key")

    # 1. Check if the key exists in the database
    db_key = db.query(db_models.ApiKey).filter(db_models.ApiKey.key == api_key).first()
    if not db_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")

    # --- NEW: RATE LIMITING LOGIC ---
    current_time = time.time()
    
    # Get the list of timestamps for this key
    timestamps = request_timestamps[api_key]
    
    # Remove timestamps that are older than 60 seconds
    # We build a new list for efficiency instead of removing in-place
    valid_timestamps = [t for t in timestamps if current_time - t < 60]
    
    # Check if the number of recent requests exceeds the limit
    if len(valid_timestamps) >= db_key.minute_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Try again in a minute."
        )
    
    # Add the current request's timestamp and update the dictionary
    valid_timestamps.append(current_time)
    request_timestamps[api_key] = valid_timestamps
    # --- END OF RATE LIMITING LOGIC ---
    
    return True