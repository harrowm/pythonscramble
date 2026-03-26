"""
terrain.py - Scrolling terrain system for Scramble.

How the original works
----------------------
Each zone has a screen layout stored as semigraphic chars at $5E00–$61FF.
These chars are copied into video RAM ($3C00–$3FFF) by fn_copy_terrain
($6300) which uses an LDIR block move.  The terrain is then scrolled left
each frame by fn_scroll_screen ($64CA), which shifts all 16 rows of video
RAM one column left using successive LDIR instructions.  New terrain column
data is read from the zone's terrain height table and written into the
rightmost column.

fn_draw_terrain ($6495) implements the height→char conversion:
    FOR each col in video RAM row 0:
        char = READ(addr)
        IF char >= $80:
            depth = char - $80
            WRITE(addr, $BF - depth)   ; convert stored height to solid block

The ceiling height (top terrain) and floor height (bottom terrain) are both
stored as semigraphic chars.  A char of $80 = 0 rows of terrain (open sky),
$BF = 63 rows (entire column blocked, which would crash the ship).

We replicate this with Python arrays of ceiling_height and floor_height
values (in logical pixel rows, 0–47).  Each frame the terrain scrolls one
column left and the rightmost column is populated from the zone definition.
"""

import random
from dataclasses import dataclass, field
from typing import Optional

from constants import (
    SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL,
    PIXELS_WIDE, PIXELS_TALL,
    TERRAIN_COLS,
    ZONE_NAMES,
)
from trs80_screen import TRS80Screen


# ---------------------------------------------------------------------------
# Zone terrain definitions
# ---------------------------------------------------------------------------
# Each zone defines how the ceiling and floor heights vary as the player
# flies through it.  Heights are in logical pixel rows (0 = flush with
# top/bottom edge, positive values = terrain extends inward).
#
# These are reconstructed from the screen layout data in sectors 2–3 of
# the disk image.  The original stores pre-rendered screen tiles; we
# re-derive the underlying height data that produced those tiles.

@dataclass
class ZoneDefinition:
    """Terrain parameters for one zone."""
    name:            str
    # (min, max) ceiling height in logical pixels (0 = no ceiling)
    ceiling_range:   tuple[int, int]
    # (min, max) floor height in logical pixels (0 = no floor)
    floor_range:     tuple[int, int]
    # Column width before transitioning to the next zone
    zone_width_cols: int
    # Whether the terrain undulates (True) or is flat (False)
    undulating:      bool
    # Obstacles in this zone: list of (relative_col, row_from_top) char positions
    # None means procedurally generated from the height tables
    obstacles:       Optional[list] = None


# Zone definitions derived from the disk image screen data.
# Heights are in logical pixel rows (out of 48 total).
# The playable corridor is PIXELS_TALL (48) minus ceiling and floor heights.
ZONE_DEFINITIONS = [
    ZoneDefinition(
        name="FIGHTERS",
        ceiling_range=(3, 9),
        floor_range=(3, 9),
        zone_width_cols=96,
        undulating=True,
    ),
    ZoneDefinition(
        name="BLIMPS",
        ceiling_range=(3, 12),
        floor_range=(3, 9),
        zone_width_cols=96,
        undulating=True,
    ),
    ZoneDefinition(
        name="BOMBERS",
        ceiling_range=(6, 12),
        floor_range=(3, 9),
        zone_width_cols=96,
        undulating=False,
    ),
    ZoneDefinition(
        name="FORT",
        ceiling_range=(3, 9),
        floor_range=(6, 15),
        zone_width_cols=128,
        undulating=True,
    ),
    ZoneDefinition(
        name="FACTORY",
        ceiling_range=(6, 12),
        floor_range=(9, 18),
        zone_width_cols=128,
        undulating=False,
    ),
    ZoneDefinition(
        name="ROCKETS",
        ceiling_range=(3, 9),
        floor_range=(3, 9),
        zone_width_cols=96,
        undulating=True,
    ),
    ZoneDefinition(
        name="FUEL TANKS",
        ceiling_range=(3, 9),
        floor_range=(6, 12),
        zone_width_cols=128,
        undulating=False,
    ),
    ZoneDefinition(
        name="ARSENAL",
        ceiling_range=(6, 15),
        floor_range=(6, 15),
        zone_width_cols=160,
        undulating=True,
    ),
]


