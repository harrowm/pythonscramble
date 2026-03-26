"""
enemies.py - Enemy system for Scramble.

Original Z80 sources
--------------------
enemy_table ($6A00):
    Array of enemy state records in RAM.  Each record contains:
        byte 0: active flag (0=inactive, non-zero=active)
        byte 1: spawn trigger (read by fn_try_spawn_enemy $69DE)
        byte 2: x position (character column)
        byte 3: y position (character row)
        byte 4: dx (x velocity, signed)
        byte 5: dy (y velocity, signed)
        byte 6: type / sprite code

fn_update_all_enemies ($69D6):
    Sets a "enemies updated" flag then returns.  The actual per-enemy
    update is handled by per-type subroutines called from the main loop.

fn_try_spawn_enemy ($69DE):
    Compares scroll position against spawn trigger; if trigger passed,
    marks enemy active.

fn_draw_enemy ($68B3):
    Writes the enemy sprite characters to video RAM at enemy position.

Enemy types and behaviours
--------------------------
Derived from the zone strings, screen layout data, and sprite chars:

FIGHTER   - moves left across the screen (mirror of player's ship sprite,
            flipped horizontally).  Standard enemy in all zones.

FIREBALL  - moves left with a sine-wave vertical oscillation.  Appears
            in Blimps and Fighters zones.

BLIMP     - large slow-moving enemy, moves left.  Zone 1.

BOMBER    - moves left, periodically drops bombs toward the player.  Zone 2.

ROCKET    - spawns from floor, rises vertically.  Zone 3 (Fort) and 5 (Rockets).

FUEL_TANK - static ground target, destroyed by bombs for bonus points.
            Zone 6.

ACK_ACK   - anti-aircraft gun on the ground, fires upward at player.
            Zone 7 (Arsenal).
"""

import math
import random
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from constants import (
    PIXELS_WIDE, PIXELS_TALL,
    SCREEN_CHARS_WIDE, SCREEN_CHARS_TALL,
    MAX_ENEMIES,
    SCORE_FIGHTER, SCORE_FIREBALL, SCORE_UFO,
    SCORE_FUEL_TANK, SCORE_ROCKET, SCORE_FORT, SCORE_ACK_ACK,
)
from trs80_screen import TRS80Screen


class EnemyType(IntEnum):
    FIGHTER   = 0
    FIREBALL  = 1
    BLIMP     = 2
    BOMBER    = 3
    ROCKET    = 4
    FUEL_TANK = 5
    ACK_ACK   = 6
    MYSTERY   = 7


# ---------------------------------------------------------------------------
# Enemy sprites
# ---------------------------------------------------------------------------
# Each enemy sprite is a list of (char_code, col_offset, row_offset) tuples.
# char_code = $20 / $80 means transparent (skip write).
# We use TRS-80 semigraphic chars to approximate the original pixel art.

