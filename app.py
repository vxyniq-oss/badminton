"""Main window: KeyAuth login screen + the app shell (sidebar and pages)."""
from __future__ import annotations

import queue
import sys
import threading
import time
import webbrowser
from datetime import date
from pathlib import Path

import customtkinter as ctk
from PIL import Image

import ui_kit as K
from data_store import Config, Store
from roles import PERMISSIONS, greeting, role_from_subscriptions  # noqa: F401 (re-exported)
from keyauth_client import KeyAuthError
from ui_kit import (ACCENT, ACCENT_SOFT, BG, BORDER, F, GOOD, HOVER, LIME, MUTED, SIDEBAR, box,
                    SURFACE, SURFACE2, TEXT, WARN, button, card, chip, entry, label, segmented)

SESSION_CHECK_MS = 10 * 60 * 1000
FILE_POLL_MS = 4000

ROLE_LABEL = {"coach": "Coach", "manager": "Manager", "player": "Player"}
ROLE_COLOR = {"coach": "#F5B83D", "manager": "#A78BFA", "player": "#60A5FA"}


def resource(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


EDITIONS = {
    "team": {"title": "PSAL Badminton — Team Points", "icon": "icon", "start": "dashboard",
             "kicker": "PSAL BADMINTON", "headline": "Team Points &\nLineup System",
             "tagline": "Hit 500 points, win your rank-up match, earn your rank.",
             "pills": ("1st–3rd Singles", "1st–2nd Doubles", "Video Quizzes", "Rank-Up Matches")},
    "manager": {"title": "PSAL Badminton Manager", "icon": "icon_manager", "start": "rankups",
                "kicker": "PSAL BADMINTON · MANAGER", "headline": "Manager\nConsole",
                "tagline": "Run rank-up matches, train your 1st singles, coach the team.",
                "pills": ("Rank-Up Matches", "Manual Ranks", "Quizzes", "1S Training")},
}


class App(ctk.CTk):
    def __init__(self, auth, edition: str = "team"):
        self.edition = edition
        self.ed = EDITIONS[edition]
        self.config_store = Config()
        ctk.set_appearance_mode(self.config_store.get("appearance", "dark"))
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=BG)
        self.auth = auth
        self.store: Store | None = None
        self.role = "player"
        self.username = ""
        self.display_name = ""
        self.player_pid = None   # set for keyless (team code + PIN) player sign-ins
        self._pin_fails: dict = {}
        self.watch_started: dict = {}  # (player id, video id) -> time Watch was pressed
        self._q: queue.Queue = queue.Queue()
        self._toasts: list = []

        self.title(self.ed["title"])
        # fit smaller school laptops (e.g. 1366x768) as well as big screens
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1320, max(1024, sw - 40)), min(840, max(620, sh - 90))
        self.geometry(f"{w}x{h}+{max(0, (sw - w) // 2)}+{max(0, (sh - h) // 3)}")
        self.minsize(min(1024, w), min(620, h))
        try:
            if sys.platform.startswith("win"):
                self.iconbitmap(str(resource(f"assets/{self.ed['icon']}.ico")))
            else:
                from PIL import ImageTk
                self._icon = ImageTk.PhotoImage(Image.open(resource(f"assets/{self.ed['icon']}_256.png")))
                self.iconphoto(True, self._icon)
        except Exception:
            pass
        logo = Image.open(resource(f"assets/{self.ed['icon']}_256.png"))
        self.logo = ctk.CTkImage(logo, size=(38, 38))
        self.logo_big = ctk.CTkImage(logo, size=(84, 84))

        from watch_server import WatchServer
        self.watch = WatchServer(lambda sess: self._q.put((self._on_watch_end, (sess,))))

        self.view = None
        self.last_input = time.monotonic()  # used to do background work only while idle
        for seq in ("<Button>", "<Key>", "<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._touched, add="+")
        self.after(60, self._drain)
        self.show_login()

    # --------------------------------------------------- background threads
    def run_bg(self, work, done=None, fail=None):
        def target():
            try:
                r = work()
                self._q.put((done, (r,)) if done else (None, ()))
            except Exception as e:  # noqa: BLE001 — reported to the UI
                self._q.put((fail or self._bg_error, (e,)))
        threading.Thread(target=target, daemon=True).start()

    def _touched(self, _e=None):
        self.last_input = time.monotonic()

    def _bg_error(self, e):
        self.toast(str(e), "error")

    def _drain(self):
        try:
            while True:
                cb, args = self._q.get_nowait()
                if cb:
                    cb(*args)
        except queue.Empty:
            pass
        self.after(60, self._drain)

    # ---------------------------------------------------------------- views
    def _swap(self, view):
        if self.view is not None:
            self.view.destroy()
        self.view = view
        view.pack(fill="both", expand=True)

    def show_login(self):
        self.store = None
        self._swap(LoginView(self))

    def on_player_signed_in(self, pid):
        """Keyless player sign-in (team code + name + PIN) — no KeyAuth key needed."""
        store = Store(self.config_store.get("data_dir"), user="player")
        p = store.players[pid]
        self.player_pid = pid
        self.username = p.get("username") or p["name"]
        self.display_name = p["name"].split()[0]
        self.role = "player"
        store.user = p["name"]
        self.store = store
        self.config_store.set("last_role", "player")
        self.config_store.set("last_player", pid)
        self.config_store.set("last_name", self.display_name)
        self._swap(Shell(self))
        self.after(FILE_POLL_MS, self._poll_file)

    def on_logged_in(self, mode: str = "Login"):
        self.player_pid = None
        u = self.auth.user_data
        self.username = u.username or "license user"
        # license-only logins have the key as their username, so don't greet with it
        self.display_name = "" if mode == "License Key" else (u.username or "")
        self.role = role_from_subscriptions(u.subscriptions)
        self.config_store.set("last_role", self.role)
        self.config_store.set("last_name", self.display_name)
        self.store = Store(self.config_store.get("data_dir"), user=self.username)
        self._swap(Shell(self))
        self.auth.log(f"{self.username} signed in as {self.role}")
        self.after(FILE_POLL_MS, self._poll_file)
        self.after(SESSION_CHECK_MS, self._check_session)

    def logout(self):
        self.run_bg(self.auth.logout)
        self.show_login()

    # ------------------------------------------------- verified video watching
    def watch_video(self, pid, vid):
        """Open a training video in the tracked, unskippable player."""
        s = self.store
        v = s.video(vid)
        st = s.video_status(pid, vid)
        if st["skipped"]:
            return self.toast("Skipping was detected on this video, so it can't earn points.", "error")
        try:
            sess, url = self.watch.new_session(pid, vid, v["url"], v["title"],
                                               60 * int(v.get("minutes", 0)), s.player_name(pid))
        except ValueError as e:
            return self.toast(str(e), "error")
        webbrowser.open(url)
        pen = s.settings["extras"].get("integrity_penalty", 10)
        self.toast(f"Opened in your browser — watch it all the way through there. "
                   f"Skipping or speeding up = no points and −{pen}.", "info", 7000)

    def _on_watch_end(self, sess):
        s = self.store
        if s is None:
            return
        name = s.player_name(sess.pid)
        try:
            if sess.state == "done":
                pts, ev = s.complete_video(sess.pid, sess.vid, sess.credited)
                v = s.video(sess.vid) or {}
                if v.get("kind") == "quiz":
                    self.toast(f"{name} watched “{v.get('title', '')}” — the quiz is unlocked!", "success", 6000)
                else:
                    self.toast(f"Verified! +{pts} points for {name}", "success", 6000)
                self.announce(ev)
            elif sess.state == "skipped":
                pen, _ = s.flag_skip(sess.pid, sess.vid, sess.reason)
                self.toast(f"Skipping detected for {name} ({sess.reason}). No points for this video"
                           + (f" and −{pen} for integrity." if pen else "."), "error", 9000)
            elif sess.state == "error":
                self.toast(f"That video couldn't count: {sess.reason}. No penalty.", "error", 7000)
            elif sess.state == "abandoned" and sess.reason != "Opened again":
                self.toast(f"{name}'s video was closed before the end — no points, no penalty.", "info")
        except Exception as e:  # noqa: BLE001
            self.toast(str(e), "error")
        if isinstance(self.view, Shell):
            self.view.refresh_current()

    def can(self, perm: str) -> bool:
        return perm in PERMISSIONS.get(self.role, set())

    def greeting(self) -> str:
        return greeting(self.display_name, self.role)

    @property
    def me(self):
        """The roster spot linked to this KeyAuth username (set in Roster → Edit)."""
        if self.store is None:
            return None
        if self.player_pid:
            return self.store.players.get(self.player_pid)
        p = self.store.player_for_username(self.username)
        return p if p and p.get("role") != "manager" else None

    @property
    def me_manager(self):
        p = self.store.player_for_username(self.username) if self.store else None
        return p if p and p.get("role") == "manager" else None

    def _poll_file(self):
        if self.store is None:
            return
        if self.store.changed_on_disk():
            self.store.reload()
            if isinstance(self.view, Shell):
                self.view.refresh_current()
        self.after(FILE_POLL_MS, self._poll_file)

    def _check_session(self):
        if self.store is None or self.player_pid:
            return

        def done(ok):
            if ok:
                self.after(SESSION_CHECK_MS, self._check_session)
            elif self.store is not None:
                self.show_login()
                self.toast("Your session expired. Please sign in again.", "error")
        self.run_bg(self.auth.check, done, lambda e: self.after(SESSION_CHECK_MS, self._check_session))

    # ---------------------------------------------------------------- toast
    def toast(self, message: str, kind: str = "info", ms: int = 3800):
        colors = {"info": ACCENT, "success": GOOD, "error": ("#DC2626", "#EF4444"), "rank": WARN,
                  "drop": ("#DC2626", "#EF4444"), "qual": LIME}
        t = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=12, border_width=1,
                         border_color=colors.get(kind, ACCENT))
        bar = ctk.CTkFrame(t, width=5, height=8, fg_color=colors.get(kind, ACCENT), corner_radius=3)
        bar.pack(side="left", fill="y", padx=(8, 0), pady=10)
        prefix = {"rank": "RANK UP  ", "drop": "RANK DOWN  ", "qual": "QUALIFIED  "}.get(kind, "")
        label(t, prefix + message, 13, "bold" if kind in ("rank", "drop", "qual") else "normal",
              wraplength=360, justify="left").pack(side="left", padx=12, pady=12)
        self._toasts.append(t)
        self._layout_toasts()
        self.after(ms, lambda: self._close_toast(t))

    def _layout_toasts(self):
        y = -22
        for t in reversed(self._toasts):
            t.place(relx=1.0, rely=1.0, anchor="se", x=-22, y=y)
            t.lift()
            t.update_idletasks()
            y -= t.winfo_reqheight() + 10

    def _close_toast(self, t):
        if t in self._toasts:
            self._toasts.remove(t)
            t.destroy()
            self._layout_toasts()

    def announce(self, events):
        for e in events or []:
            kind = "drop" if " moved down to " in e else "qual" if " qualified for " in e else "rank"
            self.toast(e, kind, 6000)


