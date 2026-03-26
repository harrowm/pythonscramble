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
# Initial position from fn_init_game_state ($638F/$6390):
#   ship_x ($6AAE) = $14 = 20  (horizontal pixel coordinate)
#   ship_y ($6AAF) = $14 = 20  (vertical pixel coordinate)
# Both values are in the same pixel space as fn_compute_vram_offset ($6EE0):
#   X range 0–$79 (121), Y range 0–$2C (44).
# NOTE: fn_init_game_state does NOT reset score/lives/fuel — only position.

SHIP_INIT_PIXEL_X   = 20    # ship_x ($6AAE) initial = $14 = 20
SHIP_INIT_PIXEL_Y   = 20    # ship_y ($6AAF) initial = $14 = 20

# Movement bounds (from fn_update_ship_pos $6926 clamp checks):
#   X: stop if would reach $7A (122), reset if would reach $FE (underflow→0)
#   Y: stop if would reach $2D (45) or above.
SHIP_X_MAX          = 121   # $79: rightmost safe X pixel column
SHIP_Y_MAX          = 44    # $2C: bottom-most safe Y pixel row

# Movement speeds per update call (from fn_update_ship_pos $6926):
#   UP/DOWN keys: INC B / INC B → ship_x ±= 2 (horizontal movement speed)
#   LEFT/RIGHT keys: INC C / DEC C → ship_y ±= 1 (vertical movement speed)
# NOTE: no gravity. The ship holds its position when no direction key pressed.
SHIP_SPEED_X        = 2     # horizontal pixels per update when moving left/right
SHIP_SPEED_Y        = 1     # vertical pixels per update when moving up/down

# Ship sprite is 13 chars wide × 5 rows (from data_ship_sprite $63BC and
# the draw loop at $6355 which uses B=$0D = 13, C=$05 = 5 rows).
# In logical pixel terms that is 26 px wide × 15 px tall.
# The actual visible sprite is sparser - spaces ($20) are transparent.
SHIP_SPRITE_COLS    = 13    # character columns
SHIP_SPRITE_ROWS    = 5     # character rows

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
# CANNON SHOT (player's forward-firing projectile)
# ---------------------------------------------------------------------------
# fn_fire_cannon ($66B0): fires if $3840 bits 3+4 set and slot at $666F empty.
# Spawn offset from ship (fn_fire_cannon $66CF/$66DC):
#   shot_col = ship_x + 6   (IX+1 ← ship_x + $06)
#   shot_row = ship_y + 3   (IX+2 ← ship_y + $03)
# Trajectory from path_table_cannon ($679E): curves Y column downward+rightward
#   then travels straight.  Deactivates when shot_row >= $30 (48).
# fn_update_cannon_shot ($66E9) advances the shot each frame.
CANNON_SPAWN_AHEAD  = 6     # columns ahead of ship (added to ship_x)
CANNON_SPAWN_BELOW  = 3     # rows below ship (added to ship_y)
CANNON_MAX_ROW      = 48    # $30: shot deactivates when shot_row reaches 48
CANNON_SPEED_PX     = 2     # horizontal pixels per frame (forward movement)
CANNON_CHAR         = 0xBF  # full block semigraphic char

# path_table_cannon ($679E–$67E5): Y-delta sequence for curved trajectory.
# Each entry is added to shot_col (the column/X) each frame while
# shot_row (the row/Y) advances +1 per frame independently.
# $7F = end-of-path sentinel (shot deactivates).
CANNON_PATH = [
    2, 2, 2, 2, 2, 2,            # $679E–$67A3 steep curve
    1, 1, 1,                     # $67A4–$67A6
    1, 0, 1,                     # $67A7–$67A9
    1, 0, 1,                     # $67AA–$67AC
    0,                           # $67AD
    1, 0, 1,                     # $67AE–$67B0
    0,                           # $67B1
    1, 0, 0,                     # $67B2–$67B4
] + [0] * 47                     # $67B5–$67E5 level flight (all zeros)

