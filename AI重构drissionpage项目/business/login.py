"""
登录处理模块
==========
检测登录状态、处理手动登录、保存/加载 cookies。
"""
from DrissionPage import ChromiumPage

from config.settings import BASE_URL, LOGIN_URL, COOKIE_FILE, SELECTORS, LOGIN_KEYWORD
from core.exceptions import LoginRequired
from utils.logger import logger


class LoginHandler:
    """Boss 直聘登录管理器。"""

    def __init__(self, page: ChromiumPage):
        self.page = page

    # -------- 登录检测 --------

    def check_login(self) -> bool:
        """
        检测当前页面是否需要登录。

        Returns:
            True 已登录 / False 需要登录
        """
        try:
            nav_ele = self.page.ele(SELECTORS["user_nav"], timeout=8)
            nav_text = nav_ele.text if nav_ele else ""
            needs_login = LOGIN_KEYWORD in nav_text
            if needs_login:
                logger.info("检测到需要登录（页面包含「%s」）", LOGIN_KEYWORD)
            else:
                logger.info("已登录状态")
            return not needs_login
        except Exception as e:
            logger.warning("检测登录状态失败，按未登录处理: %s", e)
            return False

    # -------- 登录流程 --------

    def login(self) -> bool:
        """
        完整的登录流程：
          1. 检查当前页面登录状态
          2. 尝试从文件恢复 cookies
          3. 如果未登录 → 跳转登录页 + 手动登录 + 保存 cookies

        Returns:
            True  登录成功
            False 登录失败
        """
        if self.check_login():
            return True

        # 尝试用上次保存的 cookies 恢复登录
        if self.load_cookies():
            return True

        self._navigate_to_login()
        self._wait_manual_login()

        # 保存 cookies
        try:
            cookies = self.page.cookies(all_info=True)
            COOKIE_FILE.write_text(cookies.as_json(), encoding="utf-8")
            logger.info("登录 cookies 已保存至: %s", COOKIE_FILE)
        except Exception as e:
            logger.warning("保存 cookies 失败: %s", e)

        # 二次确认
        self.page.refresh()
        self.page.wait(2)
        return self.check_login()

    # -------- Cookies 恢复（备用） --------

    def load_cookies(self) -> bool:
        """尝试从文件加载 cookies，跳过登录。"""
        if not COOKIE_FILE.exists():
            logger.info("未找到 cookies 文件，需手动登录")
            return False
        try:
            import json
            cookies = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
            self.page.set.cookies(cookies)
            self.page.refresh()
            self.page.wait(2)
            logged_in = self.check_login()
            if logged_in:
                logger.info("cookies 恢复成功")
            else:
                logger.info("cookies 已过期，需重新登录")
            return logged_in
        except Exception as e:
            logger.warning("加载 cookies 失败: %s", e)
            return False

    # -------- 内部 --------

    def _navigate_to_login(self):
        """跳转登录页。"""
        logger.info("跳转至登录页: %s", LOGIN_URL)
        self.page.get(LOGIN_URL)

    def _wait_manual_login(self):
        """等待用户手动完成登录。"""
        input("请手动登录，登录完成后按 Enter 键继续...")
        logger.info("用户确认登录完成")