ENEMY_SPRITES: dict[EnemyType, list[tuple[int, int, int]]] = {

    EnemyType.FIGHTER: [
        # A small fighter, 3×2 chars, pointing LEFT (facing the player)
        # Top row
        (0xA4, 0, 0),   # nose tip (left-pointing)
        (0xBF, 1, 0),   # fuselage
        (0xB0, 2, 0),   # tail
        # Bottom row
        (0xB4, 0, 1),   # belly
        (0xBF, 1, 1),   # fuselage
        (0x80, 2, 1),   # transparent
    ],

    EnemyType.FIREBALL: [
        # A 2×2 fireball / energy ball
        (0xB7, 0, 0),
        (0xBD, 1, 0),
        (0xBD, 0, 1),
        (0xB7, 1, 1),
    ],

    EnemyType.BLIMP: [
        # A large 5×3 blimp
        (0x80, 0, 0), (0xB5, 1, 0), (0xBF, 2, 0), (0xB5, 3, 0), (0x80, 4, 0),
        (0xBF, 0, 1), (0xBF, 1, 1), (0xBF, 2, 1), (0xBF, 3, 1), (0xBF, 4, 1),
        (0x80, 0, 2), (0x90, 1, 2), (0xB0, 2, 2), (0x90, 3, 2), (0x80, 4, 2),
    ],

    EnemyType.BOMBER: [
        # A bomber aircraft, 4×2 chars, facing left
        (0xA4, 0, 0), (0xBF, 1, 0), (0xBF, 2, 0), (0xB4, 3, 0),
        (0x80, 0, 1), (0x90, 1, 1), (0x90, 2, 1), (0x80, 3, 1),
    ],

    EnemyType.ROCKET: [
        # A vertical rocket, 2×3 chars
        (0xB5, 0, 0), (0xB5, 1, 0),
        (0xBF, 0, 1), (0xBF, 1, 1),
        (0xB0, 0, 2), (0xB0, 1, 2),
    ],

    EnemyType.FUEL_TANK: [
        # A ground-based fuel tank, 3×2 chars
        (0xB5, 0, 0), (0xBF, 1, 0), (0xB5, 2, 0),
        (0xBF, 0, 1), (0xBF, 1, 1), (0xBF, 2, 1),
    ],

    EnemyType.ACK_ACK: [
        # Anti-aircraft gun, 3×2 chars (on ground, barrel pointing up)
        (0x80, 0, 0), (0xB5, 1, 0), (0x80, 2, 0),
        (0xBF, 0, 1), (0xBF, 1, 1), (0xBF, 2, 1),
    ],

    EnemyType.MYSTERY: [
        # Mystery ship (bonus enemy)
        (0x80, 0, 0), (0xBF, 1, 0), (0xBF, 2, 0), (0x80, 3, 0),
        (0xBF, 0, 1), (0xBF, 1, 1), (0xBF, 2, 1), (0xBF, 3, 1),
    ],
}

# Score value per enemy type
ENEMY_SCORES: dict[EnemyType, int] = {
    EnemyType.FIGHTER:   SCORE_FIGHTER,
    EnemyType.FIREBALL:  SCORE_FIREBALL,
    EnemyType.BLIMP:     100,
    EnemyType.BOMBER:    100,
    EnemyType.ROCKET:    SCORE_ROCKET,
    EnemyType.FUEL_TANK: SCORE_FUEL_TANK,
    EnemyType.ACK_ACK:   SCORE_ACK_ACK,
    EnemyType.MYSTERY:   SCORE_UFO,
}

# Sprite size (cols, rows) per enemy type
ENEMY_SIZE: dict[EnemyType, tuple[int, int]] = {
    EnemyType.FIGHTER:   (3, 2),
    EnemyType.FIREBALL:  (2, 2),
    EnemyType.BLIMP:     (5, 3),
    EnemyType.BOMBER:    (4, 2),
    EnemyType.ROCKET:    (2, 3),
    EnemyType.FUEL_TANK: (3, 2),
    EnemyType.ACK_ACK:   (3, 2),
    EnemyType.MYSTERY:   (4, 2),
}


# ---------------------------------------------------------------------------
# Enemy zone spawn tables
# ---------------------------------------------------------------------------
# Which enemy types appear in each zone, and their relative spawn rate.
# Derived from zone names and the original screen layout data.

