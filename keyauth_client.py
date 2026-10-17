"""
KeyAuth client for desktop GUI apps (Windows + macOS).

Same API surface as the official KeyAuth Python example
(api(name, ownerid, version, hash_to_check) -> init / login / register /
license / upgrade / var / check / log / logout), but built for a GUI:

  * nothing calls print() or os._exit() — failures raise KeyAuthError so the
    login screen can show a friendly message
  * init() is not run inside the constructor, so the window can open first
    and connect in a background thread
  * every response is verified with KeyAuth's ed25519 signature, exactly like
    the official client, so responses can't be faked by a proxy
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import uuid

import requests

from ed25519_verify import verify as ed25519_verify

API_URL = "https://keyauth.win/api/1.3/"
# KeyAuth's public signing key (from the official Python example).
KEYAUTH_PUBLIC_KEY = "5586b4bc69c7a4b487e4563a4cd96afd39140f919bd31cea7d1c6a1e8439422b"
MAX_RESPONSE_AGE = 25  # seconds (20 + 5 buffer, same as official client)


class KeyAuthError(Exception):
    """Raised for any KeyAuth failure; str(e) is safe to show to the user."""

    def __init__(self, message: str, download: str | None = None):
        super().__init__(message)
        self.download = download  # set when a newer version is required


class _UserData:
    def __init__(self):
        self.username = ""
        self.ip = ""
        self.hwid = ""
        self.expires = ""
        self.createdate = ""
        self.lastlogin = ""
        self.subscription = ""
        self.subscriptions: list[dict] = []


class api:
    def __init__(self, name: str, ownerid: str, version: str, hash_to_check: str):
        if len(ownerid) != 10:
            raise KeyAuthError("Invalid KeyAuth owner ID — copy it from keyauth.cc/app")
        self.name = name
        self.ownerid = ownerid
        self.version = version
        self.hash_to_check = hash_to_check
        self.sessionid = ""
        self.initialized = False
        self.user_data = _UserData()
        self._public_key = bytes.fromhex(KEYAUTH_PUBLIC_KEY)

    # ------------------------------------------------------------------ core
    def _request(self, post_data: dict, signed: bool = True) -> dict:
        post_data = {**post_data, "name": self.name, "ownerid": self.ownerid}
        if self.sessionid and "sessionid" not in post_data:
            post_data["sessionid"] = self.sessionid
        try:
            resp = requests.post(API_URL, data=post_data, timeout=12)
        except requests.exceptions.Timeout:
            raise KeyAuthError("KeyAuth server timed out. Check your internet and try again.")
        except requests.exceptions.RequestException:
            raise KeyAuthError("Can't reach the login server. Check your internet connection.")

        text = resp.text
        if text == "KeyAuth_Invalid":
            raise KeyAuthError("This app doesn't exist on KeyAuth (check name / owner ID).")
        if signed:
            self._verify(resp)
        try:
            return json.loads(text)
        except ValueError:
            raise KeyAuthError("Unexpected reply from the login server.")

    def _verify(self, resp: requests.Response) -> None:
        sig = resp.headers.get("x-signature-ed25519")
        ts = resp.headers.get("x-signature-timestamp")
        if not sig or not ts:
            raise KeyAuthError("Login server reply was not signed — connection blocked.")
        if abs(time.time() - int(ts)) > MAX_RESPONSE_AGE:
            raise KeyAuthError("Your computer clock looks wrong. Sync your date & time and retry.")
        try:
            ok = ed25519_verify(self._public_key, ts.encode() + resp.content, bytes.fromhex(sig))
        except ValueError:
            ok = False
        if not ok:
            raise KeyAuthError("Signature check failed — the response was tampered with.")

    def checkinit(self):
        if not self.initialized:
            raise KeyAuthError("Not connected to KeyAuth yet.")

    def _load_user(self, info: dict) -> None:
        u = self.user_data
        u.username = info.get("username", "")
        u.ip = info.get("ip", "")
        u.hwid = info.get("hwid") or "N/A"
        u.createdate = info.get("createdate", "")
        u.lastlogin = info.get("lastlogin", "")
        subs = info.get("subscriptions") or []
        u.subscriptions = subs
        if subs:
            u.subscription = subs[0].get("subscription", "")
            u.expires = subs[0].get("expiry", "")

    # ------------------------------------------------------------- endpoints
    def init(self) -> None:
        self.sessionid = ""
        data = self._request({
            "type": "init",
            "ver": self.version,
            "hash": self.hash_to_check,
        })
        if data.get("message") == "invalidver":
            raise KeyAuthError("A new version is available. Please download the update.",
                               download=data.get("download") or None)
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Could not connect to KeyAuth."))
        self.sessionid = data["sessionid"]
        self.initialized = True

    def login(self, user, password, code=None, hwid=None):
        self.checkinit()
        post = {"type": "login", "username": user, "pass": password,
                "hwid": hwid or others.get_hwid()}
        if code:
            post["code"] = code
        data = self._request(post)
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Login failed."))
        self._load_user(data["info"])
        return data.get("message", "Logged in")

    def register(self, user, password, license, hwid=None):
        self.checkinit()
        data = self._request({"type": "register", "username": user, "pass": password,
                              "key": license, "hwid": hwid or others.get_hwid()})
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Register failed."))
        self._load_user(data["info"])
        return data.get("message", "Registered")

    def license(self, key, code=None, hwid=None):
        self.checkinit()
        post = {"type": "license", "key": key, "hwid": hwid or others.get_hwid()}
        if code:
            post["code"] = code
        data = self._request(post)
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Invalid license."))
        self._load_user(data["info"])
        return data.get("message", "Logged in")

    def upgrade(self, user, license):
        self.checkinit()
        data = self._request({"type": "upgrade", "username": user, "key": license})
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Upgrade failed."))
        return data.get("message", "Upgraded — log in again.")

    def var(self, name):
        self.checkinit()
        data = self._request({"type": "var", "varid": name})
        if not data.get("success"):
            raise KeyAuthError(data.get("message", "Variable not found."))
        return data.get("message")

    def check(self) -> bool:
        if not self.initialized:
            return False
        try:
            return bool(self._request({"type": "check"}).get("success"))
        except KeyAuthError:
            return False

    def log(self, message: str) -> None:
        """Sends a log line to your KeyAuth dashboard (needs a webhook set there)."""
        if not self.initialized:
            return
        try:
            self._request({"type": "log", "message": message,
                           "pcuser": os.getenv("USERNAME") or os.getenv("USER") or "?"},
                          signed=False)
        except KeyAuthError:
            pass

    def logout(self) -> None:
        if self.initialized:
            try:
                self._request({"type": "logout"})
            except KeyAuthError:
                pass
        self.user_data = _UserData()
        self.sessionid = ""
        self.initialized = False


class others:
    _cached_hwid: str | None = None

    @staticmethod
    def _run(cmd: list[str]) -> str:
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=8, **kwargs)
        return out.stdout

    @staticmethod
    def get_hwid() -> str:
        if others._cached_hwid:
            return others._cached_hwid
        hwid = ""
        system = platform.system()
        try:
            if system == "Windows":
                # Same value the official example uses (the user account SID),
                # read without needing pywin32.
                out = others._run(["whoami", "/user", "/fo", "csv", "/nh"])
                hwid = out.strip().split(",")[-1].strip().strip('"')
            elif system == "Darwin":
                out = others._run(["ioreg", "-l"])
                for line in out.splitlines():
                    if "IOPlatformSerialNumber" in line:
                        hwid = line.split("=", 1)[1].strip().strip('"')
                        break
            else:
                with open("/etc/machine-id") as f:
                    hwid = f.read().strip()
        except Exception:
            hwid = ""
        if not hwid:
            hwid = str(uuid.getnode())
        others._cached_hwid = hwid
        return hwid
