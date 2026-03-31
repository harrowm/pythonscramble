#!/usr/bin/env python3
"""
Annotate fn_svc_display ($580F-$59CA) in scramble_disassembly.asm.

This function is the screen-wipe/transition animation.  It has 4 modes
selected pseudo-randomly from LD A,R.  We insert comments and labels
for each mode, the self-modifying delay cell, and the shared sub-routines.
"""

import re

ASM = "/Users/malcolm/pythonscramble/scramble_disassembly.asm"

with open(ASM, "r") as f:
    text = f.read()

# -----------------------------------------------------------------------
# 1.  Expand the header comment above fn_svc_display
# -----------------------------------------------------------------------
OLD_HEADER = """; Wipes/animates the transition before blitting back-buffer to VRAM.
; Called as: CALL $5800
; ====================================================================

fn_svc_display:   ; $580F
    LD A,R                              ; 580F: ED 5F
    AND $03                             ; 5811: E6 03
    CP $00                              ; 5813: FE 00
    JP Z,$5825                          ; 5815: CA 25 58
    CP $01                              ; 5818: FE 01
    JP Z,$582A                          ; 581A: CA 2A 58
    CP $03                              ; 581D: FE 03
    JP Z,$5907                          ; 581F: CA 07 59
    JP $5982                            ; 5822: C3 82 59"""

NEW_HEADER = """; Wipes/animates the screen transition before blitting back-buffer to VRAM.
; Called via CALL $5800 (SVC_DISPLAY vector).
;
; Reads the pseudo-random Z80 R register (low 2 bits) to pick one of
; four animation styles:
;   R&3 == 0  → svc_wipe_spiral_fast  ($5825): inward-spiral of $BF blocks,
;                                               slow delay (BC=$004B per step)
;   R&3 == 1  → svc_wipe_spiral_slow  ($582A): same spiral, fast delay (BC=$0005)
;   R&3 == 2  → svc_wipe_scroll_down  ($5982): scroll back-buffer into VRAM 16 rows
;                                               at a time with a per-row blit
;   R&3 == 3  → svc_wipe_curtain      ($5907): LDIR+LDDR "curtain" wipe from both
;                                               ends of VRAM, then blit $5600 data
;
; Sub-routines used within:
;   svc_delay_bc  ($58E2)  — call ROM delay ($0060) with BC = self-modified value
;   svc_sound_row ($58EC)  — OUT $FF pulse: C outer × (B_on + B_off) inner loops
;   svc_delay_1s  ($595D)  — fixed 1000-iteration ROM delay
;   svc_sound_col ($5968)  — longer audio pulse (C=12 pairs of B=12/15 loops)
;   svc_sound_scr ($59B3)  — short audio pulse keyed to D/E scroll counters
;
; Self-modifying cell:
;   $5905-$5906  — written by svc_wipe_spiral with the 16-bit delay count;
;                  read back as BC by "LD BC,($5905)" inside svc_delay_bc.
; ====================================================================

fn_svc_display:   ; $580F
    LD A,R                              ; 580F: ED 5F  ; pseudo-random from refresh register
    AND $03                             ; 5811: E6 03  ; keep low 2 bits → 0..3
    CP $00                              ; 5813: FE 00
    JP Z,$5825                          ; 5815: CA 25 58  ; → svc_wipe_spiral_fast
    CP $01                              ; 5818: FE 01
    JP Z,$582A                          ; 581A: CA 2A 58  ; → svc_wipe_spiral_slow
    CP $03                              ; 581D: FE 03
    JP Z,$5907                          ; 581F: CA 07 59  ; → svc_wipe_curtain
    JP $5982                            ; 5822: C3 82 59  ; → svc_wipe_scroll_down (R&3==2)"""

assert OLD_HEADER in text, "Header not found - check exact whitespace"
text = text.replace(OLD_HEADER, NEW_HEADER, 1)

