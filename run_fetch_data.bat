@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul && (py -3 fetch_btc_data.py %*) || (python fetch_btc_data.py %*)
echo.
pause
