import cv2
import numpy as np
import textwrap
import json
import subprocess
import time
import requests
import logging
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageColor
from core.config import settings

logger = logging.getLogger(__name__)

TARGET_ASPECT_RATIO = 9 / 16
TARGET_RESOLUTION = (1080, 1920)

# ==============================================================================
# CORE VIDEO/FONT UTILITIES (with user-provided font downloader)
# ==============================================================================

def get_video_info(video_path: str) -> dict:
    video_path_str = str(video_path)
    cache = {}
    
    if settings.VIDEO_INFO_CACHE_FILE.exists():
        with open(settings.VIDEO_INFO_CACHE_FILE, 'r', encoding='utf-8') as f:
            try:
                cache = json.load(f)
            except json.JSONDecodeError: pass
    
    if video_path_str in cache:
        return cache[video_path_str]

    command = [ "ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", video_path_str]
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        logger.warning(f"ffprobe failed. Stderr: {result.stderr}")
        return {}
    
    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError: return {}
        
    video_stream = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not video_stream: return {}

    extracted_info = {
        "duration": float(video_stream.get('duration', 0)),
        "width": int(video_stream.get('width', 0)),
        "height": int(video_stream.get('height', 0)),
        "fps": eval(video_stream.get('avg_frame_rate', '0/1'))
    }
    cache[video_path_str] = extracted_info
    with open(settings.VIDEO_INFO_CACHE_FILE, 'w', encoding='utf-8') as f:
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
    exposure = video_settings.get('exposure', 1.0)
    brightness = video_settings.get('brightness', 1.0)
    contrast = video_settings.get('contrast', 1.0)
    saturation = video_settings.get('saturation', 1.0)
    if all(v == 1.0 for v in [exposure, brightness, contrast, saturation]):
        return frame
    frame_hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(frame_hsv)
    v_float, s_float = v.astype(np.float32), s.astype(np.float32)
    if exposure != 1.0: v_float *= exposure
    if brightness != 1.0: v_float += (brightness - 1.0) * 127.5
    if contrast != 1.0: v_float = (v_float - 127.5) * contrast + 127.5
    if saturation != 1.0: s_float *= saturation
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
    if cached_font_path.exists(): return str(cached_font_path)
    local_font_path = settings.FONTS_DIR / font_name_ttf
    if local_font_path.exists(): return str(local_font_path)
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
        if cached_font_path.exists(): return str(cached_font_path)
        lock_path.touch()
        logger.info(f"Acquired lock for {font_name_ttf}.")
        if not settings.GOOGLE_FONTS_API_KEY:
            logger.warning(f"Font '{font_name}' not found locally and no Google Fonts API key is set. Falling back to default.")
            return "arial.ttf"
        logger.info(f"Font '{font_name}' not found locally. Searching Google Fonts...")
        font_cache = {}
        if settings.FONT_CACHE_FILE.exists():
            with open(settings.FONT_CACHE_FILE, 'r', encoding='utf-8') as f:
                try: 
                    loaded_cache = json.load(f)
                    if isinstance(loaded_cache, dict): font_cache = loaded_cache
                except json.JSONDecodeError: 
                    logger.warning("Font cache file is corrupt. Regenerating.")
        if not font_cache:
            try:
                api_url = f"https://www.googleapis.com/webfonts/v1/webfonts?key={settings.GOOGLE_FONTS_API_KEY}"
                response = requests.get(api_url)
                response.raise_for_status()
                font_data = response.json()
                for item in font_data.get('items', []): font_cache[item['family']] = item['files']
                settings.FONT_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(settings.FONT_CACHE_FILE, 'w', encoding='utf-8') as f: json.dump(font_cache, f)
                logger.info("Successfully cached the Google Fonts directory.")
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
            with open(cached_font_path, 'wb') as f: f.write(font_response.content)
            logger.info(f"Successfully downloaded and saved '{font_name_ttf}' to cache.")
            return str(cached_font_path)
        except requests.RequestException as e:
            logger.error(f"Could not download font file: {e}")
            return "arial.ttf"
    finally:
        if lock_path.exists():
            lock_path.unlink()
            logger.info(f"Released lock for {font_name_ttf}.")

# ==============================================================================
# HIGH-PERFORMANCE OVERLAY FUNCTIONS (WITH ADVANCED POSITIONING)
# ==============================================================================