# -----------------------------------------------------------------------
# 2.  Label and comment the two spiral entry points ($5825 / $582A)
#     and the shared setup code at $582D
# -----------------------------------------------------------------------
OLD_SPIRAL_ENTRY = """    LD HL,$004B                         ; 5825: 21 4B 00
    JR $582D                            ; 5828: 18 03
    LD HL,$0005                         ; 582A: 21 05 00
    LD ($5905),HL                       ; 582D: 22 05 59
    LD HL,$3BFF                         ; 5830: 21 FF 3B
    LD D,$40                            ; 5833: 16 40
    LD E,$0F                            ; 5835: 1E 0F
    LD B,D                              ; 5837: 42
    INC HL                              ; 5838: 23
    LD (HL),$BF                         ; 5839: 36 BF
    CALL $58E2                          ; 583B: CD E2 58
    DJNZ $5838                          ; 583E: 10 F8
    CALL $58EC                          ; 5840: CD EC 58
    LD B,E                              ; 5843: 43
    PUSH BC                             ; 5844: C5
    LD BC,$0040                         ; 5845: 01 40 00
    ADD HL,BC                           ; 5848: 09
    LD (HL),$BF                         ; 5849: 36 BF
    POP BC                              ; 584B: C1
    CALL $58E2                          ; 584C: CD E2 58
    DJNZ $5844                          ; 584F: 10 F3
    CALL $58EC                          ; 5851: CD EC 58
    DEC D                               ; 5854: 15
    DEC E                               ; 5855: 1D
    LD B,D                              ; 5856: 42
    DEC HL                              ; 5857: 2B
    LD (HL),$BF                         ; 5858: 36 BF
    CALL $58E2                          ; 585A: CD E2 58
    DJNZ $5857                          ; 585D: 10 F8
    CALL $58EC                          ; 585F: CD EC 58
    LD A,D                              ; 5862: 7A
    CP $31                              ; 5863: FE 31
    JR Z,$587E                          ; 5865: 28 17
    LD B,E                              ; 5867: 43
    PUSH BC                             ; 5868: C5
    OR A                                ; 5869: B7
    LD BC,$0040                         ; 586A: 01 40 00
    SBC HL,BC                           ; 586D: ED 42
    LD (HL),$BF                         ; 586F: 36 BF
    POP BC                              ; 5871: C1
    CALL $58E2                          ; 5872: CD E2 58
    DJNZ $5868                          ; 5875: 10 F1
    CALL $58EC                          ; 5877: CD EC 58
    DEC D                               ; 587A: 15
    DEC E                               ; 587B: 1D
    JR $5837                            ; 587C: 18 B9
    LD E,$01                            ; 587E: 1E 01"""

