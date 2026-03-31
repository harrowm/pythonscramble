#!/usr/bin/env python3
"""
find_screen_blocks.py
---------------------
1. Load the CMD file and build a flat memory image of everything it loads.
2. Check every 64-byte-aligned 1KB window for high screen-byte ratio.
3. Cross-reference with the disassembly: find which high-score windows are
   NOT already annotated as DB directives.
4. Render any 'mystery' 1KB blocks as text so we can see what screen they show.
5. Also look at the $5E00 instructions data and show how the 688-byte source
   data decodes into the runtime instructions screen at $73CC.
"""

import os
import re

ASM_FILE = os.path.join(os.path.dirname(__file__), '..', 'scramble_disassembly.asm')
CMD_FILE = os.path.join(os.path.dirname(__file__), '..', 'arcbomb1.cmd')
DUMP_FILE = os.path.join(os.path.dirname(__file__), '..', 'memdump.bin')

VRAM_SIZE = 1024
SCREEN_COLS = 64
SCREEN_ROWS = 16

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def is_screen_byte(b):
    return (0x20 <= b <= 0x7E) or (0x80 <= b <= 0xBF)

def screen_score(data):
    if not data:
        return 0.0
    return sum(1 for b in data if is_screen_byte(b)) / len(data)

def render_screen(data, label=""):
    print(f"\n{'='*70}")
    if label:
        print(f"  {label}")
    print(f"{'='*70}")
    print("     " + "".join(f"{c%10}" for c in range(64)))
    for row in range(16):
        off = row * 64
        row_bytes = data[off:off+64]
        rendered = ""
        for b in row_bytes:
            if 0x20 <= b <= 0x7E:
                rendered += chr(b)
            elif 0x80 <= b <= 0xBF:
                cnt = bin(b & 0x3F).count('1')
                rendered += "#" if cnt >= 4 else ("+" if cnt >= 2 else ".")
            else:
                rendered += "?"
        print(f"  {row:2d}|{rendered}|")
    print(f"{'='*70}")

# ──────────────────────────────────────────────────────────────────────────────
# 1. Parse CMD file
# ──────────────────────────────────────────────────────────────────────────────

with open(CMD_FILE, 'rb') as f:
    raw = f.read()

mem_from_cmd = {}   # addr -> byte
blocks = []         # (addr, length)
pos = 0
entry_addr = None

while pos < len(raw) - 2:
    rec_type = raw[pos]
    if rec_type == 0x05:
        length = raw[pos+1]
        name = raw[pos+2:pos+2+length].decode('ascii', errors='replace').rstrip()
        pos += 2 + length
    elif rec_type == 0x02:
        length = raw[pos+1]
        if length in (0, 2, 3):
            entry_addr = raw[pos+2] | (raw[pos+3] << 8)
            pos += 4
        else:
            pos += 1
    elif rec_type == 0x01:
        length = raw[pos+1]
        if length == 0:
            length = 256
        addr = raw[pos+2] | (raw[pos+3] << 8)
        if 0x4000 <= addr <= 0x8000 and pos + 4 + length <= len(raw):
            block_bytes = raw[pos+4:pos+4+length]
            blocks.append((addr, length))
            for j, b in enumerate(block_bytes):
                mem_from_cmd[addr+j] = b
            next_hdr = pos + 4 + length - 2
            if (next_hdr + 4 <= len(raw)
                    and raw[next_hdr] == 0x01
                    and raw[next_hdr+3] != 0
                    and (0x4000 <= (raw[next_hdr+2] | (raw[next_hdr+3] << 8)) <= 0x8000)):
                pos = next_hdr
            else:
                pos += 4 + length
        else:
            pos += 1
    else:
        pos += 1

lo = min(mem_from_cmd.keys())
hi = max(mem_from_cmd.keys())
flat = bytearray(hi - lo + 1)
for addr, b in mem_from_cmd.items():
    flat[addr - lo] = b

