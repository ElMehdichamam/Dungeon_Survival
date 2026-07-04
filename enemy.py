import pygame
import math
import random
import os


# ─────────────────────────────────────────────────────────────────────────────
#  SPRITESHEET LOADER  (same layout as player: rows = directions, cols = frames)
# ─────────────────────────────────────────────────────────────────────────────
FRAME_W = 64
FRAME_H = 64

DIR_DOWN  = 1
DIR_LEFT  = 2
DIR_RIGHT = 0
DIR_UP    = 3

def _load_sheet(path, n_cols, scale=1):
    """Load all 4 directions from a spritesheet. Returns dict[direction] = [frames]."""
    sheet = pygame.image.load(path).convert_alpha()
    result = {}
    for row in range(4):
        frames = []
        for col in range(n_cols):
            surf = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
            surf.blit(sheet, (0, 0), (col * FRAME_W, row * FRAME_H, FRAME_W, FRAME_H))
            if scale != 1:
                surf = pygame.transform.scale(
                    surf, (FRAME_W * scale, FRAME_H * scale))
            frames.append(surf)
        result[row] = frames
    return result


def _make_placeholder(w, h, color, label=""):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (0, 0, w, h), border_radius=6)
    pygame.draw.rect(surf, (255, 255, 255), (0, 0, w, h), 2, border_radius=6)
    if label:
        try:
            f = pygame.font.SysFont("consolas", 11)
            t = f.render(label, True, (255, 255, 255))
            surf.blit(t, (w // 2 - t.get_width() // 2,
                          h // 2 - t.get_height() // 2))
        except Exception:
            pass
    return {d: [surf] for d in (DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP)}


# ─────────────────────────────────────────────────────────────────────────────
#  GOBLIN SPRITE CONFIG
#  filename: (n_cols)
# ─────────────────────────────────────────────────────────────────────────────
GOBLIN_SHEETS = {
    "idle":        ("orc1_idle_with_shadow.png",              4),
    "walk":        ("orc1_walk_with_shadow.png",              6),
    "run":         ("orc1_run_with_shadow.png",               8),
    "attack":      ("orc1_attack_with_shadow.png",            8),
    "walk_attack": ("orc1_walk_attack_front _with_shadow.png",6),  # FIX BUG-03: filename had double underscore, actual file has space+underscore
    "run_attack":  ("orc1_run_attack_front_with_shadow.png",  8),
    "hurt":        ("orc1_hurt_with_shadow.png",              6),
    "death":       ("orc1_death_with_shadow.png",             8),
}

GOBLIN_SCALE = 2


# ─────────────────────────────────────────────────────────────────────────────
#  SIMPLE ANIMATION HELPER
# ─────────────────────────────────────────────────────────────────────────────
class _Anim:
    def __init__(self, frames_by_dir: dict, fps: int, loop=True):
        self.frames_by_dir = frames_by_dir
        self.fps           = fps
        self.loop          = loop
        self.index         = 0
        self.timer         = 0.0
        self.done          = False
        self.death_finished = False

    def reset(self):
        self.index = 0
        self.timer = 0.0
        self.done  = False

    def update(self, dt_ms: float):
        if self.done:
            return
        self.timer += dt_ms
        spf = 1000.0 / self.fps
        while self.timer >= spf:
            self.timer -= spf
            self.index += 1
            if self.index >= len(self.frames_by_dir[DIR_DOWN]):
                if self.loop:
                    self.index = 0
                else:
                    self.index          = len(self.frames_by_dir[DIR_DOWN]) - 1
                    self.done           = True
                    self.death_finished = True
                    break

    def image(self, direction: int) -> pygame.Surface:
        frames = self.frames_by_dir.get(direction, self.frames_by_dir[DIR_DOWN])
        idx    = min(self.index, len(frames) - 1)
        return frames[idx]


# ─────────────────────────────────────────────────────────────────────────────
#  ENEMY TYPES  (non-goblin fallback placeholders)
# ─────────────────────────────────────────────────────────────────────────────
ENEMY_TYPES = {
    "goblin":   dict(hp=60,  dmg=8,  speed=90,  reward=10),
    "skeleton": dict(hp=70,  dmg=12, speed=70,  reward=20),
    "orc":      dict(hp=130, dmg=18, speed=55,  reward=35),
    "mage":     dict(hp=55,  dmg=22, speed=80,  reward=40),
}

PLACEHOLDER_COLORS = {
    "goblin":   (80,  160,  60),
    "skeleton": (180, 180, 200),
    "orc":      (60,  140,  60),
    "mage":     (120,  60, 200),
}

# FIX BUG-09: multiplicative tint applied per type so skeleton/orc/mage
# can reuse the (only available) goblin orc1_* sheets and still look distinct.
# None = no tint (original goblin colour).
ENEMY_TINTS = {
    "goblin":   None,
    "skeleton": (210, 210, 230),   # pale / cool
    "orc":      (150, 220, 150),   # green
    "mage":     (180, 140, 240),   # purple
}

# Module-level cache so multiple enemies of the same type don't reload PNGs.
_SHEET_CACHE: dict = {}


def _tint_frames(frames_by_dir, color):
    """Return a copy of frames_by_dir with multiplicative tint applied."""
    out = {}
    for d, frames in frames_by_dir.items():
        tinted = []
        for f in frames:
            cp = f.copy()
            cp.fill(color, special_flags=pygame.BLEND_RGBA_MULT)
            tinted.append(cp)
        out[d] = tinted
    return out


class Enemy:
    AGGRO_RANGE  = 400
    ATTACK_RANGE = 45
    ATTACK_CD    = 1200   # ms

    def __init__(self, x: float, y: float, etype: str = "goblin",
                 sprite_folder: str | None = None):
        cfg = ENEMY_TYPES.get(etype, ENEMY_TYPES["goblin"])
        self.etype   = etype
        self.max_hp  = cfg["hp"]
        self.hp      = cfg["hp"]
        self.dmg     = cfg["dmg"]
        self.speed   = cfg["speed"]
        self.reward  = cfg["reward"]

        self.x = float(x)
        self.y = float(y)

        # Load sprites
        self._sheets = self._load_sprites(etype, sprite_folder)

        # Animations: state → (_Anim, fps, loop)
        self._anims = {
            "idle":        _Anim(self._sheets["idle"],        6,  True),
            "walk":        _Anim(self._sheets["walk"],        8,  True),
            "run":         _Anim(self._sheets["run"],         12, True),
            "attack":      _Anim(self._sheets["attack"],      10, False),
            "walk_attack": _Anim(self._sheets["walk_attack"], 10, False),
            "run_attack":  _Anim(self._sheets["run_attack"],  12, False),
            "hurt":        _Anim(self._sheets["hurt"],        10, False),
            "death":       _Anim(self._sheets["death"],       8,  False),
        }
        # FIX BUG-01: "dead" alias so take_damage("dead") finds a valid anim
        self._anims["dead"] = self._anims["death"]

        self.state     = "walk"
        self.direction = DIR_DOWN
        self.anim      = self._anims["walk"]

        # FIX BUG-09: all types reuse the goblin sheets, so the rect uses the
        # same scale regardless of etype.
        fw = FRAME_W * GOBLIN_SCALE
        fh = FRAME_H * GOBLIN_SCALE
        self.rect        = pygame.Rect(0, 0, fw, fh)
        self.rect.center = (int(self.x), int(self.y))
        self.image       = self.anim.image(self.direction)

        self._attack_timer  = 0
        self._hurt_timer    = 0
        self._knockback_vel = pygame.math.Vector2(0, 0)

    # ── sprite loading ────────────────────────────────────────────────────
    def _load_sprites(self, etype, folder):
        """
        FIX BUG-09: every type now reuses the orc1_* sheets (the only ones
        available). Per-type tint differentiates skeleton/orc/mage from goblin.
        Sheets are cached at module scope so spawning N enemies doesn't hit
        disk N times.
        """
        sheets = {}
        if not folder:
            color = PLACEHOLDER_COLORS.get(etype, (100, 100, 100))
            ph    = _make_placeholder(FRAME_W * GOBLIN_SCALE, FRAME_H * GOBLIN_SCALE,
                                      color, etype[:3].upper())
            return {anim_name: ph for anim_name in GOBLIN_SHEETS}

        scale = GOBLIN_SCALE
        tint  = ENEMY_TINTS.get(etype)
        for anim_name, (filename, n_cols) in GOBLIN_SHEETS.items():
            cache_key = (filename, scale)
            base = _SHEET_CACHE.get(cache_key)
            if base is None:
                path = os.path.join(folder, filename)
                if os.path.exists(path):
                    try:
                        base = _load_sheet(path, n_cols, scale)
                    except Exception:
                        base = None
                if base is None:
                    base = _make_placeholder(
                        FRAME_W * scale, FRAME_H * scale,
                        PLACEHOLDER_COLORS.get("goblin"), "GOB")
                _SHEET_CACHE[cache_key] = base
            sheets[anim_name] = _tint_frames(base, tint) if tint else base
        return sheets

    # ── public API ────────────────────────────────────────────────────────
    @property
    def is_alive(self):
        return self.state != "dead"

    def _set_state(self, state: str):
        if self.state == state:
            return
        self.state = state
        self.anim  = self._anims[state]
        self.anim.reset()

    def take_damage(self, amount: int,
                    knockback_dir: pygame.math.Vector2 | None = None):
        if not self.is_alive:
            return
        self.hp -= amount
        if self.hp <= 0:
            self.hp = 0
            # FIX BUG-01: use "dead" state so is_alive, update(), and main.py removal all match
            self._set_state("dead")
        else:
            self._hurt_timer = 300
            self._set_state("hurt")
            if knockback_dir and knockback_dir.length() > 0:
                self._knockback_vel = knockback_dir.normalize() * 6

    def update(self, dt_ms: float,
               player_pos: pygame.math.Vector2, player,
               screen_w: int = 960, screen_h: int = 640):
        if self.state == "dead":
            self.anim.update(dt_ms)
            self.image = self.anim.image(self.direction)
            return

        dt = dt_ms / 1000.0

        # Knockback decay
        if self._knockback_vel.length() > 0.1:
            self.x += self._knockback_vel.x
            self.y += self._knockback_vel.y
            self._knockback_vel *= 0.80
        else:
            self._knockback_vel = pygame.math.Vector2(0, 0)

        # Hurt recovery
        if self.state == "hurt":
            self._hurt_timer -= dt_ms
            if self._hurt_timer <= 0 or self.anim.done:
                self._set_state("walk")

        # Chase + attack
        if self.state in ("walk", "run", "idle"):
            to_player = player_pos - pygame.math.Vector2(self.x, self.y)
            dist      = to_player.length()

            # Update facing direction
            if dist > 1:
                if abs(to_player.x) >= abs(to_player.y):
                    self.direction = DIR_RIGHT if to_player.x > 0 else DIR_LEFT
                else:
                    self.direction = DIR_DOWN if to_player.y > 0 else DIR_UP

            if dist < self.ATTACK_RANGE:
                self._attack_timer -= dt_ms
                if self._attack_timer <= 0:
                    self._attack_timer = self.ATTACK_CD
                    if hasattr(player, "take_damage"):
                        player.take_damage(self.dmg)
                self._set_state("idle")
            elif dist < self.AGGRO_RANGE:
                move = to_player.normalize() * self.speed * dt
                # FIX BUG-10: if a wall blocked us last frame, slide along it
                # (zero the blocked axis; if both axes were blocked we're in a
                # corner — bias perpendicular to keep moving instead of jamming).
                bx = getattr(self, "_blocked_x", False)
                by = getattr(self, "_blocked_y", False)
                if bx and not by:
                    move.x = 0
                    if abs(move.y) < 0.1:
                        move.y = self.speed * dt * (1 if random.random() < 0.5 else -1)
                elif by and not bx:
                    move.y = 0
                    if abs(move.x) < 0.1:
                        move.x = self.speed * dt * (1 if random.random() < 0.5 else -1)
                elif bx and by:
                    if abs(to_player.x) >= abs(to_player.y):
                        move.x, move.y = 0, self.speed * dt * (1 if random.random() < 0.5 else -1)
                    else:
                        move.x, move.y = self.speed * dt * (1 if random.random() < 0.5 else -1), 0
                self.x += move.x
                self.y += move.y
                self._set_state("walk")
            else:
                self._set_state("idle")

        # Clamp enemy position to map boundaries (keeping entire rect inside)
        half_w = self.rect.width // 2
        half_h = self.rect.height // 2
        self.x = max(half_w, min(screen_w - half_w, self.x))
        self.y = max(half_h, min(screen_h - half_h, self.y))

        self.rect.center = (int(self.x), int(self.y))
        self.anim.update(dt_ms)
        self.image = self.anim.image(self.direction)

    def draw_health_bar(self, surface: pygame.Surface):
        if not self.is_alive:
            return
        bw    = self.rect.width
        bx    = self.rect.left
        by    = self.rect.top - 8
        ratio = self.hp / self.max_hp
        pygame.draw.rect(surface, (80, 0, 0),    (bx, by, bw, 5))
        pygame.draw.rect(surface, (60, 200, 60), (bx, by, int(bw * ratio), 5))
        pygame.draw.rect(surface, (200, 200, 200), (bx, by, bw, 5), 1)


# ─────────────────────────────────────────────────────────────────────────────
#  WAVE MANAGER
# ─────────────────────────────────────────────────────────────────────────────
WAVE_DEFINITIONS = [
    [("goblin", 4)],
    [("goblin", 6)],
    [("goblin", 5)],
    [("goblin", 8)],
    [("goblin", 10)],
]


class WaveManager:
    def __init__(self, on_spawn_cb, spawn_region: pygame.Rect,
                 spawn_interval_ms: int = 1000,
                 between_waves_ms:  int = 3000):
        self._cb             = on_spawn_cb
        self._region         = spawn_region
        self._spawn_interval = spawn_interval_ms
        self._between_waves  = between_waves_ms
        self._wave_timer     = 0
        self._spawn_timer    = 0
        self._queue: list[str] = []
        self.current_wave    = 0
        self.total_waves     = len(WAVE_DEFINITIONS)
        self.all_waves_done  = False
        self._waiting        = False
        self._enemies_ref: list[Enemy] = []

    def register_enemies(self, enemies_list):
        self._enemies_ref = enemies_list

    def start(self):
        self._load_wave(0)

    def _load_wave(self, idx: int):
        if idx >= len(WAVE_DEFINITIONS):
            self.all_waves_done = True
            return
        self.current_wave = idx + 1
        self._queue.clear()
        for etype, count in WAVE_DEFINITIONS[idx]:
            self._queue.extend([etype] * count)
        random.shuffle(self._queue)
        self._waiting     = False
        self._spawn_timer = 0

    def _random_spawn_pos(self):
        r    = self._region
        edge = random.choice(["top", "bottom", "left", "right"])
        if edge == "top":    return r.left + random.randint(0, r.width), r.top
        if edge == "bottom": return r.left + random.randint(0, r.width), r.bottom
        if edge == "left":   return r.left, r.top + random.randint(0, r.height)
        return r.right, r.top + random.randint(0, r.height)

    def update(self, dt_ms: float):
        if self.all_waves_done:
            return

        alive = [e for e in self._enemies_ref if e.is_alive]

        if self._waiting:
            self._wave_timer -= dt_ms
            if self._wave_timer <= 0:
                self._load_wave(self.current_wave)
            return

        if self._queue:
            self._spawn_timer -= dt_ms
            if self._spawn_timer <= 0:
                self._spawn_timer = self._spawn_interval
                etype = self._queue.pop(0)
                x, y  = self._random_spawn_pos()
                self._cb(etype, x, y)
        elif not alive:
            if self.current_wave >= self.total_waves:
                self.all_waves_done = True
            else:
                self._waiting    = True
                self._wave_timer = self._between_waves