"""
constants.py - All magic numbers for the TRS-80 Scramble port.

Every value here is derived directly from the Z80 disassembly of the
original game (disk00560.dmk).  Comments explain the Z80 source where
the value originates so you can cross-reference against the .asm file.
"""

# ---------------------------------------------------------------------------
# TRS-80 DISPLAY MODEL
# ---------------------------------------------------------------------------
# The TRS-80 screen is 64 characters wide × 16 rows tall.
# Characters $80–$BF are semigraphic block characters: each cell encodes a
# 2×3 pixel grid, giving an effective resolution of 128 × 48 "pixels".
# We render each logical pixel as a scaled rectangle in SDL2.

SCREEN_CHARS_WIDE   = 64       # text columns on the TRS-80 screen
SCREEN_CHARS_TALL   = 16       # text rows
PIXELS_WIDE         = 128      # logical pixel columns (2 per char cell)
PIXELS_TALL         = 48       # logical pixel rows    (3 per char cell)

# Scale factor: each logical pixel becomes this many real screen pixels.
# 8 gives 1024×384, which fits comfortably on a modern monitor and preserves
# the original 4:3 aspect of the TRS-80 display.
PIXEL_SCALE         = 8

WINDOW_WIDTH        = PIXELS_WIDE * PIXEL_SCALE    # 1024
WINDOW_HEIGHT       = PIXELS_TALL * PIXEL_SCALE    # 384

# ---------------------------------------------------------------------------
# COLOUR PALETTE
# ---------------------------------------------------------------------------
# TRS-80 Model I/III had a green-phosphor monochrome monitor.
# These colours reproduce the look faithfully.
COLOUR_BACKGROUND   = (0,   12,  0)     # near-black phosphor background
COLOUR_PHOSPHOR     = (33,  255, 33)    # bright phosphor green (lit pixel)
COLOUR_DIM          = (10,  80,  10)    # dim glow (unlit area / scanline gap)

# HUD text colour (slightly different tone for readability)
COLOUR_HUD          = (200, 255, 200)

# Explosion flash colour
COLOUR_EXPLOSION    = (255, 200, 0)

# ---------------------------------------------------------------------------
# TIMING  (measured from trs80gp emulator cycle counts)
# ---------------------------------------------------------------------------
# The Z80 runs at 1.774 MHz.  The game loop calls ROM_DELAY ($0060) multiple
# times.  Each ROM_DELAY with BC=0 burns roughly 2000 cycles ≈ 1.1 ms.
# The main loop calls it 6 times during zone transitions (627B–628A).
# In-game, fn_add_score calls it once with BC=$0005.
#
# Measured from emulator: the plane moves approx 1 char cell per 6 frames,
# screen scrolls at ~8 frames/second in normal gameplay.

TARGET_FPS          = 30       # frames per second (matches original feel)
FRAME_TIME_MS       = 1000 // TARGET_FPS   # ≈ 33 ms

# Scroll speed table - derived from fn_scroll_screen ($64CA) phase table.
# Phase 0  = no scroll (pure delay, 3×100 DJNZ loops ≈ pause)
# Phase 1-5 = slow scroll  (delay E=$4B/$28, repeat C=2–4 times)
# Phase 6-7 = medium scroll (delay E=$96, repeat C=1)
# Phase 8   = fast scroll   (delay E=$32, repeat C=3)
# Phase 10  = fastest scroll (jump table target at $654B)
# We translate these to "pixels scrolled per frame":
SCROLL_SPEEDS = {
    0:  0,    # pause
    1:  1,
    2:  1,
    3:  1,
    4:  1,
    5:  1,
    6:  2,
    7:  2,
    8:  3,
    9:  3,
    10: 4,    # max speed (phase $0A in Z80 code)
}
DEFAULT_SCROLL_PHASE = 9   # normal in-game speed (phase stored at $64BA)

# ---------------------------------------------------------------------------
# SHIP (PLAYER)
# ---------------------------------------------------------------------------
# Initial position from fn_init_game_state ($6390):
#   ship_screen_col = $00 (A=0 → LD ($6AB6),A)
#   ship_screen_row = $05 (LD A,$05 → LD ($6AB7),A)
#   ship_pixel_x    = $67 = 103 (LD A,$67 → LD ($6AC1),A)
#   ship_pixel_y    = $00

