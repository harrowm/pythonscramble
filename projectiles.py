"""
projectiles.py - Missile (machine gun) and Bomb for Scramble.

Original Z80 sources
--------------------
fn_fire_missile ($6A16):
    Reads missile active state.  If not active, positions the missile at
    the ship's nose (right edge of ship sprite) and sets active flag.
    The missile moves rightward each frame.

fn_update_missile ($6A4E):
    Increments missile x position by MISSILE_SPEED.
    Reads video RAM at new position; if non-blank char found, it's a hit.
    On reaching right edge of screen, deactivates missile.

fn_drop_bomb ($6B98):
    Drops a bomb from beneath the ship if none is active.
    Bomb falls downward at BOMB_SPEED px/frame.

fn_update_bomb ($6C59):
    Increments bomb y position.
    Reads video RAM at new position; if non-blank found, it's a hit.
    On reaching bottom of screen, deactivates bomb.

fn_missile_hit_test ($6AC5) and fn_bomb_hit_test ($6C88):
    Both check the video RAM char at the projectile's position.
    If non-blank, the projectile has hit something.
    The specific char code determines what was hit (enemy? terrain? target?).

Key constraint from the original
---------------------------------
Only ONE missile and ONE bomb can be active at a time (single-shot system).
This is clear from the single active-flag approach and is a defining
characteristic of the game feel.
"""

from dataclasses import dataclass, field

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    MISSILE_SPEED_PX, MISSILE_CHAR,
    BOMB_SPEED_PX, BOMB_CHAR,
)
from trs80_screen import TRS80Screen


@dataclass
class Missile:
    """
    The player's forward-firing missile.

    The Z80 stores missile state in:
        missile_col    ($6BC0) - screen column
        missile_row    ($6BC1) - screen row
        missile_active ($6BC2) - non-zero if in flight

    We track position in logical pixels for sub-cell accuracy.
    """

    pixel_x: float = 0.0
    pixel_y: float = 0.0
    active:  bool  = False

    def fire(self, ship_nose_x: int, ship_nose_y: int) -> None:
        """
        Launch the missile from the ship's nose position.
        Mirrors fn_fire_missile ($6A16) which positions the missile
        at the rightmost edge of the ship sprite.
        Only fires if no missile is currently active.
        """
        if self.active:
            return   # single-shot: must wait for current missile to expire
        self.pixel_x = float(ship_nose_x)
        self.pixel_y = float(ship_nose_y)
        self.active  = True

    def erase(self, screen: TRS80Screen) -> None:
        """Erase missile from screen."""
        if not self.active:
            return
        screen.write_char(self.char_col, self.char_row, 0x20)

    def update(self, screen: TRS80Screen) -> bool:
        """
        Move the missile right and check for collision.
        Mirrors fn_update_missile ($6A4E).

        Returns True if the missile hit something (collision detected),
        False if still in flight or just deactivated on screen edge.
        """
        if not self.active:
            return False

        # Erase at current position before moving
        self.erase(screen)

        # Move right
        self.pixel_x += MISSILE_SPEED_PX

        # Deactivate if off-screen right edge
        if self.pixel_x >= PIXELS_WIDE:
            self.active = False
            return False

        # Collision check: read video RAM at new position
        char = screen.read_char(self.char_col, self.char_row)
        if char != 0x20 and char != 0x80:
            # Hit something - erase the cell and deactivate
            screen.write_char(self.char_col, self.char_row, 0x20)
            self.active = False
            return True   # HIT

        # No hit: draw missile at new position
        screen.write_char(self.char_col, self.char_row, MISSILE_CHAR)
        return False

    def deactivate(self) -> None:
        """Deactivate missile without collision (e.g. player died)."""
        self.active = False

    @property
    def char_col(self) -> int:
        return int(self.pixel_x) // 2

    @property
    def char_row(self) -> int:
        return int(self.pixel_y) // 3

    @property
    def pixel_xi(self) -> int:
        return int(self.pixel_x)

    @property
    def pixel_yi(self) -> int:
        return int(self.pixel_y)


@dataclass
class Bomb:
    """
    The player's downward-falling bomb.

    The Z80 stores bomb state in:
        bomb_col    ($6A80) - screen column
        bomb_row    ($6A81) - screen row
        bomb_active ($6A82) - non-zero if falling

    One bomb active at a time (fn_drop_bomb returns immediately if active).
    """

    pixel_x: float = 0.0
    pixel_y: float = 0.0
    active:  bool  = False

    def drop(self, ship_pixel_x: int, ship_pixel_y: int,
             ship_width_chars: int) -> None:
        """
        Drop a bomb from beneath the ship's centre.
        Mirrors fn_drop_bomb ($6B98).
        """
        if self.active:
            return  # single bomb at a time
        # Position bomb at the bottom-centre of the ship
        self.pixel_x = float(ship_pixel_x + ship_width_chars)
        self.pixel_y = float(ship_pixel_y + 6)   # below the ship (2 rows × 3px)
        self.active  = True

    def erase(self, screen: TRS80Screen) -> None:
        """Erase bomb from screen."""
        if not self.active:
            return
        screen.write_char(self.char_col, self.char_row, 0x20)

    def update(self, screen: TRS80Screen) -> bool:
        """
        Move the bomb downward and check for collision.
        Mirrors fn_update_bomb ($6C59).

        Returns True if the bomb hit something.
        """
        if not self.active:
            return False

        self.erase(screen)

        # Move down
        self.pixel_y += BOMB_SPEED_PX

        # Deactivate if off-screen bottom
        if self.pixel_y >= PIXELS_TALL:
            self.active = False
            return False

        # Collision check at new position
        char = screen.read_char(self.char_col, self.char_row)
        if char != 0x20 and char != 0x80:
            screen.write_char(self.char_col, self.char_row, 0x20)
            self.active = False
            return True   # HIT

        # Draw bomb at new position
        screen.write_char(self.char_col, self.char_row, BOMB_CHAR)
        return False

    def deactivate(self) -> None:
        """Deactivate bomb without collision."""
        self.active = False

    @property
    def char_col(self) -> int:
        return int(self.pixel_x) // 2

    @property
    def char_row(self) -> int:
        return int(self.pixel_y) // 3

    @property
    def pixel_xi(self) -> int:
        return int(self.pixel_x)

    @property
    def pixel_yi(self) -> int:
        return int(self.pixel_y)
