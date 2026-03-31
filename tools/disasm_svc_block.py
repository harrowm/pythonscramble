#!/usr/bin/env python3
"""
Disassemble the SVC block $5800-$5DFF from memdump.bin.
Produces annotated Z80 assembly listing for insertion into scramble_disassembly.asm.
"""

import sys
import os

MEMDUMP = os.path.join(os.path.dirname(__file__), '..', 'memdump.bin')

# Load memdump - it's a raw memory image starting at $0000
with open(MEMDUMP, 'rb') as f:
    mem = bytearray(f.read())

def read8(addr):
    return mem[addr]

def read16(addr):
    return mem[addr] | (mem[addr+1] << 8)

def signed8(b):
    return b if b < 128 else b - 256

# ---- Z80 disassembler (subset sufficient for this codebase) ----

def reg8(r):
    return ['B','C','D','E','H','L','(HL)','A'][r]

def reg16(r, af=False):
    if af:
        return ['BC','DE','HL','AF'][r]
    return ['BC','DE','HL','SP'][r]

def disasm(addr):
    """Disassemble one instruction at addr. Returns (mnemonic_str, length, next_addr)."""
    op = read8(addr)
    
    # --- CB prefix ---
    if op == 0xCB:
        op2 = read8(addr+1)
        row = (op2 >> 6) & 3
        col = op2 & 7
        bit = (op2 >> 3) & 7
        r = reg8(col)
        ops = ['RLC','RRC','RL','RR','SLA','SRA','SLL','SRL']
        if row == 0:
            return f"{ops[bit]} {r}", 2, addr+2
        elif row == 1:
            return f"BIT {bit},{r}", 2, addr+2
        elif row == 2:
            return f"RES {bit},{r}", 2, addr+2
        else:
            return f"SET {bit},{r}", 2, addr+2

    # --- ED prefix ---
    if op == 0xED:
        op2 = read8(addr+1)
        if op2 == 0xB0: return "LDIR", 2, addr+2
        if op2 == 0xB8: return "LDDR", 2, addr+2
        if op2 == 0xA0: return "LDI",  2, addr+2
        if op2 == 0xA8: return "LDD",  2, addr+2
        if op2 == 0xB1: return "CPIR", 2, addr+2
        if op2 == 0xB9: return "CPDR", 2, addr+2
        if op2 == 0x43: nn = read16(addr+2); return f"LD (${nn:04X}),BC", 4, addr+4
        if op2 == 0x53: nn = read16(addr+2); return f"LD (${nn:04X}),DE", 4, addr+4
        if op2 == 0x63: nn = read16(addr+2); return f"LD (${nn:04X}),HL", 4, addr+4
        if op2 == 0x73: nn = read16(addr+2); return f"LD (${nn:04X}),SP", 4, addr+4
        if op2 == 0x4B: nn = read16(addr+2); return f"LD BC,(${nn:04X})", 4, addr+4
        if op2 == 0x5B: nn = read16(addr+2); return f"LD DE,(${nn:04X})", 4, addr+4
        if op2 == 0x6B: nn = read16(addr+2); return f"LD HL,(${nn:04X})", 4, addr+4
        if op2 == 0x7B: nn = read16(addr+2); return f"LD SP,(${nn:04X})", 4, addr+4
        if op2 == 0x44: return "NEG", 2, addr+2
        if op2 == 0x45: return "RETN", 2, addr+2
        if op2 == 0x4D: return "RETI", 2, addr+2
        if op2 == 0x47: return "LD I,A", 2, addr+2
        if op2 == 0x4F: return "LD R,A", 2, addr+2
        if op2 == 0x57: return "LD A,I", 2, addr+2
        if op2 == 0x5F: return "LD A,R", 2, addr+2
        r = (op2 >> 4) & 3
        if (op2 & 0xCF) == 0x42: return f"SBC HL,{reg16(r)}", 2, addr+2
        if (op2 & 0xCF) == 0x4A: return f"ADC HL,{reg16(r)}", 2, addr+2
        return f"DB $ED,$%02X" % op2, 2, addr+2

    # --- DD prefix (IX) ---
    if op == 0xDD:
        op2 = read8(addr+1)
        if op2 == 0x21: nn = read16(addr+2); return f"LD IX,${nn:04X}", 4, addr+4
        if op2 == 0x22: nn = read16(addr+2); return f"LD (${nn:04X}),IX", 4, addr+4
        if op2 == 0x2A: nn = read16(addr+2); return f"LD IX,(${nn:04X})", 4, addr+4
        if op2 == 0x36: d = signed8(read8(addr+2)); n = read8(addr+3); return f"LD (IX{d:+d}),$%02X" % n, 4, addr+4
        if op2 == 0x46: d = signed8(read8(addr+2)); return f"LD B,(IX{d:+d})", 3, addr+3
        if op2 == 0x4E: d = signed8(read8(addr+2)); return f"LD C,(IX{d:+d})", 3, addr+3
        if op2 == 0x56: d = signed8(read8(addr+2)); return f"LD D,(IX{d:+d})", 3, addr+3
        if op2 == 0x5E: d = signed8(read8(addr+2)); return f"LD E,(IX{d:+d})", 3, addr+3
        if op2 == 0x66: d = signed8(read8(addr+2)); return f"LD H,(IX{d:+d})", 3, addr+3
        if op2 == 0x6E: d = signed8(read8(addr+2)); return f"LD L,(IX{d:+d})", 3, addr+3
        if op2 == 0x7E: d = signed8(read8(addr+2)); return f"LD A,(IX{d:+d})", 3, addr+3
        if op2 == 0x70: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),B", 3, addr+3
        if op2 == 0x71: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),C", 3, addr+3
        if op2 == 0x72: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),D", 3, addr+3
        if op2 == 0x73: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),E", 3, addr+3
        if op2 == 0x74: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),H", 3, addr+3
        if op2 == 0x75: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),L", 3, addr+3
        if op2 == 0x77: d = signed8(read8(addr+2)); return f"LD (IX{d:+d}),A", 3, addr+3
        if op2 == 0x86: d = signed8(read8(addr+2)); return f"ADD A,(IX{d:+d})", 3, addr+3
        if op2 == 0x8E: d = signed8(read8(addr+2)); return f"ADC A,(IX{d:+d})", 3, addr+3
        if op2 == 0x96: d = signed8(read8(addr+2)); return f"SUB (IX{d:+d})", 3, addr+3
        if op2 == 0x9E: d = signed8(read8(addr+2)); return f"SBC A,(IX{d:+d})", 3, addr+3
        if op2 == 0xA6: d = signed8(read8(addr+2)); return f"AND (IX{d:+d})", 3, addr+3
        if op2 == 0xAE: d = signed8(read8(addr+2)); return f"XOR (IX{d:+d})", 3, addr+3
        if op2 == 0xB6: d = signed8(read8(addr+2)); return f"OR (IX{d:+d})", 3, addr+3
        if op2 == 0xBE: d = signed8(read8(addr+2)); return f"CP (IX{d:+d})", 3, addr+3
        if op2 == 0x23: return "INC IX", 2, addr+2
        if op2 == 0x2B: return "DEC IX", 2, addr+2
        if op2 == 0xE1: return "POP IX", 2, addr+2
        if op2 == 0xE5: return "PUSH IX", 2, addr+2
        if op2 == 0xE9: return "JP (IX)", 2, addr+2
        return f"DB $DD,$%02X" % op2, 2, addr+2

    # --- FD prefix (IY) ---
    if op == 0xFD:
        op2 = read8(addr+1)
        if op2 == 0x21: nn = read16(addr+2); return f"LD IY,${nn:04X}", 4, addr+4
        if op2 == 0x2A: nn = read16(addr+2); return f"LD IY,(${nn:04X})", 4, addr+4
        if op2 == 0x7E: d = signed8(read8(addr+2)); return f"LD A,(IY{d:+d})", 3, addr+3
        if op2 == 0x77: d = signed8(read8(addr+2)); return f"LD (IY{d:+d}),A", 3, addr+3
        if op2 == 0x23: return "INC IY", 2, addr+2
        if op2 == 0x2B: return "DEC IY", 2, addr+2
        if op2 == 0xE1: return "POP IY", 2, addr+2
        if op2 == 0xE5: return "PUSH IY", 2, addr+2
        if op2 == 0xE9: return "JP (IY)", 2, addr+2
        return f"DB $FD,$%02X" % op2, 2, addr+2

    # --- single-byte and two/three-byte main opcodes ---
    n  = read8(addr+1)   if len(mem) > addr+1 else 0
    nn = read16(addr+1)  if len(mem) > addr+2 else 0
    d  = signed8(n)

    # NOP
    if op == 0x00: return "NOP", 1, addr+1
    # HALT
    if op == 0x76: return "HALT", 1, addr+1
    # RET
    if op == 0xC9: return "RET", 1, addr+1
    # RLCA/RRCA/RLA/RRA
    if op == 0x07: return "RLCA", 1, addr+1
    if op == 0x0F: return "RRCA", 1, addr+1
    if op == 0x17: return "RLA",  1, addr+1
    if op == 0x1F: return "RRA",  1, addr+1
    # CPL/CCF/SCF/DAA
    if op == 0x2F: return "CPL",  1, addr+1
    if op == 0x3F: return "CCF",  1, addr+1
    if op == 0x37: return "SCF",  1, addr+1
    if op == 0x27: return "DAA",  1, addr+1
    # EX DE,HL / EX AF,AF' / EXX
    if op == 0xEB: return "EX DE,HL", 1, addr+1
    if op == 0x08: return "EX AF,AF'", 1, addr+1
    if op == 0xD9: return "EXX", 1, addr+1
    # EX (SP),HL
    if op == 0xE3: return "EX (SP),HL", 1, addr+1
    # DI/EI
    if op == 0xF3: return "DI", 1, addr+1
    if op == 0xFB: return "EI", 1, addr+1
    # JP (HL)
    if op == 0xE9: return "JP (HL)", 1, addr+1
    # LD SP,HL
    if op == 0xF9: return "LD SP,HL", 1, addr+1

    # LD rr,nn
    if (op & 0xCF) == 0x01:
        r = (op >> 4) & 3
        return f"LD {reg16(r)},${nn:04X}", 3, addr+3
    # LD (nn),A
    if op == 0x32: return f"LD (${nn:04X}),A", 3, addr+3
    # LD A,(nn)
    if op == 0x3A: return f"LD A,(${nn:04X})", 3, addr+3
    # LD HL,(nn)
    if op == 0x2A: return f"LD HL,(${nn:04X})", 3, addr+3
    # LD (nn),HL
    if op == 0x22: return f"LD (${nn:04X}),HL", 3, addr+3
    # LD r,n
    if (op & 0xC7) == 0x06 and op != 0x76:
        r = (op >> 3) & 7
        return f"LD {reg8(r)},$%02X" % n, 2, addr+2
    # LD r,r'
    if (op & 0xC0) == 0x40 and op != 0x76:
        dst = (op >> 3) & 7
        src = op & 7
        return f"LD {reg8(dst)},{reg8(src)}", 1, addr+1
    # LD A,(BC) / LD A,(DE)
    if op == 0x0A: return "LD A,(BC)", 1, addr+1
    if op == 0x1A: return "LD A,(DE)", 1, addr+1
    # LD (BC),A / LD (DE),A
    if op == 0x02: return "LD (BC),A", 1, addr+1
    if op == 0x12: return "LD (DE),A", 1, addr+1

    # INC/DEC r
    if (op & 0xC7) == 0x04 and op != 0x34: # INC r (not INC (HL))
        r = (op >> 3) & 7
        return f"INC {reg8(r)}", 1, addr+1
    if op == 0x34: return "INC (HL)", 1, addr+1
    if (op & 0xC7) == 0x05 and op != 0x35: # DEC r
        r = (op >> 3) & 7
        return f"DEC {reg8(r)}", 1, addr+1
    if op == 0x35: return "DEC (HL)", 1, addr+1
    # INC/DEC rr
    if (op & 0xCF) == 0x03:
        r = (op >> 4) & 3
        return f"INC {reg16(r)}", 1, addr+1
    if (op & 0xCF) == 0x0B:
        r = (op >> 4) & 3
        return f"DEC {reg16(r)}", 1, addr+1

    # ADD/ADC/SUB/SBC/AND/XOR/OR/CP A,r
    alu = ['ADD A','ADC A','SUB','SBC A','AND','XOR','OR','CP']
    if (op & 0xC0) == 0x80:
        op2 = (op >> 3) & 7
        src = op & 7
        return f"{alu[op2]} {reg8(src)}", 1, addr+1
    # ADD/ADC/SUB/SBC/AND/XOR/OR/CP A,n
    if (op & 0xC7) == 0xC6:
        op2 = (op >> 3) & 7
        return f"{alu[op2]} $%02X" % n, 2, addr+2

    # ADD HL,rr
    if (op & 0xCF) == 0x09:
        r = (op >> 4) & 3
        return f"ADD HL,{reg16(r)}", 1, addr+1

    # PUSH/POP
    if (op & 0xCF) == 0xC5:
        r = (op >> 4) & 3
        return f"PUSH {reg16(r,af=True)}", 1, addr+1
    if (op & 0xCF) == 0xC1:
        r = (op >> 4) & 3
        return f"POP {reg16(r,af=True)}", 1, addr+1

    # CALL / CALL cc
    if op == 0xCD: return f"CALL ${nn:04X}", 3, addr+3
    cond = ['NZ','Z','NC','C','PO','PE','P','M']
    if (op & 0xC7) == 0xC4:
        cc = (op >> 3) & 7
        return f"CALL {cond[cc]},${nn:04X}", 3, addr+3

    # RET cc
    if (op & 0xC7) == 0xC0:
        cc = (op >> 3) & 7
        return f"RET {cond[cc]}", 1, addr+1

    # JP / JP cc
    if op == 0xC3: return f"JP ${nn:04X}", 3, addr+3
    if (op & 0xC7) == 0xC2:
        cc = (op >> 3) & 7
        return f"JP {cond[cc]},${nn:04X}", 3, addr+3

    # JR / JR cc
    if op == 0x18:
        target = (addr+2 + d) & 0xFFFF
        return f"JR ${target:04X}", 2, addr+2
    jr_cond = {0x20:'NZ', 0x28:'Z', 0x30:'NC', 0x38:'C'}
    if op in jr_cond:
        target = (addr+2 + d) & 0xFFFF
        return f"JR {jr_cond[op]},${target:04X}", 2, addr+2

    # DJNZ
    if op == 0x10:
        target = (addr+2 + d) & 0xFFFF
        return f"DJNZ ${target:04X}", 2, addr+2

    # CALL nn (already above) / RST
    if (op & 0xC7) == 0xC7:
        p = op & 0x38
        return f"RST ${p:02X}H", 1, addr+1

    # IN A,(n) / OUT (n),A
    if op == 0xDB: return f"IN A,($%02X)" % n, 2, addr+2
    if op == 0xD3: return f"OUT ($%02X),A" % n, 2, addr+2

    # default: DB
    return f"DB ${op:02X}", 1, addr+1


