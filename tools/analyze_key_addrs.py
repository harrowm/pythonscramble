#!/usr/bin/env python3
"""
analyze_key_addrs.py
--------------------
Inspect specific key memory locations in the memdump to resolve
the $6F23/fn_copy_screen_row source address mystery.
"""

import os
import struct

DUMP = os.path.join(os.path.dirname(__file__), '..', 'memdump.bin')

with open(DUMP, 'rb') as f:
    mem = bytearray(f.read())

def r8(addr):
    return mem[addr]

def r16(addr):
    lo = mem[addr]
    hi = mem[addr+1]
    return (hi << 8) | lo

def hex_dump_range(start, end, label=""):
    if label:
        print(f"\n--- {label} (${start:04X}-${end:04X}) ---")
    for addr in range(start, end+1, 16):
        chunk = mem[addr:min(addr+16, end+1)]
        hex_str = " ".join(f"{b:02X}" for b in chunk)
        asc_str = "".join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        print(f"  ${addr:04X}: {hex_str:<48}  |{asc_str}|")

print("=" * 70)
print("KEY ADDRESSES FROM MEMDUMP")
print("=" * 70)

# 1. What is at $6AB2? (ship_vram_off variable)
val_6ab2 = r16(0x6AB2)
print(f"\n$6AB2 (ship_vram_off):  stored value = ${val_6ab2:04X}")
print(f"  If fn_copy_screen_row (@$6F23) does LD HL,($6AB2):")
print(f"  -> HL = ${val_6ab2:04X}, meaning it copies FROM ${val_6ab2:04X} to VRAM $3C00")

# 2. What is at $6AB4? (second VRAM offset used by fn_draw_column_marker)
val_6ab4 = r16(0x6AB4)
print(f"\n$6AB4 (second vram offset): stored value = ${val_6ab4:04X}")

# 3. Dump the raw bytes of the fn_copy_screen_row code at $6F23
hex_dump_range(0x6F20, 0x6F5F, "fn_copy_screen_row area ($6F20-$6F5F)")

# 4. What block does ($6AB2) point to?
src_addr = val_6ab2
print(f"\n--- Block at ${src_addr:04X}-${src_addr+0x3FF:04X} (1KB pointed to by $6AB2) ---")
block = mem[src_addr:src_addr+1024]
# Render as screen
SCREEN_COLS = 64
SCREEN_ROWS = 16
print(f"  Screen render (+ = semigraphic, char = ASCII, . = blank $80, ? = other):")
print(f"  {'':5}" + "".join(f"{c%10}" for c in range(SCREEN_COLS)))
for row in range(SCREEN_ROWS):
    off = row * SCREEN_COLS
    row_bytes = block[off:off+SCREEN_COLS]
    rendered = ""
    for b in row_bytes:
        if 0x20 <= b <= 0x7E:
            rendered += chr(b)
        elif b == 0x80:
            rendered += '.'
        elif 0x81 <= b <= 0xBF:
            rendered += '#'
        else:
            rendered += '?'
    print(f"  {row:3d}|{rendered}|")

# Compute screen-data score
score = sum(1 for b in block if (0x20 <= b <= 0x7E) or (0x80 <= b <= 0xBF)) / 1024
print(f"  Screen-data score: {score:.1%}")

# 5.  Where does the instructions scroll LDIR at $5D67 copy TO?
print("\n" + "="*70)
print("LDIR @ $5D67: HL=$5E7F, DE=$5580, BC=$0228 (552 bytes)")
print("  Copies FROM $5E7F-$61A6 INTO $5580-$57A7")
print("  In the splash back-buffer: $5580 = row 4 col 0 + (0x180 = 384) = row 6")
print(f"  = splash row 6, col 0 ({0x5580 - 0x5400} / 64 = {(0x5580 - 0x5400)//64})")

src2 = mem[0x5E7F:0x5E7F+552]
score2 = sum(1 for b in src2 if (0x20 <= b <= 0x7E) or (0x80 <= b <= 0xBF)) / len(src2)
print(f"  Source block at $5E7F: score={score2:.1%}")
print(f"  First 32 bytes: {' '.join(f'{b:02X}' for b in src2[:32])}")
ascii_repr = "".join(chr(b) if 0x20<=b<=0x7E else ('.' if b==0x80 else f'\\x{b:02x}') for b in src2[:64])
print(f"  As text: {repr(ascii_repr)}")

# 6. Check what's at $5580 in the back-buffer (destination of above LDIR)
print("\n  Destination at $5580 in back-buffer:")
dest_block = mem[0x5580:0x5580+64]
print(f"  $5580-$55BF: {' '.join(f'{b:02X}' for b in dest_block)}")

# 7. Show the VRAM row 6 for comparison
vram_row6 = mem[0x3C00 + 6*64 : 0x3C00 + 7*64]
print(f"\n  VRAM row 6 ('Bomber' letters): {' '.join(f'{b:02X}' for b in vram_row6)}")
print(f"  Match with $5580? {vram_row6 == dest_block}")

# 8. Dump $6AA8-$6AC8 (game state variables near $6AB2)
hex_dump_range(0x6AA0, 0x6AD0, "Game state variables ($6AA0-$6AD0)")

# 9. Look at fnscroll area bytes more carefully
print("\n" + "="*70)
print("SVC ROUTINES NEAR $5D67 (the 552-byte copy)")
hex_dump_range(0x5D50, 0x5D90, "Around $5D67 (LDIR that copies score-table into back-buffer)")

print("\nDone.")
