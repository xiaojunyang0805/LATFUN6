# LATFUN6: an open ECP5 textbook board

An open-hardware **Lattice ECP5-5G** application board defined by the curriculum of the free, bilingual
[Open FPGA Tutorial](https://xiaojunyang0805.github.io/Free_FPGA_Tutorial/). Every on-board feature maps to a
course lab, and verification is built in: test points, rail current shunts, a logic-analyser header, loopbacks,
and a factory self-test.

> Status: **v0.2 application board: schematic done, 8-layer layout routed, EasyEDA DRC clean.** Nothing has been
> fabricated yet. Codename only; the public name is to be decided.

## At a glance

| | |
|---|---|
| FPGA | **ECP5-5G LFE5UM5G-45F**, CABGA381 (85F-ready): 44k LUT, 4 × 5 Gb/s SERDES |
| SERDES | SFP cage · 2 SMA pairs · PCIe x1 edge (low-profile add-in card) |
| Memory | DDR3L x16 512 MB (Linux-class LiteX SoCs) · 128 Mbit QSPI flash · microSD |
| Networking / USB | Gigabit Ethernet RJ45 (RTL8211F) · USB 2.0 ULPI PHY on a second USB-C |
| Programming | one USB-C: power + FT2232H JTAG (ch A) + UART (ch B), `openFPGALoader` |
| Clock | 25 MHz oscillator |
| Video / audio | HDMI (DVI) out, 3.5 mm audio (PWM/ΔΣ + RC) |
| UI | 8 LEDs, 4 buttons (one deliberately un-debounced), 4-way DIP, I²C EEPROM |
| Expansion | 4 × PMOD, each on its own bank with differential-capable pairs |
| Verification | labelled test points, 1V1/2V5/3V3 shunts, 8-ch LA header, loopback jumper |
| CAD | EasyEDA Pro (layout published as colour PDF/PNG; EDA sources and Gerbers kept local for now) |

## Repository layout

```
docs/definition.md                    board definition: requirements -> labs, power tree, bank plan, I/O budget
hardware/latfun6/board/latfun6.json   machine-readable pinout (single source of truth)
hardware/latfun6/board/latfun6.lpf    generated constraints file
hardware/latfun6/board/latfun6_platform.py  generated LiteX platform
hardware/latfun6/tools/gen_board.py   pinout generator + validator (against Lattice's ECP5-5G pinout CSVs)
hardware/latfun6/tools/lcsc_stock_check.py  JLCPCB part availability check
hardware/latfun6/layout/              colour layout pictures: per-layer PNGs, Top/Bottom composites, PDF
hardware/latfun6/tools/layout/        offline layout tools (routing, pair tuning, checks, renders) on the EDA file
hardware/latfun6/test/                P&R proofs: LiteX DDR3+Ethernet SoC, all-I/O smoke (UM5G-45F and -85F)
```

### Regenerate and check the pinout

```sh
# download the "ECP5-5G-45" and "ECP5-5G-85" pinout CSVs from latticesemi.com (see gen_board.py)
python hardware/latfun6/tools/gen_board.py ECP5-5G-45.csv ECP5-5G-85.csv
python hardware/latfun6/test/make_io_smoke.py   # all non-DDR I/O, needs OSS CAD Suite
python hardware/latfun6/test/litex_smoke.py     # DDR3 + Ethernet SoC, needs LiteX
```

## Licences

- Hardware: **CERN-OHL-S-2.0** ([LICENSES/CERN-OHL-S-2.0.txt](LICENSES/CERN-OHL-S-2.0.txt))
- Documentation: **CC BY-SA 4.0** ([LICENSES/CC-BY-SA-4.0.txt](LICENSES/CC-BY-SA-4.0.txt))
- Code (tools, RTL, tests): **MIT** ([LICENSES/MIT.txt](LICENSES/MIT.txt))

## Acknowledgements

The [ULX3S](https://github.com/emard/ulx3s) (Radiona / FER / EMARD) showed what an open ECP5 board can do for a
community; we learn from it with gratitude. LATFUN6 is an independent design from Lattice's public documentation.
