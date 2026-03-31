"""
Disassemble the SVC_KEYBOARD ($59DD) and SVC_KEYBOARD2 ($59CB) routines
from the TRS-80 memdump, plus surrounding context.
Uses a minimal Z80 disassembler (no external deps).
"""

import struct

MEMDUMP = "/Users/malcolm/pythonscramble/memdump.bin"

# memdump starts at address $0000
with open(MEMDUMP, "rb") as f:
    mem = bytearray(f.read())

def byte(addr):
    return mem[addr]

def word(addr):
    return mem[addr] | (mem[addr+1] << 8)

def hex2(v):  return f"${v:02X}"
def hex4(v):  return f"${v:04X}"

# Minimal Z80 disassembler — covers enough opcodes for typical SVC routines
def disasm_one(pc):
    """Returns (mnemonic_str, length_in_bytes)"""
    b = byte(pc)

    # CB / DD / ED / FD prefixes
    if b == 0xCB:
        b2 = byte(pc+1)
        ops = {0x7E:"BIT 7,(HL)", 0x46:"BIT 0,(HL)"}
        return ops.get(b2, f"CB {hex2(b2)}"), 2

    if b == 0xED:
        b2 = byte(pc+1)
        if b2 == 0xB0: return "LDIR", 2
        if b2 == 0xB8: return "LDDR", 2
        if b2 == 0x43: return f"LD ({hex4(word(pc+2))}),BC", 4
        if b2 == 0x53: return f"LD ({hex4(word(pc+2))}),DE", 4
        if b2 == 0x63: return f"LD ({hex4(word(pc+2))}),HL", 4
        if b2 == 0x73: return f"LD ({hex4(word(pc+2))}),SP", 4
        if b2 == 0x4B: return f"LD BC,({hex4(word(pc+2))})", 4
        if b2 == 0x5B: return f"LD DE,({hex4(word(pc+2))})", 4
        if b2 == 0x6B: return f"LD HL,({hex4(word(pc+2))})", 4
        if b2 == 0x7B: return f"LD SP,({hex4(word(pc+2))})", 4
        if b2 == 0x47: return "LD I,A", 2
        if b2 == 0x5F: return "LD A,R", 2
        if b2 == 0x57: return "LD A,I", 2
        if b2 == 0xA0: return "LDI", 2
        if b2 == 0xA1: return "CPI", 2
        if b2 == 0xB1: return "CPIR", 2
        return f"ED {hex2(b2)}", 2

    if b == 0xDD:
        b2 = byte(pc+1)
        if b2 == 0x21: return f"LD IX,{hex4(word(pc+2))}", 4
        if b2 == 0x36: return f"LD (IX+{byte(pc+2):+d}),{hex2(byte(pc+3))}", 4
        if b2 == 0x7E: return f"LD A,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x46: return f"LD B,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x4E: return f"LD C,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x56: return f"LD D,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x5E: return f"LD E,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x66: return f"LD H,(IX+{byte(pc+2):+d})", 3
        if b2 == 0x6E: return f"LD L,(IX+{byte(pc+2):+d})", 3
        if b2 == 0xE9: return "JP (IX)", 2
        if b2 == 0x23: return "INC IX", 2
        if b2 == 0x2B: return "DEC IX", 2
        return f"DD {hex2(b2)}", 2

    if b == 0xFD:
        b2 = byte(pc+1)
        if b2 == 0x21: return f"LD IY,{hex4(word(pc+2))}", 4
        if b2 == 0x7E: return f"LD A,(IY+{byte(pc+2):+d})", 3
        if b2 == 0xE9: return "JP (IY)", 2
        return f"FD {hex2(b2)}", 2

    # single-byte
    singles = {
        0x00:"NOP", 0x02:"LD (BC),A", 0x07:"RLCA", 0x08:"EX AF,AF'",
        0x09:"ADD HL,BC", 0x0A:"LD A,(BC)", 0x0F:"RRCA",
        0x12:"LD (DE),A", 0x17:"RLA", 0x18:None,  # JR e  handled below
        0x1A:"LD A,(DE)", 0x1F:"RRA",
        0x22:None, 0x2A:None, 0x32:None, 0x3A:None,  # 16-bit mem ops
        0x27:"DAA", 0x2F:"CPL", 0x37:"SCF", 0x3F:"CCF",
        0x76:"HALT",
        0x80:"ADD A,B", 0x81:"ADD A,C", 0x82:"ADD A,D", 0x83:"ADD A,E",
        0x84:"ADD A,H", 0x85:"ADD A,L", 0x86:"ADD A,(HL)", 0x87:"ADD A,A",
        0x88:"ADC A,B", 0x89:"ADC A,C", 0x8A:"ADC A,D", 0x8B:"ADC A,E",
        0x90:"SUB B", 0x91:"SUB C", 0x92:"SUB D", 0x93:"SUB E",
        0x94:"SUB H", 0x95:"SUB L", 0x96:"SUB (HL)", 0x97:"SUB A",
        0x98:"SBC A,B", 0x99:"SBC A,C",
        0xA0:"AND B", 0xA1:"AND C", 0xA2:"AND D", 0xA3:"AND E",
        0xA4:"AND H", 0xA5:"AND L", 0xA6:"AND (HL)", 0xA7:"AND A",
        0xA8:"XOR B", 0xA9:"XOR C", 0xAA:"XOR D", 0xAB:"XOR E",
        0xAC:"XOR H", 0xAD:"XOR L", 0xAE:"XOR (HL)", 0xAF:"XOR A",
        0xB0:"OR B", 0xB1:"OR C", 0xB2:"OR D", 0xB3:"OR E",
        0xB4:"OR H", 0xB5:"OR L", 0xB6:"OR (HL)", 0xB7:"OR A",
        0xB8:"CP B", 0xB9:"CP C", 0xBA:"CP D", 0xBB:"CP E",
        0xBC:"CP H", 0xBD:"CP L", 0xBE:"CP (HL)", 0xBF:"CP A",
        0xC9:"RET", 0xD9:"EXX", 0xE3:"EX (SP),HL", 0xE9:"JP (HL)",
        0xEB:"EX DE,HL", 0xF3:"DI", 0xFB:"EI", 0xF9:"LD SP,HL",
        0x02:"LD (BC),A",
    }

    # Register-based LD r,r  ($40-$7F)
    regs = ["B","C","D","E","H","L","(HL)","A"]
    if 0x40 <= b <= 0x7F and b != 0x76:
        dst = regs[(b-0x40)>>3]
        src = regs[b&7]
        return f"LD {dst},{src}", 1

    # INC/DEC r  ($04/$05, $0C/$0D, $14/$15, $1C/$1D, $24/$25, $2C/$2D, $34/$35, $3C/$3D)
    pairs8 = {0x04:"INC B",0x05:"DEC B",0x0C:"INC C",0x0D:"DEC C",
              0x14:"INC D",0x15:"DEC D",0x1C:"INC E",0x1D:"DEC E",
              0x24:"INC H",0x25:"DEC H",0x2C:"INC L",0x2D:"DEC L",
              0x34:"INC (HL)",0x35:"DEC (HL)",0x3C:"INC A",0x3D:"DEC A"}
    if b in pairs8:
        return pairs8[b], 1

    # INC/DEC 16-bit
    pairs16 = {0x03:"INC BC",0x0B:"DEC BC",0x13:"INC DE",0x1B:"DEC DE",
               0x23:"INC HL",0x2B:"DEC HL",0x33:"INC SP",0x3B:"DEC SP"}
    if b in pairs16:
        return pairs16[b], 1

    # PUSH/POP
    pushpop = {0xC1:"POP BC",0xD1:"POP DE",0xE1:"POP HL",0xF1:"POP AF",
               0xC5:"PUSH BC",0xD5:"PUSH DE",0xE5:"PUSH HL",0xF5:"PUSH AF"}
    if b in pushpop:
        return pushpop[b], 1

    # LD r,n  — immediate byte to register
    ld_imm = {0x06:"LD B", 0x0E:"LD C", 0x16:"LD D", 0x1E:"LD E",
              0x26:"LD H", 0x2E:"LD L", 0x36:"LD (HL)", 0x3E:"LD A"}
    if b in ld_imm:
        return f"{ld_imm[b]},{hex2(byte(pc+1))}", 2

    # LD rr,nn
    ld_imm16 = {0x01:"LD BC", 0x11:"LD DE", 0x21:"LD HL", 0x31:"LD SP"}
    if b in ld_imm16:
        return f"{ld_imm16[b]},{hex4(word(pc+1))}", 3

    # LD A,(nn) / LD (nn),A  / LD HL,(nn) / LD (nn),HL
    if b == 0x3A: return f"LD A,({hex4(word(pc+1))})", 3
    if b == 0x32: return f"LD ({hex4(word(pc+1))}),A", 3
    if b == 0x2A: return f"LD HL,({hex4(word(pc+1))})", 3
    if b == 0x22: return f"LD ({hex4(word(pc+1))}),HL", 3

    # CP n
    if b == 0xFE: return f"CP {hex2(byte(pc+1))}", 2
    # AND n / OR n / XOR n / ADD A,n / ADC A,n / SUB n
    if b == 0xE6: return f"AND {hex2(byte(pc+1))}", 2
    if b == 0xF6: return f"OR {hex2(byte(pc+1))}", 2
    if b == 0xEE: return f"XOR {hex2(byte(pc+1))}", 2
    if b == 0xC6: return f"ADD A,{hex2(byte(pc+1))}", 2
    if b == 0xCE: return f"ADC A,{hex2(byte(pc+1))}", 2
    if b == 0xD6: return f"SUB {hex2(byte(pc+1))}", 2
    if b == 0xDE: return f"SBC A,{hex2(byte(pc+1))}", 2

    # JP nn / CALL nn / RET cc / JP cc,nn / CALL cc,nn
    jp_cc = {0xC2:"JP NZ", 0xCA:"JP Z", 0xD2:"JP NC", 0xDA:"JP C",
             0xE2:"JP PO", 0xEA:"JP PE", 0xF2:"JP P", 0xFA:"JP M"}
    if b in jp_cc: return f"{jp_cc[b]},{hex4(word(pc+1))}", 3
    if b == 0xC3: return f"JP {hex4(word(pc+1))}", 3
    if b == 0xCD: return f"CALL {hex4(word(pc+1))}", 3

    call_cc = {0xC4:"CALL NZ", 0xCC:"CALL Z", 0xD4:"CALL NC", 0xDC:"CALL C",
               0xE4:"CALL PO", 0xEC:"CALL PE", 0xF4:"CALL P", 0xFC:"CALL M"}
    if b in call_cc: return f"{call_cc[b]},{hex4(word(pc+1))}", 3

    ret_cc = {0xC0:"RET NZ", 0xC8:"RET Z", 0xD0:"RET NC", 0xD8:"RET C",
              0xE0:"RET PO", 0xE8:"RET PE", 0xF0:"RET P", 0xF8:"RET M"}
    if b in ret_cc: return ret_cc[b], 1

    # JR e (signed relative)
    if b == 0x18:
        e = byte(pc+1)
        if e >= 0x80: e -= 0x100
        return f"JR {hex4(pc+2+e)}", 2
    jr_cc = {0x20:"JR NZ", 0x28:"JR Z", 0x30:"JR NC", 0x38:"JR C"}
    if b in jr_cc:
        e = byte(pc+1)
        if e >= 0x80: e -= 0x100
        return f"{jr_cc[b]},{hex4(pc+2+e)}", 2

    # DJNZ
    if b == 0x10:
        e = byte(pc+1)
        if e >= 0x80: e -= 0x100
        return f"DJNZ {hex4(pc+2+e)}", 2

    # RST
    if b & 0xC7 == 0xC7:
        return f"RST {hex2(b & 0x38)}", 1

    # IN / OUT
    if b == 0xDB: return f"IN A,({hex2(byte(pc+1))})", 2
    if b == 0xD3: return f"OUT ({hex2(byte(pc+1))}),A", 2

    # RL/RR/SL/SR from {singles}
    if b in singles and singles[b] is not None:
        return singles[b], 1

    return f"DB {hex2(b)}", 1


