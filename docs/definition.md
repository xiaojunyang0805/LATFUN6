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
| R25 | **PCIe x1 edge** on DCU0 CH0 | Gen1/Gen2 endpoint: PC accelerator, DMA labs. **No open ECP5 PCIe endpoint today** (LitePCIe: Xilinx/Cyclone V only); labs use Lattice's endpoint IP or the experimental open Gen1 core (Yumewatari / ECP5-PCIe GSoC). Finishing an open ECP5 PCIe endpoint is a **flagship frontier project** of the course (decision 2026-11-20) | **Gen2 needs a 200 MHz REFCLK** (multiplier ≤ 25×, TN-02206 Tab 6.1): slot 100 MHz HCSL → ×2 clock multiplier (SSC-tracking) → REFCLK_D0, as on Lattice's ECP5-5G Versa; slot clock direct = Gen1 only. TX AC caps 100 nF on card; PERST#, WAKE#, CLKREQ# sideband; **card outline = PCIe low-profile add-in card** | M |
| R26 | **DDR3L x16, 4 Gb (512 MB)**, MT41K256M16 | Linux on LiteX (VexRiscv/NaxRiscv), framebuffers, capture buffers | banks 6+7 at 1.35 V, DQS groups; VREF divider; no VTT island (single point-to-point x16, ODT on both ends) | M |
| R27 | **Gigabit Ethernet RJ45**, RTL8211F RGMII + magjack | LiteEth, Linux networking, remote labs | RGMII at 3.3 V, 125 MHz; MDC/MDIO, PHY reset/int; MAC from EEPROM | M |
| R28 | **microSD** | Linux rootfs, data logging, SD-mode and SPI labs | 4-bit SD + detect, 3.3 V | M |
| R29 | **USB 2.0 ULPI PHY** + second USB-C (device/host) | LiteX USB, Linux gadget/host, USB protocol labs | USB3320-class, 12-pin ULPI at 3.3 V, 60 MHz from PHY; VBUS switch for host mode | M |
| R30 | SERDES reference clock | SFP/SMA lanes | **I²C-programmable low-jitter clock generator** (LVDS, from crystal) → REFCLK_D1: 125 MHz (1.25/2.5 G), 250 MHz (5 G, 20×), 156.25 MHz etc. A fixed 125 MHz osc caps the lanes at 3.125 Gb/s (25× max). Shares the EEPROM I²C bus; no new FPGA pins | M |
| R31 | Dual power entry | standalone on USB-C, or powered from the PCIe slot | 12 V slot → 5 V buck (LMR33630); USB-C 5 V; TPS2121 power mux into 5V_SYS, **12 V path has priority** (USB-C on a PC port for JTAG must not become the supply); no back-feed. **x1 slot budget: 12 V ≤ 0.5 A, 3.3 V ≤ 3 A, ≤ 10 W total** **Budget calculated in [power_budget.md](power_budget.md): typical 5.2 W, worst 11.4 W (45F) / 13.6 W (85F) > 10 W x1 limit ⇒ power-entry decision pending (x4 low-profile edge 25 W vs x1 10 W with slot-3.3 V split + slot envelope).** Regulators re-sized for headroom (core 4 A-class, 3V3 3 A-class) | M |
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
                                          ├─ DCU0 CH0 ── PCIe x1 edge (REFCLK_D0 ← slot 100 MHz ×2 = 200 MHz)
                                          ├─ DCU1 CH0 ── SFP cage          ┐ REFCLK_D1 ← I²C clock gen (125/250 MHz)
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
| 5V_SYS | USB-C #1 VBUS **or** 12 V slot → LMR33630 5 V, through TPS2121 (12 V path priority) | all regulators, HDMI 5 V, USB-C #2 VBUS (host mode, switched) | slot mode ≤ 6 W from 12 V (x1 limit 0.5 A) ⇒ design budget ≈ 5 W; no back-feed |
| 3V3 | buck (existing U2) | VCCIO 0/1/2/3/8, FT2232H, PHY, ULPI PHY, SFP (filtered), SD, flash, PMOD | current up from v0.1: ≈ 1.5 A budget; inductor/rating re-checked |
| 1V2 | buck (existing U3, **FB changed for 1.2 V**) | ECP5-5G VCC core | FB sensed after shunt |
| 1V2_SER | **dedicated low-noise LDO** (TPS7A91-class, from 3V3) | VCCA0/1 (±3 %), VCCHTX ×4 / VCCHRX ×4 via 120 Ω beads | must not share VCC core (DS Tab 3.2 note 2, TN-02038 Tab 16.1); ≈ 150 mA per DCU at 5 G; each pin 10 µF + 100 nF |
| 2V5 | LDO (existing U4 AP2112, or TLV75525) | VCCAUX (F6, F15, P6, P15) via 120 Ω bead; VCCAUXA0/1 via separate 120 Ω beads | REFCLK buffers run from VCCAUX |
| 1V35 | new buck (TLV62569, same as core) | DDR3L VDD/VDDQ, VCCIO 6/7 | VREF = 0.675 V: 2 × 1 kΩ 1 % dividers (VREFDQ, VREFCA, FPGA VREF1_6/7) + 100 nF each; no VTT |
| 1V8 | new small LDO from 3V3 | USB3320 VDD18 (no internal 1.8 V regulator) | must be up before VDDIO |
| PHY internal | RTL8211F(I)-VD internal 0.9 V switcher (2.2 µH) | RTL8211F core only | straps select 3.3 V RGMII (default is 2.5 V) |

