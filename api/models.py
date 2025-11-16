# File: api/models.py

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union, Tuple

# --- Video Generation Models ---

class VideoSettings(BaseModel):
    style: str = "random"
    exposure: float = Field(1.0, ge=0.0, le=2.0)
    brightness: float = Field(1.0, ge=0.0, le=2.0)
    contrast: float = Field(1.0, ge=0.0, le=2.0)
    saturation: float = Field(1.0, ge=0.0, le=2.0)
    fade_in: int = Field(0, ge=0)
    fade_out: int = Field(0, ge=0)
    duration: int = 15
    speed: float = Field(0.5, gt=0.0)
    blur: Optional[int] = Field(0, ge=0)

class AudioSettings(BaseModel):
    audio: str = "random"
    volume: float = Field(1.0, ge=0.0, le=2.0)
    fade_in: int = 2
    fade_out: int = 2

class TextOverlay(BaseModel):
    text: str
    font: str = "Arial"
    font_size: int = 30
    font_align: str = "center"
    font_color: str = "white"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    fade_in: float = Field(0.0, ge=0.0)
    fade_out: float = Field(0.0, ge=0.0)
    positionxy: List[Union[str, int]] = Field(default_factory=lambda: ["center", "center"])
    margin: Optional[Tuple[int, int, int, int]] = (0,0,0,0)

    @validator('positionxy')
    def validate_positionxy(cls, v):
        if len(v) not in [2, 3]:
            raise ValueError('positionxy must have 2 or 3 items.')
        is_numeric = isinstance(v[0], (int, float))
        if is_numeric:
            if not all(isinstance(i, (int, float)) for i in v):
                raise ValueError('If using numeric coordinates, all items in positionxy must be numbers.')
        else:
            if len(v) != 2 or not all(isinstance(i, str) for i in v):
                raise ValueError('If using string coordinates, positionxy must be a 2-item list of strings (e.g., ["center", "top"]).')
        return v
    
class SignatureSettings(TextOverlay):
    opacity: float = Field(0.5, ge=0.0, le=1.0)

class LogoSettings(BaseModel):
    name: str
    size: int = 150
    positionxy: Tuple[Union[str, int], Union[str, int]] = ("bottom", "center")
    margin: Optional[Tuple[int, int, int, int]] = (0, 25, 25, 0)
    opacity: float = Field(1.0, ge=0.0, le=1.0)
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class VideoRequest(BaseModel):
    video: VideoSettings
    audio: Optional[AudioSettings] = None
    text_overlays: Optional[List[TextOverlay]] = None
    signature: Optional[SignatureSettings] = None
    logo: Optional[LogoSettings] = None

# --- Admin Models ---
class ApiKeyCreateRequest(BaseModel):
    daily_limit: int = 1000
    minute_limit: int = 10

class ApiKeyDetails(BaseModel):
    key: str
    daily_limit: int
    minute_limit: int
    class Config: from_attributes = True 

class ApiKeyListResponse(BaseModel):
    api_keys: List[ApiKeyDetails]

class ApiKeyUpdateRequest(BaseModel):
    daily_limit: Optional[int] = None
    minute_limit: Optional[int] = None

# --- Asset Response Models ---
class StylesResponse(BaseModel):
    styles: List[str]

class AudiosResponse(BaseModel):
    audios: List[str]

class FontsResponse(BaseModel):
    local_fonts: List[str]
    google_fonts: List[str]

class GenerateResponse(BaseModel):
    job_id: str
    status: str = "in_queue"

class StatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[int] = None
    filename: Optional[str] = None
    queue_position: Optional[int] = None
    estimated_time_remaining_s: Optional[int] = None