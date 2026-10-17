@echo off
REM Starts the PSAL Badminton website on this PC. Keep this window open.
REM Options:  start_server.bat --port 8081   or   --data "D:\Team Data"
title PSAL Badminton website
cd /d "%~dp0"
if exist "dist\PSAL Badminton Server.exe" (
  "dist\PSAL Badminton Server.exe" %*
) else if exist "PSAL Badminton Server.exe" (
  "PSAL Badminton Server.exe" %*
) else (
  echo Starting from the Python files...
  python -m pip install -q -r requirements-web.txt
  python web_server.py %*
)
echo.
echo The website has stopped.
pause
