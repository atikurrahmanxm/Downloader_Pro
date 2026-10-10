import os
import re
import json
import urllib.parse
import urllib.request
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


def resolve_redirects(url: str) -> str:
    """Resolve shortened or redirected URLs (fb.watch, vt.tiktok.com, youtu.be, etc.)."""
    try:
        if cffi_requests:
            r = cffi_requests.head(url, impersonate="chrome124", allow_redirects=True, timeout=6)
            return r.url
    except Exception:
        pass
    try:
        r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=6)
        return r.url
    except Exception:
        return url


def fetch_page_content(url: str) -> str:
    """Fetch HTML with Chrome TLS fingerprint impersonation to bypass bot protection."""
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
# 1. PEXELS EXTRACTOR (Free 4K / HD Stock Videos)
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
# 2. MIXKIT EXTRACTOR (Free 720p HD / 360p Stock Videos)
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
# 3. PIXABAY EXTRACTOR (Free 1080p / 720p / 480p Stock Videos)
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

            page.goto(url, wait_until="networkidle", timeout=20000)
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
                base_match = re.search(r'(https?://cdn\.pixabay\.com/video/.+?/(\d+)-[^_]+)_(?:large|medium|small|tiny)\.mp4', m)
                if base_match:
                    base_prefix = base_match.group(1)
                    v_id = base_match.group(2)
                    if base_prefix in seen_bases:
                        continue
                    seen_bases.add(base_prefix)

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


# =====================================================================
# 4. FACEBOOK DIRECT HTML EXTRACTOR (Backup for Reels & Watch)
# =====================================================================
def extract_facebook_html(html: str, page_url: str) -> List[Dict[str, Any]]:
    """Extract direct HD/SD MP4 URLs from Facebook HTML."""
    videos = []
    hd_matches = re.findall(r'[\"\'](?:browser_native_hd_url|hd_src)[\"\']\s*:\s*[\"\']([^\"\']+)[\"\']', html)
    sd_matches = re.findall(r'[\"\'](?:browser_native_sd_url|sd_src)[\"\']\s*:\s*[\"\']([^\"\']+)[\"\']', html)

    formats = []
    if hd_matches:
        hd_clean = hd_matches[0].replace('\\/', '/').replace('&amp;', '&')
        formats.append({"quality": "HD (720p)", "url": hd_clean, "height": 720, "type": "mp4", "use_ytdlp": False, "page_url": ""})
    if sd_matches:
        sd_clean = sd_matches[0].replace('\\/', '/').replace('&amp;', '&')
        formats.append({"quality": "SD (360p)", "url": sd_clean, "height": 360, "type": "mp4", "use_ytdlp": False, "page_url": ""})

    if formats:
        title_match = re.search(r'<title>(.*?)</title>', html)
        title = title_match.group(1).replace(" | Facebook", "").strip() if title_match else "Facebook Video"
        og_img = re.search(r'<meta property=[\"\']og:image[\"\'] content=[\"\']([^\"\']+)[\"\']', html)
        poster = og_img.group(1).replace('&amp;', '&') if og_img else ""

        videos.append({
            "id": f"fb_{abs(hash(page_url))}",
            "title": clean_html_entities(title),
            "poster": poster,
            "duration": 0,
            "duration_formatted": "",
            "source_type": "Facebook (Direct MP4)",
            "formats": formats,
            "default_url": formats[0]["url"],
            "use_ytdlp": False,
            "page_url": ""
        })
    return videos