NEW_SPIRAL_ENTRY = """; --- svc_wipe_spiral_fast ($5825) ---
; Slow step delay (BC=$004B=75): produces a visually slower spiral fill.
svc_wipe_spiral_fast:   ; $5825
    LD HL,$004B                         ; 5825: 21 4B 00  ; delay count = 75 iterations
    JR $582D                            ; 5828: 18 03     ; → shared setup

; --- svc_wipe_spiral_slow ($582A) ---
; Fast step delay (BC=$0005=5): produces a visually faster spiral fill.
svc_wipe_spiral_slow:   ; $582A
    LD HL,$0005                         ; 582A: 21 05 00  ; delay count = 5 iterations

; --- shared spiral setup ($582D) ---
; HL = delay count is self-written into ($5905) so svc_delay_bc can read it
; as a 16-bit BC value.  HL is then repurposed as the VRAM pointer.
;   D  = column-run length (starts 64, counts inward)
;   E  = row-run length    (starts 15, counts inward)
; The spiral paints $BF (full semigraphic block) one cell at a time,
; working right across the top row, down the right column, left across
; the bottom row, up the left column, then decrements both counters and
; repeats — tracing an inward rectangular spiral until D reaches $31
; (17 layers × 2 steps inward = 34 cols gone, leaving a 30-col-wide core).
    LD ($5905),HL                       ; 582D: 22 05 59  ; self-modify delay cell at $5905-$5906
    LD HL,$3BFF                         ; 5830: 21 FF 3B  ; HL = one byte before VRAM start ($3C00)
    LD D,$40                            ; 5833: 16 40     ; D = 64 (full VRAM row width)
    LD E,$0F                            ; 5835: 1E 0F     ; E = 15 (row count - 1)
; --- spiral top edge: fill D cells rightward with $BF ---
svc_spiral_top:   ; $5837
    LD B,D                              ; 5837: 42        ; B = column run length
.spiral_top_loop:
    INC HL                              ; 5838: 23        ; advance VRAM pointer right
    LD (HL),$BF                         ; 5839: 36 BF     ; paint full-block semigraphic
    CALL $58E2                          ; 583B: CD E2 58  ; svc_delay_bc: inter-pixel delay
    DJNZ .spiral_top_loop              ; 583E: 10 F8     ; repeat for all D columns
    CALL $58EC                          ; 5840: CD EC 58  ; svc_sound_row: audio tick after row
; --- spiral right edge: fill E cells downward (stride +64 per row) ---
    LD B,E                              ; 5843: 43        ; B = row run length
.spiral_right_loop:
    PUSH BC                             ; 5844: C5
    LD BC,$0040                         ; 5845: 01 40 00  ; stride = 64 (one VRAM row)
    ADD HL,BC                           ; 5848: 09        ; advance down one row
    LD (HL),$BF                         ; 5849: 36 BF     ; paint full-block
    POP BC                              ; 584B: C1
    CALL $58E2                          ; 584C: CD E2 58  ; inter-pixel delay
    DJNZ .spiral_right_loop            ; 584F: 10 F3
    CALL $58EC                          ; 5851: CD EC 58  ; svc_sound_row audio tick
; --- contract: inward one step, then fill bottom and left edges ---
    DEC D                               ; 5854: 15        ; one fewer column on next top/bottom pass
    DEC E                               ; 5855: 1D        ; one fewer row on next right/left pass
; --- spiral bottom edge: fill D cells leftward ---
    LD B,D                              ; 5856: 42
.spiral_bot_loop:
    DEC HL                              ; 5857: 2B        ; move left one column
    LD (HL),$BF                         ; 5858: 36 BF
    CALL $58E2                          ; 585A: CD E2 58
    DJNZ .spiral_bot_loop              ; 585D: 10 F8
    CALL $58EC                          ; 585F: CD EC 58
; --- check termination: stop when D reaches $31 (49 = inner 15-col core) ---
    LD A,D                              ; 5862: 7A
    CP $31                              ; 5863: FE 31     ; D == 49 → spiral complete
    JR Z,$587E                          ; 5865: 28 17     ; → svc_wipe_spiral_ix (pixel data phase)
; --- spiral left edge: fill E cells upward (stride -64 per row) ---
    LD B,E                              ; 5867: 43
.spiral_left_loop:
    PUSH BC                             ; 5868: C5
    OR A                                ; 5869: B7        ; clear carry for SBC
    LD BC,$0040                         ; 586A: 01 40 00
    SBC HL,BC                           ; 586D: ED 42     ; retreat up one row
    LD (HL),$BF                         ; 586F: 36 BF
    POP BC                              ; 5871: C1
    CALL $58E2                          ; 5872: CD E2 58
    DJNZ .spiral_left_loop             ; 5875: 10 F1
    CALL $58EC                          ; 5877: CD EC 58
; --- contract again for the next spiral layer ---
    DEC D                               ; 587A: 15
    DEC E                               ; 587B: 1D
    JR svc_spiral_top                  ; 587C: 18 B9     ; back to top-edge fill

; --- svc_wipe_spiral_ix ($587E) ---
; Second phase: after the $BF spiral is complete, walk IX through the
; pixel data at $5607, writing actual sprite/tile bytes into the remaining
; inner core of VRAM while growing/shrinking the IX window outward.
svc_wipe_spiral_ix:   ; $587E
    LD E,$01                            ; 587E: 1E 01     ; E = 1 (initial IX window half-width)"""

assert OLD_SPIRAL_ENTRY in text, "Spiral entry block not found"
text = text.replace(OLD_SPIRAL_ENTRY, NEW_SPIRAL_ENTRY, 1)