# ---- Known labels in this region ----
LABELS = {
    0x5800: 'svc_jump_table',
    0x5803: 'SVC_CLR_BUF',
    0x5806: 'SVC_DRAW_TITLE_FRAME',
    0x5809: 'SVC_MISC',
    0x580C: 'SVC_MISC2',
    0x580F: 'fn_svc_display',
    0x59CB: 'fn_draw_title_frame',
    0x59D4: 'fn_draw_splash_composite',
    0x59DD: 'fn_clear_splash_buffer',
    0x59EB: 'fn_draw_border',
    0x5A28: 'fn_copy_title_strings',
    0x5A4D: 'fn_copy_until_at',
    0x5A56: 'fn_draw_title_graphics',
    0x5ADC: 'fn_draw_top_five_box',
    0x5B6C: 'str_kansas_software',
    0x5B80: 'str_press_i_for_instr',
    0x5BAF: 'str_copyright',
    0x5BD3: 'str_top_five',
    0x5C00: 'data_svc_5C00',
    0x5D2E: 'fn_svc_misc2_impl',
    0x5D6A: 'fn_copy_until_at_2',
    0x5D73: 'str_misc2_controls_1',
    0x5DA7: 'str_misc2_controls_2',
    0x5DDB: 'str_misc2_controls_3',
}

