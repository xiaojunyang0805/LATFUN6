# LATFUN6 Schematic Worknote

> ⚠ **RE-BASELINE IN PROGRESS (2026-11-20): definition v0.2, application board.** FPGA → LFE5UM5G-45F-8BG381 (85F-ready); adds SFP + SMA + PCIe x1 (SERDES), DDR3L 512 MB, GbE (RTL8211F), microSD, USB 2.0 ULPI, 12 V slot power. Core rail 1.1 → **1.2 V**. Sections below still describe v0.1 where not yet updated; blocks A/B(partly)/D/E/F/H placements are reused. U5 (BG256) and `board/latfun6.json`/`.lpf` (v0.1) are **superseded** and will be regenerated against the ECP5-5G-45 CSV. See `docs/definition.md` §8.
>
> **v0.2 pinout DONE (2026-11-20):** `tools/gen_board.py` v0.2 → `board/latfun6.json`, `.lpf`, `latfun6_platform.py` (LiteX). 175 signals / 175 balls; checks: banks + VCCIO (3.3 V: 0/1/2/3/8; 1.35 V: 6/7), pairs, A/B LVDS pairs for PMODs, PCLK for clk_25mhz / eth_rx_clk / ulpi_clk, DDR3 byte lanes inside their DQS groups (byte0 L41 DQS K2, byte1 L29 DQS H4), K16/K17 unused, identical roles on the 85F. DDR3 ball map follows Lattice's ECP5-5G Versa reference (same device/package) plus A13 = A3, A14 = D3.
> **P&R proof:** `test/litex_smoke.py` (LiteX: LiteDRAM ECP5DDRPHY + MT41K256M16, LiteEth RGMII + Etherbone, UART bridge) and `test/make_io_smoke.py` (all 125 non-DDR I/O) both route with **0 errors on LFE5UM5G-45F and -85F** (nextpnr `--um5g-45k/85k --package CABGA381 --speed 8`). Ethernet RX 125 MHz meets timing (184 / 156 MHz). The smoke SoC's sys clock is unconstrained (gateware task, not a board risk).
> **Open-flow support found:** SERDES ✅ LiteICLink `serdes_ecp5` · RGMII ✅ LiteEth `ecp5rgmii` · DDR3 ✅ LiteDRAM `ECP5DDRPHY` · **PCIe ⚠ LitePCIe has no ECP5 PHY** (Xilinx/Cyclone V only); open ECP5 PCIe exists only as experimental Gen1 x1 work (Yumewatari PHY, ECP5-PCIe GSoC); Lattice's endpoint IP is proprietary (Diamond). Decision pending with the user.


**Project:** LATFUN6, the open ECP5 textbook board for the Open FPGA Tutorial
**Board:** latfun6 rev v0.1
**Date started:** 2026-11-20
**Status:** **S3 in progress**: EasyEDA project `hardware/EDA/Latfun6.eprj` (fresh blank project, 2026-11-20; gitignored). U5 placed on page p1.
**Design spec:** `docs/definition.md`
**Pinout source of truth:** `board/latfun6.json` (generated + validated by `tools/gen_board.py` against the Lattice CSV; P&R-proven by `test/run_smoke.sh` on 25k and 45k)
**Reference designs (Gate A2 inputs):**
- ECP5: FPGA-DS-02012 v3.4 (data sheet), FPGA-TN-02038 v2.1 (hardware checklist), FPGA-TN-02039 v2.6 (sysCONFIG), ECP5U-25 pinout CSV (FPGA-SC-02033 r2.0)
- FT2232H: FTDI DS_FT2232H, AN_124 (MPSSE), FT2232H Mini-Module schematic
- TLV62569 (TI datasheet, typical application) · AP2112K (Diodes datasheet) · W25Q128JV (Winbond) · AT24C02C (Microchip) · PCA9306 (TI, HDMI DDC application) · TPS2051C (TI) · TPD4E05U06 (TI) · USBLC6-2 (ST)

Status flags used below: ✔ verified C-number + stock (JLCPCB API, 2026-11-20) · ⚠ to decide · ✱ A2 must confirm the value

---

## Section 1 — Block Layout

| Group | Name | Components |
|---|---|---|
| A | USB-C power entry | J1, F1, D1, U1, R1–R2, C1–C3 |
| B | Regulators + rail sensing | U2 (3V3 buck), U3 (1V1 buck), U4 (2V5 LDO), L1–L2, C10–C21, R10–R16, RS1–RS3, FB1, D2, TP rails |
| C | ECP5 FPGA + config + clock | U5, X1, FB2–FB3, C30–C58, R30–R42, Q1, D3, SW1 (PROGRAMN), TP_DONE/INITN |
| D | Config flash | U6, C60, R60–R62 |
| E | USB JTAG/UART (FT2232H) + ext JTAG | U7, U8, Y1, FB4, C70–C84, R70–R82, J2 |
| F | User I/O: LEDs, buttons, DIP, I²C EEPROM | D10–D17, R100–R107, SW2–SW5, SW6 (DIP), R110–R117, U9, R120–R121, C90 |
| G | HDMI out | J3, U10–U11 (ESD), U12 (PCA9306), U13 (TPS2051C), R130–R136, C130–C132 |
| H | Audio out | J4, R140–R143, C140–C145 |
| I | Expansion + verification headers | J5–J8 (PMOD1–4), J9 (LA), J10 (loopback), TP_* signal test points |

**Single page (p1)**: blocks occupy canvas regions; the A3 frame is cosmetic (enlarge to A1 later if wanted). Title-block corner (x > 2700, y < 300) kept clear. Creation coordinates (y up):

| Region | Blocks | x range | y range |
|---|---|---|---|
| R1 | U5 (9 sub-parts) | 100–1450 | 140–1030 |
| R2 | C support: decoupling, config/JTAG resistors, X1, DONE LED, SW1 | 100–1450 | 1150–1550 |
| R3 | A + B: USB-C entry, regulators, shunts | 100–1450 | 1650–2250 |
| R4 | D flash + E FT2232H, J2 | 1600–2550 | 1150–2250 |
| R5 | F user I/O + EEPROM, H audio | 1600–2550 | 140–1030 |
| R6 | G HDMI, I PMOD/LA/loopback/TPs | 2650–3250 | 400–2250 |

### Signal flow

```
USB-C J1 ─VBUS─ F1 ─┬─ D1 TVS ── 5V_SYS ──┬─ U2 buck ─ RS1 ─ 3V3 ──┬─ U4 LDO ─ RS3 ─ 2V5 (VCCAUX via FB2)
                    │                     │                        └─ U3.EN (VCCIO before VCC)
                    │                     ├─ U3 buck ─ RS2 ─ 1V1 (VCC via FB3)
                    │                     └─ U13 switch ─ 5V_HDMI ─ J3.18
          D+/D- ─ U1 ESD ─ U7 FT2232H ─ ch A (ADBUS0-3) ─ R 33Ω ─ JTAG ─ U5 TCK/TDI/TDO/TMS ─ J2 ext
                                      └ ch B (BDBUS0-3) ─ R 33Ω ─ UART ─ U5 bank 1
U5 bank 8 ─ CCLK(R33Ω)/MOSI/MISO/CSSPIN/IO2/IO3 ─ U6 W25Q128
U5 bank 0 ─ TMDS×4 (LVCMOS33D) ─ U10/U11 ESD ─ J3 ; DDC ─ U12 ─ J3 ; HPD ← divider ← J3.19
U5 bank 0 ─ audio_l/r ─ RC-RC ─ C ─ J4 ; I²C ─ U9 24C02
U5 bank 1 ─ LEDs / buttons / DIP / UART / LA J9 / loopback J10 / tp_pll
U5 bank 7/6/2/3 ─ PMOD1/2/3/4 (J5–J8), A/B diff pairs, pin k ↔ pin k+6
```

