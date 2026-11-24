"""Strip the copper attached to parts' pads before moving them: from each pad, follow same-net track chains on the pad
layer through degree-2 joints, removing segments, until a via, a pad of another part or a branch point (degree >= 3);
a via inside the old pad is removed too when no other track reaches it.
    python strip_attached.py IN.eprj OUT.eprj DES[,DES..]"""
import sys, os, json, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

src, dst, des = sys.argv[1], sys.argv[2], set(sys.argv[3].split(','))
P = ec.Project(src); lines = P.text.split('\n')
W = lfr.World(src)
recs = {json.loads(l)[1]: json.loads(l) for l in lines if l.startswith('["LINE"')}
vias = {json.loads(l)[1]: json.loads(l) for l in lines if l.startswith('["VIA"')}
K = lambda p: (round(p[0], 3), round(p[1], 3))
seg = {r: (a[3], a[4], K(lfr.to_mm(a[5], a[6])), K(lfr.to_mm(a[7], a[8]))) for r, a in recs.items()}
at = collections.defaultdict(set)
for r, (n, l, p, q) in seg.items():
    at[(n, l, p)].add(r); at[(n, l, q)].add(r)
vpos = {r: (a[3], K(lfr.to_mm(a[5], a[6]))) for r, a in vias.items()}
inside = lambda e, p: float(lfr.shape_dist(e['s'], np.array([p[0]]), np.array([p[1]]))[0]) <= 0.001
drop, dropv = set(), set()
for k, e in W.pad.items():
    if k.split('.')[0] not in des or not e['net']:
        continue
    net = e['net']
    for l in e['layers']:
        start = [r for r, (n, ll, p, q) in seg.items() if n == net and ll == l and (inside(e, p) or inside(e, q))]
        stack = list(start)
        while stack:
            r = stack.pop()
            if r in drop:
                continue
            drop.add(r)
            n, ll, p, q = seg[r]
            for end in (p, q):
                if inside(e, end):
                    continue
                if any(vn == net and vp == end for vn, vp in vpos.values()):
                    continue                                    # stop at a via
                if any(inside(o, end) for kk, o in W.pad.items() if o['net'] == net and kk != k):
                    continue                                    # stop at another pad
                nb = at[(n, ll, end)] - {r}
                if len(nb) == 1:
                    stack.extend(nb)
    for r, (vn, vp) in vpos.items():
        if vn == net and inside(e, vp):
            others = [x for x in recs if x not in drop and seg[x][0] == net and vp in (seg[x][2], seg[x][3])]
            if not others:
                dropv.add(r)
print(f'strip: {len(drop)} segments, {len(dropv)} vias')
out = [l for l in lines if not ((l.startswith('["LINE"') or l.startswith('["VIA"')) and json.loads(l)[1] in drop | dropv)]
ec.make_candidate(P, '\n'.join(out), dst)
