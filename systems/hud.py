"""systems/hud.py — on-screen UI (PRD §12).

  top-left    player HP bar + "HP x/max" + score
  top-centre  wave / intermission / boss status
  top-right   FPS
  bottom      boss HP bar (full width, during boss fights only)
  floating    damage numbers that rise and fade
  centre      "YOU DIED" / "VICTORY!" / "PAUSED" overlays
Plus a brief white screen flash on boss phase changes and wave notifications.
"""

import pygame

from game import settings as S


_NOTIFY_DURATION = 2000


class DamageNumbers:
    """Floating combat numbers that rise and fade over DAMAGE_NUMBER_MS."""

    def __init__(self, assets):
        self.font = assets.get_font(24, bold=True)
        self.items = []          # list of [x, y, text, color, age_ms]

    def add(self, x, y, amount, color=S.COLOR_DAMAGE):
        self.items.append([x, y, str(int(amount)), color, 0.0])

    def update(self, dt_ms):
        for it in self.items:
            it[4] += dt_ms
        self.items = [it for it in self.items if it[4] < S.DAMAGE_NUMBER_MS]

    def draw(self, screen, camera):
        for x, y, text, color, age in self.items:
            frac = age / S.DAMAGE_NUMBER_MS
            sx, sy = camera.to_screen(x, y - S.DAMAGE_NUMBER_RISE * frac)
            surf = self.font.render(text, True, color)
            surf.set_alpha(int(255 * (1.0 - frac)))
            screen.blit(surf, surf.get_rect(center=(sx, sy)))


