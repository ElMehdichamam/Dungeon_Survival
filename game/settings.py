"""settings.py — ALL game constants live here.

Rule from the PRD: zero magic numbers anywhere else in the codebase.
Anything tunable (speeds, sizes, colours, timings) belongs in this file.
"""

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR    = os.path.join(BASE_DIR, "assets", "sprites")
TMX_PATH     = os.path.join(BASE_DIR, "assets", "maps", "Dungeon1.tmx")

# --------------------------------------------------------------------------
# Screen
# --------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 960, 640
FPS = 60
TITLE = "Dungeon Survival"

# --------------------------------------------------------------------------
# Scaling
# --------------------------------------------------------------------------
MAP_SCALE    = 2     # tiled map drawn at x2
SPRITE_SCALE = 2     # player + regular enemies drawn at x2
BOSS_SCALE   = 3     # bosses are drawn bigger

# --------------------------------------------------------------------------
# Sprite sheet geometry (verified against the .png files)
#   Every sheet is 4 rows (one per direction) x N frame columns, 64x64 each.
# --------------------------------------------------------------------------
FRAME_W = 64
FRAME_H = 64
SHEET_ROWS = 4

# Direction -> spritesheet row.  (DOWN=0, LEFT=1, RIGHT=2, UP=3)
DIR_DOWN, DIR_LEFT, DIR_RIGHT, DIR_UP = 0, 1, 2, 3

# Frame counts per animation (cols in each sheet)
PLAYER_ANIM_FRAMES = {
    "idle":        12,
    "walk":        6,
    "run":         8,
    "attack":      8,
    "walk_attack": 6,
    "run_attack":  8,
    "hurt":        5,
    "death":       7,
}
ENEMY_ANIM_FRAMES = {
    "idle":   4,
    "walk":   6,
    "run":    8,
    "attack": 8,
    "hurt":   6,
    "death":  8,
}

# Player sheet file names -> animation key
PLAYER_SHEETS = {
    "idle":        "Swordsman_lvl1_Idle_with_shadow.png",
    "walk":        "Swordsman_lvl1_Walk_with_shadow.png",
    "run":         "Swordsman_lvl1_Run_with_shadow.png",
    "attack":      "Swordsman_lvl1_attack_with_shadow.png",
    "walk_attack": "Swordsman_lvl1_Walk_Attack_with_shadow.png",
    "run_attack":  "Swordsman_lvl1_Run_Attack_with_shadow.png",
    "hurt":        "Swordsman_lvl1_Hurt_with_shadow.png",
    "death":       "Swordsman_lvl1_Death_with_shadow.png",
}
# Enemy sheet file names (orc1_*) -> animation key
ENEMY_SHEETS = {
    "idle":   "orc1_idle_with_shadow.png",
    "walk":   "orc1_walk_with_shadow.png",
    "run":    "orc1_run_with_shadow.png",
    "attack": "orc1_attack_with_shadow.png",
    "hurt":   "orc1_hurt_with_shadow.png",
    "death":  "orc1_death_with_shadow.png",
}

# --------------------------------------------------------------------------
# Animation timing (milliseconds per frame)
# --------------------------------------------------------------------------
ANIM_FRAME_MS = {
    "idle":        110,
    "walk":        90,
    "run":         70,
    "attack":      55,
    "walk_attack": 60,
    "run_attack":  55,
    "hurt":        60,
    "death":       90,
}
DEFAULT_FRAME_MS = 90

# --------------------------------------------------------------------------
# Player
# --------------------------------------------------------------------------
PLAYER_SPEED    = 180        # px/sec
PLAYER_RUN_MULT = 1.6
PLAYER_HP       = 100
PLAYER_DMG      = 30
PLAYER_RANGE    = 120        # melee reach (px)
PLAYER_INVIC_MS = 600
PLAYER_KNOCKBACK = 260       # knockback impulse (px/sec) applied to enemies the player hits
# index of the attack animation frame at which the swing connects
PLAYER_ATTACK_HIT_FRAME = 3
# collision hitbox (scaled px) — smaller than the sprite so corridors are passable
PLAYER_HITBOX_W = 26
PLAYER_HITBOX_H = 24
# draw offset: sprite centre relative to hitbox centre (px), lifts art so feet sit on hitbox
SPRITE_DRAW_OFFSET_Y = -18

# Knockback decay: treated as a velocity (px/sec) that loses this fraction each
# frame until it drops below KB_MIN, then stops.
KB_FRICTION = 0.82
KB_MIN = 10

