"""map.py — loads the Tiled map, renders it, and handles collision.

The supplied Dungeon1.tmx is stored as an *infinite* (chunked) map even
though its header says ``infinite="0"``.  pytmx cannot read chunked data, so
on load we flatten the chunks into a normal finite .tmx (cached next to the
source) and hand that to pytmx.

Collision is tile based: a tile is solid if it is on the Walls layer OR is not
part of the reachable dungeon floor.  We flood-fill the floor from the centre
so the player and enemies are confined to one connected arena and can never
wander into the black void around the dungeon.
"""

import os
import random
import xml.etree.ElementTree as ET
from collections import deque

import pygame
import pytmx

from . import settings as S


# --------------------------------------------------------------------------
# TMX flattening (chunked / "infinite" -> finite)
# --------------------------------------------------------------------------
def _flatten_tmx(src_path):
    """Convert a chunked .tmx into a finite one and return the new path.

    Returns ``src_path`` unchanged if the map has no chunks.  The flattened
    file is cached and only rebuilt when the source is newer.
    """
    tree = ET.parse(src_path)
    root = tree.getroot()

    has_chunks = any(layer.find("data").findall("chunk")
                     for layer in root.findall("layer"))
    if not has_chunks:
        return src_path

    stem, ext = os.path.splitext(src_path)
    dst_path = f"{stem}_flat{ext}"
    if os.path.exists(dst_path) and \
            os.path.getmtime(dst_path) >= os.path.getmtime(src_path):
        return dst_path

    # global tile bounding box across every layer's chunks
    minx = miny = 10 ** 9
    maxx = maxy = -10 ** 9
    for layer in root.findall("layer"):
        for ch in layer.find("data").findall("chunk"):
            cx, cy = int(ch.get("x")), int(ch.get("y"))
            cw, chh = int(ch.get("width")), int(ch.get("height"))
            minx, miny = min(minx, cx), min(miny, cy)
            maxx, maxy = max(maxx, cx + cw - 1), max(maxy, cy + chh - 1)

    width, height = maxx - minx + 1, maxy - miny + 1
    root.set("width", str(width))
    root.set("height", str(height))
    root.set("infinite", "0")

    for layer in root.findall("layer"):
        layer.set("width", str(width))
        layer.set("height", str(height))
        data = layer.find("data")
        grid = [[0] * width for _ in range(height)]
        for ch in data.findall("chunk"):
            cx, cy, cw = int(ch.get("x")), int(ch.get("y")), int(ch.get("width"))
            values = [int(v) for v in ch.text.replace("\n", "").split(",")
                      if v.strip() != ""]
            for i, gid in enumerate(values):
                gx = cx + (i % cw) - minx
                gy = cy + (i // cw) - miny
                grid[gy][gx] = gid
            data.remove(ch)
        data.set("encoding", "csv")
        data.text = "\n" + ",".join(str(g) for row in grid for g in row) + "\n"

    tree.write(dst_path, encoding="utf-8", xml_declaration=True)
    return dst_path


class GameMap:
    def __init__(self, tmx_path, scale=S.MAP_SCALE):
        self.scale = scale
        flat_path = _flatten_tmx(tmx_path)
        self.tmx = pytmx.load_pygame(flat_path, pixelalpha=True)

        self.tile_w = self.tmx.tilewidth * scale
        self.tile_h = self.tmx.tileheight * scale
        self.cols = self.tmx.width
        self.rows = self.tmx.height
        self.pixel_w = self.cols * self.tile_w
        self.pixel_h = self.rows * self.tile_h

        self._build_walkable()
        self.surface = self._prerender()

        # flow field (Dijkstra map) used by enemies to path around walls
        self._flow = {}
        self._flow_target_tile = None

        print(f"[map] {self.cols}x{self.rows} tiles -> "
              f"{self.pixel_w}x{self.pixel_h}px, "
              f"arena = {len(self.walkable)} walkable tiles")

    # ----------------------------------------------------------- rendering
    def _prerender(self):
        """Draw all tile layers once onto a single world-sized surface."""
        surface = pygame.Surface((self.pixel_w, self.pixel_h)).convert()
        surface.fill(S.COLOR_BG)
        scaled = {}                                   # gid -> scaled image
        for layer in self.tmx.visible_layers:
            if not hasattr(layer, "data"):
                continue
            for x, y, gid in layer:
                if not gid:
                    continue
                img = scaled.get(gid)
                if img is None:
                    raw = self.tmx.get_tile_image_by_gid(gid)
                    if raw is None:
                        continue
                    img = pygame.transform.scale(raw, (self.tile_w, self.tile_h))
                    scaled[gid] = img
                surface.blit(img, (x * self.tile_w, y * self.tile_h))
        return surface

    def draw(self, screen, camera):
        screen.fill(S.COLOR_BG)
        view = camera.view_rect
        src = view.clip(self.surface.get_rect())
        if src.width and src.height:
            screen.blit(self.surface, (src.x - view.x, src.y - view.y), area=src)

    # ----------------------------------------------------------- collision
    def _layer(self, name):
        for layer in self.tmx.layers:
            if layer.name == name:
                return layer
        return None

    def _build_walkable(self):
        """Compute the connected set of reachable floor tiles."""
        walls = set()
        wall_layer = self._layer(S.COLLISION_LAYER)
        if wall_layer is not None:
            walls = {(x, y) for x, y, gid in wall_layer if gid}

        floor = set()
        for name in S.FLOOR_LAYERS:
            layer = self._layer(name)
            if layer is None:
                continue
            floor |= {(x, y) for x, y, gid in layer if gid}

        candidates = floor - walls
        if not candidates:
            # degenerate map: fall back to "anything not a wall"
            candidates = {(x, y) for x in range(self.cols)
                          for y in range(self.rows) if (x, y) not in walls}

        # flood fill from the centroid to keep one connected arena
        cx = sum(x for x, _ in candidates) // len(candidates)
        cy = sum(y for _, y in candidates) // len(candidates)
        if (cx, cy) not in candidates:
            cx, cy = min(candidates,
                         key=lambda t: (t[0] - cx) ** 2 + (t[1] - cy) ** 2)

        reachable = {(cx, cy)}
        queue = deque([(cx, cy)])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in candidates and (nx, ny) not in reachable:
                    reachable.add((nx, ny))
                    queue.append((nx, ny))

        self.walkable = reachable
        self.spawn_tile = (cx, cy)
        # world-space tile centres, handy for spawning
        self._walk_centres = [self._tile_center(tx, ty)
                              for tx, ty in self.walkable]

    def _tile_center(self, tx, ty):
        return (tx * self.tile_w + self.tile_w // 2,
                ty * self.tile_h + self.tile_h // 2)

    def _tile_rect(self, tx, ty):
        return pygame.Rect(tx * self.tile_w, ty * self.tile_h,
                           self.tile_w, self.tile_h)

    def is_solid(self, tx, ty):
        if tx < 0 or ty < 0 or tx >= self.cols or ty >= self.rows:
            return True
        return (tx, ty) not in self.walkable

    def is_walkable_world(self, wx, wy):
        return not self.is_solid(int(wx) // self.tile_w, int(wy) // self.tile_h)

    def move_and_slide(self, entity, dx, dy):
        """Move an entity by (dx, dy) with axis-separated wall sliding."""
        rect = entity.rect

        entity.x += dx
        rect.centerx = round(entity.x)
        if self._resolve_axis(rect, dx, 0):
            entity.x = float(rect.centerx)

        entity.y += dy
        rect.centery = round(entity.y)
        if self._resolve_axis(rect, 0, dy):
            entity.y = float(rect.centery)

    def _resolve_axis(self, rect, dx, dy):
        """Push ``rect`` out of any solid tiles it overlaps on one axis."""
        adjusted = False
        tx0 = rect.left // self.tile_w - 1
        tx1 = rect.right // self.tile_w + 1
        ty0 = rect.top // self.tile_h - 1
        ty1 = rect.bottom // self.tile_h + 1
        for ty in range(ty0, ty1 + 1):
            for tx in range(tx0, tx1 + 1):
                if not self.is_solid(tx, ty):
                    continue
                wall = self._tile_rect(tx, ty)
                if not rect.colliderect(wall):
                    continue
                if dx > 0:
                    rect.right = wall.left
                elif dx < 0:
                    rect.left = wall.right
                if dy > 0:
                    rect.bottom = wall.top
                elif dy < 0:
                    rect.top = wall.bottom
                adjusted = True
        return adjusted

    def clamp_entity(self, entity):
        """Keep an entity's centre inside the map bounds (PRD §8 / §9)."""
        half_w = entity.rect.width // 2
        half_h = entity.rect.height // 2
        entity.x = max(half_w, min(self.pixel_w - half_w, entity.x))
        entity.y = max(half_h, min(self.pixel_h - half_h, entity.y))
        entity.rect.center = (round(entity.x), round(entity.y))

    # -------------------------------------------------------------- spawns
    @property
    def player_spawn(self):
        return self._tile_center(*self.spawn_tile)

    def random_spawn_point(self, from_x, from_y, min_dist=S.SPAWN_MIN_DIST):
        """A walkable world position at least ``min_dist`` px from a point."""
        min_sq = min_dist * min_dist
        far = [(px, py) for px, py in self._walk_centres
               if (px - from_x) ** 2 + (py - from_y) ** 2 >= min_sq]
        pool = far if far else self._walk_centres
        return random.choice(pool)

    def farthest_spawn_point(self, from_x, from_y):
        """The walkable world position furthest from a point (boss entrance)."""
        return max(self._walk_centres,
                   key=lambda p: (p[0] - from_x) ** 2 + (p[1] - from_y) ** 2)

    # ----------------------------------------------------------- flow field
    def _world_to_tile(self, wx, wy):
        return int(wx) // self.tile_w, int(wy) // self.tile_h

    def update_flow(self, target_x, target_y):
        """Rebuild the distance-to-player map when the player changes tile.

        A single BFS over the walkable tiles gives every tile its step distance
        to the player, so any number of enemies can path toward the player by
        walking downhill — cheap and immune to getting stuck behind walls.
        """
        tx, ty = self._world_to_tile(target_x, target_y)
        if (tx, ty) not in self.walkable:
            tx, ty = min(self.walkable,
                         key=lambda t: (t[0] - tx) ** 2 + (t[1] - ty) ** 2)
        if (tx, ty) == self._flow_target_tile:
            return
        self._flow_target_tile = (tx, ty)

        dist = {(tx, ty): 0}
        queue = deque([(tx, ty)])
        while queue:
            x, y = queue.popleft()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) in self.walkable and (nx, ny) not in dist:
                    dist[(nx, ny)] = dist[(x, y)] + 1
                    queue.append((nx, ny))
        self._flow = dist

    def flow_dir(self, wx, wy):
        """Unit direction (dx, dy) toward the player along the flow field.

        Returns None when there is no useful gradient (no field, off the grid,
        or already on the player's tile) so the caller falls back to steering
        straight at the player.
        """
        if not self._flow:
            return None
        tx, ty = self._world_to_tile(wx, wy)
        here = self._flow.get((tx, ty))
        if not here:                       # None (off grid) or 0 (on target)
            return None
        best, best_d = None, here
        for nx, ny in ((tx + 1, ty), (tx - 1, ty), (tx, ty + 1), (tx, ty - 1)):
            d = self._flow.get((nx, ny))
            if d is not None and d < best_d:
                best_d, best = d, (nx, ny)
        if best is None:
            return None
        cx, cy = self._tile_center(*best)
        ddx, ddy = cx - wx, cy - wy
        mag = (ddx * ddx + ddy * ddy) ** 0.5
        if mag < 1e-6:
            return None
        return (ddx / mag, ddy / mag)