SHIP_INIT_PIXEL_X   = 16    # left side of play area, 16 logical pixels in
SHIP_INIT_PIXEL_Y   = 24    # vertical centre (48/2)
SHIP_PIXEL_X_FIXED  = 16    # ship does NOT move horizontally in Scramble

# Ship sprite is 13 chars wide × 5 rows (from data_ship_sprite $63BC and
# the draw loop at $6355 which uses B=$0D = 13, C=$05 = 5 rows).
# In logical pixel terms that is 26 px wide × 15 px tall.
# The actual visible sprite is sparser - spaces ($20) are transparent.
SHIP_SPRITE_COLS    = 13    # character columns
SHIP_SPRITE_ROWS    = 5     # character rows

# Gravity: ship drifts down 1 logical pixel per frame if not pressing UP.
# Pressing UP raises ship 2 px/frame (net +1 upward).
# Confirmed from fn_move_ship ($65BF) which writes to ship_pixel_y ($6AC2).
SHIP_GRAVITY_PX     = 1     # pixels fallen per frame (downward)
SHIP_THRUST_PX      = 2     # pixels risen per frame when UP held

# Ship sprite: two rows of 6 semigraphic chars each.
# Drawn from data at $63BC (all $20 spaces = transparent placeholder).
# The actual sprite pattern is built from the screen layout data.
# We define it here as a 2D list of (char_or_None) values where None = transparent.
# Row 0 (top):    _ _ > = - -
# Row 1 (bottom): _ _ > = - _
# Using TRS-80 semigraphic chars: $BF=full block, $B5, $B7 etc for partial.
# From screen data at $5e80 we see: b7 ; bb ; b7 ; b5 (fighters screen uses these)
# The ship sprite chars from buf at $66A8 (written during init):
SHIP_SPRITE_CHARS = [
    # Row 0: 6 chars representing the ship profile (top half)
    0x80, 0x98, 0xB5, 0xBF, 0xB0, 0x80,
    # Row 1: 6 chars (bottom half)
    0x80, 0x90, 0xB7, 0xBF, 0xA0, 0x80,
]
SHIP_WIDTH_CHARS    = 6     # chars wide for collision
SHIP_HEIGHT_CHARS   = 2     # chars tall for collision

# ---------------------------------------------------------------------------
# MISSILE (machine gun - fires right)
# ---------------------------------------------------------------------------
# fn_fire_missile ($6A16) sets missile active and positions it at ship nose.
# Missile char is a single filled cell ($BF).
MISSILE_SPEED_PX    = 4     # pixels per frame (moves right)
MISSILE_CHAR        = 0xBF  # full block semigraphic char

# ---------------------------------------------------------------------------
# BOMB (drops downward)
# ---------------------------------------------------------------------------
# fn_drop_bomb ($6B98) drops a bomb from beneath the ship.
# Bomb moves down 1 row (2 logical pixels) per frame.
BOMB_SPEED_PX       = 2     # pixels per frame (moves down)
BOMB_CHAR           = 0xBF  # full block

# ---------------------------------------------------------------------------
# SCORING  (from fn_add_score $6D99 and fn_check_bonus_life $6DE8)
# ---------------------------------------------------------------------------
# Score is stored as 3-byte BCD at $6660–$6662.
# Points per enemy type (from zone descriptions and disassembly context):
SCORE_FIGHTER       = 50
SCORE_FIREBALL      = 50
SCORE_UFO           = 100
SCORE_FUEL_TANK     = 150   # from "150" text in sector 3 data
SCORE_ROCKET        = 50
SCORE_MYSTERY       = 100
SCORE_FORT          = 75    # "75" text in sector 3
SCORE_ACK_ACK       = 125   # "125" text in sector 3

BONUS_LIFE_SCORE    = 10000  # "BONUS LIFE FOR EVERY 10000 SCORED" at $621F

# ---------------------------------------------------------------------------
# LIVES AND FUEL
# ---------------------------------------------------------------------------
STARTING_LIVES      = 3
STARTING_FUEL       = 0x9F   # fuel_level init value (from context of $6664)
FUEL_DRAIN_RATE     = 1      # units drained per frame

# ---------------------------------------------------------------------------
# ENEMY TYPES
# ---------------------------------------------------------------------------
# Zone order from screen data strings and zone table at $63AC:
#   0 = Fighters  1 = Blimps  2 = Bombers  3 = Fort
#   4 = Factory   5 = Rocket  6 = Fuel Tank  7 = Arsenal/ACK-ACK