# -----------------------------------------------------------------------
# 3.  Label the sub-routines: svc_delay_bc ($58E2), svc_sound_row ($58EC)
# -----------------------------------------------------------------------
OLD_DELAY_BC = """    PUSH BC                             ; 58E2: C5
    LD BC,($5905)                       ; 58E3: ED 4B 05 59
    CALL $0060                          ; 58E7: CD 60 00
    POP BC                              ; 58EA: C1
    RET                                 ; 58EB: C9
    PUSH BC                             ; 58EC: C5
    PUSH DE                             ; 58ED: D5
    LD C,$0A                            ; 58EE: 0E 0A
    LD B,D                              ; 58F0: 42
    LD A,$01                            ; 58F1: 3E 01
    OUT ($FF),A                         ; 58F3: D3 FF
    DJNZ $58F5                          ; 58F5: 10 FE
    LD B,$14                            ; 58F7: 06 14
    LD A,$02                            ; 58F9: 3E 02
    OUT ($FF),A                         ; 58FB: D3 FF
    DJNZ $58FD                          ; 58FD: 10 FE
    DEC C                               ; 58FF: 0D
    JR NZ,$58F0                         ; 5900: 20 EE
    POP DE                              ; 5902: D1
    POP BC                              ; 5903: C1
    RET                                 ; 5904: C9
    LD C,E                              ; 5905: 4B
    NOP                                 ; 5906: 00"""

NEW_DELAY_BC = """; --- svc_delay_bc ($58E2) ---
; Calls ROM delay routine at $0060 with BC = value self-modified at $5905.
; Preserves BC across the call.
svc_delay_bc:   ; $58E2
    PUSH BC                             ; 58E2: C5
    LD BC,($5905)                       ; 58E3: ED 4B 05 59  ; BC = self-modified delay count
    CALL $0060                          ; 58E7: CD 60 00      ; TRS-80 ROM: delay BC × ~14 T-states
    POP BC                              ; 58EA: C1
    RET                                 ; 58EB: C9

; --- svc_sound_row ($58EC) ---
; Generates a short audio tick via TRS-80 port $FF (cassette motor on/off).
; C=10 outer loops; each loop: B=D pulses of motor-ON, then B=20 of motor-OFF.
; The resulting frequency is proportional to D (the column-run counter).
; Preserves BC, DE.
svc_sound_row:   ; $58EC
    PUSH BC                             ; 58EC: C5
    PUSH DE                             ; 58ED: D5
    LD C,$0A                            ; 58EE: 0E 0A        ; C = 10 outer iterations
.sound_row_loop:
    LD B,D                              ; 58F0: 42            ; B = D (column run = on-pulse width)
    LD A,$01                            ; 58F1: 3E 01
    OUT ($FF),A                         ; 58F3: D3 FF         ; motor ON
    DJNZ $58F5                          ; 58F5: 10 FE         ; delay B ticks
    LD B,$14                            ; 58F7: 06 14         ; B = 20 (off-pulse width, fixed)
    LD A,$02                            ; 58F9: 3E 02
    OUT ($FF),A                         ; 58FB: D3 FF         ; motor OFF
    DJNZ $58FD                          ; 58FD: 10 FE
    DEC C                               ; 58FF: 0D
    JR NZ,.sound_row_loop              ; 5900: 20 EE
    POP DE                              ; 5902: D1
    POP BC                              ; 5903: C1
    RET                                 ; 5904: C9

; --- self-modifying delay cell ($5905) ---
; Written as a 16-bit word by svc_wipe_spiral_{fast,slow} before the spiral loop.
; Read back as BC by svc_delay_bc ("LD BC,($5905)").
; Initial dummy encoding (until overwritten): $4B $00 = LD C,E / NOP
    LD C,E                              ; 5905: 4B           ; ** self-modified delay lo-byte **
    NOP                                 ; 5906: 00           ; ** self-modified delay hi-byte **"""

assert OLD_DELAY_BC in text, "svc_delay_bc block not found"
text = text.replace(OLD_DELAY_BC, NEW_DELAY_BC, 1)

