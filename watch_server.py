"""
Unskippable, verified video watching.

The app runs a tiny web server on this computer (127.0.0.1 only) and opens a
player page in the browser. The page embeds the YouTube video with no seek
bar, no keyboard shortcuts and no speed control, and reports the playback
position every 2 seconds.

The check happens HERE, not in the page: every report is compared with the
real time that passed since the last one. If the video moved further than the
clock allows (skipping ahead) or the speed isn't 1x, the session is flagged.
To get credit the video has to reach its end AND the verified watch time has
to cover 95% of it (and the coach's minimum). Faking reports doesn't help —
it still takes the full length of the video in real time.

Hiding the tab pauses the video (no penalty). Closing it just ends the session.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HEARTBEAT_S = 2
JUMP_SLACK_S = 3.0        # forgiveness for network jitter
SPEED_SLACK = 1.25        # media time may run at most this much faster than the clock
CREDIT_CAP = 1.1          # credited time can't grow faster than this vs the clock
ABANDON_AFTER_S = 90      # no reports for this long -> session over (no penalty)
FINAL = ("done", "skipped", "error", "abandoned")

_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def youtube_id(url: str) -> str | None:
    """Video ID from any normal YouTube link, or None."""
    url = (url or "").strip()
    if _YT_ID.match(url):
        return url
    try:
        u = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return None
    host = (u.hostname or "").lower()
    cand = None
    if host.endswith("youtu.be"):
        cand = u.path.strip("/").split("/")[0]
    elif "youtube.com" in host or "youtube-nocookie.com" in host:
        if u.path == "/watch":
            cand = (parse_qs(u.query).get("v") or [None])[0]
        else:
            parts = [p for p in u.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
                cand = parts[1]
    return cand if cand and _YT_ID.match(cand) else None


class Session:
    def __init__(self, pid, vid, yt, title, min_seconds, player_name):
        self.token = secrets.token_urlsafe(16)
        self.pid, self.vid, self.yt, self.title = pid, vid, yt, title
        self.player_name = player_name
        self.min_seconds = float(min_seconds)
        self.state = "open"            # open -> playing -> done | skipped | error | abandoned
        self.reason = ""
        self.credited = 0.0
        self.duration = 0.0
        self.last_t = None
        self.last_wall = None
        self.was_playing = False
        self.last_seen = time.monotonic()
        self.error_code = None
        self.lock = threading.Lock()

    @property
    def required(self) -> float:
        return max(0.95 * self.duration, self.min_seconds)

    def status(self) -> dict:
        msg = {
            "done": "Verified — you watched the whole video. Your points are in the app.",
            "skipped": "Skipping detected — this video won't give points and integrity points were taken.",
            "error": "This video can't count right now (no penalty). Ask your coach or a manager to fix it.",
            "abandoned": "Session ended. Open the video from the app to start again.",
        }.get(self.state, "")
        return {"state": self.state, "credited": round(self.credited, 1),
                "required": round(self.required, 1), "duration": round(self.duration, 1),
                "reason": self.reason, "message": msg}


class WatchServer:
    """One per app. notify(session) is called (from a server thread) whenever a
    session ends: done, skipped, error or abandoned."""

    def __init__(self, notify, clock=time.monotonic):
        self.notify = notify
        self.clock = clock
        self.sessions: dict[str, Session] = {}
        self.httpd = None
        self.port = None

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if self.httpd:
            return
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # keep the console quiet
                pass

            def _send(self, code, body: bytes, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parts = self.path.split("?")[0].strip("/").split("/")
                if len(parts) == 2 and parts[0] == "watch" and parts[1] in server.sessions:
                    s = server.sessions[parts[1]]
                    return self._send(200, server.page(s).encode("utf-8"), "text/html; charset=utf-8")
                self._send(404, b"Not found - open videos from the PSAL Badminton app.", "text/plain")

            def do_POST(self):
                parts = self.path.strip("/").split("/")
                if len(parts) != 2 or parts[0] != "hb" or parts[1] not in server.sessions:
                    return self._send(404, b"{}", "application/json")
                n = min(int(self.headers.get("Content-Length") or 0), 4096)
                try:
                    data = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    data = {}
                st = server.heartbeat(parts[1], data)
                self._send(200, json.dumps(st).encode(), "application/json")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        threading.Thread(target=self._watchdog, daemon=True).start()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd = None

    def new_session(self, pid, vid, url, title, min_seconds, player_name="") -> tuple[Session, str]:
        yt = youtube_id(url)
        if not yt:
            raise ValueError("Only YouTube links can be tracked. Ask your coach to use a YouTube video.")
        self.start()
        # one live session per player+video
        for s in self.sessions.values():
            if s.pid == pid and s.vid == vid and s.state not in FINAL:
                self._finish(s, "abandoned", "Opened again")
        s = Session(pid, vid, yt, title, min_seconds, player_name)
        s.last_seen = self.clock()
        self.sessions[s.token] = s
        return s, f"http://127.0.0.1:{self.port}/watch/{s.token}"

    # ---------------------------------------------------------- verification
    def heartbeat(self, token: str, data: dict) -> dict:
        s = self.sessions[token]
        with s.lock:
            if s.state in FINAL:
                return s.status()
            now = self.clock()
            s.last_seen = now
            ev = str(data.get("ev", "tick"))
            if ev == "error":
                s.error_code = data.get("code")
                self._finish(s, "error", f"YouTube error {s.error_code}")
                return s.status()
            try:
                t = float(data.get("t") or 0.0)
                d = float(data.get("d") or 0.0)
                rate = float(data.get("rate") or 1.0)
            except (TypeError, ValueError):
                return s.status()
            playing = bool(data.get("playing"))
            visible = data.get("visible", True) is not False

            if d > 0 and s.duration == 0:
                s.duration = d
            if abs(rate - 1.0) > 0.01:
                self._finish(s, "skipped", f"playback speed changed to {rate:g}x")
                return s.status()
            if s.last_t is not None:
                dw = max(0.0, now - s.last_wall)
                dm = t - s.last_t
                if dm > dw * SPEED_SLACK + JUMP_SLACK_S:
                    self._finish(s, "skipped", f"jumped ahead about {int(dm - dw)}s")
                    return s.status()
                if dm > 0 and (s.was_playing or playing) and visible:
                    s.credited += min(dm, dw * CREDIT_CAP)
            s.last_t, s.last_wall, s.was_playing = t, now, playing
            if playing and s.state == "open":
                s.state = "playing"

            at_end = ev == "ended" or (s.duration > 0 and t >= s.duration - 1.5)
            if at_end:
                if s.credited + JUMP_SLACK_S >= s.required:
                    self._finish(s, "done")
                elif s.min_seconds > 0.95 * s.duration and s.credited + JUMP_SLACK_S >= 0.95 * s.duration:
                    # honest viewer, but the coach's minimum is longer than the video itself
                    self._finish(s, "error", "the video is shorter than the coach's minimum watch time "
                                             "— ask them to lower it")
                else:
                    self._finish(s, "skipped", "reached the end without watching all of it")
            return s.status()

    def _finish(self, s: Session, state: str, reason: str = ""):
        s.state, s.reason = state, reason
        try:
            self.notify(s)
        except Exception:
            pass

    def _watchdog(self):
        while self.httpd:
            time.sleep(5)
            now = self.clock()
            for s in list(self.sessions.values()):
                with s.lock:
                    if s.state not in FINAL and now - s.last_seen > ABANDON_AFTER_S:
                        self._finish(s, "abandoned", "player closed")

    # ------------------------------------------------------------------ page
    def page(self, s: Session) -> str:
        return PAGE.replace("__TOKEN__", s.token).replace("__YT__", s.yt).replace(
            "__TITLE__", _html(s.title)).replace("__NAME__", _html(s.player_name or "")).replace(
            "__HB__", str(HEARTBEAT_S * 1000))


def _html(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>__TITLE__ — PSAL Badminton</title>
<style>
:root{--bg:#0d1015;--card:#161a22;--line:#252b36;--text:#e8ebf1;--muted:#8b94a5;--accent:#4f8cff;--good:#22c55e;--bad:#ef4444;--lime:#c4f432}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.45 "Segoe UI",system-ui,-apple-system,"Helvetica Neue",sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 40px}
.kicker{color:var(--lime);font-weight:700;font-size:12px;letter-spacing:.08em}
h1{font-size:24px;margin:4px 0 2px}.sub{color:var(--muted);margin:0 0 16px}
.stage{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:14px;overflow:hidden;border:1px solid var(--line)}
#yt,.stage iframe{position:absolute;inset:0;width:100%;height:100%}
.shield{position:absolute;inset:0;z-index:2;cursor:pointer}
.bar{display:flex;align-items:center;gap:14px;margin-top:14px;flex-wrap:wrap}
button{background:var(--accent);color:#fff;border:0;border-radius:10px;padding:10px 20px;font-weight:700;font-size:15px;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.track{flex:1;min-width:200px;height:10px;background:var(--line);border-radius:5px;overflow:hidden}
.fill{height:100%;width:0;background:var(--good);transition:width .4s}
.meta{color:var(--muted);font-size:13px;min-width:150px;text-align:right}
.note{margin-top:14px;padding:12px 14px;border-radius:12px;background:var(--card);border:1px solid var(--line);color:var(--muted);font-size:13px}
.result{display:none;margin-top:16px;padding:16px 18px;border-radius:12px;font-weight:700;font-size:16px}
.result.done{display:block;background:rgba(34,197,94,.12);border:1px solid var(--good);color:var(--good)}
.result.bad{display:block;background:rgba(239,68,68,.12);border:1px solid var(--bad);color:var(--bad)}
.result.info{display:block;background:var(--card);border:1px solid var(--line);color:var(--text)}
</style></head><body><div class="wrap">
<div class="kicker">PSAL BADMINTON · TRAINING</div>
<h1>__TITLE__</h1><p class="sub">Watching as __NAME__ — keep this tab open and visible until the end.</p>
<div class="stage"><div id="yt"></div><div class="shield" id="shield" title="Use the Play / Pause button"></div></div>
<div class="bar"><button id="play" disabled>Loading…</button>
<div class="track"><div class="fill" id="fill"></div></div><div class="meta" id="meta">0:00 watched</div></div>
<div class="result" id="result"></div>
<div class="note">No skipping: there's no seek bar and the speed is locked at 1×. If the app detects skipping ahead
or a speed change, this video won't give points and integrity points are taken away. Switching tabs just pauses it.</div>
</div>
<script>
const TOKEN="__TOKEN__", VID="__YT__", HB=__HB__;
let player=null, ready=false, finished=false;
const $=id=>document.getElementById(id);
function fmt(s){s=Math.max(0,Math.floor(s||0));return Math.floor(s/60)+":"+String(s%60).padStart(2,"0")}
function show(st){
  if(!st||!st.state)return;
  const need=st.required||st.duration||0;
  $("fill").style.width=(need?Math.min(100,100*st.credited/need):0)+"%";
  $("meta").textContent=fmt(st.credited)+" of "+fmt(need)+" watched";
  if(["done","skipped","error","abandoned"].includes(st.state)&&!finished){
    finished=true;
    try{player&&player.pauseVideo()}catch(e){}
    $("play").disabled=true;$("play").textContent=st.state==="done"?"Done":"Stopped";
    const r=$("result");r.className="result "+(st.state==="done"?"done":st.state==="abandoned"?"info":"bad");
    r.textContent=st.message+(st.reason&&st.state!=="done"?" ("+st.reason+")":"");
  }
}
function send(ev,extra){
  if(finished)return;
  let body={ev:ev,visible:document.visibilityState==="visible"};
  try{ if(player&&ready){body.t=player.getCurrentTime();body.d=player.getDuration();
        body.playing=player.getPlayerState()===1;body.rate=player.getPlaybackRate();} }catch(e){}
  Object.assign(body,extra||{});
  fetch("/hb/"+TOKEN,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
    .then(r=>r.json()).then(show).catch(()=>{});
}
function onYouTubeIframeAPIReady(){
  player=new YT.Player("yt",{videoId:VID,host:"https://www.youtube.com",
    playerVars:{controls:0,disablekb:1,rel:0,fs:0,playsinline:1,iv_load_policy:3,modestbranding:1,origin:location.origin},
    events:{
      onReady:()=>{ready=true;$("play").disabled=false;$("play").textContent="Play";send("ready")},
      onStateChange:e=>{ if(e.data===1){$("play").textContent="Pause"} else if(e.data===2){$("play").textContent="Play"}
                         if(e.data===0){send("ended")} else {send("state")} },
      onPlaybackRateChange:e=>{ if(e.data!==1){send("rate");try{player.setPlaybackRate(1)}catch(x){}} },
      onError:e=>{send("error",{code:e.data})}
    }});
}
$("play").onclick=()=>{ if(!ready||finished)return; const s=player.getPlayerState(); if(s===1){player.pauseVideo()}else{player.playVideo()} };
$("shield").onclick=()=>$("play").click();
document.addEventListener("visibilitychange",()=>{ if(document.visibilityState!=="visible"&&ready&&!finished){try{player.pauseVideo()}catch(e){}} send("visibility"); });
document.addEventListener("keydown",e=>{ if(["ArrowLeft","ArrowRight","j","l","J","L",">","<","."].includes(e.key)){e.preventDefault()} },true);
setInterval(()=>send("tick"),HB);
setTimeout(()=>{ if(!ready){$("play").textContent="Can't load";const r=$("result");r.className="result bad";
  r.textContent="The video player couldn't load. Check your internet connection and open the video from the app again.";}},20000);
</script>
<script src="https://www.youtube.com/iframe_api"></script>
</body></html>"""
