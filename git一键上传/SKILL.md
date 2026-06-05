---
name: git-upload
description: 一键将 coding项目 的所有更改上传到 GitHub。当用户说"上传到GitHub"、"推送代码"、"一键上传"时使用。
---

# Git 一键上传 Skill

将 `coding项目` 目录下的所有更改一键提交并推送到 GitHub。

## 使用方法

在 Claude Code 中直接输入：
- "上传到 GitHub"
- "一键上传"
- "推送代码"

## 执行步骤

```bash
cd "C:/Users/35796/Documents/coding项目"
git add -A
git commit -m "更新 $(date +%Y-%m-%d\ %H:%M)"
git push
```

## 说明

- 自动添加所有更改（包括新增、修改、删除）
- 提交信息自动包含当前时间
- 凭证已存储在 Windows 凭据管理器中，无需手动输入密码
