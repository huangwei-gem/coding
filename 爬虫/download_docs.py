"""Download DrissionPage documentation and convert to Markdown."""
import re
import os
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup
import html2text

BASE_URL = "https://www.drissionpage.cn"
OUTPUT_DIR = Path(__file__).parent / "drissionpage_docs"

# All doc pages from the sitemap (organized by section)
DOCS_URLS = {
    "00_入门": [
        "/get_start/installation",
        "/get_start/before_start",
        "/get_start/concept",
        "/get_start/import",
        "/get_start/set_lang",
        "/get_start/examples/control_browser",
        "/get_start/examples/data_packets",
        "/get_start/examples/switch_mode",
    ],
    "01_控制浏览器": [
        "/browser_control/intro",
        "/browser_control/connect_browser",
        "/browser_control/browser_options",
        "/browser_control/browser_object",
        "/browser_control/tabs",
        "/browser_control/visit",
        "/browser_control/page_operation",
        "/browser_control/get_page_info",
        "/browser_control/get_elements/intro",
        "/browser_control/get_elements/find_in_object",
        "/browser_control/get_elements/syntax",
        "/browser_control/get_elements/filter",
        "/browser_control/get_elements/behavior",
        "/browser_control/get_elements/relative",
        "/browser_control/get_elements/simplify",
        "/browser_control/get_elements/sheet",
        "/browser_control/ele_operation",
        "/browser_control/get_ele_info",
        "/browser_control/iframe",
        "/browser_control/actions",
        "/browser_control/mode_change",
        "/browser_control/waiting",
        "/browser_control/listener",
        "/browser_control/console",
        "/browser_control/screen",
        "/browser_control/upload",
        "/browser_control/pages",
    ],
    "02_SessionPage": [
        "/SessionPage/intro",
        "/SessionPage/create_obj",
        "/SessionPage/visit",
        "/SessionPage/get_ele",
        "/SessionPage/get_ele_info",
        "/SessionPage/get_page_info",
        "/SessionPage/session_opt",
        "/SessionPage/settings",
    ],
    "03_进阶使用": [
        "/download/intro",
        "/download/browser",
        "/download/DownloadKit",
        "/advance/accelerate",
        "/advance/commands",
        "/advance/docking",
        "/advance/errors",
        "/advance/ini",
        "/advance/packaging",
        "/advance/settings",
        "/advance/tools",
    ],
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

converter = html2text.HTML2Text()
converter.body_width = 0
converter.protect_links = True
converter.ignore_links = False
converter.ignore_images = False
converter.ignore_emphasis = False
converter.skip_internal_links = False
converter.unicode_snob = True


def extract_title(soup: BeautifulSoup) -> str:
    """Extract the page title from the document."""
    h1 = soup.select_one("header h1")
    if h1:
        return h1.get_text(strip=True)
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text(strip=True).replace(" | DrissionPage官网", "")
    return "untitled"


def fetch_page(url: str) -> str | None:
    """Fetch a page and return the main content HTML."""
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException as e:
        print(f"  [ERROR] Failed to fetch {url}: {e}")
        return None


def clean_markdown(md: str) -> str:
    """Clean up markdown content."""
    # Remove excessive blank lines
    md = re.sub(r"\n{4,}", "\n\n\n", md)
    # Remove "跳到主要内容" artifact
    md = md.replace("跳到主要内容", "")
    return md.strip()


def slugify(path: str) -> str:
    """Create a filesystem-safe name from a URL path."""
    name = path.strip("/").replace("/", "_")
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def download_page(url_path: str) -> tuple[str, str] | None:
    """Download a single page and convert to markdown."""
    full_url = f"{BASE_URL}{url_path}"
    print(f"  Fetching: {full_url}")

    html = fetch_page(full_url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted elements
    for elem in soup.select(
        "script, style, noscript, iframe, .wwads-cn, .wwads, "
        ".announcementBar, .footer, .navbar, nav.pagination-nav, "
        ".theme-doc-toc-mobile, .theme-doc-breadcrumbs, .table-of-contents, "
        ".codeBlockTitle, .copyButtonIcon, .copyButtonSuccessIcon, "
        ".buttonGroup__atx, .codeBlockLines_e6Vv + div"
    ):
        elem.decompose()

    # Remove ads / CC license from footer area of the article
    for elem in soup.select("br"):
        # Remove extra <br> used for spacing around ads
        pass

    # Get the main content area
    article = soup.select_one("article")
    if not article:
        # fallback: try main content area
        article = soup.select_one("main .docItemCol_Djhp")
    if not article:
        article = soup.select_one("main")
    if not article:
        print("  [WARN] No main content found")
        return None

    # Remove the breadcrumbs and TOC mobile button inside article
    for elem in article.select(
        ".theme-doc-breadcrumbs, .tocCollapsible_ETCw, "
        ".pagination-nav, .wwads-cn"
    ):
        elem.decompose()

    # Remove header nav wrapper if present
    header = article.select_one("header")
    if header:
        # Keep header
        pass

    title = extract_title(soup)

    # Convert to markdown
    content_html = str(article)
    md = converter.handle(content_html)

    # Clean up
    md = clean_markdown(md)

    return (title, md)


def main():
    total = sum(len(urls) for urls in DOCS_URLS.values())
    fetched = 0
    errors = 0

    print(f"Starting download of {total} pages...\n")

    for section, urls in DOCS_URLS.items():
        section_dir = OUTPUT_DIR / section
        section_dir.mkdir(parents=True, exist_ok=True)

        for url_path in urls:
            result = download_page(url_path)
            if result:
                title, md = result
                filename = slugify(url_path) + ".md"
                filepath = section_dir / filename

                # Prepend title if not already in markdown
                if not md.startswith(f"# {title}"):
                    md = f"# {title}\n\n{md}"

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md + "\n")

                size = len(md)
                print(f"  -> Saved: {filepath.relative_to(OUTPUT_DIR)} ({size} chars)")
                fetched += 1
            else:
                errors += 1

            time.sleep(0.3)  # Be polite

    print(f"\nDone! {fetched}/{total} pages downloaded successfully.")
    if errors:
        print(f"  {errors} pages failed.")


if __name__ == "__main__":
    main()