# =====================================================================
# 5. PINTEREST DIRECT EXTRACTOR
# =====================================================================
def extract_pinterest_html(html: str, page_url: str) -> List[Dict[str, Any]]:
    """Extract direct MP4 URLs from Pinterest."""
    videos = []
    pin_vids = re.findall(r'https?://v\.pinimg\.com/videos/[^\s\"\'<>]+\.mp4', html)
    if pin_vids:
        unique_urls = list(dict.fromkeys(pin_vids))
        formats = []
        for u in unique_urls:
            h = 720 if "720p" in u else (1080 if "1080p" in u else 480)
            label = "720p HD" if "720p" in u else ("1080p Full HD" if "1080p" in u else "SD Video")
            formats.append({"quality": label, "url": u, "height": h, "type": "mp4", "use_ytdlp": False, "page_url": ""})
        formats.sort(key=lambda x: x["height"], reverse=True)

        videos.append({
            "id": f"pin_{abs(hash(page_url))}",
            "title": "Pinterest Video",
            "poster": "",
            "duration": 0,
            "duration_formatted": "",
            "source_type": "Pinterest (Direct Video)",
            "formats": formats,
            "default_url": formats[0]["url"],
            "use_ytdlp": False,
            "page_url": ""
        })
    return videos


# =====================================================================
# 6. JWPLAYER CDN RESOLVER (Moviefone & Media Portals)
# =====================================================================
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


# =====================================================================
# 7. UNIVERSAL YT-DLP EXTRACTOR (YouTube, TikTok, Twitter, Reddit, etc.)
# =====================================================================
def extract_with_ytdlp(url: str) -> List[Dict[str, Any]]:
    """Universal video extraction using yt-dlp across 1,800+ platforms."""
    if not yt_dlp:
        return []

    # Twitter normalization
    if "x.com/" in url:
        url = url.replace("x.com/", "twitter.com/")

    videos = []
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": 12,
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
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


# =====================================================================
# 8. PLAYWRIGHT NETWORK SNIFFER FALLBACK (Dynamic JavaScript Players)
# =====================================================================
def extract_with_playwright_sniffer(url: str, timeout_sec: int = 8) -> List[Dict[str, Any]]:
    """Headless browser fallback for dynamic JS single-page apps and custom players."""
    videos = []
    seen = set()

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            captured_streams = []

            def on_response(response):
                try:
                    r_url = response.url
                    content_type = response.headers.get("content-type", "").lower()
                    if any(r_url.lower().endswith(ext) for ext in [".m3u8", ".mp4", ".mpd", ".webm"]):
                        if r_url not in seen and not any(skip in r_url.lower() for skip in ["ad_", "pixel", "analytics", "tracking"]):
                            seen.add(r_url)
                            captured_streams.append((r_url, content_type))
                    elif "video/" in content_type or "mpegurl" in content_type:
                        if r_url not in seen and not any(skip in r_url.lower() for skip in ["ad_", "pixel", "analytics", "tracking"]):
                            seen.add(r_url)
                            captured_streams.append((r_url, content_type))
                except Exception:
                    pass

            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                page.wait_for_timeout(2500)
            except Exception:
                pass

            page_title = page.title() or "Web Video"

            dom_videos = page.query_selector_all("video")
            for v_tag in dom_videos:
                try:
                    v_src = v_tag.get_attribute("src") or v_tag.get_attribute("data-src")
                    poster = v_tag.get_attribute("poster") or ""
                    if v_src and v_src not in seen:
                        seen.add(v_src)
                        abs_src = urllib.parse.urljoin(url, v_src)
                        videos.append({
                            "id": f"pw_dom_{abs(hash(abs_src))}",
                            "title": page_title,
                            "poster": urllib.parse.urljoin(url, poster) if poster else "",
                            "duration": 0,
                            "duration_formatted": "",
                            "source_type": "HTML5 Video (Rendered)",
                            "hls_url": abs_src if ".m3u8" in abs_src else None,
                            "formats": [{"quality": "Direct Stream", "url": abs_src, "type": "direct", "use_ytdlp": ".m3u8" in abs_src, "page_url": url}],
                            "default_url": abs_src,
                            "use_ytdlp": ".m3u8" in abs_src,
                            "page_url": url
                        })
                except Exception:
                    pass

            for s_url, s_type in captured_streams:
                filename = s_url.split("?")[0].split("/")[-1] or "Stream"
                is_m3u8_or_dash = ".m3u8" in s_url or ".mpd" in s_url
                videos.append({
                    "id": f"pw_net_{abs(hash(s_url))}",
                    "title": f"{page_title} - {filename}",
                    "poster": "",
                    "duration": 0,
                    "duration_formatted": "",
                    "source_type": "Captured Stream (Sniffed)",
                    "hls_url": s_url if is_m3u8_or_dash else None,
                    "formats": [{"quality": "Captured Stream", "url": s_url, "type": "stream", "use_ytdlp": is_m3u8_or_dash, "page_url": url}],
                    "default_url": s_url,
                    "use_ytdlp": is_m3u8_or_dash,
                    "page_url": url
                })

            browser.close()
    except Exception as e:
        print("Playwright fallback error:", e)

    return videos


