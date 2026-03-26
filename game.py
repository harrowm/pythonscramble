"""game.py - Main game state machine.

Original Z80 game loop (fn_main_game_loop $61AD):
    fn_loop_top:
        SCROLL terrain (every frame)
        Every 5th frame only:
            READ keyboard
            MOVE ship (4-directional, no gravity) → fn_update_ship_pos ($6926)
            CHECK ship collision                  → fn_redraw_ship ($69A4)
            UPDATE cannon shot                    → fn_update_cannon_shot ($66E9)
            UPDATE all encounters                 → fn_update_all_encounters ($6C46)
            UPDATE all enemies                    → fn_update_all_enemies ($6829)
        UPDATE HUD
        JP fn_loop_top
"""

import sdl2
from enum import Enum, auto

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL,
    TARGET_FPS, FRAME_TIME_MS,
    SCROLL_SPEEDS, DEFAULT_SCROLL_PHASE,
    SHIP_WIDTH_CHARS, SHIP_HEIGHT_CHARS,
    STARTING_FUEL,
    ZONE_NAMES,
    INSTR_SCREEN_DATA, INSTR_TEXT_ROWS,
)
from trs80_screen import TRS80Screen
from terrain     import Terrain
from ship        import Ship
from projectiles import Missile
from enemies     import EnemyManager
from explosions  import ExplosionManager
from hud         import HUD
from input       import InputHandler, InputState


class GameState(Enum):
    TITLE        = auto()
    INSTRUCTIONS = auto()
    ZONE_INTRO   = auto()
    PLAYING      = auto()
    PLAYER_DEAD  = auto()
    GAME_OVER    = auto()