# -----------------------------------------------------------------------
# 4.  Label svc_wipe_curtain ($5907) and its helpers svc_delay_1s ($595D)
#     and svc_sound_col ($5968)
# -----------------------------------------------------------------------
OLD_CURTAIN = """    LD HL,$3FFF                         ; 5907: 21 FF 3F
    LD DE,$3FFE                         ; 590A: 11 FE 3F
    EXX                                 ; 590D: D9
    LD HL,$3C00                         ; 590E: 21 00 3C
    LD DE,$3C01                         ; 5911: 11 01 3C
    LD A,$08                            ; 5914: 3E 08
    CALL $595D                          ; 5916: CD 5D 59
    CALL $5968                          ; 5919: CD 68 59
    LD BC,$0040                         ; 591C: 01 40 00
    LD (HL),$BF                         ; 591F: 36 BF
    LDIR                                ; 5921: ED B0
    LD (HL),$80                         ; 5923: 36 80
    EXX                                 ; 5925: D9
    LD BC,$0040                         ; 5926: 01 40 00
    LD (HL),$BF                         ; 5929: 36 BF
    LDDR                                ; 592B: ED B8
    LD (HL),$80                         ; 592D: 36 80
    EXX                                 ; 592F: D9
    DEC A                               ; 5930: 3D
    JR NZ,$5916                         ; 5931: 20 E3
    LD HL,$3DFF                         ; 5933: 21 FF 3D
    LD (HL),$BF                         ; 5936: 36 BF
    LD HL,$5600                         ; 5938: 21 00 56
    LD DE,$3E00                         ; 593B: 11 00 3E
    EXX                                 ; 593E: D9
    LD HL,$55FF                         ; 593F: 21 FF 55
    LD DE,$3DFF                         ; 5942: 11 FF 3D
    CALL $595D                          ; 5945: CD 5D 59
    CALL $5968                          ; 5948: CD 68 59
    LD BC,$0040                         ; 594B: 01 40 00
    LDDR                                ; 594E: ED B8
    EXX                                 ; 5950: D9
    LD BC,$0040                         ; 5951: 01 40 00
    LDIR                                ; 5954: ED B0
    LD A,$40                            ; 5956: 3E 40
    CP D                                ; 5958: BA
    RET Z                               ; 5959: C8
    EXX                                 ; 595A: D9
    JR $5945                            ; 595B: 18 E8
    PUSH AF                             ; 595D: F5
    PUSH BC                             ; 595E: C5
    LD BC,$03E8                         ; 595F: 01 E8 03
    CALL $0060                          ; 5962: CD 60 00
    POP BC                              ; 5965: C1
    POP AF                              ; 5966: F1
    RET                                 ; 5967: C9
    PUSH AF                             ; 5968: F5
    PUSH BC                             ; 5969: C5
    LD C,$C8                            ; 596A: 0E C8
    LD B,$0C                            ; 596C: 06 0C
    LD A,$01                            ; 596E: 3E 01
    OUT ($FF),A                         ; 5970: D3 FF
    DJNZ $5972                          ; 5972: 10 FE
    LD B,$0F                            ; 5974: 06 0F
    LD A,$02                            ; 5976: 3E 02
    OUT ($FF),A                         ; 5978: D3 FF
    DJNZ $597A                          ; 597A: 10 FE
    DEC C                               ; 597C: 0D
    JR NZ,$596C                         ; 597D: 20 ED
    POP BC                              ; 597F: C1
    POP AF                              ; 5980: F1
    RET                                 ; 5981: C9"""

