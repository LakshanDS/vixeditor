import subprocess
import json
import cv2
import numpy as np
import requests
import textwrap
import time
import os
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageColor
from core.config import settings

# Get a logger instance for this module
logger = logging.getLogger(__name__)

TARGET_ASPECT_RATIO = 9 / 16
TARGET_RESOLUTION = (1080, 1920)

def get_video_info(video_path: str) -> dict:
    """
    Gets video information using ffprobe, with a persistent JSON cache to avoid
    re-analyzing large files, drastically speeding up job start times.
    """
    video_path_str = str(video_path)
    cache = {}
    
    if settings.VIDEO_INFO_CACHE_FILE.exists():
        with open(settings.VIDEO_INFO_CACHE_FILE, 'r') as f:
            try:
                cache = json.load(f)
            except json.JSONDecodeError:
                pass # Will proceed to analyze if cache is corrupt
    
    if video_path_str in cache:
        logger.debug(f"Video info for {video_path_str} found in cache.")
        return cache[video_path_str]

    logger.info(f"Analyzing new video file: {video_path_str}")
    command = [ "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path_str]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"ffprobe failed for {video_path_str}. Stderr: {result.stderr}")
        return {}
    
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"Could not decode ffprobe JSON for {video_path_str}")
        return {}
        
    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    
    if not video_stream:
        logger.warning(f"No video stream found in {video_path_str}")
        return {}

    extracted_info = {
        "duration": float(video_stream.get('duration', 0)),
        "width": int(video_stream.get('width', 0)),
        "height": int(video_stream.get('height', 0)),
        "fps": eval(video_stream.get('avg_frame_rate', '0/1'))
    }

    cache[video_path_str] = extracted_info
    with open(settings.VIDEO_INFO_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=4)
        
    return extracted_info

def resize_and_crop_frame(frame: np.ndarray) -> np.ndarray:
    h, w, _ = frame.shape
    current_aspect_ratio = w / h
    if abs(current_aspect_ratio - TARGET_ASPECT_RATIO) < 0.01:
        return cv2.resize(frame, TARGET_RESOLUTION, interpolation=cv2.INTER_AREA)

    if current_aspect_ratio > TARGET_ASPECT_RATIO:
        new_w = int(h * TARGET_ASPECT_RATIO)
        crop_start = (w - new_w) // 2
        cropped_frame = frame[:, crop_start : crop_start + new_w]
    else:
        new_h = int(w / TARGET_ASPECT_RATIO)
        crop_start = (h - new_h) // 2
        cropped_frame = frame[crop_start : crop_start + new_h, :]
    return cv2.resize(cropped_frame, TARGET_RESOLUTION, interpolation=cv2.INTER_AREA)

def apply_video_effects(frame: np.ndarray, video_settings: dict) -> np.ndarray:
    """
    Applies video effects based on a [0, 2] scale where 1.0 is the default.
    """
    exposure = video_settings.get('exposure', 1.0)
    brightness = video_settings.get('brightness', 1.0)
    contrast = video_settings.get('contrast', 1.0)
    saturation = video_settings.get('saturation', 1.0)

    if exposure == 1.0 and brightness == 1.0 and contrast == 1.0 and saturation == 1.0:
        return frame

    frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(frame_hsv)
    v_float = v.astype(np.float32)
    s_float = s.astype(np.float32)

    if exposure != 1.0:
        v_float *= exposure
    if brightness != 1.0:
        v_float += (brightness - 1.0) * 127.5
    if contrast != 1.0:
        v_float = (v_float - 127.5) * contrast + 127.5
    if saturation != 1.0:
        s_float *= saturation
    v = np.clip(v_float, 0, 255).astype(np.uint8)
    s = np.clip(s_float, 0, 255).astype(np.uint8)
    final_hsv = cv2.merge((h, s, v))
    return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)

