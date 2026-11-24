"""LATFUN6 v0.2 pinout: single source of truth -> board.json + .lpf + LiteX platform, validated
against Lattice's pinout CSV.

Usage:
    python gen_board.py <ECP5-5G-45 pinout CSV> [<ECP5-5G-85 pinout CSV>]

The Lattice CSVs are not redistributed. Download "ECP5-5G-45 Pinout" (document_id=51578) and
"ECP5-5G-85 Pinout" (document_id=51579) from https://www.latticesemi.com/view_document?document_id=...

Checks:
  * every ball exists in CABGA381, is a user I/O, and is used once; K16/K17 are never used (85F-only I/O);
  * every *_p/*_n pair is a True/Comp pair of the same PIO pair;
  * pairs flagged lvds_capable sit on A/B pairs in left/right banks (2,3,6,7);
  * clocks land on PCLK-capable pins;
  * bank VCCIO matches the IO standard (LVCMOS33 on 3.3 V banks, SSTL135 on 1.35 V banks);
  * DDR3: every DQ/DM of byte n sits in the DQS group of dqs_p[n]; dqs_p[n] sits on an LDQS/RDQS pad;
  * (optional) the same ball has the same role and bank on the LFE5UM5G-85F.
"""
import csv, json, sys, pathlib
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
OUT_JSON = HERE.parent / "board" / "latfun6.json"
OUT_LPF = HERE.parent / "board" / "latfun6.lpf"
OUT_PLAT = HERE.parent / "board" / "latfun6_platform.py"

BOARD = {
    "name": "LATFUN6",
    "revision": "v0.2-draft",
    "fpga": {"part": "LFE5UM5G-45F-8BG381C", "family": "ECP5-5G", "device": "LFE5UM5G-45F", "package": "CABGA381",
             "speed": 8, "alt_parts": ["LFE5UM5G-45F-8BG381I", "LFE5UM5G-85F-8BG381x (K16/K17 unused)"],
             "nextpnr": "--um5g-45k --package CABGA381 --speed 8"},
    "clock": {"name": "clk_25mhz", "freq_hz": 25_000_000},
    "bank_vccio": {"0": 3.3, "1": 3.3, "2": 3.3, "3": 3.3, "6": 1.35, "7": 1.35, "8": 3.3},
    "banned_balls": ["K16", "K17"],
    "serdes": {"DCU0_CH0": "PCIe x1 (REFCLK_D0 from slot, 100 MHz)", "DCU0_CH1": "spare",
               "DCU1_CH0": "SMA TX/RX pairs", "DCU1_CH1": "SFP cage (REFCLK_D1, on-board oscillator); RX polarity inverted on the board: set CH1_INVERT_RX"},
    "licence": {"hardware": "CERN-OHL-S-2.0", "docs": "CC-BY-SA-4.0", "code": "MIT"},
}

S = {}  # name -> dict(ball, io, feature, attrs)
def sig(name, ball, io="LVCMOS33", feat="", **attrs):
    S[name] = dict(ball=ball, io=io, feature=feat, attrs=attrs)

def bus(prefix, balls, io="LVCMOS33", feat="", **attrs):
    for i, b in enumerate(balls.split()):
        sig(f"{prefix}[{i}]", b, io, feat, **attrs)

# ---------------- bank 1: clock + user I/O ----------------
sig("clk_25mhz", "B12", feat="R1 25 MHz oscillator (PCLKT1_0)", clock=True)
bus("led", "A12 A13 B13 C13 D13 E13 A14 C14", feat="R2 user LED", DRIVE="4")
bus("btn_n", "D14 E14 A15 B15", feat="R3 button (0=RESET, 1=un-debounced)", PULLMODE="UP")
bus("sw_n", "C15 D15 E15 A16", feat="R4 DIP switch", PULLMODE="UP")
sig("uart_tx", "B16", feat="R5 FPGA->PC (FT2232H BDBUS1 RXD)")
sig("uart_rx", "C16", feat="R5 PC->FPGA (FT2232H BDBUS0 TXD)", PULLMODE="UP")
sig("uart_rts_n", "D16", feat="R5 FPGA->FT CTS# (BDBUS3)")
sig("uart_cts_n", "B17", feat="R5 FT RTS# (BDBUS2)->FPGA", PULLMODE="UP")
bus("la", "C17 A17 B18 A18 B19 A19 B20 D11", feat="R14 LA probe out")
# 2026-11-23 (user decision, layout): loop_a/loop_b (R17 loopback jumper) and tp_pll (R15 test point) dropped from
# U5 -- E11/D12/E12 sit 4-5 rings deep in U5's crowded bottom-right corner and could not be escaped.

