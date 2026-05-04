@echo off
REM IM+云盘 启动脚本 (Windows)
echo. 
echo [IM+云盘]
echo 正在检查依赖...
pip install -r "%~dp0requirements.txt" -q 2>nul
echo 启动中... 请在浏览器打开 http://localhost:5000
cd /d "%~dp0"
python app.py --port 5000
pause
