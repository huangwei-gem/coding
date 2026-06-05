"""可视化报表模块 - 可选依赖 matplotlib"""
from pathlib import Path

from loguru import logger

from config import OUTPUT_REPORTS


class Visualizer:
    """统计可视化器"""

    def __init__(self):
        self._matplotlib_available = False
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei",
                                                  "WenQuanYi Micro Hei", "Arial Unicode MS"]
            plt.rcParams["axes.unicode_minus"] = False
            self._matplotlib_available = True
            self.plt = plt
            logger.info("[可视化] matplotlib 可用")
        except ImportError:
            logger.warning("[可视化] matplotlib 未安装，跳过图表生成")

    def can_render(self) -> bool:
        return self._matplotlib_available

    def plot_intention_pie(self, statistics: dict) -> str:
        """生成意愿分布饼图"""
        if not self._matplotlib_available:
            return ""
        labels = ["同意", "不同意", "待确认"]
        sizes = [statistics.get("agree", 0),
                 statistics.get("disagree", 0),
                 statistics.get("pending", 0)]
        colors = ["#52C41A", "#FF4D4F", "#FAAD14"]

        # 全零数据时显示占位信息
        if sum(sizes) == 0:
            fig, ax = self.plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "暂无数据", ha="center", va="center",
                    fontsize=20, color="gray")
            ax.set_title("业主意愿分布", fontsize=16, fontweight="bold")
            ax.axis("off")
        else:
            fig, ax = self.plt.subplots(figsize=(8, 6))
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct="%1.1f%%",
                colors=colors, startangle=90, textprops={"fontsize": 14},
            )
            ax.set_title("业主意愿分布", fontsize=16, fontweight="bold")

        output_path = OUTPUT_REPORTS / "意愿分布饼图.png"
        self.plt.savefig(output_path, dpi=150, bbox_inches="tight")
        self.plt.close()
        logger.info(f"[可视化] 饼图已生成: {output_path}")
        return str(output_path)

    def plot_progress_bar(self, statistics: dict) -> str:
        """生成同意率进度条"""
        if not self._matplotlib_available:
            return ""
        rate = statistics.get("agree_rate", 0)
        fig, ax = self.plt.subplots(figsize=(10, 2))
        ax.barh([0], [min(rate, 100)], color="#52C41A" if rate >= 80 else "#4A90D9",
                height=0.6)
        ax.barh([0], [100], color="#E8E8E8", height=0.6, alpha=0.3)
        ax.set_xlim(0, 100)
        ax.set_yticks([])
        ax.set_title(f"同意率: {rate:.1f}%  {'✅ 已达法定要求 (≥80%)' if rate >= 80 else '❌ 未达法定要求'}",
                     fontsize=14, fontweight="bold", pad=20)
        ax.axvline(x=80, color="red", linestyle="--", linewidth=2, label="法定线 (80%)")
        ax.legend(fontsize=12)

        output_path = OUTPUT_REPORTS / "同意率进度条.png"
        self.plt.savefig(output_path, dpi=150, bbox_inches="tight")
        self.plt.close()
        return str(output_path)
