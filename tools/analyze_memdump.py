#!/usr/bin/env python3
"""
analyze_memdump.py
------------------
Analyzes memdump.bin (full 64KB Z80 address space snapshot taken while
Bomber Scramble is waiting at the title screen -- i.e. after the first
LDIR blit of the splash screen has already run).

Goals:
  1. Dump current VRAM ($3C00-$3FFF) as text, to confirm the splash screen
     is present.
  2. Show what is at $5400-$57FF (splash back-buffer) to confirm it matches
     VRAM.
  3. Show what is at $5E00-$60AF (instructions-screen data in the CMD file).
  4. Hunt for any OTHER 1KB-aligned blocks elsewhere in RAM that look like
     TRS-80 screen data (i.e. mostly $80-$BF semigraphic / $20-$7E ASCII).
  5. Scan for LDIR opcodes (ED B0) in executable regions and show their
     context so we can find a second blit instruction.
  6. Check whether a second 1K screen buffer exists, and if so, at what
     address.
"""

import sys
import os

DUMP = os.path.join(os.path.dirname(__file__), '..', 'memdump.bin')

# TRS-80 memory map constants
VRAM_START   = 0x3C00
VRAM_END     = 0x3FFF   # inclusive
VRAM_SIZE    = VRAM_END - VRAM_START + 1  # 1024

SPLASH_BUF_START = 0x5400
SPLASH_BUF_END   = 0x57FF
INSTR_START      = 0x5E00
INSTR_END        = 0x60AF

SCREEN_COLS = 64
SCREEN_ROWS = 16

# Printable TRS-80 character: $20-$7E are normal ASCII, $80-$BF are
# semigraphic blocks.  $00 and $FF are non-printable control bytes.
def is_screen_byte(b):
    return (0x20 <= b <= 0x7E) or (0x80 <= b <= 0xBF)

def screen_score(data):
    """Return fraction of bytes that look like valid TRS-80 screen data."""
    if not data:
        return 0.0
    return sum(1 for b in data if is_screen_byte(b)) / len(data)

def render_screen(data, cols=64, rows=16, label=""):
    """Render 1KB of TRS-80 VRAM as text."""
    print(f"\n{'='*68}")
    if label:
        print(f"  {label}")
    print(f"{'='*68}")
    print(f"     " + "".join(f"{c%10}" for c in range(cols)))
    for row in range(rows):
        offset = row * cols
        row_bytes = data[offset:offset+cols]
        # Render: semigraphic $80-$BF -> '#', ASCII $20-$7E -> char, else '.'
        rendered = ""
        for b in row_bytes:
            if 0x20 <= b <= 0x7E:
                rendered += chr(b)
            elif 0x80 <= b <= 0xBF:
                # Show density of lit pixels
                pixels = b & 0x3F  # 6 pixel bits
                count  = bin(pixels).count('1')
                rendered += "#" if count >= 4 else ("+" if count >= 2 else ".")
            else:
                rendered += f"\x1b[31m?\x1b[0m"  # red ? for unexpected byte
        print(f"  {row:2d}|{rendered}|")
    print(f"{'='*68}")

def hex_dump(data, base_addr, length=None, width=16, label=""):
    """Hex dump of data starting at base_addr."""
    if length is not None:
        data = data[:length]
    if label:
        print(f"\n--- {label} (${base_addr:04X}) ---")
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_part  = " ".join(f"{b:02X}" for b in chunk)
        # ASCII-printable part
        asc_part  = "".join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
        print(f"  ${base_addr+i:04X}:  {hex_part:<{width*3}}  |{asc_part}|")

def find_ldir(mem, start=0x5800, end=0x7000):
    """Find all LDIR (ED B0) opcodes in the code region and print context."""
    hits = []
    for addr in range(start, end - 1):
        if mem[addr] == 0xED and mem[addr+1] == 0xB0:
            hits.append(addr)
    return hits

def decode_ld_bc_imm(mem, addr):
    """If byte at addr is 0x01 (LD BC,nn), return the 16-bit immediate."""
    if mem[addr] == 0x01:
        lo = mem[addr+1]
        hi = mem[addr+2]
        return (hi << 8) | lo
    return None

def decode_ld_hl_imm(mem, addr):
    """If byte at addr is 0x21 (LD HL,nn), return the 16-bit immediate."""
    if mem[addr] == 0x21:
        lo = mem[addr+1]
        hi = mem[addr+2]
        return (hi << 8) | lo
    return None

