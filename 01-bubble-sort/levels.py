"""
Level definitions.

Each level teaches one idea about Bubble Sort: the best case, the worst
case, early exit, stability, the exact minimum number of swaps, and so on.
"""

import random
from dataclasses import dataclass

VMAX = 12          # values go from 1 to VMAX


@dataclass
class Level:
    name: str
    n: int                       # number of elements
    kind: str                    # how the starting values are generated
    lesson: str                  # what the level teaches (shown in the menu and the panel)
    swap_limit: int | None = None   # extra swaps allowed above the minimum (None = unlimited)
    time_limit: int | None = None   # seconds (None = no clock)
    hidden: bool = False         # numbers hidden, only the size is visible


LEVELS = [
    Level("First Splash", 4, "random",
          "Swap neighbours until the biggest one is on top."),
    Level("Five in a Row", 5, "random",
          "Each pass carries the largest remaining element to the top."),
    Level("Almost There", 6, "nearly",
          "Best case: nearly sorted data needs only a few swaps."),
    Level("Sinking Stone", 6, "sinker",
          "The biggest one starts at the bottom: one full pass fixes it."),
    Level("Upside Down", 6, "reversed",
          "Worst case: reversed data needs n(n-1)/2 swaps."),
    Level("Twins", 7, "dupes",
          "Equal values are never swapped, so Bubble Sort is stable."),
    Level("Tight Budget", 7, "random",
          "No wasted moves allowed: use exactly the minimum.", swap_limit=0),
    Level("Against the Clock", 7, "random",
          "Sort before the time runs out.", time_limit=40),
    Level("Blindfold", 6, "spread",
          "Numbers are hidden: compare by size only.", hidden=True),
    Level("Big Tank", 9, "random",
          "More elements, more passes: O(n²) grows fast.", swap_limit=4),
    Level("Reverse Storm", 9, "reversed",
          "Worst case with a clock: 36 swaps, be quick!", time_limit=75),
    Level("Grand Master", 10, "random",
          "Ten elements, minimum swaps, against the clock.", swap_limit=0, time_limit=120),
]


def make_values(level, rng=random):
    """Starting values for a level (never already sorted)."""
    n = level.n
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
