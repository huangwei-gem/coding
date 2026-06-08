# 发票收集自动化系统

> AI + 自动化助力业主维权短信取证系统  
> 用技术解决真实法律问题的全流程自动化工具

---

## START 项目亮点（面试版）

### Situation
小区居委会乱收费、不作为。业主需依法收集 **80% 以上业主书面同意**才能起诉换届。传统线下签字效率极低，500户需 2-3 周，且常因证据链不完整被法院驳回。

### Task
**10 天内**完成全小区业主意愿取证 —— 自动发短信、收回复、判意愿、出证据，避免人工操作被运营商风控拦截，确保每条回复附带时间戳形成有效法律证据。

### Action
用 Python 搭建 **6 阶段全自动流水线**：
1. **Excel 数据清洗** — 自动识别中文列名、填充合并单元格、清洗手机号、去重
2. **批量短信分发** — 填充业主姓名/房号到模板，对接阿里云 API，失败自动重试，限速防封
3. **回复定时采集** — APScheduler 每 10 分钟轮询，自动去重，实时回调处理
4. **双层风控过滤** — 违禁词精确拦截 + AI 情绪检测（关键词+LLM），触发后自动回复安抚话术
5. **意愿语义分析** — 20+ 正则规则引擎优先判断，模糊文本走 LLM（OpenAI 兼容），置信度 <95% 自动导出人工复核
6. **证据固化与报告** — 每条回复打时间戳存档，自动生成 HTML 报告 + 饼图 + 进度条 + JSON 汇总

**技术栈**：Python, pandas/openpyxl, 阿里云短信 API, OpenAI 兼容 LLM, MySQL, APScheduler, matplotlib, loguru

### Result
- **一键运行**全流程，Demo 模式零配置即可体验，生产模式对接真实 API
- **同意率实时统计**，达标即止；人工复核兜底保证 **准确率 ≥ 95%**
- 模块化设计，**6 阶段可独立执行**（`--step clean|send|collect|analyze|report`）
- 时间戳证据固化，满足法定证据链要求

## 系统架构图

```mermaid
flowchart TB
    subgraph Input["📥 数据输入层"]
        A1["原始 Excel<br/>(业主名单)"] --> A2["configs/<br/>违禁词库"]
    end

    subgraph Pipeline["⚙️ 核心处理管道"]
        direction TB
        B1["DataCleaner<br/>数据清洗<br/>(pandas + openpyxl)"] --> B2["SmsSender<br/>短信分发<br/>(批量 + 重试)"]
        B2 --> B3["ReplyCollector<br/>回复采集<br/>(定时轮询 + 去重)"]
        B3 --> B4["ContentFilter<br/>双层风控<br/>(违禁词 + AI 情绪)"]
        B4 --> B5["IntentionAnalyzer<br/>意愿分析<br/>(规则 + LLM + 人工)"]
        B5 --> B6["EvidenceManager<br/>证据管理<br/>(存档 + 报告)"]
    end

    subgraph External["🌐 外部服务"]
        C1["短信 API<br/>(阿里云等)"]
        C2["LLM API<br/>(OpenAI 兼容)"]
    end

    subgraph Storage["💾 数据存储层"]
        D1["MySQL<br/>(生产模式)"]
        D2["内存存储<br/>(Demo 模式)"]
        D3["文件系统<br/>(data/output/)"]
    end

    subgraph Output["📊 输出层"]
        E1["cleaned/<br/>标准化 CSV"]
        E2["evidence/<br/>时间戳证据"]
        E3["reports/<br/>HTML 统计报告"]
        E4["reports/<br/>可视化图表"]
        E5["reports/<br/>人工复核列表"]
    end

    subgraph Support["🛠 基础设施"]
        F1["config.py<br/>全局配置"]
        F2["loguru<br/>日志系统"]
        F3["APScheduler<br/>任务调度"]
    end

    B1 --> D1 & D2
    B2 <--> C1
    B3 --> D1 & D2
    B4 <--> C2
    B5 <--> C2
    B5 --> D1 & D2
    B6 --> D3
    D3 --> E1 & E2 & E3 & E4 & E5
    F1 -.-> Pipeline
    F2 -.-> Pipeline
    F3 -.-> B3
```

## 项目背景

为解决小区居委会乱收费、不作为问题，需收集**80%以上业主书面同意**的法定证据以起诉换届居委会。本系统通过 AI + 自动化替代人工发短信和统计，10天内高效完成业主意愿取证，规避人工繁琐、出错和风控问题。

## 核心流程

```
原始Excel → 数据清洗 → 批量短信 → 回复采集 → 风控过滤 → AI分析 → 证据存档
```

| 阶段 | 功能 | 技术实现 |
|------|------|----------|
| **1. 数据清洗** | 处理合并单元格、列不对齐，提取业主信息 | pandas + openpyxl |
| **2. 短信分发** | 批量发送定制短信（自动填充姓名、楼层） | 短信API（阿里云等） |
| **3. 回复采集** | 定时拉取短信回复，自动去重 | APScheduler + MySQL |
| **4. 风控过滤** | 违禁词拦截 + AI情绪判断 + 安抚话术 | 规则引擎 + AI API |
| **5. 意愿分析** | 规则快速判断 + AI分析长难句 + 人工复核 | NLP语义分析 |
| **6. 证据存档** | 时间戳证据固化 + 统计报告 + 可视化 | 文件系统 + 图表 |

