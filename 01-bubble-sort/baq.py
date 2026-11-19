"""
BUBBLE SORT QUEST: a game that teaches Bubble Sort

Rules:
  A column holds numbered elements (bubbles, raindrops or fireballs, depending
  on the theme). Bigger elements want to rise to the top. You may only swap
  TWO NEIGHBOURING elements, exactly like Bubble Sort does.
  Goal: order them from smallest (bottom) to largest (top) using as few
  swaps as possible.

Menu:
  Arrows / mouse  choose,  ENTER / click  confirm,  ESC  back

In a level:
  Up / Down / wheel   choose a pair of neighbours (or click a pair)
  SPACE / click       swap the selected pair (click it once more)
  D                   DEMO: the algorithm sorts the same data step by step
                      (in demo: SPACE pause, RIGHT one step, +/- speed)
  R                   restart the level
  N                   next level (once this one is solved)
  T                   change theme
  ESC                 back to the level list

Run:
  pip install pygame
  python baq.py
"""

import json
import math
import os
import random
import sys

import pygame

from levels import LEVELS, VMAX, make_values
from themes import THEMES, W, H, lerp_color, text_outlined

FPS = 60
COL_X = 250            # x centre of the element column
BOTTOM = H - 80        # y of the lowest element
TOP = 110              # y of the highest element
PANEL_X = 480          # left edge of the info panel
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")
FONTS = "dejavusans,freesans,arial"


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


def count_stats(values):
    """How many comparisons and swaps Bubble Sort makes on this data."""
    comps = swaps = 0
    for kind, _, _ in bubble_sort_steps(values):
        comps += kind == "compare"
        swaps += kind == "swap"
    return comps, swaps


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
def ease_in_out(p):
    """Slow start, fast middle, slow end (cubic)."""
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out_back(p):
    """Overshoots a little and settles: a springy 'pop'."""
    c = 1.70158
    return 1 + (c + 1) * (p - 1) ** 3 + c * (p - 1) ** 2


def approach(cur, target, dt, speed=12.0):
    """Frame-rate independent smoothing towards a target."""
    return cur + (target - cur) * (1 - math.exp(-speed * dt))


