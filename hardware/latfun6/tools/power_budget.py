#!/usr/bin/env python3
"""LATFUN6 v0.2 power budget: rail-by-rail load currents -> regulator losses -> slot / USB-C input power.

Run:  python power_budget.py            (prints the tables used in docs/power_budget.md)
Scenarios: T = typical Linux lab, W = worst case (heavy fabric, all 4 lanes at 5 Gb/s, SFP class II, user loads).
Sources: [DS] Lattice FPGA-DS-02012 v3.4 Tab 3.8 (static) / Tab 3.10 (SERDES); [USB] Microchip DS00001792F Tab 4-x;
[FT] FTDI FT2232H DS v2.9 (operating current); [SFF] SFF-8431 power classes. Items marked EST are engineering
estimates to replace with Lattice Power Calculator results and bench measurements (shunts RS1-RS3).  MIT licence.
"""

# (rail, load, volts, amps_typ, amps_worst, source)
LOADS = [
    # ---- 1V2 core (VCC) ----
    ("1V2",  "ECP5 VCC static (45F, TJ 85C typ; worst = hot/fast silicon)", 1.20, 0.116, 0.250, "DS T3.8 / EST x2"),
    ("1V2",  "ECP5 VCC dynamic (T: LiteX Linux SoC ~21 % LUT @75 MHz; W: 80 % LUT @100 MHz)", 1.20, 0.350, 1.200, "EST"),
    # ---- 1V2_SER (VCCA + VCCHTX + VCCHRX) ----
    ("1V2S", "SERDES static ICCA, 2 DCUs x 11 mA", 1.20, 0.022, 0.022, "DS T3.8"),
    ("1V2S", "D0CH0 PCIe Gen2 5 Gb/s (VCCA+HTX+HRX)", 1.20, 0.0684, 0.0805, "DS T3.10"),
    ("1V2S", "D1CH0 SFP (T: 1.25 Gb/s, W: 5 Gb/s)", 1.20, 0.0464, 0.0805, "DS T3.10"),
    ("1V2S", "D1CH1 SMA (T: standby, W: 5 Gb/s)", 1.20, 0.0049, 0.0805, "DS T3.10"),
    ("1V2S", "D0CH1 spare (T: standby, W: 5 Gb/s)", 1.20, 0.0049, 0.0805, "DS T3.10"),
    # ---- 2V5 ----
    ("2V5",  "ECP5 VCCAUX static", 2.50, 0.017, 0.017, "DS T3.8"),
    ("2V5",  "VCCAUX dynamic (PLLs, REFCLK buffers) + VCCAUXA0/1", 2.50, 0.040, 0.080, "EST"),
    # ---- 1V35 ----
    ("1V35", "DDR3L MT41K256M16 VDD+VDDQ @300 MT/s (T: Linux idle/avg, W: streaming)", 1.35, 0.120, 0.250, "EST (Micron IDD4R class)"),
    ("1V35", "ECP5 VCCIO6/7 SSTL135 into ODT", 1.35, 0.080, 0.200, "EST"),
    ("1V35", "3 VREF dividers 2x1k", 1.35, 0.002, 0.002, "calc"),
    # ---- 1V8 ----
    ("1V8",  "USB3320 VDD18 (HS transfer)", 1.80, 0.0294, 0.0294, "USB T4 I18AVG(HS)"),
    # ---- 3V3 ----
    ("3V3",  "ECP5 VCCIO 0/1/2/3/8 (HDMI 720p LVCMOS33D, RGMII, ULPI, SD, PMOD I/O)", 3.30, 0.120, 0.200, "EST (CV^2f)"),
    ("3V3",  "FT2232H (VCC core+VCCIO, operating)", 3.30, 0.070, 0.070, "FT DS"),
    ("3V3",  "RTL8211F 1000BASE-T link, traffic", 3.30, 0.130, 0.200, "EST (vendor asks 1 A source for inrush)"),
    ("3V3",  "USB3320 VDD33 + VDDIO (HS)", 3.30, 0.017, 0.017, "USB T4"),
    ("3V3",  "SFP module (T: 1G optical 0.8 W; W: power class II 1.5 W, e.g. 1000BASE-T copper SFP)", 3.30, 0.242, 0.455, "SFF-8431"),
    ("3V3",  "2 clock generators (SERDES refclk) + 25 MHz osc", 3.30, 0.105, 0.205, "EST"),
    ("3V3",  "QSPI flash + EEPROM", 3.30, 0.005, 0.020, "datasheets"),
    ("3V3",  "microSD card (T: read; W: write, SD default-speed max)", 3.30, 0.050, 0.100, "SD spec class"),
    ("3V3",  "LEDs (power, done, 8 user, PHY, SFP)", 3.30, 0.020, 0.040, "calc"),
    ("3V3",  "PMOD user loads (allowance)", 3.30, 0.000, 0.150, "policy"),
    # ---- 5V_SYS direct ----
    ("5V",   "HDMI +5V to sink (DDC/EDID)", 5.00, 0.055, 0.055, "HDMI spec max"),
    ("5V",   "USB-C #2 host VBUS (allowance; switch current-limited)", 5.00, 0.000, 0.100, "policy"),
]