# ---------------- bank 0: HDMI, microSD, I2C, audio, PCIe/SFP sideband ----------------
for nm, (p, n) in {"gpdi_clk": ("A7", "A8"), "gpdi_d0": ("C8", "B8"),
                   "gpdi_d1": ("E8", "D8"), "gpdi_d2": ("C6", "C7")}.items():
    sig(f"{nm}_p", p, io="LVCMOS33D", feat="R12 HDMI TMDS", DRIVE="4", pair=nm)
    sig(f"{nm}_n", n, io="LVCMOS33D", feat="R12 HDMI TMDS (comp, implied by _p)", pair=nm)
sig("gpdi_scl", "D9", feat="R12 HDMI DDC SCL (via level shifter)")
sig("gpdi_sda", "E9", feat="R12 HDMI DDC SDA (via level shifter)")
sig("gpdi_hpd", "C9", feat="R12 HDMI hot-plug detect (divided 5V)")
sig("sd_clk", "E6", feat="R28 microSD CLK")
sig("sd_cmd", "D6", feat="R28 microSD CMD", PULLMODE="UP")
# 2026-11-23 (layout, user: parts/pins open): sd_dat[3] B6 -> C12 (bank 1, 3.3 V) -- B6 is boxed in by the HDMI/DDR
# escapes on every layer; C12 escapes with an in-pad via.
bus("sd_dat", "E7 D7 A6 C12", feat="R28 microSD DAT", PULLMODE="UP")
sig("sd_det_n", "D10", feat="R28 microSD card detect", PULLMODE="UP")
sig("sfp_scl", "E10", feat="R23 SFP module I2C SCL (4.7k PU)")
sig("sfp_sda", "B9", feat="R23 SFP module I2C SDA (4.7k PU)")
sig("pcie_perst_n", "C10", feat="R25 PCIe PERST# (from slot)", PULLMODE="UP")
sig("pcie_wake_n", "A9", feat="R25 PCIe WAKE# (open drain to slot)")
sig("pcie_clkreq_n", "B10", feat="R25 PCIe CLKREQ# (open drain)")
sig("i2c_scl", "A10", feat="R10 24C02 SCL (MAC address + board ID)")
sig("i2c_sda", "A11", feat="R10 24C02 SDA")
sig("audio_l", "B11", feat="R11 PWM/delta-sigma -> RC -> jack L")
sig("audio_r", "C11", feat="R11 PWM/delta-sigma -> RC -> jack R")

# ---------------- bank 2: PMOD1/2 on A/B pairs (LVDS-capable), PMOD3/4 on C/D pairs ----------------
# 2026-11-23 (user decision, layout): RGMII and PMOD3/4 swapped so all four PMODs leave U5's bottom-right toward the
# right-edge headers and RGMII + ULPI leave its bottom-left toward their PHYs (they crossed under U5 before).
# R13 relaxed for PMOD3/4: C/D true/comp pairs (single-ended / pseudo-differential, no true LVDS output).
PMODS = {
    1: ("2", [("C18", "D17"), ("D18", "E17"), ("F17", "G18"), ("H18", "H17")]),
    2: ("2", [("C20", "D19"), ("E20", "F19"), ("G19", "H20"), ("J19", "K19")]),
    3: ("2", [("J20", "K20"), ("J18", "K18"), ("F20", "G20"), ("D20", "E19")]),
    4: ("2", [("E16", "F16"), ("E18", "F18"), ("G16", "H16"), ("J17", "J16")]),
}
PMOD_LVDS = {1: True, 2: True, 3: False, 4: False}
PMOD_HDR_PIN = {0: (1, 7), 1: (2, 8), 2: (3, 9), 3: (4, 10)}
for j, (bank, pairs) in PMODS.items():
    for k, (p, n) in enumerate(pairs):
        hp, hn = PMOD_HDR_PIN[k]
        sig(f"pmod{j}[{hp}]", p, feat=f"R13 PMOD{j} pin {hp} (pair {k} true)", pair=f"pmod{j}_{k}", lvds_capable=PMOD_LVDS[j])
        sig(f"pmod{j}[{hn}]", n, feat=f"R13 PMOD{j} pin {hn} (pair {k} comp)", pair=f"pmod{j}_{k}", lvds_capable=PMOD_LVDS[j])

