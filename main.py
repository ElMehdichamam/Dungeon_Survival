import pygame
import sys
import os

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SPRITE_FOLDER = BASE_DIR   # all sprites in the same folder as main.py

sys.path.insert(0, BASE_DIR)

from player import Character
from enemy import Enemy, WaveManager
from boss import LichKing, StoneGolem

# ── Init ──────────────────────────────────────────────────────────────────────
pygame.init()
WIDTH, HEIGHT = 960, 640
screen  = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dungeon Survival")
clock   = pygame.time.Clock()
font    = pygame.font.SysFont("consolas", 15)
font_lg = pygame.font.SysFont("consolas", 21, bold=True)

# ── Colours ───────────────────────────────────────────────────────────────────
TILE_A   = (22,  16,  38)
TILE_B   = (18,  13,  30)
UI_GOLD  = (240, 210,  80)
UI_RED   = (220,  60,  60)
WHITE    = (255, 255, 255)

# ── Tile floor ────────────────────────────────────────────────────────────────
TILE = 48
floor_surf = pygame.Surface((WIDTH, HEIGHT))
for row in range(0, HEIGHT, TILE):
    for col in range(0, WIDTH, TILE):
        c = TILE_A if (row // TILE + col // TILE) % 2 == 0 else TILE_B
        pygame.draw.rect(floor_surf, c, (col, row, TILE, TILE))
        pygame.draw.rect(floor_surf, (30, 22, 48), (col, row, TILE, TILE), 1)

# ── Player attack config ───────────────────────────────────────────────────────
PLAYER_DMG    = 30
PLAYER_RANGE  = 120   # px – how far the J-attack reaches

# ── Helpers ───────────────────────────────────────────────────────────────────
def nearest_enemy(pos, enemies, boss, boss_active):
    living = [e for e in enemies if e.is_alive]
    if boss_active and boss and boss.is_alive:
        living.append(boss)
    if not living:
        return None
    return min(living, key=lambda e: (pygame.math.Vector2(e.rect.center) - pos).length())

def make_wave_mgr(enemies_list):
    spawn_region = pygame.Rect(60, 60, WIDTH - 120, HEIGHT - 120)
    def on_spawn(etype, x, y):
        enemies_list.append(Enemy(x, y, etype, sprite_folder=SPRITE_FOLDER))
    wm = WaveManager(on_spawn, spawn_region,
                     spawn_interval_ms=1100, between_waves_ms=3000)
    wm.register_enemies(enemies_list)
    wm.start()
    return wm

# ── Floating damage numbers ───────────────────────────────────────────────────
dmg_numbers: list[dict] = []

def add_dmg(x, y, amount, color=(255, 60, 60)):
    dmg_numbers.append({"text": f"-{amount}", "x": float(x), "y": float(y),
                         "timer": 900.0, "color": color})

# ── Restart ───────────────────────────────────────────────────────────────────
def restart():
    global player, enemies, boss, boss_active, wave_mgr
    enemies.clear()
    dmg_numbers.clear()
    boss        = None
    boss_active = False
    player      = Character(x=WIDTH // 2, y=HEIGHT // 2)
    wave_mgr    = make_wave_mgr(enemies)

# ── Initial state ─────────────────────────────────────────────────────────────
player      = Character(x=WIDTH // 2, y=HEIGHT // 2)
enemies: list[Enemy] = []
boss        = None
boss_active = False
wave_mgr    = make_wave_mgr(enemies)

# ── Main loop ─────────────────────────────────────────────────────────────────
running = True
while running:
    dt   = clock.tick(60)
    keys = pygame.key.get_pressed()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: running = False
            if event.key == pygame.K_r:      restart()
            if event.key == pygame.K_b:
                boss        = LichKing(80, 60, sprite_folder=SPRITE_FOLDER)
                boss_active = True
            if event.key == pygame.K_g:
                boss        = StoneGolem(80, 60, sprite_folder=SPRITE_FOLDER)
                boss_active = True

            # ── J key → attack nearest enemy in range ──
            if event.key == pygame.K_j:
                player_vec = pygame.math.Vector2(player.rect.center)
                target     = nearest_enemy(player_vec, enemies, boss, boss_active)
                if target:
                    dist = (pygame.math.Vector2(target.rect.center) - player_vec).length()
                    if dist <= PLAYER_RANGE:
                        kdir = pygame.math.Vector2(target.rect.center) - player_vec
                        target.take_damage(PLAYER_DMG, kdir)
                        add_dmg(*target.rect.midtop, PLAYER_DMG)

                # Also trigger attack animation
                moving = any(keys[k] for k in (
                    pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN,
                    pygame.K_a,    pygame.K_d,    pygame.K_w,  pygame.K_s,
                ))
                shift = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
                ctrl  = keys[pygame.K_LCTRL]  or keys[pygame.K_RCTRL]
                if moving and shift:
                    player.set_state("run_attack")
                elif moving and ctrl:
                    player.set_state("walk_attack")
                else:
                    player.set_state("attack")

        # Other player combat keys
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_k: player.set_state("hurt")

    # ── Update ───────────────────────────────────────────────────────────
    player.update(dt, keys, WIDTH, HEIGHT)
    player_vec = pygame.math.Vector2(player.rect.center)

    wave_mgr.register_enemies(enemies)
    wave_mgr.update(dt)

    for e in enemies:
        e.update(dt, player_vec, player)

    # Remove dead enemies after death anim finishes
    for e in [x for x in enemies if x.state == "dead" and x.anim.death_finished]:
        add_dmg(*e.rect.center, e.reward, color=UI_GOLD)
    enemies[:] = [e for e in enemies
                  if not (e.state == "dead" and e.anim.death_finished)]

    if boss_active and boss:
        boss.update(dt, player_vec, player)
        for s in boss.summons[:]:
            s.update(dt, player_vec, player)
        boss.summons[:] = [s for s in boss.summons
                           if not (s.state == "dead" and s.anim.death_finished)]

    for d in dmg_numbers:
        d["timer"] -= dt
        d["y"]     -= 0.5
    dmg_numbers[:] = [d for d in dmg_numbers if d["timer"] > 0]

    # ── Draw ──────────────────────────────────────────────────────────────
    screen.blit(floor_surf, (0, 0))

    for e in sorted(enemies, key=lambda x: x.rect.bottom):
        screen.blit(e.image, e.rect)
        e.draw_health_bar(screen)

    if boss_active and boss:
        screen.blit(boss.image, boss.rect)
        boss.draw_health_bar(screen)
        boss.draw_boss_ui(screen, font)
        boss.draw_effects(screen)
        for s in boss.summons:
            if s.is_alive:
                screen.blit(s.image, s.rect)
                s.draw_health_bar(screen)

    player.draw(screen)

    # Draw attack range ring when J is held
    if keys[pygame.K_j]:
        pygame.draw.circle(screen, (255, 255, 100),
                           player.rect.center, PLAYER_RANGE, 1)

    for d in dmg_numbers:
        alpha = int(255 * d["timer"] / 900)
        txt   = font_lg.render(d["text"], True, d["color"])
        txt.set_alpha(alpha)
        screen.blit(txt, (int(d["x"]) - txt.get_width() // 2, int(d["y"])))

    # ── HUD ───────────────────────────────────────────────────────────────
    bar_w = 200
    pygame.draw.rect(screen, (80, 0, 0), (10, 10, bar_w, 16))
    hp_w = int(bar_w * max(0, player.hp) / player.max_hp)
    pygame.draw.rect(screen, UI_RED,     (10, 10, hp_w, 16))
    pygame.draw.rect(screen, WHITE,      (10, 10, bar_w, 16), 1)
    screen.blit(font.render(f"HP  {player.hp}/{player.max_hp}", True, WHITE), (14, 12))

    if wave_mgr.all_waves_done:
        wave_str, col = "★  All waves cleared!  ★", UI_GOLD
    elif wave_mgr._waiting:
        secs     = int(wave_mgr._wave_timer // 1000) + 1
        wave_str = f"Wave {wave_mgr.current_wave} done  –  Next in {secs}s"
        col      = (180, 220, 255)
    else:
        alive_n  = sum(1 for e in enemies if e.is_alive)
        wave_str = (f"Wave {wave_mgr.current_wave}/{wave_mgr.total_waves}"
                    f"   Alive: {alive_n}   Queue: {len(wave_mgr._queue)}")
        col = UI_GOLD

    wt = font_lg.render(wave_str, True, col)
    screen.blit(wt, (WIDTH // 2 - wt.get_width() // 2, 10))

    if not player.is_alive:
        go = font_lg.render("YOU DIED  –  [R] Restart", True, UI_RED)
        screen.blit(go, (WIDTH // 2 - go.get_width() // 2,
                         HEIGHT // 2 - go.get_height() // 2))

    hints = ["[WASD] Move", "[Shift] Run", "[J] Attack enemy in range",
             "[B] Lich King", "[G] Stone Golem", "[R] Restart"]
    for i, h in enumerate(hints):
        ht = font.render(h, True, (140, 140, 170))
        screen.blit(ht, (WIDTH - ht.get_width() - 10,
                         HEIGHT - 16 * (len(hints) - i) - 8))

    fps_txt = font.render(f"FPS {int(clock.get_fps())}", True, (100, 100, 130))
    screen.blit(fps_txt, (WIDTH - fps_txt.get_width() - 10, 10))

    pygame.display.flip()

pygame.quit()
sys.exit()