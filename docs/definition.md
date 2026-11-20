# LATFUN6 — Board Definition v0.1 (draft)

> The open ECP5 **textbook board** for the Open FPGA Tutorial. Defined by the curriculum: every on-board feature maps to a lab.
> Status: **draft for review**, 2026-11-20. Source of truth for the schematic phase (`pcb-schematic` skill).
> Inputs: project hand-off and a ULX3S study (private working notes, not published).

## 1. Decisions (locked 2026-11-20)

| # | Decision | Choice |
|---|---|---|
| D1 | CAD | **EasyEDA Pro** (existing skills + MCP + JLCPCB/LCSC pipeline). Publish sources + PDF + Gerber/BOM/CPL |
| D2 | Scope | **HDMI on board, SDRAM off.** Grow via PMOD |
| D3 | FPGA | LFE5U-25F CABGA256. **Placed part: LFE5U-25F-7BG256I** (C1550762) because the -6BG256C is ZERO_STOCK at JLCPCB (see `hardware/latfun6/FPGA_Availability_Note.md`). Ball map **verified identical to LFE5U-45F** (Lattice CSVs). No SERDES: Ch 13 labs optional, possible later "pro" (UM) variant |
| D4 | Licence | **CERN-OHL-S v2** hardware · CC BY-SA 4.0 docs · MIT code |
| D5 | Clock | 25 MHz oscillator |
| D6 | Programming | One USB-C: power + FT2232H-class JTAG (ch A) + UART (ch B), `openFPGALoader` out of the box |

**Still open (placeholders used):** public name (codename `LATFUN6`), positioning (assumed: course first, usable as a general board), price/channel (assumed: JLCPCB-assembled, target below), board size.

## 2. Requirements table

Priority: **M** must · **S** should · **C** could · **X** out (with reason).

| ID | Feature | Lab(s) | Interface / notes | Pri |
|---|---|---|---|---|
| R1 | 25 MHz oscillator, 3.3 V CMOS, on a PCLK-capable pin; TP on the clock | 1.1, 4.1, all | Global clock input pin; TP_CLK25 + GND pad | M |
| R2 | 8 user LEDs | 1.1, 3.3, 4.x, 5.x | Active-high, FPGA → resistor → LED → GND | M |
| R3 | User buttons: 1 × RESET (user, not PROGRAMN) + 3 × user (one deliberately **un-debounced**) | 4.3, 5.2, Showcase A `btn_fire` | Active-low with pull-up, **no RC on BTN1** (bounce lab); RC option footprint on others | M |
| R4 | 4-position DIP switch | Showcase A `sw_cont`, `sw_len[1:0]` | Active-low, pull-ups | M |
| R5 | USB-UART (FT2232H ch B), 115200+ baud, RTS/CTS to FPGA | 5.x logging, 9.1, 11.1 | Nets named from FPGA side: `UART_TX` (FPGA→PC), `UART_RX` (PC→FPGA) | M |
| R6 | Fast JTAG (FT2232H ch A, MPSSE) | 1.1, 16.3, 18.1 | `openFPGALoader -b latfun6`; TCK 4.7 k pull-down, TMS/TDI/TDO pull-ups | M |
| R7 | External JTAG header | 18.1 (recovery), debug | 2×5 1.27 mm or 2.54 mm, **wired by pin number**, checked pin by pin | S |
| R8 | Config SPI flash W25Q128JV-class (QSPI), user access via `USRMCLK` | 11.2, 16.3 | **4.7 k pull-up on CSSPIN**; 1 k pull-up on CCLK; CFG[2:0]=010 | M |
| R9 | Config status: PROGRAMN button, INITN, DONE LED (+pull-ups) | 16.3, 18.1 | Per TN-02038 | M |
| R10 | On-board I²C EEPROM 24C02 + pull-ups (4.7 k) | 11.3 | 3.3 V; address shown on silkscreen | M |
| R11 | Audio out: 2 × PWM/ΔΣ pins → RC low-pass → 3.5 mm stereo jack | 14.1 | 2nd-order RC, AC-coupled, ESD; line level | M |
| R12 | HDMI/DVI out (type-A) | 15.1 | 4 TMDS pairs on adjacent differential-capable pins (LVCMOS33D as on ULX3S), DDC via level shifter to 5 V, 5 V to monitor via current-limited switch, HPD input, ESD array | M |
| R13 | 4 × PMOD (2×6, 3.3 V), pins assigned as **differential-capable pairs** | Showcases A/B, growth | Showcase B needs 22 GPIO, A needs a diff pair | M |
| R14 | Logic-analyser header: 8 FPGA-driven probe channels + GND, sigrok/Saleae-friendly 2×5 | 9.2, 9.3 cross-check | FPGA routes internal signals out | S |
| R15 | Labelled test points with adjacent GND pads | all (verification-first) | CLK25, RESET, UART TX/RX, I²C SCL/SDA, flash SCK/CS, PLL-out pin, DONE, INITN | M |
| R16 | Rail current sensing: series shunt + Kelvin TPs on 1.1 V, 2.5 V, 3.3 V | 17.3 | e.g. 0.05–0.1 Ω 1 % shunts; drop < 1 % of rail at max load | M |
| R17 | Loopback jumper pair (2 FPGA pins on a 2-pin header with jumper fitted) | self-test, 8.x on hardware | Factory test detects jumper | S |
| R18 | Power LED (3.3 V) + DONE LED | 18.1 smoke test | | M |
| R19 | Factory self-test bitstream in flash: PASS/FAIL per peripheral over UART | 18.1 | Firmware deliverable, not hardware | M |
| R20 | Mounting holes (4 × M3), rubber feet | — | | M |
| R21 | `board.json` → `.lpf`, docs, examples | 16.1, AI agents | Software deliverable; pinout frozen at v1.0 | M |
| R22 | LVDS-capable pair for Showcase A | Showcase A LVDS exercise | **Verified** (DS-02012 §2.14, Table 3.x): LVDS25 output needs VCCIO = 2.5 V, only on A/B pairs of banks 2/3/6/7; diff inputs only in L/R banks. Implemented: every PMOD sits alone on one L/R bank using A/B pairs, so a 2.5 V-PMOD variant is a single-bank change. v0.1 keeps all banks 3.3 V (LVCMOS33D for Showcase A) | S/C |
| X1 | SDRAM | 10.x | X for v1: Ch 10 labs use on-chip EBR (D2) | X |
| X2 | SERDES | 13.2, 13.3 | X: needs LFE5UM (D3) | X |
| X3 | ESP32 / Wi-Fi | — | X: JTAG-takeover risk (principle 9); PMOD instead | X |
| X4 | micro-SD, ADC, RTC, 2nd USB | — | X: no lab uses them; PMOD | X |
| X5 | VCCIO selector jumper | — | X: fixed bank voltages, documented (lesson §5) | X |

