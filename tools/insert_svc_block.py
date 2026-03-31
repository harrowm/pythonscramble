#!/usr/bin/env python3
"""
Insert the SVC block disassembly into scramble_disassembly.asm.
Inserts between the header and the INSTRUCTIONS SCREEN DATA section.
"""

import os

ASM_FILE = os.path.join(os.path.dirname(__file__), '..', 'scramble_disassembly.asm')
SVC_FILE = '/tmp/svc_block.asm'

with open(ASM_FILE, 'r') as f:
    asm_lines = f.readlines()

with open(SVC_FILE, 'r') as f:
    svc_text = f.read()

# Remove the trailing "Disassembly complete" comment line from svc output
svc_lines = [ln for ln in svc_text.splitlines(keepends=True)
             if not ln.startswith('; Disassembly complete')]

# Find insertion point: the line that starts the INSTRUCTIONS SCREEN DATA section
MARKER = '; INSTRUCTIONS SCREEN DATA  ($5E00-$60AF)'
insert_idx = None
for i, line in enumerate(asm_lines):
    if MARKER in line:
        # We want to insert *before* the blank line + '====...' that precedes it
        # Walk back to find the separator line
        j = i - 1
        while j >= 0 and asm_lines[j].strip() == '':
            j -= 1
        if asm_lines[j].strip().startswith(';') and '===' in asm_lines[j]:
            insert_idx = j  # insert before the separator
        else:
            insert_idx = i  # fallback: insert at the marker line itself
        break

if insert_idx is None:
    raise RuntimeError(f"Could not find marker: {MARKER!r}")

print(f"Inserting {len(svc_lines)} lines at line {insert_idx+1}")

# Build the section header wrapping the SVC block
header = [
    '\n',
    '; ====================================================================\n',
    '; SVC BLOCK  ($5800-$5DFF)\n',
    '; ====================================================================\n',
    '; Game-supplied LDOS SVC stubs, jump table, and implementation routines.\n',
    '; Loaded from ARCBOMB1.CMD into RAM at $5800.\n',
    '; ====================================================================\n',
    '\n',
]

footer = [
    '\n',
]

insert_content = header + svc_lines + footer

new_lines = asm_lines[:insert_idx] + insert_content + asm_lines[insert_idx:]

with open(ASM_FILE, 'w') as f:
    f.writelines(new_lines)

print(f"Done. {ASM_FILE} now has {len(new_lines)} lines.")
