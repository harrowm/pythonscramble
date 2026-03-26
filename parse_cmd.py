"""
Parse ALL CMD records from arcbomb1.cmd and dump the full memory image.
TRS-80 CMD: type 0x01 = load block [01][len][lo][hi][data...]
            type 0x02 = entry point [02][02][lo][hi]  OR  [02][00][lo][hi]
            type 0x05 = module name [05][len][name...]
Other types are skipped byte-by-byte.
"""

with open('arcbomb1.cmd', 'rb') as f:
    raw = f.read()

mem = {}
pos = 0
blocks = []
while pos < len(raw) - 3:
    rec_type = raw[pos]
    if rec_type == 0x05:
        length = raw[pos+1]
        name = raw[pos+2:pos+2+length].decode('ascii', errors='replace')
        print(f'Module name at {pos}: {name!r}')
        pos += 2 + length
    elif rec_type == 0x02:
        length = raw[pos+1]
        if length in (0, 2, 3):
            addr = raw[pos+2] | (raw[pos+3] << 8)
            print(f'Entry point at {pos}: ${addr:04X}')
            pos += 4
        else:
            pos += 1
    elif rec_type == 0x01:
        length = raw[pos+1]
        if length == 0:
            length = 256
        addr = raw[pos+2] | (raw[pos+3] << 8)
        # Accept any plausible Z80 address
        if 0x4000 <= addr <= 0x8000 and pos + 4 + length <= len(raw):
            block = raw[pos+4:pos+4+length]
            blocks.append((addr, length, pos))
            for i, b in enumerate(block):
                mem[addr+i] = b
            # Check for overlapping block header: the last 2 data bytes may serve
            # as the first 2 bytes of the next block's header (CMD overlapping encoding).
            # If so, advance by (length+2) instead of (length+4) to stay in sync.
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

print(f'\nLoaded {len(mem)} bytes across {len(blocks)} blocks')
if mem:
    print(f'Range: ${min(mem):04X}-${max(mem):04X}')

# Show ALL blocks
print('\nAll blocks:')
for addr, length, fpos in sorted(blocks, key=lambda x: x[2]):
    end = addr + length - 1
    marker = ' <-- instr' if end >= 0x5E00 and addr < 0x60B0 else ''
    print(f'  ${addr:04X}-${end:04X}  ({length:4d}b)  file offset {fpos}{marker}')

# Dump bytes around the gap boundaries
print('\n--- Gap boundary dumps ---')
for label, start, end in [
    ('after $5D80 block + before $5E80 block', 1593, 1640),
    ('after $5E80 block + before $5F80 block', 1857, 1910),
    ('after $5C80 block + before $5D80 block', 1329, 1380),
]:
    print(f'\n{label} (file {start}-{end}):')
    for i in range(start, end+1, 16):
        row = raw[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in row)
        asc = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in row)
        print(f'  {i:5d}: {hex_part}  |{asc}|')
for i in range(1330, 1481, 16):
    row = raw[i:i+16]
    hex_part = ' '.join(f'{b:02X}' for b in row)
    asc = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in row)
    print(f'  {i:5d}: {hex_part}  |{asc}|')

# Show what each CMD block actually occupies in THE FILE  
print('\n--- File-offset coverage ---')
for addr, length, fpos in sorted(blocks, key=lambda x: x[2]):
    end = addr + length - 1
    fend = fpos + 3 + length
    print(f'  file {fpos:5d}-{fend:5d}  ${addr:04X}-${end:04X}')
SIZE = 0x02B0  # $60B0 - $5E00
for row_idx in range(SIZE // 64):
    base = 0x5E00 + row_idx * 64
    chunk = [mem.get(base+c, 0xFF) for c in range(64)]
    present = sum(1 for b in chunk if b != 0xFF)
    asc = ''.join(chr(b) if 0x20 <= b < 0x7F else ('.' if b != 0xFF else '?') for b in chunk)
    hex_part = ' '.join(f'{b:02X}' for b in chunk[:32])
    print(f'row{row_idx:02d} ${base:04X} ({present}/64): {hex_part} |{asc[:32]}|')

# ---- Also show $5D00-$5E80 to see the full instructions text ----
print('\n--- $5D00-$5E80 dump (instructions text area) ---')
for base in range(0x5D00, 0x5E80, 64):
    chunk = [mem.get(base+c, 0xFF) for c in range(64)]
    asc = ''.join(chr(b) if 0x20 <= b < 0x7F else ('.' if b != 0xFF else '?') for b in chunk)
    present = sum(1 for b in chunk if b != 0xFF)
    hex_s = ' '.join(f'{b:02X}' for b in chunk[:16])
    print(f'${base:04X} ({present}/64): {hex_s}...  |{asc}|')


# The Z80 game blits bytes $5E00-$61FF (1024 bytes) to VRAM for the
# initial instructions screen display.
print('\n# ---- INSTR_SCREEN_DATA (1024 bytes: $5E00-$61FF) ----')
print('INSTR_SCREEN_DATA = bytes([')
for row in range(16):
    chunk = [mem.get(0x5E00 + row*64 + c, 0x80) for c in range(64)]
    vals = ', '.join(f'0x{b:02X}' for b in chunk)
    asc = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in chunk)
    print(f'    {vals},  # row {row:2d}  |{asc}|')
print('])')

targets = [b'TO MOVE', b'SIMULTANEOUSLY', b'MACHINE GUN', b'DROP BOMB',
           b'FIGHTERS', b'BLIMPS', b'BONUS LIFE', b'PRESS']
for t in targets:
    idx = raw.find(t)
    if idx >= 0:
        ctx = raw[idx:idx+20]
        asc = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in ctx)
        print(f'  {t!r:20s} at file offset {idx:5d}  |{asc}|')



