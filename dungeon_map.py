# # # """
# # # dungeon_map.py  –  importable DungeonMap class
# # # -----------------------------------------------
# # # Usage in your main.py:

# # #     from dungeon_map import DungeonMap

# # #     dungeon = DungeonMap("Dungeon1.tmx", scale=3)
# # #     dungeon.load()                        # call once after pygame.init()

# # #     # in your game loop:
# # #     dungeon.update()                      # advances animations
# # #     dungeon.draw(screen, cam_x, cam_y)    # renders to any surface
# # # """

# # # import os
# # # import time
# # # import xml.etree.ElementTree as ET
# # # import pygame

# # # TILE = 16   # native tile size (px)


# # # # ── TMX parsing ───────────────────────────────────────────────────────────────

# # # def _parse_tmx(path):
# # #     root = ET.parse(path).getroot()

# # #     tilesets = []
# # #     for ts in root.findall('tileset'):
# # #         img_el = ts.find('image')
# # #         anims  = {}
# # #         for tile in ts.findall('tile'):
# # #             anim = tile.find('animation')
# # #             if anim is not None:
# # #                 anims[int(tile.get('id'))] = [
# # #                     (int(f.get('tileid')), int(f.get('duration')))
# # #                     for f in anim.findall('frame')
# # #                 ]
# # #         tilesets.append(dict(
# # #             firstgid  = int(ts.get('firstgid')),
# # #             name      = ts.get('name'),
# # #             source    = img_el.get('source') if img_el is not None else None,
# # #             cols      = int(ts.get('columns', 1)),
# # #             tw        = int(ts.get('tilewidth',  TILE)),
# # #             th        = int(ts.get('tileheight', TILE)),
# # #             anims     = anims,
# # #         ))

# # #     layers = []
# # #     for layer in root.findall('layer'):
# # #         data_el = layer.find('data')
# # #         if data_el is None:
# # #             continue
# # #         tiles = {}
# # #         for chunk in data_el.findall('chunk'):
# # #             cx, cy = int(chunk.get('x')), int(chunk.get('y'))
# # #             cw     = int(chunk.get('width'))
# # #             for i, gid in enumerate(
# # #                 int(v) for v in chunk.text.strip().split(',') if v.strip()
# # #             ):
# # #                 if gid:
# # #                     tiles[(cx + i % cw, cy + i // cw)] = gid
# # #         layers.append(dict(
# # #             name    = layer.get('name', ''),
# # #             opacity = float(layer.get('opacity', 1.0)),
# # #             tiles   = tiles,
# # #         ))

# # #     return tilesets, layers


# # # # ── DungeonMap ────────────────────────────────────────────────────────────────

# # # class DungeonMap:
# # #     """
# # #     Loads a Tiled TMX file (infinite/chunked) and renders it each frame.

# # #     Parameters
# # #     ----------
# # #     tmx_path : str
# # #         Path to the .tmx file.
# # #     scale : int
# # #         Pixel scale factor (default 3 → 16px tiles become 48px).
# # #     asset_dir : str | None
# # #         Folder where the sprite-sheet PNGs live.
# # #         Defaults to the folder that contains the TMX file.
# # #     """

# # #     def __init__(self, tmx_path: str, scale: int = 3, asset_dir: str = None):
# # #         # resolve tmx_path relative to the caller's file, not the cwd
# # #         import inspect, pathlib
# # #         caller_dir = pathlib.Path(inspect.stack()[1].filename).parent
# # #         self.tmx_path  = str(caller_dir / tmx_path) if not os.path.isabs(tmx_path) else tmx_path
# # #         self.scale     = scale
# # #         self.ts        = TILE * scale          # tile size on screen
# # #         self.asset_dir = asset_dir or os.path.dirname(os.path.abspath(self.tmx_path))

# # #         # set after load()
# # #         self.tilesets   = []
# # #         self.layers     = []
# # #         self._sheets    = {}   # filename → Surface
# # #         self._cache     = {}   # raw_gid  → scaled Surface | None
# # #         self._anim_map  = {}   # raw_gid  → (tileset_dict, local_id)
# # #         self._walkable_tiles = set()  # set of (world_tx, world_ty) walkable tiles

# # #         self.world_x0 = self.world_y0 = 0
# # #         self.world_w  = self.world_h  = 0
# # #         self.pixel_w  = self.pixel_h  = 0   # total map size in screen pixels

# # #     # ── public API ────────────────────────────────────────────────────────────

# # #     def load(self):
# # #         """Parse the TMX and load all sprite sheets. Call once after pygame.init()."""
# # #         self.tilesets, self.layers = _parse_tmx(self.tmx_path)
# # #         self._load_sheets()
# # #         self._build_anim_map()
# # #         self._calc_bounds()
# # #         self._build_walkable()

# # #     def update(self):
# # #         """
# # #         Call every frame (or whenever you like) to keep animations alive.
# # #         Currently animation is time-based so this is a no-op,
# # #         but it's here so your game loop stays forward-compatible.
# # #         """
# # #         pass   # time.time() is read live inside resolve_gid

# # #     def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0):
# # #         """
# # #         Blit the visible portion of the map onto *surface*.

# # #         Parameters
# # #         ----------
# # #         surface : pygame.Surface
# # #             The target surface (usually your screen).
# # #         cam_x, cam_y : int
# # #             Camera offset in screen pixels.
# # #         """
# # #         sw, sh = surface.get_size()
# # #         ts = self.ts

# # #         tc0 = max(0, cam_x // ts)
# # #         tr0 = max(0, cam_y // ts)
# # #         tc1 = min(self.world_w, tc0 + sw // ts + 2)
# # #         tr1 = min(self.world_h, tr0 + sh // ts + 2)

# # #         for layer in self.layers:
# # #             op = layer['opacity']
# # #             for tr in range(tr0, tr1):
# # #                 for tc in range(tc0, tc1):
# # #                     wx  = tc + self.world_x0
# # #                     wy  = tr + self.world_y0
# # #                     gid = layer['tiles'].get((wx, wy), 0)
# # #                     if not gid:
# # #                         continue
# # #                     tile = self._get_tile(gid)
# # #                     if tile is None:
# # #                         continue
# # #                     sx = tc * ts - cam_x
# # #                     sy = tr * ts - cam_y
# # #                     if op < 1.0:
# # #                         tile = tile.copy()
# # #                         tile.set_alpha(int(op * 255))
# # #                     surface.blit(tile, (sx, sy))

