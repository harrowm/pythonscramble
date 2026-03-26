# Scramble — TRS-80 Python/SDL2 Port

A faithful Python reimplementation of the TRS-80 arcade game **Scramble**
(SCRAMBLE/CMD, disk00560.dmk), reverse-engineered from the original Z80
machine code.

---

## Controls

| Key | Action |
|---|---|
| **Arrow UP** / W / I | Thrust upward |
| **Z** or **X** | Fire machine gun |
| **Space** or **Alt** | Drop bomb |
| **Enter** or **Space** | Start game (on title screen) |
| **F11** | Toggle fullscreen |
| **Escape** | Quit |

The original TRS-80 controls were:
- Arrow keys or Q/W to fire (Q+W simultaneously)
- UP+DOWN simultaneously to drop bombs
- Space to start, Shift+Break to abort

---

## Setup

```bash
pip install pysdl2 pysdl2-dll
python main.py
```

Python 3.10+ required (uses `match` and `|` type union syntax).

---

## Architecture

```
scramble/
├── main.py          Entry point: SDL2 init, game loop, frame timing
├── constants.py     All magic numbers (derived from Z80 disassembly)
├── trs80_screen.py  TRS-80 128×48 semigraphic display emulation
├── terrain.py       Scrolling terrain generation (zone by zone)
├── ship.py          Player ship: movement, gravity, sprite, collision
├── projectiles.py   Missile (forward) and bomb (downward)
├── enemies.py       All 8 enemy types with spawn tables per zone
├── explosions.py    Block-char explosion animation (8 frames)
├── hud.py           Score, lives, fuel bar display
├── input.py         SDL2 keyboard polling (mirrors TRS-80 keyboard scan)
└── game.py          State machine: TITLE → PLAYING → DEAD → GAME_OVER
```

---

## TRS-80 Display Model

The TRS-80 screen is **64 columns × 16 rows** of character cells.
Characters `$80`–`$BF` are *semigraphic block characters* — each cell
encodes a **2×3 pixel grid** (6 bits), giving an effective resolution of
**128×48 pixels**.

Bit layout for char `$80 | bits`:
```
bit5 | bit4   ← top row of cell
bit3 | bit2   ← middle row
bit1 | bit0   ← bottom row
```

`trs80_screen.py` provides `set_pixel(x,y)`, `reset_pixel(x,y)`, and
`point(x,y)` — exactly mirroring the TRS-80 BASIC SET/RESET/POINT commands
and the Z80 video RAM read/write operations used throughout the original code.

Each logical pixel is rendered as an 8×8 SDL2 rectangle in phosphor green
(`#21FF21`) on near-black (`#00 0C 00`), giving the authentic CRT monitor look.

---

## Z80 Cross-Reference

Every Python module includes references to the Z80 subroutine addresses it
replicates.  Key functions:

| Python | Z80 address | Description |
|---|---|---|
| `TRS80Screen.set_pixel` | SET(x,y) BASIC / video RAM | Turn on a pixel |
| `TRS80Screen.scroll_left` | `fn_scroll_screen $64CA` | Scroll screen left |
| `Terrain.draw_to_screen` | `fn_draw_terrain $6495` | Draw terrain to screen |
| `Ship.update` | `fn_move_ship $65BF` | Apply gravity + thrust |
| `Ship.check_terrain_collision` | `fn_check_ship_crash $65C2` | Collision detection |
| `Missile.update` | `fn_update_missile $6A4E` | Move missile, check hit |
| `Bomb.update` | `fn_update_bomb $6C59` | Move bomb, check hit |
| `EnemyManager.update` | `fn_update_all_enemies $69D6` | Update all enemies |
| `HUD.add_score` | `fn_add_score $6D99` | BCD score arithmetic |
| `HUD.consume_fuel` | `fn_consume_fuel $6D46` | Drain fuel per frame |
| `Game._kill_player` | `fn_player_death $6E15` | Death sequence |
| `InputHandler.read` | `fn_read_joystick $6E54` | Keyboard poll |

Full annotated Z80 disassembly is in `scramble_disassembly.asm`.

---

## Zones

| # | Name | Enemy types |
|---|---|---|
| 0 | Fighters | Fighter jets, Fireballs |
| 1 | Blimps | Blimps, Fighters |
| 2 | Bombers | Bombers, Fighters |
| 3 | Fort | Rockets, Fuel tanks |
| 4 | Factory | Fuel tanks, Rockets |
| 5 | Rockets | Rockets, Bombers |
| 6 | Fuel Tanks | Fuel tanks, ACK-ACK |
| 7 | Arsenal | ACK-ACK, Rockets, Fuel tanks |

After Zone 7 the game loops back to Zone 0 at increased difficulty.

---

## Scoring

| Target | Points |
|---|---|
| Fighter | 50 |
| Fireball | 50 |
| Blimp | 100 |
| Bomber | 100 |
| Rocket | 50 |
| Fuel Tank | 150 |
| ACK-ACK gun | 125 |
| Fort | 75 |
| Bonus life | Every 10,000 scored |
