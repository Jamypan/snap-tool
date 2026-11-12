@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem 一键重启：结束后台残留实例后重新启动，适合「提示已在运行却看不到界面」时使用。
rem 与 run-silent.bat 一样优先用 PATH 中已装 PySide6 的 pythonw，否则回退开发机环境。

where pythonw >nul 2>nul
if errorlevel 1 goto :fallback
python -c "import PySide6" >nul 2>nul
if errorlevel 1 goto :fallback
start "" pythonw "%~dp0snap.py" --restart
exit /b 0

:fallback
set "PYW=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\pythonw.exe"
if not exist "%PYW%" goto :nopyw
start "" "%PYW%" "%~dp0snap.py" --restart
exit /b 0

:nopyw
echo [错误] 未找到可用的 Python：请安装 Python 3.10+ 并加入 PATH，执行 pip install PySide6 Pillow numpy，或修改本脚本里的 PYW 路径。
pause
