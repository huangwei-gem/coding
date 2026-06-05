#!/usr/bin/env python3
"""Agnes AI Canvas - Web UI for Image & Video Generation
Uses curl subprocess for reliable API access (Python SSL has issues on this env).
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import flask

app = flask.Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

# Runtime config (can be overridden via API or header)
RUNTIME = {
    "api_key": os.environ.get("AGNES_API_KEY", ""),
}
BASE_URL = "https://apihub.agnes-ai.com/v1"
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _get_api_key():
    """Return the effective API key (header override > runtime config > env var)."""
    # Check if request has an override header
    if flask.has_request_context():
        header_key = flask.request.headers.get("X-Agnes-Api-Key", "")
        if header_key:
            return header_key
    return RUNTIME.get("api_key") or os.environ.get("AGNES_API_KEY", "")


def curl_post(url, json_body, timeout=180):
    """Call Agnes API via curl subprocess. Retries once on timeout/error."""
    body_str = json.dumps(json_body)
    errors = []
    for attempt in range(2):
        cmd = [
            "curl", "-s", "--max-time", str(timeout),
            "--retry", "1",
            "-H", f"Authorization: Bearer {API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", body_str,
            url
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
            if result.returncode != 0:
                msg = f"curl error (code {result.returncode})"
                if result.stderr.strip():
                    msg += f": {result.stderr.strip()}"
                # On timeout (28), retry
                if result.returncode == 28 and attempt == 0:
                    errors.append(msg)
                    print(f"[api] Attempt {attempt+1} timed out, retrying...", flush=True)
                    continue
                return {"error": msg}, 502
            data = json.loads(result.stdout)
            if "error" in data:
                return data, 400
            return data, 200
        except subprocess.TimeoutExpired:
            msg = "Request timed out"
            if attempt == 0:
                errors.append(msg)
                print(f"[api] Attempt {attempt+1} timed out, retrying...", flush=True)
                continue
            return {"error": msg}, 504
        except json.JSONDecodeError as e:
            return {"error": f"Invalid response: {e}"}, 502
        except Exception as e:
            return {"error": str(e)}, 500
    return {"error": "; ".join(errors)}, 502


def curl_get(url, timeout=30):
    """Call Agnes API GET via curl subprocess."""
    cmd = [
        "curl", "-s", "--max-time", str(timeout),
        "-H", f"Authorization: Bearer {API_KEY}",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode != 0:
            return {"error": f"curl error (code {result.returncode}): {result.stderr}"}, 502
        data = json.loads(result.stdout)
        if "error" in data:
            return data, 400
        return data, 200
    except Exception as e:
        return {"error": str(e)}, 500


def upload_to_hosting(file_path):
    """Upload a file to litterbox.catbox.moe via curl, return public URL or None.
    Retries once on failure."""
    for attempt in range(2):
        cmd = [
            "curl", "-s", "--max-time", "30",
            "--retry", "1",
            "-F", "reqtype=fileupload",
            "-F", "time=1h",
            "-F", f"fileToUpload=@{file_path}",
            "https://litterbox.catbox.moe/resources/internals/api.php"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=40)
            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                if url.startswith("http"):
                    return url
        except Exception:
            pass
        print(f"[upload] Attempt {attempt+1} failed for {file_path}", flush=True)
    return None


@app.route("/")
def index():
    return flask.render_template("index.html")


@app.route("/api/generate-image", methods=["POST"])
def generate_image():
    if flask.request.content_type and "multipart" in flask.request.content_type:
        return handle_image_upload()

    data = flask.request.get_json()
    prompt = data.get("prompt", "")
    model = data.get("model", "agnes-image-2.1-flash")
    size = data.get("size", "1024x1024")
    n = data.get("n", 1)
    image_urls = data.get("images") or None

    body = {"model": model, "prompt": prompt, "size": size, "n": n}
    if image_urls:
        body["extra_body"] = {
            "tags": ["img2img"],
            "image": image_urls if isinstance(image_urls, list) else [image_urls],
            "response_format": "url"
        }

    result, status = curl_post(f"{BASE_URL}/images/generations", body)
    return flask.jsonify(result), status


@app.route("/api/generate-image/upload", methods=["POST"])
def handle_image_upload():
    """Handle image generation with optional file upload."""
    prompt = flask.request.form.get("prompt", "")
    model = flask.request.form.get("model", "agnes-image-2.1-flash")
    size = flask.request.form.get("size", "1024x1024")
    n = int(flask.request.form.get("n", 1))
    image_files = flask.request.files.getlist("images")

    body = {"model": model, "prompt": prompt, "size": size, "n": n}

    if image_files and image_files[0].filename:
        uploaded_urls = []
        for f in image_files:
            ext = os.path.splitext(f.filename)[1] or ".png"
            filename = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(UPLOAD_DIR, filename)
            f.save(save_path)
            print(f"[upload] Saved {save_path}", flush=True)

            public_url = upload_to_hosting(save_path)
            if public_url:
                uploaded_urls.append(public_url)
                print(f"[upload] Got public URL: {public_url}", flush=True)
            else:
                print(f"[upload] Failed to upload {save_path}", flush=True)

        if uploaded_urls:
            body["extra_body"] = {
                "tags": ["img2img"],
                "image": uploaded_urls,
                "response_format": "url"
            }
        else:
            return {"error": "图片上传失败，无法获取公网 URL。请尝试使用 URL 模式输入图片链接。"}, 400

    result, status = curl_post(f"{BASE_URL}/images/generations", body)
    return flask.jsonify(result), status


@app.route("/api/create-video", methods=["POST"])
def create_video():
    if flask.request.content_type and "multipart" in flask.request.content_type:
        return handle_video_upload()

    data = flask.request.get_json()
    prompt = data.get("prompt", "")
    width = data.get("width", 1152)
    height = data.get("height", 768)
    num_frames = data.get("num_frames", 121)
    frame_rate = data.get("frame_rate", 24)
    seed = data.get("seed")
    image_urls = data.get("images")
    mode = data.get("mode")
    negative_prompt = data.get("negative_prompt")

    body = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }
    if seed:
        body["seed"] = seed
    if image_urls:
        body["image"] = image_urls if isinstance(image_urls, list) else image_urls[0]
    if mode:
        body["mode"] = mode
    if negative_prompt:
        body["negative_prompt"] = negative_prompt

    result, status = curl_post(f"{BASE_URL}/videos", body, timeout=120)
    return flask.jsonify(result), status


@app.route("/api/create-video/upload", methods=["POST"])
def handle_video_upload():
    """Handle video creation with optional file upload."""
    prompt = flask.request.form.get("prompt", "")
    width = int(flask.request.form.get("width", 1152))
    height = int(flask.request.form.get("height", 768))
    num_frames = int(flask.request.form.get("num_frames", 121))
    frame_rate = int(flask.request.form.get("frame_rate", 24))
    seed = flask.request.form.get("seed")
    mode = flask.request.form.get("mode", "")
    negative_prompt = flask.request.form.get("negative_prompt", "")
    image_files = flask.request.files.getlist("images")

    body = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }
    if seed:
        body["seed"] = int(seed)
    if mode:
        body["mode"] = mode
    if negative_prompt:
        body["negative_prompt"] = negative_prompt

    if image_files and image_files[0].filename:
        uploaded_urls = []
        for f in image_files:
            ext = os.path.splitext(f.filename)[1] or ".png"
            filename = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(UPLOAD_DIR, filename)
            f.save(save_path)
            print(f"[upload] Saved {save_path}", flush=True)

            public_url = upload_to_hosting(save_path)
            if public_url:
                uploaded_urls.append(public_url)
                print(f"[upload] Got public URL: {public_url}", flush=True)
            else:
                print(f"[upload] Failed to upload {save_path}", flush=True)

        if uploaded_urls:
            body["image"] = uploaded_urls if len(uploaded_urls) > 1 else uploaded_urls[0]
        else:
            return {"error": "图片上传失败，无法获取公网 URL。请尝试使用 URL 模式输入图片链接。"}, 400

    result, status = curl_post(f"{BASE_URL}/videos", body, timeout=120)
    return flask.jsonify(result), status


@app.route("/api/video-status/<task_id>")
def video_status(task_id):
    result, status = curl_get(f"{BASE_URL}/videos/{task_id}")
    return flask.jsonify(result), status


@app.route("/api/save-file", methods=["POST"])
def save_file():
    """Download a remote URL to local uploads directory and return local URL."""
    data = flask.request.get_json(silent=True) or {}
    url = data.get("url", "")
    if not url:
        return flask.jsonify({"error": "url required"}), 400

    # Determine extension from URL or content-type
    ext = ".png"
    match = re.search(r"\.(\w+)(?:\?|$)", url.split("/")[-1])
    if match:
        ext = f".{match.group(1).lower()}"
    known_img = {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
    known_vid = {"mp4", "webm", "mov", "avi"}
    if ext.lstrip(".") not in known_img | known_vid:
        ext = ".mp4" if "video" in url.lower() else ".png"

    filename = f"{uuid.uuid4()}{ext}"
    save_path = os.path.join(UPLOAD_DIR, filename)

    # Download via curl
    rc = subprocess.run(
        ["curl", "-s", "-o", save_path, "--max-time", "60", url],
        capture_output=True
    )
    if rc.returncode != 0:
        return flask.jsonify({"error": f"download failed (code {rc.returncode})"}), 502
    if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
        return flask.jsonify({"error": "downloaded file is empty"}), 502

    local_url = f"/static/uploads/{filename}"
    return flask.jsonify({"localUrl": local_url, "size": os.path.getsize(save_path)})


@app.route("/api/clear-files", methods=["POST"])
def clear_files():
    """Delete all locally saved generation files."""
    data = flask.request.get_json(silent=True) or {}
    keep = set(data.get("keep", []))
    deleted = 0
    for f in os.listdir(UPLOAD_DIR):
        fpath = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(fpath) and f not in keep:
            os.remove(fpath)
            deleted += 1
    return flask.jsonify({"deleted": deleted})


if __name__ == "__main__":
    if not API_KEY:
        print("Warning: AGNES_API_KEY not set", file=sys.stderr)
    app.run(host="127.0.0.1", port=5000, debug=True)
