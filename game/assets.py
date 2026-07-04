"""assets.py — loads every sprite sheet exactly once and slices it into frames.

A sheet is a grid of 4 rows (directions) x N columns (animation frames),
each cell FRAME_W x FRAME_H.  We keep the raw 64x64 frames in memory and
produce scaled / tinted variants on demand (cached), so a sheet is never
read from disk more than once.
"""

import os
import pygame

from . import settings as S


def apply_tint(surface, color):
    """Recolour a sprite to a distinct, vivid tint while keeping its shading.

    The PRD's draft (``copy().fill(color + (0,), BLEND_RGBA_MULT)``) had two
    problems: the trailing ``0`` multiplies alpha by zero (sprite vanishes),
    and a plain RGB multiply onto the green orc base can only darken it, so a
    "blue"/"red"/"purple" tint just comes out muddy green.

    Instead we desaturate to luminance (which preserves per-pixel alpha) and
    multiply the tint colour onto that, giving a shaded but clearly blue / red /
    purple variant — exactly the distinct enemy types the PRD asks for.
    """
    gray = pygame.transform.grayscale(surface)
    gray.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return gray


def _scale(surface, scale):
    if scale == 1:
        return surface
    w, h = surface.get_size()
    return pygame.transform.scale(surface, (w * scale, h * scale))


class AssetLoader:
    """Loads and caches all character sprite sheets."""

    def __init__(self):
        self._raw_player = self._load_sheets(S.PLAYER_SHEETS, S.PLAYER_ANIM_FRAMES)
        self._raw_enemy  = self._load_sheets(S.ENEMY_SHEETS,  S.ENEMY_ANIM_FRAMES)

        # caches keyed so we never rebuild the same variant twice
        self._player_cache = None                 # scaled player grids
        self._enemy_cache  = {}                    # (tint, scale) -> grids
        self._font_cache   = {}

    # ------------------------------------------------------------------ load
    def _load_sheets(self, sheet_map, frame_map):
        """Return {anim: grid} where grid[row][col] is a raw 64x64 Surface."""
        grids = {}
        for anim, filename in sheet_map.items():
            path = os.path.join(S.ASSET_DIR, filename)
            sheet = pygame.image.load(path).convert_alpha()
            cols = frame_map[anim]
            grids[anim] = self._slice(sheet, cols)
        return grids

    @staticmethod
    def _slice(sheet, cols):
        """Cut a sheet into [row][col] of FRAME_W x FRAME_H sub-surfaces."""
        grid = []
        for row in range(S.SHEET_ROWS):
            frames = []
            for col in range(cols):
                rect = pygame.Rect(col * S.FRAME_W, row * S.FRAME_H,
                                   S.FRAME_W, S.FRAME_H)
                frames.append(sheet.subsurface(rect).copy())
            grid.append(frames)
        return grid

    # ------------------------------------------------------------- variants
    def get_player_animations(self):
        """{anim: grid[dir][frame]} scaled for the player."""
        if self._player_cache is None:
            self._player_cache = {
                anim: [[_scale(f, S.SPRITE_SCALE) for f in row] for row in grid]
                for anim, grid in self._raw_player.items()
            }
        return self._player_cache

    def get_enemy_animations(self, tint_color=None, scale=S.SPRITE_SCALE):
        """{anim: grid[dir][frame]} scaled and optionally tinted for an enemy."""
        key = (tint_color, scale)
        cached = self._enemy_cache.get(key)
        if cached is None:
            cached = {}
            for anim, grid in self._raw_enemy.items():
                rows = []
                for row in grid:
                    frames = []
                    for f in row:
                        img = apply_tint(f, tint_color) if tint_color else f
                        frames.append(_scale(img, scale))
                    rows.append(frames)
                cached[anim] = rows
            self._enemy_cache[key] = cached
        return cached

    # ----------------------------------------------------------------- font
    def get_font(self, size, bold=False):
        key = (size, bold)
        font = self._font_cache.get(key)
        if font is None:
            font = pygame.font.Font(None, size)
            font.set_bold(bold)
            self._font_cache[key] = font
        return font
