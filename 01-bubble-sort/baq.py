"""
BUBBLE SORT QUEST: a game that teaches Bubble Sort

Goal:
  A tank holds numbered elements (bubbles, raindrops or fireballs, depending
  on the theme). You may only swap TWO NEIGHBOURS, exactly like Bubble Sort.
  The element on top SURFACES (leaves the tank, gives points) when it is the
  biggest one in the tank, just like the largest element reaches its final
  place after a Bubble Sort pass. Several in a row make a CHAIN (x2, x3, ...),
  which is only possible when the top of the column is already sorted.
  In most levels new elements arrive from below every few seconds; if one
  arrives while the tank is full, the tank overflows and you lose.

Stars:  clear the level  ·  make the level's chain  ·  no wrong swaps

Menu:
  Arrows / mouse  choose,  ENTER / click  confirm,  ESC  back
  F on the level map: rules and star goals of the selected level

In a level:
  Up / Down / wheel   choose a pair of neighbours (or click a pair)
  SPACE / click       swap the selected pair (click it once more)
  F / click NEXT      let the next element in now (bonus points)
  D                   DEMO: the algorithm sorts the tank step by step
                      (in demo: SPACE pause, RIGHT one step, +/- speed)
  P                   pause (shows the rules); leaving the window pauses too
  R                   restart the level
  N                   next level (once this one is solved)
  T                   change theme
  ESC                 back

Anywhere:
  F11 / Alt+Enter     fullscreen on / off (remembered in save.json)

Run:
  pip install pygame
  python baq.py                # add --fullscreen or --windowed to override
"""

import json
import math
import os
import random
import sys

import pygame

from fonts import load_fontsets
from levels import ENDLESS, LEVELS, VMAX, Feed, make_values
from themes import THEMES, W, H, lerp_color

FPS = 60
COL_X = 250            # x centre of the element column
BOTTOM = H - 80        # y of the lowest slot
TOP = 120              # y of the highest slot
SURFACE_Y = TOP - 62   # where surfacing elements pop
PANEL_X = 480          # left edge of the info panel
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")
ENDLESS_UNLOCK = 3     # index of the level that unlocks Endless
OUTLINE = (10, 10, 20)


# ----------------------------------------------------------- algorithm logic
def bubble_sort_steps(values):
    """Bubble Sort written as a generator of steps.

    Instead of sorting the list in one go, the algorithm 'narrates' what it
    does: every yield is one step that the game shows on screen.
    """
    a = values[:]
    n = len(a)
    for i in range(n - 1):                 # passes
        swapped = False
        for j in range(n - 1 - i):         # the last i elements are already in place
            yield ("compare", j, i)
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
                yield ("swap", j, i)
            else:
                yield ("keep", j, i)
        yield ("pass_end", n - 1 - i, i)   # the largest remaining element reached the top
        if not swapped:                    # no swaps in a whole pass = list is sorted
            yield ("early", 0, i)
            break
    yield ("done", 0, 0)


def inversions(values):
    """Pairs that are in the wrong order. Every correct neighbour swap fixes
    exactly one, so this is also the number of swaps Bubble Sort still needs."""
    return sum(1 for i in range(len(values)) for j in range(i + 1, len(values))
               if values[i] > values[j])


def chain_start(values):
    """Index from which the top of the column would surface in one chain."""
    n = len(values)
    if n == 0:
        return 0
    pm, best = [], -1
    for v in values:
        best = max(best, v)
        pm.append(best)
    if values[-1] != pm[-1]:
        return n
    s = n - 1
    while s > 0 and values[s - 1] == pm[s - 1]:
        s -= 1
    return s


PSEUDOCODE = [
    "for i in range(n - 1):",
    "    swapped = False",
    "    for j in range(n - 1 - i):",
    "        if a[j] > a[j + 1]:",
    "            a[j], a[j+1] = a[j+1], a[j]",
    "            swapped = True",
    "    if not swapped: break",
]
STEP_LINE = {"compare": 3, "swap": 4, "keep": 2, "pass_end": 0, "early": 6, "done": -1}


# ------------------------------------------------------------------ easing
def clamp01(p):
    return 0.0 if p < 0 else 1.0 if p > 1 else p


def ease_in_out(p):
    """Slow start, fast middle, slow end (cubic)."""
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out_cubic(p):
    return 1 - (1 - p) ** 3


def ease_out_back(p):
    """Overshoots a little and settles: a springy 'pop'."""
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def approach(cur, target, dt, speed=12.0):
    """Frame-rate independent smoothing towards a target."""
    return cur + (target - cur) * (1 - math.exp(-speed * dt))


# ------------------------------------------------------------------ saving
def load_save():
    blank = {"version": 2, "stars": {}, "best": {}, "theme": "aquarium", "endless": 0,
             "fullscreen": False}
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("version") != 2:          # progress from the old swap-count game
            blank["theme"] = data.get("theme", "aquarium")
            return blank
        blank.update({k: data[k] for k in blank if k in data})
        return blank
    except (OSError, ValueError, AttributeError, TypeError):
        return blank


def write_save(data):
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass                      # saving is a bonus, the game works without it


# ------------------------------------------------------------------- board
class Element:
    def __init__(self, value, y, uid, label=""):
        self.value = value
        self.y = y                 # current (animated) position
        self.uid = uid
        self.label = label         # "a", "b", "c" for equal values (arrival order)
        self.phase = random.uniform(0, math.tau)
        # swap animation: the two elements pass each other on curved paths
        self.from_y = self.to_y = y
        self.anim = 1.0            # 0 -> 1 while swapping
        self.side = 0              # +1 = curve to the right, -1 = to the left
        self.x_off = 0.0
        self.scale = 1.0           # smoothed size multiplier (hover, swap)
        self.hover = False
        self.pop = 0.0             # 1 -> 0 springy bump (win wave, arrival)
        self.pop_delay = 0.0


class Board:
    """The column of elements: positions, swap animation and drawing."""

    SWAP_TIME = 0.28           # seconds per swap animation

    def __init__(self, values, capacity=None, col_x=COL_X, top=TOP, bottom=BOTTOM, intro=True):
        self.col_x, self.top, self.bottom = col_x, top, bottom
        self.cap = max(2, capacity or len(values))
        self.items = []
        self.next_uid = 0
        self.seen = {}
        for i, v in enumerate(values):
            self.items.append(self.make(v, self.slot_y(i)))
        if intro:                  # elements rise into place one after another
            for i, e in enumerate(self.items):
                e.y = H + 60 + i * 55

    def make(self, v, y):
        label = "abcdefgh"[self.seen.get(v, 0) % 8]
        self.seen[v] = self.seen.get(v, 0) + 1
        self.next_uid += 1
        return Element(v, y, self.next_uid, label)

    @property
    def n(self):
        return len(self.items)

    @property
    def step(self):
        return (self.bottom - self.top) / (self.cap - 1)

    def slot_y(self, i):
        """Index 0 = bottom, index cap-1 = top."""
        return self.bottom - i * self.step

    def radius(self, value):
        return int(min(self.step * 0.48, 46) * (0.45 + 0.55 * value / VMAX))

    def values(self):
        return [e.value for e in self.items]

    def swap(self, j):
        a, b = self.items[j], self.items[j + 1]
        self.items[j], self.items[j + 1] = b, a
        for e, idx, side in ((a, j + 1, 1), (b, j, -1)):
            e.from_y, e.to_y = e.y, self.slot_y(idx)
            e.anim, e.side = 0.0, side

    def arrive(self, v):
        """A new element enters at the bottom and pushes the others up."""
        for e in self.items:
            if e.anim < 1:
                e.from_y -= self.step
                e.to_y -= self.step
        e = self.make(v, self.bottom + 110)
        e.pop = 1.0
        self.items.insert(0, e)
        return e

    def pop_wave(self, delay=0.07):
        """Bounce every element, bottom to top, like a wave."""
        for i, e in enumerate(self.items):
            e.pop, e.pop_delay = 1.0, i * delay

    @property
    def busy(self):
        return any(e.anim < 1 for e in self.items)

    def settled(self, i):
        return abs(self.items[i].y - self.slot_y(i)) < 8 and self.items[i].anim >= 1

    def update(self, dt):
        for i, e in enumerate(self.items):
            if e.anim < 1:
                e.anim = min(1.0, e.anim + dt / self.SWAP_TIME)
                p = ease_in_out(e.anim)
                e.y = e.from_y + (e.to_y - e.from_y) * p
                e.x_off = e.side * math.sin(math.pi * e.anim) * 38
            else:
                e.y = approach(e.y, self.slot_y(i), dt, 9 - min(i, 6))
                e.x_off = approach(e.x_off, 0, dt)
            target = 1.0 + (0.1 if e.hover else 0) + (0.12 * math.sin(math.pi * e.anim))
            e.scale = approach(e.scale, target, dt, 14)
            if e.pop_delay > 0:
                e.pop_delay -= dt
            else:
                e.pop = max(0.0, e.pop - dt * 2.2)

    def x_of(self, e, t):
        return self.col_x + math.sin(t * 1.5 + e.phase) * 4 + e.x_off

    @staticmethod
    def pop_scale(e):
        if e.pop <= 0 or e.pop_delay > 0:
            return 1.0
        return 1 + 0.35 * math.sin(math.pi * (1 - e.pop)) * e.pop

    def pair_at(self, pos):
        """Pair index (j, j+1) whose middle is closest to the mouse, or None."""
        if self.n < 2:
            return None
        x, y = pos
        if abs(x - self.col_x) > 100 or not (self.slot_y(self.n - 1) - 50 <= y <= self.bottom + 50):
            return None
        mids = [(self.slot_y(j) + self.slot_y(j + 1)) / 2 for j in range(self.n - 1)]
        return min(range(self.n - 1), key=lambda j: abs(mids[j] - y))

    def draw(self, s, theme, font, t, ring_from, hidden=False, dx=0, labels=True):
        vals = self.values()
        # moving elements are drawn last, so they pass in front of the others
        order = sorted(range(self.n), key=lambda i: (self.items[i].anim < 1, self.items[i].side))
        for i in order:
            e = self.items[i]
            ring = theme.accent if i >= ring_from else None
            r = int(self.radius(e.value) * e.scale * self.pop_scale(e))
            label = e.label if labels and vals.count(e.value) > 1 else ""
            theme.draw_element(s, font, self.x_of(e, t) + dx, e.y, r,
                               e.value, VMAX, t, ring, label, e.phase, hidden)


# ------------------------------------------------------------------ buttons
class Button:
    def __init__(self, rect, label, action, enabled=True, sub=""):
        self.rect = pygame.Rect(rect)
        self.label, self.action, self.enabled, self.sub = label, action, enabled, sub


def _font(role):
    return property(lambda self: self.fontsets[self.theme.key][role])


