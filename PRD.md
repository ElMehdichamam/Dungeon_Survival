# PRD — Dungeon Survival (Rebuild)
> Version 1.0 | Engine: Python + Pygame | Map: pytmx + Tiled

---

## 0. INSTRUCTIONS FOR CLAUDE CODE

```
1. Create a new folder called dungeon_survival_v2/ next to the original project
2. Copy ONLY the assets into it (all .png files + Dungeon1.tmx)
3. Build every .py file from scratch — do NOT copy old code
4. After each file, run a quick test before moving to the next
5. Use this PRD as the single source of truth for all decisions
```

---

## 1. PROJECT OVERVIEW

| Field | Value |
|-------|-------|
| Game name | Dungeon Survival |
| Genre | Top-down dungeon survival |
| Engine | Python 3.11+ / Pygame-CE |
| Map format | Tiled (.tmx) via pytmx |
| Resolution | 960 × 640 px |
| Target FPS | 60 |

### Concept
The player is a swordsman trapped in a dungeon.
Survive 5 waves of enemies then defeat the final boss to escape.

---

## 2. FILE STRUCTURE

```
dungeon_survival_v2/
│
├── main.py          ← entry point only: Game().run()
├── settings.py      ← ALL constants, zero magic numbers elsewhere
├── assets.py        ← AssetLoader: loads every sprite sheet once
│
├── map.py           ← GameMap: pytmx load, draw, collision
├── camera.py        ← Camera: world→screen conversion, clamping
│
├── entities/
│   ├── __init__.py
│   ├── base.py      ← Entity base class
│   ├── player.py    ← Player(Entity)
│   ├── enemy.py     ← Enemy(Entity)
│   └── boss.py      ← LichKing(Enemy), StoneGolem(Enemy)
│
├── systems/
│   ├── __init__.py
│   ├── wave.py      ← WaveManager
│   ├── combat.py    ← damage, knockback, hit detection
│   └── hud.py       ← HP bar, wave info, damage numbers
│
└── game.py          ← Game class, main loop, state machine
```

---

## 3. SETTINGS (settings.py)

```python
# Screen
SCREEN_W, SCREEN_H = 960, 640
FPS = 60
TITLE = "Dungeon Survival"

# Player
PLAYER_SPEED     = 180   # px/sec
PLAYER_RUN_MULT  = 1.6
PLAYER_HP        = 100
PLAYER_DMG       = 30
PLAYER_RANGE     = 120
PLAYER_INVIC_MS  = 600

# Enemy base stats (overridden per type)
AGGRO_RANGE  = 400
ATTACK_RANGE = 45
ATTACK_CD_MS = 1200

# Sprite dimensions
FRAME_W = 64
FRAME_H = 64

# Enemy types: name → (hp, dmg, speed, reward, tint_color or None)
ENEMY_TYPES = {
    "goblin":   (60,  8,  90, 10, None),
    "skeleton": (70,  12, 70, 20, (150, 180, 255)),  # blue tint
    "orc":      (130, 18, 55, 35, (255, 120, 120)),  # red tint
    "mage":     (55,  22, 80, 40, (200, 120, 255)),  # purple tint
}

# Waves definition
WAVES = [
    [("goblin", 4)],
    [("goblin", 4), ("skeleton", 2)],
    [("skeleton", 3), ("orc", 2)],
    [("orc", 2), ("mage", 2)],
    [("goblin", 4), ("orc", 2), ("mage", 2)],
]
BETWEEN_WAVES_MS  = 3000
SPAWN_INTERVAL_MS = 1100

# Boss
LICH_HP   = 600
GOLEM_HP  = 800

# UI Colors
COLOR_HP_BG  = (80, 0, 0)
COLOR_HP_FG  = (220, 60, 60)
COLOR_GOLD   = (240, 210, 80)
COLOR_WHITE  = (255, 255, 255)
COLOR_DAMAGE = (255, 60, 60)
```

---

## 4. ASSET LOADER (assets.py)

### Sprite sheets available

| File | Character | Animations |
|------|-----------|------------|
| Swordsman_lvl1_Idle_with_shadow.png | Player | idle (12 frames, 4 dirs) |
| Swordsman_lvl1_Walk_with_shadow.png | Player | walk (6f) |
| Swordsman_lvl1_Run_with_shadow.png | Player | run (8f) |
| Swordsman_lvl1_attack_with_shadow.png | Player | attack (8f) |
| Swordsman_lvl1_Walk_Attack_with_shadow.png | Player | walk_attack (6f) |
| Swordsman_lvl1_Run_Attack_with_shadow.png | Player | run_attack (8f) |
| Swordsman_lvl1_Hurt_with_shadow.png | Player | hurt (5f) |
| Swordsman_lvl1_Death_with_shadow.png | Player | death (7f) |
| orc1_idle_with_shadow.png | Goblin/Enemies | idle (4f) |
| orc1_walk_with_shadow.png | | walk (6f) |
| orc1_run_with_shadow.png | | run (8f) |
| orc1_attack_with_shadow.png | | attack (8f) |
| orc1_hurt_with_shadow.png | | hurt (6f) |
| orc1_death_with_shadow.png | | death (8f) |

