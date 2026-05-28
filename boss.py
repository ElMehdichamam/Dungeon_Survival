import pygame
import math
import random
import os

from enemy import Enemy, _Anim, _make_placeholder, DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP


# ─────────────────────────────────────────────────────────────────────────────
#  BASE BOSS
# ─────────────────────────────────────────────────────────────────────────────
class Boss:
    """Base class shared by all bosses."""

    NAME       = "Boss"
    COLOR      = (160, 40, 40)
    SIZE       = (80, 96)
    MAX_HP     = 800
    SPEED      = 55
    DMG        = 25
    ATTACK_CD  = 1500   # ms
    PHASE2_PCT = 0.40   # switch phases below this HP ratio

    def __init__(self, x: float, y: float, sprite_folder: str | None = None):
        w, h = self.SIZE
        self.max_hp = self.MAX_HP
        self.hp     = self.MAX_HP
        self.x      = float(x)
        self.y      = float(y)
        self.speed  = float(self.SPEED)
        self.dmg    = self.DMG
        self.phase  = 1

        # Placeholder frames (replace with real sprites via sprite_folder)
        frame_n = _make_placeholder(w, h, self.COLOR,      self.NAME)
        frame_h = _make_placeholder(w, h, (220, 80,  80),  "HIT")
        frame_d = _make_placeholder(w, h, (40,  0,   0),   "DEAD")

        self._frames_normal = frame_n
        self._frames_hurt   = frame_h
        self._frames_dead   = frame_d

        self.direction = DIR_DOWN
        self.anim  = _Anim(self._frames_normal, 4)
        self.state = "normal"   # normal | hurt | dead

        self.rect        = frame_n[DIR_DOWN][0].get_rect()
        self.rect.center = (int(self.x), int(self.y))
        self.image       = self.anim.image(self.direction)

        self._attack_timer = 0
        self._hurt_timer   = 0
        self._knockback    = pygame.math.Vector2(0, 0)

        self.summons: list[Enemy] = []
        self._effects: list[dict] = []   # visual effect particles

    # ── public helpers ────────────────────────────────────────────────────
    @property
    def is_alive(self):
        return self.state != "dead"

    def take_damage(self, amount: int,
                    knockback_dir: pygame.math.Vector2 | None = None):
        if not self.is_alive:
            return
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.state = "dead"
            self.anim  = _Anim(self._frames_dead, 6, loop=False)
        else:
            self.state       = "hurt"
            self._hurt_timer = 200
            self.anim        = _Anim(self._frames_hurt, 10, loop=False)
            if knockback_dir and knockback_dir.length() > 0:
                self._knockback = knockback_dir.normalize() * 3

    def _move_toward(self, target: pygame.math.Vector2, dt: float):
        to = target - pygame.math.Vector2(self.x, self.y)
        if to.length() > 5:
            move = to.normalize() * self.speed * dt
            self.x += move.x
            self.y += move.y
            if abs(to.x) >= abs(to.y):
                self.direction = DIR_RIGHT if to.x > 0 else DIR_LEFT
            else:
                self.direction = DIR_DOWN if to.y > 0 else DIR_UP

    def _try_attack(self, player, dt_ms: float):
        dist = (pygame.math.Vector2(self.rect.center) -
                pygame.math.Vector2(player.rect.center)).length()
        self._attack_timer -= dt_ms
        if dist < 60 and self._attack_timer <= 0:
            self._attack_timer = self.ATTACK_CD
            if hasattr(player, "take_damage"):
                player.take_damage(self.dmg)

    def _check_phase(self):
        if self.phase == 1 and self.hp / self.max_hp < self.PHASE2_PCT:
            self.phase = 2
            self._on_phase2()

    def _on_phase2(self):
        """Override in subclasses."""
        self.speed *= 1.4
        self.dmg   = int(self.dmg * 1.3)

    def _add_effect(self, x, y, color, radius=20, life=400):
        self._effects.append({"x": x, "y": y, "color": color,
                               "r": radius, "life": life, "max_life": life})

    def update(self, dt_ms: float,
               player_pos: pygame.math.Vector2, player,
               screen_w: int = 960, screen_h: int = 640):
        if self.state == "dead":
            self.anim.update(dt_ms)
            self.image = self.anim.image(self.direction)
            return

        dt = dt_ms / 1000.0

        # Knockback
        if self._knockback.length() > 0.1:
            self.x += self._knockback.x
            self.y += self._knockback.y
            self._knockback *= 0.85

        # Hurt recovery
        if self.state == "hurt":
            self._hurt_timer -= dt_ms
            if self._hurt_timer <= 0 or self.anim.done:
                self.state = "normal"
                self.anim  = _Anim(self._frames_normal, 4)

        if self.state == "normal":
            self._move_toward(player_pos, dt)
            self._try_attack(player, dt_ms)
            self._check_phase()
            self._ai_tick(dt_ms, player_pos, player)

        # Effects
        for ef in self._effects:
            ef["life"] -= dt_ms
        self._effects[:] = [e for e in self._effects if e["life"] > 0]

        # Clamp boss position to map boundaries (keeping entire rect inside)
        half_w = self.rect.width // 2
        half_h = self.rect.height // 2
        self.x = max(half_w, min(screen_w - half_w, self.x))
        self.y = max(half_h, min(screen_h - half_h, self.y))

        self.rect.center = (int(self.x), int(self.y))
        self.anim.update(dt_ms)
        self.image = self.anim.image(self.direction)

    def _ai_tick(self, dt_ms, player_pos, player):
        """Override for boss-specific AI."""
        pass

    def draw_health_bar(self, surface: pygame.Surface):
        bw = self.rect.width
        by = self.rect.top - 10
        bx = self.rect.left
        ratio = self.hp / self.max_hp
        pygame.draw.rect(surface, (80, 0, 0),    (bx, by, bw, 8))
        pygame.draw.rect(surface, (220, 60, 60), (bx, by, int(bw * ratio), 8))
        pygame.draw.rect(surface, (255,255,255), (bx, by, bw, 8), 1)

    def draw_boss_ui(self, surface: pygame.Surface, font):
        bar_w = 400
        bar_h = 20
        bx    = surface.get_width() // 2 - bar_w // 2
        by    = surface.get_height() - 40
        ratio = self.hp / self.max_hp
        pygame.draw.rect(surface, (60, 0, 0),    (bx, by, bar_w, bar_h))
        pygame.draw.rect(surface, (220, 60, 60), (bx, by, int(bar_w * ratio), bar_h))
        pygame.draw.rect(surface, (255,255,255), (bx, by, bar_w, bar_h), 2)
        label = font.render(
            f"{self.NAME}  {self.hp}/{self.max_hp}  [Phase {self.phase}]",
            True, (255, 255, 255))
        surface.blit(label, (bx + bar_w // 2 - label.get_width() // 2,
                              by - label.get_height() - 2))

    def draw_effects(self, surface: pygame.Surface):
        for ef in self._effects:
            alpha = int(200 * ef["life"] / ef["max_life"])
            s = pygame.Surface((ef["r"] * 2, ef["r"] * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*ef["color"], alpha), (ef["r"], ef["r"]), ef["r"])
            surface.blit(s, (ef["x"] - ef["r"], ef["y"] - ef["r"]))