### Power distribution

```
5V_SYS  → U2.VIN, U3.VIN, U13.IN, (FT2232H none), TP_5V
3V3     → VCCIO0/1/2/3/6/7/8 (13 balls), U7 VREGIN/VCCIO/VPHY/VPLL, U6, U8, U9, U12.VREF1, X1, LEDs, pull-ups, PMOD pin 6/12, LA, U4.IN
1V1     → U5 VCC (6 balls), direct (no bead)
2V5     → U5 VCCAUX (2 balls) via FB2
5V_HDMI → J3.18, U12 side-2 pull-ups, HPD divider
1V8_FT  → U7 VCORE (from U7 VREGOUT, internal)
```

**Sequencing (TN-02038 §4):** VCCIO (3V3) before or with VCC/VCCAUX. U3 EN is driven by 3V3 (R/C delay); U4 is fed from 3V3. Both therefore follow 3V3 ✔.

---

## Section 2 — Master Component Table

### Block A — USB-C power entry

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| R1 | 5.1 kΩ 1 % | 0402 | C25905 ✔ BASIC | CC1 sink Rd | CC1 | GND |
| R2 | 5.1 kΩ 1 % | 0402 | C25905 ✔ | CC2 sink Rd | CC2 | GND |
| F1 | PTC 1.1 A hold, 8 V | 1206 | C126818 ✔ EXT | VBUS overcurrent | VBUS | 5V_SYS |
| D1 | SMF5.0A TVS (Ir 400 µA @ 5 V, accepted) | SOD-123FL | C193402 ✔ EXT | VBUS clamp | 5V_SYS (C, pin 1) | GND (A, pin 2) |
| C1 | 22 µF 25 V | 0805 | C45783 ✔ BASIC | 5V bulk | 5V_SYS | GND |
| C2 | 100 nF | 0402 | C1525 ✔ BASIC | 5V HF | 5V_SYS | GND |
| ~~C3~~ | **removed**: 6.3 V rating on a 5 V rail (TN-02038 §3.5.2 wants ≥ 80 % headroom) and USB VBUS inrush guideline (≤ 10 µF at attach). Bucks have their own 10 µF CIN | — | — | — | — | — |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U1 | USBLC6-2SC6 | SOT-23-6 | C2687116 ✔ EXT | USB D+/D- ESD |
| J1 | TYPE-C-31-M-12 (16P, USB2) | SMD | C165948 ✔ EXT | Power + USB2 |

✅ **Reverse current (decided 2026-11-20):** no on-board path back-feeds VBUS. HDMI pin 18 is driven through U13 (reverse-blocking) and the PMOD 3V3 pins are outputs. ⇒ PTC + TVS only; R3 placeholder deleted.

### Block B — Regulators and rail sensing

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| L1 | 2.2 µH 3.4 A | 4020 | C135262 ✔ EXT | U2 inductor | SW_3V3 | 3V3_PRE |
| L2 | 2.2 µH 3.4 A | 4020 | C135262 ✔ | U3 inductor | SW_1V1 | 1V1_PRE |
| C10, C11 | 10 µF 10 V | 0603 | C19702 ✔ BASIC | U2/U3 input | 5V_SYS | GND |
| C12, C13 | 22 µF 25 V | 0805 | C45783 ✔ | U2 output | 3V3_PRE | GND |
| C14, C15 | 22 µF 25 V | 0805 | C45783 ✔ | U3 output | 1V1_PRE | GND |
| R10 | 680 kΩ 1 % ✱ | 0402 | C4131 ✔ EXT | U2 FB top, **sensed after RS1** (shunt drop regulated out) | 3V3 | FB_3V3 |
| R11 | 150 kΩ 1 % ✱ | 0402 | C25755 ✔ EXT | U2 FB bottom (→ 3.32 V nominal) | FB_3V3 | GND |
| R12 | 100 kΩ 1 % ✱ | 0402 | C25741 ✔ BASIC | U3 FB top, **sensed after RS2** (50 mV at 1 A otherwise) | 1V1 | FB_1V1 |
| R13 | 120 kΩ 1 % ✱ | 0402 | C25750 ✔ EXT | U3 FB bottom (→ 1.100 V nominal; 1 % worst case 1.090–1.110 V) | FB_1V1 | GND |
| R14 | 100 kΩ | 0402 | C25741 ✔ | U3 EN from 3V3 (sequencing) | 3V3 | EN_1V1 |
| C16 | 100 nF | 0402 | C1525 ✔ | U3 EN delay | EN_1V1 | GND |
| C17 | 1 µF 25 V | 0402 | C52923 ✔ BASIC | U4 input | 3V3 | GND |
| C18 | 1 µF 25 V | 0402 | C52923 ✔ | U4 output | 2V5_PRE | GND |
| RS1 | 50 mΩ 1 % | 0805 | C247602 ✔ EXT | 3V3 shunt (Lab 17.3) | 3V3_PRE | 3V3 |
| RS2 | **100 mΩ 1 % alloy, 250 mW** (RL10FTNR100) | 0805 | C160917 ✔ EXT | 1V1 shunt: 7.7 mV at the 77 mA static ICC (DS-02012 T3.8); drop is regulated out (FB after shunt) | 1V1_PRE | 1V1 |
| RS3 | **1 Ω 1 %** | 0603 | C22936 ✔ BASIC | 2V5 shunt: 16 mV at the 16 mA static ICCAUX; ≤ 2 % drop at 50 mA, within VCCAUX ±5 % with the LDO's ±1.5 % | 2V5_PRE | 2V5 |
| D2 | LED red KT-0603R (**pin 1 = A, pin 2 = K**) | 0603 | C2286 ✔ BASIC | Power LED | PWR_LED (A, pin 1) | GND (K, pin 2) |
| R15 | 1 kΩ | 0402 | C11702 ✔ BASIC | Power LED | 3V3 | PWR_LED |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U2 | TLV62569DBVR (2 A buck, VFB 0.6 V ✱) | SOT-23-5 | C141836 ✔ EXT (500k stock) | 5V → 3V3 |
| U3 | TLV62569DBVR | SOT-23-5 | C141836 ✔ | 5V → 1V1 |
| U4 | AP2112K-2.5TRG1 (600 mA LDO) | SOT-23-5 | C176945 ✔ EXT | 3V3 → 2V5 |

Test points: TP_5V, TP_3V3, TP_1V1, TP_2V5, plus Kelvin pairs across each shunt: TP_3V3_SH+/−, TP_1V1_SH+/−, TP_2V5_SH+/− (keystone 5015 C5199798 ✔ EXT, or bare pads ⚠).

