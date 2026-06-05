"""意愿分析模块 - 规则快速判断 + AI语义分析 + 准确率抽查"""
import re
from typing import Optional

from loguru import logger

from config import AI_CONFIG, RUN_MODE, INTENTION_ACCURACY_THRESHOLD


class RuleEngine:
    """规则引擎 - 快速判断同意/不同意"""

    AGREE_PATTERNS = [
        re.compile(r"^\s*同意\s*[的了他吧！!\.]?\s*$"),
        re.compile(r"^同意[的了他]?$"),
        re.compile(r"我.*同意"),
        re.compile(r"支持.*换届"),
        re.compile(r"好的.*同意"),
        re.compile(r"可以.*同意"),
        re.compile(r"同意的"),
        re.compile(r"同意.*支持"),
        re.compile(r"赞成"),
        re.compile(r"好的.*[换换]"),
        re.compile(r"可以.*[换换]"),
        re.compile(r"没问题"),
    ]

    DISAGREE_PATTERNS = [
        re.compile(r"^\s*不同意\s*[的了他吧！!\.]?\s*$"),
        re.compile(r"^不同意[的了他]?$"),
        re.compile(r"我.*不同意"),
        re.compile(r"不同意的"),
        re.compile(r"不行"),
        re.compile(r"反对"),
        re.compile(r"不要换"),
        re.compile(r"不换"),
        re.compile(r"没必要"),
        re.compile(r"现在挺好"),
        re.compile(r"不需要"),
    ]

    def judge(self, text: str) -> Optional[int]:
        """规则判断意愿

        Returns:
            1 = 同意, 0 = 不同意, None = 规则无法判断
        """
        text = text.strip()

        # 先检查明确不同意（优先级更高）
        for pattern in self.DISAGREE_PATTERNS:
            if pattern.search(text):
                return 0

        # 再检查明确同意
        for pattern in self.AGREE_PATTERNS:
            if pattern.search(text):
                return 1

        return None


