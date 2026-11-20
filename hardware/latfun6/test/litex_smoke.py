#!/usr/bin/env python3
"""LATFUN6 v0.2 pinout smoke test: a CPU-less LiteX SoC with the real DDR3L controller (LiteDRAM ECP5DDRPHY,
MT41K256M16) and Gigabit Ethernet (LiteEth RGMII + Etherbone), placed and routed on the board pinout.
Passing proves the DDR3 byte lanes, DQS/clock placement and RGMII pins work with the open toolchain.  MIT licence.

Usage (needs LiteX + OSS CAD Suite on PATH):
    python litex_smoke.py [--device LFE5UM5G-45F-8BG381C | LFE5UM5G-85F-8BG381C]
"""
import argparse, pathlib, sys
from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from litex.gen import *
from litex.soc.cores.clock import ECP5PLL
from litex.soc.integration.soc_core import SoCCore
from litex.soc.integration.builder import Builder
from litex.soc.cores.led import LedChaser
from litedram.modules import MT41K256M16
from litedram.phy import ECP5DDRPHY
from liteeth.phy.ecp5rgmii import LiteEthPHYRGMII

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "board"))
import latfun6_platform


class CRG(LiteXModule):
    def __init__(self, platform, sys_clk_freq):
        self.rst = Signal()
        self.cd_init    = ClockDomain()
        self.cd_por     = ClockDomain()
        self.cd_sys     = ClockDomain()
        self.cd_sys2x   = ClockDomain()
        self.cd_sys2x_i = ClockDomain()
        self.stop  = Signal()
        self.reset = Signal()
        clk25 = platform.request("clk25")
        por_count = Signal(16, reset=2**16 - 1)
        por_done = Signal()
        self.comb += [self.cd_por.clk.eq(clk25), por_done.eq(por_count == 0)]
        self.sync.por += If(~por_done, por_count.eq(por_count - 1))
        self.pll = pll = ECP5PLL()
        self.comb += pll.reset.eq(~por_done | self.rst)
        pll.register_clkin(clk25, 25e6)
        pll.create_clkout(self.cd_sys2x_i, 2 * sys_clk_freq)
        pll.create_clkout(self.cd_init, 25e6)
        self.specials += [
            Instance("ECLKSYNCB", i_ECLKI=self.cd_sys2x_i.clk, i_STOP=self.stop, o_ECLKO=self.cd_sys2x.clk),
            Instance("CLKDIVF", p_DIV="2.0", i_ALIGNWD=0, i_CLKI=self.cd_sys2x.clk, i_RST=self.reset,
                     o_CDIVX=self.cd_sys.clk),
            AsyncResetSynchronizer(self.cd_sys, ~pll.locked | self.reset),
        ]


class SmokeSoC(SoCCore):
    def __init__(self, device, sys_clk_freq=75e6):
        platform = latfun6_platform.Platform(device=device)
        self.crg = CRG(platform, sys_clk_freq)
        SoCCore.__init__(self, platform, sys_clk_freq, ident="LATFUN6 v0.2 smoke", cpu_type=None,
                         integrated_sram_size=0, with_uart=False)
        self.add_uartbone(name="serial", baudrate=115200)
        self.ddrphy = ECP5DDRPHY(platform.request("ddram"), sys_clk_freq=sys_clk_freq)
        self.comb += [self.crg.stop.eq(self.ddrphy.init.stop), self.crg.reset.eq(self.ddrphy.init.reset)]
        self.add_sdram("sdram", phy=self.ddrphy, module=MT41K256M16(sys_clk_freq, "1:2"), l2_cache_size=0)
        self.ethphy = LiteEthPHYRGMII(clock_pads=platform.request("eth_clocks"), pads=platform.request("eth"),
                                      tx_delay=0e-9, rx_delay=0e-9)
        self.add_etherbone(phy=self.ethphy, ip_address="192.168.1.50", data_width=32)  # 32-bit => UDP/IP datapath in sys domain
        self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="LFE5UM5G-45F-8BG381C")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).resolve().parent / "build" / "litex"))
    a = ap.parse_args()
    soc = SmokeSoC(a.device)
    Builder(soc, output_dir=a.out, compile_software=False, csr_csv=None).build(run=False)
    # Run the toolchain directly (LiteX's Windows .bat wrapper can fail spuriously).
    import subprocess
    gw = pathlib.Path(a.out) / "gateware"
    dev = {"LFE5UM5G-45F": "--um5g-45k", "LFE5UM5G-85F": "--um5g-85k"}[a.device[:12]]
    subprocess.run(["yosys", "-q", "-l", "latfun6_platform.rpt", "latfun6_platform.ys"], cwd=gw, check=True)
    r = subprocess.run(["nextpnr-ecp5", "--json", "latfun6_platform.json", "--lpf", "latfun6_platform.lpf",
                        "--textcfg", "latfun6_platform.config", dev, "--package", "CABGA381", "--speed", "8",
                        "--timing-allow-fail", "--seed", "1"], cwd=gw, capture_output=True, text=True)
    (gw / "nextpnr.log").write_text(r.stdout + r.stderr)
    fm = [l for l in (r.stdout + r.stderr).splitlines() if "Max frequency" in l][-4:]
    print("nextpnr exit", r.returncode, *fm, sep=chr(10))
    sys.exit(r.returncode)
