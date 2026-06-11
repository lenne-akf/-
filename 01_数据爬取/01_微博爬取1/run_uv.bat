@echo off
chcp 65001 >nul
title MediaCrawler run_uv
echo ========================================
echo MediaCrawler 环境脚本 (.venv_new)
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "PROJECT_ROOT=%%~fI"

set "UV_CACHE_DIR=D:\uv-cache"
set "UV_PYTHON_INSTALL_DIR=D:\uv-python"
set "PLAYWRIGHT_BROWSERS_PATH=D:\playwright-browsers"
set "UV_PROJECT_ENVIRONMENT=%PROJECT_ROOT%\MediaCrawler\.venv_new"

cd /d "%PROJECT_ROOT%\MediaCrawler"
if errorlevel 1 (
    echo [错误] 无法进入目录 MediaCrawler
    goto failed
)

where uv >nul 2>&1
if errorlevel 1 (
    echo [错误] 找不到 uv 命令。请先安装: pip install uv
    echo 然后关闭本窗口，重新打开 PowerShell 再试。
    goto failed
)

if "%~1"=="" goto help
if /i "%~1"=="sync" goto sync
if /i "%~1"=="playwright" goto playwright
if /i "%~1"=="login" goto login
if /i "%~1"=="creator" goto creator
if /i "%~1"=="search" goto search
if /i "%~1"=="detail" goto detail
echo [错误] 未知参数: %~1
goto help

:sync
echo 正在执行: uv sync ...
uv sync
goto check

:playwright
echo 正在执行: uv run playwright install chromium ...
echo 浏览器将安装到: %PLAYWRIGHT_BROWSERS_PATH%
uv run playwright install chromium
goto check

:login
echo 正在执行: 微博扫码登录 ...
uv run main.py --platform wb --lt qrcode --type search
goto check

:creator
uv run main.py --platform wb --lt qrcode --type creator
goto check

:search
uv run main.py --platform wb --type search
goto check

:detail
uv run main.py --platform wb --lt qrcode --type detail
goto check

:help
echo.
echo 用法:
echo   run_uv.bat sync
echo   run_uv.bat playwright
echo   run_uv.bat login
echo   run_uv.bat creator
echo   run_uv.bat search
echo   run_uv.bat detail
echo.
echo 若在 PowerShell 里运行，请用:
echo   cmd /c "%SCRIPT_DIR%run_uv.bat playwright"
goto end

:check
if errorlevel 1 (
    echo.
    echo [失败] 上一条命令出错，错误码: %errorlevel%
    goto failed
)
echo.
echo [完成] 命令执行成功。
goto end

:failed
echo.
echo 按任意键关闭此窗口...
pause >nul
exit /b 1

:end
echo.
exit /b 0
