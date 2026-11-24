"""P/N length matching of differential pairs (EDA DRC 'Differential Pair Error: length tolerance'): serpentine bumps on
the shorter leg (lfr.tune_pair), clearance-checked against everything; the pairs' own copper is lifted into the editable
set, everything else stays fixed.
    python tune_pairs.py IN.eprj OUT.eprj [--tol 0.05] [--pairs P1/N1,P2/N2] [--report]"""
import sys, os, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
SRC, OUT = args[0], args[1]
TOL = float(opt('--tol', 0.05))
MIL = 0.0254
DEFAULT = ('DDRAM_CLK_P/DDRAM_CLK_N,DDRAM_DQS_P0/DDRAM_DQS_N0,DDRAM_DQS_P1/DDRAM_DQS_N1,'
           'GPDI_D0_P/GPDI_D0_N,GPDI_D1_P/GPDI_D1_N,GPDI_D2_P/GPDI_D2_N,GPDI_CLK_P/GPDI_CLK_N,'
           'ETH_MDI0_P/ETH_MDI0_N,ETH_MDI1_P/ETH_MDI1_N,ETH_MDI2_P/ETH_MDI2_N,ETH_MDI3_P/ETH_MDI3_N,'
           'SFP_TD_P/SFP_TD_N,SFP_RD_P/SFP_RD_N,CK1_PRI_P/CK1_PRI_N,SMA_TX_P/SMA_TX_N,SMA_RX_P/SMA_RX_N,'
           'USB2_DP/USB2_DN,USB_DP/USB_DN')
PAIRS = [tuple(x.split('/')) for x in (opt('--pairs') or DEFAULT).split(',')]
NETS = {n for p in PAIRS for n in p}
W = lfr.World(SRC, ripup_prefix=('',), ripup_nets=lambda n: n in NETS)
for t in W.B.tracks:
    if t.net in NETS:
        (x1, y1), (x2, y2) = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
        if math.hypot(x2 - x1, y2 - y1) > 1e-6:
            W.add_track(t.net, t.layer, (x1, y1), (x2, y2), t.width * MIL)
for v in W.B.vias:
    if v.net in NETS:
        x, y = lfr.to_mm(v.x, v.y)
        W.add_via(v.net, x, y, v.dia * MIL, v.hole * MIL)
L0 = lfr.net_lengths(W, NETS)
for P, N in PAIRS:
    if P in L0:
        print(f'{P:14} P {L0[P]:7.2f}  N {L0.get(N, 0):7.2f}  skew {L0[P] - L0.get(N, 0):+7.3f}')
if '--report' in args:
    sys.exit()
res = {}
for P, N in PAIRS:
    if P not in L0:
        continue
    prev = None
    for rnd in range(6):                      # step the bump height down where tall bumps no longer fit
        for hmax in (0.6, 0.9, 1.2, 0.45, 0.3, 0.22):
            sk = lfr.tune_pair(W, P, N, tol=TOL, hmax=hmax, log=lambda *a: None)
            if abs(sk) <= TOL:
                break
        if abs(sk) <= TOL or (prev is not None and abs(sk) >= abs(prev) - 1e-3):
            break
        prev = sk
    for c, top, g, m in ((0.07, 0.2, 0.2, 0.1), (0.05, 0.15, 0.15, 0.05)):     # last resort: denser, smaller bumps
        for hmax in (0.6, 0.45, 0.35, 0.28, 0.2):
            if abs(sk) > TOL:
                sk = lfr.tune_pair(W, P, N, tol=TOL, c=c, top=top, gapb=g, hmax=hmax, margin=m, log=lambda *a: None)
    res[P] = sk
    print(f'  {P:14} -> skew {sk:+.3f}', flush=True)
# collapse degenerate bump corners (segments < 10 um): drop the segment, snap its neighbours' ends onto one point
while True:
    tiny = [i for i, (n, l, (x1, y1, x2, y2), w) in enumerate(W.new_tracks) if math.hypot(x2 - x1, y2 - y1) < 0.01]
    if not tiny:
        break
    i = tiny[0]
    net, lay, (x1, y1, x2, y2), w = W.new_tracks[i]
    W.remove_new_track(i)
    fix = []
    for j, (n, l, (a1, b1, a2, b2), wj) in enumerate(W.new_tracks):
        if n == net and l == lay:
            e1 = math.hypot(a1 - x2, b1 - y2) < 1e-4; e2 = math.hypot(a2 - x2, b2 - y2) < 1e-4
            if e1 or e2:
                fix.append((j, (x1, y1) if e1 else (a1, b1), (x1, y1) if e2 else (a2, b2), wj))
    for j, p, q, wj in sorted(fix, reverse=True):
        W.remove_new_track(j)
    for j, p, q, wj in fix:
        W.add_track(net, lay, p, q, wj)
ac, rt = lfr.acute_check(W, NETS)
print(f'acute {len(ac)}, right {len(rt)}')
print('NOT MATCHED (> 0.127):', {p: round(s, 3) for p, s in res.items() if abs(s) > 0.127} or 'none')
p, n = lfr.write_candidate(W, OUT)
print('candidate', p, n)
