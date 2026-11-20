"""LATFUN6 pinout: single source of truth -> board.json + .lpf, validated against Lattice's pinout CSV.

Usage:
    python gen_board.py <ECP5U-25 pinout CSV> [<ECP5U-45 pinout CSV>]

The Lattice CSV is not redistributed here. Download "ECP5U-25 Pinout" (FPGA-SC-02033) from
https://www.latticesemi.com/view_document?document_id=50485 (45F: document_id=50486).

Checks:
  * every ball exists in CABGA256, is a user I/O, and is used once;
  * every *_p/*_n pair is a True/Comp pair of the same PIO pair;
  * pairs flagged lvds_capable sit on A/B pairs in left/right banks (2,3,6,7);
  * the clock lands on a PCLK pin;
  * bank VCCIO is consistent with the IO standard;
  * (optional) the same ball has the same role and bank on the LFE5U-45F.
"""
import csv, json, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
OUT_JSON = HERE.parent / "board" / "latfun6.json"
OUT_LPF = HERE.parent / "board" / "latfun6.lpf"

BOARD = {
    "name": "LATFUN6",              # codename; public name TBD
    "revision": "v0.1-draft",
    "fpga": {"part": "LFE5U-25F-7BG256I", "family": "ECP5", "device": "LFE5U-25F", "package": "CABGA256",
             "speed": 7, "alt_parts": ["LFE5U-25F-6BG256C", "LFE5U-45F-xBG256x"],
             "nextpnr": "--25k --package CABGA256 --speed 7"},
    "clock": {"name": "clk_25mhz", "freq_hz": 25_000_000},
    "bank_vccio": {"0": 3.3, "1": 3.3, "2": 3.3, "3": 3.3, "6": 3.3, "7": 3.3, "8": 3.3},
    "licence": {"hardware": "CERN-OHL-S-2.0", "docs": "CC-BY-SA-4.0", "code": "MIT"},
}

# signal -> (ball, io_type, extra-attrs, lab/feature)
S = {}
def sig(name, ball, io="LVCMOS33", feat="", **attrs):
    S[name] = dict(ball=ball, io=io, feature=feat, attrs=attrs)

# --- clock (R1) ---
sig("clk_25mhz", "A7", feat="R1 25 MHz oscillator (PCLKT0_0)")
# --- LEDs (R2), active high ---
for i, b in enumerate(["B9", "C9", "D9", "E9", "A9", "A10", "B10", "C10"]):
    sig(f"led[{i}]", b, feat="R2 user LED", DRIVE="4")
# --- buttons (R3), active low, external pull-up; btn[0]=RESET, btn[1]=bouncy (no RC) ---
for i, b in enumerate(["D10", "E10", "B11", "C11"]):
    sig(f"btn_n[{i}]", b, feat="R3 button (0=RESET, 1=un-debounced)", PULLMODE="UP")
# --- DIP (R4), active low ---
for i, b in enumerate(["D11", "E11", "A11", "A12"]):
    sig(f"sw_n[{i}]", b, feat="R4 DIP switch", PULLMODE="UP")