# ============================================================== login view
class LoginView(ctk.CTkFrame):
    def __init__(self, app: App):
        super().__init__(app, fg_color=BG)
        self.app = app
        self.ready = app.auth.initialized
        self.mode = "Login"
        self.download = None

        self.grid_columnconfigure(0, weight=5, uniform="x")
        self.grid_columnconfigure(1, weight=4, uniform="x")
        self.grid_rowconfigure(0, weight=1)

        # ---- left: brand + the sign
        ed = app.ed
        left = ctk.CTkFrame(self, fg_color=K.HERO_LOGIN, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        inner = box(left)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(inner, text="", image=app.logo_big).pack(anchor="w")
        label(inner, ed["kicker"], 13, "bold", LIME).pack(anchor="w", pady=(18, 2))
        label(inner, ed["headline"], 38, "bold", "#FFFFFF", justify="left").pack(anchor="w")
        label(inner, ed["tagline"], 15, color=K.HERO_SUB).pack(anchor="w", pady=(10, 26))

        sign = ctk.CTkFrame(inner, fg_color=LIME, corner_radius=16)
        sign.pack(anchor="w", fill="x")
        cfg = app.config_store
        known = cfg.get("remember_user") or cfg.get("last_role") == "player"
        hello = greeting(cfg.get("last_name", "") if known else "", cfg.get("last_role", "coach"))
        label(sign, hello, 28, "bold", "#0B1220").pack(anchor="w", padx=24, pady=(18, 0))
        sub = ("Welcome back — your team is ready to train." if app.edition == "team"
               else "Managers and coaches sign in here.")
        label(sign, sub, 13, color="#26340A").pack(anchor="w", padx=24, pady=(2, 18))

        pills = box(inner)
        pills.pack(anchor="w", pady=(26, 0))
        for t in ed["pills"]:
            ctk.CTkLabel(pills, text=f"  {t}  ", font=F(12, "bold"), text_color="#FFFFFF",
                         fg_color=K.HERO_PILL, corner_radius=14,
                         height=28).pack(side="left", padx=(0, 8))

        # ---- right: auth card
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        panel = card(right, width=400)
        panel.place(relx=0.5, rely=0.5, anchor="center")
        pad = dict(padx=30)
        label(panel, "Sign in", 24, "bold").pack(fill="x", pady=(28, 2), **pad)
        label(panel, "Secured with KeyAuth", 12, color=MUTED).pack(fill="x", **pad)

        modes = ["Player", "Login", "Register", "License Key"] if app.edition == "team" else \
            ["Login", "Register", "License Key"]
        start = "Login" if (app.edition == "manager" or app.config_store.get("remember_user")) else "Player"
        self.mode = start
        self.tabs = segmented(panel, modes, command=self._mode)
        self.tabs.set(start)
        self.tabs.pack(fill="x", pady=(18, 8), **pad)

        self.form = box(panel)
        self.form.pack(fill="x", **pad)
        self.user = entry(self.form, "Username", width=340)
        self.pw = entry(self.form, "Password", width=340, show="•")
        self.key = entry(self.form, "License key", width=340)
        self.code = entry(self.form, "2FA code (leave blank if not using 2FA)", width=340)
        # keyless player sign-in
        self.pcode = entry(self.form, "Team code (ask your coach)", width=340)
        self.pname = K.option(self.form, ["Type the team code first"], width=340,
                              command=lambda _v: self._player_changed())
        self.pname.configure(state="disabled")
        self.ppin = entry(self.form, "PIN", width=340, show="•")
        self.ppin2 = entry(self.form, "Type the new PIN again", width=340, show="•")
        self.phint = label(self.form, "", 11, color=MUTED, wraplength=340, justify="left")
        self._pids = {}
        self.pcode.bind("<KeyRelease>", lambda e: self._player_code_changed())
        remembered = app.config_store.get("remember_user", "")
        if remembered:
            self.user.insert(0, remembered)
        self.remember = ctk.CTkCheckBox(self.form, text="Remember my username", font=F(12),
                                        text_color=MUTED, checkbox_width=18, checkbox_height=18,
                                        corner_radius=5, border_width=2)
        if remembered:
            self.remember.select()

        self.go = button(panel, "Connecting…", self._submit, height=42, state="disabled")
        self.go.pack(fill="x", pady=(14, 6), **pad)
        self.status = label(panel, "", 12, color=MUTED, wraplength=340, justify="left")
        self.status.pack(fill="x", pady=(0, 4), **pad)
        self.retry = button(panel, "Retry connection", self._connect, "ghost")
        self.update_btn = button(panel, "Download update", self._open_download, "good")
        label(panel, f"v{app.auth.version}", 11, color=MUTED, anchor="e").pack(fill="x", pady=(4, 18), **pad)

        self._mode(self.mode)
        for w in (self.user, self.pw, self.key, self.code, self.ppin, self.ppin2):
            w.bind("<Return>", lambda e: self._submit())
        if self.ready:
            self._ready()
        else:
            self._connect()

    def _mode(self, mode):
        self.mode = mode
        for w in self.form.winfo_children():
            w.pack_forget()
        if mode == "Player":
            return self._player_layout()
        order = {"Login": [self.user, self.pw, self.code],
                 "Register": [self.user, self.pw, self.key],
                 "License Key": [self.key, self.code]}[mode]
        for w in order:
            w.pack(fill="x", pady=5)
        if mode != "License Key":
            self.remember.pack(anchor="w", pady=(6, 0))
        if self.ready:
            self.go.configure(text={"Login": "Sign in", "Register": "Create account",
                                    "License Key": "Activate"}[mode])

    # ------------------------------------------------ keyless player sign-in
    def _login_store(self):
        try:
            return Store(self.app.config_store.get("data_dir"), user="login")
        except Exception:
            return None

    def _player_layout(self):
        for w in self.form.winfo_children():
            w.pack_forget()
        self.pcode.pack(fill="x", pady=5)
        self.pname.pack(fill="x", pady=5)
        self.ppin.pack(fill="x", pady=5)
        self._player_code_changed()

    def _player_code_changed(self):
        st = self._login_store()
        if st is None or not st.settings.get("player_code"):
            self.pname.configure(values=["Player sign-in is off"], state="disabled")
            self.pname.set("Player sign-in is off")
            return self._player_hint("Player sign-in isn't turned on for this computer yet. Your coach sets "
                                     "a team code in Settings, and the team's data folder has to be on this computer.")
        if not st.player_code_ok(self.pcode.get()):
            self._pids = {}
            self.pname.configure(values=["Type the team code first"], state="disabled")
            self.pname.set("Type the team code first")
            return self._player_hint("No license key needed — just the team code, your name and your PIN.")
        players = [p for p in st.active_players() if p.get("role") != "manager"]
        self._pids = {p["name"]: p["id"] for p in players}
        names = list(self._pids) or ["No players on the roster yet"]
        if self.pname.get() not in self._pids:
            last = self.app.config_store.get("last_player")
            pick = next((n for n, i in self._pids.items() if i == last), None)
            self.pname.configure(values=["Choose your name"] + names, state="normal")
            self.pname.set(pick or "Choose your name")
        self._player_changed(st)

    def _player_changed(self, st=None):
        st = st or self._login_store()
        pid = self._pids.get(self.pname.get())
        self.ppin2.pack_forget()
        if not pid:
            self._player_hint("Pick your name from the list.")
            if self.ready:
                self.go.configure(text="Sign in")
            return
        if st.has_pin(pid):
            self._player_hint("Enter your PIN.")
            if self.ready:
                self.go.configure(text="Sign in")
        else:
            self.ppin2.pack(fill="x", pady=5, after=self.ppin)
            self._player_hint("First time? Make a 4–8 digit PIN and keep it secret — it's how the app knows it's you.")
            if self.ready:
                self.go.configure(text="Create PIN & sign in")

    def _player_hint(self, text):
        self.phint.configure(text=text)
        self.phint.pack(fill="x", pady=(4, 0))

    def _player_submit(self):
        import time as _t
        st = self._login_store()
        if st is None or not st.player_code_ok(self.pcode.get()):
            return self._set_status("That team code isn't right.", WARN)
        pid = self._pids.get(self.pname.get())
        if not pid:
            return self._set_status("Pick your name.", WARN)
        fails, until = self.app._pin_fails.get(pid, (0, 0))
        if _t.time() < until:
            return self._set_status(f"Too many wrong PINs. Try again in {int(until - _t.time())}s.", WARN)
        pin = self.ppin.get().strip()
        if st.has_pin(pid):
            if not st.check_pin(pid, pin):
                fails += 1
                self.app._pin_fails[pid] = (0, _t.time() + 60) if fails >= 5 else (fails, 0)
                self.ppin.delete(0, "end")
                return self._set_status("Wrong PIN." + (" Locked for 60 seconds." if fails >= 5 else
                                        " Forgot it? Ask your coach to reset it in Roster."), ("#DC2626", "#EF4444"))
        else:
            if not st.valid_pin(pin):
                return self._set_status("Your PIN must be 4 to 8 digits.", WARN)
            if pin != self.ppin2.get().strip():
                return self._set_status("The two PINs don't match.", WARN)
            st.user = st.player_name(pid)
            st.set_pin(pid, pin)
        self.app._pin_fails.pop(pid, None)
        self.app.on_player_signed_in(pid)

    def _set_status(self, text, color=MUTED):
        self.status.configure(text=text, text_color=color)

    def _connect(self):
        self.retry.pack_forget()
        self.go.configure(state="disabled", text="Connecting…")
        self._set_status("Connecting to KeyAuth…")
        self.app.run_bg(self.app.auth.init, lambda _: self._ready(), self._init_failed)

    def _ready(self):
        self.ready = True
        self.go.configure(state="normal")
        self._mode(self.mode)
        if self.mode == "Player":
            self._player_changed()
        self._set_status("Secure connection ready.", GOOD)

    def _init_failed(self, e):
        self._set_status(str(e), ("#DC2626", "#EF4444"))
        self.go.configure(text="Unavailable")
        if isinstance(e, KeyAuthError) and e.download:
            self.download = e.download
            self.update_btn.pack(fill="x", pady=(0, 6), padx=30, before=self.status)
        else:
            self.retry.pack(fill="x", pady=(0, 6), padx=30, before=self.status)

    def _open_download(self):
        if self.download:
            webbrowser.open(self.download)

    def _submit(self):
        if not self.ready or str(self.go.cget("state")) == "disabled":
            return
        if self.mode == "Player":
            return self._player_submit()
        a = self.app.auth
        u, p, k, c = (self.user.get().strip(), self.pw.get(), self.key.get().strip(),
                      self.code.get().strip() or None)
        if self.mode == "Login":
            if not u or not p:
                return self._set_status("Enter your username and password.", WARN)
            work = lambda: a.login(u, p, c)  # noqa: E731
        elif self.mode == "Register":
            if not u or not p or not k:
                return self._set_status("Username, password and license key are all required.", WARN)
            work = lambda: a.register(u, p, k)  # noqa: E731
        else:
            if not k:
                return self._set_status("Paste your license key.", WARN)
            work = lambda: a.license(k, c)  # noqa: E731

        if self.mode != "License Key":
            self.app.config_store.set("remember_user", u if self.remember.get() else "")
        self.go.configure(state="disabled", text="Signing in…")
        self._set_status("Checking your account…")
        mode = self.mode
        self.app.run_bg(work, lambda _: self._signed_in(mode), self._failed)

    def _signed_in(self, mode):
        role = role_from_subscriptions(self.app.auth.user_data.subscriptions)
        if self.app.edition == "manager" and role == "player":
            self.app.run_bg(self.app.auth.logout)
            return self._failed(KeyAuthError(
                "This is the Manager app — only coach and manager accounts can sign in. "
                "Players use the PSAL Badminton app."))
        self.app.on_logged_in(mode)

    def _failed(self, e):
        self._set_status(str(e), ("#DC2626", "#EF4444"))
        # KeyAuth sessions can expire on a failed attempt; reconnect quietly
        self.go.configure(state="disabled", text="Reconnecting…")
        self.app.auth.initialized = False
        self.app.run_bg(self.app.auth.init, lambda _: self._ready_keep_error(str(e)), self._init_failed)

    def _ready_keep_error(self, msg):
        self._ready()
        self._set_status(msg, ("#DC2626", "#EF4444"))


# ================================================================== shell
TEAM_NAV = [
    ("dashboard", "Dashboard", "⌂"),
    ("roster", "Roster", "☰"),
    ("lineup", "Lineup & Challenges", "◫"),
    ("matches", "PSAL Matches", "⚑"),
    ("practice", "Practice & Points", "✓"),
    ("quizzes", "Video Quizzes", "?"),
    ("videos", "Optional Training", "▶"),
    ("leaderboard", "Leaderboard", "★"),
    ("training", "Manager Training · 1S", "◎"),
    ("notes", "Improvement Notes", "✎"),
    ("activity", "Activity", "↻"),
    ("settings", "Settings", "⚙"),
]
MANAGER_NAV = [
    ("rankups", "Rank-Up Matches", "▲"),
    ("quizzes", "Video Quizzes", "?"),
    ("videos", "Optional Training", "▶"),
    ("roster", "Roster", "☰"),
    ("leaderboard", "Leaderboard", "★"),
    ("training", "Manager Training · 1S", "◎"),
    ("notes", "Improvement Notes", "✎"),
    ("activity", "Activity", "↻"),
    ("settings", "Settings", "⚙"),
]
NAV = TEAM_NAV  # kept for older test scripts
HIDDEN_FOR_PLAYERS = {"notes", "activity"}


class Shell(ctk.CTkFrame):
    def __init__(self, app: App, start: str | None = None):
        super().__init__(app, fg_color=BG)
        self.app = app
        import pages  # local import keeps login fast
        self.page_classes = pages.PAGES
        self.pages: dict = {}
        self.current = None
        self.current_key = None
        self.nav_buttons = {}

        side = ctk.CTkFrame(self, width=248, fg_color=SIDEBAR, corner_radius=0,
                            border_width=0)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        ctk.CTkFrame(self, width=1, height=8, fg_color=BORDER, corner_radius=0).pack(side="left", fill="y")

        brand = box(side)
        brand.pack(fill="x", padx=18, pady=(20, 18))
        ctk.CTkLabel(brand, text="", image=app.logo).pack(side="left")
        tb = box(brand)
        tb.pack(side="left", padx=10)
        self.team_label = label(tb, app.store.data["team"].get("name", "PSAL Badminton"), 15, "bold")
        self.team_label.pack(anchor="w")
        sub = "Manager · " if app.edition == "manager" else ""
        label(tb, f"{sub}Season {app.store.data['team'].get('season', '')}", 11,
              color=MUTED).pack(anchor="w")

        for key, text, icon in (MANAGER_NAV if app.edition == "manager" else TEAM_NAV):
            if app.role == "player" and key in HIDDEN_FOR_PLAYERS:
                continue
            b = ctk.CTkButton(side, text=f"  {icon}   {text}", anchor="w", height=40,
                              corner_radius=10, font=F(13), fg_color="transparent",
                              hover_color=HOVER, text_color=MUTED,
                              command=lambda k=key: self.show(k))
            b.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = b

        bottom = box(side)
        bottom.pack(side="bottom", fill="x", padx=12, pady=16)
        user = card(bottom, fg_color=SURFACE2, border_width=0)
        user.pack(fill="x")
        row = box(user)
        row.pack(fill="x", padx=12, pady=10)
        from ui_kit import avatar
        avatar(row, app.username, ROLE_COLOR[app.role], 34).pack(side="left")
        info = box(row)
        info.pack(side="left", padx=10)
        label(info, app.username, 13, "bold").pack(anchor="w")
        chip(info, ROLE_LABEL[app.role], ROLE_COLOR[app.role], size=10).pack(anchor="w", pady=(2, 0))
        btns = box(bottom)
        btns.pack(fill="x", pady=(8, 0))
        self.theme_btn = button(btns, "Light mode" if ctk.get_appearance_mode() == "Dark" else "Dark mode",
                                self.toggle_theme, "ghost", height=32)
        self.theme_btn.pack(side="left", fill="x", expand=True)
        button(btns, "Log out", app.logout, "ghost", height=32).pack(side="left", fill="x",
                                                                     expand=True, padx=(8, 0))

        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        self.nav_order = list(self.nav_buttons)
        self.show(start if start in self.nav_buttons else app.ed["start"])
        self._warm_job = self.after(900, self._warm_tick)

    def toggle_theme(self):
        mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(mode)
        self.app.config_store.set("appearance", mode)
        # fast widgets bake their colors in, so rebuild the screens in the new theme
        self.app._swap(Shell(self.app, start=self.current_key))

    def _highlight(self, key, active):
        b = self.nav_buttons.get(key)
        if b is not None:
            b.configure(fg_color=ACCENT_SOFT if active else "transparent",
                        text_color=ACCENT if active else MUTED,
                        font=F(13, "bold" if active else "normal"))

    def _page(self, key):
        """Every tab is stacked in the same spot; switching just raises one to the top.
        (Hiding and re-showing hundreds of widgets is what made switching slow, especially
        on Windows where each widget is its own window.)"""
        if key not in self.pages:
            p = self.page_classes[key](self.content, self.app, self)
            p.place(x=0, y=0, relwidth=1, relheight=1)
            if self.current is not None:
                p.lower()  # built behind the screen in use, so nothing flickers
            self.pages[key] = p
        return self.pages[key]

    def show(self, key):
        if key == self.current_key and self.current is not None:
            return
        # only the two sidebar buttons that change get restyled
        self._highlight(self.current_key, False)
        self._highlight(key, True)
        page = self._page(key)
        ver = self.app.store.version
        if getattr(page, "_seen", None) != ver:  # only redraw if the data changed
            page.refresh()
            page._seen = ver
        self.current, self.current_key = page, key
        page.tkraise()

    # ---------------------------------------------------- background pre-build
    # Tabs are built and kept up to date while you aren't clicking or typing, so
    # switching tabs only has to swap screens instead of drawing a new one.
    IDLE_BEFORE_WORK = 0.6   # seconds of no input before doing background work

    def _warm_tick(self):
        try:
            if not self.winfo_exists() or self.app.view is not self:
                return
        except Exception:
            return
        delay = 150
        if time.monotonic() - self.app.last_input >= self.IDLE_BEFORE_WORK:
            ver = self.app.store.version
            for key in self.nav_order:
                if key == self.current_key:
                    continue
                page = self._page(key)
                if getattr(page, "_seen", None) != ver:
                    try:
                        page.refresh()
                        page._seen = ver
                    except Exception:
                        page._seen = ver  # never let a background refresh break the app
                    break
            else:
                delay = 800  # everything is ready; check again later
        self._warm_job = self.after(delay, self._warm_tick)

    def refresh_current(self):
        self.team_label.configure(text=self.app.store.data["team"].get("name", "PSAL Badminton"))
        if self.current is not None:
            self.current.refresh()
            self.current._seen = self.app.store.version


def run(auth, edition: str = "team"):
    app = App(auth, edition)
    app.mainloop()