def disasm_range(start, count=40):
    pc = start
    end = start + count * 3  # upper bound
    n = 0
    while pc < min(end, len(mem)) and n < count:
        mnem, length = disasm_one(pc)
        raw = " ".join(f"{mem[pc+i]:02X}" for i in range(length))
        print(f"  ${pc:04X}  {raw:<12}  {mnem}")
        pc += length
        n += 1
    return pc


# ---- Disassemble both keyboard SVC routines ----
print("=" * 60)
print("SVC_KEYBOARD2  at $59CB  (called via $5806 JP $59CB)")
print("=" * 60)
disasm_range(0x59CB, 50)

print()
print("=" * 60)
print("SVC_KEYBOARD   at $59DD  (called via $5803 JP $59DD)")
print("=" * 60)
disasm_range(0x59DD, 60)

# Also show the jump table itself for context
print()
print("=" * 60)
print("SVC jump table  $5800-$580E")
print("=" * 60)
disasm_range(0x5800, 8)

# Show a small peek at the TRS-80 keyboard matrix addresses used
print()
print("Key bytes at keyboard matrix $3800-$3840 from memdump:")
for addr in range(0x3800, 0x3840, 8):
    row = " ".join(f"{mem[addr+i]:02X}" for i in range(8))
    print(f"  ${addr:04X}: {row}")
