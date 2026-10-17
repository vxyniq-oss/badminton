@echo off
REM Gives the website a free public https link using a Cloudflare quick tunnel,
REM so phones can open it from anywhere (not just your Wi-Fi).
REM Start the website first (start_server.bat). The link changes every time you run this;
REM for a permanent address, see "Permanent address" in WEB_SETUP.md.
title PSAL Badminton public link
set CF=cloudflared
where cloudflared >nul 2>nul || (
  if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" (set CF="%ProgramFiles(x86)%\cloudflared\cloudflared.exe") else (
  if exist "%ProgramFiles%\cloudflared\cloudflared.exe" (set CF="%ProgramFiles%\cloudflared\cloudflared.exe") else (
    echo Installing Cloudflare's tunnel tool ^(cloudflared^)...
    winget install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    if exist "%ProgramFiles(x86)%\cloudflared\cloudflared.exe" (set CF="%ProgramFiles(x86)%\cloudflared\cloudflared.exe") else (set CF="%ProgramFiles%\cloudflared\cloudflared.exe")
  ))
)
echo.
echo ===================================================================
echo  In a few seconds, look below for a line like:
echo     https://something-random.trycloudflare.com
echo  That's the link to send the team. Keep this window open.
echo ===================================================================
echo.
%CF% tunnel --url http://localhost:8080
pause
