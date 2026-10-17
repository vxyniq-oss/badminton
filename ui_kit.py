"""Shared colors, fonts and small widgets for the PSAL Badminton app.

Speed: CustomTkinter draws every widget as an anti-aliased canvas, which gets
slow when a screen has hundreds of rows. So the things that appear many times
(text, row containers, chips, avatars, progress bars, list buttons) are plain
native Tk widgets here. Their rounded shapes are drawn once as smooth images
and cached, so they look the same but cost a fraction to create. Big
interactive controls (entries, menus, main buttons) stay CustomTkinter."""
from __future__ import annotations

import platform
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

# (light, dark) pairs — CustomTkinter switches automatically with the theme
BG = ("#F3F5F9", "#0D1015")
SIDEBAR = ("#FFFFFF", "#12151C")
SURFACE = ("#FFFFFF", "#161A22")
SURFACE2 = ("#EEF1F6", "#1D222C")
HOVER = ("#E4E8F0", "#252B37")
BORDER = ("#DFE3EA", "#252B36")
TEXT = ("#0F172A", "#E8EBF1")
MUTED = ("#64748B", "#8B94A5")
ACCENT = ("#2563EB", "#4F8CFF")
ACCENT_HOVER = ("#1D4ED8", "#3B78F0")
ACCENT_SOFT = ("#DBE7FF", "#1B2A47")
LIME = "#C4F432"
GOOD = ("#16A34A", "#22C55E")
BAD = ("#DC2626", "#EF4444")
WARN = ("#D97706", "#F5B83D")
ON_COLOR = "#0B0E13"

PRIORITY_COLORS = {"High": "#EF4444", "Medium": "#F5B83D", "Low": "#22C55E"}
# Big colored banners ("Hello …" sign, login panel). The Manager app swaps
# these for purple via use_manager_theme() before any screen is imported.
HERO = ("#1E4FD8", "#17306B")
HERO_LOGIN = ("#1E4FD8", "#0F1A33")
HERO_PILL = ("#2C5EE6", "#1A2950")
HERO_SUB = "#CFDBFA"
EDITION = "team"


def use_manager_theme():
    global ACCENT, ACCENT_HOVER, ACCENT_SOFT, HERO, HERO_LOGIN, HERO_PILL, HERO_SUB, EDITION
    ACCENT = ("#7C3AED", "#8B5CF6")
    ACCENT_HOVER = ("#6D28D9", "#7C3AED")
    ACCENT_SOFT = ("#EDE4FF", "#2A1F47")
    HERO = ("#6D28D9", "#3B1F73")
    HERO_LOGIN = ("#6D28D9", "#1C1236")
    HERO_PILL = ("#7C3AED", "#2E2152")
    HERO_SUB = "#E3D7FF"
    EDITION = "manager"


POS_COLORS = {"S1": "#F5B83D", "S2": "#60A5FA", "S3": "#2DD4BF", "D1": "#A78BFA", "D2": "#F472B6"}

_SYSTEM = platform.system()
FAMILY = {"Windows": "Segoe UI", "Darwin": "Helvetica Neue"}.get(_SYSTEM, "DejaVu Sans")
_font_cache: dict = {}


def F(size=13, weight="normal"):
    key = (size, weight)
    if key not in _font_cache:
        _font_cache[key] = ctk.CTkFont(family=FAMILY, size=size, weight=weight)
    return _font_cache[key]


def card(master, **kw):
    kw.setdefault("fg_color", SURFACE)
    kw.setdefault("corner_radius", 14)
    kw.setdefault("border_width", 1)
    kw.setdefault("border_color", BORDER)
    return ctk.CTkFrame(master, **kw)


# ------------------------------------------------------------ fast layer
def dark() -> bool:
    return ctk.get_appearance_mode() == "Dark"


def resolve(color):
    """(light, dark) pair -> the hex for the current theme."""
    if isinstance(color, (tuple, list)):
        return color[1] if dark() else color[0]
    return color


