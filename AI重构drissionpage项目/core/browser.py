"""浏览器管理模块 - 封装 DrissionPage 浏览器实例与 Cookie 持久化"""
import json
import time
from datetime import datetime
from pathlib import Path
from DrissionPage import ChromiumPage

import config


def _log(msg: str):
    dt = datetime.now().strftime("%m-%d %H:%M:%S")
    line = f"[{dt}] {msg}"
    print(line)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


class BrowserManager:
    """浏览器管理器，提供 Cookie 持久化功能"""

    def __init__(self):
        self.page: ChromiumPage | None = None
        self._cookie_file: Path = config.COOKIE_FILE
        self.is_logged_in = False
        self.city_dict: dict[str, str] = {}

    @staticmethod
    def log(msg: str):
        _log(msg)

    def start(self) -> ChromiumPage:
        """启动浏览器，严格按源文件流程"""
        config.COOKIE_DIR.mkdir(parents=True, exist_ok=True)

        # 1. 实例化浏览器，访问网址 (原文件 4-7行)
        self.log("正在启动 Chromium 浏览器...")
        try:
            self.page = ChromiumPage()
        except Exception as e:
            self.log(f"创建浏览器实例失败: {e}")
            self.log("可能原因: Chrome 未安装、端口被占用、或上次浏览器未正常关闭")
            raise
        self.log("浏览器启动成功，正在访问 BOSS 直聘...")
        self.page.get(config.BASE_URL)
        time.sleep(1)

        # 2. 立即监听城市数据包 (原文件 10-11行)
        self.page.listen.start("data/city.json")

        # 3. 尝试用 cookie 恢复登录
        saved = self._load_cookies()
        if saved:
            self.page.set.cookies(saved)
            self.page.refresh()
            time.sleep(2)

        # 4. 检查登录状态 (原文件 13-16行)
        self.check_login_status()
        if self.is_logged_in:
            print("不需要登录")
            # 已自动登录 → 立即刷新获取城市数据
            self._fetch_cities()
        return self.page

    def check_login_status(self) -> bool:
        """检查当前是否已登录 — 对应原文件 .user-nav 文本检查"""
        try:
            nav_text = self.page.ele(".user-nav").text
            self.is_logged_in = "登录/注册" not in nav_text
        except Exception:
            self.is_logged_in = False
        return self.is_logged_in

    def confirm_login_and_fetch_cities(self) -> bool:
        """用户确认登录后：保存cookie → 刷新 → 获取城市数据（原文件 22-56行流程）"""
        if not self.check_login_status():
            return False

        # 保存 cookie (原文件 24-27行)
        self._save_cookies()
        print("登录状态已保存")

        # 刷新页面，获取城市数据 (原文件 42-56行)
        self._fetch_cities()
        return True

    def _fetch_cities(self):
        """刷新并获取城市数据 — 对应原文件 refresh → listen.steps 流程"""
        self.page.refresh()
        self.page.wait(2)

        self.city_dict = {}
        for packet in self.page.listen.steps():
            res = packet.response.body
            # 原文件直接 dict 访问 (不是 .get())
            city_list = res["zpData"]["hotCityList"]
            for city in city_list:
                self.city_dict[city["name"]] = city["code"]
                print(city["name"], city["code"])
            break

        print(f"已获取 {len(self.city_dict)} 个热门城市")

    def _save_cookies(self):
        """保存 cookie 到文件"""
        cookies = self.page.cookies()
        with open(self._cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f"Cookie 已保存到: {self._cookie_file}")

    def _load_cookies(self) -> list[dict] | None:
        """从文件加载 cookie"""
        if not self._cookie_file.exists():
            return None
        try:
            with open(self._cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            print(f"已加载 {len(cookies)} 条 Cookie")
            return cookies
        except (json.JSONDecodeError, IOError) as e:
            print(f"Cookie 文件读取失败: {e}")
            return None

    def logout(self):
        """清除 cookie 并退出登录"""
        self.page.set.cookies([])
        self._cookie_file.unlink(missing_ok=True)
        self.is_logged_in = False
        self.page.refresh()

    def get_cookie_info(self) -> dict:
        """获取 cookie 信息（用于 UI 展示，含异常保护）"""
        cookies = []
        if self.page:
            try:
                cookies = self.page.cookies()
            except Exception:
                cookies = []
        cookie_names = [c.get("name") for c in cookies if c.get("name")]
        has_session = any("session" in n.lower() for n in cookie_names)
        return {
            "is_logged_in": self.is_logged_in,
            "cookie_count": len(cookies),
            "has_session": has_session,
            "cookie_file_exists": self._cookie_file.exists(),
        }

    def quit(self):
        """关闭浏览器"""
        if self.page:
            try:
                self.page.quit()
            except Exception:
                pass
