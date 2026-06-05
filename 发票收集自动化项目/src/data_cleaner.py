"""Excel数据清洗模块 - 处理合并单元格、列不对齐，输出标准化CSV"""
from pathlib import Path

import pandas as pd
from loguru import logger

from config import INPUT_DIR, OUTPUT_CLEANED


class DataCleaner:
    """数据清洗器"""

    # 常见列名映射 → 标准化字段名
    COLUMN_MAP = {
        "业主": "name", "姓名": "name", "业主姓名": "name",
        "手机": "phone", "电话": "phone", "手机号": "phone", "联系电话": "phone",
        "手机号码": "phone", "联系方式": "phone",
        "楼栋": "building", "栋": "building", "楼": "building", "单元": "building",
        "楼层": "floor", "层": "floor",
        "房号": "room", "门牌": "room", "门牌号": "room", "房间": "room",
        "面积": "area", "户型": "house_type",
    }

    REQUIRED_FIELDS = ["name", "phone"]  # 必填字段

    def __init__(self, input_path: Path = None):
        self.input_path = input_path or (INPUT_DIR / "原始数据.xlsx")
        self.df: pd.DataFrame | None = None

    def load_excel(self) -> pd.DataFrame:
        """加载 Excel，自动处理合并单元格"""
        if not self.input_path.exists():
            logger.warning(f"[数据清洗] 未找到输入文件: {self.input_path}")
            logger.info("[数据清洗] 将使用内置示例数据演示")
            return self._create_demo_data()

        logger.info(f"[数据清洗] 加载文件: {self.input_path}")
        # 读取所有 sheet，合并
        xls = pd.ExcelFile(self.input_path)
        all_sheets = []
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name, header=None)
            # 向前填充合并单元格（合并单元格只有左上角有值）
            df = df.fillna(method="ffill", axis=0)
            all_sheets.append(df)

        self.df = pd.concat(all_sheets, ignore_index=True)
        logger.info(f"[数据清洗] 加载完成: {len(self.df)} 行 x {len(self.df.columns)} 列")
        return self.df

    def _create_demo_data(self) -> pd.DataFrame:
        """创建示例数据用于演示"""
        data = {
            "业主姓名": ["张三", "李四", "王五", "赵六", "孙七", "周八", "吴九", "郑十"],
            "手机号": [
                "13800001001", "13900001002", "13700001003",
                "13600001004", "13500001005", "13400001006",
                "13800001007", "13900001008",
            ],
            "楼栋": ["A栋"] * 8,
            "楼层": ["3层", "3层", "5层", "5层", "8层", "8层", "12层", "12层"],
            "房号": ["301", "302", "501", "502", "801", "802", "1201", "1202"],
        }
        self.df = pd.DataFrame(data)
        logger.info(f"[数据清洗] 使用示例数据: {len(self.df)} 条")
        return self.df

    def _normalize_columns(self) -> dict[str, str]:
        """将中文列名映射为标准化字段名"""
        if self.df is None:
            raise ValueError("请先调用 load_excel()")

        raw_cols = [str(c).strip() for c in self.df.columns]
        logger.debug(f"[数据清洗] 原始列名: {raw_cols}")

        col_map = {}
        for raw in raw_cols:
            mapped = self.COLUMN_MAP.get(raw)
            if mapped:
                col_map[raw] = mapped
            else:
                # 尝试模糊匹配
                for key, val in self.COLUMN_MAP.items():
                    if key in raw:
                        col_map[raw] = val
                        break

        if not col_map:
            logger.warning("[数据清洗] 未识别到任何列名映射，使用第1、2列作为name/phone")
            col_map[raw_cols[0]] = "name"
            if len(raw_cols) > 1:
                col_map[raw_cols[1]] = "phone"

        logger.info(f"[数据清洗] 列名映射: {col_map}")
        return col_map

    def clean(self, output_path: Path = None) -> Path:
        """执行清洗流程，返回输出文件路径"""
        self.load_excel()
        col_map = self._normalize_columns()

        # 重命名列
        self.df = self.df.rename(columns=col_map)

        # 只保留映射后的列
        keep_cols = list(col_map.values())
        self.df = self.df[keep_cols]

        # 清洗手机号：去除非数字字符
        if "phone" in self.df.columns:
            self.df["phone"] = (
                self.df["phone"]
                .astype(str)
                .str.replace(r"\D+", "", regex=True)
                .str.strip()
            )

        # 清洗姓名字段
        if "name" in self.df.columns:
            self.df["name"] = self.df["name"].astype(str).str.strip()

        # 填充缺失列
        for field in self.REQUIRED_FIELDS:
            if field not in self.df.columns:
                self.df[field] = ""

        # 删除空手机号的行
        before = len(self.df)
        self.df = self.df[self.df["phone"].str.len() >= 7]  # 至少7位
        removed = before - len(self.df)
        if removed:
            logger.warning(f"[数据清洗] 删除了 {removed} 条无效手机号记录")

        # 去重（按手机号）
        dup_before = len(self.df)
        self.df = self.df.drop_duplicates(subset=["phone"], keep="first")
        dup_removed = dup_before - len(self.df)
        if dup_removed:
            logger.warning(f"[数据清洗] 去重删除了 {dup_removed} 条重复手机号")

        # 标准化所有字段填充空值
        self.df = self.df.fillna("")

        # 保存
        output_path = output_path or (OUTPUT_CLEANED / "业主数据_清洗后.csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"[数据清洗] 清洗完成: {len(self.df)} 条 -> {output_path}")
        return output_path

    def get_cleaned_data(self) -> list[dict]:
        """获取清洗后的数据列表"""
        if self.df is None or self.df.empty:
            self.clean()
        return self.df.to_dict(orient="records") if self.df is not None else []