# # #     def tile_at_screen(self, screen_x: int, screen_y: int,
# # #                        cam_x: int, cam_y: int):
# # #         """
# # #         Return the world tile coordinate under a screen pixel.
# # #         Useful for collision or click detection in your game.
# # #         """
# # #         tx = (screen_x + cam_x) // self.ts + self.world_x0
# # #         ty = (screen_y + cam_y) // self.ts + self.world_y0
# # #         return tx, ty

# # #     def is_solid(self, world_tx: int, world_ty: int) -> bool:
# # #         """
# # #         Basic wall check: returns True if the 'Walls' layer has a tile here.
# # #         Extend this however your game needs.
# # #         """
# # #         for layer in self.layers:
# # #             if layer['name'] == 'Walls' and (world_tx, world_ty) in layer['tiles']:
# # #                 return True
# # #         return False

# # #     def is_walkable_pixel(self, world_px: float, world_py: float) -> bool:
# # #         """
# # #         Check if a world-pixel position is on a walkable floor tile.

# # #         Parameters
# # #         ----------
# # #         world_px, world_py : float
# # #             Position in world-pixel coordinates (screen_pos + camera_offset).
# # #         """
# # #         tx = int(world_px) // self.ts + self.world_x0
# # #         ty = int(world_py) // self.ts + self.world_y0
# # #         return (tx, ty) in self._walkable_tiles

# # #     # ── internals ─────────────────────────────────────────────────────────────

# # #     def _load_sheets(self):
# # #         for ts in self.tilesets:
# # #             src = ts['source']
# # #             if src and src not in self._sheets:
# # #                 path = os.path.join(self.asset_dir, src)
# # #                 if os.path.exists(path):
# # #                     self._sheets[src] = pygame.image.load(path).convert_alpha()
# # #                 else:
# # #                     print(f"[DungeonMap] WARNING: missing sprite sheet: {path}")

# # #     def _build_anim_map(self):
# # #         for ts in self.tilesets:
# # #             for lid, frames in ts['anims'].items():
# # #                 self._anim_map[ts['firstgid'] + lid] = (ts, lid)

# # #     def _calc_bounds(self):
# # #         xs, ys = [], []
# # #         for layer in self.layers:
# # #             for tx, ty in layer['tiles']:
# # #                 xs.append(tx); ys.append(ty)
# # #         if not xs:
# # #             return
# # #         self.world_x0 = min(xs)
# # #         self.world_y0 = min(ys)
# # #         self.world_w  = max(xs) - self.world_x0 + 1
# # #         self.world_h  = max(ys) - self.world_y0 + 1
# # #         self.pixel_w  = self.world_w * self.ts
# # #         self.pixel_h  = self.world_h * self.ts

# # #     _FLOOR_LAYERS = {'Floor', 'Floor2_pool', 'Floor_darker_surface',
# # #                      'Floor2_darker_surface'}
# # #     _BLOCKING_LAYERS = {'Walls', 'water_floor3', 'walls_under_water', 
# # #                         'traps', 'Objects', 'Objects2', 'Windows'}

# # #     def _build_walkable(self):
# # #         """Build a set of walkable tile positions from floor layers minus blocking layers."""
# # #         self._walkable_tiles = set()
# # #         for layer in self.layers:
# # #             if layer['name'] in self._FLOOR_LAYERS:
# # #                 self._walkable_tiles.update(layer['tiles'].keys())
                
# # #         for layer in self.layers:
# # #             if layer['name'] in self._BLOCKING_LAYERS:
# # #                 for pos in layer['tiles'].keys():
# # #                     self._walkable_tiles.discard(pos)

# # #     def _resolve_gid(self, gid: int) -> int:
# # #         """Strip flip bits and advance animation frame."""
# # #         raw = gid & 0x1FFFFFFF
# # #         if raw not in self._anim_map:
# # #             return raw
# # #         ts, lid = self._anim_map[raw]
# # #         frames  = ts['anims'][lid]
# # #         total   = sum(d for _, d in frames)
# # #         t_ms    = int(time.time() * 1000) % total
# # #         acc     = 0
# # #         for frame_lid, dur in frames:
# # #             acc += dur
# # #             if t_ms < acc:
# # #                 return ts['firstgid'] + frame_lid
# # #         return ts['firstgid'] + frames[-1][0]

# # #     def _get_tile(self, gid: int) -> pygame.Surface | None:
# # #         """Return a cached, scaled Surface for this gid (animation-resolved)."""
# # #         raw = self._resolve_gid(gid)
# # #         if raw in self._cache:
# # #             return self._cache[raw]

# # #         # find tileset
# # #         ts = None
# # #         for t in reversed(self.tilesets):
# # #             if raw >= t['firstgid']:
# # #                 ts = t; break
# # #         if ts is None or not ts['source'] or ts['source'] not in self._sheets:
# # #             self._cache[raw] = None
# # #             return None

# # #         lid  = raw - ts['firstgid']
# # #         col  = lid % ts['cols']
# # #         row  = lid // ts['cols']
# # #         rect = pygame.Rect(col * ts['tw'], row * ts['th'], ts['tw'], ts['th'])

# # #         native = pygame.Surface((ts['tw'], ts['th']), pygame.SRCALPHA)
# # #         native.blit(self._sheets[ts['source']], (0, 0), rect)
# # #         scaled = pygame.transform.scale(native, (self.ts, self.ts))

# # #         self._cache[raw] = scaled
# # #         return scaled

# # """
# # dungeon_map.py  –  importable DungeonMap class
# # -----------------------------------------------
# # Usage in your main.py:

# #     from dungeon_map import DungeonMap

# #     dungeon = DungeonMap("Dungeon1.tmx", scale=3)
# #     dungeon.load()                        # call once after pygame.init()

# #     # in your game loop:
# #     dungeon.update()                      # advances animations
# #     dungeon.draw(screen, cam_x, cam_y)    # renders to any surface
# # """

