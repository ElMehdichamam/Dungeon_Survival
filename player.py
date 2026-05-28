import pygame
import sys
import os

# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# def sprite(filename):
#     return os.path.join(BASE_DIR, "assets", "sprites", filename)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def sprite(filename):
    return os.path.join(BASE_DIR, filename)

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
FRAME_W   = 64
FRAME_H   = 64
SCALE     = 2
SPEED     = 180   # pixels per second

WINDOW_W  = 800
WINDOW_H  = 500
BG_COLOR  = (30, 30, 40)

DIR_DOWN  = 0
DIR_LEFT  = 1
DIR_RIGHT = 2
DIR_UP    = 3

ANIMATIONS = {
    "idle":        (sprite("Swordsman_lvl1_Idle_with_shadow.png"),        12, 8),
    "walk":        (sprite("Swordsman_lvl1_Walk_with_shadow.png"),         6, 10),
    "run":         (sprite("Swordsman_lvl1_Run_with_shadow.png"),          8, 14),
    "attack":      (sprite("Swordsman_lvl1_attack_with_shadow.png"),       8, 14),
    "walk_attack": (sprite("Swordsman_lvl1_Walk_Attack_with_shadow.png"),  6, 12),
    "run_attack":  (sprite("Swordsman_lvl1_Run_Attack_with_shadow.png"),   8, 16),
    "hurt":        (sprite("Swordsman_lvl1_Hurt_with_shadow.png"),         5, 10),
    "death":       (sprite("Swordsman_lvl1_Death_with_shadow.png"),        7,  8),
}

ONE_SHOT = {"attack", "walk_attack", "run_attack", "hurt", "death"}


# ─────────────────────────────────────────────
#  SPRITESHEET LOADER
# ─────────────────────────────────────────────
def load_frames(path, n_frames, direction_row):
    sheet = pygame.image.load(path).convert_alpha()
    frames = []
    for col in range(n_frames):
        surf = pygame.Surface((FRAME_W, FRAME_H), pygame.SRCALPHA)
        surf.blit(sheet, (0, 0), (col * FRAME_W, direction_row * FRAME_H, FRAME_W, FRAME_H))
        surf = pygame.transform.scale(surf, (FRAME_W * SCALE, FRAME_H * SCALE))
        frames.append(surf)
    return frames


