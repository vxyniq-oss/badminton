"""
PSAL Badminton — web version (server).

Runs on your PC and serves the team website to phones, tablets and computers.

    python web_server.py                 # http://localhost:8080 (+ your Wi-Fi address)
    python web_server.py --port 8080 --data "D:\\Team Data"

It uses the same team_data.json as the desktop apps (same folder by default),
so the desktop apps on this PC and the website stay in sync. To reach it from
anywhere, put it behind a Cloudflare Tunnel — see WEB_SETUP.md.

Security notes
  * Coaches/managers sign in with KeyAuth (checked by this server); players
    sign in with the team code + their own PIN. Sessions are signed cookies
    (HttpOnly, SameSite=Lax, Secure over HTTPS).
  * Every action is checked against the person's role on the server.
  * Quiz answers, PIN hashes, the Discord webhook and student IDs never go to
    people who shouldn't see them.
  * Wrong team codes / PINs / passwords are rate limited, with growing lockouts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import time
import traceback
from collections import defaultdict, deque
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, session
from flask.sessions import SecureCookieSessionInterface

import discord_notify
import starter_content
import watch_server as WS
from data_store import (IMPROVE_AREAS, LEVELS, LEVEL_COLORS, POSITION_LABELS, POSITION_SIZE,
                        POSITIONS, PRIORITIES, QUIZ_CATEGORIES, RANKS, RANKUP_OPEN, SKILLS,
                        TRAINING_CATEGORIES, TRAINING_FOCUS, Config, RankUpError, Store, app_dir)
from keyauth_client import KeyAuthError
from keyauth_client import api as KeyAuthApi
from roles import PERMISSIONS, greeting, role_from_subscriptions

APP_BUILD = "1.6"
BASE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB = BASE / "web"
SESSION_DAYS = 30
POLL_HINT_S = 20

# ----------------------------------------------------------------- globals
app = Flask(__name__, static_folder=None)
LOCK = threading.RLock()          # one change at a time to team_data.json
store: Store | None = None
DEV_LOGIN = False                 # only for automated tests on 127.0.0.1


class ApiError(Exception):
    def __init__(self, msg, code=400):
        super().__init__(msg)
        self.code = code


# ------------------------------------------------------------- client info
def peer_is_local() -> bool:
    return request.environ.get("REMOTE_ADDR") in ("127.0.0.1", "::1")


def client_ip() -> str:
    """Real visitor IP. Forwarded headers are only trusted from a tunnel on this PC."""
    if peer_is_local():
        cf = request.headers.get("CF-Connecting-IP")
        if cf:
            return cf.strip()
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
    return request.environ.get("REMOTE_ADDR", "?")


def is_https() -> bool:
    if request.scheme == "https":
        return True
    return peer_is_local() and request.headers.get("X-Forwarded-Proto", "").lower() == "https"


class _Sessions(SecureCookieSessionInterface):
    def get_cookie_secure(self, app_):  # Secure flag whenever the visitor uses HTTPS
        try:
            return is_https()
        except RuntimeError:
            return False


app.session_interface = _Sessions()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  SESSION_COOKIE_NAME="psal", PERMANENT_SESSION_LIFETIME=SESSION_DAYS * 86400,
                  MAX_CONTENT_LENGTH=8 * 1024 * 1024)


# ------------------------------------------------------------ rate limits
class Limiter:
    """Sliding-window attempt counter + growing lockouts for repeated failures."""

    def __init__(self):
        self.hits = defaultdict(deque)
        self.fails = defaultdict(int)
        self.locked_until = {}
        self.lock = threading.Lock()

    def allow(self, key, limit, window):
        now = time.time()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def locked(self, key) -> int:
        with self.lock:
            return max(0, int(self.locked_until.get(key, 0) - time.time()))

    def fail(self, key, every=5, steps=(60, 300, 1800, 7200)) -> int:
        """Record a failure; returns lockout seconds (0 = not locked yet)."""
        with self.lock:
            self.fails[key] += 1
            n = self.fails[key]
            if n % every == 0:
                secs = steps[min(n // every - 1, len(steps) - 1)]
                self.locked_until[key] = time.time() + secs
                return secs
            return 0

    def ok(self, key):
        with self.lock:
            self.fails.pop(key, None)
            self.locked_until.pop(key, None)


LIMIT = Limiter()


def wait_text(secs: int) -> str:
    return f"{secs // 60} min" if secs >= 120 else f"{secs}s"


# ------------------------------------------------------------------ users
class User:
    def __init__(self, kind, role, display, username, pid=None, mgr_pid=None, log_name=None):
        self.kind, self.role, self.display, self.username = kind, role, display, username
        self.pid, self.mgr_pid = pid, mgr_pid
        self.log_name = log_name or username or display or role

    def can(self, perm):
        return perm in PERMISSIONS.get(self.role, set())

    @property
    def staff(self):
        return self.role in ("coach", "manager")


def current_user() -> User | None:
    k = session.get("k")
    if not k or time.time() - float(session.get("t", 0)) > SESSION_DAYS * 86400:
        return None
    if k == "pin":
        p = store.players.get(session.get("pid"))
        if not p or not p.get("active", True) or p.get("role") == "manager":
            return None
        if (p.get("pin_salt") or "")[:12] != session.get("pv"):
            return None  # PIN was reset -> signed out everywhere
        return User("pin", "player", p["name"].split()[0], p.get("username") or p["name"],
                    pid=p["id"], log_name=p["name"])
    if k in ("key", "dev"):
        exp = session.get("exp")
        if exp and time.time() > float(exp):
            return None
        role = session.get("role", "player")
        u = session.get("u", "")
        p = store.player_for_username(u) if session.get("named") else None
        pid = p["id"] if p and p.get("role") != "manager" else None
        mgr = p["id"] if p and p.get("role") == "manager" else None
        return User(k, role, session.get("name", ""), u, pid=pid, mgr_pid=mgr,
                    log_name=(p["name"] if p else u) if session.get("named") else role.title())
    return None


def fresh_store():
    if store.changed_on_disk():
        store.reload()


# ------------------------------------------------------------------ state
def pub_player(p, pts, user: User):
    s = store
    pid = p["id"]
    name, color, frac, need = s.rank_of(pid, pts)
    st = s.player_stats(pid)
    is_mgr = p.get("role") == "manager"
    d = {"id": pid, "name": p["name"], "grade": p.get("grade", ""), "role": p.get("role", "player"),
         "active": p.get("active", True), "points": pts, "level": s.rank_level(pid), "rank": name,
         "color": color, "frac": round(frac, 3), "need": need,
         "qualified": (not is_mgr) and s.qualified(pid, pts), "pos": s.position_of(pid),
         "w": st["wins"], "l": st["losses"]}
    if user.staff or user.pid == pid:
        d["sr"] = s.skill(pid)
        r = s.open_rankup(pid)
        d["rankup"] = ({"id": r["id"], "status": r["status"], "to": s.level_name(r["to_level"])[0],
                        "when": r.get("scheduled_for", ""), "details": r.get("details", ""),
                        "manager": s.player_name(r["manager"]) if r.get("manager") else ""}
                       if r else None)
        d["stats"] = st
    if user.role == "coach":
        d.update(student_id=p.get("student_id", ""), username=p.get("username", ""),
                 discord_id=p.get("discord_id", ""), notes=p.get("notes", ""), has_pin=s.has_pin(pid))
    return d


def video_card(v, user: User):
    d = {k: v.get(k) for k in ("id", "kind", "title", "url", "category", "level", "minutes", "points")}
    d["level"] = d["level"] or "Beginner"
    d["qcount"] = len(v.get("questions") or [])
    if user.pid:
        st = store.video_status(user.pid, v["id"])
        d["my"] = status_summary(st)
    return d


def status_summary(st):
    best = st.get("pass_log") or st.get("best")
    return {"watched": st["watched"], "viewed": st["viewed"], "skipped": st["skipped"],
            "passed": st["passed"], "attempts": st["attempts"], "left": st["attempts_left"],
            "score": f"{best['score']}/{best['total']}" if best else ""}


def build_state(user: User) -> dict:
    s = store
    pts = s.all_points()
    st = {"v": s.version, "build": APP_BUILD, "poll": POLL_HINT_S}
    team = s.data["team"]
    st["team"] = {"name": team.get("name", "PSAL Badminton"), "school": team.get("school", ""),
                  "season": team.get("season", "")}
    st["me"] = {"role": user.role, "kind": user.kind, "display": user.display, "pid": user.pid,
                "mgr_pid": user.mgr_pid, "greeting": greeting(user.display, user.role),
                "perms": sorted(PERMISSIONS.get(user.role, set())), "username": user.username}
    P = s.settings["points"]
    X = s.settings["extras"]
    st["rules"] = {"start": s.settings["start_points"], "step": s.settings["rank_step"],
                   "win": P["win"], "loss": P["loss"], "team_win_bonus": P["team_win_bonus"],
                   "practice": P["practice"], "absence": P["absence"],
                   "scrimmage_win": P["scrimmage_win"], "scrimmage_loss": P["scrimmage_loss"],
                   "challenge_win": P["challenge_win"], "challenge_loss": P["challenge_loss"],
                   "quiz_points": X["quiz_points"], "video_points": X["video_points"],
                   "pass_pct": X["quiz_pass_pct"], "attempts": X["quiz_attempts"],
                   "penalty": X.get("integrity_penalty", 10), "elo": dict(s.settings["elo"])}
    st["consts"] = {"positions": POSITIONS, "labels": POSITION_LABELS, "sizes": POSITION_SIZE,
                    "levels": LEVELS, "level_colors": LEVEL_COLORS,
                    "train_cats": TRAINING_CATEGORIES, "quiz_cats": QUIZ_CATEGORIES,
                    "areas": IMPROVE_AREAS, "priorities": PRIORITIES, "focus": TRAINING_FOCUS,
                    "skills": SKILLS, "ranks": [{"name": n, "color": c} for n, c in RANKS]}
    people = sorted(s.players.values(), key=lambda p: (-pts.get(p["id"], 0), p["name"].lower()))
    if not user.staff:
        people = [p for p in people if p.get("active", True)]
    st["players"] = [pub_player(p, pts.get(p["id"], 0), user) for p in people]
    st["lineup"] = s.data["lineup"]
    w, l = s.team_record()
    st["record"] = [w, l]
    st["managers"] = [{"id": m["id"], "name": m["name"]} for m in s.managers()]
    st["matches"] = s.data["matches"][:40]
    st["challenges"] = [dict(c, swap=c.get("swap") or {}) for c in s.data["challenges"][:20]]
    st["videos"] = [video_card(v, user) for v in s.data["videos"]]
    st["webhook"] = discord_notify.valid_webhook(s.settings.get("discord_webhook", ""))
    if user.pid:
        st["my_skips"] = sum(1 for x in s.data["video_log"] if x["pid"] == user.pid and x["kind"] == "skip")
    if user.staff:
        st["attendance"] = s.data["attendance"][:40]
        st["scrimmages"] = s.data["scrimmages"][:40]
        st["rankups"] = s.data["rankups"][:120]
        st["rank_history"] = s.data["rank_history"][:60]
        st["notes"] = s.data["notes"][:200]
        st["activity"] = s.data["activity"][:300]
        tp = s.training_player()
        tpts = s.training_points()
        tr = s.data["training"]
        st["training"] = {"pid": tp, "chosen": tr.get("player_id"), "points": tpts,
                          "level": s.training_level(tpts) if tpts is not None else None,
                          "sessions": [x for x in tr["sessions"] if x["pid"] == tp][:40] if tp else [],
                          "skills": tr["skills"].get(tp, {}) if tp else {}}
    elif user.pid:
        st["rankups"] = [r for r in s.data["rankups"] if r["pid"] == user.pid][:10]
    if user.role == "coach":
        st["settings"] = {"player_code": s.settings.get("player_code", ""),
                          "webhook": s.settings.get("discord_webhook", ""),
                          "mention": s.settings.get("discord_mention", ""),
                          "points": s.settings["points"], "start_points": s.settings["start_points"],
                          "rank_step": s.settings["rank_step"],
                          "level_step": s.settings["training"]["level_step"],
                          "extras": s.settings["extras"], "elo": s.settings["elo"],
                          "data_dir": str(s.dir)}
    return st


# ------------------------------------------------------------- validation
def need(body, key, kind=str, maxlen=200, required=True, default=None):
    v = body.get(key, default)
    if v is None or (kind is str and isinstance(v, str) and not v.strip() and required):
        if required:
            raise ApiError(f"Missing {key}.")
        return default
    if kind is str:
        if not isinstance(v, str):
            raise ApiError(f"{key} must be text.")
        v = v.strip()
        if len(v) > maxlen:
            raise ApiError(f"{key} is too long (max {maxlen}).")
        return v
    if kind is int:
        try:
            return int(v)
        except (TypeError, ValueError):
            raise ApiError(f"{key} must be a whole number.")
    if kind is bool:
        return bool(v)
    if kind is list:
        if not isinstance(v, list):
            raise ApiError(f"{key} must be a list.")
        return v
    if kind is dict:
        if not isinstance(v, dict):
            raise ApiError(f"{key} must be an object.")
        return v
    return v


def rng(v, lo, hi, name):
    if not lo <= v <= hi:
        raise ApiError(f"{name} must be between {lo} and {hi}.")
    return v


def player_id(pid, allow_manager=False, active=True):
    p = store.players.get(pid) if isinstance(pid, str) else None
    if not p:
        raise ApiError("That player isn't on the roster.")
    if not allow_manager and p.get("role") == "manager":
        raise ApiError("Managers don't earn team points.")
    if active and not p.get("active", True):
        raise ApiError(f"{p['name']} is inactive.")
    return pid


def iso_day(v):
    try:
        return date.fromisoformat(str(v)).isoformat()
    except ValueError:
        raise ApiError("Pick a valid date.")


def do(fn, *args, **kwargs):
    """Run a store change and return (result, events)."""
    try:
        return fn(*args, **kwargs)
    except RankUpError as e:
        raise ApiError(str(e))


# ---------------------------------------------------------------- actions
ACTIONS: dict = {}


def action(name, perm=None, readonly=False):
    def deco(fn):
        ACTIONS[name] = (perm, readonly, fn)
        return fn
    return deco


def bg(fn, *args):
    """Run slow things (Discord) without making the person wait."""
    def run():
        try:
            fn(*args)
        except Exception:
            traceback.print_exc()
    threading.Thread(target=run, daemon=True).start()


# --- roster
def _player_fields(body, pid=None):
    name = need(body, "name", maxlen=60)
    role = body.get("role", "player")
    if role not in ("player", "manager"):
        raise ApiError("Role must be player or manager.")
    username = need(body, "username", maxlen=60, required=False, default="")
    if username:
        other = store.player_for_username(username)
        if other and other["id"] != pid:
            raise ApiError(f"“{username}” is already linked to {other['name']}.")
    discord_id = need(body, "discord_id", maxlen=25, required=False, default="")
    if discord_id and not discord_id.isdigit():
        raise ApiError("Discord user ID is only numbers.")
    return dict(name=name, grade=need(body, "grade", maxlen=10, required=False, default=""),
                student_id=need(body, "student_id", maxlen=20, required=False, default=""),
                role=role, notes=need(body, "notes", maxlen=300, required=False, default=""),
                username=username, discord_id=discord_id)


@action("player.add", "edit_roster")
def a_player_add(u, b):
    f = _player_fields(b)
    pid, ev = do(store.add_player, f["name"], f["grade"], f["student_id"], f["role"], f["notes"],
                 f["username"], f["discord_id"])
    return pid, ev, f"Added {f['name']} with {store.settings['start_points']} points"


@action("player.update", "edit_roster")
def a_player_update(u, b):
    pid = player_id(b.get("id"), allow_manager=True, active=False)
    f = _player_fields(b, pid)
    f["active"] = bool(b.get("active", True))
    _, ev = do(store.update_player, pid, **f)
    return None, ev, "Saved"


@action("player.remove", "edit_roster")
def a_player_remove(u, b):
    pid = player_id(b.get("id"), allow_manager=True, active=False)
    _, ev = do(store.remove_player, pid)
    return None, ev, "Removed"


@action("player.reset_pin", "edit_roster")
def a_reset_pin(u, b):
    pid = player_id(b.get("id"), active=False)
    _, ev = do(store.reset_pin, pid)
    return None, ev, f"PIN reset — {store.player_name(pid)} makes a new one next sign-in"


@action("points.adjust", "adjust")
def a_adjust(u, b):
    pids = [player_id(p) for p in need(b, "pids", list)]
    if not pids:
        raise ApiError("Pick at least one player.")
    delta = rng(need(b, "delta", int), -1000, 1000, "Points")
    if delta == 0:
        raise ApiError("Points can't be 0.")
    reason = need(b, "reason", maxlen=120, required=False, default="") or ("Bonus" if delta > 0 else "Penalty")
    _, ev = do(store.adjust_points, pids, delta, reason)
    return None, ev, f"{delta:+d} points saved"


@action("history.get", readonly=True)
def a_history(u, b):
    pid = b.get("id")
    if pid not in store.players:
        raise ApiError("Unknown player.")
    if not (u.staff or u.pid == pid):
        raise ApiError("You can only see your own history.", 403)
    off = max(0, int(b.get("offset", 0) or 0))
    entries = [e for e in store.data["ledger"] if e["pid"] == pid][::-1]
    ranks = [dict(h, from_name=store.level_name(h["from"])[0], to_name=store.level_name(h["to"])[0])
             for h in store.data["rank_history"] if h["pid"] == pid][:10]
    page = [{k: e.get(k) for k in ("delta", "reason", "ts", "by")} for e in entries[off:off + 60]]
    return {"entries": page, "total": len(entries), "ranks": ranks,
            "stats": store.player_stats(pid)}, [], ""


# --- lineup & challenges
@action("lineup.set", "lineup")
def a_lineup(u, b):
    lu = need(b, "lineup", dict)
    clean, seen = {}, set()
    for pos in POSITIONS:
        ids = [x for x in (lu.get(pos) or []) if x][:POSITION_SIZE[pos]]
        for x in ids:
            player_id(x)
            if x in seen:
                raise ApiError("A player can only be in one spot.")
            seen.add(x)
        clean[pos] = ids
    _, ev = do(store.set_lineup, clean)
    return None, ev, "Lineup saved"


@action("challenge.record", "challenge")
def a_challenge(u, b):
    c, d = player_id(b.get("challenger")), player_id(b.get("defender"))
    if c == d:
        raise ApiError("Pick two different players.")
    who = b.get("winner")
    if who not in ("challenger", "defender"):
        raise ApiError("Pick who won.")
    winner = c if who == "challenger" else d
    swap, ev = do(store.record_challenge, c, d, winner, need(b, "score", maxlen=60, required=False, default=""))
    gained = store.data["challenges"][0].get("gain")
    msg = (f"{store.player_name(c)} takes {POSITION_LABELS[swap['to']]}!" if swap else "Challenge recorded")
    if gained:
        msg += f" (+{gained} for {store.player_name(winner)})"
    return swap, ev, msg


# --- matches
@action("match.record", "match")
def a_match(u, b):
    day = iso_day(b.get("date"))
    opp = need(b, "opponent", maxlen=80)
    res = need(b, "results", dict)
    results, used = {}, []
    for pos in POSITIONS:
        r = res.get(pos) or {}
        played = bool(r.get("played", True))
        ids = [x for x in (r.get("players") or []) if x]
        if played:
            if len(ids) != POSITION_SIZE[pos]:
                raise ApiError(f"Pick {'both players' if POSITION_SIZE[pos] == 2 else 'a player'} for "
                               f"{POSITION_LABELS[pos]} (or mark it Not played).")
            for x in ids:
                player_id(x)
            used += ids
        score = str(r.get("score", ""))[:60]
        results[pos] = {"players": ids if played else [], "won": bool(r.get("won")), "score": score,
                        "played": played}
    if len(used) != len(set(used)):
        raise ApiError("A player is listed in two positions.")
    if not used:
        raise ApiError("Mark at least one position as played.")
    won, ev = do(store.record_match, day, opp, bool(b.get("home", True)), results)
    return won, ev, f"Match saved — {'WIN' if won else 'loss'} vs {opp}"


@action("match.delete", "delete")
def a_match_del(u, b):
    mid = b.get("id")
    if not any(m["id"] == mid for m in store.data["matches"]):
        raise ApiError("That match is already gone.")
    _, ev = do(store.delete_match, mid)
    return None, ev, "Match deleted (points taken back)"


# --- practice
@action("attendance.get", "practice", readonly=True)
def a_att_get(u, b):
    return store.attendance_for(iso_day(b.get("date"))), [], ""


@action("attendance.save", "practice")
def a_att_save(u, b):
    day = iso_day(b.get("date"))
    present = [player_id(x) for x in need(b, "present", list)]
    absent = [player_id(x) for x in need(b, "absent", list)]
    exc = need(b, "excused", dict)
    excused = {}
    for pid, why in exc.items():
        player_id(pid)
        why = str(why or "").strip()[:120]
        if not why:
            raise ApiError(f"Add a reason for {store.player_name(pid)}'s excused absence.")
        excused[pid] = why
    allp = present + absent + list(excused)
    if len(allp) != len(set(allp)):
        raise ApiError("Each player can only have one status.")
    if not allp:
        raise ApiError("Nobody is marked.")
    replaced, ev = do(store.record_attendance, day, present, absent, excused)
    return replaced, ev, f"Attendance saved for {day}" + (" (replaced)" if replaced else "")


@action("attendance.delete", "delete")
def a_att_del(u, b):
    _, ev = do(store.delete_attendance, b.get("id"))
    return None, ev, "Practice removed (points reversed)"


@action("scrimmage.record", "practice")
def a_scrim(u, b):
    a_, b_ = need(b, "a", list), need(b, "b", list)
    if len(a_) != len(b_) or len(a_) not in (1, 2):
        raise ApiError("Pick 1 player per side for singles or 2 for doubles.")
    for x in a_ + b_:
        player_id(x)
    if len(set(a_ + b_)) != len(a_ + b_):
        raise ApiError("Each player can only be on one side once.")
    w = b.get("winner")
    if w not in ("A", "B"):
        raise ApiError("Pick the winning side.")
    res, ev = do(store.record_scrimmage, a_, b_, w, need(b, "score", maxlen=60, required=False, default=""))
    return res, ev, f"Scrimmage recorded — winners +{res['gain']}, losers −{res['loss']}"


@action("scrimmage.delete", "delete")
def a_scrim_del(u, b):
    _, ev = do(store.delete_scrimmage, b.get("id"))
    return None, ev, "Scrimmage removed (points reversed)"


# --- rank-up matches
@action("rankup.request")
def a_ru_request(u, b):
    pid = b.get("id") or u.pid
    if u.role == "player":
        if not u.pid or pid != u.pid:
            raise ApiError("You can only request your own rank-up match.", 403)
    elif not u.can("rank"):
        raise ApiError("Not allowed.", 403)
    player_id(pid)
    mgr = b.get("manager") or None
    if mgr and (mgr not in store.players or store.players[mgr].get("role") != "manager"):
        raise ApiError("Pick a manager from the list.")
    rid, ev = do(store.request_rankup, pid, mgr, need(b, "message", maxlen=200, required=False, default=""),
                 u.username or u.log_name)
    hook = store.settings.get("discord_webhook", "")
    if discord_notify.valid_webhook(hook):
        req = dict(store.rankup(rid))
        bg(discord_notify.send_rankup_request, hook, store, req, store.settings.get("discord_mention", ""))
        msg = "Rank-up match requested — the manager was pinged on Discord"
    else:
        msg = "Rank-up match requested — tell your manager too"
    return rid, ev, msg


def _rankup(rid, open_only=True):
    r = store.rankup(rid)
    if not r:
        raise ApiError("That request is gone.")
    if open_only and r["status"] not in RANKUP_OPEN:
        raise ApiError("That request is already closed.")
    return r


@action("rankup.schedule", "rank")
def a_ru_schedule(u, b):
    r = _rankup(b.get("id"))
    when = date.fromisoformat(iso_day(b.get("date"))).strftime("%a %b %d")
    t = need(b, "time", maxlen=40, required=False, default="")
    if t:
        when += f", {t}"
    _, ev = do(store.schedule_rankup, r["id"], when, need(b, "details", maxlen=120, required=False, default=""))
    return None, ev, f"Scheduled for {when}"


@action("rankup.decide", "rank")
def a_ru_decide(u, b):
    r = _rankup(b.get("id"))
    passed = bool(b.get("passed"))
    _, ev = do(store.decide_rankup, r["id"], passed, need(b, "score", maxlen=60, required=False, default=""),
               need(b, "note", maxlen=200, required=False, default=""))
    hook = store.settings.get("discord_webhook", "")
    if discord_notify.valid_webhook(hook):
        bg(discord_notify.send_rankup_result, hook, store, dict(store.rankup(r["id"])))
    to = store.level_name(r["to_level"])[0]
    return None, ev, (f"{store.player_name(r['pid'])} is now {to}!" if passed else "Result saved")


@action("rankup.cancel")
def a_ru_cancel(u, b):
    r = _rankup(b.get("id"))
    if not (u.can("rank") or (u.pid and u.pid == r["pid"])):
        raise ApiError("Not allowed.", 403)
    why = "Cancelled by the player" if u.role == "player" else "Cancelled by a manager"
    _, ev = do(store.cancel_rankup, r["id"], why)
    return None, ev, "Request cancelled"


@action("rank.set", "rank")
def a_rank_set(u, b):
    pid = player_id(b.get("id"))
    step = need(b, "step", int)
    if step not in (-1, 1):
        raise ApiError("Rank changes go one step at a time.")
    reason = need(b, "reason", maxlen=120)
    lvl = store.rank_level(pid) + step
    if lvl < 0:
        raise ApiError("They're already at the lowest rank.")
    _, ev = do(store.set_rank, pid, lvl, reason)
    return None, ev, f"{store.player_name(pid)} is now {store.level_name(lvl)[0]}"


# --- videos & quizzes
def _video(vid):
    v = store.video(vid)
    if not v:
        raise ApiError("That video was removed.")
    return v


@action("video.save", "videos")
def a_video_save(u, b):
    vid = b.get("id") or None
    if vid:
        _video(vid)
    kind = b.get("kind")
    if kind not in ("quiz", "optional"):
        raise ApiError("Unknown video type.")
    title = need(b, "title", maxlen=120)
    url = need(b, "url", maxlen=300)
    if not WS.youtube_id(url):
        raise ApiError("Use a YouTube link — only YouTube videos can be tracked for skipping.")
    cats = QUIZ_CATEGORIES if kind == "quiz" else TRAINING_CATEGORIES
    cat = b.get("category")
    if cat not in cats:
        raise ApiError("Pick a category.")
    level = b.get("level")
    if level not in LEVELS:
        raise ApiError("Pick a level.")
    minutes = rng(need(b, "minutes", int), 0, 180, "Minimum minutes")
    points = rng(need(b, "points", int), 0, 500, "Points")
    questions = []
    if kind == "quiz":
        qs = need(b, "questions", list)
        if not 1 <= len(qs) <= 30:
            raise ApiError("Add between 1 and 30 questions.")
        for i, q in enumerate(qs, 1):
            text = str(q.get("q", "")).strip()[:300]
            opts = [str(o or "").strip()[:200] for o in (q.get("options") or [])][:4]
            opts += [""] * (4 - len(opts))
            try:
                ans = int(q.get("answer", -1))
            except (TypeError, ValueError):
                ans = -1
            if not text:
                raise ApiError(f"Question {i} is empty.")
            if sum(1 for o in opts if o) < 2:
                raise ApiError(f"Question {i} needs at least two answers.")
            if not 0 <= ans < 4 or not opts[ans]:
                raise ApiError(f"Question {i}: pick which answer is correct.")
            questions.append({"q": text, "options": opts, "answer": ans})
    nid, ev = do(store.save_video, vid, kind, title, url, cat, minutes, points, questions, "", level)
    return nid, ev, "Video saved"


@action("video.delete", "videos")
def a_video_del(u, b):
    _video(b.get("id"))
    _, ev = do(store.delete_video, b.get("id"))
    return None, ev, "Video deleted (points already earned are kept)"


@action("video.starters", "videos")
def a_video_starters(u, b):
    kind = b.get("kind")
    if kind not in ("quiz", "optional"):
        raise ApiError("Unknown video type.")
    n = starter_content.load_starters(store, kind)
    return n, [], f"Added {n} starter videos — preview them and swap any you don't like"


@action("video.full", "videos", readonly=True)
def a_video_full(u, b):
    return _video(b.get("id")), [], ""


@action("video.status", "quiz_others", readonly=True)
def a_video_status(u, b):
    pid = player_id(b.get("id"), active=False)
    return {v["id"]: status_summary(store.video_status(pid, v["id"])) for v in store.data["videos"]}, [], ""


def _self_pid(u):
    if not u.pid:
        raise ApiError("Videos and quizzes count for players signed in as themselves.", 403)
    return u.pid


@action("watch.start")
def a_watch(u, b):
    pid = _self_pid(u)
    v = _video(b.get("id"))
    st = store.video_status(pid, v["id"])
    if st["skipped"]:
        raise ApiError("Skipping was detected on this video, so it can't earn points.")
    try:
        sess = WATCH.start_session(pid, v)
    except ValueError as e:
        raise ApiError(str(e))
    return {"url": f"/watch/{sess.token}"}, [], ""


@action("quiz.get", readonly=True)
def a_quiz_get(u, b):
    pid = _self_pid(u)
    v = _video(b.get("id"))
    st = store.video_status(pid, v["id"])
    if v["kind"] != "quiz":
        raise ApiError("That video has no quiz.")
    if st["skipped"]:
        raise ApiError("Skipping was detected on this video, so its quiz can't earn points.")
    if not st["viewed"]:
        raise ApiError("Watch the whole video first — then the quiz unlocks.")
    if st["passed"]:
        raise ApiError("You already passed this quiz.")
    if st["attempts_left"] <= 0:
        raise ApiError("No tries left — ask a coach or manager to reset this quiz.")
    qs = [{"q": q["q"], "options": [o for o in q["options"]]} for q in v["questions"]]  # no answers
    return {"title": v["title"], "points": v["points"], "questions": qs, "left": st["attempts_left"]}, [], ""


@action("quiz.submit")
def a_quiz_submit(u, b):
    pid = _self_pid(u)
    v = _video(b.get("id"))
    answers = need(b, "answers", list)
    ans = []
    for a_ in answers[:len(v.get("questions") or [])]:
        try:
            ans.append(int(a_))
        except (TypeError, ValueError):
            ans.append(-1)
    res, ev = do(store.submit_quiz, pid, v["id"], ans)
    msg = f"Passed! +{res['points']} points" if res["passed"] else f"{res['score']}/{res['total']} — not quite"
    return res, ev, msg


@action("quiz.reset", "videos")
def a_quiz_reset(u, b):
    pid = player_id(b.get("pid"), active=False)
    _video(b.get("id"))
    _, ev = do(store.reset_quiz, pid, b.get("id"))
    return None, ev, "Tries reset"


@action("video.clear_skip", "videos")
def a_clear_skip(u, b):
    pid = player_id(b.get("pid"), active=False)
    _video(b.get("id"))
    _, ev = do(store.clear_skip, pid, b.get("id"))
    return None, ev, "They can watch it again (the −points stay)"


# --- 1st singles training
@action("training.set_player", "training")
def a_tr_player(u, b):
    pid = b.get("id") or None
    if pid:
        player_id(pid)
    _, ev = do(store.set_training_player, pid)
    return None, ev, "Training player updated"


@action("training.log", "training")
def a_tr_log(u, b):
    pid = store.training_player()
    if not pid:
        raise ApiError("Set a 1st singles player first.")
    focus = b.get("focus")
    if focus not in TRAINING_FOCUS:
        raise ApiError("Pick a focus.")
    skills = _skills(b.get("skills") or {})
    _, ev = do(store.log_training, pid, need(b, "manager", maxlen=60), focus,
               rng(need(b, "minutes", int), 1, 600, "Minutes"), rng(need(b, "effort", int), 1, 5, "Effort"),
               rng(need(b, "points", int), 0, 500, "Points"), need(b, "notes", maxlen=300, required=False, default=""),
               skills)
    return None, ev, "Training session logged"


def _skills(d):
    out = {}
    for k, v in (d or {}).items():
        if k in SKILLS:
            try:
                out[k] = max(1, min(10, int(v)))
            except (TypeError, ValueError):
                pass
    return out


@action("training.skills", "training")
def a_tr_skills(u, b):
    pid = store.training_player()
    if not pid:
        raise ApiError("Set a 1st singles player first.")
    sk = _skills(b.get("skills"))
    _, ev = do(store.mutate, lambda d: d["training"]["skills"].setdefault(pid, {}).update(sk),
               f"Updated skill ratings for {store.player_name(pid)}")
    return None, ev, "Ratings saved"


@action("training.delete", "delete")
def a_tr_del(u, b):
    _, ev = do(store.delete_training, b.get("id"))
    return None, ev, "Session deleted"


# --- improvement notes
def _send_notes(notes, u):
    hook = store.settings.get("discord_webhook", "")
    if not discord_notify.valid_webhook(hook):
        raise ApiError("Add the managers' Discord webhook in Settings first.")
    try:
        discord_notify.send_notes(hook, notes, store, u.log_name, store.settings.get("discord_mention", ""))
    except discord_notify.WebhookError as e:
        raise ApiError(str(e))
    ids = {n["id"] for n in notes}
    store.mutate(lambda d: [n.__setitem__("sent", True) for n in d["notes"] if n["id"] in ids],
                 f"Sent {len(ids)} improvement note(s) to managers on Discord")


@action("note.add", "notes")
def a_note_add(u, b):
    pid = player_id(b.get("pid"), allow_manager=True)
    area = b.get("area")
    if area not in IMPROVE_AREAS:
        raise ApiError("Pick what they need to improve.")
    prio = b.get("priority")
    if prio not in PRIORITIES:
        raise ApiError("Pick a priority.")
    nid, ev = do(store.add_note, pid, area, prio, need(b, "text", maxlen=500, required=False, default=""))
    msg = "Note added"
    if b.get("send"):
        note = next(n for n in store.data["notes"] if n["id"] == nid)
        try:
            _send_notes([note], u)
            msg = "Note added and sent to managers on Discord"
        except ApiError as e:
            msg = f"Note added, but Discord didn't send: {e}"
    return nid, ev, msg


@action("note.resolve", "notes")
def a_note_resolve(u, b):
    _, ev = do(store.update_note, b.get("id"), resolved=bool(b.get("resolved")))
    return None, ev, "Updated"


@action("note.delete", "notes")
def a_note_del(u, b):
    _, ev = do(store.delete_note, b.get("id"))
    return None, ev, "Note deleted"


@action("note.send", "notes")
def a_note_send(u, b):
    ids = b.get("ids")
    notes = store.open_notes() if ids in (None, "open") else [n for n in store.data["notes"] if n["id"] in set(ids)]
    if not notes:
        raise ApiError("There are no notes to send.")
    _send_notes(notes, u)
    return None, [], f"Sent {len(notes)} note(s) to managers on Discord"


# --- settings (coach)
@action("settings.team", "settings")
def a_set_team(u, b):
    vals = {"name": need(b, "name", maxlen=60), "school": need(b, "school", maxlen=80, required=False, default=""),
            "season": need(b, "season", maxlen=20, required=False, default="")}
    _, ev = do(store.mutate, lambda d: d["team"].update(vals), "Updated team info")
    return None, ev, "Team info saved"


@action("settings.player_code", "settings")
def a_set_code(u, b):
    code = need(b, "code", maxlen=40, required=False, default="")
    if code and len(code) < 4:
        raise ApiError("Make the team code at least 4 characters.")
    _, ev = do(store.mutate, lambda d: d["settings"].__setitem__("player_code", code),
               "Changed the player team code" if code else "Turned off player sign-in")
    return None, ev, "Player sign-in is on" if code else "Player sign-in turned off"


@action("settings.points", "settings")
def a_set_points(u, b):
    vals = need(b, "values", dict)
    num = {}
    for k, v in vals.items():
        try:
            num[k] = int(v)
        except (TypeError, ValueError):
            raise ApiError("Point values must be whole numbers.")
        rng(num[k], -1000, 10000, k)
    if num.get("rank_step", 1) <= 0 or num.get("level_step", 1) <= 0:
        raise ApiError("Points per rank must be more than 0.")

    def fn(d):
        st = d["settings"]
        for k, v in num.items():
            if k.startswith("win.") and k[4:] in POSITIONS:
                st["points"]["win"][k[4:]] = v
            elif k == "level_step":
                st["training"]["level_step"] = v
            elif k in ("start_points", "rank_step"):
                st[k] = v
            elif k in st["points"] and k != "win":
                st["points"][k] = v
    _, ev = do(store.mutate, fn, "Updated point values")
    return None, ev, "Point values saved"


@action("settings.extras", "settings")
def a_set_extras(u, b):
    vals = need(b, "values", dict)
    num = {}
    for k, v in vals.items():
        try:
            num[k] = int(v)
        except (TypeError, ValueError):
            raise ApiError("Values must be whole numbers.")
    if not 1 <= num.get("quiz_pass_pct", 70) <= 100 or num.get("quiz_attempts", 3) < 1:
        raise ApiError("Pass % must be 1–100 and tries at least 1.")

    def fn(d):
        X = d["settings"]["extras"]
        for k, v in num.items():
            if k.startswith("quiz.") and k[5:] in LEVELS:
                X["quiz_points"][k[5:]] = v
            elif k.startswith("video.") and k[6:] in LEVELS:
                X["video_points"][k[6:]] = v
            elif k in ("quiz_pass_pct", "quiz_attempts"):
                X[k] = v
            elif k == "integrity_penalty":
                X[k] = abs(v)
    _, ev = do(store.mutate, fn, "Updated video & quiz points")
    return None, ev, "Extra points saved"


@action("settings.elo", "settings")
def a_set_elo(u, b):
    vals = need(b, "values", dict)
    try:
        k = rng(int(vals.get("k", 32)), 0, 100, "K")
        lo = rng(int(vals.get("min_pct", 25)), 0, 100, "Smallest change %")
        hi = rng(int(vals.get("max_pct", 200)), 100, 500, "Biggest change %")
    except (TypeError, ValueError):
        raise ApiError("Values must be whole numbers.")
    _, ev = do(store.mutate, lambda d: d["settings"]["elo"].update(k=k, min_pct=lo, max_pct=hi),
               "Updated skill-based points")
    return None, ev, "Skill-based points " + ("saved" if k else "turned off")


@action("settings.discord", "settings")
def a_set_discord(u, b):
    url = need(b, "webhook", maxlen=300, required=False, default="")
    if url and not discord_notify.valid_webhook(url):
        raise ApiError("That isn't a Discord webhook URL.")
    mention = need(b, "mention", maxlen=80, required=False, default="")
    _, ev = do(store.mutate, lambda d: d["settings"].update(discord_webhook=url, discord_mention=mention),
               "Updated the Discord webhook")
    return None, ev, "Webhook saved"


@action("settings.discord_test", "settings", readonly=True)
def a_discord_test(u, b):
    url = store.settings.get("discord_webhook", "")
    try:
        discord_notify.send_test(url, store.data["team"].get("name", "PSAL Badminton"))
    except discord_notify.WebhookError as e:
        raise ApiError(str(e))
    return None, [], "Test message sent — check Discord"


@action("season.new", "settings")
def a_season(u, b):
    name = need(b, "name", maxlen=20)
    path, ev = do(store.new_season, name)
    return None, ev, f"New season {name} started (old season archived)"


# --- my account
@action("me.pin")
def a_me_pin(u, b):
    if u.kind != "pin":
        raise ApiError("Only players who sign in with a PIN can change it here.")
    if not store.check_pin(u.pid, str(b.get("old", ""))):
        raise ApiError("Your current PIN isn't right.")
    new, new2 = str(b.get("new", "")), str(b.get("new2", ""))
    if not store.valid_pin(new):
        raise ApiError("Your new PIN must be 4 to 8 digits.")
    if new != new2:
        raise ApiError("The new PINs don't match.")
    _, ev = do(store.set_pin, u.pid, new)
    session["pv"] = (store.players[u.pid].get("pin_salt") or "")[:12]
    return None, ev, "PIN changed"


# --------------------------------------------------------------- endpoints
def require_csrf():
    # Cross-site forms can't send custom headers, and cross-site scripts can't read replies
    if request.headers.get("X-PSAL") != "1":
        abort(403)


@app.errorhandler(ApiError)
def _api_error(e):
    return jsonify(error=str(e)), e.code


@app.post("/api/do/<name>")
def api_do(name):
    require_csrf()
    if name not in ACTIONS:
        return jsonify(error="Unknown action."), 404
    perm, readonly, fn = ACTIONS[name]
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify(error="Bad request."), 400
    with LOCK:
        fresh_store()
        u = current_user()
        if u is None:
            return jsonify(error="Please sign in again.", signin=True), 401
        if perm and not u.can(perm):
            return jsonify(error="Your account isn't allowed to do that."), 403
        store.user = u.log_name
        try:
            result, events, msg = fn(u, body)
        except ApiError:
            raise
        except Exception:
            traceback.print_exc()
            return jsonify(error="Something went wrong saving that. Nothing was changed."), 500
        out = {"ok": True, "result": result, "events": events or [], "msg": msg}
        if not readonly:
            out["state"] = build_state(u)
        return jsonify(out)


@app.get("/api/state")
def api_state():
    with LOCK:
        fresh_store()
        u = current_user()
        if u is None:
            return jsonify(signin=True, login=login_info())
        if request.args.get("v") == str(store.version) and request.args.get("u") == u.username:
            return jsonify(same=True)
        return jsonify(build_state(u))


def login_info():
    return {"build": APP_BUILD, "player_signin": bool(store.settings.get("player_code")),
            "team": store.data["team"].get("name", "PSAL Badminton")}


# --- sign in / out
KA = {}


def _keyauth_config():
    if not KA:
        import main as keyauth_main  # single source of truth for the KeyAuth app details
        ka = keyauth_main.keyauthapp
        KA.update(name=ka.name, ownerid=ka.ownerid, version=ka.version, hash=ka.hash_to_check)
    return KA


@app.post("/api/login/key")
def login_key():
    require_csrf()
    b = request.get_json(silent=True) or {}
    ip = client_ip()
    mode = b.get("mode", "login")
    user = str(b.get("username", "")).strip()[:60]
    pw = str(b.get("password", ""))[:200]
    key = str(b.get("key", "")).strip()[:120]
    code = str(b.get("code", "")).strip()[:10] or None
    if not LIMIT.allow(("key-ip", ip), 12, 600) or (user and not LIMIT.allow(("key-user", user.lower()), 8, 600)):
        return jsonify(error="Too many sign-in attempts. Wait 10 minutes and try again."), 429
    if mode == "login" and not (user and pw):
        return jsonify(error="Enter your username and password."), 400
    if mode == "register" and not (user and pw and key):
        return jsonify(error="Username, password and license key are all required."), 400
    if mode == "license" and not key:
        return jsonify(error="Paste your license key."), 400
    cfg = _keyauth_config()
    ka = KeyAuthApi(cfg["name"], cfg["ownerid"], cfg["version"], cfg["hash"])
    hwid = "web-" + hashlib.sha256((user or key).lower().encode()).hexdigest()[:24]
    try:
        ka.init()
        if mode == "register":
            ka.register(user, pw, key, hwid=hwid)
        elif mode == "license":
            ka.license(key, code, hwid=hwid)
        else:
            ka.login(user, pw, code, hwid=hwid)
    except KeyAuthError as e:
        msg = str(e)
        if "hwid" in msg.lower():
            msg += (" — turn off the HWID (hardware) lock for this app in KeyAuth, or reset this "
                    "user's HWID, so they can sign in from both the website and the desktop app.")
        return jsonify(error=msg), 401
    ud = ka.user_data
    role = role_from_subscriptions(ud.subscriptions)
    try:
        exp = min(int(s.get("expiry")) for s in ud.subscriptions if str(s.get("expiry", "")).isdigit())
    except ValueError:
        exp = None
    named = mode != "license"
    session.clear()
    session.permanent = True
    session.update(k="key", u=ud.username or user, role=role, named=named,
                   name=(ud.username or user) if named else "", exp=exp, t=time.time())
    return jsonify(ok=True)


@app.post("/api/login/names")
def login_names():
    require_csrf()
    ip = client_ip()
    wait = LIMIT.locked(("code", ip))
    if wait:
        return jsonify(error=f"Too many wrong team codes. Try again in {wait_text(wait)}."), 429
    code = str((request.get_json(silent=True) or {}).get("code", ""))[:60]
    with LOCK:
        fresh_store()
        if not store.settings.get("player_code"):
            return jsonify(error="Player sign-in is turned off. Ask your coach."), 400
        if not store.player_code_ok(code):
            secs = LIMIT.fail(("code", ip), every=8, steps=(300, 1800, 7200))
            return jsonify(error="That team code isn't right." +
                           (f" Locked for {wait_text(secs)}." if secs else "")), 401
        LIMIT.ok(("code", ip))
        ps = [p for p in store.active_players() if p.get("role") != "manager"]
        return jsonify(players=[{"id": p["id"], "name": p["name"], "has_pin": store.has_pin(p["id"])}
                                for p in ps])


@app.post("/api/login/player")
def login_player():
    require_csrf()
    b = request.get_json(silent=True) or {}
    ip = client_ip()
    if LIMIT.locked(("code", ip)):
        return jsonify(error="Too many wrong attempts. Try again later."), 429
    if not LIMIT.allow(("pin-ip", ip), 40, 3600):
        return jsonify(error="Too many sign-in attempts from this network. Try again later."), 429
    pid = str(b.get("pid", ""))
    pin, pin2 = str(b.get("pin", "")).strip(), str(b.get("pin2", "")).strip()
    with LOCK:
        fresh_store()
        if not store.player_code_ok(str(b.get("code", ""))):
            LIMIT.fail(("code", ip), every=8, steps=(300, 1800, 7200))
            return jsonify(error="That team code isn't right."), 401
        p = store.players.get(pid)
        if not p or not p.get("active", True) or p.get("role") == "manager":
            return jsonify(error="Pick your name."), 400
        wait = LIMIT.locked(("pin", pid))
        if wait:
            return jsonify(error=f"Too many wrong PINs. Try again in {wait_text(wait)}."), 429
        if store.has_pin(pid):
            if not store.check_pin(pid, pin):
                secs = LIMIT.fail(("pin", pid))
                return jsonify(error="Wrong PIN." + (f" Locked for {wait_text(secs)}." if secs else
                                                      " Forgot it? Ask your coach to reset it.")), 401
        else:
            if not store.valid_pin(pin):
                return jsonify(error="Make a PIN with 4 to 8 digits."), 400
            if pin != pin2:
                return jsonify(error="The two PINs don't match."), 400
            store.user = p["name"]
            store.set_pin(pid, pin)
        LIMIT.ok(("pin", pid))
        session.clear()
        session.permanent = True
        session.update(k="pin", pid=pid, pv=(store.players[pid].get("pin_salt") or "")[:12], t=time.time())
        return jsonify(ok=True)


@app.post("/api/login/dev")
def login_dev():
    """Automated tests only: enabled with --dev-login, and only from this PC."""
    if not DEV_LOGIN or not peer_is_local() or request.headers.get("X-Forwarded-For") \
            or request.headers.get("CF-Connecting-IP"):
        abort(404)
    require_csrf()
    b = request.get_json(silent=True) or {}
    session.clear()
    session.update(k="dev", u=b.get("username", "dev"), role=b.get("role", "coach"), named=True,
                   name=b.get("username", "dev"), t=time.time())
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    require_csrf()
    session.clear()
    return jsonify(ok=True)


# --- exports / import (coach)
def _coach():
    u = current_user()
    if u is None or not u.can("settings"):
        abort(403)
    return u


@app.get("/api/export/backup.json")
def export_backup():
    with LOCK:
        fresh_store()
        _coach()
        data = json.dumps(store.data, indent=2).encode()
    return Response(data, mimetype="application/json", headers={
        "Content-Disposition": f'attachment; filename="psal-badminton-backup-{date.today()}.json"'})


@app.get("/api/export/leaderboard.csv")
def export_csv():
    with LOCK:
        fresh_store()
        _coach()
        fd, tmp = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        store.export_csv(tmp)
        data = Path(tmp).read_bytes()
        os.remove(tmp)
    return Response(data, mimetype="text/csv", headers={
        "Content-Disposition": f'attachment; filename="leaderboard-{date.today()}.csv"'})


@app.post("/api/import")
def import_backup():
    require_csrf()
    with LOCK:
        fresh_store()
        u = _coach()
        f = request.files.get("file")
        if not f:
            return jsonify(error="Choose a backup file."), 400
        raw = f.read()
        try:
            data = json.loads(raw)
            assert isinstance(data, dict) and "players" in data
        except Exception:
            return jsonify(error="That isn't a PSAL Badminton backup file."), 400
        fd, tmp = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        Path(tmp).write_bytes(raw)
        store.user = u.log_name
        try:
            store.import_json(tmp)
        finally:
            os.remove(tmp)
        return jsonify(ok=True, msg="Backup imported (the old data was saved in the data folder)",
                       state=build_state(u))


# ------------------------------------------------------ verified watching
class WebWatch(WS.WatchServer):
    """The website serves the player page and heartbeats itself."""

    def start(self):
        if self.httpd is None:
            self.httpd = True  # marker: running inside the website
            self.port = 0
            threading.Thread(target=self._watchdog_loop, daemon=True).start()

    def _watchdog_loop(self):
        while True:
            time.sleep(5)
            now = self.clock()
            for s in list(self.sessions.values()):
                with s.lock:
                    if s.state not in WS.FINAL and now - s.last_seen > WS.ABANDON_AFTER_S:
                        self._finish(s, "abandoned", "player closed")
            # forget finished sessions after an hour
            for tok, s in list(self.sessions.items()):
                if s.state in WS.FINAL and now - s.last_seen > 3600:
                    self.sessions.pop(tok, None)

    def start_session(self, pid, v):
        sess, _ = self.new_session(pid, v["id"], v["url"], v["title"], 60 * int(v.get("minutes", 0)),
                                   store.player_name(pid))
        return sess


def on_watch_end(sess):
    """Called when a watch session ends: give points, or apply the skipping penalty."""
    with LOCK:
        fresh_store()
        store.user = store.player_name(sess.pid)
        try:
            if sess.state == "done":
                store.complete_video(sess.pid, sess.vid, sess.credited)
            elif sess.state == "skipped":
                store.flag_skip(sess.pid, sess.vid, sess.reason)
        except RankUpError:
            pass
        except Exception:
            traceback.print_exc()


WATCH = WebWatch(on_watch_end)


@app.get("/watch/<token>")
def watch_page(token):
    s = WATCH.sessions.get(token)
    with LOCK:
        fresh_store()
        u = current_user()
    if not s or u is None or u.pid != s.pid:
        return Response("This video link has expired. Open the video again from the app.",
                        404, mimetype="text/plain")
    nonce = secrets.token_urlsafe(12)
    v = store.video(s.vid) or {}
    back = "/#/quizzes" if v.get("kind") == "quiz" else "/#/videos"
    page = WATCH.page(s).replace("<script>", f'<script nonce="{nonce}">')
    page = page.replace('<div class="kicker">',
                        f'<a href="{back}" style="color:#8b94a5;text-decoration:none;font-size:14px;'
                        'display:inline-block;margin-bottom:10px">← Back to the app</a>'
                        '<div class="kicker">', 1)
    page = page.replace("Your points are in the app.", "Your points are in the app — tap “Back to the app”.")
    r = Response(page, mimetype="text/html")
    r.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://www.youtube.com https://s.ytimg.com; "
        "frame-src https://www.youtube.com https://www.youtube-nocookie.com; "
        "img-src 'self' data: https://i.ytimg.com; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
    return r


@app.post("/hb/<token>")
def watch_heartbeat(token):
    if token not in WATCH.sessions:
        return jsonify(state="abandoned", message="Session ended.")
    raw = request.get_data(cache=False, as_text=False)[:4096]
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return jsonify(WATCH.heartbeat(token, data))


# ------------------------------------------------------------ static files
_STATIC: dict = {}


def _asset(name):
    """Loads a file from web/ once, with a gzipped copy and a content hash."""
    if name not in _STATIC:
        p = (WEB / name).resolve()
        if WEB.resolve() not in p.parents or not p.is_file():
            return None
        raw = p.read_bytes()
        _STATIC[name] = {"raw": raw, "gz": gzip.compress(raw, 6),
                         "etag": hashlib.sha1(raw).hexdigest()[:16]}
    return _STATIC[name]


TYPES = {".js": "application/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".png": "image/png", ".webmanifest": "application/manifest+json", ".svg": "image/svg+xml",
         ".html": "text/html; charset=utf-8", ".ico": "image/x-icon"}


def _send_asset(name, immutable=False):
    a = _asset(name)
    if a is None:
        abort(404)
    if request.headers.get("If-None-Match") == a["etag"]:
        return Response(status=304)
    ctype = TYPES.get(Path(name).suffix, "application/octet-stream")
    gz = "gzip" in request.headers.get("Accept-Encoding", "") and not ctype.startswith("image/")
    r = Response(a["gz"] if gz else a["raw"], mimetype=ctype.split(";")[0])
    r.headers["Content-Type"] = ctype
    if gz:
        r.headers["Content-Encoding"] = "gzip"
    r.headers["Vary"] = "Accept-Encoding"
    r.headers["ETag"] = a["etag"]
    r.headers["Cache-Control"] = "public, max-age=31536000, immutable" if immutable else "no-cache"
    return r


@app.get("/")
def index():
    html = (WEB / "index.html").read_text("utf-8")
    for name in ("app.css", "app.js"):
        html = html.replace(f"/static/{name}", f"/static/{name}?v={_asset(name)['etag']}")
    r = Response(html, mimetype="text/html")
    r.headers["Cache-Control"] = "no-cache"
    return r


@app.get("/static/<path:name>")
def static_file(name):
    return _send_asset(name, immutable=bool(request.args.get("v")))


@app.get("/manifest.webmanifest")
def manifest():
    return _send_asset("manifest.webmanifest")


@app.get("/<name>.png")
def icons(name):
    if name not in ("icon-192", "icon-512", "apple-touch-icon", "icon-maskable"):
        abort(404)
    return _send_asset(f"{name}.png")


@app.get("/favicon.ico")
def favicon():
    return _send_asset("icon-192.png")


@app.get("/api/ping")
def ping():
    return jsonify(ok=True, build=APP_BUILD)


# ------------------------------------------------------- headers & gzip
@app.after_request
def harden(r):
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    r.headers.setdefault("X-Frame-Options", "DENY")
    r.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if is_https():
        r.headers.setdefault("Strict-Transport-Security", "max-age=15552000")
    if r.mimetype == "text/html" and "Content-Security-Policy" not in r.headers:
        r.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://i.ytimg.com; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    if request.path.startswith("/api/"):
        r.headers["Cache-Control"] = "no-store"
    # compress JSON replies (phones on slow data)
    if (r.mimetype == "application/json" and not r.direct_passthrough
            and "gzip" in request.headers.get("Accept-Encoding", "")
            and "Content-Encoding" not in r.headers):
        data = r.get_data()
        if len(data) > 1400:
            r.set_data(gzip.compress(data, 5))
            r.headers["Content-Encoding"] = "gzip"
            r.headers["Vary"] = "Accept-Encoding"
    return r


# ------------------------------------------------------------- backups
def backup_loop():
    """Once a day, copy team_data.json into a backups folder (keeps 30 days)."""
    while True:
        try:
            folder = store.dir / "backups"
            folder.mkdir(exist_ok=True)
            target = folder / f"team_data-{date.today().isoformat()}.json"
            if store.path.exists() and not target.exists():
                with LOCK:
                    shutil.copy2(store.path, target)
                old = sorted(folder.glob("team_data-*.json"))
                for f in old[:-30]:
                    f.unlink(missing_ok=True)
        except Exception:
            traceback.print_exc()
        time.sleep(3600)


# ---------------------------------------------------------------- startup
def secret_key() -> bytes:
    p = app_dir() / "web_secret.key"
    try:
        k = p.read_text().strip()
        if len(k) >= 64:
            return bytes.fromhex(k)
    except (OSError, ValueError):
        pass
    k = secrets.token_hex(32)
    p.write_text(k)
    return bytes.fromhex(k)


def lan_addresses() -> list[str]:
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


def setup(data_dir=None, dev_login=False):
    global store, DEV_LOGIN
    data_dir = data_dir or Config().get("data_dir")
    store = Store(data_dir, user="website")
    app.secret_key = secret_key()
    DEV_LOGIN = dev_login
    return app


def main():
    ap = argparse.ArgumentParser(description="PSAL Badminton website")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="0.0.0.0",
                    help="0.0.0.0 = this PC + same Wi-Fi (default); 127.0.0.1 = this PC / tunnel only")
    ap.add_argument("--data", help="folder with team_data.json (default: same as the desktop apps)")
    ap.add_argument("--dev-login", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--selftest", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.selftest:
        setup(tempfile.mkdtemp())
        c = app.test_client()
        ok = c.get("/").status_code == 200 and c.get("/api/state").json.get("signin") is True \
            and _asset("app.js") is not None and _asset("app.css") is not None
        print("SELFTEST OK (website)" if ok else "SELFTEST FAILED (website)")
        sys.exit(0 if ok else 1)
    try:
        sys.stdout.reconfigure(line_buffering=True)  # show the addresses right away
    except (AttributeError, ValueError):
        pass
    setup(a.data, dev_login=a.dev_login and a.host in ("127.0.0.1", "localhost"))
    threading.Thread(target=backup_loop, daemon=True).start()
    WATCH.start()
    print("=" * 64)
    print(f"  PSAL Badminton website is running   (build {APP_BUILD})")
    print(f"  Team data: {store.path}")
    print(f"  On this PC:        http://localhost:{a.port}")
    if a.host == "0.0.0.0":
        for ip in lan_addresses():
            print(f"  On the same Wi-Fi: http://{ip}:{a.port}")
    print("  For phones anywhere: run start_public_link.bat (see WEB_SETUP.md)")
    print("  Keep this window open. Close it to stop the website.")
    print("=" * 64)
    from waitress import serve
    serve(app, host=a.host, port=a.port, threads=12, ident="PSAL", channel_timeout=60,
          clear_untrusted_proxy_headers=False)


if __name__ == "__main__":
    main()