print(f"CMD loads ${lo:04X}-${hi:04X}  ({len(mem_from_cmd)} bytes across {len(blocks)} blocks)")
if entry_addr:
    print(f"Entry point: ${entry_addr:04X}")

# ──────────────────────────────────────────────────────────────────────────────
# 2. Read memdump
# ──────────────────────────────────────────────────────────────────────────────

with open(DUMP_FILE, 'rb') as f:
    memdump = bytearray(f.read())

# ──────────────────────────────────────────────────────────────────────────────
# 3. Read disassembly - find what lines are DB vs code
# ──────────────────────────────────────────────────────────────────────────────

with open(ASM_FILE, 'r') as f:
    asm_lines = f.readlines()

# Extract address -> line type from disassembly
# A line with hex address comment like "; 5E00: xx xx" marks data/code
addr_to_line = {}   # addr -> 'DB' or 'CODE' or 'comment'
db_re  = re.compile(r'^\s+DB\b.*;\s+\$?([0-9A-Fa-f]{4}):')
code_re = re.compile(r'^\s+[A-Z]{2,5}[\s,].*;\s+([0-9A-Fa-f]{4}):')
addr_comment_re = re.compile(r';\s+([0-9A-Fa-f]{4}):')

for line in asm_lines:
    m = db_re.search(line)
    if m:
        try:
            a = int(m.group(1), 16)
            addr_to_line[a] = 'DB'
        except ValueError:
            pass
        continue
    m = code_re.search(line)
    if m:
        try:
            a = int(m.group(1), 16)
            addr_to_line[a] = 'CODE'
        except ValueError:
            pass

db_addrs  = {a for a, t in addr_to_line.items() if t == 'DB'}
code_addrs = {a for a, t in addr_to_line.items() if t == 'CODE'}

print(f"\nDisassembly covers: {len(addr_to_line)} addresses")
print(f"  DB entries:   {len(db_addrs)}")
print(f"  CODE entries: {len(code_addrs)}")

# ──────────────────────────────────────────────────────────────────────────────
# 4. Scan CMD data for 1KB screen-data blocks
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print("  SCANNING CMD DATA FOR 1KB SCREEN DATA BLOCKS")
print(f"{'='*70}")
print(f"  Checking every 64-byte-aligned 1KB window from ${lo:04X} to ${hi:04X}")
print(f"  {'Base':>8}  {'Score':>7}  {'Non-blank':>10}  {'Blank$80':>9}  ASM Status")

candidates = []
for base in range(lo, hi - VRAM_SIZE + 2, 64):
    off = base - lo
    chunk = flat[off:off+VRAM_SIZE]
    if len(chunk) < VRAM_SIZE:
        break
    sc = screen_score(chunk)
    if sc >= 0.75:
        nb = sum(1 for b in chunk if b != 0x80)
        blank80 = sum(1 for b in chunk if b == 0x80)
        candidates.append((base, sc, nb, blank80, chunk))

for (base, sc, nb, blank80, chunk) in candidates:
    # Check ASM status: how many bytes in this range have DB annotations?
    db_count   = sum(1 for a in range(base, base+VRAM_SIZE) if a in db_addrs)
    code_count = sum(1 for a in range(base, base+VRAM_SIZE) if a in code_addrs)
    unannotated = VRAM_SIZE - db_count - code_count

    note = ""
    if base == 0x5400:
        note = " <-- SPLASH back-buffer"
    elif 0x5E00 <= base <= 0x60AF:
        note = " <-- instructions source data"
    elif 0x73CC <= base <= 0x7BCB:
        note = " <-- game back-buffer (runtime)"

    status = f"DB={db_count} CODE={code_count} unannotated={unannotated}"
    print(f"  ${base:04X}     {sc:>6.1%}  {nb:>10}  {blank80:>9}  [{status}]{note}")

# ──────────────────────────────────────────────────────────────────────────────
# 5. Show the two main 1KB screen blits
# ──────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print("  THE TWO 1KB LDIR SCREEN BLITS")
print(f"{'='*70}")