## 3. Block diagram

```
 USB-C ──┬─ CC1/CC2 5.1k→GND
 (5 V)   ├─ VBUS → eFuse/PTC + TVS + reverse-current protection → 5V_SYS
         └─ D+/D- → FT2232H ──ch A MPSSE── JTAG ──┬── ECP5 LFE5U-25F (CABGA256)
                     │  93LC56 EEPROM            └── ext JTAG 2×5
                     │  12 MHz xtal
                     └──ch B UART (TX/RX/RTS/CTS) ──── ECP5

 ECP5 ── bank 8 (config) ── W25Q128JV QSPI flash (CSSPIN 4.7k PU, CCLK 1k PU)
      ── 25 MHz osc (PCLK pin)          ── 8 LEDs, 4 buttons, 4-DIP
      ── I²C ── 24C02                   ── audio PWM L/R → RC → 3.5 mm jack
      ── TMDS ×4 + DDC + HPD ── HDMI-A  ── 4 × PMOD (diff pairs)
      ── LA header 2×5                  ── loopback jumper, test points
```

## 4. Power tree (to size in schematic gate A2)

| Rail | Source | Loads | Est. max | Notes |
|---|---|---|---|---|
| 5V_SYS | USB-C VBUS via protection | everything; HDMI 5 V (≤55 mA spec) | ~1.0 A | Input: TVS, PTC/eFuse, reverse-current block. USB default power (no PD) |
| 3V3 | Buck from 5 V | VCCIO banks, FT2232H, flash, EEPROM, LEDs, PMODs (≤ 100 mA each) | ~1.0 A | Shunt + Kelvin TP (R16) |
| 1V1 | Buck from 5 V (or 3.3 V) | ECP5 VCC core (+ 45F headroom) | ~1.0 A | FB divider checked worst-case with 1 % R: inside 1.1 V ± 5 % (lesson §5). Shunt + TP |
| 2V5 | LDO from 3.3 V | ECP5 VCCAUX (+ any 2.5 V bank) | ~0.2 A | Shunt + TP |
| FT 1V8 | FT2232H internal regulator | FT2232H core | — | Per FT2232H datasheet |

