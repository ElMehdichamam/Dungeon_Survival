
"""entities/base.py — the Entity base class.

Holds everything common to the player, enemies and bosses: float position +
integer hitbox, hit points, facing direction, the animation player, knockback
and invincibility.  Movement/AI/combat decisions live in the subclasses.
"""

import pygame

import settings as S

# states that play once and then hand control back (vs. looping states)
ONE_SHOT_STATES = {"attack", "walk_attack", "run_attack", "hurt", "death"}


class Entity:
    def __init__(self, x, y, hp, hitbox_w, hitbox_h):
        self.x = float(x)
        self.y = float(y)
        self.max_hp = hp
        self.hp = hp

        self.rect = pygame.Rect(0, 0, hitbox_w, hitbox_h)
        self.rect.center = (round(x), round(y))

        self.direction = S.DIR_DOWN
        self.state = "idle"
        self.alive = True          # still in play
        self.dead = False          # death animation finished -> remove

        # animation: anims[state] = grid[direction][frame]
        self.anims = {}
        self.frame_index = 0
        self.frame_timer = 0.0
        self.anim_done = False

        # knockback velocity (px/sec) and invincibility timer (ms)
        self.kb_x = 0.0
        self.kb_y = 0.0
        self.invinc_ms = 0

        self.draw_offset_y = S.SPRITE_DRAW_OFFSET_Y

    # ----------------------------------------------------------- animation
    def set_state(self, state, force_restart=False):
        if state == self.state and not force_restart:
            return
        self.state = state
        self.frame_index = 0
        self.frame_timer = 0.0
        self.anim_done = False

    def _frame_ms(self):
        return S.ANIM_FRAME_MS.get(self.state, S.DEFAULT_FRAME_MS)

    def _frames(self):
        grid = self.anims.get(self.state) or self.anims.get("idle")
        if not grid:
            return None
        row = self.direction if self.direction < len(grid) else 0
        return grid[row]

    def advance_animation(self, dt_ms):
        frames = self._frames()
        if not frames:
            return
        loop = self.state not in ONE_SHOT_STATES
        self.frame_timer += dt_ms
        step = self._frame_ms()
        while self.frame_timer >= step:
            self.frame_timer -= step
            self.frame_index += 1
            if self.frame_index >= len(frames):
                if loop:
                    self.frame_index = 0
                else:
                    self.frame_index = len(frames) - 1
                    self.anim_done = True
                    break

    @property
    def is_one_shot(self):
        return self.state in ONE_SHOT_STATES

    # -------------------------------------------------------------- combat
    def take_damage(self, amount, knockback=None):
        """Apply damage; returns True if the hit landed (not invincible)."""
        if not self.alive or self.invinc_ms > 0:
            return False
        self.hp -= amount
        if knockback:
            self.kb_x, self.kb_y = knockback
        if self.hp <= 0:
            self.hp = 0
            self.start_death()
        else:
            self.start_hurt()
        return True

    def start_hurt(self):
        self.invinc_ms = self._hurt_invinc_ms()
        self.set_state("hurt", force_restart=True)

    def start_death(self):
        self.alive = False
        self.kb_x = self.kb_y = 0.0
        self.set_state("death", force_restart=True)

    def _hurt_invinc_ms(self):
        return S.ENEMY_HURT_MS

    # ------------------------------------------------------------ movement
    def _update_timers(self, dt_ms):
        if self.invinc_ms > 0:
            self.invinc_ms = max(0, self.invinc_ms - dt_ms)

    def _apply_knockback(self, dt_ms, game_map):
        if self.kb_x == 0.0 and self.kb_y == 0.0:
            return
        game_map.move_and_slide(self,
                                self.kb_x * dt_ms / 1000.0,
                                self.kb_y * dt_ms / 1000.0)
        self.kb_x *= S.KB_FRICTION
        self.kb_y *= S.KB_FRICTION
        if abs(self.kb_x) < S.KB_MIN and abs(self.kb_y) < S.KB_MIN:
            self.kb_x = self.kb_y = 0.0

    # ---------------------------------------------------------------- draw
    def current_image(self):
        frames = self._frames()
        if not frames:
            return None
        idx = min(self.frame_index, len(frames) - 1)
        return frames[idx]

    def draw(self, screen, camera):
        image = self.current_image()
        if image is None:
            return
        # flicker while invincible (but never hide the death animation)
        if self.invinc_ms > 0 and self.alive and (self.invinc_ms // 60) % 2 == 0:
            return
        sx, sy = camera.to_screen(self.rect.centerx,
                                  self.rect.centery + self.draw_offset_y)
        rect = image.get_rect(center=(sx, sy))
        screen.blit(image, rect)