# RGMII in bank 3 (A/B pins) since 2026-11-23, next to ULPI: both go to PHYs on the board's left
sig("eth_rx_clk", "L20", feat="R27 RGMII RXC (PCLKT3_1)", clock=True)
sig("eth_rx_ctl", "M20", feat="R27 RGMII RX_CTL")
bus("eth_rx_data", "N19 N20 P20 R20", feat="R27 RGMII RXD")
sig("eth_tx_clk", "T19", feat="R27 RGMII TXC", SLEWRATE="FAST")
sig("eth_tx_ctl", "R18", feat="R27 RGMII TX_CTL", SLEWRATE="FAST")
bus("eth_tx_data", "U18 U17 N17 P16", feat="R27 RGMII TXD", SLEWRATE="FAST")
sig("eth_mdc", "N16", feat="R27 PHY MDC")
sig("eth_mdio", "M17", feat="R27 PHY MDIO (1.5k PU)")
sig("eth_rst_n", "L16", feat="R27 PHY reset")
sig("eth_int_n", "L17", feat="R27 PHY interrupt", PULLMODE="UP")

# ---------------- bank 3: RGMII on A/B (above), ULPI + SFP control on C/D ----------------
sig("ulpi_clk", "L19", feat="R29 ULPI 60 MHz clock from PHY (PCLKT3_0)", clock=True)
sig("ulpi_dir", "M19", feat="R29 ULPI DIR")
sig("ulpi_nxt", "L18", feat="R29 ULPI NXT")
sig("ulpi_stp", "M18", feat="R29 ULPI STP")
bus("ulpi_data", "N18 P17 R16 R17 T16 P19 P18 T20", feat="R29 ULPI DATA")
sig("ulpi_rst", "U20", feat="R29 ULPI PHY reset")
sig("sfp_tx_disable", "U19", feat="R23 SFP TX_DISABLE (PU on module side)")
sig("sfp_los", "T18", feat="R23 SFP LOS (4.7k PU)", PULLMODE="UP")
sig("sfp_mod_abs", "U16", feat="R23 SFP MOD_ABS (4.7k PU)", PULLMODE="UP")
sig("sfp_rs", "T17", feat="R23 SFP rate select")

# ---------------- bank 8: config flash ----------------
sig("flash_io2", "Y2", feat="R8 QSPI IO2 (D2)")
sig("flash_io3", "W1", feat="R8 QSPI IO3 (D3)")
sig("flash_mosi", "W2", feat="R8 config D0/MOSI")
sig("flash_miso", "V2", feat="R8 config D1/MISO")
sig("flash_cs_n", "R2", feat="R8 config CSSPIN (4.7k pull-up at flash)")

