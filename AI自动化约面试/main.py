#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Boss 直聘 — 数据分析岗位自动搜索 & 投递工具
========================================
基于 DrissionPage 实现，支持浏览器自动化操作：
  1. 检测/处理登录
  2. 获取热门城市
  3. 按岗位 & 城市搜索
  4. 解析岗位列表 & 提取链接
  5. 自动投递（文字 + 图片看板）

快速开始：
  pip install -r requirements.txt
  python main.py
"""
import sys

from config.settings import BASE_URL, CITY_API_PATTERN, DEFAULT_CITY, DEFAULT_JOB
from core.browser import BrowserManager
from core.exceptions import CityNotFound, ZhipinError
from utils.logger import logger


def main():
    """主流程编排。"""
    browser_mgr = BrowserManager()

    try:
        # ======== 1. 初始化浏览器 ========
        page = browser_mgr.init_page()

        # 提前监听城市数据包，避免 page.get() 时错过
        page.listen.start(CITY_API_PATTERN)

        page.get(BASE_URL)

        # ======== 2. 处理登录 ========
        from business.login import LoginHandler

        login_handler = LoginHandler(page)
        if not login_handler.login():
            logger.error("登录失败，终止程序")
            sys.exit(1)

        # ======== 3. 获取城市 & 搜索岗位 ========
        from business.city import CityFetcher

        city_fetcher = CityFetcher(page)
        city_dict = city_fetcher.fetch_hot_cities()
        logger.info("热门城市: %s", list(city_dict.keys()))

        try:
            city_code = city_fetcher.get_code(DEFAULT_CITY)
        except CityNotFound as e:
            logger.warning(e)
            sys.exit(1)

        from business.applicant import JobApplicant

        applicant = JobApplicant(page)
        applicant.search_jobs(DEFAULT_JOB, city_code)

        # ======== 4. 滚动加载 & 收集 ========
        applicant.load_more_jobs()
        job_urls = applicant.collect_job_urls()
        job_listings = applicant.parse_job_listings(job_urls)

        logger.info("共发现 %d 个岗位", len(job_listings))

        # ======== 5. 逐个投递 ========
        for idx, job in enumerate(job_listings, 1):
            url = job["url"]
            if not url:
                logger.warning("岗位 #%d 无链接，跳过", idx)
                continue

            logger.info("--- 正在处理岗位 #%d/%d: %s ---", idx, len(job_listings), job.get("job_name", url))
            try:
                success = applicant.apply_for_job(url, send_images=True)
                if success:
                    logger.info("岗位 #%d 处理完成", idx)
            except Exception as e:
                logger.error("岗位 #%d 处理异常: %s", idx, e)

            import random
            delay = random.uniform(3, 8)
            logger.debug("等待 %.1f 秒后处理下一个", delay)
            self.page.wait(delay)

    except ZhipinError as e:
        logger.error("程序异常终止: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        browser_mgr.quit_page()
        logger.info("程序结束")


if __name__ == "__main__":
    main()