def get_font_path(font_name: str) -> str:
    """
    Finds a font path by checking caches or downloading it from Google Fonts.
    This function is concurrency-safe and uses the logging module.
    """
    font_name_ttf = f"{font_name}.ttf" if not font_name.lower().endswith('.ttf') else font_name

    cached_font_path = settings.FONT_CACHE_DIR / font_name_ttf
    if cached_font_path.exists():
        return str(cached_font_path)

    local_font_path = settings.FONTS_DIR / font_name_ttf
    if local_font_path.exists():
        return str(local_font_path)

    lock_path = settings.FONT_CACHE_DIR / f"{font_name_ttf}.lock"
    settings.FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        timeout_seconds = 30
        start_wait = time.time()
        while lock_path.exists():
            if time.time() - start_wait > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for font lock: {font_name_ttf}")
            logger.debug(f"Waiting for lock on {font_name_ttf}...")
            time.sleep(0.5)

        if cached_font_path.exists():
            return str(cached_font_path)

        lock_path.touch()
        logger.info(f"Acquired lock for {font_name_ttf}.")

        if not settings.GOOGLE_FONTS_API_KEY:
            logger.warning(f"Font '{font_name}' not found locally and no Google Fonts API key is set. Falling back to default.")
            return "arial.ttf" # A default font should be available

        logger.info(f"Font '{font_name}' not found locally. Searching Google Fonts...")
        
        font_cache = {}
        if settings.FONT_CACHE_FILE.exists():
            with open(settings.FONT_CACHE_FILE, 'r') as f:
                try: 
                    loaded_cache = json.load(f)
                    # FIX: Ensure the loaded cache is a dictionary
                    if isinstance(loaded_cache, dict):
                        font_cache = loaded_cache
                    else:
                        logger.warning("Font cache file is corrupted or not in the expected format. Regenerating.")
                        font_cache = {} # Reset to empty dict
                except json.JSONDecodeError: 
                    logger.warning("Font cache file is corrupt JSON. Regenerating.")
                    pass # Will proceed with an empty cache

        if not font_cache:
            try:
                api_url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={settings.GOOGLE_FONTS_API_KEY}"
                response = requests.get(api_url)
                response.raise_for_status()
                font_data = response.json()
                for item in font_data.get('items', []):
                    font_cache[item['family']] = item['files']
                
                settings.FONT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(settings.FONT_CACHE_FILE, 'w') as f:
                    json.dump(font_cache, f)
                logger.info("Successfully downloaded and cached the Google Fonts directory.")
            except requests.RequestException as e:
                logger.error(f"Could not fetch font list from Google Fonts API: {e}")
                return "arial.ttf"

        font_info = font_cache.get(font_name)
        if not font_info:
            logger.warning(f"Font '{font_name}' not found in Google Fonts directory.")
            return "arial.ttf"

        font_url = font_info.get('regular', next(iter(font_info.values()), None))
        if not font_url:
            logger.warning(f"Could not find a downloadable file for font '{font_name}'.")
            return "arial.ttf"
        
        try:
            logger.info(f"Downloading font '{font_name}' from google fonts...")
            font_response = requests.get(font_url)
            font_response.raise_for_status()
            with open(cached_font_path, 'wb') as f:
                f.write(font_response.content)
            
            logger.info(f"Successfully downloaded and saved '{font_name_ttf}' to the font cache.")
            return str(cached_font_path)
        except requests.RequestException as e:
            logger.error(f"Could not download font file: {e}")
            return "arial.ttf"

    finally:
        if lock_path.exists():
            lock_path.unlink()
            logger.info(f"Released lock for {font_name_ttf}.")