# ---------------------------------------------------------------------------
# Semigraphic char encoding helpers
# ---------------------------------------------------------------------------
# The original fn_draw_terrain ($6495) converts height to char via:
#   char = $BF - depth  where depth = (stored_char - $80)
# We replicate this logic to produce the correct block characters for the
# terrain walls.

def height_to_chars(
    height_px: int, from_top: bool
) -> list[int]:
    """
    Convert a terrain height in logical pixels to a list of character codes
    to write into the appropriate character rows.

    from_top=True  → ceiling (chars fill from row 0 downward)
    from_top=False → floor   (chars fill from row 15 upward)

    Each char row is 3 logical pixels tall.  A height of 6px = 2 full rows.
    The partial row at the boundary uses a partial semigraphic char.

    Returns a list of (char_code, row_index) pairs for all affected rows.
    """
    cells = []
    full_rows = height_px // 3
    remainder_px = height_px % 3

    if from_top:
        # Full solid rows at the top
        for r in range(full_rows):
            cells.append((0xBF, r))   # $BF = full 2×3 block
        # Partial row
        if remainder_px > 0:
            # Build char: fill the top `remainder_px` pixel rows of the cell
            bits = 0
            for py in range(remainder_px):
                # Both pixels in this row are ON
                for px in range(2):
                    bit_index = (2 - py) * 2 + (1 - px)
                    bits |= (1 << bit_index)
            cells.append((0x80 | bits, full_rows))
    else:
        # Floor: fills from bottom upward
        total_rows = SCREEN_CHARS_TALL
        for r in range(full_rows):
            cells.append((0xBF, total_rows - 1 - r))
        if remainder_px > 0:
            bits = 0
            for py in range(3 - remainder_px, 3):
                for px in range(2):
                    bit_index = (2 - py) * 2 + (1 - px)
                    bits |= (1 << bit_index)
            cells.append((0x80 | bits, total_rows - 1 - full_rows))

    return cells


# ---------------------------------------------------------------------------
# Terrain generator
# ---------------------------------------------------------------------------