def prebake_text_overlay(text_item: dict, frame_size: tuple, asset_cache: dict) -> dict:
    """
    Returns a dict with 'array' and 'metadata' including positioning info.
    This allows us to handle pixel vs keyword positioning correctly.
    """
    try:
        text = text_item.get('text', '')
        font_name = text_item.get('font', 'Arial')
        font_size = text_item.get('font_size', 40)
        font_color = text_item.get('font_color', 'white')
        font_align = text_item.get('font_align', 'center')
        positionxy = text_item.get('positionxy', ['center', 'center'])
        margin = text_item.get('margin', [100, 50, 100, 50])  # [T, R, B, L]
        opacity = text_item.get('opacity', 1.0)
        frame_w, frame_h = frame_size

        font_path_key = f"fontpath_{font_name}"
        font_obj_key = f"fontobj_{font_name}_{font_size}"

        if font_path_key not in asset_cache:
            from core.utils import get_font_path
            asset_cache[font_path_key] = get_font_path(font_name)
        font_path = asset_cache[font_path_key]

        if font_obj_key not in asset_cache:
            asset_cache[font_obj_key] = ImageFont.truetype(font_path, font_size)
        font = asset_cache[font_obj_key]

        # Check positioning mode
        is_pixel_pos = isinstance(positionxy, list) and len(positionxy) == 3 and all(isinstance(i, int) for i in positionxy)
        
        # Determine wrapping width based on positioning mode
        if is_pixel_pos:
            # Pixel mode: [y, x, width] - use the specified width
            max_width_px = positionxy[2]
        else:
            # Keyword mode: respect margins to define the text box
            max_width_px = frame_w - margin[1] - margin[3]  # width minus right and left margins

        # Wrap text to fit within max_width_px
        temp_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        lines = []
        words = text.split()
        if not words:
            return None
        
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            if temp_draw.textlength(test_line, font=font) <= max_width_px:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        
        multiline_text = "\n".join(lines)
        line_spacing = font_size * 0.2

        # Get bounding box for the wrapped text
        bbox = temp_draw.multiline_textbbox((0, 0), multiline_text, font=font, spacing=line_spacing, align=font_align)
        
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        if text_width == 0 or text_height == 0:
            return None

        # Create canvas with exact text dimensions
        text_img = Image.new('RGBA', (math.ceil(text_width), math.ceil(text_height)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)
        
        # Parse color and apply opacity
        try:
            if isinstance(font_color, str):
                rgb = ImageColor.getrgb(font_color)
                font_color_with_opacity = rgb + (int(255 * opacity),)
            else:
                font_color_with_opacity = font_color
        except:
            font_color_with_opacity = font_color
        
        # Draw text
        draw.multiline_text(
            (-bbox[0], -bbox[1]),
            multiline_text,
            font=font,
            fill=font_color_with_opacity,
            spacing=line_spacing,
            align=font_align
        )

        # Return both the array and metadata for positioning
        return {
            'array': np.array(text_img),
            'is_pixel_pos': is_pixel_pos,
            'positionxy': positionxy,
            'margin': margin
        }
    except Exception as e:
        logger.warning(f"Could not pre-bake text overlay: {e}", exc_info=True)
        return None


def prebake_image_asset(asset_item: dict, asset_type: str, asset_cache: dict) -> np.ndarray:
    try:
        from core.config import settings
        
        asset_name = asset_item.get('name')
        if not asset_name:
            return None
        target_size = asset_item.get('size', 150)
        target_opacity = float(asset_item.get('opacity', 1.0))
        asset_key = f"{asset_type}_{asset_name}_{target_size}_{target_opacity}"
        
        if asset_key in asset_cache:
            return asset_cache[asset_key]
        
        asset_dir = settings.LOGO_DIR if asset_type == 'logo' else settings.SIGNATURE_DIR
        asset_path = asset_dir / asset_name
        
        if not asset_path.exists():
            logger.warning(f"{asset_type.capitalize()} file not found: {asset_path}")
            asset_cache[asset_key] = None
            return None
            
        with Image.open(asset_path).convert("RGBA") as img:
            img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)
            img_array = np.array(img, dtype=np.float32)
            img_array[..., 3] = img_array[..., 3] * target_opacity
            asset_array = np.clip(img_array, 0, 255).astype(np.uint8)
            asset_cache[asset_key] = asset_array
            return asset_array
    except Exception as e:
        logger.warning(f"Could not pre-bake {asset_type}: {e}", exc_info=True)
        return None


