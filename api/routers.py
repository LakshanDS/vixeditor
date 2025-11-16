import uuid
import requests
import json
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Import project modules
from core.config import settings
from database import models as db_models
from database.models import get_db
from . import models as api_models
from .security import verify_master_key, verify_api_key

# ==============================================================================
# ADMIN ROUTER
# ==============================================================================
admin_router = APIRouter(prefix="/v1/admin", tags=["Admin"], dependencies=[Depends(verify_master_key)])

@admin_router.post("/keys/create", response_model=api_models.ApiKeyDetails)
def create_api_key(key_request: api_models.ApiKeyCreateRequest, db: Session = Depends(get_db)):
    new_key_obj = db_models.ApiKey(
        key=f"catv_{uuid.uuid4().hex}", 
        daily_limit=key_request.daily_limit, 
        minute_limit=key_request.minute_limit
    )
    db.add(new_key_obj)
    db.commit()
    db.refresh(new_key_obj)
    return new_key_obj

@admin_router.get("/keys", response_model=api_models.ApiKeyListResponse)
def get_all_api_keys(db: Session = Depends(get_db)):
    keys = db.query(db_models.ApiKey).all()
    return {"api_keys": keys}

@admin_router.put("/keys/update/{key_to_update}", response_model=api_models.ApiKeyDetails)
def update_api_key(key_to_update: str, update_data: api_models.ApiKeyUpdateRequest, db: Session = Depends(get_db)):
    key_obj = db.query(db_models.ApiKey).filter(db_models.ApiKey.key == key_to_update).first()
    if not key_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
    
    if update_data.daily_limit is not None:
        key_obj.daily_limit = update_data.daily_limit
    if update_data.minute_limit is not None:
        key_obj.minute_limit = update_data.minute_limit
        
    db.commit()
    db.refresh(key_obj)
    return key_obj


# ==============================================================================
# GENERATION ROUTER (Submit Jobs)
# ==============================================================================
generation_router = APIRouter(prefix="/v1", tags=["Video Generation"])

@generation_router.post("/generate", response_model=api_models.GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
def generate_video(
    video_request: api_models.VideoRequest,
    db: Session = Depends(get_db),
    api_key_valid: bool = Depends(verify_api_key)
):
    """
    Accepts a video generation request and adds it to the database queue.
    The separate background worker in main.py will pick this up automatically.
    """
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    
    # Create the job record
    new_job = db_models.Job(
        job_id=job_id, 
        request_data=video_request.model_dump_json()
    )
    db.add(new_job)
    db.commit()
    
    # Return immediately so the API remains responsive
    return {"job_id": job_id, "status": "in_queue"}


# ==============================================================================
# STATUS ROUTER (Check Progress & Download)
# ==============================================================================
status_router = APIRouter(prefix="/v1", tags=["Video Status & Download"])

@status_router.get("/status/{job_id}", response_model=api_models.StatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(db_models.Job).filter(db_models.Job.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    response_data = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "queue_position": None,
        "estimated_time_remaining_s": None
    }
    
    # Calculate queue position if still waiting
    if job.status == 'in_queue':
        position = db.query(db_models.Job).filter(
            db_models.Job.status == 'in_queue',
            db_models.Job.created_at < job.created_at
        ).count()
        response_data['queue_position'] = position + 1

    # Calculate ETA if rendering
    if job.status == 'rendering' and job.progress > 0 and job.start_time:
        now_utc = datetime.now(timezone.utc)
        start_time_aware = job.start_time.replace(tzinfo=timezone.utc)
        time_elapsed_s = (now_utc - start_time_aware).total_seconds()
        
        if time_elapsed_s > 0:
            total_estimated_time_s = time_elapsed_s / (job.progress / 100.0)
            time_remaining_s = total_estimated_time_s - time_elapsed_s
            response_data["estimated_time_remaining_s"] = max(0, int(time_remaining_s))

    # Provide filename if complete
    if job.status == "complete":
        response_data["filename"] = f"{job.output_filename}"

    return response_data

@status_router.get("/download/{filename}")
def download_video(filename: str):
    file_path = settings.OUTPUTS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    
    return FileResponse(path=file_path, media_type='video/mp4', filename=filename)


# ==============================================================================
# ASSETS ROUTER (List Styles, Audio, Fonts)
# ==============================================================================
assets_router = APIRouter(prefix="/v1/assets", tags=["Assets"], dependencies=[Depends(verify_api_key)])

@assets_router.get("/styles", response_model=api_models.StylesResponse)
def get_styles():
    styles = ["random"]
    if settings.STYLES_DIR.is_dir():
        file_styles = [f.stem for f in settings.STYLES_DIR.iterdir() if f.is_file() and f.suffix.lower() in ['.mp4', '.mov']]
        styles.extend(sorted(file_styles))
    return {"styles": styles}

@assets_router.get("/audios", response_model=api_models.AudiosResponse)
def get_audios():
    audios = []
    if settings.AUDIO_DIR.is_dir():
        audios = [f.name for f in settings.AUDIO_DIR.iterdir() if f.is_file()]
    return {"audios": sorted(audios)}

FONT_CACHE_TTL_SECONDS = 60 * 60 * 24 # 24 Hours

@assets_router.get("/fonts", response_model=api_models.FontsResponse)
def get_fonts():
    # 1. Get Local Fonts
    local_fonts = []
    if settings.FONTS_DIR.is_dir():
        for font_file in settings.FONTS_DIR.glob("**/*"):
            if font_file.is_file() and font_file.suffix.lower() in ['.ttf', '.otf']:
                local_fonts.append(font_file.stem)
    
    # 2. Get Google Fonts (Cached)
    google_fonts = []
    use_cache = False
    
    # Check if cache exists and is fresh
    if settings.FONT_CACHE_FILE.exists():
        if (time.time() - settings.FONT_CACHE_FILE.stat().st_mtime) < FONT_CACHE_TTL_SECONDS:
            use_cache = True
            
    if use_cache:
        with open(settings.FONT_CACHE_FILE, 'r') as f:
            try:
                google_fonts = json.load(f)
            except json.JSONDecodeError:
                use_cache = False # Force refresh if corrupt

    # 3. Fetch from API if cache is missing or stale
    if not use_cache:
        if settings.GOOGLE_FONTS_API_KEY:
            try:
                print("Fetching fresh font list from Google API...")
                url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={settings.GOOGLE_FONTS_API_KEY}"
                response = requests.get(url, timeout=5)
                response.raise_for_status()
                data = response.json()
                
                # Store just the family names for the list
                google_fonts = [item['family'] for item in data.get('items', [])]
                
                # Save to the cache directory (safe from server reload)
                settings.FONT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(settings.FONT_CACHE_FILE, 'w') as f:
                    json.dump(google_fonts, f)
                    
            except requests.exceptions.RequestException as e:
                print(f"Warning: Could not fetch Google Fonts. Error: {e}")
                # If API fails, fallback to whatever we might have or empty list
                if settings.FONT_CACHE_FILE.exists():
                    with open(settings.FONT_CACHE_FILE, 'r') as f:
                        google_fonts = json.load(f)

    return {"local_fonts": sorted(list(set(local_fonts))), "google_fonts": sorted(google_fonts)}