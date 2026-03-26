; ====================================================================
; SCRAMBLE - TRS-80 Z80 GAME  (loaded at $5E00-$6F37)
; ====================================================================
;
; MEMORY MAP:
;   $0000-$2FFF  TRS-80 ROM (Level II BASIC)
;   $3800-$3BFF  Keyboard (memory-mapped read)
;   $3C00-$3FFF  Video RAM (64 cols x 16 rows of semigraphic chars)
;   $4000+       RAM
;   $41E2        Temporary LDOS loader hook: one byte, initialised to JP (HL)
;                by LDOS, overwritten with RET ($C9) by fn_game_entry at $60B0.
;   $5400-$57FF  Splash-screen BACK-BUFFER (1024 bytes).
;                Filled entirely with $80 (blank semigraphic) by fn_clear_splash_buffer
;                ($59DD), then composited in-place by fn_draw_title_graphics ($5A56)
;                and fn_draw_top_five_box ($5ADC), then blitted to video RAM with
;                LDIR at $60D7.  NOT in the CMD file; RAM is allocated by LDOS.
;   $5800-$5FFF  LDOS SVC stubs (game-supplied; loaded from CMD file)
;                $5800  JP $580F   SVC_DISPLAY  → screen wipe/blit animation
;                $5803  JP $59DD   SVC_KEYBOARD → keyboard read
;                $5806  JP $59CB   SVC_KEYBOARD2
;                $5809  JP $59D4   SVC_MISC     → build splash-screen back-buffer
;                                                 (clear + compose + draw box)
;                $580C  JP $5D2E   SVC_MISC2
;                $580F-$5FFF  SVC implementation routines:
;                  $59DD  fn_clear_splash_buffer  fills $5400 with $80 (blank)
;                  $5A4D  fn_copy_until_at        copy @-terminated string to VRAM
;                  $5A56  fn_draw_title_graphics  compose title into $5400:
;                           row 0  col 4   "KANSAS SOFTWARE ***"         ($5B6C)
;                           rows 1-3 col 5  big "Arcade" semigraphic letters
;                           rows 5-7 col 5  big "Bomber" semigraphic letters
;                           rows 9-11 col 4 big "SCRAMBLE" semigraphic letters
;                           row 13 col 4   "PRESS <I> FOR INSTRUCTIONS..."  ($5B80)
;                           row 15 col 10  "(C) 1981 - MIKE CHALK & CHRIS SMYTH" ($5BAF)
;                  $5ADC  fn_draw_top_five_box    draw "*TOP FIVE*" border box
;                           top edge: row 0  cols 46-63 with $B0 (semigraphic top bar)
;                           bot edge: row 7  cols 46-63 with $83 (semigraphic bottom bar)
;                           sides:    col 46 and col 63, rows 0-6 with $BF (full block)
;                           interior: row 1, col 49  "* TOP FIVE *" text   ($5BD3)
;   $5E00-$60AF  Instructions-screen data (not executable; decoded as instructions
;                by z80dasm but these are raw character/semigraphic bytes):
;                  $5E00-$5E1E  "@SIMULTANEOUSLY TO DROP BOMBS"
;                  $5E1F-$5E7E  "  -  PRESS UP & DOWN SIMULTANEOUSLY TO ABORT GAME"
;                               followed by padding ($80 blanks)
;                  $5E7F-$5E9B  Semigraphic tile row for score-table header
;                  $5E9C-$5EAB  "FIGHTERS" label + padding
;                  $5EAC-$5EBB  "BLIMPS"   label + padding
;                  $5EBC-$5ECB  "BOMBER"   label + padding
;                  $5ECC-$5FEE  Semigraphic score-panel tiles (score values
;                               displayed next to each enemy type on attract screen)
;                  $5FEF-$5FFB  "FACTORY"  label + padding
;                  $5FFC-$6007  "ROCKET"   label + padding
;                  $6008-$6016  "FUEL TANK" label + padding
;                  $6017-$6037  "ACK-ACK"  label (score 100 targets)
;                  $6038-$606F  Semigraphic tile rows for score-table body
;                  $6070-$60A7  Enemy sprite semigraphic tiles (used by attract mode)
;                  $60A8-$60AF  Padding ($FF, spaces)
;   $60B0-$61FF  Z80 machine code: entry point + title/game loop
;   $6200-$6F37  Z80 machine code: main game logic (this file)
;
; TRUE CMD ENTRY POINT:   $60B0  (fn_game_entry)
;   (Earlier documentation incorrectly stated $6200 as the entry point.
;    The CMD transfer record in ARCBOMB1/CMD specifies $60B0.)
;
; SPLASH SCREEN SEQUENCE (what you see on boot):
;   1. fn_game_entry ($60B0) initialises stack and clears LDOS hook.
;   2. CALL $5809 (SVC_MISC) → fn_clear_splash_buffer + fn_draw_title_graphics
;      + fn_draw_top_five_box: renders the complete splash screen into $5400.
;   3. LDIR $5400→$3C00 at $60D7: blits the back-buffer to live video RAM.
;      The display instantly shows the full title screen.
;   4. fn_title_wait_loop ($60F0) waits for I (instructions) or SPACE (start).
;      While waiting, fn_attract_mode ($6425) cycles the score table display.
;
; DISPLAY MODEL:
;   Screen = 64 chars wide x 16 rows tall
;   Chars $80-$BF = semigraphic blocks (2x3 pixel grid per cell)
;   Effective pixel resolution = 128 x 48
;   Video RAM address = $3C00 + (row * 64) + col
;
; KEY ADDRESSES:
;   Keyboard read: LD A,($38xx) reads a row of keys (memory-mapped)
;   $3802 bit 1 = 'I' key (show instructions)
;   $3840 = $80    SPACE key (start game)
;   $3880 bit 0    Space  bit 3  Up  bit 4  Down  bit 5  Left
;   Q key:  fires machine gun (with W)
;   W key:  fires machine gun (with Q)
; ====================================================================

; ====================================================================
; INSTRUCTIONS SCREEN DATA  ($5E00-$60AF)
; ====================================================================
; Pure character/semigraphic data - NOT executable code.
; z80dasm misreads these as instructions; they are screen layout bytes
; used by the instructions-scroll routine at $613B.
; $40 (ASCII '@') is used as the string terminator throughout.
; $80 is the blank semigraphic character (no pixels lit).
; ====================================================================

str_instr_drop_bombs:   ; $5E00
    ; "SIMULTANEOUSLY TO DROP BOMBS"  (@-terminated)
    DB       $54,$20,$53,$49,$4D,$55,$4C,$54,$41,$4E,$45,$4F,$55,$53,$4C,$59 ; |T SIMULTANEOUSLY|
    DB       $40                                                     ; terminator

str_instr_press_updown:   ; $5E1F
    ; "  -  PRESS UP & DOWN SIMULTANEOUSLY TO ABORT GAME"  (@-terminated)
    DB       $20,$20,$2D,$20,$20,$50,$52,$45,$53,$53,$20,$55,$50,$20,$26,$20 ; |  -  PRESS UP & |
    DB       $44,$4F,$57,$4E,$20,$53,$49,$4D,$55,$4C,$54,$41,$4E,$45,$4F,$55 ; |DOWN SIMULTANEOU|
    DB       $53,$4C,$59,$20,$54,$4F,$20,$41,$42,$4F,$52,$54,$20,$47,$41,$4D ; |SLY TO ABORT GAM|
    DB       $45,$40                                                 ; |E@|

    ; Semigraphic score-panel header tiles + padding ($80 = blank semigraphic)
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80         ; 12 blank cells
    DB       $8C,$B7,$BB,$8C,$80,$84,$88,$80,$84,$88,$80             ; score-table top border row
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; padding

str_instr_fighters:   ; $5E9C
    ; "FIGHTERS"  label for enemy type in score table
    DB       $46,$49,$47,$48,$54,$45,$52,$53                         ; |FIGHTERS|
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80         ; 12 blank padding cells

str_instr_blimps:   ; $5EAC
    ; "BLIMPS"  label for enemy type in score table
    DB       $42,$4C,$49,$4D,$50,$53                                 ; |BLIMPS|
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; padding

str_instr_bomber:   ; $5EBC
    ; "BOMBER"  label for enemy type in score table
    DB       $42,$4F,$4D,$42,$45,$52                                 ; |BOMBER|
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; padding

    ; Semigraphic score-value tiles and enemy score-panel rows
    ; Each enemy row is 16 chars: label(6) + blank(2) + score digits in semigraphics(8)
    ; Values encode the TRS-80 semigraphic chars for "150", "300", "100" etc.
    ; ($80=0, $98=top-pixel, $90=bottom-pixel, $84=left-pixel, $88=right-pixel,
    ;  $8C=left+right, $B0=top-row, $BF=all-pixels, $A0=mid-row …)
    DB       $88,$8C,$B7,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; }
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; } score
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; } panel
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; } tile
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; } data
    DB       $80,$A0,$B0,$A0,$B0,$A0,$B0,$A0,$B0,$A0,$B0,$80,$80    ; } ...

str_instr_factory:   ; $5FEF (approx)
    ; "FACTORY"  label for ground target in score table (fuel-tank / base)
    DB       $46,$4F,$52,$54,$8C,$86,$80,$80,$80,$80,$80,$80                 ; "FORT" + tiles
    DB       $B0,$B7,$BF,$BB,$B7,$B5,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; border + padding

str_instr_rocket:   ; $6000
    ; "ROCKET"  + score tiles
    DB       $4F,$43,$4B,$45,$54,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; "OCKET"+padding

str_instr_fuel_tank:   ; $6017
    ; "FUEL TANK"  label
    DB       $46,$55,$45,$4C,$80,$54,$41,$4E,$4B               ; |FUEL TANK|
    DB       $83,$8C,$A4,$B0,$B5,$B5,$B0,$8C,$8C,$81           ; score semigraphic tiles
    DB       $80,$80,$80,$80,$80,$80                           ; padding

str_instr_ackack:   ; $6037 (approx)
    ; "ACK-ACK"  label (the $31 bytes are the score "100" in semigraphic)
    DB       $31,$30,$30,$80,$80,$80,$80,$80,$80,$80,$80,$80   ; "100" score + padding
    DB       $31,$32,$35,$80,$80,$80,$80,$80,$80,$80,$80,$80   ; "125" score + padding

    ; Score-panel body tiles (enemy sprite artwork rendered in semigraphic chars)
    ; These tiles are rendered into the instructions scroll screen, one row per enemy.
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; row blank
    DB       $80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80 ; row blank
    DB       $36,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80,$80   ; sprite row data ...
    ; (remaining tile data continues to $60A7)

padding_60A8:   ; $60A8
    ; Alignment padding between screen data and code
    DB       $FF                                             ; $60A8: FF
    DB       $20,$20,$20,$20,$20,$20                        ; $60A9-$60AE: spaces
    DB       $31                                            ; $60AF: (aligns to $60B0)

