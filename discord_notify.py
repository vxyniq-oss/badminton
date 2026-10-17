"""
Sends improvement notes to the managers' Discord channel through a webhook.

Discord limits: 10 embeds per message, 25 fields per embed, 1024 chars per
field, 6000 chars per message. Notes are grouped one embed per player and
split across as many messages as needed.
"""
from __future__ import annotations

import time
from datetime import datetime

import requests

VALID_PREFIXES = (
    "https://discord.com/api/webhooks/",
    "https://discordapp.com/api/webhooks/",
    "https://canary.discord.com/api/webhooks/",
    "https://ptb.discord.com/api/webhooks/",
)
PRIORITY_COLOR = {"High": 0xEF4444, "Medium": 0xF5B83D, "Low": 0x22C55E}
PRIORITY_MARK = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}


class WebhookError(Exception):
    pass


def valid_webhook(url: str) -> bool:
    return bool(url) and url.strip().startswith(VALID_PREFIXES)


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 1] + "…"


def build_embeds(notes: list[dict], store) -> list[dict]:
    by_player: dict[str, list[dict]] = {}
    for n in notes:
        by_player.setdefault(n["pid"], []).append(n)

    embeds = []
    order = {"High": 0, "Medium": 1, "Low": 2}
    for pid, items in by_player.items():
        items.sort(key=lambda n: order.get(n["priority"], 9))
        pos = store.position_of(pid)
        from data_store import POSITION_LABELS
        pts = store.points(pid)
        rank = store.rank_of(pid)[0]
        fields = []
        for n in items[:25]:
            fields.append({
                "name": _clip(f"{PRIORITY_MARK.get(n['priority'], '•')} {n['area']} — {n['priority']}", 256),
                "value": _clip(f"{n['text'] or '(no details)'}\n*by {n['by']} · {n['ts'][:10]}*", 1024),
                "inline": False,
            })
        embeds.append({
            "title": _clip(f"{store.player_name(pid)} needs to improve", 256),
            "description": f"**{POSITION_LABELS.get(pos, 'Bench')}** · {pts} pts · {rank}",
            "color": PRIORITY_COLOR.get(items[0]["priority"], 0x4F8CFF),
            "fields": fields,
        })
    return embeds


def _embed_size(e: dict) -> int:
    return len(e.get("title", "")) + len(e.get("description", "")) + sum(
        len(f["name"]) + len(f["value"]) for f in e.get("fields", []))


def send_notes(url: str, notes: list[dict], store, sender: str, mention: str = "") -> int:
    """Posts the notes; returns how many Discord messages were sent."""
    if not valid_webhook(url):
        raise WebhookError("Add a valid Discord webhook URL in Settings first.")
    if not notes:
        raise WebhookError("There are no notes to send.")

    team = store.data["team"].get("name", "PSAL Badminton")
    embeds = build_embeds(notes, store)
    batches, cur, size = [], [], 0
    for e in embeds:
        s = _embed_size(e)
        if cur and (len(cur) == 10 or size + s > 5500):
            batches.append(cur)
            cur, size = [], 0
        cur.append(e)
        size += s
    if cur:
        batches.append(cur)

    stamp = datetime.now().strftime("%b %d, %Y %I:%M %p")
    for i, batch in enumerate(batches):
        payload = {
            "username": f"{team} Coach Bot",
            "embeds": batch,
            "allowed_mentions": {"parse": ["roles", "users"]},
        }
        if i == 0:
            header = f"📋 **Improvement notes for managers** — {len(notes)} note(s) from {sender} · {stamp}"
            payload["content"] = f"{mention} {header}".strip() if mention else header
        batch[-1]["footer"] = {"text": f"{team} · page {i + 1}/{len(batches)}"}
        _post(url, payload)
    return len(batches)


def send_test(url: str, team: str) -> None:
    if not valid_webhook(url):
        raise WebhookError("That doesn't look like a Discord webhook URL.")
    _post(url, {"username": f"{team} Coach Bot",
                "content": "✅ Webhook connected — improvement notes will show up here."})


def _post(url: str, payload: dict, attempt: int = 0) -> None:
    try:
        r = requests.post(url.strip(), json=payload, timeout=12)
    except requests.exceptions.RequestException:
        raise WebhookError("Couldn't reach Discord. Check your internet connection.")
    if r.status_code == 429 and attempt < 3:  # rate limited — wait and retry
        try:
            wait = float(r.json().get("retry_after", 1))
        except ValueError:
            wait = 1.0
        time.sleep(min(wait, 10))
        return _post(url, payload, attempt + 1)
    if r.status_code in (401, 403, 404):
        raise WebhookError("Discord rejected the webhook (it may have been deleted). Make a new one.")
    if r.status_code >= 300:
        raise WebhookError(f"Discord error {r.status_code}: {r.text[:200]}")


def send_rankup_request(url: str, store, req: dict, mention: str = "") -> None:
    """Pings the chosen manager (or the managers' channel) about a rank-up match request."""
    from data_store import POSITION_LABELS
    if not valid_webhook(url):
        raise WebhookError("No Discord webhook set — the request was saved, but nobody was pinged.")
    pid = req["pid"]
    team = store.data["team"].get("name", "PSAL Badminton")
    frm, to = store.level_name(req["from_level"])[0], store.level_name(req["to_level"])[0]
    mgr = store.players.get(req.get("manager") or "")
    ping = f"<@{mgr['discord_id']}>" if mgr and str(mgr.get("discord_id", "")).isdigit() else mention
    who = f"asked **{mgr['name']}**" if mgr else "is asking any manager"
    fields = [{"name": "Rank-up", "value": f"{frm} → **{to}**", "inline": True},
              {"name": "Points", "value": str(store.points(pid)), "inline": True},
              {"name": "Spot", "value": POSITION_LABELS.get(store.position_of(pid), "Bench"), "inline": True}]
    if req.get("message"):
        fields.append({"name": "Message", "value": _clip(req["message"], 1024), "inline": False})
    _post(url, {
        "username": f"{team} Coach Bot",
        "content": _clip(f"{ping} 🏸 **{store.player_name(pid)}** qualified for a rank-up match and {who}."
                         .strip(), 2000),
        "embeds": [{"title": f"Rank-up match request — {store.player_name(pid)}", "color": 0xA78BFA,
                    "fields": fields, "footer": {"text": "Open the PSAL Badminton Manager app to schedule it"}}],
        "allowed_mentions": {"parse": ["roles", "users"]},
    })


def send_rankup_result(url: str, store, req: dict) -> None:
    if not valid_webhook(url):
        return
    team = store.data["team"].get("name", "PSAL Badminton")
    name = store.player_name(req["pid"])
    to = store.level_name(req["to_level"])[0]
    if req["status"] == "passed":
        text = f"🎉 **{name}** won their rank-up match and is now **{to}**!"
    else:
        text = f"**{name}** didn't pass the rank-up match to {to} this time — keep training!"
    if req.get("score"):
        text += f" ({req['score']})"
    _post(url, {"username": f"{team} Coach Bot", "content": _clip(text, 2000)})