def get_overlay_position(frame_shape: tuple, overlay_shape: tuple, positionxy: list, margin: list, is_pixel_pos: bool = False, font_align: str = 'center') -> tuple:
    """
    Calculate overlay position based on positioning mode.
    
    Args:
        frame_shape: (height, width, channels) of the frame
        overlay_shape: (height, width, channels) of the overlay
        positionxy: Either ["y_align", "x_align"] or [y_pixel, x_pixel, width]
        margin: [top, right, bottom, left] margins
        is_pixel_pos: If True, use pixel positioning mode
        font_align: Text alignment ('left', 'center', 'right') - used in pixel mode
    
    Returns:
        (y, x) position tuple
    """
    frame_h, frame_w = frame_shape[:2]
    overlay_h, overlay_w = overlay_shape[:2]

    if is_pixel_pos:
        # Pixel mode: [y, x, width] 
        # y = vertical center position
        # x = horizontal anchor position
        # width = the box width defined in positionxy
        
        y_center = positionxy[0]
        x_anchor = positionxy[1]
        box_width = positionxy[2]
        
        # Y is always centered vertically around y_center
        y = y_center - (overlay_h // 2)
        
        # X position depends on font_align
        if font_align == 'left':
            # x_anchor is the LEFT edge of the box
            # Text aligns to the left within the box
            x = x_anchor
        elif font_align == 'right':
            # x_anchor is the LEFT edge of the box
            # Text aligns to the RIGHT within the box
            # So text RIGHT edge should be at: x_anchor + box_width
            x = x_anchor + box_width - overlay_w
        else:  # 'center'
            # x_anchor is the LEFT edge of the box
            # Text centers within the box
            x = x_anchor + (box_width - overlay_w) // 2
        
        return int(y), int(x)
    
    # Keyword mode: ["y_align", "x_align"] with margins
    # margin = [top, right, bottom, left]
    top_margin, right_margin, bottom_margin, left_margin = margin
    y_align, x_align = positionxy[0], positionxy[1]

    # Calculate the "content box" (frame minus margins)
    content_x = left_margin
    content_y = top_margin
    content_w = frame_w - left_margin - right_margin
    content_h = frame_h - top_margin - bottom_margin

    # Position within the content box
    if y_align == 'top':
        y = content_y
    elif y_align == 'bottom':
        y = content_y + content_h - overlay_h
    else:  # 'center'
        y = content_y + (content_h - overlay_h) // 2

    if x_align == 'left':
        x = content_x
    elif x_align == 'right':
        x = content_x + content_w - overlay_w
    else:  # 'center'
        x = content_x + (content_w - overlay_w) // 2
    
    return int(y), int(x)


def alpha_blend(frame_bgr: np.ndarray, overlay_rgba: np.ndarray, y: int, x: int):
    """Alpha blend an RGBA overlay onto a BGR frame at position (y, x)"""
    h, w = overlay_rgba.shape[:2]
    frame_h, frame_w = frame_bgr.shape[:2]
    
    # Calculate valid regions
    y_start, x_start = max(0, y), max(0, x)
    y_end, x_end = min(frame_h, y + h), min(frame_w, x + w)
    
    overlay_y_start, overlay_x_start = max(0, -y), max(0, -x)
    overlay_y_end = overlay_y_start + (y_end - y_start)
    overlay_x_end = overlay_x_start + (x_end - x_start)
    
    if (y_end <= y_start) or (x_end <= x_start):
        return

    frame_roi = frame_bgr[y_start:y_end, x_start:x_end]
    overlay_roi = overlay_rgba[overlay_y_start:overlay_y_end, overlay_x_start:overlay_x_end]
    
    alpha = (overlay_roi[..., 3:4] / 255.0).astype(np.float32)
    overlay_bgr_float = overlay_roi[..., :3][..., ::-1].astype(np.float32)  # RGBA to BGR
    frame_roi_float = frame_roi.astype(np.float32)
    
    blended_roi = frame_roi_float * (1.0 - alpha) + overlay_bgr_float * alpha
    frame_bgr[y_start:y_end, x_start:x_end] = np.clip(blended_roi, 0, 255).astype(np.uint8)


def apply_prebaked_overlays(frame: np.ndarray, prebaked_assets: dict, current_time_s: float, video_duration: float):
    """Apply all prebaked overlays to the frame at the current time"""
    for asset_info in prebaked_assets.values():
        start = asset_info.get('start_time') or 0
        end = asset_info.get('end_time') or video_duration
        
        if start <= current_time_s < end:
            overlay_array = asset_info['array']
            if overlay_array is None:
                continue
            
            final_overlay = overlay_array
            fade_in = asset_info.get('fade_in', 0)
            fade_out = asset_info.get('fade_out', 0)
            opacity = 1.0
            
            if fade_in > 0 and current_time_s < start + fade_in:
                opacity = (current_time_s - start) / fade_in
            elif fade_out > 0 and current_time_s > end - fade_out:
                opacity = (end - current_time_s) / fade_out
            
            if opacity < 1.0:
                final_overlay = final_overlay.copy()
                final_overlay[..., 3] = (final_overlay[..., 3].astype(np.float32) * max(0, min(1, opacity))).astype(np.uint8)
            
            y, x = asset_info['position']
            alpha_blend(frame, final_overlay, y, x)