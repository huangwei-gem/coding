"""
日志工具模块
==========
统一日志配置，控制台 + 可选文件输出。
"""
import logging
import sys

from config.settings import LOG_CONFIG


def setup_logger(name: str = "zhipin") -> logging.Logger:
    """获取或创建带统一格式的 logger。"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 避免重复添加
        return logger

    level = getattr(logging, LOG_CONFIG["level"].upper(), logging.DEBUG)
    logger.setLevel(level)

    fmt = logging.Formatter(LOG_CONFIG["format"], datefmt=LOG_CONFIG["datefmt"])

    # 控制台 Handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件 Handler（可选）
    if LOG_CONFIG.get("file"):
        fh = logging.FileHandler(LOG_CONFIG["file"], encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# 全局默认 logger
logger = setup_logger()