NEW_CURTAIN = """; --- svc_wipe_curtain ($5907) ---
; "Curtain" wipe: simultaneously fills VRAM from the top-left (LDIR, HL'=
; $3C00 advancing right) and from the bottom-right (LDDR, HL=$3FFF
; retreating left), meeting in the middle.  After 8 passes of 64 cells
; each the full screen is $BF (solid black).  Then it blits the pixel
; data from $5600/$55FF into the newly cleared zones, scrolling inward
; from both edges until D ($3E00 hi-byte) reaches $40.
; EXX is used to swap between the two pointer pairs each pass.
svc_wipe_curtain:   ; $5907
    LD HL,$3FFF                         ; 5907: 21 FF 3F  ; bottom-right VRAM pointer
    LD DE,$3FFE                         ; 590A: 11 FE 3F  ; bottom-right destination
    EXX                                 ; 590D: D9        ; swap to alternate register set
    LD HL,$3C00                         ; 590E: 21 00 3C  ; top-left VRAM pointer
    LD DE,$3C01                         ; 5911: 11 01 3C  ; top-left destination
    LD A,$08                            ; 5914: 3E 08     ; A = 8 passes (8×64 = 512 cells each direction)
.curtain_blackout_loop:
    CALL $595D                          ; 5916: CD 5D 59  ; svc_delay_1s: ~1000-iter delay
    CALL $5968                          ; 5919: CD 68 59  ; svc_sound_col: audio click
    LD BC,$0040                         ; 591C: 01 40 00  ; 64 cells per pass
    LD (HL),$BF                         ; 591F: 36 BF     ; seed $BF at top-left start
    LDIR                                ; 5921: ED B0     ; fill 64 cells rightward with $BF
    LD (HL),$80                         ; 5923: 36 80     ; clear landing cell
    EXX                                 ; 5925: D9        ; switch to bottom-right pointers
    LD BC,$0040                         ; 5926: 01 40 00
    LD (HL),$BF                         ; 5929: 36 BF     ; seed $BF at bottom-right start
    LDDR                                ; 592B: ED B8     ; fill 64 cells leftward with $BF
    LD (HL),$80                         ; 592D: 36 80     ; clear landing cell
    EXX                                 ; 592F: D9        ; back to top-left
    DEC A                               ; 5930: 3D        ; one pass done
    JR NZ,.curtain_blackout_loop       ; 5931: 20 E3     ; repeat 8 times
; --- curtain blit phase: copy pixel data from $5600 into cleared zone ---
    LD HL,$3DFF                         ; 5933: 21 FF 3D  ; mid-screen marker cell
    LD (HL),$BF                         ; 5936: 36 BF     ; plant $BF at centre boundary
    LD HL,$5600                         ; 5938: 21 00 56  ; source: pixel data (top half)
    LD DE,$3E00                         ; 593B: 11 00 3E  ; dest: VRAM mid-point (forward)
    EXX                                 ; 593E: D9
    LD HL,$55FF                         ; 593F: 21 FF 55  ; source: pixel data (bottom half, reversed)
    LD DE,$3DFF                         ; 5942: 11 FF 3D  ; dest: VRAM mid-point (backward)
.curtain_blit_loop:
    CALL $595D                          ; 5945: CD 5D 59  ; delay
    CALL $5968                          ; 5948: CD 68 59  ; audio click
    LD BC,$0040                         ; 594B: 01 40 00
    LDDR                                ; 594E: ED B8     ; copy 64 bytes backward (bottom half)
    EXX                                 ; 5950: D9
    LD BC,$0040                         ; 5951: 01 40 00
    LDIR                                ; 5954: ED B0     ; copy 64 bytes forward (top half)
    LD A,$40                            ; 5956: 3E 40     ; check if DE hi-byte reached $40
    CP D                                ; 5958: BA        ; ($3C00 region fully filled?)
    RET Z                               ; 5959: C8        ; yes → done
    EXX                                 ; 595A: D9
    JR .curtain_blit_loop              ; 595B: 18 E8

; --- svc_delay_1s ($595D) ---
; Calls TRS-80 ROM delay ($0060) with BC=$03E8 (1000 iterations).
; Preserves AF, BC.
svc_delay_1s:   ; $595D
    PUSH AF                             ; 595D: F5
    PUSH BC                             ; 595E: C5
    LD BC,$03E8                         ; 595F: 01 E8 03  ; 1000 delay iterations
    CALL $0060                          ; 5962: CD 60 00  ; TRS-80 ROM delay
    POP BC                              ; 5965: C1
    POP AF                              ; 5966: F1
    RET                                 ; 5967: C9

; --- svc_sound_col ($5968) ---
; Generates a longer audio click via port $FF.
; C=200 outer loops; each: B=12 pulses of motor-ON, B=15 of motor-OFF.
; Preserves AF, BC.
svc_sound_col:   ; $5968
    PUSH AF                             ; 5968: F5
    PUSH BC                             ; 5969: C5
    LD C,$C8                            ; 596A: 0E C8     ; C = 200 outer iterations
.sound_col_loop:
    LD B,$0C                            ; 596C: 06 0C     ; B = 12 on-pulse width
    LD A,$01                            ; 596E: 3E 01
    OUT ($FF),A                         ; 5970: D3 FF     ; motor ON
    DJNZ $5972                          ; 5972: 10 FE
    LD B,$0F                            ; 5974: 06 0F     ; B = 15 off-pulse width
    LD A,$02                            ; 5976: 3E 02
    OUT ($FF),A                         ; 5978: D3 FF     ; motor OFF
    DJNZ $597A                          ; 597A: 10 FE
    DEC C                               ; 597C: 0D
    JR NZ,.sound_col_loop              ; 597D: 20 ED
    POP BC                              ; 597F: C1
    POP AF                              ; 5980: F1
    RET                                 ; 5981: C9"""

