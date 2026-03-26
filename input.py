"""
input.py - Keyboard input handler.

Original Z80 sources
--------------------
fn_update_ship_pos ($6926):
    Reads TRS-80 keyboard matrix to generate 4-directional movement deltas:
        $3840 bit 6 (UP key):    B += 2  →  ship_x += 2  (move right/forward)
        $3840 bit 5 (DOWN key):  B -= 2  →  ship_x -= 2  (move left/backward)
        $3840 bit 3 (RIGHT key): C -= 1  →  ship_y -= 1  (move up on screen)
        $3840 bit 4 (LEFT key):  C += 1  →  ship_y += 1  (move down on screen)

    The ship has NO gravity and NO thrust — it holds position when no key
    is pressed.  Horizontal speed = 2 px/frame, vertical = 1 px/frame.

fn_fire_cannon ($66B0):
    Reads $3840 bits 3+4 (or $3804 bits 1+7) to detect the fire button.
    In the original, UP+RIGHT or DOWN+LEFT simultaneously fires.
    We simplify to a single FIRE key.

    Original instruction text ($5E00):
        "<SPACE> TO START   <SHIFT> & <BREAK> TO ABORT GAME"

Python/SDL2 mapping
-------------------
    Arrow UP / W / I   → move ship up    (Z80: ship_y -= 1)
    Arrow DOWN / S / M → move ship down  (Z80: ship_y += 1)
    Arrow RIGHT / D    → move ship right (Z80: ship_x += 2)
    Arrow LEFT / A     → move ship left  (Z80: ship_x -= 2)
    Z / X / Ctrl       → fire cannon
    Enter / Space      → start game
    Escape             → abort / quit
"""

import sdl2


class InputState:
    """
    Snapshot of current keyboard state.

    All fields are booleans: True = key currently held down.
    This mirrors the Z80's approach of testing key-press bits rather
    than acting on key-down events.
    """

    __slots__ = (
        "move_up",
        "move_down",
        "move_right",
        "move_left",
        "fire",
        "start",
        "abort",
    )

    def __init__(self) -> None:
        self.move_up:    bool = False
        self.move_down:  bool = False
        self.move_right: bool = False
        self.move_left:  bool = False
        self.fire:       bool = False
        self.start:      bool = False
        self.abort:      bool = False


class InputHandler:
    """
    Reads SDL2 keyboard state each frame and returns an InputState.

    The TRS-80 game reads the keyboard every frame in a tight polling loop.
    We do the same: call read() once per frame to get the current state.
    """

    def read(self) -> InputState:
        """
        Poll the current SDL2 keyboard state.
        Returns an InputState reflecting all currently held keys.
        Mirrors the per-frame keyboard scan in fn_read_joystick ($6E54).
        """
        state = InputState()
        keys = sdl2.SDL_GetKeyboardState(None)

        # Move up: arrow UP or W or I  (Z80: RIGHT key → ship_y -= 1)
        state.move_up = bool(
            keys[sdl2.SDL_SCANCODE_UP]
            or keys[sdl2.SDL_SCANCODE_W]
            or keys[sdl2.SDL_SCANCODE_I]
        )

        # Move down: arrow DOWN or S or M  (Z80: LEFT key → ship_y += 1)
        state.move_down = bool(
            keys[sdl2.SDL_SCANCODE_DOWN]
            or keys[sdl2.SDL_SCANCODE_S]
            or keys[sdl2.SDL_SCANCODE_M]
        )

        # Move right: arrow RIGHT or D  (Z80: UP key → ship_x += 2)
        state.move_right = bool(
            keys[sdl2.SDL_SCANCODE_RIGHT]
            or keys[sdl2.SDL_SCANCODE_D]
        )

        # Move left: arrow LEFT or A  (Z80: DOWN key → ship_x -= 2)
        state.move_left = bool(
            keys[sdl2.SDL_SCANCODE_LEFT]
            or keys[sdl2.SDL_SCANCODE_A]
        )

        # Fire cannon: Z or X or Ctrl  (Z80: $3840 bits 3+4 or $3804 bits 1+7)
        state.fire = bool(
            keys[sdl2.SDL_SCANCODE_Z]
            or keys[sdl2.SDL_SCANCODE_X]
            or keys[sdl2.SDL_SCANCODE_LCTRL]
            or keys[sdl2.SDL_SCANCODE_RCTRL]
        )

        # Start: Enter or Space on title screen
        state.start = bool(
            keys[sdl2.SDL_SCANCODE_RETURN]
            or keys[sdl2.SDL_SCANCODE_SPACE]
        )

        # Abort: Escape (original: Shift + Break)
        state.abort = bool(keys[sdl2.SDL_SCANCODE_ESCAPE])

        return state