class HUD:
    def __init__(self, assets):
        self.assets = assets
        self.font_sm = assets.get_font(24)
        self.font_md = assets.get_font(30, bold=True)
        self.font_lg = assets.get_font(72, bold=True)
        self.damage_numbers = DamageNumbers(assets)
        self._flash_ms = 0
        self._notify_text = ""
        self._notify_timer = 0

    # ------------------------------------------------------------ effects
    def add_damage_number(self, x, y, amount, color=S.COLOR_DAMAGE):
        self.damage_numbers.add(x, y, amount, color)

    def flash(self):
        self._flash_ms = S.PHASE_FLASH_MS

    def notify(self, text):
        self._notify_text = text
        self._notify_timer = _NOTIFY_DURATION

    def update(self, dt_ms):
        self.damage_numbers.update(dt_ms)
        if self._flash_ms > 0:
            self._flash_ms = max(0, self._flash_ms - dt_ms)
        if self._notify_timer > 0:
            self._notify_timer = max(0, self._notify_timer - dt_ms)

    # -------------------------------------------------------------- pieces
    def _draw_bar(self, screen, x, y, w, h, frac, fg, bg=S.COLOR_HP_BG):
        frac = max(0.0, min(1.0, frac))
        pygame.draw.rect(screen, bg, (x, y, w, h))
        pygame.draw.rect(screen, fg, (x, y, int(w * frac), h))
        pygame.draw.rect(screen, S.COLOR_BAR_BORDER, (x, y, w, h), 2)

    def _text(self, screen, font, text, color, center=None, topleft=None,
              topright=None):
        surf = font.render(text, True, color)
        if center:
            rect = surf.get_rect(center=center)
        elif topright:
            rect = surf.get_rect(topright=topright)
        else:
            rect = surf.get_rect(topleft=topleft)
        screen.blit(surf, rect)

    # --------------------------------------------------------------- draw
    def draw(self, screen, player, wave_mgr, fps, score, boss=None, state=None):
        from game.core import GameState

        m = S.HUD_MARGIN

        # --- player HP (top-left) ---
        self._draw_bar(screen, m, m, S.HUD_HP_BAR_W, S.HUD_HP_BAR_H,
                       player.hp / player.max_hp, S.COLOR_HP_FG)
        self._text(screen, self.font_sm, f"HP {int(player.hp)}/{player.max_hp}",
                   S.COLOR_WHITE, topleft=(m + 8, m + 1))

        # --- score (top-left, below HP) ---
        self._text(screen, self.font_sm, f"Score: {score}",
                   S.COLOR_GOLD, topleft=(m + 4, m + S.HUD_HP_BAR_H + 6))

        # --- wave / status (top-centre) ---
        self._text(screen, self.font_md, self._status_text(wave_mgr, boss),
                   S.COLOR_WHITE, center=(S.SCREEN_W // 2, m + 14))

        # --- FPS (top-right) ---
        self._text(screen, self.font_sm, f"FPS {int(fps)}",
                   S.COLOR_TEXT_DIM, topright=(S.SCREEN_W - m, m + 2))

        # --- boss bar (bottom) ---
        if boss is not None and boss.alive:
            self._draw_boss_bar(screen, boss)

        # --- wave notification (below top-centre) ---
        if self._notify_timer > 0:
            alpha = min(255, int(255 * self._notify_timer / _NOTIFY_DURATION * 3))
            surf = self.font_md.render(self._notify_text, True, S.COLOR_GOLD)
            surf.set_alpha(alpha)
            self._text(screen, self.font_md, self._notify_text, S.COLOR_GOLD,
                       center=(S.SCREEN_W // 2, m + 50))

        # --- overlays ---
        if state == GameState.GAME_OVER:
            self._draw_center_overlay(screen, "YOU DIED", S.COLOR_HP_FG,
                                      "[R] Restart    [M] Menu    [ESC] Quit")
        elif state == GameState.VICTORY:
            self._draw_center_overlay(screen, "VICTORY!", S.COLOR_GOLD,
                                      "[R] Play again    [M] Menu    [ESC] Quit")
        elif state == GameState.PAUSED:
            self._draw_pause_overlay(screen)

        # --- phase-change flash (drawn last, over everything) ---
        if self._flash_ms > 0:
            overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H))
            overlay.fill(S.COLOR_WHITE)
            overlay.set_alpha(int(180 * self._flash_ms / S.PHASE_FLASH_MS))
            screen.blit(overlay, (0, 0))

    def _status_text(self, wave_mgr, boss):
        if boss is not None and boss.alive:
            return f"BOSS  —  {boss.name}"
        if wave_mgr.in_intermission:
            nxt = wave_mgr.current_wave + 1
            if nxt > wave_mgr.total_waves:
                return "Final assault incoming..."
            return f"Wave {nxt}/{wave_mgr.total_waves} in {wave_mgr.intermission_seconds}"
        return (f"Wave {wave_mgr.current_wave}/{wave_mgr.total_waves}   "
                f"Queue: {wave_mgr.queued}")

    def _draw_boss_bar(self, screen, boss):
        w = S.SCREEN_W - 2 * S.HUD_MARGIN
        h = 26
        x = S.HUD_MARGIN
        y = S.SCREEN_H - h - S.HUD_MARGIN
        self._draw_bar(screen, x, y, w, h, boss.hp / boss.max_hp, S.COLOR_BOSS_FG)
        label = f"{boss.name}    Phase {boss.phase}    {int(boss.hp)}/{boss.max_hp}"
        self._text(screen, self.font_sm, label, S.COLOR_WHITE,
                   center=(S.SCREEN_W // 2, y + h // 2))

    def _draw_center_overlay(self, screen, title, color, subtitle):
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H))
        overlay.fill(S.COLOR_BLACK)
        overlay.set_alpha(150)
        screen.blit(overlay, (0, 0))
        self._text(screen, self.font_lg, title, color,
                   center=(S.SCREEN_W // 2, S.SCREEN_H // 2 - 30))
        self._text(screen, self.font_md, subtitle, S.COLOR_WHITE,
                   center=(S.SCREEN_W // 2, S.SCREEN_H // 2 + 40))

    def _draw_pause_overlay(self, screen):
        overlay = pygame.Surface((S.SCREEN_W, S.SCREEN_H))
        overlay.fill(S.COLOR_BLACK)
        overlay.set_alpha(160)
        screen.blit(overlay, (0, 0))
        self._text(screen, self.font_lg, "PAUSED", S.COLOR_GOLD,
                   center=(S.SCREEN_W // 2, S.SCREEN_H // 2 - 60))
        lines = [
            "[ESC / P]  Resume",
            "[R]        Restart",
            "[M]        Main Menu",
            "[Q]        Quit",
        ]
        y = S.SCREEN_H // 2 - 10
        for line in lines:
            self._text(screen, self.font_md, line, S.COLOR_WHITE,
                       center=(S.SCREEN_W // 2, y))
            y += 40