class Game:
    """
    Top-level game object.  Owns all subsystems and drives the per-frame
    update loop.  Mirrors the overall structure of the Z80 main loop.
    """

    # How many frames to stay in each transitional state
    DEATH_PAUSE_FRAMES    = 60    # ~2 seconds at 30fps
    ZONE_INTRO_FRAMES     = 45    # ~1.5 seconds
    GAME_OVER_FRAMES      = 180   # ~6 seconds
    BONUS_MSG_FRAMES      = 60    # frames to show bonus life message

    def __init__(self) -> None:
        self.screen    = TRS80Screen()
        self.terrain   = Terrain()
        self.ship      = Ship()
        self.missile   = Missile()
        self.enemies   = EnemyManager()
        self.explosions = ExplosionManager()
        self.hud       = HUD()
        self.input     = InputHandler()

        self._state:          GameState = GameState.TITLE
        self._state_timer:    int       = 0
        self._scroll_phase:   int       = DEFAULT_SCROLL_PHASE
        self._bonus_msg_timer: int      = 0
        self._fire_cooldown:  int       = 0   # frames until next shot allowed
        self._instr_phase:    int       = 0   # 0 = bonus-text overlay, 1 = score table
        self._instr_scroll:   int       = 0   # left-scroll offset for panorama

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update(self, input_state: InputState) -> bool:
        """
        Advance the game by one frame.
        Returns False if the player requested quit (abort on title/game-over).
        Mirrors the top-level dispatch of the Z80 game loop.
        """
        self._state_timer += 1

        if self._state == GameState.TITLE:
            return self._update_title(input_state)
        elif self._state == GameState.INSTRUCTIONS:
            return self._update_instructions(input_state)
        elif self._state == GameState.ZONE_INTRO:
            return self._update_zone_intro()
        elif self._state == GameState.PLAYING:
            return self._update_playing(input_state)
        elif self._state == GameState.PLAYER_DEAD:
            return self._update_player_dead(input_state)
        elif self._state == GameState.GAME_OVER:
            return self._update_game_over(input_state)
        return True

    def render(self) -> None:
        """
        Draw the current frame to the TRS-80 screen buffer.
        Rendering is separated from update so we can call render()
        independently at the display refresh rate if desired.
        """
        # The screen content is written incrementally by each subsystem
        # during update().  We just need to ensure the HUD is fresh.
        if self._state in (GameState.PLAYING, GameState.PLAYER_DEAD):
            self.hud.draw(self.screen)
            if self._bonus_msg_timer > 0:
                self.hud.draw_bonus_message(self.screen)

    # ------------------------------------------------------------------
    # State handlers
    # ------------------------------------------------------------------

    def _update_title(self, inp: InputState) -> bool:
        """
        Attract / title state.
        Waits for SPACE (start) or I (instructions).
        In the original (.title_loop at $60F3) the title screen is always
        visible; pressing I overlays the bonus-life text WITHOUT clearing
        the screen.
        """
        if inp.abort:
            return False   # quit

        if self._state_timer == 1:
            self._draw_title_screen()

        if inp.instructions and self._state_timer > 10:
            self._instr_phase = 1
            self._instr_scroll = 0
            self._transition(GameState.INSTRUCTIONS)
            self._draw_score_table()

        if inp.start and self._state_timer > 10:
            self._start_game()

        return True

    def _update_instructions(self, inp: InputState) -> bool:
        """
        Instructions state — two phases matching the original:

        Phase 0  (fn_show_bonus_life_text / .wait_for_space at $6118):
            Title screen stays fully visible; "* BONUS LIFE ... *" is
            overlaid at row 4 col 14.  SPACE → start game.  Any other
            key → phase 1.

        Phase 1  (.instr_show at $6135 in the original):
            Scrolling score table.  We show a static rendition.
            Any key → back to title.
        """
        if self._instr_phase == 0:
            if inp.start and self._state_timer > 10:
                self._start_game()
                return True
            # Any key other than I (which we already handled) advances
            # to the score-table phase.
            any_key = (
                inp.abort or inp.move_up or inp.move_down
                or inp.move_left or inp.move_right or inp.fire
            )
            if any_key and self._state_timer > 10:
                self._instr_phase = 1
                self._instr_scroll = 0
                self._state_timer = 0
                self._draw_score_table()
        else:
            # Phase 1: score table on screen; any key returns to title.
            self._instr_scroll += 1
            self._draw_score_table()
            any_key = (
                inp.abort or inp.start or inp.instructions
                or inp.move_up or inp.move_down
                or inp.move_left or inp.move_right or inp.fire
            )
            if any_key and self._state_timer > 10:
                self._transition(GameState.TITLE)
                self._draw_title_screen()

        return True

    def _update_zone_intro(self) -> bool:
        """
        Brief zone-name display before gameplay begins.
        Mirrors the delay loops at $627B–$628A (6× ROM_DELAY).
        """
        if self._state_timer == 1:
            self._draw_zone_intro()
        if self._state_timer >= self.ZONE_INTRO_FRAMES:
            self._enter_playing()
        return True

    def _update_playing(self, inp: InputState) -> bool:
        """
        Main gameplay update.  This is the heart of the game.
        Mirrors fn_main_game_loop ($61AD): terrain scrolls every frame;
        ship/cannon/enemies only update every 5th frame in the original.
        For simplicity we update all subsystems every frame here.
            1. Scroll terrain             → terrain.scroll() + draw_to_screen()
            2. Move ship                  → ship.update() / fn_update_ship_pos
            3. Check ship collision       → ship.check_terrain_collision()
            4. Draw ship                  → ship.draw()
            5. Fire / update cannon       → missile.fire() + missile.update()
            6. Update enemies             → enemies.update() / fn_update_all_enemies
            7. Update explosions
            8. Consume fuel               → hud.consume_fuel()
        """
        if inp.abort:
            self._transition(GameState.GAME_OVER)
            return True

        # --- 1. Scroll terrain one column left ---
        # fn_scroll_screen ($64CA) scrolls at speed determined by scroll_phase.
        # We perform the scroll, then redraw terrain to the screen buffer.
        self.terrain.scroll()
        self.terrain.draw_to_screen(self.screen)

        # --- 2. Move ship ---
        # fn_update_ship_pos ($6926): 4-directional, no gravity.
        self.ship.update(inp.move_up, inp.move_down, inp.move_right, inp.move_left)

        # --- 3. Check ship collision ---
        # fn_redraw_ship ($69A4) does pixel-level collision detection.
        # fn_check_ship_crash ($65CA) processes the death event.
        # We check BEFORE drawing the ship so we detect terrain/enemy chars.
        if self.ship.check_terrain_collision(self.screen):
            self._kill_player()
            return True
        if self.ship.check_screen_boundary():
            self._kill_player()
            return True

        # --- 4. Erase ship from previous frame, draw at new position ---
        self.ship.erase(self.screen)
        self.ship.draw(self.screen)

        # --- 5. Fire cannon ---
        # fn_fire_cannon ($66B0): single shot, spawns at ship_x+6, ship_y+3.
        if inp.fire and self._fire_cooldown == 0:
            self.missile.fire(int(self.ship.pixel_x), int(self.ship.pixel_y))
            self._fire_cooldown = 6   # brief cooldown so key-hold doesn't spam
        if self._fire_cooldown > 0:
            self._fire_cooldown -= 1

        # Update cannon shot position and check for hit
        missile_hit = self.missile.update(self.screen)
        if missile_hit:
            hit_enemy = self.enemies.check_missile_hit(
                self.missile.char_col, self.missile.char_row
            )
            if hit_enemy:
                self._destroy_enemy(hit_enemy)

        # --- 6. Update enemies ---
        # fn_update_all_enemies ($6829)
        self.enemies.update(self.screen)

        # Check if any enemy has flown into the ship
        if self.enemies.check_ship_collision(
            self.ship.char_col, self.ship.char_row,
            SHIP_WIDTH_CHARS, SHIP_HEIGHT_CHARS
        ):
            self._kill_player()
            return True

        # --- 7. Update explosions ---
        self.explosions.update(self.screen)

        # --- 8. Consume fuel ---
        # fn_consume_fuel ($6D46): fuel decrements each frame.
        if self.hud.consume_fuel():
            self._kill_player()   # out of fuel → death
            return True

        # --- 9. Tick bonus message display ---
        if self._bonus_msg_timer > 0:
            self._bonus_msg_timer -= 1

        return True

    def _update_player_dead(self, inp: InputState) -> bool:
        """
        Post-death pause.
        Mirrors the delay and state reset in fn_player_death ($6E15).
        Shows explosion animation, then either respawns or game-overs.
        """
        self.explosions.update(self.screen)

        if self._state_timer >= self.DEATH_PAUSE_FRAMES:
            if self.hud.lives <= 0:
                self._transition(GameState.GAME_OVER)
            else:
                # Respawn: reset ship position, keep score
                self._respawn_player()
        return True

    def _update_game_over(self, inp: InputState) -> bool:
        """
        Game over state.
        Mirrors fn_game_over ($6E25).
        """
        if self._state_timer == 1:
            self._draw_game_over_screen()

        if inp.start and self._state_timer > 30:
            self._transition(GameState.TITLE)
            self._state_timer = 0
            self.screen.clear()
            self._draw_title_screen()

        if inp.abort:
            return False

        return True

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _start_game(self) -> None:
        """
        Begin a new game.
        Mirrors fn_init_game_state ($6390) and the zone-init sequence.
        """
        self.hud.reset()
        self.terrain = Terrain()   # fresh terrain starting from zone 0
        self.ship.reset()
        self.missile.deactivate()
        self.enemies.set_zone(0)
        self.enemies.clear_all()
        self.explosions.clear_all()
        self.screen.clear()
        self._transition(GameState.ZONE_INTRO)

    def _enter_playing(self) -> None:
        """Begin active gameplay in the current zone."""
        self.screen.clear()
        self.terrain.draw_to_screen(self.screen)
        self.ship.reset()
        self._fire_cooldown = 0
        self._transition(GameState.PLAYING)

    def _kill_player(self) -> None:
        """
        Handle player death.
        Mirrors fn_player_death ($6E15).
        """
        # Spawn explosion at ship position
        self.explosions.spawn(self.ship.char_col + 2, self.ship.char_row)

        # Erase ship from screen
        self.ship.erase(self.screen)
        self.ship.alive = False

        # Deactivate all projectiles
        self.missile.deactivate()

        # Lose a life
        self.hud.lose_life()

        self._transition(GameState.PLAYER_DEAD)

    def _respawn_player(self) -> None:
        """Respawn the player at the start of the current zone."""
        self.enemies.clear_all()
        self.explosions.clear_all()
        self.screen.clear()
        self.terrain.draw_to_screen(self.screen)
        self.ship.reset()
        self.ship.alive = True
        # Restore some fuel on respawn
        self.hud.fuel = STARTING_FUEL
        self._transition(GameState.PLAYING)

    def _destroy_enemy(self, enemy) -> None:
        """Destroy a hit enemy: explosion + score."""
        self.explosions.spawn(enemy.char_col + 1, enemy.char_row)
        score_pts = enemy.score_value
        self.enemies.destroy_enemy(enemy, self.screen)
        bonus_awarded = self.hud.add_score(score_pts)
        if bonus_awarded:
            self._bonus_msg_timer = self.BONUS_MSG_FRAMES

    def _transition(self, new_state: GameState) -> None:
        self._state       = new_state
        self._state_timer = 0

    # ------------------------------------------------------------------
    # Screen drawing helpers
    # ------------------------------------------------------------------

    def _overlay_bonus_life_text(self) -> None:
        """
        Overlay "* BONUS LIFE FOR EVERY 10000 SCORED *" on the CURRENT screen.
        Mirrors fn_show_bonus_life_text ($6210):
            LDIR str_bonus_life ($621F, 37 bytes) → splash back-buffer at $550E.
            $550E - $5400 = $10E = 270 bytes into VRAM → row 4, col 14.
        Title screen remains fully visible as background.
        """
        bonus = "* BONUS LIFE FOR EVERY 10000 SCORED *"
        # $550E offset = 270 bytes = row 4 (4*64=256), col 14 (270-256=14)
        self.screen.write_string(14, 4, bonus)

    def _draw_score_table(self) -> None:
        """Draw the instructions screen using actual ROM data.

        Matches the original Z80 layout:
          Rows 0-4:  five instruction text lines from INSTR_TEXT_ROWS
          Row  4:    * BONUS LIFE * overlay (written on top of row 4 text)
          Rows 5-12: 8 rows of scrolling semigraphic panorama (INSTR_SCREEN_DATA)
          Rows 13-15: blank (0x80)
        The panorama scrolls left by 1 column per frame, wrapping every 64 cols.
        """
        self.screen.fill_rect(0, 0, SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL, 0x80)

        # Rows 0-4: instruction text (verbatim from Z80 $5D40-$5E7F)
        for row_idx, line in enumerate(INSTR_TEXT_ROWS):
            self.screen.write_string(0, row_idx, line[:SCREEN_CHARS_WIDE])

        # Row 4: bonus life overlay (matches fn_show_bonus_life_text)
        self._overlay_bonus_life_text()

        # Rows 5-12: scrolling semigraphic enemy/score panorama
        off = self._instr_scroll % 64
        for prow in range(8):
            for col in range(SCREEN_CHARS_WIDE):
                src = prow * 64 + (col + off) % 64
                self.screen.write_char(col, 5 + prow, INSTR_SCREEN_DATA[src])

    def _draw_instructions_screen(self) -> None:
        """Legacy wrapper — calls _draw_score_table for backward compat."""
        self._draw_score_table()

    def _draw_title_screen(self) -> None:
        """Draw the title/attract screen matching the original TRS-80 layout.

        Draw order matters: draw_text_big() uses set_pixel() which ORs into
        semigraphic cells, so it must run BEFORE write_string() calls that
        place ASCII characters in the same area (row 0 / rows 13-15).

        Proportions: x_scale=1, y_scale=2 reproduces the original TRS-80's
        non-square logical pixels (4px wide × 8px tall on the CRT phosphor).
        Each big glyph is 6×14 logical pixels; three bands fit in rows 1-13.
        """
        self.screen.clear()

        # --- large pixel-art title (drawn FIRST to avoid overwriting ASCII) ---
        # x_scale=1, y_scale=2 → each glyph step = 6+1 = 7 logical px wide,
        # 14 logical px tall.  Left-align at x=2 (matches original screen dump).
        # y bands: 4-17 (Arcade), 18-31 (Bomber), 32-45 (SCRAMBLE).
        self.screen.draw_text_big(2,  4, "Arcade",   x_scale=1, y_scale=2)
        self.screen.draw_text_big(2, 18, "Bomber",   x_scale=1, y_scale=2)
        self.screen.draw_text_big(2, 32, "SCRAMBLE", x_scale=1, y_scale=2)

        # --- header row (char row 0, y=0-2) — written AFTER big text ---
        self.screen.write_string(0, 0, "KANSAS SOFTWARE ***")

        # --- TOP FIVE box (top-right corner, rows 0-4) ---
        box_col = 44
        box_w   = 20
        self.screen.write_string(box_col + 4, 0, "* TOP FIVE *")
        for c in range(box_col, box_col + box_w):
            self.screen.write_char(c, 1, 0xBF)
            self.screen.write_char(c, 4, 0xBF)
        for r in range(1, 5):
            self.screen.write_char(box_col,             r, 0xBF)
            self.screen.write_char(box_col + box_w - 1, r, 0xBF)
        hi_val = self.hud.hi_score if self.hud.hi_score > 0 else 0
        hi_str = f"{hi_val:06d}"
        hi_col = box_col + (box_w - len(hi_str)) // 2
        self.screen.write_string(hi_col, 2, hi_str)
        self.screen.write_string(hi_col, 3, hi_str)

        # --- bottom text (char rows 13-15) — written AFTER big text ---
        inst = "PRESS (I) FOR INSTRUCTIONS OR (SPACE) TO START"
        col = (SCREEN_CHARS_WIDE - len(inst)) // 2
        self.screen.write_string(max(0, col), 13, inst)

        copy_str = "(C) 1981 - MIKE CHALK & CHRIS SMYTH"
        col = (SCREEN_CHARS_WIDE - len(copy_str)) // 2
        self.screen.write_string(max(0, col), 15, copy_str)

    def _draw_zone_intro(self) -> None:
        """Display zone name before gameplay."""
        self.screen.clear()
        zone_name = ZONE_NAMES[min(self.terrain.zone_index, len(ZONE_NAMES) - 1)]
        msg = f"ZONE  {zone_name}"
        col = (SCREEN_CHARS_WIDE - len(msg)) // 2
        self.screen.write_string(col, 7, msg)

    def _draw_game_over_screen(self) -> None:
        """Display game over message."""
        self.screen.clear()
        msg = "GAME  OVER"
        col = (SCREEN_CHARS_WIDE - len(msg)) // 2
        self.screen.write_string(col, 6, msg)

        score_msg = f"SCORE  {self.hud.score:06d}"
        col = (SCREEN_CHARS_WIDE - len(score_msg)) // 2
        self.screen.write_string(col, 8, score_msg)

        if self.hud.score >= self.hud.hi_score and self.hud.score > 0:
            new_hi = "NEW  HI-SCORE!"
            col = (SCREEN_CHARS_WIDE - len(new_hi)) // 2
            self.screen.write_string(col, 10, new_hi)

        restart = "PRESS SPACE TO RESTART"
        col = (SCREEN_CHARS_WIDE - len(restart)) // 2
        self.screen.write_string(col, 13, restart)