ZONE_ENEMIES: list[list[tuple[EnemyType, float]]] = [
    # Zone 0: Fighters
    [(EnemyType.FIGHTER, 1.0), (EnemyType.FIREBALL, 0.3)],
    # Zone 1: Blimps
    [(EnemyType.BLIMP, 0.8), (EnemyType.FIGHTER, 0.4)],
    # Zone 2: Bombers
    [(EnemyType.BOMBER, 0.9), (EnemyType.FIGHTER, 0.3)],
    # Zone 3: Fort
    [(EnemyType.ROCKET, 0.8), (EnemyType.FIGHTER, 0.4), (EnemyType.FUEL_TANK, 0.5)],
    # Zone 4: Factory
    [(EnemyType.FUEL_TANK, 0.9), (EnemyType.ROCKET, 0.4), (EnemyType.FIGHTER, 0.3)],
    # Zone 5: Rockets
    [(EnemyType.ROCKET, 1.0), (EnemyType.BOMBER, 0.3)],
    # Zone 6: Fuel Tanks
    [(EnemyType.FUEL_TANK, 1.0), (EnemyType.ACK_ACK, 0.5)],
    # Zone 7: Arsenal / ACK-ACK
    [(EnemyType.ACK_ACK, 1.0), (EnemyType.ROCKET, 0.6), (EnemyType.FUEL_TANK, 0.4)],
]


# ---------------------------------------------------------------------------
# Enemy dataclass
# ---------------------------------------------------------------------------