Sequencing: VCCIO before or with VCC/VCCAUX (TN-02038 §4), DDR3L per JEDEC (VDD ramps with VDDQ).

## 6. Physical targets

- **PCIe x1 low-profile add-in card** (≤ 68.9 × 167.65 mm), bracket optional; also usable on the bench (USB-C power, rubber feet).
- **6 layers** (SIG/GND/SIG/PWR/GND/SIG): BG381 0.8 mm escape, DDR3 point-to-point, 100 Ω SERDES/PCIe/HDMI pairs, 90 Ω USB, solid references.
- Connectors: PCIe fingers on the bottom edge; bracket edge: SFP, RJ45, HDMI, USB-C #1/#2 (or USB on the opposite edge if the bracket gets crowded); SMA, PMODs, audio, LA header on the top/inner edges.

## 7. Cost (estimate, qty 10)

FPGA ≈ $80 (consigned) · DDR3L ≈ $20 · FT2232H ≈ $13.5 · RTL8211F + magjack ≈ $4 · USB3320 ≈ $2 · SFP cage + SMA ≈ $5 · clock generators ≈ $8 · power ≈ $8 · passives/connectors ≈ $15 ⇒ **BOM ≈ $150**, plus 6-layer PCB + assembly. Target retail well under the ULX3S-85F class ($275) with far more capability.

## 8. Re-baseline impact on the v0.1 schematic

Reused as placed: USB-C entry, FT2232H block, QSPI flash, user I/O (LEDs, buttons, DIP), I²C EEPROM, audio, 3V3 buck, 2V5 LDO, test-point plan.
Changed: U5 (9-part BG256 symbol → BG381 UM5G symbol, more decoupling); U3 feedback 1.1 → 1.2 V; pinout regenerated against the ECP5-5G-45 CSV.
New: SERDES block (refclk osc, AC caps, SFP cage, SMA, PCIe fingers, SERDES rails), DDR3L + 1V35 buck, RGMII PHY + magjack, ULPI PHY + USB-C #2, microSD, 12 V input + power mux.

## 9. Verify-before-capture

1. LiteDRAM ECP5 DDR3 PHY pin rules (DQS groups, CK placement) → choose DDR3 balls with a place-and-route of a LiteX DDR3 SoC, not by hand.
2. ~~LitePCIe on ECP5-5G~~ **Resolved 2026-11-20:** no ECP5 PHY in LitePCIe; experimental open Gen1 x1 only. User kept PCIe x1 (option a) as hardware-ready + frontier lab.
3. ✅ (§10) ECP5-5G SERDES power and REFCLK requirements (TN-02038 SERDES sections, SERDES/PCS usage guide): VCCA/VCCHRX/VCCHTX filtering, refclk standard and termination.
4. ✅ (§10) RTL8211F and USB3320 reference designs (internal regulators, strap pins, clocking).
5. ✅ (§10, secondary sources) PCIe CEM card rules: outline, finger plating/bevel, PRSNT pins, 12 V / 3.3 V budget.
6. ✅ (§10) Power mux / ideal-diode part for USB-C vs 12 V slot.

## 10. Datasheet check results (2026-11-20)

Primary sources: Lattice FPGA-DS-02012 v3.4 [DS], FPGA-TN-02038 v2.1 [CL], FPGA-TN-02206 v1.8 [SG], FPGA-TN-02077 v3.3 [ER], ECP5-5G Versa FPGA-EB-02048 v1.4 [VB]; Realtek RTL8211F(I)-VD Rev 1.0; Microchip USB3320 DS00001792F; SFF-8431 rev 4.1; HanRun HR911130C. PCIe CEM values are from secondary sources (spec not public).