# ---------------- banks 6/7: DDR3L x16 (Lattice ECP5-5G reference ball map + A13/A14) ----------------
DDR = "SSTL135_I"
bus("ddram_a", "P2 C4 E5 F5 B3 F4 B5 E4 C5 E3 D5 B4 C3 A3 D3", io=DDR, feat="R26 DDR3 address A0-A14")
bus("ddram_ba", "P5 N3 M3", io=DDR, feat="R26 DDR3 bank address")
sig("ddram_ras_n", "P1", io=DDR, feat="R26 DDR3 RAS#")
sig("ddram_cas_n", "L1", io=DDR, feat="R26 DDR3 CAS#")
sig("ddram_we_n", "M1", io=DDR, feat="R26 DDR3 WE#")
sig("ddram_cs_n", "K1", io=DDR, feat="R26 DDR3 CS#")
sig("ddram_cke", "N2", io=DDR, feat="R26 DDR3 CKE")
sig("ddram_odt", "L2", io=DDR, feat="R26 DDR3 ODT")
sig("ddram_reset_n", "N4", io=DDR, feat="R26 DDR3 RESET#")
sig("ddram_clk_p", "M4", io="SSTL135D_I", feat="R26 DDR3 CK (comp implied)")
bus("ddram_dm", "J4 H5", io=DDR, feat="R26 DDR3 DM0/DM1", ddr_byte=None)
bus("ddram_dq", "L5 F1 K4 G1 L4 H1 G2 J3 D1 C1 E2 C2 F3 A2 E1 B1", io=DDR, feat="R26 DDR3 DQ", TERMINATION="75")
bus("ddram_dqs_p", "K2 H4", io="SSTL135D_I", feat="R26 DDR3 DQS (comp implied)", TERMINATION="OFF", DIFFRESISTOR="100")

# Showcase mappings (documentation; showcase LPFs are generated from these)
SHOWCASES = {
    "A": {"clk_25mhz": "clk_25mhz", "btn_fire": "btn_n[2]", "sw_cont": "sw_n[0]", "sw_len[0]": "sw_n[1]",
          "sw_len[1]": "sw_n[2]", "out_p": "pmod1[1]", "out_n": "pmod1[7]", "drv_en": "pmod1[2]",
          "led_active": "led[0]", "led_lock": "led[1]"},
    "B": {"clk_25mhz": "clk_25mhz",
          **{f"drv_a[{i}]": f"pmod3[{p}]" for i, p in enumerate([1, 2, 3, 4, 7, 8, 9, 10])},
          **{f"drv_b[{i}]": f"pmod4[{p}]" for i, p in enumerate([1, 2, 3, 4, 7, 8, 9, 10])},
          "spi_sck": "pmod2[1]", "spi_cs_n": "pmod2[2]", "spi_mosi": "pmod2[3]", "spi_miso": "pmod2[4]",
          "trig_in": "pmod2[7]", "interlock": "pmod2[8]", "led_busy": "led[0]", "led_lock": "led[1]"},
}


def load(fn):
    out, ci = {}, None
    for r in csv.reader(open(fn, encoding="utf-8", errors="replace")):
        if not r or r[0].startswith("#"):
            continue
        if r[0] == "PAD":
            ci = r.index("CABGA381"); continue
        if ci is not None and len(r) > ci and r[ci] not in ("-", ""):
            out[r[ci]] = dict(func=r[1], bank=r[2], dual=r[3], diff=r[4], dqs=r[6])
    return out


def is_io(f):
    return f[0] == "P" and f[1] in "LRTB" and f[2].isdigit()


def grp(dqs):  # 'LDQS41' / 'LDQSN41' / 'LDQ41' -> 'L41'
    return dqs[0] + "".join(c for c in dqs if c.isdigit()) if dqs not in ("-", "") else None


