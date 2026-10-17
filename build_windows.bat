@echo off
REM Builds everything into the dist folder and self-tests it:
REM   dist\PSAL Badminton.exe          (desktop app - team / players)
REM   dist\PSAL Badminton Manager.exe  (desktop app - managers & coaches)
REM   dist\PSAL Badminton Server.exe   (the website - run it on the PC that hosts it)
cd /d "%~dp0"
findstr /c:"nacl" keyauth_client.py >nul && (
  echo.
  echo These are the OLD files. Unzip the newest PSAL-Badminton zip and run build_windows.bat from that folder.
  pause
  exit /b 1
)
REM Remove any old build so an outdated .exe can't be left behind
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
del /q *.spec 2>nul
python -m pip install --upgrade pip
python -m pip install --upgrade -r requirements.txt -r requirements-web.txt pyinstaller
set COMMON=--noconfirm --clean --windowed --onefile --add-data "assets;assets" --collect-data customtkinter --hidden-import PIL._tkinter_finder

python -m PyInstaller %COMMON% --name "PSAL Badminton" --icon assets\icon.ico main.py
if errorlevel 1 goto failed
python -m PyInstaller %COMMON% --name "PSAL Badminton Manager" --icon assets\icon_manager.ico manager_main.py
if errorlevel 1 goto failed
python -m PyInstaller --noconfirm --clean --onefile --console --name "PSAL Badminton Server" --icon assets\icon.ico ^
  --add-data "web;web" --exclude-module customtkinter --exclude-module tkinter --exclude-module PIL web_server.py
if errorlevel 1 goto failed

echo Testing the finished apps...
start "" /wait "dist\PSAL Badminton.exe" --selftest
if errorlevel 1 goto failed
start "" /wait "dist\PSAL Badminton Manager.exe" --selftest
if errorlevel 1 goto failed
"dist\PSAL Badminton Server.exe" --selftest
if errorlevel 1 goto failed
echo.
echo Done! All self-tests passed. Your apps are in the dist folder:
echo   PSAL Badminton.exe          - desktop app for players and coaches
echo   PSAL Badminton Manager.exe  - desktop app for managers and coaches
echo   PSAL Badminton Server.exe   - the website (double-click start_server.bat to run it)
pause
exit /b 0

:failed
echo.
echo BUILD FAILED. Details:
type "%TEMP%\psal_badminton_selftest_team.txt" 2>nul
type "%TEMP%\psal_badminton_selftest_manager.txt" 2>nul
pause
exit /b 1
