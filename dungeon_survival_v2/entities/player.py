"""entities/player.py — the swordsman the user controls.

Controls (PRD §8):
    WASD / Arrows   move
    Shift + move    run
    J               attack
    Shift + J       run attack
    Ctrl + J        walk attack
The actual damage of a swing is resolved by the Game when ``consume_hit()``
reports the swing connected; the Player only signals the moment of impact.
"""

import pygame

import settings as S
from .base import Entity

_LEFT_KEYS  = (pygame.K_a, pygame.K_LEFT)
_RIGHT_KEYS = (pygame.K_d, pygame.K_RIGHT)
_UP_KEYS    = (pygame.K_w, pygame.K_UP)
_DOWN_KEYS  = (pygame.K_s, pygame.K_DOWN)
_RUN_KEYS   = (pygame.K_LSHIFT, pygame.K_RSHIFT)
_CTRL_KEYS  = (pygame.K_LCTRL, pygame.K_RCTRL)
_ATTACK_KEY = pygame.K_j


def _any(keys, group):
    return any(keys[k] for k in group)


class Player(Entity):
    def __init__(self, x, y, assets):
        super().__init__(x, y, S.PLAYER_HP, S.PLAYER_HITBOX_W, S.PLAYER_HITBOX_H)
        self.anims = assets.get_player_animations()
        self.attacking = False
        self._attack_dealt = False
        self._pending_hit = False

    def _hurt_invinc_ms(self):
        return S.PLAYER_INVIC_MS

    def start_hurt(self):
        self.attacking = False
        super().start_hurt()

    # ----------------------------------------------------------- main loop
    def update(self, dt_ms, keys, game_map):
        self._update_timers(dt_ms)

        if not self.alive:
            self.advance_animation(dt_ms)        # play death, freeze on last frame
            return

        self._apply_knockback(dt_ms, game_map)

        # ---- read input ----
        mx = (-1 if _any(keys, _LEFT_KEYS) else 0) + (1 if _any(keys, _RIGHT_KEYS) else 0)
        my = (-1 if _any(keys, _UP_KEYS) else 0) + (1 if _any(keys, _DOWN_KEYS) else 0)
        moving = mx != 0 or my != 0
        running = _any(keys, _RUN_KEYS)
        ctrl = _any(keys, _CTRL_KEYS)

        # holding J chains attacks (each one still gated by the previous
        # swing's animation finishing), tapping works too
        attack_down = keys[_ATTACK_KEY]

        # ---- facing ----
        if moving:
            if abs(mx) >= abs(my) and mx != 0:
                self.direction = S.DIR_RIGHT if mx > 0 else S.DIR_LEFT
            elif my != 0:
                self.direction = S.DIR_DOWN if my > 0 else S.DIR_UP

        # ---- movement (always allowed, even mid-swing) ----
        if moving:
            speed = S.PLAYER_SPEED * (S.PLAYER_RUN_MULT if running else 1.0)
            length = (mx * mx + my * my) ** 0.5
            step = speed * dt_ms / 1000.0
            game_map.move_and_slide(self, mx / length * step, my / length * step)
        game_map.clamp_entity(self)

        # ---- state machine ----
        hurt_busy = self.state == "hurt" and not self.anim_done
        if self.attacking:
            if self.anim_done:
                self.attacking = False
        elif not hurt_busy and attack_down:
            self._start_attack(moving, running, ctrl)

        if not self.attacking and not hurt_busy:
            if moving:
                self.set_state("run" if running else "walk")
            else:
                self.set_state("idle")

        # ---- resolve swing impact frame ----
        if self.attacking and not self._attack_dealt and \
                self.frame_index >= S.PLAYER_ATTACK_HIT_FRAME:
            self._attack_dealt = True
            self._pending_hit = True

        self.advance_animation(dt_ms)

    def _start_attack(self, moving, running, ctrl):
        if ctrl:
            variant = "walk_attack"
        elif running and moving:
            variant = "run_attack"
        elif moving:
            variant = "walk_attack"
        else:
            variant = "attack"
        self.attacking = True
        self._attack_dealt = False
        self.set_state(variant, force_restart=True)

    def consume_hit(self):
        """True exactly once per swing, on the frame the blade connects."""
        if self._pending_hit:
            self._pending_hit = False
            return True
        return False
