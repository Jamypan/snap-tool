@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

if not exist "%PY%" (
    echo [错误] 未找到 Python 环境：%PY%
    echo 请修改本脚本中的 PY 路径。
    pause
    exit /b 1
)

"%PY%" "%~dp0snap.py"
if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出，请把上面的报错信息发给助手。
    pause
)
