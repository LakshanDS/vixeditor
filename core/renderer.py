import time
import json
import random
import cv2
import numpy as np
import subprocess
import math
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from database.models import Job
from core.config import settings
from core.utils import (
    get_video_info, resize_and_crop_frame, apply_video_effects,
    prebake_text_overlay, prebake_image_asset, get_overlay_position,
    apply_prebaked_overlays
)

MIN_FINAL_FPS = 24.0
DB_UPDATE_INTERVAL_FRAMES = 30
logger = logging.getLogger(__name__)

def start_video_render(job_id: str, on_finish_callback: callable):
    logger.info(f"[{job_id}] Render job started.")
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    job = None
    
    cap, writer = None, None
    trimmed_source_path = settings.OUTPUTS_DIR / f"trimmed_{job_id}.mp4"

    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job: raise ValueError("Job not found.")

        job.status = "rendering"; job.start_time = datetime.now(timezone.utc); job.progress = 0
        db.commit()

        request = json.loads(job.request_data)
        video_settings = request.get('video', {})
        final_duration_s = video_settings.get('duration', 10)
        speed = video_settings.get('speed', 1.0)
        if speed <= 0: speed = 1.0
        
        required_source_duration = final_duration_s * speed

        style_name = video_settings.get('style', 'random')
        candidate_paths = list(settings.STYLES_DIR.glob("*.mp4")) if style_name == 'random' else [settings.STYLES_DIR / f"{style_name}.mp4"]
        valid_videos = [(p, get_video_info(str(p))) for p in candidate_paths if p.exists() and get_video_info(str(p)).get('duration', 0) > required_source_duration]
        if not valid_videos: raise ValueError("No suitable source videos found.")
        source_video_path, source_info = random.choice(valid_videos)
        start_time_s = random.uniform(0, source_info['duration'] - required_source_duration)
        
        logger.info(f"[{job_id}] Pre-trimming to get {required_source_duration:.2f}s clip.")
        command = ["ffmpeg", "-y", "-ss", str(start_time_s), "-t", str(required_source_duration), "-i", str(source_video_path), "-c", "copy", "-avoid_negative_ts", "make_zero", str(trimmed_source_path)]
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')

        logger.info(f"[{job_id}] Starting asset pre-baking...")
        asset_cache, prebaked_assets = {}, {}
        frame_shape = (1920, 1080, 3) # height, width, channels

        # --- Text Overlays with Advanced Positioning ---
        for i, text_item in enumerate(request.get('text_overlays', [])):
            result = prebake_text_overlay(text_item, (frame_shape[1], frame_shape[0]), asset_cache)
            if result is not None:
                overlay_array = result['array']
                is_pixel_pos = result['is_pixel_pos']
                positionxy = result['positionxy']
                margin = result['margin']
                font_align = text_item.get('font_align', 'center')
                
                # Calculate position based on mode
                pos = get_overlay_position(
                    frame_shape, 
                    overlay_array.shape, 
                    positionxy, 
                    margin, 
                    is_pixel_pos,
                    font_align  # Pass alignment for pixel mode
                )
                
                prebaked_assets[f'text_{i}'] = {
                    **text_item, 
                    'array': overlay_array, 
                    'position': pos
                }

        # --- Signature (treated as a text overlay) ---
        if 'signature' in request and request.get('signature'):
            sig_item = request['signature']
            result = prebake_text_overlay(sig_item, (frame_shape[1], frame_shape[0]), asset_cache)
            if result is not None:
                overlay_array = result['array']
                is_pixel_pos = result['is_pixel_pos']
                positionxy = result['positionxy']
                margin = result['margin']
                font_align = sig_item.get('font_align', 'center')
                
                pos = get_overlay_position(
                    frame_shape,
                    overlay_array.shape,
                    positionxy,
                    margin,
                    is_pixel_pos,
                    font_align  # Pass alignment for pixel mode
                )
                
                prebaked_assets['signature_0'] = {
                    **sig_item,
                    'array': overlay_array,
                    'position': pos
                }

        # --- Logo ---
        if 'logo' in request and request.get('logo'):
            logo_item = request['logo']
            logo_array = prebake_image_asset(logo_item, 'logo', asset_cache)
            if logo_array is not None:
                margin = logo_item.get('margin', [0, 25, 25, 0])
                positionxy = logo_item.get('positionxy', ['bottom', 'center'])
                pos = get_overlay_position(
                    frame_shape,
                    logo_array.shape,
                    positionxy,
                    margin,
                    is_pixel_pos=False  # Logos always use keyword positioning
                )
                prebaked_assets['logo_0'] = {
                    **logo_item,
                    'array': logo_array,
                    'position': pos
                }

        logger.info(f"[{job_id}] Asset pre-baking complete.")
        
        output_filename = f"{job_id}.mp4"
        output_path = settings.OUTPUTS_DIR / output_filename
        temp_video_path = settings.OUTPUTS_DIR / f"temp_{output_filename}"

        trimmed_info = get_video_info(str(trimmed_source_path))
        final_fps = trimmed_info.get('fps', 30)
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(temp_video_path), fourcc, final_fps, (1080, 1920))
        cap = cv2.VideoCapture(str(trimmed_source_path))
        if not cap.isOpened(): raise IOError("Could not open trimmed source video.")
        
        num_source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_output_frames = int(final_duration_s * final_fps)
        logger.info(f"[{job_id}] Processing {num_source_frames} frames to generate {total_output_frames} final frames.")

        frames_written_count = 0
        last_processed_frame = None
        
        for source_frame_index in range(num_source_frames):
            ret, frame = cap.read()
            if not ret:
                if last_processed_frame is None: break
                frame = last_processed_frame
            
            processed_frame = resize_and_crop_frame(frame)
            processed_frame = apply_video_effects(processed_frame, video_settings)
            blur_amount = video_settings.get('blur', 0)
            if blur_amount > 0:
                ksize = int(blur_amount) * 2 + 1 if int(blur_amount) % 2 != 0 else int(blur_amount) + 1
                processed_frame = cv2.GaussianBlur(processed_frame, (ksize, ksize), 0)
            
            last_processed_frame = processed_frame.copy()

            target_frames_after_this_source = math.floor((source_frame_index + 1) / speed)
            num_frames_to_write = target_frames_after_this_source - frames_written_count
            if num_frames_to_write <= 0: continue

            current_time_s = frames_written_count / final_fps
            final_frame = processed_frame.copy()
            if prebaked_assets:
                apply_prebaked_overlays(final_frame, prebaked_assets, current_time_s, final_duration_s)
            
            master_fade_in_s = video_settings.get('fade_in', 0)
            master_fade_out_s = video_settings.get('fade_out', 0)
            alpha = 1.0
            if master_fade_in_s > 0 and current_time_s < master_fade_in_s:
                alpha = current_time_s / master_fade_in_s
            time_at_fade_out_start = final_duration_s - master_fade_out_s
            if master_fade_out_s > 0 and current_time_s > time_at_fade_out_start:
                alpha = max(0, 1.0 - ((current_time_s - time_at_fade_out_start) / master_fade_out_s))
            
            if alpha < 1.0:
                final_frame = cv2.addWeighted(np.zeros_like(final_frame), 1 - alpha, final_frame, max(0, min(1, alpha)), 0)
            
            for _ in range(num_frames_to_write):
                if frames_written_count < total_output_frames:
                    writer.write(final_frame)
                    frames_written_count += 1
            
            if (source_frame_index + 1) % DB_UPDATE_INTERVAL_FRAMES == 0:
                job.progress = int((frames_written_count / total_output_frames) * 95)
                db.commit()

        logger.info(f"[{job_id}] Frame processing finished. Frames written: {frames_written_count}")
        
        if writer: writer.release(); writer = None
        if cap: cap.release(); cap = None
        
        audio_settings = request.get('audio', {})
        if audio_settings.get('audio') != 'none' and any(settings.AUDIO_DIR.iterdir()):
            selected_audio_path = random.choice(list(settings.AUDIO_DIR.glob("**/*.*")))
            command = ["ffmpeg", "-y", "-i", str(temp_video_path), "-i", str(selected_audio_path), "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(output_path)]
            subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
            temp_video_path.unlink()
        else:
            temp_video_path.rename(output_path)

        job.status = "complete"; job.progress = 100; job.output_filename = output_filename
        db.commit()
        logger.info(f"[{job_id}] Render complete.")

    except Exception as e:
        stderr_msg = str(e)
        if isinstance(e, subprocess.CalledProcessError):
            stderr_msg = e.stderr if e.stderr else 'No stderr'
        logger.error(f"[{job_id}] Render failed. Error: {stderr_msg}", exc_info=True)
        if job:
            job.status = "failed"; job.error_message = stderr_msg
            db.commit()
    finally:
        if cap: cap.release()
        if writer: writer.release()
        if db: db.close()
        if trimmed_source_path.exists():
            try:
                trimmed_source_path.unlink()
            except PermissionError as e:
                logger.error(f"Could not delete temp file '{trimmed_source_path}': {e}")
        logger.info(f"[{job_id}] Worker finished.")
        on_finish_callback()