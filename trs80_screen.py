"""
trs80_screen.py - Faithful emulation of the TRS-80 128×48 semigraphic display.

The TRS-80 display model
------------------------
The physical screen is 64 character columns × 16 rows.

Characters in the range $80–$BF are *semigraphic* block characters.  Each
character cell encodes a 2×3 grid of 6 pixels.  The 6 bits of (char & $3F)
correspond to the 6 pixels laid out as:

    bit5 | bit4
    bit3 | bit2
    bit1 | bit0

So char $80 = 0b000000 = all 6 pixels OFF (blank cell)
   char $BF = 0b111111 = all 6 pixels ON  (full solid block)
   char $B5 = 0b110101 = a particular partial block

This module provides:
  - set_pixel(x, y)   ← mirrors the Z80 SET(x,y) BASIC command
  - reset_pixel(x, y) ← mirrors RESET(x,y)
  - point(x, y)       ← mirrors POINT(x,y), returns True if pixel is set
  - write_char(col, row, char_code)  ← direct character cell write
  - read_char(col, row)              ← direct character cell read
  - clear()           ← CLS
  - render(renderer)  ← draw the current state to the SDL2 renderer

The render() method draws each logical 2×3-pixel cell as scaled SDL2
rectangles, producing the characteristic chunky block look of the original.
"""

import ctypes
import sdl2

from constants import (
    SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL,
    PIXELS_WIDE, PIXELS_TALL,
    PIXEL_SCALE,
    COLOUR_BACKGROUND, COLOUR_PHOSPHOR, COLOUR_DIM,
)