### Block C — ECP5 FPGA, configuration, clock

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| FB2 | BLM18PG221SN1D 220 Ω @ 100 MHz, 1.4 A, 0.1 Ω | 0603 | C80165 ✔ EXT | VCCAUX filter (TN-02038 Fig 3.1 shows a bead on VCCAUX only) | 2V5 | VCCAUX |
| ~~FB3~~ | **removed**: TN-02038 Fig 3.1 has no bead on VCC; C1002 is rated 200 mA and a 1.3 A bead drops 150 mV at 1 A. VCC balls connect to 1V1 directly | — | — | — | — | — |
| C30–C35 | 100 nF | 0402 | C1525 ✔ | VCC balls G6 G7 G9 L8 L9 L10 | 1V1 | GND |
| C36, C37 | 10 µF | 0603 | C19702 ✔ | VCC bulk | 1V1 | GND |
| C38, C39 | 100 nF | 0402 | C1525 ✔ | VCCAUX balls G11, L7 | VCCAUX | GND |
| C40 | 10 µF | 0603 | C19702 ✔ | VCCAUX bulk | VCCAUX | GND |
| C41–C53 | 100 nF | 0402 | C1525 ✔ | VCCIO balls F6 F7 F10 F11 H11 J11 K11 L11 J6 J7 H6 H7 L6 | 3V3 | GND |
| C54–C57 | 10 µF | 0603 | C19702 ✔ | VCCIO bulk, one per die side | 3V3 | GND |
| C58 | 100 nF | 0402 | C1525 ✔ | X1 supply | 3V3_OSC | GND |
| FB5 | 600 Ω | 0603 | C1002 ✔ | X1 supply filter (TN-02038 §3.4) | 3V3 | 3V3_OSC |
| R30 | 4.7 kΩ | 0402 | C25900 ✔ BASIC | PROGRAMN pull-up | PROGRAMN | 3V3 |
| R31 | 4.7 kΩ | 0402 | C25900 ✔ | INITN pull-up | INITN | 3V3 |
| R32 | 4.7 kΩ | 0402 | C25900 ✔ | DONE pull-up | DONE | 3V3 |
| R33 | 1 kΩ | 0402 | C11702 ✔ | CCLK pull-up (TN-02038 T6.2) | CCLK | 3V3 |
| R34 | 33 Ω ✱ (22–80 Ω) | 0402 | C25105 ✔ BASIC | CCLK series at FPGA (TX side) | CCLK | FLASH_CLK |
| R35 | 4.7 kΩ | 0402 | C25900 ✔ | CFG1 pull-up (CFG=010 MSPI) | CFG1 | 3V3 |
| — | direct | — | — | CFG0 = GND, CFG2 = GND | CFG0/CFG2 | GND |
| R36 | 4.7 kΩ | 0402 | C25900 ✔ | TDI pull-up | JTAG_TDI | 3V3 |
| R37 | 4.7 kΩ | 0402 | C25900 ✔ | TMS pull-up | JTAG_TMS | 3V3 |
| R38 | 4.7 kΩ | 0402 | C25900 ✔ | TDO pull-up | JTAG_TDO | 3V3 |
| R39 | 4.7 kΩ | 0402 | C25900 ✔ | **TCK pull-down** | JTAG_TCK | GND |
| R40 | 10 kΩ | 0402 | C25744 ✔ BASIC | Q1 gate pull-down | DONE_LED_G | GND |
| R41 | 1 kΩ | 0402 | C11702 ✔ | DONE LED current | 3V3 | DONE_LED_A |
| R42 | 0 Ω | 0402 | C17168 ✔ BASIC | DONE → Q1 gate | DONE | DONE_LED_G |
| D3 | LED yellow-green KT-0603YG (Vf 2.0–2.2 V) | 0603 | C2289 ✔ EXT | DONE LED (A=DONE_LED_A) | DONE_LED_A (A) | DONE_LED_K (K) |
| C59 | 100 nF ✱ (optional) | 0402 | C1525 | PROGRAMN button debounce | PROGRAMN | GND |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U5 | **LFE5U-25F-7BG256I** | CABGA256 | **C1550762 ✔ EXT (1093)**, see FPGA_Availability_Note.md | FPGA |
| X1 | 25 MHz oscillator 3.3 V CMOS (YSO690PR) | 3225 | C496680 ✔ EXT (1729), alt C160454 | clk_25mhz → A7 |
| Q1 | BSS138 | SOT-23 | C40912 ✔ EXT | DONE LED driver (D=DONE_LED_K, S=GND) |
| SW1 | TS-1187A-B-A-B | SMD 5.1 mm | C318884 ✔ BASIC | PROGRAMN (reload from flash) |

⚠ **E7 caught (library descriptions, S3):** C1002 bead is 200 mA (kept only for X1 / FT2232H PLL filters FB4, FB5). C12624 green LED has Vf 3.1 V (≈0.2 mA at 3.3 V/1 kΩ) → replaced by C2289. C9006 (first candidate for X1) is a **passive crystal** (YSX321SL 12 pF), not an oscillator. Rejected.

**U5 dedicated/power ball map** (from the Lattice CSV, CABGA256):
VCC G6 G7 G9 L8 L9 L10 · VCCAUX G11 L7 · VCCIO0 F6 F7 · VCCIO1 F10 F11 · VCCIO2 H11 J11 · VCCIO3 K11 L11 · VCCIO6 J6 J7 · VCCIO7 H6 H7 · VCCIO8 L6 · GND (27) A1 A16 D2 D15 F8 F9 G8 G10 H1 H8 H9 H10 H16 J8 J9 J10 K6 K7 K8 K9 K10 N2 N15 T1 T5 T12 T16 · CCLK N9 · CFG0 N10 · CFG1 P10 · CFG2 R10 · DONE P9 · INITN T9 · PROGRAMN R9 · TCK T10 · TDI R11 · TDO M10 · TMS T11.
User I/O: 80 balls per `board/latfun6.lpf`. The remaining 113 I/O are unconnected (left open, per TN-02038 note).

### Block D — Configuration flash

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| C60 | 100 nF | 0402 | C1525 ✔ | U6 VCC | 3V3 | GND |
| R60 | 4.7 kΩ | 0402 | C25900 ✔ | **CSSPIN pull-up, placed at the flash** (TN-02038 T6.2 note 2) | FLASH_CS_N | 3V3 |
| R61 | 10 kΩ | 0402 | C25744 ✔ | IO2/WP# pull-up | FLASH_IO2 | 3V3 |
| R62 | 10 kΩ | 0402 | C25744 ✔ | IO3/HOLD# pull-up | FLASH_IO3 | 3V3 |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U6 | W25Q128JVSIQ (128 Mbit QSPI, 3 V) | SOIC-8 208 mil | C97521 ✔ **BASIC** (67k) | Bitstream + user data (Lab 11.2) |

### Block E — FT2232H USB JTAG + UART, external JTAG