def bg_of(w) -> str:
    """The background color a child of `w` should use to blend in."""
    while w is not None:
        try:
            fg = w.cget("fg_color")
            if fg and fg != "transparent":
                return resolve(fg)
        except (tk.TclError, ValueError, AttributeError, KeyError):
            try:
                return w.cget("bg")
            except (tk.TclError, AttributeError):
                pass
        w = getattr(w, "master", None)
    return resolve(BG)


def scale_of(w) -> float:
    try:
        return ctk.ScalingTracker.get_widget_scaling(w)
    except Exception:
        return 1.0


_nfonts: dict = {}


def _root_key():
    root = tk._default_root
    return id(root.tk) if root is not None else 0


def NF(size=13, weight="normal", scale=1.0):
    """Native font in pixels, matching CTkFont sizes at the current DPI scaling."""
    key = (_root_key(), size, weight, round(scale, 2))
    if key not in _nfonts:
        _nfonts[key] = tkfont.Font(family=FAMILY, size=-max(6, round(size * scale)), weight=weight)
    return _nfonts[key]


class FastLabel(tk.Label):
    """tk.Label that also understands the CTk options our code uses."""

    def configure(self, cnf=None, **kw):
        if "text_color" in kw:
            kw["fg"] = resolve(kw.pop("text_color"))
        if "fg_color" in kw:
            c = kw.pop("fg_color")
            kw["bg"] = bg_of(self.master) if c == "transparent" else resolve(c)
        return super().configure(cnf, **kw)

    config = configure

    def cget(self, key):
        return super().cget("fg" if key == "text_color" else key)


def box(master, **kw):
    """Invisible container (fast replacement for a transparent CTkFrame)."""
    sc = scale_of(master)
    for k in ("width", "height"):
        if k in kw:
            kw[k] = max(1, round(kw[k] * sc))
    return tk.Frame(master, bg=bg_of(master), bd=0, highlightthickness=0, **kw)


def label(master, text="", size=13, weight="normal", color=TEXT, width=None, wraplength=None, **kw):
    sc = scale_of(master)
    font = NF(size, weight, sc)
    kw.setdefault("anchor", "w")
    if width:  # CTk widths are pixels; tk label widths are characters
        kw["width"] = max(1, round(width * sc / max(1, font.measure("0"))))
    if wraplength:
        kw["wraplength"] = round(wraplength * sc)
    return FastLabel(master, text=text, font=font, fg=resolve(color), bg=bg_of(master), bd=0,
                     padx=0, pady=1, highlightthickness=0, **kw)


# smooth rounded shapes, drawn once and reused
_imgs: dict = {}


def _rounded(w, h, fill, bg, radius, track=None, frac=None):
    key = (_root_key(), w, h, fill, bg, radius, track, frac)
    if key in _imgs:
        return _imgs[key]
    k = 4  # supersample for smooth edges
    im = Image.new("RGB", (w * k, h * k), bg)
    d = ImageDraw.Draw(im)
    r = min(radius, h // 2, w // 2) * k
    if track is not None:
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r, fill=track)
        if frac and frac > 0:
            fw = max(h * k, int(w * k * frac))
            d.rounded_rectangle([0, 0, fw - 1, h * k - 1], radius=r, fill=fill)
    else:
        d.rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=r, fill=fill)
    im = im.resize((w, h), Image.LANCZOS)
    photo = ImageTk.PhotoImage(im)
    _imgs[key] = photo
    return photo


def chip(master, text, color, text_color=ON_COLOR, size=11):
    sc = scale_of(master)
    font = NF(size, "bold", sc)
    bg = bg_of(master)
    h = round(22 * sc)
    w = font.measure(text) + round(16 * sc)
    img = _rounded(w, h, resolve(color), bg, round(8 * sc))
    return FastLabel(master, image=img, text=text, compound="center", fg=resolve(text_color), bg=bg,
                     font=font, bd=0, padx=0, pady=0, highlightthickness=0)


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper() if parts else "?"


