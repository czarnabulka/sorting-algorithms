"""
BUBBLE AQUARIUM: a game that teaches Bubble Sort

Rules:
  The aquarium holds a column of numbered bubbles. Bigger bubbles want to
  float up to the surface. You may only swap TWO NEIGHBOURING bubbles,
  exactly like Bubble Sort does.
  Goal: order the bubbles from smallest (bottom) to largest (surface)
  using as few swaps as possible.

Controls:
  Up / Down  move the pointer (choose a pair of neighbours)
  SPACE      swap the selected pair
  D          DEMO mode: the algorithm sorts the same bubbles step by step
  + / -      demo speed
  R          restart the level
  N          next level (more bubbles)
  ESC        quit

Run:
  pip install pygame
  python bubble_aquarium.py
"""

import math
import random
import sys

import pygame

# ------------------------------------------------------------------ settings
W, H = 980, 720
FPS = 60
COL_X = 250            # x centre of the bubble column
BOTTOM = H - 80        # y of the lowest bubble
TOP = 110              # y of the highest bubble
PANEL_X = 480          # left edge of the info panel

WATER_TOP = (40, 140, 190)
WATER_BOTTOM = (8, 30, 70)
GOLD = (255, 205, 80)
WHITE = (240, 248, 255)
DIM = (150, 180, 210)
RED = (255, 110, 110)
GREEN = (120, 230, 150)
PANEL_BG = (12, 24, 48)


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
        yield ("pass_end", n - 1 - i, i)   # the largest remaining bubble reached the top
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


# Pseudocode shown in the panel; the active line lights up in DEMO mode.
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


# ------------------------------------------------------------------ graphics
class Bubble:
    def __init__(self, value, y):
        self.value = value
        self.y = y                 # current (animated) position
        self.phase = random.uniform(0, math.tau)


def make_water():
    """Water gradient, computed once and then just copied to the screen."""
    surf = pygame.Surface((W, H))
    for y in range(H):
        t = y / H
        c = [int(WATER_TOP[k] * (1 - t) + WATER_BOTTOM[k] * t) for k in range(3)]
        pygame.draw.line(surf, c, (0, y), (W, y))
    # light rays coming from the surface
    rays = pygame.Surface((W, H), pygame.SRCALPHA)
    for x0 in (60, 200, 340, 620, 820):
        pygame.draw.polygon(rays, (255, 255, 255, 14),
                            [(x0, 0), (x0 + 60, 0), (x0 + 160, H), (x0 + 40, H)])
    surf.blit(rays, (0, 0))
    return surf


def bubble_color(value, vmax):
    """Small bubble = teal, big bubble = pink/purple."""
    t = (value - 1) / max(1, vmax - 1)
    a, b = (90, 220, 230), (240, 110, 200)
    return tuple(int(a[k] * (1 - t) + b[k] * t) for k in range(3))