# We'll also add block comments for each major sub-section
BLOCK_COMMENTS = {
    0x5800: """; ====================================================================
; SVC JUMP TABLE  ($5800-$580E)
; ====================================================================
; The game installs 5 SVC vectors in the LDOS SVC table.
; Each is a 3-byte JP instruction that vectors into the implementation code below.
; ====================================================================
""",
    0x580F: """; ====================================================================
; fn_svc_display  ($580F)
; Wipes/animates the transition before blitting back-buffer to VRAM.
; Called as: CALL $5800
; ====================================================================
""",
    0x59CB: """; ====================================================================
; fn_draw_title_frame  ($59CB)
; Clears back-buffer, draws semigraphic box border, copies title strings.
; Called as: CALL $5806  (SVC_DRAW_TITLE_FRAME)
; ====================================================================
""",
    0x59D4: """; ====================================================================
; fn_draw_splash_composite  ($59D4)
; Calls fn_clear_splash_buffer + fn_draw_title_graphics + fn_draw_top_five_box.
; Called as: CALL $5809  (SVC_MISC)
; ====================================================================
""",
    0x59DD: """; ====================================================================
; fn_clear_splash_buffer  ($59DD)
; Fills $5400-$57FF with $80 (blank semigraphic) using LDIR.
; Called as: CALL $5803 (SVC_CLR_BUF) or internally.
; ====================================================================
""",
    0x59EB: """; ====================================================================
; fn_draw_border  ($59EB)
; Draws semigraphic box border into back-buffer:
;   Row  0  (offset $5400 + 0*64 = $5400): fill with $84 (top-bar chars)
;   Row 15  (offset $5400 + 15*64 = $5600+): fill with $81 (bottom-bar)
;   Left/right cols: fill with $85 (side-bar)
; ====================================================================
""",
    0x5A28: """; ====================================================================
; fn_copy_title_strings  ($5A28)
; Copies @-terminated strings from embedded data into specific
; back-buffer positions for the title screen layout.
; ====================================================================
""",
    0x5A4D: """; ====================================================================
; fn_copy_until_at  ($5A4D)
; Copies bytes from (HL) to (DE) until byte == $40 ('@') is found.
; Advances HL and DE past the string. $40 is NOT copied (terminator).
; ====================================================================
""",
    0x5A56: """; ====================================================================
; fn_draw_title_graphics  ($5A56)
; Blits the composed title art (big "Arcade Bomber SCRAMBLE" semigraphic
; letters) and text strings into the back-buffer at $5400.
; String data lives at $5B6C, $5B80, $5BAF, $5BD3 (below).
; ====================================================================
""",
    0x5ADC: """; ====================================================================
; fn_draw_top_five_box  ($5ADC)
; Draws the "*TOP FIVE*" score-table border box in the top-right corner
; of the back-buffer (rows 0-7, cols 46-63).
; Uses: $B0 (top bar), $83 (bottom bar), $BF (solid block) chars.
; String "* TOP FIVE *" from $5BD3.
; ====================================================================
""",
    0x5B6C: """; ====================================================================
; Embedded title-screen string data  ($5B6C-$5BFF)
; @-terminated ASCII strings used by fn_draw_title_graphics and
; fn_draw_top_five_box to build the back-buffer.
; ====================================================================
""",
    0x5D2E: """; ====================================================================
; fn_svc_misc2_impl  ($5D2E)
; SVC_MISC2 implementation.  Called as: CALL $580C
; Clears back-buffer then copies 5 @-terminated control strings + one
; raw block (552 bytes from $5E7F) into specific back-buffer positions.
; Used to build the "controls" help screen in the back-buffer.
; ====================================================================
""",
    0x5D6A: """; fn_copy_until_at_2  ($5D6A)  -- local copy-until-@ (same logic as $5A4D)
""",
    0x5D73: """; ====================================================================
; fn_svc_misc2 embedded string data  ($5D73-$5DFF)
; @-terminated ASCII strings describing game controls.
; Copied into the splash back-buffer by fn_svc_misc2_impl above.
; ====================================================================
""",
    0x5E00: "",
}