@dataclass
class Enemy:
    """
    One enemy object.  Mirrors one record in the Z80 enemy_table ($6A00).
    """
    enemy_type: EnemyType = EnemyType.FIGHTER
    pixel_x:    float = 0.0
    pixel_y:    float = 0.0
    vel_x:      float = 0.0    # pixels/frame horizontal (negative = moving left)
    vel_y:      float = 0.0    # pixels/frame vertical
    active:     bool  = False
    frame:      int   = 0      # animation / behaviour counter
    alive:      bool  = True

    # For sine-wave movement (fireballs)
    _sine_phase: float = 0.0

    @property
    def char_col(self) -> int:
        return max(0, int(self.pixel_x) // 2)

    @property
    def char_row(self) -> int:
        return max(0, int(self.pixel_y) // 3)

    @property
    def score_value(self) -> int:
        return ENEMY_SCORES.get(self.enemy_type, 50)

    @property
    def sprite(self) -> list[tuple[int, int, int]]:
        return ENEMY_SPRITES.get(self.enemy_type, [])

    @property
    def size(self) -> tuple[int, int]:
        return ENEMY_SIZE.get(self.enemy_type, (2, 2))


# ---------------------------------------------------------------------------
# EnemyManager
# ---------------------------------------------------------------------------

class EnemyManager:
    """
    Manages the pool of active enemies.
    Mirrors the enemy_table and fn_update_all_enemies ($69D6).
    """

    def __init__(self) -> None:
        self._pool: list[Enemy] = [Enemy() for _ in range(MAX_ENEMIES)]
        self._zone_index: int = 0
        self._rng = random.Random()
        self._spawn_timer: int = 0
        self._spawn_interval: int = 45   # frames between spawn attempts

    def set_zone(self, zone_index: int) -> None:
        """Switch to a new zone and reset the enemy pool."""
        self._zone_index = zone_index
        self.clear_all()
        self._spawn_timer = 0
        # Shorter spawn interval in later (harder) zones
        self._spawn_interval = max(20, 45 - zone_index * 3)

    def clear_all(self) -> None:
        """Deactivate all enemies.  Called on zone transition or player death."""
        for enemy in self._pool:
            enemy.active = False
            enemy.alive  = True

    def update(self, screen: TRS80Screen) -> None:
        """
        Update all active enemies for one frame.
        Mirrors fn_update_all_enemies ($69D6).
        Called once per frame from the main game loop.
        """
        # Try to spawn a new enemy periodically
        self._spawn_timer += 1
        if self._spawn_timer >= self._spawn_interval:
            self._spawn_timer = 0
            self._try_spawn()

        # Update each active enemy
        for enemy in self._pool:
            if not enemy.active:
                continue
            self._erase_enemy(screen, enemy)
            self._update_enemy(enemy)
            # Deactivate if enemy moved off left edge of screen
            if enemy.pixel_x < -10 or enemy.pixel_y < -6 or enemy.pixel_y > PIXELS_TALL + 6:
                enemy.active = False
                continue
            if enemy.alive:
                self._draw_enemy(screen, enemy)

    def check_missile_hit(
        self, missile_col: int, missile_row: int
    ) -> Optional[Enemy]:
        """
        Check if the missile has hit any active enemy.
        Mirrors fn_missile_hit_test ($6AC5).
        Returns the hit Enemy object, or None.
        """
        for enemy in self._pool:
            if not enemy.active or not enemy.alive:
                continue
            cols, rows = enemy.size
            if (enemy.char_col <= missile_col < enemy.char_col + cols
                    and enemy.char_row <= missile_row < enemy.char_row + rows):
                return enemy
        return None

    def check_bomb_hit(
        self, bomb_col: int, bomb_row: int
    ) -> Optional[Enemy]:
        """
        Check if the bomb has hit any active enemy / ground target.
        Mirrors fn_bomb_hit_test ($6C88).
        """
        for enemy in self._pool:
            if not enemy.active or not enemy.alive:
                continue
            cols, rows = enemy.size
            if (enemy.char_col <= bomb_col < enemy.char_col + cols
                    and enemy.char_row <= bomb_row < enemy.char_row + rows):
                return enemy
        return None

    def check_ship_collision(
        self, ship_col: int, ship_row: int,
        ship_w: int, ship_h: int
    ) -> bool:
        """Return True if any enemy overlaps the ship's bounding box."""
        for enemy in self._pool:
            if not enemy.active or not enemy.alive:
                continue
            ecols, erows = enemy.size
            # AABB overlap test
            if (ship_col < enemy.char_col + ecols
                    and ship_col + ship_w > enemy.char_col
                    and ship_row < enemy.char_row + erows
                    and ship_row + ship_h > enemy.char_row):
                return True
        return False

    def destroy_enemy(
        self, enemy: Enemy, screen: TRS80Screen
    ) -> None:
        """Destroy an enemy: erase its sprite and deactivate it."""
        self._erase_enemy(screen, enemy)
        enemy.active = False
        enemy.alive  = False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _try_spawn(self) -> None:
        """
        Attempt to spawn a new enemy from the current zone's spawn table.
        Mirrors fn_try_spawn_enemy ($69DE).
        """
        if self._zone_index >= len(ZONE_ENEMIES):
            return

        # Find a free slot in the pool
        free_slot = next(
            (e for e in self._pool if not e.active), None
        )
        if free_slot is None:
            return   # all slots occupied

        # Pick an enemy type according to zone weights
        spawn_table = ZONE_ENEMIES[self._zone_index]
        choices = [(etype, w) for etype, w in spawn_table]
        total   = sum(w for _, w in choices)
        r       = self._rng.random() * total
        cumulative = 0.0
        chosen_type = EnemyType.FIGHTER
        for etype, w in choices:
            cumulative += w
            if r <= cumulative:
                chosen_type = etype
                break

        self._init_enemy(free_slot, chosen_type)

    def _init_enemy(self, enemy: Enemy, enemy_type: EnemyType) -> None:
        """Initialise an enemy record for spawning."""
        enemy.enemy_type = enemy_type
        enemy.alive      = True
        enemy.active     = True
        enemy.frame      = 0
        enemy._sine_phase = self._rng.uniform(0, math.tau)

        cols, rows = ENEMY_SIZE[enemy_type]

        if enemy_type == EnemyType.FUEL_TANK:
            # Fuel tanks appear on the ground (bottom of screen)
            floor_row = SCREEN_CHARS_TALL - rows - 1
            enemy.pixel_x = float(PIXELS_WIDE)   # spawn off right edge
            enemy.pixel_y = float(floor_row * 3)
            enemy.vel_x   = 0.0   # fuel tanks don't move - they're terrain
            enemy.vel_y   = 0.0

        elif enemy_type == EnemyType.ACK_ACK:
            # ACK-ACK guns sit on the ground
            floor_row = SCREEN_CHARS_TALL - rows - 1
            enemy.pixel_x = float(PIXELS_WIDE)
            enemy.pixel_y = float(floor_row * 3)
            enemy.vel_x   = 0.0
            enemy.vel_y   = 0.0

        elif enemy_type == EnemyType.ROCKET:
            # Rockets spawn from the floor and rise vertically
            enemy.pixel_x = float(PIXELS_WIDE - self._rng.randint(0, 16))
            enemy.pixel_y = float(PIXELS_TALL - rows * 3)
            enemy.vel_x   = -1.5   # drift left slowly
            enemy.vel_y   = -2.0   # rise upward

        else:
            # All other enemies spawn from the right edge of the screen
            # at a random vertical position within the flyable corridor.
            enemy.pixel_x = float(PIXELS_WIDE)
            safe_y_min    = 6
            safe_y_max    = PIXELS_TALL - rows * 3 - 6
            enemy.pixel_y = float(self._rng.randint(safe_y_min, max(safe_y_min, safe_y_max)))

            # Horizontal speed: fighters move fast, blimps slow
            speeds = {
                EnemyType.FIGHTER:  -2.0,
                EnemyType.FIREBALL: -1.5,
                EnemyType.BLIMP:    -1.0,
                EnemyType.BOMBER:   -1.5,
                EnemyType.MYSTERY:  -3.0,
            }
            enemy.vel_x = speeds.get(enemy_type, -1.5)
            enemy.vel_y = 0.0

    def _update_enemy(self, enemy: Enemy) -> None:
        """Apply per-frame movement for one enemy."""
        enemy.frame += 1

        if enemy.enemy_type == EnemyType.FIREBALL:
            # Sine-wave vertical oscillation
            enemy._sine_phase += 0.25
            enemy.vel_y = math.sin(enemy._sine_phase) * 1.5
            enemy.pixel_x += enemy.vel_x
            enemy.pixel_y += enemy.vel_y

        elif enemy.enemy_type == EnemyType.BOMBER:
            # Bombers move left and periodically drop bombs (handled by game.py)
            enemy.pixel_x += enemy.vel_x
            # Slight up-down oscillation
            enemy.pixel_y += math.sin(enemy.frame * 0.1) * 0.5

        elif enemy.enemy_type in (EnemyType.FUEL_TANK, EnemyType.ACK_ACK):
            # Static ground targets: move left at scroll speed so they appear
            # to be part of the terrain
            enemy.pixel_x -= 2.0   # one char per frame (matches scroll)

        else:
            enemy.pixel_x += enemy.vel_x
            enemy.pixel_y += enemy.vel_y

    def _draw_enemy(self, screen: TRS80Screen, enemy: Enemy) -> None:
        """
        Write the enemy sprite to video RAM.
        Mirrors fn_draw_enemy ($68B3): writes char codes at enemy position,
        skipping transparent ($20/$80) cells.
        """
        base_col = enemy.char_col
        base_row = enemy.char_row
        for char_code, dc, dr in enemy.sprite:
            if char_code == 0x80 or char_code == 0x20:
                continue
            c = base_col + dc
            r = base_row + dr
            if 0 <= c < SCREEN_CHARS_WIDE and 0 <= r < SCREEN_CHARS_TALL:
                screen.write_char(c, r, char_code)

    def _erase_enemy(self, screen: TRS80Screen, enemy: Enemy) -> None:
        """Erase the enemy's sprite cells (write space chars)."""
        base_col = enemy.char_col
        base_row = enemy.char_row
        cols, rows = enemy.size
        for dr in range(rows):
            for dc in range(cols):
                c = base_col + dc
                r = base_row + dr
                if 0 <= c < SCREEN_CHARS_WIDE and 0 <= r < SCREEN_CHARS_TALL:
                    screen.write_char(c, r, 0x20)
