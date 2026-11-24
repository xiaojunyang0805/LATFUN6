"""Plane delivery (layout worknote §3): every SMD pad of NET without a same-net via gets one, placed at the nearest legal
spot (0.40/0.20 mm via, outside the BGA fields) and joined by a short stub on the pad's layer, clearance-checked by
lfr's router. The vias reach the In1/In4 GND planes once the pours exist.
    python gndvias.py IN.eprj OUT.eprj [--net GND] [--r 1.6] [--w 0.2]"""
import sys, os, math, time
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst = args[0], args[1]
NET = opt('--net', 'GND'); R = float(opt('--r', 1.6)); WS = float(opt('--w', 0.2))
SKIP = set((opt('--skip') or '').split(','))          # designators left out
ONLY = set((opt('--only') or '').split(',')) - {''}   # designators handled (default all)
YMAX = float(opt('--ymax', 1e9))                      # vias only above this y (mm, y down): J12 tab kept free
VD, VH = 0.40, 0.20
W = lfr.World(src)
for d in ('U5', 'U30'):
    W.add_field(d)
Rt = lfr.Router(W, log=lambda *a: None)
vias = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == NET]
trk = [e['s'] for e in W.sh if e['cls'] == 'trk' and e['net'] == NET]


def served(e):
    V = vias + [(v[1], v[2]) for v in W.new_vias if v[0] == NET]
    if V:
        X = np.array([v[0] for v in V]); Y = np.array([v[1] for v in V])
        if (lfr.shape_dist(e['s'], X, Y) <= VD / 2 + 0.01).any():
            return True
    for s in trk:                      # a stub from the pad to a via
        for (ax, ay), (bx, by) in (((s[1], s[2]), (s[3], s[4])), ((s[3], s[4]), (s[1], s[2]))):
            if lfr.shape_dist(e['s'], np.array([ax]), np.array([ay]))[0] <= 0.01 and \
                    any(math.hypot(bx - v[0], by - v[1]) < 0.02 for v in V):
                return True
    return False


pads = [(k, e) for k, e in W.pad.items() if e['net'] == NET and len(e['layers']) == 1
        and k.split('.')[0] not in SKIP and (not ONLY or k.split('.')[0] in ONLY)]
todo = [(k, e) for k, e in pads if not served(e)]
print(f'{NET}: {len(pads)} SMD pads, {len(todo)} without a via')
t0 = time.time(); ok = fail = 0; failed = []
for k, e in todo:
    lay = next(iter(e['layers']))
    c = lfr.shape_center(e['s'])
    win = W.win([c], R + 0.2)
    vok = W.via_ok({NET}, win, dia=VD, hole=VH)
    ix0, iy0 = win[0], win[1]
    vok[(np.arange(win[1], win[3] + 1) * lfr.G > YMAX), :] = False
    ys, xs = np.nonzero(vok)
    if len(xs) == 0:
        fail += 1; failed.append(k); continue
    px = (xs + ix0) * lfr.G; py = (ys + iy0) * lfr.G
    dd = np.hypot(px - c[0], py - c[1])
    done = False
    for j in np.argsort(dd)[:25]:
        if dd[j] > R:
            break
        v = (float(px[j]), float(py[j]))
        m = W.mark()
        r = Rt.route_net(NET, c, v, [lay], WS, margin=0.6, bend=0.3, maxexp=60_000)
        if r is None:
            W.rollback(m); continue
        Ls = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for _, pts in r for p, q in zip(pts, pts[1:]))
        if Ls > 2.2 * dd[j] + 0.3:
            W.rollback(m); continue
        W.add_via(NET, v[0], v[1], VD, VH)
        done = True; break
    if done:
        ok += 1
    else:
        fail += 1; failed.append(k)
print(f'placed {ok} vias, {fail} pads without a legal spot within {R} mm: {failed[:40]} ({time.time() - t0:.0f} s)')
print('edge check:', W.edge_check()[:5])
p, n = lfr.write_candidate(W, dst)
print(f'candidate {p}: {n} records')