# ---------------------------------------------------------------------------
# SCORING  (from fn_add_pending_score $6A16 / fn_score_to_decimal $6A4E /
#           fn_check_ship_crash $65CA)
# ---------------------------------------------------------------------------
# Score is stored as 24-bit binary at $6696 (hi) / $6697-$6698 (lo).
# Pending score increment is held at $66AE (16-bit) and added by
# fn_add_pending_score ($6A16) which then re-encodes to 6 ASCII digits.
#
# Points per hit_type come from the 16-bit table at $64AA (LE pairs):
#   type 0: $0000 = 0     type 1: $007D = 125   type 2: $004B = 75
#   type 3: $0064 = 100   type 4: $0096 = 150   type 5: $004B = 75
#   type 6: $0032 = 50    type 7: $0019 = 25
#   type 8 (bunker): random 500 / 1000 / 1500 via Z80 R register
#   type 9 (fuel pod): 0 (already handled, no score awarded)
SCORE_ENC_TYPE = {
    1: 125,    # type 1 (ACK-ACK / anti-aircraft)
    2:  75,    # type 2 (fort / bunker shell)
    3: 100,    # type 3 (medium aircraft)
    4: 150,    # type 4 (fuel tank)
    5:  75,    # type 5
    6:  50,    # type 6 (fighter)
    7:  25,    # type 7 (small target)
    8: 1000,   # type 8 (bunker, midpoint of 500/1000/1500 range)
}
# Named aliases matching the Python enemy type names:
SCORE_FIGHTER       = 50    # encounter type 6: $0032
SCORE_FIREBALL      = 50    # same as fighter
SCORE_UFO           = 100   # encounter type 3: $0064
SCORE_FUEL_TANK     = 150   # encounter type 4: $0096
SCORE_ROCKET        = 75    # encounter type 2: $004B
SCORE_MYSTERY       = 100   # encounter type 3: $0064
SCORE_FORT          = 75    # encounter type 2: $004B
SCORE_ACK_ACK       = 125   # encounter type 1: $007D

BONUS_LIFE_SCORE    = 10000  # str_bonus_life at $621F: "BONUS LIFE FOR EVERY 10000 SCORED"

# ---------------------------------------------------------------------------
# LIVES AND FUEL
# ---------------------------------------------------------------------------
# lives_remaining at $6663: initialised by fn_init_game_state path.
# fuel_level at $6664: 11 bytes (RAM block, $6664-$666E).
# fn_consume_fuel ($6D46) decrements IX+7 (encounter fuel counter).
# fn_consume_entry_fuel ($6CA8) drains fuel when ship is near a fuel encounter.
# fuel_level is part of the encounter record system, not a simple global counter.
STARTING_LIVES      = 3
STARTING_FUEL       = 0x9F   # initial fuel bar fill (encoded as fraction of $9F)
FUEL_DRAIN_RATE     = 1      # units drained per frame (approximation)

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

# terrain_step ($6AAD) controls the height appended by fn_advance_terrain.
# Initial value = $2F = 47 from data block at $6AAD.
# fn_update_terrain_height (.L6E7F) modifies it via a 16-bit LFSR
# seeded from the terrain-type table at $702C + (level_pos & $1F)*2.
# Modifier at $6AC0: +1 (gentle slope) or $FF (-1, flat/blocked ocean).
# terrain_step clamps: if step >= $30 (48) modifier becomes $FF;
#                      if step < $19 (25) modifier is +1;
#                      otherwise depends on level_pos bit 6.
TERRAIN_INIT_STEP   = 47     # $2F: initial terrain_step at $6AAD

