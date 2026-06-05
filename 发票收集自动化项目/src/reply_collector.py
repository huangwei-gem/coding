"""回复采集模块 - 定时拉取短信回复 + 去重写入数据库"""
import random
import time
from datetime import datetime
from typing import Callable

from loguru import logger

from config import RUN_MODE


class ReplyCollector:
    """短信回复采集器"""

    def __init__(self, db, progress_callback: Callable = None):
        self.db = db
        self.progress_callback = progress_callback
        self.new_replies = []

    def _fetch_replies_demo(self) -> list[dict]:
        """demo 模式：模拟产生回复"""
        # 模拟一些随机回复
        demo_replies = [
            "同意",
            "不同意",
            "我同意，支持换届",
            "我不同意换届",
            "同意，希望小区越来越好",
            "不同意，现在挺好的",
            "同意支持！",
            "不同意的",
            "支持，同意换届",
            "我同意",
            "不同意！",
            "可以，同意",
            "不行，我不同意",
            "同意的",
            "我不同意这个事",
        ]
        # demo 模式：每次调用随机产生 2~5 条回复
        count = random.randint(2, 5)
        owners = self.db.get_all_owners()
        if not owners:
            return []

        replies = []
        for _ in range(count):
            owner = random.choice(owners)
            content = random.choice(demo_replies)
            replies.append({
                "phone": owner["phone"],
                "content": content,
                "received_at": datetime.now(),
            })
        return replies

    def _fetch_replies_production(self) -> list[dict]:
        """生产模式：通过短信API拉取回复

        实际使用时需对接具体短信服务商的回复拉取接口，
        这里实现通用框架。
        """
        provider = "aliyun"
        if provider == "aliyun":
            # 阿里云短信回执查询
            pass
        return []

    def poll(self) -> list[dict]:
        """执行一次拉取，返回新增回复"""
        if RUN_MODE == "demo":
            raw_replies = self._fetch_replies_demo()
        else:
            raw_replies = self._fetch_replies_production()

        self.new_replies = []
        for reply in raw_replies:
            # 去重检查
            if self.db.is_duplicate_reply(reply["phone"], reply["content"]):
                logger.debug(f"[回复采集] 去重跳过: {reply['phone']} - {reply['content'][:20]}")
                continue

            # 写入数据库
            reply_id = self.db.insert_reply(
                phone=reply["phone"],
                content=reply["content"],
                received_at=reply["received_at"],
                is_duplicate=False,
                raw_data={"source": "sms_api", "raw": reply},
            )
            reply["id"] = reply_id
            self.new_replies.append(reply)

            logger.info(f"[回复采集] 新回复 #{reply_id}: {reply['phone']} - {reply['content'][:30]}")

            if self.progress_callback:
                self.progress_callback(reply)

        if self.new_replies:
            logger.info(f"[回复采集] 本轮采集到 {len(self.new_replies)} 条新回复")
        else:
            logger.debug("[回复采集] 本轮无新回复")
        return self.new_replies

    def start_polling_loop(self, interval_minutes: int = 10, max_rounds: int = None):
        """启动定时采集循环

        Args:
            interval_minutes: 拉取间隔（分钟）
            max_rounds: 最大轮数，None=无限
        """
        from apscheduler.schedulers.background import BackgroundScheduler
        import atexit

        logger.info(f"[回复采集] 启动定时任务，每 {interval_minutes} 分钟拉取一次")

        scheduler = BackgroundScheduler()
        scheduler.add_job(
            func=self.poll,
            trigger="interval",
            minutes=interval_minutes,
            id="reply_polling",
            name="短信回复定时采集",
        )
        scheduler.start()

        atexit.register(lambda: scheduler.shutdown(wait=False))

        # 立即执行一次
        self.poll()

        # 等待（仅在 demo 模式下模拟几轮）
        if RUN_MODE == "demo" and max_rounds:
            try:
                for _ in range(max_rounds * interval_minutes):
                    time.sleep(60)
            except KeyboardInterrupt:
                logger.info("[回复采集] 用户中断")
        else:
            # 生产模式或无限模式，保持进程存活
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                logger.info("[回复采集] 用户中断")