**SERDES ([DS] Tab 3.2/3.10/3.29, [CL] §3, [SG] §8/§17)**
- VCC core 1.2 V (1.14–1.26). LCSC lists "1.045–1.155 V" for this part: that is the non-5G value (E7 note, ignore).
- VCCA0/1 1.2 V **±3 %**, dedicated quiet supply on its own plane; VCCHTX/VCCHRX 1.2 V, bead-filtered; VCCAUXA0/1 2.5 V, bead-filtered. Balls: VCCA0 T6/U6, VCCA1 T15/U15, VCCAUXA0 V10/V11, VCCAUXA1 V17/V18, VCCHTX T7/T10/T11/T14, VCCHRX T8/T9/T12/T13.
- REFCLK 50–320 MHz, internal 100 Ω or Hi-Z, **no internal AC caps**. LVDS: DC-coupled, internal 100 Ω. Refclk = rate / {8,10,16,20,25} ⇒ 5 Gb/s needs 200 or 250 MHz.
- One TxPLL per DCU: both lanes of a DCU must run related rates (full, ÷2, ÷11). DCU1 = SFP + SMA, so they share a rate family.
- PCIe TX AC caps 100 nF 0402 (Versa C86/C87); RX caps are on the host. Unused D0CH1: power VCCHTX/VCCHRX, HDRX to pads (spare), HDTX open. Lattice docs disagree on unused-channel handling; this choice satisfies all of them.
- W10/W11 RESERVED (NC). No external SERDES resistor pins.

**RTL8211F(I)-VD** (40-QFN; -CG is the older 1.0 V-core silicon, same pinout)
- Straps (4.7 kΩ, never direct): PHYAD = 001 (RXD3 up, RXC down, RXCTL down); PLLOFF down; **TXDLY up, RXDLY up** (PHY adds both 2 ns delays, so ecp5rgmii runs with no FPGA delay); **CFG_EXT up, CFG_LDO1:0 = 00 ⇒ 3.3 V RGMII** (power-on default is 2.5 V).
- LED0 active-low, LED1/LED2 active-high (polarity follows the strap). MDIO 1.5 kΩ pull-up. PHYRSTB from the FPGA with a pull-down (≥ 10 ms low, 72 ms before MDIO). 25 MHz crystal, ESR ≤ 50 Ω.
- RSET value is not in the datasheet text: get it from the Realtek reference schematic before capture (third-party value 2.49 kΩ, unverified).
- Magjack **HR911130C**: 1000BASE-T, 1CT:1CT, Bob Smith termination inside. Centre taps (P1) to GND through 100 nF (voltage-mode PHY; confirm against the Realtek reference).

**USB3320C-EZK**
- **External 1.8 V needed** (VDD18 pins 28/30). VDDIO 3.3 V allows ULPI at LVCMOS33. VBAT tied to VDD33 (2.2 µF). RBIAS 8.06 kΩ 1 %.
- 24 MHz crystal, REFSEL = 111; CLKOUT 60 MHz from the PHY to the FPGA (ulpi_clk L19, PCLK).
- RESETB has no internal pull: the FPGA drives it, plus an external pull-down. RVBUS 10 kΩ (device) / 1 kΩ (OTG). ID to VDD33 unless host. DP/DM have internal ±8 kV ESD.
- USB-C #2: 5.1 kΩ Rd per CC for device. Host needs Rp plus a current-limited VBUS switch (CPEN); full dual-role needs a CC controller (TUSB320-class). Decide at A2.

**PCIe x1 card edge**
- B1–B3 12 V; A9/A10/B8 3.3 V; B10 3.3Vaux (optional); A11 PERST#; B11 WAKE#; B12 CLKREQ#; A13/A14 REFCLK±; B14/B15 PETp/n0 (card TX, caps here); A16/A17 PERp/n0 (card RX); **A1 PRSNT1# tied to B17 PRSNT2#**.
- JTAG and SMBus fingers are left open.
- Low profile ≤ 167.65 × 68.90 mm, 1.57 mm board, 1.0 mm finger pitch, hard gold, 45° bevel.

**Power parts:** LMR33630 (12 → 5 V, 3 A), TPS2121 (5 V mux, 4.5 A, 12 V path priority via PR1), TLV62569 ×2 (1V2 core, 1V35 DDR), TPS7A91 (1V2_SER from 3V3, about 0.6 W, needs thermal vias), TLV75525 or AP2112 (2V5), a small 1.8 V LDO.

**SFP** (SFF-8431)
- Host board needs no TD/RD caps (the module has blocking caps); 0402 pads are fitted with 0 Ω for legacy modules.
- VccT and VccR each get 0.1 µF + 22 µF / 4.7 µH / 0.1 µF filters.
- 4.7 kΩ pull-ups to 3V3 on TX_FAULT, LOS, MOD_ABS, SCL, SDA. TX_DISABLE and RS are driven by the FPGA.
- Cage TE 2227302-1 (press-fit).
- **Connector to source:** TE 1367073-1 shows as discontinued or 20-week lead time at RS; alternatives Molex 74441 series.

**SMA:** Molex 73251-1150 edge-launch, 18 GHz, LCSC C841205 (1.6 mm board; 73251-1290 for 0.062").

**Open items for A2:** ×2 PCIe refclk multiplier part (must track slot SSC; candidates to check: Renesas 5P49V6965, TI CDCE6214, Skyworks Si5332); DCU1 clock-generator part; RTL8211F RSET and inductor values from the Realtek reference; SFP connector source; SFP TX_FAULT has no FPGA pin yet (read via pull-up only, or take one spare I/O).
