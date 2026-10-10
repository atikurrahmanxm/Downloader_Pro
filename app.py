import os
import sys
import webbrowser
import threading
from flask import Flask, render_template, request, jsonify

from extractor import extract_videos_from_url
from downloader import (
    queue_download,
    get_all_tasks,
    cancel_download,
    open_downloads_folder,
    open_file_by_task,
    clear_completed_tasks,
    DOWNLOADS_DIR
)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False


@app.route("/")
def index():
    return render_template("index.html", downloads_dir=DOWNLOADS_DIR)


@app.route("/api/scan", methods=["POST"])
def scan_url():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "URL cannot be empty."}), 400

    try:
        videos = extract_videos_from_url(url)
        return jsonify({
            "success": True,
            "url": url,
            "count": len(videos),
            "videos": videos
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def download_single():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    title = data.get("title", "Video").strip()
    quality = data.get("quality", "Best")
    poster = data.get("poster", "")
    page_url = data.get("page_url", "")
    use_ytdlp = data.get("use_ytdlp", False)

    if not url and not page_url:
        return jsonify({"success": False, "error": "Media URL required."}), 400

    task_id = queue_download(title, url, quality=quality, poster=poster, page_url=page_url, use_ytdlp=use_ytdlp)
    return jsonify({"success": True, "task_id": task_id})


@app.route("/api/download-batch", methods=["POST"])
def download_batch():
    data = request.get_json() or {}
    items = data.get("items", [])
    if not items:
        return jsonify({"success": False, "error": "No items provided for batch download."}), 400

    task_ids = []
    for item in items:
        url = item.get("url", "").strip()
        title = item.get("title", "Video").strip()
        quality = item.get("quality", "Best")
        poster = item.get("poster", "")
        page_url = item.get("page_url", "")
        use_ytdlp = item.get("use_ytdlp", False)
        if url or page_url:
            tid = queue_download(title, url, quality=quality, poster=poster, page_url=page_url, use_ytdlp=use_ytdlp)
            task_ids.append(tid)

    return jsonify({"success": True, "queued": len(task_ids), "task_ids": task_ids})


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    tasks = get_all_tasks()
    return jsonify({"success": True, "tasks": tasks})


@app.route("/api/cancel/<task_id>", methods=["POST"])
def cancel_task(task_id):
    success = cancel_download(task_id)
    return jsonify({"success": success})


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    ok = open_downloads_folder()
    return jsonify({"success": ok, "path": DOWNLOADS_DIR})


@app.route("/api/open-file", methods=["POST"])
def open_file():
    data = request.get_json() or {}
    task_id = data.get("task_id", "").strip()
    if not task_id:
        return jsonify({"success": False, "error": "Task ID required."}), 400
    ok = open_file_by_task(task_id)
    return jsonify({"success": ok})


@app.route("/api/clear-completed", methods=["POST"])
def clear_completed():
    clear_completed_tasks()
    return jsonify({"success": True})


def open_browser(port):
    """Automatically open web browser when server starts."""
    import time
    time.sleep(1.2)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    port = 5000
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    print(f"\n=======================================================")
    print(f"  [*] Web Video Downloader is running!")
    print(f"  [*] URL: http://127.0.0.1:{port}")
    print(f"  [*] Downloads: {DOWNLOADS_DIR}")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
