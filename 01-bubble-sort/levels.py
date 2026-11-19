"""
Level definitions.

The goal in every level is the same: SURFACE elements. The element on top of
the column leaves the tank ("surfaces") as soon as it is the biggest one in
the tank, exactly like the largest element reaches its final place at the
end of a Bubble Sort pass. Surfacing several in a row makes a CHAIN, and a
chain is only possible when the top of the column is already sorted.

Most levels also have ARRIVALS: a new element enters at the bottom every few
seconds. If it arrives while the tank is full, the tank overflows and the
level is lost. So you cannot fix inversions at random: you have to carry the
biggest element up, again and again, like Bubble Sort does.

Every level has three stars:
  1. clear the level (surface `goal` elements),
  2. make a chain of at least `chain`,
  3. never make a wrong swap (only swap when the lower element is bigger,
     the `if a[j] > a[j + 1]` line of Bubble Sort).
"""

import random
from dataclasses import dataclass

VMAX = 12          # values go from 1 to VMAX


@dataclass
class Level:
    name: str
    lesson: str                  # what the level teaches (shown on the map and in the panel)
    start: int                   # elements in the tank at the start
    kind: str                    # how the starting values are generated
    capacity: int                # slots in the tank
    goal: int | None             # elements to surface (None = endless)
    spawn: float | None = None   # seconds between arrivals (None = no arrivals)
    feed: str = "random"         # how arriving values are chosen
    chain: int = 2               # chain needed for the 2nd star
    strict: bool = False         # a wrong swap ends the level
    hidden: bool = False         # numbers hidden, only the size is visible
    speedup: float = 1.0         # arrival interval is multiplied by this after each arrival
    min_spawn: float = 1.8


LEVELS = [
    Level("First Splash",
          "The biggest one on top surfaces. Empty the tank!",
          start=4, kind="random", capacity=4, goal=4, chain=2),
    Level("Sinking Stone",
          "One pass carries the largest all the way up, and the rest follows.",
          start=6, kind="sinker", capacity=6, goal=6, chain=6),
    Level("Almost There",
          "Best case: nearly sorted data needs only a few swaps.",
          start=7, kind="nearly", capacity=7, goal=7, chain=7),
    Level("Upside Down",
          "Worst case: reversed data needs n(n-1)/2 swaps.",
          start=6, kind="reversed", capacity=6, goal=6, chain=3),
    Level("First Drops",
          "New ones arrive from below. Do not let the tank overflow!",
          start=4, kind="random", capacity=8, goal=8, spawn=7.0, chain=3),
    Level("Twins",
          "Equal values are never swapped: that keeps Bubble Sort stable.",
          start=6, kind="dupes", capacity=8, goal=9, spawn=7.0, feed="dupes", chain=3),
    Level("Clean Hands",
          "Swap only if the lower one is bigger. One wrong swap cracks the tank.",
          start=6, kind="random", capacity=8, goal=10, spawn=6.5, chain=3, strict=True),
    Level("Rising Tide",
          "Arrivals speed up. Keep carrying the biggest one up.",
          start=5, kind="random", capacity=8, goal=14, spawn=5.5, chain=4, speedup=0.97),
    Level("Blindfold",
          "Numbers are hidden: compare by size only.",
          start=5, kind="spread", capacity=8, goal=10, spawn=6.5, chain=3, hidden=True),
    Level("Pressure",
          "A small tank and a fast stream. Sort the top for big chains.",
          start=6, kind="random", capacity=7, goal=14, spawn=4.6, chain=4),
    Level("Reverse Storm",
          "Every newcomer is bigger than the last: each must cross the whole tank.",
          start=6, kind="reversed", capacity=9, goal=14, spawn=5.5, feed="rising", chain=4),
    Level("Grand Master",
          "Fast, strict and long. Only clean swaps, only big chains.",
          start=7, kind="random", capacity=9, goal=20, spawn=4.8, chain=5, strict=True,
          speedup=0.98),
]

ENDLESS = Level("Endless Tide",
                "Survive as long as you can. Arrivals keep getting faster.",
                start=5, kind="random", capacity=9, goal=None, spawn=5.0, chain=99,
                speedup=0.97, min_spawn=1.2)


def make_values(level, rng=random):
    """Starting values for a level (never already sorted)."""
    n = level.start
    while True:
        if level.kind == "random":
            vals = rng.sample(range(1, VMAX + 1), n)
        elif level.kind == "nearly":
            vals = sorted(rng.sample(range(1, VMAX + 1), n))
            for _ in range(2):
                j = rng.randrange(n - 1)
                vals[j], vals[j + 1] = vals[j + 1], vals[j]
        elif level.kind == "sinker":
            vals = sorted(rng.sample(range(1, VMAX + 1), n))
            vals = [vals[-1]] + vals[:-1]
        elif level.kind == "reversed":
            vals = sorted(rng.sample(range(1, VMAX + 1), n), reverse=True)
        elif level.kind == "dupes":
            pool = rng.sample(range(2, VMAX + 1), n - 3)
            twins = rng.sample(pool, 2)
            vals = pool + twins + [twins[0]]
            rng.shuffle(vals)
        elif level.kind == "spread":
            vals = rng.sample(range(2, VMAX + 1, 2), n)
        else:
            raise ValueError(level.kind)
        if vals != sorted(vals):
            return vals


class Feed:
    """Values of the elements that arrive during a level."""

    def __init__(self, level, rng=random):
        self.level, self.rng = level, rng
        self.last = rng.randint(1, 4)

    def next(self, present):
        """A new value; `present` = values already in the tank or the queue."""
        kind, rng = self.level.feed, self.rng
        if kind == "rising":                     # 2, 4, 6, ... then wrap around
            self.last = self.last + rng.randint(1, 3)
            if self.last > VMAX:
                self.last = rng.randint(1, 3)
            return self.last
        if kind == "dupes" and present and rng.random() < 0.45:
            return rng.choice(present)           # a twin of something already here
        choices = [v for v in range(1, VMAX + 1) if v not in present] or list(range(1, VMAX + 1))
        if self.level.hidden:                    # bigger steps between sizes
            choices = [v for v in choices if v % 2 == 0] or choices
        return rng.choice(choices)