# # import os
# # import time
# # import xml.etree.ElementTree as ET
# # import pygame

# # TILE = 16   # native tile size (px)


# # # ── TMX parsing ───────────────────────────────────────────────────────────────

# # def _parse_tmx(path):
# #     root = ET.parse(path).getroot()

# #     tilesets = []
# #     for ts in root.findall('tileset'):
# #         img_el = ts.find('image')
# #         anims  = {}
# #         for tile in ts.findall('tile'):
# #             anim = tile.find('animation')
# #             if anim is not None:
# #                 anims[int(tile.get('id'))] = [
# #                     (int(f.get('tileid')), int(f.get('duration')))
# #                     for f in anim.findall('frame')
# #                 ]
# #         tilesets.append(dict(
# #             firstgid  = int(ts.get('firstgid')),
# #             name      = ts.get('name'),
# #             source    = img_el.get('source') if img_el is not None else None,
# #             cols      = int(ts.get('columns', 1)),
# #             tw        = int(ts.get('tilewidth',  TILE)),
# #             th        = int(ts.get('tileheight', TILE)),
# #             anims     = anims,
# #         ))

# #     layers = []
# #     for layer in root.findall('layer'):
# #         data_el = layer.find('data')
# #         if data_el is None:
# #             continue
# #         tiles = {}
# #         for chunk in data_el.findall('chunk'):
# #             cx, cy = int(chunk.get('x')), int(chunk.get('y'))
# #             cw     = int(chunk.get('width'))
# #             for i, gid in enumerate(
# #                 int(v) for v in chunk.text.strip().split(',') if v.strip()
# #             ):
# #                 if gid:
# #                     tiles[(cx + i % cw, cy + i // cw)] = gid
# #         layers.append(dict(
# #             name    = layer.get('name', ''),
# #             opacity = float(layer.get('opacity', 1.0)),
# #             tiles   = tiles,
# #         ))

# #     return tilesets, layers


# # # ── DungeonMap ────────────────────────────────────────────────────────────────

# # class DungeonMap:
# #     """
# #     Loads a Tiled TMX file (infinite/chunked) and renders it each frame.

# #     Parameters
# #     ----------
# #     tmx_path : str
# #         Path to the .tmx file.
# #     scale : int
# #         Pixel scale factor (default 3 → 16px tiles become 48px).
# #     asset_dir : str | None
# #         Folder where the sprite-sheet PNGs live.
# #         Defaults to the folder that contains the TMX file.
# #     """

# #     def __init__(self, tmx_path: str, scale: int = 3, asset_dir: str = None):
# #         # resolve tmx_path relative to the caller's file, not the cwd
# #         import inspect, pathlib
# #         caller_dir = pathlib.Path(inspect.stack()[1].filename).parent
# #         self.tmx_path  = str(caller_dir / tmx_path) if not os.path.isabs(tmx_path) else tmx_path
# #         self.scale     = scale
# #         self.ts        = TILE * scale          # tile size on screen
# #         self.asset_dir = asset_dir or os.path.dirname(os.path.abspath(self.tmx_path))

# #         # set after load()
# #         self.tilesets   = []
# #         self.layers     = []
# #         self._sheets    = {}   # filename → Surface
# #         self._cache     = {}   # raw_gid  → scaled Surface | None
# #         self._anim_map  = {}   # raw_gid  → (tileset_dict, local_id)

# #         self.world_x0 = self.world_y0 = 0
# #         self.world_w  = self.world_h  = 0
# #         self.pixel_w  = self.pixel_h  = 0   # total map size in screen pixels

# #         # Fast O(1) collision sets (world tile coords) – built in load()
# #         self._solid_tiles    : set = set()
# #         self._walkable_tiles : set = set()
# #         self._gid_tileset    : dict = {}   # raw_gid -> tileset name

# #     # ── public API ────────────────────────────────────────────────────────────

# #     def load(self):
# #         """Parse the TMX and load all sprite sheets. Call once after pygame.init()."""
# #         self.tilesets, self.layers = _parse_tmx(self.tmx_path)
# #         self._load_sheets()
# #         self._build_anim_map()
# #         self._calc_bounds()
# #         self._build_collision_set()

# #     def update(self):
# #         """
# #         Call every frame (or whenever you like) to keep animations alive.
# #         Currently animation is time-based so this is a no-op,
# #         but it's here so your game loop stays forward-compatible.
# #         """
# #         pass   # time.time() is read live inside resolve_gid

# #     def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0):
# #         """
# #         Blit the visible portion of the map onto *surface*.

# #         Parameters
# #         ----------
# #         surface : pygame.Surface
# #             The target surface (usually your screen).
# #         cam_x, cam_y : int
# #             Camera offset in screen pixels.
# #         """
# #         sw, sh = surface.get_size()
# #         ts = self.ts

# #         tc0 = max(0, cam_x // ts)
# #         tr0 = max(0, cam_y // ts)
# #         tc1 = min(self.world_w, tc0 + sw // ts + 2)
# #         tr1 = min(self.world_h, tr0 + sh // ts + 2)

# #         for layer in self.layers:
# #             op = layer['opacity']
# #             for tr in range(tr0, tr1):
# #                 for tc in range(tc0, tc1):
# #                     wx  = tc + self.world_x0
# #                     wy  = tr + self.world_y0
# #                     gid = layer['tiles'].get((wx, wy), 0)
# #                     if not gid:
# #                         continue
# #                     tile = self._get_tile(gid)
# #                     if tile is None:
# #                         continue
# #                     sx = tc * ts - cam_x
# #                     sy = tr * ts - cam_y
# #                     if op < 1.0:
# #                         tile = tile.copy()
# #                         tile.set_alpha(int(op * 255))
# #                     surface.blit(tile, (sx, sy))

# #     def tile_at_screen(self, screen_x: int, screen_y: int,
# #                        cam_x: int, cam_y: int):
# #         """
# #         Return the world tile coordinate under a screen pixel.
# #         Useful for collision or click detection in your game.
# #         """
# #         tx = (screen_x + cam_x) // self.ts + self.world_x0
# #         ty = (screen_y + cam_y) // self.ts + self.world_y0
# #         return tx, ty

