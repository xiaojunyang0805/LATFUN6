"""Move U5's perimeter decap ring outward (user decision 2026-11-23): each listed bottom-side part is shifted
perpendicular to its U5 side by the first legal amount of --shifts (mm), legal = its pads clear every other part's
pads by >= 0.6 mm and all copper of other nets by the general rule; copper attached to its pads (GND stub + via from
gndvias / perimeter_gnd) is stripped first. Writes OUT with the parts moved.
    python decapmove.py IN.eprj OUT.eprj DES[,DES...] [--shifts 1.4,1.2,1.6,1.0,1.8,2.0]"""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst, des = args[0], args[1], args[2].split(',')
SHIFTS = [float(v) for v in (opt('--shifts') or '1.4,1.2,1.6,1.0,1.8,2.0').split(',')]
MIL = 0.0254
P = ec.Project(src); lines = P.text.split('\n')
W = lfr.World(src); W.add_field('U5')
fx0, fy0, fx1, fy1 = W.fields[0]
mine = {k for k in W.pad if k.split('.')[0] in des}
# 1. strip copper touching the movers' pads (and vias at those stubs' far ends)
recs = [json.loads(l) for l in lines if l.startswith('["LINE"') or l.startswith('["VIA"')]
drop, ends = set(), []
for a in recs:
    if a[0] != 'LINE':
        continue
    p, q = lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])
    for k in mine:
        e = W.pad[k]
        if a[3] != e['net']:
            continue
        for u, v in ((p, q), (q, p)):
            if lfr.shape_dist(e['s'], np.array([u[0]]), np.array([u[1]]))[0] <= 0.01:
                drop.add(a[1]); ends.append((a[3], v))
for a in recs:
    if a[0] == 'VIA':
        c = lfr.to_mm(a[5], a[6])
        if any(n == a[3] and math.hypot(c[0] - v[0], c[1] - v[1]) < 0.02 for n, v in ends):
            drop.add(a[1])
lines = [l for l in lines if not ((l.startswith('["LINE"') or l.startswith('["VIA"')) and json.loads(l)[1] in drop)]
tmp = dst + '.strip.eprj'
ec.make_candidate(P, '\n'.join(lines), tmp)
print(f'stripped {len(drop)} records attached to {len(des)} parts')
# 2. legal shift per part (sequential: earlier movers become obstacles)
W = lfr.World(tmp)
B = ec.Board(tmp)
placed = []
moves = []
for d in des:
    pads = [(k, W.pad[k]) for k in W.pad if k.split('.')[0] == d]
    pts = [lfr.shape_center(e['s']) for _, e in pads]
    cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
    side = 'R' if cx > fx1 else 'L' if cx < fx0 else 'B' if cy > fy1 else 'T'
    ux, uy = {'R': (1, 0), 'L': (-1, 0), 'B': (0, 1), 'T': (0, -1)}[side]
    others = [e for e in W.sh if e['net'] is not None and e['src'] not in {k for k, _ in pads}
              and 2 in e['layers'] or e['cls'] == 'via']
    chosen = None
    for sh in SHIFTS:
        dx, dy = ux * sh, uy * sh
        ok = True
        for k, e in pads:
            b = lfr.shape_bbox(e['s']); bb = (b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy)
            X, Y = np.meshgrid(np.linspace(bb[0], bb[2], 5), np.linspace(bb[1], bb[3], 5))
            for o in W.near((bb[0] - 0.7, bb[1] - 0.7, bb[2] + 0.7, bb[3] + 0.7)):
                if o['src'] in {kk for kk, _ in pads}:
                    continue
                if 2 not in o['layers'] and o['cls'] != 'via':
                    continue
                need = 0.6 if o['cls'] == 'pad' else (W.EDGE if o['cls'] == 'npth' else W.CLR)
                if o['cls'] in ('trk', 'via') and o['net'] == e['net']:
                    continue
                if float(lfr.shape_dist(o['s'], X, Y).min()) < need:
                    ok = False; break
            if ok and any(not (q[2] + 0.6 < bb[0] or q[0] - 0.6 > bb[2] or q[3] + 0.6 < bb[1] or q[1] - 0.6 > bb[3]) for q in placed):
                ok = False
            if not ok:
                break
        if ok:
            chosen = (sh, dx, dy); break
    if chosen is None:
        print(f'{d}: no legal outward shift; stays'); continue
    sh, dx, dy = chosen
    for k, e in pads:
        b = lfr.shape_bbox(e['s']); placed.append((b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy))
    c = B.comp[B.byd[d]]
    moves.append(f"{d}:{c[4] * MIL + dx:.3f}:{-c[5] * MIL + dy:.3f}:{c[6] or 0}:{c[3]}")
    print(f'{d} ({side}): shifted {sh} mm')
open(dst + '.moves.txt', 'w').write(' '.join(moves))
print('moves ->', dst + '.moves.txt')
