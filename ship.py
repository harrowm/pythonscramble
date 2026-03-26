"""
ship.py - Player ship for Scramble.

Original Z80 sources
--------------------
fn_init_game_state ($638F/$6390):
    ship_x ($6AAE) = $14 = 20   (horizontal pixel coordinate)
    ship_y ($6AAF) = $14 = 20   (vertical pixel coordinate)
    These are written by LD A,$00/$05/$67 stores; the true entry is at
    $638F where the tail byte $3E of the *LAST* hi-score string acts as
    the opcode for LD A,$00.

fn_update_ship_pos ($6926):
    Reads TRS-80 joystick matrix at $3800 and updates ship_x / ship_y.
    NO GRAVITY.  Ship holds its current position when no direction key
    is being held.  Movement per update tick (every 5th frame):
        UP key   ($3840 bit 6): B += 2 → ship_x += 2 (move right/forward)
        DOWN key ($3840 bit 5): B -= 2 → ship_x -= 2 (move left/backward)
        RIGHT key ($3840 bit 3): C -= 1 → ship_y -= 1 (move up)
        LEFT key  ($3840 bit 4): C += 1 → ship_y += 1 (move down)
    Clamps: X stops at $7A (122); Y stops at $2D (45).

fn_redraw_ship ($69A4):
    Blits the ship sprite to VRAM using pixel-bitmask technique (fn_update_
    cannon_shot style OR-into-cell).  Detects collision via AND between the
    sprite bitmask and existing VRAM content; sets collision_flag ($6678).

fn_draw_ship ($65A3):
    Copies B bytes from sprite buffer (HL) to VRAM (DE) with per-byte
    transparency: bytes equal to $20 (ASCII space) are skipped.
"""

from dataclasses import dataclass

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    SHIP_INIT_PIXEL_X, SHIP_INIT_PIXEL_Y,
    SHIP_X_MAX, SHIP_Y_MAX,
    SHIP_SPEED_X, SHIP_SPEED_Y,
    SHIP_SPRITE_CHARS, SHIP_WIDTH_CHARS, SHIP_HEIGHT_CHARS,
)
from trs80_screen import TRS80Screen


# ---------------------------------------------------------------------------
# Ship sprite definition
# ---------------------------------------------------------------------------
# Each entry is a (char_code, col_offset, row_offset) tuple.
# char_code = TRS-80 semigraphic char; 0x20 = transparent (not drawn).
# This matches the masked-sprite approach of fn_draw_ship ($65A3).
#
# The sprite is 6 chars wide × 2 rows.  We define it so that the ship
# looks like a side-view spacecraft pointing right (the direction of travel).
#
# Semigraphic chars used:
#   $80 = blank/transparent
#   $BF = full block (both cols, all 3 rows ON)
#   $B5 = right half + top-left + bottom-left  (10 11 01)  →  ▌▐-type
#   $B7 = right half solid (10 11 11)
#   $9C = top-right + bottom right (01 11 00) → partial
#   $90 = top-right only (01 00 00)
#   $A0 = bottom-right row only (00 00 01) - no, let's compute properly
#
#  bit layout (for char = $80 | bits):
#    bit5 bit4 = row0 (top):    left-px  right-px
#    bit3 bit2 = row1 (mid):    left-px  right-px
#    bit1 bit0 = row2 (bottom): left-px  right-px
#
# Building the ship shape (pointing RIGHT →):
#
#   col: 0    1    2    3    4    5
# row 0: .    .    ##   ##   ##   .      (top half of fuselage + wing)
# row 1: ##   ##   ##   ##   .    .      (bottom fuselage + cockpit nose)
#
# Let's assign chars:
#   col 0, row 0 = $80  (transparent)
#   col 1, row 0 = $B0  = bits 110000 = top two rows, left pixel only
#   col 2, row 0 = $B8  = bits 111000 = top row both + mid left
#   col 3, row 0 = $BF  = full block
#   col 4, row 0 = $B4  = bits 110100 = top row + mid right only
#   col 5, row 0 = $80  (transparent)
#
#   col 0, row 1 = $9F  = bits 011111 = all except top-left
#   col 1, row 1 = $BF  = full block
#   col 2, row 1 = $BF  = full block
#   col 3, row 1 = $B7  = bits 110111 = full except mid-left
#   col 4, row 1 = $A4  = bits 100100 = top-right + bottom-right (nose tip)
#   col 5, row 1 = $80  (transparent)

