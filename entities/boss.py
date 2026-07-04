"""entities/boss.py — the two bosses (PRD §10).

LichKing  : 2 phases (50% hp).  Phase 2 = faster + summons goblins.
StoneGolem: 2 phases (40% hp).  Phase 2 = ground-stomp AoE.

Bosses reuse the Enemy melee AI but bypass its ENEMY_TYPES lookup.  Special
behaviours are exposed as *requests* (summon / stomp / phase flash) that the
Game fulfils, so all damage and damage-numbers stay funnelled through one place.
"""

import pygame

from game import settings as S
from .base import Entity
from .enemy import Enemy


class Boss(Enemy):
    def __init__(self, x, y, assets, hp, dmg, speed, tint, name, reward):
        # deliberately skip Enemy.__init__ (no ENEMY_TYPES entry for bosses)
        Entity.__init__(self, x, y, hp, S.BOSS_HITBOX_W, S.BOSS_HITBOX_H)
        self.anims = assets.get_enemy_animations(tint, S.BOSS_SCALE)
        self.type = name
        self.name = name
        self.dmg = dmg
        self.speed = speed
        self.reward = reward

        self.aggro_range = 10 ** 9          # always pursue the player
        self.attack_range = S.BOSS_ATTACK_RANGE
        self.attack_cd_value = S.BOSS_ATTACK_CD_MS

        self.attacking = False
        self._attack_dealt = False
        self._pending_hit = False
        self.attack_cd = 0

        self.is_boss = True
        self.phase = 1
        self.draw_offset_y = int(S.SPRITE_DRAW_OFFSET_Y * S.BOSS_SCALE / S.SPRITE_SCALE)

        # requests consumed by the Game
        self._flash_request = False
        self.summon_request = 0
        self.stomp_request = None

    def _hurt_invinc_ms(self):
        return S.BOSS_INVIC_MS

    def _check_phase(self, threshold):
        if self.alive and self.phase == 1 and self.hp <= self.max_hp * threshold:
            self.phase = 2
            self._flash_request = True
            self._enter_phase2()

    def _enter_phase2(self):
        pass

    def consume_flash(self):
        if self._flash_request:
            self._flash_request = False
            return True
        return False

    def consume_summons(self):
        n = self.summon_request
        self.summon_request = 0
        return n

    def consume_stomp(self):
        req = self.stomp_request
        self.stomp_request = None
        return req

    # bosses get their own (full-width) HP bar, so suppress the small one
    def draw(self, screen, camera):
        Entity.draw(self, screen, camera)


class LichKing(Boss):
    def __init__(self, x, y, assets):
        super().__init__(x, y, assets, S.LICH_HP, S.LICH_DMG, S.LICH_SPEED_P1,
                         S.LICH_TINT, "Lich King", S.LICH_REWARD)
        self.summon_timer = 0

    def _enter_phase2(self):
        self.speed = S.LICH_SPEED_P2

    def update(self, dt_ms, player, game_map):
        self._check_phase(S.LICH_PHASE2_AT)
        if self.alive and self.phase == 2:
            self.summon_timer += dt_ms
            if self.summon_timer >= S.LICH_SUMMON_MS:
                self.summon_timer = 0
                self.summon_request += S.LICH_SUMMON_COUNT
        super().update(dt_ms, player, game_map)


class StoneGolem(Boss):
    def __init__(self, x, y, assets):
        super().__init__(x, y, assets, S.GOLEM_HP, S.GOLEM_DMG, S.GOLEM_SPEED_P1,
                         S.GOLEM_TINT, "Stone Golem", S.GOLEM_REWARD)
        self.stomp_timer = 0
        self.winding = False
        self.windup = 0
        self._fx_ms = 0          # shockwave effect timer

    def _enter_phase2(self):
        self.speed = S.GOLEM_SPEED_P2

    def update(self, dt_ms, player, game_map):
        self._check_phase(S.GOLEM_PHASE2_AT)
        if self.alive and self.phase == 2:
            self._update_stomp(dt_ms)
        if self._fx_ms > 0:
            self._fx_ms = max(0, self._fx_ms - dt_ms)
        super().update(dt_ms, player, game_map)

    def _update_stomp(self, dt_ms):
        if self.winding:
            self.windup -= dt_ms
            if self.windup <= 0:
                self.winding = False
                self.stomp_request = (self.x, self.y,
                                      S.GOLEM_STOMP_RADIUS, S.GOLEM_STOMP_DMG)
                self._fx_ms = S.PHASE_FLASH_MS
        else:
            self.stomp_timer += dt_ms
            if self.stomp_timer >= S.GOLEM_STOMP_MS:
                self.stomp_timer = 0
                self.winding = True
                self.windup = S.GOLEM_STOMP_WINDUP_MS

    def draw(self, screen, camera):
        # telegraph ring during wind-up, shockwave ring just after the stomp
        cx, cy = camera.to_screen(self.rect.centerx, self.rect.centery)
        r = S.GOLEM_STOMP_RADIUS
        if self.winding:
            frac = 1.0 - max(0, self.windup) / S.GOLEM_STOMP_WINDUP_MS
            pygame.draw.circle(screen, (220, 120, 40), (cx, cy),
                               max(4, int(r * frac)), 3)
        elif self._fx_ms > 0:
            frac = 1.0 - self._fx_ms / S.PHASE_FLASH_MS
            pygame.draw.circle(screen, (255, 200, 80), (cx, cy),
                               int(r * (0.4 + frac)), 4)
        super().draw(screen, camera)