# --- UART (R5), named from the FPGA side ---
sig("uart_tx", "B12", feat="R5 FPGA->PC (FT2232H BDBUS1 RXD)")
sig("uart_rx", "C12", feat="R5 PC->FPGA (FT2232H BDBUS0 TXD)", PULLMODE="UP")
sig("uart_rts_n", "D12", feat="R5 FPGA->FT CTS# (BDBUS3)")
sig("uart_cts_n", "E12", feat="R5 FT RTS# (BDBUS2)->FPGA", PULLMODE="UP")
# --- QSPI flash extra lines (R8); CS/MOSI/MISO/CCLK are dedicated config pins ---
sig("flash_io2", "M7", feat="R8 QSPI IO2 (D2)")
sig("flash_io3", "N7", feat="R8 QSPI IO3 (D3)")
sig("flash_mosi", "T8", feat="R8 config D0/MOSI")
sig("flash_miso", "T7", feat="R8 config D1/MISO")
sig("flash_cs_n", "N8", feat="R8 config CSSPIN (4.7k pull-up at flash)")
# --- I2C EEPROM (R10) ---
sig("i2c_scl", "E5", feat="R10 24C02 SCL (4.7k pull-up)")
sig("i2c_sda", "D5", feat="R10 24C02 SDA (4.7k pull-up)")
# --- audio (R11) ---
sig("audio_l", "C6", feat="R11 PWM/delta-sigma -> RC -> jack L")
sig("audio_r", "B6", feat="R11 PWM/delta-sigma -> RC -> jack R")
# --- HDMI (R12), emulated differential on top bank 0 ---
for nm, (p, n) in {"gpdi_clk": ("A3", "A4"), "gpdi_d0": ("C4", "B4"),
                   "gpdi_d1": ("C5", "B5"), "gpdi_d2": ("A5", "A6")}.items():
    sig(f"{nm}_p", p, io="LVCMOS33D", feat="R12 HDMI TMDS", DRIVE="4", pair=nm)
    sig(f"{nm}_n", n, io="LVCMOS33D", feat="R12 HDMI TMDS (comp, implied by _p)", pair=nm)
sig("gpdi_scl", "E4", feat="R12 HDMI DDC SCL (via level shifter)")
sig("gpdi_sda", "D4", feat="R12 HDMI DDC SDA (via level shifter)")
sig("gpdi_hpd", "E6", feat="R12 HDMI hot-plug detect (divided 5V)")
# --- logic-analyser probe header (R14) ---
for i, b in enumerate(["B13", "C13", "D13", "E13", "A13", "A14", "B14", "A15"]):
    sig(f"la[{i}]", b, feat="R14 LA probe out")
# --- test point and loopback (R15, R17) ---
sig("tp_pll", "C8", feat="R15 PLL/clock observation test point")
sig("loop_a", "E8", feat="R17 loopback jumper side A")
sig("loop_b", "D8", feat="R17 loopback jumper side B", PULLMODE="DOWN")

# --- PMODs (R13): each on its own L/R bank, A/B (LVDS-capable) pairs, pin k pairs with pin k+6 ---
PMODS = {
    1: ("7", [("B1", "B2"), ("C1", "C2"), ("D1", "E2"), ("G5", "G4")]),
    2: ("6", [("L1", "L2"), ("K4", "K5"), ("N1", "P2"), ("P1", "R1")]),
    3: ("2", [("B16", "B15"), ("C16", "C15"), ("D16", "E15"), ("G12", "G13")]),
    4: ("3", [("L16", "L15"), ("K13", "K12"), ("N16", "P15"), ("P16", "R16")]),
}
PMOD_HDR_PIN = {0: (1, 7), 1: (2, 8), 2: (3, 9), 3: (4, 10)}   # pair index -> (P pin, N pin) on 2x6 header
for j, (bank, pairs) in PMODS.items():
    for k, (p, n) in enumerate(pairs):
        hp, hn = PMOD_HDR_PIN[k]
        sig(f"pmod{j}[{hp}]", p, feat=f"R13 PMOD{j} pin {hp} (pair {k} true)", pair=f"pmod{j}_{k}", lvds_capable=True)
        sig(f"pmod{j}[{hn}]", n, feat=f"R13 PMOD{j} pin {hn} (pair {k} comp)", pair=f"pmod{j}_{k}", lvds_capable=True)

# Showcase mappings (documentation; the showcase LPFs are generated from these)
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
            ci = r.index("CABGA256"); continue
        if ci is not None and len(r) > ci and r[ci] not in ("-", ""):
            out[r[ci]] = dict(func=r[1], bank=r[2], dual=r[3], diff=r[4])
    return out


def is_io(f):
    return f[0] == "P" and f[1] in "LRTB" and f[2].isdigit()