# #     def get_bounds(self, margin: int = 0) -> pygame.Rect:
# #         """
# #         Return a pygame.Rect describing the playable area in screen pixels.

# #         Parameters
# #         ----------
# #         margin : int
# #             Shrink the boundary inward by this many pixels on every side.
# #             Useful so sprites don't clip the very edge of the map.
# #         """
# #         return pygame.Rect(
# #             margin,
# #             margin,
# #             self.pixel_w - margin * 2,
# #             self.pixel_h - margin * 2,
# #         )

# #     def clamp_rect(self, rect: pygame.Rect, margin: int = 0) -> pygame.Rect:
# #         """
# #         Return a copy of *rect* clamped inside the map bounds.
# #         Call this every frame for the player and each enemy.

# #         Example
# #         -------
# #         player.rect = dungeon.clamp_rect(player.rect, margin=4)
# #         """
# #         bounds = self.get_bounds(margin)
# #         return rect.clamp(bounds)

# #     def is_solid(self, world_tx: int, world_ty: int) -> bool:
# #         """Return True if this world tile coordinate blocks movement."""
# #         return (world_tx, world_ty) in self._solid_tiles

# #     def is_walkable_pixel(self, world_px: float, world_py: float) -> bool:
# #         """Return True if the world-pixel position is on walkable floor."""
# #         tx = int(world_px) // self.ts + self.world_x0
# #         ty = int(world_py) // self.ts + self.world_y0
# #         return (tx, ty) in self._walkable_tiles

# #     def resolve_collision(self, rect: pygame.Rect) -> pygame.Rect:
# #         """
# #         Push *rect* out of solid tiles (axis-separated to avoid corner slips).
# #         Call AFTER moving the entity each frame.
# #         """
# #         ts = self.ts
# #         x0, y0 = self.world_x0, self.world_y0

# #         def tile_rect(tx: int, ty: int) -> pygame.Rect:
# #             return pygame.Rect((tx - x0) * ts, (ty - y0) * ts, ts, ts)

# #         def overlapping_tiles(r: pygame.Rect):
# #             # rect.right/bottom are exclusive; use -1 for inclusive tile index
# #             left_t  = r.left // ts + x0
# #             right_t = (r.right - 1) // ts + x0
# #             top_t   = r.top // ts + y0
# #             bot_t   = (r.bottom - 1) // ts + y0
# #             for ty in range(top_t, bot_t + 1):
# #                 for tx in range(left_t, right_t + 1):
# #                     if (tx, ty) in self._solid_tiles:
# #                         tr = tile_rect(tx, ty)
# #                         if r.colliderect(tr):
# #                             yield tr

# #         # Resolve X then Y (standard platformer separation)
# #         for tr in overlapping_tiles(rect):
# #             overlap_left  = rect.right - tr.left
# #             overlap_right = tr.right - rect.left
# #             if overlap_left <= overlap_right:
# #                 rect.right = tr.left
# #             else:
# #                 rect.left = tr.right

# #         for tr in overlapping_tiles(rect):
# #             overlap_top    = rect.bottom - tr.top
# #             overlap_bottom = tr.bottom - rect.top
# #             if overlap_top <= overlap_bottom:
# #                 rect.bottom = tr.top
# #             else:
# #                 rect.top = tr.bottom

# #         return rect

# #     # ── internals ─────────────────────────────────────────────────────────────

# #     _FLOOR_LAYERS = {
# #         'Floor', 'Floor2_pool', 'Floor_darker_surface', 'Floor2_darker_surface',
# #     }
# #     _BLOCKING_LAYERS = {
# #         'Walls', 'traps', 'Objects', 'Objects2', 'Objects_under_wall',
# #     }
# #     _WATER_LAYERS = {'water_floor3', 'walls_under_water'}
# #     _WATER_TILESETS = {
# #         'Water_coasts_animation', 'Water_detilazation',
# #         'Water_coasts_animation_decorative_cracks',
# #     }
# #     _WALL_TILESETS = {'cracked_tiles'}

# #     def _build_gid_tileset_map(self):
# #         """Map stripped GID -> tileset name for collision rules."""
# #         self._gid_tileset = {}
# #         ordered = sorted(self.tilesets, key=lambda t: t['firstgid'])
# #         for i, ts in enumerate(ordered):
# #             if i + 1 < len(ordered):
# #                 last_gid = ordered[i + 1]['firstgid'] - 1
# #             else:
# #                 last_gid = ts['firstgid'] + 4095
# #             for raw in range(ts['firstgid'], last_gid + 1):
# #                 self._gid_tileset[raw] = ts['name']

# #     def _tileset_name(self, gid: int) -> str:
# #         raw = gid & 0x1FFFFFFF
# #         return self._gid_tileset.get(raw, '')

# #     def _build_collision_set(self):
# #         """
# #         Build solid and walkable tile sets.

# #         Walkable = floor tiles minus blocking overlays.
# #         Solid    = anything that blocks movement (walls, traps, props, deep water).

# #         Shallow water puddles on open floor (water_floor3 with no wall) stay walkable.
# #         Windows are decorative and do not block (walls already block those cells).
# #         """
# #         self._build_gid_tileset_map()

# #         floor_tiles = set()
# #         for layer in self.layers:
# #             if layer['name'] in self._FLOOR_LAYERS:
# #                 floor_tiles.update(layer['tiles'].keys())

# #         walls_tiles = set()
# #         for layer in self.layers:
# #             if layer['name'] == 'Walls':
# #                 walls_tiles.update(layer['tiles'].keys())

# #         self._solid_tiles = set()
# #         for layer in self.layers:
# #             if layer['name'] in self._BLOCKING_LAYERS:
# #                 self._solid_tiles.update(layer['tiles'].keys())

# #         # Water / underwater decor: block pools, but not shallow puddles on open floor
# #         for layer in self.layers:
# #             if layer['name'] not in self._WATER_LAYERS:
# #                 continue
# #             for pos, gid in layer['tiles'].items():
# #                 ts_name = self._tileset_name(gid)
# #                 if ts_name == 'walls_floor':
# #                     continue
# #                 if pos in floor_tiles and pos not in walls_tiles:
# #                     continue
# #                 self._solid_tiles.add(pos)

