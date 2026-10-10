import os
import re
import time
import uuid
import threading
from typing import Dict, Any, List
import requests

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

download_tasks: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()


def sanitize_filename(name: str) -> str:
    """Sanitize name to make it a valid Windows filename while preserving Unicode/Bengali."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name)
    clean = clean.replace('&amp;', '&').replace('&#039;', "'").replace('&quot;', '"').replace('&apos;', "'")
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:120] if clean else "video"


def format_bytes(bytes_num: float) -> str:
    """Format bytes into readable string (KB, MB, GB)."""
    if not bytes_num or bytes_num <= 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"


def format_speed(bytes_per_sec: float) -> str:
    """Format download speed."""
    if not bytes_per_sec or bytes_per_sec <= 0:
        return "0 KB/s"
    return f"{format_bytes(bytes_per_sec)}/s"


def is_direct_media(url: str) -> bool:
    """Check if URL points to a direct downloadable media file."""
    if not url:
        return False
    u = url.lower().split("?")[0]
    is_ext = any(u.endswith(ext) for ext in [".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi", ".ts"])
    is_cdn = any(cdn in u for cdn in [
        "fbcdn.net", "v.pinimg.com", "assets.mixkit.co", "images.pexels.com",
        "cdn.pixabay.com", "content.jwplatform.com"
    ])
    return is_ext or is_cdn


def is_manifest_stream(url: str) -> bool:
    """Check if URL is an HLS (m3u8) or DASH (mpd) stream."""
    if not url:
        return False
    u = url.lower().split("?")[0]
    return ".m3u8" in u or ".mpd" in u or "manifest" in u


def _download_ytdlp(task_id: str, target_url: str, filename: str, quality: str):
    """Download video using yt-dlp with live progress hooks and audio/video merging."""
    target_path = os.path.join(DOWNLOADS_DIR, f"{filename}.mp4")
    counter = 1
    base_name = filename
    while os.path.exists(target_path):
        target_path = os.path.join(DOWNLOADS_DIR, f"{base_name}_{counter}.mp4")
        counter += 1

    with tasks_lock:
        download_tasks[task_id]["file_path"] = target_path
        download_tasks[task_id]["filename"] = os.path.basename(target_path)
        download_tasks[task_id]["status"] = "downloading"
        download_tasks[task_id]["start_time"] = time.time()

    def ytdl_hook(d):
        if download_tasks.get(task_id, {}).get("cancelled"):
            raise Exception("Download cancelled by user")

        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            pct = int((downloaded / total * 100)) if total > 0 else 50
            speed = d.get('speed', 0) or 0

            with tasks_lock:
                download_tasks[task_id]["downloaded_bytes"] = downloaded
                download_tasks[task_id]["total_bytes"] = total
                download_tasks[task_id]["downloaded_bytes_formatted"] = format_bytes(downloaded)
                download_tasks[task_id]["total_bytes_formatted"] = format_bytes(total) if total else "Calculating..."
                download_tasks[task_id]["progress"] = min(pct, 98)
                download_tasks[task_id]["speed"] = format_speed(speed)
        elif status == 'finished':
            with tasks_lock:
                download_tasks[task_id]["progress"] = 99
                download_tasks[task_id]["speed"] = "Merging audio & video..."

    def ytdl_post_hook(d):
        status = d.get('status')
        if status == 'started':
            with tasks_lock:
                download_tasks[task_id]["speed"] = "Processing video format..."
                download_tasks[task_id]["progress"] = 99

    # Determine format selection
    height_match = re.search(r'(\d+)p', str(quality))
    target_height = height_match.group(1) if height_match else ""

    if "audio" in str(quality).lower() or "mp3" in str(quality).lower():
        fmt_str = "bestaudio/best"
    elif target_height:
        fmt_str = f"bestvideo[height<={target_height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={target_height}]+bestaudio/best[height<={target_height}]/best"
    else:
        fmt_str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

    ydl_opts = {
        'format': fmt_str,
        'outtmpl': target_path.replace(".mp4", "") + ".%(ext)s",
        'progress_hooks': [ytdl_hook],
        'postprocessor_hooks': [ytdl_post_hook],
        'quiet': True,
        'no_warnings': True,
        'merge_output_format': 'mp4',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    }
    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([target_url])

        # Locate final merged file
        final_file = target_path
        if not os.path.exists(final_file):
            candidate = target_path.replace(".mp4", "") + ".mkv"
            if os.path.exists(candidate):
                final_file = candidate
            else:
                candidate_webm = target_path.replace(".mp4", "") + ".webm"
                if os.path.exists(candidate_webm):
                    final_file = candidate_webm

        final_size = os.path.getsize(final_file) if os.path.exists(final_file) else 0

        with tasks_lock:
            download_tasks[task_id]["progress"] = 100
            download_tasks[task_id]["status"] = "completed"
            download_tasks[task_id]["file_path"] = final_file
            download_tasks[task_id]["downloaded_bytes_formatted"] = format_bytes(final_size)
            download_tasks[task_id]["total_bytes_formatted"] = format_bytes(final_size)
            download_tasks[task_id]["speed"] = "Completed"
            download_tasks[task_id]["filename"] = os.path.basename(final_file)

    except Exception as e:
        err_msg = str(e)
        if "ERROR:" in err_msg:
            err_msg = err_msg.split("ERROR:")[-1].strip()
        with tasks_lock:
            download_tasks[task_id]["status"] = "error"
            download_tasks[task_id]["error"] = err_msg
            download_tasks[task_id]["speed"] = "Failed"


def _download_direct_stream(task_id: str, media_url: str, filename: str, referer: str = ""):
    """Download direct video file via HTTP chunked streaming with live progress tracking."""
    target_path = os.path.join(DOWNLOADS_DIR, f"{filename}.mp4")

    if "cdn.jwplayer.com/videos/" in media_url:
        media_url = media_url.replace("cdn.jwplayer.com/videos/", "content.jwplatform.com/videos/")

    counter = 1
    base_name = filename
    while os.path.exists(target_path):
        target_path = os.path.join(DOWNLOADS_DIR, f"{base_name}_{counter}.mp4")
        counter += 1

    with tasks_lock:
        download_tasks[task_id]["file_path"] = target_path
        download_tasks[task_id]["filename"] = os.path.basename(target_path)
        download_tasks[task_id]["status"] = "downloading"
        download_tasks[task_id]["start_time"] = time.time()

    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }
        if referer:
            headers["Referer"] = referer

        with session.get(media_url, headers=headers, stream=True, timeout=25) as response:
            response.raise_for_status()
            total_size_header = response.headers.get('content-length')
            total_bytes = int(total_size_header) if total_size_header else 0

            with tasks_lock:
                download_tasks[task_id]["total_bytes"] = total_bytes
                download_tasks[task_id]["total_bytes_formatted"] = format_bytes(total_bytes) if total_bytes else "Unknown"

            chunk_size = 256 * 1024  # 256 KB chunks
            downloaded = 0
            start_time = time.time()
            last_speed_check = start_time
            bytes_since_last_check = 0

            with open(target_path, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if download_tasks.get(task_id, {}).get("cancelled"):
                        raise Exception("Download cancelled by user")

                    if chunk:
                        out_file.write(chunk)
                        downloaded += len(chunk)
                        bytes_since_last_check += len(chunk)
                        now = time.time()

                        if now - last_speed_check >= 0.3:
                            elapsed = now - last_speed_check
                            speed = bytes_since_last_check / elapsed if elapsed > 0 else 0
                            pct = int((downloaded / total_bytes * 100)) if total_bytes > 0 else 50

                            with tasks_lock:
                                download_tasks[task_id]["downloaded_bytes"] = downloaded
                                download_tasks[task_id]["downloaded_bytes_formatted"] = format_bytes(downloaded)
                                download_tasks[task_id]["progress"] = min(pct, 99)
                                download_tasks[task_id]["speed"] = format_speed(speed)

                            last_speed_check = now
                            bytes_since_last_check = 0

        final_size = os.path.getsize(target_path) if os.path.exists(target_path) else downloaded
        with tasks_lock:
            download_tasks[task_id]["progress"] = 100
            download_tasks[task_id]["status"] = "completed"
            download_tasks[task_id]["file_path"] = target_path
            download_tasks[task_id]["downloaded_bytes_formatted"] = format_bytes(final_size)
            download_tasks[task_id]["total_bytes_formatted"] = format_bytes(final_size)
            download_tasks[task_id]["speed"] = "Completed"

    except Exception as e:
        with tasks_lock:
            download_tasks[task_id]["status"] = "error"
            download_tasks[task_id]["error"] = str(e)
            download_tasks[task_id]["speed"] = "Failed"
        if os.path.exists(target_path) and os.path.getsize(target_path) == 0:
            try:
                os.remove(target_path)
            except Exception:
                pass


def queue_download(title: str, media_url: str, quality: str = "High", poster: str = "", page_url: str = "", use_ytdlp: bool = False) -> str:
    """Smart router to download video via direct stream or yt-dlp."""
    task_id = str(uuid.uuid4())[:8]
    clean_title = sanitize_filename(title)

    is_manifest = is_manifest_stream(media_url)
    is_direct = is_direct_media(media_url)

    # If media is a direct file (.mp4, CDN link) and not a playlist -> direct high-speed HTTP stream
    if is_direct and not is_manifest:
        target_func = _download_direct_stream
        target_args = (task_id, media_url, clean_title, page_url)
    elif is_manifest:
        # HLS or DASH stream -> pass stream URL directly to yt-dlp for lossless chunk merging
        target_func = _download_ytdlp
        target_args = (task_id, media_url, clean_title, quality)
    elif use_ytdlp or any(k in (page_url or media_url).lower() for k in [
        "youtube.com", "youtu.be", "googlevideo.com", "tiktok.com", "x.com", "twitter.com",
        "vimeo.com", "reddit.com", "instagram.com", "twitch.tv", "dailymotion.com"
    ]):
        target_func = _download_ytdlp
        target_args = (task_id, page_url or media_url, clean_title, quality)
    else:
        # Fallback to direct stream
        target_func = _download_direct_stream
        target_args = (task_id, media_url, clean_title, page_url)

    with tasks_lock:
        download_tasks[task_id] = {
            "id": task_id,
            "title": title,
            "filename": f"{clean_title}.mp4",
            "file_path": os.path.join(DOWNLOADS_DIR, f"{clean_title}.mp4"),
            "media_url": media_url,
            "page_url": page_url or media_url,
            "quality": quality,
            "poster": poster,
            "status": "queued",
            "progress": 0,
            "speed": "Starting...",
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "downloaded_bytes_formatted": "0 B",
            "total_bytes_formatted": "Calculating...",
            "created_at": time.time(),
            "cancelled": False,
            "error": None
        }

    thread = threading.Thread(
        target=target_func,
        args=target_args,
        daemon=True
    )
    thread.start()
    return task_id


def get_all_tasks() -> List[Dict[str, Any]]:
    """Get all tasks ordered by creation time descending."""
    with tasks_lock:
        return sorted(list(download_tasks.values()), key=lambda x: x.get("created_at", 0), reverse=True)


def cancel_download(task_id: str) -> bool:
    """Cancel a running download task."""
    with tasks_lock:
        if task_id in download_tasks:
            download_tasks[task_id]["cancelled"] = True
            download_tasks[task_id]["status"] = "cancelled"
            return True
    return False


def clear_completed_tasks():
    """Remove finished, cancelled, and errored tasks from the queue."""
    with tasks_lock:
        to_del = [tid for tid, t in download_tasks.items() if t.get("status") in ("completed", "cancelled", "error")]
        for tid in to_del:
            del download_tasks[tid]


def open_file_by_task(task_id: str) -> bool:
    """Open downloaded video file in default Windows video player."""
    with tasks_lock:
        task = download_tasks.get(task_id)
        if not task:
            return False
        file_path = task.get("file_path", "")

    if file_path and os.path.exists(file_path):
        try:
            os.startfile(file_path)
            return True
        except Exception as e:
            print(f"Error opening file {file_path}:", e)
            return False
    return False


def open_downloads_folder() -> bool:
    """Open the downloads folder in Windows Explorer."""
    try:
        os.startfile(DOWNLOADS_DIR)
        return True
    except Exception as e:
        print("Failed to open folder:", e)
        return False
