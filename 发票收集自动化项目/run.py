#!/usr/bin/env python3
"""发票收集自动化系统 - 主入口

全流程：数据清洗 → 短信分发 → 回复采集 → 风控过滤 → AI分析 → 证据存档

用法:
    python run.py                  # 全自动运行（demo模式）
    python run.py --mode demo      # demo模式
    python run.py --mode production  # 生产模式

分步执行:
    python run.py --step clean     # 只做数据清洗
    python run.py --step send      # 只发短信
    python run.py --step collect   # 只采集回复
    python run.py --step analyze   # 只分析意愿
    python run.py --step report    # 只生成报告
"""
import sys
import time
import argparse
from pathlib import Path

# 解决 Windows 终端中文乱码
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 确保项目根目录在 path 中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

# 配置 loguru
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | {message}",
           level="DEBUG")
logger.add(PROJECT_ROOT / "logs" / "系统运行日志_{time:YYYY-MM-DD}.log",
           rotation="10 MB", retention="7 days", level="INFO")


def step_clean(db):
    """阶段1：数据清洗"""
    from src.data_cleaner import DataCleaner

    logger.info("=" * 50)
    logger.info("阶段1/5：Excel 数据清洗")
    logger.info("=" * 50)

    cleaner = DataCleaner()
    output_path = cleaner.clean()
    owners = cleaner.get_cleaned_data()

    # 同步到数据库
    if db:
        db.batch_insert_owners(owners)

    logger.info(f"[完成] 清洗后共 {len(owners)} 条有效业主数据")
    return owners


def step_send(owners, db):
    """阶段2：短信分发"""
    from src.sms_service import SmsSender

    logger.info("=" * 50)
    logger.info("阶段2/5：批量发送通知短信")
    logger.info("=" * 50)

    sender = SmsSender()
    results = sender.send_batch(owners)

    # 记录发送结果到数据库
    if db:
        for r in results:
            db.insert_sms_record(
                owner_id=r["owner"].get("id", 0),
                phone=r["owner"].get("phone", ""),
                content=r.get("content", ""),
                status="sent" if r["success"] else "failed",
                msg_id=r.get("msg_id", ""),
            )

    logger.info(f"[完成] 发送完成: 成功 {sender.success_count}, 失败 {sender.fail_count}")
    return results


def step_collect(db):
    """阶段3+4+6：回复采集、风控过滤、证据存档（一体化循环）"""
    logger.info("=" * 50)
    logger.info("阶段3/5：启动回复采集（每10分钟拉取一次）")
    logger.info("=" * 50)

    from src.reply_collector import ReplyCollector
    from src.content_filter import ContentFilter
    from src.intention_analyzer import IntentionAnalyzer
    from src.evidence_manager import EvidenceManager

    collector = ReplyCollector(db)
    content_filter = ContentFilter(db)
    analyzer = IntentionAnalyzer(db)
    evidence_mgr = EvidenceManager(db)

    collected_replies = []

    def on_new_reply(reply):
        """每收到一条新回复的处理流程"""
        nonlocal collected_replies
        collected_replies.append(reply)

        # 阶段4：风控过滤
        filter_result = content_filter.filter_reply(
            text=reply["content"],
            reply_id=reply.get("id"),
        )

        if filter_result["action"] == "block":
            logger.warning(f"[风控] 回复 #{reply['id']} 被拦截")
            return

        if filter_result["action"] == "soothe":
            logger.info(f"[风控] 回复 #{reply['id']} 情绪化，已发送安抚话术")
            # 情绪化但仍进行意愿分析

        # 阶段5：意愿分析
        owner = db.get_owner_by_phone(reply["phone"])
        owner_id = owner["id"] if owner else None
        analysis = analyzer.analyze_reply(
            text=reply["content"],
            reply_id=reply.get("id"),
            owner_id=owner_id,
        )
        logger.info(f"[意愿] 回复 #{reply['id']}: intention={analysis['intention']}, "
                    f"method={analysis['method']}")

        # 阶段6：证据存档
        evidence_mgr.archive_evidence(reply)

        # 实时输出统计
        stats = db.get_intention_statistics()
        logger.info(f"[统计] 当前: 总{stats['total']} 同意{stats['agree']} "
                    f"不同意{stats['disagree']} 待确认{stats['pending']} "
                    f"同意率{stats['agree_rate']}%")

    # 配置回调
    collector.progress_callback = on_new_reply

    # 在 demo 模式下，拉取 3 轮（每轮间隔模拟 10 分钟 = 实际 5 秒）
    from config import RUN_MODE
    if RUN_MODE == "demo":
        logger.info("[采集] demo 模式: 模拟拉取 3 轮回复")
        for round_num in range(3):
            logger.info(f"[采集] 第 {round_num+1} 轮拉取...")
            new_replies = collector.poll()
            for reply in new_replies:
                on_new_reply(reply)
            if round_num < 2:
                time.sleep(2)  # 模拟间隔
    else:
        collector.start_polling_loop(interval_minutes=10)

    return collected_replies


