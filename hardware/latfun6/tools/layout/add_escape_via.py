"""Give individual pads a dedicated escape via (pcb-layout W6b: the last nets, diagnosed by diag_nets.py).
For each listed pad: nearest legal 0.40/0.20 via spot within --r mm (BGA fields allowed here: exact clearance to all
copper and the hole-to-hole rule still apply), joined by a short stub on the pad's layer (0.1 mm, octilinear).
    python add_escape_via.py IN.eprj OUT.eprj DES.NUM[,DES.NUM...] [--r 1.2]"""
import sys, os, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst, keys = args[0], args[1], args[2].split(',')
R = float(opt('--r', 1.2))
W = lfr.World(src)                         # no fields: in-field spots are allowed for these escapes
Rt = lfr.Router(W, log=lambda *a: None)
for kk in keys:
    k, *sz = kk.split(':')
    VDk, VHk = (float(sz[0]), float(sz[1])) if sz else (0.40, 0.20)
    e = W.pad[k]; net = e['net']; lay = next(iter(e['layers']))
    c = lfr.shape_center(e['s'])
    win = W.win([c], R + 0.3)
    vok = W.via_ok({net}, win, dia=VDk, hole=VHk)
    ys, xs = np.nonzero(vok)
    px = (xs + win[0]) * lfr.G; py = (ys + win[1]) * lfr.G
    dd = np.hypot(px - c[0], py - c[1])
    done = None
    for j in np.argsort(dd)[:40]:
        if dd[j] > R:
            break
        v = (float(px[j]), float(py[j]))
        m = W.mark()
        m0 = lfr.M; lfr.M = 0.01               # short stub between balls: small sampling margin, re-checked below
        try:
            r = Rt.route_net(net, c, v, [lay], 0.1, margin=0.5, bend=0.2, maxexp=40_000)
        finally:
            lfr.M = m0
        if r is None:
            W.rollback(m); continue
        ok = all(lfr._clear_poly(W, net, None, l_, pts, 0.1, step=0.005) for l_, pts in r if len(pts) > 1)
        if not ok:
            W.rollback(m); continue
        W.add_via(net, v[0], v[1], VDk, VHk)
        done = (v, round(float(dd[j]), 2)); break
    print(f'{k:10} {net:14} ' + (f'via at ({done[0][0]:.2f},{done[0][1]:.2f}), {done[1]} mm' if done else 'NO legal via spot'))
print('edge', W.edge_check()[:3])
p, n = lfr.write_candidate(W, dst)
print(f'candidate {p}: {n} records')