assert OLD_CURTAIN in text, "svc_wipe_curtain block not found"
text = text.replace(OLD_CURTAIN, NEW_CURTAIN, 1)

# -----------------------------------------------------------------------
# 5.  Label svc_wipe_scroll_down ($5982) and svc_sound_scr ($59B3)
# -----------------------------------------------------------------------
OLD_SCROLL = """    LD A,$10                            ; 5982: 3E 10
    LD HL,$5400                         ; 5984: 21 00 54
    PUSH HL                             ; 5987: E5
    PUSH AF                             ; 5988: F5
    LD HL,$3C40                         ; 5989: 21 40 3C
    LD DE,$3C00                         ; 598C: 11 00 3C
    LD BC,$03C0                         ; 598F: 01 C0 03
    LD A,(HL)                           ; 5992: 7E
    LD (DE),A                           ; 5993: 12
    INC HL                              ; 5994: 23
    INC DE                              ; 5995: 13
    DEC BC                              ; 5996: 0B
    LD A,E                              ; 5997: 7B
    AND $FF                             ; 5998: E6 FF
    CP $1E                              ; 599A: FE 1E
    CALL C,$59B3                        ; 599C: DC B3 59
    LD A,B                              ; 599F: 78
    OR C                                ; 59A0: B1
    JR NZ,$5992                         ; 59A1: 20 EF
    POP AF                              ; 59A3: F1
    POP HL                              ; 59A4: E1
    LD DE,$3FC0                         ; 59A5: 11 C0 3F
    LD BC,$0040                         ; 59A8: 01 40 00
    LDIR                                ; 59AB: ED B0
    PUSH HL                             ; 59AD: E5
    DEC A                               ; 59AE: 3D
    JR NZ,$5988                         ; 59AF: 20 D7
    POP HL                              ; 59B1: E1
    RET                                 ; 59B2: C9
    PUSH AF                             ; 59B3: F5
    PUSH BC                             ; 59B4: C5
    LD C,$01                            ; 59B5: 0E 01
    LD B,E                              ; 59B7: 43
    LD A,$01                            ; 59B8: 3E 01
    OUT ($FF),A                         ; 59BA: D3 FF
    DJNZ $59BC                          ; 59BC: 10 FE
    LD B,D                              ; 59BE: 42
    LD A,$02                            ; 59BF: 3E 02
    OUT ($FF),A                         ; 59C1: D3 FF
    DJNZ $59C3                          ; 59C3: 10 FE
    DEC C                               ; 59C5: 0D
    JR NZ,$59B7                         ; 59C6: 20 EF
    POP BC                              ; 59C8: C1
    POP AF                              ; 59C9: F1
    RET                                 ; 59CA: C9"""