### Spritesheet layout
- Rows = directions: DOWN=0, LEFT=1, RIGHT=2, UP=3  *(verify with .tmx)*
- Cols = animation frames (left to right)
- Each frame: 64×64 px
- Scale factor: ×2 for player and goblin

### Tinting system for enemy variants
```python
def apply_tint(surface, color):
    tinted = surface.copy()
    tinted.fill(color + (0,), special_flags=pygame.BLEND_RGBA_MULT)
    return tinted
```
- skeleton → blue tint (150, 180, 255)
- orc      → red tint  (255, 120, 120)
- mage     → purple tint (200, 120, 255)

---

## 5. MAP SYSTEM (map.py)

### Loading
```python
class GameMap:
    def __init__(self, tmx_path, scale=2):
        self.tmx = pytmx.load_pygame(tmx_path, pixelalpha=True)
        self.scale = scale
        self.tile_w = self.tmx.tilewidth * scale
        self.tile_h = self.tmx.tileheight * scale
        self.pixel_w = self.tmx.width * self.tile_w
        self.pixel_h = self.tmx.height * self.tile_h
        self._build_collision_rects()
```

### Collision detection
```python
def _build_collision_rects(self):
    # Step 1: print ALL layer names to find the correct collision layer
    for layer in self.tmx.layers:
        print(f"Layer: {layer.name}")
    
    # Step 2: build rects from the collision layer
    self.walls = []
    for layer in self.tmx.layers:
        if hasattr(layer, 'data'):  # tile layer
            if 'wall' in layer.name.lower() or 'collision' in layer.name.lower():
                for x, y, gid in layer:
                    if gid:
                        rect = pygame.Rect(
                            x * self.tile_w,
                            y * self.tile_h,
                            self.tile_w,
                            self.tile_h
                        )
                        self.walls.append(rect)
```

### Wall sliding (CRITICAL — replaces old broken system)
```python
def move_and_slide(self, entity, dx, dy):
    """
    Move entity with wall sliding.
    Separates X and Y movement to allow sliding along walls.
    """
    # Move X only
    entity.rect.x += int(dx)
    for wall in self.walls:
        if entity.rect.colliderect(wall):
            if dx > 0: entity.rect.right = wall.left
            if dx < 0: entity.rect.left  = wall.right

    # Move Y only
    entity.rect.y += int(dy)
    for wall in self.walls:
        if entity.rect.colliderect(wall):
            if dy > 0: entity.rect.bottom = wall.top
            if dy < 0: entity.rect.top    = wall.bottom

    # Sync float position
    entity.x = float(entity.rect.centerx)
    entity.y = float(entity.rect.centery)
```

---

## 6. CAMERA (camera.py)

```python
class Camera:
    def __init__(self, map_w, map_h, screen_w, screen_h):
        self.map_w, self.map_h = map_w, map_h
        self.screen_w, self.screen_h = screen_w, screen_h
        self.x = self.y = 0

    def update(self, target_x, target_y):
        self.x = int(target_x - self.screen_w // 2)
        self.y = int(target_y - self.screen_h // 2)
        self.x = max(0, min(self.x, self.map_w - self.screen_w))
        self.y = max(0, min(self.y, self.map_h - self.screen_h))

    def to_screen(self, world_x, world_y):
        return world_x - self.x, world_y - self.y

    def apply(self, rect):
        return pygame.Rect(rect.x - self.x, rect.y - self.y,
                           rect.width, rect.height)
```

---

## 7. ENTITY BASE (entities/base.py)

```python
class Entity:
    def __init__(self, x, y, hp, frame_w, frame_h):
        self.x = float(x)
        self.y = float(y)
        self.max_hp = hp
        self.hp = hp
        self.rect = pygame.Rect(0, 0, frame_w, frame_h)
        self.rect.center = (int(x), int(y))
        self.direction = 0   # DIR_DOWN
        self.state = "idle"
        self.alive = True

    def take_damage(self, amount, knockback=None): ...
    def update(self, dt_ms, **kwargs): ...
    def draw(self, surface, camera): ...
```

---

## 8. PLAYER (entities/player.py)

### Controls
| Key | Action |
|-----|--------|
| WASD / Arrows | Move |
| Shift + Move | Run |
| J | Attack nearest enemy in range |
| Shift + J | Run attack |
| Ctrl + J | Walk attack |
| R | Restart (game over only) |
| ESC | Quit |

### States & transitions
```
idle ──(move)──► walk ──(shift)──► run
 ▲                                  │
 └──────────────(stop)──────────────┘
 
any ──(J key)──► attack / walk_attack / run_attack  (one-shot)
any ──(hit)───► hurt  (one-shot, then back to prev)
any ──(hp=0)──► death (one-shot, freeze on last frame)
```

