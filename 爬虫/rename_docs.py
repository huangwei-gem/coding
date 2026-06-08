"""Rename downloaded md files to use Chinese titles from h1."""
import re
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "drissionpage_docs"

# Manual filename overrides for cleaner names (key = section folder)
FILENAME_MAP = {
    "00_入门": {
        "get_start_installation": "安装",
        "get_start_before_start": "开始之前",
        "get_start_concept": "概念",
        "get_start_import": "导入",
        "get_start_set_lang": "设置语言",
        "get_start_examples_control_browser": "示例_控制浏览器",
        "get_start_examples_data_packets": "示例_数据包",
        "get_start_examples_switch_mode": "示例_切换模式",
    },
    "01_控制浏览器": {
        "browser_control_intro": "概述",
        "browser_control_connect_browser": "连接浏览器",
        "browser_control_browser_options": "浏览器启动设置",
        "browser_control_browser_object": "浏览器对象",
        "browser_control_tabs": "标签页管理",
        "browser_control_visit": "访问网页",
        "browser_control_page_operation": "页面交互",
        "browser_control_get_page_info": "获取网页信息",
        "browser_control_get_elements_intro": "查找元素_概述",
        "browser_control_get_elements_find_in_object": "查找元素_在对象中查找",
        "browser_control_get_elements_syntax": "查找元素_语法",
        "browser_control_get_elements_filter": "查找元素_筛选",
        "browser_control_get_elements_behavior": "查找元素_行为",
        "browser_control_get_elements_relative": "查找元素_相对定位",
        "browser_control_get_elements_simplify": "查找元素_简化写法",
        "browser_control_get_elements_sheet": "查找元素_速查表",
        "browser_control_ele_operation": "元素交互",
        "browser_control_get_ele_info": "获取元素信息",
        "browser_control_iframe": "iframe操作",
        "browser_control_actions": "动作链",
        "browser_control_mode_change": "模式切换",
        "browser_control_waiting": "等待",
        "browser_control_listener": "监听网络数据",
        "browser_control_console": "获取控制台信息",
        "browser_control_screen": "截图和录像",
        "browser_control_upload": "上传文件",
        "browser_control_pages": "Page对象",
    },
    "02_SessionPage": {
        "SessionPage_intro": "概述",
        "SessionPage_create_obj": "创建对象",
        "SessionPage_visit": "访问网页",
        "SessionPage_get_ele": "查找元素",
        "SessionPage_get_ele_info": "获取元素信息",
        "SessionPage_get_page_info": "获取网页信息",
        "SessionPage_session_opt": "Session操作",
        "SessionPage_settings": "设置",
    },
    "03_进阶使用": {
        "download_intro": "概述",
        "download_browser": "下载浏览器文件",
        "download_DownloadKit": "DownloadKit",
        "advance_accelerate": "加速",
        "advance_commands": "命令行",
        "advance_docking": "对接",
        "advance_errors": "错误处理",
        "advance_ini": "ini配置",
        "advance_packaging": "打包",
        "advance_settings": "设置",
        "advance_tools": "工具",
    },
}


def extract_h1_title(filepath: Path) -> str | None:
    """Read the first line of the markdown file to get the h1 title."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline().strip()
    if first_line.startswith("# "):
        return first_line[2:].strip()
    return None


def sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in filenames."""
    # Remove emoji and special Unicode symbols, keep Chinese chars
    name = re.sub(r'[🛰️✅️📌🔎🔦✅⭐]*', '', name)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '', name)
    name = name.strip('._')
    return name if name else "untitled"


def main():
    total = 0
    renamed = 0

    for section in sorted(OUTPUT_DIR.iterdir()):
        if not section.is_dir():
            continue
        section_name = section.name
        name_map = FILENAME_MAP.get(section_name, {})
        order = 0

        for filepath in sorted(section.glob("*.md")):
            total += 1
            stem = filepath.stem
            order += 1

            # Determine new name
            if stem in name_map:
                new_stem = name_map[stem]
            else:
                h1 = extract_h1_title(filepath)
                if h1:
                    new_stem = sanitize_filename(h1)
                else:
                    print(f"  [SKIP] {filepath.name} — no mapping and no h1")
                    continue

            new_filename = f"{order:02d}_{new_stem}.md"
            new_path = filepath.parent / new_filename

            if filepath != new_path:
                filepath.rename(new_path)
                print(f"  {filepath.name} -> {new_path.name}")
                renamed += 1
            else:
                print(f"  {filepath.name} (already ok)")

    print(f"\nDone! {renamed}/{total} files renamed.")


if __name__ == "__main__":
    main()
