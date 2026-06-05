"""证据管理模块 - 证据固化、文件归档、统计报表"""
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from config import OUTPUT_EVIDENCE, OUTPUT_REPORTS


class EvidenceManager:
    """证据管理器"""

    def __init__(self, db=None):
        self.db = db
        # 按文件夹规范组织
        self.evidence_root = OUTPUT_EVIDENCE
        self.evidence_root.mkdir(parents=True, exist_ok=True)

    def save_screenshot_placeholder(self, owner_name: str, phone: str,
                                     reply_content: str, received_at: datetime) -> str:
        """保存截图占位文件（实际截图需用浏览器自动化工具如 Selenium）

        生产环境可集成截图工具，这里先生成含证据信息的文本存档。
        """
        timestamp = received_at.strftime("%Y%m%d_%H%M%S")
        filename = f"{owner_name}_{phone[-4:]}_{timestamp}.txt"
        filepath = self.evidence_root / filename

        content = (
            f"证据存档\n"
            f"{'='*40}\n"
            f"业主: {owner_name}\n"
            f"手机号: {phone}\n"
            f"回复时间: {received_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"回复内容: {reply_content}\n"
            f"{'='*40}\n"
            f"此文件为证据占位文件，正式使用请替换为短信截图\n"
        )
        filepath.write_text(content, encoding="utf-8")
        logger.debug(f"[证据管理] 证据文件已生成: {filepath}")
        return str(filepath)

    def archive_evidence(self, reply: dict, screenshot_path: str = None) -> int:
        """存档一条证据"""
        owner = None
        owner_id = reply.get("owner_id")

        if not owner_id and self.db:
            owner = self.db.get_owner_by_phone(reply.get("phone", ""))
            owner_id = owner["id"] if owner else None

        # 生成截图
        owner_name = owner.get("name", "未知") if owner else "未知"
        if not screenshot_path:
            screenshot_path = self.save_screenshot_placeholder(
                owner_name=owner_name,
                phone=reply.get("phone", ""),
                reply_content=reply.get("content", ""),
                received_at=reply.get("received_at", datetime.now()),
            )

        # 记录到数据库
        if self.db:
            ev_id = self.db.insert_evidence(
                owner_id=owner_id,
                reply_id=reply.get("id"),
                screenshot_path=screenshot_path,
                reply_content=reply.get("content", ""),
                received_at=reply.get("received_at", datetime.now()),
            )
            return ev_id
        return 0

    def archive_batch(self, replies: list[dict]):
        """批量存档证据"""
        for reply in replies:
            self.archive_evidence(reply)
        logger.info(f"[证据管理] 已存档 {len(replies)} 条证据")

    def generate_report(self, statistics: dict = None) -> str:
        """生成统计报表（HTML格式）"""
        from config import DB_CONFIG

        if not statistics and self.db:
            statistics = self.db.get_intention_statistics()

        if not statistics:
            statistics = {"total": 0, "agree": 0, "disagree": 0,
                          "pending": 0, "agree_rate": 0.0}

        report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>业主意愿统计报告</title>
    <style>
        body {{ font-family: 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
        h1 {{ color: #333; border-bottom: 2px solid #4A90D9; padding-bottom: 10px; }}
        .summary {{ display: flex; gap: 20px; margin: 30px 0; flex-wrap: wrap; }}
        .card {{ flex: 1; min-width: 140px; padding: 20px; border-radius: 8px; color: white; text-align: center; }}
        .card.total {{ background: #4A90D9; }}
        .card.agree {{ background: #52C41A; }}
        .card.disagree {{ background: #FF4D4F; }}
        .card.pending {{ background: #FAAD14; }}
        .card .number {{ font-size: 36px; font-weight: bold; }}
        .card .label {{ font-size: 14px; opacity: 0.9; margin-top: 5px; }}
        .rate-box {{ background: #F5F5F5; border-radius: 8px; padding: 30px; text-align: center; margin: 20px 0; }}
        .rate-box .rate {{ font-size: 48px; color: #4A90D9; font-weight: bold; }}
        .footer {{ color: #999; font-size: 12px; margin-top: 40px; text-align: center; }}
    </style>
</head>
<body>
    <h1>业主意愿统计报告</h1>
    <p>报告生成时间：{report_time}</p>
    <p>数据库：{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}</p>

    <div class="summary">
        <div class="card total">
            <div class="number">{statistics['total']}</div>
            <div class="label">总回复数</div>
        </div>
        <div class="card agree">
            <div class="number">{statistics['agree']}</div>
            <div class="label">同意</div>
        </div>
        <div class="card disagree">
            <div class="number">{statistics['disagree']}</div>
            <div class="label">不同意</div>
        </div>
        <div class="card pending">
            <div class="number">{statistics['pending']}</div>
            <div class="label">待确认</div>
        </div>
    </div>

    <div class="rate-box">
        <div>同意率</div>
        <div class="rate">{statistics['agree_rate']}%</div>
        <div>（超过80%即可满足法定条件）</div>
    </div>

    <div class="footer">
        <p>本报告由 发票收集自动化系统 自动生成</p>
        <p>证据文件已存档至: {self.evidence_root}</p>
    </div>
</body>
</html>"""

        output_path = OUTPUT_REPORTS / "业主意愿统计报告.html"
        output_path.write_text(html, encoding="utf-8")
        logger.info(f"[证据管理] 统计报告已生成: {output_path}")
        return str(output_path)

    def generate_summary_json(self, statistics: dict = None) -> str:
        """生成汇总 JSON，方便其他程序消费"""
        if not statistics and self.db:
            statistics = self.db.get_intention_statistics()
        if not statistics:
            statistics = {"total": 0, "agree": 0, "disagree": 0,
                          "pending": 0, "agree_rate": 0.0}

        summary = {
            "生成时间": datetime.now().isoformat(),
            "统计": statistics,
            "法定条件达标": statistics.get("agree_rate", 0) >= 80,
            "证据目录": str(self.evidence_root),
        }
        output_path = OUTPUT_REPORTS / "汇总数据.json"
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        return str(output_path)