Values per **DS_FT2232H v2.9** Fig 6.1 (bus-powered example), §6.3 (oscillator), §5 (REF, RESET#, VREGIN). Our 3V3 rail plays the role of the figure's LDO output.

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| R70 | 12 kΩ 1 % | 0402 | C25752 ✔ BASIC | REF to GND (DS §5: "12 K between REF and GND") | FT_REF | GND |
| R71 | 10 kΩ | 0402 | C25744 ✔ | RESET# to VCCIO (DS: "tied to VCCIO if not used") | FT_RESET_N | 3V3 |
| R72 | 10 kΩ | 0402 | C25744 ✔ | EECS pull-up (Fig 6.1) | FT_EECS | 3V3 |
| R73 | 10 kΩ | 0402 | C25744 ✔ | EECLK pull-up (Fig 6.1) | FT_EECLK | 3V3 |
| R74 | 2.2 kΩ | 0402 | C25879 ✔ BASIC | EEDATA → EEPROM DO (Fig 6.1); EEPROM DI connects to EEDATA directly | FT_EEDATA | EE_DO |
| R75 | 10 kΩ | 0402 | C25744 ✔ | EEDATA pull-up (Fig 6.1) | FT_EEDATA | 3V3 |
| R76–R79 | 33 Ω | 0402 | C25105 ✔ | JTAG series (design choice, damping + contention limit): AD0→TCK, AD1→TDI, TDO→AD2, AD3→TMS | FT_AD0..3 | JTAG_TCK/TDI/TDO/TMS |
| R80–R81 | 33 Ω | 0402 | C25105 ✔ | UART series: BD1 RXD ← UART_TX, BD0 TXD → UART_RX | FT_BD1 / FT_BD0 | UART_TX / UART_RX |
| R82–R83 | 33 Ω | 0402 | C25105 ✔ | BD2 RTS# → UART_CTS_N, BD3 CTS# ← UART_RTS_N | FT_BD2 / FT_BD3 | UART_CTS_N / UART_RTS_N |
| C70, C71 | 27 pF C0G | 0402 | C1557 ✔ EXT | Y1 load caps (DS §6.3: 27 pF; crystal CL 20 pF ⇒ 2·(20−~6) ≈ 28 pF ✔) | FT_OSCI / FT_OSCO | GND |
| C72 | 100 nF | 0402 | C1525 ✔ | VREGIN (pin 50) HF | 3V3 | GND |
| C81 | 4.7 µF | 0603 | C19666 ✔ BASIC | VREGIN bulk (DS §5 "add an external filtering capacitor") | 3V3 | GND |
| C80 | 3.3 µF | 0603 | C51412 ✔ EXT | VREGOUT (pin 49), as Fig 6.1 | 1V8_FT | GND |
| C73–C75 | 100 nF | 0402 | C1525 ✔ | VCORE pins 12, 37, 64 (fed from VREGOUT) | 1V8_FT | GND |
| C76–C79 | 100 nF | 0402 | C1525 ✔ | VCCIO pins 20, 31, 42, 56 | 3V3 | GND |
| FB4 | 600 Ω @ 100 MHz (200 mA OK here) | 0603 | C1002 ✔ BASIC | VPHY/VPLL filter (reference-design practice; DS figure shows caps only) | 3V3 | 3V3_FTA |
| C83, C84 | 4.7 µF / 100 nF | 0603 / 0402 | C19666 / C1525 ✔ | VPHY (pin 4) | 3V3_FTA | GND |
| C85, C86 | 4.7 µF / 100 nF | 0603 / 0402 | C19666 / C1525 ✔ | VPLL (pin 9) | 3V3_FTA | GND |
| C82 | 100 nF | 0402 | C1525 ✔ | U8 VCC | 3V3 | GND |

Direct connections (no part): TEST (13) → GND · AGND (10) and GND pins → GND · DM (7)/DP (8) → USB_DN/USB_DP **direct** (Fig 6.1 has no series R) · PWREN# (60), SUSPEND# (36), unused ADBUS4–7/ACBUS/BDBUS4–7/BCBUS → NC (named `*_NC`).

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| R70 | 12 kΩ 1 % | 0402 | C25752 ✔ BASIC | FT REF | FT_REF | GND |
| R71 | 10 kΩ | 0402 | C25744 ✔ | FT RESET# pull-up | FT_RESET_N | 3V3 |
| R72 | 10 kΩ ✱ | 0402 | C25744 ✔ | EECS pull-down/up per DS | FT_EECS | 3V3 |
| R73 | 10 kΩ ✱ | 0402 | C25744 ✔ | EECLK | FT_EECLK | 3V3 |
| R74 | 2.2 kΩ ✱ | 0402 | C25879 ✔ BASIC | EEDATA ↔ DO series | FT_EEDATA | EE_DO |
| R75 | 10 kΩ ✱ | 0402 | C25744 ✔ | EEDATA pull-up | FT_EEDATA | 3V3 |
| R76–R79 | 33 Ω | 0402 | C25105 ✔ | JTAG series: ADBUS0→TCK, ADBUS1→TDI, TDO→ADBUS2, ADBUS3→TMS | FT_AD0..3 | JTAG_TCK/TDI/TDO/TMS |
| R80–R81 | 33 Ω | 0402 | C25105 ✔ | UART series: BDBUS1 RXD ← UART_TX, BDBUS0 TXD → UART_RX | FT_BD1 / FT_BD0 | UART_TX / UART_RX |
| R82–R83 | 33 Ω | 0402 | C25105 ✔ | BDBUS2 RTS# → UART_CTS_N, BDBUS3 CTS# ← UART_RTS_N | FT_BD2 / FT_BD3 | UART_CTS_N / UART_RTS_N |
| C72–C79 | 100 nF | 0402 | C1525 ✔ | FT VCCIO/VPHY/VPLL/VREGIN/VCORE decoupling | per pin | GND |
| C80–C81 | 4.7 µF ✱ / 3.3 µF | 0603 | — ⚠ | VREGIN/VREGOUT per DS | FT_VREGIN / 1V8_FT | GND |
| C82 | 100 nF | 0402 | C1525 ✔ | U8 VCC | 3V3 | GND |
| FB4 | 600 Ω | 0603 | C1002 ✔ | VPHY/VPLL filter | 3V3 | 3V3_FTA |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U7 | **FT2232HL-TRAY** | LQFP-64 | **C1521564** ✔ EXT (231, $13.50). ⚠ E7: C27882 (REEL) listing describes an "FT2232H Mini Module eval board" while MPN/package say bare IC, so it was rejected; alternate only after confirming with LCSC | USB ↔ JTAG (ch A MPSSE) + UART (ch B) |
| U8 | 93LC56BT-I/OT | SOT-23-6 | C190271 ✔ EXT | FT config EEPROM (board name, VID/PID) |
| Y1 | 12 MHz crystal, 20 pF, ±10 ppm | 3225 | C9002 ✔ BASIC | FT2232H clock |
| J2 | PZ254V-11-06P 1×6 2.54 mm male: **1 TCK · 2 TDI · 3 TDO · 4 TMS · 5 GND · 6 3V3** (matches the in-house FT2232H Mini Module JTAG wiring), **pin by pin vs. silkscreen** | THT | C492405 ✔ EXT (70k) | External JTAG / recovery |

### Block F — User I/O and I²C EEPROM

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| D10–D17 | LED yellow-green KT-0603YG (Vf 2.0–2.2 V, ≈1.2 mA) | 0603 | C2289 ✔ EXT | led[0..7], active high (A = R side) | LEDn_A (A) | GND (K) |
| R100–R107 | 1 kΩ | 0402 | C11702 ✔ | LED current (~1.3 mA) | LED[n] | LEDn_A |
| SW2 | TS-1187A | SMD | C318884 ✔ | btn_n[0] **RESET** | BTN_N0 | GND |
| SW3 | TS-1187A | SMD | C318884 ✔ | btn_n[1] **un-debounced** (Lab 5.2), no RC by design | BTN_N1 | GND |
| SW4, SW5 | TS-1187A | SMD | C318884 ✔ | btn_n[2] (Showcase A fire), btn_n[3] | BTN_N2/3 | GND |
| R110–R113 | 10 kΩ | 0402 | C25744 ✔ | button pull-ups | BTN_N0..3 | 3V3 |
| SW6 | DIP 4P 1.27 mm SMD | SMD | C7430300 ✔ EXT | sw_n[0..3] | SW_N0..3 | GND |
| R114–R117 | 10 kΩ | 0402 | C25744 ✔ | DIP pull-ups | SW_N0..3 | 3V3 |
| R120 | 4.7 kΩ | 0402 | C25900 ✔ | I²C SCL pull-up | I2C_SCL | 3V3 |
| R121 | 4.7 kΩ | 0402 | C25900 ✔ | I²C SDA pull-up | I2C_SDA | 3V3 |
| C90 | 100 nF | 0402 | C1525 ✔ | U9 VCC | 3V3 | GND |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| U9 | AT24C02C-SSHM-T (A2..A0=GND → 0x50, WP=GND) | SOIC-8 | C6203 ✔ EXT (194k) | Lab 11.3 I²C target |

### Block G — HDMI out

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| R130 | 2.2 kΩ ✱ (HDMI: 1.5–2 k to 5 V) | 0402 | C25879 ✔ | DDC SCL 5 V-side pull-up | HDMI_SCL_5V | 5V_HDMI |
| R131 | 2.2 kΩ ✱ | 0402 | C25879 ✔ | DDC SDA 5 V-side pull-up | HDMI_SDA_5V | 5V_HDMI |
| R132 | 4.7 kΩ | 0402 | C25900 ✔ | DDC SCL 3V3-side pull-up | GPDI_SCL | 3V3 |
| R133 | 4.7 kΩ | 0402 | C25900 ✔ | DDC SDA 3V3-side pull-up | GPDI_SDA | 3V3 |
| R134 | 200 kΩ ✱ | 0402 | — | U12 EN pull-up to VREF2 (per PCA9306 DS) | PCA_EN | 5V_HDMI |
| R135 | 10 kΩ | 0402 | C25744 ✔ | HPD divider top | HDMI_HPD | GPDI_HPD |
| R136 | 20 kΩ ✱ | 0402 | — | HPD divider bottom (5.3 V → 3.5 V) | GPDI_HPD | GND |
| C130 | 100 nF | 0402 | C1525 ✔ | U13 input | 5V_SYS | GND |
| C131 | 1 µF | 0402 | C52923 ✔ | 5V_HDMI output | 5V_HDMI | GND |
| C132 | 100 nF | 0402 | C1525 ✔ | U12 VREF | 3V3 | GND |

| Desig | Value | Pkg | LCSC | Function |
|---|---|---|---|---|
| J3 | HDMI-A receptacle 19P | SMD | C720616 ✔ EXT (45k) | TMDS D2± D1± D0± CLK±, DDC, HPD, +5V |
| U10, U11 | TPD4E05U06DQAR | USON-10 | C138714 ✔ EXT | TMDS ESD (flow-through) |
| U12 | PCA9306DCUR | VSSOP-8 | C33196 ✔ EXT | DDC 3.3 ↔ 5 V |
| U13 | TPS2051CDBVR (current-limited, reverse-blocking ✱) | SOT-23-5 | C129581 ✔ EXT | 5 V to monitor (≥ 55 mA) |

TMDS: FPGA pins direct to connector through ESD; no series resistors (as on the ULX3S GPDI) ✱ A2. Diff 100 Ω routing in layout.

### Block H — Audio out

Per channel (L shown, R = +1 designators): `audio_l → R140 1 kΩ → node1 (C140 10 nF to GND) → R141 1 kΩ → node2 (C141 10 nF to GND) → C142 10 µF → J4 tip`. ✱ fc ≈ 16 kHz per pole; A2/Lab 14.1 to confirm with the NCO sample rate.

| Desig | Value | Pkg | LCSC | Function | Pin1 Net | Pin2 Net |
|---|---|---|---|---|---|---|
| R140, R141 | 1 kΩ | 0402 | C11702 ✔ | L RC stages | AUDIO_L / AUD_L1 | AUD_L1 / AUD_L2 |
| C140, C141 | 10 nF | 0402 | C15195 ✔ BASIC | L RC stages | AUD_L1 / AUD_L2 | GND |
| C142 | 10 µF | 0603 | C19702 ✔ | L AC coupling | AUD_L2 | JACK_L |
| R142, R143 | 1 kΩ | 0402 | C11702 ✔ | R RC stages | AUDIO_R / AUD_R1 | AUD_R1 / AUD_R2 |
| C143, C144 | 10 nF | 0402 | C15195 ✔ | R RC stages | AUD_R1 / AUD_R2 | GND |
| C145 | 10 µF | 0603 | C19702 ✔ | R AC coupling | AUD_R2 | JACK_R |

| Desig | Part | LCSC | Function |
|---|---|---|---|
| J4 | PJ-313D 3.5 mm stereo jack (SMD) | C668608 ✔ EXT | tip=L, ring=R, sleeve=GND |

### Block I — Expansion and verification headers

| Desig | Part | LCSC | Function |
|---|---|---|---|
| J5–J8 | 2×6 2.54 mm **female right-angle** (PMOD host) | C5333437 ⚠ EXT (only 322 in stock) / alt male RA C2894986 | PMOD1 (bank 7), PMOD2 (6), PMOD3 (2), PMOD4 (3). Pin 5/11 = GND, 6/12 = 3V3 |
| J9 | 2×5 2.54 mm vertical: la[0..7] + 2×GND | C843271 ⚠ (female listed; want male pins) | Logic-analyser probe header |
| J10 | 1×2 2.54 mm + jumper | ⚠ | loop_a ↔ loop_b (factory self-test) |

Signal test points (bare 1.0 mm pads + adjacent GND pad, or keystone 5015 C5199798): TP_CLK25, TP_RESET (btn_n[0]), TP_UART_TX, TP_UART_RX, TP_SCL, TP_SDA, TP_FLASH_CLK, TP_FLASH_CS, TP_PLL (C8), TP_DONE, TP_INITN.

### Designator rules
Globally unique. Non-LCSC parts: none planned. Connectors with low or wrong-gender stock are flagged ⚠ for the S3 gate.

---

## Section 3 — Inter-Block Net Map

### Signals (FPGA ball in brackets; user I/O from `board/latfun6.json`)

| Net | From | To | Notes |
|---|---|---|---|
| CLK_25MHZ | X1.3 OUT | U5 [A7], TP_CLK25 | PCLKT0_0 |
| JTAG_TCK | U7 ADBUS0 via R76 | U5 [T10], J2.3, R39 (PD) | |
| JTAG_TDI | U7 ADBUS1 via R77 | U5 [R11], J2.5, R36 | |
| JTAG_TDO | U5 [M10] | U7 ADBUS2 via R78, J2.4, R38 | |
| JTAG_TMS | U7 ADBUS3 via R79 | U5 [T11], J2.6, R37 | |
| UART_TX | U5 [B12] | U7 BDBUS1 (RXD) via R80, TP_UART_TX | FPGA → PC |
| UART_RX | U7 BDBUS0 (TXD) via R81 | U5 [C12], TP_UART_RX | PC → FPGA |
| UART_CTS_N | U7 BDBUS2 (RTS#) via R82 | U5 [E12] | |
| UART_RTS_N | U5 [D12] | U7 BDBUS3 (CTS#) via R83 | |
| CCLK / FLASH_CLK | U5 [N9] → R34 | U6.6 CLK, R33 (PU at CCLK), TP_FLASH_CLK | USRMCLK in user mode |
| FLASH_MOSI | U5 [T8] | U6.5 DI/IO0 | |
| FLASH_MISO | U6.2 DO/IO1 | U5 [T7] | |
| FLASH_CS_N | U5 [N8] CSSPIN | U6.1 /CS, R60 (PU at flash), TP_FLASH_CS | |
| FLASH_IO2 | U5 [M7] | U6.3 /WP, R61 | |
| FLASH_IO3 | U5 [N7] | U6.7 /HOLD, R62 | |
| PROGRAMN | U5 [R9] | SW1, R30, C59 | |
| INITN | U5 [T9] | R31, TP_INITN | |
| DONE | U5 [P9] | R32, R42→Q1, TP_DONE | |
| CFG0, CFG2 | U5 [N10], [R10] | GND | CFG=010 |
| CFG1 | U5 [P10] | R35 → 3V3 | |
| LED[0..7] | U5 [B9 C9 D9 E9 A9 A10 B10 C10] | R100–R107 | |
| BTN_N[0..3] | SW2–SW5, R110–R113 | U5 [D10 E10 B11 C11] | BTN_N0 also TP_RESET |
| SW_N[0..3] | SW6, R114–R117 | U5 [D11 E11 A11 A12] | |
| I2C_SCL / I2C_SDA | U5 [E5] / [D5] | U9.6 / U9.5, R120/R121, TPs | 0x50 |
| AUDIO_L / AUDIO_R | U5 [C6] / [B6] | R140 / R142 | |
| JACK_L / JACK_R | C142 / C145 | J4 tip / ring | |
| GPDI_CLK_P/N | U5 [A3]/[A4] | U10, J3.10/J3.12 | LVCMOS33D |
| GPDI_D0_P/N | U5 [C4]/[B4] | U10, J3.7/J3.9 | |
| GPDI_D1_P/N | U5 [C5]/[B5] | U11, J3.4/J3.6 | |
| GPDI_D2_P/N | U5 [A5]/[A6] | U11, J3.1/J3.3 | ✱ verify J3 pin numbers against C720616 drawing |
| GPDI_SCL / GPDI_SDA | U5 [E4] / [D4] | U12 SCL1/SDA1, R132/R133 | |
| HDMI_SCL_5V / HDMI_SDA_5V | U12 SCL2/SDA2 | J3.15 / J3.16, R130/R131 | |
| HDMI_HPD → GPDI_HPD | J3.19 | R135/R136 → U5 [E6] | |
| LA[0..7] | U5 [B13 C13 D13 E13 A13 A14 B14 A15] | J9.1–8 | |
| TP_PLL | U5 [C8] | TP_PLL | |
| LOOP_A / LOOP_B | U5 [E8] / [D8] | J10.1 / J10.2 | |
| PMOD1[1..4,7..10] | U5 bank 7 [B1 C1 D1 G5 / B2 C2 E2 G4] | J5 | pairs (1,7)(2,8)(3,9)(4,10) |
| PMOD2[…] | U5 bank 6 [L1 K4 N1 P1 / L2 K5 P2 R1] | J6 | |
| PMOD3[…] | U5 bank 2 [B16 C16 D16 G12 / B15 C15 E15 G13] | J7 | |
| PMOD4[…] | U5 bank 3 [L16 K13 N16 P16 / L15 K12 P15 R16] | J8 | |
| USB_DP / USB_DN | J1 A6/B6, A7/B7 | U1, U7 DP/DM | |
| CC1 / CC2 | J1 A5 / B5 | R1 / R2 | |

### Power

| Net | Source | Loads |
|---|---|---|
| VBUS → 5V_SYS | J1 VBUS → F1 | D1, C1, C2, U2, U3, U13 (total VBUS capacitance 22 + 2×10 µF ≈ 42 µF nominal, ≈ 20 µF effective at 5 V bias: above the 10 µF USB guideline, accepted and common on dev boards; PTC limits inrush) |
| 3V3_PRE → 3V3 | U2 + L1 → RS1 | see §1 power distribution |
| 1V1_PRE → 1V1 | U3 + L2 → RS2 (FB sensed at 1V1) | U5 VCC ×6 |
| 2V5_PRE → 2V5 → VCCAUX | U4 → RS3 → FB2 | U5 VCCAUX ×2 |
| 5V_HDMI | U13 OUT | J3.18, R130/R131, U12 VREF2 path |
| 1V8_FT | U7 VREGOUT | U7 VCORE |
| GND | J1 GND/shield | all |

---

## Section 4 — Component Summary (S1 estimate; stock as of 2026-11-20)

| Category | Designators | Qty | LCSC | Stock status |
|---|---|---|---|---|
| FPGA | U5 | 1 | C1550762 | EXTENDED, 1093 (−6C variant ZERO_STOCK, see note) |
| USB bridge | U7 | 1 | C1521564 | EXTENDED, 231 (C27882 rejected, E7) |
| Flash | U6 | 1 | C97521 | BASIC, 67k |
| Bucks | U2, U3 | 2 | C141836 | EXTENDED, 500k |
| LDO | U4 | 1 | C176945 | EXTENDED, 2.7k |
| EEPROMs | U8, U9 | 2 | C190271, C6203 | EXTENDED |
| HDMI parts | J3, U10–U13 | 5 | C720616, C138714, C33196, C129581 | EXTENDED |
| USB-C, ESD, PTC, TVS | J1, U1, F1, D1 | 4 | C165948, C2687116, C126818, C193402 | EXTENDED |
| Oscillator / crystal | X1, Y1 | 2 | C496680, C9002 | EXT 1.7k / BASIC |
| Buttons | SW1–SW5 | 5 | C318884 | BASIC |
| DIP | SW6 | 1 | C7430300 | EXTENDED |
| LEDs | D2, D3, D10–D17 | 10 | C2286, C12624 | BASIC / EXT |
| Audio jack | J4 | 1 | C668608 | EXTENDED |
| PMOD / LA / JTAG / loop headers | J2, J5–J10 | 7 | ⚠ | to resolve at S3 (gender/stock) |
| Passives | R, C, L, FB, RS | ~150 | basic where possible | — |

**Unique EXTENDED parts ≈ 30** → ~$90 per JLCPCB order in setup fees (amortised over the batch). Major BOM cost per board ≈ FPGA $24 + FT2232H $11 + rest ~$8 ≈ **$43 + PCB/assembly**, which is at the $45 target ⚠. Cost levers: CH347-class or FT232H JTAG (needs `openFPGALoader` support check), fewer EXTENDED passives.

---

## Section 5 — Execution Checklist

### S1 Worknote — IN PROGRESS
- [x] Blocks, master table, net map, summary drafted
- [ ] Resolve ⚠ items: header genders/stock (J2, J5–J10), R3/reverse-current, RS3 value, missing C-numbers (R134, R136, C80–C81)
- [ ] Quality checklist below all ✓

### S2 Discovery — N/A (new schematic)

### S3 Place — IN PROGRESS
- [x] U5 LFE5U-25F-7BG256I (C1550762, EasyEDA device `6f94a9b5…`, symbol copy `92047faa…`, footprint CABGA-256 0.8 mm) placed on p1 as **9 sub-parts**, all `U5` / uniqueId `gge5001`:
  .1 bank 7 (200,850) · .2 bank 6 (580,850) · .7 bank 1 (960,850) · .5 bank 2/3 (1340,850) · .8 bank 0 (200,400) · .3 bank 8 + config (600,420) · .4 JTAG (600,180) · .6 bank 3/2 (960,400) · .9 power/GND (1340,420). No overlaps (checked from the saved file).
- [x] **U5 symbol vs. Lattice CSV: 256/256 balls, number and name identical (strict check), 0 missing, 0 extra.** Done offline from the saved .eprj.
- [x] **Region R2 (Block C support) placed, 2026-11-20**, sheet now A0 (user):
  - y=1450: C30–C35 100 nF, C36–C37 10 µF (VCC) · C38–C39 100 nF, C40 10 µF (VCCAUX) · FB2 BLM18PG221 (1130,1450, horizontal)
  - y=1650: C41–C53 100 nF (VCCIO ×13) · C54–C57 10 µF
  - y=1250: R30–R39 (PROGRAMN, INITN, DONE PU · R33 CCLK PU 1k · R34 CCLK series 33 Ω · R35 CFG1 PU · R36–R38 TDI/TMS/TDO PU · R39 TCK PD)
  - y=1850: X1 (250) · FB5 (450) · C58 (570) · SW1 (750) · C59 (870) · R40 (970) · R41 (1050) · R42 (1130) · Q1 (1250) · D3 (1380)
  - Caps/resistors at 90°: **pin 2 = top, pin 1 = bottom**, 40 apart. Convention: decoupling top (pin 2) = rail, bottom (pin 1) = GND.
  - Audit from saved file: 58 parts, every designator/uniqueId set, no duplicates.
- **Symbol pin maps (verified from the saved symbols):**
  - X1 O9322525MEDA4SI: 1 OE/NC (tie to 3V3_OSC = always enabled), 2 GND, 3 OUT, 4 VDD
  - SW1 TS-1187A: A–B (pins 1, 2) joined, C–D (pins 3, 4) joined, switch between the pairs → PROGRAMN on 1/2, GND on 3/4. ✱ A2: confirm against the C318884 datasheet drawing
  - Q1 BSS138-7-F: 1 G, 2 S, 3 D · D3 KT-0603YG: 1 K, 2 A
- [x] **Region R4 (part), 2026-11-20:** U7 FT2232HL-TRAY (2300,1750; body ±100 × −190…+200, pins to x 2180/2420, y 1540/1970) · Y1 (1950,1560) · U8 93LC56BT (1880,1800) · U6 W25Q128JVSIQ (2750,2250) · Block D row y=2380: R60 (2650), R61 (2730), R62 (2810), C60 (2890).
  - Symbol pin maps: U6 1 CS#, 2 DO, 3 IO2, 4 GND, 5 DI, 6 CLK, 7 IO3, 8 VCC · U8 1 DO, 2 VSS, 3 DI, 4 CLK, 5 CS, 6 VCC (93LC56**B** = fixed ×16, as the FT2232H needs) · Y1 1 OSC1, 3 OSC2, 2/4 GND · U7: 64 pins named per the standard FT2232HL map (VREGIN 50, VREGOUT 49, VCORE 12/37/64, VCCIO 20/31/42/56, VPHY 4, VPLL 9, REF 6, RESET# 14, TEST 13, EECS/EECLK/EEDATA 63/62/61, ADBUS0–3 16–19, BDBUS0–3 38–41). ✱ A2: confirm against DS_FT2232H.
- [x] **Region R4 complete, 2026-11-20** (values from DS_FT2232H v2.9, supplied by the user):
  - y=2100: FB4 (1760) · C83 4.7 µF, C84 (VPHY) · C85 4.7 µF, C86 (VPLL) · C72, C81 4.7 µF (VREGIN) · C80 3.3 µF (VREGOUT) · C73–C75 (VCORE) — x 1860…2580 step 80
  - y=2220: C76–C79 (VCCIO) x 1860…2100
  - y=1400: R70 12k · R71 RESET# PU · R72 EECS PU · R73 EECLK PU · R75 EEDATA PU · R74 2k2 · C70/C71 27 pF · C82 (U8) — x 1800…2460
  - y=1290: R76–R83 33 Ω — x 1800…2360
  - J2 PZ254V-11-06P (2700,1880)
  - Audit: 99 parts, designators unique, **no overlaps** (bbox check incl. stub margin).
- [x] **Region R3 complete, 2026-11-20** (TLV62569 + AP2112 datasheets checked, see A2):
  - y=2840: J1 USB-C (220,2900; all signal pins on its left edge, shell EH 1–4 on the right) · U1 (480,3000) · F1 (460) · D1 (600) · C1 (680) · C2 (760) · R1 (840) · R2 (920)
  - y=2560: U2 (300) · L1 (480) · C10 (580) · C12 (660) · C13 (740) · R10 (820) · R11 (900) · RS1 (1020, horizontal)
  - y=2320: U3 (300) · L2 (480) · C11 (580) · C14 (660) · C15 (740) · R12 (820) · R13 (900) · RS2 (1020, horizontal) · R14 (1140) · C16 (1220)
  - y=2110: U4 (300) · C17 (480) · C18 (560) · RS3 (680, horizontal) · D2 (840) · R15 (920)
  - C3 placed then deleted (see Block A); R3 never placed (deleted from design)
  - Audit: 131 parts, designators unique, no overlaps.
- **Symbol pin maps R3 (from saved file):** U2/U3 1 EN · 2 GND · 3 SW · 4 VIN · 5 FB (= TI DBV ✅) · U4 1 IN · 2 GND · 3 EN · 4 NC · 5 OUT (= Diodes SOT25 ✅) · U1 USBLC6: 1/6 I/O1, 3/4 I/O2 (flow-through), 2 GND, 5 VBUS · D1 SMF5.0A: **1 C (cathode) → 5V_SYS, 2 A → GND** · J1: A1B12/B1A12 GND, A4B9/B4A9 VBUS, A5 CC1, B5 CC2, A6/B6 DP1/DP2 → USB_DP, A7/B7 DN1/DN2 → USB_DN, A8/B8 SBU NC, EH 1–4 shell → GND
- ⚠ **LED pin numbering differs between libraries (lesson §5 trap):** D2 KT-0603R **1 = A, 2 = K**; D3/D10–D17 KT-0603YG **1 = K, 2 = A**. ⇒ Wire LEDs by function (A/K names), never by pin number; Gate C3 checks the anode net on every LED.

### S4 Wire / S5 Frames — NOT STARTED

### GATE A2 — IN PROGRESS: U5 symbol ✅ (256/256); U7 design ✅ (below); pending U2/U3, U4, U6, U9, U12, U13, U10/U11, U1, U8

#### A2 — U2/U3 (TLV62569DBV) — PASS (design values)
- **Datasheet:** TI TLV62569 (SLVSD58-family PDF, local copy), §7 VFB, §8.2.2, Table 4
- Pinout DBV: 1 EN · 2 GND · 3 SW · 4 VIN · 5 FB (confirm against the EasyEDA symbol at placement)
- VFB 0.588/0.600/0.612 V (±2 %) · VOUT = VFB·(1 + R1/R2) · R2 ≤ 200 kΩ ✅ (150 k / 120 k)
- 3V3: R10 680 k / R11 150 k ⇒ 3.320 V nominal; worst case (±2 % ref, 1 % R) 3.21–3.43 V ✅ (FT2232H 2.97–3.63 V, VCCIO ±5 %: 3.135–3.465 V ✅)
- 1V1: R12 100 k / R13 120 k ⇒ 1.100 V nominal; worst case 1.067–1.133 V ✅ inside ECP5 VCC 1.045–1.155 V (±5 %); ⚠ uses about 3 % of budget for the source, which is Lattice's TN-02038 §2.2 guideline: noise margin is then ~2 %. Accepted; measurable at TP_1V1
- LC per Table 4: 1V1 2.2 µH + 2×22 µF (standard ++ cell) ✅ · 3V3 2.2 µH + 2×22 µF ("+" proven cell) ✅ · CIN ≥ 4.7 µF (10 µF) ✅ · inductor Isat 3.4 A ≥ 1.3 × IL,max ✅
- EN must not float: U2 EN → 5V_SYS; U3 EN → R14/C16 from 3V3 (sequencing, VIH ≤ 1.2 V) ✅
- Feedback sensed after the shunts (R10 top on 3V3, R12 top on 1V1) ✅. Feed-forward cap (6.8 pF for R2 = 100 k) optional, not fitted

#### A2 — U4 (AP2112K-2.5) — PASS
- **Datasheet:** Diodes AP2112 (June 2017), SOT25: 1 VIN · 2 GND · 3 EN · 4 NC · 5 VOUT; typical app 1 µF in/out ✅ (C17/C18); EN → VIN ✅; 0.8 V headroom vs 250 mV dropout ✅; VOUT ±1.5 %

#### A2 — U7 (FT2232HL) — PASS (design values; re-run on the live netlist after S4)
- **Datasheet:** DS_FT2232H v2.9 (local copy `hardware/datasheets/`, not redistributed), Fig 6.1, §5, §6.3, §7
- **Reference practice:** FT2232H Mini Module style VPHY/VPLL filtering; known FT2232H capture pitfalls (floating RESET#, missing EEPROM pull-ups, unfiltered VPHY/VPLL)

| Pin | Name | Reference (DS v2.9) | Project | Verdict |
|---|---|---|---|---|
| 50 | VREGIN | +3.3 V + filter cap | 3V3, C72 100 nF + C81 4.7 µF | ✅ |
| 49 | VREGOUT | 3.3 µF, routed to VCORE | 1V8_FT, C80 3.3 µF | ✅ |
| 12/37/64 | VCORE | 1.8 V from VREGOUT, 100 nF each | 1V8_FT, C73–C75 | ✅ |
| 20/31/42/56 | VCCIO | 3.3 V, 100 nF each | 3V3, C76–C79 | ✅ |
| 4 | VPHY | 3.3 V, 4.7 µF + 100 nF | 3V3_FTA (via FB4), C83/C84 | ✅ (bead added) |
| 9 | VPLL | 3.3 V, 4.7 µF + 100 nF | 3V3_FTA (via FB4), C85/C86 | ✅ (bead added) |
| 6 | REF | 12 kΩ to GND | R70 12 k 1 % | ✅ |
| 14 | RESET# | tie to VCCIO if unused | R71 10 k to 3V3 | ✅ |
| 13 | TEST | GND | GND | ✅ |
| 2/3 | OSCI/OSCO | 12 MHz crystal, 27 pF each | Y1 C9002 (CL 20 pF), C70/C71 27 pF | ✅ |
| 61/62/63 | EEDATA/EECLK/EECS | 93Cx6 ×16; 10 k PU ×3; EEDATA→2k2→DO, EEDATA→DI | U8 93LC56B (×16); R72/R73/R75 10 k; R74 2k2 | ✅ |
| 7/8 | DM/DP | direct to USB | direct to J1 via U1 ESD | ✅ |
| 10, GND | AGND/GND | GND | GND | ✅ |
| 16–19 | ADBUS0–3 | MPSSE TCK/TDI/TDO/TMS | JTAG via R76–R79 33 Ω | ✅ |
| 38–41 | BDBUS0–3 | UART TXD/RXD/RTS#/CTS# | UART via R80–R83 33 Ω | ✅ |
| 36/60 | SUSPEND#/PWREN# | outputs, optional | NC | ✅ |

**In-house FT2232H lessons applied (from earlier boards; nothing copied):**
1. **Crystal pin swap (YSX321SL / C9002):** working pins are the **diagonal 1 + 3**; 2 and 4 are internal GND leads. Wiring OSCO to pin 2 shorts it to GND and kills oscillation, and it is invisible to DRC. ⇒ **Y1.1 → FT_OSCI, Y1.3 → FT_OSCO, Y1.2 + Y1.4 → GND.** Added to Gate C3 as a mandatory netlist check.
2. **EEPROM DI/DO:** DI and DO both tied straight to EEDATA is a known defect. ⇒ DI direct, DO via R74 2.2 kΩ (DS Fig 6.1).
3. Load caps: an earlier board used 18 pF; DS v2.9 §6.3 shows 27 pF and CL = 20 pF supports ~28 pF ⇒ **27 pF**.
4. USB DP/DM: an earlier board used 27 Ω series; DS v2.9 Fig 6.1 shows none ⇒ **direct**.

### GATE C3 — top-3 risk: U5 (config pull-ups), U7 (EEPROM/REF/regulator), U2/U3 (FB dividers)
- Mandatory extra checks: every LED anode on its drive/resistor net and cathode on GND/Q1 (by A/K name) · D1 cathode on 5V_SYS · **Y1.1 = FT_OSCI, Y1.3 = FT_OSCO, Y1.2/Y1.4 = GND** · U8 DI on FT_EEDATA, U8 DO only via R74 · X1.1 OE on 3V3_OSC
### GATE C4 / D — NOT STARTED

---

## Worknote Quality Checklist

- [x] Every component in the design spec appears in exactly one block table
- [~] Every 2-pin passive has Pin1/Pin2 nets (FT2232H decoupling C72–C79 listed per-pin "per pin": expand at A2)
- [x] Every IC's pins covered (U5 via ball map + board.json; others at A2 pin-by-pin)
- [x] Every cross-block net in the Net Map
- [ ] Component Summary total matches block tables (finalise after ⚠)
- [~] LCSC C-numbers verified via JLCPCB API (✔ marks); missing: R134, R136, C80, C81, J2/J5–J10 final
- [x] Non-LCSC parts: none
- [x] Power nets traced source → loads
- [x] Reference designs identified for every IC ≥ 8 pins
