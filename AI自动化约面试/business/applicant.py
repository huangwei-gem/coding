"""
岗位申请自动化模块
==========
搜索岗位、解析列表、自动沟通 & 发送简历看板。
"""
from DrissionPage import ChromiumPage

from config.settings import (
    BASE_URL,
    JOB_SEARCH_PATH,
    SELECTORS,
    CONTINUE_CHAT_TEXT,
    APPLY_MESSAGE,
    DASHBOARD_IMAGES,
    SCROLL_TIMES,
    SCROLL_WAIT,
    SCROLL_RETRY_WAIT,
)
from core.exceptions import ElementNotFound
from utils.helpers import (
    scroll_to_bottom_safe,
    safe_ele_text,
    parse_job_info,
)
from utils.logger import logger


class JobApplicant:
    """岗位搜索 + 自动投递管理器。"""

    def __init__(self, page: ChromiumPage):
        self.page = page

    # -------- 1. 搜索岗位 --------

    def search_jobs(self, job_name: str, city_code: str):
        """
        按岗位名 & 城市 code 跳转搜索结果页。

        Args:
            job_name:   岗位名称，如 "数据分析"
            city_code:  城市 code，如 "101020100"
        """
        url = f"{BASE_URL}{JOB_SEARCH_PATH}?query={job_name}&city={city_code}&industry=&position="
        logger.info("搜索岗位: %s | city_code=%s", job_name, city_code)
        self.page.get(url)

    # -------- 2. 加载更多岗位 --------

    def load_more_jobs(self, times: int = SCROLL_TIMES):
        """
        反复滚动到底部以触发懒加载。

        Args:
            times: 滚动次数
        """
        logger.info("开始滚动加载更多岗位 (共 %d 次)", times)
        for i in range(1, times + 1):
            scroll_to_bottom_safe(self.page, wait_sec=SCROLL_WAIT)
            logger.debug("第 %d/%d 次滚动完成", i, times)

    # -------- 3. 收集岗位链接 --------

    def collect_job_urls(self) -> list[str]:
        """
        从页面中提取所有岗位详情页链接。

        Returns:
            str 列表：岗位完整 URL
        """
        elements = self.page.eles(SELECTORS["job_name"])
        urls: list[str] = []
        for elem in elements:
            href = elem.attr("href")
            if href:
                urls.append(href)

        logger.info("提取到 %d 个岗位链接", len(urls))
        return urls

    # -------- 4. 解析岗位列表信息 --------

    def parse_job_listings(self, urls: list[str]) -> list[dict]:
        """
        从岗位列表区域解析文本信息，与 URL 一一对应组装。

        Args:
            urls: 岗位链接列表

        Returns:
            [{
                "job_name", "salary", "experience", "education",
                "company_location", "raw", "url"
            }, ...]
        """
        job_texts = self.page.ele(SELECTORS["rec_job_list"]).texts()
        results = []
        for i, text_block in enumerate(job_texts):
            url = urls[i] if i < len(urls) else ""
            info = parse_job_info(text_block, url)
            results.append(info)

        logger.info("解析了 %d 条岗位信息", len(results))
        return results

    # -------- 5. 自动投递 --------

    def apply_for_job(self, url: str, send_images: bool = True) -> bool:
        """
        对单个岗位执行完整投递流程。

        Args:
            url:         岗位详情页 URL
            send_images: 是否附带看板图片

        Returns:
            True  投递完成（或已沟通过跳过）
            False 投递失败
        """
        logger.info("访问岗位: %s", url)
        self.page.get(url)

        # -------- 5a. 检查是否已沟通 --------
        try:
            chat_btn = self.page.ele(SELECTORS["btn_startchat"], timeout=8)
            btn_text = chat_btn.text if chat_btn else ""
            if CONTINUE_CHAT_TEXT in btn_text:
                logger.info("已沟通过，跳过")
                return True
        except Exception:
            pass

        # -------- 5b. 提取岗位关键信息 --------
        self._log_job_details()

        # -------- 5c. 发送文字消息 --------
        if not self._send_text_message():
            return False

        # -------- 5d. 发送图片（可选） --------
        if send_images:
            self._send_images()

        return True

    # -------- 内部方法 --------

    def _log_job_details(self):
        """日志打印岗位详情。"""
        salary = safe_ele_text(self.page, SELECTORS["salary"])
        active_time = safe_ele_text(self.page, SELECTORS["boss_active_time"])
        company_scale = safe_ele_text(self.page, SELECTORS["icon_scale"])
        job_desc = safe_ele_text(self.page, SELECTORS["job_sec_text"])

        logger.info("薪资: %s", salary)
        logger.info("活跃度: %s", active_time)
        logger.info("公司规模: %s", company_scale)
        logger.info("岗位描述: %s", job_desc[:100] if job_desc else "无")

    def _send_text_message(self) -> bool:
        """
        点击「立即沟通」→ 输入文字 → 发送。

        Returns:
            bool 是否成功
        """
        try:
            btn = self.page.ele(SELECTORS["btn_startchat"], timeout=10)
            if not btn:
                raise ElementNotFound(SELECTORS["btn_startchat"], self.page.url)
            btn.click()
            self.page.wait(1)
        except Exception as e:
            logger.warning("点击「立即沟通」失败: %s", e)
            return False

        try:
            input_el = self.page.ele(SELECTORS["input_area"], timeout=8)
            if input_el:
                input_el.input(APPLY_MESSAGE)
                logger.info("已输入投递消息")
            else:
                raise ElementNotFound(SELECTORS["input_area"])

            send_btn = self.page.ele(SELECTORS["send_message"], timeout=5)
            if send_btn:
                send_btn.click()
                logger.info("消息已发送")
            else:
                raise ElementNotFound(SELECTORS["send_message"])

            return True
        except Exception as e:
            logger.warning("发送文字消息失败: %s", e)
            return False

    def _send_images(self):
        """点击关闭 → 继续沟通 → 逐张上传看板图片。"""
        try:
            close_btn = self.page.ele(SELECTORS["icon_close"], timeout=5)
            if close_btn:
                close_btn.click()
                self.page.wait(1)
                logger.info("已关闭聊天窗口")
        except Exception as e:
            logger.debug("关闭聊天窗口失败（可能已关闭）: %s", e)

        try:
            chat_btn = self.page.ele(SELECTORS["btn_startchat"], timeout=8)
            if chat_btn:
                chat_btn.click()
                self.page.wait(1)
                logger.info("已重新点击「立即沟通」")
        except Exception as e:
            logger.warning("重新点击沟通按钮失败: %s", e)
            return

        for img_path in DASHBOARD_IMAGES:
            try:
                upload_btn = self.page.ele(SELECTORS["upload_btn"], timeout=8)
                if upload_btn:
                    upload_btn.click.to_upload(img_path)
                    self.page.wait(1)
                    logger.info("已上传: %s", img_path)
                else:
                    logger.warning("上传按钮未找到，跳过: %s", img_path)
            except Exception as e:
                logger.warning("上传图片失败 %s: %s", img_path, e)
