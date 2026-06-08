#!/usr/bin/env bash
# ============================================
# One-Click GitHub Upload Script
# ============================================
# Usage: bash git-push.sh [commit-message]
# If no commit message is provided, it defaults
# to "Update YYYY-MM-DD HH:MM"
# ============================================

set -e

PROJECT_DIR="C:/Users/35796/Documents/coding项目"
cd "$PROJECT_DIR"

echo "================================="
echo "  One-Click GitHub Upload"
echo "================================="

# 1. Show current status
echo ""
echo "[1/4] Checking repository status..."
git status

# 2. Stage all changes
echo ""
echo "[2/4] Staging all changes..."
git add -A

# 3. Commit
echo ""
echo "[3/4] Committing changes..."
COMMIT_MSG="${1:-Update $(date +'%Y-%m-%d %H:%M')}"
git commit -m "$COMMIT_MSG"

# 4. Push
echo ""
echo "[4/4] Pushing to GitHub..."
git push

echo ""
echo "================================="
echo "  Done! Successfully uploaded."
echo "================================="
