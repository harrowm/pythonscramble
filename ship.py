"""
ship.py - Player ship for Scramble.

Original Z80 sources
--------------------
fn_init_game_state ($6390):
    ship_screen_col ($6AB6) = 0
    ship_screen_row ($6AB7) = 5
    ship_pixel_x    ($6AC1) = $67 = 103  (horizontal pixel position)
    ship_pixel_y    ($6AC2) = 0

fn_draw_ship ($65A3):
    Copies 6 chars from buf at $66A8 to video RAM at $3C39.
    The loop: LD A,(HL) / CP $20 / JR Z,skip / LD (DE),A
    i.e. space chars ($20) are transparent - not written to screen.
    This is the "masked sprite" technique.

fn_erase_ship ($65AE):
    Writes $20 (space) to 6 consecutive video RAM addresses.

fn_move_ship ($65BF):
    Loads ship_pixel_y, applies UP/DOWN input, gravity.

fn_check_ship_crash ($65C2):
    Checks 6 video RAM cells at ship position for non-space chars.

The ship is fixed at a horizontal pixel position of ~16 (left side of
screen).  Vertical position is controlled by the player: UP key applies
upward thrust, gravity pulls the ship down each frame.

Ship sprite
-----------
The ship sprite is 6 character cells wide × 2 rows tall.  In the original
the sprite data is loaded from the screen layout buffer at $66A8.  We
approximate the original sprite shape using TRS-80 semigraphic characters:

  Top row:    [blank, top-right-corner, right-block, full-block, partial, blank]
  Bottom row: [blank, bottom-right, right-block, full-block, partial, blank]

The rightmost part is the cockpit/nose; the left part is the engine exhaust.
"""

from dataclasses import dataclass

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    SHIP_INIT_PIXEL_X, SHIP_INIT_PIXEL_Y,
    SHIP_PIXEL_X_FIXED,
    SHIP_GRAVITY_PX, SHIP_THRUST_PX,
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

    Position is tracked in *logical pixels* (0–127 horizontal, 0–47 vertical).
    The ship is drawn as a 6×2 character-cell sprite, with each char cell
    covering 2×3 logical pixels.

    Mirrors the state tracked by the Z80 game at:
        $6AB6 (ship_screen_col), $6AB7 (ship_screen_row)
        $6AC1 (ship_pixel_x),    $6AC2 (ship_pixel_y)
    """

    # Pixel-space position of the top-left corner of the sprite
    pixel_x: float = float(SHIP_INIT_PIXEL_X)
    pixel_y: float = float(SHIP_INIT_PIXEL_Y)

    # Previous pixel_y - used for erase/redraw
    prev_pixel_y: float = float(SHIP_INIT_PIXEL_Y)

    # Vertical velocity in pixels/frame (positive = downward)
    velocity_y: float = 0.0

    # State flags
    alive: bool = True
    invulnerable_frames: int = 0  # frames of post-death invulnerability

    def reset(self) -> None:
        """
        Reset ship to initial state.
        Mirrors fn_init_game_state ($6390).
        """
        self.pixel_x = float(SHIP_INIT_PIXEL_X)
        self.pixel_y = float(SHIP_INIT_PIXEL_Y)
        self.prev_pixel_y = float(SHIP_INIT_PIXEL_Y)
        self.velocity_y = 0.0
        self.alive = True
        self.invulnerable_frames = 0

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def update(self, thrust_up: bool, thrust_down: bool) -> None:
        """
        Apply gravity and player input to update vertical position.
        Mirrors fn_move_ship ($65BF).

        The original game:
        - Gravity pulls the ship down SHIP_GRAVITY_PX pixels/frame
        - Pressing UP applies SHIP_THRUST_PX upward force
        - Pressing DOWN (not in classic Scramble - the ship can only go up
          or drift down naturally)  -- some versions allow down.
        - Horizontal position is FIXED (Scramble has no horizontal control)
        """
        self.prev_pixel_y = self.pixel_y

        if self.invulnerable_frames > 0:
            self.invulnerable_frames -= 1

        # Apply thrust or gravity to velocity
        if thrust_up:
            # Thrust up: overcome gravity + climb
            self.velocity_y -= SHIP_THRUST_PX
        else:
            # Gravity
            self.velocity_y += SHIP_GRAVITY_PX

        # Clamp velocity to sane range
        self.velocity_y = max(-6.0, min(4.0, self.velocity_y))

        # Apply velocity
        self.pixel_y += self.velocity_y

        # Clamp to screen bounds (can't fly above top or below bottom)
        # Leave 6 px buffer at top (ceiling), 6 px at bottom (floor HUD row)
        self.pixel_y = max(0.0, min(PIXELS_TALL - 6.0, self.pixel_y))

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
        Mirrors fn_check_ship_crash ($65C2).

        The Z80 code reads the video RAM character at each of the 6 cells
        occupied by the ship.  If any cell contains a non-blank char that
        was NOT written by the ship itself (i.e. was already there before
        fn_draw_ship ran), the ship has crashed.

        We implement this by checking the cells BEFORE drawing the ship,
        looking for any non-blank content.
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
        return self.pixel_y <= 0 or self.pixel_y >= PIXELS_TALL - 6

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
