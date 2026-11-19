"""
Fonts: every theme has its own typefaces.

  Bubble Aquarium  Fredoka (round, soft, bubbly)
  Rain Garden      Caveat Brush (hand-painted garden sign) + Nunito
  Fire Pit         Bungee (bold signage) + Barlow Semi Condensed
  pseudocode       JetBrains Mono (all themes)

The .ttf files live in fonts/ (SIL Open Font License, see fonts/OFL.txt).
Display fonts do not have arrows or stars, so every Font falls back to
DejaVu Sans for the characters its main face is missing.
"""

import os

import pygame
import pygame.freetype

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FALLBACK = "dejavusans,freesans,arial"
MONO = "JetBrainsMono-Medium.ttf"

# role -> (file, size multiplier). Sizes are tuned so every theme fills the
# same boxes: Bungee is wide, Caveat Brush is small for its point size.
SPECS = {
    "aquarium": {"display": ("Fredoka-Bold.ttf", 1.0), "head": ("Fredoka-Bold.ttf", 1.0),
                 "ui": ("Fredoka-Medium.ttf", 1.0), "bold": ("Fredoka-Bold.ttf", 1.0),
                 "num": ("Fredoka-Bold.ttf", 1.05), "caps": ("Fredoka-Bold.ttf", 1.0)},
    "garden": {"display": ("CaveatBrush-Regular.ttf", 1.22), "head": ("CaveatBrush-Regular.ttf", 1.2),
               "ui": ("Nunito-Bold.ttf", 1.0), "bold": ("Nunito-Black.ttf", 1.0),
               "num": ("Nunito-Black.ttf", 1.0), "caps": ("Nunito-Black.ttf", 0.95)},
    "fire": {"display": ("Bungee-Regular.ttf", 0.82), "head": ("Bungee-Regular.ttf", 0.78),
             "ui": ("BarlowSemiCondensed-SemiBold.ttf", 1.1), "bold": ("BarlowSemiCondensed-Bold.ttf", 1.12),
             "num": ("Bungee-Regular.ttf", 0.8), "caps": ("BarlowSemiCondensed-Bold.ttf", 1.1)},
}

# game role -> (spec role, base size)
ROLES = {
    "title": ("display", 58), "big": ("head", 36), "head": ("head", 28),
    "mid": ("bold", 20), "small": ("ui", 16), "tiny": ("caps", 12),
    "value": ("num", 27), "elem": ("num", 21), "code": (None, 14),
}


class Font:
    """pygame.font.Font with a fallback face for missing glyphs."""

    def __init__(self, filename, size):
        path = os.path.join(FONT_DIR, filename)
        try:
            self.main = pygame.font.Font(path, size)
            self.probe = pygame.freetype.Font(path, size)
        except (OSError, FileNotFoundError, pygame.error):
            self.main = pygame.font.SysFont(FALLBACK, size, bold=True)
            self.probe = None
        self.fallback = pygame.font.SysFont(FALLBACK, max(8, int(size * 0.9)), bold=True)
        self.known = {}

    def has(self, ch):
        if self.probe is None or ch == " ":
            return True
        ok = self.known.get(ch)
        if ok is None:
            ok = self.known[ch] = self.probe.get_metrics(ch)[0] is not None
        return ok

    def runs(self, text):
        out = []
        for ch in text:
            f = self.main if self.has(ch) else self.fallback
            if out and out[-1][0] is f:
                out[-1][1] += ch
            else:
                out.append([f, ch])
        return out

    def render(self, text, aa=True, color=(255, 255, 255)):
        runs = self.runs(text)
        if len(runs) <= 1:
            return (runs[0][0] if runs else self.main).render(text, aa, color)
        imgs = [(f, f.render(t, aa, color)) for f, t in runs]
        asc = self.main.get_ascent()
        h = max(self.main.get_height(), *(asc - f.get_ascent() + i.get_height() for f, i in imgs))
        surf = pygame.Surface((sum(i.get_width() for _, i in imgs), h), pygame.SRCALPHA)
        x = 0
        for f, img in imgs:
            surf.blit(img, (x, asc - f.get_ascent()))
            x += img.get_width()
        return surf

    def size(self, text):
        return self.render(text).get_size()

    def get_height(self):
        return self.main.get_height()


def load_fontsets(theme_keys):
    """{theme key: {game role: Font}}"""
    pygame.freetype.init()
    sets = {}
    mono = {}
    for key in theme_keys:
        spec = SPECS.get(key, SPECS["aquarium"])
        fs = {}
        for role, (srole, size) in ROLES.items():
            if srole is None:
                fs[role] = mono.setdefault(size, Font(MONO, size))
            else:
                fname, k = spec[srole]
                fs[role] = Font(fname, int(round(size * k)))
        sets[key] = fs
    return sets
