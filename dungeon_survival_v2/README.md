# Dungeon Survival (v2)

A top-down dungeon survival game built from the PRD with Python + Pygame-CE +
pytmx.  Survive 5 waves of enemies, then defeat the Lich King and the Stone
Golem to win.

## Run

```bash
pip install pygame-ce pytmx
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| WASD / Arrows | Move |
| Shift + Move | Run |
| J (hold) | Attack the nearest enemy in range |
| Shift + J | Run attack |
| Ctrl + J | Walk attack |
| R | Restart (on the Game Over / Victory screen) |
| ESC | Quit |

## Structure

```
main.py        entry point
settings.py    every tunable constant (no magic numbers elsewhere)
assets.py      AssetLoader — loads/slices/tints/caches sprite sheets
map.py         GameMap — TMX load, render, collision, pathfinding flow field
camera.py      Camera — world->screen, follow + clamp
entities/      Entity base, Player, Enemy, LichKing, StoneGolem
systems/       WaveManager, combat helpers, HUD + damage numbers
game.py        Game — window, main loop, state machine, combat resolution
```

## Decisions / deviations from the PRD draft

These were forced by what the real assets actually contain; each keeps the
PRD's intent while making the game correct and playable.

1. **Chunked map.**  `Dungeon1.tmx` is stored as an *infinite* (chunked) map
   (its header's `infinite="0"` is wrong), which pytmx cannot read.  On load we
   flatten the chunks into a normal finite `.tmx` (cached as `Dungeon1_flat.tmx`)
   and hand that to pytmx.  The real map is **64×48** tiles, not the 16×24 in
   the header.

2. **Tinting.**  The PRD's `apply_tint` used `color + (0,)` which multiplies
   *alpha* by zero (the sprite disappears).  A plain RGB multiply also can't
   turn the green orc base blue/red/purple — it only darkens.  We desaturate to
   luminance and multiply the tint onto that, giving clearly distinct
   blue skeleton / red orc / purple mage variants (goblin keeps the green base).

3. **Spawning & aggro.**  The dungeon doesn't fill its bounding rect, so
   "spawn on map edges" is meaningless here — enemies spawn on reachable floor
   tiles ≥300px from the player.  `AGGRO_RANGE` was raised from 400 (smaller
   than this arena) so wave enemies actually hunt the player, and they latch on
   once aggroed.

4. **Pathfinding.**  Straight-line chasing got enemies stuck behind walls and
   waves never cleared.  A single BFS flow field from the player's tile (shared
   by all enemies) lets them route around walls cheaply.

5. **Collision.**  Tile-based with axis-separated sliding (PRD §5).  Solid =
   the `Walls` layer **or** any non-floor void tile, which keeps actors on the
   visible dungeon floor.  Play is confined to the connected arena (flood-filled
   from the centre).
```