# #         # Wall tileset placed on floor without a Walls layer tile (map gaps)
# #         for layer in self.layers:
# #             if layer['name'] not in self._FLOOR_LAYERS:
# #                 continue
# #             for pos, gid in layer['tiles'].items():
# #                 if pos in walls_tiles:
# #                     continue
# #                 if self._tileset_name(gid) in self._WALL_TILESETS:
# #                     self._solid_tiles.add(pos)

# #         self._walkable_tiles = set(floor_tiles)
# #         self._walkable_tiles -= self._solid_tiles

# #         print(
# #             f"[DungeonMap] Collision: {len(self._solid_tiles)} solid, "
# #             f"{len(self._walkable_tiles)} walkable"
# #         )

# #     def _load_sheets(self):
# #         for ts in self.tilesets:
# #             src = ts['source']
# #             if src and src not in self._sheets:
# #                 path = os.path.join(self.asset_dir, src)
# #                 if os.path.exists(path):
# #                     self._sheets[src] = pygame.image.load(path).convert_alpha()
# #                 else:
# #                     print(f"[DungeonMap] WARNING: missing sprite sheet: {path}")

# #     def _build_anim_map(self):
# #         for ts in self.tilesets:
# #             for lid, frames in ts['anims'].items():
# #                 self._anim_map[ts['firstgid'] + lid] = (ts, lid)

# #     def _calc_bounds(self):
# #         xs, ys = [], []
# #         for layer in self.layers:
# #             for tx, ty in layer['tiles']:
# #                 xs.append(tx); ys.append(ty)
# #         if not xs:
# #             return
# #         self.world_x0 = min(xs)
# #         self.world_y0 = min(ys)
# #         self.world_w  = max(xs) - self.world_x0 + 1
# #         self.world_h  = max(ys) - self.world_y0 + 1
# #         self.pixel_w  = self.world_w * self.ts
# #         self.pixel_h  = self.world_h * self.ts

# #     def _resolve_gid(self, gid: int) -> int:
# #         """Strip flip bits and advance animation frame."""
# #         raw = gid & 0x1FFFFFFF
# #         if raw not in self._anim_map:
# #             return raw
# #         ts, lid = self._anim_map[raw]
# #         frames  = ts['anims'][lid]
# #         total   = sum(d for _, d in frames)
# #         t_ms    = int(time.time() * 1000) % total
# #         acc     = 0
# #         for frame_lid, dur in frames:
# #             acc += dur
# #             if t_ms < acc:
# #                 return ts['firstgid'] + frame_lid
# #         return ts['firstgid'] + frames[-1][0]

# #     def _get_tile(self, gid: int) -> pygame.Surface | None:
# #         """Return a cached, scaled Surface for this gid (animation-resolved)."""
# #         raw = self._resolve_gid(gid)
# #         if raw in self._cache:
# #             return self._cache[raw]

# #         # find tileset
# #         ts = None
# #         for t in reversed(self.tilesets):
# #             if raw >= t['firstgid']:
# #                 ts = t; break
# #         if ts is None or not ts['source'] or ts['source'] not in self._sheets:
# #             self._cache[raw] = None
# #             return None

# #         lid  = raw - ts['firstgid']
# #         col  = lid % ts['cols']
# #         row  = lid // ts['cols']
# #         rect = pygame.Rect(col * ts['tw'], row * ts['th'], ts['tw'], ts['th'])

# #         native = pygame.Surface((ts['tw'], ts['th']), pygame.SRCALPHA)
# #         native.blit(self._sheets[ts['source']], (0, 0), rect)
# #         scaled = pygame.transform.scale(native, (self.ts, self.ts))

# #         self._cache[raw] = scaled
# #         return scaled


# """
# dungeon_map.py  –  importable DungeonMap class
# -----------------------------------------------
# Usage in your main.py:

#     from dungeon_map import DungeonMap

#     dungeon = DungeonMap("Dungeon1.tmx", scale=3)
#     dungeon.load()                        # call once after pygame.init()

#     # in your game loop:
#     dungeon.update()                      # advances animations
#     dungeon.draw(screen, cam_x, cam_y)    # renders to any surface
# """

# import os
# import time
# import xml.etree.ElementTree as ET
# import pygame

# TILE = 16   # native tile size (px)


# # ── TMX parsing ───────────────────────────────────────────────────────────────

# def _parse_tmx(path):
#     root = ET.parse(path).getroot()

#     tilesets = []
#     for ts in root.findall('tileset'):
#         img_el = ts.find('image')
#         anims  = {}
#         for tile in ts.findall('tile'):
#             anim = tile.find('animation')
#             if anim is not None:
#                 anims[int(tile.get('id'))] = [
#                     (int(f.get('tileid')), int(f.get('duration')))
#                     for f in anim.findall('frame')
#                 ]
#         tilesets.append(dict(
#             firstgid  = int(ts.get('firstgid')),
#             name      = ts.get('name'),
#             source    = img_el.get('source') if img_el is not None else None,
#             cols      = int(ts.get('columns', 1)),
#             tw        = int(ts.get('tilewidth',  TILE)),
#             th        = int(ts.get('tileheight', TILE)),
#             anims     = anims,
#         ))

#     layers = []
#     for layer in root.findall('layer'):
#         data_el = layer.find('data')
#         if data_el is None:
#             continue
#         tiles = {}
#         for chunk in data_el.findall('chunk'):
#             cx, cy = int(chunk.get('x')), int(chunk.get('y'))
#             cw     = int(chunk.get('width'))
#             for i, gid in enumerate(
#                 int(v) for v in chunk.text.strip().split(',') if v.strip()
#             ):
#                 if gid:
#                     tiles[(cx + i % cw, cy + i // cw)] = gid
#         layers.append(dict(
#             name    = layer.get('name', ''),
#             opacity = float(layer.get('opacity', 1.0)),
#             tiles   = tiles,
#         ))

#     return tilesets, layers


# # ── DungeonMap ────────────────────────────────────────────────────────────────

# class DungeonMap:
#     """
#     Loads a Tiled TMX file (infinite/chunked) and renders it each frame.

