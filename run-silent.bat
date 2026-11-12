@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 日常用这个：无控制台窗口，托盘常驻
rem 优先使用 PATH 中「已装 PySide6」的 pythonw；否则回退开发机自带环境。

where pythonw >nul 2>nul
if errorlevel 1 goto :fallback
python -c "import PySide6" >nul 2>nul
if errorlevel 1 goto :fallback
start "" pythonw "%~dp0snap.py"
exit /b 0

:fallback
set "PYW=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
if not exist "%PYW%" goto :nopyw
start "" "%PYW%" "%~dp0snap.py"
exit /b 0

:nopyw
echo [错误] 未找到可用的 Python：请安装 Python 3.10+ 并加入 PATH，执行 pip install PySide6 Pillow numpy，或修改本脚本里的 PYW 路径。
pause
