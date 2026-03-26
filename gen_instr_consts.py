"""Generate INSTR_SCREEN_DATA and INSTR_TEXT_ROWS for constants.py."""
with open('arcbomb1.cmd', 'rb') as f:
    raw = f.read()

mem = {}
pos = 0
while pos < len(raw) - 3:
    rt = raw[pos]
    if rt == 0x05:
        pos += 2 + raw[pos+1]
    elif rt == 0x02:
        pos += 4 if raw[pos+1] in (0, 2, 3) else 1
    elif rt == 0x01:
        length = raw[pos+1] or 256
        addr = raw[pos+2] | (raw[pos+3] << 8)
        if 0x4000 <= addr <= 0x8000 and pos + 4 + length <= len(raw):
            for i, b in enumerate(raw[pos+4:pos+4+length]):
                mem[addr+i] = b
            nh = pos + 4 + length - 2
            if (nh + 4 <= len(raw) and raw[nh] == 0x01 and raw[nh+3] != 0
                    and 0x4000 <= (raw[nh+2] | (raw[nh+3] << 8)) <= 0x8000):
                pos = nh
            else:
                pos += 4 + length
        else:
            pos += 1
    else:
        pos += 1

NAMES = [
    'FIGHTERS/BLIMPS header row',
    'BOMBER score row',
    'enemy-sprite data row 1',
    'enemy-sprite data row 2',
    'FORT/blimp sprite row',
    '150/FACTORY score row',
    'ROCKET/FUEL TANK row',
    '75/125/ACK-ACK row',
]

print('# ---------------------------------------------------------------------------')
print('# INSTRUCTIONS SCREEN DATA  (extracted from arcbomb1.cmd)')
print('# ---------------------------------------------------------------------------')
print('# Semigraphic score/enemy panorama: 8 rows x 64 bytes from Z80 addr $5E80.')
print('# Displayed in screen rows 5-14 with left-scroll during INSTRUCTIONS state.')
print('INSTR_SCREEN_DATA = bytes([')
for row in range(8):
    chunk = [mem.get(0x5E80 + row * 64 + c, 0x80) for c in range(64)]
    vals = ','.join(f'0x{b:02X}' for b in chunk)
    print(f'    {vals},  # {NAMES[row]}')
print('])')
print()

rows_out = []
cur = ''
for addr in range(0x5D40, 0x5E80):
    b = mem.get(addr, 0x80)
    if b == 0x40:
        s = cur.strip()
        if s and len(s) > 10:
            rows_out.append(s)
        cur = ''
    elif 0x20 <= b <= 0x7F:
        cur += chr(b)
    elif b >= 0x80:
        s = cur.strip()
        if s and len(s) > 10:
            rows_out.append(s)
        cur = ''
rows5 = [r for r in rows_out if len(r) > 10][:5]

print('# Five @-terminated instruction text rows, verbatim from Z80 memory $5D40-$5E7F.')
print('INSTR_TEXT_ROWS = [')
for r in rows5:
    padded = r.center(64)[:64]
    print(f'    {padded!r},')
print(']')