# ---------------------------------------------------------------------------
# TRS-80 character ROM font  (6 wide × 7 tall)
# ---------------------------------------------------------------------------
# Indexed by (char_code - 0x20).  Covers printable ASCII 0x20–0x7E.
# Each glyph is 7 bytes; each byte is a 6-bit row bitmap where
# bit 5 = leftmost pixel (col 0) and bit 0 = rightmost pixel (col 5).
TRS80_FONT = [
    [0x00,0x00,0x00,0x00,0x00,0x00,0x00],  # 0x20 ' '
    [0x08,0x08,0x08,0x08,0x00,0x08,0x00],  # 0x21 '!'
    [0x14,0x14,0x00,0x00,0x00,0x00,0x00],  # 0x22 '"'
    [0x14,0x3F,0x14,0x14,0x3F,0x14,0x00],  # 0x23 '#'
    [0x08,0x1E,0x28,0x1E,0x05,0x1E,0x08],  # 0x24 '$'
    [0x30,0x31,0x02,0x04,0x08,0x13,0x03],  # 0x25 '%'
    [0x10,0x28,0x10,0x2B,0x25,0x32,0x1D],  # 0x26 '&'
    [0x0C,0x04,0x08,0x00,0x00,0x00,0x00],  # 0x27 "'"
    [0x04,0x08,0x10,0x10,0x10,0x08,0x04],  # 0x28 '('
    [0x10,0x08,0x04,0x04,0x04,0x08,0x10],  # 0x29 ')'
    [0x00,0x08,0x1C,0x08,0x1C,0x08,0x00],  # 0x2A '*'
    [0x00,0x08,0x08,0x3F,0x08,0x08,0x00],  # 0x2B '+'
    [0x00,0x00,0x00,0x00,0x0C,0x08,0x10],  # 0x2C ','
    [0x00,0x00,0x00,0x3F,0x00,0x00,0x00],  # 0x2D '-'
    [0x00,0x00,0x00,0x00,0x00,0x0C,0x00],  # 0x2E '.'
    [0x01,0x02,0x04,0x08,0x10,0x20,0x00],  # 0x2F '/'
    # digits
    [0x1E,0x21,0x23,0x25,0x29,0x31,0x1E],  # 0x30 '0'
    [0x08,0x18,0x08,0x08,0x08,0x08,0x1C],  # 0x31 '1'
    [0x1E,0x21,0x01,0x0E,0x18,0x20,0x3F],  # 0x32 '2'
    [0x1E,0x21,0x01,0x0E,0x01,0x21,0x1E],  # 0x33 '3'
    [0x04,0x0C,0x14,0x24,0x3F,0x04,0x04],  # 0x34 '4'
    [0x3F,0x20,0x3E,0x01,0x01,0x21,0x1E],  # 0x35 '5'
    [0x1E,0x20,0x20,0x3E,0x21,0x21,0x1E],  # 0x36 '6'
    [0x3F,0x01,0x02,0x04,0x08,0x08,0x08],  # 0x37 '7'
    [0x1E,0x21,0x21,0x1E,0x21,0x21,0x1E],  # 0x38 '8'
    [0x1E,0x21,0x21,0x1F,0x01,0x21,0x1E],  # 0x39 '9'
    # punctuation
    [0x00,0x0C,0x0C,0x00,0x0C,0x0C,0x00],  # 0x3A ':'
    [0x00,0x0C,0x0C,0x00,0x0C,0x08,0x10],  # 0x3B ';'
    [0x02,0x04,0x08,0x10,0x08,0x04,0x02],  # 0x3C '<'
    [0x00,0x00,0x3F,0x00,0x3F,0x00,0x00],  # 0x3D '='
    [0x20,0x10,0x08,0x04,0x08,0x10,0x20],  # 0x3E '>'
    [0x1E,0x21,0x01,0x06,0x08,0x00,0x08],  # 0x3F '?'
    [0x1E,0x21,0x27,0x2B,0x2F,0x20,0x1E],  # 0x40 '@'
    # uppercase A-Z
    [0x1E,0x21,0x21,0x3F,0x21,0x21,0x21],  # 0x41 'A'
    [0x3E,0x21,0x21,0x3E,0x21,0x21,0x3E],  # 0x42 'B'
    [0x1E,0x21,0x20,0x20,0x20,0x21,0x1E],  # 0x43 'C'
    [0x3C,0x22,0x21,0x21,0x21,0x22,0x3C],  # 0x44 'D'
    [0x3F,0x20,0x20,0x3E,0x20,0x20,0x3F],  # 0x45 'E'
    [0x3F,0x20,0x20,0x3E,0x20,0x20,0x20],  # 0x46 'F'
    [0x1E,0x21,0x20,0x27,0x21,0x21,0x1E],  # 0x47 'G'
    [0x21,0x21,0x21,0x3F,0x21,0x21,0x21],  # 0x48 'H'
    [0x1C,0x08,0x08,0x08,0x08,0x08,0x1C],  # 0x49 'I'
    [0x07,0x02,0x02,0x02,0x02,0x22,0x1C],  # 0x4A 'J'
    [0x22,0x24,0x28,0x30,0x28,0x24,0x22],  # 0x4B 'K'
    [0x20,0x20,0x20,0x20,0x20,0x20,0x3F],  # 0x4C 'L'
    [0x21,0x33,0x2D,0x21,0x21,0x21,0x21],  # 0x4D 'M'
    [0x21,0x31,0x29,0x25,0x23,0x21,0x21],  # 0x4E 'N'
    [0x1E,0x21,0x21,0x21,0x21,0x21,0x1E],  # 0x4F 'O'
    [0x3E,0x21,0x21,0x3E,0x20,0x20,0x20],  # 0x50 'P'
    [0x1E,0x21,0x21,0x21,0x25,0x22,0x1D],  # 0x51 'Q'
    [0x3E,0x21,0x21,0x3E,0x28,0x24,0x22],  # 0x52 'R'
    [0x1E,0x21,0x20,0x1E,0x01,0x21,0x1E],  # 0x53 'S'
    [0x3F,0x08,0x08,0x08,0x08,0x08,0x08],  # 0x54 'T'
    [0x21,0x21,0x21,0x21,0x21,0x21,0x1E],  # 0x55 'U'
    [0x21,0x21,0x21,0x12,0x12,0x0C,0x0C],  # 0x56 'V'
    [0x21,0x21,0x21,0x2D,0x2D,0x33,0x21],  # 0x57 'W'
    [0x21,0x12,0x0C,0x08,0x0C,0x12,0x21],  # 0x58 'X'
    [0x21,0x12,0x0C,0x08,0x08,0x08,0x08],  # 0x59 'Y'
    [0x3F,0x01,0x02,0x04,0x08,0x10,0x3F],  # 0x5A 'Z'
    [0x1C,0x10,0x10,0x10,0x10,0x10,0x1C],  # 0x5B '['
    [0x20,0x10,0x08,0x04,0x02,0x01,0x00],  # 0x5C '\'
    [0x0E,0x02,0x02,0x02,0x02,0x02,0x0E],  # 0x5D ']'
    [0x08,0x14,0x22,0x00,0x00,0x00,0x00],  # 0x5E '^'
    [0x00,0x00,0x00,0x00,0x00,0x00,0x3F],  # 0x5F '_'
    [0x10,0x08,0x00,0x00,0x00,0x00,0x00],  # 0x60 '`'
    # lowercase a-z
    [0x00,0x1E,0x01,0x1F,0x21,0x21,0x1F],  # 0x61 'a'
    [0x20,0x20,0x3E,0x21,0x21,0x21,0x3E],  # 0x62 'b'
    [0x00,0x00,0x1E,0x20,0x20,0x20,0x1E],  # 0x63 'c'
    [0x01,0x01,0x1F,0x21,0x21,0x21,0x1F],  # 0x64 'd'
    [0x00,0x1E,0x21,0x3F,0x20,0x21,0x1E],  # 0x65 'e'
    [0x06,0x08,0x1C,0x08,0x08,0x08,0x08],  # 0x66 'f'
    [0x00,0x1F,0x21,0x21,0x1F,0x01,0x1E],  # 0x67 'g'
    [0x20,0x20,0x3E,0x21,0x21,0x21,0x21],  # 0x68 'h'
    [0x08,0x00,0x18,0x08,0x08,0x08,0x1C],  # 0x69 'i'
    [0x02,0x00,0x06,0x02,0x02,0x22,0x1C],  # 0x6A 'j'
    [0x20,0x20,0x24,0x28,0x30,0x28,0x24],  # 0x6B 'k'
    [0x18,0x08,0x08,0x08,0x08,0x08,0x1C],  # 0x6C 'l'
    [0x00,0x00,0x37,0x2A,0x2A,0x2A,0x2A],  # 0x6D 'm'
    [0x00,0x00,0x3E,0x21,0x21,0x21,0x21],  # 0x6E 'n'
    [0x00,0x00,0x1E,0x21,0x21,0x21,0x1E],  # 0x6F 'o'
    [0x00,0x00,0x3E,0x21,0x21,0x3E,0x20],  # 0x70 'p'
    [0x00,0x00,0x1F,0x21,0x21,0x1F,0x01],  # 0x71 'q'
    [0x00,0x00,0x2E,0x30,0x20,0x20,0x20],  # 0x72 'r'
    [0x00,0x00,0x1E,0x20,0x1E,0x01,0x1E],  # 0x73 's'
    [0x08,0x08,0x1C,0x08,0x08,0x09,0x06],  # 0x74 't'
    [0x00,0x00,0x21,0x21,0x21,0x23,0x1D],  # 0x75 'u'
    [0x00,0x00,0x21,0x21,0x12,0x0C,0x0C],  # 0x76 'v'
    [0x00,0x00,0x21,0x2D,0x2D,0x33,0x21],  # 0x77 'w'
    [0x00,0x00,0x21,0x12,0x0C,0x12,0x21],  # 0x78 'x'
    [0x00,0x00,0x21,0x21,0x1F,0x01,0x1E],  # 0x79 'y'
    [0x00,0x00,0x3F,0x02,0x04,0x08,0x3F],  # 0x7A 'z'
    [0x06,0x08,0x08,0x18,0x08,0x08,0x06],  # 0x7B '{'
    [0x08,0x08,0x08,0x08,0x08,0x08,0x08],  # 0x7C '|'
    [0x18,0x04,0x04,0x06,0x04,0x04,0x18],  # 0x7D '}'
    [0x00,0x11,0x2A,0x24,0x00,0x00,0x00],  # 0x7E '~'
]