# ------------------------------------------------------------------ saving
def load_save():
    try:
        with open(SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {"stars": dict(data.get("stars", {})), "best": dict(data.get("best", {})),
                "theme": data.get("theme", "aquarium")}
    except (OSError, ValueError, AttributeError):
        return {"stars": {}, "best": {}, "theme": "aquarium"}


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
        self.uid = uid             # starting position, used to check stability
        self.label = label         # "a", "b", "c" for equal values
        self.phase = random.uniform(0, math.tau)
        # swap animation: the two elements pass each other on curved paths
        self.from_y = self.to_y = y
        self.anim = 1.0            # 0 -> 1 while swapping
        self.side = 0              # +1 = curve to the right, -1 = to the left
        self.x_off = 0.0
        self.scale = 1.0           # smoothed size multiplier (hover, swap)
        self.hover = False
        self.pop = 0.0             # 1 -> 0 springy bump (win wave, sorted)
        self.pop_delay = 0.0


class Board:
    """The column of elements: positions, swap animation and drawing."""

    SWAP_TIME = 0.32           # seconds per swap animation

    def __init__(self, values, col_x=COL_X, top=TOP, bottom=BOTTOM, intro=True):
        self.col_x, self.top, self.bottom = col_x, top, bottom
        n = len(values)
        counts = {v: values.count(v) for v in values}
        seen = {}
        self.items = []
        for i, v in enumerate(values):
            label = ""
            if counts[v] > 1:
                label = "abc"[seen.get(v, 0)]
                seen[v] = seen.get(v, 0) + 1
            self.items.append(Element(v, self.slot_y(i, n), i, label))
        if intro:                  # elements rise into place one after another
            for i, e in enumerate(self.items):
                e.y = H + 60 + i * 55

    @property
    def n(self):
        return len(self.items)

    def slot_y(self, i, n=None):
        """Index 0 = bottom, index n-1 = top."""
        n = n or self.n
        return self.bottom - i * (self.bottom - self.top) / (n - 1)

    def radius(self, value):
        step = (self.bottom - self.top) / (self.n - 1)
        return int(min(step * 0.48, 46) * (0.45 + 0.55 * value / VMAX))

    def values(self):
        return [e.value for e in self.items]

    def is_sorted(self):
        v = self.values()
        return v == sorted(v)

    def is_stable(self):
        """Equal values still in their original order?"""
        last = {}
        for e in self.items:
            if e.uid < last.get(e.value, -1):
                return False
            last[e.value] = e.uid
        return True

    def swap(self, j):
        a, b = self.items[j], self.items[j + 1]
        self.items[j], self.items[j + 1] = b, a
        for e, idx, side in ((a, j + 1, 1), (b, j, -1)):
            e.from_y, e.to_y = e.y, self.slot_y(idx)
            e.anim, e.side = 0.0, side

    def pop_wave(self, delay=0.07):
        """Bounce every element, bottom to top, like a wave."""
        for i, e in enumerate(self.items):
            e.pop, e.pop_delay = 1.0, i * delay

    @property
    def busy(self):
        return any(e.anim < 1 for e in self.items)

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

    def pop_scale(self, e):
        if e.pop <= 0 or e.pop_delay > 0:
            return 1.0
        return 1 + 0.35 * math.sin(math.pi * (1 - e.pop)) * e.pop

    def pair_at(self, pos):
        """Pair index (j, j+1) whose middle is closest to the mouse, or None."""
        x, y = pos
        if abs(x - self.col_x) > 100 or not (self.top - 50 <= y <= self.bottom + 50):
            return None
        mids = [(self.slot_y(j) + self.slot_y(j + 1)) / 2 for j in range(self.n - 1)]
        return min(range(self.n - 1), key=lambda j: abs(mids[j] - y))

    def draw(self, s, theme, font, t, sorted_from, hidden=False, dx=0):
        # moving elements are drawn last, so they pass in front of the others
        order = sorted(range(self.n), key=lambda i: (self.items[i].anim < 1, self.items[i].side))
        for i in order:
            e = self.items[i]
            ring = theme.accent if i >= sorted_from else None
            r = int(self.radius(e.value) * e.scale * self.pop_scale(e))
            theme.draw_element(s, font, self.x_of(e, t) + dx, e.y, r,
                               e.value, VMAX, t, ring, e.label, e.phase, hidden)


# ------------------------------------------------------------------ buttons
class Button:
    def __init__(self, rect, label, action, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label, self.action, self.enabled = label, action, enabled


# --------------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.f_title = pygame.font.SysFont(FONTS, 54, bold=True)
        self.f_big = pygame.font.SysFont(FONTS, 34, bold=True)
        self.f_head = pygame.font.SysFont(FONTS, 27, bold=True)
        self.f_mid = pygame.font.SysFont(FONTS, 20, bold=True)
        self.f_small = pygame.font.SysFont(FONTS, 16)
        self.f_tiny = pygame.font.SysFont(FONTS, 12, bold=True)
        self.f_value = pygame.font.SysFont(FONTS, 26, bold=True)
        self.f_code = pygame.font.SysFont("dejavusansmono,monospace", 15)

        self.save = load_save()
        self.themes = [cls() for cls in THEMES]
        keys = [th.key for th in self.themes]
        self.theme_idx = keys.index(self.save["theme"]) if self.save["theme"] in keys else 0
        self.apply_theme()

        self.t = 0.0
        self.dt = 1 / FPS
        self.fade = 1.0                   # 1 = black screen, fades out after a scene change
        self.ui = {}                      # smoothed hover amounts of buttons, keyed by name
        self.shaking = {}                 # locked level cards that wiggle when clicked
        self.hand = False                 # is the mouse cursor a hand?
        self.scene = "menu"
        self.sel = 0                      # keyboard selection in menus
        self.level_sel = self.first_unfinished()
        self.demo_delay = 0.7
        self.menu_demo_reset()

    # ---------------------------------------------------------- helpers
    @property
    def theme(self):
        return self.themes[self.theme_idx]

    def apply_theme(self):
        pygame.display.set_caption(f"{self.theme.title}: Bubble Sort")
        self.save["theme"] = self.theme.key

    def stars(self, idx):
        return self.save["stars"].get(str(idx), 0)

    def unlocked(self, idx):
        return idx == 0 or self.stars(idx - 1) > 0

    def first_unfinished(self):
        for i in range(len(LEVELS)):
            if self.stars(i) == 0:
                return i
        return 0

    def text(self, txt, font, color, x, y, alpha=255, scale=1.0):
        img = font.render(txt, True, color)
        h = img.get_height()
        if scale != 1.0:
            img = pygame.transform.smoothscale_by(img, scale)
            y0 = y - (img.get_height() - h) / 2      # grows around its middle line
            x0 = x
        else:
            x0, y0 = x, y
        if alpha < 255:
            img.set_alpha(int(alpha))
        self.screen.blit(img, (x0, y0))
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

    @staticmethod
    def wrap(txt, width):
        lines, cur = [], ""
        for w in txt.split():
            if cur and len(cur) + len(w) + 1 > width:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
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
            pygame.draw.rect(surf, (*color, int(strength * 40 / k)), r, border_radius=radius + k * 5)
        self.screen.blit(surf, (rect.x - pad, rect.y - pad))

    def draw_button(self, b, selected, key):
        th = self.theme
        a = self.smooth(key, 1.0 if selected and b.enabled else 0.0)
        r = b.rect.inflate(int(12 * a), int(6 * a))
        self.glow_rect(r, th.accent, a)
        self.panel(r, 190 + 50 * a)
        pygame.draw.rect(self.screen, lerp_color(th.dim, th.accent, a), r, 1 + round(2 * a),
                         border_radius=14)
        color = lerp_color(th.text if b.enabled else th.dim, th.accent, a)
        img = self.f_mid.render(b.label, True, color)
        self.screen.blit(img, img.get_rect(center=r.center))

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
        """Small spaced-out capital letters, used for labels."""
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

    def draw_star(self, cx, cy, r, filled, scale=1.0):
        th = self.theme
        pts = self.star_points(cx, cy, r * scale)
        if filled:
            pygame.draw.polygon(self.screen, lerp_color(th.accent, (120, 70, 0), 0.45),
                                [(x, y + 2) for x, y in pts])
            pygame.draw.polygon(self.screen, th.accent, pts)
        else:
            pygame.draw.polygon(self.screen, lerp_color(th.panel_bg, (0, 0, 0), 0.3), pts)
            pygame.draw.polygon(self.screen, lerp_color(th.dim, th.panel_bg, 0.4), pts, 2)

    def draw_icon(self, kind, cx, cy, color):
        """Tiny vector icons: clock, limit, eye."""
        s = self.screen
        if kind == "clock":
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

    def draw_stars(self, cx, y, count, font=None):
        font = font or self.f_mid
        self.center_text("★" * count + "☆" * (3 - count), font, self.theme.accent, cx, y)

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

    def go(self, scene):
        self.scene = scene
        self.fade = 0.6
        self.sel = 0
        if scene == "levels":
            self.sel = self.level_sel
        elif scene == "themes":
            self.sel = self.theme_idx
        elif scene == "menu":
            self.menu_demo_reset()

    def handle(self, e):
        getattr(self, f"handle_{self.scene}")(e)

    def update(self, dt):
        self.t += dt
        self.dt = dt
        self.fade = max(0.0, self.fade - dt * 3)
        self.theme.update(dt, self.t)
        if self.scene == "play":
            self.update_play(dt)
        elif self.scene == "menu":
            self.update_menu_demo(dt)

    def draw(self):
        self.theme.draw_background(self.screen, self.t)
        getattr(self, f"draw_{self.scene}")()
        self.theme.draw_sparks(self.screen)
        if self.fade > 0:                       # smooth fade after a scene change
            veil = pygame.Surface((W, H))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * ease_in_out(min(1.0, self.fade))))
            self.screen.blit(veil, (0, 0))

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
        labels = [("Play", lambda: self.start_level(self.first_unfinished())),
                  ("Choose level", lambda: self.go("levels")),
                  ("Theme: " + self.theme.title, lambda: self.go("themes")),
                  ("Quit", self.quit)]
        return [Button((x, 300 + k * 78, w, 60), lbl, act) for k, (lbl, act) in enumerate(labels)]

    def menu_demo_reset(self):
        self.menu_board = Board(make_values(LEVELS[1]), COL_X, 200, BOTTOM)
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
        self.menu_input(e, self.menu_buttons())

    def draw_menu(self):
        s, th = self.screen, self.theme
        rect = pygame.Rect(COL_X - 110, 140, 220, BOTTOM - 200 + 120)
        th.draw_container(s, rect, self.t)
        lbl = self.f_small.render(th.up_label, True, th.dim)
        s.blit(lbl, lbl.get_rect(center=(COL_X, 125)))
        a = self.smooth("menu_pair_a", 1.0 if self.menu_pair is not None else 0.0, 8)
        if self.menu_pair is not None:
            self.menu_pair_f = self.smooth("menu_pair_f", self.menu_pair, 10)
        if a > 0.02:
            self.draw_selector(self.menu_board, self.ui.get("menu_pair_f", 0), th.accent, a)
        self.menu_board.draw(s, th, self.f_mid, self.t, self.menu_sorted)

        bob = math.sin(self.t * 1.6) * 5
        text_outlined(s, self.f_title, th.title, (720, 120 + bob), th.accent, (10, 10, 20), 3)
        text_outlined(s, self.f_mid, "a game about Bubble Sort", (720, 175), th.text, (10, 10, 20))
        text_outlined(s, self.f_small, th.tagline, (720, 210), th.dim, (10, 10, 20), 1)
        total = sum(self.stars(i) for i in range(len(LEVELS)))
        text_outlined(s, self.f_mid, f"★ {total} / {3 * len(LEVELS)}", (720, 255), th.accent, (10, 10, 20))
        for i, b in enumerate(self.menu_buttons()):
            self.draw_button(b, i == self.sel, f"menu{i}")
        text_outlined(s, self.f_small, "↑↓ choose   ENTER confirm   T theme   ESC quit",
                      (720, H - 40), th.dim, (10, 10, 20), 1)

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

    def handle_levels(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self.go("menu")
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
            self.set_hand(over or self.play_button_rect().collidepoint(e.pos))
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

        # --- header: title + star progress bar
        text_outlined(s, self.f_big, "Choose a level", (W // 2, 48), th.text, (10, 10, 20), 3)
        total, most = sum(self.stars(i) for i in range(len(LEVELS))), 3 * len(LEVELS)
        bar = pygame.Rect(W // 2 - 150, 78, 300, 12)
        pygame.draw.rect(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), bar, border_radius=6)
        pygame.draw.rect(s, lerp_color(th.dim, th.panel_bg, 0.5), bar.inflate(4, 4), 1, border_radius=8)
        shown = self.smooth("star_bar", total / most, 5)
        if shown > 0.005:
            pygame.draw.rect(s, th.accent, (bar.x, bar.y, max(12, int(bar.w * shown)), bar.h), border_radius=6)
        self.draw_star(bar.right + 18, bar.centery, 10, True)
        img = self.f_mid.render(f"{total}/{most}", True, th.accent)
        s.blit(img, img.get_rect(midleft=(bar.right + 34, bar.centery)))

        # --- the path between nodes (bright where you already went)
        for i in range(len(LEVELS) - 1):
            done = self.stars(i) > 0
            pts = self.path_points(i)
            dist = 0.0
            for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
                dist += math.hypot(xb - xa, yb - ya)
                if int(dist / 13) != int((dist - math.hypot(xb - xa, yb - ya)) / 13):
                    if math.hypot(xb - self.node_pos(i)[0], yb - self.node_pos(i)[1]) < self.NODE_R + 6:
                        continue
                    if math.hypot(xb - self.node_pos(i + 1)[0], yb - self.node_pos(i + 1)[1]) < self.NODE_R + 6:
                        continue
                    if done:
                        pygame.draw.circle(s, th.accent, (int(xb), int(yb)), 4)
                    else:
                        pygame.draw.circle(s, lerp_color(th.dim, th.panel_bg, 0.5), (int(xb), int(yb)), 3)

        # --- nodes
        current = self.first_unfinished()
        for i, b in enumerate(self.level_buttons()):
            x, y = self.node_pos(i)
            sel = i == self.sel
            hov = b.rect.collidepoint(mouse)
            a = self.smooth(f"lvl{i}", 1.0 if sel else 0.5 if hov else 0.0)
            if i in self.shaking:                        # locked node wiggles "no"
                self.shaking[i] -= self.dt
                x += int(math.sin(self.shaking[i] * 50) * 7 * self.shaking[i] / 0.45)
                if self.shaking[i] <= 0:
                    del self.shaking[i]
            y -= int(6 * a)
            r = int(self.NODE_R * (1 + 0.15 * a))
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
                th.draw_element(s, self.f_mid, x, y, r, min(VMAX, i + 1), VMAX, self.t,
                                th.accent if self.stars(i) == 3 else None, phase=i)
                # 3 small stars in an arc under the node
                for k in range(3):
                    sx = x + (k - 1) * 20
                    sy = y + r + 14 + (0 if k == 1 else -4)
                    self.draw_star(sx, sy, 8, k < self.stars(i))
            else:
                pygame.draw.circle(s, lerp_color(th.panel_bg, (0, 0, 0), 0.35), (x, y), r)
                pygame.draw.circle(s, lerp_color(th.dim, th.panel_bg, 0.5), (x, y), r, 2)
                self.draw_lock(x, y + 6)
            # rule badges in the corner of the node
            lv = LEVELS[i]
            icons = [k for k, on in (("clock", lv.time_limit), ("limit", lv.swap_limit is not None),
                                     ("eye", lv.hidden)) if on]
            for k, icon in enumerate(icons):
                bx, by = x + r - 2 + k * 22, y - r + 4
                pygame.draw.circle(s, th.panel_bg, (bx, by), 11)
                pygame.draw.circle(s, th.dim, (bx, by), 11, 1)
                self.draw_icon(icon, bx, by, th.text if b.enabled else th.dim)
            name_col = lerp_color(th.dim, th.text, a) if b.enabled else lerp_color(th.dim, th.panel_bg, 0.3)
            text_outlined(s, self.f_small, lv.name, (x, y + r + 36), name_col, (10, 10, 20), 1)

        self.draw_level_card()
        hint = "arrows choose  ·  ENTER play  ·  ESC back"
        text_outlined(s, self.f_small, hint, (W // 2, H - 16), th.dim, (10, 10, 20), 1)

    def draw_level_card(self):
        """Details of the selected level with a big PLAY button."""
        s, th = self.screen, self.theme
        lv, i, ok = LEVELS[self.sel], self.sel, self.unlocked(self.sel)
        box = pygame.Rect(90, 560, W - 180, 120)
        self.glow_rect(box, th.accent, 0.35, 16)
        self.card(box, 0.04, 235, 16, (*th.accent, 90))
        # big number badge
        bc = (box.x + 60, box.centery)
        pygame.draw.circle(s, th.accent if ok else th.dim, bc, 38)
        pygame.draw.circle(s, lerp_color(th.accent, (255, 255, 255), 0.4) if ok else th.dim, bc, 38, 3)
        img = self.f_big.render(str(i + 1), True, (25, 20, 15))
        s.blit(img, img.get_rect(center=bc))
        # name, lesson, rule chips
        x = box.x + 120
        self.caps(f"Level {i + 1}  ·  {lv.n} {th.nouns}", x, box.y + 14, th.accent)
        self.text(lv.name, self.f_head, th.text, x, box.y + 30)
        self.text(lv.lesson, self.f_small, th.dim, x, box.y + 66)
        cx = x
        chips = []
        if lv.time_limit:
            chips.append(f"{lv.time_limit} s clock")
        if lv.swap_limit is not None:
            chips.append("exact minimum" if lv.swap_limit == 0 else f"minimum + {lv.swap_limit}")
        if lv.hidden:
            chips.append("hidden numbers")
        best = self.save["best"].get(str(i))
        if best is not None:
            chips.append(f"best: {best} swaps")
        for c in chips:
            cx += self.chip(c, cx, box.y + 90, th.accent) + 8
        # PLAY button
        pr = self.play_button_rect()
        hov = pr.collidepoint(pygame.mouse.get_pos())
        a = self.smooth("playbtn", 1.0 if hov else 0.0)
        pr = pr.inflate(int(8 * a), int(6 * a))
        if ok:
            pulse = 0.5 + 0.5 * math.sin(self.t * 3)
            self.glow_rect(pr, th.accent, 0.6 + 0.4 * pulse * (1 - a) + a, 30)
            pygame.draw.rect(s, lerp_color(th.accent, (120, 70, 0), 0.4), pr.move(0, 4), border_radius=30)
            pygame.draw.rect(s, lerp_color(th.accent, (255, 255, 255), 0.25 * a), pr, border_radius=30)
            # play triangle + text
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
        self.theme_idx = k
        self.apply_theme()
        write_save(self.save)
        self.go("menu")

    def cycle_theme(self):
        self.fade = 0.5
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
        text_outlined(s, self.f_big, "Choose a theme", (W // 2, 80), self.theme.accent, (10, 10, 20), 3)
        for k, b in enumerate(self.theme_buttons()):
            th, sel = self.themes[k], k == self.sel
            a = self.smooth(f"theme{k}", 1.0 if sel else 0.0)
            b.rect = b.rect.move(0, int(-10 * a))
            self.glow_rect(b.rect, th.accent, a, 6)
            # each card is a little window into its own theme
            card = pygame.Surface(b.rect.size)
            card.blit(th.bg, (0, 0), pygame.Rect(COL_X - b.rect.w // 2, H - b.rect.h, *b.rect.size))
            s.blit(card, b.rect)
            for v, yy in ((4, 300), (8, 230)):
                fy = math.sin(self.t * 2 + v) * 6 * (0.3 + a)
                th.draw_element(s, self.f_mid, b.rect.centerx, b.rect.y + yy + fy,
                                int((14 + v * 3) * (1 + 0.1 * a)), v, VMAX, self.t,
                                th.accent if v == 8 else None, phase=v)
            pygame.draw.rect(s, lerp_color(th.dim, th.accent, a), b.rect, 1 + round(3 * a), border_radius=6)
            text_outlined(s, self.f_mid, th.title, (b.rect.centerx, b.rect.y + 30), th.accent, (10, 10, 20))
            for n, line in enumerate(self.wrap(th.tagline, 28)):
                text_outlined(s, self.f_small, line, (b.rect.centerx, b.rect.y + 62 + n * 20),
                              th.text, (10, 10, 20), 1)
            if k == self.theme_idx:
                text_outlined(s, self.f_small, "current", (b.rect.centerx, b.rect.bottom - 20),
                              th.accent, (10, 10, 20), 1)
        text_outlined(s, self.f_small, "←→ choose   ENTER apply   ESC back",
                      (W // 2, H - 40), self.theme.dim, (10, 10, 20), 1)

    # ------------------------------------------------------------- playing
    def start_level(self, idx):
        if not self.unlocked(idx):
            return
        self.level_idx = self.level_sel = idx
        self.level = LEVELS[idx]
        self.start_values = make_values(self.level)
        self.scene = "play"
        self.fade = 0.6
        self.reset()

    def reset(self):
        self.board = Board(self.start_values)
        self.cursor = 0
        self.swaps = 0
        self.opt_comps, self.opt_swaps = count_stats(self.start_values)
        self.limit = None if self.level.swap_limit is None else self.opt_swaps + self.level.swap_limit
        self.time_left = self.level.time_limit
        self.result = None            # None | "won" | "failed" | "demo"
        self.fail_reason = ""
        self.new_record = False
        self.demo = None
        self.demo_step = None
        self.demo_timer = 0.0
        self.demo_paused = False
        self.demo_swapped = False
        self.sorted_from = self.board.n
        self.shake = 0.0
        # animation state of the play screen
        self.cur_f = 0.0               # smoothed pointer position (pair index)
        self.sel_color = self.theme.accent
        self.hover_pair = None         # pair under the mouse
        self.hover_shown = 0           # last hovered pair, kept while it fades out
        self.hover_a = 0.0
        self.swap_pop = 0.0            # "Swaps: N" bounces when it changes
        self.msg_age = 0.0
        self.shown_msg = ""
        self.hl_y = None               # smoothed pseudocode highlight
        self.result_age = 0.0
        th = self.theme
        self.msg_kind = "info"
        self.message = f"Swap neighbouring {th.nouns}. Big ones must reach the top!"
        self.msg_kind = "info"

    def player_swap(self):
        if self.result or self.demo:
            return
        b, j = self.board, self.cursor
        a, c = b.items[j].value, b.items[j + 1].value
        b.swap(j)
        self.swaps += 1
        self.swap_pop = 1.0
        th = self.theme
        y = (b.slot_y(j) + b.slot_y(j + 1)) / 2
        if a > c:
            self.message = f"Nice! {a} > {c}, so {a} {th.rise_verb}."
            self.msg_kind = "good"
            th.burst(COL_X, y)
        elif a == c:
            self.msg_kind = "bad"
            self.message = (f"{a} = {c}: Bubble Sort never swaps equal values. "
                            "That is what makes it stable!")
            self.shake = 0.3
        else:
            self.message = f"Hmm, {a} < {c}: that swap breaks the order!"
            self.msg_kind = "bad"
            self.shake = 0.4
        if self.level.hidden:
            self.message = "Swapped. " + ("Bigger one went up, good!" if a > c else "Careful, that made it worse!")
        if b.is_sorted():
            self.win()
        elif self.limit is not None and self.swaps >= self.limit:
            self.fail("No swaps left! Every wasted swap counts.")

    def win(self):
        self.result = "won"
        self.sorted_from = 0
        extra = self.swaps - self.opt_swaps
        self.earned = 3 if extra == 0 else 2 if extra <= max(2, self.board.n // 3) else 1
        key = str(self.level_idx)
        if self.earned > self.stars(self.level_idx):
            self.save["stars"][key] = self.earned
        best = self.save["best"].get(key)
        if best is None or self.swaps < best:
            self.save["best"][key] = self.swaps
            self.new_record = best is not None
        write_save(self.save)
        self.result_age = 0.0
        self.board.pop_wave()
        for i in range(self.board.n):
            self.theme.burst(COL_X, self.board.slot_y(i), 10)

    def fail(self, reason):
        self.result = "failed"
        self.result_age = 0.0
        self.fail_reason = reason
        self.shake = 0.5

    def toggle_demo(self):
        was = self.demo
        self.reset()
        if was:
            return
        self.demo = bubble_sort_steps(self.start_values)
        self.time_left = None
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
            self.sorted_from = j
            b.items[j].pop = 1.0
            self.message = f"End of pass {i + 1}: {self.theme.noun} {v[j]} is now in its final place."
            self.msg_kind = "good"
        elif kind == "early":
            self.sorted_from = 0
            self.message = "A whole pass with no swaps → everything is sorted, stop early!"
            self.msg_kind = "good"
        elif kind == "done":
            self.sorted_from = 0
            self.result = "demo"
            self.result_age = 0.0
            b.pop_wave()
            self.demo = None

    def handle_play(self, e):
        if e.type == pygame.KEYDOWN:
            self.on_key(e.key)
        elif e.type == pygame.MOUSEWHEEL and not self.demo and not self.result:
            self.cursor = max(0, min(self.board.n - 2, self.cursor + e.y))
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1 and not self.demo and not self.result:
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
            self.go("levels")
        elif k == pygame.K_t:
            self.cycle_theme()
        elif k == pygame.K_r:
            self.reset()
        elif k == pygame.K_d:
            self.toggle_demo()
        elif k == pygame.K_n:
            nxt = self.level_idx + 1
            if nxt < len(LEVELS) and self.unlocked(nxt):
                self.start_level(nxt)
            elif nxt >= len(LEVELS):
                self.message = "That was the last level. You are a Bubble Sort master!"
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
        elif self.result:
            return
        elif k == pygame.K_UP:
            self.cursor = min(self.cursor + 1, n - 2)
        elif k == pygame.K_DOWN:
            self.cursor = max(self.cursor - 1, 0)
        elif k == pygame.K_SPACE:
            self.player_swap()

    def update_play(self, dt):
        b = self.board
        # which pair is under the mouse?
        interactive = not self.demo and not self.result and pygame.mouse.get_focused()
        self.hover_pair = b.pair_at(pygame.mouse.get_pos()) if interactive else None
        self.set_hand(self.hover_pair is not None)
        if self.hover_pair is not None and self.hover_pair != self.cursor:
            self.hover_shown = self.hover_pair
        show = self.hover_pair is not None and self.hover_pair != self.cursor
        self.hover_a = approach(self.hover_a, 1.0 if show else 0.0, dt, 16)
        for i, e in enumerate(b.items):
            e.hover = show and i in (self.hover_pair, self.hover_pair + 1)
        # smooth pointer movement and colour
        self.cur_f = approach(self.cur_f, self.cursor, dt, 16)
        step = self.demo_step[0] if (self.demo and self.demo_step) else None
        th = self.theme
        target = {"swap": th.bad, "keep": th.good}.get(step, th.accent)
        if self.shake > 0 and not self.demo:
            target = th.bad
        self.sel_color = tuple(approach(c, tc, dt, 12) for c, tc in zip(self.sel_color, target))
        self.swap_pop = max(0.0, self.swap_pop - dt * 3)
        self.msg_age += dt
        self.result_age += dt

        b.update(dt)
        self.shake = max(0.0, self.shake - dt)
        if self.time_left is not None and not self.result and not self.demo:
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.fail("Time is up!")
        if self.demo and not self.demo_paused:
            self.demo_timer += dt
            if self.demo_timer >= self.demo_delay:
                self.demo_timer = 0
                self.demo_advance()

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
        # a soft shine line along the top of the capsule
        pygame.draw.rect(fill, (255, 255, 255, int(alpha * 40)), (18, 6, box.w - 36, 4), border_radius=2)
        s.blit(fill, box)
        edge = pygame.Surface(box.size, pygame.SRCALPHA)
        pygame.draw.rect(edge, (*color, int(255 * alpha)), edge.get_rect(), 3, border_radius=30)
        s.blit(edge, box)
        # chevrons on both sides, bobbing towards the pair
        cy, bob = box.centery, 5 * math.sin(t * 6)
        for side in (-1, 1):
            x = box.centerx + side * (box.w / 2 + 18 + bob)
            pts = [(x + side * 9, cy - 11), (x - side * 5, cy), (x + side * 9, cy + 11)]
            pygame.draw.polygon(s, lerp_color((20, 20, 30), color, alpha), pts)
        # little swap icon: two arrows, one up, one down
        ix = box.right + 44 + dx
        for k, d in ((-1, -1), (1, 1)):
            ax = ix + k * 6
            ay = cy - d * 9 + d * 2 * math.sin(t * 6)
            pygame.draw.line(s, color, (ax, cy - 10), (ax, cy + 10), 2)
            pygame.draw.polygon(s, color, [(ax - 5, ay), (ax + 5, ay), (ax, ay - d * 7)])

    def draw_hover(self, board, j, alpha, t, dx=0):
        """The pair under the mouse: soft halos and thin rings around its two
        elements only, so it never covers the selected (gold) capsule."""
        th = self.theme
        for i in (j, j + 1):
            if i == self.cursor or i == self.cursor + 1:
                continue                         # already inside the gold capsule
            e = board.items[i]
            x, y = board.x_of(e, t) + dx, e.y
            r = int(board.radius(e.value) * e.scale) + 8
            halo = pygame.Surface((r * 2 + 24, r * 2 + 24), pygame.SRCALPHA)
            c = r + 12
            for k in range(4):
                pygame.draw.circle(halo, (*th.text, int(alpha * 14 * (k + 1))), (c, c), r + 10 - k * 3)
            pygame.draw.circle(halo, (*th.text, int(alpha * 200)), (c, c), r, 2)
            self.screen.blit(halo, (x - c, y - c))
        # a small tag at the left, pointing at the middle of the pair
        y1, y2 = board.slot_y(j), board.slot_y(j + 1)
        cy = (y1 + y2) / 2
        img = self.f_tiny.render("SELECT", True, th.text)
        tag = pygame.Rect(0, 0, img.get_width() + 16, img.get_height() + 8)
        tag.midright = (board.col_x - 116 + dx, cy)
        surf = pygame.Surface(tag.size, pygame.SRCALPHA)
        pygame.draw.rect(surf, (*th.panel_bg, int(220 * alpha)), surf.get_rect(), border_radius=tag.h // 2)
        pygame.draw.rect(surf, (*th.text, int(150 * alpha)), surf.get_rect(), 1, border_radius=tag.h // 2)
        img.set_alpha(int(255 * alpha))
        surf.blit(img, img.get_rect(center=surf.get_rect().center))
        self.screen.blit(surf, tag)
        if alpha > 0.5:                          # small arrow pointing at the pair
            pygame.draw.polygon(self.screen, th.text,
                                [(tag.right + 3, cy - 5), (tag.right + 9, cy), (tag.right + 3, cy + 5)])

    def draw_play(self):
        s, th = self.screen, self.theme
        dx = int(math.sin(self.t * 60) * 8 * self.shake)
        rect = pygame.Rect(COL_X - 110 + dx, TOP - 60, 220, BOTTOM - TOP + 120)
        th.draw_container(s, rect, self.t)
        text_outlined(s, self.f_small, th.up_label, (COL_X, TOP - 75), th.dim, (10, 10, 20), 1)

        step = self.demo_step[0] if (self.demo and self.demo_step) else None
        show_sel = not self.result and (not self.demo or step in ("compare", "swap", "keep"))
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
        self.board.draw(s, th, self.f_mid, self.t, self.sorted_from,
                        self.level.hidden and self.result is None, dx)
        self.draw_panel()
        if self.result:
            self.draw_result()

    def draw_panel(self):
        """Right side: header, stat tiles, message, pseudocode card, controls."""
        s, th, lv = self.screen, self.theme, self.level
        px, pw = PANEL_X, W - PANEL_X - 20
        self.panel(pygame.Rect(px, 20, pw, H - 40), 200)
        x, inner = px + 20, pw - 40

        # --- header
        self.caps(f"Level {self.level_idx + 1}  ·  {self.board.n} {th.nouns}", x, 34, th.accent)
        if self.demo or self.result == "demo":
            label = "demo paused" if self.demo_paused else f"demo · {self.demo_delay:.1f}s"
            img = self.f_tiny.render(label.upper(), True, th.text)
            self.chip(label, x + inner - img.get_width() - 18, 30, th.accent, filled=True)
        self.text(lv.name, self.f_head, th.text, x, 50)
        y = 86
        for line in self.wrap(lv.lesson, 54):
            y = self.text(line, self.f_small, th.dim, x, y) - 2

        # --- stat tiles
        best = self.save["best"].get(str(self.level_idx))
        tiles = [("swaps", str(self.swaps),
                  f"limit {self.limit}" if self.limit is not None and not self.demo else None),
                 ("minimum", str(self.opt_swaps), None),
                 ("compares", str(self.opt_comps), None)]
        if self.time_left is not None:
            tiles.append(("time", f"{math.ceil(self.time_left)}s", None))
        else:
            tiles.append(("best", "-" if best is None else str(best), None))
        off = max(0, y + 6 - 132)              # a 2-line lesson pushes everything down a bit
        gap, ty = 10, 132 + off
        tw = (inner - gap * (len(tiles) - 1)) / len(tiles)
        for k, (name, value, sub) in enumerate(tiles):
            r = pygame.Rect(int(x + k * (tw + gap)), ty, int(tw), 70)
            hot = name == "swaps" and self.swap_pop > 0
            hurry = name == "time" and self.time_left < 10 and not self.result
            border = th.bad if hurry else th.accent if hot else None
            self.card(r, 0.07, 220, 12, (*border, 200) if border else None)
            self.caps(name, r.x + 12, r.y + 9, th.dim)
            col = th.bad if hurry else lerp_color(th.text, th.accent, self.swap_pop) if name == "swaps" else th.text
            scale = 1.0
            if name == "swaps" and self.swap_pop > 0:
                scale += math.sin(math.pi * self.swap_pop) * 0.2
            if hurry:
                scale += 0.15 * (self.time_left % 1) ** 3
            self.text(value, self.f_value, col, r.x + 12, r.y + 26, scale=scale)
            if sub:
                img = self.f_tiny.render(sub.upper(), True, th.dim)
                s.blit(img, img.get_rect(bottomright=(r.right - 10, r.bottom - 9)))
            if name == "swaps" and self.limit is not None and not self.demo:
                frac = min(1.0, self.swaps / max(1, self.limit))     # budget bar
                pygame.draw.rect(s, lerp_color(th.panel_bg, (0, 0, 0), 0.3), (r.x + 10, r.bottom - 6, r.w - 20, 3))
                pygame.draw.rect(s, th.bad if frac > 0.8 else th.accent,
                                 (r.x + 10, r.bottom - 6, int((r.w - 20) * frac), 3))

        # --- message card (slides in when it changes)
        if self.message != self.shown_msg:
            self.shown_msg, self.msg_age = self.message, 0.0
        k = ease_in_out(min(1.0, self.msg_age / 0.25))
        kind_col = {"good": th.good, "bad": th.bad, "swap": th.bad}.get(self.msg_kind, th.accent)
        mr = pygame.Rect(x, 214 + off, inner, 62)
        self.card(mr, 0.04, 220, 12)
        pygame.draw.rect(s, kind_col, (mr.x, mr.y, 5, mr.h), border_top_left_radius=12, border_bottom_left_radius=12)
        lines = self.wrap(self.message, 50)[:2]
        my = mr.centery - len(lines) * 10
        for line in lines:
            my = self.text(line, self.f_small, th.text, mr.x + 18 + int(10 * (1 - k)), my, 255 * k) - 4

        # --- pseudocode card
        cr = pygame.Rect(x, 288 + off, inner, 196)
        self.card(cr, -0.35, 200, 12)
        self.caps("pseudocode", cr.x + 14, cr.y + 10, th.dim)
        if self.demo and self.demo_step:
            _, jj, ii = self.demo_step
            vars_txt = f"i={ii}  j={jj}  swapped={self.demo_swapped}"
            img = self.f_code.render(vars_txt, True, th.accent)
            s.blit(img, img.get_rect(topright=(cr.right - 14, cr.y + 7)))
        line_h, y0 = 20, cr.y + 34
        active = STEP_LINE.get(self.demo_step[0], -1) if (self.demo and self.demo_step) else -1
        if active >= 0:                            # highlight glides between lines
            target = y0 + active * line_h
            self.hl_y = target if self.hl_y is None else approach(self.hl_y, target, self.dt, 18)
            pygame.draw.rect(s, th.code_hl, (cr.x + 8, self.hl_y - 2, cr.w - 16, line_h), border_radius=5)
            pygame.draw.rect(s, th.accent, (cr.x + 8, self.hl_y - 2, 3, line_h), border_radius=2)
        for idx, line in enumerate(PSEUDOCODE):
            ly = y0 + idx * line_h
            num = self.f_code.render(str(idx + 1), True, lerp_color(th.dim, th.panel_bg, 0.5))
            s.blit(num, (cr.x + 18, ly))
            self.text(line, self.f_code, th.accent if idx == active else lerp_color(th.text, th.dim, 0.35),
                      cr.x + 40, ly)

        # --- complexity chips
        cx = x
        for c in ("best O(n)", "worst O(n²)", "memory O(1)", "stable"):
            cx += self.chip(c, cx, 494 + off, th.dim) + 6

        # --- controls as keycaps, two columns
        self.caps("controls", x, 530 + off, th.dim)
        if self.demo:
            rows = [((["SPACE"], "pause"), (["→"], "step")),
                    ((["+", "-"], "speed"), (["D"], "stop demo")),
                    ((["R"], "restart"), (["N"], "next level")),
                    ((["T"], "theme"), (["ESC"], "levels"))]
        else:
            rows = [((["↑", "↓"], "choose pair"), (["SPACE"], "swap")),
                    ((["D"], "watch demo"), (["R"], "restart")),
                    ((["N"], "next level"), (["T"], "theme")),
                    ((["ESC"], "levels"), (["CLICK"], "select / swap"))]
        for r_i, row in enumerate(rows):
            ry = 550 + off + r_i * 29
            for c_i, (keys, label) in enumerate(row):
                kx = x + c_i * (inner // 2)
                for key in keys:
                    kx += self.keycap(key, kx, ry) + 4
                img = self.f_small.render(label, True, th.text)
                s.blit(img, (kx + 4, ry + 1))

    def draw_result(self):
        """Result card: pops in with a springy scale, stars appear one by one."""
        s, th, age = self.screen, self.theme, self.result_age
        if age < 0.15:                       # let the last swap finish first
            return
        age -= 0.15
        card = pygame.Surface((420, 236), pygame.SRCALPHA)
        pygame.draw.rect(card, (*th.panel_bg, 252), card.get_rect(), border_radius=12)
        border = th.bad if self.result == "failed" else th.accent
        pygame.draw.rect(card, border, card.get_rect(), 3, border_radius=12)
        cx, y = card.get_width() // 2, 16
        bottom = card.get_height() - 30
        ct = self.center_text
        if self.result == "won":
            y = ct("Sorted!", self.f_big, th.accent, cx, y, card)
            for k in range(3):                # stars pop in one after another
                p = (age - 0.25 - k * 0.18) / 0.3
                if p <= 0:
                    continue
                sc = ease_out_back(min(1.0, p))
                full = k < self.earned
                img = self.f_big.render("★" if full else "☆", True, th.accent if full else th.dim)
                img = pygame.transform.smoothscale_by(img, max(0.05, sc))
                card.blit(img, img.get_rect(center=(cx + (k - 1) * 44, y + 20)))
            y += 46
            y = ct(f"{self.swaps} swaps (minimum: {self.opt_swaps})", self.f_mid, th.text, cx, y, card)
            if self.new_record:
                y = ct("New personal best!", self.f_small, th.good, cx, y, card)
            elif self.earned < 3:
                y = ct("Match the minimum for 3 stars.", self.f_small, th.dim, cx, y, card)
            if any(e.label for e in self.board.items):
                ok = self.board.is_stable()
                ct("Stable: twins kept their order (a, b, c)" if ok else "Not stable: the twins changed order!",
                   self.f_small, th.good if ok else th.bad, cx, y, card)
            nxt = "N next level   " if self.level_idx + 1 < len(LEVELS) else ""
            ct(nxt + "R again   ESC levels", self.f_small, th.dim, cx, bottom, card)
        elif self.result == "failed":
            y = ct("Not this time", self.f_big, th.bad, cx, y + 10, card)
            for line in self.wrap(self.fail_reason, 40):
                y = ct(line, self.f_mid, th.text, cx, y + 6, card)
            ct(f"Bubble Sort needs only {self.opt_swaps} swaps here.", self.f_small, th.dim, cx, y + 10, card)
            ct("R try again   D watch demo   ESC levels", self.f_small, th.dim, cx, bottom, card)
        else:
            y = ct("Demo finished", self.f_big, th.accent, cx, y + 10, card)
            y = ct(f"{self.opt_comps} comparisons, {self.opt_swaps} swaps", self.f_mid, th.text, cx, y + 6, card)
            ct("Now try it yourself!", self.f_mid, th.good, cx, y + 10, card)
            ct("R play   ESC levels", self.f_small, th.dim, cx, bottom, card)

        p = min(1.0, age / 0.4)
        center = (PANEL_X + (W - PANEL_X - 20) // 2, H // 2)   # over the panel, not the column
        veil = pygame.Surface((W - PANEL_X - 20, H - 40), pygame.SRCALPHA)
        pygame.draw.rect(veil, (0, 0, 0, int(110 * p)), veil.get_rect(), border_radius=14)
        s.blit(veil, (PANEL_X, 20))
        self.glow_rect(card.get_rect(center=center), border, p, 12)
        img = pygame.transform.smoothscale_by(card, max(0.05, ease_out_back(p)))
        img.set_alpha(int(255 * min(1.0, p * 2)))
        s.blit(img, img.get_rect(center=center))

if __name__ == "__main__":
    Game().run()
    pygame.quit()