# --------------------------------------------------------------------------
# Enemy base stats (per-type values override these where given)
# --------------------------------------------------------------------------
# AGGRO_RANGE spans the whole arena (~1070px diagonal at this map scale) so
# wave enemies actually hunt the player; once aggroed they never disengage.
AGGRO_RANGE  = 1200
ATTACK_RANGE = 45
ATTACK_CD_MS = 1200
ENEMY_HURT_MS = 300
ENEMY_HITBOX_W = 26
ENEMY_HITBOX_H = 24
ENEMY_KNOCKBACK = 180        # knockback enemies apply to the player
ENEMY_ATTACK_HIT_FRAME = 4   # frame at which an enemy swing connects
ENEMY_KNOCKBACK_TAKEN = 220  # knockback enemies receive from the player

# Enemy types: name -> (hp, dmg, speed, reward, tint_color or None)
ENEMY_TYPES = {
    "goblin":   (60,  8,  90, 10, None),
    "skeleton": (70,  12, 70, 20, (150, 180, 255)),   # blue tint
    "orc":      (130, 18, 55, 35, (255, 120, 120)),   # red tint
    "mage":     (55,  22, 80, 40, (200, 120, 255)),   # purple tint
}

# --------------------------------------------------------------------------
# Waves
# --------------------------------------------------------------------------
WAVES = [
    [("goblin", 4)],
    [("goblin", 4), ("skeleton", 2)],
    [("skeleton", 3), ("orc", 2)],
    [("orc", 2), ("mage", 2)],
    [("goblin", 4), ("orc", 2), ("mage", 2)],
]
BETWEEN_WAVES_MS  = 3000
SPAWN_INTERVAL_MS = 1100
SPAWN_MIN_DIST    = 300       # enemies spawn at least this far (px) from the player

# --------------------------------------------------------------------------
# Bosses
# --------------------------------------------------------------------------
LICH_HP   = 600
GOLEM_HP  = 800

# Lich King
LICH_TINT          = (120, 90, 200)   # dark arcane purple
LICH_DMG           = 20
LICH_SPEED_P1      = 70
LICH_SPEED_P2      = 115
LICH_PHASE2_AT     = 0.5              # switch at 50% hp
LICH_SUMMON_MS     = 5000             # phase 2 summons every 5s
LICH_SUMMON_COUNT  = 2
LICH_MAX_SUMMONS   = 4
LICH_REWARD        = 200

# Stone Golem
GOLEM_TINT         = (150, 150, 150)  # stony grey
GOLEM_DMG          = 28
GOLEM_SPEED_P1     = 45
GOLEM_SPEED_P2     = 60
GOLEM_PHASE2_AT    = 0.4              # switch at 40% hp
GOLEM_STOMP_MS     = 2500             # stomp cooldown in phase 2
GOLEM_STOMP_RADIUS = 80               # AoE radius (px)
GOLEM_STOMP_DMG    = 35
GOLEM_STOMP_WINDUP_MS = 600           # telegraph before the stomp lands
GOLEM_REWARD       = 300

BOSS_ATTACK_RANGE = 72
BOSS_ATTACK_CD_MS = 1300
BOSS_HITBOX_W = 30        # kept under one tile (32px) so bosses clear corridors
BOSS_HITBOX_H = 28
BOSS_INVIC_MS = 120                   # bosses flinch only briefly

# --------------------------------------------------------------------------
# Map / collision
# --------------------------------------------------------------------------
COLLISION_LAYER = "Walls"             # the layer whose tiles are solid
FLOOR_LAYERS = ["Floor", "Floor2_pool", "Floor2_darker_surface",
                "Floor_darker_surface"]
# tiles that are neither floor nor wall are treated as void (also solid),
# which keeps entities on the visible dungeon floor.

# --------------------------------------------------------------------------
# UI colours
# --------------------------------------------------------------------------
COLOR_HP_BG   = (80, 0, 0)
COLOR_HP_FG   = (220, 60, 60)
COLOR_GOLD    = (240, 210, 80)
COLOR_WHITE   = (255, 255, 255)
COLOR_DAMAGE  = (255, 60, 60)
COLOR_BLACK   = (0, 0, 0)
COLOR_BG      = (12, 10, 16)          # backdrop behind the map / void
COLOR_PANEL   = (20, 18, 24)
COLOR_BAR_BORDER = (10, 10, 10)
COLOR_BOSS_FG = (180, 40, 200)
COLOR_TEXT_DIM = (180, 180, 190)
COLOR_ENEMY_HP = (90, 200, 90)

# --------------------------------------------------------------------------
# HUD / damage numbers
# --------------------------------------------------------------------------
HUD_HP_BAR_W = 200
HUD_HP_BAR_H = 22
HUD_MARGIN = 14
DAMAGE_NUMBER_MS = 900       # lifetime of a floating damage number
DAMAGE_NUMBER_RISE = 40      # how far it floats up over its lifetime (px)
ENEMY_HP_BAR_W = 40
ENEMY_HP_BAR_H = 5
PHASE_FLASH_MS = 220         # white flash duration on a boss phase change