def draw_bubble(screen, font, x, y, r, value, vmax, ring=None):
    color = bubble_color(value, vmax)
    s = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
    c = r + 4
    pygame.draw.circle(s, (*color, 150), (c, c), r)                 # body
    pygame.draw.circle(s, (*WHITE, 220), (c, c), r, 2)              # outline
    pygame.draw.circle(s, (255, 255, 255, 170),                     # highlight
                       (c - r // 3, c - r // 3), max(3, r // 4))
    screen.blit(s, (x - c, y - c))
    if ring:
        pygame.draw.circle(screen, ring, (int(x), int(y)), r + 5, 3)
    txt = font.render(str(value), True, WHITE)
    screen.blit(txt, txt.get_rect(center=(x, y)))


# ---------------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Bubble Aquarium: Bubble Sort")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        fonts = "dejavusans,freesans,arial"
        self.f_big = pygame.font.SysFont(fonts, 34, bold=True)
        self.f_mid = pygame.font.SysFont(fonts, 20, bold=True)
        self.f_small = pygame.font.SysFont(fonts, 16)
        self.f_code = pygame.font.SysFont("dejavusansmono,monospace", 15)
        self.water = make_water()
        self.particles = [[random.uniform(0, W), random.uniform(0, H),
                           random.uniform(1, 3), random.uniform(20, 60)]
                          for _ in range(60)]
        self.level = 1
        self.demo_delay = 0.7      # seconds per DEMO step
        self.new_level()

    # --- levels ---
    def new_level(self):
        n = min(4 + self.level, 10)
        vals = random.sample(range(1, 13), n)
        while vals == sorted(vals):
            random.shuffle(vals)
        self.start_values = vals
        self.reset()

    def reset(self):
        self.bubbles = [Bubble(v, self.slot_y(i, len(self.start_values)))
                        for i, v in enumerate(self.start_values)]
        self.cursor = 0
        self.swaps = 0
        self.opt_comps, self.opt_swaps = count_stats(self.start_values)
        self.won = False
        self.demo = None           # step generator while DEMO is running
        self.demo_step = None
        self.demo_timer = 0.0
        self.sorted_from = len(self.start_values)   # everything from this index up is in place
        self.message = "Swap neighbouring bubbles. Big ones must float to the top!"

    # --- geometry ---
    @property
    def n(self):
        return len(self.bubbles)

    def slot_y(self, i, n):
        """Index 0 = bottom, index n-1 = surface."""
        step = (BOTTOM - TOP) / (n - 1)
        return BOTTOM - i * step

    def radius(self, value):
        step = (BOTTOM - TOP) / (self.n - 1)
        return int(step * 0.48 * (0.45 + 0.55 * value / 12))

    def values(self):
        return [b.value for b in self.bubbles]

    # --- actions ---
    def swap(self, j):
        self.bubbles[j], self.bubbles[j + 1] = self.bubbles[j + 1], self.bubbles[j]

    def player_swap(self):
        if self.won or self.demo:
            return
        a, b = self.bubbles[self.cursor].value, self.bubbles[self.cursor + 1].value
        self.swap(self.cursor)
        self.swaps += 1
        if a > b:
            self.message = f"Nice! {a} > {b}, so {a} floats up."
        else:
            self.message = f"Hmm, {a} < {b}: that swap breaks the order!"
        if self.values() == sorted(self.values()):
            self.won = True
            self.sorted_from = 0

    def toggle_demo(self):
        if self.demo:
            self.reset()
            return
        self.reset()
        self.demo = bubble_sort_steps(self.start_values)
        self.demo_timer = 0.0
        self.message = "DEMO: watch how the algorithm does it."

    def demo_advance(self):
        kind, j, i = self.demo_step = next(self.demo)
        v = self.values()
        if kind == "compare":
            self.cursor = j
            self.message = f"Pass {i + 1}: comparing {v[j]} and {v[j + 1]}"
        elif kind == "swap":
            self.swap(j)
            self.swaps += 1
            self.message = f"{v[j]} > {v[j + 1]} → swap! The bigger one floats up."
        elif kind == "keep":
            self.message = f"{v[j]} < {v[j + 1]} → leave them, the order is fine."
        elif kind == "pass_end":
            self.sorted_from = j
            self.message = f"End of pass {i + 1}: bubble {v[j]} is now in its final place."
        elif kind == "early":
            self.sorted_from = 0
            self.message = "A whole pass with no swaps → everything is sorted, done!"
        elif kind == "done":
            self.sorted_from = 0
            self.won = True
            self.demo = None

    # --- main loop ---
    def run(self):
        while True:
            dt = self.clock.tick(FPS) / 1000
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    return
                if e.type == pygame.KEYDOWN:
                    self.on_key(e)
            self.update(dt)
            self.draw()
            pygame.display.flip()

    def on_key(self, e):
        k = e.key
        if k == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        elif k == pygame.K_UP and not self.demo:
            self.cursor = min(self.cursor + 1, self.n - 2)
        elif k == pygame.K_DOWN and not self.demo:
            self.cursor = max(self.cursor - 1, 0)
        elif k == pygame.K_SPACE:
            self.player_swap()
        elif k == pygame.K_d:
            self.toggle_demo()
        elif k == pygame.K_r:
            self.reset()
        elif k == pygame.K_n:
            self.level += 1
            self.new_level()
        elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.demo_delay = max(0.1, self.demo_delay - 0.1)
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.demo_delay = min(2.0, self.demo_delay + 0.1)

    def update(self, dt):
        # bubbles glide smoothly to their slots (swap animation)
        for i, b in enumerate(self.bubbles):
            target = self.slot_y(i, self.n)
            b.y += (target - b.y) * min(1, dt * 10)
        # tiny background bubbles
        for p in self.particles:
            p[1] -= p[3] * dt
            p[0] += math.sin(p[1] / 30) * 0.3
            if p[1] < -5:
                p[0], p[1] = random.uniform(0, W), H + 5
        # DEMO: one algorithm step every demo_delay seconds
        if self.demo:
            self.demo_timer += dt
            if self.demo_timer >= self.demo_delay:
                self.demo_timer = 0
                self.demo_advance()

    # --- drawing ---
    def draw(self):
        s = self.screen
        s.blit(self.water, (0, 0))
        for x, y, r, _ in self.particles:
            pygame.draw.circle(s, (200, 230, 255), (int(x), int(y)), int(r), 1)

        # aquarium glass + sand at the bottom
        glass = pygame.Rect(COL_X - 110, TOP - 60, 220, BOTTOM - TOP + 120)
        pygame.draw.rect(s, (220, 240, 255), glass, 2, border_radius=14)
        pygame.draw.rect(s, (194, 170, 120),
                         (glass.x + 2, glass.bottom - 22, glass.w - 4, 20),
                         border_bottom_left_radius=12, border_bottom_right_radius=12)
        lbl = self.f_small.render("SURFACE ↑", True, DIM)
        s.blit(lbl, lbl.get_rect(center=(COL_X, TOP - 75)))

        t = pygame.time.get_ticks() / 1000
        vmax = 12

        # player's pointer, or the pair being compared in demo
        show_pair = not self.won and (not self.demo or (self.demo_step and
                                      self.demo_step[0] in ("compare", "swap", "keep")))
        if show_pair:
            j = self.cursor
            y1, y2 = self.slot_y(j, self.n), self.slot_y(j + 1, self.n)
            color = GOLD
            if self.demo_step and self.demo:
                color = {"swap": RED, "keep": GREEN}.get(self.demo_step[0], GOLD)
            box = pygame.Rect(COL_X - 80, y2 - 34, 160, y1 - y2 + 68)
            pygame.draw.rect(s, color, box, 3, border_radius=30)
            arrow = self.f_mid.render("◄", True, color)
            s.blit(arrow, arrow.get_rect(center=(COL_X + 100, (y1 + y2) / 2)))

        for i, b in enumerate(self.bubbles):
            x = COL_X + math.sin(t * 1.5 + b.phase) * 4
            ring = GOLD if i >= self.sorted_from else None
            draw_bubble(s, self.f_mid, x, b.y, self.radius(b.value), b.value, vmax, ring)

        self.draw_panel()
        if self.won:
            self.draw_win()

    def text(self, txt, font, color, x, y):
        img = font.render(txt, True, color)
        self.screen.blit(img, (x, y))
        return y + img.get_height() + 4

    def draw_panel(self):
        s = self.screen
        panel = pygame.Surface((W - PANEL_X - 20, H - 40), pygame.SRCALPHA)
        panel.fill((*PANEL_BG, 200))
        s.blit(panel, (PANEL_X, 20))
        x, y = PANEL_X + 20, 36

        y = self.text("Bubble Aquarium", self.f_big, WHITE, x, y)
        mode = "DEMO: the algorithm plays" if self.demo else f"Level {self.level} · {self.n} bubbles"
        y = self.text(mode, self.f_mid, GOLD, x, y) + 8

        y = self.text(f"Your swaps:  {self.swaps}", self.f_mid, WHITE, x, y)
        y = self.text(f"Minimum (what Bubble Sort does):  {self.opt_swaps}", self.f_small, DIM, x, y)
        y = self.text(f"Bubble Sort comparisons:  {self.opt_comps}", self.f_small, DIM, x, y) + 10

        # status message (wrapped)
        for line in self.wrap(self.message, 46):
            y = self.text(line, self.f_small, WHITE, x, y)
        y += 14

        # pseudocode with highlighting
        y = self.text("Pseudocode:", self.f_mid, WHITE, x, y)
        active = STEP_LINE.get(self.demo_step[0], -1) if (self.demo and self.demo_step) else -1
        for idx, line in enumerate(PSEUDOCODE):
            if idx == active:
                pygame.draw.rect(s, (70, 60, 20), (x - 6, y - 2, W - PANEL_X - 50, 21), border_radius=4)
            y = self.text(line, self.f_code, GOLD if idx == active else DIM, x, y)
        y += 14

        y = self.text("Time:  O(n²) worst/average,", self.f_small, WHITE, x, y)
        y = self.text("       O(n) when already sorted", self.f_small, WHITE, x, y)
        y = self.text("Memory:  O(1) · stable", self.f_small, WHITE, x, y) + 14

        keys = ["↑↓ choose pair   SPACE swap",
                "D demo   +/- demo speed",
                "R restart   N next level"]
        for k in keys:
            y = self.text(k, self.f_small, DIM, x, y)

    @staticmethod
    def wrap(txt, width):
        words, lines, cur = txt.split(), [], ""
        for w in words:
            if len(cur) + len(w) + 1 > width:
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        return lines + [cur]

    def draw_win(self):
        s = self.screen
        box = pygame.Rect(0, 0, 400, 190)
        box.center = (COL_X, H // 2)
        overlay = pygame.Surface(box.size, pygame.SRCALPHA)
        overlay.fill((10, 20, 40, 225))
        s.blit(overlay, box)
        pygame.draw.rect(s, GOLD, box, 3, border_radius=12)
        extra = self.swaps - self.opt_swaps
        stars = 3 if extra == 0 else 2 if extra <= 3 else 1
        lines = [("Sorted!", self.f_big, GOLD),
                 ("★" * stars + "☆" * (3 - stars), self.f_big, GOLD),
                 (f"{self.swaps} swaps (minimum: {self.opt_swaps})", self.f_mid, WHITE),
                 ("N = next level   R = play again", self.f_small, DIM)]
        y = box.y + 18
        for txt, f, c in lines:
            img = f.render(txt, True, c)
            s.blit(img, img.get_rect(midtop=(box.centerx, y)))
            y += img.get_height() + 8


if __name__ == "__main__":
    Game().run()
    pygame.quit()
