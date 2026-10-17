"""All app pages. Each page builds its static layout once (build) and
redraws its live data in refresh(), so half-typed forms survive refreshes."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
import tkinter as tk
import webbrowser
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

import discord_notify
import ui_kit as K
from data_store import (IMPROVE_AREAS, LEVEL_COLORS, LEVELS, POSITION_LABELS, POSITION_SIZE,
                        POSITIONS, PRIORITIES, QUIZ_CATEGORIES, RANKUP_OPEN, SKILLS,
                        TRAINING_CATEGORIES, TRAINING_FOCUS, RankUpError, Store)
from ui_kit import (FastScroll, FastToggle, box, small_button, ACCENT, ACCENT_SOFT, BAD, BG, BORDER, GOOD, HOVER, LIME, MUTED, ON_COLOR,
                    POS_COLORS, PRIORITY_COLORS, SURFACE, SURFACE2, TEXT, WARN, Dialog, F, avatar,
                    button, card, chip, clear, confirm, empty_state, entry, label, option,
                    progress, segmented, vbar)

EMPTY = "— Empty —"


def nice_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %Y")
    except ValueError:
        return iso


def nice_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%b %d · %I:%M %p").replace(" 0", " ")
    except ValueError:
        return iso


class PlayerPicker:
    """Option menu that maps player names <-> ids."""

    def __init__(self, master, width=220, empty_label=EMPTY, command=None):
        self.empty_label = empty_label
        self.to_id, self.to_label = {}, {}
        self._cmd = command
        self.menu = option(master, [empty_label], width=width,
                           command=(lambda _v: command()) if command else None)
        self.menu.set(empty_label)

    def set_players(self, players, keep=True):
        current = self.get() if keep else None
        self.to_id, self.to_label = {}, {}
        labels = [self.empty_label] if self.empty_label else []
        for p in players:
            text = p["name"]
            if text in self.to_id:
                text = f"{p['name']} ({p.get('grade') or p['id'][:4]})"
            self.to_id[text] = p["id"]
            self.to_label[p["id"]] = text
            labels.append(text)
        self.menu.configure(values=labels or ["—"])
        self.set(current)

    def get(self):
        return self.to_id.get(self.menu.get())

    def set(self, pid):
        if pid and pid in self.to_label:
            self.menu.set(self.to_label[pid])
        elif self.empty_label:
            self.menu.set(self.empty_label)
        elif self.to_label:
            self.menu.set(next(iter(self.to_label.values())))
        else:
            self.menu.set("—")

    def pack(self, **kw):
        self.menu.pack(**kw)
        return self

    def grid(self, **kw):
        self.menu.grid(**kw)
        return self

    def configure(self, **kw):
        self.menu.configure(**kw)


def paged(master, items, render, first=60, step=60):
    """Draw the first `first` items, then a 'Show more' button (long lists stay fast)."""
    state = {"n": 0}
    more = {"w": None}

    def draw(upto):
        if more["w"] is not None:
            more["w"].destroy()
            more["w"] = None
        for it in items[state["n"]:upto]:
            render(it)
        state["n"] = min(upto, len(items))
        left = len(items) - state["n"]
        if left > 0:
            more["w"] = small_button(master, f"Show {min(step, left)} more  ({left} left)",
                                     lambda: draw(state["n"] + step), "ghost", height=32)
            more["w"].pack(pady=10)
    draw(first)


# ===================================================================== base
class Page(ctk.CTkFrame):
    title = ""
    subtitle = ""
    scroll = False

    def __init__(self, master, app, shell):
        super().__init__(master, fg_color=BG)
        self.app, self.shell = app, shell
        self.dirty = True
        head = box(self)
        head.pack(fill="x", padx=32, pady=(26, 14))
        txt = box(head)
        txt.pack(side="left")
        label(txt, self.title, 26, "bold").pack(anchor="w")
        if self.subtitle:
            label(txt, self.subtitle, 13, color=MUTED).pack(anchor="w", pady=(2, 0))
        self.actions = box(head, width=1, height=1)
        self.actions.pack(side="right")
        if self.scroll:
            self.body = FastScroll(self, fg_color=BG, corner_radius=0)
            self.body.pack(fill="both", expand=True, padx=(20, 8), pady=(0, 12))
        else:
            self.body = ctk.CTkFrame(self, fg_color=BG)
            self.body.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self.build()

    @property
    def store(self) -> Store:
        return self.app.store

    def build(self):
        pass

    def refresh(self):
        pass

    def act(self, fn, *args, success=None, **kwargs):
        """Run a store change, show rank-ups and refresh every page."""
        try:
            result, events = fn(*args, **kwargs)
        except RankUpError as e:
            self.app.toast(str(e), "error")
            return None
        except Exception as e:  # noqa: BLE001
            self.app.toast(f"Couldn't save: {e}", "error")
            return None
        if success:
            self.app.toast(success if isinstance(success, str) else success(result), "success")
        self.app.announce(events)
        self.shell.refresh_current()
        return result

    def readonly_note(self, master, text="View only — your account can't change this."):
        label(master, text, 12, color=MUTED).pack(anchor="w", pady=(4, 0))

    def section(self, master, title, subtitle=""):
        c = card(master)
        h = box(c)
        h.pack(fill="x", padx=20, pady=(16, 8))
        label(h, title, 16, "bold").pack(anchor="w")
        if subtitle:
            label(h, subtitle, 12, color=MUTED, wraplength=520, justify="left").pack(anchor="w")
        inner = box(c)
        inner.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        return c, inner, h


def rank_badge(master, store, pts):
    name, color, _, _ = store.rank(pts)  # preview only
    return chip(master, name, color)


def pos_chip(master, pos):
    if not pos:
        return chip(master, "Bench", SURFACE2, text_color=MUTED)
    return chip(master, POSITION_LABELS[pos], POS_COLORS[pos])


# ======================================================= rank-up helpers
def rankup_status_text(store, req) -> str:
    mgr = store.player_name(req["manager"]) if req.get("manager") else "any manager"
    if req["status"] == "scheduled":
        when = req.get("scheduled_for") or "time TBD"
        return f"Scheduled: {when}" + (f" · {req['details']}" if req.get("details") else "") + f" · with {mgr}"
    return f"Requested {nice_ts(req['ts'])} · waiting for {mgr}"


def request_rankup_dialog(page, pid):
    """Ask a manager for a rank-up match (players for themselves, coaches/managers for anyone)."""
    s, app = page.store, page.app
    lvl = s.rank_level(pid)
    d = Dialog(page, "Request a rank-up match", width=480)
    label(d.body, f"{s.player_name(pid)}: {s.level_name(lvl)[0]} → {s.level_name(lvl + 1)[0]}", 15,
          "bold").pack(fill="x")
    label(d.body, f"{s.points(pid)} points — qualified! Pick a manager to run your rank-up match.",
          12, color=MUTED, wraplength=430, justify="left").pack(fill="x")
    mgrs = s.managers()
    names = ["Any manager"] + [m["name"] for m in mgrs]
    pick = d.field("Ask which manager?", lambda m: option(m, names, width=420))
    msg = d.field("Message (optional)", lambda m: entry(m, "e.g. I'm free after practice Tue/Thu"))
    hook_ok = discord_notify.valid_webhook(s.settings.get("discord_webhook", ""))
    label(d.body, "The manager gets a Discord ping." if hook_ok else
          "Tip: tell the manager in person too — no Discord webhook is set up yet.", 11,
          color=MUTED).pack(fill="x", pady=(8, 0))

    def send():
        mgr = next((m["id"] for m in mgrs if m["name"] == pick.get()), None)
        d.destroy()
        rid = page.act(s.request_rankup, pid, mgr, msg.get(), app.username,
                       success="Rank-up match requested")
        if rid and hook_ok:
            req = s.rankup(rid)
            app.run_bg(lambda: discord_notify.send_rankup_request(
                s.settings["discord_webhook"], s, req, s.settings.get("discord_mention", "")),
                lambda _: app.toast("Manager pinged on Discord", "success"),
                lambda e: app.toast(f"Saved, but Discord didn't send: {e}", "error"))
    button(d.buttons, "Send request", send).pack(side="right")
    button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
    d.show()


def my_progress_card(page, master):
    """'Your progress' card for the signed-in player (linked by KeyAuth username)."""
    s, app = page.store, page.app
    p = app.me
    if p is None:
        if app.role == "player":
            c = card(master)
            c.pack(fill="x", pady=(0, 16))
            label(c, "Link your account", 16, "bold").pack(anchor="w", padx=22, pady=(16, 2))
            label(c, f"Your username “{app.username}” isn't on the roster yet. Ask your coach to add it "
                     "in Roster → Edit → KeyAuth username so you can track your points, take quizzes "
                     "and request rank-up matches.", 12, color=MUTED, wraplength=820,
                  justify="left").pack(anchor="w", padx=22, pady=(0, 16))
        return
    pid = p["id"]
    pts = s.points(pid)
    name, color, frac, need = s.rank_of(pid, pts)
    nxt = s.level_name(s.rank_level(pid) + 1)[0]
    c = card(master)
    c.pack(fill="x", pady=(0, 16))
    row = box(c)
    row.pack(fill="x", padx=22, pady=18)
    avatar(row, p["name"], color, 56).pack(side="left")
    col = box(row)
    col.pack(side="left", padx=16)
    top = box(col)
    top.pack(anchor="w")
    label(top, "YOUR PROGRESS", 11, "bold", MUTED).pack(side="left")
    label(col, f"{pts} points", 24, "bold").pack(anchor="w")
    r2 = box(col)
    r2.pack(anchor="w", pady=(2, 6))
    chip(r2, name, color).pack(side="left")
    pos_chip(r2, s.position_of(pid)).pack(side="left", padx=6)
    progress(col, frac, color, 300).pack(anchor="w")

    right = box(row)
    right.pack(side="right")
    req = s.open_rankup(pid)
    if req:
        chip(right, "Rank-up match " + ("scheduled" if req["status"] == "scheduled" else "requested"),
             LIME).pack(anchor="e")
        label(right, rankup_status_text(s, req), 12, color=MUTED, wraplength=360,
              justify="right", anchor="e").pack(anchor="e", pady=(6, 0))
    elif s.qualified(pid, pts):
        label(right, f"You qualify for a rank-up match to {nxt}!", 15, "bold", GOOD,
              anchor="e").pack(anchor="e")
        button(right, "Request rank-up match", lambda: request_rankup_dialog(page, pid),
               height=38).pack(anchor="e", pady=(8, 0))
    else:
        label(right, f"{need} more points to qualify for your {nxt} rank-up match", 13, "bold",
              anchor="e").pack(anchor="e")
        links = box(right)
        links.pack(anchor="e", pady=(8, 0))
        label(links, "Need extra points?", 12, color=MUTED).pack(side="left", padx=(0, 8))
        button(links, "Video Quizzes", lambda: page.shell.show("quizzes"), "ghost", height=32).pack(side="left")
        button(links, "Optional Training", lambda: page.shell.show("videos"), "ghost",
               height=32).pack(side="left", padx=(6, 0))


# ================================================================ dashboard
class DashboardPage(Page):
    title = "Dashboard"
    subtitle = "Your team at a glance"
    scroll = True

    def build(self):
        self.wrap = box(self.body)
        self.wrap.pack(fill="both", expand=True, padx=12)

    def refresh(self):
        s = self.store
        clear(self.wrap)
        team = s.data["team"]

        # ---- the sign
        sign = ctk.CTkFrame(self.wrap, fg_color=K.HERO, corner_radius=18)
        sign.pack(fill="x", pady=(0, 16))
        left = box(sign)
        left.pack(side="left", padx=28, pady=24)
        label(left, self.app.greeting(), 34, "bold", "#FFFFFF").pack(anchor="w")
        w, l = s.team_record()
        label(left, f"{date.today():%A, %B %d}  ·  {team.get('name')}  ·  Season record {w}-{l}",
              14, color=K.HERO_SUB).pack(anchor="w", pady=(4, 0))
        ctk.CTkLabel(sign, text=f"  Season {team.get('season', '')}  ", font=F(13, "bold"),
                     fg_color=LIME, text_color="#0B1220", corner_radius=14,
                     height=32).pack(side="right", padx=28)

        my_progress_card(self, self.wrap)

        # ---- stat cards
        stats = box(self.wrap)
        stats.pack(fill="x")
        board = s.leaderboard()
        top = board[0] if board else None
        notes_high = sum(1 for n in s.open_notes() if n["priority"] == "High")
        tp = s.training_points()
        items = [
            ("Players", str(len(board)), f"{len(s.active_players('manager'))} manager(s)"),
            ("Team record", f"{w}-{l}", f"{len(s.data['matches'])} PSAL matches"),
            ("Top player", top[0]["name"] if top else "—", f"{top[1]} pts" if top else "Add players"),
            ("1S training", f"{tp} pts" if tp is not None else "—",
             s.training_level(tp)[0] if tp is not None else "Set a 1st singles"),
            ("Open notes", str(len(s.open_notes())), f"{notes_high} high priority"),
        ]
        for i, (t, v, sub) in enumerate(items):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            c = card(stats)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 4 else 6))
            label(c, t.upper(), 11, "bold", MUTED).pack(anchor="w", padx=18, pady=(16, 0))
            label(c, v, 24 if len(v) <= 11 else 17, "bold").pack(anchor="w", padx=18, pady=(0, 0 if len(v) <= 11 else 5))
            label(c, sub, 12, color=MUTED).pack(anchor="w", padx=18, pady=(0, 16))

        # ---- lineup + top 5
        row = box(self.wrap)
        row.pack(fill="x", pady=16)
        row.grid_columnconfigure(0, weight=1, uniform="r")
        row.grid_columnconfigure(1, weight=1, uniform="r")

        lc, li, _ = self.section(row, "Current lineup")
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        for pos in POSITIONS:
            r = ctk.CTkFrame(li, fg_color=SURFACE2, corner_radius=10)
            r.pack(fill="x", pady=3)
            vbar(r, POS_COLORS[pos]).pack(
                side="left", fill="y", padx=(8, 10), pady=8)
            label(r, POSITION_LABELS[pos], 13, "bold", width=110).pack(side="left", pady=10)
            ids = s.data["lineup"].get(pos, [])
            names = " & ".join(f"{s.player_name(p)} ({s.points(p)})" for p in ids) or "Not set"
            label(r, names, 13, color=TEXT if ids else MUTED).pack(side="left", padx=6)

        tc, ti, _ = self.section(row, "Top 5", "Every 500 points = a rank-up match")
        tc.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        if not board:
            empty_state(ti, "No players yet", "Add your team in Roster")
        for i, (p, pts) in enumerate(board[:5], 1):
            name, color, frac, need = s.rank_of(p["id"], pts)
            r = box(ti)
            r.pack(fill="x", pady=4)
            label(r, f"{i}", 15, "bold", MUTED, width=22).pack(side="left")
            avatar(r, p["name"], color, 32).pack(side="left", padx=(4, 10))
            col = box(r)
            col.pack(side="left", fill="x", expand=True)
            label(col, p["name"], 13, "bold").pack(anchor="w")
            progress(col, frac, color, 180).pack(anchor="w", pady=(4, 0))
            label(r, f"{pts}", 15, "bold").pack(side="right", padx=(8, 0))
            chip(r, name, color).pack(side="right")

        # ---- activity + notes
        row2 = box(self.wrap)
        row2.pack(fill="x", pady=(0, 16))
        row2.grid_columnconfigure(0, weight=1, uniform="r")
        row2.grid_columnconfigure(1, weight=1, uniform="r")
        ac, ai, _ = self.section(row2, "Recent activity")
        ac.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        acts = s.data["activity"][:7]
        if not acts:
            empty_state(ai, "Nothing yet")
        for a in acts:
            r = box(ai)
            r.pack(fill="x", pady=3)
            label(r, a["text"], 13, wraplength=380, justify="left").pack(anchor="w")
            label(r, f"{a['by']} · {nice_ts(a['ts'])}", 11, color=MUTED).pack(anchor="w")

        nc, ni, _ = self.section(row2, "Who needs to improve",
                                 "Open improvement notes, highest priority first")
        nc.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        notes = s.open_notes()[:6] if self.app.role != "player" else []
        if self.app.role == "player":
            empty_state(ni, "Coach & managers only")
        elif not notes:
            empty_state(ni, "No open notes")
        for n in notes:
            r = box(ni)
            r.pack(fill="x", pady=3)
            chip(r, n["priority"], PRIORITY_COLORS[n["priority"]]).pack(side="left")
            label(r, f"{s.player_name(n['pid'])} — {n['area']}", 13, "bold").pack(side="left", padx=8)


# =================================================================== roster
class RosterPage(Page):
    title = "Roster"
    subtitle = "Everyone starts at 100 points · every 500 points earns a rank-up match"
    COLS = [(46, 0), (170, 1), (116, 0), (64, 0), (220, 0), (50, 0), (268, 0)]

    def build(self):
        if self.app.can("edit_roster"):
            button(self.actions, "+ Add player", self.add_dialog).pack(side="right")
        bar = box(self.body)
        bar.pack(fill="x", pady=(0, 10))
        self.search = entry(bar, "Search by name or ID…", width=280)
        self.search.pack(side="left")
        self._typing = None

        def typed(_e):  # wait until typing pauses, then filter once
            if self._typing:
                self.after_cancel(self._typing)
            self._typing = self.after(180, self.refresh)
        self.search.bind("<KeyRelease>", typed)
        self.filter = segmented(bar, ["All", "Players", "Managers", "Inactive"],
                                command=lambda v: self.refresh())
        self.filter.set("All")
        self.filter.pack(side="left", padx=12)
        self.count = label(bar, "", 12, color=MUTED)
        self.count.pack(side="right")

        panel = card(self.body)
        panel.pack(fill="both", expand=True)
        head = box(panel)
        head.pack(fill="x", padx=16, pady=(12, 4))
        self._cols(head)
        for i, t in enumerate(["", "Name", "Position", "Points", "Rank / next rank", "W-L", ""]):
            label(head, t.upper(), 11, "bold", MUTED).grid(row=0, column=i, sticky="w", padx=4)
        ctk.CTkFrame(panel, height=1, fg_color=BORDER).pack(fill="x", padx=16)
        self.list = FastScroll(panel, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=8, pady=8)

    def _cols(self, f):
        for i, (w, wt) in enumerate(self.COLS):
            f.grid_columnconfigure(i, minsize=w, weight=wt)

    def refresh(self):
        s = self.store
        clear(self.list)
        q = self.search.get().strip().lower()
        flt = self.filter.get()
        pts = s.all_points()
        people = sorted(s.players.values(), key=lambda p: (-pts.get(p["id"], 0), p["name"].lower()))
        rows = []
        for p in people:
            active = p.get("active", True)
            if flt == "Inactive" and active or flt != "Inactive" and not active:
                continue
            if flt == "Players" and p.get("role") == "manager":
                continue
            if flt == "Managers" and p.get("role") != "manager":
                continue
            if q and q not in p["name"].lower() and q not in str(p.get("student_id", "")).lower():
                continue
            rows.append(p)
        self.count.configure(text=f"{len(rows)} shown")
        if not rows:
            empty_state(self.list, "No one here yet",
                        "Click “+ Add player” to build your team" if self.app.can("edit_roster") else "")
            return
        for p in rows:
            self._row(p, pts.get(p["id"], s.settings["start_points"]))

    def _row(self, p, pts):
        s = self.store
        name, color, frac, need = s.rank_of(p["id"], pts)
        st = s.player_stats(p["id"])
        r = box(self.list)
        r.pack(fill="x", pady=1)
        self._cols(r)
        avatar(r, p["name"], color if p.get("role") != "manager" else "#A78BFA", 34).grid(
            row=0, column=0, padx=4, pady=8)
        nm = box(r)
        nm.grid(row=0, column=1, sticky="w", padx=4)
        label(nm, p["name"], 14, "bold").pack(anchor="w")
        sub = " · ".join(x for x in [f"Grade {p['grade']}" if p.get("grade") else "",
                                     f"ID {p['student_id']}" if p.get("student_id") else "",
                                     "Manager" if p.get("role") == "manager" else ""] if x)
        label(nm, sub or "—", 11, color=MUTED).pack(anchor="w")
        if p.get("role") == "manager":
            chip(r, "Manager", "#A78BFA").grid(row=0, column=2, sticky="w", padx=4)
            label(r, "—", 14, color=MUTED).grid(row=0, column=3, sticky="w", padx=4)
        else:
            pos_chip(r, s.position_of(p["id"])).grid(row=0, column=2, sticky="w", padx=4)
            label(r, str(pts), 16, "bold").grid(row=0, column=3, sticky="w", padx=4)
            rk = box(r)
            rk.grid(row=0, column=4, sticky="w", padx=4)
            top = box(rk)
            top.pack(anchor="w")
            chip(top, name, color).pack(side="left")
            req = s.open_rankup(p["id"])
            if req:
                chip(top, "Match " + req["status"], ACCENT_SOFT, text_color=ACCENT, size=10).pack(
                    side="left", padx=6)
            elif s.qualified(p["id"], pts):
                chip(top, "Qualified", LIME, size=10).pack(side="left", padx=6)
            else:
                label(top, f"  {need} to qualify", 11, color=MUTED).pack(side="left")
            progress(rk, frac, color, 180).pack(anchor="w", pady=(5, 0))
            label(r, f"{st['wins']}-{st['losses']}", 13).grid(row=0, column=5, sticky="w", padx=4)
        acts = box(r)
        acts.grid(row=0, column=6, sticky="e", padx=4)
        small_button(acts, "History", lambda: self.history(p["id"]), "ghost", width=62, height=30,
               font=F(12)).pack(side="left", padx=2)
        if (self.app.can("rank") and p.get("role") != "manager" and s.qualified(p["id"], pts)
                and not s.open_rankup(p["id"])):
            small_button(acts, "Rank-up", lambda: request_rankup_dialog(self, p["id"]), "primary", width=64,
                   height=30, font=F(12)).pack(side="left", padx=2)
        if self.app.can("adjust") and p.get("role") != "manager":
            small_button(acts, "± Pts", lambda: self.adjust(p["id"]), "ghost", width=56, height=30,
                   font=F(12)).pack(side="left", padx=2)
        if self.app.can("edit_roster"):
            small_button(acts, "Edit", lambda: self.edit_dialog(p["id"]), "ghost", width=52, height=30,
                   font=F(12)).pack(side="left", padx=2)

    # ---- dialogs
    def add_dialog(self):
        self._player_dialog(None)

    def edit_dialog(self, pid):
        self._player_dialog(pid)

    def _player_dialog(self, pid):
        s = self.store
        p = s.players.get(pid, {}) if pid else {}
        d = Dialog(self, "Edit player" if pid else "Add player", width=460)
        name = d.field("Full name", lambda m: entry(m, "e.g. Jordan Lee"))
        two = box(d.body)
        two.pack(fill="x")
        two.grid_columnconfigure((0, 1), weight=1, uniform="a")
        label(two, "Grade", 12, "bold", MUTED).grid(row=0, column=0, sticky="w", pady=(8, 4))
        label(two, "Student / OSIS ID", 12, "bold", MUTED).grid(row=0, column=1, sticky="w", padx=(10, 0), pady=(8, 4))
        grade = option(two, ["", "9", "10", "11", "12"], width=190)
        grade.grid(row=1, column=0, sticky="ew")
        sid = entry(two, "Optional")
        sid.grid(row=1, column=1, sticky="ew", padx=(10, 0))
        role = d.field("Role", lambda m: segmented(m, ["Player", "Manager"]))
        uname = d.field("KeyAuth username (links their login to this spot)",
                        lambda m: entry(m, "The username they sign in with"))
        disc = d.field("Discord user ID (managers — to ping them about rank-up requests)",
                       lambda m: entry(m, "Optional, e.g. 123456789012345678"))
        notes = d.field("Notes", lambda m: entry(m, "Optional"))
        active = ctk.CTkCheckBox(d.body, text="Active on the team", font=F(13))
        if pid:
            active.pack(anchor="w", pady=(12, 0))
        name.insert(0, p.get("name", ""))
        grade.set(p.get("grade", ""))
        sid.insert(0, p.get("student_id", ""))
        role.set("Manager" if p.get("role") == "manager" else "Player")
        uname.insert(0, p.get("username", ""))
        disc.insert(0, p.get("discord_id", ""))
        notes.insert(0, p.get("notes", ""))
        if p.get("active", True):
            active.select()
        err = label(d.body, "", 12, color=BAD)
        err.pack(fill="x", pady=(6, 0))

        def save():
            n = name.get().strip()
            if not n:
                return err.configure(text="Enter a name.")
            u = uname.get().strip()
            other = s.player_for_username(u)
            if u and other and other["id"] != pid:
                return err.configure(text=f"“{u}” is already linked to {other['name']}.")
            fields = dict(name=n, grade=grade.get(), student_id=sid.get().strip(),
                          role=role.get().lower(), notes=notes.get().strip(), username=u,
                          discord_id=disc.get().strip())
            d.destroy()
            if pid:
                fields["active"] = bool(active.get())
                self.act(s.update_player, pid, success="Saved", **fields)
            else:
                self.act(s.add_player, fields["name"], fields["grade"], fields["student_id"],
                         fields["role"], fields["notes"], fields["username"], fields["discord_id"],
                         success=f"Added {n} with {s.settings['start_points']} points")

        button(d.buttons, "Save", save).pack(side="right")
        button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
        if pid:
            button(d.buttons, "Remove", lambda: (d.destroy(), confirm(
                self, "Remove player?", f"This deletes {p['name']} and all of their points history. "
                "To keep history, untick “Active” instead.", "Remove", True,
                lambda: self.act(s.remove_player, pid, success="Removed"))), "danger").pack(side="left")
        if pid and s.has_pin(pid):
            button(d.buttons, "Reset PIN", lambda: (d.destroy(), confirm(
                self, "Reset PIN?", f"{p['name']} will make a new PIN the next time they sign in with the team code.",
                "Reset PIN", False, lambda: self.act(s.reset_pin, pid, success="PIN reset"))),
                "ghost").pack(side="left", padx=8)
        name.bind("<Return>", lambda e: save())
        d.show()
        name.focus_set()

    def adjust(self, pid):
        PointsDialog(self, [pid])

    def history(self, pid):
        HistoryDialog(self, pid)


class PointsDialog:
    def __init__(self, page: Page, pids):
        s = page.store
        d = Dialog(page, "Adjust points", width=460)
        who = ", ".join(s.player_name(p) for p in pids)
        label(d.body, who, 14, "bold").pack(fill="x")
        if len(pids) == 1:
            label(d.body, f"Currently {s.points(pids[0])} pts · {s.rank_of(pids[0])[0]}",
                  12, color=MUTED).pack(fill="x")
        amt = d.field("Points (use a minus sign to take away)", lambda m: entry(m, "e.g. 25 or -10"))
        quick = box(d.body)
        quick.pack(fill="x", pady=(8, 0))
        for v in (10, 25, 50, 100, -10, -25):
            button(quick, f"{v:+d}", lambda v=v: (amt.delete(0, "end"), amt.insert(0, str(v))),
                   "ghost", width=56, height=30, font=F(12)).pack(side="left", padx=(0, 6))
        reason = d.field("Reason", lambda m: entry(m, "e.g. Great sportsmanship"))
        err = label(d.body, "", 12, color=BAD)
        err.pack(fill="x", pady=(6, 0))

        def save():
            try:
                v = int(amt.get().strip())
            except ValueError:
                return err.configure(text="Points must be a whole number.")
            if v == 0:
                return err.configure(text="Points can't be 0.")
            r = reason.get().strip() or ("Bonus" if v > 0 else "Penalty")
            d.destroy()
            page.act(s.adjust_points, pids, v, r, success=f"{v:+d} points saved")
        button(d.buttons, "Apply", save).pack(side="right")
        button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
        amt.bind("<Return>", lambda e: save())
        d.show()
        amt.focus_set()


class HistoryDialog:
    def __init__(self, page: Page, pid):
        s = page.store
        p = s.players[pid]
        pts = s.points(pid)
        d = Dialog(page, p["name"], width=580, height=640)
        name, color, frac, need = s.rank_of(pid, pts)
        top = box(d.body)
        top.pack(fill="x")
        avatar(top, p["name"], color, 52).pack(side="left")
        info = box(top)
        info.pack(side="left", padx=14)
        label(info, f"{pts} points", 20, "bold").pack(anchor="w")
        rr = box(info)
        rr.pack(anchor="w", pady=(2, 0))
        chip(rr, name, color).pack(side="left")
        pos_chip(rr, s.position_of(pid)).pack(side="left", padx=6)
        nxt = s.level_name(s.rank_level(pid) + 1)[0]
        label(info, f"Qualified for a rank-up match to {nxt}" if s.qualified(pid, pts)
              else f"{need} points to qualify for {nxt}", 12,
              color=GOOD if s.qualified(pid, pts) else MUTED).pack(anchor="w", pady=(4, 0))
        st = s.player_stats(pid)
        grid = box(d.body)
        grid.pack(fill="x", pady=14)
        stats = [("Skill rating", str(s.skill(pid))), ("Matches", f"{st['wins']}-{st['losses']}"),
                 ("Scrimmages", f"{st['scr_wins']}-{st['scr_losses']}"),
                 ("Challenges", f"{st['ch_wins']}-{st['ch_losses']}"),
                 ("Practices", str(st["practices"])),
                 ("Unexcused", str(st["absences"])),
                 ("Excused", str(st["excused"])),
                 ("Quizzes passed", str(st["quizzes"])),
                 ("Videos watched", str(st["videos"]))]
        for i, (t, v) in enumerate(stats):
            grid.grid_columnconfigure(i % 4, weight=1, uniform="g")
            c = ctk.CTkFrame(grid, fg_color=SURFACE2, corner_radius=10)
            c.grid(row=i // 4, column=i % 4, sticky="ew", padx=3, pady=3)
            label(c, t.upper(), 10, "bold", MUTED).pack(anchor="w", padx=12, pady=(8, 0))
            label(c, v, 16, "bold").pack(anchor="w", padx=12, pady=(0, 8))
        hist = [h for h in s.data["rank_history"] if h["pid"] == pid][:3]
        if hist:
            label(d.body, "RANK HISTORY", 11, "bold", MUTED).pack(fill="x")
            for h in hist:
                how = "rank-up match" if h["kind"] == "match" else f"set by {h['by']}"
                label(d.body, f"{s.level_name(h['from'])[0]} → {s.level_name(h['to'])[0]} · {how} · "
                              f"{nice_ts(h['ts'])}" + (f" — {h['reason']}" if h.get("reason") else ""),
                      12, wraplength=520, justify="left").pack(fill="x", pady=1)
        label(d.body, "POINTS HISTORY", 11, "bold", MUTED).pack(fill="x")
        lst = FastScroll(d.body, fg_color=SURFACE2, corner_radius=10, height=260)
        lst.pack(fill="both", expand=True, pady=(6, 0))
        entries = [e for e in s.data["ledger"] if e["pid"] == pid][::-1]
        if not entries:
            empty_state(lst, "No points changes yet", f"Started at {s.settings['start_points']}")
        def row(e):
            r = box(lst)
            r.pack(fill="x", pady=3, padx=6)
            d_txt = f"{e['delta']:+d}" if e["delta"] else "0"
            d_col = GOOD if e["delta"] > 0 else BAD if e["delta"] < 0 else MUTED
            label(r, d_txt, 14, "bold", d_col, width=56).pack(side="left")
            col = box(r)
            col.pack(side="left", fill="x", expand=True)
            label(col, e["reason"], 13).pack(anchor="w")
            label(col, f"{nice_ts(e['ts'])} · by {e['by']}", 11, color=MUTED).pack(anchor="w")
        paged(lst, entries, row, first=40, step=80)
        button(d.buttons, "Close", d.destroy).pack(side="right")
        d.show()


# =================================================================== lineup
class LineupPage(Page):
    title = "Lineup & Challenges"
    subtitle = "PSAL format: 3 singles + 2 doubles · win a challenge to take a higher spot"

    def build(self):
        self.body.grid_columnconfigure(0, weight=3, uniform="c")
        self.body.grid_columnconfigure(1, weight=2, uniform="c")
        self.body.grid_rowconfigure(0, weight=1)
        can = self.app.can("lineup")
        if can:
            button(self.actions, "Save lineup", self.save).pack(side="right")
            button(self.actions, "Auto-fill by points", self.autofill, "ghost").pack(side="right", padx=8)

        left = FastScroll(self.body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.pickers: dict[str, list[PlayerPicker]] = {}
        self.pinfo: dict[str, list] = {}
        for pos in POSITIONS:
            c = card(left)
            c.pack(fill="x", pady=(0, 10))
            h = box(c)
            h.pack(fill="x", padx=18, pady=(14, 6))
            ctk.CTkFrame(h, width=10, height=10, corner_radius=5,
                         fg_color=POS_COLORS[pos]).pack(side="left")
            label(h, POSITION_LABELS[pos], 16, "bold").pack(side="left", padx=8)
            if pos == "S1":
                chip(h, "Manager training focus", "#A78BFA", size=10).pack(side="left", padx=4)
            row = box(c)
            row.pack(fill="x", padx=18, pady=(0, 14))
            self.pickers[pos], self.pinfo[pos] = [], []
            for i in range(POSITION_SIZE[pos]):
                col = box(row)
                col.pack(side="left", padx=(0, 14))
                pk = PlayerPicker(col, width=230, command=self._update_info)
                pk.pack(anchor="w")
                if not can:
                    pk.configure(state="disabled")
                info = label(col, "", 11, color=MUTED)
                info.pack(anchor="w", pady=(4, 0))
                self.pickers[pos].append(pk)
                self.pinfo[pos].append(info)
        if not can:
            self.readonly_note(left)

        right = box(self.body)
        right.grid(row=0, column=1, sticky="nsew")
        cc, ci, _ = self.section(right, "Challenge match",
                                 "If the challenger beats a player in a higher spot, they swap spots.")
        cc.pack(fill="x")
        label(ci, "CHALLENGER", 11, "bold", MUTED).pack(anchor="w")
        self.ch = PlayerPicker(ci, width=300, empty_label="Choose challenger", command=lambda: self._ch_preview())
        self.ch.pack(fill="x", pady=(4, 10))
        label(ci, "DEFENDER", 11, "bold", MUTED).pack(anchor="w")
        self.de = PlayerPicker(ci, width=300, empty_label="Choose defender", command=lambda: self._ch_preview())
        self.de.pack(fill="x", pady=(4, 10))
        self.winner = segmented(ci, ["Challenger won", "Defender won"])
        self.winner.set("Challenger won")
        self.winner.pack(fill="x", pady=(0, 10))
        self.ch_score = entry(ci, "Score (optional) e.g. 21-17, 21-19")
        self.ch_score.pack(fill="x")
        self.ch_prev = label(ci, "", 12, color=MUTED, wraplength=320, justify="left")
        self.ch_prev.pack(fill="x", pady=(8, 0))
        b = button(ci, "Record challenge", self.challenge)
        b.pack(fill="x", pady=(12, 0))
        if not self.app.can("challenge"):
            b.configure(state="disabled")

        hc, hi, _ = self.section(right, "Recent challenges")
        hc.pack(fill="both", expand=True, pady=(10, 0))
        self.ch_list = FastScroll(hi, fg_color="transparent", height=180)
        self.ch_list.pack(fill="both", expand=True)

    def _ch_preview(self):
        s = self.store
        c, d = self.ch.get(), self.de.get()
        if not c or not d or c == d:
            P = s.settings["points"]
            self.ch_prev.configure(text=f"Winner gets about +{P['challenge_win']} (more for beating a "
                                        f"stronger player), loser +{P['challenge_loss']}.")
            return
        pv = s.challenge_points(c, d)
        self.ch_prev.configure(text=f"Win chance: {s.player_name(c)} {pv['chance_c']:.0%} · "
                                    f"{s.player_name(d)} {1 - pv['chance_c']:.0%}\n"
                                    f"Winner gets +{pv['challenger']} ({s.player_name(c)}) or "
                                    f"+{pv['defender']} ({s.player_name(d)}); loser +{pv['loser']}")

    def _eligible(self):
        return [p for p in self.store.active_players() if p.get("role") != "manager"]

    def refresh(self):
        s = self.store
        people = self._eligible()
        for pos in POSITIONS:
            ids = s.data["lineup"].get(pos, [])
            for i, pk in enumerate(self.pickers[pos]):
                pk.set_players(people, keep=False)
                pk.set(ids[i] if i < len(ids) else None)
        self._update_info()
        self.ch.set_players(people)
        self.de.set_players(people)
        self._ch_preview()
        clear(self.ch_list)
        chs = s.data["challenges"][:12]
        if not chs:
            empty_state(self.ch_list, "No challenges yet")
        for c in chs:
            r = box(self.ch_list)
            r.pack(fill="x", pady=4)
            loser = c["defender"] if c["winner"] == c["challenger"] else c["challenger"]
            label(r, f"{s.player_name(c['winner'])} beat {s.player_name(loser)}", 13, "bold").pack(anchor="w")
            extra = f"Took {POSITION_LABELS[c['swap']['to']]}" if c.get("swap") else "No spot change"
            label(r, f"{nice_ts(c['ts'])} · {c.get('score') or 'no score'} · {extra}", 11,
                  color=MUTED).pack(anchor="w")

    def _update_info(self):
        s = self.store
        for pos in POSITIONS:
            for pk, info in zip(self.pickers[pos], self.pinfo[pos]):
                pid = pk.get()
                if pid:
                    pts = s.points(pid)
                    info.configure(text=f"{pts} pts · {s.rank_of(pid, pts)[0]}")
                else:
                    info.configure(text="Open spot")

    def _current(self):
        return {pos: [pk.get() for pk in self.pickers[pos] if pk.get()] for pos in POSITIONS}

    def save(self):
        lineup = self._current()
        flat = [p for ids in lineup.values() for p in ids]
        if len(flat) != len(set(flat)):
            return self.app.toast("A player can only be in one spot.", "error")
        self.act(self.store.set_lineup, lineup, success="Lineup saved")

    def autofill(self):
        ranked = [p["id"] for p, _ in self.store.leaderboard()]
        plan = {"S1": ranked[0:1], "S2": ranked[1:2], "S3": ranked[2:3],
                "D1": ranked[3:5], "D2": ranked[5:7]}
        for pos in POSITIONS:
            for i, pk in enumerate(self.pickers[pos]):
                pk.set(plan[pos][i] if i < len(plan[pos]) else None)
        self._update_info()
        self.app.toast("Filled by points — press Save lineup to keep it.")

    def challenge(self):
        c, d = self.ch.get(), self.de.get()
        if not c or not d:
            return self.app.toast("Pick both players.", "error")
        if c == d:
            return self.app.toast("Pick two different players.", "error")
        winner = c if self.winner.get() == "Challenger won" else d
        score = self.ch_score.get().strip()
        self.ch_score.delete(0, "end")

        def msg(swap):
            if swap:
                return f"{self.store.player_name(c)} takes {POSITION_LABELS[swap['to']]}!"
            return "Challenge recorded"
        self.act(self.store.record_challenge, c, d, winner, score, success=msg)


# ================================================================== matches
class MatchesPage(Page):
    title = "PSAL Matches"
    subtitle = "Record a match and points are awarded automatically"

    def build(self):
        self.tabs = segmented(self.actions, ["Record match", "Match history"], command=self._tab)
        self.tabs.pack(side="right")
        self.form = FastScroll(self.body, fg_color="transparent")
        self.hist = FastScroll(self.body, fg_color="transparent")
        self._build_form()
        self.tabs.set("Record match" if self.app.can("match") else "Match history")
        self._tab(self.tabs.get())

    def _tab(self, v):
        self.form.pack_forget()
        self.hist.pack_forget()
        (self.form if v == "Record match" else self.hist).pack(fill="both", expand=True)
        self.refresh()

    def _build_form(self):
        c, inner, _ = self.section(self.form, "Match details")
        c.pack(fill="x")
        top = box(inner)
        top.pack(fill="x")
        for i, t in enumerate(["DATE", "OPPONENT SCHOOL", "HOME / AWAY"]):
            label(top, t, 11, "bold", MUTED).grid(row=0, column=i, sticky="w", padx=(0, 12))
        self.day = entry(top, "YYYY-MM-DD", width=150)
        self.day.insert(0, date.today().isoformat())
        self.day.grid(row=1, column=0, padx=(0, 12), pady=(4, 0))
        self.opp = entry(top, "e.g. Stuyvesant HS", width=280)
        self.opp.grid(row=1, column=1, padx=(0, 12), pady=(4, 0))
        self.home = segmented(top, ["Home", "Away"])
        self.home.set("Home")
        self.home.grid(row=1, column=2, pady=(4, 0))

        rc, ri, _ = self.section(self.form, "Results",
                                 "Players are filled from your saved lineup — change them if someone subbed in.")
        rc.pack(fill="x", pady=(12, 0))
        self.rows = {}
        for pos in POSITIONS:
            r = ctk.CTkFrame(ri, fg_color=SURFACE2, corner_radius=12)
            r.pack(fill="x", pady=4)
            vbar(r, POS_COLORS[pos]).pack(
                side="left", fill="y", padx=(10, 12), pady=10)
            label(r, POSITION_LABELS[pos], 13, "bold", width=104).pack(side="left")
            pk_frame = box(r)
            pk_frame.pack(side="left", padx=6, pady=10)
            pks = [PlayerPicker(pk_frame, width=170).pack(side="left", padx=(0, 6))
                   for _ in range(POSITION_SIZE[pos])]
            res = segmented(r, ["Win", "Loss", "Not played"], command=lambda v: self._preview())
            res.set("Win")
            res.pack(side="left", padx=8)
            sc = entry(r, "Score e.g. 21-15, 21-18", width=180)
            sc.pack(side="left", padx=(0, 10))
            self.rows[pos] = (pks, res, sc)

        bottom = box(self.form)
        bottom.pack(fill="x", pady=12)
        self.preview = label(bottom, "", 14, "bold")
        self.preview.pack(side="left")
        self.save_btn = button(bottom, "Save match & award points", self.submit, height=42)
        self.save_btn.pack(side="right")
        button(bottom, "Reset from lineup", self._fill_from_lineup, "ghost", height=42).pack(side="right", padx=8)
        if not self.app.can("match"):
            self.save_btn.configure(state="disabled")
            self.readonly_note(bottom)

    def _fill_from_lineup(self):
        people = [p for p in self.store.active_players() if p.get("role") != "manager"]
        for pos, (pks, res, sc) in self.rows.items():
            ids = self.store.data["lineup"].get(pos, [])
            for i, pk in enumerate(pks):
                pk.set_players(people, keep=False)
                pk.set(ids[i] if i < len(ids) else None)
        self._preview()

    def _preview(self):
        played = [r for r in self.rows.values() if r[1].get() != "Not played"]
        wins = sum(1 for r in played if r[1].get() == "Win")
        if not played:
            return self.preview.configure(text="No positions played", text_color=MUTED)
        won = wins > len(played) / 2
        self.preview.configure(text=f"Team {'WINS' if won else 'LOSES'} {wins}-{len(played) - wins}",
                               text_color=GOOD if won else BAD)

    def refresh(self):
        if self.tabs.get() == "Record match":
            people = [p for p in self.store.active_players() if p.get("role") != "manager"]
            first = not getattr(self, "_filled", False)
            for pos, (pks, res, sc) in self.rows.items():
                for pk in pks:
                    pk.set_players(people, keep=True)
            if first:
                self._fill_from_lineup()
                self._filled = True
            self._preview()
        else:
            self._history()

    def submit(self):
        s = self.store
        try:
            day = date.fromisoformat(self.day.get().strip()).isoformat()
        except ValueError:
            return self.app.toast("Date must look like 2026-10-15.", "error")
        opp = self.opp.get().strip()
        if not opp:
            return self.app.toast("Enter the opponent school.", "error")
        results, used = {}, []
        P = s.settings["points"]
        lines = []
        for pos, (pks, res, sc) in self.rows.items():
            ids = [pk.get() for pk in pks if pk.get()]
            played = res.get() != "Not played"
            if played and len(ids) != POSITION_SIZE[pos]:
                return self.app.toast(f"Pick {'both players' if POSITION_SIZE[pos] == 2 else 'a player'} "
                                      f"for {POSITION_LABELS[pos]} (or mark it Not played).", "error")
            used += ids if played else []
            results[pos] = {"players": ids if played else [], "won": res.get() == "Win",
                            "score": sc.get().strip(), "played": played}
            if played:
                pts = P["win"][pos] if res.get() == "Win" else P["loss"]
                lines.append(f"{POSITION_LABELS[pos]}: {' & '.join(s.player_name(i) for i in ids)} "
                             f"{'won' if res.get() == 'Win' else 'lost'} → +{pts}")
        if len(used) != len(set(used)):
            return self.app.toast("A player is listed in two positions.", "error")
        if not used:
            return self.app.toast("Mark at least one position as played.", "error")
        played = [r for r in results.values() if r["played"]]
        wins = sum(r["won"] for r in played)
        if wins > len(played) / 2 and P["team_win_bonus"]:
            lines.append(f"Team win bonus: +{P['team_win_bonus']} each")

        def go():
            self.act(s.record_match, day, opp, self.home.get() == "Home", results,
                     success=lambda won: f"Match saved — {'WIN' if won else 'loss'} vs {opp}")
            self.opp.delete(0, "end")
            for pks, res, sc in self.rows.values():
                sc.delete(0, "end")
                res.set("Win")
            self._preview()
        confirm(self, f"Save match vs {opp}?", "\n".join(lines), "Save & award points", on_ok=go)

    def _history(self):
        s = self.store
        clear(self.hist)
        ms = s.data["matches"]
        w, l = s.team_record()
        label(self.hist, f"Season record {w}-{l}", 15, "bold").pack(anchor="w", pady=(0, 8))
        if not ms:
            empty_state(self.hist, "No matches yet", "Record your first PSAL match")
        for m in ms:
            c = card(self.hist)
            c.pack(fill="x", pady=5)
            h = box(c)
            h.pack(fill="x", padx=18, pady=(14, 6))
            chip(h, "W" if m["team_won"] else "L", GOOD[1] if m["team_won"] else BAD[1], size=13).pack(side="left")
            label(h, f"  vs {m['opponent']}", 16, "bold").pack(side="left")
            label(h, f"  {m['score']} · {'Home' if m.get('home') else 'Away'} · {nice_date(m['date'])}",
                  12, color=MUTED).pack(side="left")
            if self.app.can("delete"):
                small_button(h, "Delete", lambda mid=m["id"], o=m["opponent"]: confirm(
                    self, "Delete match?", f"This removes the match vs {o} and takes back the points it gave.",
                    "Delete", True, lambda: self.act(s.delete_match, mid, success="Match deleted")),
                    "danger", width=70, height=28, font=F(12)).pack(side="right")
            g = box(c)
            g.pack(fill="x", padx=18, pady=(0, 14))
            for pos in POSITIONS:
                r = m["results"].get(pos)
                if not r:
                    continue
                row = box(g)
                row.pack(fill="x", pady=1)
                label(row, POSITION_LABELS[pos], 12, "bold", MUTED, width=100).pack(side="left")
                if not r.get("played", True):
                    label(row, "Not played", 12, color=MUTED).pack(side="left")
                    continue
                label(row, "WIN" if r["won"] else "LOSS", 12, "bold", GOOD if r["won"] else BAD,
                      width=44).pack(side="left")
                label(row, " & ".join(s.player_name(p) for p in r["players"]), 12).pack(side="left")
                if r.get("score"):
                    label(row, f"  ({r['score']})", 12, color=MUTED).pack(side="left")


# ================================================================= practice
class PracticePage(Page):
    title = "Practice & Points"
    subtitle = "Attendance (unexcused absences lose points) and practice scrimmages (losers lose points)"
    STATUSES = ["Present", "Absent", "Excused"]

    def build(self):
        self.body.grid_columnconfigure(0, weight=3, uniform="c")
        self.body.grid_columnconfigure(1, weight=2, uniform="c")
        self.body.grid_rowconfigure(0, weight=1)
        self.state: dict[str, list] = {}   # pid -> [status, reason]
        self.rows: dict[str, tuple] = {}
        self._roster_sig = None
        can = self.app.can("practice")

        left = card(self.body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        head = box(left)
        head.pack(fill="x", padx=20, pady=(16, 10))
        label(head, "Practice", 16, "bold").pack(side="left")
        self.tab = segmented(head, ["Attendance", "Scrimmage"], command=self._tab)
        self.tab.set("Attendance")
        self.tab.pack(side="right")

        # ---------------- attendance
        self.att = box(left)
        bar = box(self.att)
        bar.pack(fill="x")
        self.day = entry(bar, "YYYY-MM-DD", width=130)
        self.day.insert(0, date.today().isoformat())
        self.day.pack(side="left")
        self.day.bind("<Return>", lambda e: self.load_day())
        button(bar, "Load day", self.load_day, "ghost", width=84, height=34).pack(side="left", padx=6)
        button(bar, "Everyone present", self.all_present, "ghost", height=34).pack(side="left")
        self.day_note = label(bar, "", 11, color=MUTED)
        self.day_note.pack(side="right")
        label(self.att, "Absent = unexcused (loses points). Excused needs a reason and costs nothing.",
              11, color=MUTED).pack(anchor="w", pady=(8, 0))
        self.list = FastScroll(self.att, fg_color=SURFACE2, corner_radius=10)
        self.list.pack(fill="both", expand=True, pady=8)
        foot = box(self.att)
        foot.pack(fill="x")
        self.att_preview = label(foot, "", 13, "bold")
        self.att_preview.pack(side="left")
        self.att_btn = button(foot, "Save attendance", self.save_attendance, height=40)
        self.att_btn.pack(side="right")

        # ---------------- scrimmage
        self.scr = box(left)
        label(self.scr, "TYPE", 11, "bold", MUTED).pack(anchor="w")
        self.scr_type = segmented(self.scr, ["Singles", "Doubles"], command=lambda v: self._scr_layout())
        self.scr_type.set("Singles")
        self.scr_type.pack(anchor="w", pady=(4, 14))
        sides = box(self.scr)
        sides.pack(fill="x")
        sides.grid_columnconfigure((0, 2), weight=1, uniform="s")
        self.side_boxes, self.side_pk = [], []
        for col, name in ((0, "SIDE A"), (2, "SIDE B")):
            panel = ctk.CTkFrame(sides, fg_color=SURFACE2, corner_radius=12)
            panel.grid(row=0, column=col, sticky="nsew")
            label(panel, name, 11, "bold", MUTED).pack(anchor="w", padx=14, pady=(12, 4))
            pks = [PlayerPicker(panel, width=220, empty_label="Choose player",
                                command=lambda: self._scr_preview()) for _ in range(2)]
            for pk in pks:
                pk.pack(fill="x", padx=14, pady=(0, 8))
            self.side_boxes.append(panel)
            self.side_pk.append(pks)
        label(sides, "vs", 16, "bold", MUTED, anchor="center", width=40).grid(row=0, column=1)
        label(self.scr, "RESULT", 11, "bold", MUTED).pack(anchor="w", pady=(14, 0))
        self.scr_win = segmented(self.scr, ["Side A won", "Side B won"])
        self.scr_win.set("Side A won")
        self.scr_win.pack(fill="x", pady=(4, 10))
        self.scr_score = entry(self.scr, "Score (optional) e.g. 21-18")
        self.scr_score.pack(fill="x")
        self.scr_preview = label(self.scr, "", 13, "bold")
        self.scr_preview.pack(anchor="w", pady=(12, 0))
        self.scr_btn = button(self.scr, "Record scrimmage", self.save_scrimmage, height=40)
        self.scr_btn.pack(fill="x", pady=(10, 0))
        self._scr_layout()
        self._tab("Attendance")

        if not can:
            for b in (self.att_btn, self.scr_btn):
                b.configure(state="disabled")

        # ---------------- right column
        right = FastScroll(self.body, fg_color="transparent", corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        hc, hi, hh = self.section(right, "Recent")
        hc.pack(fill="x", padx=(0, 6))
        self.hist_tab = segmented(hh, ["Practices", "Scrimmages"], command=lambda v: self._history())
        self.hist_tab.set("Practices")
        self.hist_tab.pack(anchor="w", pady=(8, 0))
        self.hist = box(hi)
        self.hist.pack(fill="x")
        rc, self.rules, _ = self.section(right, "How points are earned & lost",
                                         "Coaches can change these numbers in Settings.")
        rc.pack(fill="x", padx=(0, 6), pady=(10, 0))

    # ------------------------------------------------------------- helpers
    def _tab(self, v):
        self.att.pack_forget()
        self.scr.pack_forget()
        (self.att if v == "Attendance" else self.scr).pack(fill="both", expand=True, padx=20, pady=(0, 18))

    def _scr_layout(self):
        doubles = self.scr_type.get() == "Doubles"
        for pks in self.side_pk:
            if doubles:
                pks[1].pack(fill="x", padx=14, pady=(0, 8))
            else:
                pks[1].menu.pack_forget()
                pks[1].set(None)
        self._scr_preview()

    def _scr_preview(self):
        """Skill-based (Valorant-style) points: shows what each result is worth."""
        s = self.store
        P = s.settings["points"]
        size = 2 if self.scr_type.get() == "Doubles" else 1
        each = " each" if size == 2 else ""
        a = [pk.get() for pk in self.side_pk[0][:size]]
        b = [pk.get() for pk in self.side_pk[1][:size]]
        if None in a or None in b or len(set(a + b)) != len(a + b):
            self.scr_preview.configure(text=f"Even game: winners +{P['scrimmage_win']}{each}, losers "
                                            f"−{abs(P['scrimmage_loss'])}{each}. Pick players to see "
                                            "skill-based points.")
            return
        pv = s.scrimmage_points(a, b)
        ca = pv["chance_a"]
        self.scr_preview.configure(text=(
            f"Win chance: A {ca:.0%} · B {1 - ca:.0%}\n"
            f"If A wins: A +{pv['A']['gain']}, B −{pv['A']['loss']}{each}\n"
            f"If B wins: B +{pv['B']['gain']}, A −{pv['B']['loss']}{each}"))

    def _people(self):
        return [p for p in self.store.active_players() if p.get("role") != "manager"]

    def _capture(self):
        for pid, (seg, reason) in self.rows.items():
            self.state[pid] = [seg.get(), reason.get().strip()]

    def _build_rows(self):
        s = self.store
        clear(self.list)
        self.rows = {}
        people = self._people()
        if not people:
            empty_state(self.list, "No players yet")
        for p in people:
            st = self.state.setdefault(p["id"], ["Present", ""])
            r = box(self.list)
            r.pack(fill="x", pady=3, padx=6)
            label(r, p["name"], 13, "bold", width=150).pack(side="left")
            label(r, f"{s.points(p['id'])} pts", 11, color=MUTED, width=56).pack(side="left")
            seg = FastToggle(r, self.STATUSES)
            seg.set(st[0])
            seg.pack(side="left", padx=8)
            rb = box(r)  # reason panel: only shown for Excused (keeps 40+ rows light)
            label(rb, "Reason:", 12, color=MUTED).pack(side="left", padx=(4, 6))
            sc = K.scale_of(rb)
            reason = tk.Entry(rb, font=K.NF(13, "normal", sc), relief="flat", bd=0, highlightthickness=1,
                              bg=K.resolve(SURFACE), fg=K.resolve(TEXT), insertbackground=K.resolve(TEXT),
                              highlightbackground=K.resolve(BORDER), highlightcolor=K.resolve(ACCENT))
            reason.pack(side="left", fill="x", expand=True, ipady=round(5 * sc))
            if st[1]:
                reason.insert(0, st[1])
            seg._cmd = lambda v, e=reason: self._status_changed(e, v)
            self._status_changed(reason, st[0], update=False)
            self.rows[p["id"]] = (seg, reason)
        self._att_preview()

    def _status_changed(self, reason_entry, value, update=True):
        if value == "Excused":
            reason_entry.master.pack(side="left", fill="x", expand=True)
        else:
            reason_entry.master.pack_forget()
        if update:
            self._att_preview()

    def _att_preview(self):
        P = self.store.settings["points"]
        vals = [seg.get() for seg, _ in self.rows.values()]
        pr, ab, ex = vals.count("Present"), vals.count("Absent"), vals.count("Excused")
        txt = f"{pr} present (+{P['practice']})"
        if ab:
            txt += f"  ·  {ab} unexcused (−{abs(P['absence'])})"
        if ex:
            txt += f"  ·  {ex} excused (0)"
        self.att_preview.configure(text=txt, text_color=BAD if ab else TEXT)

    def _parse_day(self):
        try:
            return date.fromisoformat(self.day.get().strip()).isoformat()
        except ValueError:
            self.app.toast("Date must look like 2026-10-15.", "error")
            return None

    def load_day(self):
        day = self._parse_day()
        if not day:
            return
        rec = self.store.attendance_for(day)
        self.state = {}
        if rec:
            for pid in rec["present"]:
                self.state[pid] = ["Present", ""]
            for pid in rec["absent"]:
                self.state[pid] = ["Absent", ""]
            for pid, why in rec["excused"].items():
                self.state[pid] = ["Excused", why]
            self.day_note.configure(text="Already saved — saving again replaces it", text_color=WARN)
        else:
            self.day_note.configure(text="New practice day", text_color=MUTED)
        self._build_rows()

    def all_present(self):
        for seg, reason in self.rows.values():
            seg.set("Present")
            self._status_changed(reason, "Present", update=False)
        self._att_preview()

    # -------------------------------------------------------------- refresh
    def refresh(self):
        s = self.store
        if self.rows:
            self._capture()
        sig = tuple(p["id"] for p in self._people())
        if sig != self._roster_sig:
            self._roster_sig = sig
            if not self.state:
                self.load_day()
            else:
                self._build_rows()
        else:
            # just refresh the points shown next to names
            self._build_rows()
        people = self._people()
        for pks in self.side_pk:
            for pk in pks:
                pk.set_players(people)
        self._scr_layout()

        P = s.settings["points"]
        clear(self.rules)
        rows = [("Start", f"{s.settings['start_points']} points for everyone", TEXT),
                ("Rank-up match", f"Qualify every {s.settings['rank_step']} points", TEXT),
                ("Practice attendance", f"+{P['practice']}", GOOD),
                ("Unexcused absence", f"−{abs(P['absence'])}", BAD),
                ("Excused absence (with reason)", "0", MUTED),
                ("Scrimmage win", f"+{P['scrimmage_win']}", GOOD),
                ("Scrimmage loss", f"−{abs(P['scrimmage_loss'])}", BAD)]
        rows += [(f"{POSITION_LABELS[p]} match win", f"+{P['win'][p]}", GOOD) for p in POSITIONS]
        rows += [("Match loss (played)", f"+{P['loss']}", GOOD),
                 ("Team win bonus", f"+{P['team_win_bonus']} each", GOOD),
                 ("Challenge win / loss", f"+{P['challenge_win']} / +{P['challenge_loss']}", GOOD)]
        for k, v, color in rows:
            r = box(self.rules)
            r.pack(fill="x", pady=1)
            label(r, k, 12, color=MUTED).pack(side="left")
            label(r, v, 12, "bold", color).pack(side="right")
        self._history()

    def _history(self):
        s = self.store
        clear(self.hist)
        can_del = self.app.can("delete")
        if self.hist_tab.get() == "Practices":
            recs = s.data["attendance"][:15]
            if not recs:
                empty_state(self.hist, "No practices saved yet")
            for a in recs:
                r = box(self.hist)
                r.pack(fill="x", pady=4)
                top = box(r)
                top.pack(fill="x")
                label(top, nice_date(a["date"]), 13, "bold").pack(side="left")
                if can_del:
                    small_button(top, "Undo", lambda aid=a["id"], dd=a["date"]: confirm(
                        self, "Undo this practice?", f"Removes attendance for {nice_date(dd)} and "
                        "reverses its points.", "Undo", True,
                        lambda: self.act(s.delete_attendance, aid, success="Practice removed")),
                        "danger", width=54, height=24, font=F(11)).pack(side="right")
                label(r, f"{len(a['present'])} present · {len(a['absent'])} unexcused · "
                         f"{len(a['excused'])} excused", 11, color=MUTED).pack(anchor="w")
                if a["absent"]:
                    label(r, "Unexcused: " + ", ".join(s.player_name(p) for p in a["absent"]), 11,
                          color=BAD, wraplength=330, justify="left").pack(anchor="w")
                for pid, why in a["excused"].items():
                    label(r, f"Excused: {s.player_name(pid)} — {why}", 11, color=MUTED,
                          wraplength=330, justify="left").pack(anchor="w")
        else:
            recs = s.data["scrimmages"][:15]
            if not recs:
                empty_state(self.hist, "No scrimmages yet")
            for x in recs:
                win, lose = (x["a"], x["b"]) if x["winner"] == "A" else (x["b"], x["a"])
                r = box(self.hist)
                r.pack(fill="x", pady=4)
                top = box(r)
                top.pack(fill="x")
                label(top, " & ".join(s.player_name(p) for p in win), 13, "bold", GOOD).pack(side="left")
                label(top, "  beat  ", 12, color=MUTED).pack(side="left")
                label(top, " & ".join(s.player_name(p) for p in lose), 13, "bold", BAD).pack(side="left")
                if can_del:
                    small_button(top, "Undo", lambda sid=x["id"]: self.act(
                        s.delete_scrimmage, sid, success="Scrimmage removed"),
                        "danger", width=54, height=24, font=F(11)).pack(side="right")
                label(r, f"{nice_ts(x['ts'])}" + (f" · {x['score']}" if x.get("score") else ""), 11,
                      color=MUTED).pack(anchor="w")

    # -------------------------------------------------------------- actions
    def save_attendance(self):
        s = self.store
        day = self._parse_day()
        if not day:
            return
        self._capture()
        present, absent, excused = [], [], {}
        for pid in self.rows:
            status, why = self.state[pid]
            if status == "Present":
                present.append(pid)
            elif status == "Absent":
                absent.append(pid)
            else:
                if not why:
                    return self.app.toast(f"Add a reason for {s.player_name(pid)}'s excused absence "
                                          "(or mark them Absent).", "error")
                excused[pid] = why
        P = s.settings["points"]
        lines = [f"{len(present)} present → +{P['practice']} each"]
        if absent:
            lines.append(f"{len(absent)} unexcused → −{abs(P['absence'])} each: "
                         + ", ".join(s.player_name(p) for p in absent))
        if excused:
            lines.append(f"{len(excused)} excused → no change")
        title = f"Save attendance for {nice_date(day)}?"
        if s.attendance_for(day):
            title = f"Replace attendance for {nice_date(day)}?"
            lines.append("This day was already saved — the old points will be undone first.")

        def go():
            self.act(s.record_attendance, day, present, absent, excused,
                     success=f"Attendance saved for {nice_date(day)}")
            self.day_note.configure(text="Saved", text_color=GOOD)
        confirm(self, title, "\n".join(lines), "Save", on_ok=go)

    def save_scrimmage(self):
        s = self.store
        size = 2 if self.scr_type.get() == "Doubles" else 1
        a = [pk.get() for pk in self.side_pk[0][:size]]
        b = [pk.get() for pk in self.side_pk[1][:size]]
        if None in a or None in b:
            return self.app.toast(f"Pick {size * 2} players.", "error")
        if len(set(a + b)) != len(a + b):
            return self.app.toast("Each player can only be on one side once.", "error")
        winner = "A" if self.scr_win.get() == "Side A won" else "B"
        score = self.scr_score.get().strip()
        self.act(s.record_scrimmage, a, b, winner, score, success="Scrimmage recorded")
        self.scr_score.delete(0, "end")
        for pks in self.side_pk:
            for pk in pks:
                pk.set(None)


# ============================================================== leaderboard
class LeaderboardPage(Page):
    title = "Leaderboard"
    subtitle = "Bronze → Silver → Gold → Platinum → Diamond → Champion → Legend"

    def build(self):
        button(self.actions, "Export CSV", self.export, "ghost").pack(side="right")
        self.filter = segmented(self.actions, ["All", "Singles", "Doubles", "Bench"],
                                command=lambda v: self.refresh())
        self.filter.set("All")
        self.filter.pack(side="right", padx=10)
        self.podium = box(self.body)
        self.podium.pack(fill="x")
        panel = card(self.body)
        panel.pack(fill="both", expand=True, pady=(14, 0))
        self.list = FastScroll(panel, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self):
        s = self.store
        f = self.filter.get()
        board = s.leaderboard()

        def keep(p):
            pos = s.position_of(p["id"])
            return (f == "All" or f == "Singles" and pos in ("S1", "S2", "S3")
                    or f == "Doubles" and pos in ("D1", "D2") or f == "Bench" and pos is None)
        board = [(p, pts) for p, pts in board if keep(p)]
        clear(self.podium)
        for i in range(3):
            self.podium.grid_columnconfigure(i, weight=1, uniform="p")
        medal = ["#F5B83D", "#AEB7C4", "#CD7F32"]
        for col, idx in ((1, 0), (0, 1), (2, 2)):
            c = card(self.podium)
            c.grid(row=0, column=col, sticky="nsew", padx=6, pady=(0 if idx == 0 else 18, 0))
            if idx >= len(board):
                label(c, "—", 18, "bold", MUTED, anchor="center").pack(pady=40)
                continue
            p, pts = board[idx]
            name, color, frac, need = s.rank_of(p["id"], pts)
            chip(c, f"#{idx + 1}", medal[idx], size=13).pack(pady=(16, 6))
            avatar(c, p["name"], color, 58 if idx == 0 else 48).pack()
            label(c, p["name"], 16, "bold", anchor="center").pack(pady=(8, 0))
            label(c, f"{pts} pts", 22 if idx == 0 else 18, "bold", anchor="center").pack()
            chip(c, name, color).pack(pady=(4, 6))
            progress(c, frac, color, 150).pack(pady=(0, 18))

        clear(self.list)
        if not board:
            empty_state(self.list, "No players to show")
        for i, (p, pts) in enumerate(board, 1):
            name, color, frac, need = s.rank_of(p["id"], pts)
            r = ctk.CTkFrame(self.list, fg_color=SURFACE2 if i % 2 else "transparent", corner_radius=10)
            r.pack(fill="x", pady=1)
            label(r, f"{i}", 15, "bold", MUTED, width=36, anchor="center").pack(side="left", padx=(8, 4), pady=10)
            avatar(r, p["name"], color, 32).pack(side="left", padx=6)
            label(r, p["name"], 14, "bold", width=200).pack(side="left", padx=6)
            pos_chip(r, s.position_of(p["id"])).pack(side="left", padx=6)
            label(r, f"{pts} pts", 14, "bold").pack(side="right", padx=16)
            label(r, "Qualified!" if s.qualified(p["id"], pts) else f"{need} to qualify", 11,
                  color=GOOD if s.qualified(p["id"], pts) else MUTED, width=92,
                  anchor="e").pack(side="right", padx=6)
            progress(r, frac, color, 160).pack(side="right", padx=6)
            chip(r, name, color).pack(side="right", padx=6)

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"leaderboard-{date.today()}.csv")
        if path:
            self.store.export_csv(path)
            self.app.toast("Leaderboard exported", "success")


# ======================================================= manager training
class TrainingPage(Page):
    title = "Manager Training · 1st Singles"
    subtitle = "A separate point track managers use to develop the team's best player"
    scroll = True

    def build(self):
        w = box(self.body)
        w.pack(fill="both", expand=True, padx=12)
        self.hero = card(w)
        self.hero.pack(fill="x")

        row = box(w)
        row.pack(fill="x", pady=14)
        row.grid_columnconfigure(0, weight=1, uniform="t")
        row.grid_columnconfigure(1, weight=1, uniform="t")

        lc, li, _ = self.section(row, "Log a training session",
                                 "Training points are separate from team points.")
        lc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        g = box(li)
        g.pack(fill="x")
        g.grid_columnconfigure((0, 1), weight=1, uniform="g")
        label(g, "MANAGER", 11, "bold", MUTED).grid(row=0, column=0, sticky="w")
        label(g, "FOCUS", 11, "bold", MUTED).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.mgr = option(g, ["—"], width=200)
        self.mgr.grid(row=1, column=0, sticky="ew", pady=(4, 10))
        self.focus = option(g, TRAINING_FOCUS, width=200, command=lambda v: self._suggest())
        self.focus.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(4, 10))
        label(g, "MINUTES", 11, "bold", MUTED).grid(row=2, column=0, sticky="w")
        label(g, "TRAINING POINTS", 11, "bold", MUTED).grid(row=2, column=1, sticky="w", padx=(10, 0))
        self.minutes = entry(g, "60")
        self.minutes.insert(0, "60")
        self.minutes.grid(row=3, column=0, sticky="ew", pady=(4, 10))
        self.minutes.bind("<KeyRelease>", lambda e: self._suggest())
        self.tpoints = entry(g, "auto")
        self.tpoints.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=(4, 10))
        label(li, "EFFORT", 11, "bold", MUTED).pack(anchor="w")
        self.effort = segmented(li, ["1", "2", "3", "4", "5"], command=lambda v: self._suggest())
        self.effort.set("4")
        self.effort.pack(fill="x", pady=(4, 10))
        label(li, "NOTES", 11, "bold", MUTED).pack(anchor="w")
        self.tnotes = ctk.CTkTextbox(li, height=80, corner_radius=10, fg_color=SURFACE2,
                                     border_width=1, border_color=BORDER, font=F(13), text_color=TEXT)
        self.tnotes.pack(fill="x", pady=(4, 10))
        self.log_btn = button(li, "Log session", self.log, height=40)
        self.log_btn.pack(fill="x")
        self._suggest()

        sc, si, _ = self.section(row, "Skill ratings", "Rate 1–10. Saved with the next session or on its own.")
        sc.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.sliders = {}
        for sk in SKILLS:
            r = box(si)
            r.pack(fill="x", pady=4)
            label(r, sk, 13, width=90).pack(side="left")
            val = label(r, "5", 13, "bold", width=26, anchor="e")
            val.pack(side="right")
            sl = ctk.CTkSlider(r, from_=1, to=10, number_of_steps=9, height=16,
                               button_color=ACCENT, progress_color=ACCENT, fg_color=SURFACE2,
                               command=lambda v, lab=val: lab.configure(text=str(int(v))))
            sl.pack(side="left", fill="x", expand=True, padx=8)
            self.sliders[sk] = (sl, val)
        self.skill_btn = button(si, "Save ratings", self.save_skills, "ghost")
        self.skill_btn.pack(fill="x", pady=(10, 0))

        hc, self.hist, _ = self.section(w, "Session history")
        hc.pack(fill="x", pady=(0, 14))

        if not self.app.can("training"):
            for b in (self.log_btn, self.skill_btn):
                b.configure(state="disabled")

    def _suggest(self):
        try:
            mins = int(self.minutes.get() or 0)
        except ValueError:
            mins = 0
        pts = round(mins * 0.5 + int(self.effort.get()) * 5)
        self.tpoints.delete(0, "end")
        self.tpoints.insert(0, str(pts))

    def refresh(self):
        s = self.store
        pid = s.training_player()
        clear(self.hero)
        hero = box(self.hero)
        hero.pack(fill="x", padx=22, pady=20)
        if not pid:
            label(hero, "No 1st singles player yet", 18, "bold").pack(anchor="w")
            label(hero, "Set one in Lineup, or choose a training player here.", 13, color=MUTED).pack(anchor="w")
        else:
            tp = s.training_points()
            lvl, frac, need = s.training_level(tp)
            avatar(hero, s.player_name(pid), "#A78BFA", 64).pack(side="left")
            col = box(hero)
            col.pack(side="left", padx=18)
            r = box(col)
            r.pack(anchor="w")
            label(r, s.player_name(pid), 22, "bold").pack(side="left")
            pos_chip(r, s.position_of(pid)).pack(side="left", padx=10)
            label(col, f"Team points: {s.points(pid)} · {s.rank_of(pid)[0]}", 12,
                  color=MUTED).pack(anchor="w", pady=(2, 8))
            pr = box(col)
            pr.pack(anchor="w")
            progress(pr, frac, "#A78BFA", 280).pack(side="left")
            label(pr, f"  {need} to next level", 12, color=MUTED).pack(side="left")
            right = box(hero)
            right.pack(side="right")
            label(right, "TRAINING POINTS", 11, "bold", MUTED, anchor="e").pack(anchor="e")
            label(right, str(tp), 34, "bold", anchor="e").pack(anchor="e")
            chip(right, lvl, "#A78BFA", size=12).pack(anchor="e")
        if self.app.can("training"):
            pick_row = box(self.hero)
            pick_row.pack(fill="x", padx=22, pady=(0, 16))
            label(pick_row, "Training player:", 12, color=MUTED).pack(side="left")
            picker = PlayerPicker(pick_row, width=220, empty_label="Current 1st Singles",
                                  command=lambda: self.act(s.set_training_player, picker.get(),
                                                           success="Training player updated"))
            picker.set_players([p for p in s.active_players() if p.get("role") != "manager"])
            picker.set(s.data["training"].get("player_id"))
            picker.pack(side="left", padx=8)

        managers = [p["name"] for p in s.active_players("manager")]
        names = managers + ([self.app.username] if self.app.username not in managers else [])
        cur = self.mgr.get()
        self.mgr.configure(values=names)
        self.mgr.set(cur if cur in names else names[0])

        skills = s.data["training"]["skills"].get(pid, {}) if pid else {}
        for sk, (sl, val) in self.sliders.items():
            v = skills.get(sk, 5)
            sl.set(v)
            val.configure(text=str(int(v)))

        clear(self.hist)
        sessions = [x for x in s.data["training"]["sessions"] if x["pid"] == pid] if pid else []
        total_min = sum(x["minutes"] for x in sessions)
        label(self.hist, f"{len(sessions)} sessions · {total_min // 60}h {total_min % 60}m trained", 12,
              color=MUTED).pack(anchor="w", pady=(0, 6))
        if not sessions:
            empty_state(self.hist, "No sessions logged yet")
        for x in sessions[:40]:
            r = ctk.CTkFrame(self.hist, fg_color=SURFACE2, corner_radius=10)
            r.pack(fill="x", pady=3)
            label(r, f"+{x['points']}", 15, "bold", "#A78BFA", width=60).pack(side="left", padx=(12, 4), pady=10)
            col = box(r)
            col.pack(side="left", fill="x", expand=True, pady=8)
            label(col, f"{x['focus']} · {x['minutes']} min · effort {x['effort']}/5", 13, "bold").pack(anchor="w")
            label(col, f"with {x['manager']} · {nice_date(x['date'])}"
                  + (f" — {x['notes']}" if x.get("notes") else ""), 12, color=MUTED,
                  wraplength=640, justify="left").pack(anchor="w")
            if self.app.can("delete"):
                small_button(r, "Delete", lambda sid=x["id"]: self.act(s.delete_training, sid, success="Deleted"),
                       "danger", width=64, height=28, font=F(12)).pack(side="right", padx=10)

    def _skills(self):
        return {sk: int(sl.get()) for sk, (sl, _) in self.sliders.items()}

    def log(self):
        s = self.store
        pid = s.training_player()
        if not pid:
            return self.app.toast("Set a 1st singles player first.", "error")
        try:
            mins = int(self.minutes.get())
            pts = int(self.tpoints.get())
        except ValueError:
            return self.app.toast("Minutes and points must be numbers.", "error")
        notes = self.tnotes.get("1.0", "end").strip()
        self.act(s.log_training, pid, self.mgr.get(), self.focus.get(), mins, int(self.effort.get()),
                 pts, notes, self._skills(), success=f"+{pts} training points logged")
        self.tnotes.delete("1.0", "end")

    def save_skills(self):
        s = self.store
        pid = s.training_player()
        if not pid:
            return self.app.toast("Set a 1st singles player first.", "error")
        sk = self._skills()
        self.act(s.mutate, lambda d: d["training"]["skills"].setdefault(pid, {}).update(sk),
                 f"Updated skill ratings for {s.player_name(pid)}", success="Ratings saved")


# ======================================================= improvement notes
class NotesPage(Page):
    title = "Improvement Notes"
    subtitle = "Who needs to improve on what — send them straight to the managers on Discord"

    def build(self):
        self.body.grid_columnconfigure(0, weight=2, uniform="n")
        self.body.grid_columnconfigure(1, weight=3, uniform="n")
        self.body.grid_rowconfigure(0, weight=1)

        fc, fi, _ = self.section(self.body, "New note")
        fc.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        label(fi, "PLAYER", 11, "bold", MUTED).pack(anchor="w")
        self.pk = PlayerPicker(fi, width=300, empty_label="Choose a player")
        self.pk.pack(fill="x", pady=(4, 10))
        label(fi, "NEEDS TO IMPROVE ON", 11, "bold", MUTED).pack(anchor="w")
        self.area = option(fi, IMPROVE_AREAS, width=300)
        self.area.pack(fill="x", pady=(4, 10))
        label(fi, "PRIORITY", 11, "bold", MUTED).pack(anchor="w")
        self.prio = segmented(fi, PRIORITIES)
        self.prio.set("Medium")
        self.prio.pack(fill="x", pady=(4, 10))
        label(fi, "DETAILS", 11, "bold", MUTED).pack(anchor="w")
        self.text = ctk.CTkTextbox(fi, height=110, corner_radius=10, fg_color=SURFACE2, border_width=1,
                                   border_color=BORDER, font=F(13), text_color=TEXT)
        self.text.pack(fill="x", pady=(4, 10))
        self.send_now = ctk.CTkCheckBox(fi, text="Also send to managers on Discord", font=F(13),
                                        checkbox_width=20, checkbox_height=20, corner_radius=6)
        self.send_now.pack(anchor="w", pady=(0, 10))
        self.add_btn = button(fi, "Add note", self.add, height=40)
        self.add_btn.pack(fill="x")
        self.hook_status = label(fi, "", 12, color=MUTED, wraplength=300, justify="left")
        self.hook_status.pack(anchor="w", pady=(10, 0))

        lc, li, lh = self.section(self.body, "Notes")
        lc.grid(row=0, column=1, sticky="nsew")
        bar = box(lh)
        bar.pack(fill="x", pady=(8, 0))
        self.filter = segmented(bar, ["Open", "Resolved", "All"], command=lambda v: self.refresh())
        self.filter.set("Open")
        self.filter.pack(side="left")
        self.send_all_btn = button(bar, "Send open notes to managers", self.send_all, height=34)
        self.send_all_btn.pack(side="right")
        self.list = FastScroll(li, fg_color="transparent")
        self.list.pack(fill="both", expand=True)

        if not self.app.can("notes"):
            self.add_btn.configure(state="disabled")
            self.send_all_btn.configure(state="disabled")

    def refresh(self):
        s = self.store
        self.pk.set_players(s.active_players())
        hook = s.settings.get("discord_webhook", "")
        if discord_notify.valid_webhook(hook):
            self.hook_status.configure(text="Discord webhook connected.", text_color=GOOD)
        else:
            self.hook_status.configure(text="No Discord webhook yet — a coach can add one in Settings.",
                                       text_color=WARN)
        clear(self.list)
        f = self.filter.get()
        notes = s.open_notes() if f == "Open" else [
            n for n in s.data["notes"] if f == "All" or n.get("resolved")]
        if not notes:
            empty_state(self.list, "No notes here", "Add one on the left" if f == "Open" else "")
        for n in notes:
            self._note(n)

    def _note(self, n):
        s = self.store
        c = ctk.CTkFrame(self.list, fg_color=SURFACE2, corner_radius=12)
        c.pack(fill="x", pady=4, padx=2)
        vbar(c, PRIORITY_COLORS.get(n["priority"], ACCENT[1])).pack(
            side="left", fill="y", padx=(10, 12), pady=12)
        col = box(c)
        col.pack(side="left", fill="x", expand=True, pady=10)
        top = box(col)
        top.pack(anchor="w")
        label(top, s.player_name(n["pid"]), 14, "bold").pack(side="left")
        chip(top, n["area"], ACCENT_SOFT, text_color=ACCENT).pack(side="left", padx=8)
        chip(top, n["priority"], PRIORITY_COLORS.get(n["priority"], "#888")).pack(side="left")
        if n.get("resolved"):
            chip(top, "Resolved", GOOD[1]).pack(side="left", padx=6)
        if n.get("text"):
            label(col, n["text"], 13, wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))
        meta = f"by {n['by']} · {nice_ts(n['ts'])}"
        if n.get("sent"):
            meta += " · sent to managers"
        label(col, meta, 11, color=MUTED).pack(anchor="w", pady=(2, 0))
        if self.app.can("notes"):
            acts = box(c)
            acts.pack(side="right", padx=10)
            small_button(acts, "Send", lambda: self._send([n]), "ghost", width=60, height=28,
                   font=F(12)).pack(pady=2)
            small_button(acts, "Reopen" if n.get("resolved") else "Resolve",
                   lambda: self.act(s.update_note, n["id"], resolved=not n.get("resolved")),
                   "ghost", width=60, height=28, font=F(12)).pack(pady=2)
            small_button(acts, "Delete", lambda: self.act(s.delete_note, n["id"]), "danger", width=60,
                   height=28, font=F(12)).pack(pady=2)

    def add(self):
        s = self.store
        pid = self.pk.get()
        if not pid:
            return self.app.toast("Choose a player.", "error")
        text = self.text.get("1.0", "end").strip()
        nid = self.act(s.add_note, pid, self.area.get(), self.prio.get(), text, success="Note added")
        self.text.delete("1.0", "end")
        if nid and self.send_now.get():
            note = next((x for x in s.data["notes"] if x["id"] == nid), None)
            if note:
                self._send([note])

    def send_all(self):
        notes = self.store.open_notes()
        if not notes:
            return self.app.toast("No open notes to send.", "error")
        confirm(self, "Send to managers?",
                f"Post {len(notes)} open note(s) to the managers' Discord channel?", "Send",
                on_ok=lambda: self._send(notes))

    def _send(self, notes):
        s = self.store
        hook = s.settings.get("discord_webhook", "")
        mention = s.settings.get("discord_mention", "")
        if not discord_notify.valid_webhook(hook):
            return self.app.toast("Add the managers' Discord webhook in Settings first.", "error")
        ids = [n["id"] for n in notes]
        self.app.toast(f"Sending {len(notes)} note(s) to Discord…")

        def done(_):
            s.mutate(lambda d: [n.__setitem__("sent", True) for n in d["notes"] if n["id"] in ids],
                     f"Sent {len(ids)} improvement note(s) to managers on Discord")
            self.app.toast("Sent to managers on Discord", "success")
            self.shell.refresh_current()

        self.app.run_bg(lambda: discord_notify.send_notes(hook, notes, s, self.app.username, mention),
                        done, lambda e: self.app.toast(str(e), "error"))


# ======================================================= training library
LEVEL_BLURB = {"Beginner": "Start here — the basics every player needs.",
               "Intermediate": "Sharpen technique once the basics feel easy.",
               "Expert": "Advanced skills — worth the most points."}


class LibraryPage(Page):
    """Shared by Video Quizzes (kind='quiz') and Optional Training (kind='optional')."""
    KIND = "optional"
    CATEGORIES = TRAINING_CATEGORIES
    scroll = True

    def build(self):
        if self.app.can("videos"):
            button(self.actions, "+ Add video", lambda: video_editor(self, None, self.KIND)).pack(side="right")
        bar = box(self.body)
        bar.pack(fill="x", padx=12, pady=(0, 6))
        self.level = segmented(bar, ["All levels"] + LEVELS, command=lambda v: self.refresh())
        self.level.set("All levels")
        self.level.pack(side="left")
        self.cat = segmented(bar, ["All"] + self.CATEGORIES, command=lambda v: self.refresh())
        self.cat.set("All")
        self.cat.pack(side="left", padx=10)
        self.who_box = box(bar, width=1, height=1)
        self.who_box.pack(side="right")
        self.who = None
        if self.app.can("quiz_others"):
            label(self.who_box, "Player:", 12, color=MUTED).pack(side="left", padx=(0, 6))
            self.who = PlayerPicker(self.who_box, width=190, empty_label="Choose player",
                                    command=self.refresh)
            self.who.pack(side="left")
        self.info = box(self.body)
        self.info.pack(fill="x", padx=12)
        self.list = box(self.body)
        self.list.pack(fill="both", expand=True, padx=12)

    def pid(self):
        if self.who is not None:
            return self.who.get()
        me = self.app.me
        return me["id"] if me else None

    def refresh(self):
        s = self.store
        if self.who is not None:
            self.who.set_players([p for p in s.active_players() if p.get("role") != "manager"])
            if self.who.get() is None and self.app.me:
                self.who.set(self.app.me["id"])
        pid = self.pid()
        clear(self.info)
        pen = s.settings["extras"].get("integrity_penalty", 10)
        if self.KIND == "quiz":
            txt = (f"Watch the whole video in the app, then pass the quiz ({s.settings['extras']['quiz_pass_pct']}% "
                   f"to pass, {s.settings['extras']['quiz_attempts']} tries). Skipping is detected: no points and −{pen}.")
        else:
            txt = f"Watch for extra points — no quiz. Videos can't be skipped: skipping = no points and −{pen}."
        label(self.info, txt, 12, color=MUTED, wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))
        if pid is None:
            msg = ("Choose a player above to see their progress and start a video." if self.who is not None else
                   f"Your username “{self.app.username}” isn't linked to the roster yet — ask your coach.")
            label(self.info, msg, 13, "bold", WARN).pack(anchor="w", pady=(0, 6))

        clear(self.list)
        vids = s.videos(self.KIND)
        if not vids:
            panel = card(self.list)
            panel.pack(fill="x", pady=8)
            empty_state(panel, "No videos yet", "Coaches and managers can add YouTube videos here."
                        if not self.app.can("videos") else "")
            if self.app.can("videos"):
                n = 13 if self.KIND == "optional" else 6
                button(panel, f"Add {n} starter videos (all levels)", self.load_starters).pack(pady=(0, 22))
            return
        lv, ct = self.level.get(), self.cat.get()
        for level in LEVELS:
            if lv != "All levels" and lv != level:
                continue
            items = [v for v in vids if v.get("level", "Beginner") == level and (ct == "All" or v["category"] == ct)]
            head = box(self.list)
            head.pack(fill="x", pady=(14, 6))
            vbar(head, LEVEL_COLORS[level], 6).pack(side="left", fill="y", padx=(0, 10))
            label(head, level, 18, "bold").pack(side="left")
            label(head, f"   {LEVEL_BLURB[level]}", 12, color=MUTED).pack(side="left")
            done = sum(1 for v in items if pid and (s.video_status(pid, v["id"])["passed" if self.KIND == "quiz" else "watched"]))
            if pid and items:
                label(head, f"{done}/{len(items)} done", 12, "bold", MUTED).pack(side="right")
            if not items:
                label(self.list, "Nothing here yet.", 12, color=MUTED).pack(anchor="w", padx=16)
                continue
            grid = box(self.list)
            grid.pack(fill="x")
            grid.grid_columnconfigure((0, 1), weight=1, uniform="v")
            for i, v in enumerate(items):
                self._card(grid, v, pid).grid(row=i // 2, column=i % 2, sticky="nsew",
                                              padx=(0 if i % 2 == 0 else 6, 6 if i % 2 == 0 else 0), pady=6)

    def _card(self, master, v, pid):
        s, app = self.store, self.app
        c = card(master)
        top = box(c)
        top.pack(fill="x", padx=18, pady=(16, 4))
        chip(top, v.get("level", "Beginner"), LEVEL_COLORS[v.get("level", "Beginner")], size=10).pack(side="left")
        chip(top, v["category"], SURFACE2, text_color=TEXT, size=10).pack(side="left", padx=6)
        label(top, f"+{v['points']} pts", 14, "bold", GOOD).pack(side="right")
        label(c, v["title"], 15, "bold", wraplength=400, justify="left").pack(fill="x", padx=18)
        sub = f"Min. {v.get('minutes', 0)} min · tracked, no skipping"
        if self.KIND == "quiz":
            sub = f"{len(v.get('questions', []))} questions · " + sub
        label(c, sub, 11, color=MUTED).pack(fill="x", padx=18, pady=(2, 8))

        st = s.video_status(pid, v["id"]) if pid else None
        row = box(c)
        row.pack(fill="x", padx=18, pady=(0, 16))
        if st:
            if st["skipped"]:
                label(row, "Skipping detected — no points", 12, "bold", BAD).pack(side="left")
            elif self.KIND == "optional":
                if st["watched"]:
                    label(row, "Watched ✓ points earned", 12, "bold", GOOD).pack(side="left")
                else:
                    small_button(row, "Watch", lambda: app.watch_video(pid, v["id"]), height=32).pack(side="left")
            else:
                if st["passed"]:
                    b = st["pass_log"]
                    label(row, f"Passed ✓ {b['score']}/{b['total']}", 12, "bold", GOOD).pack(side="left")
                elif not st["viewed"]:
                    small_button(row, "Watch to unlock quiz", lambda: app.watch_video(pid, v["id"]),
                           height=32).pack(side="left")
                elif st["attempts_left"] <= 0:
                    label(row, "No tries left", 12, "bold", BAD).pack(side="left")
                else:
                    small_button(row, f"Take quiz ({st['attempts_left']} tries left)",
                           lambda: quiz_dialog(self, pid, v["id"]), "good", height=32).pack(side="left")
            if app.can("videos") and st["skipped"]:
                small_button(row, "Allow re-watch", lambda: self.act(s.clear_skip, pid, v["id"], success="They can try again"),
                       "ghost", height=30, font=F(12)).pack(side="left", padx=6)
            if app.can("videos") and self.KIND == "quiz" and not st["passed"] and st["attempts"] > 0:
                small_button(row, "Reset tries", lambda: self.act(s.reset_quiz, pid, v["id"], success="Tries reset"),
                       "ghost", height=30, font=F(12)).pack(side="left", padx=6)
        if app.can("videos"):
            small_button(row, "Delete", lambda: confirm(self, "Delete video?", f"Remove “{v['title']}”? Points players "
                   "already earned are kept.", "Delete", True, lambda: self.act(s.delete_video, v["id"])),
                   "danger", width=60, height=30, font=F(12)).pack(side="right")
            small_button(row, "Edit", lambda: video_editor(self, v["id"], self.KIND), "ghost", width=50, height=30,
                   font=F(12)).pack(side="right", padx=6)
        return c

    def load_starters(self):
        import starter_content
        try:
            n = starter_content.load_starters(self.store, self.KIND)
        except Exception as e:  # noqa: BLE001
            return self.app.toast(f"Couldn't add starters: {e}", "error")
        self.app.toast(f"Added {n} starter videos — preview them and swap any you don't like.", "success")
        self.shell.refresh_current()


class QuizzesPage(LibraryPage):
    title = "Video Quizzes"
    subtitle = "Need extra points? Watch a training video, then pass the quiz"
    KIND = "quiz"
    CATEGORIES = QUIZ_CATEGORIES


class VideosPage(LibraryPage):
    title = "Optional Training"
    subtitle = "Footwork · Shots · Grip · Plyometrics — watch the whole video for extra points"
    KIND = "optional"
    CATEGORIES = TRAINING_CATEGORIES


def quiz_dialog(page, pid, vid):
    s = page.store
    v = s.video(vid)
    d = Dialog(page, v["title"], width=620, height=640)
    label(d.body, f"Quiz for {s.player_name(pid)} · {len(v['questions'])} questions · "
                  f"{s.settings['extras']['quiz_pass_pct']}% to pass · +{v['points']} pts", 12,
          color=MUTED).pack(fill="x")
    panel = FastScroll(d.body, fg_color=SURFACE2, corner_radius=10, height=430)
    panel.pack(fill="both", expand=True, pady=(10, 0))
    picks = []
    for i, q in enumerate(v["questions"]):
        label(panel, f"{i + 1}. {q['q']}", 14, "bold", wraplength=540, justify="left").pack(
            fill="x", padx=12, pady=(14, 6))
        var = ctk.IntVar(value=-1)
        picks.append(var)
        for j, opt in enumerate(q["options"]):
            if str(opt).strip():
                ctk.CTkRadioButton(panel, text=opt, variable=var, value=j, font=F(13), text_color=TEXT,
                                   radiobutton_width=18, radiobutton_height=18).pack(anchor="w", padx=26, pady=3)
    err = label(d.body, "", 12, color=BAD)
    err.pack(fill="x", pady=(6, 0))

    def submit():
        answers = [var.get() for var in picks]
        if -1 in answers:
            return err.configure(text=f"Answer every question first (question {answers.index(-1) + 1} is empty).")
        d.destroy()
        res = page.act(s.submit_quiz, pid, vid, answers)
        if res:
            quiz_result(page, v, res)
    button(d.buttons, "Submit answers", submit, "good").pack(side="right")
    button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
    d.show()


def quiz_result(page, v, res):
    d = Dialog(page, "Passed!" if res["passed"] else "Not quite", width=440)
    label(d.body, f"{res['score']} / {res['total']} correct", 26, "bold", GOOD if res["passed"] else BAD).pack(fill="x")
    if res["passed"]:
        label(d.body, f"+{res['points']} points added.", 14).pack(fill="x", pady=(4, 0))
    else:
        wrong = ", ".join(str(i + 1) for i in res["wrong"])
        label(d.body, f"Review question(s) {wrong} and try again — {res['attempts_left']} tries left.", 13,
              color=MUTED, wraplength=390, justify="left").pack(fill="x", pady=(4, 0))
    button(d.buttons, "OK", d.destroy).pack(side="right")
    d.show()


def video_editor(page, vid, kind):
    """Add / edit a training video (and its quiz questions)."""
    s = page.store
    v = s.video(vid) if vid else {}
    is_quiz = kind == "quiz"
    d = Dialog(page, ("Edit " if vid else "Add ") + ("quiz video" if is_quiz else "training video"),
               width=640, height=640 if is_quiz else 540)
    form = FastScroll(d.body, fg_color="transparent", height=470 if is_quiz else 380)
    form.pack(fill="both", expand=True)

    def field(title, w):
        label(form, title, 12, "bold", MUTED).pack(fill="x", pady=(8, 4))
        w.pack(fill="x")
        return w
    title = field("Title", entry(form, "e.g. Split-step basics"))
    url = field("YouTube link", entry(form, "https://www.youtube.com/watch?v=…"))
    row = box(form)
    row.pack(fill="x", pady=(8, 0))
    row.grid_columnconfigure((0, 1, 2, 3), weight=1)
    for i, t in enumerate(["CATEGORY", "LEVEL", "POINTS", "MIN. MINUTES"]):
        label(row, t, 11, "bold", MUTED).grid(row=0, column=i, sticky="w", padx=(0, 8))
    cats = QUIZ_CATEGORIES if is_quiz else TRAINING_CATEGORIES
    cat = option(row, cats, width=150)
    cat.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 0))
    pts = entry(row, "", width=80)
    lvl = segmented(row, LEVELS, command=lambda val: (pts.delete(0, "end"),
                                                      pts.insert(0, str(s.default_video_points(kind, val)))))
    lvl.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(4, 0))
    pts.grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(4, 0))
    mins = entry(row, "", width=80)
    mins.grid(row=1, column=3, sticky="ew", pady=(4, 0))
    label(form, "Min. minutes is a floor on top of 95% of the real video — keep it at or below the video's length.",
          11, color=MUTED, wraplength=560, justify="left").pack(fill="x", pady=(4, 0))

    title.insert(0, v.get("title", ""))
    url.insert(0, v.get("url", ""))
    cat.set(v.get("category", cats[0]))
    level0 = v.get("level", "Beginner")
    lvl.set(level0)
    pts.insert(0, str(v.get("points", s.default_video_points(kind, level0))))
    mins.insert(0, str(v.get("minutes", 1)))

    qblocks = []
    if is_quiz:
        label(form, "QUESTIONS", 12, "bold", MUTED).pack(fill="x", pady=(16, 4))
        qwrap = box(form)
        qwrap.pack(fill="x")

        def add_q(q=None):
            q = q or {"q": "", "options": ["", "", "", ""], "answer": 0}
            b = ctk.CTkFrame(qwrap, fg_color=SURFACE2, corner_radius=10)
            b.pack(fill="x", pady=4)
            h = box(b)
            h.pack(fill="x", padx=10, pady=(8, 0))
            num = label(h, "", 12, "bold")
            num.pack(side="left")
            rec = {}

            def remove():
                qblocks.remove(rec)
                b.destroy()
                renumber()
            button(h, "Remove", remove, "danger", width=64, height=26, font=F(11)).pack(side="right")
            qe = entry(b, "Question")
            qe.pack(fill="x", padx=10, pady=(6, 4))
            qe.insert(0, q["q"])
            opts = []
            for j in range(4):
                e = entry(b, f"Answer {'ABCD'[j]}" + (" (optional)" if j > 1 else ""))
                e.pack(fill="x", padx=10, pady=2)
                if j < len(q["options"]):
                    e.insert(0, q["options"][j])
                opts.append(e)
            r = box(b)
            r.pack(fill="x", padx=10, pady=(4, 10))
            label(r, "Correct answer:", 12, color=MUTED).pack(side="left", padx=(0, 8))
            ans = segmented(r, ["A", "B", "C", "D"])
            ans.set("ABCD"[q.get("answer", 0)])
            ans.pack(side="left")
            rec.update(q=qe, opts=opts, ans=ans, num=num)
            qblocks.append(rec)
            renumber()

        def renumber():
            for i, r in enumerate(qblocks, 1):
                r["num"].configure(text=f"Question {i}")
        for q in v.get("questions", []) or [None]:
            add_q(q)
        button(form, "+ Add question", lambda: add_q(), "ghost").pack(anchor="w", pady=(6, 4))

    err = label(d.body, "", 12, color=BAD)
    err.pack(fill="x", pady=(6, 0))

    def save():
        from watch_server import youtube_id
        t, u = title.get().strip(), url.get().strip()
        if not t:
            return err.configure(text="Give the video a title.")
        if not youtube_id(u):
            return err.configure(text="Use a YouTube link — only YouTube videos can be tracked for skipping.")
        try:
            p, m = int(pts.get()), int(mins.get())
        except ValueError:
            return err.configure(text="Points and minutes must be whole numbers.")
        questions = []
        for i, r in enumerate(qblocks, 1):
            qt = r["q"].get().strip()
            opts = [e.get().strip() for e in r["opts"]]
            a = "ABCD".index(r["ans"].get())
            if not qt:
                return err.configure(text=f"Question {i} is empty.")
            if sum(1 for o in opts if o) < 2:
                return err.configure(text=f"Question {i} needs at least two answers.")
            if not opts[a]:
                return err.configure(text=f"Question {i}: the correct answer ({'ABCD'[a]}) is blank.")
            questions.append({"q": qt, "options": opts, "answer": a})
        if is_quiz and not questions:
            return err.configure(text="Add at least one question.")
        d.destroy()
        page.act(s.save_video, vid, kind, t, u, cat.get(), m, p, questions, "", lvl.get(),
                 success="Video saved")
    button(d.buttons, "Save", save).pack(side="right")
    button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
    d.show()


# ======================================================= rank-up matches (Manager app)
class RankUpsPage(Page):
    title = "Rank-Up Matches"
    subtitle = "Players qualify every 500 points — run their match, then rank them up"
    scroll = True

    def build(self):
        self.w = box(self.body)
        self.w.pack(fill="both", expand=True, padx=12)
        self.filter_val = "Open"

    def refresh(self):
        s, app = self.store, self.app
        clear(self.w)
        sign = ctk.CTkFrame(self.w, fg_color=K.HERO, corner_radius=18)
        sign.pack(fill="x", pady=(0, 14))
        lf = box(sign)
        lf.pack(side="left", padx=26, pady=20)
        label(lf, app.greeting(), 30, "bold", "#FFFFFF").pack(anchor="w")
        reqs = s.data["rankups"]
        open_r = [r for r in reqs if r["status"] in RANKUP_OPEN]
        mine = [r for r in open_r if app.me_manager and r.get("manager") == app.me_manager["id"]]
        label(lf, f"{len(open_r)} open rank-up request(s)" + (f" · {len(mine)} assigned to you" if mine else ""),
              14, color=K.HERO_SUB).pack(anchor="w", pady=(4, 0))

        qual = [p for p, pts in s.leaderboard() if s.qualified(p["id"], pts) and not s.open_rankup(p["id"])]
        season_ups = sum(1 for h in s.data["rank_history"] if h["to"] > h["from"])
        stats = box(self.w)
        stats.pack(fill="x")
        for i, (t, v, sub) in enumerate([
                ("Waiting", str(sum(1 for r in open_r if r["status"] == "pending")), "requests to schedule"),
                ("Scheduled", str(sum(1 for r in open_r if r["status"] == "scheduled")), "matches coming up"),
                ("Qualified", str(len(qual)), "no request yet"),
                ("Rank-ups", str(season_ups), "this season")]):
            stats.grid_columnconfigure(i, weight=1, uniform="s")
            c = card(stats)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            label(c, t.upper(), 11, "bold", MUTED).pack(anchor="w", padx=18, pady=(14, 0))
            label(c, v, 24 if len(v) <= 11 else 17, "bold").pack(anchor="w", padx=18, pady=(0, 0 if len(v) <= 11 else 5))
            label(c, sub, 12, color=MUTED).pack(anchor="w", padx=18, pady=(0, 14))

        cols = box(self.w)
        cols.pack(fill="x", pady=14)
        cols.grid_columnconfigure(0, weight=3, uniform="c")
        cols.grid_columnconfigure(1, weight=2, uniform="c")

        rc, ri, rh = self.section(cols, "Requests")
        rc.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        f = segmented(rh, ["Open", "Closed", "All"], command=lambda val: (setattr(self, "filter_val", val), self.refresh()))
        f.set(self.filter_val)
        f.pack(anchor="w", pady=(8, 0))
        show = {"Open": open_r, "Closed": [r for r in reqs if r["status"] not in RANKUP_OPEN], "All": reqs}[self.filter_val]
        show = sorted(show, key=lambda r: (r not in mine, r["ts"]))
        if not show:
            empty_state(ri, "No requests here", "Players request a match from their dashboard once they hit 500 points.")
        for r in show[:40]:
            self._request(ri, r, r in mine)

        right = box(cols)
        right.grid(row=0, column=1, sticky="nsew")
        qc, qi, _ = self.section(right, "Qualified — no request yet")
        qc.pack(fill="x")
        if not qual:
            empty_state(qi, "Nobody waiting")
        for p in qual:
            row = box(qi)
            row.pack(fill="x", pady=4)
            lvl = s.rank_level(p["id"])
            col = box(row)
            col.pack(side="left")
            label(col, p["name"], 13, "bold").pack(anchor="w")
            label(col, f"{s.points(p['id'])} pts · {s.level_name(lvl)[0]} → {s.level_name(lvl + 1)[0]}", 11,
                  color=MUTED).pack(anchor="w")
            if app.can("rank"):
                small_button(row, "Start match", lambda pid=p["id"]: self.act(
                    s.request_rankup, pid, app.me_manager["id"] if app.me_manager else None,
                    "Started by a manager", app.username, success="Request created — schedule it on the left"),
                    height=30, font=F(12)).pack(side="right")

        mc, mi, _ = self.section(right, "Manual rank change", "Rank someone up or down without a match.")
        mc.pack(fill="x", pady=(10, 0))
        pk = PlayerPicker(mi, width=300, empty_label="Choose player")
        pk.set_players([p for p in s.active_players() if p.get("role") != "manager"])
        pk.pack(fill="x")
        cur = label(mi, "", 12, color=MUTED)
        cur.pack(anchor="w", pady=(6, 6))
        pk.menu.configure(command=lambda _v: cur.configure(
            text=f"Current rank: {s.rank_of(pk.get())[0]} · {s.points(pk.get())} pts" if pk.get() else ""))
        reason = entry(mi, "Reason (required)")
        reason.pack(fill="x")
        br = box(mi)
        br.pack(fill="x", pady=(10, 0))

        def change(step):
            pid = pk.get()
            if not pid:
                return app.toast("Choose a player.", "error")
            why = reason.get().strip()
            if not why:
                return app.toast("Add a reason for the rank change.", "error")
            lvl = s.rank_level(pid)
            if lvl + step < 0:
                return app.toast("They're already at the lowest rank.", "error")
            new = s.level_name(lvl + step)[0]
            confirm(self, "Change rank?", f"{s.player_name(pid)}: {s.level_name(lvl)[0]} → {new}\nReason: {why}",
                    "Rank up" if step > 0 else "Rank down", step < 0,
                    lambda: self.act(s.set_rank, pid, lvl + step, why, success=f"{s.player_name(pid)} is now {new}"))
        b1 = button(br, "▲ Rank up", lambda: change(1), "good")
        b1.pack(side="left", fill="x", expand=True)
        b2 = button(br, "▼ Rank down", lambda: change(-1), "danger")
        b2.pack(side="left", fill="x", expand=True, padx=(8, 0))
        if not app.can("rank"):
            b1.configure(state="disabled")
            b2.configure(state="disabled")

    def _request(self, master, r, mine):
        s, app = self.store, self.app
        pid = r["pid"]
        c = ctk.CTkFrame(master, fg_color=SURFACE2, corner_radius=12, border_width=2 if mine else 0,
                         border_color=ACCENT)
        c.pack(fill="x", pady=5)
        top = box(c)
        top.pack(fill="x", padx=14, pady=(12, 2))
        name, color, _, _ = s.rank_of(pid)
        avatar(top, s.player_name(pid), color, 36).pack(side="left")
        col = box(top)
        col.pack(side="left", padx=10)
        label(col, s.player_name(pid), 14, "bold").pack(anchor="w")
        label(col, f"{s.level_name(r['from_level'])[0]} → {s.level_name(r['to_level'])[0]} · {s.points(pid)} pts",
              12, color=MUTED).pack(anchor="w")
        status_color = {"pending": WARN[1], "scheduled": ACCENT[1], "passed": GOOD[1], "failed": BAD[1],
                        "cancelled": "#8B94A5"}[r["status"]]
        chip(top, r["status"].title(), status_color).pack(side="right")
        if mine:
            chip(top, "Assigned to you", ACCENT_SOFT, text_color=ACCENT, size=10).pack(side="right", padx=6)
        body = box(c)
        body.pack(fill="x", padx=14, pady=(4, 0))
        if r["status"] in RANKUP_OPEN:
            label(body, rankup_status_text(s, r), 12, wraplength=520, justify="left").pack(anchor="w")
        else:
            res = f"{r['status'].title()} · by {r.get('decided_by', '?')} · {nice_ts(r.get('decided_ts') or r['ts'])}"
            if r.get("score"):
                res += f" · {r['score']}"
            label(body, res, 12, wraplength=520, justify="left").pack(anchor="w")
        if r.get("message"):
            label(body, f"“{r['message']}”", 12, color=MUTED, wraplength=520, justify="left").pack(anchor="w", pady=(2, 0))
        if r.get("result_note"):
            label(body, r["result_note"], 12, color=MUTED, wraplength=520, justify="left").pack(anchor="w")
        acts = box(c)
        acts.pack(fill="x", padx=14, pady=(8, 12))
        if r["status"] in RANKUP_OPEN and app.can("rank"):
            small_button(acts, "Record result", lambda: self.result_dialog(r), "good", height=30, font=F(12)).pack(side="left")
            small_button(acts, "Schedule" if r["status"] == "pending" else "Reschedule", lambda: self.schedule_dialog(r),
                   "ghost", height=30, font=F(12)).pack(side="left", padx=6)
            small_button(acts, "Cancel", lambda: confirm(self, "Cancel request?", f"Cancel {s.player_name(pid)}'s rank-up "
                   "request? They can request again later.", "Cancel request", True,
                   lambda: self.act(s.cancel_rankup, r["id"], "Cancelled by a manager", success="Cancelled")),
                   "danger", height=30, font=F(12)).pack(side="right")

    def schedule_dialog(self, r):
        s = self.store
        d = Dialog(self, f"Schedule {s.player_name(r['pid'])}'s rank-up match", width=460)
        day = d.field("Date", lambda m: entry(m, "YYYY-MM-DD"))
        day.insert(0, date.today().isoformat())
        tm = d.field("Time", lambda m: entry(m, "e.g. 3:30 PM after practice"))
        det = d.field("Format / opponent", lambda m: entry(m, "e.g. Best of 3 to 21 vs a manager"))
        det.insert(0, r.get("details", ""))

        def go():
            try:
                when = date.fromisoformat(day.get().strip()).strftime("%a %b %d")
            except ValueError:
                return self.app.toast("Date must look like 2026-10-20.", "error")
            if tm.get().strip():
                when += f", {tm.get().strip()}"
            d.destroy()
            self.act(s.schedule_rankup, r["id"], when, det.get(), success=f"Scheduled for {when}")
        button(d.buttons, "Schedule", go).pack(side="right")
        button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
        d.show()

    def result_dialog(self, r):
        s, app = self.store, self.app
        to = s.level_name(r["to_level"])[0]
        d = Dialog(self, f"Rank-up match: {s.player_name(r['pid'])} → {to}", width=480)
        res = d.field("Result", lambda m: segmented(m, ["Passed — rank up", "Did not pass"]))
        res.set("Passed — rank up")
        score = d.field("Score (optional)", lambda m: entry(m, "e.g. 21-17, 21-19"))
        note = d.field("Note (optional)", lambda m: entry(m, "e.g. Great net play — work on backhand clears"))

        def go():
            passed = res.get().startswith("Passed")
            d.destroy()
            ok = self.act(s.decide_rankup, r["id"], passed, score.get(), note.get(),
                          success=f"{s.player_name(r['pid'])} is now {to}!" if passed else "Result saved")
            hook = s.settings.get("discord_webhook", "")
            if ok is not None and discord_notify.valid_webhook(hook):
                req = s.rankup(r["id"])
                app.run_bg(lambda: discord_notify.send_rankup_result(hook, s, req), None, lambda e: None)
        button(d.buttons, "Save result", go, "good").pack(side="right")
        button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
        d.show()


# ================================================================ activity
class ActivityPage(Page):
    title = "Activity"
    subtitle = "Every change, who made it and when"

    def build(self):
        panel = card(self.body)
        panel.pack(fill="both", expand=True)
        self.list = FastScroll(panel, fg_color="transparent")
        self.list.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self):
        clear(self.list)
        acts = self.store.data["activity"]
        if not acts:
            empty_state(self.list, "Nothing yet")
        def row(a):
            r = box(self.list)
            r.pack(fill="x", pady=4, padx=10)
            vbar(r, ACCENT, 3).pack(side="left", fill="y", padx=(0, 12))
            label(r, a["text"], 13).pack(side="left")
            label(r, f"{a['by']} · {nice_ts(a['ts'])}", 11, color=MUTED).pack(side="right")
        paged(self.list, acts, row, first=60, step=100)


# ================================================================ settings
class SettingsPage(Page):
    title = "Settings"
    subtitle = "Team info, point values, Discord, data and your account"
    scroll = True

    def build(self):
        self.w = box(self.body)
        self.w.pack(fill="both", expand=True, padx=12)

    def refresh(self):
        s = self.store
        app = self.app
        clear(self.w)
        coach = app.can("settings")

        # ---- account
        c, i, _ = self.section(self.w, "Your account")
        c.pack(fill="x", pady=(0, 12))
        u = app.auth.user_data
        for k, v in [("Username", app.username), ("App role", app.role.title()),
                     ("KeyAuth subscription", u.subscription or "—"),
                     ("Expires", self._expiry(u.expires)), ("Last login", self._expiry(u.lastlogin))]:
            r = box(i)
            r.pack(fill="x", pady=2)
            label(r, k, 13, color=MUTED, width=180).pack(side="left")
            label(r, v, 13, "bold").pack(side="left")

        if not coach:
            self.readonly_note(self.w, "Only coaches can change team settings.")
            return

        # ---- team
        c, i, _ = self.section(self.w, "Team")
        c.pack(fill="x", pady=(0, 12))
        team = s.data["team"]
        g = box(i)
        g.pack(fill="x")
        self.team_fields = {}
        for col, (k, t) in enumerate([("name", "Team name"), ("school", "School"), ("season", "Season")]):
            g.grid_columnconfigure(col, weight=1)
            label(g, t.upper(), 11, "bold", MUTED).grid(row=0, column=col, sticky="w", padx=(0, 10))
            e = entry(g, t, width=180)
            e.insert(0, team.get(k, ""))
            e.grid(row=1, column=col, sticky="ew", padx=(0, 10), pady=(4, 0))
            self.team_fields[k] = e
        button(i, "Save team info", self.save_team).pack(anchor="w", pady=(12, 0))

        # ---- keyless player sign-in
        c, i, _ = self.section(self.w, "Player sign-in (no license key)",
                               "Players open the PSAL Badminton app, choose the Player tab, type this team code, "
                               "pick their name and make their own PIN the first time. Coaches and managers still "
                               "use their keys. Leave the code empty to turn player sign-in off.")
        c.pack(fill="x", pady=(0, 12))
        r = box(i)
        r.pack(fill="x")
        label(r, "TEAM CODE", 11, "bold", MUTED).pack(anchor="w")
        row = box(r)
        row.pack(fill="x", pady=(4, 0))
        self.pcode = entry(row, "e.g. Lions2026", width=260)
        self.pcode.insert(0, s.settings.get("player_code", ""))
        self.pcode.pack(side="left")
        button(row, "Save code", self.save_code).pack(side="left", padx=8)
        players = [p for p in s.active_players() if p.get("role") != "manager"]
        with_pin = sum(1 for p in players if s.has_pin(p["id"]))
        status = (f"On · {with_pin} of {len(players)} players have made a PIN" if s.settings.get("player_code")
                  else "Off — no team code set")
        label(i, status, 12, color=GOOD if s.settings.get("player_code") else MUTED).pack(anchor="w", pady=(8, 0))
        label(i, "Forgot PIN? Roster → Edit → Reset PIN. Changing the code doesn't erase anyone's PIN.", 11,
              color=MUTED).pack(anchor="w", pady=(2, 0))

        # ---- points
        c, i, _ = self.section(self.w, "Point system", "Changes apply to new points only — history stays the same.")
        c.pack(fill="x", pady=(0, 12))
        P = s.settings["points"]
        fields = [("start_points", "Starting points", s.settings["start_points"]),
                  ("rank_step", "Points per rank-up match", s.settings["rank_step"])]
        fields += [(f"win.{p}", f"{POSITION_LABELS[p]} win", P["win"][p]) for p in POSITIONS]
        fields += [("loss", "Loss (played)", P["loss"]), ("team_win_bonus", "Team win bonus", P["team_win_bonus"]),
                   ("practice", "Practice (+)", P["practice"]),
                   ("absence", "Unexcused absence (−)", P["absence"]),
                   ("scrimmage_win", "Scrimmage win (+)", P["scrimmage_win"]),
                   ("scrimmage_loss", "Scrimmage loss (−)", P["scrimmage_loss"]),
                   ("challenge_win", "Challenge win", P["challenge_win"]),
                   ("challenge_loss", "Challenge loss", P["challenge_loss"]),
                   ("training.level_step", "Training pts per level", s.settings["training"]["level_step"]),
                   ("elo.k", "Skill K (0 = off)", s.settings["elo"]["k"]),
                   ("elo.min_pct", "Skill smallest %", s.settings["elo"]["min_pct"]),
                   ("elo.max_pct", "Skill biggest %", s.settings["elo"]["max_pct"])]
        g = box(i)
        g.pack(fill="x")
        self.point_fields = {}
        for n, (k, t, v) in enumerate(fields):
            rr, cc = divmod(n, 4)
            g.grid_columnconfigure(cc, weight=1)
            f = box(g)
            f.grid(row=rr, column=cc, sticky="ew", padx=(0, 10), pady=4)
            label(f, t.upper(), 10, "bold", MUTED).pack(anchor="w")
            e = entry(f, "", width=150)
            e.insert(0, str(v))
            e.pack(fill="x", pady=(3, 0))
            self.point_fields[k] = e
        button(i, "Save point values", self.save_points).pack(anchor="w", pady=(12, 0))

        # ---- extra points: videos & quizzes
        c, i, _ = self.section(self.w, "Extra points — videos & quizzes",
                               "Default points by level (each video can still be changed), quiz rules and the "
                               "integrity penalty for skipping.")
        c.pack(fill="x", pady=(0, 12))
        X = s.settings["extras"]
        qp, vp = X["quiz_points"], X["video_points"]
        xf = [(f"quiz.{lv}", f"Quiz · {lv}", qp.get(lv, 0)) for lv in LEVELS]
        xf += [(f"video.{lv}", f"Video · {lv}", vp.get(lv, 0)) for lv in LEVELS]
        xf += [("quiz_pass_pct", "Quiz pass %", X["quiz_pass_pct"]), ("quiz_attempts", "Quiz tries", X["quiz_attempts"]),
               ("integrity_penalty", "Skipping penalty (−)", X.get("integrity_penalty", 10))]
        g = box(i)
        g.pack(fill="x")
        self.extra_fields = {}
        for n, (k, t, v) in enumerate(xf):
            rr, cc = divmod(n, 3)
            g.grid_columnconfigure(cc, weight=1)
            f = box(g)
            f.grid(row=rr, column=cc, sticky="ew", padx=(0, 10), pady=4)
            label(f, t.upper(), 10, "bold", MUTED).pack(anchor="w")
            e = entry(f, "", width=150)
            e.insert(0, str(v))
            e.pack(fill="x", pady=(3, 0))
            self.extra_fields[k] = e
        button(i, "Save extra points", self.save_extras).pack(anchor="w", pady=(12, 0))

        # ---- discord
        c, i, _ = self.section(self.w, "Discord — managers' channel",
                               "In Discord: Server Settings → Integrations → Webhooks → New Webhook → "
                               "pick the managers' channel → Copy Webhook URL.")
        c.pack(fill="x", pady=(0, 12))
        label(i, "WEBHOOK URL", 11, "bold", MUTED).pack(anchor="w")
        self.hook = entry(i, "https://discord.com/api/webhooks/…", width=600, show="•")
        self.hook.insert(0, s.settings.get("discord_webhook", ""))
        self.hook.pack(fill="x", pady=(4, 10))
        label(i, "PING (OPTIONAL) — e.g. <@&ROLE_ID> to ping the Managers role", 11, "bold", MUTED).pack(anchor="w")
        self.mention = entry(i, "<@&123456789012345678>", width=600)
        self.mention.insert(0, s.settings.get("discord_mention", ""))
        self.mention.pack(fill="x", pady=(4, 10))
        r = box(i)
        r.pack(fill="x")
        button(r, "Save webhook", self.save_hook).pack(side="left")
        button(r, "Send test message", self.test_hook, "ghost").pack(side="left", padx=8)
        button(r, "Show / hide URL", lambda: self.hook.configure(
            show="" if self.hook.cget("show") else "•"), "ghost").pack(side="left")

        # ---- data
        c, i, _ = self.section(self.w, "Data & backups",
                               "Tip: put the data folder in a shared OneDrive / Google Drive / Dropbox folder "
                               "so every coach and manager computer sees the same points.")
        c.pack(fill="x", pady=(0, 12))
        r = ctk.CTkFrame(i, fg_color=SURFACE2, corner_radius=10)
        r.pack(fill="x")
        label(r, str(s.dir), 12, wraplength=560, justify="left").pack(side="left", padx=12, pady=10)
        button(r, "Open", self.open_folder, "ghost", width=60, height=30).pack(side="right", padx=6)
        button(r, "Change…", self.change_folder, "ghost", width=80, height=30).pack(side="right")
        r = box(i)
        r.pack(fill="x", pady=(10, 0))
        button(r, "Export backup (.json)", self.export_json, "ghost").pack(side="left")
        button(r, "Import backup", self.import_json, "ghost").pack(side="left", padx=8)
        button(r, "Export leaderboard (.csv)", self.export_csv, "ghost").pack(side="left")
        button(r, "Start new season…", self.new_season, "danger").pack(side="right")

        # ---- roles
        c, i, _ = self.section(self.w, "Roles from KeyAuth")
        c.pack(fill="x", pady=(0, 12))
        label(i, "KeyAuth subscriptions named Coach, Managers and Players decide what each account can do "
                 "(keys at level 3 / 2 / 1). Coach = full control. Manager = matches, practice, rank-up matches, "
                 "videos & quizzes, 1S training and notes, plus the Manager app. Player = their own progress, "
                 "videos and quizzes. Any other subscription (like “default”) gets coach access. Link each "
                 "person's login to their roster spot in Roster → Edit → KeyAuth username.",
              12, color=MUTED, wraplength=760, justify="left").pack(anchor="w")

    @staticmethod
    def _expiry(v):
        try:
            return datetime.fromtimestamp(int(v)).strftime("%b %d, %Y")
        except (TypeError, ValueError):
            return str(v or "—")

    def save_code(self):
        code = self.pcode.get().strip()
        if code and len(code) < 4:
            return self.app.toast("Make the team code at least 4 characters.", "error")
        self.act(self.store.mutate, lambda d: d["settings"].__setitem__("player_code", code),
                 "Changed the player team code" if code else "Turned off player sign-in",
                 success="Player sign-in is on" if code else "Player sign-in turned off")

    def save_team(self):
        vals = {k: e.get().strip() for k, e in self.team_fields.items()}
        self.act(self.store.mutate, lambda d: d["team"].update(vals), "Updated team info", success="Team info saved")

    def save_extras(self):
        vals = {}
        for k, e in self.extra_fields.items():
            try:
                vals[k] = int(e.get().strip())
            except ValueError:
                return self.app.toast("Values must be whole numbers.", "error")
        if not 1 <= vals["quiz_pass_pct"] <= 100 or vals["quiz_attempts"] < 1:
            return self.app.toast("Pass % must be 1–100 and tries at least 1.", "error")

        def fn(d):
            X = d["settings"]["extras"]
            for k, v in vals.items():
                if k.startswith("quiz."):
                    X["quiz_points"][k[5:]] = v
                elif k.startswith("video."):
                    X["video_points"][k[6:]] = v
                else:
                    X[k] = abs(v) if k == "integrity_penalty" else v
        self.act(self.store.mutate, fn, "Updated video & quiz points", success="Extra points saved")

    def save_points(self):
        vals = {}
        for k, e in self.point_fields.items():
            try:
                vals[k] = int(e.get().strip())
            except ValueError:
                return self.app.toast("Point values must be whole numbers.", "error")
        if vals["rank_step"] <= 0 or vals["training.level_step"] <= 0:
            return self.app.toast("Points per rank must be more than 0.", "error")

        def fn(d):
            st = d["settings"]
            for k, v in vals.items():
                if k.startswith("win."):
                    st["points"]["win"][k[4:]] = v
                elif k == "training.level_step":
                    st["training"]["level_step"] = v
                elif k.startswith("elo."):
                    st["elo"][k[4:]] = v
                elif k in ("start_points", "rank_step"):
                    st[k] = v
                else:
                    st["points"][k] = v
        self.act(self.store.mutate, fn, "Updated point values", success="Point values saved")

    def save_hook(self):
        url, mention = self.hook.get().strip(), self.mention.get().strip()
        if url and not discord_notify.valid_webhook(url):
            return self.app.toast("That isn't a Discord webhook URL.", "error")
        self.act(self.store.mutate, lambda d: d["settings"].update(discord_webhook=url, discord_mention=mention),
                 "Updated the Discord webhook", success="Webhook saved")

    def test_hook(self):
        url = self.hook.get().strip()
        team = self.store.data["team"].get("name", "PSAL Badminton")
        self.app.run_bg(lambda: discord_notify.send_test(url, team),
                        lambda _: self.app.toast("Test message sent — check Discord", "success"),
                        lambda e: self.app.toast(str(e), "error"))

    def open_folder(self):
        path = str(self.store.dir)
        if platform.system() == "Windows":
            os.startfile(path)  # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def change_folder(self):
        new = filedialog.askdirectory(title="Choose the team data folder")
        if not new:
            return
        target = Path(new) / Store.FILE
        if not target.exists():
            shutil.copy2(self.store.path, target)
            msg = "Data copied to the new folder"
        else:
            msg = "Using the team data already in that folder"
        self.app.config_store.set("data_dir", new)
        self.app.store = Store(new, user=self.app.username)
        self.app.toast(msg, "success")
        self.shell.refresh_current()

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")],
                                            initialfile=f"psal-badminton-backup-{date.today()}.json")
        if path:
            self.store.export_json(path)
            self.app.toast("Backup saved", "success")

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            confirm(self, "Import backup?", "This replaces the current team data. A copy of the current "
                    "data is saved in the data folder first.", "Import", True,
                    lambda: self.act(self.store.import_json, path, success="Backup imported"))

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"leaderboard-{date.today()}.csv")
        if path:
            self.store.export_csv(path)
            self.app.toast("Leaderboard exported", "success")

    def new_season(self):
        d = Dialog(self, "Start a new season", width=460)
        label(d.body, "Everyone goes back to the starting points. Matches, challenges and training are "
                      "archived to a file in the data folder. The roster and lineup stay.", 13,
              color=MUTED, wraplength=410, justify="left").pack(fill="x")
        name = d.field("New season name", lambda m: entry(m, "e.g. 2027"))
        name.insert(0, str(date.today().year + 1))

        def go():
            n = name.get().strip()
            if not n:
                return
            d.destroy()
            self.act(self.store.new_season, n, success=lambda p: f"New season {n} started (archive saved)")
        button(d.buttons, "Start new season", go, "danger").pack(side="right")
        button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
        d.show()


PAGES = {
    "dashboard": DashboardPage, "roster": RosterPage, "lineup": LineupPage, "matches": MatchesPage,
    "practice": PracticePage, "leaderboard": LeaderboardPage, "training": TrainingPage,
    "notes": NotesPage, "activity": ActivityPage, "settings": SettingsPage,
    "quizzes": QuizzesPage, "videos": VideosPage, "rankups": RankUpsPage,
}
