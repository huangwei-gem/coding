"""项目配置"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent

# Cookie 存储路径
COOKIE_DIR = ROOT_DIR / "cookies"
COOKIE_FILE = COOKIE_DIR / "zhipin_cookies.json"

# 看板图片目录
DASHBOARD_DIR = ROOT_DIR / "数据分析看板"

# 自动化默认配置
DEFAULT_CITY = "上海"
DEFAULT_JOB = "数据分析"
DEFAULT_MESSAGE = "您好，我是双一流的本科，应聘数据分析岗位。在校系统学习数据分析相关知识，掌握Excel、基础SQL与数据整理技能，具备数据思维。做事严谨细心，学习能力强，愿意踏实积累。十分认可贵公司，希望能获得面试机会。"

# BOSS 直聘 URL
BASE_URL = "https://www.zhipin.com"
LOGIN_URL = "https://www.zhipin.com/web/user/?ka=header-login"
JOB_SEARCH_URL = "https://www.zhipin.com/web/geek/jobs"
CITY_API_URL = "https://www.zhipin.com/wapi/zpCommon/data/city.json"

# 浏览器配置
BROWSER_HEADLESS = False
BROWSER_PORT = None

# 日志文件
LOG_FILE = ROOT_DIR / "automation.log"

# 滚动加载次数
SCROLL_TIMES = 5

# Flask
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5000
FLASK_DEBUG = True
