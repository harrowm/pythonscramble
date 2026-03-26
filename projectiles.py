"""
projectiles.py - Cannon shot (player's forward-firing projectile) for Scramble.

Original Z80 sources
--------------------
fn_fire_cannon ($66B0):
    Reads fire buttons from TRS-80 keyboard matrix ($3840 bits 3+4, or
    $3804 bits 1+7).  If the cannon-shot slot at $666F is empty (state=0),
    initialises it:
        IX+0 = 1 (active)
        IX+1 = ship_x + 6   (shot column, starts 6 pixels ahead of ship)
        IX+2 = ship_y + 3   (shot row,    starts 3 pixels below ship)
        IX+3/4 = path_table_cannon ($679E)
    Only ONE cannon shot exists at a time (single-shot system).

fn_update_cannon_shot ($66E9):
    Each frame:
        1. Check IX+2 (row counter) against terrain via fn_check_terrain_clip
           ($69DE).
        2. Compute VRAM address via fn_compute_vram_offset, test bitmask
           against existing VRAM.  If overlap → collision (enemy hit).
        3. OR bitmask into VRAM to draw the shot.
        4. INC IX+2 (advance row by 1 per frame).
        5. If IX+2 >= $30 (48) → deactivate (shot went out of range).
        6. Advance path table pointer, apply Y-delta to IX+1 (column).
           If path entry = $7F → deactivate.

path_table_cannon ($679E–$67E5):
    Y-delta (column adjustment) sequence for the curved cannon trajectory.
    The shot starts by curving briskly (delta +2 for 6 frames) then
    gradually straightens (+1, then 0).

Key constraint: only ONE cannon shot active at a time (slot at $666F).
"""

from dataclasses import dataclass, field

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    CANNON_SPAWN_AHEAD, CANNON_SPAWN_BELOW,
    CANNON_MAX_ROW, CANNON_SPEED_PX, CANNON_CHAR,
    CANNON_PATH,
)
from trs80_screen import TRS80Screen


@dataclass
class CannonShot:
    """
    The player's forward-firing cannon shot.

    Z80 cannon-shot slot at $666F (5 bytes):
        +0 state   (0=inactive, 1=active)
        +1 col     (Y in Z80 coords = horizontal column; advances with path)
        +2 row     (X in Z80 coords = vertical row;    advances +1/frame)
        +3 path_lo (pointer into path_table_cannon)
        +4 path_hi

    In Python's horizontal-scroller view:
        pixel_x → horizontal position (advances by CANNON_SPEED_PX)
        pixel_y → vertical position   (adjusted by CANNON_PATH deltas)
    """

    pixel_x: float = 0.0
    pixel_y: float = 0.0
    active:  bool  = False
    _path_idx: int = 0      # current index into CANNON_PATH

    def fire(self, ship_pixel_x: float, ship_pixel_y: float) -> None:
        """
        Launch the cannon shot from just ahead of and below the ship.
        Mirrors fn_fire_cannon ($66CB–$66E8).

        Spawn offset (from assembly):
            shot column = ship_x + CANNON_SPAWN_AHEAD  (6 pixels ahead)
            shot row    = ship_y + CANNON_SPAWN_BELOW  (3 pixels below)
        Only fires if no shot is currently active (single-shot system).
        """
        if self.active:
            return   # single-shot: wait for current shot to expire
        self.pixel_x  = float(ship_pixel_x) + CANNON_SPAWN_AHEAD
        self.pixel_y  = float(ship_pixel_y) + CANNON_SPAWN_BELOW
        self._path_idx = 0
        self.active   = True

    def erase(self, screen: TRS80Screen) -> None:
        """Erase cannon shot from screen."""
        if not self.active:
            return
        screen.write_char(self.char_col, self.char_row, 0x20)

    def update(self, screen: TRS80Screen) -> bool:
        """
        Advance the cannon shot by one frame and check for collision.
        Mirrors fn_update_cannon_shot ($66E9).

        Each frame:
          • Erase at current position.
          • Advance pixel_y (row) by +1 (shot moves in Y direction).
          • Advance pixel_x (col) by the current CANNON_PATH delta (shot
            curves horizontally according to the path table).
          • Deactivate if pixel_y >= CANNON_MAX_ROW (48) or path exhausted.
          • Collision test: read VRAM char at new cell; if non-blank, hit.

        Returns True if the shot hit something (collision → caller scores),
        False if still in flight or deactivated on boundary.
        """
        if not self.active:
            return False

        # Erase at current position
        self.erase(screen)

        # Advance row (Y axis) by 1 per frame (fn_update_cannon_shot INC IX+2)
        self.pixel_y += 1.0

        # Advance column (X axis) by path-table delta (fn $6749: Y += delta)
        if self._path_idx < len(CANNON_PATH):
            delta = CANNON_PATH[self._path_idx]
            self._path_idx += 1
        else:
            delta = 0

        self.pixel_x += float(delta)

        # Deactivate if row reached $30 = 48 (fn $6740: CP $30, JR NZ,.L6749)
        if self.pixel_y >= CANNON_MAX_ROW:
            self.active = False
            return False

        # Deactivate if moved off the screen area
        if self.pixel_x >= PIXELS_WIDE or self.pixel_x < 0:
            self.active = False
            return False

        # Collision check: read VRAM char at the shot's new cell
        char = screen.read_char(self.char_col, self.char_row)
        if char != 0x20 and char != 0x80:
            screen.write_char(self.char_col, self.char_row, 0x20)
            self.active = False
            return True   # HIT

        # No collision: draw the shot
        screen.write_char(self.char_col, self.char_row, CANNON_CHAR)
        return False

    def deactivate(self) -> None:
        """Deactivate without collision (e.g. player died)."""
        self.active = False

    @property
    def char_col(self) -> int:
        return max(0, min(63, int(self.pixel_x) // 2))

    @property
    def char_row(self) -> int:
        return max(0, min(15, int(self.pixel_y) // 3))


# ---------------------------------------------------------------------------
# Backward-compatibility alias so existing imports of "Missile" still work
# during the transition period.
# ---------------------------------------------------------------------------
Missile = CannonShot   # noqa: N816  (alias, not a class definition)
