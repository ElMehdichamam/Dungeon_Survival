import pygame
import sys
import os

# Fix pygame.image.load for non-BMP images (SDL2_image not available)
import _pygame_image_fix

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SPRITE_FOLDER = BASE_DIR

sys.path.insert(0, BASE_DIR)

from player import Character
from enemy import Enemy, WaveManager
from boss import LichKing, StoneGolem
from dungeon_map import DungeonMap

# ── Init ──────────────────────────────────────────────────────────────────────
pygame.init()
WIDTH, HEIGHT = 960, 640
screen  = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dungeon Survival")
clock   = pygame.time.Clock()
font    = pygame.font.SysFont("consolas", 15)
font_lg = pygame.font.SysFont("consolas", 21, bold=True)

# ── Dungeon map ───────────────────────────────────────────────────────────────
dungeon = DungeonMap("Dungeon1.tmx", scale=2, asset_dir=BASE_DIR)
dungeon.load()

MAP_W = dungeon.pixel_w   # total map width  in screen pixels
MAP_H = dungeon.pixel_h   # total map height in screen pixels
print(f"MAP size: {MAP_W}x{MAP_H}")

# ── Colours ───────────────────────────────────────────────────────────────────
UI_GOLD  = (240, 210,  80)
UI_RED   = (220,  60,  60)
WHITE    = (255, 255, 255)

# ── Player attack config ───────────────────────────────────────────────────────
PLAYER_DMG   = 30
PLAYER_RANGE = 120

# ── Helpers ───────────────────────────────────────────────────────────────────
def nearest_enemy(pos, enemies, boss, boss_active):
    living = [e for e in enemies if e.is_alive]
    if boss_active and boss and boss.is_alive:
        living.append(boss)
    if not living:
        return None
    return min(living, key=lambda e: (pygame.math.Vector2(e.rect.center) - pos).length())

def make_wave_mgr(enemies_list):
    # Spawn enemies anywhere on the walkable map, away from the center
    spawn_region = pygame.Rect(60, 60, MAP_W - 120, MAP_H - 120)
    def on_spawn(etype, x, y):
        enemies_list.append(Enemy(x, y, etype, sprite_folder=SPRITE_FOLDER))
    wm = WaveManager(on_spawn, spawn_region,
                     spawn_interval_ms=1100, between_waves_ms=3000)
    wm.register_enemies(enemies_list)
    wm.start()
    return wm

