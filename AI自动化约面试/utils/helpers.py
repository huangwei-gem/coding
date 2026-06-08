"""
通用工具函数
==========
"""
import time
from typing import Any, Callable, Optional, TypeVar

from DrissionPage import ChromiumPage

from core.exceptions import MaxRetryExceeded
from utils.logger import logger

T = TypeVar("T")


def retry(
    func: Callable[..., T],
    retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple = (Exception,),
    action_desc: str = "",
) -> T:
    """
    通用重试装饰器（函数式用法）。

    Args:
        func:        要重试的函数
        retries:     最大重试次数
        delay:       重试间隔（秒）
        exceptions:  捕获的异常类型
        action_desc: 操作的描述文字（日志用）

    Returns:
        函数执行结果

    Raises:
        MaxRetryExceeded: 超过最大重试次数
    """
    desc = action_desc or getattr(func, "__name__", "未知操作")
    for attempt in range(1, retries + 1):
        try:
            return func()
        except exceptions as e:
            logger.warning("%s 失败 (第%d/%d次): %s", desc, attempt, retries, e)
            if attempt < retries:
                time.sleep(delay)
            else:
                raise MaxRetryExceeded(desc, retries) from e


def scroll_to_bottom_safe(page: ChromiumPage, wait_sec: float = 2.0, retries: int = 2):
    """
    安全滚动到页面底部，带重试。

    Args:
        page:      ChromiumPage 实例
        wait_sec:  滚动后等待秒数
        retries:   重试次数
    """
    for attempt in range(1, retries + 1):
        try:
            page.scroll.to_bottom()
            page.wait(wait_sec)
            return
        except Exception as e:
            logger.warning("滚动到底部失败 (第%d/%d次): %s", attempt, retries, e)
            if attempt < retries:
                page.wait(3)
    logger.error("滚动到底部已超出最大重试次数")


def safe_ele_text(page: ChromiumPage, selector: str, default: str = "") -> str:
    """安全获取元素的文本内容，失败返回默认值。"""
    try:
        ele = page.ele(selector, timeout=5)
        return ele.text if ele else default
    except Exception as e:
        logger.debug("获取元素文本失败 selector=%s: %s", selector, e)
        return default


def safe_click(page: ChromiumPage, selector: str, timeout: float = 10) -> bool:
    """安全点击元素。"""
    try:
        btn = page.ele(selector, timeout=timeout)
        if btn:
            btn.click()
            return True
        logger.warning("点击元素不存在: %s", selector)
        return False
    except Exception as e:
        logger.warning("点击失败 selector=%s: %s", selector, e)
        return False


def safe_input(page: ChromiumPage, selector: str, text: str, timeout: float = 10) -> bool:
    """安全输入文本。"""
    try:
        ele = page.ele(selector, timeout=timeout)
        if ele:
            ele.input(text)
            return True
        logger.warning("输入框不存在: %s", selector)
        return False
    except Exception as e:
        logger.warning("输入失败 selector=%s: %s", selector, e)
        return False


def parse_job_info(job_str: str, url: str = "") -> dict:
    """
    解析单条岗位信息的文本字符串为结构化字典。

    Args:
        job_str: 岗位文本块（由 \\n 分隔多行）
        url:     对应的岗位链接

    Returns:
        dict: {
            "job_name", "salary", "experience", "education",
            "company_location", "raw", "url"
        }
    """
    from config.settings import SALARY_MARKERS

    parts = job_str.split("\n")
    info: dict = {
        "job_name": "",
        "salary": "",
        "experience": parts[1] if len(parts) >= 2 else "",
        "education": parts[2] if len(parts) >= 3 else "",
        "company_location": parts[3] if len(parts) >= 4 else "",
        "raw": job_str,
        "url": url,
    }

    if parts:
        first = parts[0]
        # 找到第一个薪资标记的位置进行分离
        pos = len(first)
        for marker in SALARY_MARKERS:
            idx = first.find(marker)
            if idx != -1 and idx < pos:
                pos = idx
        if pos < len(first):
            info["job_name"] = first[:pos].strip()
            info["salary"] = first[pos:].strip()
        else:
            info["job_name"] = first

    return info