# ─────────────────────────────────────────────
#  CHARACTER
# ─────────────────────────────────────────────
class Character:
    def __init__(self, x=None, y=None):
        # HP
        self.max_hp = 100
        self.hp     = 100

        # Invincibility frames after taking a hit
        self.invincible       = False
        self.invincible_timer = 0.0
        self.INVINCIBLE_MS    = 600

        # Load all frames
        self.frames: dict[str, dict[int, list[pygame.Surface]]] = {}
        for state, (path, n_frames, _) in ANIMATIONS.items():
            self.frames[state] = {
                d: load_frames(path, n_frames, d)
                for d in (DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP)
            }

        self.state       = "idle"
        self.direction   = DIR_DOWN
        self.frame_index = 0
        self.timer       = 0.0
        self.locked      = False

        # Start position — defaults to center of standalone window
        self.x = float(x if x is not None else WINDOW_W // 2)
        self.y = float(y if y is not None else WINDOW_H // 2)

        # pos vector so main.py can read player_vec easily
        self.pos = pygame.math.Vector2(self.x, self.y)

        fw = FRAME_W * SCALE
        fh = FRAME_H * SCALE
        self.rect        = pygame.Rect(0, 0, fw, fh)
        self.rect.center = (int(self.x), int(self.y))

    # ── properties ───────────────────────────
    @property
    def fps(self):      return ANIMATIONS[self.state][2]
    @property
    def n_frames(self): return ANIMATIONS[self.state][1]
    @property
    def is_alive(self): return self.hp > 0

    # ── state ────────────────────────────────
    def set_state(self, state: str):
        if self.locked:
            return
        if state == self.state:
            return
        self.state       = state
        self.frame_index = 0
        self.timer       = 0.0
        self.locked      = state in ONE_SHOT

    # ── damage ───────────────────────────────
    def take_damage(self, amount: int):
        if self.invincible or not self.is_alive:
            return
        self.hp = max(0, self.hp - amount)
        self.invincible       = True
        self.invincible_timer = self.INVINCIBLE_MS
        if self.hp > 0:
            self.set_state("hurt")
        else:
            self.set_state("death")

    # ── update ───────────────────────────────
    def update(self, dt, keys, screen_w=None, screen_h=None):
        """
        dt       – seconds (standalone) OR milliseconds (main.py passes ms).
                   We detect by value: if dt > 5 it's ms, convert to seconds.
        screen_w / screen_h – boundaries; fall back to WINDOW_W/H if not given.
        """
        # Normalise dt to seconds
        if dt > 5:
            dt = dt / 1000.0

        sw = screen_w if screen_w is not None else WINDOW_W
        sh = screen_h if screen_h is not None else WINDOW_H

        # Invincibility countdown
        if self.invincible:
            self.invincible_timer -= dt * 1000
            if self.invincible_timer <= 0:
                self.invincible = False

        # Movement (blocked only during death)
        if self.state != "death":
            dx = dy = 0
            if keys[pygame.K_LEFT]  or keys[pygame.K_a]: dx -= 1
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]: dx += 1
            if keys[pygame.K_UP]    or keys[pygame.K_w]: dy -= 1
            if keys[pygame.K_DOWN]  or keys[pygame.K_s]: dy += 1

            # Normalize diagonal movement
            if dx != 0 and dy != 0:
                dx *= 0.7071
                dy *= 0.7071

            moving = dx != 0 or dy != 0

            if moving:
                self.x += dx * SPEED * dt
                self.y += dy * SPEED * dt

                if abs(dx) >= abs(dy):
                    self.direction = DIR_RIGHT if dx > 0 else DIR_LEFT
                else:
                    self.direction = DIR_DOWN if dy > 0 else DIR_UP

                if not self.locked:
                    is_running = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                    self.set_state("run" if is_running else "walk")
            else:
                if not self.locked:
                    self.set_state("idle")

            # Clamp player position to map boundaries (keeping entire rect inside)
            half_w = self.rect.width // 2
            half_h = self.rect.height // 2
            self.x = max(half_w, min(sw - half_w, self.x))
            self.y = max(half_h, min(sh - half_h, self.y))

            self.rect.center = (int(self.x), int(self.y))
            self.pos.update(self.x, self.y)

        # Frame advance
        self.timer += dt
        if self.timer >= 1.0 / self.fps:
            self.timer -= 1.0 / self.fps
            self.frame_index += 1
            if self.frame_index >= self.n_frames:
                if self.state == "death":
                    self.frame_index = self.n_frames - 1
                else:
                    self.frame_index = 0
                    self.locked = False

    def handle_event(self, event, keys):
        """Call from the event loop for combat inputs."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_j:
                moving = any(keys[k] for k in (
                    pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                    pygame.K_a,    pygame.K_d,    pygame.K_w,  pygame.K_s,
                ))
                shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                ctrl  = keys[pygame.K_LCTRL]  or keys[pygame.K_RCTRL]
                if moving and shift:
                    self.set_state("run_attack")
                elif moving and ctrl:
                    self.set_state("walk_attack")
                else:
                    self.set_state("attack")
            if event.key == pygame.K_k:
                self.set_state("hurt")
            if event.key == pygame.K_l:
                self.set_state("death")

    def draw(self, surface: pygame.Surface):
        # Flicker when invincible
        if self.invincible and int(pygame.time.get_ticks() / 80) % 2 == 0:
            return
        frame = self.frames[self.state][self.direction][self.frame_index]
        surface.blit(frame, self.rect)


# ─────────────────────────────────────────────
#  HUD  (standalone mode only)
# ─────────────────────────────────────────────
HUD_LINES = [
    ("WASD / Arrows",  "Move"),
    ("Shift + move",   "Run"),
    ("J",              "Attack"),
    ("Shift + J",      "Run Attack"),
    ("Ctrl + J",       "Walk Attack"),
    ("K",              "Hurt"),
    ("L",              "Death"),
]

def draw_hud(surface, character, font):
    x, y = 10, 10
    for key_hint, label in HUD_LINES:
        surface.blit(font.render(f"[{key_hint}]  {label}", True, (180, 180, 180)), (x, y))
        y += 24

    dir_sym = ["↓", "←", "→", "↑"][character.direction]
    info    = f"State: {character.state}   Dir: {dir_sym}"
    surface.blit(font.render(info, True, (255, 220, 50)), (10, WINDOW_H - 30))


# ─────────────────────────────────────────────
#  STANDALONE MAIN  (run player.py directly)
# ─────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("Swordsman")
    clock = pygame.time.Clock()
    font  = pygame.font.SysFont("monospace", 17)

    try:
        character = Character()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        pygame.quit()
        sys.exit(1)

    running = True
    while running:
        dt   = clock.tick(60) / 1000.0
        keys = pygame.key.get_pressed()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            character.handle_event(event, keys)

        character.update(dt, keys)

        screen.fill(BG_COLOR)
        character.draw(screen)
        draw_hud(screen, character, font)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
