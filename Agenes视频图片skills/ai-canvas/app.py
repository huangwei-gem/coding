#!/usr/bin/env python3
"""Agnes AI Canvas - Web UI for Image & Video Generation
Uses curl subprocess for reliable API access (Python SSL has issues on this env).
"""

import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import uuid

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
    """Call Agnes API via curl subprocess. Retries once on timeout/error.
    Uses stdin pipe (-d @-) to avoid Windows command-line length limits."""
    body_str = json.dumps(json_body)
    errors = []
    for attempt in range(2):
        http_code = "000"
        cmd = [
            "curl", "-s", "--max-time", str(timeout),
            "-w", "\n%{http_code}",
            "-H", f"Authorization: Bearer {_get_api_key()}",
            "-H", "Content-Type: application/json",
            "-d", "@-",
            url
        ]
        try:
            result = subprocess.run(cmd, input=body_str, capture_output=True, text=True, timeout=timeout + 15)
            stdout = result.stdout or ""
            stderr = result.stderr.strip() if result.stderr else ""

            # Split body and HTTP status code (last line after -w)
            lines = stdout.rstrip().split("\n")
            http_code = lines[-1].strip() if len(lines) > 1 else "000"
            resp_body = "\n".join(lines[:-1]) if len(lines) > 1 else stdout

            if result.returncode != 0:
                msg = f"curl error (code {result.returncode})"
                if stderr:
                    msg += f": {stderr}"
                if result.returncode == 28 and attempt == 0:
                    errors.append(msg)
                    print(f"[api] Attempt {attempt+1} timed out, retrying...", flush=True)
                    continue
                return {"error": msg}, 502

            if not resp_body or not resp_body.strip():
                detail = f" (HTTP {http_code}"
                detail += f", stderr: {stderr}" if stderr else ")"
                if attempt == 0:
                    errors.append(f"empty response{detail}")
                    print(f"[api] Attempt {attempt+1} got empty response{detail}, retrying...", flush=True)
                    continue
                return {"error": f"empty response from API{detail}"}, 502

            data = json.loads(resp_body)
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
            return {"error": f"Invalid response: {e} (HTTP {http_code})"}, 502
        except Exception as e:
            return {"error": str(e)}, 500
    return {"error": "; ".join(errors)}, 502


def curl_get(url, timeout=30):
    """Call Agnes API GET via curl subprocess."""
    cmd = [
        "curl", "-s", "--max-time", str(timeout),
        "-H", f"Authorization: Bearer {_get_api_key()}",
        url
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
        if result.returncode != 0:
            return {"error": f"curl error (code {result.returncode})"}, 502
        raw = result.stdout
        if not raw or not raw.strip():
            return {"error": "empty response from API"}, 502
        data = json.loads(raw)
        if "error" in data:
            return data, 400
        return data, 200
    except json.JSONDecodeError:
        return {"error": "invalid JSON response from API"}, 502
    except Exception as e:
        return {"error": str(e)}, 500


def file_to_data_url(file_storage):
    """Convert a Flask FileStorage to a base64 data URL.
    Returns data URL string or None on failure."""
    try:
        raw = file_storage.read()
        file_storage.seek(0)
        mime_type, _ = mimetypes.guess_type(file_storage.filename)
        if not mime_type:
            mime_type = "image/png"
        b64_str = base64.b64encode(raw).decode("ascii")
        return f"data:{mime_type};base64,{b64_str}"
    except Exception as e:
        print(f"[upload] Failed to convert {file_storage.filename} to data URL: {e}", flush=True)
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
        data_urls = []
        for f in image_files:
            print(f"[upload] Processing {f.filename}", flush=True)
            data_url = file_to_data_url(f)
            if data_url:
                data_urls.append(data_url)
                print(f"[upload] Converted {f.filename} to data URL ({len(data_url)} chars)", flush=True)
            else:
                print(f"[upload] Failed to convert {f.filename}", flush=True)

        if data_urls:
            body["extra_body"] = {
                "tags": ["img2img"],
                "image": data_urls,
                "response_format": "url"
            }
        else:
            return {"error": "图片转换失败，无法读取文件内容。请尝试使用 URL 模式输入图片链接。"}, 400

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
        data_urls = []
        for f in image_files:
            print(f"[upload] Processing {f.filename}", flush=True)
            data_url = file_to_data_url(f)
            if data_url:
                data_urls.append(data_url)
                print(f"[upload] Converted {f.filename} to data URL ({len(data_url)} chars)", flush=True)
            else:
                print(f"[upload] Failed to convert {f.filename}", flush=True)

        if data_urls:
            body["image"] = data_urls if len(data_urls) > 1 else data_urls[0]
        else:
            return {"error": "图片转换失败，无法读取文件内容。请尝试使用 URL 模式输入图片链接。"}, 400

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

    # Download via curl (follow redirects, allow 5 min for large videos)
    rc = subprocess.run(
        ["curl", "-sL", "-o", save_path, "--max-time", "300", url],
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


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """Get or set runtime configuration."""
    if flask.request.method == "GET":
        return flask.jsonify({
            "has_api_key": bool(_get_api_key()),
            "api_key_set_via": "header" if flask.request.headers.get("X-Agnes-Api-Key") else ("runtime" if RUNTIME.get("api_key") else "env"),
        })
    data = flask.request.get_json(silent=True) or {}
    changed = []
    if "api_key" in data:
        RUNTIME["api_key"] = data["api_key"]
        changed.append("api_key")
    return flask.jsonify({"ok": True, "changed": changed})


if __name__ == "__main__":
    if not _get_api_key():
        print("Warning: AGNES_API_KEY not set", file=sys.stderr)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False, threaded=True)
