"""
hud.py - Heads-up display for Scramble.

Original Z80 sources
--------------------
fn_draw_status_bar ($6355):
    Draws the HUD into the bottom row (row 15) of the screen.
    Uses ROM_PRINT_AT ($0040) to position text.
    Copies the ship sprite into the status area for the lives counter.

fn_add_score ($6D99):
    BCD arithmetic on score bytes at $6660–$6662.
    Calls ROM_DELAY once after each add (brief pause for flash effect).

fn_check_bonus_life ($6DE8):
    Checks if score has crossed the next 10000 boundary.

fn_draw_fuel_bar ($6E71):
    Uses LD A,R (Z80 refresh register as pseudo-random) to update
    a fluctuating fuel bar display.  The fuel bar is a row of block
    chars; its width represents the current fuel level.

buf_score_display ($634E):
    7-character BCD score display buffer.

HUD layout (64-column screen, row 15):
    Col 0-9:   SCORE label + 6-digit decimal score
    Col 16-19: LIVES label + count
    Col 24-44: FUEL bar (block chars)
    Col 46-55: Zone name
    Col 58-63: Hi-score (last)

We keep a Python score integer and convert to display on each update.
The fuel bar mirrors the original's block-char fill.
"""

from constants import (
    SCREEN_CHARS_WIDE,
    HUD_ROW,
    HUD_SCORE_COL, HUD_LIVES_COL, HUD_FUEL_COL,
    HUD_FUEL_BAR_WIDTH, HUD_ZONE_COL,
    STARTING_LIVES, STARTING_FUEL,
    BONUS_LIFE_SCORE,
    ZONE_NAMES,
)
from trs80_screen import TRS80Screen


class HUD:
    """
    Manages game state (score, lives, fuel) and draws the HUD.
    Mirrors the score/lives/fuel logic of the original Z80 game.
    """

    def __init__(self) -> None:
        self.score:       int = 0
        self.hi_score:    int = 0
        self.lives:       int = STARTING_LIVES
        self.fuel:        int = STARTING_FUEL
        self.zone_index:  int = 0
        self._bonus_threshold: int = BONUS_LIFE_SCORE  # next bonus life target

    def reset(self) -> None:
        """
        Reset all counters for a new game.
        Mirrors fn_init_game_state ($6390).
        """
        self.score    = 0
        self.lives    = STARTING_LIVES
        self.fuel     = STARTING_FUEL
        self._bonus_threshold = BONUS_LIFE_SCORE

    def add_score(self, points: int) -> bool:
        """
        Add points to the score and check for bonus life.
        Mirrors fn_add_score ($6D99) and fn_check_bonus_life ($6DE8).

        Returns True if a bonus life was awarded this call.
        The original uses BCD arithmetic (DAA instruction); we use plain
        integer arithmetic which is equivalent for our purposes.
        """
        self.score += points
        # Update hi-score
        if self.score > self.hi_score:
            self.hi_score = self.score

        # Bonus life check (fn_check_bonus_life $6DE8)
        # "BONUS LIFE FOR EVERY 10000 SCORED" - str at $621F
        if self.score >= self._bonus_threshold:
            self.lives += 1
            self._bonus_threshold += BONUS_LIFE_SCORE
            return True   # bonus life awarded
        return False

    def consume_fuel(self, amount: int = 1) -> bool:
        """
        Decrease fuel.  Returns True if fuel hit zero (ship dies).
        Mirrors fn_consume_fuel ($6D46) and fn_check_fuel_empty ($6D55).
        """
        self.fuel = max(0, self.fuel - amount)
        return self.fuel == 0

    def refuel(self, amount: int) -> None:
        """Refuel the ship (flying over a fuel tank in Zone 6)."""
        self.fuel = min(STARTING_FUEL, self.fuel + amount)

    def lose_life(self) -> bool:
        """
        Decrement lives.  Returns True if game over (no lives left).
        Mirrors fn_player_death ($6E15).
        """
        self.lives -= 1
        return self.lives <= 0

    def set_zone(self, zone_index: int) -> None:
        """Update zone display."""
        self.zone_index = zone_index

    def draw(self, screen: TRS80Screen) -> None:
        """
        Render the entire HUD into row 15 of the screen.
        Mirrors fn_draw_status_bar ($6355).
        """
        row = HUD_ROW

        # Clear the HUD row
        for col in range(SCREEN_CHARS_WIDE):
            screen.write_char(col, row, 0x20)

        # Score: "SCORE 000000"
        score_str = f"SC{self.score:06d}"
        screen.write_string(HUD_SCORE_COL, row, score_str)

        # Lives indicator: filled ship-silhouette chars × lives
        # In the original, the actual ship sprite chars are drawn.
        # We use a solid block char × lives count as a simple approximation.
        lives_str = "LF" + chr(0x20) * max(0, self.lives) # filled chars
        screen.write_string(HUD_LIVES_COL, row, "LF")
        for i in range(min(self.lives, 6)):
            screen.write_char(HUD_LIVES_COL + 2 + i, row, 0xBF)

        # Fuel bar: fn_draw_fuel_bar ($6E71)
        # Width of filled bar = (fuel / STARTING_FUEL) * HUD_FUEL_BAR_WIDTH
        screen.write_string(HUD_FUEL_COL, row, "FL")
        bar_filled = int(
            (self.fuel / max(1, STARTING_FUEL)) * HUD_FUEL_BAR_WIDTH
        )
        bar_col = HUD_FUEL_COL + 2
        for i in range(HUD_FUEL_BAR_WIDTH):
            char = 0xBF if i < bar_filled else 0x80
            screen.write_char(bar_col + i, row, char)

        # Zone name (abbreviated to fit)
        zone_name = ZONE_NAMES[min(self.zone_index, len(ZONE_NAMES) - 1)]
        zone_abbr = zone_name[:8]
        screen.write_string(HUD_ZONE_COL, row, zone_abbr)

    def draw_bonus_message(self, screen: TRS80Screen) -> None:
        """
        Display the "BONUS LIFE" message briefly.
        Mirrors the bonus life announcement text at str_bonus_life ($621F):
        "* BONUS LIFE FOR EVERY 10000 SCORED *"
        We display it centred on row 7 (middle of the play area).
        """
        msg = "* BONUS LIFE *"
        col = (SCREEN_CHARS_WIDE - len(msg)) // 2
        screen.write_string(col, 7, msg)
