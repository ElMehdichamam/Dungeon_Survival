"""camera.py — converts world coordinates to screen coordinates.

The camera follows a target (the player) and clamps to the map bounds so we
never scroll past the edge of the world.  If the map is smaller than the
screen on an axis, the map is centred on that axis instead.
"""

import pygame


class Camera:
    def __init__(self, map_w, map_h, screen_w, screen_h):
        self.map_w, self.map_h = map_w, map_h
        self.screen_w, self.screen_h = screen_w, screen_h
        self.x = 0
        self.y = 0

    def update(self, target_x, target_y):
        self.x = self._clamp(int(target_x - self.screen_w // 2),
                             self.map_w, self.screen_w)
        self.y = self._clamp(int(target_y - self.screen_h // 2),
                             self.map_h, self.screen_h)

    @staticmethod
    def _clamp(value, map_size, screen_size):
        if map_size <= screen_size:
            # map smaller than the viewport on this axis -> centre it
            return (map_size - screen_size) // 2
        return max(0, min(value, map_size - screen_size))

    def to_screen(self, world_x, world_y):
        return world_x - self.x, world_y - self.y

    def apply(self, rect):
        return pygame.Rect(rect.x - self.x, rect.y - self.y,
                           rect.width, rect.height)

    @property
    def view_rect(self):
        """The slice of the world currently visible (world coordinates)."""
        return pygame.Rect(self.x, self.y, self.screen_w, self.screen_h)
