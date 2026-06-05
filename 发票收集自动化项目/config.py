"""全局配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 运行模式
RUN_MODE = os.getenv("RUN_MODE", "demo")  # demo | production

# ----- 数据库 -----
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "invoice_project"),
}

# ----- 短信服务 -----
SMS_CONFIG = {
    "provider": os.getenv("SMS_PROVIDER", "aliyun"),
    "access_key_id": os.getenv("SMS_ACCESS_KEY_ID", ""),
    "access_key_secret": os.getenv("SMS_ACCESS_KEY_SECRET", ""),
    "sign_name": os.getenv("SMS_SIGN_NAME", ""),
    "template_code": os.getenv("SMS_TEMPLATE_CODE", ""),
    "custom_content": os.getenv(
        "SMS_CUSTOM_CONTENT",
        "尊敬的{name}业主您好，关于小区居委会换届事宜，"
        '请您回复"同意"或"不同意"确认您的意愿。感谢您的支持！',
    ),
}

# ----- AI API -----
AI_CONFIG = {
    "api_key": os.getenv("AI_API_KEY", ""),
    "api_base": os.getenv("AI_API_BASE", "https://api.openai.com/v1"),
    "model": os.getenv("AI_MODEL", "gpt-4o-mini"),
}

# ----- 数据目录 -----
DATA_DIR = ROOT_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_CLEANED = DATA_DIR / "output" / "cleaned"
OUTPUT_EVIDENCE = DATA_DIR / "output" / "evidence"
OUTPUT_REPORTS = DATA_DIR / "output" / "reports"

# ----- 违禁词库 -----
PROHIBITED_WORDS_FILE = ROOT_DIR / "configs" / "prohibited_words.txt"

# ----- 定时任务配置 -----
REPLY_POLL_INTERVAL_MINUTES = 10  # 每10分钟拉取一次回复

# ----- 意愿分析 -----
INTENTION_ACCURACY_THRESHOLD = 0.95  # 准确率阈值