# --------------------------------------------------------------------- game
class Game:
    f_title, f_big, f_head, f_mid = _font("title"), _font("big"), _font("head"), _font("mid")
    f_small, f_tiny, f_value, f_elem = _font("small"), _font("tiny"), _font("value"), _font("elem")
    f_code = _font("code")

    def __init__(self):
        pygame.init()
        self.save = load_save()
        if "--fullscreen" in sys.argv:
            self.save["fullscreen"] = True
        elif "--windowed" in sys.argv:
            self.save["fullscreen"] = False
        self.fullscreen = False
        self.set_display(self.save["fullscreen"])
        self.clock = pygame.time.Clock()
        self.themes = [cls() for cls in THEMES]
        self.fontsets = load_fontsets([th.key for th in self.themes])
        keys = [th.key for th in self.themes]
        self.theme_idx = keys.index(self.save["theme"]) if self.save["theme"] in keys else 0
        self.apply_theme()

        self.t = 0.0
        self.dt = 1 / FPS
        self.trans = None                 # screen transition (snapshot of the old frame)
        self.scene_age = 0.0              # drives the entrance animations
        self.ui = {}                      # smoothed hover amounts of buttons, keyed by name
        self.shaking = {}                 # locked level cards / buttons that wiggle when clicked
        self.hand = False                 # is the mouse cursor a hand?
        self.glyphs = {}                  # cache of outlined text
        self.info_open = False            # rules card on the level map
        self.badge_tip = None
        self.paused = None                # None | "brief" | "pause" (in a level)
        self.scene = "menu"
        self.sel = 0                      # keyboard selection in menus
        self.level_sel = self.first_unfinished()
        self.demo_delay = 0.6
        self.menu_demo_reset()

    # ---------------------------------------------------------- helpers
    @property
    def theme(self):
        return self.themes[self.theme_idx]

    def apply_theme(self):
        pygame.display.set_caption(f"{self.theme.title}: Bubble Sort Quest")
        self.save["theme"] = self.theme.key

    def stars(self, idx):
        return self.save["stars"].get(str(idx), 0)

    def unlocked(self, idx):
        return idx == 0 or self.stars(idx - 1) > 0

    def endless_unlocked(self):
        return self.stars(ENDLESS_UNLOCK) > 0

    def first_unfinished(self):
        for i in range(len(LEVELS)):
            if self.stars(i) == 0:
                return i
        return 0

    def ent(self, k=0, step=0.06, dur=0.5, delay=0.04, back=False):
        """Entrance progress 0 -> 1 of the k-th thing on a freshly opened screen."""
        p = clamp01((self.scene_age - delay - k * step) / dur)
        return ease_out_back(p) if back else ease_out_cubic(p)

    def outlined(self, font, txt, color, outline=OUTLINE, width=2):
        """Text with a dark outline (cached: it is drawn every frame)."""
        key = (id(font), txt, tuple(color), outline, width)
        img = self.glyphs.get(key)
        if img is None:
            if len(self.glyphs) > 3000:
                self.glyphs.clear()
            base = font.render(txt, True, outline)
            fg = font.render(txt, True, color)
            img = pygame.Surface((fg.get_width() + 2 * width, fg.get_height() + 2 * width), pygame.SRCALPHA)
            for ddx in (-width, 0, width):
                for ddy in (-width, 0, width):
                    if ddx or ddy:
                        img.blit(base, (width + ddx, width + ddy))
            img.blit(fg, (width, width))
            self.glyphs[key] = img
        return img

    def otext(self, font, txt, center, color, width=2, alpha=255, scale=1.0, surf=None):
        img = self.outlined(font, txt, color, OUTLINE, width)
        if scale != 1.0:
            img = pygame.transform.smoothscale_by(img, max(0.01, scale))
        elif alpha < 255:
            img = img.copy()
        if alpha < 255:
            img.set_alpha(int(max(0, alpha)))
        (surf or self.screen).blit(img, img.get_rect(center=(int(center[0]), int(center[1]))))

    def wave_text(self, font, txt, cx, cy, color, width=3, amp=5.0, speed=2.4):
        """A title whose letters bob one after another."""
        total = font.size(txt)[0]
        x = cx - total / 2
        for i, ch in enumerate(txt):
            w = font.size(txt[:i + 1])[0] - font.size(txt[:i])[0]
            if ch != " ":
                y = cy + math.sin(self.t * speed - i * 0.45) * amp
                self.otext(font, ch, (x + w / 2, y), color, width)
            x += w

    def text(self, txt, font, color, x, y, alpha=255, scale=1.0):
        img = font.render(txt, True, color)
        h = img.get_height()
        if scale != 1.0:
            img = pygame.transform.smoothscale_by(img, scale)
            y0 = y - (img.get_height() - h) / 2      # grows around its middle line
        else:
            y0 = y
        if alpha < 255:
            img.set_alpha(int(alpha))
        self.screen.blit(img, (x, y0))
        return y + h + 4

    def center_text(self, txt, font, color, cx, y, surf=None):
        img = font.render(txt, True, color)
        (surf or self.screen).blit(img, img.get_rect(midtop=(cx, y)))
        return y + img.get_height() + 4

    def smooth(self, key, target, speed=14.0):
        """A value that glides towards target; used for hover animations."""
        v = approach(self.ui.get(key, target), target, self.dt, speed)
        self.ui[key] = v
        return v

    def set_hand(self, on):
        """Show a hand cursor over clickable things."""
        if on != self.hand:
            self.hand = on
            try:
                pygame.mouse.set_system_cursor(pygame.SYSTEM_CURSOR_HAND if on
                                               else pygame.SYSTEM_CURSOR_ARROW)
            except (pygame.error, AttributeError):
                pass

    def wrap(self, txt, font, width):
        """Split text into lines that fit `width` pixels."""
        lines, cur = [], ""
        for w in txt.split():
            test = f"{cur} {w}".strip()
            if cur and font.size(test)[0] > width:
                lines.append(cur)
                cur = w
            else:
                cur = test
        return lines + [cur]

    _panel_cache = {}

    def panel(self, rect, alpha=210, surf=None):
        key = (rect.size, self.theme.panel_bg, int(alpha))
        img = self._panel_cache.get(key)
        if img is None:
            if len(self._panel_cache) > 300:
                self._panel_cache.clear()
            img = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(img, (*self.theme.panel_bg, int(alpha)), img.get_rect(), border_radius=14)
            self._panel_cache[key] = img
        (surf or self.screen).blit(img, rect)

    def glow_rect(self, rect, color, strength, radius=16, layers=4):
        """Soft halo around a rounded rectangle."""
        if strength <= 0.01:
            return
        pad = layers * 5
        surf = pygame.Surface((rect.w + pad * 2, rect.h + pad * 2), pygame.SRCALPHA)
        for k in range(layers, 0, -1):
            r = pygame.Rect(pad - k * 5, pad - k * 5, rect.w + k * 10, rect.h + k * 10)
            pygame.draw.rect(surf, (*color, int(min(1.0, strength) * 40 / k)), r, border_radius=radius + k * 5)
        self.screen.blit(surf, (rect.x - pad, rect.y - pad))

    def draw_button(self, b, selected, key, ox=0):
        th = self.theme
        a = self.smooth(key, 1.0 if selected and b.enabled else 0.0)
        r = b.rect.inflate(int(12 * a), int(6 * a)).move(ox, 0)
        if key in self.shaking:
            r.x += int(math.sin(self.shaking[key] * 50) * 7 * self.shaking[key] / 0.45)
        self.glow_rect(r, th.accent, a)
        self.panel(r, 190 + 50 * a)
        pygame.draw.rect(self.screen, lerp_color(th.dim, th.accent, a), r, 1 + round(2 * a),
                         border_radius=14)
        color = lerp_color(th.text if b.enabled else th.dim, th.accent, a)
        img = self.f_mid.render(b.label, True, color)
        if b.sub:
            sub = self.f_tiny.render(b.sub.upper(), True, lerp_color(th.dim, th.text, a))
            self.screen.blit(img, img.get_rect(midbottom=(r.centerx, r.centery + 4)))
            self.screen.blit(sub, sub.get_rect(midtop=(r.centerx, r.centery + 5)))
        else:
            self.screen.blit(img, img.get_rect(center=r.center))
        # a small arrow slides in next to the selected button
        if a > 0.05:
            ax = r.x - 8 - 14 * a
            cy = r.centery
            pts = [(ax, cy - 8), (ax + 10, cy), (ax, cy + 8)]
            pygame.draw.polygon(self.screen, lerp_color(th.panel_bg, th.accent, a), pts)

    # ------------------------------------------------- modern UI pieces
    def card(self, rect, tint=0.06, alpha=215, radius=14, border=None, surf=None):
        """A rounded card a bit lighter (tint > 0) or darker (tint < 0) than the panel."""
        th = self.theme
        base = lerp_color(th.panel_bg, (255, 255, 255) if tint > 0 else (0, 0, 0), abs(tint))
        img = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(img, (*base, alpha), img.get_rect(), border_radius=radius)
        if border:
            pygame.draw.rect(img, border, img.get_rect(), 1, border_radius=radius)
        (surf or self.screen).blit(img, rect)

    def caps(self, txt, x, y, color, anchor="topleft"):
        """Small capital letters, used for labels."""
        img = self.f_tiny.render(txt.upper(), True, color)
        r = img.get_rect(**{anchor: (x, y)})
        self.screen.blit(img, r)
        return r

    def chip(self, txt, x, y, color, filled=False):
        """A pill-shaped tag. Returns its width."""
        img = self.f_tiny.render(txt.upper(), True, (20, 20, 25) if filled else color)
        r = pygame.Rect(x, y, img.get_width() + 18, img.get_height() + 8)
        surf = pygame.Surface(r.size, pygame.SRCALPHA)
        if filled:
            pygame.draw.rect(surf, color, surf.get_rect(), border_radius=r.h // 2)
        else:
            pygame.draw.rect(surf, (*color, 40), surf.get_rect(), border_radius=r.h // 2)
            pygame.draw.rect(surf, (*color, 160), surf.get_rect(), 1, border_radius=r.h // 2)
        surf.blit(img, img.get_rect(center=surf.get_rect().center))
        self.screen.blit(surf, r)
        return r.w

    def keycap(self, label, x, y):
        """A keyboard key drawn as a small 3D cap. Returns its width."""
        th = self.theme
        img = self.f_tiny.render(label, True, th.text)
        r = pygame.Rect(x, y, max(24, img.get_width() + 14), 22)
        pygame.draw.rect(self.screen, lerp_color(th.panel_bg, (0, 0, 0), 0.4), r.move(0, 2), border_radius=5)
        pygame.draw.rect(self.screen, lerp_color(th.panel_bg, (255, 255, 255), 0.16), r, border_radius=5)
        pygame.draw.rect(self.screen, lerp_color(th.panel_bg, (255, 255, 255), 0.3), r, 1, border_radius=5)
        self.screen.blit(img, img.get_rect(center=r.center))
        return r.w

    @staticmethod
    def star_points(cx, cy, r_out, r_in=None):
        r_in = r_in or r_out * 0.45
        pts = []
        for k in range(10):
            r = r_out if k % 2 == 0 else r_in
            a = -math.pi / 2 + k * math.pi / 5
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        return pts

    def draw_star(self, cx, cy, r, filled, scale=1.0, surf=None):
        th, s = self.theme, surf or self.screen
        pts = self.star_points(cx, cy, r * scale)
        if filled:
            pygame.draw.polygon(s, lerp_color(th.accent, (120, 70, 0), 0.45), [(x, y + 2) for x, y in pts])
            pygame.draw.polygon(s, th.accent, pts)
        else:
            pygame.draw.polygon(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), pts)
            pygame.draw.polygon(s, lerp_color(th.dim, th.panel_bg, 0.4), pts, 2)

    def draw_icon(self, kind, cx, cy, color, surf=None):
        """Tiny vector icons: clock (arrivals), limit (strict), eye (hidden),
        speed, free (no arrivals), tank, twins, rising."""
        s = surf or self.screen
        if kind == "speed":
            for k in (-5, 1):
                pygame.draw.lines(s, color, False, [(cx + k, cy - 6), (cx + k + 5, cy), (cx + k, cy + 6)], 2)
        elif kind == "free":
            pygame.draw.lines(s, color, False, [(cx - 7, cy - 7), (cx + 7, cy - 7), (cx - 7, cy + 7),
                                                 (cx + 7, cy + 7), (cx - 7, cy - 7)], 2)
        elif kind == "tank":
            pygame.draw.rect(s, color, (cx - 6, cy - 8, 12, 16), 2, border_radius=3)
            pygame.draw.line(s, color, (cx - 3, cy + 3), (cx + 3, cy + 3), 2)
        elif kind == "twins":
            pygame.draw.circle(s, color, (cx - 4, cy), 5, 2)
            pygame.draw.circle(s, color, (cx + 4, cy), 5, 2)
        elif kind == "rising":
            pygame.draw.lines(s, color, False, [(cx - 7, cy + 6), (cx - 2, cy + 1), (cx + 1, cy + 3), (cx + 7, cy - 5)], 2)
            pygame.draw.polygon(s, color, [(cx + 8, cy - 7), (cx + 2, cy - 6), (cx + 7, cy - 1)])
        elif kind == "clock":
            pygame.draw.circle(s, color, (cx, cy), 7, 2)
            pygame.draw.line(s, color, (cx, cy), (cx, cy - 4), 2)
            pygame.draw.line(s, color, (cx, cy), (cx + 3, cy + 1), 2)
        elif kind == "limit":
            for k in range(3):
                pygame.draw.line(s, color, (cx - 6 + k * 4, cy - 6), (cx - 6 + k * 4, cy + 6), 2)
            pygame.draw.line(s, color, (cx - 8, cy + 4), (cx + 6, cy - 4), 2)
        elif kind == "eye":
            pygame.draw.ellipse(s, color, (cx - 8, cy - 5, 16, 10), 2)
            pygame.draw.circle(s, color, (cx, cy), 2)
            pygame.draw.line(s, color, (cx - 8, cy + 6), (cx + 8, cy - 6), 2)

    # --------------------------------------------------- rules / info card
    START_KIND = {"reversed": "It starts reversed: the worst case.",
                  "nearly": "It starts nearly sorted: the best case.",
                  "sinker": "The biggest one starts at the very bottom."}

    def level_rules(self, lv):
        """(icon, title, description) for every rule of a level."""
        th = self.theme
        rules = []
        if lv.spawn:
            rules.append(("clock", "Arrivals",
                          f"A new {th.noun} enters at the bottom every {lv.spawn:g} s (watch the NEXT box). "
                          "If the tank is full when it comes, the tank overflows and you lose."))
            if lv.speedup < 1:
                rules.append(("speed", "Speeding up",
                              f"Each arrival comes {round((1 - lv.speedup) * 100)}% sooner than the one "
                              f"before, down to one every {lv.min_spawn:g} s."))
        else:
            rules.append(("free", "No arrivals", "Nothing new comes in. Take your time and empty the tank."))
        rules.append(("tank", f"Tank of {lv.capacity}",
                      f"At most {lv.capacity} {th.nouns} fit; you start with {lv.start}. "
                      + self.START_KIND.get(lv.kind, "")))
        if lv.feed == "dupes":
            rules.append(("twins", "Twins", "Equal values arrive (labelled a, b, c). Never swap two equal "
                          "ones: Bubble Sort keeps them in their order, that is what stable means."))
        if lv.feed == "rising":
            rules.append(("rising", "Rising stream", "Every newcomer is bigger than the one before, "
                          "so each one has to travel up the whole tank."))
        if lv.strict:
            rules.append(("limit", "No wrong swaps", "Swapping a pair that is already in order (or equal) "
                          "cracks the tank: the level is lost at once."))
        if lv.hidden:
            rules.append(("eye", "Hidden numbers", "The numbers are not shown. Compare the sizes instead."))
        return rules

    def level_goals(self, lv):
        if lv.goal is None:
            return [("Survive", "keep the tank from overflowing as long as you can"),
                    ("Score", f"chains multiply points; your best is {self.save.get('endless', 0)}"),
                    ("Clean", "no wrong swaps")]
        return [("Cleared", f"surface {lv.goal} {self.theme.nouns}"),
                (f"Chain ×{lv.chain}", f"surface {lv.chain} in a row: sort the top before the biggest gets there"),
                ("Clean", "never swap a pair that is already in order")]

    def draw_info_card(self, lv, header, footer, p):
        """A card in the middle of the screen with the rules and the star goals
        of a level. p (0..1) animates it in and out."""
        th = self.theme
        cw, pad = 620, 26
        tw = cw - 2 * pad - 46
        rules = [(ic, t, self.wrap(d, self.f_small, tw)) for ic, t, d in self.level_rules(lv)]
        lesson = self.wrap(lv.lesson, self.f_small, cw - 2 * pad)
        goals = self.level_goals(lv)
        title_h = self.f_big.get_height() + 2
        ch = (pad + 18 + title_h + 20 * len(lesson) + 14
              + sum(26 + 20 * len(d) + 8 for _, _, d in rules)
              + 16 + 22 + 3 * 26 + 18 + 24 + pad - 8)
        card = pygame.Surface((cw, ch), pygame.SRCALPHA)
        pygame.draw.rect(card, (*th.panel_bg, 250), card.get_rect(), border_radius=16)
        pygame.draw.rect(card, (*th.accent, 200), card.get_rect(), 2, border_radius=16)
        y = pad
        img = self.f_tiny.render(header.upper(), True, th.accent)
        card.blit(img, (pad, y))
        y += 18
        img = self.f_big.render(lv.name, True, th.text)
        card.blit(img, (pad, y))
        y += title_h
        for line in lesson:
            card.blit(self.f_small.render(line, True, th.dim), (pad, y))
            y += 20
        y += 6
        pygame.draw.line(card, lerp_color(th.panel_bg, th.dim, 0.4), (pad, y), (cw - pad, y), 1)
        y += 8
        for icon, title, desc in rules:
            ic = (pad + 16, y + 13)
            pygame.draw.circle(card, lerp_color(th.panel_bg, th.accent, 0.18), ic, 16)
            pygame.draw.circle(card, th.accent, ic, 16, 1)
            self.draw_icon(icon, ic[0], ic[1], th.accent, card)
            card.blit(self.f_mid.render(title, True, th.text), (pad + 46, y + 1))
            y += 26
            for line in desc:
                card.blit(self.f_small.render(line, True, th.dim), (pad + 46, y))
                y += 20
            y += 8
        pygame.draw.line(card, lerp_color(th.panel_bg, th.dim, 0.4), (pad, y), (cw - pad, y), 1)
        y += 12
        card.blit(self.f_tiny.render("THREE STARS", True, th.accent), (pad, y))
        y += 22
        for title, desc in goals:
            self.draw_star(pad + 12, y + 10, 9, True, surf=card)
            img = self.f_mid.render(title, True, th.text)
            card.blit(img, (pad + 30, y))
            card.blit(self.f_small.render("  " + desc, True, th.dim), (pad + 30 + img.get_width(), y + 2))
            y += 26
        y += 10
        img = self.f_small.render(footer, True, th.dim)
        card.blit(img, img.get_rect(midtop=(cw // 2, y)))

        veil = pygame.Surface((W, H), pygame.SRCALPHA)
        veil.fill((0, 0, 0, int(150 * p)))
        self.screen.blit(veil, (0, 0))
        sc = 0.9 + 0.1 * ease_out_back(p)
        center = (W // 2, H // 2 + int(30 * (1 - p)))
        img = pygame.transform.smoothscale_by(card, sc) if sc != 1 else card
        img.set_alpha(int(255 * min(1.0, p * 1.5)))
        rect = img.get_rect(center=center)
        self.glow_rect(rect, th.accent, 0.5 * p, 16)
        self.screen.blit(img, rect)

    # ---------------------------------------------------------- main loop
    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    write_save(self.save)
                    return
                self.handle(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def quit(self):
        write_save(self.save)
        pygame.quit()
        sys.exit()

    # ------------------------------------------------------ transitions
    def begin_transition(self, kind="fade", center=None, dur=None):
        """Remember the current frame; it is drawn over the new one while it
        fades and zooms out ("fade") or while a circle of the new frame grows
        through it ("circle")."""
        img = self.screen.copy()
        if kind == "circle":
            img = img.convert_alpha()
        self.trans = {"img": img, "age": 0.0, "kind": kind,
                      "center": center or (W // 2, H // 2),
                      "dur": dur or (0.75 if kind == "circle" else 0.38)}

    def draw_transition(self):
        tr = self.trans
        p = tr["age"] / tr["dur"]
        if p >= 1:
            self.trans = None
            return
        if tr["kind"] == "fade":
            e = ease_out_cubic(p)
            img = pygame.transform.smoothscale_by(tr["img"], 1 + 0.05 * e)
            img.set_alpha(int(255 * (1 - e)))
            self.screen.blit(img, img.get_rect(center=(W // 2, H // 2)))
        else:
            cx, cy = tr["center"]
            far = max(math.hypot(cx - x, cy - y) for x in (0, W) for y in (0, H))
            r = int(far * ease_in_out(p)) + 1
            img = tr["img"].copy()
            pygame.draw.circle(img, (0, 0, 0, 0), (cx, cy), r)
            self.screen.blit(img, (0, 0))
            col = self.theme.accent
            glow = pygame.Surface((W, H), pygame.SRCALPHA)
            for k in range(5):
                pygame.draw.circle(glow, (*col, 60 - k * 11), (cx, cy), r + k * 4, 4)
            self.screen.blit(glow, (0, 0))
            pygame.draw.circle(self.screen, col, (cx, cy), r, 3)

    def go(self, scene, transition=True):
        if transition:
            self.begin_transition("fade")
        self.scene = scene
        self.scene_age = 0.0
        self.sel = 0
        self.info_open = False
        if scene == "levels":
            self.sel = self.level_sel
        elif scene == "themes":
            self.sel = self.theme_idx
        elif scene == "menu":
            self.menu_demo_reset()

    # ------------------------------------------------------- fullscreen
    def set_display(self, fullscreen):
        """The game always draws at W x H; SCALED stretches it to the window or
        the whole screen (keeping the aspect ratio) and maps the mouse back."""
        flags = pygame.SCALED | (pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
            self.fullscreen = fullscreen
        except pygame.error:
            self.screen = pygame.display.set_mode((W, H))
            self.fullscreen = False

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = not self.fullscreen
        except pygame.error:
            self.set_display(not self.fullscreen)
        self.save["fullscreen"] = self.fullscreen
        write_save(self.save)

    def handle(self, e):
        if e.type == pygame.KEYDOWN and (e.key == pygame.K_F11 or
                                         (e.key == pygame.K_RETURN and e.mod & pygame.KMOD_ALT)):
            self.toggle_fullscreen()
            return
        if e.type == getattr(pygame, "WINDOWFOCUSLOST", -1) and self.scene == "play":
            self.pause("pause")                   # alt-tab / click outside pauses the level
            return
        getattr(self, f"handle_{self.scene}")(e)

    def update(self, dt):
        self.t += dt
        self.dt = dt
        self.scene_age += dt
        if self.trans:
            self.trans["age"] += dt
        for k in list(self.shaking):
            self.shaking[k] -= dt
            if self.shaking[k] <= 0:
                del self.shaking[k]
        self.theme.update(dt, self.t)
        if self.scene == "play":
            self.update_play(dt)
        elif self.scene == "menu":
            self.update_menu_demo(dt)

    def draw(self):
        self.theme.draw_background(self.screen, self.t)
        getattr(self, f"draw_{self.scene}")()
        self.theme.draw_sparks(self.screen)
        if self.trans:
            self.draw_transition()

    # ------------------------------------------------- generic menu input
    def menu_input(self, e, buttons, cols=1, on_locked=None):
        """Keyboard + mouse navigation shared by all menu screens."""
        if e.type == pygame.KEYDOWN:
            step = {pygame.K_UP: -cols, pygame.K_DOWN: cols,
                    pygame.K_LEFT: -1, pygame.K_RIGHT: 1}.get(e.key)
            if cols == 1 and e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                step = None
            if step is not None:
                self.sel = (self.sel + step) % len(buttons)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                b = buttons[self.sel]
                if b.enabled:
                    b.action()
                elif on_locked:
                    on_locked(self.sel)
        elif e.type == pygame.MOUSEMOTION:
            over = False
            for i, b in enumerate(buttons):
                if b.rect.collidepoint(e.pos):
                    self.sel = i
                    over = b.enabled
            self.set_hand(over)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, b in enumerate(buttons):
                if b.rect.collidepoint(e.pos):
                    self.sel = i
                    if b.enabled:
                        self.set_hand(False)
                        b.action()
                    elif on_locked:
                        on_locked(i)
                    return

    # ---------------------------------------------------------- main menu
    def menu_buttons(self):
        x, w = 560, 320
        nxt = self.first_unfinished()
        best = self.save.get("endless", 0)
        items = [("Play", lambda: self.start_level(self.first_unfinished()), True,
                  f"level {nxt + 1}: {LEVELS[nxt].name}"),
                 ("Level map", lambda: self.go("levels"), True, ""),
                 ("Endless tide", lambda: self.start_level("endless"), self.endless_unlocked(),
                  f"best {best}" if self.endless_unlocked() else f"clear level {ENDLESS_UNLOCK + 1} to unlock"),
                 ("Theme: " + self.theme.title, lambda: self.go("themes"), True, ""),
                 ("Fullscreen: " + ("on" if self.fullscreen else "off"), self.toggle_fullscreen, True, "F11"),
                 ("Quit", self.quit, True, "")]
        return [Button((x, 278 + k * 64, w, 54), lbl, act, ok, sub)
                for k, (lbl, act, ok, sub) in enumerate(items)]

    def menu_demo_reset(self):
        self.menu_board = Board(make_values(LEVELS[1]), None, COL_X, 200, BOTTOM)
        self.menu_steps = bubble_sort_steps(self.menu_board.values())
        self.menu_timer = 0.0
        self.menu_pair = None
        self.menu_sorted = self.menu_board.n

    def update_menu_demo(self, dt):
        """A tiny self-playing demo on the left side of the main menu."""
        self.menu_board.update(dt)
        self.menu_timer += dt
        if self.menu_timer < 0.45:
            return
        self.menu_timer = 0
        step = next(self.menu_steps, None)
        if step is None:                     # finished and admired: start again
            self.menu_demo_reset()
            return
        kind, j, _ = step
        if kind in ("compare", "keep"):
            self.menu_pair = j
        elif kind == "swap":
            self.menu_board.swap(j)
            self.theme.burst(COL_X, self.menu_board.slot_y(j + 1), 6)
        elif kind == "pass_end":
            self.menu_sorted = j
            self.menu_board.items[j].pop = 1.0
            self.menu_pair = None
        elif kind in ("early", "done"):
            self.menu_sorted = 0
            self.menu_pair = None
            if kind == "done":
                self.menu_board.pop_wave()
                self.menu_timer = -2.0       # admire the result for a moment

    def handle_menu(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.quit()
        if e.type == pygame.KEYDOWN and e.key == pygame.K_t:
            self.cycle_theme()
            return
        self.menu_input(e, self.menu_buttons(), on_locked=lambda i: self.shaking.__setitem__(f"menu{i}", 0.45))

    def draw_menu(self):
        s, th = self.screen, self.theme
        rect = pygame.Rect(COL_X - 110, 140, 220, BOTTOM - 200 + 120)
        th.draw_container(s, rect, self.t)
        self.otext(self.f_small, th.up_label, (COL_X, 122), th.dim, 1)
        a = self.smooth("menu_pair_a", 1.0 if self.menu_pair is not None else 0.0, 8)
        if self.menu_pair is not None:
            self.smooth("menu_pair_f", self.menu_pair, 10)
        if a > 0.02:
            self.draw_selector(self.menu_board, self.ui.get("menu_pair_f", 0), th.accent, a)
        self.menu_board.draw(s, th, self.f_elem, self.t, self.menu_sorted)

        e0 = self.ent(0, dur=0.6)
        self.wave_text(self.f_title, th.title, 720, 105 - 40 * (1 - e0), th.accent, 3)
        e1 = self.ent(1)
        self.otext(self.f_mid, "a game about Bubble Sort", (720, 165 + 20 * (1 - e1)), th.text, 2)
        self.otext(self.f_small, th.tagline, (720, 196 + 20 * (1 - e1)), th.dim, 1)
        total = sum(self.stars(i) for i in range(len(LEVELS)))
        self.draw_star(672, 240, 11, True)
        img = self.outlined(self.f_mid, f"{total} / {3 * len(LEVELS)}", th.accent)
        s.blit(img, img.get_rect(midleft=(690, 240)))
        for i, b in enumerate(self.menu_buttons()):
            ox = int(90 * (1 - self.ent(i + 2, step=0.06)))
            self.draw_button(b, i == self.sel, f"menu{i}", ox)
        self.otext(self.f_small, "↑↓ choose   ENTER confirm   T theme   F11 fullscreen   ESC quit",
                   (720, H - 30), th.dim, 1)

    # -------------------------------------------------------- level select
    # Levels are nodes on a winding path, like a map in a mobile game:
    # row 1 goes left -> right, row 2 right -> left, row 3 left -> right.
    NODE_XS = (190, 393, 597, 800)
    NODE_YS = (165, 300, 435)
    NODE_R = 34

    def node_pos(self, i):
        row, col = divmod(i, 4)
        if row % 2:
            col = 3 - col
        return self.NODE_XS[col], self.NODE_YS[row]

    def level_buttons(self):
        out = []
        for i in range(len(LEVELS)):
            x, y = self.node_pos(i)
            r = pygame.Rect(0, 0, 120, 120)
            r.center = (x, y + 14)
            out.append(Button(r, LEVELS[i].name, lambda i=i: self.start_level(i), self.unlocked(i)))
        return out

    def play_button_rect(self):
        return pygame.Rect(W - 90 - 170, 590, 150, 60)

    def rules_link_rect(self):
        return pygame.Rect(W - 90 - 170, 652, 150, 24)

    def handle_levels(self, e):
        if self.info_open:                       # the rules card is open
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_ESCAPE, pygame.K_f, pygame.K_i, pygame.K_BACKSPACE):
                    self.info_open = False
                elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    if self.unlocked(self.sel):
                        self.info_open = False
                        self.start_level(self.sel)
                    else:
                        self.locked_click(self.sel)
                elif e.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    d = 1 if e.key in (pygame.K_RIGHT, pygame.K_DOWN) else -1
                    self.sel = self.level_sel = (self.sel + d) % len(LEVELS)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                self.info_open = False
            return
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_f, pygame.K_i):
            self.info_open = True
            return
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.rules_link_rect().collidepoint(e.pos)):
            self.info_open = True
            return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.go("menu")
                return
            if e.key == pygame.K_t:
                self.cycle_theme()
                return
            # arrows jump to the nearest node in that direction (works on the winding path)
            d = {pygame.K_LEFT: (-1, 0), pygame.K_RIGHT: (1, 0),
                 pygame.K_UP: (0, -1), pygame.K_DOWN: (0, 1)}.get(e.key)
            if d:
                x0, y0 = self.node_pos(self.sel)
                best, best_cost = None, 1e9
                for i in range(len(LEVELS)):
                    x, y = self.node_pos(i)
                    dx, dy = x - x0, y - y0
                    along = dx * d[0] + dy * d[1]
                    if i == self.sel or along <= 0:
                        continue
                    cost = along + 2.5 * abs(dx * d[1] + dy * d[0])
                    if cost < best_cost:
                        best, best_cost = i, cost
                if best is not None:
                    self.sel = self.level_sel = best
                return
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.play_button_rect().collidepoint(e.pos)):
            if self.unlocked(self.sel):
                self.start_level(self.sel)
            else:
                self.locked_click(self.sel)
            return
        if e.type == pygame.MOUSEMOTION:
            # hover over a node only highlights it; the selection changes on click
            over = any(b.rect.collidepoint(e.pos) and b.enabled for b in self.level_buttons())
            self.set_hand(over or self.play_button_rect().collidepoint(e.pos)
                          or self.rules_link_rect().collidepoint(e.pos))
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, b in enumerate(self.level_buttons()):
                if b.rect.collidepoint(e.pos):
                    if i == self.sel and b.enabled:
                        self.start_level(i)        # second click on a node = play
                    elif not b.enabled:
                        self.sel = self.level_sel = i
                        self.locked_click(i)
                    else:
                        self.sel = self.level_sel = i
                    return
            return
        self.menu_input(e, self.level_buttons(), cols=4, on_locked=self.locked_click)
        self.level_sel = self.sel

    def locked_click(self, i):
        self.shaking[i] = 0.45

    def path_points(self, i):
        """Sampled curve from node i to node i + 1."""
        (x1, y1), (x2, y2) = self.node_pos(i), self.node_pos(i + 1)
        pts = []
        if y1 == y2:                             # same row: a gentle wave
            cx, cy = (x1 + x2) / 2, y1 + (24 if i % 2 else -24)
            for k in range(25):
                u = k / 24
                pts.append(((1 - u) ** 2 * x1 + 2 * u * (1 - u) * cx + u * u * x2,
                            (1 - u) ** 2 * y1 + 2 * u * (1 - u) * cy + u * u * y2))
        else:                                    # row change: a U-turn at the side
            out = 95 if x1 > W / 2 else -95
            c1, c2 = (x1 + out, y1), (x2 + out, y2)
            for k in range(31):
                u = k / 30
                a, b, c, d = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
                pts.append((a * x1 + b * c1[0] + c * c2[0] + d * x2, a * y1 + b * c1[1] + c * c2[1] + d * y2))
        return pts

    def draw_levels(self):
        s, th = self.screen, self.theme
        mouse = pygame.mouse.get_pos()

        # --- header: title + star progress bar (drops in)
        hy = -30 * (1 - self.ent(0))
        self.otext(self.f_big, "Choose a level", (W // 2, 46 + hy), th.text, 3)
        total, most = sum(self.stars(i) for i in range(len(LEVELS))), 3 * len(LEVELS)
        bar = pygame.Rect(W // 2 - 150, 80 + hy, 300, 12)
        pygame.draw.rect(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), bar, border_radius=6)
        pygame.draw.rect(s, lerp_color(th.dim, th.panel_bg, 0.5), bar.inflate(4, 4), 1, border_radius=8)
        shown = (total / most) * self.ent(3, dur=0.9)
        if shown > 0.005:
            pygame.draw.rect(s, th.accent, (bar.x, bar.y, max(12, int(bar.w * shown)), bar.h), border_radius=6)
        self.draw_star(bar.right + 18, bar.centery, 10, True)
        img = self.f_mid.render(f"{total}/{most}", True, th.accent)
        s.blit(img, img.get_rect(midleft=(bar.right + 34, bar.centery)))

        # --- the path between nodes, drawn out dot by dot as the screen opens
        for i in range(len(LEVELS) - 1):
            done = self.stars(i) > 0
            pts = self.path_points(i)
            reveal = clamp01((self.scene_age - 0.1 - i * 0.06) / 0.25)
            dist, total_len = 0.0, sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                seg = math.hypot(xb - xa, yb - ya)
                dist += seg
                if dist > total_len * reveal:
                    break
                if int(dist / 13) != int((dist - seg) / 13):
                    if math.hypot(xb - self.node_pos(i)[0], yb - self.node_pos(i)[1]) < self.NODE_R + 6:
                        continue
                    if math.hypot(xb - self.node_pos(i + 1)[0], yb - self.node_pos(i + 1)[1]) < self.NODE_R + 6:
                        continue
                    if done:
                        # light travels along finished paths
                        k = 0.5 + 0.5 * math.sin(dist / 30 - self.t * 4)
                        pygame.draw.circle(s, lerp_color(th.accent, (255, 255, 255), 0.4 * k),
                                           (int(xb), int(yb)), 3 + round(k))
                    else:
                        pygame.draw.circle(s, lerp_color(th.dim, th.panel_bg, 0.5), (int(xb), int(yb)), 3)

        # --- nodes (pop in one after another along the path)
        current = self.first_unfinished()
        self.badge_tip = None
        for i, b in enumerate(self.level_buttons()):
            pop = self.ent(i, step=0.06, dur=0.45, delay=0.08, back=True)
            if pop <= 0.02:
                continue
            x, y = self.node_pos(i)
            sel = i == self.sel
            hov = b.rect.collidepoint(mouse)
            a = self.smooth(f"lvl{i}", 1.0 if sel else 0.5 if hov else 0.0)
            if i in self.shaking:                        # locked node wiggles "no"
                x += int(math.sin(self.shaking[i] * 50) * 7 * self.shaking[i] / 0.45)
            y -= int(6 * a)
            r = max(2, int(self.NODE_R * (1 + 0.15 * a) * pop))
            if sel:                                      # rotating dashed ring around the selection
                for k in range(12):
                    a0 = self.t * 1.5 + k * math.tau / 12
                    rr = pygame.Rect(0, 0, 2 * r + 26, 2 * r + 26)
                    rr.center = (x, y)
                    pygame.draw.arc(s, th.accent if b.enabled else th.dim, rr, a0, a0 + 0.3, 3)
            if b.enabled:
                if i == current and self.stars(i) == 0:  # the next level to play pulses
                    k = (self.t * 0.8) % 1
                    halo = pygame.Surface((200, 200), pygame.SRCALPHA)
                    pygame.draw.circle(halo, (*th.accent, int(140 * (1 - k))), (100, 100), int(r + 8 + 30 * k), 3)
                    s.blit(halo, (x - 100, y - 100))
                # the node is the theme's own element, showing the level number
                th.draw_element(s, self.f_elem, x, y, r, min(VMAX, i + 1), VMAX, self.t,
                                th.accent if self.stars(i) == 3 else None, phase=i)
                for k in range(3):                       # 3 small stars in an arc under the node
                    sx = x + (k - 1) * 20
                    sy = y + r + 14 + (0 if k == 1 else -4)
                    self.draw_star(sx, sy, 8, k < self.stars(i), pop)
            else:
                pygame.draw.circle(s, lerp_color(th.panel_bg, (0, 0, 0), 0.35), (x, y), r)
                pygame.draw.circle(s, lerp_color(th.dim, th.panel_bg, 0.5), (x, y), r, 2)
                if pop > 0.8:
                    self.draw_lock(x, y + 6)
            if pop < 0.9:
                continue
            lv = LEVELS[i]
            icons = [k for k, on in (("clock", lv.spawn), ("limit", lv.strict), ("eye", lv.hidden)) if on]
            for k, icon in enumerate(icons):             # rule badges in the corner of the node
                bx, by = x + r - 2 + k * 22, y - r + 4
                if math.hypot(mouse[0] - bx, mouse[1] - by) < 13 and not self.info_open:
                    tip = {"clock": f"arrival every {lv.spawn:g} s" if lv.spawn else "",
                           "limit": "no wrong swaps", "eye": "hidden numbers"}[icon]
                    self.badge_tip = (tip, bx, by)
                pygame.draw.circle(s, th.panel_bg, (bx, by), 11)
                pygame.draw.circle(s, th.dim, (bx, by), 11, 1)
                self.draw_icon(icon, bx, by, th.text if b.enabled else th.dim)
            name_col = lerp_color(th.dim, th.text, a) if b.enabled else lerp_color(th.dim, th.panel_bg, 0.3)
            self.otext(self.f_small, lv.name, (x, y + r + 36), name_col, 1)

        if self.badge_tip:                               # tooltip over a rule badge
            tip, bx, by = self.badge_tip
            img = self.f_tiny.render(tip.upper() + "  ·  F RULES", True, th.text)
            r = img.get_rect(midbottom=(bx, by - 16)).inflate(18, 10)
            r.clamp_ip(s.get_rect())
            self.card(r, 0.08, 240, r.h // 2, (*th.accent, 200))
            s.blit(img, img.get_rect(center=r.center))
        self.draw_level_card(int(170 * (1 - self.ent(4, dur=0.55))))
        hint = "arrows choose  ·  ENTER play  ·  F rules  ·  T theme  ·  ESC back"
        self.otext(self.f_small, hint, (W // 2, H - 16), th.dim, 1)
        p = self.smooth("info", 1.0 if self.info_open else 0.0, 12)
        if p > 0.02:
            ok = self.unlocked(self.sel)
            self.draw_info_card(LEVELS[self.sel], f"Level {self.sel + 1}  ·  rules",
                                ("ENTER play   ·   " if ok else "locked   ·   ") + "←→ other levels   ·   F / ESC close", p)

    def draw_level_card(self, oy=0):
        """Details of the selected level with a big PLAY button."""
        s, th = self.screen, self.theme
        lv, i, ok = LEVELS[self.sel], self.sel, self.unlocked(self.sel)
        box = pygame.Rect(90, 560 + oy, W - 180, 120)
        self.glow_rect(box, th.accent, 0.35, 16)
        self.card(box, 0.04, 235, 16, (*th.accent, 90))
        bc = (box.x + 60, box.centery)                   # big number badge
        pygame.draw.circle(s, th.accent if ok else th.dim, bc, 38)
        pygame.draw.circle(s, lerp_color(th.accent, (255, 255, 255), 0.4) if ok else th.dim, bc, 38, 3)
        img = self.f_big.render(str(i + 1), True, (25, 20, 15))
        s.blit(img, img.get_rect(center=bc))
        x = box.x + 120
        self.caps(f"Level {i + 1}  ·  tank of {lv.capacity}  ·  {lv.start} {th.nouns} to start",
                  x, box.y + 12, th.accent)
        self.text(lv.name, self.f_head, th.text, x, box.y + 26)
        self.text(self.wrap(lv.lesson, self.f_small, 470)[0], self.f_small, th.dim, x, box.y + 64)
        chips = [f"surface {lv.goal}", f"chain ×{lv.chain}"]
        chips.append(f"arrival every {lv.spawn:g}s" if lv.spawn else "no arrivals")
        if lv.strict:
            chips.append("no wrong swaps")
        if lv.hidden:
            chips.append("hidden numbers")
        best = self.save["best"].get(str(i))
        if best is not None:
            chips.append(f"best {best}")
        cx = x
        for c in chips:
            cx += self.chip(c, cx, box.y + 90, th.accent) + 6
        pr = self.play_button_rect().move(0, oy)          # PLAY button
        hov = pr.collidepoint(pygame.mouse.get_pos())
        a = self.smooth("playbtn", 1.0 if hov else 0.0)
        pr = pr.inflate(int(8 * a), int(6 * a))
        if ok:
            pulse = 0.5 + 0.5 * math.sin(self.t * 3)
            self.glow_rect(pr, th.accent, 0.6 + 0.4 * pulse * (1 - a) + a, 30)
            pygame.draw.rect(s, lerp_color(th.accent, (120, 70, 0), 0.4), pr.move(0, 4), border_radius=30)
            pygame.draw.rect(s, lerp_color(th.accent, (255, 255, 255), 0.25 * a), pr, border_radius=30)
            tx, ty = pr.x + 34, pr.centery
            pygame.draw.polygon(s, (25, 20, 15), [(tx - 7, ty - 10), (tx - 7, ty + 10), (tx + 10, ty)])
            img = self.f_mid.render("PLAY", True, (25, 20, 15))
            s.blit(img, img.get_rect(midleft=(tx + 18, ty)))
        else:
            pygame.draw.rect(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), pr, border_radius=30)
            pygame.draw.rect(s, th.dim, pr, 1, border_radius=30)
            self.draw_lock(pr.x + 32, pr.centery + 6)
            img = self.f_mid.render("Locked", True, th.dim)
            s.blit(img, img.get_rect(midleft=(pr.x + 54, pr.centery)))
        lr = self.rules_link_rect().move(0, oy)           # "F rules & stars" link
        a = self.smooth("ruleslink", 1.0 if lr.collidepoint(pygame.mouse.get_pos()) else 0.0)
        kw = self.keycap("F", lr.x + 10, lr.y)
        img = self.f_small.render("rules & stars", True, lerp_color(th.dim, th.accent, a))
        s.blit(img, img.get_rect(midleft=(lr.x + 16 + kw, lr.centery)))

    def draw_lock(self, cx, cy):
        c = self.theme.dim
        pygame.draw.arc(self.screen, c, (cx - 9, cy - 20, 18, 22), 0, math.pi, 3)
        pygame.draw.rect(self.screen, c, (cx - 12, cy - 9, 24, 18), border_radius=4)
        pygame.draw.circle(self.screen, lerp_color(c, (0, 0, 0), 0.6), (cx, cy - 1), 3)

    # -------------------------------------------------------- theme select
    def theme_buttons(self):
        w, h, gap = 270, 360, 30
        x0 = (W - 3 * w - 2 * gap) // 2
        return [Button((x0 + k * (w + gap), 150, w, h), th.title, lambda k=k: self.pick_theme(k))
                for k, th in enumerate(self.themes)]

    def pick_theme(self, k):
        center = self.theme_buttons()[k].rect.center
        self.begin_transition("circle", center)
        self.theme_idx = k
        self.apply_theme()
        write_save(self.save)
        self.go("menu", transition=False)

    def cycle_theme(self, center=None):
        self.begin_transition("circle", center)
        self.theme_idx = (self.theme_idx + 1) % len(self.themes)
        self.apply_theme()
        write_save(self.save)

    def handle_themes(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.go("menu")
            return
        self.menu_input(e, self.theme_buttons(), cols=3)

    def draw_themes(self):
        s = self.screen
        self.otext(self.f_big, "Choose a theme", (W // 2, 80 - 30 * (1 - self.ent(0))), self.theme.accent, 3)
        for k, b in enumerate(self.theme_buttons()):
            th, sel = self.themes[k], k == self.sel
            fs = self.fontsets[th.key]
            a = self.smooth(f"theme{k}", 1.0 if sel else 0.0)
            b.rect = b.rect.move(0, int(-10 * a + 140 * (1 - self.ent(k + 1, step=0.08))))
            self.glow_rect(b.rect, th.accent, a, 6)
            # each card is a little window into its own theme
            card = pygame.Surface(b.rect.size)
            card.blit(th.bg, (0, 0), pygame.Rect(COL_X - b.rect.w // 2, H - b.rect.h, *b.rect.size))
            s.blit(card, b.rect)
            for v, yy in ((4, 300), (8, 230)):
                fy = math.sin(self.t * 2 + v) * 6 * (0.3 + a)
                th.draw_element(s, fs["elem"], b.rect.centerx, b.rect.y + yy + fy,
                                int((14 + v * 3) * (1 + 0.1 * a)), v, VMAX, self.t,
                                th.accent if v == 8 else None, phase=v)
            pygame.draw.rect(s, lerp_color(th.dim, th.accent, a), b.rect, 1 + round(3 * a), border_radius=6)
            # the title is written in the theme's own font
            self.otext(fs["head"], th.title, (b.rect.centerx, b.rect.y + 34), th.accent, 2)
            for n, line in enumerate(self.wrap(th.tagline, fs["small"], b.rect.w - 30)):
                self.otext(fs["small"], line, (b.rect.centerx, b.rect.y + 72 + n * 20), th.text, 1)
            if k == self.theme_idx:
                self.otext(fs["small"], "current", (b.rect.centerx, b.rect.bottom - 20), th.accent, 1)
        self.otext(self.f_small, "←→ choose   ENTER apply   ESC back", (W // 2, H - 40), self.theme.dim, 1)

    # ------------------------------------------------------------- playing
    def start_level(self, idx):
        if idx == "endless":
            if not self.endless_unlocked():
                return
            self.level_idx, self.level = -1, ENDLESS
        else:
            if not self.unlocked(idx):
                return
            self.level_idx = self.level_sel = idx
            self.level = LEVELS[idx]
        self.start_values = make_values(self.level)
        self.seed = random.randrange(1 << 30)
        self.go("play")
        self.reset()
        first = (self.save.get("endless", 0) == 0) if self.endless else self.stars(self.level_idx) == 0
        if first:                          # the first try starts with the rules card
            self.paused = "brief"

    @property
    def endless(self):
        return self.level.goal is None

    def pause(self, kind="pause"):
        if self.scene == "play" and not self.result and not self.paused and not self.demo_finale:
            self.paused = kind

    def reset(self):
        lv = self.level
        self.paused = None
        self.board = Board(self.start_values, lv.capacity)
        self.feed = Feed(lv, random.Random(self.seed))   # the same arrivals after a restart
        self.queue = []
        for _ in range(3):
            self.queue.append(self.feed.next(self.start_values + self.queue))
        self.spawn_every = lv.spawn
        self.spawn_t = (lv.spawn + 2.0) if lv.spawn else None   # a little extra time to look first
        self.cursor = 0
        self.swaps = 0
        self.wrong = 0
        self.surfaced = 0
        self.score = 0
        self.shown_score = 0.0
        self.chain = 0
        self.chain_t = 0.0
        self.best_chain = 0
        self.ready_t = 0.0
        self.result = None            # None | "won" | "failed" | "demo"
        self.fail_reason = ""
        self.new_record = False
        self.earned = 0
        self.demo = None
        self.demo_step = None
        self.demo_timer = 0.0
        self.demo_paused = False
        self.demo_swapped = False
        self.demo_finale = False
        self.demo_sorted = None
        self.shake = 0.0
        # animation state of the play screen
        self.rising = []              # elements on their way out of the tank
        self.rings = []               # shock-wave rings where they popped
        self.popups = []              # floating "+120" texts
        self.banner = None            # ["CHAIN x3", age]
        self.code_flash = None        # [line, colour, age]
        self.cur_f = 0.0              # smoothed pointer position (pair index)
        self.sel_color = self.theme.accent
        self.hover_pair = None        # pair under the mouse
        self.hover_shown = 0          # last hovered pair, kept while it fades out
        self.hover_a = 0.0
        self.swap_pop = 0.0           # tiles bounce when they change
        self.score_pop = 0.0
        self.msg_age = 0.0
        self.shown_msg = ""
        self.hl_y = None              # smoothed pseudocode highlight
        self.result_age = 0.0
        self.ring_from = self.board.n
        th = self.theme
        if lv.spawn:
            self.message = f"Bring the biggest {th.noun} to the top. Newcomers arrive from below!"
        else:
            self.message = f"The biggest {th.noun} on top surfaces. Empty the tank!"
        self.msg_kind = "info"

    # --- the rules
    def surface_ready(self):
        b = self.board
        if b.n == 0 or b.busy or not b.settled(b.n - 1):
            return False
        return b.items[-1].value >= max(b.values())

    def surface(self):
        """The top element is the biggest: it leaves the tank."""
        b, th = self.board, self.theme
        e = b.items.pop()
        x, y = b.x_of(e, self.t), e.y
        self.rising.append({"e": e, "x": x, "y0": y, "age": 0.0, "r": b.radius(e.value)})
        self.ready_t = 0.0
        self.cursor = max(0, min(self.cursor, b.n - 2))
        if self.demo_finale:
            if b.n == 0:
                self.result, self.result_age = "demo", -0.4
            return
        self.chain += 1
        self.chain_t = 1.1
        self.best_chain = max(self.best_chain, self.chain)
        pts = 10 * e.value * self.chain
        self.score += pts
        self.score_pop = 1.0
        self.surfaced += 1
        txt = f"+{pts}" if self.chain < 2 else f"+{pts}  ×{self.chain}"
        self.popups.append({"txt": txt, "x": x + 70, "y": SURFACE_Y + 20, "age": 0.0, "col": th.accent})
        if self.chain >= 2:
            self.banner = [f"CHAIN ×{self.chain}", 0.0]
            self.message = (f"Chain ×{self.chain}! The top was already sorted, "
                            "so it surfaces in one go.")
            self.msg_kind = "good"
        elif not self.result:
            self.message = f"{th.noun.capitalize()} {e.value} was the biggest: it surfaced!"
            self.msg_kind = "good"
        if self.level.goal and self.surfaced >= self.level.goal and not self.result:
            self.win()
        elif b.n == 0 and not self.level.spawn and not self.result:
            self.win()

    def arrive(self, early=False):
        """The next element enters at the bottom of the tank."""
        b, th = self.board, self.theme
        if b.n >= b.cap:
            self.fail("The tank overflowed!")
            return
        v = self.queue.pop(0)
        self.queue.append(self.feed.next(b.values() + self.queue + [v]))
        b.arrive(v)
        if b.n > 2:
            self.cursor = min(self.cursor + 1, b.n - 2)
        self.spawn_every = max(self.level.min_spawn, self.spawn_every * self.level.speedup)
        if early:
            bonus = int(self.spawn_t * 4) + 5
            self.score += bonus
            self.score_pop = 1.0
            self.popups.append({"txt": f"+{bonus} early", "x": 90, "y": BOTTOM - 40, "age": 0.0,
                                "col": th.good})
        self.spawn_t = self.spawn_every
        th.burst(COL_X, b.bottom + 20, 10)
        if b.n == b.cap:
            self.message = "The tank is full! Surface something before the next one arrives."
            self.msg_kind = "bad"

    def call_next(self):
        if self.level.spawn and not self.result and not self.demo and not self.demo_finale:
            self.arrive(early=True)

    def player_swap(self):
        b = self.board
        if self.result or self.demo or self.demo_finale or b.n < 2:
            return
        j = self.cursor
        a, c = b.items[j].value, b.items[j + 1].value
        b.swap(j)
        self.swaps += 1
        self.swap_pop = 1.0
        self.ready_t = 0.0
        th = self.theme
        y = (b.slot_y(j) + b.slot_y(j + 1)) / 2
        if a > c:
            self.message = f"{a} > {c}: swap! {a} {th.rise_verb}."
            if self.level.hidden:
                self.message = f"Good swap: the bigger one {th.rise_verb}."
            self.msg_kind = "good"
            self.code_flash = [4, th.good, 0.0]
            th.burst(COL_X, y)
            return
        self.wrong += 1
        self.shake = 0.35
        self.code_flash = [3, th.bad, 0.0]
        if a == c:
            self.message = f"{a} = {c}: Bubble Sort never swaps equal values. That keeps it stable!"
        elif self.level.hidden:
            self.message = "Wrong swap: the smaller one went up."
        else:
            self.message = f"{a} < {c}: that swap breaks the order!"
        self.msg_kind = "bad"
        if self.level.strict:
            self.fail("A wrong swap cracked the tank!")

    def win(self):
        self.result = "won"
        self.result_age = -0.5              # let the last element surface first
        lv = self.level
        self.earned = 1 + (self.best_chain >= lv.chain) + (self.wrong == 0)
        key = str(self.level_idx)
        if self.earned > self.stars(self.level_idx):
            self.save["stars"][key] = self.earned
        best = self.save["best"].get(key)
        if best is None or self.score > best:
            self.save["best"][key] = self.score
            self.new_record = best is not None
        write_save(self.save)
        self.board.pop_wave()
        for i in range(self.board.n):
            self.theme.burst(COL_X, self.board.slot_y(i), 10)

    def fail(self, reason):
        self.result = "failed"
        self.result_age = 0.0
        self.fail_reason = reason
        self.shake = 0.6
        if self.endless:
            best = self.save.get("endless", 0)
            self.new_record = self.score > best
            if self.new_record:
                self.save["endless"] = self.score
                write_save(self.save)
        for e in self.board.items:
            self.theme.burst(COL_X, e.y, 4)

    # --- demo
    def toggle_demo(self):
        was = self.demo or self.demo_finale
        self.reset()
        if was:
            return
        self.demo = bubble_sort_steps(self.start_values)
        self.spawn_t = None
        self.message = "DEMO: watch how the algorithm does it."
        self.msg_kind = "info"

    def demo_advance(self):
        kind, j, i = self.demo_step = next(self.demo)
        b = self.board
        v = b.values()
        if kind == "compare":
            if j == 0:
                self.demo_swapped = False
            self.cursor = j
            self.message = f"Pass {i + 1}: comparing {v[j]} and {v[j + 1]}"
            self.msg_kind = "info"
        elif kind == "swap":
            b.swap(j)
            self.swaps += 1
            self.swap_pop = 1.0
            self.demo_swapped = True
            self.theme.burst(COL_X, b.slot_y(j + 1), 8)
            self.message = f"{v[j]} > {v[j + 1]} → swap! The bigger one {self.theme.rise_verb}."
            self.msg_kind = "swap"
        elif kind == "keep":
            same = " (equal: no swap, stays stable)" if v[j] == v[j + 1] else ""
            self.message = f"{v[j]} ≤ {v[j + 1]} → leave them, the order is fine{same}."
            self.msg_kind = "good"
        elif kind == "pass_end":
            self.demo_sorted = j
            b.items[j].pop = 1.0
            self.message = f"End of pass {i + 1}: {self.theme.noun} {v[j]} is now in its final place."
            self.msg_kind = "good"
        elif kind == "early":
            self.demo_sorted = 0
            self.message = "A whole pass with no swaps → everything is sorted, stop early!"
            self.msg_kind = "good"
        elif kind == "done":
            self.demo = None
            self.demo_finale = True
            self.message = "Sorted! Now the whole tank surfaces in one chain."
            self.msg_kind = "good"

    # --- input
    def next_rect(self):
        return pygame.Rect(18, BOTTOM - 196, 100, 262)

    def handle_play(self, e):
        if self.paused:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.go("menu" if self.endless else "levels")
                elif e.key == pygame.K_t:
                    self.cycle_theme((COL_X, H // 2))
                elif e.key == pygame.K_r:
                    self.reset()
                elif e.key in (pygame.K_p, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.paused = None
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.paused = None
            return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_p:
            self.pause("pause")
            return
        if e.type == pygame.KEYDOWN:
            self.on_key(e.key)
        elif e.type == pygame.MOUSEWHEEL and not self.demo and not self.result and self.board.n >= 2:
            self.cursor = max(0, min(self.board.n - 2, self.cursor + e.y))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.demo and not self.result:
            if self.level.spawn and self.next_rect().collidepoint(e.pos):
                self.call_next()
                return
            j = self.board.pair_at(e.pos)
            if j is None:
                return
            if j == self.cursor:
                self.player_swap()       # click the selected pair = swap it
            else:
                self.cursor = j          # click another pair = select it

    def on_key(self, k):
        n = self.board.n
        if k == pygame.K_ESCAPE:
            self.go("menu" if self.endless else "levels")
        elif k == pygame.K_t:
            self.cycle_theme((COL_X, H // 2))
        elif k == pygame.K_r:
            self.begin_transition("fade", dur=0.25)
            self.reset()
        elif k == pygame.K_d:
            self.toggle_demo()
        elif k == pygame.K_n and not self.endless:
            nxt = self.level_idx + 1
            if nxt < len(LEVELS) and self.unlocked(nxt):
                self.start_level(nxt)
            elif nxt >= len(LEVELS):
                self.message = "That was the last level. Try the Endless tide!"
            else:
                self.message = "Solve this level first to unlock the next one."
        elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.demo_delay = max(0.1, round(self.demo_delay - 0.1, 1))
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.demo_delay = min(2.0, round(self.demo_delay + 0.1, 1))
        elif self.demo:
            if k == pygame.K_SPACE:
                self.demo_paused = not self.demo_paused
            elif k == pygame.K_RIGHT and self.demo_paused:
                self.demo_advance()
        elif self.result or self.demo_finale:
            return
        elif k == pygame.K_f:
            self.call_next()
        elif n < 2:
            return
        elif k == pygame.K_UP:
            self.cursor = min(self.cursor + 1, n - 2)
        elif k == pygame.K_DOWN:
            self.cursor = max(self.cursor - 1, 0)
        elif k == pygame.K_SPACE:
            self.player_swap()

    # --- update
    def update_play(self, dt):
        b, th = self.board, self.theme
        if self.paused:                    # time stands still, only settle the animations
            b.update(dt)
            self.set_hand(False)
            self.hover_a = approach(self.hover_a, 0.0, dt, 16)
            return
        # which pair is under the mouse?
        interactive = (not self.demo and not self.result and not self.demo_finale
                       and pygame.mouse.get_focused())
        self.hover_pair = b.pair_at(pygame.mouse.get_pos()) if interactive else None
        over_next = interactive and self.level.spawn and self.next_rect().collidepoint(pygame.mouse.get_pos())
        self.set_hand(self.hover_pair is not None or bool(over_next))
        if self.hover_pair is not None and self.hover_pair != self.cursor:
            self.hover_shown = self.hover_pair
        show = self.hover_pair is not None and self.hover_pair != self.cursor
        self.hover_a = approach(self.hover_a, 1.0 if show else 0.0, dt, 16)
        for i, e in enumerate(b.items):
            e.hover = show and i in (self.hover_pair, self.hover_pair + 1)
        # smooth pointer movement and colour
        self.cursor = max(0, min(self.cursor, b.n - 2))
        self.cur_f = approach(self.cur_f, self.cursor, dt, 16)
        step = self.demo_step[0] if (self.demo and self.demo_step) else None
        target = {"swap": th.bad, "keep": th.good}.get(step, th.accent)
        if self.shake > 0 and not self.demo:
            target = th.bad
        self.sel_color = tuple(approach(c, tc, dt, 12) for c, tc in zip(self.sel_color, target))
        self.swap_pop = max(0.0, self.swap_pop - dt * 3)
        self.score_pop = max(0.0, self.score_pop - dt * 2.5)
        self.shown_score = approach(self.shown_score, self.score, dt, 8)
        self.msg_age += dt
        self.result_age += dt
        self.shake = max(0.0, self.shake - dt)
        b.update(dt)

        # which elements would surface in one chain? (gold rings)
        self.ring_from = self.demo_sorted if self.demo_sorted is not None and not self.demo_finale \
            else chain_start(b.values())

        # surfacing: the top element leaves when it is the biggest
        playing = not self.result and not self.demo
        if playing or self.demo_finale:
            if self.surface_ready():
                self.ready_t += dt
                if self.ready_t >= (0.22 if self.chain_t > 0 or self.demo_finale else 0.4):
                    self.surface()
            else:
                self.ready_t = 0.0
        if self.chain_t > 0:
            self.chain_t -= dt
            if self.chain_t <= 0:
                self.chain = 0

        # arrivals
        if playing and self.spawn_t is not None and not self.demo_finale:
            self.spawn_t -= dt
            if self.spawn_t <= 0:
                self.arrive()

        if self.demo and not self.demo_paused:
            self.demo_timer += dt
            if self.demo_timer >= self.demo_delay:
                self.demo_timer = 0
                self.demo_advance()

        # effects
        for r in self.rising:
            r["age"] += dt
            if r["age"] >= 0.42 and not r.get("popped"):
                r["popped"] = True
                th.burst(r["x"], SURFACE_Y, 18)
                self.rings.append([r["x"], SURFACE_Y, 0.0])
        self.rising = [r for r in self.rising if not r.get("popped")]
        for ring in self.rings:
            ring[2] += dt
        self.rings = [r for r in self.rings if r[2] < 0.5]
        for p in self.popups:
            p["age"] += dt
        self.popups = [p for p in self.popups if p["age"] < 1.1]
        if self.banner:
            self.banner[1] += dt
            if self.banner[1] > 1.3:
                self.banner = None
        if self.code_flash:
            self.code_flash[2] += dt
            if self.code_flash[2] > 0.9:
                self.code_flash = None

    # --- drawing
    def pair_rect(self, board, jf, dx=0, grow=0):
        """Rounded box around pair jf (float, so it can glide between pairs)."""
        y1, y2 = board.slot_y(jf), board.slot_y(jf + 1)
        pad = min(40, (y1 - y2) * 0.55) + grow
        return pygame.Rect(board.col_x - 78 + dx - grow, y2 - pad, 156 + 2 * grow, y1 - y2 + 2 * pad)

    def draw_selector(self, board, jf, color, alpha=1.0, dx=0):
        """The selected pair: glowing, breathing capsule with arrows that point at it."""
        s, t = self.screen, self.t
        breathe = 0.5 + 0.5 * math.sin(t * 4)
        box = self.pair_rect(board, jf, dx, int(2 * breathe))
        self.glow_rect(box, color, alpha * (0.7 + 0.5 * breathe), 30, 5)
        fill = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(fill, (*color, int(alpha * (30 + 25 * breathe))), fill.get_rect(), border_radius=30)
        pygame.draw.rect(fill, (255, 255, 255, int(alpha * 40)), (18, 6, box.w - 36, 4), border_radius=2)
        s.blit(fill, box)
        edge = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(edge, (*color, int(255 * alpha)), edge.get_rect(), 3, border_radius=30)
        s.blit(edge, box)
        cy, bob = box.centery, 5 * math.sin(t * 6)          # chevrons bobbing towards the pair
        for side in (-1, 1):
            x = box.centerx + side * (box.w / 2 + 18 + bob)
            pts = [(x + side * 9, cy - 11), (x - side * 5, cy), (x + side * 9, cy + 11)]
            pygame.draw.polygon(s, lerp_color((20, 20, 30), color, alpha), pts)
        ix = box.right + 44 + dx                              # little swap icon
        for k, d in ((-1, -1), (1, 1)):
            ax = ix + k * 6
            ay = cy - d * 9 + d * 2 * math.sin(t * 6)
            pygame.draw.line(s, color, (ax, cy - 10), (ax, cy + 10), 2)
            pygame.draw.polygon(s, color, [(ax - 5, ay), (ax + 5, ay), (ax, ay - d * 7)])

    def draw_hover(self, board, j, alpha, t, dx=0):
        """The pair under the mouse: soft halos and thin rings around its two
        elements only, so it never covers the selected (gold) capsule."""
        th = self.theme
        if j >= board.n - 1:
            return
        for i in (j, j + 1):
            if i == self.cursor or i == self.cursor + 1:
                continue
            e = board.items[i]
            x, y = board.x_of(e, t) + dx, e.y
            r = int(board.radius(e.value) * e.scale) + 8
            halo = pygame.Surface((r * 2 + 24, r * 2 + 24), pygame.SRCALPHA)
            c = r + 12
            for k in range(4):
                pygame.draw.circle(halo, (*th.text, int(alpha * 14 * (k + 1))), (c, c), r + 10 - k * 3)
            pygame.draw.circle(halo, (*th.text, int(alpha * 200)), (c, c), r, 2)
            self.screen.blit(halo, (x - c, y - c))
        cy = (board.slot_y(j) + board.slot_y(j + 1)) / 2
        img = self.f_tiny.render("SELECT", True, th.text)
        tag = pygame.Rect(0, 0, img.get_width() + 16, img.get_height() + 8)
        tag.midright = (board.col_x - 116 + dx, cy)
        surf = pygame.Surface(tag.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (*th.panel_bg, int(220 * alpha)), surf.get_rect(), border_radius=tag.h // 2)
        pygame.draw.rect(surf, (*th.text, int(150 * alpha)), surf.get_rect(), 1, border_radius=tag.h // 2)
        img.set_alpha(int(255 * alpha))
        surf.blit(img, img.get_rect(center=surf.get_rect().center))
        self.screen.blit(surf, tag)
        if alpha > 0.5:
            pygame.draw.polygon(self.screen, th.text,
                                [(tag.right + 3, cy - 5), (tag.right + 9, cy), (tag.right + 3, cy + 5)])

    def draw_tank_marks(self, rect, dx):
        """Slot lights on the side of the tank and the surface line on top."""
        s, th, b = self.screen, self.theme, self.board
        full = b.n >= b.cap and not self.result
        danger = full and self.spawn_t is not None and not self.demo
        pulse = 0.5 + 0.5 * math.sin(self.t * 10)
        if danger:
            self.glow_rect(rect, th.bad, 0.6 + 0.6 * pulse, 14, 5)
        for i in range(b.cap):
            y = int(b.slot_y(i))
            on = i < b.n
            col = (th.bad if danger else th.accent) if on else lerp_color(th.dim, th.panel_bg, 0.55)
            k = self.smooth(f"slot{i}", 1.0 if on else 0.0, 10)
            r = 3 + round(2 * k)
            pygame.draw.circle(s, lerp_color(th.panel_bg, col, 0.4 + 0.6 * k), (rect.x + 14, y), r)
        # surface line: dashed, slowly flowing
        y = SURFACE_Y + 18
        off = (self.t * 30) % 16
        x = rect.x + 10 - off
        while x < rect.right - 10:
            x0, x1 = max(rect.x + 10, x), min(rect.right - 10, x + 8)
            if x1 > x0:
                pygame.draw.line(s, lerp_color(th.dim, th.accent, 0.3), (x0, y), (x1, y), 2)
            x += 16

    def draw_next(self):
        """The queue of arriving elements, with a timer ring around the first one."""
        s, th, b = self.screen, self.theme, self.board
        r0 = self.next_rect()
        e_in = self.ent(2, dur=0.5)
        r0 = r0.move(int(-140 * (1 - e_in)), 0)
        hov = r0.collidepoint(pygame.mouse.get_pos()) and not self.result and not self.demo
        a = self.smooth("nexthov", 1.0 if hov else 0.0)
        full = b.n >= b.cap and not self.result
        border = th.bad if full else lerp_color(th.dim, th.accent, a)
        self.glow_rect(r0, border, 0.3 + 0.5 * a, 16)
        self.card(r0, 0.04, 210, 16, (*border, 160))
        self.caps("next", r0.centerx, r0.y + 10, th.accent, "midtop")
        frac = 0.0 if self.spawn_t is None else 1 - self.spawn_t / max(0.1, self.spawn_every)
        frac = clamp01(frac)
        ys = (r0.bottom - 58, r0.bottom - 128, r0.bottom - 186)
        for k in range(2, -1, -1):
            v = self.queue[k]
            rr = int(b.radius(v) * (0.7 if k == 0 else 0.55))
            y = ys[k]
            if k == 0 and frac > 0.8 and not self.result and self.spawn_t is not None:
                y += math.sin(self.t * 40) * 2 * (frac - 0.8) * 5         # jitters before it drops in
            th.draw_element(s, self.f_elem if k == 0 else self.f_small, r0.centerx, y, rr, v, VMAX,
                            self.t, None, "", k, self.level.hidden)
        # timer ring around the first one
        cx, cy, R = r0.centerx, ys[0], 34
        pygame.draw.circle(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), (cx, cy), R, 4)
        if frac > 0:
            col = th.bad if full or frac > 0.8 else th.accent
            pygame.draw.arc(s, col, (cx - R, cy - R, 2 * R, 2 * R),
                            math.pi / 2 - math.tau * frac, math.pi / 2, 4)
        # "F early" hint
        kx = r0.centerx - 34
        kw = self.keycap("F", kx, r0.bottom - 26)
        img = self.f_tiny.render("NOW +", True, th.dim)
        s.blit(img, (kx + kw + 6, r0.bottom - 22))

    def draw_play(self):
        s, th = self.screen, self.theme
        dx = int(math.sin(self.t * 60) * 8 * self.shake)
        rect = pygame.Rect(COL_X - 110 + dx, TOP - 80, 220, BOTTOM - TOP + 140)
        th.draw_container(s, rect, self.t)
        self.otext(self.f_small, th.up_label, (COL_X, TOP - 95), th.dim, 1)
        self.draw_tank_marks(rect, dx)

        step = self.demo_step[0] if (self.demo and self.demo_step) else None
        show_sel = (not self.result and not self.demo_finale and self.board.n >= 2
                    and (not self.demo or step in ("compare", "swap", "keep")))
        sel_a = self.smooth("sel_a", 1.0 if show_sel else 0.0, 10)
        if sel_a > 0.02:
            self.draw_selector(self.board, self.cur_f, self.sel_color, sel_a, dx)
            if self.hover_pair == self.cursor:
                box = self.pair_rect(self.board, self.cur_f, dx)
                img = self.f_tiny.render("SWAP", True, (25, 20, 15))
                tag = pygame.Rect(0, 0, img.get_width() + 16, img.get_height() + 8)
                tag.midright = (self.board.col_x - 116 + dx, box.centery)
                pygame.draw.rect(s, self.sel_color, tag, border_radius=tag.h // 2)
                cy = tag.centery
                pygame.draw.polygon(s, self.sel_color, [(tag.right + 3, cy - 5), (tag.right + 9, cy), (tag.right + 3, cy + 5)])
                s.blit(img, img.get_rect(center=tag.center))
        if self.hover_a > 0.02:
            self.draw_hover(self.board, self.hover_shown, self.hover_a, self.t, dx)
        # the top element glows while it is about to surface
        b = self.board
        if b.n and self.ready_t > 0:
            e = b.items[-1]
            k = clamp01(self.ready_t / 0.4)
            R = int(b.radius(e.value) * 1.6)
            halo = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
            pygame.draw.circle(halo, (*th.accent, int(90 * k)), (R, R), R)
            s.blit(halo, (b.x_of(e, self.t) + dx - R, e.y - R))
        b.draw(s, th, self.f_elem, self.t, self.ring_from,
               self.level.hidden and self.result is None, dx, labels=self.level.feed == "dupes")
        for r in self.rising:                      # elements on their way out
            p = clamp01(r["age"] / 0.42)
            y = r["y0"] + (SURFACE_Y - r["y0"]) * ease_in_out(p)
            rr = int(r["r"] * (1 + 0.25 * p))
            e = r["e"]
            th.draw_element(s, self.f_elem, r["x"] + dx, y, rr, e.value, VMAX, self.t,
                            th.accent, "", e.phase, self.level.hidden and not self.result)
        for x, y, age in self.rings:               # pop shock waves
            k = age / 0.5
            surf = pygame.Surface((200, 200), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*th.accent, int(220 * (1 - k))), (100, 100), int(20 + 70 * ease_out_cubic(k)), 3)
            s.blit(surf, (x - 100, y - 100))
        for p in self.popups:                      # floating score texts
            k = p["age"] / 1.1
            self.otext(self.f_mid, p["txt"], (p["x"], p["y"] - 46 * ease_out_cubic(k)), p["col"], 2,
                       255 * (1 - k ** 3))
        if self.banner:                            # CHAIN xN
            txt, age = self.banner
            sc = ease_out_back(clamp01(age / 0.3))
            alpha = 255 * clamp01((1.3 - age) / 0.35)
            self.otext(self.f_big, txt, (COL_X, TOP + 30), th.accent, 3, alpha, max(0.05, sc))
        if self.level.spawn:
            self.draw_next()
        self.draw_panel()
        if self.result:
            self.draw_result()
        p = self.smooth("pause", 1.0 if self.paused else 0.0, 12)
        if p > 0.02:
            head = "Endless tide" if self.endless else f"Level {self.level_idx + 1}"
            if self.paused == "brief" or (not self.paused and self.ui.get("was_brief")):
                self.ui["was_brief"] = self.paused == "brief" or p > 0.05
                self.draw_info_card(self.level, f"{head}  ·  before you start",
                                    "SPACE / click start   ·   ESC back", p)
            else:
                self.draw_info_card(self.level, f"{head}  ·  paused",
                                    "P / SPACE resume   ·   R restart   ·   ESC back", p)
        else:
            self.ui["was_brief"] = False

    def draw_panel(self):
        """Right side: header, stat tiles, goals, message, pseudocode, controls."""
        s, th, lv = self.screen, self.theme, self.level
        e_in = self.ent(0, dur=0.55)
        ox = int(340 * (1 - e_in))
        px, pw = PANEL_X + ox, W - PANEL_X - 20
        self.panel(pygame.Rect(px, 20, pw, H - 40), 200)
        x, inner = px + 20, pw - 40

        # --- header
        head = "Endless tide" if self.endless else f"Level {self.level_idx + 1}"
        self.caps(f"{head}  ·  tank of {lv.capacity}", x, 34, th.accent)
        if self.demo or self.demo_finale or self.result == "demo":
            label = "demo paused" if self.demo_paused else f"demo · {self.demo_delay:.1f}s"
            img = self.f_tiny.render(label.upper(), True, th.text)
            self.chip(label, x + inner - img.get_width() - 18, 30, th.accent, filled=True)
        self.text(lv.name, self.f_head, th.text, x, 50)
        y = 90
        for line in self.wrap(lv.lesson, self.f_small, inner)[:2]:
            y = self.text(line, self.f_small, th.dim, x, y) - 2
        off = max(0, y + 6 - 132)

        # --- stat tiles (stagger in)
        goal_txt = f"{self.surfaced}/{lv.goal}" if lv.goal else str(self.surfaced)
        tiles = [("score", str(int(round(self.shown_score))), self.score_pop),
                 ("surfaced", goal_txt, 0.0),
                 ("inversions", str(inversions(self.board.values())), self.swap_pop),
                 ("chain", f"×{max(self.chain, 1)}" if self.chain else "-", 0.0)]
        gap, ty = 10, 132 + off
        tw = (inner - gap * (len(tiles) - 1)) / len(tiles)
        for k, (name, value, pop) in enumerate(tiles):
            tin = self.ent(k + 1, step=0.05)
            r = pygame.Rect(int(x + k * (tw + gap)), ty + int(30 * (1 - tin)), int(tw), 68)
            border = th.accent if pop > 0 else None
            self.card(r, 0.07, 220, 12, (*border, int(200 * pop)) if border else None)
            self.caps(name, r.x + 12, r.y + 9, th.dim)
            col = lerp_color(th.text, th.accent, pop)
            if name == "chain" and self.chain >= 2:
                col = th.accent
            scale = 1.0 + math.sin(math.pi * pop) * 0.2
            self.text(value, self.f_value, col, r.x + 12, r.y + 26, scale=scale)
            if name == "surfaced" and lv.goal:              # progress bar
                frac = self.smooth("goalbar", min(1.0, self.surfaced / lv.goal), 8)
                pygame.draw.rect(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), (r.x + 10, r.bottom - 7, r.w - 20, 3))
                pygame.draw.rect(s, th.good, (r.x + 10, r.bottom - 7, int((r.w - 20) * frac), 3))

        # --- the three star goals
        gy = 210 + off
        gw = (inner - 2 * 8) / 3
        if self.endless:
            goals = [(f"best {self.save.get('endless', 0)}", self.score > self.save.get("endless", 0), False),
                     (f"best chain ×{self.best_chain}", self.best_chain >= 3, False),
                     ("clean" if self.wrong == 0 else f"{self.wrong} wrong", self.wrong == 0, self.wrong > 0)]
        else:
            goals = [(f"surface {lv.goal}", self.surfaced >= lv.goal, False),
                     (f"chain ×{lv.chain}", self.best_chain >= lv.chain, False),
                     ("no wrong swaps" if self.wrong == 0 else f"{self.wrong} wrong swap{'s' * (self.wrong > 1)}",
                      self.wrong == 0, self.wrong > 0)]
        for k, (label, ok, broken) in enumerate(goals):
            r = pygame.Rect(int(x + k * (gw + 8)), gy, int(gw), 30)
            lit = self.smooth(f"goal{k}", 1.0 if ok else 0.0, 8)
            col = th.bad if broken else lerp_color(th.dim, th.accent, lit)
            self.card(r, 0.04, 200, 15, (*col, 120 + int(100 * lit)))
            self.draw_star(r.x + 17, r.centery, 8, ok, 1 + 0.25 * lit * (0.5 + 0.5 * math.sin(self.t * 5)))
            if broken:
                pygame.draw.line(s, th.bad, (r.x + 9, r.centery + 7), (r.x + 25, r.centery - 7), 2)
            img = self.f_tiny.render(label.upper(), True, th.bad if broken else lerp_color(th.dim, th.text, lit))
            s.blit(img, img.get_rect(midleft=(r.x + 31, r.centery)))

        # --- message card (slides in when it changes)
        if self.message != self.shown_msg:
            self.shown_msg, self.msg_age = self.message, 0.0
        k = ease_in_out(min(1.0, self.msg_age / 0.25))
        kind_col = {"good": th.good, "bad": th.bad, "swap": th.bad}.get(self.msg_kind, th.accent)
        mr = pygame.Rect(x, 252 + off, inner, 58)
        self.card(mr, 0.04, 220, 12)
        pygame.draw.rect(s, kind_col, (mr.x, mr.y, 5, mr.h), border_top_left_radius=12, border_bottom_left_radius=12)
        lines = self.wrap(self.message, self.f_small, inner - 40)[:2]
        my = mr.centery - len(lines) * 10
        for line in lines:
            my = self.text(line, self.f_small, th.text, mr.x + 18 + int(10 * (1 - k)), my, 255 * k) - 4

        # --- pseudocode card
        cr = pygame.Rect(x, 320 + off, inner, 184)
        self.card(cr, -0.35, 200, 12)
        self.caps("bubble sort", cr.x + 14, cr.y + 10, th.dim)
        if self.demo and self.demo_step:
            _, jj, ii = self.demo_step
            img = self.f_code.render(f"i={ii}  j={jj}  swapped={self.demo_swapped}", True, th.accent)
            s.blit(img, img.get_rect(topright=(cr.right - 14, cr.y + 7)))
        else:
            img = self.f_tiny.render("BEST O(N) · WORST O(N²) · STABLE", True, lerp_color(th.dim, th.panel_bg, 0.3))
            s.blit(img, img.get_rect(topright=(cr.right - 14, cr.y + 10)))
        line_h, y0 = 20, cr.y + 32
        active = STEP_LINE.get(self.demo_step[0], -1) if (self.demo and self.demo_step) else -1
        hl_col = th.code_hl
        if active < 0 and self.code_flash:          # your own swap lights up its line
            active, fc, age = self.code_flash
            hl_col = lerp_color(th.panel_bg, fc, 0.45 * (1 - age / 0.9))
        if active >= 0:                            # highlight glides between lines
            target = y0 + active * line_h
            self.hl_y = target if self.hl_y is None else approach(self.hl_y, target, self.dt, 18)
            pygame.draw.rect(s, hl_col, (cr.x + 8, self.hl_y - 2, cr.w - 16, line_h), border_radius=5)
            pygame.draw.rect(s, th.accent, (cr.x + 8, self.hl_y - 2, 3, line_h), border_radius=2)
        for idx, line in enumerate(PSEUDOCODE):
            ly = y0 + idx * line_h
            num = self.f_code.render(str(idx + 1), True, lerp_color(th.dim, th.panel_bg, 0.5))
            s.blit(num, (cr.x + 18, ly))
            self.text(line, self.f_code, th.accent if idx == active else lerp_color(th.text, th.dim, 0.35),
                      cr.x + 40, ly)

        # --- controls as keycaps, two columns
        self.caps("controls", x, 516 + off, th.dim)
        if self.demo or self.demo_finale:
            rows = [((["SPACE"], "pause"), (["→"], "step")),
                    ((["+", "-"], "speed"), (["D"], "stop demo")),
                    ((["R"], "restart"), (["N"], "next level")),
                    ((["T"], "theme"), (["ESC"], "back"))]
        else:
            rows = [((["↑", "↓"], "choose pair"), (["SPACE"], "swap")),
                    ((["F"], "next one now"), (["D"], "watch demo")),
                    ((["R"], "restart"), (["P"], "pause & rules")),
                    ((["T"], "theme"), (["ESC"], "back"))]
        for r_i, row in enumerate(rows):
            ry = 536 + off + r_i * 29
            for c_i, (keys, label) in enumerate(row):
                kx = x + c_i * (inner // 2)
                for key in keys:
                    kx += self.keycap(key, kx, ry) + 4
                img = self.f_small.render(label, True, th.text)
                s.blit(img, img.get_rect(midleft=(kx + 4, ry + 11)))

    def draw_result(self):
        """Result card: pops in with a springy scale, stars appear one by one."""
        s, th, age = self.screen, self.theme, self.result_age
        if age < 0.15:
            return
        age -= 0.15
        card = pygame.Surface((420, 250), pygame.SRCALPHA)
        pygame.draw.rect(card, (*th.panel_bg, 252), card.get_rect(), border_radius=12)
        border = th.bad if self.result == "failed" else th.accent
        pygame.draw.rect(card, border, card.get_rect(), 3, border_radius=12)
        cx, y = card.get_width() // 2, 14
        bottom = card.get_height() - 30
        ct = self.center_text
        if self.result == "won":
            y = ct("Tank cleared!", self.f_big, th.accent, cx, y, card)
            labels = ["cleared", f"chain ×{self.level.chain}", "clean"]
            got = [True, self.best_chain >= self.level.chain, self.wrong == 0]
            for k in range(3):                # stars pop in one after another
                p = (age - 0.25 - k * 0.18) / 0.3
                sx = cx + (k - 1) * 110
                lab = self.f_tiny.render(labels[k].upper(), True, th.text if got[k] else th.dim)
                card.blit(lab, lab.get_rect(midtop=(sx, y + 44)))
                if p <= 0:
                    continue
                self.draw_star(sx, y + 20, 20, got[k], max(0.05, ease_out_back(min(1.0, p))), card)
            y += 70
            y = ct(f"Score {self.score}   ·   {self.swaps} swaps", self.f_mid, th.text, cx, y, card)
            if self.new_record:
                ct("New personal best!", self.f_small, th.good, cx, y, card)
            nxt = "N next level   " if self.level_idx + 1 < len(LEVELS) else ""
            ct(nxt + "R again   ESC levels", self.f_small, th.dim, cx, bottom, card)
        elif self.result == "failed":
            y = ct("Game over" if self.endless else "Not this time", self.f_big, th.bad, cx, y + 6, card)
            for line in self.wrap(self.fail_reason, self.f_mid, 380):
                y = ct(line, self.f_mid, th.text, cx, y + 4, card)
            y = ct(f"Score {self.score}   ·   surfaced {self.surfaced}", self.f_mid, th.accent, cx, y + 8, card)
            if self.endless:
                ct("New high score!" if self.new_record else f"High score {self.save.get('endless', 0)}",
                   self.f_small, th.good if self.new_record else th.dim, cx, y + 4, card)
            else:
                ct("Tip: carry the biggest one up first.", self.f_small, th.dim, cx, y + 4, card)
            ct("R try again   D watch demo   ESC back", self.f_small, th.dim, cx, bottom, card)
        else:
            y = ct("Demo finished", self.f_big, th.accent, cx, y + 10, card)
            y = ct(f"{self.swaps} swaps = {inversions(self.start_values)} inversions", self.f_mid, th.text, cx, y + 6, card)
            ct("Now try it yourself!", self.f_mid, th.good, cx, y + 10, card)
            ct("R play   ESC back", self.f_small, th.dim, cx, bottom, card)

        p = min(1.0, age / 0.4)
        center = (PANEL_X + (W - PANEL_X - 20) // 2, H // 2)   # over the panel, not the column
        veil = pygame.Surface((W - PANEL_X - 20, H - 40), pygame.SRCALPHA)
        pygame.draw.rect(veil, (0, 0, 0, int(120 * p)), veil.get_rect(), border_radius=14)
        s.blit(veil, (PANEL_X, 20))
        self.glow_rect(card.get_rect(center=center), border, p, 12)
        img = pygame.transform.smoothscale_by(card, max(0.05, ease_out_back(p)))
        img.set_alpha(int(255 * min(1.0, p * 2)))
        s.blit(img, img.get_rect(center=center))


if __name__ == "__main__":
    Game().run()
    pygame.quit()