class AiAnalyzer:
    """AI 语义分析器"""

    def __init__(self):
        self.client = None
        self._init_client()

    def _init_client(self):
        if AI_CONFIG["api_key"]:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=AI_CONFIG["api_key"],
                    base_url=AI_CONFIG["api_base"],
                )
            except Exception as e:
                logger.warning(f"[AI分析] OpenAI 客户端初始化失败: {e}")
                self.client = None
        else:
            logger.info("[AI分析] 未配置 API_KEY，使用 demo 模式模拟 AI 响应")

    def analyze_sentiment(self, text: str) -> dict:
        """AI 情绪分析

        Returns:
            {"is_emotional": bool, "level": str, "suggestion": str}
        """
        if not self.client:
            return self._demo_sentiment(text)

        prompt = f"""分析以下业主短信回复的情绪状态，仅返回JSON：
{{
    "is_emotional": true/false,
    "level": "calm"|"mild_negative"|"strong_negative"|"excited",
    "suggestion": "直接处理"|"安抚话术+核心反问"
}}

回复内容：{text}"""
        try:
            resp = self.client.chat.completions.create(
                model=AI_CONFIG["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            import json
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.warning(f"[AI分析] 情绪分析异常: {e}")
            return self._demo_sentiment(text)

    def _demo_sentiment(self, text: str) -> dict:
        """demo 模式模拟情绪判断"""
        emotional_keywords = ["投诉", "举报", "烦", "闹心", "生气", "无语", "法院", "曝光"]
        if any(kw in text for kw in emotional_keywords):
            return {"is_emotional": True, "level": "mild_negative",
                    "suggestion": "安抚话术+核心反问"}
        return {"is_emotional": False, "level": "calm", "suggestion": "直接处理"}

    def analyze_intention(self, text: str) -> dict:
        """AI 分析模糊/长文本的意愿

        Returns:
            {"intention": 1/0/-1, "confidence": float, "reason": str}
        """
        if not self.client:
            return self._demo_intention(text)

        prompt = f"""你是一个业主意愿分析助手。分析以下回复内容，判断业主是否同意小区居委会换届。

回复内容：{text}

请以JSON格式返回：
{{
    "intention": 1（同意）或 0（不同意）或 -1（不确定）,
    "confidence": 0.0~1.0 置信度,
    "reason": "判断理由"
}}"""
        try:
            resp = self.client.chat.completions.create(
                model=AI_CONFIG["model"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            import json
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.warning(f"[AI分析] 意愿分析异常: {e}")
            return self._demo_intention(text)

    def _demo_intention(self, text: str) -> dict:
        """demo 模式模拟 AI 意愿分析"""
        text_lower = text.lower()
        if "同意" in text_lower and "不同意" not in text_lower:
            return {"intention": 1, "confidence": 0.85, "reason": "包含'同意'关键词"}
        elif "不同意" in text_lower:
            return {"intention": 0, "confidence": 0.90, "reason": "包含'不同意'关键词"}
        elif "支持" in text_lower:
            return {"intention": 1, "confidence": 0.80, "reason": "包含'支持'关键词"}
        elif "反对" in text_lower:
            return {"intention": 0, "confidence": 0.80, "reason": "包含'反对'关键词"}
        else:
            return {"intention": -1, "confidence": 0.30, "reason": "语义模糊，无法确定"}


class IntentionAnalyzer:
    """意愿分析整合器 - 规则 + AI + 人工抽查"""

    def __init__(self, db=None):
        self.db = db
        self.rule_engine = RuleEngine()
        self.ai_analyzer = AiAnalyzer()
        self.manual_check_list = []  # 需要人工复核的列表

    def analyze_reply(self, text: str, reply_id: int = None,
                      owner_id: int = None) -> dict:
        """对单条回复执行意愿分析

        流程：规则快速判断 → 判断不了的走AI → 置信度低的走人工复核

        Returns:
            {"intention": int, "method": str, "confidence": float, "needs_review": bool}
        """
        # 第一步：规则快速判断
        rule_result = self.rule_engine.judge(text)

        if rule_result is not None:
            result = {
                "intention": rule_result,
                "method": "rule",
                "confidence": 1.0,
                "needs_review": False,
            }
            logger.debug(f"[意愿分析] 规则判断: {text[:20]} -> {rule_result}")
        else:
            # 第二步：AI 分析长难句
            logger.info(f"[意愿分析] 规则无法判断，调用 AI: {text[:40]}")
            ai_result = self.ai_analyzer.analyze_intention(text)
            result = {
                "intention": ai_result["intention"],
                "method": "ai",
                "confidence": ai_result.get("confidence", 0.5),
                "needs_review": ai_result.get("confidence", 0) < INTENTION_ACCURACY_THRESHOLD,
            }
            logger.info(f"[意愿分析] AI 结果: intention={ai_result['intention']}, "
                        f"confidence={ai_result.get('confidence'):.2f}, "
                        f"reason={ai_result.get('reason', '')}")

        # 记录到数据库
        if self.db and reply_id and owner_id:
            self.db.insert_intention(
                owner_id=owner_id,
                reply_id=reply_id,
                intention=result["intention"],
                method=result["method"],
                confidence=result["confidence"],
                raw_reply=text,
            )

        # 需要人工复核的加入列表
        if result["needs_review"]:
            self.manual_check_list.append({
                "reply_id": reply_id,
                "owner_id": owner_id,
                "text": text,
                "ai_intention": result["intention"],
                "confidence": result["confidence"],
            })

        return result

    def analyze_batch(self, replies: list[dict]) -> list[dict]:
        """批量分析回复"""
        results = []
        for reply in replies:
            result = self.analyze_reply(
                text=reply["content"],
                reply_id=reply.get("id"),
                owner_id=reply.get("owner_id"),
            )
            results.append({**reply, **result})
        return results

    def export_manual_check(self, output_path: str = None) -> list[dict]:
        """导出需要人工复核的列表"""
        if not self.manual_check_list:
            import pandas as pd
            from config import OUTPUT_REPORTS

            # 从数据库读取置信度低的结果
            if self.db:
                unverified = self.db.get_unverified_intentions()
                for item in unverified:
                    self.manual_check_list.append({
                        "reply_id": item["reply_id"],
                        "owner_id": item["owner_id"],
                        "text": item.get("raw_reply", ""),
                        "ai_intention": item["intention"],
                        "confidence": float(item["confidence"]),
                    })

        if not self.manual_check_list:
            logger.info("[意愿分析] 无需人工复核")
            return []

        # 导出为 CSV
        import pandas as pd
        output_path = output_path or str(OUTPUT_REPORTS / "需人工复核列表.csv")
        df = pd.DataFrame(self.manual_check_list)

        # 人工复核列（留空）
        df["人工复核结果"] = ""
        df["备注"] = ""
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"[意愿分析] 导出 {len(self.manual_check_list)} 条需人工复核记录 -> {output_path}")
        return self.manual_check_list