# ---------------------------------------------------------------------------
# Semigraphic character encoding
# ---------------------------------------------------------------------------
# For a char in range $80–$BF, bits 5–0 of (char & 0x3F) encode 6 pixels:
#
#   pixel column:  0    1
#   pixel row 0:  bit5  bit4
#   pixel row 1:  bit3  bit2
#   pixel row 2:  bit1  bit0
#
# Characters outside $80–$BF are text characters.  We render them as solid
# blocks if they are printable ASCII (the game uses ASCII for HUD text), or
# as blank if they are space ($20).

def _semigraphic_pixel(char_code: int, px: int, py: int) -> bool:
    """
    Return True if the pixel at (px, py) within a semigraphic char cell is ON.
    px in {0, 1}, py in {0, 1, 2}.
    Only valid for char_code in $80–$BF.
    """
    bits = char_code & 0x3F
    # Bit layout:  row0→(bit5, bit4)  row1→(bit3, bit2)  row2→(bit1, bit0)
    bit_index = (2 - py) * 2 + (1 - px)   # maps (px=0,py=0)→bit5, (px=1,py=2)→bit0
    return bool(bits & (1 << bit_index))


class TRS80Screen:
    """
    Emulates the TRS-80 128×48 semigraphic display using an SDL2 renderer.

    Internally stores a 64×16 array of character codes, exactly as the
    original hardware's video RAM ($3C00–$3FFF) was laid out.  The render()
    method converts character codes to pixel rectangles on screen.
    """

    CHAR_PIXEL_W = 2    # each char cell is 2 logical pixels wide
    CHAR_PIXEL_H = 3    # each char cell is 3 logical pixels tall

    # Font glyph metrics (screen pixels)
    _FONT_PX_W   = 2   # screen pixels per font column
    _FONT_PX_H   = 3   # screen pixels per font row
    _FONT_COLS   = 6   # font glyph width  in pixels
    _FONT_ROWS   = 7   # font glyph height in pixels
    # Margins to centre the 12×21 glyph in the 16×24 cell
    _FONT_LEFT   = 2   # (16 - 6*2) // 2
    _FONT_TOP    = 1   # (24 - 7*3) // 2

    def __init__(self) -> None:
        # 64 cols × 16 rows of character codes, matching video RAM layout.
        # Initialised to $80 (blank semigraphic cell), like a cleared screen.
        self._vram: list[list[int]] = [
            [0x80] * SCREEN_CHARS_WIDE for _ in range(SCREEN_CHARS_TALL)
        ]

        # Pre-compute SDL_Rect for every logical pixel position.
        # This avoids creating objects inside the hot render loop.
        self._rects: list[list[sdl2.SDL_Rect]] = [
            [
                sdl2.SDL_Rect(
                    x * PIXEL_SCALE,
                    y * PIXEL_SCALE,
                    PIXEL_SCALE,
                    PIXEL_SCALE,
                )
                for x in range(PIXELS_WIDE)
            ]
            for y in range(PIXELS_TALL)
        ]

        # Reusable rect for font glyph rendering (avoids per-pixel allocation)
        self._font_rect = sdl2.SDL_Rect(0, 0, self._FONT_PX_W, self._FONT_PX_H)

    # ------------------------------------------------------------------
    # Public API - mirrors original TRS-80 BASIC / Z80 ROM interface
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Clear the entire screen to blank ($80 semigraphic char)."""
        for row in self._vram:
            for col in range(SCREEN_CHARS_WIDE):
                row[col] = 0x80

    def set_pixel(self, x: int, y: int) -> None:
        """
        Turn ON the logical pixel at (x, y).
        Mirrors the TRS-80 SET(x, y) BASIC command.
        x in 0..127, y in 0..47.
        """
        if not (0 <= x < PIXELS_WIDE and 0 <= y < PIXELS_TALL):
            return
        col, px, row, py = self._pixel_to_cell(x, y)
        char = self._vram[row][col]
        if not (0x80 <= char <= 0xBF):
            char = 0x80  # treat non-semigraphic as blank before setting
        bits = char & 0x3F
        bit_index = (2 - py) * 2 + (1 - px)
        bits |= (1 << bit_index)
        self._vram[row][col] = 0x80 | bits

    def reset_pixel(self, x: int, y: int) -> None:
        """
        Turn OFF the logical pixel at (x, y).
        Mirrors the TRS-80 RESET(x, y) BASIC command.
        """
        if not (0 <= x < PIXELS_WIDE and 0 <= y < PIXELS_TALL):
            return
        col, px, row, py = self._pixel_to_cell(x, y)
        char = self._vram[row][col]
        if not (0x80 <= char <= 0xBF):
            return  # non-semigraphic, nothing to reset
        bits = char & 0x3F
        bit_index = (2 - py) * 2 + (1 - px)
        bits &= ~(1 << bit_index)
        self._vram[row][col] = 0x80 | bits

    def point(self, x: int, y: int) -> bool:
        """
        Return True if the logical pixel at (x, y) is ON.
        Mirrors the TRS-80 POINT(x, y) BASIC function.
        This is used for collision detection in the original Z80 code:
        the game reads video RAM at the ship / projectile position and
        checks whether any non-blank char is present.
        """
        if not (0 <= x < PIXELS_WIDE and 0 <= y < PIXELS_TALL):
            return False
        col, px, row, py = self._pixel_to_cell(x, y)
        char = self._vram[row][col]
        if not (0x80 <= char <= 0xBF):
            # Non-semigraphic chars (text, space) are treated as solid
            # for collision purposes, matching Z80 behaviour: any char
            # != $20 (space) at ship position triggers death.
            return char != 0x20 and char != 0x80
        return _semigraphic_pixel(char, px, py)

    def write_char(self, col: int, row: int, char_code: int) -> None:
        """
        Write a character code directly to cell (col, row).
        Equivalent to a direct Z80 write to video RAM:
            LD (HL), char_code   ; where HL = $3C00 + row*64 + col
        """
        if 0 <= col < SCREEN_CHARS_WIDE and 0 <= row < SCREEN_CHARS_TALL:
            self._vram[row][col] = char_code & 0xFF

    def read_char(self, col: int, row: int) -> int:
        """
        Read the character code at cell (col, row).
        Equivalent to reading video RAM in Z80.
        Returns $80 (blank) for out-of-bounds.
        """
        if 0 <= col < SCREEN_CHARS_WIDE and 0 <= row < SCREEN_CHARS_TALL:
            return self._vram[row][col]
        return 0x80

    def write_string(self, col: int, row: int, text: str) -> None:
        """
        Write a string of ASCII characters starting at (col, row).
        Used for HUD text: score, lives, zone name.
        """
        for i, ch in enumerate(text):
            c = col + i
            if c >= SCREEN_CHARS_WIDE:
                break
            self.write_char(c, row, ord(ch))

    def fill_rect(self, col: int, row: int,
                  width: int, height: int, char_code: int) -> None:
        """
        Fill a rectangle of character cells with the given char code.
        Used to clear sprite areas or draw solid terrain blocks.
        Matches the Z80 LDIR block-fill idiom used throughout the code.
        """
        for r in range(row, row + height):
            for c in range(col, col + width):
                self.write_char(c, r, char_code)

    def scroll_left(self, cols: int = 1) -> None:
        """
        Scroll the entire screen left by `cols` character columns.
        Mirrors fn_scroll_screen ($64CA) which uses LDIR block moves to
        shift each of the 16 rows left by one character cell, then fills
        the rightmost column with a new terrain character.

        After scrolling, the rightmost column is filled with $80 (blank);
        the caller (terrain system) will write the new column data.
        """
        for row in range(SCREEN_CHARS_TALL):
            self._vram[row] = (
                self._vram[row][cols:]
                + [0x80] * cols
            )

    def is_cell_blank(self, col: int, row: int) -> bool:
        """Return True if the cell contains a blank ($80 or $20) character."""
        ch = self.read_char(col, row)
        return ch == 0x80 or ch == 0x20

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer) -> None:
        """
        Draw the current screen state to the SDL2 renderer.

        Each character cell becomes a 2×3 block of logical pixels.
        Each logical pixel is rendered as a PIXEL_SCALE × PIXEL_SCALE
        rectangle in phosphor green on a near-black background.

        Semigraphic chars ($80–$BF): individual pixels rendered per bit.
        Text chars ($20–$7E):        rendered using TRS-80 bitmap font glyphs.
        Space ($20) / blank ($80):   cell rendered as background colour.
        """
        # Draw background
        sdl2.SDL_SetRenderDrawColor(
            renderer,
            COLOUR_BACKGROUND[0], COLOUR_BACKGROUND[1], COLOUR_BACKGROUND[2],
            255,
        )
        sdl2.SDL_RenderClear(renderer)

        sdl2.SDL_SetRenderDrawColor(
            renderer,
            COLOUR_PHOSPHOR[0], COLOUR_PHOSPHOR[1], COLOUR_PHOSPHOR[2],
            255,
        )

        for row in range(SCREEN_CHARS_TALL):
            for col in range(SCREEN_CHARS_WIDE):
                char = self._vram[row][col]
                # Base pixel position for this cell
                base_x = col * self.CHAR_PIXEL_W
                base_y = row * self.CHAR_PIXEL_H

                if 0x80 <= char <= 0xBF:
                    # Semigraphic: render individual pixels
                    bits = char & 0x3F
                    if bits == 0:
                        continue  # blank cell - background colour already drawn
                    for py in range(3):
                        for px in range(2):
                            bit_index = (2 - py) * 2 + (1 - px)
                            if bits & (1 << bit_index):
                                rect = self._rects[base_y + py][base_x + px]
                                sdl2.SDL_RenderFillRect(renderer, rect)

                elif char == 0x20:
                    # Space character - blank, skip
                    continue

                elif 0x20 < char <= 0x7E:
                    # Printable ASCII: render using TRS-80 bitmap font.
                    glyph_idx = char - 0x20
                    glyph = TRS80_FONT[glyph_idx]
                    cell_x = base_x * PIXEL_SCALE + self._FONT_LEFT
                    cell_y = base_y * PIXEL_SCALE + self._FONT_TOP
                    fr = self._font_rect
                    fr.w = self._FONT_PX_W
                    fr.h = self._FONT_PX_H
                    for fy in range(self._FONT_ROWS):
                        row_bits = glyph[fy]
                        if row_bits == 0:
                            continue
                        for fx in range(self._FONT_COLS):
                            if row_bits & (1 << (5 - fx)):
                                fr.x = cell_x + fx * self._FONT_PX_W
                                fr.y = cell_y + fy * self._FONT_PX_H
                                sdl2.SDL_RenderFillRect(renderer, fr)

                # Other chars (control codes etc.) are treated as blank

    def draw_text_big(self, x: int, y: int, text: str,
                      x_scale: int = 2, y_scale: int = 2) -> None:
        """
        Draw text at logical pixel position (x, y) using scaled font glyphs.
        x_scale=1, y_scale=2 matches the original TRS-80's non-square logical
        pixels (4px wide × 8px tall on the CRT), giving faithful proportions.
        x_scale=2, y_scale=2 gives square pixels (wider letters).
        """
        cx = x
        for ch in text:
            code = ord(ch)
            idx = code - 0x20
            if 0 <= idx < len(TRS80_FONT):
                glyph = TRS80_FONT[idx]
                for fy, row_bits in enumerate(glyph):
                    if row_bits == 0:
                        continue
                    for fx in range(6):
                        if row_bits & (1 << (5 - fx)):
                            for sy in range(y_scale):
                                for sx in range(x_scale):
                                    self.set_pixel(
                                        cx + fx * x_scale + sx,
                                        y  + fy * y_scale + sy,
                                    )
            cx += 6 * x_scale + x_scale  # glyph width + 1-pixel gap

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pixel_to_cell(x: int, y: int) -> tuple[int, int, int, int]:
        """
        Convert logical pixel (x, y) to (col, px, row, py) where:
          col, row  = character cell indices
          px in {0,1}, py in {0,1,2} = pixel offset within the cell

        Relationship to Z80 video RAM:
          col = x // 2
          row = y // 3
          vram_addr = $3C00 + row * 64 + col
        """
        col = x // 2
        px  = x % 2
        row = y // 3
        py  = y % 3
        return col, px, row, py
