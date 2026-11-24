"""Strict connectivity (EDA-like): a track joins another object only through an END POINT lying on it (track centre
line within tol, or inside a pad/via shape). Crossing/overlapping bodies without an end point do not connect.
Reports, per net, the components that hold no pad of the main group.
    python strict_conn.py BOARD.eprj [--tol 0.002] [--all]"""
import sys, os, collections, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr

args = sys.argv[1:]
src = args[0]
TOL = float(args[args.index('--tol') + 1]) if '--tol' in args else 0.002
W = lfr.World(src); B = W.B
par = {}
def find(a):
    par.setdefault(a, a)
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a
def uni(a, b): par[find(a)] = find(b)

bynet = collections.defaultdict(lambda: {'trk': [], 'pv': []})
for t in B.tracks:
    a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
    bynet[t.net]['trk'].append((('t', t.id), t.layer, a, b))
for e in W.sh:
    if e['cls'] == 'pad' and e['net']:
        bynet[e['net']]['pv'].append((('p', e['src']), e['layers'], e['s']))
    elif e['cls'] == 'via' and e['net']:
        bynet[e['net']]['pv'].append((('v', e['src']), e['layers'], e['s']))
res = {}
for net, d in bynet.items():
    T, PV = d['trk'], d['pv']
    for k, *_ in T: find(k)
    for k, *_ in PV: find(k)
    for k, lay, a, b in T:
        for p in (a, b):
            for k2, lay2, a2, b2 in T:
                if k2 != k and lay2 == lay and lfr.pt_seg(p[0], p[1], (a2, b2)) <= TOL:
                    uni(k, k2)
            for k2, lays, s in PV:
                if lay in lays and float(lfr.shape_dist(s, np.array([p[0]]), np.array([p[1]]))[0]) <= TOL:
                    uni(k, k2)
    # pad-via overlap (in-pad vias)
    for i in range(len(PV)):
        for j in range(i + 1, len(PV)):
            k1, l1, s1 = PV[i]; k2, l2, s2 = PV[j]
            if set(l1) & set(l2):
                c = lfr.shape_center(s2)
                if float(lfr.shape_dist(s1, np.array([c[0]]), np.array([c[1]]))[0]) <= 0:
                    uni(k1, k2)
    comps = collections.defaultdict(list)
    for k, *_ in T + PV:
        comps[find(k)].append(k)
    res[net] = list(comps.values())
bad = 0
for net, cs in sorted(res.items()):
    if net == 'GND' and '--all' not in args:
        continue
    withpad = [c for c in cs if any(k[0] == 'p' for k in c)]
    nopad = [c for c in cs if not any(k[0] == 'p' for k in c)]
    if len(withpad) > 1 or nopad:
        bad += 1
        print(f'{net}: {len(withpad)} pad groups, {len(nopad)} pad-less fragments')
        for c in withpad[1:]:
            print('    pads', [k[1] for k in c if k[0] == 'p'][:4])
        for c in nopad:
            print('    frag', [k[1] for k in c][:6])
print('nets with problems:', bad)
