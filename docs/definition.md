# LATFUN6: Board Definition v0.2 (application board)

> The open ECP5-5G board for the Open FPGA Tutorial: **from verified RTL to real systems**. Linux-class SoCs, multi-gigabit links, networking and video, with the verification-first features kept.
> Status: **v0.2 draft, 2026-11-20.** Replaces v0.1 (25F CABGA256 textbook board, see git history). Source of truth for the schematic re-baseline.
> Positioning: ULX3S answers *"what can I build with an FPGA?"*. LATFUN6 answers *"how do I build and **prove** a real system?"*: DDR3 + Linux, 5 Gb/s SERDES with SFP/SMA/PCIe, Gigabit Ethernet, USB 2.0, HDMI, with test points, shunts, an LA header and a self-test on every interface.

## 1. Decisions

| # | Decision | Choice | Date |
|---|---|---|---|
| D1 | CAD | EasyEDA Pro, single schematic page (A0) | 2026-11-20 |
| D2 | Scope | **Application board**: SERDES, DDR3L, GbE, USB 2.0, microSD, HDMI, audio, UI, 4 PMOD | 2026-11-20 (supersedes v0.1 D2) |
| D3 | FPGA | **LFE5UM5G-45F-8BG381** (C or I), **85F-ready**: same CABGA381 footprint; balls **K16/K17 stay unused** (NC on 45F, I/O on 85F) | 2026-11-20 (supersedes v0.1 D3) |
| D4 | Licence | CERN-OHL-S-2.0 hardware · CC BY-SA 4.0 docs · MIT code | 2026-11-20 |
| D5 | Clock | 25 MHz system oscillator + SERDES reference oscillator(s) | 2026-11-20 |
| D6 | Programming | One USB-C: power + FT2232H JTAG (ch A) + UART (ch B) | 2026-11-20 |
| D7 | Sourcing | JLCPCB assembly; parts JLCPCB lacks (FPGA) are bought elsewhere and consigned | 2026-11-20 |
| D8 | Course | The playground and course move to the same device (`nextpnr-ecp5 --um5g-45k --package CABGA381`) | 2026-11-20 (user upgrades tutorial repo) |

Supply check (2026-11-20): DigiKey LFE5UM5G-45F-8BG381C **44 pcs, $78.21**; -8BG381I **54 pcs, $86.08**; Active. 85F BG381 $138–147, restock 2027. JLCPCB: all UM5G at 0 ⇒ consign.

### Facts verified from the Lattice pinout CSVs (ECP5-5G-45 / -85, CABGA381)
- 381 balls, **203 user I/O** (85F: 205, the two extra being K16/K17).
- **2 DCUs × 2 channels = 4 SERDES lanes** (HDTX/HDRX D0CH0/1, D1CH0/1), **REFCLKP/N_D0 and _D1**, supplies VCCA0/1, VCCAUXA0/1, VCCHRX ×4, VCCHTX ×4.
- I/O per bank: 0: 27 · 1: 33 · 2: 32 · 3: 33 · 6: 33 · 7: 32 · 8: 13 (config shared). DQS groups (DDR) exist only in banks 2, 3, 6, 7.

## 2. Requirements (v0.1 R1–R22 carried over unless changed)

