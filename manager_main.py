"""
PSAL Badminton Manager — the managers' and coaches' version of the app.
Run:  python manager_main.py
Same KeyAuth app and same team data as the Team app; players can't sign in here.
"""
import sys

import ui_kit

ui_kit.use_manager_theme()  # must run before any screen is imported

from main import keyauthapp, selftest  # noqa: E402  (KeyAuth details live in main.py)

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest("manager"))
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    from app import run
    run(keyauthapp, "manager")
