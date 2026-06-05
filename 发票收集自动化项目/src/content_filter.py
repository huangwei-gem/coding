"""双层风控过滤 - 违禁词筛查 + AI情绪判断"""
import re
from pathlib import Path
from typing import Optional

from loguru import logger

from config import PROHIBITED_WORDS_FILE


class ContentFilter:
    """内容过滤器"""

    def __init__(self, db=None):
        self.db = db
        self._prohibited_words: list[str] = []
        self._prohibited_patterns: list[re.Pattern] = []
        self._load_prohibited_words()

    def _load_prohibited_words(self):
        """加载违禁词库"""
        path = Path(PROHIBITED_WORDS_FILE)
        if not path.exists():
            logger.warning(f"[内容过滤] 违禁词库不存在: {path}")
            return

        words = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    words.append(line)
        self._prohibited_words = words
        self._prohibited_patterns = [re.compile(re.escape(w), re.IGNORECASE)
                                     for w in words]
        logger.info(f"[内容过滤] 已加载 {len(words)} 个违禁词")

    def check_prohibited_words(self, text: str) -> Optional[str]:
        """第一层过滤：检查是否包含违禁词

        Returns:
            命中词条 or None
        """
        for word, pattern in zip(self._prohibited_words, self._prohibited_patterns):
            if pattern.search(text):
                logger.debug(f"[内容过滤] 命中违禁词: {word}")
                return word
        return None

    def check_sentiment(self, text: str, ai_analyzer=None) -> dict:
        """第二层过滤：AI 情绪判断

        Returns:
            {"is_emotional": bool, "level": str, "suggestion": str}
        """
        # 先做关键词级情绪检测（快速通道）
        quick_result = self._quick_emotion_check(text)
        if quick_result["is_emotional"]:
            logger.debug(f"[内容过滤] 快速情绪检测触发: {quick_result['level']}")
            return quick_result

        # 如果没有 AI 分析器，返回快速检测结果
        if not ai_analyzer:
            return {"is_emotional": False, "level": "calm",
                    "suggestion": "直接处理"}

        # AI 情绪分析
        try:
            ai_result = ai_analyzer.analyze_sentiment(text)
            return ai_result
        except Exception as e:
            logger.warning(f"[内容过滤] AI 情绪分析异常: {e}，使用快速检测结果")
            return quick_result

    def _quick_emotion_check(self, text: str) -> dict:
        """关键词级快速情绪检测"""
        text_lower = text.lower()

        # 强烈负面情绪
        strong_negative = ["投诉", "举报", "法院见", "起诉", "曝光", "媒体", "记者"]
        for kw in strong_negative:
            if kw in text:
                return {
                    "is_emotional": True,
                    "level": "strong_negative",
                    "suggestion": "安抚话术+核心反问",
                }

        # 一般负面情绪
        mild_negative = ["烦", "吵", "闹心", "不满意", "生气", "无语"]
        for kw in mild_negative:
            if kw in text:
                return {
                    "is_emotional": True,
                    "level": "mild_negative",
                    "suggestion": "安抚话术+核心反问",
                }

        # 强烈标点（多个感叹号/问号）
        if re.search(r"[!！?？]{2,}", text):
            return {
                "is_emotional": True,
                "level": "excited",
                "suggestion": "安抚话术+核心反问",
            }

        return {"is_emotional": False, "level": "calm", "suggestion": "直接处理"}

    def get_soothing_reply(self, level: str) -> str:
        """根据情绪等级生成安抚话术"""
        soothing_messages = {
            "strong_negative": '您好，非常理解您的心情。关于居委会换届事宜，我们只是想了解一下您的真实意愿，'
                                '您的意见对我们非常重要。请问您是否同意进行换届？（回复"同意"或"不同意"即可）',
            "mild_negative": '您好，不好意思打扰您了。关于居委会换届的事情，我们只是想确认一下您的想法，'
                              '您的每一票都很重要。请问您同意还是不同意呢？（回复"同意"或"不同意"即可）',
            "excited": '您好，感谢您的关注。请消消气，我们就是想了解一下您对居委会换届的真实想法，'
                        '您的意见很重要。请回复"同意"或"不同意"即可，谢谢！',
        }
        return soothing_messages.get(level, '您好，请回复"同意"或"不同意"告知您的意愿，谢谢！')

    def filter_reply(self, text: str, reply_id: int = None,
                     ai_analyzer=None) -> dict:
        """对单条回复执行完整双层过滤

        Returns:
            {
                "passed": bool,
                "prohibited_word": str or None,
                "sentiment": dict,
                "action": str,  # block / soothe / pass
                "soothing_reply": str or None,
            }
        """
        result = {
            "passed": True,
            "prohibited_word": None,
            "sentiment": None,
            "action": "pass",
            "soothing_reply": None,
        }

        # 第一层：违禁词过滤
        hit_word = self.check_prohibited_words(text)
        if hit_word:
            result["passed"] = False
            result["prohibited_word"] = hit_word
            result["action"] = "block"
            logger.info(f"[内容过滤] 回复 #{reply_id} 因违禁词被拦截: {hit_word}")
            if self.db:
                self.db.insert_filter_log(
                    reply_id=reply_id,
                    filter_type="prohibited",
                    action_taken="block",
                    details=f"命中违禁词: {hit_word}",
                )
            return result

        # 第二层：情绪判断
        sentiment = self.check_sentiment(text, ai_analyzer)
        result["sentiment"] = sentiment
        if sentiment["is_emotional"]:
            result["soothing_reply"] = self.get_soothing_reply(sentiment["level"])
            result["action"] = "soothe"
            # 情绪化但仍可继续处理（不做 block，只记录）
            if self.db:
                self.db.insert_filter_log(
                    reply_id=reply_id,
                    filter_type="sentiment",
                    action_taken="soothe",
                    details=f"情绪等级: {sentiment['level']}, 发送安抚话术",
                )
            logger.info(f"[内容过滤] 回复 #{reply_id} 触发情绪过滤: {sentiment['level']}")

        return result