class Terrain:
    """
    Generates and manages the scrolling terrain.

    Maintains two ring-buffer arrays:
      ceiling_heights[col] - ceiling height in logical pixels at each column
      floor_heights[col]   - floor height in logical pixels at each column

    Each frame, scroll() shifts the buffer left and generates new right-edge
    column data from the current zone definition.
    """

    def __init__(self) -> None:
        # Current terrain data for one screen's worth of columns plus lookahead
        self.ceiling_heights = [6] * TERRAIN_COLS
        self.floor_heights   = [6] * TERRAIN_COLS
        self._zone_index     = 0
        self._col_in_zone    = 0    # how many columns we have scrolled in this zone
        self._rng            = random.Random(42)  # seeded for reproducibility

        # Smooth terrain by tracking the current height so we don't jump
        self._current_ceiling = 6
        self._current_floor   = 6

        # Initialise the full terrain buffer for the first zone
        self._zone_def = ZONE_DEFINITIONS[0]
        for col in range(TERRAIN_COLS):
            self._generate_column(col)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def zone_index(self) -> int:
        return self._zone_index

    @property
    def zone_name(self) -> str:
        return self._zone_def.name

    def advance_zone(self) -> None:
        """Move to the next zone, wrapping around after the last."""
        self._zone_index = (self._zone_index + 1) % len(ZONE_DEFINITIONS)
        self._zone_def = ZONE_DEFINITIONS[self._zone_index]
        self._col_in_zone = 0

    def scroll(self) -> None:
        """
        Scroll the terrain one character column to the left.
        Matches fn_scroll_screen ($64CA): shifts video RAM left, then
        the terrain system fills the new rightmost column.
        Called once per frame.
        """
        # Shift everything left
        self.ceiling_heights.pop(0)
        self.floor_heights.pop(0)
        # Generate new rightmost column
        self._generate_column(TERRAIN_COLS - 1)
        self._col_in_zone += 1
        # Check if we've completed this zone
        if self._col_in_zone >= self._zone_def.zone_width_cols:
            self.advance_zone()

    def get_ceiling_height(self, col: int) -> int:
        """Return ceiling height (pixels) for the given terrain column."""
        return self.ceiling_heights[min(col, TERRAIN_COLS - 1)]

    def get_floor_height(self, col: int) -> int:
        """Return floor height (pixels) for the given terrain column."""
        return self.floor_heights[min(col, TERRAIN_COLS - 1)]

    def is_in_terrain(self, pixel_x: int, pixel_y: int) -> bool:
        """
        Return True if the given logical pixel is inside terrain (ceiling or floor).
        Used for collision detection, mirroring the Z80 fn_check_ship_crash ($65C2)
        which reads video RAM and tests for non-blank chars.
        """
        # Map pixel_x to terrain column index (accounting for scroll)
        # For simplicity we use the leftmost visible columns
        col = min(pixel_x // 2, TERRAIN_COLS - 1)
        ceiling = self.ceiling_heights[col]
        floor_top = PIXELS_TALL - self.floor_heights[col]
        return pixel_y < ceiling or pixel_y >= floor_top

    def draw_to_screen(self, screen: TRS80Screen) -> None:
        """
        Write the currently visible terrain columns to the TRS-80 screen.
        Replicates fn_draw_terrain ($6495) and fn_copy_terrain ($6300).

        For each of the 64 visible character columns:
          - Write ceiling chars into rows 0..N  (from top)
          - Write floor chars into rows (16-M)..15 (from bottom)
          - Clear the space between them
        """
        for char_col in range(SCREEN_CHARS_WIDE):
            ceiling_px = self.ceiling_heights[char_col]
            floor_px   = self.floor_heights[char_col]

            # Clear the entire column to blank first
            for char_row in range(SCREEN_CHARS_TALL):
                screen.write_char(char_col, char_row, 0x80)

            # Write ceiling
            for char_code, char_row in height_to_chars(ceiling_px, from_top=True):
                screen.write_char(char_col, char_row, char_code)

            # Write floor
            for char_code, char_row in height_to_chars(floor_px, from_top=False):
                screen.write_char(char_col, char_row, char_code)

    # ------------------------------------------------------------------
    # Private terrain generation
    # ------------------------------------------------------------------

    def _generate_column(self, col: int) -> None:
        """
        Generate terrain heights for one new column using the current zone
        definition.  Applies smoothing so height changes are gradual,
        matching the original game's terrain which never changes by more
        than 1 logical pixel per column.
        """
        zone = self._zone_def
        cmin, cmax = zone.ceiling_range
        fmin, fmax = zone.floor_range

        if zone.undulating:
            # Drift the current height by ±1 with random walk, clamped to range
            self._current_ceiling = self._smooth_height(
                self._current_ceiling, cmin, cmax
            )
            self._current_floor = self._smooth_height(
                self._current_floor, fmin, fmax
            )
        else:
            # Flat: stay near the midpoint of the range
            target_c = (cmin + cmax) // 2
            target_f = (fmin + fmax) // 2
            self._current_ceiling = self._approach(self._current_ceiling, target_c)
            self._current_floor   = self._approach(self._current_floor, target_f)

        self.ceiling_heights[col] = self._current_ceiling
        self.floor_heights[col]   = self._current_floor

    def _smooth_height(self, current: int, lo: int, hi: int) -> int:
        """Random-walk the height value, clamped to [lo, hi]."""
        delta = self._rng.choice([-1, 0, 0, 1])
        return max(lo, min(hi, current + delta))

    def _approach(self, current: int, target: int) -> int:
        """Move current one step toward target."""
        if current < target:
            return current + 1
        elif current > target:
            return current - 1
        return current
