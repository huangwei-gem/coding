#!/usr/bin/env python3
"""Agnes AI Video Generation Script - Async with polling"""

import argparse
import json
import os
import sys
import time
import re

import requests

API_KEY = os.environ.get("AGNES_API_KEY", "")
BASE_URL = "https://apihub.agnes-ai.com/v1"


def is_chinese(text: str) -> bool:
    return bool(re.search(r'[一-鿿]', text))


def translate_text(text: str) -> str:
    if not is_chinese(text):
        return text
    try:
        resp = requests.post(
            f"{BASE_URL}/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            json={
                "model": "agnes-qwen-v2.5-7b",
                "messages": [
                    {"role": "system", "content": "You are a translator. Translate the following Chinese text to English. Return ONLY the translation, nothing else."},
                    {"role": "user", "content": text}
                ]
            },
            timeout=60
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"Warning: Translation failed ({e}), using original prompt.", file=sys.stderr)
        return text


def create_video_task(prompt: str, width: int = 1152, height: int = 768,
                      num_frames: int = 121, frame_rate: int = 24,
                      seed: int = None, image_urls: list = None,
                      mode: str = None, negative_prompt: str = None,
                      no_translate: bool = False):
    if not API_KEY:
        print("Error: AGNES_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if not no_translate:
        prompt = translate_text(prompt)

    # Validate num_frames: must satisfy 8n+1, <= 441
    valid_frames = {8 * n + 1 for n in range(1, 56) if 8 * n + 1 <= 441}
    if num_frames not in valid_frames:
        closest = min(valid_frames, key=lambda x: abs(x - num_frames))
        print(f"Warning: num_frames={num_frames} must satisfy 8n+1 (<= 441). Using {closest}.", file=sys.stderr)
        num_frames = closest

    body = {
        "model": "agnes-video-v2.0",
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
    }

    if seed is not None:
        body["seed"] = seed
    if image_urls:
        body["image"] = image_urls if len(image_urls) > 1 else image_urls[0]
    if mode:
        body["mode"] = mode
    if negative_prompt:
        body["negative_prompt"] = negative_prompt

    try:
        resp = requests.post(
            f"{BASE_URL}/videos",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            json=body,
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def get_video_task(task_id: str):
    try:
        resp = requests.get(
            f"{BASE_URL}/videos/{task_id}",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def poll_video_task(task_id: str, interval: int = 10, timeout: int = 600):
    start = time.time()
    while time.time() - start < timeout:
        result = get_video_task(task_id)
        status = result.get("status", "unknown")
        elapsed = int(time.time() - start)
        print(f"[{elapsed}s] Status: {status}", file=sys.stderr)

        if status == "completed":
            return result
        elif status == "failed":
            print(f"Task failed: {result}", file=sys.stderr)
            sys.exit(1)

        time.sleep(interval)

    print(f"Timeout after {timeout}s", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate videos with Agnes AI")
    subparsers = parser.add_subparsers(dest="command", help="Sub-command")

    # create subcommand
    create_parser = subparsers.add_parser("create", help="Create a video generation task")
    create_parser.add_argument("--prompt", "-p", required=True, help="Video description prompt")
    create_parser.add_argument("--width", type=int, default=1152, help="Video width (default: 1152)")
    create_parser.add_argument("--height", type=int, default=768, help="Video height (default: 768)")
    create_parser.add_argument("--num-frames", type=int, default=121, help="Number of frames (8n+1, <=441, default: 121)")
    create_parser.add_argument("--frame-rate", type=int, default=24, help="Frame rate (default: 24)")
    create_parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    create_parser.add_argument("--image", action="append", dest="images", help="Reference image URL(s)")
    create_parser.add_argument("--mode", choices=["keyframes"], help="Video mode (keyframes for start-end animation)")
    create_parser.add_argument("--negative-prompt", help="What to avoid in the video")
    create_parser.add_argument("--no-translate", action="store_true", help="Skip Chinese translation")
    create_parser.add_argument("--poll", action="store_true", help="Poll until completion")

    # get subcommand
    get_parser = subparsers.add_parser("get", help="Get video task result")
    get_parser.add_argument("task_id", help="Task ID to query")

    args = parser.parse_args()

    if args.command == "get":
        result = get_video_task(args.task_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "create":
        result = create_video_task(
            prompt=args.prompt,
            width=args.width,
            height=args.height,
            num_frames=args.num_frames,
            frame_rate=args.frame_rate,
            seed=args.seed,
            image_urls=args.images,
            mode=args.mode,
            negative_prompt=args.negative_prompt,
            no_translate=args.no_translate
        )
        task_id = result.get("task_id") or result.get("id", "unknown")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if args.poll:
            print(f"\nPolling task {task_id}...", file=sys.stderr)
            final = poll_video_task(task_id)
            print(json.dumps(final, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
