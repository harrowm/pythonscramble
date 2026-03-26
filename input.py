"""
input.py - Keyboard input handler.

Original Z80 sources
--------------------
fn_read_joystick ($6E54):
    Reads from a lookup table at $6F5C indexed by a value at $6AB0.
    The value at $6AB0 is an index into an input state table, masking
    the lower 4 bits.  This is an indirect keyboard state read.

The original keyboard mapping (from instruction text at $5E00):
    "PRESS ARROW KEYS OR Q,W TO FIRE MACHINE GUN"
    "PRESS LEFT & RIGHT SIMULTANEOUSLY TO DROP BOMBS"
    "PRESS UP & DOWN SIMULTANEOUSLY TO DROP BOMBS"
    "<SPACE> TO START, <SHIFT> & <BREAK> TO ABORT GAME"

TRS-80 keyboard rows (memory-mapped at $3800–$38FF):
    $3880: bits 0-7 = various keys including arrow keys
    The game reads these via IN A,(port) or direct memory reads.

Python/SDL2 mapping
-------------------
We map the original controls to a comfortable modern layout:

    Arrow UP        → thrust up
    Arrow DOWN      → (not used in classic Scramble, but some versions allow)
    Z key           → fire machine gun (mapped from Q)
    X key           → fire machine gun (mapped from W) -- both needed simultaneously
    Space / Ctrl    → drop bomb
    Enter           → start game
    Escape          → abort / quit

The original required Q+W held simultaneously to fire the machine gun.
We simplify to a single FIRE key (Z or Space) for usability.
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
        "thrust_up",
        "thrust_down",
        "fire",
        "bomb",
        "start",
        "abort",
    )

    def __init__(self) -> None:
        self.thrust_up:  bool = False
        self.thrust_down: bool = False
        self.fire:       bool = False
        self.bomb:       bool = False
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

        # Thrust up: arrow UP or W or I
        state.thrust_up = bool(
            keys[sdl2.SDL_SCANCODE_UP]
            or keys[sdl2.SDL_SCANCODE_W]
            or keys[sdl2.SDL_SCANCODE_I]
        )

        # Thrust down: arrow DOWN or S or M
        # (not used in original Scramble, but some ports allowed it)
        state.thrust_down = bool(
            keys[sdl2.SDL_SCANCODE_DOWN]
            or keys[sdl2.SDL_SCANCODE_S]
            or keys[sdl2.SDL_SCANCODE_M]
        )

        # Fire machine gun: Z or X (original: Q+W simultaneously)
        # Both keys can fire independently (we relax the simultaneous requirement)
        state.fire = bool(
            keys[sdl2.SDL_SCANCODE_Z]
            or keys[sdl2.SDL_SCANCODE_X]
            or keys[sdl2.SDL_SCANCODE_LCTRL]
            or keys[sdl2.SDL_SCANCODE_RCTRL]
        )

        # Drop bomb: Space or Left-Alt (original: UP+DOWN simultaneously)
        state.bomb = bool(
            keys[sdl2.SDL_SCANCODE_SPACE]
            or keys[sdl2.SDL_SCANCODE_LALT]
            or keys[sdl2.SDL_SCANCODE_RALT]
        )

        # Start: Enter or Space on title screen
        state.start = bool(
            keys[sdl2.SDL_SCANCODE_RETURN]
            or keys[sdl2.SDL_SCANCODE_SPACE]
        )

        # Abort: Escape (original: Shift + Break)
        state.abort = bool(keys[sdl2.SDL_SCANCODE_ESCAPE])

        return state
