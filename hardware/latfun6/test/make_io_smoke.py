#!/usr/bin/env python3
"""Generate an all-I/O smoke top from board/latfun6.json (every non-DDR signal driven as an output, differential
pairs via their _p side) plus a matching LPF, then place-and-route it on the 45F and 85F.  MIT licence.
Usage: python make_io_smoke.py   (needs OSS CAD Suite on PATH)"""
import json, pathlib, re, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
board = json.loads((here.parent / "board" / "latfun6.json").read_text())
out = here / "build" / "io_smoke"; out.mkdir(parents=True, exist_ok=True)
sigs = {n: s for n, s in board["signals"].items()
        if not n.startswith("ddram_") and not (s["io"] == "LVCMOS33D" and n.endswith("_n")) and n != "clk_25mhz"}
port = lambda n: re.sub(r"[\[\]]", "_", n).strip("_")
v = ["module io_smoke(input wire clk_25mhz,"] + [f"  output wire {port(n)}," for n in sigs]
v[-1] = v[-1].rstrip(",")
v += [");", "  reg [31:0] c = 0; always @(posedge clk_25mhz) c <= c + 1;"]
v += [f"  assign {port(n)} = c[{i % 32}] ^ c[{(i * 7 + 3) % 32}];" for i, n in enumerate(sigs)] + ["endmodule"]
(out / "io_smoke.v").write_text("\n".join(v) + "\n")
lpf = [f'LOCATE COMP "clk_25mhz" SITE "{board["signals"]["clk_25mhz"]["ball"]}";', 'IOBUF PORT "clk_25mhz" IO_TYPE=LVCMOS33;']
for n, s in sigs.items():
    lpf += [f'LOCATE COMP "{port(n)}" SITE "{s["ball"]}";', f'IOBUF PORT "{port(n)}" IO_TYPE={s["io"]};']
(out / "io_smoke.lpf").write_text("\n".join(lpf) + "\n")
subprocess.run(["yosys", "-q", "-p", "read_verilog io_smoke.v; synth_ecp5 -top io_smoke -json io_smoke.json"], cwd=out, check=True)
rc = 0
for dev in ("um5g-45k", "um5g-85k"):
    r = subprocess.run(["nextpnr-ecp5", f"--{dev}", "--package", "CABGA381", "--speed", "8", "--json", "io_smoke.json",
                        "--lpf", "io_smoke.lpf", "--textcfg", f"io_smoke_{dev}.config"], cwd=out, capture_output=True, text=True)
    log = r.stdout + r.stderr; (out / f"pnr_{dev}.log").write_text(log)
    io = [l.strip() for l in log.splitlines() if "TRELLIS_IO:" in l][-1:]
    print(f"{'PASS' if r.returncode == 0 else 'FAIL'} {dev}: {len(sigs)+1} I/O", *io)
    rc |= r.returncode
sys.exit(rc)