#     Parameters
#     ----------
#     tmx_path : str
#         Path to the .tmx file.
#     scale : int
#         Pixel scale factor (default 3 → 16px tiles become 48px).
#     asset_dir : str | None
#         Folder where the sprite-sheet PNGs live.
#         Defaults to the folder that contains the TMX file.
#     """

#     def __init__(self, tmx_path: str, scale: int = 3, asset_dir: str = None):
#         # resolve tmx_path relative to the caller's file, not the cwd
#         import inspect, pathlib
#         caller_dir = pathlib.Path(inspect.stack()[1].filename).parent
#         self.tmx_path  = str(caller_dir / tmx_path) if not os.path.isabs(tmx_path) else tmx_path
#         self.scale     = scale
#         self.ts        = TILE * scale          # tile size on screen
#         self.asset_dir = asset_dir or os.path.dirname(os.path.abspath(self.tmx_path))

#         # set after load()
#         self.tilesets   = []
#         self.layers     = []
#         self._sheets    = {}   # filename → Surface
#         self._cache     = {}   # raw_gid  → scaled Surface | None
#         self._anim_map  = {}   # raw_gid  → (tileset_dict, local_id)

#         self.world_x0 = self.world_y0 = 0
#         self.world_w  = self.world_h  = 0
#         self.pixel_w  = self.pixel_h  = 0   # total map size in screen pixels

#         # Fast O(1) collision sets (world tile coords) – built in load()
#         self._solid_tiles : set = set()   # walls + water

#     # ── public API ────────────────────────────────────────────────────────────

#     def load(self):
#         """Parse the TMX and load all sprite sheets. Call once after pygame.init()."""
#         self.tilesets, self.layers = _parse_tmx(self.tmx_path)
#         self._load_sheets()
#         self._build_anim_map()
#         self._calc_bounds()
#         self._build_collision_set()

#     def update(self):
#         """
#         Call every frame (or whenever you like) to keep animations alive.
#         Currently animation is time-based so this is a no-op,
#         but it's here so your game loop stays forward-compatible.
#         """
#         pass   # time.time() is read live inside resolve_gid

#     def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0):
#         """
#         Blit the visible portion of the map onto *surface*.

#         Parameters
#         ----------
#         surface : pygame.Surface
#             The target surface (usually your screen).
#         cam_x, cam_y : int
#             Camera offset in screen pixels.
#         """
#         sw, sh = surface.get_size()
#         ts = self.ts

#         tc0 = max(0, cam_x // ts)
#         tr0 = max(0, cam_y // ts)
#         tc1 = min(self.world_w, tc0 + sw // ts + 2)
#         tr1 = min(self.world_h, tr0 + sh // ts + 2)

#         for layer in self.layers:
#             op = layer['opacity']
#             for tr in range(tr0, tr1):
#                 for tc in range(tc0, tc1):
#                     wx  = tc + self.world_x0
#                     wy  = tr + self.world_y0
#                     gid = layer['tiles'].get((wx, wy), 0)
#                     if not gid:
#                         continue
#                     tile = self._get_tile(gid)
#                     if tile is None:
#                         continue
#                     sx = tc * ts - cam_x
#                     sy = tr * ts - cam_y
#                     if op < 1.0:
#                         tile = tile.copy()
#                         tile.set_alpha(int(op * 255))
#                     surface.blit(tile, (sx, sy))

#     def tile_at_screen(self, screen_x: int, screen_y: int,
#                        cam_x: int, cam_y: int):
#         """
#         Return the world tile coordinate under a screen pixel.
#         Useful for collision or click detection in your game.
#         """
#         tx = (screen_x + cam_x) // self.ts + self.world_x0
#         ty = (screen_y + cam_y) // self.ts + self.world_y0
#         return tx, ty

#     def get_bounds(self, margin: int = 0) -> pygame.Rect:
#         """
#         Return a pygame.Rect describing the playable area in screen pixels.

#         Parameters
#         ----------
#         margin : int
#             Shrink the boundary inward by this many pixels on every side.
#             Useful so sprites don't clip the very edge of the map.
#         """
#         return pygame.Rect(
#             margin,
#             margin,
#             self.pixel_w - margin * 2,
#             self.pixel_h - margin * 2,
#         )

#     def clamp_rect(self, rect: pygame.Rect, margin: int = 0) -> pygame.Rect:
#         """
#         Return a copy of *rect* clamped inside the map bounds.
#         Call this every frame for the player and each enemy.

#         Example
#         -------
#         player.rect = dungeon.clamp_rect(player.rect, margin=4)
#         """
#         bounds = self.get_bounds(margin)
#         return rect.clamp(bounds)

#     def is_solid(self, world_tx: int, world_ty: int) -> bool:
#         """Return True if this world tile coordinate is a wall or water."""
#         return (world_tx, world_ty) in self._solid_tiles

#     def resolve_collision(self, rect: pygame.Rect) -> pygame.Rect:
#         """
#         Push *rect* out of any solid wall/water tiles it overlaps.
#         Uses a tight hitbox at the feet of the sprite so big sprite art
#         doesn't block movement through doorways.

#         Call AFTER moving the entity, then sync .x/.y:
#             entity.rect = dungeon.resolve_collision(entity.rect)
#             entity.x = float(entity.rect.centerx)
#             entity.y = float(entity.rect.centery)
#         """
#         ts = self.ts

#         # Tight hitbox: 40% of sprite width, 25% of sprite height, at the feet
#         hw  = max(6, rect.width  * 2 // 10)   # half-width of hitbox
#         hh  = max(6, rect.height * 1 // 8)    # half-height of hitbox
#         # Place hitbox center at lower quarter of sprite
#         cx  = rect.centerx
#         cy  = rect.top + (rect.height * 3 // 4)
#         hit = pygame.Rect(cx - hw, cy - hh, hw * 2, hh * 2)

#         left_t  = (hit.left   // ts) + self.world_x0
#         right_t = (hit.right  // ts) + self.world_x0
#         top_t   = (hit.top    // ts) + self.world_y0
#         bot_t   = (hit.bottom // ts) + self.world_y0

#         for ty in range(top_t, bot_t + 1):
#             for tx in range(left_t, right_t + 1):
#                 if (tx, ty) not in self._solid_tiles:
#                     continue

