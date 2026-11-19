"""
Visual themes for the Bubble Sort game.

Every theme draws the same things in its own style:
  * the background (gradient + ambient particles such as rain or embers),
  * the container that holds the column of elements,
  * a single element (bubble / raindrop / fireball),
  * a short "burst" effect when two elements are swapped.

The game logic never cares which theme is active: it only calls the methods
of the Theme base class below.
"""

import math
import random
from functools import lru_cache

import pygame

W, H = 980, 720


# ----------------------------------------------------------------- helpers
def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(lerp(c1[k], c2[k], t)) for k in range(3))


def gradient_color(stops, t):
    """Colour from a list of stops, t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    seg = t * (len(stops) - 1)
    k = min(int(seg), len(stops) - 2)
    return lerp_color(stops[k], stops[k + 1], seg - k)


def vertical_gradient(top, bottom, size=(W, H)):
    w, h = size
    surf = pygame.Surface(size)
    for y in range(h):
        pygame.draw.line(surf, lerp_color(top, bottom, y / h), (0, y), (w, y))
    return surf


def text_outlined(screen, font, txt, center, color, outline=(0, 0, 0), width=2):
    """Text with a dark outline, readable on any background."""
    base = font.render(txt, True, outline)
    rect = base.get_rect(center=center)
    for dx in (-width, 0, width):
        for dy in (-width, 0, width):
            if dx or dy:
                screen.blit(base, rect.move(dx, dy))
    screen.blit(font.render(txt, True, color), rect)


@lru_cache(maxsize=512)
def soft_glow(radius, color, strength=90):
    """A radial glow: concentric circles with growing transparency (cached)."""
    surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    steps = 12
    for k in range(steps):
        r = int(radius * (1 - k / steps))
        a = int(strength * (k + 1) / steps / 3)
        pygame.draw.circle(surf, (*color, a), (radius, radius), r)
    return surf


def leaf_points(cx, cy, length, width, angle):
    """Points of a leaf (pointed ellipse) rotated by angle (radians)."""
    pts = []
    for k in range(17):
        u = k / 16 * math.pi
        px = math.cos(u) * length / 2
        py = math.sin(u) ** 1.3 * width / 2
        pts.append((px, py))
    pts += [(px, -py) for px, py in reversed(pts[1:-1])]
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + px * ca - py * sa, cy + px * sa + py * ca) for px, py in pts]


_SMALL = None


def small_font():
    global _SMALL
    if _SMALL is None:
        _SMALL = pygame.font.SysFont("dejavusans,freesans,arial", 13, bold=True)
    return _SMALL


class Spark:
    """Generic short-lived particle used for swap bursts."""
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "gravity")

    def __init__(self, x, y, vx, vy, life, color, size, gravity):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.gravity = color, size, gravity


# -------------------------------------------------------------- base class
class Theme:
    key = "base"
    title = "Sorting"
    tagline = ""
    up_label = "TOP ↑"
    noun = "element"          # singular, used in messages
    nouns = "elements"
    rise_verb = "floats up"

    accent = (255, 205, 80)   # gold: pointer, sorted ring, highlights
    text = (240, 248, 255)
    dim = (150, 180, 210)
    panel_bg = (12, 24, 48)
    good = (120, 230, 150)
    bad = (255, 110, 110)
    code_hl = (70, 60, 20)

    def __init__(self):
        self.bg = self.make_background()
        self.sparks = []
        self.init_ambient()

    # --- to override ---
    def make_background(self):
        return vertical_gradient((40, 40, 40), (0, 0, 0))

    def init_ambient(self):
        pass

    def update_ambient(self, dt, t):
        pass

    def draw_ambient(self, s, t):
        pass

    def draw_container(self, s, rect, t):
        pygame.draw.rect(s, self.text, rect, 2, border_radius=14)

    def element_color(self, value, vmax):
        return (200, 200, 200)

    def draw_element(self, s, font, x, y, r, value, vmax, t, ring=None, label="", phase=0.0, hidden=False):
        raise NotImplementedError

    def burst_colors(self):
        return [self.text]

    burst_gravity = 0.0

    # --- shared ---
    def update(self, dt, t):
        self.update_ambient(dt, t)
        for p in self.sparks:
            p.life -= dt
            p.vy += p.gravity * dt
            p.x += p.vx * dt
            p.y += p.vy * dt
        self.sparks = [p for p in self.sparks if p.life > 0]

    def draw_background(self, s, t):
        s.blit(self.bg, (0, 0))
        self.draw_ambient(s, t)

    def draw_sparks(self, s):
        for p in self.sparks:
            k = p.life / p.max_life
            r = max(1, int(p.size * (0.4 + 0.6 * k)))
            surf = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (*p.color, int(255 * k)), (r + 1, r + 1), r)
            s.blit(surf, (p.x - r - 1, p.y - r - 1))

    def burst(self, x, y, amount=14):
        colors = self.burst_colors()
        for _ in range(amount):
            a = random.uniform(0, math.tau)
            v = random.uniform(40, 170)
            self.sparks.append(Spark(x, y, math.cos(a) * v, math.sin(a) * v,
                                     random.uniform(0.35, 0.8), random.choice(colors),
                                     random.uniform(2, 5), self.burst_gravity))

    def draw_label(self, s, font, value, label, x, y, hidden):
        if hidden:
            text_outlined(s, font, "?", (x, y), self.text, (20, 20, 30))
            return
        text_outlined(s, font, str(value), (x, y), self.text, (20, 20, 30))
        if label:
            text_outlined(s, small_font(), label, (x + 13, y + 11), self.accent, (20, 20, 30), 1)


# ---------------------------------------------------------------- aquarium
class AquariumTheme(Theme):
    key = "aquarium"
    title = "Bubble Aquarium"
    tagline = "Big bubbles float up to the surface"
    up_label = "SURFACE ↑"
    noun, nouns = "bubble", "bubbles"
    rise_verb = "floats up"
    panel_bg = (12, 24, 48)
    burst_gravity = -60

    def make_background(self):
        surf = vertical_gradient((40, 140, 190), (8, 30, 70))
        rays = pygame.Surface((W, H), pygame.SRCALPHA)
        for x0 in (60, 200, 340, 620, 820):
            pygame.draw.polygon(rays, (255, 255, 255, 14),
                                [(x0, 0), (x0 + 60, 0), (x0 + 160, H), (x0 + 40, H)])
        surf.blit(rays, (0, 0))
        return surf

    def init_ambient(self):
        self.particles = [[random.uniform(0, W), random.uniform(0, H),
                           random.uniform(1, 3), random.uniform(20, 60)] for _ in range(60)]
        self.weeds = [(x, random.uniform(60, 140), random.uniform(0, math.tau))
                      for x in range(20, W, 37)]

    def update_ambient(self, dt, t):
        for p in self.particles:
            p[1] -= p[3] * dt
            p[0] += math.sin(p[1] / 30) * 0.3
            if p[1] < -5:
                p[0], p[1] = random.uniform(0, W), H + 5

    def draw_ambient(self, s, t):
        for x, y, r, _ in self.particles:
            pygame.draw.circle(s, (200, 230, 255), (int(x), int(y)), int(r), 1)
        for x, h, ph in self.weeds:            # swaying seaweed
            pts = []
            for k in range(9):
                f = k / 8
                pts.append((x + math.sin(t * 1.3 + ph + f * 3) * 10 * f, H - f * h))
            pygame.draw.lines(s, (30, 110, 80), False, pts, 4)

    def draw_container(self, s, rect, t):
        pygame.draw.rect(s, (220, 240, 255), rect, 2, border_radius=14)
        pygame.draw.rect(s, (194, 170, 120),
                         (rect.x + 2, rect.bottom - 22, rect.w - 4, 20),
                         border_bottom_left_radius=12, border_bottom_right_radius=12)

    def element_color(self, value, vmax):
        return lerp_color((90, 220, 230), (240, 110, 200), (value - 1) / max(1, vmax - 1))

    def draw_element(self, s, font, x, y, r, value, vmax, t, ring=None, label="", phase=0.0, hidden=False):
        color = self.element_color(value, vmax)
        surf = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        c = r + 4
        pygame.draw.circle(surf, (*color, 150), (c, c), r)
        pygame.draw.circle(surf, (*self.text, 220), (c, c), r, 2)
        pygame.draw.circle(surf, (255, 255, 255, 170), (c - r // 3, c - r // 3), max(3, r // 4))
        s.blit(surf, (x - c, y - c))
        if ring:
            pygame.draw.circle(s, ring, (int(x), int(y)), r + 5, 3)
        self.draw_label(s, font, value, label, x, y, hidden)

    def burst_colors(self):
        return [(220, 240, 255), (170, 220, 255)]


# ------------------------------------------------------------- rain garden
class GardenTheme(Theme):
    key = "garden"
    title = "Rain Garden"
    tagline = "Heavy raindrops climb the vine towards the sun"
    up_label = "SUNLIGHT ↑"
    noun, nouns = "drop", "drops"
    rise_verb = "climbs up"
    accent = (255, 222, 100)
    text = (240, 255, 240)
    dim = (160, 200, 170)
    panel_bg = (12, 34, 24)
    code_hl = (60, 70, 25)
    burst_gravity = 380

    GROUND = H - 34

    def make_background(self):
        surf = vertical_gradient((46, 78, 70), (10, 30, 22))
        # soft sun glow at the top
        surf.blit(soft_glow(260, (255, 240, 170), 70), (250 - 260, -200))
        # big background leaves
        layer = pygame.Surface((W, H), pygame.SRCALPHA)
        rng = random.Random(7)
        for _ in range(26):
            cx, cy = rng.uniform(-40, W + 40), rng.uniform(H * 0.25, H + 40)
            ln = rng.uniform(120, 260)
            col = (rng.randint(20, 45), rng.randint(70, 110), rng.randint(45, 70), 120)
            pts = leaf_points(cx, cy, ln, ln * 0.38, rng.uniform(-2.6, -0.5))
            pygame.draw.polygon(layer, col, pts)
            pygame.draw.line(layer, (90, 140, 100, 90), pts[0], pts[16], 2)
        surf.blit(layer, (0, 0))
        # soil
        pygame.draw.rect(surf, (48, 34, 24), (0, self.GROUND, W, H - self.GROUND))
        for _ in range(140):
            pygame.draw.circle(surf, (70, 50, 34),
                               (rng.randint(0, W), rng.randint(self.GROUND + 4, H)), rng.randint(1, 3))
        return surf

    def init_ambient(self):
        self.rain = [self.new_drop(random.uniform(0, H)) for _ in range(140)]
        self.ripples = []
        self.blades = [(x + random.uniform(-6, 6), random.uniform(18, 46), random.uniform(0, math.tau))
                       for x in range(0, W, 9)]

    @staticmethod
    def new_drop(y=None):
        return [random.uniform(-100, W), -20 if y is None else y,
                random.uniform(420, 700), random.uniform(10, 22)]

    def update_ambient(self, dt, t):
        for d in self.rain:
            d[1] += d[2] * dt
            d[0] += d[2] * 0.18 * dt
            if d[1] > self.GROUND + random.uniform(-6, 10):
                if random.random() < 0.5:
                    self.ripples.append([d[0], d[1], 0.0])
                d[:] = self.new_drop()
        for r in self.ripples:
            r[2] += dt
        self.ripples = [r for r in self.ripples if r[2] < 0.45]

    def draw_ambient(self, s, t):
        if not hasattr(self, "_layer"):
            self._layer = pygame.Surface((W, H), pygame.SRCALPHA)
        rain = self._layer
        rain.fill((0, 0, 0, 0))
        for x, y, v, ln in self.rain:
            pygame.draw.line(rain, (190, 230, 255, 110), (x, y), (x - ln * 0.18, y - ln), 1)
        for x, y, age in self.ripples:
            k = age / 0.45
            w = int(6 + 26 * k)
            pygame.draw.ellipse(rain, (200, 235, 255, int(160 * (1 - k))),
                                (x - w / 2, y - w / 8, w, w / 4), 1)
        s.blit(rain, (0, 0))
        for x, h, ph in self.blades:            # grass swaying in the wind
            sway = math.sin(t * 2 + ph) * 6
            pygame.draw.polygon(s, (60, 140, 70),
                                [(x - 3, self.GROUND + 4), (x + 3, self.GROUND + 4),
                                 (x + sway, self.GROUND - h)])

    def draw_container(self, s, rect, t):
        # a trellis frame with a vine growing up the middle
        frame = pygame.Surface(rect.size, pygame.SRCALPHA)
        frame.fill((20, 50, 30, 70))
        s.blit(frame, rect)
        pygame.draw.rect(s, (120, 90, 60), rect, 4, border_radius=10)
        for yy in range(rect.y + 40, rect.bottom, 60):
            pygame.draw.line(s, (100, 75, 50), (rect.x + 4, yy), (rect.right - 4, yy), 2)
        cx = rect.centerx
        pts = [(cx + math.sin(yy / 45 + t * 0.6) * 14, yy)
               for yy in range(rect.bottom - 6, rect.y + 6, -8)]
        pygame.draw.lines(s, (50, 120, 50), False, pts, 6)
        for k, (px, py) in enumerate(pts[3::5]):
            side = 1 if k % 2 else -1
            pygame.draw.polygon(s, (70, 160, 70),
                                leaf_points(px + side * 22, py, 44, 18, -0.4 * side + (0 if side > 0 else math.pi)))
        # flower pot / soil at the bottom
        pygame.draw.rect(s, (150, 80, 50), (rect.x + 20, rect.bottom - 26, rect.w - 40, 24),
                         border_radius=6)

    def element_color(self, value, vmax):
        return gradient_color([(175, 240, 140), (80, 200, 170), (40, 120, 210)],
                              (value - 1) / max(1, vmax - 1))

    def draw_element(self, s, font, x, y, r, value, vmax, t, ring=None, label="", phase=0.0, hidden=False):
        r = int(r * 0.82)          # the tip makes drops taller than bubbles
        color = self.element_color(value, vmax)
        # teardrop: a circle + a tip pointing up
        size = (int(r * 2 + 10), int(r * 2.7 + 10))
        surf = pygame.Surface(size, pygame.SRCALPHA)
        cx, cy = size[0] / 2, size[1] - r - 5
        d = r * 1.55
        alpha = math.acos(r / d)
        phi = -math.pi / 2
        pts = [(cx, cy - d)]
        for k in range(25):
            a = phi + alpha + (math.tau - 2 * alpha) * k / 24
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        pygame.draw.polygon(surf, (*color, 175), pts)
        pygame.draw.polygon(surf, (*self.text, 220), pts, 2)
        pygame.draw.ellipse(surf, (255, 255, 255, 170),
                            (cx - r * 0.55, cy - r * 0.6, r * 0.38, r * 0.6))
        oy = y + r * 0.15
        s.blit(surf, (x - cx, oy - cy))
        if ring:
            pygame.draw.circle(s, ring, (int(x), int(oy)), r + 5, 3)
        self.draw_label(s, font, value, label, x, oy, hidden)

    def burst_colors(self):
        return [(180, 230, 255), (140, 220, 170), (230, 255, 230)]


# ------------------------------------------------------------------ fire pit
class FireTheme(Theme):
    key = "fire"
    title = "Fire Pit"
    tagline = "The hottest fireballs rise to the top of the chimney"
    up_label = "HOT AIR ↑"
    noun, nouns = "fireball", "fireballs"
    rise_verb = "rises"
    accent = (255, 215, 90)
    text = (255, 246, 230)
    dim = (220, 160, 130)
    panel_bg = (34, 10, 8)
    code_hl = (90, 40, 10)
    good = (170, 230, 110)
    bad = (120, 180, 255)
    burst_gravity = -200

    def make_background(self):
        surf = vertical_gradient((18, 6, 12), (80, 18, 6))
        surf.blit(soft_glow(420, (255, 110, 30), 120), (W / 2 - 420, H - 300))
        # dark rock silhouettes
        rng = random.Random(3)
        x = 0
        pts = [(0, H)]
        while x < W:
            pts.append((x, H - 70 - rng.uniform(0, 50)))
            x += rng.uniform(30, 80)
        pts += [(W, H - 80), (W, H)]
        pygame.draw.polygon(surf, (30, 12, 10), pts)
        return surf

    def init_ambient(self):
        self.embers = [self.new_ember(random.uniform(0, H)) for _ in range(90)]
        self.tongues = [(x, random.uniform(40, 90), random.uniform(0, math.tau), random.uniform(3, 6))
                        for x in range(0, W + 40, 34)]

    @staticmethod
    def new_ember(y=None):
        return [random.uniform(0, W), H + 5 if y is None else y,
                random.uniform(40, 120), random.uniform(1.5, 3.5), random.uniform(0, math.tau)]

    def update_ambient(self, dt, t):
        for e in self.embers:
            e[1] -= e[2] * dt
            e[0] += math.sin(t * 2 + e[4]) * 20 * dt
            if e[1] < -5:
                e[:] = self.new_ember()

    def draw_ambient(self, s, t):
        if not hasattr(self, "_layer"):
            self._layer = pygame.Surface((W, H), pygame.SRCALPHA)
        layer = self._layer
        layer.fill((0, 0, 0, 0))
        for x, y, v, size, ph in self.embers:
            k = max(0.0, min(1.0, y / H))
            col = gradient_color([(255, 70, 30), (255, 160, 40), (255, 240, 150)], k)
            pygame.draw.circle(layer, (*col, int(80 + 175 * k)), (int(x), int(y)), int(size))
        s.blit(layer, (0, 0))
        self.draw_flames(s, t)

    def draw_flames(self, s, t):
        layers = [((200, 40, 20), 1.0, 1.0), ((255, 120, 30), 0.7, 0.72), ((255, 220, 90), 0.42, 0.45)]
        for col, wk, hk in layers:
            for x, h, ph, sp in self.tongues:
                hh = h * hk * (0.75 + 0.25 * math.sin(t * sp + ph) + 0.1 * math.sin(t * 13 + ph * 3))
                w = 26 * wk
                sway = math.sin(t * 3 + ph) * 8
                pygame.draw.polygon(s, col, [(x - w, H), (x - w * 0.6, H - hh * 0.45),
                                             (x + sway, H - hh), (x + w * 0.6, H - hh * 0.45), (x + w, H)])

    def draw_container(self, s, rect, t):
        # a stone chimney with glowing coals at the bottom
        inner = pygame.Surface(rect.size, pygame.SRCALPHA)
        inner.fill((10, 4, 4, 120))
        s.blit(inner, rect)
        stone = (95, 70, 62)
        pygame.draw.rect(s, stone, rect, 5, border_radius=8)
        for yy in range(rect.y + 30, rect.bottom - 20, 44):
            for side in (rect.x - 10, rect.right - 2):
                pygame.draw.rect(s, (70, 50, 44), (side, yy, 12, 26), border_radius=3)
        for k in range(9):
            cx = rect.x + 18 + k * (rect.w - 36) / 8
            glow = 0.6 + 0.4 * math.sin(t * 4 + k * 1.7)
            pygame.draw.ellipse(s, lerp_color((120, 20, 10), (255, 140, 40), glow),
                                (cx - 14, rect.bottom - 26, 28, 16))

    def element_color(self, value, vmax):
        return gradient_color([(210, 50, 30), (255, 140, 30), (255, 235, 140)],
                              (value - 1) / max(1, vmax - 1))

    def draw_element(self, s, font, x, y, r, value, vmax, t, ring=None, label="", phase=0.0, hidden=False):
        color = self.element_color(value, vmax)
        g = int(r * 1.9)
        s.blit(soft_glow(g, color, 110), (x - g, y - g))
        # flickering flame tail above the ball
        f1 = math.sin(t * 9 + phase) * r * 0.25
        f2 = math.sin(t * 7 + phase * 2) * r * 0.25
        tail = [(x - r * 0.95, y), (x - r * 0.55 + f1, y - r * 1.35), (x - r * 0.1, y - r * 0.95),
                (x + r * 0.15 + f2, y - r * 1.85), (x + r * 0.45, y - r * 1.0),
                (x + r * 0.7 + f1, y - r * 1.3), (x + r * 0.95, y)]
        pygame.draw.polygon(s, lerp_color(color, (200, 40, 20), 0.4), tail)
        pygame.draw.circle(s, color, (int(x), int(y)), r)
        pygame.draw.circle(s, lerp_color(color, (255, 255, 220), 0.5),
                           (int(x - r * 0.12), int(y - r * 0.12)), int(r * 0.62))
        if ring:
            pygame.draw.circle(s, ring, (int(x), int(y)), r + 6, 3)
        self.draw_label(s, font, value, label, x, y, hidden)

    def burst_colors(self):
        return [(255, 220, 90), (255, 140, 30), (255, 80, 30)]


THEMES = [AquariumTheme, GardenTheme, FireTheme]