# rail -> (source rail, kind, efficiency or None for LDO)
REG = {
    "1V2":  ("VIN_LV", "buck TLV62569", 0.85),
    "1V35": ("VIN_LV", "buck TLV62569", 0.86),
    "1V8":  ("VIN_LV", "buck TLV62569", 0.82),
    "1V2S": ("1V8",    "LDO TPS7A91", None),
    "2V5":  ("3V3",    "LDO TLV75525/AP2112", None),
    "3V3":  ("5V",     "buck TLV62569 (U2)", 0.90),
}
VOLT = {"1V2": 1.2, "1V35": 1.35, "1V8": 1.8, "1V2S": 1.2, "2V5": 2.5, "3V3": 3.3, "5V": 5.0}
LDO_IQ = 0.001  # A, quiescent current per LDO (order of magnitude)
ETA_12V = 0.90   # LMR33630 12 V -> 5 V at ~1 A
R_MUX = 0.056    # TPS2121 on-resistance (ohm)


def solve(col, vin_lv):
    """vin_lv: '5V' (bench / no slot 3.3 V) or '3V3SLOT' (low-voltage bucks fed from slot 3.3 V)."""
    amps = {r: 0.0 for r in VOLT}
    amps["VIN_LV"] = 0.0
    for rail, _, _, at, aw, _ in LOADS:
        amps[rail] += at if col == 0 else aw
    loss = {}
    # order: LDOs first (they load their source rails), then bucks
    for rail in ("1V2S", "2V5"):
        src, kind, _ = REG[rail]
        i_in = amps[rail] + LDO_IQ
        loss[rail] = (VOLT[src] - VOLT[rail]) * amps[rail]
        amps[src] += i_in
    vlv = 5.0 if vin_lv == "5V" else 3.3
    p_lv = 0.0
    for rail in ("1V2", "1V35", "1V8"):
        p_out = VOLT[rail] * amps[rail]
        p_in = p_out / REG[rail][2]
        loss[rail] = p_in - p_out
        p_lv += p_in
    p3 = VOLT["3V3"] * amps["3V3"]
    p3_in = p3 / REG["3V3"][2]
    loss["3V3"] = p3_in - p3
    p5_loads = 5.0 * amps["5V"]
    p_5v = p3_in + p5_loads + (p_lv if vin_lv == "5V" else 0.0)
    i5 = p_5v / 5.0
    loss["mux5"] = R_MUX * i5 ** 2
    p_5v += loss["mux5"]
    p_slot33 = 0.0
    if vin_lv != "5V":
        i33 = p_lv / 3.3
        loss["mux33"] = R_MUX * i33 ** 2
        p_slot33 = p_lv + loss["mux33"]
    return amps, loss, p_5v, p_slot33


def report():
    print("| Rail | Load | T (mA) | W (mA) | Source |\n|---|---|---|---|---|")
    for rail, name, v, at, aw, src in LOADS:
        print(f"| {rail} | {name} | {at*1000:.0f} | {aw*1000:.0f} | {src} |")
    for arch in ("5V", "3V3SLOT"):
        print(f"\n### Architecture: low-voltage bucks fed from {'5V_SYS' if arch == '5V' else 'slot 3.3 V (in slot)'}")
        print("| | T | W |\n|---|---|---|")
        res = [solve(c, arch) for c in (0, 1)]
        for rail in ("1V2", "1V2S", "1V35", "1V8", "2V5", "3V3", "5V"):
            print(f"| {rail} output current (A) | {res[0][0][rail]:.3f} | {res[1][0][rail]:.3f} |")
        loads_t = sum(v * at for _, _, v, at, _, _ in LOADS)
        loads_w = sum(v * aw for _, _, v, _, aw, _ in LOADS)
        print(f"| Sum of load power (W) | {loads_t:.2f} | {loads_w:.2f} |")
        print(f"| Regulator + mux losses (W) | {sum(res[0][1].values()):.2f} | {sum(res[1][1].values()):.2f} |")

        p12 = [r[2] / ETA_12V for r in res]
        print(f"| 5V_SYS input power (W) = USB-C bench draw | {res[0][2]:.2f} | {res[1][2]:.2f} |")
        print(f"| Slot 12 V draw (W) / (A) | {p12[0]:.2f} / {p12[0]/12:.2f} | {p12[1]:.2f} / {p12[1]/12:.2f} |")
        if arch != "5V":
            print(f"| Slot 3.3 V draw (W) / (A) | {res[0][3]:.2f} / {res[0][3]/3.3:.2f} | {res[1][3]:.2f} / {res[1][3]/3.3:.2f} |")
        tot = [p12[i] + res[i][3] for i in (0, 1)]
        print(f"| **Slot total (W)** vs 10 W | **{tot[0]:.2f}** | **{tot[1]:.2f}** |")


if __name__ == "__main__":
    report()
