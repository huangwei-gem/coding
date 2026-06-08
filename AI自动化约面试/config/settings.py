"""
项目全局配置
==========
集中管理所有可配置项，避免硬编码散落在业务代码中。
"""
import os
from pathlib import Path

# ---------- 路径 ----------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COOKIE_FILE = PROJECT_ROOT / "zhipin_cookies"
DASHBOARD_DIR = PROJECT_ROOT / "数据分析看板"
DASHBOARD_IMAGES = [
    str(DASHBOARD_DIR / "看板1.png"),
    str(DASHBOARD_DIR / "看板2.png"),
    str(DASHBOARD_DIR / "看板3.png"),
]

# ---------- 目标网站 ----------
BASE_URL = "https://www.zhipin.com"
LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
CITY_API_PATTERN = "data/city.json"
JOB_SEARCH_PATH = "/web/geek/jobs"

# ---------- 业务参数 ----------
DEFAULT_CITY = "上海"
DEFAULT_JOB = "数据分析"
SCROLL_TIMES = 5
SCROLL_WAIT = 2
SCROLL_RETRY_WAIT = 3

# ---------- 元素选择器 ----------
SELECTORS = {
    "user_nav": ".user-nav",
    "job_name": ".job-name",
    "rec_job_list": ".rec-job-list",
    "btn_startchat": ".btn btn-startchat",
    "boss_active_time": ".boss-active-time",
    "icon_scale": ".icon-scale",
    "job_sec_text": ".job-sec-text",
    "salary": ".salary",
    "input_area": ".input-area",
    "send_message": ".send-message",
    "icon_close": ".icon-close",
    "upload_btn": ".toolbar-btn-content icon btn-sendimg tooltip tooltip-top",
}

# ---------- 关键字 ----------
LOGIN_KEYWORD = "登录/注册"
CONTINUE_CHAT_TEXT = "继续沟通"

# ---------- 薪资标记（用于从字符串中分离职位名与薪资） ----------
SALARY_MARKERS = ["K", "元/月", "元/天", "薪"]

# ---------- 投递消息 ----------
APPLY_MESSAGE = (
    "您好，我是双一流的本科，应聘数据分析岗位。"
    "在校系统学习数据分析相关知识，掌握Excel、基础SQL与数据整理技能，具备数据思维。"
    "做事严谨细心，学习能力强，愿意踏实积累。"
    "十分认可贵公司，希望能获得面试机会。"
)

# ---------- 浏览器配置 ----------
BROWSER_CONFIG = {
    "headless": False,      # True=无头模式 False=有界面
    "no_imgs": True,         # True=禁用图片加载（提升速度）
    "incognito": True,       # True=无痕模式
    "page_load_strategy": "normal",
    "auto_port": True,
    "set_user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "browser_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    # Edge 备用路径（如果上面找不到 Chrome，这里会自动尝试）
    "browser_path_fallback": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    # -------- 防检测配置 --------------
    "prefs": {
        "disable_browser_features": True,
        "webrtc_ip_handling": "disable_non_proxied_udp",
        "exclude_switches": ["enable-automation"],
        "suppress_warning": True,
    },
}

# ---------- 日志配置 ----------
LOG_CONFIG = {
    "level": "DEBUG",
    "format": "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
    "file": None,  # None 表示只输出到控制台；可设为 PROJECT_ROOT / "app.log"
}
