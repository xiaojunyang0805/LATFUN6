# LATFUN6: an open ECP5 textbook board

An open-hardware **Lattice ECP5** board defined by the curriculum of the free, bilingual
[Open FPGA Tutorial](https://xiaojunyang0805.github.io/Free_FPGA_Tutorial/). Every on-board feature maps to a
course lab, and verification is built in: test points, rail current shunts, a logic-analyser header, loopbacks,
and a factory self-test.

> Status: **v0.1, definition + schematic worknote (pre-capture).** Nothing has been fabricated yet. Codename only;
> the public name is to be decided.

## At a glance

| | |
|---|---|
| FPGA | LFE5U-25F, CABGA256 (placed: `-7BG256I`), ball-compatible with LFE5U-45F |
| Programming | one USB-C: power + FT2232H JTAG (ch A) + UART (ch B), `openFPGALoader` |
| Clock | 25 MHz oscillator |
| Config | 128 Mbit QSPI flash (W25Q128JV), user-accessible via `USRMCLK` |
| Video / audio | HDMI (DVI) out, 3.5 mm audio (PWM/ΔΣ + RC) |
| UI | 8 LEDs, 4 buttons (one deliberately un-debounced), 4-way DIP, I²C EEPROM |
| Expansion | 4 × PMOD, each on its own bank with differential-capable pairs |
| Verification | labelled test points, 1V1/2V5/3V3 shunts, 8-ch LA header, loopback jumper |
| CAD | EasyEDA Pro (sources + PDF + Gerber/BOM published) |

## Repository layout

```
docs/definition.md                    board definition: requirements -> labs, power tree, bank plan, I/O budget
hardware/latfun6/latfun6_worknote.md  schematic worknote (blocks, parts with LCSC numbers, net map, gates)
hardware/latfun6/board/latfun6.json   machine-readable pinout (single source of truth)
hardware/latfun6/board/latfun6.lpf    generated constraints file
hardware/latfun6/tools/gen_board.py   pinout generator + validator (against Lattice's pinout CSV)
hardware/latfun6/tools/lcsc_stock_check.py  JLCPCB part availability check
hardware/latfun6/test/                pinout smoke test (Yosys + nextpnr-ecp5 on 25k and 45k)
```

### Regenerate and check the pinout

```sh
# download "ECP5U-25 Pinout" (and optionally ECP5U-45) CSVs from latticesemi.com (see gen_board.py)
python hardware/latfun6/tools/gen_board.py ECP5U-25.csv ECP5U-45.csv
sh hardware/latfun6/test/run_smoke.sh      # needs OSS CAD Suite
```

## Licences

- Hardware: **CERN-OHL-S-2.0** ([LICENSES/CERN-OHL-S-2.0.txt](LICENSES/CERN-OHL-S-2.0.txt))
- Documentation: **CC BY-SA 4.0** ([LICENSES/CC-BY-SA-4.0.txt](LICENSES/CC-BY-SA-4.0.txt))
- Code (tools, RTL, tests): **MIT** ([LICENSES/MIT.txt](LICENSES/MIT.txt))

## Acknowledgements

The [ULX3S](https://github.com/emard/ulx3s) (Radiona / FER / EMARD) showed what an open ECP5 board can do for a
community; we learn from it with gratitude. LATFUN6 is an independent design from Lattice's public documentation.
