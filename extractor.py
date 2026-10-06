import os
import re
import json
import urllib.parse
import concurrent.futures
from typing import List, Dict, Any

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_PATH = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1"
}


def clean_html_entities(text: str) -> str:
    """Clean HTML entities while preserving unicode characters."""
    if not text:
        return ""
    text = re.sub(r'&#039;|&apos;', "'", text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fetch_page_content(url: str) -> str:
    """Fetch HTML with anti-bot bypass."""
    if cffi_requests:
        try:
            resp = cffi_requests.get(url, impersonate="chrome124", timeout=12)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass

    session = requests.Session()
    resp = session.get(url, headers=HEADERS, timeout=12)
    return resp.text


# =====================================================================
# 1. PEXELS NATIVE EXTRACTOR (Free 4K / HD Stock Videos)
# =====================================================================
def extract_pexels(url: str) -> List[Dict[str, Any]]:
    """Native extractor for Pexels stock videos (supports 4K UHD, 1080p, 720p)."""
    videos = []
    try:
        html = fetch_page_content(url)
        soup = BeautifulSoup(html, "html.parser")
        next_script = soup.find("script", id="__NEXT_DATA__")
        if not next_script or not next_script.string:
            return videos

        data = json.loads(next_script.string)

        def find_videos(obj):
            found = []
            if isinstance(obj, dict):
                if "video_files" in obj and obj.get("video_files"):
                    found.append(obj)
                for v in obj.values():
                    found.extend(find_videos(v))
            elif isinstance(obj, list):
                for item in obj:
                    found.extend(find_videos(item))
            return found

        v_objs = find_videos(data)
        seen = set()

        for obj in v_objs:
            v_files = obj.get("video_files", [])
            if not v_files:
                continue

            first_link = v_files[0].get("link", "")
            id_match = re.search(r'/(\d+)/', first_link)
            v_id = id_match.group(1) if id_match else str(abs(hash(first_link)))
            if v_id in seen:
                continue
            seen.add(v_id)

            poster = obj.get("thumbnail") or obj.get("preview_src") or ""
            formats = []

            for vf in v_files:
                link = vf.get("link")
                if link:
                    q = str(vf.get("quality") or "").upper()
                    w = vf.get("width")
                    h = vf.get("height")
                    label = f"{q} ({w}x{h})" if w and h else (f"{h}p" if h else q or "MP4")
                    formats.append({
                        "quality": label,
                        "url": link,
                        "height": h or 0,
                        "type": "mp4",
                        "use_ytdlp": False,
                        "page_url": ""
                    })

            formats.sort(key=lambda x: x.get("height", 0), reverse=True)
            videos.append({
                "id": f"pexels_{v_id}",
                "title": f"Pexels Free Stock Video #{v_id}",
                "poster": poster,
                "duration": 0,
                "duration_formatted": "",
                "source_type": "Pexels (Free Stock 4K/HD)",
                "formats": formats,
                "default_url": formats[0]["url"] if formats else "",
                "use_ytdlp": False,
                "page_url": ""
            })
    except Exception as e:
        print("Pexels extraction error:", e)
    return videos


# =====================================================================
# 2. MIXKIT NATIVE EXTRACTOR (Free 720p HD / 360p Stock Videos)
# =====================================================================
def extract_mixkit(url: str) -> List[Dict[str, Any]]:
    """Native extractor for Mixkit stock videos."""
    videos = []
    seen = set()
    try:
        html = fetch_page_content(url)
        soup = BeautifulSoup(html, "html.parser")

        for v_tag in soup.find_all("video"):
            src = v_tag.get("src") or ""
            id_match = re.search(r'/videos/(\d+)/', src)
            if id_match:
                v_id = id_match.group(1)
                if v_id in seen:
                    continue
                seen.add(v_id)

                poster = v_tag.get("poster") or ""
                hd_url = f"https://assets.mixkit.co/videos/{v_id}/{v_id}-720.mp4"
                sd_url = f"https://assets.mixkit.co/videos/{v_id}/{v_id}-360.mp4"

                formats = [
                    {"quality": "720p HD", "url": hd_url, "height": 720, "type": "mp4", "use_ytdlp": False, "page_url": ""},
                    {"quality": "360p SD", "url": sd_url, "height": 360, "type": "mp4", "use_ytdlp": False, "page_url": ""}
                ]
                videos.append({
                    "id": f"mixkit_{v_id}",
                    "title": f"Mixkit Free Stock Video #{v_id}",
                    "poster": poster,
                    "duration": 0,
                    "duration_formatted": "",
                    "source_type": "Mixkit (Free Stock HD)",
                    "formats": formats,
                    "default_url": hd_url,
                    "use_ytdlp": False,
                    "page_url": ""
                })
    except Exception as e:
        print("Mixkit extraction error:", e)
    return videos


# =====================================================================
# 3. PIXABAY NATIVE EXTRACTOR (Free 1080p / 720p / 480p Stock Videos)
# =====================================================================
def extract_pixabay(url: str) -> List[Dict[str, Any]]:
    """Native extractor for Pixabay videos with Playwright stealth."""
    videos = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            page.goto(url, wait_until="networkidle", timeout=22000)
            html = page.content()

            raw_matches = re.findall(r'https?://cdn\.pixabay\.com/video/[^\s\"\'<>]+\.(?:mp4|webm)', html)
            posters = re.findall(r'https?://cdn\.pixabay\.com/video/[^\s\"\'<>]+\.jpg', html)
            poster_map = {}
            for p_url in posters:
                id_m = re.search(r'/(\d+)-', p_url)
                if id_m:
                    poster_map[id_m.group(1)] = p_url

            seen_bases = set()
            for m in raw_matches:
                m = m.replace('&amp;', '&')
                # Pattern: https://cdn.pixabay.com/video/2023/06/26/168896-839912975_tiny.mp4
                base_match = re.search(r'(https?://cdn\.pixabay\.com/video/.+?/(\d+)-[^_]+)_(?:large|medium|small|tiny)\.mp4', m)
                if base_match:
                    base_prefix = base_match.group(1)
                    v_id = base_match.group(2)
                    if base_prefix in seen_bases:
                        continue
                    seen_bases.add(base_prefix)

                    # Build high-res formats
                    large_url = f"{base_prefix}_large.mp4"
                    medium_url = f"{base_prefix}_medium.mp4"
                    small_url = f"{base_prefix}_small.mp4"
                    tiny_url = f"{base_prefix}_tiny.mp4"

                    formats = [
                        {"quality": "1080p Full HD", "url": large_url, "height": 1080, "type": "mp4", "use_ytdlp": False, "page_url": ""},
                        {"quality": "720p HD", "url": medium_url, "height": 720, "type": "mp4", "use_ytdlp": False, "page_url": ""},
                        {"quality": "480p SD", "url": small_url, "height": 480, "type": "mp4", "use_ytdlp": False, "page_url": ""},
                        {"quality": "360p Preview", "url": tiny_url, "height": 360, "type": "mp4", "use_ytdlp": False, "page_url": ""},
                    ]

                    videos.append({
                        "id": f"pixabay_{v_id}",
                        "title": f"Pixabay Free Stock Video #{v_id}",
                        "poster": poster_map.get(v_id, ""),
                        "duration": 0,
                        "duration_formatted": "",
                        "source_type": "Pixabay (Free Stock 1080p)",
                        "formats": formats,
                        "default_url": large_url,
                        "use_ytdlp": False,
                        "page_url": ""
                    })

            browser.close()
    except Exception as e:
        print("Pixabay extraction error:", e)
    return videos


def resolve_jwplayer_media(jw_id: str, title: str = "", poster: str = "") -> Dict[str, Any]:
    """Resolve JWPlayer media ID to direct high-speed MP4 download links."""
    api_url = f"https://cdn.jwplayer.com/v2/media/{jw_id}"
    try:
        if cffi_requests:
            resp = cffi_requests.get(api_url, impersonate="chrome124", timeout=6)
        else:
            resp = requests.get(api_url, headers=HEADERS, timeout=6)

        if resp.status_code != 200:
            return None
        data = resp.json()

        media_title = title or data.get("title", f"Video_{jw_id}")
        media_poster = poster or data.get("image", "")
        duration = data.get("duration", 0)

        formats = []
        hls_url = None

        playlist = data.get("playlist", [])
        if playlist:
            item = playlist[0]
            media_title = item.get("title") or media_title
            media_poster = item.get("image") or media_poster
            duration = item.get("duration") or duration

            for src in item.get("sources", []):
                file_url = src.get("file", "")
                src_type = src.get("type", "")
                label = src.get("label", "")

                if "cdn.jwplayer.com/videos/" in file_url:
                    file_url = file_url.replace("cdn.jwplayer.com/videos/", "content.jwplatform.com/videos/")

                if "mpegurl" in src_type or file_url.endswith(".m3u8"):
                    hls_url = file_url
                elif "mp4" in src_type or ".mp4" in file_url:
                    height = src.get("height")
                    if not height and label and "p" in label:
                        try:
                            height = int(label.replace("p", ""))
                        except Exception:
                            height = 0

                    formats.append({
                        "quality": label or (f"{height}p" if height else "MP4"),
                        "url": file_url,
                        "type": "mp4",
                        "height": height or 0,
                        "use_ytdlp": False,
                        "page_url": ""
                    })

        formats.sort(key=lambda x: x.get("height", 0), reverse=True)
        default_url = formats[0]["url"] if formats else hls_url

        return {
            "id": f"jw_{jw_id}",
            "title": clean_html_entities(media_title),
            "poster": media_poster,
            "duration": duration,
            "duration_formatted": f"{int(duration)//60}:{int(duration)%60:02d}" if duration else "",
            "source_type": "Direct Media (JWPlayer)",
            "hls_url": hls_url,
            "formats": formats,
            "default_url": default_url,
            "use_ytdlp": False,
            "page_url": ""
        }
    except Exception:
        return None


def extract_with_ytdlp(url: str) -> List[Dict[str, Any]]:
    """Universal video extraction using yt-dlp across 1,800+ platforms."""
    if not yt_dlp:
        return []

    videos = []
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": 8,
        }
        if FFMPEG_PATH:
            ydl_opts["ffmpeg_location"] = FFMPEG_PATH

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []

            entries = info.get("entries") if "entries" in info else [info]
            for entry in entries:
                if not entry:
                    continue
                e_id = entry.get("id") or str(abs(hash(entry.get("webpage_url", url))))
                webpage_url = entry.get("webpage_url") or url

                formats_map = {}
                for f in entry.get("formats", []):
                    height = f.get("height")
                    if height and height >= 144:
                        res_label = f"{height}p"
                        if res_label not in formats_map or (f.get("filesize") or 0) > (formats_map[res_label].get("filesize") or 0):
                            formats_map[res_label] = {
                                "quality": res_label,
                                "url": f.get("url"),
                                "format_id": f.get("format_id"),
                                "height": height,
                                "ext": f.get("ext", "mp4"),
                                "filesize": f.get("filesize"),
                                "use_ytdlp": True,
                                "page_url": webpage_url
                            }

                formats = list(formats_map.values())
                if not formats:
                    for f in entry.get("formats", []):
                        if f.get("vcodec") != "none" and f.get("url"):
                            label = f.get("format_note") or f"{f.get('height')}p" if f.get('height') else f.get('format_id')
                            formats.append({
                                "quality": label or "Video",
                                "url": f.get("url"),
                                "format_id": f.get("format_id"),
                                "height": f.get("height") or 0,
                                "use_ytdlp": True,
                                "page_url": webpage_url
                            })

                formats.sort(key=lambda x: x.get("height", 0), reverse=True)
                dur = entry.get("duration", 0)

                videos.append({
                    "id": f"ytdl_{e_id}",
                    "title": clean_html_entities(entry.get("title", "Online Video")),
                    "poster": entry.get("thumbnail", ""),
                    "duration": dur,
                    "duration_formatted": f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "",
                    "source_type": entry.get("extractor_key", "Streaming Video"),
                    "hls_url": None,
                    "formats": formats or [{
                        "quality": "Best Quality",
                        "url": entry.get("url"),
                        "use_ytdlp": True,
                        "page_url": webpage_url
                    }],
                    "default_url": formats[0]["url"] if formats else entry.get("url"),
                    "use_ytdlp": True,
                    "page_url": webpage_url
                })
    except Exception:
        pass
    return videos


