"""systems/wave.py — spawns enemies wave by wave (PRD §11).

Flow: a 3s intermission, then the wave's enemies trickle in one every
SPAWN_INTERVAL_MS at a walkable tile >= SPAWN_MIN_DIST from the player.  A wave
is only cleared once its queue is empty AND every enemy is gone (death anim
finished, so the Game has removed it).  After the last wave the manager reports
``is_done`` and the Game starts the boss sequence.
"""

import random

from game import settings as S
from entities import Enemy

STATE_INTERMISSION = "between"
STATE_SPAWNING = "spawning"
STATE_DONE = "done"


class WaveManager:
    def __init__(self, assets, game_map):
        self.assets = assets
        self.game_map = game_map
        self.total_waves = len(S.WAVES)
        self.reset()

    def reset(self):
        self.wave_index = -1                 # incremented when a wave begins
        self.queue = []
        self.spawn_timer = 0
        self.state = STATE_INTERMISSION
        self.intermission_timer = S.BETWEEN_WAVES_MS

    # ------------------------------------------------------------- queries
    @property
    def current_wave(self):
        return self.wave_index + 1           # 1-based for display

    @property
    def queued(self):
        return len(self.queue)

    @property
    def is_done(self):
        return self.state == STATE_DONE

    @property
    def intermission_seconds(self):
        return max(0, (self.intermission_timer + 999) // 1000)

    @property
    def in_intermission(self):
        return self.state == STATE_INTERMISSION

    # --------------------------------------------------------------- logic
    def update(self, dt_ms, player, enemies):
        if self.state == STATE_INTERMISSION:
            self.intermission_timer -= dt_ms
            if self.intermission_timer <= 0:
                self._begin_wave()

        elif self.state == STATE_SPAWNING:
            if self.queue:
                self.spawn_timer += dt_ms
                if self.spawn_timer >= S.SPAWN_INTERVAL_MS:
                    self.spawn_timer = 0
                    self._spawn_one(player, enemies)
            elif not enemies:
                self._end_wave()

    def _begin_wave(self):
        self.wave_index += 1
        self.queue = []
        for enemy_type, count in S.WAVES[self.wave_index]:
            self.queue.extend([enemy_type] * count)
        random.shuffle(self.queue)
        self.state = STATE_SPAWNING
        self.spawn_timer = S.SPAWN_INTERVAL_MS    # first enemy arrives at once

    def _spawn_one(self, player, enemies):
        enemy_type = self.queue.pop(0)
        x, y = self.game_map.random_spawn_point(player.x, player.y)
        enemies.append(Enemy(enemy_type, x, y, self.assets))

    def _end_wave(self):
        if self.wave_index + 1 < self.total_waves:
            self.state = STATE_INTERMISSION
            self.intermission_timer = S.BETWEEN_WAVES_MS
        else:
            self.state = STATE_DONE