NEW_SCROLL = """; --- svc_wipe_scroll_down ($5982) ---
; Scrolls the back-buffer ($5400) into VRAM ($3C00) by shifting existing
; VRAM content up one row at a time while writing new rows from the buffer.
; A=16 = number of rows (full screen height).
; Each pass: copy 960 bytes ($3C40→$3C00, i.e. shift everything up 1 row),
; then LDIR the bottom row from the back-buffer into VRAM row 15 ($3FC0).
; svc_sound_scr is called whenever E (low byte of DE) crosses $1E to
; produce a short audio buzz proportional to the current scroll position.
svc_wipe_scroll_down:   ; $5982
    LD A,$10                            ; 5982: 3E 10     ; A = 16 rows to scroll in
    LD HL,$5400                         ; 5984: 21 00 54  ; HL = start of back-buffer
.scroll_row_setup:
    PUSH HL                             ; 5987: E5        ; save back-buffer pointer
    PUSH AF                             ; 5988: F5        ; save row counter
; --- shift VRAM content up by one row (64 bytes = $40) ---
    LD HL,$3C40                         ; 5989: 21 40 3C  ; source: VRAM row 1 (one row below top)
    LD DE,$3C00                         ; 598C: 11 00 3C  ; dest:   VRAM row 0 (top)
    LD BC,$03C0                         ; 598F: 01 C0 03  ; count: 960 bytes = 15 rows
.scroll_shift_loop:
    LD A,(HL)                           ; 5992: 7E        ; read source byte
    LD (DE),A                           ; 5993: 12        ; write to dest (one row up)
    INC HL                              ; 5994: 23
    INC DE                              ; 5995: 13
    DEC BC                              ; 5996: 0B
    LD A,E                              ; 5997: 7B        ; check DE low byte
    AND $FF                             ; 5998: E6 FF
    CP $1E                              ; 599A: FE 1E     ; crossed $xx1E boundary?
    CALL C,$59B3                        ; 599C: DC B3 59  ; yes → svc_sound_scr: audio buzz
    LD A,B                              ; 599F: 78
    OR C                                ; 59A0: B1        ; BC == 0?
    JR NZ,.scroll_shift_loop           ; 59A1: 20 EF     ; no → keep shifting
; --- blit new bottom row from back-buffer ---
    POP AF                              ; 59A3: F1        ; restore row counter
    POP HL                              ; 59A4: E1        ; restore back-buffer ptr
    LD DE,$3FC0                         ; 59A5: 11 C0 3F  ; dest: VRAM last row ($3FC0)
    LD BC,$0040                         ; 59A8: 01 40 00  ; 64 bytes = 1 row
    LDIR                                ; 59AB: ED B0     ; copy row from back-buffer to bottom VRAM row
    PUSH HL                             ; 59AD: E5        ; HL now points to next back-buffer row
    DEC A                               ; 59AE: 3D        ; one fewer row to do
    JR NZ,.scroll_row_setup            ; 59AF: 20 D7     ; repeat for all 16 rows
    POP HL                              ; 59B1: E1
    RET                                 ; 59B2: C9

; --- svc_sound_scr ($59B3) ---
; Short audio buzz called mid-row during scroll wipe.
; C=1 pass; B=E on-pulse, B=D off-pulse (width keyed to scroll position).
; Preserves AF, BC.
svc_sound_scr:   ; $59B3
    PUSH AF                             ; 59B3: F5
    PUSH BC                             ; 59B4: C5
    LD C,$01                            ; 59B5: 0E 01     ; C = 1 outer loop
.sound_scr_loop:
    LD B,E                              ; 59B7: 43        ; on-pulse width = E (DE low byte)
    LD A,$01                            ; 59B8: 3E 01
    OUT ($FF),A                         ; 59BA: D3 FF     ; motor ON
    DJNZ $59BC                          ; 59BC: 10 FE
    LD B,D                              ; 59BE: 42        ; off-pulse width = D (DE high byte)
    LD A,$02                            ; 59BF: 3E 02
    OUT ($FF),A                         ; 59C1: D3 FF     ; motor OFF
    DJNZ $59C3                          ; 59C3: 10 FE
    DEC C                               ; 59C5: 0D
    JR NZ,.sound_scr_loop              ; 59C6: 20 EF
    POP BC                              ; 59C8: C1
    POP AF                              ; 59C9: F1
    RET                                 ; 59CA: C9"""

assert OLD_SCROLL in text, "svc_wipe_scroll_down block not found"
text = text.replace(OLD_SCROLL, NEW_SCROLL, 1)

# -----------------------------------------------------------------------
# 6.  Write the result
# -----------------------------------------------------------------------
with open(ASM, "w") as f:
    f.write(text)

print("Done. All replacements applied successfully.")