#                 tile_rect = pygame.Rect(
#                     (tx - self.world_x0) * ts,
#                     (ty - self.world_y0) * ts,
#                     ts, ts,
#                 )

#                 if not hit.colliderect(tile_rect):
#                     continue

#                 ol  = hit.right  - tile_rect.left
#                 or_ = tile_rect.right  - hit.left
#                 ot  = hit.bottom - tile_rect.top
#                 ob  = tile_rect.bottom - hit.top

#                 if min(ol, or_) <= min(ot, ob):
#                     dx = -ol if ol < or_ else or_
#                     hit.x  += dx
#                     rect.x += dx
#                 else:
#                     dy = -ot if ot < ob else ob
#                     hit.y  += dy
#                     rect.y += dy

#         return rect

#     # ── internals ─────────────────────────────────────────────────────────────

#     def _build_collision_set(self):
#         """
#         Build solid tile set from the Walls layer, but exclude any tile
#         that is also covered by a floor or water layer (submerged/decorative walls).
#         """
#         # Tiles covered by any passable surface layer
#         passable = set()
#         PASSABLE_LAYERS = {
#             'Floor', 'Floor_darker_surface',
#             'Floor2_pool', 'Floor2_darker_surface',
#             'water_floor3',
#         }
#         for layer in self.layers:
#             if layer['name'] in PASSABLE_LAYERS:
#                 passable.update(layer['tiles'].keys())

#         # Wall tiles that are NOT covered by any passable tile = truly solid
#         self._solid_tiles = set()
#         for layer in self.layers:
#             if layer['name'] == 'Walls':
#                 for pos in layer['tiles']:
#                     if pos not in passable:
#                         self._solid_tiles.add(pos)

#         print(f"[DungeonMap] Solid wall tiles: {len(self._solid_tiles)}")

#     def _load_sheets(self):
#         for ts in self.tilesets:
#             src = ts['source']
#             if src and src not in self._sheets:
#                 path = os.path.join(self.asset_dir, src)
#                 if os.path.exists(path):
#                     self._sheets[src] = pygame.image.load(path).convert_alpha()
#                 else:
#                     print(f"[DungeonMap] WARNING: missing sprite sheet: {path}")

#     def _build_anim_map(self):
#         for ts in self.tilesets:
#             for lid, frames in ts['anims'].items():
#                 self._anim_map[ts['firstgid'] + lid] = (ts, lid)

#     def _calc_bounds(self):
#         xs, ys = [], []
#         for layer in self.layers:
#             for tx, ty in layer['tiles']:
#                 xs.append(tx); ys.append(ty)
#         if not xs:
#             return
#         self.world_x0 = min(xs)
#         self.world_y0 = min(ys)
#         self.world_w  = max(xs) - self.world_x0 + 1
#         self.world_h  = max(ys) - self.world_y0 + 1
#         self.pixel_w  = self.world_w * self.ts
#         self.pixel_h  = self.world_h * self.ts

#     def _resolve_gid(self, gid: int) -> int:
#         """Strip flip bits and advance animation frame."""
#         raw = gid & 0x1FFFFFFF
#         if raw not in self._anim_map:
#             return raw
#         ts, lid = self._anim_map[raw]
#         frames  = ts['anims'][lid]
#         total   = sum(d for _, d in frames)
#         t_ms    = int(time.time() * 1000) % total
#         acc     = 0
#         for frame_lid, dur in frames:
#             acc += dur
#             if t_ms < acc:
#                 return ts['firstgid'] + frame_lid
#         return ts['firstgid'] + frames[-1][0]

#     def _get_tile(self, gid: int) -> pygame.Surface | None:
#         """Return a cached, scaled Surface for this gid (animation-resolved)."""
#         raw = self._resolve_gid(gid)
#         if raw in self._cache:
#             return self._cache[raw]

#         # find tileset
#         ts = None
#         for t in reversed(self.tilesets):
#             if raw >= t['firstgid']:
#                 ts = t; break
#         if ts is None or not ts['source'] or ts['source'] not in self._sheets:
#             self._cache[raw] = None
#             return None

#         lid  = raw - ts['firstgid']
#         col  = lid % ts['cols']
#         row  = lid // ts['cols']
#         rect = pygame.Rect(col * ts['tw'], row * ts['th'], ts['tw'], ts['th'])

#         native = pygame.Surface((ts['tw'], ts['th']), pygame.SRCALPHA)
#         native.blit(self._sheets[ts['source']], (0, 0), rect)
#         scaled = pygame.transform.scale(native, (self.ts, self.ts))

#         self._cache[raw] = scaled
#         return scaled


