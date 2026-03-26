"""
explosions.py - Explosion animation for Scramble.

Original Z80 sources
--------------------
fn_draw_explosion ($6CA8):
    Renders a 3×3 char explosion pattern centred at (col, row).
    The pattern uses semigraphic chars to create a blocky starburst.

fn_update_explosion ($6CE6):
    Decrements the explosion frame counter.  At 0 the explosion cells
    are cleared back to blank ($20).

The original uses 8 animation frames.  Each frame the explosion chars
transition from full dense blocks toward sparse partial blocks, then blank.
This gives a convincing expand-and-fade effect with the block graphics.

We support multiple simultaneous explosions (player death + enemies exploding
at the same time), using a small pool matching the original game's approach.
"""

from dataclasses import dataclass, field
from typing import Optional

from constants import (
    EXPLOSION_FRAMES, EXPLOSION_CHARS,
    SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL,
)
from trs80_screen import TRS80Screen


# Maximum simultaneous explosions (enough for one per enemy + player)
MAX_EXPLOSIONS = 6


@dataclass
class Explosion:
    """One active explosion animation."""
    char_col: int   = 0
    char_row: int   = 0
    frame:    int   = 0     # current frame index (counts up to EXPLOSION_FRAMES)
    active:   bool  = False


class ExplosionManager:
    """
    Manages a pool of simultaneous explosions.
    Mirrors fn_draw_explosion ($6CA8) and fn_update_explosion ($6CE6).
    """

    def __init__(self) -> None:
        self._pool: list[Explosion] = [Explosion() for _ in range(MAX_EXPLOSIONS)]

    def spawn(self, char_col: int, char_row: int) -> None:
        """
        Start a new explosion centred at (char_col, char_row).
        Mirrors the Z80 code which sets the explosion position and resets
        the frame counter to EXPLOSION_FRAMES.
        If the pool is full, the oldest explosion is replaced.
        """
        # Find a free slot, or reuse the most advanced (oldest) one
        slot = next((e for e in self._pool if not e.active), None)
        if slot is None:
            slot = max(self._pool, key=lambda e: e.frame)

        slot.char_col = char_col
        slot.char_row = char_row
        slot.frame    = 0
        slot.active   = True

    def update(self, screen: TRS80Screen) -> None:
        """
        Advance all active explosions by one frame.
        Mirrors fn_update_explosion ($6CE6).

        Each frame:
          1. Erase the previous frame's chars from screen.
          2. Increment frame counter.
          3. If counter < EXPLOSION_FRAMES, draw the new frame's chars.
          4. If counter >= EXPLOSION_FRAMES, deactivate.
        """
        for explosion in self._pool:
            if not explosion.active:
                continue

            # Erase previous frame
            self._erase(screen, explosion)

            explosion.frame += 1

            if explosion.frame >= EXPLOSION_FRAMES:
                explosion.active = False
            else:
                # Draw new frame
                self._draw(screen, explosion)

    def clear_all(self) -> None:
        """Deactivate all explosions (e.g. on player death or zone change)."""
        for exp in self._pool:
            exp.active = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _draw(self, screen: TRS80Screen, explosion: Explosion) -> None:
        """
        Draw the 3×3 explosion pattern for the current frame.
        The pattern is centred at (char_col, char_row), so the 3×3 grid
        spans char_col-1 .. char_col+1 horizontally and char_row-1 ..
        char_row+1 vertically.
        """
        frame_chars = EXPLOSION_CHARS[explosion.frame]
        cx = explosion.char_col - 1
        cy = explosion.char_row - 1

        idx = 0
        for dr in range(3):
            for dc in range(3):
                c = cx + dc
                r = cy + dr
                char = frame_chars[idx]
                idx += 1
                if char == 0x80:
                    continue   # transparent
                if 0 <= c < SCREEN_CHARS_WIDE and 0 <= r < SCREEN_CHARS_TALL:
                    screen.write_char(c, r, char)

    def _erase(self, screen: TRS80Screen, explosion: Explosion) -> None:
        """Clear the 3×3 explosion area back to blanks."""
        cx = explosion.char_col - 1
        cy = explosion.char_row - 1
        for dr in range(3):
            for dc in range(3):
                c = cx + dc
                r = cy + dr
                if 0 <= c < SCREEN_CHARS_WIDE and 0 <= r < SCREEN_CHARS_TALL:
                    # Only clear if the cell still holds explosion chars
                    # (don't clobber terrain or other sprites that drew over us)
                    ch = screen.read_char(c, r)
                    if 0x80 <= ch <= 0xBF:
                        screen.write_char(c, r, 0x20)
