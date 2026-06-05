#!/usr/bin/env python3
"""Agnes AI Image Generation Script"""

import argparse
import json
import os
import sys
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


def generate_image(prompt: str, model: str = "agnes-image-2.1-flash",
                   size: str = "1024x1024", n: int = 1,
                   image_urls: list = None, no_translate: bool = False):
    if not API_KEY:
        print("Error: AGNES_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    if not no_translate:
        prompt = translate_text(prompt)

    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": n,
    }

    if image_urls:
        body["extra_body"] = {
            "tags": ["img2img"],
            "image": image_urls,
            "response_format": "url"
        }

    try:
        resp = requests.post(
            f"{BASE_URL}/images/generations",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
            json=body,
            timeout=180
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Generate images with Agnes AI")
    parser.add_argument("--prompt", "-p", required=True, help="Image description prompt")
    parser.add_argument("--model", "-m", default="agnes-image-2.1-flash",
                        choices=["agnes-image-2.0-flash", "agnes-image-2.1-flash"],
                        help="Model version")
    parser.add_argument("--size", "-s", default="1024x1024",
                        help="Image size (e.g. 1024x1024, 1152x864)")
    parser.add_argument("--n", type=int, default=1, help="Number of images (1-4)")
    parser.add_argument("--image", action="append", dest="images", help="Reference image URL(s)")
    parser.add_argument("--no-translate", action="store_true", help="Skip Chinese translation")
    args = parser.parse_args()

    result = generate_image(
        prompt=args.prompt,
        model=args.model,
        size=args.size,
        n=args.n,
        image_urls=args.images,
        no_translate=args.no_translate
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