## 项目结构

```
├── run.py                    # 主入口（支持分步执行）
├── config.py                 # 全局配置
├── requirements.txt          # 依赖清单
├── .env.example              # 配置模板
├── configs/
│   └── prohibited_words.txt  # 违禁词库（可自定义）
├── src/
│   ├── database.py           # 数据库模块（MySQL + demo内存模式）
│   ├── data_cleaner.py       # 数据清洗（Excel→标准化CSV）
│   ├── sms_service.py        # 短信发送（批量 + 重试）
│   ├── reply_collector.py    # 回复采集（定时轮询 + 去重）
│   ├── content_filter.py     # 双层风控（违禁词 + 情绪）
│   ├── intention_analyzer.py # 意愿分析（规则 + AI + 人工复核）
│   ├── evidence_manager.py   # 证据管理（存档 + 报告）
│   └── visualizer.py         # 可视化（饼图 + 进度条）
├── data/
│   ├── input/                # 放原始Excel（如 原始数据.xlsx）
│   └── output/
│       ├── cleaned/          # 清洗后的标准化CSV
│       ├── evidence/         # 按时间戳命名的证据文件
│       └── reports/          # 统计报告（HTML + 图表 + JSON）
└── logs/                     # 运行日志
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行Demo（无需任何配置）

```bash
python run.py
```

Demo模式使用内存存储和模拟数据，不开通任何真实服务即可体验全流程。

### 3. 分步执行

```bash
python run.py --step clean     # 只清洗数据
python run.py --step send      # 只发短信
python run.py --step collect   # 只采集回复
python run.py --step analyze   # 只分析意愿
python run.py --step report    # 只生成报告
```

### 4. 生产模式

复制 `.env.example` 为 `.env`，填入真实配置后运行：

```bash
python run.py --mode production
```

## 配置说明

### `.env` 核心配置项

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `DB_HOST` | MySQL主机 | `127.0.0.1` |
| `DB_USER` | 数据库用户名 | `root` |
| `DB_PASSWORD` | 数据库密码 | `your_password` |
| `DB_NAME` | 数据库名 | `invoice_project` |
| `SMS_PROVIDER` | 短信服务商 | `aliyun` |
| `SMS_ACCESS_KEY_ID` | 短信API密钥 | `LTAI...` |
| `SMS_ACCESS_KEY_SECRET` | 短信API密钥 |  |
| `SMS_SIGN_NAME` | 短信签名 | `XX小区业主委员会` |
| `SMS_TEMPLATE_CODE` | 短信模板ID | `SMS_123456789` |
| `AI_API_KEY` | AI API密钥 | `sk-...` |
| `AI_API_BASE` | AI API地址 | `https://api.openai.com/v1` |
| `AI_MODEL` | AI模型 | `gpt-4o-mini` |
| `RUN_MODE` | 运行模式 | `demo` 或 `production` |

### 违禁词库

编辑 `configs/prohibited_words.txt`，每行一个词，支持 `#` 注释。命中这些词的回复将被拦截，不进入 AI 分析。

## 输出说明

运行完成后，在 `data/output/` 目录下可以找到：

- `cleaned/业主数据_清洗后.csv` — 清洗后的标准化数据
- `evidence/` — 每条回复的时间戳证据文件
- `reports/业主意愿统计报告.html` — 可视化统计报告
- `reports/意愿分布饼图.png` — 意愿占比饼图
- `reports/同意率进度条.png` — 同意率进度条
- `reports/汇总数据.json` — 结构化汇总数据

## 人工复核流程

对于 AI 置信度低于 95% 的模糊回复，系统自动导出到 `data/output/reports/需人工复核列表.csv`，复核流程：

1. 打开 CSV，逐条确认业主真实意愿
2. 在"人工复核结果"列填写 `1`（同意）或 `0`（不同意）
3. 确认整体准确率 ≥ 95% 后，复核结果生效

## 技术栈

- **数据处理**: Python, pandas, openpyxl
- **接口服务**: 短信服务商 API (阿里云等)
- **数据库**: MySQL (生产模式) / 内存存储 (Demo模式)
- **AI能力**: 规则引擎 + LLM API (OpenAI兼容)
- **任务调度**: APScheduler
- **可视化**: matplotlib
- **日志**: loguru

## 运行日志

```
🔥 发票收集自动化系统 启动 (模式: demo)
阶段1/5：Excel 数据清洗
  清洗完成: 8 条 -> data/output/cleaned/业主数据_清洗后.csv
阶段2/5：批量发送通知短信
  发送完成: 成功 8, 失败 0
阶段3/5：启动回复采集
  新回复 #1: 13600001004 - 不行，我不同意
  意愿: intention=0, method=rule
  统计: 总12 同意6 不同意6 同意率50.0%
阶段5/5：AI 意愿分析 + 人工复核导出
  最终: 同意10 不同意8 待确认0 同意率55.56%
生成统计报告与可视化
  HTML报告: data/output/reports/业主意愿统计报告.html
🎉 全流程执行完成！
```
