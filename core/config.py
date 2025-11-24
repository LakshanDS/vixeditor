import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Define the absolute path to the project's root directory
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # --- Admin & Security ---
    MASTER_KEY: str
    MASTER_IP: str | None = None # Marked as optional as seen in .env

    # --- Google API ---
    GOOGLE_FONTS_API_KEY: str | None = None

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'catvideo.db'}"
    
    # --- Cleanup Settings ---
    OUTPUT_RETENTION_HOURS: int = 24  # Delete output files older than this many hours
    CLEANUP_INTERVAL_MINUTES: int = 60  # Run cleanup check every this many minutes

    # --- Directory Paths ---
    STYLES_DIR: Path = BASE_DIR / "source/videos/styles"
    AUDIO_DIR: Path = BASE_DIR / "source/audio"
    FONTS_DIR: Path = BASE_DIR / "source/fonts"
    LOGO_DIR: Path = BASE_DIR / "source/logo"
    OUTPUTS_DIR: Path = BASE_DIR / "outputs"
    VIDEOS_DIR: Path = BASE_DIR / "source/videos"
    CACHE_DIR: Path = BASE_DIR / "cache"
    FONT_CACHE_DIR: Path = FONTS_DIR / "google"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # --- File Paths ---
    FONT_CACHE_FILE: Path = CACHE_DIR / "google_fonts_cache.json"
    VIDEO_INFO_CACHE_FILE: Path = CACHE_DIR / "video_info_cache.json"
    STYLE_SKIPS_FILE: Path = STYLES_DIR / "style_skips.json"
    LOG_FILE: Path = LOGS_DIR / "catvideo.log"

    class Config:
        # Pydantic will automatically read from this file
        env_file = ".env"
        env_file_encoding = 'utf-8'

# Create a single, reusable instance of the settings
settings = Settings()

# --- Utility function to create directories on startup ---
def ensure_directories_exist():
    """Checks if required directories exist and creates them if not."""
    print("Checking if required directories exist...")
    dirs_to_check = [
        settings.STYLES_DIR,
        settings.AUDIO_DIR,
        settings.FONTS_DIR,
        settings.LOGO_DIR,
        settings.OUTPUTS_DIR,
        settings.VIDEOS_DIR,
        settings.CACHE_DIR,
        settings.FONT_CACHE_DIR,
        settings.LOGS_DIR,
    ]
    for dir_path in dirs_to_check:
        dir_path.mkdir(parents=True, exist_ok=True)
    print("All required directories are present.")