"""
dungeon_map.py  –  importable DungeonMap class
-----------------------------------------------
Usage in your main.py:

    from dungeon_map import DungeonMap

    dungeon = DungeonMap("Dungeon1.tmx", scale=3)
    dungeon.load()                        # call once after pygame.init()

    # in your game loop:
    dungeon.update()                      # advances animations
    dungeon.draw(screen, cam_x, cam_y)    # renders to any surface
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
        for chunk in data_el.findall('chunk'):
            cx, cy = int(chunk.get('x')), int(chunk.get('y'))
            cw     = int(chunk.get('width'))
            for i, gid in enumerate(
                int(v) for v in chunk.text.strip().split(',') if v.strip()
            ):
                if gid:
                    tiles[(cx + i % cw, cy + i // cw)] = gid
        layers.append(dict(
            name    = layer.get('name', ''),
            opacity = float(layer.get('opacity', 1.0)),
            tiles   = tiles,
        ))

    return tilesets, layers


# ── DungeonMap ────────────────────────────────────────────────────────────────

class DungeonMap:
    """
    Loads a Tiled TMX file (infinite/chunked) and renders it each frame.

    Parameters
    ----------
    tmx_path : str
        Path to the .tmx file.
    scale : int
        Pixel scale factor (default 3 → 16px tiles become 48px).
    asset_dir : str | None
        Folder where the sprite-sheet PNGs live.
        Defaults to the folder that contains the TMX file.
    """

    def __init__(self, tmx_path: str, scale: int = 3, asset_dir: str = None):
        # resolve tmx_path relative to the caller's file, not the cwd
        import inspect, pathlib
        caller_dir = pathlib.Path(inspect.stack()[1].filename).parent
        self.tmx_path  = str(caller_dir / tmx_path) if not os.path.isabs(tmx_path) else tmx_path
        self.scale     = scale
        self.ts        = TILE * scale          # tile size on screen
        self.asset_dir = asset_dir or os.path.dirname(os.path.abspath(self.tmx_path))

        # set after load()
        self.tilesets   = []
        self.layers     = []
        self._sheets    = {}   # filename → Surface
        self._cache     = {}   # raw_gid  → scaled Surface | None
        self._anim_map  = {}   # raw_gid  → (tileset_dict, local_id)

        self.world_x0 = self.world_y0 = 0
        self.world_w  = self.world_h  = 0
        self.pixel_w  = self.pixel_h  = 0   # total map size in screen pixels

        # Fast O(1) collision sets (world tile coords) – built in load()
        self._solid_tiles : set = set()   # walls + water

    # ── public API ────────────────────────────────────────────────────────────

    def load(self):
        """Parse the TMX and load all sprite sheets. Call once after pygame.init()."""
        self.tilesets, self.layers = _parse_tmx(self.tmx_path)
        self._load_sheets()
        self._build_anim_map()
        self._calc_bounds()
        self._build_collision_set()

    def update(self):
        """
        Call every frame (or whenever you like) to keep animations alive.
        Currently animation is time-based so this is a no-op,
        but it's here so your game loop stays forward-compatible.
        """
        pass   # time.time() is read live inside resolve_gid

    def draw(self, surface: pygame.Surface, cam_x: int = 0, cam_y: int = 0):
        """
        Blit the visible portion of the map onto *surface*.

        Parameters
        ----------
        surface : pygame.Surface
            The target surface (usually your screen).
        cam_x, cam_y : int
            Camera offset in screen pixels.
        """
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

    def tile_at_screen(self, screen_x: int, screen_y: int,
                       cam_x: int, cam_y: int):
        """
        Return the world tile coordinate under a screen pixel.
        Useful for collision or click detection in your game.
        """
        tx = (screen_x + cam_x) // self.ts + self.world_x0
        ty = (screen_y + cam_y) // self.ts + self.world_y0
        return tx, ty

    def get_bounds(self, margin: int = 0) -> pygame.Rect:
        """
        Return a pygame.Rect describing the playable area in screen pixels.

        Parameters
        ----------
        margin : int
            Shrink the boundary inward by this many pixels on every side.
            Useful so sprites don't clip the very edge of the map.
        """
        return pygame.Rect(
            margin,
            margin,
            self.pixel_w - margin * 2,
            self.pixel_h - margin * 2,
        )

    def clamp_rect(self, rect: pygame.Rect, margin: int = 0) -> pygame.Rect:
        """
        Return a copy of *rect* clamped inside the map bounds.
        Call this every frame for the player and each enemy.

        Example
        -------
        player.rect = dungeon.clamp_rect(player.rect, margin=4)
        """
        bounds = self.get_bounds(margin)
        return rect.clamp(bounds)

    def is_solid(self, world_tx: int, world_ty: int) -> bool:
        """Return True if this world tile coordinate is a wall or water."""
        return (world_tx, world_ty) in self._solid_tiles

    def resolve_collision(self, rect: pygame.Rect) -> pygame.Rect:
        """
        Push *rect* out of any solid wall/water tiles it overlaps.
        Uses a tight hitbox at the feet of the sprite so big sprite art
        doesn't block movement through doorways.

        Call AFTER moving the entity, then sync .x/.y:
            entity.rect = dungeon.resolve_collision(entity.rect)
            entity.x = float(entity.rect.centerx)
            entity.y = float(entity.rect.centery)
        """
        ts = self.ts

        # Tight hitbox: 40% of sprite width, 25% of sprite height, at the feet
        hw  = max(6, rect.width  * 2 // 10)   # half-width of hitbox
        hh  = max(6, rect.height * 1 // 8)    # half-height of hitbox
        # Place hitbox center at lower quarter of sprite
        cx  = rect.centerx
        cy  = rect.top + (rect.height * 3 // 4)
        hit = pygame.Rect(cx - hw, cy - hh, hw * 2, hh * 2)

        left_t  = (hit.left   // ts) + self.world_x0
        right_t = (hit.right  // ts) + self.world_x0
        top_t   = (hit.top    // ts) + self.world_y0
        bot_t   = (hit.bottom // ts) + self.world_y0

        for ty in range(top_t, bot_t + 1):
            for tx in range(left_t, right_t + 1):
                if (tx, ty) not in self._solid_tiles:
                    continue

                tile_rect = pygame.Rect(
                    (tx - self.world_x0) * ts,
                    (ty - self.world_y0) * ts,
                    ts, ts,
                )

                if not hit.colliderect(tile_rect):
                    continue

                ol  = hit.right  - tile_rect.left
                or_ = tile_rect.right  - hit.left
                ot  = hit.bottom - tile_rect.top
                ob  = tile_rect.bottom - hit.top

                if min(ol, or_) <= min(ot, ob):
                    dx = -ol if ol < or_ else or_
                    hit.x  += dx
                    rect.x += dx
                else:
                    dy = -ot if ot < ob else ob
                    hit.y  += dy
                    rect.y += dy

        return rect

    # ── internals ─────────────────────────────────────────────────────────────

    def _build_collision_set(self):
        """
        Solid = Walls layer tiles + water_floor3 tiles.
        Floor tiles are always walkable and are NOT in this set.
        """
        SOLID_LAYERS = {'Walls', 'water_floor3', 'walls_under_water'}
        self._solid_tiles = set()
        for layer in self.layers:
            if layer['name'] in SOLID_LAYERS:
                self._solid_tiles.update(layer['tiles'].keys())
        print(f"[DungeonMap] Solid tiles loaded: {len(self._solid_tiles)}")

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
        """Strip flip bits and advance animation frame."""
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
        """Return a cached, scaled Surface for this gid (animation-resolved)."""
        raw = self._resolve_gid(gid)
        if raw in self._cache:
            return self._cache[raw]

        # find tileset
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