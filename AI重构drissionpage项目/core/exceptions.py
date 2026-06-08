"""
自定义异常模块
==========
"""
from typing import Optional


class ZhipinError(Exception):
    """Boss 直聘自动化基础异常。"""


class LoginRequired(ZhipinError):
    """需要用户手动登录。"""


class CityNotFound(ZhipinError):
    """城市未在热门城市列表中找到。"""

    def __init__(self, city: str, available: Optional[list] = None):
        self.city = city
        self.available = available or []
        super().__init__(f"城市「{city}」不在热门列表中，可用: {self.available}")


class ElementNotFound(ZhipinError):
    """页面元素未找到。"""

    def __init__(self, selector: str, url: str = ""):
        self.selector = selector
        self.url = url
        super().__init__(f"元素未找到: {selector} (url={url})")


class ActionFailed(ZhipinError):
    """操作执行失败（如点击、输入、上传）。"""


class MaxRetryExceeded(ZhipinError):
    """超过最大重试次数。"""

    def __init__(self, action_desc: str, retries: int):
        self.action_desc = action_desc
        self.retries = retries
        super().__init__(f"操作「{action_desc}」超过最大重试次数 ({retries})")
