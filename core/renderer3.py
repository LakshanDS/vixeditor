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
from core.utils import get_video_info, resize_and_crop_frame, draw_overlays_on_frame, apply_video_effects

MIN_FINAL_FPS = 24.0
logger = logging.getLogger(__name__)

def start_video_render(job_id: str, on_finish_callback: callable):
    logger.info(f"[{job_id}] Render job started.")
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    job = None
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            raise ValueError("Job not found in database.")

        job.status = "rendering"
        job.start_time = datetime.now(timezone.utc)
        job.progress = 0
        db.commit()

        request = json.loads(job.request_data)
        video_settings = request.get('video', {}) # Use .get for safety
        final_duration_s = video_settings.get('duration', 10) # Default duration
        speed = video_settings.get('speed', 1.0)
        master_fade_in_s = video_settings.get('fade_in', 0)
        master_fade_out_s = video_settings.get('fade_out', 0)
        required_source_duration = final_duration_s * speed

        style_name = video_settings.get('style', 'random')
        candidate_paths = list(settings.STYLES_DIR.glob("*.mp4")) if style_name == 'random' else [settings.STYLES_DIR / f"{style_name}.mp4"]
        valid_videos = []
        for video_path in candidate_paths:
            if not video_path.exists():
                continue
            info = get_video_info(video_path)
            if not info or info.get('duration', 0) <= required_source_duration:
                continue
            source_fps = info.get('fps', 0)
            if speed < 1.0 and (source_fps * speed) < MIN_FINAL_FPS:
                continue
            valid_videos.append((video_path, info))

        if not valid_videos:
            raise ValueError("No suitable source videos found meeting duration and FPS criteria.")

        source_video_path, source_info = random.choice(valid_videos)
        logger.info(f"[{job_id}] Selected source video: {source_video_path.name}")
        logger.debug(f"[{job_id}] Source video details: {source_info}")
        source_fps = source_info.get('fps', 30)

        # --- Calculate valid start time based on skip intervals ---
        skips_path = settings.STYLE_SKIPS_FILE
        skip_intervals = []
        if skips_path.exists():
            with open(skips_path, 'r') as f:
                all_skips = json.load(f)
                style_key = source_video_path.stem
                if style_key in all_skips:
                    skip_intervals = all_skips[style_key]

        valid_intervals = []
        last_end_time = 0
        video_duration = source_info['duration']

        for skip in sorted(skip_intervals, key=lambda x: x['start']):
            if skip['start'] > last_end_time:
                valid_intervals.append({'start': last_end_time, 'end': skip['start']})
            last_end_time = skip['end']

        if video_duration > last_end_time:
            valid_intervals.append({'start': last_end_time, 'end': video_duration})

        if not valid_intervals:
            valid_intervals.append({'start': 0, 'end': video_duration})

        possible_start_ranges = []
        total_possible_duration = 0
        for interval in valid_intervals:
            max_start = interval['end'] - required_source_duration
            if max_start > interval['start']:
                duration = max_start - interval['start']
                possible_start_ranges.append({'start': interval['start'], 'end': max_start, 'duration': duration})
                total_possible_duration += duration

        if not possible_start_ranges:
            raise ValueError("No suitable time slot found in source video to fit the required duration.")

        random_point = random.uniform(0, total_possible_duration)
        start_time_s = 0
        for r in possible_start_ranges:
            if random_point < r['duration']:
                start_time_s = r['start'] + random_point
                break
            random_point -= r['duration']
        
        logger.debug(f"[{job_id}] Calculated source start time: {start_time_s:.2f}s")

        # --- NEW FFmpeg PRE-TRIMMING LOGIC ---
        logger.info(f"[{job_id}] Pre-trimming source video with FFmpeg for faster processing.")

        # Define a path for the temporary trimmed video
        trimmed_source_path = settings.OUTPUTS_DIR / f"trimmed_{job_id}.mp4"

        # Build the FFmpeg command
        # -ss: seek start time
        # -t: duration
        # -i: input file
        # -c copy: stream copy (no re-encoding, extremely fast)
        # -avoid_negative_ts make_zero: fixes a common issue with cutting
        command = [
            "ffmpeg",
            "-y", # Overwrite output file if it exists
            "-ss", str(start_time_s),
            "-t", str(required_source_duration),
            "-i", str(source_video_path),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(trimmed_source_path)
        ]

        try:
            # Run the command and wait for it to complete
            subprocess.run(command, check=True, capture_output=True, text=True)
            logger.info(f"[{job_id}] FFmpeg pre-trimming successful.")
        except subprocess.CalledProcessError as e:
            logger.error(f"[{job_id}] FFmpeg pre-trimming failed. Stderr: {e.stderr}", exc_info=True)
            raise # Re-raise the exception to stop the job
        # --- END OF NEW LOGIC ---

        # --- Setup Video I/O ---
        output_filename = f"{job_id}.mp4"
        output_path = settings.OUTPUTS_DIR / output_filename
        temp_video_path = settings.OUTPUTS_DIR / f"temp_{output_filename}"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        final_fps = source_fps
        writer = cv2.VideoWriter(str(temp_video_path), fourcc, final_fps, (1080, 1920))

        # Use the new, trimmed video file as the source
        cap = cv2.VideoCapture(str(trimmed_source_path))
        if not cap.isOpened():
            raise IOError(f"OpenCV could not open the trimmed source video file: {trimmed_source_path}")

        logger.info(f"[{job_id}] Writing to {temp_video_path.name} at {final_fps} FPS.")
        total_output_frames_to_write = int(final_duration_s * final_fps)
        num_source_frames_to_read = math.ceil(required_source_duration * source_fps)
        logger.debug(f"[{job_id}] Will read {num_source_frames_to_read} source frames to write {total_output_frames_to_write} final frames.")

        frames_written = 0
        asset_cache = {}

        def process_and_write(frame_to_process, source_index):
            nonlocal frames_written
            processed_frame = resize_and_crop_frame(frame_to_process)
            processed_frame = apply_video_effects(processed_frame, video_settings)

            blur_amount = video_settings.get('blur', 0)
            if blur_amount > 0:
                ksize = int(blur_amount) * 2 + 1
                processed_frame = cv2.GaussianBlur(processed_frame, (ksize, ksize), 0)

            start_write_index = int(source_index / speed)
            end_write_index = int((source_index + 1) / speed)

            for _ in range(start_write_index, end_write_index):
                if frames_written >= total_output_frames_to_write:
                    return True  # Signal to stop

                current_time_in_seconds = frames_written / final_fps
                final_frame = draw_overlays_on_frame(processed_frame.copy(), request, current_time_in_seconds, asset_cache)

                if master_fade_in_s > 0 and current_time_in_seconds < master_fade_in_s:
                    alpha = current_time_in_seconds / float(master_fade_in_s)
                    final_frame = cv2.addWeighted(np.zeros_like(final_frame), 1 - alpha, final_frame, alpha, 0)
                
                time_at_fade_out_start = final_duration_s - master_fade_out_s
                if master_fade_out_s > 0 and current_time_in_seconds > time_at_fade_out_start:
                    time_into_fade = current_time_in_seconds - time_at_fade_out_start
                    alpha = max(0, 1.0 - (time_into_fade / float(master_fade_out_s)))
                    final_frame = cv2.addWeighted(np.zeros_like(final_frame), 1 - alpha, final_frame, alpha, 0)
                
                writer.write(final_frame)
                frames_written += 1
            return frames_written >= total_output_frames_to_write

        # --- Main Frame Processing Loop (Simplified) ---
        # We can now read frames sequentially from the start of the trimmed video
        for i in range(num_source_frames_to_read):
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"[{job_id}] Stopped reading source frames early at frame {i}. Trimmed video stream ended.")
                break
            
            if process_and_write(frame, i):
                logger.info(f"[{job_id}] Reached target frame count. Breaking loop.")
                break
            
            current_progress = int(((i + 1) / num_source_frames_to_read) * 95)
            if current_progress > job.progress:
                job.progress = current_progress
                db.commit()

        logger.info(f"[{job_id}] Frame processing loop finished. Total frames written: {frames_written}")
        cap.release()
        writer.release()

        if frames_written == 0:
            raise ValueError("No frames were written. Check logs for open/seek errors.")

        # --- Audio Muxing with FFmpeg ---
        audio_settings = request.get('audio', {})
        if not audio_settings or audio_settings.get('audio') == 'none':
            logger.info(f"[{job_id}] No audio requested. Renaming temp video to final output.")
            temp_video_path.rename(output_path)
        else:
            audio_files = list(settings.AUDIO_DIR.glob("**/*.*"))
            if not audio_files:
                logger.warning(f"[{job_id}] Audio was requested, but no audio files found in {settings.AUDIO_DIR}. Renaming video without audio.")
                temp_video_path.rename(output_path)
            else:
                selected_audio_path = random.choice(audio_files)
                command = ["ffmpeg", "-y", "-i", str(temp_video_path), "-i", str(selected_audio_path), "-c:v", "copy"]
                audio_filters = []
                volume = audio_settings.get('volume', 1.0)
                fade_in = audio_settings.get('fade_in', 0)
                fade_out = audio_settings.get('fade_out', 0)
                if volume != 1.0:
                    audio_filters.append(f"volume={volume}")
                if fade_in > 0:
                    audio_filters.append(f"afade=t=in:d={fade_in}")
                if fade_out > 0:
                    fade_out_start = final_duration_s - fade_out
                    if fade_out_start > 0:
                        audio_filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out}")
                if audio_filters:
                    command.extend(["-af", ",".join(audio_filters)])
                
                command.extend(["-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(output_path)])
                logger.info(f"[{job_id}] Running FFmpeg command to add audio: {' '.join(command)}")
                subprocess.run(command, check=True, capture_output=True)
                temp_video_path.unlink()

        job.status = "complete"
        job.progress = 100
        job.output_filename = output_filename
        db.commit()
        logger.info(f"[{job_id}] Render complete. Output: {output_filename}")

    except Exception as e:
        if isinstance(e, subprocess.CalledProcessError):
            stderr = e.stderr.decode(errors='ignore') if e.stderr else 'No stderr'
            logger.error(f"[{job_id}] FFmpeg execution failed. Stderr: {stderr}", exc_info=True)
        else:
            logger.error(f"[{job_id}] An error occurred during rendering.", exc_info=True)

        if job:
            job.status = "failed"
            db.commit()
    finally:
        db.close()
        # Clean up the temporary trimmed source video
        if 'trimmed_source_path' in locals() and trimmed_source_path.exists():
            trimmed_source_path.unlink()
            logger.info(f"[{job_id}] Cleaned up temporary trimmed source video.")
        
        logger.info(f"[{job_id}] Worker finished. Triggering queue check.")
        on_finish_callback()