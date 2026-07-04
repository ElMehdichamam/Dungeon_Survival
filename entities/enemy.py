"""entities/enemy.py — regular enemies (goblin / skeleton / orc / mage).

All four share one orc sprite sheet; variants differ only by stats and a
colour tint applied in the AssetLoader.  AI (PRD §9):

    idle  -> player within AGGRO_RANGE -> chase (walk)
    chase -> player within ATTACK_RANGE -> attack (cooldown ATTACK_CD_MS)
    any   -> take a hit -> hurt
    any   -> hp 0 -> death -> removed
"""

import pygame

from game import settings as S
from .base import Entity


class Enemy(Entity):
    def __init__(self, enemy_type, x, y, assets,
                 hitbox=(S.ENEMY_HITBOX_W, S.ENEMY_HITBOX_H), scale=S.SPRITE_SCALE):
        hp, dmg, speed, reward, tint = S.ENEMY_TYPES[enemy_type]
        super().__init__(x, y, hp, *hitbox)
        self.type = enemy_type
        self.anims = assets.get_enemy_animations(tint, scale)
        self.dmg = dmg
        self.speed = speed
        self.reward = reward

        self.aggro_range = S.AGGRO_RANGE
        self.attack_range = S.ATTACK_RANGE
        self.attack_cd_value = S.ATTACK_CD_MS

        self.attacking = False
        self._attack_dealt = False
        self._pending_hit = False
        self.attack_cd = 0
        self.aggroed = False        # latches on once the player is sighted

    def _hurt_invinc_ms(self):
        return S.ENEMY_HURT_MS

    def start_hurt(self):
        self.attacking = False
        super().start_hurt()

    # ----------------------------------------------------------- main loop
    def update(self, dt_ms, player, game_map):
        self._update_timers(dt_ms)
        if self.attack_cd > 0:
            self.attack_cd = max(0, self.attack_cd - dt_ms)

        if not self.alive:
            self.advance_animation(dt_ms)
            if self.anim_done:
                self.dead = True
            return

        self._apply_knockback(dt_ms, game_map)
        self._run_ai(dt_ms, player, game_map)
        self.advance_animation(dt_ms)

    def _run_ai(self, dt_ms, player, game_map):
        dx, dy = player.x - self.x, player.y - self.y
        dist = (dx * dx + dy * dy) ** 0.5
        self._face(dx, dy)

        hurt_busy = self.state == "hurt" and not self.anim_done
        if dist <= self.aggro_range:
            self.aggroed = True

        if self.attacking:
            if self.anim_done:
                self.attacking = False
                self.attack_cd = self.attack_cd_value
        elif hurt_busy:
            pass
        elif dist <= self.attack_range and self.attack_cd == 0:
            self._begin_attack()
        elif self.aggroed:
            self._chase(dt_ms, dx, dy, dist, game_map)
        else:
            self.set_state("idle")

        # resolve the swing: connect on the hit frame if still in range
        if self.attacking and not self._attack_dealt and \
                self.frame_index >= S.ENEMY_ATTACK_HIT_FRAME:
            self._attack_dealt = True
            if dist <= self.attack_range + self.rect.width:
                self._pending_hit = True

    def _begin_attack(self):
        self.attacking = True
        self._attack_dealt = False
        self.set_state("attack", force_restart=True)

    def _chase(self, dt_ms, dx, dy, dist, game_map):
        self.set_state("walk")
        # follow the flow field around walls; steer straight when close / no field
        move = game_map.flow_dir(self.x, self.y)
        if move is None:
            if dist <= 1e-6:
                return
            move = (dx / dist, dy / dist)
        step = self.speed * dt_ms / 1000.0
        game_map.move_and_slide(self, move[0] * step, move[1] * step)
        game_map.clamp_entity(self)

    def _face(self, dx, dy):
        if abs(dx) >= abs(dy):
            self.direction = S.DIR_RIGHT if dx > 0 else S.DIR_LEFT
        else:
            self.direction = S.DIR_DOWN if dy > 0 else S.DIR_UP

    def consume_hit(self):
        if self._pending_hit:
            self._pending_hit = False
            return True
        return False

    # ---------------------------------------------------------------- draw
    def draw(self, screen, camera):
        super().draw(screen, camera)
        if self.alive and 0 < self.hp < self.max_hp:
            self._draw_hp_bar(screen, camera)

    def _draw_hp_bar(self, screen, camera):
        w, h = S.ENEMY_HP_BAR_W, S.ENEMY_HP_BAR_H
        cx, cy = camera.to_screen(self.rect.centerx, self.rect.top)
        x = cx - w // 2
        y = cy + self.draw_offset_y - h - 2
        pygame.draw.rect(screen, S.COLOR_HP_BG, (x, y, w, h))
        fill = int(w * self.hp / self.max_hp)
        pygame.draw.rect(screen, S.COLOR_ENEMY_HP, (x, y, fill, h))
        pygame.draw.rect(screen, S.COLOR_BAR_BORDER, (x, y, w, h), 1)
