import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def cleanup_old_files(outputs_dir: Path, retention_hours: int = 24):
    """
    Scans the outputs directory and deletes files older than the retention period.
    
    Args:
        outputs_dir: Path to the outputs directory
        retention_hours: Number of hours to retain files (default: 24)
    
    Returns:
        Tuple of (files_deleted_count, errors_count)
    """
    if not outputs_dir.exists() or not outputs_dir.is_dir():
        logger.warning(f"Outputs directory does not exist: {outputs_dir}")
        return 0, 0
    
    now = time.time()
    retention_seconds = retention_hours * 3600
    files_deleted = 0
    errors = 0
    
    logger.info(f"Starting cleanup for files older than {retention_hours} hours in {outputs_dir}")
    
    try:
        for file_path in outputs_dir.iterdir():
            if not file_path.is_file():
                continue
            
            try:
                # Get file modification time
                file_mtime = file_path.stat().st_mtime
                file_age_seconds = now - file_mtime
                
                # Check if file is older than retention period
                if file_age_seconds > retention_seconds:
                    file_age_hours = file_age_seconds / 3600
                    logger.info(f"Deleting old file: {file_path.name} (age: {file_age_hours:.1f} hours)")
                    
                    # Delete the file
                    file_path.unlink()
                    files_deleted += 1
                    
            except PermissionError:
                logger.error(f"Permission denied when trying to delete: {file_path.name}")
                errors += 1
            except OSError as e:
                logger.error(f"OS error when processing {file_path.name}: {e}")
                errors += 1
            except Exception as e:
                logger.error(f"Unexpected error when processing {file_path.name}: {e}")
                errors += 1
    
    except Exception as e:
        logger.error(f"Error scanning outputs directory: {e}")
        errors += 1
    
    if files_deleted > 0 or errors > 0:
        logger.info(f"Cleanup complete. Files deleted: {files_deleted}, Errors: {errors}")
    else:
        logger.debug(f"Cleanup complete. No files to delete.")
    
    return files_deleted, errors
