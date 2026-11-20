# FPGA availability note — LATFUN6 v0.1

**Date:** 2026-11-20 · **Gate:** pcb-schematic S3 (E6/E10), re-check at pcb-fab-prep F2.

## Finding

| Part | LCSC | JLCPCB class | JLCPCB stock | Unit price |
|---|---|---|---|---|
| LFE5U-25F-**6**BG256**C** (spec'd in handoff) | C1521614 | — | **0 (ZERO_STOCK)** | $15.22 |
| LFE5U-25F-**7**BG256**I** | **C1550762** | EXTENDED | **1093** | $23.97 |
| LFE5U-25F-6BG256I | C5272996 | EXTENDED | 22 | $48.40 |
| LFE5U-25F-8BG256C | C1552103 | EXTENDED | 6 | $46.74 |
| LFE5U-12F-6BG256C | C1521852 | EXTENDED | 168 | $19.64 |
| LFE5U-45F-7BG256I | C1550826 | EXTENDED | 1 | $32.44 |

## Decision (proposed): place **LFE5U-25F-7BG256I** (C1550762)

- Same die, same CABGA256 package and ball map as the -6BG256C. Speed grade 7 is *faster*; "I" is industrial temperature range (−40…100 °C Tj). It is a drop-in replacement.
- Toolchain: `nextpnr-ecp5 --25k --package CABGA256 --speed 7`. The pinout smoke test passes at speed 7 (`test/run_smoke.sh`).
- Course impact: the playground's timing reports (speed 6) stay *conservative* versus the board. Mention in the Devkit page.
- Cost impact: +$8.75 per board over the (unavailable) -6C part.

## 45F compatibility (verified)

Lattice pinout CSVs (ECP5U-25 vs ECP5U-45, CABGA256): all 256 balls have identical role, bank, and true/comp polarity. The 45F adds GPLL input dual functions on balls A2, B3, A15, B14, B1, B2, B15, B16, which is harmless. The 45F BG256 currently has almost no JLCPCB stock (1 unit), so 45F remains footprint-only for now.

## Fallbacks

1. Consign -6BG256C parts bought elsewhere (DigiKey/Mouser) to JLCPCB.
2. LFE5U-12F-6BG256C (C1521852, 168 units) for a low-cost variant. Same ball map is **not yet verified**: run `gen_board.py` against the ECP5U-12 CSV (doc 51576) before relying on it.
