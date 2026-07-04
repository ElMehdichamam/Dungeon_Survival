"""
dungeon_map.py  –  importable DungeonMap class
"""

import os
import time
import xml.etree.ElementTree as ET
import pygame

TILE = 16   # native tile size (px)


# ── TMX parsing ───────────────────────────────────────────────────────────────

def _parse_tmx(path):
    root = ET.parse(path).getroot()

    tilesets = []
    for ts in root.findall('tileset'):
        img_el = ts.find('image')
        anims  = {}
        for tile in ts.findall('tile'):
            anim = tile.find('animation')
            if anim is not None:
                anims[int(tile.get('id'))] = [
                    (int(f.get('tileid')), int(f.get('duration')))
                    for f in anim.findall('frame')
                ]
        tilesets.append(dict(
            firstgid  = int(ts.get('firstgid')),
            name      = ts.get('name'),
            source    = img_el.get('source') if img_el is not None else None,
            cols      = int(ts.get('columns', 1)),
            tw        = int(ts.get('tilewidth',  TILE)),
            th        = int(ts.get('tileheight', TILE)),
            anims     = anims,
        ))

    layers = []
    for layer in root.findall('layer'):
        data_el = layer.find('data')
        if data_el is None:
            continue
        tiles = {}

        # Support both chunked (infinite maps) and flat CSV data
        chunks = data_el.findall('chunk')
        if chunks:
            for chunk in chunks:
                cx, cy = int(chunk.get('x')), int(chunk.get('y'))
                cw     = int(chunk.get('width'))
                for i, gid in enumerate(
                    int(v) for v in chunk.text.strip().split(',') if v.strip()
                ):
                    if gid:
                        tiles[(cx + i % cw, cy + i // cw)] = gid
        else:
            # Flat layer (non-infinite map)
            lw = int(layer.get('width',  1))
            lh = int(layer.get('height', 1))
            # Find map origin from parent map element
            map_el = root
            # x/y offset of the layer (default 0)
            ox = int(layer.get('x', 0))
            oy = int(layer.get('y', 0))
            raw = data_el.text.strip() if data_el.text else ""
            vals = [int(v) for v in raw.split(',') if v.strip()]
            for i, gid in enumerate(vals):
                if gid:
                    tx = ox + (i % lw)
                    ty = oy + (i // lw)
                    tiles[(tx, ty)] = gid

        layers.append(dict(
            name    = layer.get('name', ''),
            opacity = float(layer.get('opacity', 1.0)),
            tiles   = tiles,
        ))

    return tilesets, layers


# ── DungeonMap ────────────────────────────────────────────────────────────────

class DungeonMap:
    """
    Loads a Tiled TMX file and renders it each frame.
    Supports both infinite (chunked) and fixed-size maps.
    """

    def __init__(self, tmx_path: str, scale: int = 3, asset_dir: str = None):
        import inspect, pathlib
        caller_dir = pathlib.Path(inspect.stack()[1].filename).parent
        self.tmx_path  = str(caller_dir / tmx_path) if not os.path.isabs(tmx_path) else tmx_path
        self.scale     = scale
        self.ts        = TILE * scale
        self.asset_dir = asset_dir or os.path.dirname(os.path.abspath(self.tmx_path))

        self.tilesets   = []
        self.layers     = []
        self._sheets    = {}
        self._cache     = {}
        self._anim_map  = {}

        self.world_x0 = self.world_y0 = 0
        self.world_w  = self.world_h  = 0
        self.pixel_w  = self.pixel_h  = 0

        self._solid_tiles: set = set()

    # ── public API ────────────────────────────────────────────────────────────

    def load(self):
        self.tilesets, self.layers = _parse_tmx(self.tmx_path)
        self._load_sheets()
        self._build_anim_map()
        self._calc_bounds()
        self._build_collision_set()

    def update(self):
        pass   # animation is time-based

    def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0):
        sw, sh = surface.get_size()
        ts = self.ts

        tc0 = max(0, cam_x // ts)
        tr0 = max(0, cam_y // ts)
        tc1 = min(self.world_w, tc0 + sw // ts + 2)
        tr1 = min(self.world_h, tr0 + sh // ts + 2)

        for layer in self.layers:
            op = layer['opacity']
            for tr in range(tr0, tr1):
                for tc in range(tc0, tc1):
                    wx  = tc + self.world_x0
                    wy  = tr + self.world_y0
                    gid = layer['tiles'].get((wx, wy), 0)
                    if not gid:
                        continue
                    tile = self._get_tile(gid)
                    if tile is None:
                        continue
                    sx = tc * ts - cam_x
                    sy = tr * ts - cam_y
                    if op < 1.0:
                        tile = tile.copy()
                        tile.set_alpha(int(op * 255))
                    surface.blit(tile, (sx, sy))

    def tile_at_screen(self, screen_x, screen_y, cam_x, cam_y):
        tx = (screen_x + cam_x) // self.ts + self.world_x0
        ty = (screen_y + cam_y) // self.ts + self.world_y0
        return tx, ty

    def get_bounds(self, margin: int = 0) -> pygame.Rect:
        return pygame.Rect(
            margin,
            margin,
            self.pixel_w - margin * 2,
            self.pixel_h - margin * 2,
        )

    def clamp_rect(self, rect: pygame.Rect, margin: int = 0) -> pygame.Rect:
        return rect.clamp(self.get_bounds(margin))

    def is_solid(self, world_tx: int, world_ty: int) -> bool:
        return (world_tx, world_ty) in self._solid_tiles

    def resolve_collision(self, rect: pygame.Rect) -> pygame.Rect:
        """
        Push *rect* out of any solid wall tiles it overlaps.

        Two-pass approach (X then Y) prevents corner lock-ups where fixing
        one wall pushes the entity into an adjacent wall on the other axis.

        The hitbox is a small rectangle at the sprite's feet:
          • width  = 14 px  (fits through 1-tile / 32 px doorways)
          • height = 10 px  (sits at the very bottom of the sprite)
        Keeping the hitbox well under one tile wide/tall in both axes is what
        lets entities slide through narrow doorways without getting stuck.
        """
        ts = self.ts
        HW = 7    # half-width  → total 14 px  (< 16 px = half a tile)
        HH = 5    # half-height → total 10 px

        def _make_hit(r):
            cx = r.centerx
            cy = r.bottom - HH - 1          # placed at the feet
            return pygame.Rect(cx - HW, cy - HH, HW * 2, HH * 2)

        # FIX BUG-11: shrink each solid tile to ~60% so the player can walk
        # closer to walls and squeeze through doorways.
        SOLID_SCALE = 0.6
        solid_size  = max(1, int(ts * SOLID_SCALE))
        pad         = (ts - solid_size) // 2

        def _solid_rects_near(h):
            """Return tile rects (shrunk to SOLID_SCALE of a full tile)
            that the hitbox h currently overlaps."""
            left_t  = (h.left   // ts) + self.world_x0
            right_t = (h.right  // ts) + self.world_x0
            top_t   = (h.top    // ts) + self.world_y0
            bot_t   = (h.bottom // ts) + self.world_y0
            out = []
            for ty in range(top_t, bot_t + 1):
                for tx in range(left_t, right_t + 1):
                    if (tx, ty) in self._solid_tiles:
                        out.append(pygame.Rect(
                            (tx - self.world_x0) * ts + pad,
                            (ty - self.world_y0) * ts + pad,
                            solid_size, solid_size,
                        ))
            return out

        # ── Pass 1: resolve X axis only ──────────────────────────────────────
        hit = _make_hit(rect)
        for tile_rect in _solid_rects_near(hit):
            if not hit.colliderect(tile_rect):
                continue
            ol  = hit.right - tile_rect.left    # overlap from the right
            or_ = tile_rect.right - hit.left    # overlap from the left
            dx  = -ol if ol < or_ else or_
            hit.x  += dx
            rect.x += dx

        # ── Pass 2: resolve Y axis only ──────────────────────────────────────
        hit = _make_hit(rect)                   # recompute after X correction
        for tile_rect in _solid_rects_near(hit):
            if not hit.colliderect(tile_rect):
                continue
            ot  = hit.bottom - tile_rect.top    # overlap from below
            ob  = tile_rect.bottom - hit.top    # overlap from above
            dy  = -ot if ot < ob else ob
            hit.y  += dy
            rect.y += dy

        return rect

    # ── internals ─────────────────────────────────────────────────────────────

    def _build_collision_set(self):
        """Solid = Walls + water tiles (unwalkable)."""
        SOLID_LAYERS = {'Walls', 'water_floor3', 'walls_under_water'}
        # FIX BUG-11: surface the TMX layer names so a future mismatch is
        # immediately visible at boot.
        all_layer_names = [l['name'] for l in self.layers]
        print(f"[DungeonMap] TMX layers: {all_layer_names}")
        print(f"[DungeonMap] Configured SOLID_LAYERS: {sorted(SOLID_LAYERS)}")
        missing = SOLID_LAYERS - set(all_layer_names)
        if missing:
            print(f"[DungeonMap] WARNING: expected solid layers not found in TMX: {missing}")

        self._solid_tiles = set()
        for layer in self.layers:
            if layer['name'] in SOLID_LAYERS:
                self._solid_tiles.update(layer['tiles'].keys())
        matched = [l['name'] for l in self.layers if l['name'] in SOLID_LAYERS]
        print(f"[DungeonMap] Solid tiles: {len(self._solid_tiles)} from layers: {matched}")

    def _load_sheets(self):
        for ts in self.tilesets:
            src = ts['source']
            if src and src not in self._sheets:
                path = os.path.join(self.asset_dir, src)
                if os.path.exists(path):
                    self._sheets[src] = pygame.image.load(path).convert_alpha()
                else:
                    print(f"[DungeonMap] WARNING: missing sprite sheet: {path}")

    def _build_anim_map(self):
        for ts in self.tilesets:
            for lid, frames in ts['anims'].items():
                self._anim_map[ts['firstgid'] + lid] = (ts, lid)

    def _calc_bounds(self):
        xs, ys = [], []
        for layer in self.layers:
            for tx, ty in layer['tiles']:
                xs.append(tx); ys.append(ty)
        if not xs:
            return
        self.world_x0 = min(xs)
        self.world_y0 = min(ys)
        self.world_w  = max(xs) - self.world_x0 + 1
        self.world_h  = max(ys) - self.world_y0 + 1
        self.pixel_w  = self.world_w * self.ts
        self.pixel_h  = self.world_h * self.ts

    def _resolve_gid(self, gid: int) -> int:
        raw = gid & 0x1FFFFFFF
        if raw not in self._anim_map:
            return raw
        ts, lid = self._anim_map[raw]
        frames  = ts['anims'][lid]
        total   = sum(d for _, d in frames)
        t_ms    = int(time.time() * 1000) % total
        acc     = 0
        for frame_lid, dur in frames:
            acc += dur
            if t_ms < acc:
                return ts['firstgid'] + frame_lid
        return ts['firstgid'] + frames[-1][0]

    def _get_tile(self, gid: int) -> pygame.Surface | None:
        raw = self._resolve_gid(gid)
        if raw in self._cache:
            return self._cache[raw]

        ts = None
        for t in reversed(self.tilesets):
            if raw >= t['firstgid']:
                ts = t; break
        if ts is None or not ts['source'] or ts['source'] not in self._sheets:
            self._cache[raw] = None
            return None

        lid  = raw - ts['firstgid']
        col  = lid % ts['cols']
        row  = lid // ts['cols']
        rect = pygame.Rect(col * ts['tw'], row * ts['th'], ts['tw'], ts['th'])

        native = pygame.Surface((ts['tw'], ts['th']), pygame.SRCALPHA)
        native.blit(self._sheets[ts['source']], (0, 0), rect)
        scaled = pygame.transform.scale(native, (self.ts, self.ts))

        self._cache[raw] = scaled
        return scaled