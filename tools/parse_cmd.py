#!/usr/bin/env python3
"""
parse_cmd.py
------------
Parse the TRS-80 CMD file (arcbomb1.cmd) to show all load segments,
entry point, and identify where the two 1KB screen data blocks live.
"""

import os

CMD = os.path.join(os.path.dirname(__file__), '..', 'arcbomb1.cmd')
DUMP = os.path.join(os.path.dirname(__file__), '..', 'memdump.bin')

SCREEN_COLS = 64
SCREEN_ROWS = 16
VRAM_SIZE = SCREEN_COLS * SCREEN_ROWS  # 1024

def is_screen_byte(b):
    return (0x20 <= b <= 0x7E) or (0x80 <= b <= 0xBF)

def screen_score(data):
    if not data:
        return 0.0
    return sum(1 for b in data if is_screen_byte(b)) / len(data)

def render_screen(data, label=""):
    print(f"\n{'='*68}")
    if label:
        print(f"  {label}")
    print(f"{'='*68}")
    print(f"     " + "".join(f"{c%10}" for c in range(64)))
    for row in range(16):
        offset = row * 64
        row_bytes = data[offset:offset+64]
        rendered = ""
        for b in row_bytes:
            if 0x20 <= b <= 0x7E:
                rendered += chr(b)
            elif 0x80 <= b <= 0xBF:
                pixels = b & 0x3F
                count  = bin(pixels).count('1')
                rendered += "#" if count >= 4 else ("+" if count >= 2 else ".")
            else:
                rendered += "?"
        print(f"  {row:2d}|{rendered}|")
    print(f"{'='*68}")


with open(CMD, 'rb') as f:
    cmd_data = bytearray(f.read())

with open(DUMP, 'rb') as f:
    memdump = bytearray(f.read())

print(f"CMD file size: {len(cmd_data)} bytes")
print()

# Build a flat image of what the CMD loads into memory
mem_image = {}   # addr -> byte  (sparse)
segments = []

i = 0
while i < len(cmd_data):
    rec_type = cmd_data[i]
    if rec_type == 0x01:  # data block
        raw_len = cmd_data[i+1]
        length = 256 if raw_len == 0 else raw_len
        addr = (cmd_data[i+3] << 8) | cmd_data[i+2]
        end_addr = addr + length - 1
        payload = cmd_data[i+4 : i+4+length]
        sample = ' '.join(f'{b:02X}' for b in payload[:8])
        sc = screen_score(payload)
        # count blanks ($80)
        blank80 = sum(1 for b in payload if b == 0x80)
        non_blank = sum(1 for b in payload if b != 0x80)
        print(f"  DATA ${addr:04X}-${end_addr:04X}  ({length:4d} bytes)  "
              f"screen={sc:.0%}  non-blank={non_blank}  [{sample} ...]")
        segments.append((addr, end_addr, payload))
        for j, b in enumerate(payload):
            mem_image[addr + j] = b
        i += 4 + length

    elif rec_type == 0x02:  # transfer record (entry point)
        entry = (cmd_data[i+2] << 8) | cmd_data[i+1]
        print(f"\n  ENTRY POINT: ${entry:04X}")
        i += 3

    elif rec_type == 0x05:  # end of file
        print(f"  EOF marker")
        i += 1
        break
    else:
        print(f"  Unknown record ${rec_type:02X} at offset {i}")
        i += 1

print()
print("="*68)
print("SCANNING CMD DATA FOR 1KB BLOCKS THAT LOOK LIKE SCREEN DATA")
print("="*68)

# Build a contiguous array from the sparse image
if mem_image:
    lo = min(mem_image.keys())
    hi = max(mem_image.keys())
    flat = bytearray(hi - lo + 1)
    for addr, b in mem_image.items():
        flat[addr - lo] = b

    print(f"  CMD loads addresses ${lo:04X}-${hi:04X}")
    print()

    # Check every 64-byte-aligned 1KB window
    STEP = 64
    candidates = []
    for base in range(lo, hi - VRAM_SIZE + 2, STEP):
        chunk = flat[base-lo : base-lo+VRAM_SIZE]
        if len(chunk) < VRAM_SIZE:
            break
        sc = screen_score(chunk)
        non_blank = sum(1 for b in chunk if b != 0x80)
        if sc >= 0.70:
            candidates.append((base, sc, non_blank, chunk))

    print(f"  {'Address':>10}  {'Score':>8}  {'Non-blank':>10}  Note")
    for (base, sc, nb, chunk) in candidates:
        note = ""
        if 0x5400 <= base <= 0x5400:
            note = "<-- splash back-buffer"
        elif 0x5E00 <= base <= 0x61FF:
            note = "<-- instructions data region"
        print(f"  ${base:04X}         {sc:>7.1%}  {nb:>10}")

    # Show the top two candidates as rendered screens
    print()
    sorted_cands = sorted(candidates, key=lambda x: (-x[1], -x[2]))
    print("TOP CANDIDATE BLOCKS:")
    for (base, sc, nb, chunk) in sorted_cands[:4]:
        render_screen(chunk, label=f"${base:04X}-${base+VRAM_SIZE-1:04X}  (score={sc:.1%}  non-blank={nb})")

print()
print("="*68)
print("CHECKING KNOWN SCREEN BUFFERS IN MEMDUMP")
print("="*68)

# Splash back-buffer
splash = memdump[0x5400:0x5800]
print(f"\n  Splash back-buffer $5400-$57FF in memdump:")
render_screen(splash, label="SPLASH BACK-BUFFER ($5400-$57FF)")

# Instructions screen buffer
ptr_lo = memdump[0x6AB2]
ptr_hi = memdump[0x6AB3]
ptr = (ptr_hi << 8) | ptr_lo
print(f"\n  $6AB2 pointer = ${ptr:04X}")
instr_buf = memdump[ptr:ptr+VRAM_SIZE]
sc = screen_score(instr_buf)
nb = sum(1 for b in instr_buf if b != 0x80)
print(f"  Instructions screen buffer at ${ptr:04X}-${ptr+VRAM_SIZE-1:04X}: score={sc:.1%}  non-blank={nb}")
if nb > 10:
    render_screen(instr_buf, label=f"INSTRUCTIONS SCREEN (${ptr:04X}-${ptr+VRAM_SIZE-1:04X})")
else:
    print("  (buffer is mostly blank - instructions screen not yet rendered)")
    # Show the CMD instructions data region instead
    cmd_instr = flat[0x5E00-lo : 0x5E00-lo+0x02B0]  # $5E00-$60AF = 688 bytes
    sc2 = screen_score(cmd_instr)
    print(f"\n  CMD instructions data $5E00-$60AF: score={sc2:.1%}")

print("\nDone.")