def extract_videos_from_url(page_url: str) -> List[Dict[str, Any]]:
    """Master Multi-Tier Extraction Engine."""
    page_url = page_url.strip()
    if not page_url.startswith(("http://", "https://")):
        page_url = "https://" + page_url

    clean_path = page_url.split("?")[0].lower()

    # --- 1. Direct Video File Link ---
    if clean_path.endswith((".mp4", ".m3u8", ".webm", ".mov", ".mkv", ".mpd", ".flv", ".ts")):
        filename = page_url.split("?")[0].split("/")[-1] or "Direct_Video.mp4"
        return [{
            "id": f"direct_input_{abs(hash(page_url))}",
            "title": clean_html_entities(filename),
            "poster": "",
            "duration": 0,
            "duration_formatted": "",
            "source_type": "Direct Media File",
            "hls_url": page_url if ".m3u8" in page_url else None,
            "formats": [{"quality": "Original File", "url": page_url, "type": "direct", "use_ytdlp": False, "page_url": ""}],
            "default_url": page_url,
            "use_ytdlp": False,
            "page_url": ""
        }]

    # --- 2. Pexels Dedicated Support ---
    if "pexels.com" in page_url.lower():
        px_vids = extract_pexels(page_url)
        if px_vids:
            return px_vids

    # --- 3. Mixkit Dedicated Support ---
    if "mixkit.co" in page_url.lower():
        mx_vids = extract_mixkit(page_url)
        if mx_vids:
            return mx_vids

    # --- 4. Pixabay Dedicated Support ---
    if "pixabay.com" in page_url.lower():
        pb_vids = extract_pixabay(page_url)
        if pb_vids:
            return pb_vids

    # --- 5. Universal yt-dlp Support ---
    ytdl_results = extract_with_ytdlp(page_url)
    if ytdl_results:
        return ytdl_results

    # --- 6. Deep HTML Scraper ---
    videos = []
    seen_ids = set()
    try:
        html = fetch_page_content(page_url)
        soup = BeautifulSoup(html, "html.parser")
        page_title = clean_html_entities(soup.title.string if soup.title else "Web Video")

        # JWPlayer
        jw_tasks = []
        for el in soup.find_all(attrs={"data-jw": True}):
            jw_id = el.get("data-jw")
            if jw_id and jw_id not in seen_ids:
                seen_ids.add(jw_id)
                t = el.get("data-title") or el.get("data-sub") or el.text.strip()
                p = el.get("data-poster") or ""
                jw_tasks.append((jw_id, t, p))

        for jw_id in re.findall(r'data-jw=[\"\']([a-zA-Z0-9]{8})[\"\']', html):
            if jw_id not in seen_ids:
                seen_ids.add(jw_id)
                jw_tasks.append((jw_id, "", ""))

        if jw_tasks:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                future_to_jw = {
                    executor.submit(resolve_jwplayer_media, item[0], item[1], item[2]): item[0]
                    for item in jw_tasks
                }
                for future in concurrent.futures.as_completed(future_to_jw):
                    res = future.result()
                    if res:
                        videos.append(res)

        # HTML5 tags
        for video_tag in soup.find_all("video"):
            poster = video_tag.get("poster", "")
            if poster:
                poster = urllib.parse.urljoin(page_url, poster)

            src_attrs = ["src", "data-src", "data-url", "data-original", "data-video-src", "data-mp4"]
            sources = []
            for attr in src_attrs:
                val = video_tag.get(attr)
                if val:
                    sources.append(urllib.parse.urljoin(page_url, val))

            for source_tag in video_tag.find_all("source"):
                for attr in src_attrs:
                    val = source_tag.get(attr)
                    if val:
                        sources.append(urllib.parse.urljoin(page_url, val))

            for media_src in sources:
                if media_src and media_src not in seen_ids:
                    seen_ids.add(media_src)
                    filename = media_src.split("?")[0].split("/")[-1] or "video.mp4"
                    t = video_tag.get("title") or video_tag.get("aria-label") or page_title or filename
                    videos.append({
                        "id": f"html5_{abs(hash(media_src))}",
                        "title": clean_html_entities(t),
                        "poster": poster,
                        "duration": 0,
                        "duration_formatted": "",
                        "source_type": "HTML5 Video",
                        "hls_url": media_src if media_src.endswith(".m3u8") else None,
                        "formats": [{"quality": "Direct Stream", "url": media_src, "type": "direct", "use_ytdlp": False, "page_url": ""}],
                        "default_url": media_src,
                        "use_ytdlp": False,
                        "page_url": ""
                    })

        # Iframes
        iframes = soup.find_all("iframe")
        iframe_urls = []
        for f in iframes:
            src = f.get("src") or f.get("data-src")
            if src:
                full_src = urllib.parse.urljoin(page_url, src)
                if any(k in full_src.lower() for k in ["youtube.com", "youtu.be", "vimeo.com", "dailymotion.com", "wistia.net", "streamable.com", "player", "video", "embed"]):
                    iframe_urls.append(full_src)

        if iframe_urls:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_iframe = {executor.submit(extract_with_ytdlp, ifr_url): ifr_url for ifr_url in iframe_urls[:6]}
                for future in concurrent.futures.as_completed(future_to_iframe):
                    res_list = future.result()
                    for v in res_list:
                        if v["id"] not in seen_ids:
                            seen_ids.add(v["id"])
                            videos.append(v)

    except Exception as e:
        print("Scrape error:", e)

    return videos