def avatar(master, name, color, size=36):
    sc = scale_of(master)
    px = round(size * sc)
    bg = bg_of(master)
    img = _rounded(px, px, resolve(color), bg, px // 2)
    return FastLabel(master, image=img, text=initials(name), compound="center", fg=ON_COLOR, bg=bg,
                     font=NF(max(11, size // 3), "bold", sc), bd=0, padx=0, pady=0, highlightthickness=0)


def vbar(master, color, width=4):
    """Thin vertical accent bar (pack with fill='y')."""
    sc = scale_of(master)
    return tk.Frame(master, width=max(2, round(width * sc)), height=8, bg=resolve(color), bd=0,
                    highlightthickness=0)


def progress(master, value, color, width=140):
    sc = scale_of(master)
    w, h = round(width * sc), max(4, round(8 * sc))
    bg = bg_of(master)
    frac = round(max(0.0, min(1.0, value)) * 100) / 100
    img = _rounded(w, h, resolve(color), bg, h // 2, track=resolve(SURFACE2) if resolve(SURFACE2) != bg
                   else resolve(HOVER), frac=frac)
    return FastLabel(master, image=img, bg=bg, bd=0, padx=0, pady=0, highlightthickness=0)


_BTN = {
    "primary": (lambda: ACCENT, lambda: ACCENT_HOVER, lambda: "#FFFFFF"),
    "ghost": (lambda: SURFACE2, lambda: HOVER, lambda: TEXT),
    "danger": (lambda: ("#FEE2E2", "#3A1619"), lambda: ("#FECACA", "#4C1C20"), lambda: BAD),
    "good": (lambda: GOOD, lambda: ("#15803D", "#16A34A"), lambda: "#FFFFFF"),
}


class SmallButton(FastLabel):
    """Lightweight rounded button for lists (looks like the big ones, ~20x cheaper)."""

    def __init__(self, master, text, command=None, kind="ghost", width=None, height=30, size=12):
        sc = scale_of(master)
        self._cmd, self._state = command, "normal"
        font = NF(size, "bold", sc)
        bg = bg_of(master)
        fill, hover, fg = (f() for f in _BTN[kind])
        w = max(round((width or 0) * sc), font.measure(text) + round(24 * sc))
        h = round(height * sc)
        r = round(9 * sc)
        self._img = _rounded(w, h, resolve(fill), bg, r)
        self._hov = _rounded(w, h, resolve(hover), bg, r)
        self._dis = _rounded(w, h, resolve(SURFACE2), bg, r)
        self._fg = resolve(fg)
        super().__init__(master, image=self._img, text=text, compound="center", fg=self._fg, bg=bg,
                         font=font, bd=0, padx=0, pady=0, highlightthickness=0, cursor="hand2")
        self.bind("<Enter>", lambda e: self._state == "normal" and super(SmallButton, self).configure(image=self._hov))
        self.bind("<Leave>", lambda e: self._state == "normal" and super(SmallButton, self).configure(image=self._img))
        self.bind("<ButtonRelease-1>", lambda e: self.invoke())

    def invoke(self):
        if self._state == "normal" and self._cmd:
            self._cmd()

    def configure(self, cnf=None, **kw):
        if "state" in kw:
            self._state = str(kw.pop("state"))
            dis = self._state == "disabled"
            super().configure(image=self._dis if dis else self._img, fg=resolve(MUTED) if dis else self._fg,
                              cursor="arrow" if dis else "hand2")
        if "command" in kw:
            self._cmd = kw.pop("command")
        return super().configure(cnf, **kw) if (cnf or kw) else None

    config = configure

    def cget(self, key):
        return self._state if key == "state" else super().cget(key)


def small_button(master, text, command=None, kind="ghost", width=None, height=30, font=None, **_ignored):
    return SmallButton(master, text, command, kind, width, height)


class FastToggle(tk.Frame):
    """Cheap segmented control for long lists: get()/set() like CTkSegmentedButton."""

    def __init__(self, master, values, command=None, size=12):
        super().__init__(master, bg=bg_of(master), bd=0, highlightthickness=0)
        self._cmd = command
        self.var = tk.StringVar(value=values[0])
        sc = scale_of(master)
        font = NF(size, "bold", sc)
        self._sel, self._unsel = resolve(ACCENT), resolve(SURFACE)
        for v in values:
            b = tk.Radiobutton(self, text=v, value=v, variable=self.var, indicatoron=False, font=font,
                               bd=0, relief="flat", offrelief="flat", highlightthickness=0,
                               padx=round(10 * sc), pady=round(4 * sc), cursor="hand2",
                               bg=self._unsel, fg=resolve(TEXT), selectcolor=self._sel,
                               activebackground=resolve(HOVER), activeforeground=resolve(TEXT),
                               command=self._changed)
            b.pack(side="left", padx=(0, 2))
        self._btns = self.winfo_children()
        self._paint()

    def _paint(self):
        for b in self._btns:
            on = b.cget("value") == self.var.get()
            b.configure(fg="#FFFFFF" if on else resolve(TEXT))

    def _changed(self):
        self._paint()
        if self._cmd:
            self._cmd(self.var.get())

    def get(self):
        return self.var.get()

    def set(self, v):
        self.var.set(v)
        self._paint()


def button(master, text, command=None, kind="primary", width=0, **kw):
    styles = {
        "primary": dict(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="#FFFFFF"),
        "ghost": dict(fg_color=SURFACE2, hover_color=HOVER, text_color=TEXT),
        "danger": dict(fg_color=("#FEE2E2", "#3A1619"), hover_color=("#FECACA", "#4C1C20"),
                       text_color=BAD),
        "good": dict(fg_color=GOOD, hover_color=("#15803D", "#16A34A"), text_color="#FFFFFF"),
    }
    opts = dict(styles[kind], corner_radius=10, height=36, font=F(13, "bold"))
    if width:
        opts["width"] = width
    opts.update(kw)
    return ctk.CTkButton(master, text=text, command=command, **opts)


def entry(master, placeholder="", width=200, **kw):
    return ctk.CTkEntry(master, placeholder_text=placeholder, width=width, height=36,
                        corner_radius=10, border_width=1, border_color=BORDER,
                        fg_color=SURFACE2, text_color=TEXT, font=F(13), **kw)


def option(master, values, width=200, command=None, **kw):
    return ctk.CTkOptionMenu(master, values=values or ["—"], width=width, height=36,
                             corner_radius=10, fg_color=SURFACE2, button_color=SURFACE2,
                             button_hover_color=HOVER, text_color=TEXT, font=F(13),
                             dropdown_font=F(13), dynamic_resizing=False, command=command, **kw)


def segmented(master, values, command=None, **kw):
    return ctk.CTkSegmentedButton(master, values=values, command=command, height=34,
                                  corner_radius=10, font=F(12, "bold"), fg_color=SURFACE2,
                                  unselected_color=SURFACE2, unselected_hover_color=HOVER,
                                  selected_color=ACCENT, selected_hover_color=ACCENT_HOVER,
                                  text_color=TEXT, **kw)


def clear(frame):
    for w in frame.winfo_children():
        w.destroy()


def empty_state(master, title, hint=""):
    f = box(master)
    label(f, title, 14, "bold", MUTED, anchor="center").pack(pady=(28, 2))
    if hint:
        label(f, hint, 12, color=MUTED, anchor="center").pack(pady=(0, 24))
    f.pack(fill="x")
    return f


class Dialog(ctk.CTkToplevel):
    """Modal dialog with a title, a body frame and a button row."""

    def __init__(self, master, title, width=460, height=None):
        super().__init__(master)
        self.title(title)
        self.configure(fg_color=BG)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.result = None
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=22, pady=(20, 8))
        label(self.body, title, 18, "bold").pack(fill="x", pady=(0, 12))
        self.buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons.pack(fill="x", padx=22, pady=(4, 20))
        self._dw, self._dh = width, height
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.update_idletasks()
        root = self.master.winfo_toplevel()
        w = self._dw
        h = min(self._dh or self.winfo_reqheight(), self.winfo_screenheight() - 80)
        x = root.winfo_rootx() + (root.winfo_width() - w) // 2
        y = max(10, min(root.winfo_rooty() + max(30, (root.winfo_height() - h) // 2),
                        self.winfo_screenheight() - h - 50))
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.after(80, self._grab)
        return self

    def _grab(self):
        try:
            self.grab_set()
            self.focus_force()
        except tk.TclError:
            pass

    def field(self, title, widget_factory):
        label(self.body, title, 12, "bold", MUTED).pack(fill="x", pady=(8, 4))
        w = widget_factory(self.body)
        w.pack(fill="x")
        return w


def confirm(master, title, message, ok_text="Confirm", danger=False, on_ok=None):
    d = Dialog(master, title, width=440)
    label(d.body, message, 13, color=MUTED, wraplength=390, justify="left").pack(fill="x")

    def ok():
        d.destroy()
        if on_ok:
            on_ok()
    button(d.buttons, ok_text, ok, "danger" if danger else "primary").pack(side="right")
    button(d.buttons, "Cancel", d.destroy, "ghost").pack(side="right", padx=8)
    d.show()
    return d


class FastScroll(tk.Frame):
    _active = None
    _wheel_roots: set = set()

    """Drop-in replacement for CTkScrollableFrame: put children straight into it.

    A plain Tk canvas with a thin rounded scrollbar. Much cheaper to show and
    scroll than CTkScrollableFrame (which redraws its scrollbar and forces an
    extra layout pass every time its contents change)."""

    def __init__(self, master, fg_color="transparent", height=200, corner_radius=0, width=None, **_ignored):
        sc = scale_of(master)
        bg = bg_of(master) if fg_color in (None, "transparent") else resolve(fg_color)
        self._outer = tk.Frame(master, bg=bg, bd=0, highlightthickness=0)
        self._canvas = tk.Canvas(self._outer, bg=bg, bd=0, highlightthickness=0, height=round(height * sc),
                                 yscrollincrement=max(1, round(4 * sc)))
        if width:
            self._canvas.configure(width=round(width * sc))
        self._bw = max(6, round(8 * sc))
        self._bar = tk.Canvas(self._outer, width=self._bw + 4, bg=bg, bd=0, highlightthickness=0)
        self._bar.pack(side="right", fill="y", pady=4)
        self._canvas.pack(side="left", fill="both", expand=True)
        super().__init__(self._canvas, bg=bg, bd=0, highlightthickness=0)
        self._bgc = bg
        self._win = self._canvas.create_window(0, 0, window=self, anchor="nw")
        self._thumb_col = resolve(("#C5CCD8", "#3A4250"))
        self._thumb = self._bar.create_line(0, 0, 0, 0, width=self._bw, capstyle="round", fill=self._thumb_col)
        self._lohi = (0.0, 1.0)
        self._pending = None
        self.bind("<Configure>", self._inner_changed)
        self._canvas.bind("<Configure>", self._canvas_changed)
        self._canvas.configure(yscrollcommand=self._scrolled)
        self._bar.bind("<Configure>", lambda e: self._draw_thumb())
        self._bar.bind("<Button-1>", self._drag_start)
        self._bar.bind("<B1-Motion>", self._drag)
        for w in (self._outer, self._canvas, self):
            w.bind("<Enter>", self._wheel_on, add="+")
            w.bind("<Leave>", self._wheel_off, add="+")
        # one shared wheel handler per window (added once, never replaces other handlers)
        root = self.winfo_toplevel()
        rk = (id(root.tk), str(root))
        if rk not in FastScroll._wheel_roots:
            FastScroll._wheel_roots.add(rk)
            root.bind_all("<MouseWheel>", FastScroll._wheel, add="+")
            root.bind_all("<Button-4>", lambda e: FastScroll._wheel_linux(-1), add="+")
            root.bind_all("<Button-5>", lambda e: FastScroll._wheel_linux(1), add="+")

    # geometry calls act on the outer box, like CTkScrollableFrame
    def pack(self, **kw):
        self._outer.pack(**kw)

    def grid(self, **kw):
        self._outer.grid(**kw)

    def place(self, **kw):
        self._outer.place(**kw)

    def pack_forget(self):
        self._outer.pack_forget()

    def grid_forget(self):
        self._outer.grid_forget()

    def destroy(self):
        # The visible box is self._outer (outer -> canvas -> this frame). Destroying the
        # outer box destroys this frame too, so guard against calling ourselves forever.
        if not getattr(self, "_dying", False):
            self._dying = True
            try:
                self._outer.destroy()
            except tk.TclError:
                pass
            return
        try:
            tk.Frame.destroy(self)
        except tk.TclError:
            pass

    def cget(self, key):
        if key == "fg_color":
            return self._bgc
        return super().cget(key)

    # ------------------------------------------------------------- scrolling
    def _inner_changed(self, _e=None):
        if self._pending is None:  # batch many child changes into one update
            self._pending = self.after_idle(self._update_region)

    def _update_region(self):
        self._pending = None
        try:
            h = self.winfo_reqheight()
            self._canvas.configure(scrollregion=(0, 0, self._canvas.winfo_width(), h))
        except tk.TclError:
            pass

    def _canvas_changed(self, e):
        self._canvas.itemconfigure(self._win, width=e.width)
        self._inner_changed()

    def _fits(self):
        return self.winfo_reqheight() <= self._canvas.winfo_height()

    def _scrolled(self, lo, hi):
        self._lohi = (float(lo), float(hi))
        self._draw_thumb()

    def _draw_thumb(self):
        lo, hi = self._lohi
        h = self._bar.winfo_height()
        if hi - lo >= 0.999 or h < 10:
            self._bar.itemconfigure(self._thumb, state="hidden")
            return
        pad = self._bw // 2 + 2
        x = (self._bw + 4) / 2
        self._bar.coords(self._thumb, x, pad + lo * (h - 2 * pad), x, pad + hi * (h - 2 * pad))
        self._bar.itemconfigure(self._thumb, state="normal")

    def _drag_start(self, e):
        self._drag(e)

    def _drag(self, e):
        lo, hi = self._lohi
        h = max(1, self._bar.winfo_height())
        self._canvas.yview_moveto(max(0.0, min(1.0, e.y / h - (hi - lo) / 2)))

    def _wheel_on(self, _e=None):
        FastScroll._active = self

    def _wheel_off(self, e=None):
        # only release if the pointer really left this scroller (not just moved onto a child)
        try:
            x, y = self.winfo_pointerxy()
            w = self.winfo_containing(x, y)
        except (tk.TclError, KeyError):
            w = None
        while w is not None:
            if w is self._outer:
                return
            w = getattr(w, "master", None)
        if getattr(FastScroll, "_active", None) is self:
            FastScroll._active = None

    @staticmethod
    def _wheel_linux(steps):
        target = FastScroll._active
        if target is not None:
            target._scroll_by(steps)

    @staticmethod
    def _wheel(e):
        target = FastScroll._active
        if target is None:
            return
        try:
            if not target.winfo_exists():
                FastScroll._active = None
                return
        except tk.TclError:
            FastScroll._active = None
            return
        delta = e.delta
        if abs(delta) >= 120:          # Windows: 120 per notch
            steps = -int(delta / 120) * 3
        else:                          # macOS: small values, smooth trackpads
            steps = -delta
        target._scroll_by(steps)

    def _scroll_by(self, steps):
        try:
            if not self._fits():
                self._canvas.yview_scroll(int(steps) * 8, "units")
        except tk.TclError:
            pass