# ─────────────────────────────────────────────────────────────────────────────
#  LICH KING
# ─────────────────────────────────────────────────────────────────────────────
class LichKing(Boss):
    NAME       = "Lich King"
    COLOR      = (80, 0, 160)
    SIZE       = (72, 88)
    MAX_HP     = 600
    SPEED      = 60
    DMG        = 20
    ATTACK_CD  = 1200
    PHASE2_PCT = 0.45

    def __init__(self, x, y, sprite_folder=None):
        super().__init__(x, y, sprite_folder)
        self._summon_timer   = 5000   # ms until first summon
        self._teleport_timer = 8000
        self._orb_timer      = 3000

    def _on_phase2(self):
        super()._on_phase2()
        self._summon_timer   = 2500
        self._teleport_timer = 4000

    def _ai_tick(self, dt_ms, player_pos, player):
        # Summon skeletons
        self._summon_timer -= dt_ms
        if self._summon_timer <= 0:
            self._summon_timer = 4000 if self.phase == 1 else 2200
            for _ in range(2 if self.phase == 1 else 3):
                ox = self.x + random.randint(-80, 80)
                oy = self.y + random.randint(-80, 80)
                self.summons.append(Enemy(ox, oy, "skeleton"))
            self._add_effect(self.x, self.y, (120, 0, 200), radius=40, life=500)

        # Teleport
        self._teleport_timer -= dt_ms
        if self._teleport_timer <= 0:
            self._teleport_timer = 8000 if self.phase == 1 else 4500
            # Teleport to a random spot away from player
            angle = random.uniform(0, math.tau)
            dist  = random.uniform(150, 280)
            self.x = player_pos.x + math.cos(angle) * dist
            self.y = player_pos.y + math.sin(angle) * dist
            self._add_effect(self.x, self.y, (200, 100, 255), radius=50, life=600)

        # Phase 2: shoot orbs (just deals damage if very close)
        if self.phase == 2:
            self._orb_timer -= dt_ms
            if self._orb_timer <= 0:
                self._orb_timer = 1800
                dist = (player_pos - pygame.math.Vector2(self.x, self.y)).length()
                if dist < 200 and hasattr(player, "take_damage"):
                    player.take_damage(10)
                self._add_effect(
                    *player_pos, (180, 60, 255), radius=25, life=350)