| ID | Feature | Lab / application | Interface notes | Pri |
|---|---|---|---|---|
| R1–R21 | Clock, LEDs, buttons, DIP, UART, JTAG, flash, config, EEPROM, audio, HDMI, PMOD, LA header, test points, shunts, loopback, LEDs, self-test, holes, board.json | as v0.1 | unchanged except: core rail is **1.2 V** (ECP5-5G), EEPROM also stores the **Ethernet MAC** | M |
| R23 | **SFP cage** on SERDES DCU1 CH0 | 1000BASE-X / 2.5GBASE-X Ethernet, fibre/DAC loopback, BER with real optics | TX AC-coupled; SFP control (TX_DISABLE, LOS, MOD_ABS, RS) + module I²C at 3.3 V; 3.3 V supply with SFP filter | M |
| R24 | **2 SMA pairs** (TX±, RX±) on DCU1 CH1 | cable loopback, eye/BER with instruments, board-to-board links | AC-coupled, 100 Ω diff, edge-launch SMA | M |
| R25 | **PCIe x1 edge** on DCU0 CH0 | Gen1/Gen2 endpoint: PC accelerator, DMA labs (LitePCIe) | 100 MHz REFCLK from slot → REFCLK_D0; TX AC caps on card; PERST#, WAKE#, CLKREQ# sideband; **card outline = PCIe low-profile add-in card** | M |
| R26 | **DDR3L x16, 4 Gb (512 MB)**, MT41K256M16 | Linux on LiteX (VexRiscv/NaxRiscv), framebuffers, capture buffers | banks 6+7 at 1.35 V, DQS groups; VREF divider; no VTT island (single point-to-point x16, ODT on both ends) | M |
| R27 | **Gigabit Ethernet RJ45**, RTL8211F RGMII + magjack | LiteEth, Linux networking, remote labs | RGMII at 3.3 V, 125 MHz; MDC/MDIO, PHY reset/int; MAC from EEPROM | M |
| R28 | **microSD** | Linux rootfs, data logging, SD-mode and SPI labs | 4-bit SD + detect, 3.3 V | M |
| R29 | **USB 2.0 ULPI PHY** + second USB-C (device/host) | LiteX USB, Linux gadget/host, USB protocol labs | USB3320-class, 12-pin ULPI at 3.3 V, 60 MHz from PHY; VBUS switch for host mode | M |
| R30 | SERDES reference clock | SFP/SMA lanes | local low-jitter differential oscillator (125 MHz class, LVDS/HCSL) → REFCLK_D1 | M |
| R31 | Dual power entry | standalone on USB-C, or powered from the PCIe slot | 12 V slot → 5 V buck; USB-C 5 V; ideal-diode / power-mux OR into 5V_SYS; no back-feed into USB or slot | M |
| R32 | DCU0 CH1 (4th lane) | spare | AC-cap pads + test points, or second SMA pair (decide at layout) | C |
| X1 | ~~SDRAM~~ | now covered by R26 | | — |
| X2 | ~~SERDES out~~ | now R23–R25 | | — |
| X3 | ESP32 / Wi-Fi | — | out: JTAG-takeover risk; PMOD instead | X |
| X5 | VCCIO selector jumper | — | out: fixed bank voltages | X |

## 3. Block diagram

```
USB-C #1 (5 V, FT2232H) ─┐                       ┌─ DDR3L x16 512 MB (banks 6+7, 1.35 V)
PCIe slot 12 V ─ buck 5V ┼─ power OR ─ 5V_SYS ─┐ │
                          │                     ├─ bucks/LDOs: 3V3 · 1V2 core · 1V35 DDR · 2V5 AUX · 1V2 SERDES (clean)
FT2232H ── JTAG/UART ─────┴──────────── ECP5-5G LFE5UM5G-45F (CABGA381)
                                          ├─ DCU0 CH0 ── PCIe x1 edge (REFCLK from slot)
                                          ├─ DCU1 CH0 ── SFP cage          ┐ REFCLK_D1 ← 125 MHz osc
                                          ├─ DCU1 CH1 ── SMA TX±/RX±       ┘
                                          ├─ RGMII ── RTL8211F ── RJ45 magjack
                                          ├─ ULPI ── USB3320 ── USB-C #2 (device/host)
                                          ├─ SD ── microSD
                                          ├─ TMDS ── HDMI · PWM ── audio jack
                                          ├─ QSPI flash (bank 8) · I²C EEPROM (MAC)
                                          └─ LEDs, buttons, DIP, 4 PMOD, LA header, TPs
```

## 4. I/O budget (203 user I/O)

