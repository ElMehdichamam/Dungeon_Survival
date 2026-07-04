"""systems/combat.py — pure geometry/combat helpers.

These functions do not own any state; the Game uses them to resolve hits and
compute knockback, then calls ``Entity.take_damage`` itself.
"""

import math


def distance(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def alive_targets(entities):
    return [e for e in entities if e.alive]


def nearest_in_range(x, y, entities, max_range):
    """Closest living entity within ``max_range`` of (x, y), or None."""
    best = None
    best_d = max_range
    for e in alive_targets(entities):
        d = distance(x, y, e.x, e.y)
        if d <= best_d:
            best_d = d
            best = e
    return best


def in_range(x, y, entities, max_range):
    """All living entities within ``max_range`` of (x, y)."""
    return [e for e in alive_targets(entities)
            if distance(x, y, e.x, e.y) <= max_range]


def knockback_vector(src_x, src_y, dst_x, dst_y, strength):
    """A velocity (px/sec) pushing the target away from the source."""
    dx, dy = dst_x - src_x, dst_y - src_y
    mag = math.hypot(dx, dy)
    if mag < 1e-6:
        return (0.0, -strength)        # degenerate: shove straight up
    return (dx / mag * strength, dy / mag * strength)
