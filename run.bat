@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 优先使用 PATH 中「已装 PySide6」的 Python（clone 后装好依赖即可直接运行）；
rem 没有可用依赖时回退到开发机自带的 Python 环境，保证原部署不受影响。
where python >nul 2>nul
if errorlevel 1 goto :fallback
python -c "import PySide6" >nul 2>nul
if errorlevel 1 goto :fallback
goto :run

:fallback
set "PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" goto :nopy
"%PY%" "%~dp0snap.py" || goto :failed
exit /b 0

:run
python "%~dp0snap.py" || goto :failed
exit /b 0

:nopy
echo [错误] 未找到可用的 Python：请安装 Python 3.10+ 并加入 PATH，执行 pip install PySide6 Pillow numpy，或修改本脚本里的 PY 路径。
pause
exit /b 1

:failed
echo.
echo [错误] 程序异常退出，请把上面的报错信息发给助手。
pause
exit /b 1
