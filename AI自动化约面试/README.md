# Boss直聘 — 数据分析岗位自动搜索 & 投递工具

基于 **DrissionPage** 开发的 Boss直聘自动化工具，支持岗位搜索、信息解析、自动沟通与简历看板投递。

## 目录结构

```
AI重构drissionpage项目/
├── main.py                         # 程序入口，编排整体流程
├── config/
│   ├── __init__.py
│   └── settings.py                 # 全局配置（URL、选择器、超时等）
├── core/
│   ├── __init__.py
│   ├── browser.py                  # 浏览器管理器（单例、防检测、优雅关闭）
│   └── exceptions.py               # 自定义异常体系
├── utils/
│   ├── __init__.py
│   ├── logger.py                   # 统一日志配置
│   └── helpers.py                  # 工具函数（重试、安全操作、数据解析）
├── business/
│   ├── __init__.py
│   ├── login.py                    # 登录检测 & 手动登录
│   ├── city.py                     # 城市数据获取
│   └── applicant.py                # 岗位搜索 & 自动投递
├── 数据分析看板/                    # 待上传的简历看板图片
│   ├── 看板1.png
│   ├── 看板2.png
│   └── 看板3.png
├── requirements.txt                # Python 依赖
└── README.md                       # 本文档
```

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 功能流程

1. **浏览器启动** — 自动配置防检测参数（自定义 UA、禁用自动化标志、无痕模式）
2. **登录检测** — 检测页面是否需要登录；若需要，自动跳转登录页并等待手动登录，登录后保存 cookies（`zhipin_cookies`）
3. **城市获取** — 监听网络请求获取热门城市列表，建立城市名→code 映射
4. **岗位搜索** — 按岗位 & 城市跳转搜索结果页
5. **滚动加载** — 多次滚动到底部触发懒加载
6. **岗位解析** — 提取岗位名、薪资、经验、学历、公司/地点、详情链接
7. **自动投递** — 访问每个岗位详情页 → 发送文字消息 → 关闭窗口 → 重新沟通 → 上传看板图片

## 配置说明

所有可配置项集中在 `config/settings.py`：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BASE_URL` | 目标网站 | `https://www.zhipin.com` |
| `DEFAULT_CITY` | 搜索城市 | `上海` |
| `DEFAULT_JOB` | 搜索岗位 | `数据分析` |
| `SCROLL_TIMES` | 滚动加载次数 | `5` |
| `SELECTORS` | 所有 CSS 选择器 | — |
| `BROWSER_CONFIG` | 浏览器启动参数 | 防检测配置 |
| `APPLY_MESSAGE` | 自动投递消息文本 | — |

修改 `BROWSER_CONFIG` 可切换无头模式（`headless: True`）。

## 与原代码的核心修改点

| 维度 | 原代码 (mian.py) | 重构后 |
|------|------------------|--------|
| **结构** | 单体脚本，~190行 | 5个模块11个文件，分层清晰 |
| **配置** | 硬编码散落各处 | 集中 `config/settings.py` |
| **浏览器管理** | 直接实例化 `ChromiumPage()` | `BrowserManager` 单例 + 防检测 + 优雅关闭 |
| **日志** | 只有 `print` | 统一 `logging`，时间/级别/模块一目了然 |
| **异常处理** | 少量 try/except | 自定义异常体系 + 重试机制 |
| **数据解析** | 内联处理 | `parse_job_info()` 独立工具函数 |
| **可扩展性** | 难以新增功能 | 按业务分模块，新增功能不影响现有逻辑 |
| **选择器** | `.btn btn-startchat`（无效CSS） | `.btn.btn-startchat`（修复） |

## 注意事项

- 首次运行需要手动扫码/登录
- 程序默认仅处理第一个岗位（`break` 调试开关），移除后可批量处理
- 上传图片需确保 `数据分析看板/` 目录下有对应文件
- 浏览器禁用图片加载以提升速度，如需查看图片请修改 `BROWSER_CONFIG` 中的 `disable_imgs`

## 依赖

- Python >= 3.9
- [DrissionPage](https://github.com/g1879/DrissionPage) >= 4.1.0