# =====================================================================
# MASTER MULTI-TIER EXTRACTION ENGINE
# =====================================================================
def extract_videos_from_url(page_url: str) -> List[Dict[str, Any]]:
    """Master Multi-Tier Extraction Engine."""
    page_url = page_url.strip()
    if not page_url.startswith(("http://", "https://")):
        page_url = "https://" + page_url

    # Expand shortened links (fb.watch, vt.tiktok.com, youtu.be, bit.ly, etc.)
    if any(short in page_url.lower() for short in ["youtu.be", "fb.watch", "vt.tiktok.com", "bit.ly", "t.co", "tinyurl"]):
        page_url = resolve_redirects(page_url)

    clean_path = page_url.split("?")[0].lower()

    # --- 1. Direct Video File Link Input ---
    if clean_path.endswith((".mp4", ".m3u8", ".webm", ".mov", ".mkv", ".mpd", ".flv", ".ts")):
        filename = page_url.split("?")[0].split("/")[-1] or "Direct_Video.mp4"
        is_stream = any(ext in clean_path for ext in [".m3u8", ".mpd"])
        return [{
            "id": f"direct_input_{abs(hash(page_url))}",
            "title": clean_html_entities(filename),
            "poster": "",
            "duration": 0,
            "duration_formatted": "",
            "source_type": "Direct Media File",
            "hls_url": page_url if is_stream else None,
            "formats": [{"quality": "Original File", "url": page_url, "type": "direct", "use_ytdlp": is_stream, "page_url": page_url}],
            "default_url": page_url,
            "use_ytdlp": is_stream,
            "page_url": page_url
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

    # --- 5. Universal yt-dlp Engine ---
    ytdl_results = extract_with_ytdlp(page_url)
    if ytdl_results:
        return ytdl_results

    # --- 6. Deep HTML & Embed Parser ---
    videos = []
    seen_ids = set()
    try:
        html = fetch_page_content(page_url)
        soup = BeautifulSoup(html, "html.parser")
        page_title = clean_html_entities(soup.title.string if soup.title else "Web Video")

        # A. Facebook HTML fallback
        if "facebook.com" in page_url.lower():
            fb_vids = extract_facebook_html(html, page_url)
            if fb_vids:
                return fb_vids

        # B. Pinterest HTML fallback
        if "pinterest.com" in page_url.lower():
            pin_vids = extract_pinterest_html(html, page_url)
            if pin_vids:
                return pin_vids

        # C. JWPlayer Resolution
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

        # D. HTML5 <video> & <source> tags
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
                    is_hls = ".m3u8" in media_src or ".mpd" in media_src
                    videos.append({
                        "id": f"html5_{abs(hash(media_src))}",
                        "title": clean_html_entities(t),
                        "poster": poster,
                        "duration": 0,
                        "duration_formatted": "",
                        "source_type": "HTML5 Video",
                        "hls_url": media_src if is_hls else None,
                        "formats": [{"quality": "Direct Stream", "url": media_src, "type": "direct", "use_ytdlp": is_hls, "page_url": page_url}],
                        "default_url": media_src,
                        "use_ytdlp": is_hls,
                        "page_url": page_url
                    })

        # E. Embedded iframes (YouTube, Vimeo, Dailymotion, Wistia, Streamable, etc.)
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

        # F. JSON-LD Schema (VideoObject)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "VideoObject":
                        c_url = item.get("contentUrl") or item.get("embedUrl")
                        if c_url and c_url not in seen_ids:
                            seen_ids.add(c_url)
                            is_hls = ".m3u8" in c_url or ".mpd" in c_url
                            videos.append({
                                "id": f"jsonld_{abs(hash(c_url))}",
                                "title": clean_html_entities(item.get("name", page_title)),
                                "poster": item.get("thumbnailUrl") or "",
                                "duration": 0,
                                "duration_formatted": "",
                                "source_type": "Schema VideoObject",
                                "hls_url": c_url if is_hls else None,
                                "formats": [{"quality": "Original", "url": c_url, "type": "direct", "use_ytdlp": is_hls, "page_url": page_url}],
                                "default_url": c_url,
                                "use_ytdlp": is_hls,
                                "page_url": page_url
                            })
            except Exception:
                pass

        # G. OpenGraph & Twitter video meta tags
        meta_tags = [
            soup.find("meta", property="og:video"),
            soup.find("meta", property="og:video:url"),
            soup.find("meta", property="og:video:secure_url"),
            soup.find("meta", attrs={"name": "twitter:player:stream"}),
        ]
        og_poster = soup.find("meta", property="og:image")
        poster_url = og_poster.get("content", "") if og_poster else ""

        for m in meta_tags:
            if m and m.get("content"):
                m_url = urllib.parse.urljoin(page_url, m["content"])
                if m_url not in seen_ids and not any(skip in m_url.lower() for skip in ["ad_", "pixel"]):
                    seen_ids.add(m_url)
                    is_hls = ".m3u8" in m_url or ".mpd" in m_url
                    videos.append({
                        "id": f"meta_{abs(hash(m_url))}",
                        "title": page_title,
                        "poster": poster_url,
                        "duration": 0,
                        "duration_formatted": "",
                        "source_type": "Social Media Meta",
                        "hls_url": m_url if is_hls else None,
                        "formats": [{"quality": "Meta Stream", "url": m_url, "type": "direct", "use_ytdlp": is_hls, "page_url": page_url}],
                        "default_url": m_url,
                        "use_ytdlp": is_hls,
                        "page_url": page_url
                    })

        # H. Deep Regex for media URLs inside scripts
        direct_media = re.findall(r'https?://[^\s\"\'<>]+\.(?:mp4|m3u8)(?:\?[^\s\"\'<>]*)?', html)
        for media_url in direct_media:
            if media_url not in seen_ids and not any(skip in media_url.lower() for skip in ["track", "analytics", "ad_", "pixel", "beacon"]):
                seen_ids.add(media_url)
                name = media_url.split("?")[0].split("/")[-1]
                is_hls = ".m3u8" in media_url
                videos.append({
                    "id": f"script_direct_{abs(hash(media_url))}",
                    "title": clean_html_entities(name),
                    "poster": poster_url,
                    "duration": 0,
                    "duration_formatted": "",
                    "source_type": "Direct Link Detected",
                    "hls_url": media_url if is_hls else None,
                    "formats": [{"quality": "Direct Link", "url": media_url, "type": "direct", "use_ytdlp": is_hls, "page_url": page_url}],
                    "default_url": media_url,
                    "use_ytdlp": is_hls,
                    "page_url": page_url
                })

    except Exception as e:
        print("Scrape error:", e)

    # --- 7. Playwright Headless Browser Sniffer Fallback ---
    # If no videos found through static methods or yt-dlp, launch Playwright
    if not videos:
        print(f"Static extractors returned 0 videos for {page_url}. Launching Playwright sniffer...")
        pw_results = extract_with_playwright_sniffer(page_url)
        for v in pw_results:
            if v["id"] not in seen_ids:
                seen_ids.add(v["id"])
                videos.append(v)

    return videos
