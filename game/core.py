"""game.py — the Game class: window, main loop and state machine (PRD §13).

States:
    PLAYING    fighting waves (includes the between-wave countdown)
    WAVE_END   reserved label for the intermission (tracked by WaveManager)
    BOSS       fighting Lich King, then Stone Golem
    GAME_OVER  player died
    VICTORY    both bosses defeated

The Game owns every actor and is the single place combat is resolved: entities
only *signal* that a swing connected; the Game applies the damage, knockback,
damage numbers and score.
"""

import os
from enum import Enum

import pygame

from . import settings as S
from .assets import AssetLoader
from .camera import Camera
from .map import GameMap
from entities import Player, Enemy, LichKing, StoneGolem
from systems import WaveManager, HUD, combat


class GameState(Enum):
    PLAYING   = "playing"
    WAVE_END  = "wave_end"
    BOSS      = "boss"
    PAUSED    = "paused"
    GAME_OVER = "game_over"
    VICTORY   = "victory"


class _NoKeys:
    """Stand-in for pygame's key state when the player has no control."""
    def __getitem__(self, _key):
        return False


_NO_KEYS = _NoKeys()
_DMG_COLOR_ENEMY = S.COLOR_WHITE
_DMG_COLOR_PLAYER = S.COLOR_DAMAGE
_MAX_DT_MS = 50          # clamp dt so a lag spike can't tunnel through walls


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(S.TITLE)
        self.screen = pygame.display.set_mode((S.SCREEN_W, S.SCREEN_H))
        self.clock = pygame.time.Clock()
        self.running = True

        self.assets = AssetLoader()
        self.game_map = GameMap(S.TMX_PATH)
        self.camera = Camera(self.game_map.pixel_w, self.game_map.pixel_h,
                             S.SCREEN_W, S.SCREEN_H)
        self.hud = HUD(self.assets)
        self._return_menu = False
        self._prev_state = GameState.PLAYING
        self._start_new_run()

    # -------------------------------------------------------- run lifecycle
    def _start_new_run(self):
        spawn_x, spawn_y = self.game_map.player_spawn
        self.player = Player(spawn_x, spawn_y, self.assets)
        self.wave_mgr = WaveManager(self.assets, self.game_map)
        self.enemies = []
        self.boss = None
        self.boss_stage = 0          # 0 none, 1 lich, 2 golem
        self.score = 0
        self.state = GameState.PLAYING
        self.hud.damage_numbers.items.clear()
        self.hud._notify_text = ""
        self.hud._notify_timer = 0
        self._return_menu = False
        self.camera.update(self.player.x, self.player.y)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(S.FPS), _MAX_DT_MS)
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()
        pygame.quit()
        return "menu" if self._return_menu else "quit"

    # -------------------------------------------------------------- events
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == GameState.PAUSED:
                        self.state = self._prev_state
                    elif self.state in (GameState.PLAYING, GameState.BOSS):
                        self._prev_state = self.state
                        self.state = GameState.PAUSED
                    else:
                        self.running = False
                elif event.key == pygame.K_p and \
                        self.state in (GameState.PLAYING, GameState.BOSS, GameState.PAUSED):
                    if self.state == GameState.PAUSED:
                        self.state = self._prev_state
                    else:
                        self._prev_state = self.state
                        self.state = GameState.PAUSED
                elif event.key == pygame.K_m and \
                        self.state in (GameState.GAME_OVER, GameState.VICTORY, GameState.PAUSED):
                    self.running = False
                    self._return_menu = True
                elif event.key == pygame.K_q and self.state == GameState.PAUSED:
                    self.running = False
                elif event.key == pygame.K_r:
                    if self.state == GameState.PAUSED:
                        self._start_new_run()
                    elif self.state in (GameState.GAME_OVER, GameState.VICTORY):
                        self._start_new_run()

    # -------------------------------------------------------------- update
    def _update(self, dt):
        self.hud.update(dt)

        if self.state == GameState.PAUSED:
            return

        if self.state == GameState.PLAYING:
            was_intermission = self.wave_mgr.in_intermission
            was_state = self.wave_mgr.state

            self._update_actors(dt, pygame.key.get_pressed())
            if not self.player.alive:
                self.state = GameState.GAME_OVER
            elif self.wave_mgr.is_done and not self.enemies:
                self.hud.notify("BOSS INCOMING!")
                self._spawn_lich()
            else:
                self.wave_mgr.update(dt, self.player, self.enemies)

            if was_intermission and not self.wave_mgr.in_intermission:
                self.hud.notify(f"Wave {self.wave_mgr.current_wave} START!")
            elif was_state == "spawning" and not self.wave_mgr.is_done \
                    and self.wave_mgr.in_intermission:
                self.player.hp = self.player.max_hp
                self.hud.notify("Wave Complete!  HP Restored")

        elif self.state == GameState.BOSS:
            self._update_actors(dt, pygame.key.get_pressed())
            self._handle_boss_requests()
            if not self.player.alive:
                self.state = GameState.GAME_OVER
            elif self.boss.dead:
                self.hud.notify(f"{self.boss.name} DEFEATED!")
                self._advance_boss()

        else:   # GAME_OVER / VICTORY — keep animations ticking, no control
            self.player.update(dt, _NO_KEYS, self.game_map)
            for e in self.enemies:
                e.update(dt, self.player, self.game_map)
            if self.boss:
                self.boss.update(dt, self.player, self.game_map)

    def _update_actors(self, dt, keys):
        self.player.update(dt, keys, self.game_map)
        self.game_map.update_flow(self.player.x, self.player.y)
        for e in self.enemies:
            e.update(dt, self.player, self.game_map)
        if self.boss:
            self.boss.update(dt, self.player, self.game_map)
        self._resolve_combat()
        self._cleanup_dead()
        self.camera.update(self.player.x, self.player.y)

    # -------------------------------------------------------------- combat
    def _attackers(self):
        attackers = list(self.enemies)
        if self.boss:
            attackers.append(self.boss)
        return attackers

    def _resolve_combat(self):
        # player's swing -> nearest enemy/boss in reach
        if self.player.consume_hit():
            target = combat.nearest_in_range(self.player.x, self.player.y,
                                             self._attackers(), S.PLAYER_RANGE)
            if target:
                kb = combat.knockback_vector(self.player.x, self.player.y,
                                             target.x, target.y, S.PLAYER_KNOCKBACK)
                if target.take_damage(S.PLAYER_DMG, kb):
                    self._popup(target, S.PLAYER_DMG, _DMG_COLOR_ENEMY)

        # each enemy/boss swing -> the player
        for a in self._attackers():
            if a.consume_hit():
                kb = combat.knockback_vector(a.x, a.y, self.player.x,
                                             self.player.y, S.ENEMY_KNOCKBACK)
                if self.player.take_damage(a.dmg, kb):
                    self._popup(self.player, a.dmg, _DMG_COLOR_PLAYER)

    def _popup(self, entity, amount, color):
        self.hud.add_damage_number(entity.x, entity.y + entity.draw_offset_y,
                                   amount, color)

    def _cleanup_dead(self):
        for e in self.enemies:
            if e.dead:
                self.score += e.reward
        self.enemies = [e for e in self.enemies if not e.dead]

    # --------------------------------------------------------------- boss
    def _spawn_lich(self):
        x, y = self.game_map.farthest_spawn_point(self.player.x, self.player.y)
        self.boss = LichKing(x, y, self.assets)
        self.boss_stage = 1
        self.enemies = []
        self.state = GameState.BOSS

    def _advance_boss(self):
        self.score += self.boss.reward
        if self.boss_stage == 1:
            x, y = self.game_map.farthest_spawn_point(self.player.x, self.player.y)
            self.boss = StoneGolem(x, y, self.assets)
            self.boss_stage = 2
            self.enemies = []        # clear any leftover summons
        else:
            self.boss = None
            self.state = GameState.VICTORY

    def _handle_boss_requests(self):
        if not self.boss:
            return
        if self.boss.consume_flash():
            self.hud.flash()

        wanted = self.boss.consume_summons()
        if wanted:
            alive_summons = sum(1 for e in self.enemies if e.alive)
            for _ in range(min(wanted, S.LICH_MAX_SUMMONS - alive_summons)):
                x, y = self.game_map.random_spawn_point(self.boss.x, self.boss.y,
                                                        min_dist=64)
                self.enemies.append(Enemy("goblin", x, y, self.assets))

        stomp = self.boss.consume_stomp()
        if stomp:
            sx, sy, radius, dmg = stomp
            if combat.distance(sx, sy, self.player.x, self.player.y) <= radius:
                kb = combat.knockback_vector(sx, sy, self.player.x,
                                             self.player.y, S.ENEMY_KNOCKBACK)
                if self.player.take_damage(dmg, kb):
                    self._popup(self.player, dmg, _DMG_COLOR_PLAYER)

    # ---------------------------------------------------------------- draw
    def _draw(self):
        self.game_map.draw(self.screen, self.camera)

        actors = [self.player] + self.enemies
        if self.boss:
            actors.append(self.boss)
        for actor in sorted(actors, key=lambda e: e.rect.bottom):
            actor.draw(self.screen, self.camera)

        self.hud.damage_numbers.draw(self.screen, self.camera)
        self.hud.draw(self.screen, self.player, self.wave_mgr,
                      self.clock.get_fps(), self.score, self.boss, self.state)