SHIP_SPRITE = [
    # (char_code, col_offset, row_offset)
    # Top row
    (0x80, 0, 0),   # transparent
    (0xB0, 1, 0),   # upper wing root
    (0xB8, 2, 0),   # upper fuselage
    (0xBF, 3, 0),   # upper fuselage (solid)
    (0xB4, 4, 0),   # upper nose
    (0x80, 5, 0),   # transparent
    # Bottom row
    (0x9F, 0, 1),   # engine / exhaust
    (0xBF, 1, 1),   # lower fuselage
    (0xBF, 2, 1),   # lower fuselage
    (0xB7, 3, 1),   # lower nose
    (0xA4, 4, 1),   # nose tip
    (0x80, 5, 1),   # transparent
]


@dataclass
class Ship:
    """
    Represents the player's ship.

    Position is tracked in *logical pixels* matching the TRS-80 semigraphic
    coordinate space used by fn_compute_vram_offset ($6EE0):
        X (horizontal): 0–121  ($6AAE ship_x)
        Y (vertical):   0–44   ($6AAF ship_y)

    The ship has NO gravity.  It holds its current position until the player
    presses a direction key.  This matches fn_update_ship_pos ($6926) which
    only updates position when a key is held.
    """

    # Pixel-space position
    pixel_x: float = float(SHIP_INIT_PIXEL_X)
    pixel_y: float = float(SHIP_INIT_PIXEL_Y)

    # Previous pixel_y - used for erase/redraw
    prev_pixel_y: float = float(SHIP_INIT_PIXEL_Y)

    # State flags
    alive: bool = True
    invulnerable_frames: int = 0  # frames of post-death invulnerability

    def reset(self) -> None:
        """
        Reset ship to initial state.
        Mirrors fn_init_game_state ($638F/$6390) which sets:
            ship_x ($6AAE) <- 20, ship_y ($6AAF) <- 20.
        """
        self.pixel_x = float(SHIP_INIT_PIXEL_X)
        self.pixel_y = float(SHIP_INIT_PIXEL_Y)
        self.prev_pixel_y = float(SHIP_INIT_PIXEL_Y)
        self.alive = True
        self.invulnerable_frames = 0

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def update(
        self,
        move_up: bool = False,
        move_down: bool = False,
        move_right: bool = False,
        move_left: bool = False,
    ) -> None:
        """
        Apply player directional input to update position.
        Mirrors fn_update_ship_pos ($6926).

        No gravity.  The ship holds its current position until a key is
        pressed.  Per fn_update_ship_pos:
            UP/DOWN keys:   ship_x ±2 (horizontal, forward/backward)
            LEFT/RIGHT keys: ship_y ±1 (vertical, up/down in the cave)

        In Python's horizontal-scroller interpretation:
            RIGHT arrow → ship_x += SHIP_SPEED_X (fly forward)
            LEFT arrow  → ship_x -= SHIP_SPEED_X (pull back)
            UP arrow    → ship_y -= SHIP_SPEED_Y (rise toward ceiling)
            DOWN arrow  → ship_y += SHIP_SPEED_Y (dive toward floor)

        Bounds from fn_update_ship_pos $6963/$6972:
            X: skip store if X would reach $7A (122) or wrap via $FE
            Y: skip store if Y >= $2D (45)
        """
        self.prev_pixel_y = self.pixel_y

        if self.invulnerable_frames > 0:
            self.invulnerable_frames -= 1

        # Horizontal movement (maps to UP/DOWN keys in Z80)
        if move_right:
            new_x = self.pixel_x + SHIP_SPEED_X
            if new_x < SHIP_X_MAX:
                self.pixel_x = new_x
        if move_left:
            new_x = self.pixel_x - SHIP_SPEED_X
            if new_x >= 0:
                self.pixel_x = new_x

        # Vertical movement (maps to RIGHT/LEFT keys in Z80)
        if move_up:
            new_y = self.pixel_y - SHIP_SPEED_Y
            if new_y >= 0:
                self.pixel_y = new_y
        if move_down:
            new_y = self.pixel_y + SHIP_SPEED_Y
            if new_y <= SHIP_Y_MAX:
                self.pixel_y = new_y

    # ------------------------------------------------------------------
    # Screen drawing
    # ------------------------------------------------------------------

    def erase(self, screen: TRS80Screen) -> None:
        """
        Erase the ship sprite from the screen by writing blank chars.
        Mirrors fn_erase_ship ($65AE) which writes $20 (space) to each
        of the 6 character cells the ship occupied.
        """
        col = int(self.pixel_x) // 2
        row = int(self.prev_pixel_y) // 3
        for dc in range(SHIP_WIDTH_CHARS):
            for dr in range(SHIP_HEIGHT_CHARS):
                screen.write_char(col + dc, row + dr, 0x20)

    def draw(self, screen: TRS80Screen) -> None:
        """
        Draw the ship sprite to the screen.
        Mirrors fn_draw_ship ($65A3) which copies the sprite buffer to
        video RAM, skipping cells where the sprite char is $20 (space).
        This transparency lets the background show through the ship outline.
        """
        if not self.alive:
            return

        col = int(self.pixel_x) // 2
        row = int(self.pixel_y) // 3

        for char_code, dc, dr in SHIP_SPRITE:
            if char_code == 0x80 or char_code == 0x20:
                continue  # transparent pixel - don't overwrite background
            c = col + dc
            r = row + dr
            if 0 <= c < 64 and 0 <= r < 16:
                screen.write_char(c, r, char_code)

    # ------------------------------------------------------------------
    # Collision detection
    # ------------------------------------------------------------------

    def check_terrain_collision(self, screen: TRS80Screen) -> bool:
        """
        Check whether the ship has collided with terrain or an enemy.
        Mirrors the pixel-bitmask collision in fn_redraw_ship ($69A4): the
        sprite mask bytes are AND-ed against existing VRAM content; if any
        overlap exists fn_set_collision_flag ($69D6) fires and sets
        collision_flag $6678.  fn_check_ship_crash ($65CA) then processes
        that event (awards score, triggers scroll effect).

        We approximate this at char-cell granularity: any non-blank cell
        at a position the ship occupies counts as a collision.
        """
        if not self.alive or self.invulnerable_frames > 0:
            return False

        col = int(self.pixel_x) // 2
        row = int(self.pixel_y) // 3

        for dc in range(SHIP_WIDTH_CHARS):
            for dr in range(SHIP_HEIGHT_CHARS):
                c = col + dc
                r = row + dr
                if 0 <= c < 64 and 0 <= r < 16:
                    char = screen.read_char(c, r)
                    # Any non-blank char (not $20 space, not $80 blank)
                    # that was not written by our own sprite is a collision.
                    if char != 0x20 and char != 0x80:
                        return True
        return False

    def check_screen_boundary(self) -> bool:
        """Return True if ship is touching the top or bottom screen edge."""
        return self.pixel_y <= 0 or self.pixel_y >= SHIP_Y_MAX

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def char_col(self) -> int:
        """Character column of ship's top-left corner."""
        return int(self.pixel_x) // 2

    @property
    def char_row(self) -> int:
        """Character row of ship's top-left corner."""
        return int(self.pixel_y) // 3

    @property
    def nose_pixel_x(self) -> int:
        """Logical pixel x of the ship's nose (rightmost point)."""
        return int(self.pixel_x) + SHIP_WIDTH_CHARS * 2

    @property
    def nose_pixel_y(self) -> int:
        """Logical pixel y of the ship's centre (vertically)."""
        return int(self.pixel_y) + SHIP_HEIGHT_CHARS  # midpoint