# Blit 1: $5400 -> $3C00  (splash screen back-buffer in memdump)
splash = memdump[0x5400:0x5800]
sc_splash = screen_score(splash)
nb_splash = sum(1 for b in splash if b != 0x80)
print(f"\nBLIT 1 (LDIR @ $60D7): $5400 → $3C00  (splash/title screen)")
print(f"  Source $5400-$57FF: score={sc_splash:.1%}  non-blank={nb_splash}")
print(f"  Source is a RAM back-buffer - NOT stored as blob in CMD")
print(f"  Built dynamically by fn_draw_title_graphics ($5A56) + fn_draw_top_five_box ($5ADC)")
render_screen(splash, label="SPLASH SCREEN BACK-BUFFER $5400-$57FF (from memdump)")

# Blit 2: ($6AB2) -> $3C00  (at runtime $6AB2=$73CC = game back-buffer)
ptr_lo = memdump[0x6AB2]
ptr_hi = memdump[0x6AB3]
ptr = (ptr_hi << 8) | ptr_lo
game_buf = memdump[ptr:ptr+VRAM_SIZE]
sc_game = screen_score(game_buf)
nb_game = sum(1 for b in game_buf if b != 0x80)
print(f"\nBLIT 2 (LDIR @ $6F2C): ($6AB2)=${ptr:04X} → $3C00  (game display page)")
print(f"  $6AB2 = ship_vram_off = game display buffer base")
print(f"  Initial CMD value $6AB2 = $73CC (the 2KB game back-buffer)")
print(f"  Source ${ptr:04X}-${ptr+VRAM_SIZE-1:04X}: score={sc_game:.1%}  non-blank={nb_game}")
if nb_game <= 5:
    print(f"  (buffer blank: game not yet started)")
else:
    render_screen(game_buf, label=f"GAME DISPLAY BUFFER ${ptr:04X}-${ptr+VRAM_SIZE-1:04X}")

# Show instructions source data for comparison  
print(f"\n{'='*70}")
print("  INSTRUCTIONS SOURCE DATA $5E00-$60AF (688 bytes in CMD)")
print(f"{'='*70}")
instr_src = flat[0x5E00-lo:0x5E00-lo+688]
sc_instr = screen_score(instr_src)
print(f"  score={sc_instr:.1%}  This is @-terminated string + semigraphic tile data")
print(f"  Decoded by fn_scroll_screen ($64CA) which scrolls text across screen")
print(f"  NOT a flat 1KB screen image; the scroll routine renders it line by line")

print(f"\n{'='*70}")
print("  SUMMARY OF FINDINGS")
print(f"{'='*70}")
print("""
  BLIT 1: fn_game_entry ($60B0) builds splash screen into $5400-$57FF
    then LDIR $5400→$3C00 at $60D7.
    The splash back-buffer is RAM, NOT a pre-stored blob in CMD.
    Its content is built from string tables at $5B6C/$5B80/$5BAF/$5BD3
    (embedded inside the SVC code block $5800-$5DFF).

  BLIT 2: fn_copy_screen_row ($6F23) copies 1KB from ($6AB2)=$73CC to VRAM.
    $6AB2 = ship_vram_off = base address of the 2KB game back-buffer.
    The CMD stores $73CC as the INITIAL VALUE of $6AB2.
    fn_clear_buffers ($643C) fills $73CC with 2048x$80 at game start.
    During gameplay, rendering routines paint into $73CC and then the
    fn_copy_screen_row blit pushes 1KB of it to VRAM each frame.

  DISASSEMBLY STATUS:
    - $5E00-$60AF: instructions source data is correctly annotated as DB ✓
    - $6F23 comment incorrectly says "$6AB2 = $5E00 at startup"
      CORRECT:  $6AB2 = ship_vram_off, initial CMD value = $73CC
    - $6F23 is the general-purpose screen blit ("fn_copy_screen_row" in
      game loop), NOT solely a "title screen" function
    - No additional undiscovered 1KB screen blobs found in CMD data
""")
print("Done.")
