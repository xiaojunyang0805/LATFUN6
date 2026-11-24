"""Remove acute bends inside one path (degree-2 vertices, user rule: no acute joints): the vertex V between A and B is
replaced by the straight A-B segment when that is clear, otherwise cut by two points P (on VA) and Q (on VB) at equal
distance t from V (two obtuse corners). Exact clearance check per change.
    python fix_hairpins.py IN.eprj OUT.eprj NET:x,y:layer [...]"""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eprj_core as ec
import lfr

src, dst = sys.argv[1], sys.argv[2]
jobs = []
for a in sys.argv[3:]:
    n, xy, l = a.split(':'); x, y = (float(v) for v in xy.split(',')); jobs.append((n, (x, y), int(l)))
MIL = 0.0254
P = ec.Project(src); lines = P.text.split('\n')
recs = {json.loads(l)[1]: json.loads(l) for l in lines if l.startswith('["LINE"')}
W = lfr.World(src)
nid = P.id_alloc('e9h')
to_mil = lambda p: (round(p[0] / MIL, 4), round(-p[1] / MIL, 4))
near = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1]) < 0.003
drop, add = set(), []
for net, V, lay in jobs:
    segs = []
    for rid, a in recs.items():
        if rid in drop or a[3] != net or a[4] != lay:
            continue
        p, q = lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])
        if near(p, V):
            segs.append((rid, q, a[9]))
        elif near(q, V):
            segs.append((rid, p, a[9]))
    if len(segs) != 2:
        print(f'{net} {V}: degree {len(segs)}, skipped'); continue
    (ra, A, wa), (rb, Bp, wb) = segs
    w = min(wa, wb) * MIL
    la = math.hypot(A[0] - V[0], A[1] - V[1]); lb = math.hypot(Bp[0] - V[0], Bp[1] - V[1])
    cands = []
    if any(e['net'] == net and e['cls'] in ('pad', 'via') and lay in e['layers'] and
           float(lfr.shape_dist(e['s'], __import__('numpy').array([V[0]]), __import__('numpy').array([V[1]]))[0]) < 0.25
           for e in W.near((V[0] - 1, V[1] - 1, V[0] + 1, V[1] + 1))):
        print(f'{net} {V}: touches a pad/via, skipped'); continue
    for t in (0.6, 0.4, 0.25, 0.15, 0.1):
        if t < min(la, lb):
            Pp = (V[0] + (A[0] - V[0]) * t / la, V[1] + (A[1] - V[1]) * t / la)
            Qq = (V[0] + (Bp[0] - V[0]) * t / lb, V[1] + (Bp[1] - V[1]) * t / lb)
            cands.append([A, Pp, Qq, Bp])
    done = False
    for pl in cands:
        # never let the replacement make a new acute angle at A / B with their other segments: accept straight A-B
        # only when both ends are pads/vias or collinear continuations; the cut variant keeps A and B directions
        if lfr._clear_poly(W, net, None, lay, pl, w, step=0.005):
            drop |= {ra, rb}
            for p, q in zip(pl, pl[1:]):
                m1, m2 = to_mil(p), to_mil(q)
                add.append(['LINE', nid(), 0, net, lay, m1[0], m1[1], m2[0], m2[1], min(wa, wb), 0])
            print(f'{net} {V}: {"straightened" if len(pl) == 2 else "cut"}'); done = True; break
    if not done:
        print(f'{net} {V}: no clear fix')
out = [l for l in lines if not (l.startswith('["LINE"') and json.loads(l)[1] in drop)]
out = ec.insert_after_last(out, [json.dumps(a, separators=(',', ':')) for a in add], ('LINE',))
ec.make_candidate(P, '\n'.join(out), dst)
print('written', dst)
