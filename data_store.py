"""
Team data + point engine.

Everything lives in one JSON file (team_data.json). Points are never stored as
a plain number: every change is a ledger entry (who, how much, why, when), and
a player's points = starting points + sum of their ledger. That makes the
numbers auditable and lets a deleted match cleanly undo its points.

Writes always re-read the file first, so if the data folder is a shared
OneDrive / Google Drive / Dropbox folder, two coaches won't overwrite each
other's changes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import platform
import shutil
import tempfile
import time
import uuid
import zlib
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

APP_NAME = "PSAL Badminton"

# ---------------------------------------------------------------- constants
POSITIONS = ["S1", "S2", "S3", "D1", "D2"]
POSITION_LABELS = {
    "S1": "1st Singles", "S2": "2nd Singles", "S3": "3rd Singles",
    "D1": "1st Doubles", "D2": "2nd Doubles",
}
POSITION_SIZE = {"S1": 1, "S2": 1, "S3": 1, "D1": 2, "D2": 2}

RANKS = [  # every `rank_step` points (default 500) = one rank up
    ("Bronze", "#CD7F32"),
    ("Silver", "#AEB7C4"),
    ("Gold", "#F5B83D"),
    ("Platinum", "#2DD4BF"),
    ("Diamond", "#60A5FA"),
    ("Champion", "#A78BFA"),
    ("Legend", "#F472B6"),
]

TRAINING_FOCUS = ["Footwork", "Smash", "Clears", "Drop shots", "Net play",
                  "Defense", "Serve / Return", "Stamina", "Match play", "Mental game"]
SKILLS = ["Footwork", "Smash", "Net play", "Defense", "Serve", "Stamina", "Strategy"]
TRAINING_LEVELS = ["Prospect", "Contender", "Varsity Ace", "All-City", "PSAL Elite", "Champion"]

TRAINING_CATEGORIES = ["Footwork", "Shots", "Grip", "Plyometrics"]
QUIZ_CATEGORIES = TRAINING_CATEGORIES + ["Rules & Strategy"]
LEVELS = ["Beginner", "Intermediate", "Expert"]
LEVEL_COLORS = {"Beginner": "#22C55E", "Intermediate": "#F5B83D", "Expert": "#EF4444"}
RANKUP_OPEN = ("pending", "scheduled")


class RankUpError(ValueError):
    """Shown to the user as-is."""


IMPROVE_AREAS = ["Footwork", "Smash", "Clears", "Drop shots", "Net play", "Defense",
                 "Serve / Return", "Stamina", "Doubles rotation", "Consistency",
                 "Strategy", "Attitude / Effort", "Attendance"]
PRIORITIES = ["High", "Medium", "Low"]

DEFAULT_SETTINGS = {
    "start_points": 100,
    "rank_step": 500,
    "points": {
        "win": {"S1": 60, "S2": 50, "S3": 40, "D1": 45, "D2": 40},
        "loss": 10,            # showing up and competing still counts
        "team_win_bonus": 10,  # everyone in the lineup when the team wins
        "practice": 10,
        "absence": 15,         # LOST for an unexcused absence (excused = no change)
        "challenge_win": 30,
        "challenge_loss": 5,
        "scrimmage_win": 15,   # practice scrimmage vs teammates
        "scrimmage_loss": 10,  # LOST for losing a practice scrimmage
    },
    "training": {"start_points": 100, "level_step": 500},
    "extras": {
        # default points by level (each video can be changed when it's added)
        "quiz_points": {"Beginner": 15, "Intermediate": 20, "Expert": 30},
        "video_points": {"Beginner": 5, "Intermediate": 10, "Expert": 15},
        "quiz_pass_pct": 70,   # % correct needed to pass
        "quiz_attempts": 3,    # tries per quiz
        "integrity_penalty": 10,  # LOST when skipping a training video is detected
    },
    "player_code": "",         # team code for keyless player sign-in ("" = turned off)
    # Skill-based points for scrimmages & challenges (like Valorant): a hidden skill
    # rating decides how many points you win/lose. k = how fast ratings move (0 = off).
    "elo": {"start": 1000, "k": 32, "min_pct": 25, "max_pct": 200},
    "discord_webhook": "",
    "discord_mention": "",     # e.g. a role mention like <@&123456789>
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def empty_data() -> dict:
    return {
        "schema": 1,
        "team": {"name": "PSAL Badminton", "school": "",
                 "season": str(date.today().year)},
        "settings": deepcopy(DEFAULT_SETTINGS),
        "players": {},
        "lineup": {p: [] for p in POSITIONS},
        "ledger": [],
        "matches": [],
        "challenges": [],
        "attendance": [],
        "scrimmages": [],
        "training": {"player_id": None, "ledger": [], "sessions": [], "skills": {}},
        "notes": [],
        "rankups": [],
        "rank_history": [],
        "videos": [],
        "video_log": [],
        "activity": [],
    }


def _merge_defaults(data: dict) -> dict:
    base = empty_data()
    for k, v in base.items():
        data.setdefault(k, v)
    s = data["settings"]
    for k, v in DEFAULT_SETTINGS.items():
        if isinstance(v, dict):
            s.setdefault(k, {})
            for k2, v2 in v.items():
                if isinstance(v2, dict):
                    s[k].setdefault(k2, {})
                    for k3, v3 in v2.items():
                        s[k][k2].setdefault(k3, v3)
                else:
                    s[k].setdefault(k2, v2)
        else:
            s.setdefault(k, v)
    for k, v in base["training"].items():
        data["training"].setdefault(k, v)
    for p in POSITIONS:
        data["lineup"].setdefault(p, [])
    return data


# ------------------------------------------------------------- app folders
def app_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif system == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    d = root / "PSALBadminton"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Config:
    """Small per-computer settings (data folder, theme, remembered username)."""

    def __init__(self):
        self.path = app_dir() / "config.json"
        self.values = {"data_dir": str(app_dir()), "appearance": "dark", "remember_user": ""}
        try:
            self.values.update(json.loads(self.path.read_text("utf-8")))
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value
        try:
            self.path.write_text(json.dumps(self.values, indent=2), "utf-8")
        except OSError:
            pass


# ------------------------------------------------------------------- store
class Store:
    FILE = "team_data.json"

    def __init__(self, data_dir: str | Path, user: str = "coach"):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / self.FILE
        self.user = user
        self._mtime = 0.0
        self.version = 0          # bumps on every change; screens redraw only when it moves
        self._cache: dict = {}
        self._cache_ver = -1
        self._crc = None          # checksum of the file contents we last loaded/saved
        self.data = empty_data()
        self.reload()

    # -------------------------------------------------------------- disk io
    def reload(self, force: bool = False) -> None:
        if self.path.exists():
            try:
                raw = self.path.read_bytes()
                crc = zlib.crc32(raw)
                if crc == self._crc and self.version and not force:
                    # same contents (e.g. OneDrive/Google Drive just touched the file):
                    # nothing changed, so don't reload or redraw anything
                    self._mtime = self.path.stat().st_mtime
                    return
                self.data = _merge_defaults(json.loads(raw.decode("utf-8")))
                self._mtime = self.path.stat().st_mtime
                self._crc = crc
                self.version += 1
                self._migrate()
                return
            except (OSError, ValueError):
                # keep a copy of the unreadable file, never silently lose data
                shutil.copy2(self.path, self.path.with_suffix(f".corrupt-{int(time.time())}.json"))
        self.data = empty_data()
        self._write()

    def _migrate(self) -> None:
        """Older files had ranks worked out from points; keep those ranks."""
        missing = [p for p in self.data["players"].values() if "rank_level" not in p]
        if missing:
            pts = self.all_points()
            step = self.settings["rank_step"]
            for p in missing:
                p["rank_level"] = max(0, pts.get(p["id"], 0)) // step

    def changed_on_disk(self) -> bool:
        try:
            return self.path.stat().st_mtime > self._mtime + 1e-6
        except OSError:
            return False

    def _write(self) -> None:
        raw = json.dumps(self.data, separators=(",", ":")).encode("utf-8")  # compact = faster
        fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=".team_data", suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        os.replace(tmp, self.path)
        self._crc = zlib.crc32(raw)
        self._mtime = self.path.stat().st_mtime
        self.version += 1

    def _cached(self, key, build):
        """Results that only change when the data changes (points, stats, …)."""
        if self._cache_ver != self.version:
            self._cache, self._cache_ver = {}, self.version
        if key not in self._cache:
            self._cache[key] = build()
        return self._cache[key]

    def mutate(self, fn, activity: str | None = None):
        """Reload latest from disk, apply fn(data), log + save. Returns
        (fn result, list of rank-up events)."""
        if self.changed_on_disk() or self.version == 0:
            self.reload()  # someone else saved — start from their version
        before = (self.all_points(), {pid: self.rank_level(pid) for pid in self.players},
                  {pid for pid in self.players if self.qualified(pid)})
        before_t = self.training_points()
        try:
            result = fn(self.data)
        except Exception:
            self.reload(force=True)  # throw away a half-done change
            raise
        if activity:
            self.data["activity"].insert(0, {"ts": now_iso(), "by": self.user, "text": activity})
            del self.data["activity"][500:]
        self._write()
        return result, self._rank_events(before, before_t)

    def _rank_events(self, before, before_t: int | None) -> list[str]:
        _, levels, quals = before
        events = []
        for pid in self.players:
            lvl, old = self.rank_level(pid), levels.get(pid)
            name = self.player_name(pid)
            if old is not None and lvl > old:
                events.append(f"{name} ranked up to {self.level_name(lvl)[0]}!")
            elif old is not None and lvl < old:
                events.append(f"{name} moved down to {self.level_name(lvl)[0]}")
            elif self.qualified(pid) and pid not in quals and self.players[pid].get("role") != "manager":
                events.append(f"{name} qualified for a rank-up match to "
                              f"{self.level_name(lvl + 1)[0]}!")
        tp = self.training_points()
        if tp is not None and before_t is not None:
            lstep = self.settings["training"]["level_step"]
            if tp // lstep > before_t // lstep:
                events.append(f"Training level up: {self.training_level(tp)[0]}!")
        return events

    # -------------------------------------------------------------- helpers
    @property
    def settings(self) -> dict:
        return self.data["settings"]

    @property
    def players(self) -> dict:
        return self.data["players"]

    def player_name(self, pid) -> str:
        p = self.players.get(pid)
        return p["name"] if p else "(removed player)"

    def active_players(self, role: str | None = None) -> list[dict]:
        out = [p for p in self.players.values() if p.get("active", True)]
        if role:
            out = [p for p in out if p.get("role", "player") == role]
        return sorted(out, key=lambda p: p["name"].lower())

    def all_points(self) -> dict:
        return self._cached("points", self._all_points)

    def _all_points(self) -> dict:
        start = self.settings["start_points"]
        pts = {pid: start for pid in self.players}
        for e in self.data["ledger"]:  # in order; points never drop below zero
            if e["pid"] in pts:
                pts[e["pid"]] = max(0, pts[e["pid"]] + e["delta"])
        return pts

    def points(self, pid) -> int:
        return self.all_points().get(pid, self.settings["start_points"])

    # ---------------------------------------------------------------- ranks
    # A rank is EARNED: reaching the next 500 points only qualifies a player
    # for a rank-up match. Winning that match (or a manager) moves them up.
    @staticmethod
    def level_name(level: int):
        """-> (name, color) for a rank level"""
        level = max(0, level)
        if level < len(RANKS):
            return RANKS[level]
        return f"Legend {level - len(RANKS) + 2}", RANKS[-1][1]

    def rank_level(self, pid) -> int:
        p = self.players.get(pid) or {}
        return int(p.get("rank_level", 0))

    def threshold(self, level: int) -> int:
        """Points needed to qualify for the match up to level+1."""
        return (level + 1) * self.settings["rank_step"]

    def qualified(self, pid, pts=None) -> bool:
        if pid not in self.players or self.players[pid].get("role") == "manager":
            return False
        pts = self.points(pid) if pts is None else pts
        return pts >= self.threshold(self.rank_level(pid))

    def rank_of(self, pid, pts=None):
        """-> (name, color, progress 0..1 toward qualifying, points still needed)"""
        lvl = self.rank_level(pid)
        name, color = self.level_name(lvl)
        pts = self.points(pid) if pts is None else pts
        step = self.settings["rank_step"]
        frac = (pts - lvl * step) / step
        return name, color, max(0.0, min(1.0, frac)), max(0, self.threshold(lvl) - pts)

    def rank(self, points: int):
        """Rank implied by points alone (used for new-player previews)."""
        step = self.settings["rank_step"]
        lvl = max(points, 0) // step
        name, color = self.level_name(lvl)
        into = max(points, 0) % step
        return name, color, into / step, step - into

    def player_for_username(self, username: str):
        u = (username or "").strip().lower()
        if not u:
            return None
        for p in self.players.values():
            if str(p.get("username", "")).strip().lower() == u:
                return p
        return None

    def position_of(self, pid) -> str | None:
        for pos, ids in self.data["lineup"].items():
            if pid in ids:
                return pos
        return None

    def leaderboard(self) -> list[tuple[dict, int]]:
        pts = self.all_points()
        rows = [(p, pts[p["id"]]) for p in self.active_players() if p.get("role") != "manager"]
        return sorted(rows, key=lambda r: (-r[1], r[0]["name"].lower()))

    def player_stats(self, pid) -> dict:
        return self._cached(("stats", pid), lambda: self._player_stats(pid))

    def _player_stats(self, pid) -> dict:
        w = l = 0
        for m in self.data["matches"]:
            for pos, r in m["results"].items():
                if pid in r.get("players", []) and r.get("played", True):
                    w += r["won"]
                    l += not r["won"]
        cw = sum(1 for c in self.data["challenges"] if c["winner"] == pid)
        cl = sum(1 for c in self.data["challenges"]
                 if pid in (c["challenger"], c["defender"]) and c["winner"] != pid)
        practices = absences = excused = 0
        for a in self.data["attendance"]:
            practices += pid in a["present"]
            absences += pid in a["absent"]
            excused += pid in a["excused"]
        # older versions logged practice straight to the ledger
        practices += sum(1 for e in self.data["ledger"]
                         if e["pid"] == pid and e["kind"] == "practice" and not e.get("ref"))
        sw = sl = 0
        for x in self.data["scrimmages"]:
            if pid in x["a"] + x["b"]:
                won = pid in (x["a"] if x["winner"] == "A" else x["b"])
                sw += won
                sl += not won
        quizzes = sum(1 for x in self.data["video_log"] if x["pid"] == pid and x["kind"] == "quiz"
                      and x.get("passed"))
        videos = sum(1 for x in self.data["video_log"] if x["pid"] == pid and x["kind"] == "watched")
        skips = sum(1 for x in self.data["video_log"] if x["pid"] == pid and x["kind"] == "skip")
        return {"wins": w, "losses": l, "ch_wins": cw, "ch_losses": cl, "practices": practices,
                "quizzes": quizzes, "videos": videos, "skips": skips,
                "absences": absences, "excused": excused, "scr_wins": sw, "scr_losses": sl}

    def team_record(self) -> tuple[int, int]:
        w = sum(1 for m in self.data["matches"] if m["team_won"])
        return w, len(self.data["matches"]) - w

    def _ledger(self, data, pid, delta, reason, kind, ref=None):
        # raw delta is stored; all_points() applies the zero floor in order,
        # so undoing an older entry can never leave someone negative
        data["ledger"].append({"id": new_id(), "ts": now_iso(), "pid": pid, "delta": int(delta),
                               "reason": reason, "kind": kind, "ref": ref, "by": self.user})

    # -------------------------------------------------------------- players
    def add_player(self, name, grade="", student_id="", role="player", notes="",
                   username="", discord_id=""):
        pid = new_id()

        def fn(d):
            d["players"][pid] = {"id": pid, "name": name.strip(), "grade": grade,
                                 "student_id": student_id, "role": role, "notes": notes,
                                 "username": username.strip(), "discord_id": discord_id.strip(),
                                 "rank_level": 0, "active": True, "created": now_iso()}
            return pid
        return self.mutate(fn, f"Added {role} {name.strip()}")

    def update_player(self, pid, **fields):
        def fn(d):
            d["players"][pid].update(fields)
            if fields.get("role") == "manager" or fields.get("active") is False:
                for pos in POSITIONS:
                    d["lineup"][pos] = [x for x in d["lineup"][pos] if x != pid]
        return self.mutate(fn, f"Updated {fields.get('name') or self.player_name(pid)}")

    def remove_player(self, pid):
        name = self.player_name(pid)

        def fn(d):
            d["players"].pop(pid, None)
            for pos in POSITIONS:
                d["lineup"][pos] = [x for x in d["lineup"][pos] if x != pid]
            d["ledger"] = [e for e in d["ledger"] if e["pid"] != pid]
            d["rankups"] = [r for r in d["rankups"] if r["pid"] != pid]
            if d["training"]["player_id"] == pid:
                d["training"]["player_id"] = None
        return self.mutate(fn, f"Removed {name}")

    def adjust_points(self, pids, delta, reason, kind="manual"):
        pids = list(pids)

        def fn(d):
            for pid in pids:
                self._ledger(d, pid, delta, reason, kind)
        names = ", ".join(self.player_name(p) for p in pids[:4]) + ("…" if len(pids) > 4 else "")
        sign = "+" if delta >= 0 else ""
        return self.mutate(fn, f"{sign}{delta} pts — {reason} ({names})")

    def record_practice(self, pids, day: str):
        return self.record_attendance(day, list(pids), [], {})

    # ------------------------------------------------------------ attendance
    def attendance_for(self, day: str) -> dict | None:
        return next((a for a in self.data["attendance"] if a["date"] == day), None)

    def record_attendance(self, day: str, present, absent, excused: dict):
        """present: [pid], absent (unexcused): [pid], excused: {pid: reason}.
        Saving the same date again replaces that day (old points are undone)."""
        P = self.settings["points"]
        aid = new_id()

        def fn(d):
            old = [a for a in d["attendance"] if a["date"] == day]
            if old:
                refs = {a["id"] for a in old}
                d["ledger"] = [e for e in d["ledger"] if e.get("ref") not in refs]
                d["attendance"] = [a for a in d["attendance"] if a["date"] != day]
            for pid in present:
                self._ledger(d, pid, P["practice"], f"Practice attendance {day}", "practice", aid)
            for pid in absent:
                self._ledger(d, pid, -abs(P["absence"]), f"Unexcused absence {day}", "absence", aid)
            for pid, reason in excused.items():
                self._ledger(d, pid, 0, f"Excused absence {day}: {reason}", "excused", aid)
            d["attendance"].insert(0, {"id": aid, "date": day, "present": list(present),
                                       "absent": list(absent), "excused": dict(excused),
                                       "by": self.user, "ts": now_iso()})
            d["attendance"].sort(key=lambda a: a["date"], reverse=True)
            return bool(old)
        return self.mutate(fn, f"Attendance {day}: {len(present)} present, {len(absent)} unexcused, "
                               f"{len(excused)} excused")

    def delete_attendance(self, aid):
        a = next((x for x in self.data["attendance"] if x["id"] == aid), None)

        def fn(d):
            d["attendance"] = [x for x in d["attendance"] if x["id"] != aid]
            d["ledger"] = [e for e in d["ledger"] if e.get("ref") != aid]
        return self.mutate(fn, f"Deleted attendance for {a['date'] if a else '?'} (points reversed)")

    # ------------------------------------------------------------ scrimmages
    # ------------------------------------------- skill rating (like Valorant)
    # Every player has a hidden skill rating (SR), like Valorant's MMR. It starts at
    # 1000 and moves after each scrimmage/challenge using the Elo formula: beating a
    # stronger player moves it a lot, beating a weaker one barely moves it. SR is
    # rebuilt from the game history, so undoing a game also undoes its effect.
    def _elo(self) -> dict:
        return self.settings["elo"]

    def skill_ratings(self) -> dict:
        return self._cached("sr", self._skill_ratings)

    def _skill_ratings(self) -> dict:
        E = self._elo()
        start, k = float(E["start"]), float(E["k"])
        sr = {pid: float(p.get("sr_base", start)) for pid, p in self.players.items()}
        games = []
        for x in reversed(self.data["scrimmages"]):          # oldest first
            w, l = (x["a"], x["b"]) if x["winner"] == "A" else (x["b"], x["a"])
            games.append((x.get("ts", ""), w, l))
        for c in reversed(self.data["challenges"]):
            loser = c["defender"] if c["winner"] == c["challenger"] else c["challenger"]
            games.append((c.get("ts", ""), [c["winner"]], [loser]))
        games.sort(key=lambda g: g[0])
        for _ts, w, l in games:
            rw = sum(sr.get(p, start) for p in w) / len(w)
            rl = sum(sr.get(p, start) for p in l) / len(l)
            delta = k * (1 - 1 / (1 + 10 ** ((rl - rw) / 400)))
            for p in w:
                if p in sr:
                    sr[p] += delta
            for p in l:
                if p in sr:
                    sr[p] -= delta
        return {pid: round(v) for pid, v in sr.items()}

    def skill(self, pid) -> int:
        return self.skill_ratings().get(pid, int(self._elo()["start"]))

    def win_chance(self, side_a, side_b) -> float:
        """Chance (0..1) that side A beats side B, from their skill ratings."""
        ra = sum(self.skill(p) for p in side_a) / max(1, len(side_a))
        rb = sum(self.skill(p) for p in side_b) / max(1, len(side_b))
        return 1 / (1 + 10 ** ((rb - ra) / 400))

    def elo_multiplier(self, winner_chance: float) -> float:
        """How much a result is worth: 1.0 for an even game, up to max_pct for a big
        upset, down to min_pct for an expected win. Off (always 1.0) when k = 0."""
        E = self._elo()
        if not E.get("k"):
            return 1.0
        m = 2 * (1 - winner_chance)
        return max(E["min_pct"] / 100, min(E["max_pct"] / 100, m))

    def scrimmage_points(self, side_a, side_b) -> dict:
        """Preview: points for each result before the game is played."""
        P = self.settings["points"]
        pa = self.win_chance(side_a, side_b)
        out = {"chance_a": pa}
        for side, chance in (("A", pa), ("B", 1 - pa)):
            m = self.elo_multiplier(chance)
            out[side] = {"gain": max(1, int(P["scrimmage_win"] * m + 0.5)),
                         "loss": max(1, int(abs(P["scrimmage_loss"]) * m + 0.5)), "mult": m}
        return out

    def challenge_points(self, challenger, defender) -> dict:
        P = self.settings["points"]
        pc = self.win_chance([challenger], [defender])
        return {"chance_c": pc,
                "challenger": max(1, int(P["challenge_win"] * self.elo_multiplier(pc) + 0.5)),
                "defender": max(1, int(P["challenge_win"] * self.elo_multiplier(1 - pc) + 0.5)),
                "loser": P["challenge_loss"]}

    @staticmethod
    def _upset_note(m: float, won: bool) -> str:
        if m >= 1.15:
            return " — upset win!" if won else " — lost as the favorite"
        if m <= 0.85:
            return " — expected win" if won else " — tough opponent"
        return ""

    def record_scrimmage(self, side_a, side_b, winner: str, score=""):
        """side_a / side_b: lists of 1 (singles) or 2 (doubles) pids; winner 'A' or 'B'.
        Points depend on the skill gap (see scrimmage_points)."""
        sid = new_id()
        win, lose = (side_a, side_b) if winner == "A" else (side_b, side_a)
        wn = " & ".join(self.player_name(p) for p in win)
        ln = " & ".join(self.player_name(p) for p in lose)
        pv = self.scrimmage_points(side_a, side_b)[winner]
        gain, loss, m = pv["gain"], pv["loss"], pv["mult"]
        chance = self.win_chance(win, lose)

        def fn(d):
            for pid in win:
                self._ledger(d, pid, gain, f"Scrimmage win vs {ln}{self._upset_note(m, True)}", "scrimmage", sid)
            for pid in lose:
                self._ledger(d, pid, -loss, f"Scrimmage loss vs {wn}{self._upset_note(m, False)}", "scrimmage", sid)
            d["scrimmages"].insert(0, {"id": sid, "ts": now_iso(), "date": date.today().isoformat(),
                                       "a": list(side_a), "b": list(side_b), "winner": winner,
                                       "score": score, "by": self.user, "gain": gain, "loss": loss,
                                       "chance": round(chance, 3)})
            return {"gain": gain, "loss": loss, "chance": chance}
        return self.mutate(fn, f"Scrimmage: {wn} beat {ln} (+{gain} / −{loss})")

    def delete_scrimmage(self, sid):
        def fn(d):
            d["scrimmages"] = [x for x in d["scrimmages"] if x["id"] != sid]
            d["ledger"] = [e for e in d["ledger"] if e.get("ref") != sid]
        return self.mutate(fn, "Deleted a scrimmage (points reversed)")

    # --------------------------------------------------------------- lineup
    def set_lineup(self, lineup: dict):
        def fn(d):
            d["lineup"] = {p: [x for x in lineup.get(p, []) if x][:POSITION_SIZE[p]] for p in POSITIONS}
        return self.mutate(fn, "Updated the lineup")

    def record_challenge(self, challenger, defender, winner, score=""):
        P = self.settings["points"]
        loser = defender if winner == challenger else challenger
        cid = new_id()
        swapped = {}
        wchance = self.win_chance([winner], [loser])
        wm = self.elo_multiplier(wchance)
        win_pts = max(1, int(P["challenge_win"] * wm + 0.5))

        def fn(d):
            pos_c, pos_d = self.position_of(challenger), self.position_of(defender)
            order = {p: i for i, p in enumerate(POSITIONS)}
            # challenger takes the defender's spot if they win and the spot is higher
            if winner == challenger and pos_d and (pos_c is None or order[pos_d] < order[pos_c]):
                d["lineup"][pos_d] = [challenger if x == defender else x for x in d["lineup"][pos_d]]
                if pos_c:
                    d["lineup"][pos_c] = [defender if x == challenger else x for x in d["lineup"][pos_c]]
                swapped.update({"to": pos_d, "from": pos_c})
            self._ledger(d, winner, win_pts, f"Challenge win vs {self.player_name(loser)}"
                         f"{self._upset_note(wm, True)}", "challenge", cid)
            self._ledger(d, loser, P["challenge_loss"], f"Challenge match vs {self.player_name(winner)}",
                         "challenge", cid)
            d["challenges"].insert(0, {"id": cid, "ts": now_iso(), "challenger": challenger,
                                       "defender": defender, "winner": winner, "score": score,
                                       "swap": dict(swapped), "by": self.user, "gain": win_pts,
                                       "chance": round(wchance, 3)})
            return dict(swapped)
        return self.mutate(fn, f"Challenge: {self.player_name(winner)} beat {self.player_name(loser)}")

    # -------------------------------------------------------------- matches
    def record_match(self, day, opponent, home, results: dict):
        """results: {pos: {"players": [...], "won": bool, "score": str, "played": bool}}"""
        P = self.settings["points"]
        mid = new_id()
        played = {k: v for k, v in results.items() if v.get("played", True)}
        wins = sum(1 for r in played.values() if r["won"])
        team_won = wins > len(played) / 2

        def fn(d):
            for pos, r in played.items():
                for pid in r["players"]:
                    if r["won"]:
                        self._ledger(d, pid, P["win"][pos], f"{POSITION_LABELS[pos]} win vs {opponent}",
                                     "match", mid)
                    else:
                        self._ledger(d, pid, P["loss"], f"{POSITION_LABELS[pos]} vs {opponent}",
                                     "match", mid)
                    if team_won and P["team_win_bonus"]:
                        self._ledger(d, pid, P["team_win_bonus"], f"Team win vs {opponent}", "match", mid)
            d["matches"].insert(0, {"id": mid, "date": day, "opponent": opponent, "home": home,
                                    "results": results, "team_won": team_won,
                                    "score": f"{wins}-{len(played) - wins}", "by": self.user,
                                    "ts": now_iso()})
            return team_won
        result = "W" if team_won else "L"
        return self.mutate(fn, f"Match vs {opponent}: {result} {wins}-{len(played) - wins}")

    def delete_match(self, mid):
        m = next((x for x in self.data["matches"] if x["id"] == mid), None)

        def fn(d):
            d["matches"] = [x for x in d["matches"] if x["id"] != mid]
            d["ledger"] = [e for e in d["ledger"] if e.get("ref") != mid]
        return self.mutate(fn, f"Deleted match vs {m['opponent'] if m else '?'} (points reversed)")

    # ------------------------------------------------- manager training (1S)
    def training_player(self) -> str | None:
        tp = self.data["training"].get("player_id")
        if tp and tp in self.players:
            return tp
        s1 = self.data["lineup"].get("S1") or []
        return s1[0] if s1 else None

    def training_points(self) -> int | None:
        pid = self.training_player()
        if not pid:
            return None
        start = self.settings["training"]["start_points"]
        return start + sum(e["delta"] for e in self.data["training"]["ledger"] if e["pid"] == pid)

    def training_level(self, points: int):
        step = self.settings["training"]["level_step"]
        idx = max(points, 0) // step
        name = TRAINING_LEVELS[min(idx, len(TRAINING_LEVELS) - 1)]
        into = max(points, 0) % step
        return name, into / step, step - into

    def set_training_player(self, pid):
        return self.mutate(lambda d: d["training"].__setitem__("player_id", pid),
                           f"Manager training focus set to {self.player_name(pid)}")

    def log_training(self, pid, manager, focus, minutes, effort, points, notes="", skills=None):
        sid = new_id()

        def fn(d):
            d["training"]["sessions"].insert(0, {
                "id": sid, "ts": now_iso(), "date": date.today().isoformat(), "pid": pid,
                "manager": manager, "focus": focus, "minutes": minutes, "effort": effort,
                "points": points, "notes": notes, "by": self.user})
            d["training"]["ledger"].append({"id": new_id(), "ts": now_iso(), "pid": pid,
                                            "delta": int(points), "reason": f"{focus} session",
                                            "ref": sid, "by": self.user})
            if skills:
                d["training"]["skills"].setdefault(pid, {}).update(skills)
        return self.mutate(fn, f"Training: {focus} with {manager} (+{points} training pts)")

    def delete_training(self, sid):
        def fn(d):
            d["training"]["sessions"] = [s for s in d["training"]["sessions"] if s["id"] != sid]
            d["training"]["ledger"] = [e for e in d["training"]["ledger"] if e.get("ref") != sid]
        return self.mutate(fn, "Deleted a training session")

    # ------------------------------------------------------ improvement notes
    def add_note(self, pid, area, priority, text):
        nid = new_id()

        def fn(d):
            d["notes"].insert(0, {"id": nid, "ts": now_iso(), "pid": pid, "area": area,
                                  "priority": priority, "text": text.strip(), "by": self.user,
                                  "resolved": False, "sent": False})
            return nid
        return self.mutate(fn, f"Note for {self.player_name(pid)}: work on {area}")

    def update_note(self, nid, **fields):
        def fn(d):
            for n in d["notes"]:
                if n["id"] == nid:
                    n.update(fields)
        return self.mutate(fn)

    def delete_note(self, nid):
        return self.mutate(lambda d: d.__setitem__("notes", [n for n in d["notes"] if n["id"] != nid]),
                           "Deleted an improvement note")

    def open_notes(self) -> list[dict]:
        order = {p: i for i, p in enumerate(PRIORITIES)}
        notes = [n for n in self.data["notes"] if not n.get("resolved")]
        return sorted(notes, key=lambda n: (order.get(n["priority"], 9), n["ts"]))

    # ---------------------------------------------------------- rank-up matches
    def managers(self) -> list[dict]:
        return self.active_players("manager")

    def open_rankup(self, pid):
        return next((r for r in self.data["rankups"] if r["pid"] == pid and r["status"] in RANKUP_OPEN),
                    None)

    def rankup(self, rid):
        return next((r for r in self.data["rankups"] if r["id"] == rid), None)

    def request_rankup(self, pid, manager_pid=None, message="", requested_by=None):
        if not self.qualified(pid):
            need = self.rank_of(pid)[3]
            raise RankUpError(f"{self.player_name(pid)} needs {need} more points to qualify.")
        if self.open_rankup(pid):
            raise RankUpError(f"{self.player_name(pid)} already has a rank-up match request open.")
        lvl = self.rank_level(pid)
        rid = new_id()

        def fn(d):
            d["rankups"].insert(0, {
                "id": rid, "pid": pid, "from_level": lvl, "to_level": lvl + 1, "status": "pending",
                "manager": manager_pid, "message": message.strip(), "points": self.points(pid),
                "requested_by": requested_by or self.user, "ts": now_iso(),
                "scheduled_for": "", "details": "", "score": "", "result_note": "",
                "decided_by": "", "decided_ts": ""})
            return rid
        to = self.level_name(lvl + 1)[0]
        who = f" with {self.player_name(manager_pid)}" if manager_pid else ""
        return self.mutate(fn, f"{self.player_name(pid)} requested a rank-up match to {to}{who}")

    def schedule_rankup(self, rid, when: str, details: str = ""):
        r = self.rankup(rid)

        def fn(d):
            for x in d["rankups"]:
                if x["id"] == rid:
                    x.update(status="scheduled", scheduled_for=when.strip(), details=details.strip())
        return self.mutate(fn, f"Scheduled {self.player_name(r['pid'])}'s rank-up match for {when}")

    def decide_rankup(self, rid, passed: bool, score="", note=""):
        r = self.rankup(rid)
        if not r or r["status"] not in RANKUP_OPEN:
            raise RankUpError("That request is already closed.")

        def fn(d):
            x = next(x for x in d["rankups"] if x["id"] == rid)
            x.update(status="passed" if passed else "failed", score=score.strip(),
                     result_note=note.strip(), decided_by=self.user, decided_ts=now_iso())
            p = d["players"].get(x["pid"])
            if passed and p:
                old = int(p.get("rank_level", 0))
                p["rank_level"] = max(old, x["to_level"])
                d["rank_history"].insert(0, {"ts": now_iso(), "pid": x["pid"], "from": old,
                                             "to": p["rank_level"], "kind": "match", "by": self.user,
                                             "reason": f"Won rank-up match {score}".strip()})
            return passed
        res = "won" if passed else "did not pass"
        return self.mutate(fn, f"{self.player_name(r['pid'])} {res} the rank-up match to "
                               f"{self.level_name(r['to_level'])[0]}")

    def cancel_rankup(self, rid, reason=""):
        r = self.rankup(rid)

        def fn(d):
            for x in d["rankups"]:
                if x["id"] == rid and x["status"] in RANKUP_OPEN:
                    x.update(status="cancelled", result_note=reason.strip(), decided_by=self.user,
                             decided_ts=now_iso())
        return self.mutate(fn, f"Cancelled {self.player_name(r['pid'])}'s rank-up request")

    def set_rank(self, pid, level: int, reason: str):
        """Manager rank up / down without a match."""
        level = max(0, int(level))
        old = self.rank_level(pid)

        def fn(d):
            d["players"][pid]["rank_level"] = level
            d["rank_history"].insert(0, {"ts": now_iso(), "pid": pid, "from": old, "to": level,
                                         "kind": "manual", "by": self.user, "reason": reason.strip()})
            for x in d["rankups"]:  # a request for a rank they now have is no longer needed
                if x["pid"] == pid and x["status"] in RANKUP_OPEN and x["to_level"] <= level:
                    x.update(status="cancelled", result_note="Rank set by a manager",
                             decided_by=self.user, decided_ts=now_iso())
        verb = "Ranked up" if level > old else "Moved down"
        return self.mutate(fn, f"{verb} {self.player_name(pid)}: {self.level_name(old)[0]} → "
                               f"{self.level_name(level)[0]} ({reason.strip() or 'no reason'})")

    # ------------------------------------------------ training videos & quizzes
    def videos(self, kind: str) -> list[dict]:
        return [v for v in self.data["videos"] if v["kind"] == kind]

    def video(self, vid):
        return next((v for v in self.data["videos"] if v["id"] == vid), None)

    def default_video_points(self, kind: str, level: str) -> int:
        table = self.settings["extras"]["quiz_points" if kind == "quiz" else "video_points"]
        return int(table.get(level, 10)) if isinstance(table, dict) else int(table)

    def save_video(self, vid, kind, title, url, category, minutes, points, questions=None,
                   description="", level="Beginner"):
        """Create (vid=None) or update a training video. kind: 'quiz' or 'optional'."""
        new = vid is None
        vid = vid or new_id()
        rec = {"id": vid, "kind": kind, "title": title.strip(), "url": url.strip(),
               "category": category, "level": level if level in LEVELS else "Beginner",
               "minutes": int(minutes), "points": int(points),
               "description": description.strip(), "questions": questions or []}

        def fn(d):
            for i, v in enumerate(d["videos"]):
                if v["id"] == vid:
                    rec["created_by"] = v.get("created_by", self.user)
                    d["videos"][i] = rec
                    return vid
            rec["created_by"] = self.user
            d["videos"].append(rec)
            return vid
        what = "quiz video" if kind == "quiz" else "training video"
        return self.mutate(fn, f"{'Added' if new else 'Edited'} {what}: {title.strip()}")

    def delete_video(self, vid):
        v = self.video(vid)
        return self.mutate(lambda d: d.__setitem__("videos", [x for x in d["videos"] if x["id"] != vid]),
                           f"Deleted video: {v['title'] if v else '?'} (points already earned are kept)")

    def _video_index(self) -> dict:
        idx: dict = {}
        for x in self.data["video_log"]:
            idx.setdefault((x["pid"], x["vid"]), []).append(x)
        return idx

    def video_status(self, pid, vid) -> dict:
        logs = self._cached("video_index", self._video_index).get((pid, vid), [])
        quiz = [x for x in logs if x["kind"] == "quiz"]
        passed = next((x for x in quiz if x.get("passed")), None)
        best = max(quiz, key=lambda x: x["score"] / max(1, x["total"]), default=None)
        skip = next((x for x in logs if x["kind"] == "skip" and not x.get("cleared")), None)
        return {"watched": any(x["kind"] == "watched" for x in logs),
                "viewed": any(x["kind"] in ("viewed", "watched") for x in logs),
                "skipped": bool(skip), "skip_log": skip, "passed": bool(passed),
                "attempts": len(quiz), "best": best, "pass_log": passed,
                "attempts_left": max(0, self.settings["extras"]["quiz_attempts"] - len(quiz))}

    def required_watch_seconds(self, vid, reported_duration: float) -> float:
        """Must watch 95% of the video, and never less than the coach's minimum."""
        v = self.video(vid) or {}
        return max(0.95 * max(0.0, reported_duration), 60.0 * int(v.get("minutes", 0)))

    def complete_video(self, pid, vid, watched_seconds: float = 0):
        """Called only after the in-app player verified the whole video was watched.
        Optional videos give points; quiz videos unlock the quiz."""
        v = self.video(vid)
        if not v:
            raise RankUpError("That video was removed.")
        st = self.video_status(pid, vid)
        if st["skipped"]:
            raise RankUpError("Skipping was detected on this video, so it can't earn points.")
        kind = "watched" if v["kind"] == "optional" else "viewed"
        if (kind == "watched" and st["watched"]) or (kind == "viewed" and st["viewed"]):
            return 0, []
        lid = new_id()
        pts = v["points"] if kind == "watched" else 0

        def fn(d):
            d["video_log"].append({"id": lid, "vid": vid, "pid": pid, "kind": kind, "points": pts,
                                   "seconds": int(watched_seconds), "ts": now_iso(), "by": self.user})
            if pts:
                self._ledger(d, pid, pts, f"Training video: {v['title']}", "video", lid)
            return pts
        msg = (f"{self.player_name(pid)} watched “{v['title']}” (+{pts})" if pts
               else f"{self.player_name(pid)} watched “{v['title']}” — quiz unlocked")
        return self.mutate(fn, msg)

    def flag_skip(self, pid, vid, reason: str):
        """Skipping detected: no points from this video and an integrity penalty."""
        v = self.video(vid) or {"title": "?"}
        if self.video_status(pid, vid)["skipped"]:
            return 0, []
        pen = abs(int(self.settings["extras"].get("integrity_penalty", 10)))
        lid = new_id()

        def fn(d):
            d["video_log"].append({"id": lid, "vid": vid, "pid": pid, "kind": "skip", "reason": reason,
                                   "points": -pen, "ts": now_iso(), "by": self.user})
            self._ledger(d, pid, -pen, f"Integrity: skipped “{v['title']}” ({reason})", "integrity", lid)
            return pen
        return self.mutate(fn, f"Skipping detected: {self.player_name(pid)} on “{v['title']}” "
                               f"(−{pen}, {reason})")

    def clear_skip(self, pid, vid):
        """Coach/manager lets a player try the video again (the penalty stays)."""
        def fn(d):
            for x in d["video_log"]:
                if x["pid"] == pid and x["vid"] == vid and x["kind"] == "skip":
                    x["cleared"] = True
        return self.mutate(fn, f"Allowed {self.player_name(pid)} to re-watch a flagged video")

    def submit_quiz(self, pid, vid, answers: list):
        """answers: chosen option index per question (None = skipped)."""
        v = self.video(vid)
        if not v or not v.get("questions"):
            raise RankUpError("This quiz has no questions yet.")
        st = self.video_status(pid, vid)
        if st["skipped"]:
            raise RankUpError("Skipping was detected on this video, so its quiz can't earn points.")
        if not st["viewed"]:
            raise RankUpError("Watch the whole video in the app first — then the quiz unlocks.")
        if st["passed"]:
            raise RankUpError(f"{self.player_name(pid)} already passed this quiz.")
        if st["attempts_left"] <= 0:
            raise RankUpError("No tries left on this quiz — ask a coach or manager to reset it.")
        qs = v["questions"]
        wrong = [i for i, q in enumerate(qs) if i >= len(answers) or answers[i] != q["answer"]]
        score, total = len(qs) - len(wrong), len(qs)
        passed = score * 100 >= self.settings["extras"]["quiz_pass_pct"] * total
        lid = new_id()

        def fn(d):
            d["video_log"].append({"id": lid, "vid": vid, "pid": pid, "kind": "quiz", "score": score,
                                   "total": total, "passed": passed,
                                   "points": v["points"] if passed else 0, "ts": now_iso(),
                                   "by": self.user})
            if passed:
                self._ledger(d, pid, v["points"], f"Passed quiz: {v['title']} ({score}/{total})",
                             "quiz", lid)
            return {"score": score, "total": total, "passed": passed, "wrong": wrong,
                    "points": v["points"] if passed else 0,
                    "attempts_left": st["attempts_left"] - 1}
        res = f"passed ({score}/{total}, +{v['points']})" if passed else f"scored {score}/{total}"
        return self.mutate(fn, f"{self.player_name(pid)} {res} on quiz “{v['title']}”")

    def reset_quiz(self, pid, vid):
        """Give a player their tries back (keeps a pass and its points)."""
        def fn(d):
            d["video_log"] = [x for x in d["video_log"] if not (
                x["pid"] == pid and x["vid"] == vid and x["kind"] == "quiz" and not x.get("passed"))]
        return self.mutate(fn, f"Reset quiz tries for {self.player_name(pid)}")

    # ------------------------------------------- keyless player sign-in (PINs)
    PIN_ITERATIONS = 120_000

    @staticmethod
    def _pin_hash(pin: str, salt: str) -> str:
        return hashlib.pbkdf2_hmac("sha256", pin.encode(), bytes.fromhex(salt), Store.PIN_ITERATIONS).hex()

    def player_code_ok(self, code: str) -> bool:
        real = str(self.settings.get("player_code", "")).strip()
        return bool(real) and hmac.compare_digest(real.lower(), (code or "").strip().lower())

    def has_pin(self, pid) -> bool:
        return bool((self.players.get(pid) or {}).get("pin_hash"))

    def check_pin(self, pid, pin: str) -> bool:
        p = self.players.get(pid) or {}
        if not p.get("pin_hash"):
            return False
        return hmac.compare_digest(p["pin_hash"], self._pin_hash(pin, p["pin_salt"]))

    @staticmethod
    def valid_pin(pin: str) -> bool:
        return pin.isdigit() and 4 <= len(pin) <= 8

    def set_pin(self, pid, pin: str):
        if not self.valid_pin(pin):
            raise RankUpError("PIN must be 4 to 8 digits.")
        salt = secrets.token_hex(16)
        h = self._pin_hash(pin, salt)

        def fn(d):
            d["players"][pid].update(pin_hash=h, pin_salt=salt)
        return self.mutate(fn, f"{self.player_name(pid)} set their sign-in PIN")

    def reset_pin(self, pid):
        def fn(d):
            d["players"][pid].pop("pin_hash", None)
            d["players"][pid].pop("pin_salt", None)
        return self.mutate(fn, f"Reset {self.player_name(pid)}'s PIN — they'll make a new one next sign-in")

    # ---------------------------------------------------------- import/export
    def export_json(self, path):
        Path(path).write_text(json.dumps(self.data, indent=2), "utf-8")

    def import_json(self, path):
        incoming = _merge_defaults(json.loads(Path(path).read_text("utf-8")))
        backup = self.dir / f"team_data.backup-{datetime.now():%Y%m%d-%H%M%S}.json"
        if self.path.exists():
            shutil.copy2(self.path, backup)
        return self.mutate(lambda d: (d.clear(), d.update(incoming)), "Imported a backup")

    def export_csv(self, path):
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Rank #", "Name", "Grade", "Student ID", "Position", "Points", "Rank",
                        "Match W", "Match L", "Scrimmage W", "Scrimmage L", "Challenge W",
                        "Challenge L", "Practices", "Unexcused absences", "Excused absences"])
            for i, (p, pts) in enumerate(self.leaderboard(), 1):
                s = self.player_stats(p["id"])
                pos = self.position_of(p["id"])
                w.writerow([i, p["name"], p.get("grade", ""), p.get("student_id", ""),
                            POSITION_LABELS.get(pos, "Bench"), pts, self.rank_of(p["id"])[0],
                            s["wins"], s["losses"], s["scr_wins"], s["scr_losses"], s["ch_wins"],
                            s["ch_losses"], s["practices"], s["absences"], s["excused"]])

    def new_season(self, season_name):
        """Archive everything to a backup file, then reset points/matches but keep the roster."""
        archive = self.dir / f"season-{self.data['team'].get('season', 'old')}-{int(time.time())}.json"
        self.export_json(archive)
        start = self._elo()["start"]
        carry = {pid: round(start + (r - start) * 0.5) for pid, r in self.skill_ratings().items()}

        def fn(d):
            for pid, p in d["players"].items():   # soft reset, like a new Valorant act
                p["sr_base"] = carry.get(pid, start)
            d["ledger"], d["matches"], d["challenges"] = [], [], []
            d["attendance"], d["scrimmages"] = [], []
            d["rankups"], d["rank_history"], d["video_log"] = [], [], []
            for p in d["players"].values():
                p["rank_level"] = 0
            d["training"]["ledger"], d["training"]["sessions"] = [], []
            d["notes"] = [n for n in d["notes"] if not n.get("resolved")]
            d["team"]["season"] = season_name
            return str(archive)
        return self.mutate(fn, f"Started new season {season_name}")