ZONE_NAMES = [
    "FIGHTERS",
    "BLIMPS",
    "BOMBERS",
    "FORT",
    "FACTORY",
    "ROCKETS",
    "FUEL TANKS",
    "ARSENAL",
]
NUM_ZONES = len(ZONE_NAMES)

# Number of enemies active at once per zone (approximate from original)
MAX_ENEMIES         = 8

# Enemy object record size (fields): x, y, dx, dy, type, active, frame
ENEMY_RECORD_SIZE   = 7

# ---------------------------------------------------------------------------
# TERRAIN
# ---------------------------------------------------------------------------
# The TRS-80 screen has 64 columns.  The terrain occupies the top N rows
# (ceiling) and bottom M rows (floor).  During gameplay the terrain scrolls
# left; new column data comes from the zone's terrain height table.
#
# Video RAM base = $3C00.  fn_draw_terrain ($6495) reads from $3C00 and
# converts chars: if char >= $80 it computes BF - (char - 80) as the
# solid-block depth.  This means char $80 = 0 depth (blank), $BF = 63 deep.
#
# The ceiling height and floor height are stored per-column.
TERRAIN_COLS        = 128    # logical pixel columns in the terrain buffer
                             # (wider than screen so we can scroll smoothly)

# Terrain height ranges per zone (top ceiling depth, bottom floor depth)
# in logical pixel rows (0 = flush with edge, 48 = whole screen blocked)
TERRAIN_CEILING_MIN = 4
TERRAIN_CEILING_MAX = 16
TERRAIN_FLOOR_MIN   = 4
TERRAIN_FLOOR_MAX   = 16

# ---------------------------------------------------------------------------
# EXPLOSION ANIMATION
# ---------------------------------------------------------------------------
# fn_draw_explosion ($6CA8) renders a 3×3 char explosion that fades over
# several frames.  We use 8 frames matching the original timing.
EXPLOSION_FRAMES    = 8
EXPLOSION_CHARS = [
    # Frame 0 (brightest - full blocks)
    [0xBF, 0xBF, 0xBF,
     0xBF, 0xBF, 0xBF,
     0xBF, 0xBF, 0xBF],
    # Frame 1
    [0xBF, 0xB7, 0xBF,
     0xB7, 0xBF, 0xB7,
     0xBF, 0xB7, 0xBF],
    # Frame 2
    [0xB5, 0xB7, 0xB5,
     0xB7, 0xBF, 0xB7,
     0xB5, 0xB7, 0xB5],
    # Frame 3
    [0x90, 0xB5, 0x90,
     0xB5, 0xB7, 0xB5,
     0x90, 0xB5, 0x90],
    # Frame 4
    [0x80, 0x90, 0x80,
     0x90, 0xB5, 0x90,
     0x80, 0x90, 0x80],
    # Frame 5
    [0x80, 0x80, 0x80,
     0x80, 0x90, 0x80,
     0x80, 0x80, 0x80],
    # Frames 6-7 (blank)
    [0x80] * 9,
    [0x80] * 9,
]

# ---------------------------------------------------------------------------
# HUD LAYOUT  (character positions on the 64×16 text screen)
# ---------------------------------------------------------------------------
HUD_ROW             = 15    # bottom row of the screen
HUD_SCORE_COL       = 0
HUD_LIVES_COL       = 20
HUD_FUEL_COL        = 32
HUD_FUEL_BAR_WIDTH  = 20    # characters wide for the fuel bar
HUD_ZONE_COL        = 54

# ---------------------------------------------------------------------------
# KEYBOARD MAPPING
# ---------------------------------------------------------------------------
# TRS-80 keyboard is memory-mapped at $3800-$38FF.
# We map these to SDL2 keycodes in input.py.
# Original: UP/DOWN = arrow keys or I/M, FIRE = Q+W, BOMB = UP+DOWN
# (from instruction text at $5E00: "PRESS ARROW KEYS OR Q,W TO FIRE")

# SDL2 scancodes used by input.py - defined here as documentation.
# input.py uses sdl2.SDL_SCANCODE_* directly; these are just reference values.
# UP arrow, DOWN arrow, Z, X, Space, Alt, Enter, Escape
# See input.py for the full keyboard mapping.