### Boundary enforcement
Player position is clamped AFTER map.move_and_slide():
```python
half_w = self.rect.width  // 2
half_h = self.rect.height // 2
self.x = max(half_w, min(game_map.pixel_w - half_w, self.x))
self.y = max(half_h, min(game_map.pixel_h - half_h, self.y))
```

---

## 9. ENEMY (entities/enemy.py)

### AI States
```
idle ──(player enters AGGRO_RANGE=400)──► walk (chase)
walk ──(player enters ATTACK_RANGE=45)──► attack
attack ──(cooldown=1200ms)──────────────► walk
any ──(take hit)──────────────────────► hurt (300ms)
any ──(hp=0)──────────────────────────► death → remove
```

### Sprite loading
```python
def _load_sprites(self, assets, tint_color):
    sheets = assets.get_enemy_sheets()   # orc1_*.png
    if tint_color:
        sheets = {k: apply_tint(v, tint_color) for k, v in sheets.items()}
    return sheets
```

### Boundary enforcement (same as player)
After move_and_slide(), clamp to map bounds.

---

## 10. BOSS (entities/boss.py)

### LichKing
| Property | Value |
|----------|-------|
| HP | 600 |
| Phases | 2 (switches at 50% HP) |
| Phase 1 | chases player, melee attack |
| Phase 2 | faster + summons 2 goblins every 5 seconds |
| Summons | max 4 alive at once |

### StoneGolem
| Property | Value |
|----------|-------|
| HP | 800 |
| Phases | 2 (switches at 40% HP) |
| Phase 1 | slow, high damage melee |
| Phase 2 | stomps (AoE damage in radius 80px) |

### Boss UI
- Large health bar at bottom of screen (full width)
- Boss name + phase label
- Phase change: flash screen white briefly

---

## 11. WAVE SYSTEM (systems/wave.py)

### Wave sequence
```
Wave 1 → 4 goblins
Wave 2 → 4 goblins + 2 skeletons
Wave 3 → 3 skeletons + 2 orcs
Wave 4 → 2 orcs + 2 mages
Wave 5 → 4 goblins + 2 orcs + 2 mages
─── 3s pause ───
BOSS: LichKing
─── defeat ───
BOSS: StoneGolem
─── defeat ───
VICTORY screen
```

### Spawn rules
- Enemies spawn on the MAP EDGES (not screen edges)
- Minimum distance from player: 300px
- One enemy spawned every 1100ms until queue empty
- Next wave starts only when ALL enemies are dead AND death animation finished

---

## 12. HUD (systems/hud.py)

### Elements
```
Top-left:    [HP bar 200px wide] "HP 80/100"
Top-center:  "Wave 2/5  Alive: 3  Queue: 1"
Top-right:   "FPS 60"
Bottom:      Boss health bar (full width, only during boss fight)
Floating:    Damage numbers (rise up, fade out over 900ms)
Center:      "YOU DIED — [R] Restart" (on death)
Center:      "VICTORY!" in gold (on win)
```

---

## 13. GAME STATES (game.py)

```python
class GameState(Enum):
    PLAYING   = "playing"
    WAVE_END  = "wave_end"    # 3s countdown between waves
    BOSS      = "boss"
    GAME_OVER = "game_over"
    VICTORY   = "victory"
```

### Main loop structure
```python
def run(self):
    while self.running:
        dt = self.clock.tick(FPS)
        self._handle_events()
        self._update(dt)
        self._draw()
        pygame.display.flip()

def _update(self, dt):
    if self.state == GameState.PLAYING:
        self.player.update(dt, keys, self.game_map)
        self.wave_mgr.update(dt)
        for enemy in self.enemies:
            enemy.update(dt, self.player, self.game_map)
        self.camera.update(self.player.x, self.player.y)
```

---

## 14. BUILD CHECKLIST

Claude Code must verify each item before calling the build complete:

```
[ ] python main.py → window opens, no import errors
[ ] Map loads → MAP_W and MAP_H printed, both > 0
[ ] Player moves in all 4 directions
[ ] Player CANNOT leave the map from any edge
[ ] Player slides along walls (doesn't get stuck)
[ ] Goblin spawns and chases player with real sprite
[ ] All 4 enemy types show colored sprites (NO gray placeholder boxes)
[ ] Enemies slide along walls (don't get stuck)
[ ] Wave 1 completes → 3s countdown → Wave 2 starts
[ ] All 5 waves complete → LichKing spawns
[ ] LichKing defeated → StoneGolem spawns
[ ] StoneGolem defeated → VICTORY screen
[ ] Player dies → "YOU DIED" + [R] restarts cleanly
[ ] FPS stays above 50 with 10 enemies on screen
```

---

## 15. DEPENDENCIES

```bash
pip install pygame-ce pytmx
```

> Use pygame-ce (Community Edition), NOT the original pygame.
> If pygame-ce conflicts, fall back to: pip install pygame pytmx