| Group | Pins | Bank / VCCIO |
|---|---|---|
| DDR3L x16 (DQ16, DQS×2 pairs, DM×2, A0–A14, BA0–2, RAS/CAS/WE/CS/ODT/CKE/RESET, CK pair) | ≈ 49 | 6 + 7 @ 1.35 V (65 available) |
| HDMI (4 TMDS pairs, DDC, HPD) | 11 | 0/1 @ 3.3 V |
| RGMII + MDC/MDIO + reset/int | 16 | 3.3 V |
| ULPI (DATA0–7, CLK, DIR, NXT, STP) + reset | 13 | 3.3 V |
| microSD (CLK, CMD, DAT0–3, detect) | 7 | 3.3 V |
| 4 × PMOD | 32 | 2/3 @ 3.3 V (L/R banks keep differential inputs) |
| LEDs 8 · buttons 4 · DIP 4 | 16 | 3.3 V |
| UART 4 · I²C 2 · audio 2 · clock 1 · loopback 2 · PLL TP 1 | 12 | 3.3 V |
| LA header | 8 | 3.3 V |
| PCIe sideband (PERST#, WAKE#, CLKREQ#) | 3 | 3.3 V |
| SFP control (TX_DIS, LOS, MOD_ABS, RS) + SFP I²C | 6 | 3.3 V |
| Flash QSPI extra (IO2/IO3) | 2 | 8 @ 3.3 V |
| **Total** | **≈ 175** | 3.3 V side ≈ 126 of 138 (banks 0/1/2/3/8), DDR side 49 of 65 |

Margin ≈ 12 I/O on 3.3 V banks; 16 unused 1.35 V balls in banks 6/7. If the pinout run gets tight, the LA header shrinks first (8 → 4).

## 5. Power tree (to size at Gate A2)

| Rail | Source | Loads | Notes |
|---|---|---|---|
| 5V_SYS | USB-C #1 VBUS **or** 12 V slot → 5 V buck, through an ideal-diode / power mux | all regulators, HDMI 5 V, USB-C #2 VBUS (host mode, switched) | PCIe add-in card ≤ 10 W (low-profile); no back-feed |
| 3V3 | buck (existing U2) | VCCIO 0/1/2/3/8, FT2232H, PHY, ULPI PHY, SFP (filtered), SD, flash, PMOD | current up from v0.1: ≈ 1.5 A budget; inductor/rating re-checked |
| 1V2 | buck (existing U3, **FB changed for 1.2 V**) | ECP5-5G VCC core | FB sensed after shunt |
| 1V2_SER | low-noise LDO or bead-filtered from 1V2 per TN-02038 Fig 3.1 | VCCA0/1, VCCHRX, VCCHTX | ≤ 0.25 % noise target for PLLs |
| 2V5 | LDO (existing U4, may need more current) | VCCAUX, VCCAUXA0/1 (filtered) | |
| 1V35 | new buck | DDR3L VDD/VDDQ, VCCIO 6/7 | VREF = 0.675 V divider (0.1 %), no VTT |
| PHY internal | RTL8211F / USB3320 internal regulators | per their datasheets | A2 |

Sequencing: VCCIO before or with VCC/VCCAUX (TN-02038 §4), DDR3L per JEDEC (VDD ramps with VDDQ).

## 6. Physical targets

- **PCIe x1 low-profile add-in card** (≤ 68.9 × 167.65 mm), bracket optional; also usable on the bench (USB-C power, rubber feet).
- **6 layers** (SIG/GND/SIG/PWR/GND/SIG): BG381 0.8 mm escape, DDR3 point-to-point, 100 Ω SERDES/PCIe/HDMI pairs, 90 Ω USB, solid references.
- Connectors: PCIe fingers on the bottom edge; bracket edge: SFP, RJ45, HDMI, USB-C #1/#2 (or USB on the opposite edge if the bracket gets crowded); SMA, PMODs, audio, LA header on the top/inner edges.

## 7. Cost (estimate, qty 10)

FPGA ≈ $80 (consigned) · DDR3L ≈ $20 · FT2232H ≈ $13.5 · RTL8211F + magjack ≈ $4 · USB3320 ≈ $2 · SFP cage + SMA ≈ $5 · oscillators ≈ $3 · power ≈ $8 · passives/connectors ≈ $15 ⇒ **BOM ≈ $150**, plus 6-layer PCB + assembly. Target retail well under the ULX3S-85F class ($275) with far more capability.

## 8. Re-baseline impact on the v0.1 schematic

Reused as placed: USB-C entry, FT2232H block, QSPI flash, user I/O (LEDs, buttons, DIP), I²C EEPROM, audio, 3V3 buck, 2V5 LDO, test-point plan.
Changed: U5 (9-part BG256 symbol → BG381 UM5G symbol, more decoupling); U3 feedback 1.1 → 1.2 V; pinout regenerated against the ECP5-5G-45 CSV.
New: SERDES block (refclk osc, AC caps, SFP cage, SMA, PCIe fingers, SERDES rails), DDR3L + 1V35 buck, RGMII PHY + magjack, ULPI PHY + USB-C #2, microSD, 12 V input + power mux.

## 9. Verify-before-capture

1. LiteDRAM ECP5 DDR3 PHY pin rules (DQS groups, CK placement) → choose DDR3 balls with a place-and-route of a LiteX DDR3 SoC, not by hand.
2. LitePCIe on ECP5-5G: open-flow support status for Gen1/Gen2 endpoint; reference designs.
3. ECP5-5G SERDES power and REFCLK requirements (TN-02038 SERDES sections, SERDES/PCS usage guide): VCCA/VCCHRX/VCCHTX filtering, refclk standard and termination.
4. RTL8211F and USB3320 reference designs (internal regulators, strap pins, clocking).
5. PCIe CEM card rules: outline, finger plating/bevel, PRSNT pins, 12 V / 3.3 V budget.
6. Power mux / ideal-diode part for USB-C vs 12 V slot.
