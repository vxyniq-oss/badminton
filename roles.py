"""Who can do what — shared by the desktop apps and the website."""


def role_from_subscriptions(subs: list[dict]) -> str:
    """KeyAuth subscription level name -> app role.
    Make subscription levels named 'coach', 'manager', 'player' in KeyAuth.
    Any other name (e.g. KeyAuth's 'default') gets full coach access."""
    names = [str(s.get("subscription", "")).lower() for s in subs or []]
    if any(k in n for n in names for k in ("coach", "admin", "owner")):
        return "coach"
    if any("manager" in n for n in names):
        return "manager"
    if any(k in n for n in names for k in ("player", "student", "member")):
        return "player"
    return "coach"


PERMISSIONS = {
    "coach": {"edit_roster", "lineup", "match", "challenge", "practice", "adjust", "training",
              "notes", "settings", "delete", "rank", "videos", "quiz_others"},
    "manager": {"match", "challenge", "practice", "training", "notes", "rank", "videos", "quiz_others"},
    "player": set(),
}


def greeting(name: str, role: str) -> str:
    """The front-screen sign: uses the username the person signed up with."""
    name = (name or "").strip()
    if role == "coach":
        return f"Hello Coach {name}!" if name else "Hello Coach!"
    return f"Hello {name}!" if name else "Hello!"