def main():
    pins = load(sys.argv[1])
    pins85 = load(sys.argv[2]) if len(sys.argv) > 2 else None
    err, used = [], {}
    for name, s in S.items():
        b = s["ball"]
        if b in BOARD["banned_balls"]: err.append(f"{name}: {b} is reserved (85F-only I/O)")
        if b not in pins: err.append(f"{name}: ball {b} not in CABGA381"); continue
        p = pins[b]
        if not is_io(p["func"]): err.append(f"{name}: {b} is {p['func']}, not user I/O")
        if b in used: err.append(f"{name}: {b} already used by {used[b]}")
        used[b] = name
        s.update(bank=p["bank"], pio=p["func"], dual=p["dual"], dqs=p["dqs"])
        v = BOARD["bank_vccio"][p["bank"]]
        want = 3.3 if s["io"].startswith("LVCMOS33") else 1.35 if s["io"].startswith("SSTL135") else None
        if want != v: err.append(f"{name}: {s['io']} in a {v} V bank")
        if pins85:
            q = pins85.get(b)
            if not q or q["bank"] != p["bank"] or not is_io(q["func"]) or q["func"][-1] != p["func"][-1]:
                err.append(f"{name}: {b} differs on 85F ({q})")
    # differential pairs
    pairs = {}
    for name, s in S.items():
        if "pair" in s["attrs"]: pairs.setdefault(s["attrs"]["pair"], []).append((name, s))
    for pr, members in pairs.items():
        (n1, s1), (n2, s2) = members
        d1 = pins[s1["ball"]]["diff"]
        if not (d1.startswith("True_OF_") and d1.endswith(s2["pio"])):
            err.append(f"pair {pr}: {n1}={s1['ball']} is not the true side of {n2}={s2['ball']}")
        if s1["attrs"].get("lvds_capable") and (s1["bank"] not in "2367" or s1["pio"][-1] != "A"):
            err.append(f"pair {pr}: not an A/B pair in a left/right bank -> no true LVDS driver")
    # true side of implied-complement differential signals
    for name, s in S.items():
        if (s["io"].endswith("D_I") or s["io"] == "LVCMOS33D") and "pair" not in s["attrs"]:
            if not pins[s["ball"]]["diff"].startswith("True_OF_"):
                err.append(f"{name}: differential signal on a complement ball {s['ball']}")
    for name, s in S.items():
        if s["attrs"].get("clock") and "PCLK" not in s["dual"]:
            err.append(f"{name}: clock not on a PCLK pin ({s['ball']} {s['dual']})")
    # DDR3 byte lanes
    for byte in (0, 1):
        dqs = S[f"ddram_dqs_p[{byte}]"]
        if not dqs["dqs"].startswith(("LDQS", "RDQS")) or "DQSN" in dqs["dqs"]:
            err.append(f"ddram_dqs_p[{byte}] on {dqs['ball']} ({dqs['dqs']}) is not a DQS pad")
        g = grp(dqs["dqs"])
        members = [f"ddram_dq[{byte*8+i}]" for i in range(8)] + [f"ddram_dm[{byte}]"]
        for m in members:
            if grp(S[m]["dqs"]) != g:
                err.append(f"{m} on {S[m]['ball']} ({S[m]['dqs']}) not in DQS group {g} of byte {byte}")
    if err:
        print("FAIL\n  " + "\n  ".join(err)); sys.exit(1)

    OUT_JSON.parent.mkdir(exist_ok=True)
    clean = lambda s: {k: v for k, v in s.items() if k != "attrs"} | {
        "attrs": {k: v for k, v in s["attrs"].items() if k not in ("pair", "lvds_capable", "clock", "ddr_byte")}}
    board = dict(BOARD, signals={n: clean(s) for n, s in S.items()},
                 pmods={str(j): {"bank": bank, "pairs": pr} for j, (bank, pr) in PMODS.items()}, showcases=SHOWCASES)
    OUT_JSON.write_text(json.dumps(board, indent=1), encoding="utf-8")

    lines = [f"# {BOARD['name']} {BOARD['revision']} - generated by tools/gen_board.py. Do not edit.",
             f"# FPGA {BOARD['fpga']['part']}  ({BOARD['fpga']['nextpnr']})", "BLOCK RESETPATHS;", "BLOCK ASYNCPATHS;",
             "SYSCONFIG CONFIG_IOVOLTAGE=3.3 COMPRESS_CONFIG=ON MCCLK_FREQ=62 SLAVE_SPI_PORT=DISABLE MASTER_SPI_PORT=ENABLE SLAVE_PARALLEL_PORT=DISABLE;", ""]
    for n, s in S.items():
        if (s["io"] == "LVCMOS33D") and n.endswith("_n"):
            continue
        lines.append(f'LOCATE COMP "{n}" SITE "{s["ball"]}"; # {s["feature"]}')
        attrs = " ".join(f"{k}={v}" for k, v in clean(s)["attrs"].items())
        lines.append(f'IOBUF PORT "{n}" IO_TYPE={s["io"]} {attrs};'.replace(" ;", ";"))
    lines += ['FREQUENCY PORT "clk_25mhz" 25 MHZ;', 'FREQUENCY PORT "eth_rx_clk" 125 MHZ;', 'FREQUENCY PORT "ulpi_clk" 60 MHZ;']
    OUT_LPF.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # LiteX platform (used by test/litex_smoke.py)
    def pins_of(prefix):
        names = sorted([n for n in S if n.startswith(prefix + "[")], key=lambda n: int(n[len(prefix) + 1:-1]))
        return " ".join(S[n]["ball"] for n in names)
    P = []
    P.append('("clk25", 0, Pins("%s"), IOStandard("LVCMOS33"))' % S["clk_25mhz"]["ball"])
    P.append('("serial", 0, Subsignal("tx", Pins("%s")), Subsignal("rx", Pins("%s")), IOStandard("LVCMOS33"))'
             % (S["uart_tx"]["ball"], S["uart_rx"]["ball"]))
    P.append('("user_led", 0, Pins("%s"), IOStandard("LVCMOS33"))' % pins_of("led"))
    ddr = [('a', pins_of("ddram_a"), DDR), ('ba', pins_of("ddram_ba"), DDR)] + \
          [(k, S[f"ddram_{k}"]["ball"], DDR) for k in ("ras_n", "cas_n", "we_n", "cs_n", "cke", "odt", "reset_n")] + \
          [('dm', pins_of("ddram_dm"), DDR)]
    sub = ", ".join(f'Subsignal("{k}", Pins("{v}"), IOStandard("{io}"))' for k, v, io in ddr)
    sub += f', Subsignal("dq", Pins("{pins_of("ddram_dq")}"), IOStandard("{DDR}"), Misc("TERMINATION=75"))'
    sub += f', Subsignal("dqs_p", Pins("{pins_of("ddram_dqs_p")}"), IOStandard("SSTL135D_I"), Misc("TERMINATION=OFF"), Misc("DIFFRESISTOR=100"))'
    sub += f', Subsignal("clk_p", Pins("{S["ddram_clk_p"]["ball"]}"), IOStandard("SSTL135D_I"))'
    P.append(f'("ddram", 0, {sub}, Misc("SLEWRATE=FAST"))')
    eth = (f'("eth_clocks", 0, Subsignal("tx", Pins("{S["eth_tx_clk"]["ball"]}")), Subsignal("rx", Pins("{S["eth_rx_clk"]["ball"]}")), IOStandard("LVCMOS33"))',
           f'("eth", 0, Subsignal("rst_n", Pins("{S["eth_rst_n"]["ball"]}")), Subsignal("mdio", Pins("{S["eth_mdio"]["ball"]}")), '
           f'Subsignal("mdc", Pins("{S["eth_mdc"]["ball"]}")), Subsignal("rx_ctl", Pins("{S["eth_rx_ctl"]["ball"]}")), '
           f'Subsignal("rx_data", Pins("{pins_of("eth_rx_data")}")), Subsignal("tx_ctl", Pins("{S["eth_tx_ctl"]["ball"]}")), '
           f'Subsignal("tx_data", Pins("{pins_of("eth_tx_data")}")), IOStandard("LVCMOS33"))')
    P += list(eth)
    OUT_PLAT.write_text(
        "# Generated by tools/gen_board.py - LiteX platform for LATFUN6 " + BOARD["revision"] + ". Do not edit.\n"
        "from litex.build.generic_platform import *\nfrom litex.build.lattice import LatticeECP5Platform\n\n"
        "_io = [\n    " + ",\n    ".join(P) + ",\n]\n\n"
        "class Platform(LatticeECP5Platform):\n"
        "    default_clk_name = 'clk25'\n    default_clk_period = 1e9/25e6\n"
        "    def __init__(self, device='LFE5UM5G-45F-8BG381C', toolchain='trellis', **kw):\n"
        "        LatticeECP5Platform.__init__(self, device, _io, toolchain=toolchain, **kw)\n", encoding="utf-8")

    per_bank = dict(sorted(Counter(s["bank"] for s in S.values()).items()))
    print(f"PASS  {len(S)} signals, {len(used)} balls; per bank {per_bank}")
    print(f"wrote {OUT_JSON}\nwrote {OUT_LPF}\nwrote {OUT_PLAT}")


if __name__ == "__main__":
    main()