def draw_overlays_on_frame(frame: np.ndarray, request: dict, current_time_s: float, asset_cache: dict) -> np.ndarray:
    frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    overlay = Image.new('RGBA', frame_pil.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    frame_w, frame_h = frame_pil.size
    video_duration = request['video']['duration']

    # --- 1. Text Overlays ---
    if 'text_overlays' in request and request['text_overlays']:
        for text_item in request['text_overlays']:

            start = text_item.get('start_time') or 0
            end = text_item.get('end_time') or video_duration
            
            if start <= current_time_s < end:
                try:
                    # Provide defaults for all possible fields
                    text = text_item.get('text', '')
                    font_name = text_item.get('font', 'arial')
                    font_size = text_item.get('font_size', 40)
                    font_align = text_item.get('font_align', 'center')
                    font_color = text_item.get('font_color', 'white')
                    fade_in = text_item.get('fade_in', 0)
                    fade_out = text_item.get('fade_out', 0)
                    positionxy = text_item.get('positionxy', ['center', 'center'])
                    margin = text_item.get('margin', [0, 20, 0, 20])
                    
                    font_path_key = f"fontpath_{font_name}"; font_obj_key = f"fontobj_{font_name}_{font_size}"
                    if font_path_key not in asset_cache: asset_cache[font_path_key] = get_font_path(font_name)
                    font_path = asset_cache[font_path_key]
                    if font_obj_key not in asset_cache: asset_cache[font_obj_key] = ImageFont.truetype(font_path, font_size)
                    font = asset_cache[font_obj_key]

                    opacity = 1.0
                    if fade_in > 0 and current_time_s < start+fade_in: opacity=(current_time_s - start)/fade_in
                    if fade_out > 0 and current_time_s > end-fade_out: opacity=(end - current_time_s)/fade_out
                    opacity=max(0,min(1,opacity))
                    
                    if opacity > 0:
                        max_width = frame_w - margin[1] - margin[3]
                        avg_char_width = font.getlength("abcdefghijklmnopqrstuvwxyz") / 26
                        wrap_width = int(max_width / avg_char_width) if avg_char_width > 0 else 40
                        
                        wrapped_text = textwrap.fill(text, width=wrap_width)
                        lines = wrapped_text.split('\n')

                        line_heights = [draw.textbbox((0,0), line, font=font)[3] for line in lines]
                        line_spacing = font_size * 0.2
                        total_text_height = sum(line_heights) + line_spacing * (len(lines) - 1)

                        pos_x_val, pos_y_val = positionxy[0], positionxy[1]
                        if pos_y_val == 'top': y = margin[0]
                        elif pos_y_val == 'bottom': y = frame_h - total_text_height - margin[2]
                        else: y = (frame_h - total_text_height) / 2
                        
                        current_y = y; rgb = ImageColor.getrgb(font_color); alpha = int(opacity * 255)
                        
                        for i, line in enumerate(lines):
                            line_w = font.getlength(line)
                            if pos_x_val == 'left': x = margin[3]
                            elif pos_x_val == 'right': x = frame_w - line_w - margin[1]
                            else: x = (frame_w - line_w) / 2
                            draw.text((x, current_y), line, font=font, fill=rgb + (alpha,)); current_y += line_heights[i] + line_spacing
                except Exception as e: logger.warning(f"Could not render text overlay. Error: {e}", exc_info=True)

    # 2. Logo Overlay
    if 'logo' in request and request['logo'] and isinstance(request['logo'], dict):
        logo_item = request['logo']
        
        start = text_item.get('start_time') or 0
        end = text_item.get('end_time') or video_duration
        
        if start <= current_time_s < end:
            try:
                # Provide defaults for all fields
                logo_name = logo_item.get('name')
                if not logo_name:
                    logger.warning("Logo item found but 'name' is missing. Skipping.")

                target_size = logo_item.get('size', 150)
                target_opacity = logo_item.get('opacity', 1.0)
                positionxy = logo_item.get('positionxy', ['bottom', 'center'])
                margin = logo_item.get('margin', [0, 25, 25, 0])
                
                logo_key = f"logo_{logo_name}_{target_size}_{target_opacity}"
                if logo_key not in asset_cache:
                    logo_path = settings.LOGO_DIR / logo_name
                    if logo_path.exists():
                        with Image.open(logo_path).convert("RGBA") as img:
                            img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
                            if target_opacity < 1.0:
                                alpha_layer = img.getchannel('A')
                                new_alpha = alpha_layer.point(lambda i: int(i * target_opacity))
                                img.putalpha(new_alpha)
                            asset_cache[logo_key] = img
                    else:
                        logger.warning(f"Logo file not found: {logo_path}"); asset_cache[logo_key] = None

                logo_img = asset_cache.get(logo_key)
                if logo_img:
                    logo_w, logo_h = logo_img.size
                    pos_y, pos_x = positionxy[0], positionxy[1]
                    if pos_y == 'top': y = margin[0]
                    elif pos_y == 'bottom': y = frame_h - logo_h - margin[2]
                    else: y = (frame_h - logo_h) / 2
                    if pos_x == 'left': x = margin[3]
                    elif pos_x == 'right': x = frame_w - logo_w - margin[1]
                    else: x = (frame_w - logo_w) / 2
                    overlay.paste(logo_img, (int(x), int(y)), logo_img)
            except Exception as e: logger.warning(f"Could not render logo. Error: {e}", exc_info=True)

    # 3. Signature Overlay
    if 'signature' in request and request['signature'] and isinstance(request['signature'], dict):
        # Convert the single signature object into a list with one item
        signature_items = [request['signature']]
        
        for sig_item in signature_items:
            # This check is now redundant but good for safety
            if not isinstance(sig_item, dict):
                logger.warning(f"Skipping invalid signature item. Expected a dictionary, but got: {type(sig_item)}")
                continue

            try:
                # Use .get() with default values to prevent errors if a key is missing
                start = text_item.get('start_time') or 0
                end = text_item.get('end_time') or video_duration

                if start <= current_time_s < end:
                    font_name = sig_item.get('font', 'arial')
                    font_size = sig_item.get('font_size', 20)
                    
                    font_path_key = f"fontpath_{font_name}"; font_obj_key = f"fontobj_{font_name}_{font_size}"
                    if font_path_key not in asset_cache: asset_cache[font_path_key] = get_font_path(font_name)
                    font_path = asset_cache[font_path_key]
                    if font_obj_key not in asset_cache: asset_cache[font_obj_key] = ImageFont.truetype(font_path, font_size)
                    font = asset_cache[font_obj_key]

                    opacity = sig_item.get('opacity', 0.7)
                    if opacity > 0:
                        text = sig_item.get('text', '')
                        margin = sig_item.get('margin', [0, 15, 15, 0])
                        positionxy = sig_item.get('positionxy', ['bottom', 'right'])
                        
                        _, _, line_w, line_h = draw.textbbox((0, 0), text, font=font)
                        pos_x_val, pos_y_val = positionxy[1], positionxy[0]

                        if pos_y_val == 'top': y = margin[0]
                        elif pos_y_val == 'bottom': y = frame_h - line_h - margin[2]
                        else: y = (frame_h - line_h) / 2
                        
                        if pos_x_val == 'left': x = margin[3]
                        elif pos_x_val == 'right': x = frame_w - line_w - margin[1]
                        else: x = (frame_w - line_w) / 2
                        
                        rgb = ImageColor.getrgb(sig_item.get('font_color', 'white'))
                        alpha = int(opacity * 255)
                        draw.text((x, y), text, font=font, fill=rgb + (alpha,))
                            
            except Exception as e: 
                logger.warning(f"Could not render signature. Error: {e}", exc_info=True)

    frame_pil = Image.alpha_composite(frame_pil.convert("RGBA"), overlay)
    return cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)