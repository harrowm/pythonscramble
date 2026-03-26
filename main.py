"""
main.py - Entry point for the Scramble Python/SDL2 port.

SDL2 initialisation, main loop, and frame-rate control.

The original TRS-80 game controls its speed through delay loops:
    fn_add_score ($6D99) calls ROM_DELAY once (BC=$0005)
    Zone init calls ROM_DELAY 6 times ($627B-$628A)
    fn_scroll_screen ($64CA) has phase-based delay loops

We replicate this timing with SDL2's timer:
    - Target 30 fps (FRAME_TIME_MS ≈ 33 ms per frame)
    - Each frame: update game state, render to TRS80Screen, blit to SDL window
    - If a frame completes early, SDL_Delay() burns the remaining time

This gives the same feel as the original without busy-waiting.
"""

import sys
import ctypes

import sdl2
import sdl2.ext

from constants import (
    WINDOW_WIDTH, WINDOW_HEIGHT,
    FRAME_TIME_MS,
    COLOUR_BACKGROUND,
)
from trs80_screen import TRS80Screen
from game         import Game
from input        import InputHandler


def main() -> int:
    """
    Initialise SDL2, run the game loop, clean up on exit.
    Returns 0 on clean exit, 1 on error.
    """

    # ----------------------------------------------------------------
    # SDL2 initialisation
    # ----------------------------------------------------------------
    if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO | sdl2.SDL_INIT_TIMER) != 0:
        print(f"SDL_Init error: {sdl2.SDL_GetError()}", file=sys.stderr)
        return 1

    window = sdl2.SDL_CreateWindow(
        b"SCRAMBLE - TRS-80",
        sdl2.SDL_WINDOWPOS_CENTERED,
        sdl2.SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        sdl2.SDL_WINDOW_SHOWN,
    )
    if not window:
        print(f"SDL_CreateWindow error: {sdl2.SDL_GetError()}", file=sys.stderr)
        sdl2.SDL_Quit()
        return 1

    # Use an accelerated renderer with vsync disabled so our frame limiter
    # has precise control (matches the original's software timing).
    renderer = sdl2.SDL_CreateRenderer(
        window, -1,
        sdl2.SDL_RENDERER_ACCELERATED,
    )
    if not renderer:
        print(f"SDL_CreateRenderer error: {sdl2.SDL_GetError()}", file=sys.stderr)
        sdl2.SDL_DestroyWindow(window)
        sdl2.SDL_Quit()
        return 1

    # ----------------------------------------------------------------
    # Game initialisation
    # ----------------------------------------------------------------
    game         = Game()
    input_handler = InputHandler()
    event         = sdl2.SDL_Event()

    running = True
    while running:
        frame_start_ms = sdl2.SDL_GetTicks()

        # ---- Process SDL events ----
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            if event.type == sdl2.SDL_QUIT:
                running = False
                break
            if event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_F11:
                    # Toggle fullscreen
                    flags = sdl2.SDL_GetWindowFlags(window)
                    if flags & sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP:
                        sdl2.SDL_SetWindowFullscreen(window, 0)
                    else:
                        sdl2.SDL_SetWindowFullscreen(
                            window, sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP
                        )

        if not running:
            break

        # ---- Read keyboard state ----
        # The TRS-80 game polls the keyboard every frame (no event queue).
        inp = input_handler.read()

        # ---- Update game state ----
        if not game.update(inp):
            running = False
            break

        # ---- Render ----
        # game.render() refreshes any HUD text on top of the game content
        # that was written to TRS80Screen during update().
        game.render()

        # Blit the TRS80Screen to the SDL2 renderer
        game.screen.render(renderer)

        sdl2.SDL_RenderPresent(renderer)

        # ---- Frame timing ----
        # Burn remaining time to hit the target frame rate.
        # This mirrors the Z80 delay loops that controlled game speed.
        frame_elapsed = sdl2.SDL_GetTicks() - frame_start_ms
        remaining = FRAME_TIME_MS - frame_elapsed
        if remaining > 1:
            sdl2.SDL_Delay(remaining - 1)

    # ----------------------------------------------------------------
    # Clean up
    # ----------------------------------------------------------------
    sdl2.SDL_DestroyRenderer(renderer)
    sdl2.SDL_DestroyWindow(window)
    sdl2.SDL_Quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
