"""
Weather: every theme changes the game a little, in levels with arrivals.

  Bubble Aquarium  CURRENTS     a current hits one pair (you see it coming)
                                and swaps it: it may help or hurt. Move one
                                of the two away to dodge it.
  Rain Garden      RAIN SHOWERS between showers new drops arrive 25% slower,
                                during a short shower twice as fast.
  Fire Pit         HEAT WAVES   numbers vanish in the shimmer (sizes still
                                show), but every surfacing scores double.

Each kind cycles through three phases: calm -> warning -> active -> calm.
A current has no active phase: it strikes at the end of the warning.
The game logic lives in baq.py; this file only holds the numbers and texts.
"""

WEATHER = {
    "aquarium": {
        "kind": "current", "name": "Currents", "icon": "wave", "color": (150, 225, 255),
        "calm": (11.0, 15.0), "warn": 2.6, "active": 0.0,
        "desc": "A current hits one pair now and then (waves warn you) and swaps it. "
                "It may help or hurt: move one of the two away to dodge it.",
        "short": "currents swap a pair",
        "labels": {"calm": "calm water", "warn": "current!"},
    },
    "garden": {
        "kind": "rain", "name": "Rain showers", "icon": "cloud", "color": (150, 195, 255),
        "calm": (12.0, 16.0), "warn": 3.0, "active": 5.0,
        "desc": "Between showers new drops arrive 25% slower; during a short "
                "shower they arrive twice as fast.",
        "short": "showers speed up arrivals",
        "labels": {"calm": "sunny", "warn": "clouds...", "active": "shower!"},
        "rate": {"calm": 0.75, "warn": 1.0, "active": 2.0},
    },
    "fire": {
        "kind": "heat", "name": "Heat waves", "icon": "flame", "color": (255, 150, 50),
        "calm": (12.0, 16.0), "warn": 2.5, "active": 8.0,
        "desc": "During a heat wave the numbers vanish in the shimmer (sizes "
                "still show), but every surfacing scores double.",
        "short": "heat hides numbers, ×2 points",
        "labels": {"calm": "embers", "warn": "heating up", "active": "heat wave!"},
    },
}
