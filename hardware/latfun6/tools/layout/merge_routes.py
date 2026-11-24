"""Carry routing from an earlier candidate onto a repaired board (escape vias added, parts moved).
Each net's NEW copper in ROUTED (vs its base BASE) is re-added to TARGET only if all of it passes the exact clearance
check against TARGET (incl. copper merged so far); otherwise the whole net is left out (to be re-routed).
    python merge_routes.py BASE.eprj ROUTED.eprj TARGET.eprj OUT.eprj"""
import sys, os, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

base, routed, target, out = sys.argv[1:5]
k3 = lambda v: round(v, 3)
B0 = ec.Board(base); B1 = ec.Board(routed)
seen_t = set(); seen_v = set()
for t in B0.tracks:
    a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
    seen_t.add((t.net, t.layer, k3(a[0]), k3(a[1]), k3(b[0]), k3(b[1]))); seen_t.add((t.net, t.layer, k3(b[0]), k3(b[1]), k3(a[0]), k3(a[1])))
for v in B0.vias:
    q = lfr.to_mm(v.x, v.y); seen_v.add((v.net, k3(q[0]), k3(q[1])))
NEW = collections.defaultdict(lambda: dict(trk=[], via=[]))
for t in B1.tracks:
    a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
    if (t.net, t.layer, k3(a[0]), k3(a[1]), k3(b[0]), k3(b[1])) not in seen_t and math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
        NEW[t.net]['trk'].append((t.layer, a, b, t.width * lfr.MIL))
for v in B1.vias:
    q = lfr.to_mm(v.x, v.y)
    if (v.net, k3(q[0]), k3(q[1])) not in seen_v:
        NEW[v.net]['via'].append((q, v.dia * lfr.MIL, v.hole * lfr.MIL))
W = lfr.World(target)
kept, dropped = [], []
for net in sorted(NEW):
    d = NEW[net]
    ok = all(lfr._clear_poly(W, net, None, lay, [a, b], w, step=0.004) for lay, a, b, w in d["trk"])
    if ok:
        for (q, dia, hole) in d['via']:
            X, Y = np.array([q[0]]), np.array([q[1]])
            for e in W.near((q[0] - 1, q[1] - 1, q[0] + 1, q[1] + 1)):
                if e['net'] == net:
                    continue
                need = W.EDGE if e['cls'] == 'npth' else W.CLR
                if float(lfr.shape_dist(e['s'], X, Y)[0]) - dia / 2 < need - 1e-4:
                    ok = False; break
            if ok and any(math.hypot(hx - q[0], hy - q[1]) - hole / 2 - hr < W.HH - 1e-4 for hx, hy, hr in W.holes
                          if math.hypot(hx - q[0], hy - q[1]) > 0.02):
                ok = False
            if not ok:
                break
    if ok:
        for lay, a, b, w in d['trk']:
            W.add_track(net, lay, a, b, w)
        for (q, dia, hole) in d['via']:
            W.add_via(net, q[0], q[1], dia, hole)
        kept.append(net)
    else:
        dropped.append(net)
print(f'kept {len(kept)} nets, dropped {len(dropped)}: {dropped}')
p, n = lfr.write_candidate(W, out)
print(f'candidate {p}: {n} records')
