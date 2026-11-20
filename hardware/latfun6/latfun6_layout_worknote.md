# LATFUN6 Layout Worknote

**Project:** LATFUN6, open ECP5-5G application board
**Board:** LATFUN6 rev v0.2. File `hardware/EDA/Latfun6.eprj`, PCB document `pcb1`.
**Date started:** 2026-11-20
**Status:** W2 placement v2 (with 4 mounting holes) written 2026-11-21; layout research on reference boards in progress
**Schematic worknote:** `latfun6_worknote.md` (gates A2 / C3 / C4 / D PASS, 2026-11-20)
**EasyEDA Pro version:** V2.2.47.7

> Worknote-first: write the plan, then execute. **State is read from the file** (`eprj_check.py`), never from this note.
> **Starting state (file, 2026-11-20):** `pcb1` has 2 copper layers, 0 components, 0 tracks. Rules in the file: clearance 0.152 mm, track 0.152/0.254/2.54 mm, via 0.610/0.305 mm. `eprj_check.py --selftest` PASS.

---

## Decision 2026-11-20: full-height PCIe card (user)

The low-profile outline in definition v0.2 (≤ 68.9 × 167.65 mm) does not fit:
- **Bracket edge:** SFP 16.1 + RJ45 17.7 + HDMI 16.0 + USB-C 2 × 9.9 + 12 V jack ≈ 9 mm, total ≈ 79 mm (≈ 89 mm with gaps), on a 68.9 mm edge.
- **Area:** the courtyards of all 450 parts (footprint pads + body + silk, plus 0.6 mm assembly spacing, measured from the project's own footprints) add up to ≈ 9,400 mm². One side of the low-profile card is 11,550 mm², so it is > 80 % full before routing.

**Chosen:** full-height add-in card, ≈ 111.15 × 167.65 mm (CEM full height × half length; secondary source, ✱ confirm against the finger footprint datum). That is ≈ 18,600 mm² per side, or ≈ 50 % area use. Every bracket connector fits the full-height bracket. `docs/definition.md` §physical updated to match.

## Section 1 — W1: What is PCB-sensitive on this board (FIRST)

| rank | block / nets | what layout changes | the number |
|---:|---|---|---|
| 1 | **SERDES 5 Gb/s**: PCIE_HDTX/RX, SFP_HDTX/HDRX, SMA_HDTX/HDRX, REFCLK_D0/D1 (FPGA side and connector side) | impedance, intra-pair skew, vias, reference continuity, stubs | 100 Ω diff ±10 %; P/N skew ≤ 0.13 mm (5 mil); ≤ 2 vias per lane, each with an adjacent GND return via; no reference-plane split crossings; AC caps (C322/C323, C340–C343) 0402 at the connector end, pads voided on the plane below ✱; SFP and SMA routes kept short (< 60 mm target) |
| 2 | **DDR3L x16** (U5 banks 6/7 ↔ U30), point-to-point, 1 chip | impedance, byte-lane matching, address/command group matching, VREF | 40 Ω SE / 80 Ω diff target (✱ per stackup); DQ/DM to own DQS within ±0.5 mm ✱ (ECP5 DDR3 guide TN-02035 to confirm); ADDR/CMD/CTL to CK within ±2.5 mm ✱; CK and DQS longer than their groups as the guide says ✱; all on one reference (GND); VREF dividers ≤ 5 mm from the balls, VREF track ≥ 0.5 mm from switching nets |
| 3 | **BG381 0.8 mm escape** (U5) and FBGA-96 0.8 mm (U30) | via size, track/space, layer count | dog-bone via 0.45 pad / 0.20 drill, 0.10/0.10 mm track/space inside the ball field (JLC 6-layer capability) ✱; outer two rings escape on Top, inner rings on L3 and Bottom |
| 4 | **Switchers**: U22 LMR33630 (12 → 5 V 3 A), U3 TPS62827 (1V2 4 A), U2 TPS62826 (3V3 3 A), U24/U25 TLV62569 | input loop area, SW node area, FB routing | VIN ceramics ≤ 2 mm from VIN/PGND; SW copper minimal; FB taken at the load side and ≥ 3 mm from SW; solid GND under each, no signal on the layer beneath the SW node |
| 5 | **1V2_SER / VCCAUXA analog supplies** | noise coupling | U26 and FB20 near U5's SERDES corner; 100 nF caps at the balls (bottom, under the BGA); not routed alongside switch nodes |
| 6 | **HDMI TMDS** (≤ 742.5 Mb/s, 720p) | impedance, intra-pair skew | 100 Ω diff; P/N skew ≤ 0.15 mm; ESD U10/U11 inline at the connector, flow-through |
| 7 | **USB 2.0 HS** (J1 → U7 FT2232H, J20 → U32 USB3320) | impedance, intra-pair skew | 90 Ω diff; skew ≤ 0.15 mm; short (< 50 mm) |
| 8 | **Ethernet MDI** (U31 → J19) | impedance, pair symmetry | 100 Ω diff; pairs on one layer, no vias if possible |
| 9 | **RGMII** (U5 ↔ U31, 125 MHz DDR, PHY adds the 2 ns delays) | group matching only | each direction's CLK/CTL/DATA within ±5 mm; < 75 mm total |
| 10 | **ULPI** (U5 ↔ U32, 60 MHz) | length | < 75 mm, CLK not crossing other clocks |
| 11 | **25 MHz clock, QSPI flash (CCLK ≤ 62 MHz)** | short, series resistors at the source | X1 and R34 near U5; FLASH group < 50 mm |
| ⛔ | **LEDs, buttons, DIP, PMOD (unbuffered user I/O), LA header, I²C, UART, audio PWM, SFP/PCIe sideband, microSD (≤ 25 MHz)** | **NOTHING**: slow or user-defined | no impedance control, no length matching; route anywhere |
| ⛔ | **Power-good, enables, LED drivers, test points** | **NOTHING** | default width |

## Section 2 — Outline + stackup (W5)

- Outline ≈ 111.15 × 167.65 mm, full-height card. x4 fingers on the bottom edge, bracket on the short edge. Hard gold and 45° bevel on the fingers. Exact finger datum, key notch and outline offsets come from the J12 edge footprint (below).
- Mounting: bracket screw tab per CEM; 2 × M3 bench feet holes ✱ (positions at placement).
- **Demand count before allocating layers:** ✱ at W4, after parts are placed (BGA ring count and plane-pad escapes).

| Layer | id | Function | Pour (W8) |
|---|---|---|---|
| Top | 1 | signal + parts; SERDES, HDMI, USB, MDI pairs (microstrip over L2) | GND fill |
| Inner1 | 15 | **GND plane** (reference for Top and Inner2) | GND (solid) |
| Inner2 | 16 | signal: DDR3 and BGA inner rings (stripline between GND and PWR) | GND fill |
| Inner3 | 17 | **PWR**: 1V2 / 3V3 / 1V35 split regions under their loads | power regions |
| Inner4 | 18 | **GND plane** (reference for Bottom) | GND (solid) |
| Bottom | 2 | signal + BGA decaps; slow nets | GND fill |

Definition v0.2 stackup (SIG/GND/SIG/PWR/GND/SIG). JLC 6-layer impedance stackup code ✱ (pick at W5 and compute 100 Ω / 90 Ω / 40 Ω widths with JLC's calculator). Thickness 1.57 mm (CEM). ⚠ Change the copper count **before** routing: `set_copper_count` wipes all tracks. It is done first, while the board is empty.

## Section 3 — W3: how ground reaches each pin

- **Chosen: plane delivery (deviation from the skill default, justified).** The SERDES, DDR3 and HDMI rows of §1 need continuous reference planes, so Inner1 and Inner4 are solid GND. Every SMD ground pad gets its own via, **placed with the parts**: BGA ground balls through dog-bone vias, passives with a via at the pad. Count ✱ at W2 (≈ 87 U5 GND balls + ≈ 300 passive GND pads).
- Ground is still kept as a routed net on Top/Bottom where a pad-to-via stub is needed; pours are added after routing; stitching vias last (and a via fence along the SERDES pairs).
- Switchers: solid GND under each loop on Inner1; no Inner2 signal under the SW nodes.

## Section 4 — Placement zones + rules (W2)

Draft, to confirm once J12's finger datum is known. Bracket edge = left (x = 0), fingers = bottom edge.

| Block | Zone | Side | Constraints |
|---|---|---|---|
| Bracket I/O (top → bottom) | x 0–25 | Top | HDMI J3 · USB-C J1 (FT2232H) · USB-C J20 (ULPI) · RJ45 J19 · SFP cage J14 (cage runs 50 mm along x) · 12 V jack J11; each connector's IC directly behind it (U10/U11/U12, U7, U32, U31) |
| B2 FPGA U5 | centre, ≈ x 60–80 | Top; decaps Bottom under the BGA | SERDES corner (W/Y columns) faces the SFP cage, SMA and the PCIe fingers; bank 6/7 side faces U30 |
| B8 DDR3L U30 | next to banks 6/7, ≤ 25 mm from U5 | Top | VREF parts at the balls |
| B7 SERDES | between U5 and the fingers/SFP | Top | CDCE6214 U27/U28 next to the REFCLK balls; PCIe TX caps at the fingers; SMA J15–J18 on the top edge or the rear edge (edge-launch) |
| B1 power | rear end (x ≈ 130–167) and near the 12 V finger pins | Top | LMR33630 loop compact; 1V2 buck ≤ 15 mm from U5's VCC field (or on the bottom under it ✱) |
| B4 FT2232H + flash, B10 ULPI + microSD, B9 PHY | behind their bracket connectors | Top | |
| B5 user I/O, B11 PMOD/LA/TPs | top edge (PMODs right-angle, facing out) and rear | Top | |

**Pass rules, fixed before measuring:**
- ≥ 0.6 mm pad-to-pad between parts (JLC SMT + rework);
- courtyard = pads ∪ body ∪ silk;
- decaps ≤ 3 mm from their pins (BGA decaps on the bottom under the ball field);
- the escape-via zone of U5 and U30 (ball field + 1.5 mm) kept free of other parts on both sides, except decaps placed between the via sites.


### Placement draft v1 (2026-11-20), `tools/layout/placer.py` → `plan_v1.json`, preview `placement_draft_v1.png`

**Starting state (file):**
- J12 footprint attached; 6 copper layers; all 451 parts imported.
- User outline: rectangle 168 × 110 mm, r 5 mm.

**Outline (new):**
- Body 167.65 × 102.75 mm, r 5 mm. The outline is open across the PCIe tab, because J12's footprint draws the tab on the outline layer: 8.4 mm deep, key notch, chamfers.
- Tab tip at 111.15 mm, which equals the CEM full height measured to the finger tip. The 110 mm frame was 7 mm too tall, since the tab is extra.
- J12 key-notch centre 57.15 mm from the bracket end ✱. Secondary source (a project citing CEM Figures 6-7/6-9); confirm against a CEM-based template before fab.

**U5 orientation (rot 270)**, from the ball map:
- SERDES edge faces the bracket and fingers; DDR3 faces up to U30.
- Ethernet/ULPI/PMOD face down; HDMI/SD/user I/O face right.
- One PCIe/SFP crossing is unavoidable in every orientation. It stays inside the ≤ 2 vias per lane budget: PCIe RX lands on the bottom-side A fingers anyway.

**Bracket column, top → bottom:** HDMI J3, USB-C J1 (FT2232H), SFP cage J14 (board edge at the cage footprint's outline mark), RJ45 J19, USB-C J20 (ULPI), 12 V jack J11. Each connector's IC sits directly behind it.

**Top edge:**
- SMA J15–J18, x 34.5–70.5, edge launch, each with its AC cap under the centre pin.
- PROGRAMN SW1, buttons SW2–5, DIP SW6, audio J4, LA header J9/J10.
- microSD J21, card inserted from the top.

**Rear edge:** PMOD J5–J8, facing out.

**Bottom strip:**
- 12 V OR next to the jack and the slot 12 V pins.
- 5 V buck, mux and 3V3/1V8/2V5 regulators at the bottom right.
- 1V2 core buck U3 15 mm from U5; 1V35 U24 beside U30; 1V2_SER U26 on the SERDES side.

**Placement rules:**
- **Corridors kept free of top-side parts:** PCIe (x 57.5–65.8, y 52–101.5) with C322/C323 placed at the B14/B15 fingers; SFP channel U5 → cage; SMA corridor to the top edge.
- **BGA decaps** (62 parts) on the bottom, in the band under the two outer ball rings (they escape on Top, so no vias there) and just outside. Exact positions follow the fan-out (W5b).

**Checks:**
- Pad-to-pad (exact shapes, `padcheck.py`): **0 pairs < 0.6 mm**.
- No non-edge part off the outline.
- PAD_NET identical before and after.

**Written 2026-11-21** (EDA closed): candidate rebuilt from the latest saved file, then `Project.write`.
- Backup `Latfun6.eprj.bak_placement_v1_20261121-000606`; integrity ok, read-back identical.
- All 451 parts at their plan positions.
- Re-check on the project: 0 pad pairs < 0.6 mm; PAD_NET unchanged.

**Open ✱ items:**
1. J13 SFP connector position inside the cage: placed at cage x +8.5 mm, rotated 90°. Must be checked against the TE 2227302-1 / 1888247-1 application drawing; pin-1 side decides TD/RD.
2. Bracket screw holes / keep-outs (CEM full-height bracket) are not reserved yet.
3. Connector overhang at the bracket: USB-C/HDMI 1 mm, RJ45 2 mm, jack 0.5 mm. Confirm in 3D against a bracket.
4. J9 LA header and J10 are vertical male headers at the top-right inner area.

### Placement v2: 4 mounting holes (user request 2026-11-21)

- **Holes:** 4 × M3 board-level PADs, plated, net GND, hole 3.2 mm, pad 6.0 mm. Record template copied from a GUI-made board PAD (field 15 = 1 = plated). Keep-out for parts: 4.3 mm radius, both sides.
- **Positions (mm):** MH1 (19.5, 4.5), MH2 (163.65, 4.0), MH3 (19.5, 98.25), MH4 (163.65, 98.75).
- **Why the left holes are 19.5 mm in from the bracket edge:** the six bracket connectors need ≈ 85 mm of the ≈ 86 mm left between corner holes at x = 4. Moving the holes in also keeps clear of where the bracket screws attach (✱ open item 2).
- **Moves to make room:** PMODs shifted 4 mm down; U10/U11 and U20 moved off the keep-outs.
- **Written:** backup `Latfun6.eprj.bak_placement_v2_holes_20261121-003151`. Re-check on the project: 0 pad pairs < 0.6 mm (holes included).
- **Reference noted (user):** ALINX AX7020 (Zynq, 130 × 90 mm, 8 layers with dedicated power + GND layers, 4 corner holes, all I/O on the edges, DDR3 beside the SoC, regulators in one column along one side).

## Section 5 — Net classes and widths (from §1 only)

| Class | Nets | Track rule | Why (§1 row) |
|---|---|---|---|
| SERDES_100 | PCIE_*, SFP_HD*, SMA_*, REFCLK_D*, SFP_TD/RD*, PCIE_TX/RX*, PCIE_REFCLK*, CK*_PRI* | diff pair, width/gap from stackup ✱ | 1 |
| DDR | DDRAM_* | 40 Ω width ✱; 0.10 mm min inside the ball fields | 2, 3 |
| HDMI_100 / USB_90 / MDI_100 | GPDI_D*/CLK*, USB_DP/DN, USB2_DP/DN, ETH_MDI* | diff pairs ✱ | 6, 7, 8 |
| PWR | 12V_*, 5V_*, 3V3, 1V2, 1V35, 1V8, 1V2_SER, 2V5, VCCAUX*, SW_*, VBUS* | 0.25 / 0.5 / 3.0 mm (min 0.25 allows necking at pads) | 4 |
| default | everything else | 0.10 / 0.15 / 2.54 mm | ⛔ rows |

Rule values are set in the GUI (the MCP cannot create rules).

## Section 6 — Critical nets routed first (W5b) and protected

| Net(s) | Who / tool | Layer(s) | Target | Done |
|---|---|---|---|---|
| U5 + U30 BGA fan-out (dog-bones) | script (`offline_routing.md` §7) | Top / vias | every ball escaped | ☐ |
| DDR3 byte lanes + ADDR/CMD | script, then length-tune (user) | Top + Inner2 | §1 row 2 | ☐ |
| SERDES lanes + REFCLK | user (GUI), diff pairs | Top | §1 row 1 | ☐ |
| Switcher loops | user (GUI) | Top | §1 row 4 | ☐ |

## Section 7 — Routing runs (W6)

| # | date | command | existing | Freerouting | joined / multi-pin | open | violations | applied? |
|---|---|---|---|---|---|---|---|---|

## Section 8 — Pours, keep-outs, thermal vias, widening (W8)

(empty)

## Section 9 — GATE L-DRC (W9)

(empty)

## Section 10 — Hand-off (W10)

(empty)

---

## Open blockers

1. **J12 has no footprint.** The KiCad-imported `Bus_PCI_Express_x4` symbol came in without a footprint, and LCSC has no card-edge-finger part (only slot connectors). Needed: the KiCad footprint `Connector_PCBEdge:BUS_PCIexpress_x4`, imported the same way as the symbol and linked to J12's device. The MCP cannot create or bind footprints. Its finger datum sets the outline.
2. **Hand-off for offline writes:** the project must be closed in EDA whenever a script writes the `.eprj`.