def step_analyze(db):
    """阶段5：集中意愿分析（处理所有未分析回复）"""
    from src.intention_analyzer import IntentionAnalyzer

    logger.info("=" * 50)
    logger.info("阶段5/5：AI 意愿分析 + 人工复核导出")
    logger.info("=" * 50)

    analyzer = IntentionAnalyzer(db)

    # 获取未处理的回复
    unprocessed = db.get_unprocessed_replies()
    logger.info(f"[意愿分析] 待处理回复: {len(unprocessed)} 条")

    if not unprocessed:
        logger.info("[意愿分析] 没有待处理的回复")
    else:
        results = analyzer.analyze_batch(unprocessed)
        logger.info(f"[意愿分析] 已分析: {len(results)} 条")

    # 导出人工复核列表
    manual_list = analyzer.export_manual_check()
    if manual_list:
        logger.warning(f"[意愿分析] ⚠️ 共 {len(manual_list)} 条需要人工复核，"
                       f"请检查 需人工复核列表.csv")
        logger.info(f"[意愿分析] 要求: 人工复核准确率 ≥ 95% 后方可生效")

    # 统计结果
    stats = db.get_intention_statistics()
    logger.info(f"[统计] 最终结果:")
    logger.info(f"       总回复: {stats['total']}")
    logger.info(f"       同意:   {stats['agree']}")
    logger.info(f"       不同意: {stats['disagree']}")
    logger.info(f"       待确认: {stats['pending']}")
    logger.info(f"       同意率: {stats['agree_rate']}%")
    if stats['agree_rate'] >= 80:
        logger.success(f"[统计] ✅ 同意率 ≥ 80%，满足法定条件！")
    else:
        logger.warning(f"[统计] ❌ 同意率未达80%，需继续收集")

    return stats


def step_report(db, stats=None):
    """生成报告"""
    from src.evidence_manager import EvidenceManager
    from src.visualizer import Visualizer

    logger.info("=" * 50)
    logger.info("生成统计报告与可视化")
    logger.info("=" * 50)

    evidence_mgr = EvidenceManager(db)
    viz = Visualizer()

    # HTML 报告
    report_path = evidence_mgr.generate_report(stats)
    json_path = evidence_mgr.generate_summary_json(stats)

    # 可视化图表
    if viz.can_render():
        pie_path = viz.plot_intention_pie(stats)
        bar_path = viz.plot_progress_bar(stats)

    logger.info(f"[报告] HTML 报告: {report_path}")
    logger.info(f"[报告] JSON 汇总: {json_path}")
    if viz.can_render():
        logger.info(f"[报告] 饼图: {pie_path}")
        logger.info(f"[报告] 进度条: {bar_path}")


def main():
    parser = argparse.ArgumentParser(description="发票收集自动化系统")
    parser.add_argument("--mode", choices=["demo", "production"],
                        default=None, help="运行模式（覆盖 .env 设置）")
    parser.add_argument("--step", choices=["all", "clean", "send", "collect",
                                            "analyze", "report"],
                        default="all", help="执行步骤")
    parser.add_argument("--input", type=str, default=None,
                        help="原始Excel文件路径")
    args = parser.parse_args()

    # 模式覆写
    if args.mode:
        import os
        os.environ["RUN_MODE"] = args.mode

    from config import RUN_MODE, INPUT_DIR
    logger.info(f"🔥 发票收集自动化系统 启动 (模式: {RUN_MODE})")
    logger.info(f"{'='*50}")

    # 数据库连接
    from src.database import Database
    db = Database()
    db.connect()

    try:
        # 分步执行
        if args.step in ("all", "clean"):
            owners = step_clean(db)
        else:
            owners = db.get_all_owners()

        if args.step in ("all", "send") and owners:
            step_send(owners, db)
        elif args.step == "send" and not owners:
            logger.warning("无业主数据，请先执行 clean 步骤")

        if args.step in ("all", "collect"):
            step_collect(db)

        if args.step in ("all", "analyze"):
            stats = step_analyze(db)
        else:
            stats = db.get_intention_statistics()

        if args.step in ("all", "report"):
            step_report(db, stats)

        logger.info(f"\n{'='*50}")
        logger.success("🎉 全流程执行完成！")
        logger.info("=" * 50)

    except KeyboardInterrupt:
        logger.info("\n[系统] 用户中断")
    except Exception as e:
        logger.exception(f"[系统] 运行异常: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
