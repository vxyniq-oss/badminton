#!/bin/bash
# Builds BOTH apps into the dist folder and self-tests them:
#   dist/PSAL Badminton.app          (team / players)
#   dist/PSAL Badminton Manager.app  (managers & coaches)
set -e
cd "$(dirname "$0")"
if grep -q nacl keyauth_client.py; then
  echo "These are the OLD files. Unzip the newest PSAL-Badminton zip and run build_mac.sh from that folder."; exit 1
fi
rm -rf build dist ./*.spec
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r requirements.txt pyinstaller
COMMON=(--noconfirm --clean --windowed --add-data "assets:assets" --collect-data customtkinter --hidden-import PIL._tkinter_finder)

python3 -m PyInstaller "${COMMON[@]}" --name "PSAL Badminton" --icon assets/icon.png \
  --osx-bundle-identifier org.psal.badminton main.py
python3 -m PyInstaller "${COMMON[@]}" --name "PSAL Badminton Manager" --icon assets/icon_manager.png \
  --osx-bundle-identifier org.psal.badminton.manager manager_main.py

echo "Testing the finished apps..."
for APP in "PSAL Badminton" "PSAL Badminton Manager"; do
  if ! "dist/$APP.app/Contents/MacOS/$APP" --selftest; then
    echo "BUILD FAILED:"; cat "${TMPDIR:-/tmp}"/psal_badminton_selftest_*.txt 2>/dev/null; exit 1
  fi
done
echo ""
echo "Done! Both self-tests passed. Your apps are in the dist folder."
