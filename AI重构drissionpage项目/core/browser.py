"""
浏览器管理模块
==========
封装 ChromiumPage，提供统一初始化、防检测配置、优雅关闭。
"""
import os
from contextlib import contextmanager
from typing import Optional

from DrissionPage import ChromiumPage, ChromiumOptions

from config.settings import BROWSER_CONFIG
from utils.logger import logger


class BrowserManager:
    """浏览器管理器 —— 单例模式，确保全局只有一个浏览器实例。"""

    _instance: Optional["BrowserManager"] = None
    _page: Optional[ChromiumPage] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # -------- 初始化 --------

    def init_page(
        self,
        headless: Optional[bool] = None,
        no_imgs: Optional[bool] = None,
        incognito: Optional[bool] = None,
        port: Optional[int] = None,
    ) -> ChromiumPage:
        """
        初始化（或复用）ChromiumPage。

        Args:
            headless: 是否无头模式，None 使用 settings 默认
            no_imgs:  是否禁用图片
            incognito: 是否无痕模式
            port:     指定端口，None 则自动分配

        Returns:
            ChromiumPage 实例
        """
        if self._page is not None and self._page.states.is_alive:
            logger.info("复用已有浏览器页面")
            return self._page

        co = self._build_options(headless, no_imgs, incognito, port)
        self._page = ChromiumPage(addr_or_opts=co)
        logger.info(
            "浏览器已启动 | headless=%s no_imgs=%s incognito=%s",
            headless if headless is not None else BROWSER_CONFIG.get("headless", False),
            no_imgs if no_imgs is not None else BROWSER_CONFIG.get("disable_imgs", True),
            incognito if incognito is not None else BROWSER_CONFIG.get("incognito", True),
        )
        return self._page

    # -------- 关闭 --------

    def quit_page(self):
        """优雅关闭浏览器并释放资源。"""
        if self._page and self._page.states.is_alive:
            try:
                self._page.quit()
                logger.info("浏览器已优雅关闭")
            except Exception as e:
                logger.warning("关闭浏览器时异常: %s", e)
            finally:
                self._page = None
        else:
            logger.info("浏览器已关闭，无需重复操作")

    # -------- 属性 --------

    @property
    def page(self) -> ChromiumPage:
        """获取当前页面实例（未初始化时自动初始化）。"""
        if self._page is None or not self._page.states.is_alive:
            return self.init_page()
        return self._page

    @page.setter
    def page(self, value: ChromiumPage):
        self._page = value

    # -------- 内部 --------

    @staticmethod
    def _build_options(
        headless: Optional[bool],
        no_imgs: Optional[bool],
        incognito: Optional[bool],
        port: Optional[int],
    ) -> ChromiumOptions:
        c = BROWSER_CONFIG
        co = ChromiumOptions()

        # 基础设置（DrissionPage 4.x 使用属性赋值）
        co.headless = headless if headless is not None else c.get("headless", False)
        co.no_imgs = no_imgs if no_imgs is not None else c.get("no_imgs", True)
        co.incognito = incognito if incognito is not None else c.get("incognito", True)
        co.set_load_mode(c.get("page_load_strategy", "normal"))
        if port:
            co.set_local_port(port)
        elif c.get("auto_port", True):
            co.auto_port()  # 调用方法而非赋值，会清除 address 并启用自动端口

        # 浏览器可执行文件路径（解决 Windows 下 PATH 找不到 chrome 的问题）
        browser_path = c.get("browser_path") or c.get("browser_path_fallback")
        if browser_path and os.path.isfile(browser_path):
            co.set_browser_path(browser_path)
        elif browser_path:
            logger.warning("配置的浏览器路径不存在: %s", browser_path)

        # 自定义 UA（防检测）
        if ua := c.get("set_user_agent"):
            co.set_user_agent(ua)

        # 加载偏好设置
        prefs = c.get("prefs", {})
        if prefs.get("disable_browser_features"):
            co.set_flag("disable-blink-features", "AutomationControlled")
            co.set_flag("disable-blink-features", "ChromeDevTools")
        if prefs.get("webrtc_ip_handling"):
            co.set_flag("webrtc-ip-handling-policy", prefs["webrtc_ip_handling"])
        if prefs.get("exclude_switches"):
            for sw in prefs["exclude_switches"]:
                co.set_flag("exclude-switches", sw)

        return co

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit_page()


# 全局单例
browser = BrowserManager()


@contextmanager
def managed_page(**kwargs):
    """上下文管理器，自动初始化 & 关闭浏览器。"""
    page = browser.init_page(**kwargs)
    try:
        yield page
    finally:
        browser.quit_page()