def decode_ld_de_imm(mem, addr):
    """If byte at addr is 0x11 (LD DE,nn), return the 16-bit immediate."""
    if mem[addr] == 0x11:
        lo = mem[addr+1]
        hi = mem[addr+2]
        return (hi << 8) | lo
    return None


def main():
    with open(DUMP, 'rb') as f:
        mem = bytearray(f.read())

    print(f"Loaded memdump.bin: {len(mem)} bytes")
    assert len(mem) == 65536, "Expected 64KB dump!"

    # ----------------------------------------------------------------
    # 1. Show the current VRAM (splash screen should be visible)
    # ----------------------------------------------------------------
    vram = mem[VRAM_START : VRAM_START + VRAM_SIZE]
    render_screen(vram, label=f"CURRENT VRAM ($3C00-$3FFF) - Splash screen")

    # Count non-$80 bytes in VRAM
    blank_count = sum(1 for b in vram if b == 0x80)
    print(f"  VRAM: {blank_count} blank ($80) cells, {VRAM_SIZE-blank_count} non-blank")

    # ----------------------------------------------------------------
    # 2. Show splash back-buffer $5400-$57FF
    # ----------------------------------------------------------------
    splash = mem[SPLASH_BUF_START : SPLASH_BUF_START + VRAM_SIZE]
    match = sum(1 for a, b in zip(vram, splash) if a == b)
    print(f"\n  Splash buffer ($5400-$57FF) vs VRAM: {match}/{VRAM_SIZE} bytes match")
    if match == VRAM_SIZE:
        print("  ✓ VRAM == splash buffer  (LDIR blit confirmed, buffer not yet cleared)")
    else:
        print("  ≠ VRAM differs from splash buffer")
        render_screen(splash, label=f"SPLASH BACK-BUFFER ($5400-$57FF)")

    # Score the splash buffer for screen-data quality
    sp_score = screen_score(splash)
    print(f"  Splash buffer screen-data score: {sp_score:.1%}")

    # ----------------------------------------------------------------
    # 3. Show instructions data $5E00-$60AF
    # ----------------------------------------------------------------
    instr_data = mem[INSTR_START : INSTR_END + 1]
    instr_score = screen_score(instr_data)
    print(f"\n  Instructions data ($5E00-$60AF, {len(instr_data)} bytes)")
    print(f"  Screen-data score: {instr_score:.1%}")
    # Render as text to see what strings are in it
    print("  ASCII strings in instructions data:")
    buf = ""
    for i, b in enumerate(instr_data):
        if 0x20 <= b <= 0x7E:
            buf += chr(b)
        else:
            if len(buf) >= 4:
                print(f"    ${INSTR_START+i-len(buf):04X}: {repr(buf)}")
            buf = ""
    if len(buf) >= 4:
        print(f"    (end): {repr(buf)}")

    # ----------------------------------------------------------------
    # 4. Hunt for second 1K screen-data block in RAM
    # ----------------------------------------------------------------
    print("\n\n" + "="*68)
    print("  SCANNING FOR 1KB BLOCKS THAT LOOK LIKE TRS-80 SCREEN DATA")
    print("="*68)
    print("  (checking every 256-byte-aligned 1KB window from $4000 to $FFFF)")
    print(f"  {'Address':>10}  {'Score':>8}  {'Non-blank':>10}  Note")

    candidates = []
    for base in range(0x4000, 0xFC00, 0x100):   # step by 256 bytes
        block = mem[base:base+VRAM_SIZE]
        if len(block) < VRAM_SIZE:
            break
        sc = screen_score(block)
        if sc >= 0.70:   # at least 70% of bytes are valid screen bytes
            nblank = sum(1 for b in block if b != 0x80)
            note = ""
            if base == SPLASH_BUF_START:
                note = "<-- splash back-buffer"
            elif base == VRAM_START:
                note = "<-- VRAM"
            elif INSTR_START <= base <= INSTR_END:
                note = "<-- inside instructions data"
            elif base == 0x73CC:
                note = "<-- display page buffer (fn_clear_buffers)"
            candidates.append((base, sc, nblank, note))
            print(f"  ${base:04X}       {sc:>7.1%}  {nblank:>10}  {note}")

    # ----------------------------------------------------------------
    # 5. Find all LDIR opcodes in instruction region
    # ----------------------------------------------------------------
    print("\n\n" + "="*68)
    print("  ALL LDIR (ED B0) OPCODES IN CODE REGION ($5800-$7000)")
    print("="*68)

    ldir_addrs = find_ldir(mem, 0x5800, 0x7000)
    print(f"  Found {len(ldir_addrs)} LDIR instructions\n")

    for ldir_addr in ldir_addrs:
        # Walk back up to 20 bytes before LDIR looking for LD HL, LD DE, LD BC
        hl_src  = None
        de_dst  = None
        bc_cnt  = None
        for back in range(1, 21):
            addr = ldir_addr - back
            val  = mem[addr]
            if val == 0x21 and hl_src is None:
                hl_src = decode_ld_hl_imm(mem, addr)
            elif val == 0x11 and de_dst is None:
                de_dst = decode_ld_de_imm(mem, addr)
            elif val == 0x01 and bc_cnt is None:
                bc_cnt = decode_ld_bc_imm(mem, addr)

        hl_str = f"${hl_src:04X}" if hl_src is not None else "?"
        de_str = f"${de_dst:04X}" if de_dst is not None else "?"
        bc_str = f"${bc_cnt:04X} ({bc_cnt})" if bc_cnt is not None else "?"

        print(f"  LDIR @ ${ldir_addr:04X}:  HL={hl_str}  DE={de_str}  BC={bc_str}")

        # Classify
        if bc_cnt == 0x0400:
            print(f"         *** 1KB BLIT: ${hl_src:04X} -> ${de_dst:04X} ***")
        elif bc_cnt == 0x0800:
            print(f"         *** 2KB FILL ***")
        elif bc_cnt is not None and bc_cnt >= 512:
            print(f"         *** Large copy: {bc_cnt} bytes ***")
        print()

    # ----------------------------------------------------------------
    # 6. Detailed look at candidates -- render any non-splash 1KB blocks
    # ----------------------------------------------------------------
    for base, sc, nblank, note in candidates:
        if base == SPLASH_BUF_START or base == VRAM_START:
            continue  # already shown above
        block = mem[base:base+VRAM_SIZE]
        render_screen(block, label=f"1KB block @ ${base:04X}  (score={sc:.1%}, note={note})")

    # ----------------------------------------------------------------
    # 7. Quick look at what is loaded in CMD load range
    # ----------------------------------------------------------------
    print("\n\n" + "="*68)
    print("  CMD FILE LOAD REGION OVERVIEW  ($5800-$6F37)")
    print("="*68)
    cmd_start = 0x5800
    cmd_end   = 0x6F37
    for region_start, region_end, label in [
        (0x5800, 0x5FFF, "SVC stubs + routines"),
        (0x5E00, 0x60AF, "Instructions screen data"),
        (0x60B0, 0x61FF, "Entry + title/game loop code"),
        (0x6200, 0x6F37, "Main game logic code"),
    ]:
        data = mem[region_start:region_end+1]
        sc   = screen_score(data)
        nblank = sum(1 for b in data if b == 0x80)
        print(f"  ${region_start:04X}-${region_end:04X}  ({len(data):5d} bytes)"
              f"  screen_score={sc:5.1%}  blank=$80:{nblank:4d}  -- {label}")

    # ----------------------------------------------------------------
    # 8.  Does the instructions data ($5E00-$60AF) look like it COULD be
    #     a sub-set of a 1KB screen buffer? Find where the other 337
    #     bytes of a 1KB buffer starting at $5C00 would be.
    # ----------------------------------------------------------------
    print("\n\n" + "="*68)
    print("  HYPOTHESIS: instructions data is the SECOND 1KB screen buffer")
    print("  If instructions buffer starts at $5C00, it ends at $5FFF.")
    print("  If instructions buffer starts at $5E00, it ends at $61FF.")
    print("="*68)
    for hyp_start in [0x5C00, 0x5D00, 0x5E00]:
        hyp_data = mem[hyp_start:hyp_start+VRAM_SIZE]
        sc = screen_score(hyp_data)
        nblank = sum(1 for b in hyp_data if b == 0x80)
        print(f"  Hypothetical buffer ${hyp_start:04X}-${hyp_start+VRAM_SIZE-1:04X}:"
              f"  score={sc:5.1%}  blank={nblank}  non-blank={VRAM_SIZE-nblank}")
        render_screen(hyp_data, label=f"${hyp_start:04X}-${hyp_start+0x3FF:04X}")

    print("\nDone.")


if __name__ == '__main__':
    main()