# ─────────────────────────────────────────────────────────────────────────────
#  STONE GOLEM
# ─────────────────────────────────────────────────────────────────────────────
class StoneGolem(Boss):
    NAME       = "Stone Golem"
    COLOR      = (100, 100, 110)
    SIZE       = (96, 112)
    MAX_HP     = 1200
    SPEED      = 38
    DMG        = 35
    ATTACK_CD  = 1800
    PHASE2_PCT = 0.35

    def __init__(self, x, y, sprite_folder=None):
        super().__init__(x, y, sprite_folder)
        self._slam_timer    = 4000
        self._boulder_timer = 7000
        self._rage          = False

    def _on_phase2(self):
        super()._on_phase2()
        self._rage       = True
        self._slam_timer = 2000
        self.dmg         = int(self.dmg * 1.5)

    def _ai_tick(self, dt_ms, player_pos, player):
        # Ground slam – damages player if close
        self._slam_timer -= dt_ms
        if self._slam_timer <= 0:
            self._slam_timer = 3500 if not self._rage else 1800
            dist = (player_pos - pygame.math.Vector2(self.x, self.y)).length()
            if dist < 120:
                if hasattr(player, "take_damage"):
                    player.take_damage(self.dmg // 2)
            self._add_effect(self.x, self.y, (180, 140, 60), radius=60, life=500)

        # Boulder throw – summons an orc as a stand-in projectile enemy
        self._boulder_timer -= dt_ms
        if self._boulder_timer <= 0:
            self._boulder_timer = 8000 if not self._rage else 4500
            angle = math.atan2(
                player_pos.y - self.y,
                player_pos.x - self.x)
            for spread in [-0.3, 0, 0.3]:
                ox = self.x + math.cos(angle + spread) * 60
                oy = self.y + math.sin(angle + spread) * 60
                self.summons.append(Enemy(ox, oy, "orc"))
            self._add_effect(self.x, self.y, (200, 160, 80), radius=45, life=400)
