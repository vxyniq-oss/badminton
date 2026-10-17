"""
PSAL Badminton — Team Points & Lineup System
Run:  python main.py
"""
import hashlib
import os
import sys

from keyauth_client import api


def getchecksum():
    # The built .exe / .app when packaged, otherwise this script.
    path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
    md5_hash = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


keyauthapp = api(
    name = "psal badminton",
    ownerid = "jiSHQAsHVQ",
    version = "1.0",
    hash_to_check = getchecksum()
)


def selftest(edition: str = "team") -> int:
    """`PSAL Badminton --selftest`: imports everything the packaged app needs
    and exits 0 if OK. The build scripts run this so a broken build is caught."""
    import tempfile
    import traceback
    log = os.path.join(tempfile.gettempdir(), f"psal_badminton_selftest_{edition}.txt")
    try:
        import customtkinter  # noqa: F401
        import requests  # noqa: F401
        from PIL import Image, ImageTk  # noqa: F401
        import app  # noqa: F401
        import pages  # noqa: F401
        import discord_notify  # noqa: F401
        import starter_content  # noqa: F401
        import watch_server
        assert watch_server.youtube_id("https://youtu.be/T6gZMcFYZNo") == "T6gZMcFYZNo"
        from ed25519_verify import verify
        assert verify(bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"), b"",
                      bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"))
        for f in ("assets/icon.ico", "assets/icon_256.png", "assets/icon_manager.ico",
                  "assets/icon_manager_256.png"):
            assert app.resource(f).exists(), f"missing {f}"
        assert edition in app.EDITIONS
        msg, code = f"SELFTEST OK ({edition} app)", 0
    except Exception:
        msg, code = "SELFTEST FAILED\n" + traceback.format_exc(), 1
    with open(log, "w", encoding="utf-8") as f:
        f.write(msg)
    print(msg)
    return code


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    if sys.platform == "win32":
        try:  # crisp text on high-DPI Windows screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    from app import run
    run(keyauthapp)
