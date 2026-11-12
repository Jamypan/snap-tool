@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem 构建 Windows 绿色版：dist\SnapTool\SnapTool.exe
rem 优先用 PATH 中「装齐依赖」的 python；否则回退到开发机自带环境。

where python >nul 2>nul
if errorlevel 1 goto :fallback
python -c "import PySide6, PyInstaller, rapidocr, onnxruntime" >nul 2>nul
if errorlevel 1 goto :fallback
set "PY=python"
goto :build

:fallback
set "PY=C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" goto :deps
"%PY%" -c "import PySide6, PyInstaller, rapidocr, onnxruntime" >nul 2>nul
if errorlevel 1 goto :deps
goto :build

:build
echo [1/1] 正在打包，首次约需 1-3 分钟...
"%PY%" -m PyInstaller --noconfirm --clean SnapTool.spec || goto :failed
echo.
echo [完成] 产物：dist\SnapTool\SnapTool.exe
echo 分发：把整个 dist\SnapTool 目录压缩成 zip / 7z，不要只单独拷 exe。
echo 验证：dist\SnapTool\SnapTool.exe --selftest
echo       结果写入 %APPDATA%\SnapTool\selftest.log
echo.
pause
exit /b 0

:deps
echo [错误] 未找到装齐依赖的 python。请先执行：
echo    pip install PySide6 Pillow numpy opencv-python pyinstaller rapidocr onnxruntime
echo 或切换到已装好依赖的虚拟环境后重试。
pause
exit /b 1

:failed
echo.
echo [错误] 打包失败，请把上面的报错信息发给助手。
pause
exit /b 1