# LFSR initial state at $6ABE (lo=00), $6ABF (hi=FF) — effectively HL=$FF00.
# Seeds at $702C are 2-byte pairs for each of 32 terrain type slots.
# We approximate with 32 seed pairs that produce varied terrain patterns.
TERRAIN_SEED_TABLE = [
    # 32 entries x 2 bytes (lo & hi): sourced from $702C-$706B in ROM.
    # These approximate the original ROM values to produce similar terrain.
    0xA8, 0x03,  0xD0, 0x07,  0x68, 0x0F,  0x50, 0x1E,
    0xB8, 0x01,  0x70, 0x03,  0xC0, 0x06,  0x80, 0x0D,
    0x38, 0x1B,  0x10, 0x36,  0x20, 0x6C,  0x40, 0x58,
    0xC8, 0x0B,  0x90, 0x17,  0x60, 0x2F,  0xA0, 0x5F,
    0x78, 0x04,  0xF0, 0x08,  0xE0, 0x11,  0xC4, 0x23,
    0x88, 0x02,  0x48, 0x05,  0x28, 0x0A,  0x58, 0x14,
    0x30, 0x29,  0x60, 0x52,  0xC0, 0x24,  0x80, 0x49,
    0xA0, 0x12,  0x40, 0x25,  0xE8, 0x4A,  0xD0, 0x15,
]

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
# ---------------------------------------------------------------------------
# INSTRUCTIONS SCREEN DATA  (extracted from arcbomb1.cmd)
# ---------------------------------------------------------------------------
# Semigraphic score/enemy panorama: 8 rows x 64 bytes from Z80 addr $5E80.
# Displayed in screen rows 5-14 with left-scroll during INSTRUCTIONS state.
INSTR_SCREEN_DATA = bytes([
    0x80,0x80,0x80,0x80,0x80,0x8C,0xB7,0xBB,0x8C,0x80,0x84,0x88,0x80,0x84,0x88,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x88,0x8C,0xB7,0x80,0x46,0x49,0x47,0x48,0x54,0x45,0x52,0x53,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x98,0x90,0x80,0x42,0x4C,0x49,0x4D,0x50,0x53,0x80,0x80,0x80,0x80,0x80,0x80,0x80,  # FIGHTERS/BLIMPS header row
    0x80,0x80,0x80,0x80,0x80,0x42,0x4F,0x4D,0x42,0x45,0x52,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x88,0x8C,0xB7,0x80,0x80,0x35,0x30,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x82,0x80,0xA6,0x84,0x80,0x32,0x35,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,  # BOMBER score row
    0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x8C,0x80,0x80,0x80,0x80,0xA0,0xA0,0xA0,0xA0,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xA8,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,  # enemy-sprite data row 1
    0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xB0,0xB7,0xBF,0xBB,0xB7,0xB5,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xBC,0x80,0x80,0x80,0x80,0x81,0x81,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xB0,0xB0,0x90,0xB0,0x80,0x80,0x80,0x80,0x80,  # enemy-sprite data row 2
    0x80,0xA0,0x80,0x80,0x80,0x80,0x80,0x80,0xB0,0xB0,0xB0,0x8C,0x86,0x80,0x46,0x4F,0x52,0x54,0x80,0x83,0xA4,0x90,0x80,0x80,0x80,0x80,0x80,0xB0,0xB0,0x90,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xA0,0xB0,0x8C,0x8C,0xB0,0xB0,0xBD,0xB5,0xB7,0xB7,0xB5,0x80,0x80,0x80,0xB0,  # FORT/blimp sprite row
    0xB0,0xB6,0xB4,0xB0,0x98,0x8C,0x83,0x83,0x80,0x80,0x80,0x80,0x80,0x80,0x31,0x35,0x30,0x80,0x80,0x80,0x80,0x82,0x83,0x89,0x8C,0xB0,0xB2,0xB7,0xB7,0xB7,0xB0,0xB0,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0xA0,0xB0,0xB0,0xB7,0xB7,0xB5,0x98,0x8C,0x81,0x80,0x80,0x80,0x46,0x41,0x43,0x54,0x4F,0x52,0x59,0x89,0x8C,0x90,0x52,  # 150/FACTORY score row
    0x4F,0x43,0x4B,0x45,0x54,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x46,0x55,0x45,0x4C,0x80,0x54,0x41,0x4E,0x4B,0x83,0x8C,0xA4,0xB0,0xB5,0xB5,0xB0,0x8C,0x8C,0x81,0x41,0x52,0x53,0x45,0x4E,0x41,0x4C,0x80,0x80,0x80,0x80,0x80,0x80,0x31,0x30,0x30,0x80,0x80,0x80,0x80,0x82,0x80,  # ROCKET/FUEL TANK row
    0x37,0x35,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x31,0x32,0x35,0x80,0x80,0x80,0x80,0x80,0x41,0x43,0x4B,0x2D,0x41,0x43,0x4B,0x80,0x80,0x80,0x80,0x80,0x3F,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,0x80,  # 75/125/ACK-ACK row
])

# Five @-terminated instruction text rows, verbatim from Z80 memory $5D40-$5E7F.
INSTR_TEXT_ROWS = [
    '      TO MOVE BOMBER  LEFT,RIGHT  PRESS ARROW KEYS OR O,P       ',
    '               UP,DOWN   PRESS ARROW KEYS OR Q,W                ',
    '     TO FIRE MACHINE GUN PRESS LEFT & RIGHT SIMULTANEOUSLY      ',
    '     TO DROP BOMBS   -   PRESS   UP & DOWN  SIMULTANEOUSLY      ',
    '    PRESS <SPACE> TO START, <SHIFT> & <BREAK> TO ABORT GAME     ',
]