def main():
    pins = load(sys.argv[1])
    pins45 = load(sys.argv[2]) if len(sys.argv) > 2 else None
    err = []
    used = {}
    for name, s in S.items():
        b = s["ball"]
        if b not in pins: err.append(f"{name}: ball {b} not in CABGA256"); continue
        p = pins[b]
        if not is_io(p["func"]): err.append(f"{name}: {b} is {p['func']}, not user I/O")
        if b in used: err.append(f"{name}: {b} already used by {used[b]}")
        used[b] = name
        s["bank"] = p["bank"]; s["pio"] = p["func"]; s["dual"] = p["dual"]
        v = BOARD["bank_vccio"][p["bank"]]
        if s["io"].startswith("LVCMOS33") and v != 3.3: err.append(f"{name}: LVCMOS33 in {v} V bank")
        if pins45:
            q = pins45[b]
            if q["bank"] != p["bank"] or not is_io(q["func"]) or q["func"][-1] != p["func"][-1]:
                err.append(f"{name}: {b} differs on 45F ({q})")
    # pairs
    pairs = {}
    for name, s in S.items():
        if "pair" in s["attrs"]: pairs.setdefault(s["attrs"]["pair"], []).append((name, s))
    for pr, members in pairs.items():
        (n1, s1), (n2, s2) = members
        f1, f2 = s1["pio"], s2["pio"]
        d1 = pins[s1["ball"]]["diff"]
        if not (d1.startswith("True_OF_") and d1.endswith(f2)):
            err.append(f"pair {pr}: {n1}={s1['ball']}({f1}) is not the true side of {n2}={s2['ball']}({f2})")
        if s1["attrs"].get("lvds_capable"):
            if s1["bank"] not in "2367" or f1[-1] != "A":
                err.append(f"pair {pr}: not an A/B pair in a left/right bank -> no true LVDS driver")
    if "PCLK" not in pins[S["clk_25mhz"]["ball"]]["dual"]:
        err.append("clk_25mhz not on a PCLK pin")
    if err:
        print("FAIL\n  " + "\n  ".join(err)); sys.exit(1)

    # outputs
    OUT_JSON.parent.mkdir(exist_ok=True)
    board = dict(BOARD, signals={n: {k: v for k, v in s.items() if k != "attrs"} | {"attrs": {
        k: v for k, v in s["attrs"].items() if k not in ("pair", "lvds_capable")}} for n, s in S.items()},
        pmods={str(j): {"bank": bank, "pairs": pairs_} for j, (bank, pairs_) in PMODS.items()},
        showcases=SHOWCASES)
    OUT_JSON.write_text(json.dumps(board, indent=1), encoding="utf-8")
    lines = [f"# {BOARD['name']} {BOARD['revision']} - generated by tools/gen_board.py from board/latfun6.json. Do not edit.",
             f"# FPGA {BOARD['fpga']['part']}  ({BOARD['fpga']['nextpnr']})", "BLOCK RESETPATHS;", "BLOCK ASYNCPATHS;",
             'SYSCONFIG CONFIG_IOVOLTAGE=3.3 COMPRESS_CONFIG=ON MCCLK_FREQ=62 SLAVE_SPI_PORT=DISABLE MASTER_SPI_PORT=ENABLE SLAVE_PARALLEL_PORT=DISABLE;',
             ""]
    for n, s in S.items():
        if s["io"] == "LVCMOS33D" and n.endswith("_n"):
            continue  # complement is implied by the _p side
        if n in ("flash_mosi", "flash_miso", "flash_cs_n"):
            pass
        lines.append(f'LOCATE COMP "{n}" SITE "{s["ball"]}"; # {s["feature"]}')
        attrs = " ".join(f"{k}={v}" for k, v in s["attrs"].items() if k not in ("pair", "lvds_capable"))
        lines.append(f'IOBUF PORT "{n}" IO_TYPE={s["io"]} {attrs};'.replace("  ", " ").replace(" ;", ";"))
    lines.append(f'FREQUENCY PORT "clk_25mhz" 25 MHZ;')
    OUT_LPF.write_text("\n".join(lines) + "\n", encoding="utf-8")
    from collections import Counter
    print(f"PASS  {len(S)} signals, {len(used)} balls; per bank {dict(sorted(Counter(s['bank'] for s in S.values()).items()))}")
    print(f"wrote {OUT_JSON}\nwrote {OUT_LPF}")


if __name__ == "__main__":
    main()
