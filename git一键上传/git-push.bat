@echo off
chcp 65001 >nul
title One-Click GitHub Upload

echo =================================
echo    One-Click GitHub Upload
echo =================================

pushd "%~dp0.."

echo.
echo [1/4] Checking repository status...
git status

echo.
echo [2/4] Staging all changes...
git add -A

echo.
echo [3/4] Committing changes...
set "msg=Update %date% %time%"
if not "%1"=="" set "msg=%*"
git commit -m "%msg%"

echo.
echo [4/4] Pushing to GitHub...
git push

echo.
echo =================================
echo    Done! Press any key to exit.
echo =================================

pause
popd