; ====================================================================
; ENTRY POINT + SPLASH SCREEN DISPLAY  ($60B0-$60DF)
; ====================================================================
; fn_game_entry  --  $60B0
;
; This is the TRUE CMD ENTRY POINT (ARCBOMB1/CMD transfer record = $60B0).
; Executed once, immediately after LDOS finishes loading the game from disk.
;
; Responsibilities:
;   1. Initialise Z80 stack pointer to top of RAM ($7FFF)
;   2. Remove the LDOS "loader hook" (patch $41E2 with RET so it's a no-op)
;   3. Blank the ship-sprite working area ($63BC, 65 bytes → $20 space)
;   4. Reset zone counter to 0 ($6244 = 0)
;   5. Call SVC_MISC ($5809) which:
;        a. fn_clear_splash_buffer ($59DD):
;              fills entire splash back-buffer $5400-$57FF with $80 (blank)
;        b. fn_draw_title_graphics ($5A56):
;              blits pre-composed tile strips from ROM data into the buffer:
;              row 0  col 4   "KANSAS SOFTWARE ***"          (from $5B6C)
;              rows 1-3 col 5  big "Arcade"  semigraphic letters
;              rows 5-7 col 5  big "Bomber"  semigraphic letters
;              rows 9-11 col 4 big "SCRAMBLE" semigraphic letters
;              row 13 col 4   "PRESS <I> FOR INSTRUCTIONS OR <SPACE> TO START"
;                                                             (from $5B80)
;              row 15 col 10  "(C) 1981 - MIKE CHALK & CHRIS SMYTH"
;                                                             (from $5BAF)
;        c. fn_draw_top_five_box ($5ADC):
;              draws a rectangular semigraphic border box at rows 0-7, cols 46-63
;              (top-right corner of the screen) and writes "* TOP FIVE *" inside
;              (from $5BD3).  Uses $B0 (top-bar), $83 (bottom-bar), $BF (solid)
;              for the frame characters.
;   6. LDIR $5400→$3C00: BLIT the completed back-buffer to live video RAM.
;      The splash screen now appears instantaneously on screen.
;   7. Call fn_clear_buffers and fn_init_game_state to set up the game variables.
;   8. Jump into the title-screen wait loop (fn_title_wait_loop, $60F0).
; ====================================================================

fn_game_entry:   ; $60B0  ← TRUE CMD ENTRY POINT
    LD SP,$7FFF                                             ; 60B0: 31 FF 7F   init stack pointer to top of RAM
    LD A,$C9                                                ; 60B3: 3E C9      A = $C9 = Z80 RET opcode
    LD ($41E2),A                                            ; 60B5: 32 E2 41   patch LDOS loader hook → RET (disarm it)
    LD HL,$63BC  ; data_ship_sprite                         ; 60B8: 21 BC 63
    LD DE,$63BD                                             ; 60BB: 11 BD 63   DE = HL+1 (LDIR fill idiom)
    INC DE                                                  ; 60BE: 13
    LD (HL),$20                                             ; 60BF: 36 20      first byte = $20 (space = transparent)
    LD BC,$0041                                             ; 60C1: 01 41 00   65 bytes to clear
    LDIR                                                    ; 60C4: ED B0      blank the ship-sprite buffer
    LD A,$00                                                ; 60C6: 3E 00
    LD ($6244),A  ; current_zone                            ; 60C8: 32 44 62   zone = 0 (not yet in-game)
    CALL $5809  ; SVC_MISC → fn_clear_splash_buffer         ; 60CB: CD 09 58
                ; + fn_draw_title_graphics + fn_draw_top_five_box
                ; After this call, $5400-$57FF holds the complete splash screen:
                ;   row  0       "KANSAS SOFTWARE ***"  (left) + top of TOP-FIVE box (right)
                ;   rows 1-3     big "Arcade"  letters in semigraphic pixels
                ;   row  4       blank separator
                ;   rows 5-7     big "Bomber"  letters in semigraphic pixels
                ;   row  8       blank separator
                ;   rows 9-11    big "SCRAMBLE" letters in semigraphic pixels
                ;   row  12      blank
                ;   row  13      "PRESS <I> FOR INSTRUCTIONS OR <SPACE> TO START"
                ;   row  14      blank
                ;   row  15      "(C) 1981 - MIKE CHALK & CHRIS SMYTH"
                ;   cols 46-63 rows 0-7: "*TOP FIVE*" score box border
    LD HL,$5400  ; splash screen back-buffer                ; 60CE: 21 00 54
    LD DE,$3C00  ; video RAM base                           ; 60D1: 11 00 3C
    LD BC,$0400  ; 1024 bytes = 64 cols × 16 rows           ; 60D4: 01 00 04
    LDIR         ; BLIT: copy back-buffer → live video RAM  ; 60D7: ED B0
                 ; splash screen is now fully visible on the TRS-80 display
    CALL $643C   ; fn_clear_buffers (init display page buffers)  ; 60D9: CD 3C 64
    CALL $638F   ; fn_init_game_state (score=0, lives=3, fuel=full) ; 60DC: CD 8F 63
    JR .title_draw  ; first-time path: skip the extra re-init calls ; 60DF: 18 0F

; ====================================================================
; TITLE SCREEN RE-ENTRY AFTER GAME OVER  ($60E1)
; ====================================================================
; Jumped to via JP $60E1 from fn_copy_terrain ($633E) and .L634B
; when the game ends (lives=0).  Redraws the splash screen, resets
; game state, and drops back to the title wait loop.
; ====================================================================

fn_title_redraw:   ; $60E1
    CALL $643C   ; fn_clear_buffers                        ; 60E1: CD 3C 64
    CALL $638F   ; fn_init_game_state (reset lives/score)  ; 60E4: CD 8F 63
    CALL $5809   ; SVC_MISC → rebuild splash back-buffer   ; 60E7: CD 09 58
    CALL $6355   ; fn_draw_status_bar (draw HUD row)        ; 60EA: CD 55 63
    CALL $5800   ; SVC_DISPLAY → wipe/animate transition    ; 60ED: CD 00 58

; ====================================================================
; TITLE SCREEN WAIT LOOP  ($60F0)
; ====================================================================
; Displays the splash screen and waits for player input.
; On each iteration fn_attract_mode ($6425) cycles the enemy/score
; table shown in the *TOP FIVE* area (attract mode animation).
; ====================================================================

.title_draw:   ; $60F0
    CALL $641B   ; fn_init_score_display (prime score/HUD buffer) ; 60F0: CD 1B 64

.title_loop:   ; $60F3  ← title screen poll loop
    LD A,($3802) ; read keyboard row 2                     ; 60F3: 3A 02 38
    CP $02       ; test bit 1 = 'I' key                    ; 60F6: FE 02
    JR Z,.instr_pressed  ; I pressed → show instructions   ; 60F8: 28 15
    LD A,($3840) ; read keyboard row $40                    ; 60FA: 3A 40 38
    CP $80       ; $3840=$80 means SPACE key held           ; 60FD: FE 80
    JR Z,.space_pressed  ; SPACE pressed → start game      ; 60FF: 28 25
    CALL $6425   ; fn_attract_mode: cycle score table anim  ; 6101: CD 25 64
                 ; Returns NZ while animating, Z when cycle complete
    JR NZ,.title_loop  ; still animating → keep polling    ; 6104: 20 ED

.any_key_wait:   ; $6106
    CALL $5803   ; SVC_KEYBOARD → wait for any keypress    ; 6106: CD 03 58
    CALL $5800   ; SVC_DISPLAY → refresh display           ; 6109: CD 00 58
    JP .instr_show  ; → show instructions                  ; 610C: C3 35 61

.instr_pressed:   ; $610F
    CALL $6210   ; fn_show_bonus_life_text: writes          ; 610F: CD 10 62
                 ; "* BONUS LIFE FOR EVERY 10000 SCORED *" to screen
    CALL $5800   ; SVC_DISPLAY                             ; 6112: CD 00 58
    CALL $641B   ; fn_init_score_display                   ; 6115: CD 1B 64

.wait_for_space:   ; $6118  ← wait loop after 'I' pressed
    LD A,($3840) ; read SPACE key row                      ; 6118: 3A 40 38
    CP $80                                                  ; 611B: FE 80
    JR Z,.space_pressed  ; SPACE → start game              ; 611D: 28 07
    CALL $6425   ; fn_attract_mode                         ; 611F: CD 25 64
    JR NZ,.wait_for_space  ; still animating → keep waiting ; 6122: 20 F4
    JR .any_key_wait  ; cycle done → wait for key          ; 6124: 18 E0

.space_pressed:   ; $6126  ← player pressed SPACE = start game
    CALL $643C   ; fn_clear_buffers                        ; 6126: CD 3C 64
    CALL $638F   ; fn_init_game_state (fresh game: score=0, lives=3) ; 6129: CD 8F 63
    CALL $5803   ; SVC_KEYBOARD (flush key buffer)         ; 612C: CD 03 58
    CALL $5800   ; SVC_DISPLAY                             ; 612F: CD 00 58
    JP fn_main_game_loop  ; → main gameplay loop           ; 6132: C3 AD 61

; ====================================================================
; INSTRUCTIONS SCREEN SCROLL  ($6135)
; ====================================================================
; Jumped to via JP $6135 from .any_key_wait above when the player
; presses some key other than SPACE.  Scrolls the instructions screen
; ($5E00 data) from right to left using fn_scroll_screen ($64CA).
; Counter stored at $61AB counts down $05DC (1500) scroll steps.
; Pressing any key or counter expiry returns to the title screen.
; ====================================================================

.instr_show:   ; $6135
    LD HL,$05DC  ; 1500 scroll iterations                  ; 6135: 21 DC 05
    LD ($61AB),HL ; store countdown at self-modifying addr  ; 6138: 22 AB 61

.instr_scroll_loop:   ; $613B
    CALL $64CA   ; fn_scroll_screen                        ; 613B: CD CA 64
    CALL $64CA   ; fn_scroll_screen (×8 total per frame    ; 613E: CD CA 64
    CALL $64CA   ; to advance the terrain scroll by one    ; 6141: CD CA 64
    CALL $64CA   ; pixel column, consistent with the       ; 6144: CD CA 64
    CALL $64CA   ; normal gameplay scroll speed)           ; 6147: CD CA 64
    CALL $64CA                                              ; 614A: CD CA 64
    CALL $64CA                                              ; 614D: CD CA 64
    CALL $64CA                                              ; 6150: CD CA 64
    CALL $6E71   ; fn_draw_fuel_bar (keep audio synced)    ; 6153: CD 71 6E
    LD A,($6AAE) ; scroll_x_lo                             ; 6156: 3A AE 6A
    INC A                                                   ; 6159: 3C
    AND $7F      ; keep in 0-127 range                     ; 615A: E6 7F
    LD ($6AAE),A                                            ; 615C: 32 AE 6A
    LD A,($6AAF) ; scroll_x_hi                             ; 615F: 3A AF 6A
    INC A                                                   ; 6162: 3C
    AND $1F      ; keep in 0-31 range                      ; 6163: E6 1F
    LD ($6AAF),A                                            ; 6165: 32 AF 6A
    CALL $6A00   ; fn_init_enemy_table (clear enemy table)  ; 6168: CD 00 6A
    CALL $6B7B   ; missile init                            ; 616B: CD 7B 6B
    CALL $6F23   ; fn_copy_screen_row (copy one row to VRAM) ; 616E: CD 23 6F
    CALL $6B77   ; bomb init                               ; 6171: CD 77 6B
    CALL $6C46   ; fn_update_all_bombs                     ; 6174: CD 46 6C
    CALL $6B2C   ; fn_update_missile                       ; 6177: CD 2C 6B
    CALL $6F2F   ; fn_display_update (push frame to screen) ; 617A: CD 2F 6F
    LD IX,$3800  ; IX = keyboard base address              ; 617D: DD 21 00 38
    LD A,(IX+$01) ; read keyboard row 1                    ; 6181: DD 7E 01
    OR (IX+$02)  ; row 2                                   ; 6184: DD B6 02
    OR (IX+$04)  ; row 4                                   ; 6187: DD B6 04
    OR (IX+$08)  ; row 8                                   ; 618A: DD B6 08
    OR (IX+$10)  ; row $10                                 ; 618D: DD B6 10
    OR (IX+$20)  ; row $20                                 ; 6190: DD B6 20
    OR (IX+$40)  ; row $40                                 ; 6193: DD B6 40
    LD HL,$3880  ; special keys row                        ; 6196: 21 80 38
    OR (HL)      ; include SPACE/shift row                 ; 6199: B6
    JP NZ,$634B  ; any key pressed → back to title screen  ; 619A: C2 4B 63
    LD HL,($61AB) ; load countdown                         ; 619D: 2A AB 61
    DEC HL       ; decrement                               ; 61A0: 2B
    LD ($61AB),HL ; store back                             ; 61A1: 22 AB 61
    LD A,H                                                  ; 61A4: 7C
    OR L         ; HL=0?                                   ; 61A5: B5
    JP Z,$634B   ; countdown expired → back to title screen ; 61A6: CA 4B 63
    JR .instr_scroll_loop  ; → next scroll frame           ; 61A9: 18 90

instr_scroll_counter:   ; $61AB
    DB       $00,$00  ; 2-byte countdown (self-modifying data)

; ====================================================================
; MAIN GAMEPLAY LOOP - PER FRAME  ($61AD)
; ====================================================================
; Jumped to from fn_game_entry / scroll loop on game start.
; Also jumped to from $620E (JR $61AD) to re-enter the loop.
; This is the inner loop that runs every frame while playing.
; Each call to fn_scroll_screen + fn_draw_fuel_bar + all the game
; system updates constitutes one game frame.
; ====================================================================

fn_main_game_loop:   ; $61AD
    CALL $64CA   ; fn_scroll_screen: advance terrain scroll ; 61AD: CD CA 64
    CALL $6E71   ; fn_draw_fuel_bar: update fuel display    ; 61B0: CD 71 6E
    LD A,($6680) ; frame counter (mod-5 cycle)             ; 61B3: 3A 80 66
    INC A                                                   ; 61B6: 3C
    LD ($6680),A                                            ; 61B7: 32 80 66
    SUB $05      ; have 5 frames elapsed?                  ; 61BA: D6 05
    JR NZ,.slow_path  ; not yet → only do minimal updates  ; 61BC: 20 25
    LD ($6680),A ; reset counter to 0                      ; 61BE: 32 80 66
    ; --- Full-update frame (every 5th frame) ---
    CALL $66B0   ; fn_read_ship_controls (read keys, move ship) ; 61C1: CD B0 66
    CALL $676E   ; fn_update_ship_x (advance ship X scroll pos) ; 61C4: CD 6E 67
    CALL $6A00   ; fn_init_enemy_table (enemy state step)  ; 61C7: CD 00 6A
    CALL $6926   ; fn_read_joystick (direction input)      ; 61CA: CD 26 69
    CALL $6B7B   ; missile setup                           ; 61CD: CD 7B 6B
    CALL $6F23   ; fn_copy_screen_row                      ; 61D0: CD 23 6F
    CALL $69A4   ; fn_draw_ship (blit ship sprite to VRAM)  ; 61D3: CD A4 69
    CALL $6570   ; fn_update_terrain_scroll                ; 61D6: CD 70 65
    CALL $6B77   ; bomb input check                        ; 61D9: CD 77 6B
    LD A,($6678) ; collision_flag                          ; 61DC: 3A 78 66
    CP $01       ; ship hit something?                     ; 61DF: FE 01
    JR Z,.full_update_done  ; → skip remaining if dead     ; 61E1: 28 62

.slow_path:   ; $61E3  ← every frame
    CALL $6829   ; fn_update_all_enemies (move/animate all enemies) ; 61E3: CD 29 68
    CALL $65CA   ; fn_check_ship_crash (collision detect)  ; 61E6: CD CA 65
    LD A,($6680) ; reload frame counter                    ; 61E9: 3A 80 66
    CP $00       ; is it 0 (just reset above)?             ; 61EC: FE 00
    JR NZ,fn_main_game_loop  ; not 0 → keep looping       ; 61EE: 20 BD
    ; --- End-of-5-frame housekeeping ---
    CALL $66E9   ; fn_fire_cannon (check fire key + spawn missile) ; 61F0: CD E9 66
    CALL $6C46   ; fn_update_all_bombs                     ; 61F3: CD 46 6C
    CALL $65CA   ; fn_check_ship_crash (second check after bombs) ; 61F6: CD CA 65
    CALL $6B2C   ; fn_update_missile                       ; 61F9: CD 2C 6B
    CALL $6F2F   ; fn_display_update (copy frame to screen) ; 61FC: CD 2F 6F

; ---------------------------------------------------------------
; $61FF: after every full-update frame the loop falls through here.
; JR Z,.full_update_done from $61E1 (offset $62) lands at $6245
; (the LD B,$28 before fn_init_level); it does NOT land here.
; The byte at $61FF closes the main-loop body; execution continues
; at fn_loop_dispatch/$6200 only via fall-through or direct jump.
; ---------------------------------------------------------------
.full_update_done:   ; $61FF  (fall-through from CALL $6F2F at $61FC)

; ====================================================================
; MAIN LOOP TAIL  ($6200 – $620F)
; ====================================================================
; On every completed main-loop frame execution falls into this block.
; A holds the current frame counter (already SUB-ed against 5).
; The short dispatch below handles the post-frame house-keeping:
;   • JR C,$6224   – carry set → fast-return path (counter still live)
;   • ADD A,B/$38  – combined game-state branch
;   • CP $05/JP Z  – fuel or zone counter hit threshold → title redraw
;   • CALL fn_draw_fuel_bar + JR fn_main_game_loop – normal loop back
; $6210 is a SEPARATE, directly-called routine (fn_show_bonus_life_text).
; ====================================================================

fn_loop_dispatch:   ; $6200
    LD B,B       ; NOP-equivalent (opcode $40); keeps byte alignment  ; 6200: 40
    JR C,$6224   ; carry set → skip the ADD+branch, go to $6224      ; 6201: 38 21
    ADD A,B      ; incorporate B into accumulated frame value         ; 6203: 80
    JR C,fn_main_game_loop+$0F  ; carry after ADD → loop fast path   ; 6204: 38 B6
    CP $05       ; has the zone/fuel counter reached threshold?       ; 6206: FE 05
    JP Z,$634B   ; yes → jump to game-over / title-redraw path        ; 6208: CA 4B 63
    CALL $6E71   ; fn_draw_fuel_bar: refresh fuel display             ; 620B: CD 71 6E
    JR fn_main_game_loop    ; loop back to top of main game loop      ; 620E: 18 9D

; ---- fn_show_bonus_life_text  ($6210) --------------------------------
; Called from fn_title_redraw ($610F) to write the "bonus life" message
; into the splash back-buffer.  Not reached by normal loop fall-through.
    CALL $580C   ; SVC_MISC2: clears / re-arms splash buffer          ; 6210: CD 0C 58
    LD HL,$621F  ; src = str_bonus_life ("* BONUS LIFE FOR...*\0")    ; 6213: 21 1F 62
    LD DE,$550E  ; dst = back-buffer offset $550E (mid of back-buf)   ; 6216: 11 0E 55
    LD BC,$0025  ; 37 bytes to copy                                   ; 6219: 01 25 00
    LDIR         ; copy bonus-life string into back-buffer            ; 621C: ED B0
    RET          ; return to caller                                   ; 621E: C9

str_bonus_life:   ; $621F
    DB       $2A,$20,$42,$4F,$4E,$55,$53,$20,$4C,$49,$46,$45,$20,$46,$4F,$52 ; |* BONUS LIFE FOR|
    DB       $20,$45,$56,$45,$52,$59,$20,$31,$30,$30,$30,$30,$20,$53,$43,$4F ; | EVERY 10000 SCO|
    DB       $52,$45,$44,$20,$2A,$00                                 ; |RED *.|
; $6245 is the JR Z target from fn_main_game_loop ($61E1: JR Z,+$62).
; When the ship-collision flag is set, the main loop jumps here to
; re-initialise the level (death → respawn sequence).
    LD B,$28     ; loop count = 40 terrain-draw/scroll cycles         ; 6245: 06 28

; ====================================================================
; fn_init_level  ($6247)
; ====================================================================
; Initialises a level for play.  Called with B already set to the
; desired number of scroll cycles (40 = $28 from the $6245 preamble).
; Steps:
;   1. Set scroll_phase=9 (full-terrain initial draw mode)
;   2. Loop B times: draw terrain + scroll one column
;   3. Dec level-init counter ($64C9); if not zero, update display
;      and fall back to main game loop (level still initialising)
;   4. When counter reaches 0: clear zone-border cells, long delay,
;      then enter hi-score comparison and entry logic
; ====================================================================

fn_init_level:   ; $6247
    LD A,$09                                                ; 6247: 3E 09
    LD ($64BA),A  ; scroll_phase ← 9 (initial full-draw mode)         ; 6249: 32 BA 64
.L624C:
    PUSH BC       ; preserve loop counter across calls                ; 624C: C5
    CALL $6495    ; fn_draw_terrain: render one column of terrain      ; 624D: CD 95 64
    CALL $64CA    ; fn_scroll_screen: advance scroll one column        ; 6250: CD CA 64
    POP BC        ; restore loop counter                              ; 6253: C1
    DJNZ .L624C   ; repeat B times (40 cycles fill the screen)        ; 6254: 10 F6
    LD A,($64C9)  ; level-init phase counter                          ; 6256: 3A C9 64
    DEC A         ; decrement phase                                   ; 6259: 3D
    LD ($64C9),A  ; store decremented value                           ; 625A: 32 C9 64
    CP $00        ; has phase reached 0? (final init pass)            ; 625D: FE 00
    JR Z,$6267    ; yes → do border-cell clear + hi-score logic       ; 625F: 28 06
    CALL $6470    ; fn_update_display: blit back-buffer to VRAM        ; 6261: CD 70 64
    JP fn_main_game_loop  ; not 0 yet → keep playing/scrolling        ; 6264: C3 AD 61

; --- Final init pass (phase=0): clear border cells, then hi-score ---
.L6267:
    LD A,$20      ; space char (blank)                                ; 6267: 3E 20
.L6269:           ; clear 5 specific VRAM cells in row 0 / row 14 area
    LD ($3C0D),A  ; row 0, col 13 → blank                            ; 6269: 32 0D 3C
    LD ($3C3B),A  ; row 0, col 59 → blank (right-side border)        ; 626C: 32 3B 3C
    LD ($3C3C),A  ; row 0, col 60 → blank                            ; 626F: 32 3C 3C
    LD ($3C3D),A  ; row 0, col 61 → blank                            ; 6272: 32 3D 3C
    LD ($3C3E),A  ; row 0, col 62 → blank                            ; 6275: 32 3E 3C
    LD BC,$0000   ; BC=0 → maximum ROM delay duration                ; 6278: 01 00 00
    CALL $0060    ; ROM_DELAY: pause (display settle)                 ; 627B: CD 60 00
    CALL $0060    ; ROM_DELAY                                         ; 627E: CD 60 00
    CALL $0060    ; ROM_DELAY                                         ; 6281: CD 60 00
    CALL $0060    ; ROM_DELAY                                         ; 6284: CD 60 00
    CALL $0060    ; ROM_DELAY                                         ; 6287: CD 60 00
    CALL $0060    ; ROM_DELAY (6 × maximum delay = visible pause)     ; 628A: CD 60 00

; --- Hi-score comparison and entry ($628D–$632B) ---
; Tests whether the just-played score ($66A2 = 6-byte packed BCD)
; qualifies for the top-5 hi-score table (stored starting at $63C3).
; Each hi-score entry is 13 bytes ($0D): 6-byte score + 7-byte name.

    LD A,($6696)  ; score accumulator high byte (part of 3-byte BCD) ; 628D: 3A 96 66
.L6290:
    LD HL,($6697) ; score BCD pointer (may be 0 if no score)         ; 6290: 2A 97 66
    OR H          ; combine H,L,A to test for non-zero score          ; 6293: B4
    OR L          ;                                                   ; 6294: B5
    JP Z,$634B    ; score=0 → skip hi-score, jump to fn_title_redraw  ; 6295: CA 4B 63
    LD HL,$66A2   ; HL → packed score bytes (6 bytes at $66A2-$66A7)  ; 6298: 21 A2 66
    LD DE,$6389   ; DE → scratch buffer for score comparison          ; 629B: 11 89 63
    LD BC,$0006   ; copy 6 bytes (full packed BCD score)              ; 629E: 01 06 00
    LDIR          ; save current score to scratch buffer              ; 62A1: ED B0
    LD B,$07      ; 7 bytes to clear                                  ; 62A3: 06 07
    LD HL,$634E   ; buf_score_display: 7-char score display buffer    ; 62A5: 21 4E 63
.L62A8:
    LD (HL),$20   ; fill score display buffer with spaces (blank)     ; 62A8: 36 20
    INC HL                                                            ; 62AA: 23
    DJNZ .L62A8                                                       ; 62AB: 10 FB
    LD C,$05      ; C = 5 (top-5 table; compare against each entry)   ; 62AD: 0E 05
    LD HL,$63C3   ; HL → first entry of hi-score table                ; 62AF: 21 C3 63
.L62B2:           ; --- compare current score against table entry HL ---
    LD A,($66A2)  ; most-significant byte of current score            ; 62B2: 3A A2 66
    CP (HL)       ; compare against hi-score entry's top byte        ; 62B5: BE
    JP C,$6341    ; current score < hi-score → try next entry         ; 62B6: DA 41 63
    JR NZ,$62D0   ; current score > hi-score → insert before HL      ; 62B9: 20 15
    ; Equal top byte: compare remaining 5 bytes one by one
    LD B,$05      ; 5 more bytes to compare                           ; 62BB: 06 05
    PUSH HL       ; save hi-score entry pointer                       ; 62BD: E5
    POP DE        ; DE = HL (copy pointer for INC DE walk)            ; 62BE: D1
    LD IX,$66A2   ; IX → current score bytes                          ; 62BF: DD 21 A2 66
.L62C3:           ; byte-by-byte tiebreak comparison
    INC DE        ; advance hi-score byte pointer                     ; 62C3: 13
    INC IX        ; advance current score byte pointer                ; 62C4: DD 23
    LD A,(DE)     ; hi-score byte                                     ; 62C6: 1A
    CP (IX+0)     ; vs current score byte                             ; 62C7: DD BE 00
    JR C,$62D0    ; hi-score < current → insert here                  ; 62CA: 38 04
    JR NZ,$6341   ; hi-score > current → not a new high score         ; 62CC: 20 73
    DJNZ .L62C3   ; repeat for all 5 remaining bytes                  ; 62CE: 10 F3
.L62D0:           ; --- insert new score at position C (shift entries down) ---
    LD B,C        ; B = current table position (0-4)                  ; 62D0: 41
    DEC C         ; move to next lower position                       ; 62D1: 0D
    JR Z,$62E8    ; C was 1 → already at last slot, just write        ; 62D2: 28 14
    XOR A         ; A = 0 (accumulator for byte offset)               ; 62D4: AF
.L62D5:           ; compute byte offset = position × 13 (entry size)
    ADD A,$0D     ; add 13 per position                               ; 62D5: C6 0D
    DJNZ .L62D5   ; loops B (= original C) times                      ; 62D7: 10 FC
    PUSH HL       ; save target slot pointer                          ; 62D9: E5
    LD B,A        ; B = total bytes to shift = (rank-1) × 13         ; 62DA: 47
    LD HL,$63EF   ; HL → last byte of entry at hi-score table end     ; 62DB: 21 EF 63
    LD DE,$63FC   ; DE → destination (one entry lower in table)       ; 62DE: 11 FC 63
.L62E1:           ; shift existing entries downward (reverse copy)
    LD A,(HL)     ; read byte from higher entry                       ; 62E1: 7E
    LD (DE),A     ; write to lower entry (shifting down)              ; 62E2: 12
    DEC HL        ; move backwards through table                      ; 62E3: 2B
    DEC DE                                                            ; 62E4: 1B
    DJNZ .L62E1   ; repeat for all bytes to shift                     ; 62E5: 10 FA
    POP HL        ; restore target slot pointer                       ; 62E7: E1
.L62E8:           ; --- write new score into the freed slot ---
    LD B,$06      ; copy 6 bytes (full score)                         ; 62E8: 06 06
    LD DE,$66A2   ; DE → current score source buffer                  ; 62EA: 11 A2 66
.L62ED:
    LD A,(DE)     ; read current score byte                           ; 62ED: 1A
    LD (HL),A     ; write into hi-score slot                          ; 62EE: 77
    INC HL                                                            ; 62EF: 23
    INC DE                                                            ; 62F0: 13
    DJNZ .L62ED   ; copy all 6 score bytes                            ; 62F1: 10 FA
    PUSH HL       ; save pointer (now points to name field)           ; 62F3: E5
    CALL $5806    ; SVC_KEYBOARD2: wait/read player initials input     ; 62F4: CD 06 58
    LD HL,$669C   ; HL → initials buffer ("SCORE" at $669C = player name) ; 62F7: 21 9C 66
    LD DE,$549A   ; DE → back-buffer position for score display        ; 62FA: 11 9A 54
    LD BC,$000C   ; 12 bytes to copy                                  ; 62FD: 01 0C 00

; ====================================================================
; fn_copy_terrain  ($6300)
; ====================================================================
; Continues from the hi-score entry code above.  Copies the newly
; formed score entry to the relevant display areas, sets current_zone=1
; (player enters zone 1 / "in-game" state), and rebuilds the score
; display buffer from the hi-score table for on-screen presentation.
; ====================================================================

fn_copy_terrain:   ; $6300
    LDIR          ; copy 12 bytes: initials→back-buffer score display  ; 6300: ED B0
    LD HL,$3EE6   ; VRAM address used as "current terrain pointer"     ; 6302: 21 E6 3E
    LD ($4020),HL ; store terrain pointer at $4020                     ; 6305: 22 20 40
    CALL $5800    ; SVC_DISPLAY: refresh screen from back-buffer       ; 6308: CD 00 58
    LD HL,$634E   ; buf_score_display (7-byte display buffer)          ; 630B: 21 4E 63
    LD B,$06      ; print 6 characters                                 ; 630E: 06 06
    CALL $0040    ; ROM_PRINT_AT: output score display at current pos   ; 6310: CD 40 00
    LD A,$01      ; zone = 1 (now "in game" / active level)            ; 6313: 3E 01
    LD ($6244),A  ; current_zone ← 1                                   ; 6315: 32 44 62
    LD B,$07      ; 7 chars to scan in score buffer                    ; 6318: 06 07
    LD HL,$634E   ; buf_score_display                                  ; 631A: 21 4E 63
.L631D:           ; --- strip leading spaces from score display ---
    LD A,(HL)     ; load display byte                                  ; 631D: 7E
    CP $20        ; is it a space?                                     ; 631E: FE 20
    JR NC,$6329   ; not a space (or >=) → found non-space, stop scan   ; 6320: 30 07
.L6322:
    LD (HL),$20   ; fill remaining positions with space                ; 6322: 36 20
    INC HL                                                             ; 6324: 23
    DJNZ .L6322   ; fill to end of 7-char buffer                       ; 6325: 10 FB
    JR $632C      ; done                                              ; 6327: 18 03
.L6329:
    INC HL        ; advance past non-space byte                        ; 6329: 23
    DJNZ .L631D   ; scan next byte                                     ; 632A: 10 F1
.L632C:           ; --- copy score from display buffer into hi-score table slot ---
    LD B,$07      ; 7 bytes to copy                                    ; 632C: 06 07
    POP HL        ; HL = saved hi-score name-field pointer (from PUSH HL at $62F3) ; 632E: E1
    LD DE,$000D   ; 13 = size of one hi-score entry                   ; 632F: 11 0D 00
    XOR A         ; clear carry                                        ; 6332: AF
    SBC HL,DE     ; HL -= 13: back to start of this entry's name field ; 6333: ED 52
    LD DE,$634E   ; DE → score display buffer (source of formatted name) ; 6335: 11 4E 63
.L6338:           ; copy 7 bytes of formatted name into this hi-score slot
    LD A,(DE)     ; source byte                                        ; 6338: 1A
    LD (HL),A     ; write into hi-score table                          ; 6339: 77
    INC HL                                                             ; 633A: 23
    INC DE                                                             ; 633B: 13
    DJNZ .L6338                                                        ; 633C: 10 FA
.L633E:           ; return to title screen (hi-score entry complete)
    JP fn_title_redraw  ; redraw title/attract screen                  ; 633E: C3 E1 60
.L6341:           ; --- this table entry has higher score: advance to next slot ---
    LD DE,$000D   ; 13 bytes per hi-score entry                        ; 6341: 11 0D 00
    ADD HL,DE     ; HL → next entry                                    ; 6344: 19
    DEC C         ; one fewer entry to check                           ; 6345: 0D
    JP NZ,$62B2   ; still entries remaining → compare next             ; 6346: C2 B2 62
    JR $633E      ; all 5 checked, score didn’t qualify → title screen ; 6349: 18 F3
.L634B:
    JP fn_title_redraw  ; no score (or score=0) → title screen         ; 634B: C3 E1 60

buf_score_display:   ; $634E
    DB       $00,$00,$00,$00,$00,$00,$00  ; 7-byte score display work buffer (RAM, init=0)

; ====================================================================
; fn_draw_status_bar  ($6355)
; ====================================================================
; Renders the ship-icon tiles into the HUD / status-bar area of the
; back-buffer (rows 14–15 at $54B0+).  Also copies the "*LAST*" hi-score
; label if current_zone ≠ 0 (i.e. the game is in progress).
;
; On entry: no parameters (uses fixed addresses)
; IX format during loop: IX points through data_ship_sprite (13 bytes
;   wide, 5 rows).  Each row is written to HL, then HL advances 64
;   bytes (one screen row) by adding DE=$0033 (51) after the 13 bytes.
; ====================================================================

fn_draw_status_bar:   ; $6355
    LD C,$05      ; C = 5 rows to render                              ; 6355: 0E 05
    LD DE,$0033   ; $33 = 51: stride padding per row (64 - 13 = 51)  ; 6357: 11 33 00
    LD HL,$54B0   ; HL → back-buffer row-14 col-16 (HUD ship area)    ; 635A: 21 B0 54
    LD IX,$63BC   ; IX → data_ship_sprite: 5×13 byte sprite            ; 635D: DD 21 BC 63
.L6361:
    LD B,$0D      ; B = 13 bytes per sprite row                       ; 6361: 06 0D
.L6363:           ; inner: copy 13 bytes of sprite row to back-buffer
    LD A,(IX+0)   ; sprite pixel byte                                 ; 6363: DD 7E 00
    LD (HL),A     ; write to back-buffer                              ; 6366: 77
    INC IX        ; next sprite byte                                  ; 6367: DD 23
    INC HL        ; next screen column                                ; 6369: 23
    DJNZ .L6363   ; loop 13 times (one sprite row)                    ; 636A: 10 F7
    ADD HL,DE     ; skip 51 bytes to align HL to next screen row      ; 636C: 19
    DEC C         ; one fewer row to go                               ; 636D: 0D
    JR NZ,.L6361  ; repeat for all 5 rows                             ; 636E: 20 F1
    LD A,($6244)  ; current_zone                                      ; 6370: 3A 44 62
    CP $00        ; are we still on the title screen?                 ; 6373: FE 00
    RET Z         ; zone=0 → no in-game hi-score label needed          ; 6375: C8
    LD HL,$6382   ; HL → "*LAST*       >" string in fn_copy_hiscore   ; 6376: 21 82 63
    LD DE,$5630   ; DE → back-buffer position for hi-score label      ; 6379: 11 30 56
    LD BC,$000D   ; 13 bytes to copy                                  ; 637C: 01 0D 00
    LDIR          ; copy "*LAST*       >" into back-buffer             ; 637F: ED B0
; 
; ; ---- fn_draw_status_bar --------------------------------------
; ; Draws score, lives, fuel gauge in the bottom row of the
; ; screen (row 15, y=15*64 = $3FC0 in video RAM).

fn_draw_status_bar:   ; $6355
    LD C,$05                                                ; 6355: 0E 05
    LD DE,$0033  ; ROM_PRINT_CHAR                           ; 6357: 11 33 00
    LD HL,$54B0                                             ; 635A: 21 B0 54
    LD IX,$63BC  ; data_ship_sprite                         ; 635D: DD 21 BC 63
.L6361:
    LD B,$0D                                                ; 6361: 06 0D
.L6363:
    LD A,(IX++0)                                            ; 6363: DD 7E 00
    LD (HL),A                                               ; 6366: 77
    INC IX                                                  ; 6367: DD 23
    INC HL                                                  ; 6369: 23
    DJNZ $6363                                              ; 636A: 10 F7
    ADD HL,DE                                               ; 636C: 19
    DEC C                                                   ; 636D: 0D
    JR NZ,$6361                                             ; 636E: 20 F1
    LD A,($6244)  ; current_zone                            ; 6370: 3A 44 62
    CP $00                                                  ; 6373: FE 00
    RET Z                                                   ; 6375: C8
    LD HL,$6382                                             ; 6376: 21 82 63
    LD DE,$5630                                             ; 6379: 11 30 56
    LD BC,$000D                                             ; 637C: 01 0D 00
    LDIR                                                    ; 637F: ED B0

fn_copy_hiscore:   ; $6381
    RET                                                     ; 6381: C9
    DB       $2A,$4C,$41,$53,$54,$2A,$20,$20,$20,$20,$20,$20,$20,$3E ; |*LAST*       >|
; ====================================================================
; fn_copy_hiscore  ($6381)
; ====================================================================
; Just a RET stub.  The 14 bytes following the RET form the hi-score
; label string "*LAST*       >".  The trailing > ($3E) is ALSO the Z80
; opcode for LD A,n — so calling the address $638F (where > lives)
; executes "LD A,$00" (bytes $3E $00) which falls into fn_init_ship_pos
; below.  This is an intentional dual-use byte.
; ====================================================================

fn_copy_hiscore:   ; $6381
    RET           ; return to fn_draw_status_bar (normal exit)        ; 6381: C9
    DB       $2A,$4C,$41,$53,$54,$2A,$20,$20,$20,$20,$20,$20,$20,$3E ; |*LAST*       >|
    ; ^ last byte $3E = ASCII ‘>’ AND Z80 opcode LD A,imm8
    ; calling $638F executes "LD A,$00" spanning $638F-$6390

; ====================================================================
; fn_init_ship_pos  (entry at $638F, labelled at $6390)
; ====================================================================
; Resets ship position variables to the start-of-level defaults:
;   ship_screen_col = 0   ship_pixel_y = 0   ship_char_code = 0
;   ship_screen_row = 5   ship_pixel_x  = $67 (103 px)  prev_char=$67
; NOTE: "fn_init_game_state" was an older (incorrect) name; this
; function does NOT touch score, lives, or fuel.
; Entry is at $638F: the byte $3E (end of the *LAST* string above)
; serves as "LD A," opcode; the $00 NOP at $6390 is its argument.
; ====================================================================

fn_init_game_state:   ; $6390  (real entry at $638F via "LD A,$00" trick)
    NOP           ; $00 = arg byte for "LD A,$00" at $638F            ; 6390: 00
    LD ($6AB6),A  ; ship_screen_col ← 0                               ; 6391: 32 B6 6A
    LD ($6AC2),A  ; ship_pixel_y   ← 0                               ; 6394: 32 C2 6A
    LD ($6AC3),A  ; ship_char_code ← 0                               ; 6397: 32 C3 6A
    LD A,$05      ; row 5 = mid-screen starting row                  ; 639A: 3E 05
    LD ($6AB7),A  ; ship_screen_row ← 5                              ; 639C: 32 B7 6A
    LD A,$67      ; pixel X = $67 = 103: ship’s initial X position   ; 639F: 3E 67
    LD ($6AC1),A  ; ship_pixel_x  ← $67                              ; 63A1: 32 C1 6A
    LD ($6AC4),A  ; ship_prev_char ← $67 (saves previous VRAM char)  ; 63A4: 32 C4 6A
    RET           ; return to caller                                 ; 63A7: C9
    DB       $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00 ; |................|
    DB       $00,$00,$00,$00                                         ; |....|

; ====================================================================
; data_ship_sprite  ($63BC)
; ====================================================================
; 65-byte working buffer that holds the current ship sprite pixels.
; Initially filled with $20 (space = transparent cell).  Each game
; frame the ship-drawing code composites the ship shape into this
; buffer before blitting it to VRAM.
; Immediately after the 65-byte buffer, $63FD-$63FE are 2-byte RAM
; (hi-score entry counter/animation frame index reused as variables).
; The 65 bytes are: 5 rows × 13 columns = 65 cells.
; ====================================================================

data_ship_sprite:   ; $63BC  [65-byte sprite buffer, all $20 initially]
    DB       $20,$20,$20,$20,$20,$20,$20,$20,$20,$20,$20,$20,$20     ; row 0: all blank
    ; $63C9-$63FC: rows 1-4 (all $20 = transparent space)           ; decoded as JR NZ by z80dasm
    DB       $20,$20  ; 63C9
    DB       $20,$20  ; 63CB
    DB       $20,$20  ; 63CD
    DB       $20,$20  ; 63CF
    DB       $20,$20  ; 63D1
    DB       $20,$20  ; 63D3
    DB       $20,$20  ; 63D5
    DB       $20,$20  ; 63D7
    DB       $20,$20  ; 63D9
    DB       $20,$20  ; 63DB
    DB       $20,$20  ; 63DD
    DB       $20,$20  ; 63DF
    DB       $20,$20  ; 63E1
    DB       $20,$20  ; 63E3
    DB       $20,$20  ; 63E5
    DB       $20,$20  ; 63E7
    DB       $20,$20  ; 63E9
    DB       $20,$20  ; 63EB
    DB       $20,$20  ; 63ED
    DB       $20,$20  ; 63EF
    DB       $20,$20  ; 63F1
    DB       $20,$20  ; 63F3
    DB       $20,$20  ; 63F5
    DB       $20,$20  ; 63F7
    DB       $20,$20  ; 63F9
    DB       $20,$20  ; 63FB (last 2 bytes of row 4)
    ; $63FD-$63FE: embedded-in-sprite animation counter variables
    DB       $00      ; 63FD: attract_sub_frame counter (0-9)
    DB       $00      ; 63FE: attract_frame_index (increments every 10 subframes)

; ====================================================================
; fn_draw_ship_to_vram  ($63FF)
; ====================================================================
; Directly blits the ship-sprite buffer (data_ship_sprite at $63BC)
; to video RAM at $3E20 (row 8, col 32 of the 64×16 VRAM grid).
; 5 rows × 13 bytes, skipping 51 bytes between rows to align.
; Unlike fn_draw_ship ($65A3), this writes WITHOUT transparency.
; ====================================================================

    LD C,$05      ; 5 rows to draw                                    ; 63FF: 0E 05
    LD DE,$0033   ; stride padding per row (64 - 13 = 51 bytes)      ; 6401: 11 33 00
    LD HL,$3E20   ; VRAM destination: row 8, col 32 ($3C00+8*64+32)  ; 6404: 21 20 3E
    LD IX,$63BC   ; IX → data_ship_sprite source buffer               ; 6407: DD 21 BC 63
.L640B:
    LD B,$0D      ; 13 bytes per sprite row                           ; 640B: 06 0D
.L640D:
    LD A,(IX+0)   ; sprite byte from buffer                          ; 640D: DD 7E 00
    LD (HL),A     ; write direct to VRAM (no transparency check)     ; 6410: 77
    INC IX        ; next sprite byte                                  ; 6411: DD 23
    INC HL        ; next VRAM column                                  ; 6413: 23
    DJNZ .L640D   ; loop 13 times (one row)                           ; 6414: 10 F7
    ADD HL,DE     ; advance HL by 51 to reach start of next VRAM row  ; 6416: 19
    DEC C         ; one fewer row                                     ; 6417: 0D
    JR NZ,.L640B  ; repeat for all 5 rows                             ; 6418: 20 F1
    RET           ; done                                             ; 641A: C9

; ====================================================================
; fn_init_score_display  ($641B)
; ====================================================================
; Initialise / reset the attract-mode animation counters embedded in
; the sprite buffer at $63FD-$63FE.  Called from fn_title_redraw to
; restart the score-table cycling animation.
; ====================================================================

    LD HL,$0000   ; HL = 0 (zero both counter bytes)                  ; 641B: 21 00 00
    LD ($63FD),HL ; attract_sub_frame ← 0 (low byte)                   ; 641E: 22 FD 63
    LD ($63FE),HL ; attract_frame_index ← 0 (high byte)                ; 6421: 22 FE 63
    RET           ; return                                            ; 6424: C9

; ====================================================================
; fn_attract_mode  ($6425)
; ====================================================================
; Advance one tick of the attract-mode score-table animation.
; Increments attract_sub_frame at $63FD; when it reaches 10 ($0A),
; resets it to 0 and increments attract_frame_index at $63FE.
; Returns NZ while the animation is still running (frame index != 0).
; Returns Z when the animation cycle completes (used to trigger
; the "any key" wait in the title loop).
; ====================================================================

    LD A,($63FD)  ; attract_sub_frame (0–9)                           ; 6425: 3A FD 63
    INC A         ; advance sub-frame                                 ; 6428: 3C
    LD ($63FD),A  ; store updated sub-frame                           ; 6429: 32 FD 63
    SUB $0A       ; has sub-frame reached 10?                         ; 642C: D6 0A
    RET NZ        ; no → return NZ (still animating)                  ; 642E: C0
    LD ($63FD),A  ; yes → reset sub-frame to 0 (A=0 after SUB)        ; 642F: 32 FD 63
    LD HL,($63FE) ; load 16-bit frame index                           ; 6432: 2A FE 63
    INC HL        ; advance frame                                     ; 6435: 23
    LD ($63FE),HL ; store new frame index                             ; 6436: 22 FE 63
    LD A,H        ; test if frame index has wrapped to 0              ; 6439: 7C
    OR L          ; combine H and L                                   ; 643A: B5
    RET           ; return Z if frame=0 (cycle done), NZ if still running ; 643B: C9
; ====================================================================
; fn_clear_buffers  ($643C)
; ====================================================================
; Initialises the double-buffered display system and resets game state
; for a clean level start.  Called at game-over and zone transition.
; Steps:
;   1. Fill 2K at $73CC with $80 (blank semigraphic cell)
;   2. Fill 128 bytes at $7284 with $2F (terrain scroll buffer init)
;   3. Set level-init counter ($64C9) = 3
;   4. Call fn_erase_ship (clear ship state)
;   5. Set terrain step value, ship-path pointer, and step counter
; The back-buffer at $5400-$57FF is NOT cleared here (that’s the splash
; screen buffer, cleared separately by SVC_MISC at $5809).
; ====================================================================

    LD HL,$73CC    ; LDIR-fill idiom: src = $73CC                    ; 643C: 21 CC 73
    LD DE,$73CC    ; dst = $73CC (same start)                        ; 643F: 11 CC 73
    INC DE         ; dst now $73CD (1 ahead of src)                  ; 6442: 13
    LD (HL),$80    ; seed first byte with $80 (blank semigraphic)    ; 6443: 36 80
    LD BC,$0800    ; 2048 bytes to fill                              ; 6445: 01 00 08
    LDIR           ; fill entire 2K display page with $80            ; 6448: ED B0
    LD HL,$7284    ; LDIR-fill idiom: src = $7284                    ; 644A: 21 84 72
    LD DE,$7284    ; dst = $7284                                     ; 644D: 11 84 72
    INC DE         ; dst = $7285                                     ; 6450: 13
    LD (HL),$2F    ; seed first byte: $2F = ‘/’ (terrain scroll seed)  ; 6451: 36 2F
    LD BC,$0080    ; 128 bytes to fill                               ; 6453: 01 80 00
    LDIR           ; fill scroll buffer with $2F                     ; 6456: ED B0
    LD A,$03       ; level-init phase counter initial value = 3      ; 6458: 3E 03
    LD ($64C9),A   ; init_phase ← 3                                   ; 645A: 32 C9 64
    CALL $65AE     ; fn_erase_ship: clear ship position/state vars   ; 645D: CD AE 65
    LD A,$2F       ; terrain step = $2F = ‘/’ (initial terrain char)   ; 6460: 3E 2F
    LD ($6AAD),A   ; terrain_step ← $2F                              ; 6462: 32 AD 6A
    LD HL,$6F8B    ; HL → ship Y-path table (sine-wave data)         ; 6465: 21 8B 6F
    LD ($6ABA),HL  ; ship_path_ptr ← $6F8B                           ; 6468: 22 BA 6A
    LD A,$40       ; initial path step counter = 64                  ; 646B: 3E 40
    LD ($6ABC),A   ; ship_path_step ← $40                            ; 646D: 32 BC 6A

; ====================================================================
; fn_update_display  ($6470)
; ====================================================================
; Resets the sprite/object bitmask buffers used for hit-detection and
; display.  Called each frame to clear stale collision data before
; the objects are re-rendered at their new positions.
;   $7304-$73CB: sprite presence bitmask table (200 bytes)
;   $663F-$667A: enemy/ship overlap flags (60 bytes)
; ====================================================================

fn_update_display:   ; $6470
    LD A,$04       ; initial sentinel value                           ; 6470: 3E 04
    LD ($6AAE),A   ; ship_x_lo ← 4 (reset sub-pixel X)               ; 6472: 32 AE 6A
    LD ($6AAF),A   ; ship_x_hi ← 4 (reset sub-pixel X high)           ; 6475: 32 AF 6A
    LD HL,$7304    ; LDIR-fill idiom: collision/sprite table start    ; 6478: 21 04 73
    LD DE,$7304    ; dst = same (copy trick)                          ; 647B: 11 04 73
    INC DE         ; dst = $7305                                     ; 647E: 13
    LD (HL),$00    ; seed first byte with 0 (no sprites present)     ; 647F: 36 00
    LD BC,$00C8    ; 200 bytes to zero                               ; 6481: 01 C8 00
    LDIR           ; clear sprite bitmask table                      ; 6484: ED B0
    LD HL,$663F    ; LDIR-fill idiom: enemy/ship overlap flags start  ; 6486: 21 3F 66
    LD DE,$663F    ; dst = same                                      ; 6489: 11 3F 66
    INC DE         ; dst = $6640                                     ; 648C: 13
    LD (HL),$00    ; seed with 0 (no overlap)                        ; 648D: 36 00
    LD BC,$003C    ; 60 bytes to zero                                ; 648F: 01 3C 00
    LDIR           ; clear enemy/ship overlap flags                  ; 6492: ED B0
    RET            ; return to caller                                ; 6494: C9

; ====================================================================
; fn_draw_terrain  ($6495)
; ====================================================================
; Iterates across the entire video RAM ($3C00-$3FFF) and INVERTS each
; semigraphic cell.  Semigraphic cells have bit 7 set ($80-$FF):
;   raw byte b → screen byte = $BF - (b - $80) = $BF - b + $80
; This flips the 6-pixel pattern within the cell:  a fully-lit cell
; ($BF) becomes blank ($80) and vice versa, creating the cave/tunnel
; appearance for the terrain (foreground colour vs background).
; Plain ASCII cells (b < $80) are left unchanged.
; ====================================================================

fn_draw_terrain:   ; $6495
    LD HL,$3C00    ; HL → start of video RAM                         ; 6495: 21 00 3C
.L6498:
    LD A,(HL)      ; load current VRAM byte                          ; 6498: 7E
    SUB $80        ; subtract $80: result < 0 implies plain ASCII    ; 6499: D6 80
    JR C,.L64A2  ; bit 7 clear → plain ASCII cell, skip inversion    ; 649B: 38 05
    LD D,A         ; D = (original_byte - $80) = semigraphic data bits ; 649D: 57
    LD A,$BF       ; $BF = all 6 pixel-bits set ($80|$3F)              ; 649E: 3E BF
    SUB D          ; A = $BF - (byte-$80): complement the pattern      ; 64A0: 92
    LD (HL),A      ; write inverted cell back to VRAM                 ; 64A1: 77
.L64A2:
    INC HL         ; advance to next VRAM cell                        ; 64A2: 23
    LD A,$40       ; test if we have passed $3FFF (H=$40)             ; 64A3: 3E 40
    CP H           ; compare H with $40                               ; 64A5: BC
    JR NZ,.L6498  ; not past end → keep scanning                      ; 64A6: 20 F0
    RET            ; done: all VRAM cells inverted                    ; 64A8: C9

; ====================================================================
; terrain data area  ($64A9–$64C9)  [RAM / data, NOT executable code]
; ====================================================================
; These bytes are game-state variables and a data table used by
; fn_scroll_screen.  z80dasm decodes them as instructions but they
; are purely data referenced by 16-bit load/store operations.
;
;  $64A9-$64AB: (scratch / alignment padding, 3 zero bytes)
;  $64AC: LD A,L   – byte value $7D  (terrain colour LUT entry)
;  $64AD: $00     – LUT entry
;  $64AE: $4B ‘K’  – terrain step table entry
;  $64AF: $00     – entry
;  $64B0: $64 ‘d’  – entry
;  $64B1: $00     – entry
;  $64B2: $96     – entry (semigraphic char)
;  $64B3: $00     – entry
;  $64B4: $4B ‘K’  – entry
;  $64B5: $00     – entry
;  $64B6-$64B8: $32 $00 $19 – 3-byte entry (LD, addr lo/hi decoded as code)
;  $64B9: $00     – entry
; (↑ these 17 bytes form the scroll-speed / stride lookup table)
; ====================================================================

    NOP                                                     ; 64A9: 00
    NOP                                                     ; 64AA: 00
    NOP                                                     ; 64AB: 00
    LD A,L                                                  ; 64AC: 7D  ;  terrain LUT[0]
    NOP                                                     ; 64AD: 00
    LD C,E                                                  ; 64AE: 4B  ;  terrain LUT[1]
    NOP                                                     ; 64AF: 00
    LD H,H                                                  ; 64B0: 64  ;  terrain LUT[2]
    NOP                                                     ; 64B1: 00
    SUB (HL)                                                ; 64B2: 96  ;  terrain LUT[3]
    NOP                                                     ; 64B3: 00
    LD C,E                                                  ; 64B4: 4B  ;  terrain LUT[4]
    NOP                                                     ; 64B5: 00
    LD ($1900),A                                            ; 64B6: 32 00 19  ; terrain LUT[5]
    NOP                                                     ; 64B9: 00

; ---- RAM variables for fn_scroll_screen -------------------------
scroll_phase:   ; $64BA  [byte: which scroll-step is currently active; 0=idle]
    NOP            ; $64BA: scroll_phase (init=0)                     ; 64BA: 00
    NOP            ; $64BB: scroll_mode (latched copy of scroll_phase) ; 64BB: 00
    NOP            ; $64BC: scroll_count (pulse-pair repeat count)    ; 64BC: 00
    NOP            ; $64BD: scroll_speed_table[0] (phase 1 speed)     ; 64BD: 00
    LD A,(BC)      ; $64BE: scroll_speed_table[1]                     ; 64BE: 0A
    LD A,(BC)      ; $64BF: scroll_speed_table[2]                     ; 64BF: 0A
    LD A,(BC)      ; $64C0: scroll_speed_table[3]                     ; 64C0: 0A
    LD A,(BC)      ; $64C1: scroll_speed_table[4]                     ; 64C1: 0A
    LD A,(BC)      ; $64C2: scroll_speed_table[5]                     ; 64C2: 0A
    LD B,$06       ; $64C3-4: scroll_speed_table[6-7]                 ; 64C3: 06 06
    DJNZ $64EF     ; $64C5-6: scroll_speed_table[8-9]                 ; 64C5: 10 28
    INC A          ; $64C7: scroll_speed_table[10]                    ; 64C7: 3C
    NOP            ; $64C8: scroll_phase_2 (secondary phase counter)  ; 64C8: 00
    NOP            ; $64C9: init_phase (level-init countdown, 3→0)    ; 64C9: 00

; ====================================================================
; fn_scroll_screen  ($64CA)
; ====================================================================
; Controls the TRS-80 floppy-disk motor via OUT port $FF to produce
; the scrolling sound effect (alternating motor pulses).
; Also manages the multi-step scroll animation phase state.
;
; scroll_phase ($64BA):
;   0 = idle (no scroll in progress)
;   1–5 = slow-scroll phases (use shorter pulse pairs)
;   6,7 = medium-scroll phases
;   8   = fast-scroll phase
;   9   = initial  level-fill phase (terrain being drawn)
;  10   = post-collision / death scroll
;
; Port $FF (OUT($FF),A):
;   A=1 → pulse motor ON    A=2 → pulse motor OFF
;   Alternating pulses generate the scrolling "whoosh" sound.
;
; scroll_mode  ($64BB): latched phase so scroll_phase can be cleared.
; scroll_count ($64BC): counts down pulse pairs; 0=scroll done.
; ====================================================================

fn_scroll_screen:   ; $64CA
    LD A,($64BA)   ; scroll_phase: is a scroll step requested?       ; 64CA: 3A BA 64
    CP $00         ; 0 = idle                                        ; 64CD: FE 00
    JR Z,.L64E4    ; idle → skip new-phase setup, read scroll_mode    ; 64CF: 28 13
    ; --- Latch new scroll phase ---
    LD ($64BB),A   ; scroll_mode ← scroll_phase (latch current phase) ; 64D1: 32 BB 64
    LD HL,$64BD    ; HL → start of scroll speed table                ; 64D4: 21 BD 64
    LD D,$00       ; D = 0 (16-bit offset)                           ; 64D7: 16 00
    LD E,A         ; E = scroll_phase (index into speed table)       ; 64D9: 5F
    ADD HL,DE      ; HL → speed table[scroll_phase]                  ; 64DA: 19
    LD A,(HL)      ; load pulse repeat count for this phase          ; 64DB: 7E
    LD ($64BC),A   ; scroll_count ← pulse repeat count               ; 64DC: 32 BC 64
    LD A,$00       ; clear phase (will re-trigger only if set again) ; 64DF: 3E 00
    LD ($64BA),A   ; scroll_phase ← 0 (idle)                         ; 64E1: 32 BA 64
.L64E4:            ; --- dispatch on scroll_mode to appropriate pulse timing ---
    LD A,($64BB)   ; scroll_mode: what kind of scroll is this?       ; 64E4: 3A BB 64
    CP $00         ; mode 0 = pure timing delay (no motor pulse)     ; 64E7: FE 00
    JR Z,$6512     ; → do soft-delay loop (no audio pulse)           ; 64E9: 28 27
    CP $01         ; modes 1–5: slow terrain scroll                   ; 64EB: FE 01
    JR Z,$651C     ; → slow pulse path                               ; 64ED: 28 2D
.L64EF:
    CP $02                                                   ; 64EF: FE 02  ; mode 2
    JR Z,$651C     ; slow                                            ; 64F1: 28 29
    CP $03                                                   ; 64F3: FE 03  ; mode 3
    JR Z,$651C     ; slow                                            ; 64F5: 28 25
    CP $04                                                   ; 64F7: FE 04  ; mode 4
    JR Z,$651C     ; slow                                            ; 64F9: 28 21
    CP $05                                                   ; 64FB: FE 05  ; mode 5
    JR Z,$651C     ; slow                                            ; 64FD: 28 1D
    CP $06         ; modes 6,7: medium scroll                        ; 64FF: FE 06
    JR Z,$652E     ; → medium pulse path                             ; 6501: 28 2B
    CP $07                                                   ; 6503: FE 07
    JR Z,$652E     ; medium                                          ; 6505: 28 27
    CP $08         ; mode 8: fast scroll                             ; 6507: FE 08
    JR Z,$6534     ; → fast pulse path                               ; 6509: 28 29
    CP $0A         ; mode 10: post-death / game-over scroll           ; 650B: FE 0A
    JP Z,$654B     ; → special slow path                             ; 650D: CA 4B 65
    JR $653A       ; default: medium-fast path                       ; 6510: 18 28
.L6512:            ; --- mode 0: pure delay (no motor pulse output) ---
    LD C,$03       ; 3 outer delay loops                             ; 6512: 0E 03
.L6514:
    LD B,$64       ; 100 inner loops                                 ; 6514: 06 64
.L6516:
    DJNZ .L6516    ; tight inner delay loop (B × 1 NOP-equivalent)    ; 6516: 10 FE
    DEC C          ; outer loop counter                              ; 6518: 0D
    JR NZ,.L6514   ; repeat 3 × 100 iterations                       ; 6519: 20 F9
    RET            ; return (no motor output)                        ; 651B: C9
.L651C:            ; --- modes 1–5: slow-scroll pulse timing ---
    LD E,$4B       ; pulse duration = $4B = 75 (iterations)          ; 651C: 1E 4B
    LD C,$02       ; 2 pulse pairs per scroll step                   ; 651E: 0E 02
    LD A,($64BC)   ; scroll_count: remaining steps                   ; 6520: 3A BC 64
    CP $04         ; fewer than 4 remaining?                         ; 6523: FE 04
    JP NC,$6551    ; ≥ 4 remaining → use normal E=$4B rate             ; 6525: D2 51 65
    LD E,$28       ; near end: slow down to E=$28=40 (longer pulses)  ; 6528: 1E 28
    LD C,$04       ; 4 pulse pairs                                   ; 652A: 0E 04
    JR $6551       ; → common pulse-output entry point               ; 652C: 18 23
.L652E:            ; --- modes 6,7: medium-scroll pulse timing ---
    LD E,$96       ; pulse duration = $96 = 150 (medium)              ; 652E: 1E 96
    LD C,$01       ; 1 pulse pair per step                           ; 6530: 0E 01
    JR $6551       ; → pulse output                                  ; 6532: 18 1D
.L6534:            ; --- mode 8: fast-scroll pulse timing ---
    LD E,$32       ; pulse duration = $32 = 50 (short = fast)         ; 6534: 1E 32
    LD C,$03       ; 3 pulse pairs                                   ; 6536: 0E 03
    JR $6551       ; → pulse output                                  ; 6538: 18 17
.L653A:            ; --- default path: medium-fast timing ---
    LD E,$32       ; pulse duration = 50                             ; 653A: 1E 32
    LD C,$0F       ; 15 pulse pairs                                  ; 653C: 0E 0F
    LD A,($64BC)   ; remaining scroll steps                          ; 653E: 3A BC 64
    CP $14         ; fewer than 20 steps?                            ; 6541: FE 14
    JR NC,$6551    ; no → use current timing                          ; 6543: 30 0C
    LD E,$96       ; yes → use longer pulse duration                   ; 6545: 1E 96
    LD C,$05       ; 5 pulse pairs (slow down near end)              ; 6547: 0E 05
    JR $6551       ; → pulse output                                  ; 6549: 18 06
.L654B:            ; --- mode 10: post-death slow path ---
    LD E,$1E       ; pulse duration = $1E = 30 (very slow)            ; 654B: 1E 1E
    LD C,$05       ; 5 pulse pairs                                   ; 654D: 0E 05
    JR $6551       ; → pulse output (fall-through)                   ; 654F: 18 00
.L6551:            ; --- common pulse output: E=duration, C=repeat count ---
    LD A,$01       ; motor-on value                                  ; 6551: 3E 01
    OUT ($FF),A    ; TRS-80 port $FF: cassette/motor ON pulse         ; 6553: D3 FF
    LD B,E         ; B = pulse duration                              ; 6555: 43
.L6556:
    DJNZ .L6556    ; delay loop (motor ON for E iterations)           ; 6556: 10 FE
    LD A,$02       ; motor-off value                                 ; 6558: 3E 02
    OUT ($FF),A    ; TRS-80 port $FF: cassette/motor OFF pulse        ; 655A: D3 FF
    LD B,E         ; B = pulse duration                              ; 655C: 43
.L655D:
    DJNZ .L655D    ; delay loop (motor OFF for E iterations)          ; 655D: 10 FE
    DEC C          ; one fewer pulse pair                            ; 655F: 0D
    JR NZ,.L6551   ; repeat C pulse pairs                             ; 6560: 20 EF
    ; --- decrement overall scroll_count; if 0 clear scroll_mode ---
    LD A,($64BC)   ; remaining scroll steps                          ; 6562: 3A BC 64
    DEC A          ; step count -= 1                                 ; 6565: 3D
    LD ($64BC),A   ; update scroll_count                             ; 6566: 32 BC 64
    CP $00         ; done?                                           ; 6569: FE 00
    RET NZ         ; not yet done → return (will be called again)      ; 656B: C0
    LD ($64BB),A   ; scroll_mode ← 0 (clear: scroll complete)          ; 656C: 32 BB 64
    RET            ; return                                          ; 656F: C9

; ====================================================================
; fn_update_terrain_scroll  ($6570)
; ====================================================================
; Called each full-update frame.  Draws the level-progression bar
; (a row of [ $5B ] chars in VRAM row 0 col 13 onwards), decrement
; the terrain phase counter, and (when phase reaches 0) calls
; fn_move_ship to advance the ship along its Y-path and draws it.
; Also writes the "top terrain" data to VRAM rows 0 and 13.
; ====================================================================

    LD A,($64C9)   ; init_phase counter (from fn_clear_buffers = 3)  ; 6570: 3A C9 64
    CP $10         ; phase >= 16?                                    ; 6573: FE 10
    JR C,$6579     ; no → use raw phase as B                          ; 6575: 38 02
    LD A,$0F       ; cap at 15 columns                               ; 6577: 3E 0F
.L6579:
    LD B,A         ; B = number of [brackets] to draw in header row  ; 6579: 47
    LD HL,$3C0D    ; VRAM row 0, col 13 (after status char area)     ; 657A: 21 0D 3C
.L657D:
    LD (HL),$5B    ; write ‘[’ = $5B (used as terrain bar char)        ; 657D: 36 5B
    INC HL         ; next column                                     ; 657F: 23
    DJNZ .L657D    ; repeat B times                                  ; 6580: 10 FB
    LD A,($64C8)   ; scroll_phase_2 counter                          ; 6582: 3A C8 64
    CP $00         ; is it 0 (time to move ship)?                    ; 6585: FE 00
    JR Z,$6590     ; yes → skip decrement, go draw ship               ; 6587: 28 07
    DEC A          ; decrement phase_2 counter                       ; 6589: 3D
    LD ($64C8),A   ; store updated counter                           ; 658A: 32 C8 64
    CALL Z,$65BF   ; if just reached 0, call fn_move_ship            ; 658D: CC BF 65
.L6590:            ; --- draw ship sprite to VRAM ---
    LD HL,$669C    ; HL → ship colour/pixel data at $669C             ; 6590: 21 9C 66
    LD DE,$3C00    ; DE → VRAM start (row 0)                         ; 6593: 11 00 3C
    LD B,$0C       ; 12 bytes to copy (ship sprite row 0)            ; 6596: 06 0C
    CALL $65A3     ; fn_draw_ship: copy with transparency (skip $20) ; 6598: CD A3 65
    LD HL,$66A8    ; HL → second ship row pixel data at $66A8         ; 659B: 21 A8 66
    LD DE,$3C39    ; DE → VRAM row 0, col 57 ($3C00 + 57)            ; 659E: 11 39 3C
    LD B,$06       ; 6 bytes to copy (second sprite row)             ; 65A1: 06 06

; ====================================================================
; fn_draw_ship  ($65A3)
; ====================================================================
; Copies B bytes from sprite buffer (HL) to VRAM (DE) with per-byte
; transparency: bytes equal to $20 (ASCII space) are skipped so the
; background shows through.  Falls through from fn_update_terrain_scroll
; with a second call for the lower ship row.
; ====================================================================

fn_draw_ship:   ; $65A3
    LD A,(HL)      ; load sprite byte from buffer                    ; 65A3: 7E
    CP $20         ; is it $20 = transparent (space) pixel?          ; 65A4: FE 20
    JR Z,.L65A9    ; yes → skip VRAM write (transparent)              ; 65A6: 28 01
    LD (DE),A      ; no → write sprite pixel to VRAM                 ; 65A8: 12
.L65A9:
    INC HL         ; next sprite byte                                ; 65A9: 23
    INC DE         ; next VRAM cell                                  ; 65AA: 13
    DJNZ fn_draw_ship  ; loop for all B bytes                        ; 65AB: 10 F6
    RET            ; done                                            ; 65AD: C9

; ====================================================================
; fn_erase_ship  ($65AE)
; ====================================================================
; Clears the score/ship-position state variables, then falls into
; fn_check_ship_crash to clear the 6-cell overlap record buffer.
; Called from fn_clear_buffers at game start.
; ====================================================================

fn_erase_ship:   ; $65AE
    LD HL,$0000    ; zero value                                      ; 65AE: 21 00 00
    LD ($6697),HL  ; score_ptr_lo/hi ← 0 (reset score accumulator ptr) ; 65B1: 22 97 66
    LD A,$00       ; A = 0                                           ; 65B4: 3E 00
    LD ($6696),A   ; score_hi_byte ← 0                               ; 65B6: 32 96 66
    LD HL,$66A2    ; HL → score data buffer ($66A2-$66A7)             ; 65B9: 21 A2 66
    CALL $65C2     ; fn_check_ship_crash: zeroes 6 bytes at HL       ; 65BC: CD C2 65

; ====================================================================
; fn_move_ship  ($65BF)
; ====================================================================
; Advances the ship along the Y-path defined by a lookup table,
; adjusting the ship’s screen row over time.  Falls into
; fn_check_ship_crash to clear any stale overlap.
; ====================================================================

fn_move_ship:   ; $65BF
    LD HL,$66A8    ; HL → second ship row data buffer ($66A8)         ; 65BF: 21 A8 66

; ====================================================================
; fn_check_ship_crash  ($65C2)
; ====================================================================
; Zeroes a 6-byte overlap/collision record buffer pointed to by HL.
; The first 6 bytes encode which cells the ship occupies; clearing
; them prepares for the next frame’s collision detection pass.
; Entry from fn_move_ship: HL=$66A8 (second ship-row overlap buffer).
; Entry from fn_erase_ship: HL=$66A2 (first ship-row overlap buffer).
; The actual collision TEST (reading VRAM chars at ship position)
; is done in the code at $65CA onwards.
; ====================================================================

; ====================================================================
; fn_clear_overlap_buf  ($65C2)
; ====================================================================
; Writes $20 (space = transparent) to 6 bytes starting at HL.
; Called from fn_erase_ship (HL=$66A2) and fallen into via fn_move_ship
; (HL=$66A8) to clear ship-row overlap tracking buffers each frame.
; ====================================================================

fn_clear_overlap_buf:   ; $65C2
    LD B,$06       ; 6 bytes to clear                                ; 65C2: 06 06
.L65C4:
    LD (HL),$20    ; fill with $20 = ‘blank’ (no overlap recorded)     ; 65C4: 36 20
    INC HL         ; advance pointer                                 ; 65C6: 23
    DJNZ .L65C4    ; loop 6 times                                    ; 65C7: 10 FB
    RET            ; return to fn_erase_ship / fn_move_ship callers ; 65C9: C9

; ====================================================================
; fn_check_ship_crash  ($65CA)
; ====================================================================
; Processes the hit event set by the per-pixel collision scan.
; Called from main loop at $61E6 / $61F6 once per frame.
; hit_type $09 = fuel pod  -> already handled, return
; hit_type $08 = bunker    -> random score 500/1000/1500 via R reg
; hit_type  <8 = terrain/enemy type -> score from table $64AA[type*2]
; Awards score, triggers scroll effect, fires missile.
; ====================================================================

fn_check_ship_crash:   ; $65CA
    LD A,($6679)   ; ship_hit_flag: collision flagged this frame?    ; 65CA: 3A 79 66
    CP $00         ; zero = no collision this frame                  ; 65CD: FE 00
    RET Z          ; -> return                                       ; 65CF: C8
    LD A,$00       ; A = 0                                           ; 65D0: 3E 00
    LD ($6679),A   ; clear ship_hit_flag (consume event)             ; 65D2: 32 79 66
    LD A,($667A)   ; load hit_type                                   ; 65D5: 3A 7A 66
    CP $09         ; type $09 = fuel pod -> already scored           ; 65D8: FE 09
    RET Z          ; -> return (no further action)                   ; 65DA: C8
    CP $08         ; type $08 = bunker/cannon destroyed?             ; 65DB: FE 08
    JR NZ,.L6623   ; no -> table-lookup score path                   ; 65DD: 20 44
    ; --- type $08 (bunker): random score 500 / 1000 / 1500 ---
    LD HL,$01F4    ; HL = 500 (score base)                           ; 65DF: 21 F4 01
    LD DE,$01F4    ; DE = 500 (score addend)                         ; 65E2: 11 F4 01
    LD A,R         ; Z80 R register (pseudo-random 0-127)            ; 65E5: ED 5F
    AND $07        ; mask to range 0-7                               ; 65E7: E6 07
    CP $03         ; A < 3 (3/8 chance)?                             ; 65E9: FE 03
    JR C,.L65F3    ; -> score = 500, skip both adds                  ; 65EB: 38 06
    CP $06         ; A < 6 (3/8 chance)?                             ; 65ED: FE 06
    JR C,.L65F2    ; -> one add, score = 1000                        ; 65EF: 38 01
    ADD HL,DE      ; A in [6,7] (2/8): step 1 -> HL = 1000          ; 65F1: 19
    ADD HL,DE      ; step 2 -> HL = 1000 or 1500                     ; 65F2: 19
.L65F3:
    LD ($66AE),HL  ; pending_score <- 500 / 1000 / 1500             ; 65F3: 22 AE 66
.L65F6:            ; --- common tail: trigger scroll effect ---
    LD A,($64BB)   ; current scroll_mode                             ; 65F6: 3A BB 64
    CP $0A         ; already at max deceleration?                    ; 65F9: FE 0A
    JR Z,.L6608    ; yes -> skip redundant update                    ; 65FB: 28 0B
    LD A,$0A       ; value = 10                                      ; 65FD: 3E 0A
    LD ($64C8),A   ; scroll_phase_2 <- 10 (trigger slow-out)        ; 65FF: 32 C8 64
    LD A,($667A)   ; reload hit_type                                 ; 6602: 3A 7A 66
    LD ($64BA),A   ; scroll_phase <- hit_type (sets scroll speed)    ; 6605: 32 BA 64
.L6608:            ; --- fire a retaliation missile ---
    LD A,($66A3)   ; snapshot missile-state byte at $66A3            ; 6608: 3A A3 66
    LD B,A         ; save snapshot in B                              ; 660B: 47
    PUSH BC        ; keep B across call                              ; 660C: C5
    CALL $6A16     ; fn_fire_missile: try to fire player missile     ; 660D: CD 16 6A
    POP BC         ; restore B                                       ; 6610: C1
    LD A,($66A3)   ; re-read missile state                           ; 6611: 3A A3 66
    CP B           ; did fn_fire_missile change the state?           ; 6614: B8
    RET Z          ; no change -> missile already flying -> return   ; 6615: C8
    ; missile newly fired -> advance init_phase + lock scroll=10
    LD A,($64C9)   ; init_phase counter                              ; 6616: 3A C9 64
    INC A          ; advance one phase                               ; 6619: 3C
    LD ($64C9),A   ; store                                           ; 661A: 32 C9 64
    LD A,$0A       ; scroll_phase max = 10                           ; 661D: 3E 0A
    LD ($64BA),A   ; scroll_phase <- 10                              ; 661F: 32 BA 64
    RET            ; done                                            ; 6622: C9
.L6623:            ; --- table-lookup score for terrain/enemy types ---
    SLA A          ; hit_type * 2 (16-bit entries in table)          ; 6623: CB 27
    LD HL,$64AA    ; base of terrain-type score table                ; 6625: 21 AA 64
    LD E,A         ; E = byte offset = hit_type*2                    ; 6628: 5F
    LD D,$00       ; D = 0                                           ; 6629: 16 00
    ADD HL,DE      ; HL -> score entry for this hit_type             ; 662B: 19
    LD DE,$66AE    ; DE -> pending_score word                        ; 662C: 11 AE 66
    LD A,(HL)      ; low byte of score from table                    ; 662F: 7E
    LD (DE),A      ; pending_score_lo <- table[hit_type*2]          ; 6630: 12
    INC HL         ; advance to high byte                            ; 6631: 23
    LD A,(HL)      ; high byte                                       ; 6632: 7E
    INC DE         ; advance pending_score pointer                   ; 6633: 13
    LD (DE),A      ; pending_score_hi <- table[hit_type*2+1]        ; 6634: 12
; ====================================================================
; RAM variable block  ($6637 -- $669B)
; ====================================================================
; Layout (zero-initialised at startup):
;   $6637-$663E  8 bytes  staging area used by the LDDR-based enemy-table
;                          shift in fn_spawn_enemy ($67E6).  When a new
;                          enemy spawns the existing 6 records are shifted
;                          from $6637-$6666 -> $663F-$666E by LDDR, making
;                          room for a fresh record placed at $663F.
;
;   $663F-$666E  48 bytes enemy_record_table: 6 slots x 8 bytes each.
;                          Slot layout (offsets from slot base):
;                            +0 state  (0=empty 1=active 2=hit/dying)
;                            +1 x_pos
;                            +2 y_pos
;                            +3 vram_ptr_lo
;                            +4 vram_ptr_hi
;                            +5 sprite_mask (alternated each frame)
;                            +6 countdown
;                            +7 (unused)
;
;   $666F-$6673  5 bytes  cannon_shot record (single player projectile):
;                            +0 state  +1 x  +2 y  +3 fn_ptr_lo  +4 fn_ptr_hi
;
;   $6674-$6676  3 bytes  (unknown game variables)
;   $6677        1 byte   enemy_spawn_timer  (reset to $0A; counts down)
;   $6678        1 byte   (unknown)
;   $6679        1 byte   ship_hit_flag      (set by collision; cleared here)
;   $667A        1 byte   hit_type           (0-7=terrain/enemy $08=bunker
;                                             $09=fuel pod)
;   $667B-$667C  2 bytes  (unknown; possibly hit pointer)
;   $667D        1 byte   enemy_hit_flag     (set when enemy projectile hits)
;   $667E        1 byte   (unknown)
;   $667F-$6680  2 bytes  frame_counter / display-toggle (see $6843)
;   $6681-$6684  4 bytes  (unknown)
;   $6685-$6693  15 bytes decimal_place_values table (24-bit LE):
;                          $6685: 10000  $6688: 1000  $668B: 100
;                          $668E: 10    $6691: 1
;   $6694-$669B  8 bytes  (unknown; possibly score BCD or other state)
; ====================================================================

    LD BC,$0000                                             ; 6637: 01 00 00
    NOP                                                     ; 663A: 00
    NOP                                                     ; 663B: 00
    NOP                                                     ; 663C: 00
    INC A                                                   ; 663D: 3C
    NOP                                                     ; 663E: 00
enemy_table:   ; $663F -- 6 x 8-byte records, all zero-init
    NOP                                                     ; 663F: 00
    NOP                                                     ; 6640: 00
    NOP                                                     ; 6641: 00
    NOP                                                     ; 6642: 00
    NOP                                                     ; 6643: 00
    NOP                                                     ; 6644: 00
    NOP                                                     ; 6645: 00
    NOP                                                     ; 6646: 00
    NOP                                                     ; 6647: 00
    NOP                                                     ; 6648: 00
    NOP                                                     ; 6649: 00
    NOP                                                     ; 664A: 00
    NOP                                                     ; 664B: 00
    NOP                                                     ; 664C: 00
    NOP                                                     ; 664D: 00
    NOP                                                     ; 664E: 00
    NOP                                                     ; 664F: 00
    NOP                                                     ; 6650: 00
    NOP                                                     ; 6651: 00
    NOP                                                     ; 6652: 00
    NOP                                                     ; 6653: 00
    NOP                                                     ; 6654: 00
    NOP                                                     ; 6655: 00
    NOP                                                     ; 6656: 00
    NOP                                                     ; 6657: 00
    NOP                                                     ; 6658: 00
    NOP                                                     ; 6659: 00
    NOP                                                     ; 665A: 00
    NOP                                                     ; 665B: 00
    NOP                                                     ; 665C: 00
    NOP                                                     ; 665D: 00
    NOP                                                     ; 665E: 00
    NOP                                                     ; 665F: 00

score_bcd_lo:   ; $6660
    NOP                                                     ; 6660: 00

score_bcd_mid:   ; $6661
    NOP                                                     ; 6661: 00

score_bcd_hi:   ; $6662
    NOP                                                     ; 6662: 00

lives_remaining:   ; $6663
    NOP                                                     ; 6663: 00

fuel_level:   ; $6664
    NOP                                                     ; 6664: 00
    NOP                                                     ; 6665: 00
    NOP                                                     ; 6666: 00
    NOP                                                     ; 6667: 00
    NOP                                                     ; 6668: 00
    NOP                                                     ; 6669: 00
    NOP                                                     ; 666A: 00
    NOP                                                     ; 666B: 00
    NOP                                                     ; 666C: 00
    NOP                                                     ; 666D: 00
    NOP                                                     ; 666E: 00
cannon_shot:   ; $666F -- 5-byte player-projectile record
    NOP                                                     ; 666F: 00
    NOP                                                     ; 6670: 00
    NOP                                                     ; 6671: 00
    NOP                                                     ; 6672: 00
    NOP                                                     ; 6673: 00
    NOP                                                     ; 6674: 00
    NOP                                                     ; 6675: 00
    NOP                                                     ; 6676: 00
enemy_spawn_timer:   ; $6677 -- reset to $0A, counts down to 0
    NOP                                                     ; 6677: 00
    NOP                                                     ; 6678: 00    ; (unknown)
ship_hit_flag:   ; $6679
    NOP                                                     ; 6679: 00
hit_type:   ; $667A  (0-7=terrain/enemy $08=bunker $09=fuel pod)
    NOP                                                     ; 667A: 00
    NOP                                                     ; 667B: 00    ; hit_ptr_lo (unknown)
    NOP                                                     ; 667C: 00    ; hit_ptr_hi (unknown)
enemy_hit_flag:   ; $667D
    NOP                                                     ; 667D: 00
    NOP                                                     ; 667E: 00    ; (unknown)
frame_counter:   ; $667F -- alternates to toggle enemy sprite visibility
    LD A,$00                                                ; 667F: 3E 00
    LD BC,$86A0                                             ; 6681: 01 A0 86
    NOP                                                     ; 6684: 00
    DJNZ $66AE                                              ; 6685: 10 27
    NOP                                                     ; 6687: 00
    RET PE                                                  ; 6688: E8
    INC BC                                                  ; 6689: 03
    NOP                                                     ; 668A: 00
    LD H,H                                                  ; 668B: 64
    NOP                                                     ; 668C: 00
    NOP                                                     ; 668D: 00
    LD A,(BC)                                               ; 668E: 0A
    NOP                                                     ; 668F: 00
    NOP                                                     ; 6690: 00
    LD BC,$0000                                             ; 6691: 01 00 00
    NOP                                                     ; 6694: 00
    NOP                                                     ; 6695: 00
    NOP                                                     ; 6696: 00
    NOP                                                     ; 6697: 00
    NOP                                                     ; 6698: 00
    NOP                                                     ; 6699: 00
    NOP                                                     ; 669A: 00
    NOP                                                     ; 669B: 00    ; (end of variable block)

; ====================================================================
; str_score_display  ($669C)
; ====================================================================
; "SCORE" label + 9 trailing spaces + null; written to VRAM row 0 at
; game start.  The 9 spaces serve as the live score digit display area
; (digits overwritten by fn_draw_number / fn_add_score at runtime).
; ====================================================================

; ====================================================================
; fn_fire_cannon  ($66B0)
; ====================================================================
; Reads TRS-80 joystick/keyboard fire input.  If fire is pressed AND
; the cannon_shot slot is currently empty, initialises a new projectile
; slot at $666F and returns.
; TRS-80 keyboard matrix read via $3840 (row read) and $3804 (column).
; Ship position read from $6AAE (X) / $6AAF (Y); shot spawns 6 cols
; ahead and 3 rows below ship position.
; ====================================================================

fn_fire_cannon:   ; $66B0
    LD A,($3840)   ; read TRS-80 keyboard row $38, col select $40    ; 66B0: 3A 40 38
    AND $18        ; mask bits 3+4 (joystick/key fire signals)       ; 66B3: E6 18
    CP $18         ; both bits set = fire button pressed?            ; 66B5: FE 18
    JR Z,.L66C1    ; yes -> try to fire                              ; 66B7: 28 08
    LD A,($3804)   ; read alternate keyboard row (second fire key)   ; 66B9: 3A 04 38
    AND $82        ; mask bits 1+7                                   ; 66BC: E6 82
    CP $82         ; both set = alternate fire?                      ; 66BE: FE 82
    RET NZ         ; neither pressed -> return (no shot)             ; 66C0: C0
.L66C1:            ; --- spawn a cannon shot ---
    LD IX,$666F    ; IX -> cannon_shot slot                          ; 66C1: DD 21 6F 66
.L66C5:
    LD A,(IX++0)   ; load slot state flag                            ; 66C5: DD 7E 00
    CP $00         ; is slot empty?                                  ; 66C8: FE 00
    RET NZ         ; no -> already a shot in flight, return          ; 66CA: C0
.L66CB:            ; --- initialise the new cannon shot ---
    LD (IX++0),$01 ; mark slot active                                ; 66CB: DD 36 00 01
    LD A,($6AAE)   ; ship X position                                 ; 66CF: 3A AE 6A
    ADD A,$06      ; offset 6 cols ahead of ship                     ; 66D2: C6 06
    LD (IX++1),A   ; shot Y position <- ship_x + 6                  ; 66D4: DD 77 01
    LD A,($6AAF)   ; ship Y (row) position                           ; 66D7: 3A AF 6A
    ADD A,$03      ; offset 3 rows below ship                        ; 66DA: C6 03
    LD (IX++2),A   ; shot X position <- ship_y + 3                  ; 66DC: DD 77 02
    LD HL,$679E    ; HL = pointer to cannon-shot path table at $679E ; 66DF: 21 9E 67
    LD (IX++3),L   ; store path ptr lo                               ; 66E2: DD 75 03
    LD (IX++4),H   ; store path ptr hi                               ; 66E5: DD 74 04
    RET            ; done                                            ; 66E8: C9

; ====================================================================
; fn_update_cannon_shot  ($66E9)
; ====================================================================
; Called each frame to advance the cannon shot (if active) and check
; for enemy/terrain collision.  Uses the path table pointed by IX+3/4
; to compute a curved trajectory.
; Slot layout (cannon_shot at $666F):
;   +0 state (0=inactive 1=active)  +1 Y position  +2 X (column 0-63)
;   +3 path_ptr_lo  +4 path_ptr_hi
; On collision: sets enemy_hit_flag ($667D) and jumps to fn_draw_enemy.
; ====================================================================

fn_update_cannon_shot:   ; $66E9
    LD IX,$666F    ; IX -> cannon_shot slot                          ; 66E9: DD 21 6F 66
    LD A,(IX++0)   ; state: is shot active?                          ; 66ED: DD 7E 00
    CP $00         ; zero = inactive                                 ; 66F0: FE 00
    RET Z          ; -> return (nothing to update)                   ; 66F2: C8
    CALL $69DE     ; fn_try_spawn_enemy: try to find a free slot     ; 66F3: CD DE 69
    CP $01         ; fn_try_spawn_enemy returned 1 (occupied)?       ; 66F6: FE 01
    RET Z          ; yes -> abort update this frame                  ; 66F8: C8
    LD E,(IX++1)   ; E = shot Y position (used as column)            ; 66F9: DD 5E 01
    LD A,(IX++2)   ; A = shot X position (used as row)               ; 66FC: DD 7E 02
    CALL $6EE0     ; fn_draw_lives (NOTE: here used to compute VRAM  ; 66FF: CD E0 6E
                   ;   back-buffer offset from E=col / A=row -> HL)  ;
    LD DE,$3C00    ; base of VRAM                                    ; 6702: 11 00 3C
    ADD HL,DE      ; HL = VRAM address of shot position              ; 6705: 19
    PUSH HL        ;                                                 ; 6706: E5
    POP IY         ; IY = VRAM address                               ; 6707: FD E1
    LD B,C         ; B = column byte returned in C                   ; 6709: 41
    SRL B          ; B = col / 2 (which pair of columns)             ; 670A: CB 38
    INC B          ; B += 1                                          ; 670C: 04
    LD DE,$0004    ; stride = 4 bytes per pixel-mask entry            ; 670D: 11 04 00
    LD HL,$7273    ; start of sprite pixel-mask table at $7273       ; 6710: 21 73 72
.L6713:
    ADD HL,DE      ; advance to mask entry for this column           ; 6713: 19
    DJNZ .L6713    ; loop B times                                    ; 6714: 10 FD
    BIT 0,(IX++1)  ; is shot Y position odd?                         ; 6716: DD CB 01 46
    JR Z,.L671F    ; no -> use current mask entry                    ; 671A: 28 03
    SRL E          ; yes -> adjust E                                 ; 671C: CB 3B
    ADD HL,DE      ; advance to alternate (half-column) mask entry   ; 671E: 19
.L671F:
    LD A,(HL)      ; load pixel mask byte for this position          ; 671F: 7E
    AND (IY++0)    ; does mask overlap existing VRAM content?        ; 6720: FD A6 00
    JR NZ,.L6762   ; overlap -> collision!                           ; 6723: 20 3D
    LD A,(HL)      ; reload mask                                     ; 6725: 7E
    OR (IY++0)     ; OR pixel into VRAM cell (draw the shot)         ; 6726: FD B6 00
    LD (IY++0),A   ; write updated cell back                         ; 6729: FD 77 00
    INC HL         ; next mask byte (second VRAM cell)               ; 672C: 23
    LD A,(HL)      ; second mask byte                                ; 672D: 7E
    AND (IY++1)    ; check second cell for collision                 ; 672E: FD A6 01
    JR NZ,.L6762   ; collision in second cell                        ; 6731: 20 2F
    LD A,(HL)      ; reload second mask                              ; 6733: 7E
    OR (IY++1)     ; OR into second VRAM cell                        ; 6734: FD B6 01
    LD (IY++1),A   ; write back                                      ; 6737: FD 77 01
    INC (IX++2)    ; advance shot X (column) by 1                    ; 673A: DD 34 02
    LD A,(IX++2)   ; re-read X                                       ; 673D: DD 7E 02
    CP $30         ; reached column 48 (off right side of screen)?   ; 6740: FE 30
    JR NZ,.L6749   ; no -> update trajectory                         ; 6742: 20 05
.L6744:
    LD (IX++0),$00 ; deactivate cannon_shot (off-screen or expired)  ; 6744: DD 36 00 00
    RET            ; done                                            ; 6748: C9
.L6749:            ; --- advance path pointer, update Y ---
    LD L,(IX++3)   ; load current path pointer lo                    ; 6749: DD 6E 03
    LD H,(IX++4)   ; load path pointer hi                            ; 674C: DD 66 04
    INC HL         ; advance path pointer to next entry              ; 674F: 23
    LD (IX++3),L   ; store updated lo                                ; 6750: DD 75 03
    LD (IX++4),H   ; store updated hi                                ; 6753: DD 74 04
    LD A,(HL)      ; read Y-delta from path table                    ; 6756: 7E
    ADD A,(IX++1)  ; shot_Y += delta (curved trajectory)             ; 6757: DD 86 01
    LD (IX++1),A   ; store new Y position                            ; 675A: DD 77 01
    CP $7F         ; $7F = end-of-path sentinel                      ; 675D: FE 7F
    JR Z,.L6744    ; end of path -> deactivate                       ; 675F: 28 E3
    RET            ; done                                            ; 6761: C9
.L6762:            ; --- collision detected ---
    LD A,$01       ; A = 1 = hit                                     ; 6762: 3E 01
    LD ($667D),A   ; enemy_hit_flag <- 1                             ; 6764: 32 7D 66
    LD (IX++0),$00 ; deactivate the cannon shot                      ; 6767: DD 36 00 00
    JP $68B3       ; -> fn_draw_enemy (handle hit animation/score)   ; 676B: C3 B3 68
; ====================================================================
; fn_update_ship_x  ($676E)
; ====================================================================
; Reads thrust/direction keys from TRS-80 keyboard to control the
; ship's lateral speed.  Also manages the enemy_spawn_timer ($6677):
; when timer expires (reaches 5) a new enemy is spawned via fn_spawn_enemy.
; TRS-80 keyboard matrix:
;   $3840 bits 5+6 = lateral movement keys (left/right joystick)
;   $3802 bit 7 + $3804 bit 0 = alternate keys (thrust/fire)
; ====================================================================

fn_update_ship_x:   ; $676E
    LD A,($3840)   ; read keyboard row $40                          ; 676E: 3A 40 38
    AND $60        ; mask bits 5+6 (direction keys)                 ; 6771: E6 60
    CP $60         ; both bits set = ship moving / input active?    ; 6773: FE 60
    JR Z,.L678D    ; yes -> update spawn timer                      ; 6775: 28 16
    LD IX,$3800    ; IX -> TRS-80 keyboard matrix base              ; 6777: DD 21 00 38
    BIT 7,(IX++2)  ; read bit 7 of keyboard row $3802               ; 677B: DD CB 02 7E
    JR Z,.L6787    ; not set -> reset timer                         ; 677F: 28 06
    BIT 0,(IX++4)  ; read bit 0 of keyboard row $3804               ; 6781: DD CB 04 46
    JR NZ,.L678D   ; set -> update timer                            ; 6785: 20 06
.L6787:
    LD A,$0A       ; reset value = 10                               ; 6787: 3E 0A
    LD ($6677),A   ; enemy_spawn_timer <- 10 (restart countdown)    ; 6789: 32 77 66
    RET            ; done                                           ; 678C: C9
.L678D:
    LD A,($6677)   ; load enemy_spawn_timer                         ; 678D: 3A 77 66
    CP $00         ; is it zero?                                    ; 6790: FE 00
    JR Z,.L6787    ; yes -> reset to 10 and return                  ; 6792: 28 F3
    DEC A          ; decrement timer                                ; 6794: 3D
    LD ($6677),A   ; store updated timer                            ; 6795: 32 77 66
    CP $05         ; has it reached 5 (halfway)?                    ; 6798: FE 05
    JP NC,$67E6    ; yes -> fn_spawn_enemy: shift table + add enemy ; 679A: D2 E6 67
    RET            ; not yet                                        ; 679D: C9
; ====================================================================
; path_table_cannon  ($679E)
; ====================================================================
; Y-delta sequence used by fn_update_cannon_shot to produce a curved
; trajectory.  Each byte is added to the shot's Y-position each frame.
; Read-pointer starts at $679E and advances one byte per frame.
; $02 = rising steeply; $01 = gentle rise; $00 = level; $FF/$7F = end.
; After the deltas run out the shot travels horizontally until it
; either hits something or reaches column 48 ($30) off the right edge.
; ====================================================================

path_table_cannon:   ; $679E
    ; Rising phase: +2 per frame x6, then +1 per frame x7
    DB $02,$02,$02,$02,$02,$02                               ; 679E-67A3
    DB $01,$01,$01                                           ; 67A4-67A6
    DB $01,$00,$01                                           ; 67A7-67A9
    DB $01,$00,$01                                           ; 67AA-67AC
    DB $00                                                   ; 67AD
    DB $01,$00,$01                                           ; 67AE-67B0
    DB $00                                                   ; 67B1
    ; Level/terminal phase: all zeros through $67E5
    DB $01,$00,$00                                           ; 67B2-67B4
    DB $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00  ; 67B5..
    DB $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00  ; ..
    DB $00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00,$00  ; ..
    DB $00                                                   ; 67E5

; ====================================================================
; fn_spawn_enemy  ($67E6)
; ====================================================================
; Shifts the enemy record table DOWN by 8 bytes using LDDR (making
; room at slot 0), then initialises slot 0 with a new enemy record.
; The new enemy is spawned just ahead of the current ship position.
; Called from fn_update_ship_x ($679A) when enemy_spawn_timer >= 5.
; ====================================================================

fn_spawn_enemy:   ; $67E6
    LD HL,$6666    ; source tail   of enemy table ($6637-$6666)     ; 67E6: 21 66 66
    LD DE,$666E    ; dest tail: shift everything 8 bytes downward    ; 67E9: 11 6E 66
    LD BC,$0030    ; 48 bytes = 6 slots x 8                          ; 67EC: 01 30 00
    LDDR           ; copy backward: shifts table slice $6637-$6666 -> $663F-$666E
                   ;                                                 ; 67EF: ED B8
    LD A,($6AAE)   ; ship X (column)                                ; 67F1: 3A AE 6A
    ADD A,$08      ; shoot 8 columns ahead of ship                  ; 67F4: C6 08
    LD E,A         ; E = new enemy X                                ; 67F6: 5F
    LD A,($6AAF)   ; ship Y (row)                                   ; 67F7: 3A AF 6A
    INC A          ; Y + 1 (one row below ship)                     ; 67FA: 3C
    LD IX,$663F    ; IX -> newly-freed slot 0 of enemy table        ; 67FB: DD 21 3F 66
    LD (IX++1),E   ; slot_x <- ship_x + 8                          ; 67FF: DD 73 01
    LD (IX++2),A   ; slot_y <- ship_y + 1                          ; 6802: DD 77 02
    CALL $6EE0     ; compute VRAM back-buffer offset (E=col, A=row) ; 6805: CD E0 6E
    LD DE,$3C00    ; VRAM base                                      ; 6808: 11 00 3C
    ADD HL,DE      ; HL = VRAM address of enemy spawn position      ; 680B: 19
    LD (IX++3),L   ; slot_vram_ptr_lo <- HL lo                     ; 680C: DD 75 03
    LD (IX++4),H   ; slot_vram_ptr_hi <- HL hi                     ; 680F: DD 74 04
    ; --- compute sprite_mask from column ---
    LD B,$01       ; start with mask bit 0                          ; 6812: 06 01
    LD A,C         ; C = column (mod 2) from CALL $6EE0             ; 6814: 79
    CP $00         ; column even?                                   ; 6815: FE 00
    JR Z,.L6825    ; yes -> use mask $01 as-is                      ; 6817: 28 0C
    SLA B          ; B <<= 1 (B=$02)                                ; 6819: CB 20
    SLA B          ; B <<= 1 (B=$04)                                ; 681B: CB 20
    CP $02         ; column mod 4 == 2?                             ; 681D: FE 02
    JR Z,.L6825    ; yes -> use mask $04                            ; 681F: 28 04
    SLA B          ; B <<= 1 (B=$08)                                ; 6821: CB 20
    SLA B          ; B <<= 1 (B=$10)                                ; 6823: CB 20
.L6825:
    LD (IX++5),B   ; slot_sprite_mask <- B                         ; 6825: DD 70 05
    RET            ; done                                           ; 6828: C9
; ====================================================================
; fn_update_all_enemies  ($6829)
; ====================================================================
; Two-pass update of the enemy record table at $663F (6 slots x 8 bytes).
; Pass 1 ($6829-$68B0): for each ACTIVE slot, XOR sprite_mask into VRAM
;   (alternating with frame_counter for flicker animation), advance
;   the slot's path pointer, update X position, check screen bounds.
; Pass 2 ($6891-$68B2): for slots in state=2 (hit/dying) call fn_draw_enemy
;   to render the hit-flash graphic.
; Enemy slot layout (+0 state +1 x +2 y +3 vram_lo +4 vram_hi
;                    +5 sprite_mask +6 countdown +7 unused)
; frame_counter ($667F / $6680): toggles each frame for sprite flash.
; ====================================================================

fn_update_all_enemies:   ; $6829
    LD A,$00       ; A = 0                                          ; 6829: 3E 00
    LD ($667D),A   ; clear enemy_hit_flag for this frame            ; 682B: 32 7D 66
    LD IX,$663F    ; IX -> enemy table base                         ; 682E: DD 21 3F 66
    LD B,$06       ; 6 slots to process                             ; 6832: 06 06
    LD DE,$0008    ; slot stride = 8 bytes                          ; 6834: 11 08 00
.L6837:            ; --- Pass 1: update each active slot ---
    BIT 0,(IX++0)  ; is slot state bit 0 set? (active)              ; 6837: DD CB 00 46
    JR Z,.L688D    ; inactive -> skip to next slot                  ; 683B: 28 50
    LD L,(IX++3)   ; load VRAM ptr lo                               ; 683D: DD 6E 03
    LD H,(IX++4)   ; load VRAM ptr hi                               ; 6840: DD 66 04
    LD A,($6680)   ; frame_counter (toggles each frame)             ; 6843: 3A 80 66
    CP $00         ; is it zero?                                    ; 6846: FE 00
    JR Z,.L684F    ; yes -> skip sprite XOR this frame (flicker off) ; 6848: 28 05
    LD A,(IX++5)   ; load sprite_mask for this slot                 ; 684A: DD 7E 05
    XOR (HL)       ; XOR into VRAM cell (toggle sprite pixel)       ; 684D: AE
    LD (HL),A      ; write back                                     ; 684E: 77
.L684F:
    BIT 0,(IX++1)  ; is X position bit 0 set? (odd column)         ; 684F: DD CB 01 46
    JR NZ,.L685B   ; odd -> use SRA path                            ; 6853: 20 06
    SLA (IX++5)    ; even col: shift mask left (advance to next col) ; 6855: DD CB 05 26
    JR .L6865      ; jump over SRA path                             ; 6859: 18 0A
.L685B:
    SRA (IX++5)    ; odd col: shift mask right                      ; 685B: DD CB 05 2E
    INC (IX++3)    ; advance VRAM ptr lo (move to next VRAM cell)   ; 685F: DD 34 03
    LD L,(IX++3)   ; reload ptr lo                                  ; 6862: DD 6E 03
.L6865:
    INC (IX++1)    ; advance X position by 1                        ; 6865: DD 34 01
    CALL $69DE     ; fn_try_spawn_enemy: check spawn conditions      ; 6868: CD DE 69
    CP $01         ; returns 1 if slot found/occupied               ; 686B: FE 01
    JR Z,.L688D    ; -> skip remaining update for this slot         ; 686D: 28 1E
    DEC (IX++6)    ; decrement countdown for this slot              ; 686F: DD 35 06
    BIT 7,(IX++6)  ; has countdown wrapped to negative (bit 7 set)? ; 6872: DD CB 06 7E
    JR Z,.L687E    ; no -> continue                                  ; 6876: 28 06
    LD (IX++0),$00 ; expired -> deactivate slot                     ; 6878: DD 36 00 00
    JR .L688D      ; advance to next slot                           ; 687C: 18 0F
.L687E:
    LD A,(IX++5)   ; sprite_mask                                    ; 687E: DD 7E 05
    AND (HL)       ; does sprite pixel overlap VRAM content?        ; 6881: A6
    JR Z,.L6888    ; no overlap -> just OR in                       ; 6882: 28 04
    LD (IX++0),$02 ; mark slot as hit/dying (state=2)               ; 6884: DD 36 00 02
.L6888:
    LD A,(IX++5)   ; sprite_mask                                    ; 6888: DD 7E 05
    OR (HL)        ; OR pixel into VRAM (draw sprite)               ; 688B: B6
    LD (HL),A      ; write back                                     ; 688C: 77
.L688D:
    ADD IX,DE      ; IX += 8 (advance to next slot)                 ; 688D: DD 19
    DJNZ .L6837    ; process all 6 slots                            ; 688F: 10 A6
    ; --- Pass 2: render hit-flash for dying slots ---
    LD IX,$663F    ; IX -> enemy table base                         ; 6891: DD 21 3F 66
    LD B,$06       ; 6 slots                                        ; 6895: 06 06
.L6897:
    LD A,(IX++0)   ; load slot state                                ; 6897: DD 7E 00
    CP $00         ; inactive?                                      ; 689A: FE 00
    JR Z,.L68AE    ; yes -> skip                                    ; 689C: 28 10
    CP $02         ; state==2 (hit/dying)?                          ; 689E: FE 02
    CALL Z,$68B3   ; yes -> fn_draw_enemy: draw hit-flash/explosion ; 68A0: CC B3 68
    LD A,(IX++1)   ; load X position                                ; 68A3: DD 7E 01
    CP $7F         ; has X reached $7F (off-screen sentinel)?       ; 68A6: FE 7F
    JR NZ,.L68AE   ; no -> keep slot                                ; 68A8: 20 04
    LD (IX++0),$00 ; X=$7F -> deactivate                            ; 68AA: DD 36 00 00
.L68AE:
    ADD IX,DE      ; IX += 8                                        ; 68AE: DD 19
    DJNZ .L6897    ; loop all 6 slots                               ; 68B0: 10 E5
    RET            ; done                                           ; 68B2: C9
; 
; ====================================================================
; fn_draw_enemy  ($68B3)
; ====================================================================
; NOTE: label is historical; this function primarily *processes* an enemy
; hit recorded while drawing rather than drawing.
; Called when an enemy record enters state=2 (hit/dying) or when the
; cannon shot collision handler (fn_update_cannon_shot) detects a hit.
; Steps:
;  1. Saves hit-slot ptr in IY; calls $6E25 to init encounter-table scan
;     (IX=$7304, DE=$0008, B=23 entries).
;  2. Clears the hit-slot state byte (IY+0 <- 0).
;  3. Scans 23 entries in the encounter table ($7304).  For each entry
;     whose Y (IX+2) is within 2 rows of IY+2 AND whose X (IX+1)
;     brackets the hit X position (IY+1):
;       -> write entry-type to hit_type ($667A)
;       -> deactivate encounter entry (IX+0 <- 0)
;       -> record VRAM ptr to hit_ptr ($667B)
;       -> set ship_hit_flag ($6679) <- 1
; The main loop then handles the hit via fn_check_ship_crash ($65CA).
; ====================================================================

fn_draw_enemy:   ; $68B3
    PUSH BC        ; save BC                                         ; 68B3: C5
    PUSH IX        ; save IX (hit enemy slot ptr)                    ; 68B4: DD E5
    POP IY         ; IY <- IX (hit slot ptr preserved in IY)         ; 68B6: FD E1
    PUSH DE        ; save DE                                         ; 68B8: D5
    PUSH IX        ; push hit slot again for restore at exit         ; 68B9: DD E5
    CALL $6E25     ; init encounter-table scan: IX<-$7304, DE<-8, B<-23 ; 68BB: CD 25 6E
    LD (IY++0),$00 ; deactivate hit slot (state <- 0)                ; 68BE: FD 36 00 00
.L68C2:            ; --- scan encounter table entries ---
    LD A,(IX++0)   ; entry state                                     ; 68C2: DD 7E 00
    CP $00         ; inactive?                                       ; 68C5: FE 00
    JR NZ,.L68D2   ; active -> check for match                       ; 68C7: 20 09
.L68C9:
    ADD IX,DE      ; advance IX by 8 (next encounter entry)          ; 68C9: DD 19
    DJNZ .L68C2    ; loop all B=23 entries                           ; 68CB: 10 F5
.L68CD:            ; --- restore and return ---
    POP IX         ; restore IX (hit slot ptr)                       ; 68CD: DD E1
    POP DE         ; restore DE                                      ; 68CF: D1
    POP BC         ; restore BC                                      ; 68D0: C1
    RET            ; done                                            ; 68D1: C9
.L68D2:
    CP $09         ; type $09 = fuel pod? skip                       ; 68D2: FE 09
    JR Z,.L68C9    ; -> skip                                         ; 68D4: 28 F3
    LD A,($667D)   ; enemy_hit_flag: was a cannon hit already set?   ; 68D6: 3A 7D 66
    CP $00         ;                                                 ; 68D9: FE 00
    JR NZ,.L68E8   ; yes -> force position-range check               ; 68DB: 20 0B
    LD A,(IX++0)   ; no cannon hit: only check types 6 and 7         ; 68DD: DD 7E 00
    CP $06         ; type $06 = bonus/base?                          ; 68E0: FE 06
    JR Z,.L68E8    ; yes -> check                                    ; 68E2: 28 04
    CP $07         ; type $07?                                       ; 68E4: FE 07
    JR NZ,.L68C9   ; other type -> skip                              ; 68E6: 20 E1
.L68E8:            ; --- check Y proximity (within 3 rows) ---
    LD A,(IX++2)   ; encounter entry Y position                      ; 68E8: DD 7E 02
    CP (IY++2)     ; == hit slot Y?                                  ; 68EB: FD BE 02
    JR Z,.L68FC    ; yes -> check X                                  ; 68EE: 28 0C
    INC A          ; entry_Y + 1                                     ; 68F0: 3C
    CP (IY++2)     ; == hit slot Y?                                  ; 68F1: FD BE 02
    JR Z,.L68FC    ; yes -> check X                                  ; 68F4: 28 06
    INC A          ; entry_Y + 2                                     ; 68F6: 3C
    CP (IY++2)     ; == hit slot Y?                                  ; 68F7: FD BE 02
    JR NZ,.L68C9   ; no match within 3 rows -> skip                  ; 68FA: 20 CD
.L68FC:            ; --- check X range ---
    LD A,(IX++1)   ; encounter entry X position                      ; 68FC: DD 7E 01
    DEC A          ; X - 1                                           ; 68FF: 3D
    DEC A          ; X - 2 (lower bound)                             ; 6900: 3D
    CP (IY++1)     ; lower bound <= hit slot X?                      ; 6901: FD BE 01
    JR NC,.L68C9   ; hit X < lower bound -> skip                     ; 6904: 30 C3
    LD L,(IX++3)   ; entry VRAM ptr lo                               ; 6906: DD 6E 03
    LD H,(IX++4)   ; entry VRAM ptr hi                               ; 6909: DD 66 04
    ADD A,(HL)     ; lower_bound + width_byte (upper bound)          ; 690C: 86
    CP (IY++1)     ; upper bound >= hit slot X?                      ; 690D: FD BE 01
    JR C,.L68C9    ; hit X > upper bound -> skip                     ; 6910: 38 B7
    ; --- match found: record hit ---
    LD A,(IX++0)   ; encounter entry type                            ; 6912: DD 7E 00
    LD ($667A),A   ; hit_type <- entry type                          ; 6915: 32 7A 66
    LD (IX++0),$00 ; deactivate encounter entry                      ; 6918: DD 36 00 00
    LD ($667B),HL  ; hit_ptr <- encounter VRAM ptr                   ; 691C: 22 7B 66
    LD A,$01       ; A = 1                                           ; 691F: 3E 01
    LD ($6679),A   ; ship_hit_flag <- 1 (trigger fn_check_ship_crash) ; 6921: 32 79 66
    JR .L68CD      ; -> restore and return                           ; 6924: 18 A7

; ====================================================================
; fn_update_ship_pos  ($6926)
; ====================================================================
; Reads TRS-80 joystick input and updates the ship position variables:
;   $6AAE = ship X (column, clamped 0-$79 = col 0-121)
;   $6AAF = ship Y (row,    clamped 0-$2C = row 0-44)
; Also computes the ship's VRAM cell address and sprite mask index,
; storing them at $667E (VRAM ptr) and $69DC (mask table ptr) for
; the subsequent fn_redraw_ship call at $69A4.
; Key input via TRS-80 keyboard matrix at base IX=$3800:
;   $3840 bit3 = RIGHT, bit4 = LEFT, bit5 = DOWN, bit6 = UP
;   $3804 bit1 = alt-LEFT, bit7 = alt-RIGHT, bit0 = alt-UP, bit7 = alt-DOWN
; ====================================================================

fn_update_ship_pos:   ; $6926
    LD BC,$0000    ; B=Dx=0, C=Dy=0 (speed accumulators)            ; 6926: 01 00 00
    LD IX,$3800    ; IX -> TRS-80 keyboard matrix                    ; 6929: DD 21 00 38
    BIT 3,(IX++64) ; $3840 bit 3 = RIGHT key?                        ; 692D: DD CB 40 5E
    JR NZ,.L6939   ; pressed -> DEC C (move left/down?)              ; 6931: 20 06
    BIT 1,(IX++4)  ; $3804 bit 1 = alt-LEFT?                         ; 6933: DD CB 04 4E
    JR Z,.L693A    ; not pressed -> skip                             ; 6937: 28 01
.L6939:
    DEC C          ; C-- (Y delta: move up or similar)               ; 6939: 0D
.L693A:
    BIT 4,(IX++64) ; $3840 bit 4 = LEFT key?                         ; 693A: DD CB 40 66
    JR NZ,.L6946   ; pressed -> INC C                                ; 693E: 20 06
    BIT 7,(IX++4)  ; $3804 bit 7 = alt-RIGHT?                        ; 6940: DD CB 04 7E
    JR Z,.L6947    ; not pressed -> skip                             ; 6944: 28 01
.L6946:
    INC C          ; C++ (Dy up: move right/down?)                   ; 6946: 0C
.L6947:
    BIT 5,(IX++64) ; $3840 bit 5 = DOWN key?                         ; 6947: DD CB 40 6E
    JR NZ,.L6953   ; pressed -> DEC B                                ; 694B: 20 06
    BIT 7,(IX++2)  ; $3802 bit 7 = alt-DOWN?                         ; 694D: DD CB 02 7E
    JR Z,.L6955    ; not pressed -> skip                             ; 6951: 28 02
.L6953:
    DEC B          ; B-- / B-- (Dx: move left, 2 units)              ; 6953: 05
    DEC B          ;                                                 ; 6954: 05
.L6955:
    BIT 6,(IX++64) ; $3840 bit 6 = UP key?                           ; 6955: DD CB 40 76
    JR NZ,.L6961   ; pressed -> INC B / INC B                        ; 6959: 20 06
    BIT 0,(IX++4)  ; $3804 bit 0 = alt-UP?                           ; 695B: DD CB 04 46
    JR Z,.L6963    ; not pressed -> skip                             ; 695F: 28 02
.L6961:
    INC B          ; B++ / B++ (Dx: move right, 2 units)             ; 6961: 04
    INC B          ;                                                 ; 6962: 04
.L6963:            ; --- apply Dx (B) to ship X, clamped ---
    LD A,($6AAE)   ; ship X current                                  ; 6963: 3A AE 6A
    ADD A,B        ; X += Dx                                         ; 6966: 80
    CP $7A         ; X == 122 = right edge stop?                     ; 6967: FE 7A
    JR Z,.L6972    ; yes -> skip store (stay at boundary)            ; 6969: 28 07
    CP $FE         ; X == $FE = underflow (went negative)?           ; 696B: FE FE
    JR Z,.L6972    ; yes -> skip store (stay at 0)                   ; 696D: 28 03
    LD ($6AAE),A   ; store updated ship X                            ; 696F: 32 AE 6A
.L6972:            ; --- apply Dy (C) to ship Y, clamped ---
    LD A,($6AAF)   ; ship Y current                                  ; 6972: 3A AF 6A
    ADD A,C        ; Y += Dy                                         ; 6975: 81
    CP $2D         ; Y >= $2D = 45 (bottom boundary)?                ; 6976: FE 2D
    JR NC,.L697D   ; yes -> skip store (clamp at top)                ; 6978: 30 03
    LD ($6AAF),A   ; store updated ship Y                            ; 697A: 32 AF 6A
.L697D:            ; --- compute ship VRAM cell address ---
    LD A,($6AAE)   ; ship X (column)                                 ; 697D: 3A AE 6A
    LD E,A         ; E = column                                      ; 6980: 5F
    LD A,($6AAF)   ; ship Y (row)                                    ; 6981: 3A AF 6A
    CALL $6EE0     ; fn_draw_lives (here: compute VRAM offset)       ; 6984: CD E0 6E
    LD DE,$3C00    ; VRAM base                                       ; 6987: 11 00 3C
    ADD HL,DE      ; HL = VRAM cell address of ship                  ; 698A: 19
    PUSH HL        ; save VRAM address                               ; 698B: E5
    LD HL,$7214    ; start of sprite pixel-mask table at $7214       ; 698C: 21 14 72
    LD DE,$0010    ; stride = 16 bytes per mask entry                ; 698F: 11 10 00
    LD B,C         ; B = column (from fn_draw_lives return)          ; 6992: 41
    SRL B          ; B = col/2                                       ; 6993: CB 38
    INC B          ; B++                                             ; 6995: 04
.L6996:
    ADD HL,DE      ; advance to mask entry for this column           ; 6996: 19
    DJNZ .L6996    ; loop B times                                    ; 6997: 10 FD
    LD A,($6AAE)   ; ship X again (for odd-column adjustment)        ; 6999: 3A AE 6A
    LD ($69DC),HL  ; store mask table ptr at $69DC (data variable)   ; 699C: 22 DC 69
    POP HL         ; restore VRAM address                            ; 699F: E1
    LD ($667E),HL  ; store ship VRAM address for fn_redraw_ship      ; 69A0: 22 7E 66
    RET            ; done                                            ; 69A3: C9

; ====================================================================
; fn_redraw_ship  ($69A4)
; ====================================================================
; Blits the ship sprite to VRAM using pre-computed ship VRAM ptr ($667E)
; and mask table ptr ($69DC).  Also checks for collision (if any VRAM
; cell already has a set pixel that overlaps the sprite mask, calls
; fn_set_collision_flag to set $6678=1).
; Called from main game loop each frame at $61D3.
; ====================================================================

fn_redraw_ship:   ; $69A4
    LD A,$00       ; A = 0                                           ; 69A4: 3E 00
    LD ($6678),A   ; clear collision flag ($6678)                    ; 69A6: 32 78 66
    LD IX,($667E)  ; IX <- ship VRAM cell ptr                        ; 69A9: DD 2A 7E 66
    LD DE,($69DC)  ; DE <- ship sprite mask table ptr                ; 69AD: ED 5B DC 69
    LD B,$04       ; 4 pairs of sprite cells to process              ; 69B1: 06 04
.L69B3:            ; --- collision-check + draw loop ---
    LD A,(DE)      ; load sprite mask byte                           ; 69B3: 1A
    AND (IX++0)    ; does mask overlap existing VRAM byte?           ; 69B4: DD A6 00
    CALL NZ,$69D6  ; yes -> fn_set_collision_flag: set $6678=1       ; 69B7: C4 D6 69
    LD A,(DE)      ; reload mask                                     ; 69BA: 1A
    OR (IX++0)     ; OR into VRAM (draw sprite pixel)                ; 69BB: DD B6 00
    LD (IX++0),A   ; write back to VRAM                              ; 69BE: DD 77 00
    INC DE         ; next mask byte                                  ; 69C1: 13
    LD A,(DE)      ; second sprite mask byte (row below)             ; 69C2: 1A
    AND (IX++64)   ; overlap check in row below (VRAM +64 = 1 row)  ; 69C3: DD A6 40
    CALL NZ,$69D6  ; collision in row below                          ; 69C6: C4 D6 69
    LD A,(DE)      ; reload second mask                              ; 69C9: 1A
    OR (IX++64)    ; OR into VRAM row below                          ; 69CA: DD B6 40
    LD (IX++64),A  ; write back                                      ; 69CD: DD 77 40
    INC DE         ; advance mask pointer                            ; 69D0: 13
    INC IX         ; advance VRAM pointer (next column)              ; 69D1: DD 23
    DJNZ .L69B3    ; process all 4 column-pairs                      ; 69D3: 10 DE
    RET            ; done                                            ; 69D5: C9

; ====================================================================
; fn_set_collision_flag  ($69D6)
; ====================================================================
; Sets $6678=1 (collision signal).  Called (CALL NZ) by fn_redraw_ship
; when an AND test reveals sprite overlap with existing VRAM content.
; NOTE: label in original session was 'fn_update_all_enemies'; that
;       name belongs to the 6-slot update loop at $6829 instead.
; ====================================================================

fn_set_collision_flag:   ; $69D6
    LD A,$01       ; collision signal                                 ; 69D6: 3E 01
    LD ($6678),A   ; set collision flag                              ; 69D8: 32 78 66
    RET            ; done                                            ; 69DB: C9

mask_ptr_low:   ; $69DC -- embedded 2-byte data variable (ship mask ptr lo/hi)
    NOP            ; $69DC (lo byte, set by fn_update_ship_pos)      ; 69DC: 00
    NOP            ; $69DD (hi byte)                                 ; 69DD: 00

; ====================================================================
; fn_check_terrain_clip  ($69DE)
; ====================================================================
; Checks whether an entity (enemy or cannon shot) at IX+1 (X column)
; and IX+2 (Y row) has gone below the terrain surface or off-screen.
; Uses terrain height table at $7284 (128-byte map, one byte per column).
; If X >= $80 (off right edge) OR terrain_height[X] >= Y:
;   -> deactivate entity (IX+0 <- 0) and return A=1  (clipped)
; Otherwise return A=0  (entity is still flying above terrain).
; Called as fn_try_spawn_enemy in earlier notes (name is a misnomer).
; ====================================================================

fn_check_terrain_clip:   ; $69DE
    LD A,(IX++1)   ; IX+1 = entity X column                          ; 69DE: DD 7E 01
    CP $80         ; off the right edge of screen?                   ; 69E1: FE 80
    JR NC,.L69F9   ; yes -> deactivate + return 1                    ; 69E3: 30 14
    PUSH HL        ; save HL                                         ; 69E5: E5
    PUSH DE        ; save DE                                         ; 69E6: D5
    LD E,A         ; E = X (table index)                             ; 69E7: 5F
    LD D,$00       ; D = 0                                           ; 69E8: 16 00
    LD HL,$7284    ; terrain height table base                       ; 69EA: 21 84 72
    ADD HL,DE      ; HL = &terrain_height[X]                         ; 69ED: 19
    LD A,(HL)      ; A = terrain height at column X                  ; 69EE: 7E
    POP DE         ; restore DE                                      ; 69EF: D1
    POP HL         ; restore HL                                      ; 69F0: E1
    CP (IX++2)     ; terrain_height >= entity Y?                     ; 69F1: DD BE 02
    JR C,.L69F9    ; yes (C set means height >= Y) -> clipped        ; 69F4: 38 03
    LD A,$00       ; A = 0 = not clipped                             ; 69F6: 3E 00
    RET            ; return 0                                        ; 69F8: C9
.L69F9:
    LD (IX++0),$00 ; deactivate entity                               ; 69F9: DD 36 00 00
    LD A,$01       ; A = 1 = clipped (entity removed)                ; 69FD: 3E 01
    RET            ; return 1                                        ; 69FF: C9

; ====================================================================
; fn_advance_terrain  ($6A00)
; ====================================================================
; Scrolls the terrain height table one step to the left (LDIR shift
; of $7284-$7303: 128 entries), then appends the new terrain step
; value ($6AAD) at the end ($7303).  Called each time the level
; terrain advances by one column.
; ====================================================================

fn_advance_terrain:   ; $6A00
    CALL $6E2F     ; fn_clear_screen (here: advances level-scroll state) ; 6A00: CD 2F 6E
    LD HL,$7284    ; source = terrain_height[1] (skip first entry)   ; 6A03: 21 84 72
    LD DE,$7284    ; dest   = terrain_height[0]                      ; 6A06: 11 84 72
    INC HL         ; HL = &terrain_height[1]                         ; 6A09: 23
    LD BC,$007F    ; count = 127 bytes                               ; 6A0A: 01 7F 00
    LDIR           ; shift entire table left by one entry             ; 6A0D: ED B0
    LD A,($6AAD)   ; new terrain_step value                          ; 6A0F: 3A AD 6A
    LD ($7303),A   ; append at end of table                          ; 6A12: 32 03 73
    RET            ; done                                            ; 6A15: C9
; 
; ====================================================================
; fn_add_pending_score  ($6A16)
; ====================================================================
; Adds the 16-bit pending score increment at $66AE to the 24-bit
; binary score accumulator ($6696 hi, $6697-$6698 lo).  Then encodes
; the accumulator as 6 ASCII decimal digits in two passes:
;   Pass 1: IX=$66A2  total score into main score display string
;   Pass 2: IX=$66A8  just the added delta into secondary display
; NOTE: previously labelled fn_fire_missile — that name is incorrect.
; ====================================================================

fn_add_pending_score:   ; $6A16
    LD DE,($66AE)      ; DE = pending score increment (16-bit word)  ; 6A16: ED 5B AE 66
    LD HL,($6697)      ; HL = score_lo (low 16 bits of 24-bit score) ; 6A1A: 2A 97 66
    ADD HL,DE          ; score_lo += pending                         ; 6A1D: 19
    LD ($6697),HL      ; save updated score_lo                       ; 6A1E: 22 97 66
    LD HL,$6696        ; HL -> score_hi byte                         ; 6A21: 21 96 66
    LD A,$00           ; A = 0                                        ; 6A24: 3E 00
    ADC A,(HL)         ; A = score_hi + carry from ADD above          ; 6A26: 8E
    LD (HL),A          ; save updated score_hi                       ; 6A27: 77
    LD ($669A),DE      ; keep copy of delta at $669A for pass 2      ; 6A28: ED 53 9A 66
    LD HL,($6697)      ; reload score_lo                             ; 6A2C: 2A 97 66
    LD ($6694),HL      ; load into digit-extraction temp buffer      ; 6A2F: 22 94 66
    LD A,($6696)       ; reload score_hi                             ; 6A32: 3A 96 66
    LD ($6693),A       ; load hi byte into extraction temp           ; 6A35: 32 93 66
    LD IX,$66A2        ; IX -> score display area (total score)      ; 6A38: DD 21 A2 66
    CALL $6A4E  ; fn_score_to_decimal: convert to 6 ASCII digits     ; 6A3C: CD 4E 6A
    LD HL,($669A)      ; reload saved delta                          ; 6A3F: 2A 9A 66
    LD ($6694),HL      ; delta into extraction temp (pass 2)         ; 6A42: 22 94 66
    LD A,$00           ; delta hi byte = 0 (fits in 16 bits)         ; 6A45: 3E 00
    LD ($6693),A       ; clear hi temp                               ; 6A47: 32 93 66
    LD IX,$66A8        ; IX -> secondary score display at $66A8      ; 6A4A: DD 21 A8 66
    ; falls through into fn_score_to_decimal with IX=$66A8

; ====================================================================
; fn_score_to_decimal  ($6A4E)
; ====================================================================
; Converts the 24-bit value in RAM temp buffer
;   ($6693 = hi byte, $6694-$6695 = lo 16 bits)
; to 6 ASCII decimal digit characters written to IX+0..IX+5.
; Place-value table at $6681: 6 entries x 3 bytes each:
;   [val_hi8, val_lo8, val_mid8]  for 100000, 10000, 1000, 100, 10, 1
; Algorithm: for each place value, count subtractions until borrow.
; After digit writing: suppress leading zeros (replace '0' with ' ').
; If $66A2 digit overflows (>=':'): wrap by subtracting $4240 from
; score_lo and retrying.
; NOTE: previously labelled fn_update_missile — that name is incorrect.
; ====================================================================

fn_score_to_decimal:   ; $6A4E
    LD B,$06           ; B = 6 digits to compute                     ; 6A4E: 06 06
    PUSH IX            ; save digit write pointer for post-processing ; 6A50: DD E5
    LD IY,$6681        ; IY -> decimal place-value table (6 x 3 B)   ; 6A52: FD 21 81 66
.L6A56:
    LD C,$30           ; C = '0' (digit accumulator, ASCII base)      ; 6A56: 0E 30
    OR A               ; clear carry flag                             ; 6A58: B7
    LD HL,($6694)      ; HL = temp lo 16 bits of value to convert    ; 6A59: 2A 94 66
    LD E,(IY++1)       ; E = place-value bits 0-7                    ; 6A5C: FD 5E 01
    LD D,(IY++2)       ; D = place-value bits 8-15                   ; 6A5F: FD 56 02
.L6A62:
    SBC HL,DE          ; subtract lo 16 bits of place value          ; 6A62: ED 52
    LD A,($6693)       ; A = temp hi byte                            ; 6A64: 3A 93 66
    FD $9E             ; SBC A,(IY+0): subtract place-value hi byte  ; 6A67: FD 9E
    NOP                ; (offset byte $00 for SBC A,(IY+0))          ; 6A69: 00
    JR C,.L6A75        ; borrow -> this digit is C, advance          ; 6A6A: 38 09
    LD ($6693),A       ; save reduced hi byte                        ; 6A6C: 32 93 66
    LD ($6694),HL      ; save reduced lo                             ; 6A6F: 22 94 66
    INC C              ; digit++ (one more place-value subtracted)   ; 6A72: 0C
    JR .L6A62          ; loop: try subtracting again                 ; 6A73: 18 ED
.L6A75:
    LD (IX++0),C       ; store ASCII digit char at IX+0              ; 6A75: DD 71 00
    INC IX             ; advance digit write pointer                 ; 6A78: DD 23
    INC IY             ; advance IY by 3 to next place-value entry   ; 6A7A: FD 23
    INC IY             ;   (IY+1 was val_lo, IY+2 was val_mid,       ; 6A7C: FD 23
    INC IY             ;    IY+0 next = next entry val_hi)           ; 6A7E: FD 23
    DJNZ .L6A56        ; repeat for all 6 digits                     ; 6A80: 10 D4
    ; ---- leading-zero suppression and overflow wrap ----
.L6A82:
    LD B,$06           ; scan 6 digit positions                      ; 6A82: 06 06
    POP HL             ; HL = original IX (start of digit string)    ; 6A84: E1
.L6A85:
    LD A,(HL)          ; read digit char                             ; 6A85: 7E
    CP $30             ; is it '0'?                                  ; 6A86: FE 30
    JR NZ,.L6A8F       ; no -> stop leading-zero suppression         ; 6A88: 20 05
    LD (HL),$20        ; replace leading '0' with ' ' (space)        ; 6A8A: 36 20
    INC HL             ; advance to next digit position              ; 6A8C: 23
    DJNZ .L6A85        ; repeat for all 6                            ; 6A8D: 10 F6
.L6A8F:
    LD HL,$66A2        ; HL -> most-significant display digit        ; 6A8F: 21 A2 66
    LD A,(HL)          ; read the digit char there                   ; 6A92: 7E
    CP $3A             ; < ':' (i.e. digit char is '0'-'9', OK)?     ; 6A93: FE 3A
    RET C              ; yes -> return, score display is valid       ; 6A95: D8
    ; digit overflowed (> '9'): wrap score accumulator
    LD A,$30           ; cap overflow digit at '0'                   ; 6A96: 3E 30
    LD (HL),A          ; write '0' to $66A2                          ; 6A98: 77
    PUSH HL            ; save $66A2 pointer                          ; 6A99: E5
    LD A,$00           ; clear score hi byte                         ; 6A9A: 3E 00
    LD ($6696),A       ; $6696 = 0                                   ; 6A9C: 32 96 66
    LD HL,($6697)      ; reload score_lo                             ; 6A9F: 2A 97 66
    LD DE,$4240        ; DE = $4240 = 16,960 (overflow correction)   ; 6AA2: 11 40 42
    OR A               ; clear carry                                 ; 6AA5: B7
    SBC HL,DE          ; score_lo -= $4240 (wrap)                    ; 6AA6: ED 52
    LD ($6697),HL      ; save adjusted score_lo                      ; 6AA8: 22 97 66
    JR .L6A82          ; re-check for further overflow               ; 6AAB: 18 D5

; ---- game state RAM variables ($6AAD–$6AC0) ----------------------
; The following bytes are decoded as Z80 instructions by the
; disassembler, but they are game-state data variables initialised
; to the values their opcodes happen to encode.  They are written
; and read throughout the code by explicit LD ($addr) instructions.

terrain_step:   ; $6AAD  — new terrain height byte appended per scroll step
    DB $2F       ; initial value $2F = 47 (terrain step)

ship_x:   ; $6AAE  — player ship X column (0–$79, written by fn_update_ship_pos)
    DB $14       ; initial column 20

ship_y:   ; $6AAF  — player ship Y row (0–$2C, written by fn_update_ship_pos)
    DB $14       ; initial row 20

level_pos:   ; $6AB0  — terrain-type byte at the ship's current column
    DB $39       ; initial = $39

scroll_sub:   ; $6AB1  — sub-pixel scroll accumulator (used by fn_draw_fuel_bar)
    DB $30       ; initial = $30

ship_vram_off:   ; $6AB2  — 16-bit VRAM offset for ship sprite position
    DW $73CC     ; initial = $73CC (overwritten at runtime)

    DB $CC $77   ; $6AB4–$6AB5: reserved bytes

ship_screen_col:   ; $6AB6  — encounter-aircraft column state (0 = inactive)
    DB $00

ship_screen_row:   ; $6AB7  — encounter-aircraft screen row
    DB $07

    DB $00 $00   ; $6AB8–$6AB9: boundary value / fuel-tank flag

stage_data_ptr:   ; $6ABA  — 16-bit pointer into stage terrain-definition table
    DW $6F8B     ; initial = $6F8B (start of stage data)

terrain_col_count:   ; $6ABC  — countdown: terrain columns before next type change
    DB $00

terrain_advance_ctr:   ; $6ABD  — delay counter for fn_advance_terrain steps
    DB $00

    DB $00 $00 $FF   ; $6ABE–$6AC0: padding / unused

ship_pixel_x:   ; $6AC1  — encounter aircraft sub-pixel X position
    DB $6E       ; initial = $6E

ship_pixel_y:   ; $6AC2  — pixel-within-char Y counter (+=4 each step, wraps at 0)
    DB $00

ship_char_code:   ; $6AC3  — sprite sequence index (0–$0F)
    DB $00

ship_prev_char:   ; $6AC4  — launch countdown (decrements until aircraft fires)
    DB $64       ; initial = $64 = 100 steps


; ====================================================================
; fn_advance_encounter_aircraft  ($6AC5)
; ====================================================================
; Advances the positional state of the current encounter aircraft:
;   ship_pixel_y ($6AC2) += 4 each call (pixel counter within char cell)
;   On wrap (pixel_y = 0): advance ship_char_code ($6AC3):
;     – if char_code is odd: shift ship_pixel_x left and row down
;     – if char_code >= $10 (sprite sequence exhausted): skip
;   If ship_screen_col ($6AB6) = 0 (aircraft at launch position):
;     decrement ship_prev_char launch countdown; when expired, arm
;     the aircraft (set ship_screen_col = 6 or 7 based on $6AB0 bit 0)
; NOTE: previously labelled fn_missile_hit_test.
; ====================================================================

fn_advance_encounter_aircraft:   ; $6AC5
    LD A,($6AC2)  ; ship_pixel_y                             ; 6AC5: 3A C2 6A
    ADD A,$04     ; advance 4/256 of a char cell per step   ; 6AC8: C6 04
    LD ($6AC2),A  ; save updated pixel_y                    ; 6ACA: 32 C2 6A
    CP $00        ; did it wrap around to 0?                ; 6ACD: FE 00
    JR NZ,.L6AEF  ; no -> check col state                  ; 6ACF: 20 1E
    ; pixel_y wrapped: advance to next char in sprite sequence
    LD A,($6AC3)  ; ship_char_code                          ; 6AD1: 3A C3 6A
    CP $10        ; already at end of sprite sequence?      ; 6AD4: FE 10
    JR NC,.L6AEF  ; yes -> skip advancement                 ; 6AD6: 30 17
    INC A          ; char_code++                            ; 6AD8: 3C
    LD ($6AC3),A  ; save                                    ; 6AD9: 32 C3 6A
    BIT 0,A        ; odd char code? (right-half of sprite pair) ; 6ADC: CB 47
    JR Z,.L6AEF   ; even -> nothing more to adjust          ; 6ADE: 28 0F
    ; odd char_code: diagonal step — shift pixel_x and move one row down
    LD A,($6AC1)  ; ship_pixel_x                            ; 6AE0: 3A C1 6A
    SUB $0A       ; pixel_x -= 10 (step left by half-char)  ; 6AE3: D6 0A
    LD ($6AC1),A  ; save                                    ; 6AE5: 32 C1 6A
    LD A,($6AB7)  ; ship_screen_row                         ; 6AE8: 3A B7 6A
    INC A          ; advance one screen row down            ; 6AEB: 3C
    LD ($6AB7),A  ; save                                    ; 6AEC: 32 B7 6A
.L6AEF:
    LD A,($6AB6)  ; ship_screen_col (0 = not yet at launch) ; 6AEF: 3A B6 6A
    CP $00        ; is it 0?                                ; 6AF2: FE 00
    RET NZ        ; no -> aircraft already armed, done      ; 6AF4: C0
    ; col = 0: decrement launch countdown ship_prev_char
    LD A,($6AC4)  ; ship_prev_char (launch countdown)       ; 6AF5: 3A C4 6A
    DEC A          ; countdown--                            ; 6AF8: 3D
    CP $6F        ; did it reach $6F or higher?             ; 6AF9: FE 6F
    JR NC,.L6B03  ; yes -> arm aircraft                     ; 6AFB: 30 06
    LD ($6AC4),A  ; save decremented countdown              ; 6AFD: 32 C4 6A
    CP $00        ; reached 0?                              ; 6B00: FE 00
    RET NZ        ; no -> still counting down               ; 6B02: C0
    ; countdown hit 0 -> arm aircraft
.L6B03:
    LD A,($6AB0)  ; level_pos                               ; 6B03: 3A B0 6A
    BIT 0,A        ; bit 0 set?                             ; 6B06: CB 47
    JR Z,.L6B1B   ; no -> arm with col=7                    ; 6B08: 28 11
    ; bit 0 set: arm at column 6
    LD A,$06       ; ship_screen_col = 6                    ; 6B0A: 3E 06
    LD ($6AB6),A  ; ship_screen_col                         ; 6B0C: 32 B6 6A
    LD A,$28       ; boundary = $28                         ; 6B0F: 3E 28
    LD ($6AB8),A  ; save boundary                           ; 6B11: 32 B8 6A
    LD A,($6AB7)  ; ship_screen_row                         ; 6B14: 3A B7 6A
    LD ($6B76),A  ; store row to countdown variable         ; 6B17: 32 76 6B
    RET            ; aircraft armed at column 6             ; 6B1A: C9
.L6B1B:
    ; bit 0 clear: arm at column 7
    LD A,$07       ; ship_screen_col = 7                    ; 6B1B: 3E 07
    LD ($6AB6),A  ; ship_screen_col                         ; 6B1D: 32 B6 6A
    LD A,$28       ; boundary = $28                         ; 6B20: 3E 28
    LD ($6AB8),A  ; save boundary                           ; 6B22: 32 B8 6A
    LD A,($6AB7)  ; ship_screen_row                         ; 6B25: 3A B7 6A
    LD ($6B76),A  ; store row to countdown variable         ; 6B28: 32 76 6B
    RET            ; aircraft armed at column 7             ; 6B2B: C9
; ====================================================================
; fn_update_encounter_aircraft  ($6B2C)
; ====================================================================
; Called every frame from the main loop (was mislabelled fn_update_missile).
; Part 1 ($6B2C–$6B75): manages the armed encounter aircraft:
;   Calls fn_advance_encounter_aircraft to step the aircraft position.
;   Checks if aircraft has reached the player (terrain/column bounds).
;   If in range: decrements row countdown; when expired, deactivates
;   or kills the player via fn_player_death, then spawns a new entry
;   via fn_grant_bonus_life and stores IX+5 = terrain_step-8.
; Part 2 ($6B77–$6B97): encounter-table scan loop:
;   Two entry points: $6B77 (flag=1) and $6B7B (flag=0) set $6C45
;   then call fn_init_encounter_scan (IX=$7304, DE=8, B=23) and loop:
;     active entry (IX+0 != 0): call fn_draw_encounter_entry ($6B98)
;     inactive entry (IX+0 == 0): call fn_rom_delay ($6D99)
; ====================================================================

fn_update_encounter_aircraft:   ; $6B2C
    CALL $6AC5  ; fn_advance_encounter_aircraft: step position      ; 6B2C: CD C5 6A
    LD A,($6AB6)  ; ship_screen_col (0 = inactive)                  ; 6B2F: 3A B6 6A
    CP $00        ; aircraft inactive?                               ; 6B32: FE 00
    RET Z         ; yes -> nothing to do                             ; 6B34: C8
    ; aircraft is armed: check if it has reached the player
    LD A,($6AB8)  ; boundary value ($28 = 40)                        ; 6B35: 3A B8 6A
    LD B,A        ; B = boundary                                    ; 6B38: 47
    LD A,($6AB0)  ; level_pos                                        ; 6B39: 3A B0 6A
    CP B          ; level_pos >= boundary?                           ; 6B3C: B8
    RET NC        ; yes -> aircraft not in range yet, return         ; 6B3D: D0
    ; level_pos < boundary: check terrain proximity
    LD A,($6AAD)  ; terrain_step                                     ; 6B3E: 3A AD 6A
    SUB $0B       ; terrain_step - 11                               ; 6B41: D6 0B
    LD B,A        ; B = terrain threshold                           ; 6B43: 47
    LD A,($6AB0)  ; level_pos                                        ; 6B44: 3A B0 6A
    AND $3F       ; low 6 bits                                       ; 6B47: E6 3F
    LD H,A        ; H = level_pos & $3F                             ; 6B49: 67
    SUB B         ; A = (level_pos & $3F) - threshold               ; 6B4A: 90
    RET NC        ; if >= 0: aircraft above terrain, not striking    ; 6B4B: D0
    ; aircraft has reached player level: decrement row countdown
    LD A,($6B76)  ; row countdown                                    ; 6B4C: 3A 76 6B
    DEC A          ; countdown--                                     ; 6B4F: 3D
    CP $00         ; reached 0?                                      ; 6B50: FE 00
    JR NZ,.L6B5E  ; no -> apply effect                              ; 6B52: 20 0A
    ; countdown = 0: deactivate aircraft
    LD ($6AB6),A  ; ship_screen_col = 0 (deactivate)                ; 6B54: 32 B6 6A
    LD A,($6AC1)  ; ship_pixel_x                                     ; 6B57: 3A C1 6A
    LD ($6AC4),A  ; reset launch countdown from pixel_x             ; 6B5A: 32 C4 6A
    RET            ; done                                           ; 6B5D: C9
.L6B5E:
    LD ($6B76),A  ; save updated row countdown                      ; 6B5E: 32 76 6B
    CALL $6E15  ; fn_scan_encounter_for_empty: find inactive slot    ; 6B61: CD 15 6E
    RET NZ        ; if no empty slot found, return                   ; 6B64: C0
    ; empty slot found: launch aircraft (spawn new encounter entry)
    LD A,($6AB6)  ; ship_screen_col (= 6 or 7 = entry type)        ; 6B65: 3A B6 6A
    LD E,A        ; E = entry-type index                            ; 6B68: 5F
    LD A,H        ; A = H = level_pos & $3F (column)               ; 6B69: 7C
    CALL $6DEE  ; fn_grant_bonus_life: init IX slot with E/A        ; 6B6A: CD EE 6D
    LD A,($6AAD)  ; terrain_step                                     ; 6B6D: 3A AD 6A
    SUB $08       ; base encounter height = terrain_step - 8        ; 6B70: D6 08
    LD (IX++5),A  ; store in encounter entry byte 5                 ; 6B72: DD 77 05
    RET            ; done                                           ; 6B75: C9

arcft_row_ctr:   ; $6B76  — row countdown data byte (initial value 0)
    DB $00

    ; entry point for encounter-scan with flag=1
    LD A,$01       ; flag value 1                                    ; 6B77: 3E 01
    JR .L6B7D      ; jump to scan with flag=1                       ; 6B79: 18 02
    ; entry point for encounter-scan with flag=0
    LD A,$00       ; flag value 0                                    ; 6B7B: 3E 00
.L6B7D:
    LD ($6C45),A  ; store flag used in fn_draw_encounter_entry      ; 6B7D: 32 45 6C
    CALL $6E25  ; fn_init_encounter_scan: IX=$7304, DE=8, B=23      ; 6B80: CD 25 6E
.L6B83:
    LD A,(IX++0)  ; read encounter entry state byte                  ; 6B83: DD 7E 00
    CP $00         ; is entry inactive?                              ; 6B86: FE 00
    CALL NZ,$6B98  ; no  -> fn_draw_encounter_entry: draw/move it   ; 6B88: C4 98 6B
    LD A,(IX++0)  ; re-read state (may have changed)                ; 6B8B: DD 7E 00
    CP $00         ; now inactive?                                   ; 6B8E: FE 00
    CALL Z,$6D99  ; yes -> fn_rom_delay: delay (terrain gen side)   ; 6B90: CC 99 6D
    ADD IX,DE     ; advance IX to next encounter entry (stride 8)   ; 6B93: DD 19
    DJNZ .L6B83   ; loop 23 times                                   ; 6B95: 10 EC
    RET            ; done                                           ; 6B97: C9
; 
; ====================================================================
; fn_draw_encounter_entry  ($6B98)
; ====================================================================
; Draws (or erases) one entry from the encounter object table at $7304.
; IX = pointer to 8-byte entry:  [0]=state  [1]=X  [2]=Y
;   [3-4]=sprite_ptr  [5]=terrain_threshold  [6]=Y_limit  [7]=delay
; Uses fn_compute_vram_offset ($6EE0) to get VRAM pointer,
; adjusts for ship_vram_off ($6AB2) and bit-7 half-row flag on IX+1.
; Selects draw mode via SELF-MODIFYING CODE: writes AND operands at
;   $6C38 and $6C42 before the blit loop:
;   $FF -> pure OR blit (draw)    $80 -> partial mask
;   Then XOR+AND path erases sprite (flag $6C45 == 1)
; State dispatch:
;   state $06,$07,$09 -> draw with mask $80
;   state $02, IX+6 > IX+2 -> draw with mask $80
;   else -> draw with mask $FF (full)
; NOTE: previously labelled fn_drop_bomb — that name is incorrect.
; ====================================================================

fn_draw_encounter_entry:   ; $6B98
    PUSH BC        ; save B (encounter loop counter)                 ; 6B98: C5
    PUSH DE        ; save DE                                         ; 6B99: D5
    LD C,(IX++2)   ; C = encounter Y row                            ; 6B9A: DD 4E 02
    LD A,(IX++1)   ; A = encounter X column                         ; 6B9D: DD 7E 01
    BIT 7,A        ; X bit 7 = half-row flag?                       ; 6BA0: CB 7F
    JR Z,.L6BA6    ; not set -> use X as-is                         ; 6BA2: 28 02
    ADD A,$80      ; flip bit 7 back to get true column             ; 6BA4: C6 80
.L6BA6:
    LD E,A         ; E = X column for fn_compute_vram_offset        ; 6BA6: 5F
    LD A,C         ; A = Y row                                      ; 6BA7: 79
    CALL $6EE0  ; fn_compute_vram_offset: (E=col,A=row) -> HL=VRAM  ; 6BA8: CD E0 6E
    LD DE,($6AB2)  ; DE = ship_vram_off (global VRAM scroll offset) ; 6BAB: ED 5B B2 6A
    ADD HL,DE      ; HL = encounter VRAM address                    ; 6BAF: 19
    BIT 7,(IX++1)  ; IX+1 bit 7 set? (entry occupies lower subrow)  ; 6BB0: DD CB 01 7E
    JR Z,.L6BBC    ; no -> use computed address                     ; 6BB4: 28 06
    LD DE,$0040    ; one screen row = 64 bytes                      ; 6BB6: 11 40 00
    OR A           ; clear carry                                    ; 6BB9: B7
    SBC HL,DE      ; subtract one row (move up half-row)            ; 6BBA: ED 52
.L6BBC:
    PUSH HL        ; push adjusted VRAM address                     ; 6BBC: E5
    POP IY         ; IY = VRAM address to blit to                   ; 6BBD: FD E1
    LD B,C         ; B = Y row (used as sprite row index)           ; 6BBF: 41
    SRL B          ; B = Y / 2  (half-row sprite stride index)      ; 6BC0: CB 38
    INC B          ; B += 1 (DJNZ iteration count for row offset)   ; 6BC2: 04 (note: byte also labeled missile_active in orig)
    LD L,(IX++3)   ; L = sprite data pointer lo                     ; 6BC3: DD 6E 03
    LD H,(IX++4)   ; H = sprite data pointer hi                     ; 6BC6: DD 66 04
    PUSH HL        ; save sprite base pointer                       ; 6BC9: E5
    LD E,(HL)      ; E = sprite row stride (first byte of table)    ; 6BCA: 5E
    SLA E          ; stride *= 2 (bytes per row)                    ; 6BCB: CB 23
    LD D,$00       ; D = 0                                          ; 6BCD: 16 00
.L6BCF:
    ADD HL,DE      ; advance HL by one sprite row                   ; 6BCF: 19
    DJNZ .L6BCF    ; repeat B times to reach the correct sprite row ; 6BD0: 10 FD
    DEC HL         ; HL -> sprite data for this row                 ; 6BD2: 2B
    BIT 0,(IX++1)  ; X column bit 0 = right-half offset?            ; 6BD3: DD CB 01 46
    JR Z,.L6BDC    ; no -> use current row pointer                  ; 6BD7: 28 03
    SRL E          ; half-width offset                              ; 6BD9: CB 3B
    ADD HL,DE      ; add half-row offset                            ; 6BDB: 19
.L6BDC:
    POP DE         ; DE = sprite base pointer (first byte = stride) ; 6BDC: D1
    LD A,(DE)      ; A = sprite column count                        ; 6BDD: 1A
    LD B,A         ; B = column count                               ; 6BDE: 47
    SRL B          ; B = column count / 2 (column pairs)            ; 6BDF: CB 38
    ; --- select draw mask based on entry state ---
    LD C,(IX++1)   ; C = X column (bit 7 = half-row flag still set) ; 6BE1: DD 4E 01
    LD A,(IX++0)   ; A = state byte                                 ; 6BE4: DD 7E 00
    CP $06         ; state = 6 (active type A)?                     ; 6BE7: FE 06
    JR Z,.L6C03    ; yes -> mask $80                                ; 6BE9: 28 18
    CP $07         ; state = 7 (active type B)?                     ; 6BEB: FE 07
    JR Z,.L6C03    ; yes -> mask $80                                ; 6BED: 28 14
    CP $09         ; state = 9 (fuel pickup)?                       ; 6BEF: FE 09
    JR Z,.L6C03    ; yes -> mask $80                                ; 6BF1: 28 10
    CP $02         ; state = 2 (explosion)?                         ; 6BF3: FE 02
    JR NZ,.L6BFF   ; no -> full mask $FF                            ; 6BF5: 20 08
    LD A,(IX++6)   ; A = Y_limit (state 2: check Y range)           ; 6BF7: DD 7E 06
    CP (IX++2)     ; IX+6 >= current Y?                             ; 6BFA: DD BE 02
    JR NC,.L6C03   ; yes -> mask $80                                ; 6BFD: 30 04
.L6BFF:
    LD A,$FF       ; full blit mask (draw all bits)                 ; 6BFF: 3E FF
    JR .L6C05      ; store mask and proceed                         ; 6C01: 18 02
.L6C03:
    LD A,$80       ; partial blit mask                              ; 6C03: 3E 80
.L6C05:
    ; self-modifying code: patch AND operands in the blit loop below
    LD ($6C38),A   ; patch first AND operand at $6C38               ; 6C05: 32 38 6C
    LD ($6C38),A   ; (written twice for both sub-loops)             ; 6C08: 32 38 6C
    LD ($6C42),A   ; patch second AND operand at $6C42              ; 6C0B: 32 42 6C
    ; --- sprite blit loop: B pairs of columns ---
.L6C0E:
    BIT 7,C        ; bit 7 of X = skip drawing flag?                ; 6C0E: CB 79
    JR NZ,.L6C29   ; set -> skip this char, just advance            ; 6C10: 20 17
    LD A,($6C45)   ; scan flag (0=draw, 1=erase)                    ; 6C12: 3A 45 6C
    CP $01         ; erase mode?                                    ; 6C15: FE 01
    LD A,(HL)      ; A = sprite byte for column pair, row 0         ; 6C17: 7E
    JR Z,.L6C34    ; yes -> erase (XOR) path                        ; 6C18: 28 1A
    ; draw (OR) mode: OR sprite bytes into VRAM
    OR (IY++0)     ; A = sprite | VRAM[IY]                          ; 6C1A: FD B6 00
    LD (IY++0),A   ; write back to VRAM                             ; 6C1D: FD 77 00
    INC HL         ; advance sprite pointer to row 1                ; 6C20: 23
    LD A,(HL)      ; A = sprite byte for row 1                      ; 6C21: 7E
    OR (IY++64)    ; A = sprite | VRAM[IY+64] (next screen row)     ; 6C22: FD B6 40
.L6C25:
    LD (IY++64),A  ; write back to VRAM row 1                       ; 6C25: FD 77 40
    DEC HL         ; restore sprite pointer to row 0 byte           ; 6C28: 2B
.L6C29:
    INC HL         ; advance sprite pointer (2 bytes per col pair)  ; 6C29: 23
    INC HL         ;                                                 ; 6C2A: 23
    INC IY         ; advance VRAM pointer 1 column right            ; 6C2B: FD 23
    INC C          ; advance X column index                         ; 6C2D: 0C
    INC C          ;   (2 columns per char pair)                    ; 6C2E: 0C
    DJNZ .L6C0E    ; repeat for all column pairs                    ; 6C2F: 10 DD
    POP DE         ; restore DE                                     ; 6C31: D1
    POP BC         ; restore BC                                     ; 6C32: C1
    RET            ; done                                           ; 6C33: C9
.L6C34:
    ; erase (XOR + mask) path
    XOR (IY++0)    ; A XOR VRAM[IY]                                 ; 6C34: FD AE 00
    AND $00        ; AND mask (patched at $6C38 by self-mod code)   ; 6C37: E6 00
    LD (IY++0),A   ; write erased byte back                         ; 6C39: FD 77 00
    INC HL         ; advance sprite pointer                         ; 6C3C: 23
    LD A,(HL)      ; row 1 sprite byte                              ; 6C3D: 7E
    XOR (IY++64)   ; A XOR VRAM row 1                               ; 6C3E: FD AE 40
    AND $00        ; AND mask (patched at $6C42 by self-mod code)   ; 6C41: E6 00
    JR .L6C25      ; rejoin draw path to write and advance          ; 6C43: 18 E0
; ====================================================================
; fn_update_all_encounters  ($6C46)
; ====================================================================
; Called every frame.  Initialises the encounter scan (IX=$7304,
; DE=8, B=23) then loops through all 23 encounter table entries:
;   active entry (IX+0 != 0): call fn_update_encounter_entry ($6C59)
; Uses scan_flag $6C45 = 0 (draw mode for fn_draw_encounter_entry).
; ====================================================================

fn_update_all_encounters:   ; $6C46
    CALL $6E54  ; fn_lookup_encounter_type: HL = type-table ptr     ; 6C46: CD 54 6E
    CALL $6E25  ; fn_init_encounter_scan: IX=$7304, DE=8, B=23      ; 6C49: CD 25 6E
.L6C4C:
    LD A,(IX++0)  ; load encounter entry state                      ; 6C4C: DD 7E 00
    CP $00        ; inactive?                                        ; 6C4F: FE 00
    CALL NZ,$6C59  ; no -> fn_update_encounter_entry: run state mach ; 6C51: C4 59 6C
    ADD IX,DE     ; advance to next entry                           ; 6C54: DD 19
    DJNZ .L6C4C   ; repeat for all 23 entries                       ; 6C56: 10 F4
    RET            ; done                                           ; 6C58: C9

; ====================================================================
; fn_update_encounter_entry  ($6C59)
; ====================================================================
; State machine update for one encounter table entry (IX points to
; the 8-byte slot).  On entry A = IX+0 (state from caller).
; Entry format: [0]=state [1]=X [2]=Y [3-4]=sprite_ptr
;               [5]=terrain_threshold [6]=Y_limit [7]=delay_ctr
; State dispatch:
;   state=6 -> fn_check_entry_Y_bounds ($6C88)
;   state=2 -> fn_consume_entry_fuel ($6CA8) [fuel drain animation]
;   state>=9 -> fn_consume_fuel ($6D46) [fuel pickup countdown]
;   state=5 -> fn_spawn_fuel_pickup ($6CE6) [generate fuel encounter]
; After dispatch: DEC IX+1 (move entry X left one column).
; When IX+1 decrements past $F5 (i.e. object gone off left edge):
;   -> deactivate entry (IX+0 = 0).
; NOTE: previously labelled fn_update_bomb — that name is incorrect.
; ====================================================================

fn_update_encounter_entry:   ; $6C59
    CP $06         ; state = 6?                                      ; 6C59: FE 06
    CALL Z,$6C88  ; yes -> fn_check_entry_Y_bounds                  ; 6C5B: CC 88 6C
    LD A,(IX++0)  ; reload state (may have changed)                 ; 6C5E: DD 7E 00
    CP $02         ; state = 2?                                      ; 6C61: FE 02
    CALL Z,$6CA8  ; yes -> fn_consume_entry_fuel: drain fuel bar    ; 6C63: CC A8 6C
    LD A,(IX++0)  ; reload state                                    ; 6C66: DD 7E 00
    CP $09         ; state >= 9?                                     ; 6C69: FE 09
    CALL NC,$6D46  ; yes -> fn_consume_fuel: count down fuel         ; 6C6B: D4 46 6D
    LD A,(IX++0)  ; reload state                                    ; 6C6E: DD 7E 00
    PUSH HL        ; save HL                                        ; 6C71: E5
    PUSH BC        ; save BC                                        ; 6C72: C5
    CP $05         ; state = 5?                                      ; 6C73: FE 05
    CALL Z,$6CE6  ; yes -> fn_spawn_fuel_pickup: generate fuel obj  ; 6C75: CC E6 6C
    POP BC         ; restore BC                                     ; 6C78: C1
    POP HL         ; restore HL                                     ; 6C79: E1
    DEC (IX++1)    ; X-- (move encounter object left one column)    ; 6C7A: DD 35 01
    LD A,(IX++1)  ; reload X                                        ; 6C7D: DD 7E 01
    CP $F5         ; X < $F5? (object has scrolled off left edge)   ; 6C80: FE F5
    RET NZ         ; still on screen -> return                      ; 6C82: C0
    LD (IX++0),$00 ; deactivate: set state = 0                      ; 6C83: DD 36 00 00
    RET            ; done                                           ; 6C87: C9

; ====================================================================
; fn_check_entry_Y_bounds  ($6C88)
; ====================================================================
; Called when entry state = 6 (active object).  Adjusts IX+2 (Y) to
; stay within the range bounded by IX+5 (terrain threshold).
; HL is already pointing to some state byte (set by the caller).
; BIT 0,(HL): if bit 0 clear -> entry is below threshold, INC Y
;             if bit 0 set  -> entry is above threshold, DEC Y
; Returns: IX+2 clamped to IX+5 target height.
; NOTE: previously labelled fn_bomb_hit_test — name is incorrect.
; ====================================================================

fn_check_entry_Y_bounds:   ; $6C88
    BIT 0,(HL)     ; test bit 0 of current state byte               ; 6C88: CB 46
    INC HL         ; advance HL                                     ; 6C8A: 23
    LD A,(IX++2)   ; A = current Y                                  ; 6C8B: DD 7E 02
    JR Z,.L6C9A    ; bit 0 clear -> Y adjustment path              ; 6C8E: 28 0A
    ; bit 0 set: Y is above threshold -> increment Y
    INC A          ; Y++                                            ; 6C90: 3C
    CP (IX++5)     ; exceeded terrain threshold?                    ; 6C91: DD BE 05
    JR C,.L6CA4    ; yes -> clamp to threshold                     ; 6C94: 38 0E
    DEC (IX++2)    ; overshoot -> decrement Y back                 ; 6C96: DD 35 02
    RET            ; done                                          ; 6C99: C9
.L6C9A:
    ; bit 0 clear: Y is below threshold -> decrement Y
    DEC A          ; Y--                                            ; 6C9A: 3D
    CP (IX++5)     ; below terrain threshold?                       ; 6C9B: DD BE 05
    JR C,.L6CA4    ; yes -> clamp                                  ; 6C9E: 38 04
    INC (IX++2)    ; undershoot -> increment back                  ; 6CA0: DD 34 02
    RET            ; done                                          ; 6CA3: C9
.L6CA4:
    LD (IX++2),A   ; clamp Y to computed target                    ; 6CA4: DD 77 02
    RET            ; done                                          ; 6CA7: C9
; 
; ====================================================================
; fn_consume_entry_fuel  ($6CA8)
; ====================================================================
; Called when an encounter entry has state=2 (fuel consumption active).
; Checks proximity to the player ship (ship_y/$6AAF, ship_x/$6AAE).
; IX+7 (delay bit): 0 = check fuel source; 1 = just advance fuel drain.
; When fuel source nearby (fn_find_fuel_objects returns non-empty):
;   set IX+7 bit 0 and drain: IX+2 -= 2 each step until IX+2 < $2F.
; IX+2 < $2F: entry deactivated.
; NOTE: previously labelled fn_draw_explosion — name misleads.
; ====================================================================

fn_consume_entry_fuel:   ; $6CA8
    BIT 0,(IX++7)   ; IX+7 bit 0: 0=proximity check, 1=just drain   ; 6CA8: DD CB 07 46
    JR NZ,.L6CD0    ; bit set -> skip proximity check, drain now    ; 6CAC: 20 22
    ; proximity check: is encounter close enough to the player?
    LD A,($6AAF)    ; ship_y                                         ; 6CAE: 3A AF 6A
    LD C,A          ; C = ship_y                                    ; 6CB1: 4F
    LD A,(IX++2)    ; A = encounter Y                               ; 6CB2: DD 7E 02
    SUB C           ; A = encounter_Y - ship_Y (vertical distance)  ; 6CB5: 91
    RET C           ; encounter is above ship -> no effect           ; 6CB6: D8
    LD C,A          ; C = vertical distance                         ; 6CB7: 4F
    PUSH BC         ; save C                                        ; 6CB8: C5
    LD A,($6AAE)    ; ship_x                                        ; 6CB9: 3A AE 6A
    LD C,A          ; C = ship_x                                    ; 6CBC: 4F
    LD A,(IX++1)    ; A = encounter X                               ; 6CBD: DD 7E 01
    SUB C           ; A = encounter_X - ship_X (horizontal distance); 6CC0: 91
    SLA A           ; double horizontal distance                    ; 6CC1: CB 27
    SUB $02         ; A = (encounter_X - ship_X)*2 - 2              ; 6CC3: D6 02
    POP BC          ; restore C = vertical distance                 ; 6CC5: C1
    SUB C           ; A -= vertical_dist (combined proximity check) ; 6CC6: 91
    RET NC          ; ship not in range -> return                   ; 6CC7: D0
    CALL $6D55  ; fn_find_fuel_objects: scan for nearby fuel sources ; 6CC8: CD 55 6D
    RET Z           ; none found -> return                          ; 6CCB: C8
    LD (IX++7),$01  ; set bit 0: start drain mode                  ; 6CCC: DD 36 07 01
.L6CD0:
    ; drain mode: decrement IX+2 by 2 (shrink fuel position)
    LD A,(IX++2)    ; A = encounter Y / fuel column pos             ; 6CD0: DD 7E 02
    DEC A           ; A -= 2                                        ; 6CD3: 3D
    DEC A           ;                                               ; 6CD4: 3D
    CP $2F          ; reached minimum ($2F = 47)?                   ; 6CD5: FE 2F
    JR NC,.L6CDD    ; >= $2F -> fuel fully consumed, deactivate     ; 6CD7: 30 04
    LD (IX++2),A    ; save decremented position                     ; 6CD9: DD 77 02
    RET             ; still draining                                ; 6CDC: C9
.L6CDD:
    LD (IX++7),$00  ; clear drain flag                             ; 6CDD: DD 36 07 00
    LD (IX++0),$00  ; deactivate entry (state = 0)                  ; 6CE1: DD 36 00 00
    RET             ; done                                          ; 6CE5: C9

; ====================================================================
; fn_spawn_fuel_pickup  ($6CE6)
; ====================================================================
; Called when encounter entry has state=5.  Each call decrements
; IX+7 (delay counter) until it reaches 0, then:
;   Computes a Y position based on level_pos ($6AB0) and terrain.
;   Finds an empty encounter slot via fn_find_empty_encounter_slot.
;   Initialises it as a fuel-pickup (state=9, sprite=$7254, delay=15).
;   Calls fn_advance_level_pos to record the new fuel object.
; NOTE: previously labelled fn_update_explosion — name misleads.
; ====================================================================

fn_spawn_fuel_pickup:   ; $6CE6
    LD A,(IX++7)    ; IX+7 = spawn delay counter                    ; 6CE6: DD 7E 07
    CP $00          ; counter at 0?                                 ; 6CE9: FE 00
    JR Z,.L6CF1     ; yes -> attempt spawn                         ; 6CEB: 28 04
    DEC (IX++7)     ; decrement delay counter                      ; 6CED: DD 35 07
    RET             ; not yet time                                  ; 6CF0: C9
.L6CF1:
    ; compute spawn Y from terrain
    LD A,(IX++2)    ; A = current encounter Y                      ; 6CF1: DD 7E 02
    SUB $05         ; A -= 5 (Y offset from encounter position)    ; 6CF4: D6 05
    LD B,A          ; B = base Y threshold                         ; 6CF6: 47
    LD A,($6AB0)    ; level_pos                                    ; 6CF7: 3A B0 6A
    AND $0F         ; terrain type nibble (0-15)                   ; 6CFA: E6 0F
    LD C,A          ; C = terrain type                            ; 6CFC: 4F
    LD A,($6AAF)    ; ship_y                                       ; 6CFD: 3A AF 6A
    CP $08          ; ship near top of screen?                     ; 6D00: FE 08
    JR NC,.L6D0B    ; yes -> use base Y threshold                 ; 6D02: 30 07
    ; ship in upper area: select the smaller of C and B
    LD A,C          ; A = terrain type                            ; 6D04: 79
    CP B            ; terrain type < base threshold?              ; 6D05: B8
    JR NC,.L6D0B    ; terrain >= threshold -> use threshold        ; 6D06: 30 03
    LD H,A          ; H = spawn Y = terrain type                  ; 6D08: 67
    JR .L6D0D       ; proceed                                     ; 6D09: 18 02
.L6D0B:
    LD A,B          ; A = base threshold                          ; 6D0B: 78
    SUB C           ; A = threshold - terrain type                ; 6D0C: 91
.L6D0D:
    CP $30          ; spawn Y >= $30? (off screen)                ; 6D0D: FE 30
    RET NC          ; yes -> do not spawn                         ; 6D0F: D0
    LD H,A          ; H = final spawn Y                          ; 6D10: 67
    LD (IX++7),$14  ; reset delay counter = 20                   ; 6D11: DD 36 07 14
    ; find empty encounter slot, init as fuel pickup
    PUSH IX         ; save current IX                             ; 6D15: DD E5
    PUSH BC         ; save BC                                     ; 6D17: C5
    PUSH DE         ; save DE                                     ; 6D18: D5
    CALL $6E15  ; fn_find_empty_encounter_slot: IX -> empty slot   ; 6D19: CD 15 6E
    PUSH IX         ; save new empty-slot pointer as IY           ; 6D1C: DD E5
    POP IY          ; IY = empty encounter slot                   ; 6D1E: FD E1
    POP DE          ; restore DE                                  ; 6D20: D1
    POP BC          ; restore BC                                  ; 6D21: C1
    POP IX          ; restore IX to original encounter entry      ; 6D22: DD E1
    RET NZ          ; no empty slot found -> return               ; 6D24: C0
    LD A,(IX++1)    ; A = encounter X (source position)           ; 6D25: DD 7E 01
    CP $05          ; X < 5? (too far left)                      ; 6D28: FE 05
    RET C           ; yes -> do not spawn                        ; 6D2A: D8
    LD (IY++1),A    ; new fuel entry X = source X                ; 6D2B: FD 77 01
    LD (IY++2),H    ; new fuel entry Y = H (spawn Y)             ; 6D2E: FD 74 02
    LD HL,$7254     ; HL -> fuel tank sprite data at $7254       ; 6D31: 21 54 72
    LD (IY++3),L    ; sprite ptr lo byte                         ; 6D34: FD 75 03
    LD (IY++4),H    ; sprite ptr hi byte                         ; 6D37: FD 74 04
    LD (IY++0),$09  ; new entry state = 9 (fuel pickup active)   ; 6D3A: FD 36 00 09
    LD (IY++7),$0F  ; spawn delay = 15                           ; 6D3E: FD 36 07 0F
    CALL $6E71  ; fn_advance_level_pos: advance level scroll      ; 6D42: CD 71 6E
    RET             ; done                                        ; 6D45: C9
; 
; ====================================================================
; fn_consume_fuel  ($6D46)
; ====================================================================
; Called each frame when encounter entry state >= 9 (fuel pickup).
; Decrements IX+7 (fuel supply counter) each call.
; When counter hits 0: deactivate entry (IX+0 = 0).
; ====================================================================

fn_consume_fuel:   ; $6D46
    LD A,(IX++7)    ; A = fuel supply counter                       ; 6D46: DD 7E 07
    DEC A           ; counter--                                     ; 6D49: 3D
    LD (IX++7),A    ; save                                          ; 6D4A: DD 77 07
    CP $00          ; counter = 0?                                  ; 6D4D: FE 00
    RET NZ          ; no -> fuel still available                   ; 6D4F: C0
    LD (IX++0),$00  ; fuel depleted: deactivate entry              ; 6D50: DD 36 00 00
    RET             ; done                                         ; 6D54: C9

; ====================================================================
; fn_find_fuel_objects  ($6D55)
; ====================================================================
; Searches the encounter table for state=6 or state=7 objects whose
; X position (+10) falls within the X range [IX+1+4 .. IX+1+14].
; Used by fn_consume_entry_fuel to detect when a fuel-draining object
; is adjacent to a fuel tank (state 6/7) on the terrain.
; Sets $6AB9 = 1 if a fuel object is found.  Returns:
;   Z = 0 (NZ) -> fuel object found
;   Z = 1 (Z)  -> no fuel object in range
; NOTE: previously labelled fn_check_fuel_empty — name misleads.
; ====================================================================

fn_find_fuel_objects:   ; $6D55
    LD A,(IX++1)    ; A = current encounter X                       ; 6D55: DD 7E 01
    ADD A,$0A       ; A = X + 10                                   ; 6D58: C6 0A
    PUSH HL         ; save HL                                      ; 6D5A: E5
    SUB $06         ; A = X + 4  (low bound of range)              ; 6D5B: D6 06
    LD H,A          ; H = X + 4                                    ; 6D5D: 67
    ADD A,$0A       ; A = X + 14 (high bound of range)             ; 6D5E: C6 0A
    LD L,A          ; L = X + 14                                   ; 6D60: 6F
    LD A,$00        ; clear found flag                             ; 6D61: 3E 00
    LD ($6AB9),A    ; $6AB9 = 0 (not found yet)                    ; 6D63: 32 B9 6A
    PUSH IX         ; save original IX                             ; 6D66: DD E5
    PUSH BC         ; save BC                                      ; 6D68: C5
    PUSH DE         ; save DE                                      ; 6D69: D5
    CALL $6E25  ; fn_init_encounter_scan: IX=$7304, DE=8, B=23      ; 6D6A: CD 25 6E
.L6D6D:
    LD A,(IX++0)    ; encounter entry state                        ; 6D6D: DD 7E 00
    CP $06          ; state = 6?                                   ; 6D70: FE 06
    JR Z,.L6D87     ; yes -> check X range                        ; 6D72: 28 13
    CP $07          ; state = 7?                                   ; 6D74: FE 07
    JR Z,.L6D87     ; yes -> check X range                        ; 6D76: 28 0F
.L6D78:
    ADD IX,DE       ; advance to next entry                        ; 6D78: DD 19
    DJNZ .L6D6D     ; loop 23 entries                             ; 6D7A: 10 F1
.L6D7C:
    POP DE          ; restore DE                                   ; 6D7C: D1
    POP BC          ; restore BC                                   ; 6D7D: C1
    POP IX          ; restore IX to original entry                 ; 6D7E: DD E1
    POP HL          ; restore HL                                   ; 6D80: E1
    LD A,($6AB9)    ; A = found flag (0 or 1)                     ; 6D81: 3A B9 6A
    CP $01          ; found = 1?                                   ; 6D84: FE 01
    RET             ; Z=1 if found, Z=0 if not                    ; 6D86: C9
.L6D87:
    ; state = 6 or 7: check if X+10 is within [H, L]
    LD A,(IX++1)    ; A = encounter X                              ; 6D87: DD 7E 01
    ADD A,$0A       ; A = X + 10                                   ; 6D8A: C6 0A
    CP H            ; < low bound?                                 ; 6D8C: BC
    JR C,.L6D78     ; yes -> not in range                         ; 6D8D: 38 E9
    CP L            ; >= high bound?                               ; 6D8F: BD
    JR NC,.L6D78    ; yes -> not in range                         ; 6D90: 30 E6
    LD A,$01        ; in range: set found flag                    ; 6D92: 3E 01
    LD ($6AB9),A    ; $6AB9 = 1                                   ; 6D94: 32 B9 6A
    JR .L6D7C       ; restore and return                          ; 6D97: 18 E3
; 
; ====================================================================
; fn_rom_delay  ($6D99)
; ====================================================================
; Calls ROM_DELAY ($0060) with BC=5 — a short timing delay.
; Returns immediately after the delay.
; NOTE: previously labelled fn_add_score — that name is incorrect.
;       Actual score addition is done by fn_add_pending_score ($6A16).
; ====================================================================

fn_rom_delay:   ; $6D99
    PUSH BC        ; save BC                                        ; 6D99: C5
    LD BC,$0005    ; BC = 5 (delay count)                          ; 6D9A: 01 05 00
    CALL $0060  ; ROM_DELAY                                        ; 6D9D: CD 60 00
    POP BC         ; restore BC                                    ; 6DA0: C1
    RET            ; done                                          ; 6DA1: C9

; ====================================================================
; fn_advance_terrain_column  ($6DA2)
; ====================================================================
; Reached via JP Z,$6DA2 from fn_update_terrain_height when terrain
; column counter $6ABC wraps to $FF.  Reads the next entry from the
; stage terrain-definition table (pointer at $6ABA), wraps pointer
; around to $6F8B+$19 at end of table, then updates:
;   $6ABC = lower 5 bits of entry (terrain column count)
;   $6AC0 = terrain step modifier selected from entry upper bits
; Also calls fn_draw_fuel_bar and fn_find_empty_encounter_slot to
; dispatch new terrain-type objects for the upcoming column.
; ====================================================================

.L6DA2:
    LD HL,($6ABA)   ; HL = stage_data_ptr (pointer into stage table); 6DA2: 2A BA 6A
    LD A,(HL)       ; A = current stage table byte                 ; 6DA5: 7E
    CP $00          ; end-of-table sentinel?                       ; 6DA6: FE 00
    JR NZ,.L6DB5    ; no -> use it                                ; 6DA8: 20 0B
    ; end of table: wrap back to $6F8B + $19 = $6FA4
    LD HL,$6F8B     ; HL = stage data base                        ; 6DAA: 21 8B 6F
    LD DE,$0019     ; offset $19 into table                       ; 6DAD: 11 19 00
    ADD HL,DE       ; HL = $6FA4                                  ; 6DB0: 19
    LD ($6ABA),HL   ; update stage_data_ptr                       ; 6DB1: 22 BA 6A
    LD A,(HL)       ; load first byte from wrapped position        ; 6DB4: 7E
.L6DB5:
    PUSH AF         ; save entry byte                             ; 6DB5: F5
    PUSH HL         ; save pointer                                ; 6DB6: E5
    CALL $6E71  ; fn_advance_level_pos: update level_pos/$6AB1    ; 6DB7: CD 71 6E
    POP HL          ; restore pointer                             ; 6DBA: E1
    POP AF          ; restore entry byte                          ; 6DBB: F1
    INC HL          ; advance pointer to next entry               ; 6DBC: 23
    LD ($6ABA),HL   ; save updated stage_data_ptr                 ; 6DBD: 22 BA 6A
    LD B,A          ; B = entry byte                              ; 6DC0: 47
    AND $1F         ; lower 5 bits = column count                 ; 6DC1: E6 1F
    LD ($6ABC),A    ; store terrain_col_count                     ; 6DC3: 32 BC 6A
    LD A,B          ; reload entry byte                           ; 6DC6: 78
    SRL A           ; shift out lowest 5 bits (×5 SRL)            ; 6DC7: CB 3F
    SRL A           ;                                             ; 6DC9: CB 3F
    SRL A           ;                                             ; 6DCB: CB 3F
    SRL A           ;                                             ; 6DCD: CB 3F
    SRL A           ; A = entry >> 5 = object-type index (0-7)    ; 6DCF: CB 3F
    CP $06          ; index = 6?                                  ; 6DD1: FE 06
    JR NZ,.L6DD7    ; no -> use as-is                            ; 6DD3: 20 02
    ADD A,$02       ; skip index 6 -> remap to 8                  ; 6DD5: C6 02
.L6DD7:
    LD E,A          ; E = object-type index                       ; 6DD7: 5F
    PUSH DE         ; save                                        ; 6DD8: D5
    CALL $6E15  ; fn_find_empty_encounter_slot: IX -> empty slot   ; 6DD9: CD 15 6E
    POP DE          ; restore DE                                  ; 6DDC: D1
    RET NZ          ; no empty slot -> return                     ; 6DDD: C0
    CALL $6DE8  ; fn_init_encounter_from_type: init IX slot        ; 6DDE: CD E8 6D
    LD A,(BC)       ; A = byte pointed by BC (set by fn above)    ; 6DE1: 0A
    DEC A           ; A--                                         ; 6DE2: 3D
    DEC A           ; A-- = A-2                                   ; 6DE3: 3D
    LD ($6ABD),A    ; terrain_advance_ctr = A-2                   ; 6DE4: 32 BD 6A
    RET             ; done                                        ; 6DE7: C9

; ====================================================================
; fn_init_encounter_from_type  ($6DE8)
; ====================================================================
; Reads terrain_step ($6AAD), subtracts 3 to get a Y base offset,
; then falls into fn_init_encounter_slot to fill the IX entry.
; Called from fn_advance_terrain_column with E = object-type index.
; NOTE: previously labelled fn_check_bonus_life — name unclear.
; ====================================================================

fn_init_encounter_from_type:   ; $6DE8
    LD A,($6AAD)    ; A = terrain_step                              ; 6DE8: 3A AD 6A
    DEC A           ; A -= 3 (3x DEC for -3 offset)                ; 6DEB: 3D
    DEC A           ;                                              ; 6DEC: 3D
    DEC A           ;                                              ; 6DED: 3D
    ; falls through into fn_init_encounter_slot with A = Y base

; ====================================================================
; fn_init_encounter_slot  ($6DEE)
; ====================================================================
; Fills the IX-pointed encounter entry based on:
;   E  = object-type index (from fn_advance_terrain_column)
;   A  = entry Y position
;   Uses encounter type table at $6E61 (indexed by E) for
;   sprite pointer bytes at IX+3/IX+4.
; Entry setup:
;   IX+0 = E (state / type)           IX+1 = $7F (X = rightmost)
;   IX+2 = A (Y position)
;   IX+3 = sprite ptr lo  (from $6E61 table entry)
;   IX+4 = sprite ptr hi
;   IX+6 = A - 4 (Y upper limit)
; NOTE: previously labelled fn_grant_bonus_life — name incorrect.
; ====================================================================

fn_init_encounter_slot:   ; $6DEE
    LD (IX++2),A    ; IX+2 = A (entry Y position)                  ; 6DEE: DD 77 02
    SUB $04         ; A -= 4 (upper Y limit)                       ; 6DF1: D6 04
    LD (IX++6),A    ; IX+6 = Y - 4 (upper limit)                  ; 6DF3: DD 77 06
    LD (IX++0),E    ; IX+0 = E (object type / state)               ; 6DF6: DD 73 00
    LD (IX++1),$7F  ; IX+1 = $7F (start at rightmost column)      ; 6DF9: DD 36 01 7F
    DEC E           ; E -= 1 (convert to 0-based type index)       ; 6DFD: 1D
    SLA E           ; E *= 2 (2 bytes per table entry)             ; 6DFE: CB 23
    LD D,$00        ; D = 0                                        ; 6E00: 16 00
    LD IY,$6E61     ; IY -> encounter sprite pointer table at $6E61; 6E02: FD 21 61 6E
    FD $19          ; ADD IY,DE  (IY = $6E61 + 2*(type-1))        ; 6E06: FD 19
    LD C,(IY++0)    ; C = sprite ptr lo from table                 ; 6E08: FD 4E 00
    LD (IX++3),C    ; store in entry IX+3                          ; 6E0B: DD 71 03
    LD B,(IY++1)    ; B = sprite ptr hi from table                 ; 6E0E: FD 46 01
    LD (IX++4),B    ; store in entry IX+4                          ; 6E11: DD 70 04
    RET             ; done                                         ; 6E14: C9
; 
; ====================================================================
; fn_find_empty_encounter_slot  ($6E15)
; ====================================================================
; Searches the encounter table for the first inactive entry
; (IX+0 == 0).  Initialises the scan via fn_init_encounter_scan
; (IX=$7304, DE=8, B=23), then walks each entry:
;   active entry (IX+0 != 0): advance to next, loop
;   inactive entry (IX+0 == 0): RET with Z=1, IX pointing to slot
; If all 23 entries are active: CP $00; RET with Z flag
; NOTE: previously labelled fn_player_death — that name is incorrect.
; ====================================================================

fn_find_empty_encounter_slot:   ; $6E15
    CALL $6E25  ; fn_init_encounter_scan: IX=$7304, DE=8, B=23      ; 6E15: CD 25 6E
.L6E18:
    LD A,(IX++0)  ; read entry state byte                           ; 6E18: DD 7E 00
    CP $00        ; inactive (state = 0)?                           ; 6E1B: FE 00
    RET Z         ; yes -> IX points here, return Z=1 (found)      ; 6E1D: C8
    ADD IX,DE     ; advance to next entry (stride 8)               ; 6E1E: DD 19
    DJNZ .L6E18   ; try all 23 entries                             ; 6E20: 10 F6
    CP $00        ; last A was non-zero -> sets Z=0 (not found)    ; 6E22: FE 00
    RET           ; return Z=0 (no empty slot)                     ; 6E24: C9

; ====================================================================
; fn_init_encounter_scan  ($6E25)
; ====================================================================
; Initialises IX/DE/B for the encounter-table scan loop in fn_draw_enemy:
;   IX <- $7304  (encounter table base, 23 entries x 8 bytes each)
;   DE <- $0008  (8-byte stride per entry)
;   B  <- $17    (23 entries to scan)
; Returns immediately.  Called at the start of fn_draw_enemy.
; NOTE: previously labelled fn_game_over -- that label is incorrect.
; ====================================================================

fn_init_encounter_scan:   ; $6E25
    LD IX,$7304    ; IX -> encounter table (23 sprites x 8 bytes)    ; 6E25: DD 21 04 73
    LD DE,$0008    ; stride = 8 bytes per entry                      ; 6E29: 11 08 00
    LD B,$17       ; B = 23 entries to scan                          ; 6E2C: 06 17
    RET            ; return                                          ; 6E2E: C9

; ====================================================================
; fn_update_terrain_scroll  ($6E2F)
; ====================================================================
; Manages the terrain_advance_ctr ($6ABD) countdown and drives the
; terrain scroll/generation pipeline each frame step:
;   terrain_advance_ctr > 0: decrement, call fn_draw_column_marker ($6EFB)
;   terrain_advance_ctr = 0: call fn_draw_column_marker, then check
;     terrain_col_count ($6ABC):
;       $6ABC = $FF -> JP fn_advance_terrain_column ($6DA2)
;       else -> decrement $6ABC; if now $FF -> JP fn_draw_column_marker
;       else -> JP fn_update_terrain_height (.L6E7F)
; NOTE: previously labelled fn_clear_screen — name is incorrect.
; ====================================================================

fn_update_terrain_scroll:   ; $6E2F
    LD A,($6ABD)    ; A = terrain_advance_ctr                      ; 6E2F: 3A BD 6A
    CP $00          ; counter = 0?                                 ; 6E32: FE 00
    JR Z,.L6E3D     ; yes -> run full update                       ; 6E34: 28 07
    ; counter > 0: just decrement and draw column marker
    DEC A           ; counter--                                    ; 6E36: 3D
    LD ($6ABD),A    ; save                                         ; 6E37: 32 BD 6A
    JP $6EFB  ; fn_draw_column_marker and return                   ; 6E3A: C3 FB 6E
.L6E3D:
    ; counter = 0: run terrain column update
    CALL $6EFB  ; fn_draw_column_marker: draw terrain pixel marker ; 6E3D: CD FB 6E
    LD A,($6ABC)    ; A = terrain_col_count                        ; 6E40: 3A BC 6A
    CP $FF          ; wrapped to $FF?                              ; 6E43: FE FF
    JP Z,.L6DA2  ; yes -> fn_advance_terrain_column: next segment  ; 6E45: CA A2 6D
    ; terrain_col_count not wrapped: continue step
    DEC A           ; terrain_col_count--                          ; 6E48: 3D
    LD ($6ABC),A    ; save                                         ; 6E49: 32 BC 6A
    CP $FF          ; just wrapped?                                ; 6E4C: FE FF
    JP Z,$6EFB  ; yes -> draw column marker again                  ; 6E4E: CA FB 6E
    JP .L6E7F   ; else -> fn_update_terrain_height: LFSR step      ; 6E51: C3 7F 6E
; 
; ====================================================================
; fn_lookup_encounter_type  ($6E54)
; ====================================================================
; Returns HL = pointer into the encounter sprite-type table at $6F5C
; indexed by level_pos ($6AB0) & $0F (terrain type, 0–15).
; Called each frame from fn_update_all_encounters.
; NOTE: previously labelled fn_read_joystick — name is incorrect.
; ====================================================================

fn_lookup_encounter_type:   ; $6E54
    LD A,($6AB0)    ; A = level_pos                                 ; 6E54: 3A B0 6A
    AND $0F         ; low nibble = terrain type index (0–15)        ; 6E57: E6 0F
    LD E,A          ; E = index                                    ; 6E59: 5F
    LD D,$00        ; D = 0                                        ; 6E5A: 16 00
    LD HL,$6F5C     ; HL -> encounter type table base              ; 6E5C: 21 5C 6F
    ADD HL,DE       ; HL = &table[terrain_type]                    ; 6E5F: 19
    RET             ; return HL = type table pointer               ; 6E60: C9

; ---- encounter sprite pointer table ($6E61) ---------------------
; 8 entries x 2 bytes each: lo and hi bytes of sprite data address.
; Indexed by encounter object type (E): used by fn_init_encounter_slot
; via FD $19 (ADD IY,DE) to load IX+3/IX+4 sprite data pointers.
enc_sprite_table:   ; $6E61
    DB $6C $70   ; type 1: sprite ptr = $706C                      ; 6E61-6E62
    DB $AB $70   ; type 2: sprite ptr = $70AB                      ; 6E63-6E64
    DB $CA $70   ; type 3: sprite ptr = $70CA                      ; 6E65-6E66
    DB $68 $71   ; type 4: sprite ptr = $7168                      ; 6E67-6E68
    DB $71 $71   ; type 5: sprite ptr = $7171                      ; 6E69-6E6A
    DB $71 $71   ; type 6: sprite ptr = $7171                      ; 6E6B-6E6C (duplicate)
    DB $71 $71   ; type 7: sprite ptr = $7171                      ; 6E6D-6E6E
    DB $71 $71   ; type 8: sprite ptr = $7171                      ; 6E6F-6E70

; ====================================================================
; fn_advance_level_pos  ($6E71)
; ====================================================================
; Increments scroll_sub ($6AB1) by A (sub-pixel scroll counter),
; then advances level_pos ($6AB0) by a semi-random amount from
; the Z80 R register (& $7F).
; Called each terrain scroll step to keep level_pos synchronized
; with the background scroll.
; NOTE: previously labelled fn_draw_fuel_bar — name is incorrect.
; ====================================================================

fn_advance_level_pos:   ; $6E71
    LD HL,$6AB0     ; HL -> level_pos ($6AB0)                      ; 6E71: 21 B0 6A
    INC HL          ; HL -> scroll_sub ($6AB1)                     ; 6E74: 23
    ADD A,(HL)      ; scroll_sub += A                              ; 6E75: 86
    LD (HL),A       ; save updated scroll_sub                      ; 6E76: 77
    DEC HL          ; HL -> level_pos ($6AB0)                      ; 6E77: 2B
    LD A,R          ; A = Z80 R register (pseudo-random increment) ; 6E78: ED 5F
    AND $7F         ; keep 7 bits                                  ; 6E7A: E6 7F
    ADD A,(HL)      ; level_pos += R & $7F                         ; 6E7C: 86
    LD (HL),A       ; save updated level_pos                       ; 6E7D: 77
    RET             ; done                                         ; 6E7E: C9
; ====================================================================
; fn_update_terrain_height  (.L6E7F)
; ====================================================================
; Stepped via JP from fn_update_terrain_scroll when terrain_col_count
; is not wrapping.  Runs a 16-bit LFSR stored at $6ABE-$6ABF to
; produce the next terrain height byte.  When LFSR exhausted (L=0):
;   loads next 2-byte seed from terrain-type table at
;   $702C + (level_pos & $1F)*2, and updates terrain_step modifier
;   in $6AC0 (1 for normal terrain, $FF for blocked/ocean).
; ====================================================================

.L6E7F:
    LD HL,($6ABE)   ; HL = LFSR state ($6ABE lo, $6ABF hi)         ; 6E7F: 2A BE 6A
    BIT 0,L         ; L bit 0 = gate: apply terrain step?          ; 6E82: CB 45
    JR Z,.L6E95     ; bit 0 clear -> just shift, no height update  ; 6E84: 28 0F
    ; bit 0 set: update terrain_step
    LD A,($6AAD)    ; A = terrain_step                             ; 6E86: 3A AD 6A
    LD B,A          ; B = terrain_step                             ; 6E89: 47
    LD A,($6AC0)    ; A = terrain step modifier                    ; 6E8A: 3A C0 6A
    ADD A,B         ; A = terrain_step + modifier                  ; 6E8D: 80
    CP $30          ; hit maximum $30 (48)?                        ; 6E8E: FE 30
    JR Z,.L6ED3     ; yes -> set modifier to $FF (blocked)         ; 6E90: 28 41
    LD ($6AAD),A    ; save updated terrain_step                    ; 6E92: 32 AD 6A
.L6E95:
    ; shift LFSR right by 1 bit (H:L >> 1, with bit carry)
    SRL L           ; L >>= 1                                      ; 6E95: CB 3D
    BIT 0,H         ; H bit 0 = next bit to shift into L?          ; 6E97: CB 44
    JR Z,.L6E9D     ; no carry                                     ; 6E99: 28 02
    SET 7,L         ; set bit 7 of L from H bit 0                  ; 6E9B: CB FD
.L6E9D:
    SRL H           ; H >>= 1                                      ; 6E9D: CB 3C
    LD ($6ABE),HL   ; save updated LFSR                            ; 6E9F: 22 BE 6A
    LD A,L          ; A = new L                                    ; 6EA2: 7D
    CP $00          ; LFSR exhausted (L = 0)?                      ; 6EA3: FE 00
    RET NZ          ; no -> return, keep stepping                  ; 6EA5: C0
    ; LFSR exhausted: load next seed from terrain-type table
    LD A,($6AB0)    ; A = level_pos                                ; 6EA6: 3A B0 6A
    AND $1F         ; low 5 bits (terrain type cycle 0–31)         ; 6EA9: E6 1F
    SLA A           ; * 2 (2 bytes per table entry)                ; 6EAB: CB 27
    LD HL,$702C     ; HL -> terrain seed table at $702C            ; 6EAD: 21 2C 70
    LD B,$00        ; B = 0                                        ; 6EB0: 06 00
    LD C,A          ; C = index                                    ; 6EB2: 4F
    ADD HL,BC       ; HL = &seed_table[index]                      ; 6EB3: 09
    LD A,(HL)       ; A = lo byte of seed                          ; 6EB4: 7E
    AND $F8         ; keep upper 5 bits as LFSR seed               ; 6EB5: E6 F8
    LD ($6ABE),A    ; store new LFSR lo byte                       ; 6EB7: 32 BE 6A
    INC HL          ; pointer to hi byte                           ; 6EBA: 23
    LD A,(HL)       ; A = hi byte of seed                          ; 6EBB: 7E
    LD ($6ABF),A    ; store new LFSR hi byte                       ; 6EBC: 32 BF 6A
    CALL $6E71  ; fn_advance_level_pos: step scroll counter        ; 6EBF: CD 71 6E
    ; select terrain_step modifier based on terrain_step value
    LD A,($6AAD)    ; A = terrain_step                             ; 6EC2: 3A AD 6A
    CP $19          ; < $19 (25)?                                  ; 6EC5: FE 19
    JR NC,.L6ECF    ; >= 25 -> further check                       ; 6EC7: 30 06
.L6EC9:
    LD A,$01        ; modifier = 1 (gentle slope)                  ; 6EC9: 3E 01
.L6ECB:
    LD ($6AC0),A    ; save terrain step modifier to $6AC0          ; 6ECB: 32 C0 6A
    RET             ; done                                         ; 6ECE: C9
.L6ECF:
    CP $2C          ; < $2C (44)?                                  ; 6ECF: FE 2C
    JR C,.L6ED7     ; yes -> check level_pos bit 6                 ; 6ED1: 38 04
.L6ED3:
    LD A,$FF        ; modifier = $FF (flat / blocked terrain)      ; 6ED3: 3E FF
    JR .L6ECB       ; store and return                             ; 6ED5: 18 F4
.L6ED7:
    LD A,($6AB0)    ; A = level_pos                                ; 6ED7: 3A B0 6A
    BIT 6,A         ; level_pos bit 6 set?                         ; 6EDA: CB 77
    JR Z,.L6EC9     ; no -> modifier = 1                           ; 6EDC: 28 EB
    JR .L6ED3       ; yes -> modifier = $FF                        ; 6EDE: 18 F3

; ====================================================================
; fn_compute_vram_offset  ($6EE0)
; ====================================================================
; Converts a pixel coordinate (A=pixel_row, E=pixel_col) to a
; TRS-80 VRAM offset and a pixel-within-char indicator:
;   HL = (pixel_row / 3) * 64 + pixel_col / 2  (VRAM char offset)
;   C  = (pixel_row mod 3) * 2                 (pixel row within char)
; TRS-80 semigraphic chars are 2×3 pixels (64 cols × 16 rows of chars
; = 128×48 virtual pixel grid).
; NOTE: previously labelled fn_draw_lives — that name is incorrect.
; ====================================================================

fn_compute_vram_offset:   ; $6EE0
    LD B,$FF        ; B = -1 (quotient counter, starts at $FF)     ; 6EE0: 06 FF
.L6EE2:
    INC B           ; B++ (count subtractions)                     ; 6EE2: 04
    SUB $03         ; A -= 3 (divide A by 3)                       ; 6EE3: D6 03
    JP P,.L6EE2     ; A still >= 0 -> continue dividing            ; 6EE5: F2 E2 6E
    ADD A,$03       ; fix overshoot: A = A mod 3                   ; 6EE8: C6 03
    SLA A           ; A = 2 * (A mod 3) (pixel row within char)    ; 6EEA: CB 27
    LD C,A          ; C = pixel row offset within char             ; 6EEC: 4F
    LD L,B          ; L = quotient (A / 3)                         ; 6EED: 68
    LD H,$00        ; H = 0                                        ; 6EEE: 26 00
    LD B,$06        ; B = 6 (left-shift count for *64)             ; 6EF0: 06 06
.L6EF2:
    ADD HL,HL       ; HL <<= 1 (multiply by 2, six times = *64)    ; 6EF2: 29
    DJNZ .L6EF2     ; repeat 6 times -> HL = (A/3)*64             ; 6EF3: 10 FD
    LD D,$00        ; D = 0                                        ; 6EF5: 16 00
    SRL E           ; E = pixel_col / 2 (pixel col to char col)    ; 6EF7: CB 3B
    ADD HL,DE       ; HL = (A/3)*64 + pixel_col/2 = VRAM offset   ; 6EF9: 19
    RET             ; done: HL = VRAM offset, C = pixel row offset ; 6EFA: C9

; ====================================================================
; fn_draw_column_marker  ($6EFB)
; ====================================================================
; Draws the terrain boundary pixel marker on the right edge of the
; screen (column $7F) at the row given by terrain_step ($6AAD).
; Calls fn_set_pixel_bit twice (via fn_compute_vram_offset at $6EE0)
; to set two adjacent semigraphic pixel bits, using ship_vram_off
; ($6AB2) and $6AB4 for VRAM pointer adjustments.
; NOTE: previously labelled fn_draw_number — name misleads.
; ====================================================================

fn_draw_column_marker:   ; $6EFB
    LD A,($6AAD)    ; A = terrain_step (row in pixels)              ; 6EFB: 3A AD 6A
    LD E,$7F        ; E = $7F = column 127 (right edge of screen)  ; 6EFE: 1E 7F
    CALL $6EE0  ; fn_compute_vram_offset: HL=VRAM offset, C=row-bit ; 6F00: CD E0 6E
    PUSH HL         ; save VRAM offset                             ; 6F03: E5
    PUSH BC         ; save C (pixel row offset)                    ; 6F04: C5
    LD DE,($6AB2)   ; DE = ship_vram_off (scroll-adjusted offset)  ; 6F05: ED 5B B2 6A
    INC C           ; C++ (advance to next pixel row bit)          ; 6F09: 0C
    CALL $6F13  ; fn_set_pixel_bit: set pixel at (HL+DE, C)        ; 6F0A: CD 13 6F
    POP BC          ; restore C                                    ; 6F0D: C1
    POP HL          ; restore VRAM offset                          ; 6F0E: E1
    LD DE,($6AB4)   ; DE = second VRAM offset adjustment           ; 6F0F: ED 5B B4 6A
    ; falls through into fn_set_pixel_bit for second pixel

; ====================================================================
; fn_set_pixel_bit  ($6F13)
; ====================================================================
; Sets one semigraphic pixel bit in VRAM using SELF-MODIFYING CODE.
; Process:
;   1. HL = HL + DE (adjust VRAM pointer)
;   2. C = C * 8     (map pixel-row-offset to CB SET bit index)
;   3. Compute opcode byte: A = $C6 + C*8
;      ($C6 = SET 0,(HL), $CE = SET 1,(HL), ... $EE = SET 5,(HL))
;   4. Patch byte at $6F21 with the computed opcode argument.
;   5. Execute the now-patched CB instruction which sets the pixel.
; This encodes SET b,(HL) dynamically based on the pixel row C.
; NOTE: previously labelled fn_print_string — name is incorrect.
; ====================================================================

fn_set_pixel_bit:   ; $6F13
    ADD HL,DE       ; HL = VRAM char address + offset               ; 6F13: 19
    SLA C           ; C *= 2                                       ; 6F14: CB 21
    SLA C           ;    *= 4                                      ; 6F16: CB 21
    SLA C           ;    *= 8 (C = 8 * pixel_row_offset)           ; 6F18: CB 21
    LD A,$C6        ; A = $C6 (base opcode for SET 0,(HL))         ; 6F1A: 3E C6
    ADD A,C         ; A = $C6 + C*8 (selects SET 0..5,(HL))        ; 6F1C: 81
    LD ($6F21),A    ; ** SELF-MODIFYING ** patch SET operand byte   ; 6F1D: 32 21 6F
    RLC B           ; execute: CB ?? = SET n,(HL) (patched byte)   ; 6F20: CB 00
    RET             ; return                                       ; 6F22: C9
; fn_copy_title_screen_to_vram:
;   Copies the 1024-byte ($0400) pre-formed title screen image from the address
;   stored in $6AB2 (= $5E00 at startup) directly into video RAM at $3C00.
;   This is the mechanism by which the title/attract screen is displayed:
;   the entire 64×16 semigraphic VRAM layout is stored as a flat binary blob
;   at $5E00-$61FF and blasted to VRAM in one LDIR instruction.
    LD BC,$0400                                             ; 6F23: 01 00 04  ; 1024 bytes = full screen
    LD HL,($6AB2)                                           ; 6F26: 2A B2 6A  ; src = title screen data ($5E00)
    LD DE,$3C00                                             ; 6F29: 11 00 3C  ; dst = video RAM base
    LDIR                                                    ; 6F2C: ED B0     ; copy all 1024 bytes
    RET                                                     ; 6F2E: C9
    LD BC,$03FF                                             ; 6F2F: 01 FF 03
    LD HL,($6AB2)                                           ; 6F32: 2A B2 6A
    LD DE,($0000)                                           ; 6F35: ED 5B 00 00