# Data regions (not disassembled as code - emit as DB blocks)
# Format: (start, end_exclusive, label_hint)
DATA_REGIONS = [
    (0x5B6C, 0x5C00, 'title_string_data'),
    (0x5C00, 0x5D2E, 'svc_data_5C00'),
    (0x5D73, 0x5E00, 'svc_misc2_string_data'),
]

def is_data(addr):
    for (s, e, _) in DATA_REGIONS:
        if s <= addr < e:
            return True
    return False

def data_region_for(addr):
    for (s, e, hint) in DATA_REGIONS:
        if s <= addr < e:
            return s, e, hint
    return None

def bytes_as_db(start, end):
    """Emit raw bytes as DB lines, 16 bytes per line, with ASCII hint."""
    lines = []
    addr = start
    while addr < end:
        chunk = mem[addr:min(addr+16, end)]
        hex_bytes = ','.join(f'${b:02X}' for b in chunk)
        ascii_hint = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        addr_tag = f'; {addr:04X}:'
        lines.append(f"    DB       {hex_bytes:<55} ; {addr_tag} |{ascii_hint}|")
        addr += len(chunk)
    return lines

# ---- Main disassembly loop ----

START = 0x5800
END   = 0x5E00   # stop before instruction data region

lines = []
addr = START

# Track which data regions we've emitted
emitted_data_starts = set()

while addr < END:
    # emit block comment if any
    if addr in BLOCK_COMMENTS:
        lines.append('')
        lines.append(BLOCK_COMMENTS[addr].rstrip())
        lines.append('')

    # emit label if any
    if addr in LABELS:
        lbl = LABELS[addr]
        lines.append(f'{lbl}:   ; ${addr:04X}')

    # check if this is a data region
    if is_data(addr):
        region = data_region_for(addr)
        rs, re, hint = region
        if rs not in emitted_data_starts:
            emitted_data_starts.add(rs)
            lines.append(f'    ; --- embedded data: {hint} ---')
            db_lines = bytes_as_db(rs, re)
            lines.extend(db_lines)
        addr = re
        continue

    # disassemble instruction
    mnem, length, next_addr = disasm(addr)
    
    # build raw bytes string
    raw = ' '.join(f'{mem[addr+i]:02X}' for i in range(length))
    
    # build annotated line
    line = f"    {mnem:<35} ; {addr:04X}: {raw}"
    lines.append(line)
    
    addr = next_addr

print('\n'.join(lines))
print()
print(f'; Disassembly complete: ${START:04X}-${END:04X}')