# ── Camera ────────────────────────────────────────────────────────────────────
def get_camera(player_x, player_y):
    """Return (cam_x, cam_y) so the player is centred on screen."""
    cx = int(player_x - WIDTH  // 2)
    cy = int(player_y - HEIGHT // 2)
    cx = max(0, min(cx, MAP_W - WIDTH))
    cy = max(0, min(cy, MAP_H - HEIGHT))
    return cx, cy

# ── Floating damage numbers ───────────────────────────────────────────────────
dmg_numbers: list[dict] = []

def add_dmg(x, y, amount, color=(255, 60, 60)):
    dmg_numbers.append({"text": f"-{amount}", "x": float(x), "y": float(y),
                         "timer": 900.0, "color": color})

# ── World-to-screen helper ────────────────────────────────────────────────────
def world_to_screen(wx, wy, cam_x, cam_y):
    return wx - cam_x, wy - cam_y

# ── Collision helper (shared) ─────────────────────────────────────────────────
def apply_wall_collision(entity, dungeon: DungeonMap):
    """Push entity out of solid tiles. Works for player, enemy, and boss.

    FIX BUG-10: record which axis was reverted so enemy AI can slide along the
    wall on the next frame instead of mashing into it.
    """
    pre_x, pre_y = entity.x, entity.y
    entity.rect  = dungeon.resolve_collision(entity.rect)
    entity.x     = float(entity.rect.centerx)
    entity.y     = float(entity.rect.centery)
    entity._blocked_x = abs(entity.x - pre_x) > 0.5
    entity._blocked_y = abs(entity.y - pre_y) > 0.5

# ── Restart ───────────────────────────────────────────────────────────────────
def restart():
    global player, enemies, boss, boss_active, wave_mgr
    enemies.clear()
    dmg_numbers.clear()
    boss        = None
    boss_active = False
    # Place player near the centre of the map
    player      = Character(x=MAP_W // 2, y=MAP_H // 2)
    wave_mgr    = make_wave_mgr(enemies)

# ── Initial state ─────────────────────────────────────────────────────────────
player      = Character(x=MAP_W // 2, y=MAP_H // 2)
enemies: list[Enemy] = []
boss        = None
boss_active = False
wave_mgr    = make_wave_mgr(enemies)

# ── Main loop ─────────────────────────────────────────────────────────────────
running = True
while running:
    dt   = clock.tick(60)
    keys = pygame.key.get_pressed()

    # Camera (before any draw, based on last frame's player pos)
    cam_x, cam_y = get_camera(player.x, player.y)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: running = False
            if event.key == pygame.K_r:      restart()
            if event.key == pygame.K_b:
                boss        = LichKing(MAP_W // 2 - 200, MAP_H // 2, sprite_folder=SPRITE_FOLDER)
                boss_active = True
            if event.key == pygame.K_g:
                boss        = StoneGolem(MAP_W // 2 - 200, MAP_H // 2, sprite_folder=SPRITE_FOLDER)
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
                        sx, sy = world_to_screen(*target.rect.midtop, cam_x, cam_y)
                        add_dmg(sx + cam_x, sy + cam_y, PLAYER_DMG)

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

            # FIX BUG-06: merged duplicate KEYDOWN block
            if event.key == pygame.K_k: player.set_state("hurt")

    # ── Update ───────────────────────────────────────────────────────────
    # Pass map pixel size as boundaries so entities don't go OOB
    player.update(dt, keys, MAP_W, MAP_H)
    apply_wall_collision(player, dungeon)

    player_vec = pygame.math.Vector2(player.rect.center)

    wave_mgr.register_enemies(enemies)
    wave_mgr.update(dt)

    for e in enemies:
        e.update(dt, player_vec, player, MAP_W, MAP_H)
        apply_wall_collision(e, dungeon)

    # Remove dead enemies after death anim finishes
    for e in [x for x in enemies if x.state == "dead" and x.anim.death_finished]:
        add_dmg(*e.rect.center, e.reward, color=UI_GOLD)
    enemies[:] = [e for e in enemies
                  if not (e.state == "dead" and e.anim.death_finished)]

    if boss_active and boss:
        boss.update(dt, player_vec, player, MAP_W, MAP_H)
        apply_wall_collision(boss, dungeon)
        for s in boss.summons[:]:
            s.update(dt, player_vec, player, MAP_W, MAP_H)
            apply_wall_collision(s, dungeon)
        boss.summons[:] = [s for s in boss.summons
                           if not (s.state == "dead" and s.anim.death_finished)]

    for d in dmg_numbers:
        d["timer"] -= dt
        d["y"]     -= 0.5
    dmg_numbers[:] = [d for d in dmg_numbers if d["timer"] > 0]

    # Recalculate camera after movement + collision resolution
    cam_x, cam_y = get_camera(player.x, player.y)

    # ── Draw ──────────────────────────────────────────────────────────────
    screen.fill((10, 8, 20))
    dungeon.update()
    dungeon.draw(screen, cam_x, cam_y)

    def blit_world(surf, rect):
        sx = rect.x - cam_x
        sy = rect.y - cam_y
        screen.blit(surf, (sx, sy))

    def draw_hbar_world(entity):
        # Re-draw health bar at camera-adjusted position
        bw = entity.rect.width
        bx = entity.rect.left - cam_x
        by = entity.rect.top  - cam_y - 8
        ratio = entity.hp / entity.max_hp
        pygame.draw.rect(screen, (80, 0, 0),     (bx, by, bw, 5))
        pygame.draw.rect(screen, (60, 200, 60),  (bx, by, int(bw * ratio), 5))
        pygame.draw.rect(screen, (200, 200, 200),(bx, by, bw, 5), 1)

    for e in sorted(enemies, key=lambda x: x.rect.bottom):
        blit_world(e.image, e.rect)
        draw_hbar_world(e)

    if boss_active and boss:
        blit_world(boss.image, boss.rect)
        # Boss health bar above sprite
        bw = boss.rect.width
        bx = boss.rect.left - cam_x
        by = boss.rect.top  - cam_y - 10
        ratio = boss.hp / boss.max_hp
        pygame.draw.rect(screen, (80, 0, 0),    (bx, by, bw, 8))
        pygame.draw.rect(screen, (220, 60, 60), (bx, by, int(bw * ratio), 8))
        pygame.draw.rect(screen, (255,255,255), (bx, by, bw, 8), 1)
        boss.draw_boss_ui(screen, font)
        boss.draw_effects(screen, cam_x, cam_y)  # FIX BUG-07/08: pass camera offset
        for s in boss.summons:
            if s.is_alive:
                blit_world(s.image, s.rect)
                draw_hbar_world(s)

    # Player — drawn at camera-adjusted position
    player_screen_x = int(player.x) - cam_x
    player_screen_y = int(player.y) - cam_y
    frame = player.frames[player.state][player.direction][player.frame_index]
    if not (player.invincible and int(pygame.time.get_ticks() / 80) % 2 == 0):
        screen.blit(frame, (player_screen_x - frame.get_width() // 2,
                             player_screen_y - frame.get_height() // 2))

    # Draw attack range ring when J is held
    if keys[pygame.K_j]:
        pygame.draw.circle(screen, (255, 255, 100),
                           (player_screen_x, player_screen_y), PLAYER_RANGE, 1)

    # Damage numbers (stored in world coords, converted to screen)
    for d in dmg_numbers:
        alpha = int(255 * d["timer"] / 900)
        txt   = font_lg.render(d["text"], True, d["color"])
        txt.set_alpha(alpha)
        sx = int(d["x"]) - cam_x - txt.get_width() // 2
        sy = int(d["y"]) - cam_y
        screen.blit(txt, (sx, sy))

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