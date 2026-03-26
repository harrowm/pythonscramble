"""
Extract instructions screen data from arcbomb1.cmd and write them to
a Python snippet that can be pasted into constants.py.
"""
import sys

with open('arcbomb1.cmd', 'rb') as f:
    raw = f.read()

mem = {}
pos = 0
blocks = []
while pos < len(raw) - 3:
    rec_type = raw[pos]
    if rec_type == 0x05:
        length = raw[pos+1]
        pos += 2 + length
    elif rec_type == 0x02:
        length = raw[pos+1]
        pos += 4 if length in (0, 2, 3) else 1
    elif rec_type == 0x01:
        length = raw[pos+1] or 256
        addr = raw[pos+2] | (raw[pos+3] << 8)
        if 0x4000 <= addr <= 0x8000 and pos + 4 + length <= len(raw):
            block = raw[pos+4:pos+4+length]
            blocks.append((addr, length, pos))
            for i, b in enumerate(block):
                mem[addr+i] = b
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

# ---------------------------------------------------------------
# Build INSTR_SCREEN_DATA: rows 2-9 of the panorama (semigraphics)
# stored at $5E80-$60BF, 8 rows × 64 bytes = 512 bytes
# ---------------------------------------------------------------
PANO_START = 0x5E80
PANO_ROWS  = 8   # rows 2-9 from primary panorama data

lines_pano = ["# Semigraphic score/enemy-sprite panorama from $5E80-$60BF (Z80 instructions screen)"]
lines_pano += ["# 8 rows × 64 bytes each.  Displayed in screen rows 5-14 with left-scroll."]
lines_pano += ["INSTR_SCREEN_DATA = bytes(["]
for row in range(PANO_ROWS):
    chunk = [mem.get(PANO_START + row*64 + c, 0x80) for c in range(64)]
    vals = ', '.join(f'0x{b:02X}' for b in chunk)
    asc = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
    lines_pano.append(f'    {vals},  # row {row}  |{asc}|')
lines_pano.append("])")

# ---------------------------------------------------------------
# Parse INSTR_TEXT_ROWS: @-terminated text strings at $5D40-$5E7F
# ---------------------------------------------------------------
STREAM_START = 0x5D40
STREAM_END   = 0x5E80

all_lines = []
cur_line = ""
for addr in range(STREAM_START, STREAM_END):
    b = mem.get(addr, 0x80)
    if b == 0x40:          # '@'
        s = cur_line.strip()
        if s and len(s) > 5:
            all_lines.append(s)
        cur_line = ""
    elif 0x20 <= b <= 0x7F:
        cur_line += chr(b)
    elif b >= 0x80:
        s = cur_line.strip()
        if s and len(s) > 5:
            all_lines.append(s)
        cur_line = ""

if cur_line.strip() and len(cur_line.strip()) > 5:
    all_lines.append(cur_line.strip())

# Take the 5 main instruction lines (skip very short ones)
instr_lines = [l for l in all_lines if len(l) > 10][:5]

lines_text = ["# @-terminated instruction text strings read from Z80 memory $5D40-$5E7F"]
lines_text.append("INSTR_TEXT_ROWS = [")
for line in instr_lines:
    line_padded = line.center(64)[:64]
    lines_text.append(f'    {line_padded!r},')
lines_text.append("]")

# ---------------------------------------------------------------
# Output
# ---------------------------------------------------------------
out = '\n'.join(lines_pano) + '\n\n' + '\n'.join(lines_text) + '\n'
# Write to stdout
sys.stdout.write(out)


with open('arcbomb1.cmd', 'rb') as f:
    raw = f.read()

mem = {}
pos = 0
blocks = []
while pos < len(raw) - 3:
    rec_type = raw[pos]
    if rec_type == 0x05:
        length = raw[pos+1]
        pos += 2 + length
    elif rec_type == 0x02:
        length = raw[pos+1]
        if length in (0, 2, 3):
            pos += 4
        else:
            pos += 1
    elif rec_type == 0x01:
        length = raw[pos+1]
        if length == 0:
            length = 256
        addr = raw[pos+2] | (raw[pos+3] << 8)
        if 0x4000 <= addr <= 0x8000 and pos + 4 + length <= len(raw):
            block = raw[pos+4:pos+4+length]
            blocks.append((addr, length, pos))
            for i, b in enumerate(block):
                mem[addr+i] = b
            # Overlapping block check: last 2 data bytes may be next header
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

