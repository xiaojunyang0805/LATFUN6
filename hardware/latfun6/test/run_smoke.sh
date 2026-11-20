#!/bin/sh
# Usage: sh run_smoke.sh   (needs OSS CAD Suite on PATH)
set -e
cd "$(dirname "$0")"
yosys -q -p "read_verilog pinout_smoke.v; synth_ecp5 -top pinout_smoke -json build/smoke.json"
for dev in 25k 45k; do
  nextpnr-ecp5 --$dev --package CABGA256 --speed 7 --json build/smoke.json --lpf ../board/latfun6.lpf \
     --textcfg build/smoke_$dev.config --lpf-allow-unconstrained 2>build/pnr_$dev.log \
     && echo "PASS nextpnr $dev" || { echo "FAIL nextpnr $dev"; tail -20 build/pnr_$dev.log; exit 1; }
  grep -iE "warning" build/pnr_$dev.log | grep -viE "unconstrained|pmod.\[(5|6)\]" | head -10 || true
done
ecppack --compress build/smoke_25k.config build/smoke_25k.bit && echo "PASS ecppack 25k ($(wc -c < build/smoke_25k.bit) bytes)"
