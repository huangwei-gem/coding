---
name: agnes-image-2.0
description: 使用 Agnes AI 模型生成图片和视频。包含 agnes-image-2.0-flash（文生图/图生图）和 agnes-video-v2.0（文生视频/图生视频/关键帧动画）。当用户要求使用 Agnes 生图、生视频、AI 绘图、文生视频时使用。
---

# Agnes Image & Video 生成 Skill

通过 `https://apihub.agnes-ai.com` 调用 Agnes AI API 生成图片和视频。

## 使用前配置

1. **API Key** 已配置到环境变量（项目 settings 中已设置），直接使用即可。
2. **确保 Python 3 可用** — 脚本依赖 Python 3 标准库（无需额外安装）。
3. 查看完整 API 文档：`references/api.md`

---

# 图片生成 (Image 2.0)

模型：`agnes-image-2.0-flash`（也支持 `agnes-image-2.1-flash`）

## 文生图

```bash
python scripts/agnes_image.py --prompt "一只发光的浮空城市，悬浮于晨雾峡谷之上，电影级写实"
```

## 指定尺寸

```bash
python scripts/agnes_image.py --prompt "未来城市集市，飞行汽车，全息招牌，赛博朋克风格" --size 1152x864
```

## 指定模型版本

```bash
python scripts/agnes_image.py --prompt "..." --model agnes-image-2.1-flash
```

## 图生图（以图生图 / 图片编辑）

```bash
python scripts/agnes_image.py --prompt "把场景改成雨夜赛博朋克风格，保留构图" --image https://example.com/input.png
```

## 多张参考图

```bash
python scripts/agnes_image.py --prompt "融合两张图的风格" --image https://example.com/a.png --image https://example.com/b.png
```

## 跳过中文翻译

```bash
python scripts/agnes_image.py --prompt "An English prompt already" --no-translate
```

# 视频生成 (Video 2.0)

模型：`agnes-video-v2.0`

视频 API 是**异步**的：先用 `create` 创建任务，再用 `get` 查询结果。

## 文生视频（创建任务，手动查询）

```bash
# 创建任务
python scripts/agnes_video.py create --prompt "一只猫在日落时分的海滩上散步，电影感镜头，慢速摇镜"

# 查询结果（用上面返回的 task_id）
python scripts/agnes_video.py get task_xxxxxxxxx
```

## 文生视频（创建后自动轮询等待）

```bash
python scripts/agnes_video.py create --prompt "日落海滩上的猫，电影感镜头" --poll
```

## 图生视频

```bash
python scripts/agnes_video.py create --prompt "温柔飘浮动画，稳定居中构图" --image https://example.com/input.png --poll
```

## 多图视频

```bash
python scripts/agnes_video.py create --prompt "两张图之间的平滑过渡" --image https://example.com/a.png --image https://example.com/b.png --poll
```

## 关键帧动画

```bash
python scripts/agnes_video.py create --prompt "两张关键帧之间的电影级过渡" --image https://example.com/a.png --image https://example.com/b.png --mode keyframes --poll
```

## 自定义参数

```bash
python scripts/agnes_video.py create --prompt "..." \
  --width 1152 --height 768 \
  --num-frames 121 --frame-rate 24 \
  --seed 42 --negative-prompt "模糊，抖动" \
  --poll
```

# AI Infinite Canvas（可视化 Web UI）

提供了一个无限画布界面的 Web 应用，可以通过可视化方式操作图片和视频生成。

## 启动方式

```bash
cd ai-canvas
python app.py
```

然后访问 http://localhost:5000

## 功能

- **生成图片**：点击"生成图片"按钮，填写 prompt 和参数，结果以卡片形式出现在画布上
- **生成视频**：点击"生成视频"按钮，填写 prompt 和参数，自动轮询等待完成
- **无限画布**：鼠标拖拽平移，滚轮缩放
- **卡片拖动**：拖拽卡片标题区域可任意移动位置
- **图生图/图生视频**：在表单中填入参考图片 URL 即可
- **状态持久化**：画布状态自动保存到 localStorage

# 通用说明

- **中文提示词**：图片和视频脚本都会自动检测中文并翻译为英文后再调 API，以获得更稳定的生成效果。已是英文可加 `--no-translate` 跳过。
- **图片 Prompt 结构**：`[主体] + [场景/环境] + [风格] + [光照] + [构图] + [质量要求]`
- **视频 Prompt 结构**：`[主体] + [动作] + [场景] + [镜头运动] + [光照] + [风格]`
- **视频推荐参数**：`width=1152`, `height=768`, `num_frames=121`, `frame_rate=24`
- **帧数限制**：`num_frames` 必须满足 `8n+1` 且 `<= 441`（如 81、121、249）
- **输出**：JSON 格式，包含 `urls`（生成结果链接）、`prompt_used`、`status`、`raw`
- **有效期**：生成的图片/视频 URL 有时效性，请及时保存或下载