# ---------------------------------------------------------------
# Parse the @-terminated instruction text strings from $5D40-$5E80
# ---------------------------------------------------------------
STREAM_START = 0x5D40
STREAM_END   = 0x5E80

# Find all @-separated text strings
stream = [mem.get(STREAM_START + i, 0x80) for i in range(STREAM_END - STREAM_START)]
strings = []
cur = []
for b in stream:
    if b == 0x40:   # '@' = terminator
        if cur:
            strings.append(bytes(cur).decode('ascii', errors='replace'))
            cur = []
    elif b >= 0x20 and b < 0x80:
        cur.append(b)
    else:
        # Semigraphic or other non-text — separate text sections
        if cur:
            strings.append(bytes(cur).decode('ascii', errors='replace'))
            cur = []
        if b >= 0x80:
            break  # hit graphics area

# Output the text strings we found
print("# Instruction text strings (@ terminated), from $5D40-$5E80", file=sys.stderr)
for i, s in enumerate(strings):
    print(f"#   [{i}]: {s!r}", file=sys.stderr)

# ---------------------------------------------------------------
# Output INSTR_SCREEN_DATA: the 10-row × 64-col panorama ($5E00-$6040)
# Rows 0-1: text lines (used for display text)
# Rows 2-9: semigraphic score table graphics
# ---------------------------------------------------------------
PANO_START = 0x5E00
PANO_ROWS  = 10       # 10 × 64 = 640 bytes

print("# Instructions panorama data extracted from arcbomb1.cmd")
print("# 10 rows × 64 bytes per row = initial 640 bytes of the instructions scroll buffer")
print("# Source address $5E00 in Z80 RAM")
print("INSTR_SCREEN_DATA = bytes([")
for row in range(PANO_ROWS):
    chunk = [mem.get(PANO_START + row*64 + c, 0x80) for c in range(64)]
    vals = ', '.join(f'0x{b:02X}' for b in chunk)
    asc = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
    print(f'    {vals},  # row {row:2d}  |{asc}|')
print("])")

# ---------------------------------------------------------------
# Output INSTR_TEXT_ROWS: the 5 instruction lines derived from the text stream
# ---------------------------------------------------------------
# Map the @ strings to the 5 canonical text rows
text_stream_raw = []
addr = STREAM_START
while addr < STREAM_END:
    b = mem.get(addr, 0x80)
    if b < 0x80:
        text_stream_raw.append(b)
    addr += 1
    if addr >= STREAM_END or mem.get(addr, 0x80) >= 0x80:
        break

# Concatenate the full ASCII text stream
full_text = bytes([b for b in [mem.get(STREAM_START + i, 0x80) for i in range(STREAM_END - STREAM_START)] if b < 0x80 or b == 0x40])
full_text_str = full_text.decode('ascii', errors='replace')

print()
print("# Instruction text lines (5 rows for on-screen display)")
print("# Derived from @-terminated strings in Z80 memory $5D40-$5E80")
# Split on '@' and take meaningful non-empty parts
all_lines = []
cur_line = ""
first_non_code = False
for addr in range(STREAM_START, STREAM_END):
    b = mem.get(addr, 0x80)
    if b == 0x40:  # '@'
        line = cur_line.strip()
        if line and len(line) > 5:
            all_lines.append(line)
        cur_line = ""
    elif 0x20 <= b <= 0x7F:
        cur_line += chr(b)
    elif b >= 0x80:
        if cur_line.strip() and len(cur_line.strip()) > 5:
            all_lines.append(cur_line.strip())
        cur_line = ""

if cur_line.strip() and len(cur_line.strip()) > 5:
    all_lines.append(cur_line.strip())

print("INSTR_TEXT_ROWS = [")
for line in all_lines[:6]:  # up to 6 instruction lines
    line_centered = line.center(64) if len(line) < 64 else line[:64]
    print(f"    {line_centered!r},")
print("]")