Power sequencing per ECP5 datasheet (FPGA-DS-02012): verify that no sequencing is required, or that a power-good chain is needed. Ferrite beads are real beads, not 0 Ω (lesson §5).

## 5. Bank-voltage plan (verified against the CABGA256 pinout)

| Bank | VCCIO | Use |
|---|---|---|
| 0 | 3.3 V | clock, HDMI TMDS (LVCMOS33D) + DDC/HPD, audio, I²C |
| 1 | 3.3 V | LEDs, buttons, DIP, UART, LA header, loopback, PLL test point |
| 7 / 6 / 2 / 3 | 3.3 V | PMOD1 / PMOD2 / PMOD3 / PMOD4 (one PMOD per bank, A/B pairs) |
| 8 | 3.3 V | Config: SPI flash (QSPI) |

Implemented in `hardware/latfun6/board/latfun6.json` (generated by `tools/gen_board.py`, validated against the Lattice CSV, place-and-route proven on 25k and 45k).

All user I/O are 3.3 V, fixed and silkscreened. R22 may change one bank to 2.5 V if true LVDS is promoted to S.

## 6. I/O budget (LFE5U-25F CABGA256: 197 user I/O)

| Group | Pins |
|---|---|
| Clock | 1 |
| LEDs | 8 |
| Buttons (user) | 4 |
| DIP | 4 |
| UART (TX/RX/RTS/CTS) | 4 |
| Flash QSPI extra (IO2/IO3; CS/MOSI/MISO/CCLK are config pins) | 2 |
| I²C | 2 |
| Audio | 2 |
| HDMI (8 TMDS + SCL/SDA + HPD) | 11 |
| 4 × PMOD | 32 |
| LA header | 8 |
| Loopback | 2 |
| **Total** | **80 user I/O + 4 config-shared flash pins** (~41 % of 197), leaving room for a 45F and a later GPIO header |

## 7. Physical and manufacturing targets

- PCB: **4 layers** (SIG / GND / PWR / SIG) as the target. CABGA256 is 0.8 mm pitch, which is standard (not class 3) at JLCPCB. Confirm via size/trace capability at layout; fall back to 6 layers only if fan-out or TMDS needs it.
- Size target ~ 90 × 60 mm, all connectors on edges: USB-C, HDMI, audio on one long edge; PMODs on the opposite edge and ends.
- Assembly: JLCPCB SMT, single-side top where possible. Parts from LCSC basic/preferred where possible. Every part passes the availability gate (pcb-fab-prep).
- Silkscreen: pin names on every header, bank voltages, I²C address, TP names, licence + revision.

## 8. Cost target (placeholder)

- Assembled board BOM + PCB + assembly at qty 10: **≤ US$ 45** target (FPGA + FT2232H dominate; to be priced at A2).
- Student price goal: **well below the US$ 155 class**. Exact channel to decide (open item).

## 9. Verification hooks (summary)

Test points (R15) · rail shunts (R16) · LA header (R14) · loopback (R17) · DONE/INITN visible · factory self-test (R19) · `board.json` single source (R21).

## 10. Verify-before-capture list (feeds pcb-schematic gate A2)

1. ECP5 CABGA256 pinout: PCLK pins, differential pairs per bank, bank-8 config pins, VCCIO/VCCAUX/VCC ball map (FPGA-DS-02012, pinout CSV).
2. Configuration per TN-02038 / FPGA-TN-02039: CFG pins, CCLK/CSSPIN pull-ups, PROGRAMN/INITN/DONE.
3. LVDS / LVCMOS33D rules per sysIO TN (R22), TMDS on ECP5 at 3.3 V (pixel clock 25.175 MHz → 252 Mbit/s for 640×480).
4. FT2232H reference design: VREGIN, EEPROM 93LC56, 12 MHz crystal, USB-C connection. `openFPGALoader` board-entry format (FTDI VID/PID, ch A JTAG).
5. Buck/LDO choices on LCSC with FB math; USB-C protection part.
6. LFE5U-25F and LFE5U-45F: same CABGA256 ball map and power pins (45F compatibility).
7. HDMI DDC level shifter + 5 V current limit + ESD reference.
