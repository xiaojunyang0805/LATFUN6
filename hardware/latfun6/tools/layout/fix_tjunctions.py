"""Fix acute T-junctions outside pads/vias (user rule: no acute joints). At a junction where a branch meets a straight
track at < 90 degrees, the branch's last 0.2 mm is bent so it meets the track at 90 degrees (a T always has a <= 90
side). A 0-degree junction (narrower segment lying on a wider one from the same point) drops the covered segment.
Every change is clearance-checked exactly.
    python fix_tjunctions.py IN.eprj OUT.eprj NET:x,y:layer [...]"""
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
P = ec.Project(src)
lines = P.text.split('\n')
recs = {json.loads(l)[1]: json.loads(l) for l in lines if l.startswith('["LINE"')}
W = lfr.World(src)
nid = P.id_alloc('e8r')
to_mil = lambda p: (p[0] / MIL, -p[1] / MIL)
near = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1]) < 0.003
drop, add = set(), []
for net, J, lay in jobs:
    segs = []
    for rid, a in recs.items():
        if a[3] == net and a[4] == lay:
            p, q = lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])
            if near(p, J):
                segs.append((rid, q, a[9] * MIL))
            elif near(q, J):
                segs.append((rid, p, a[9] * MIL))
    best = None
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            u = (segs[i][1][0] - J[0], segs[i][1][1] - J[1]); v = (segs[j][1][0] - J[0], segs[j][1][1] - J[1])
            c = (u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
            ang = math.degrees(math.acos(max(-1, min(1, c))))
            if best is None or ang < best[0]:
                best = (ang, i, j)
    if best is None:
        print(f'{net} {J}: junction not found'); continue
    ang, i, j = best
    if ang < 5:                                   # overlap: drop the narrower / shorter of the two
        a_, b_ = segs[i], segs[j]
        La = math.hypot(a_[1][0] - J[0], a_[1][1] - J[1]); Lb = math.hypot(b_[1][0] - J[0], b_[1][1] - J[1])
        victim = a_ if (a_[2], La) < (b_[2], Lb) else b_
        drop.add(victim[0]); print(f'{net} {J}: overlapping segment {victim[0]} dropped'); continue
    # the trunk = the segment on the far side (straight through), the branch = the one making the acute angle with it
    others = [s for k, s in enumerate(segs) if k not in (i, j)]
    trunk_dir = None
    for k in (i, j):
        s = segs[k]
        for o in others:
            u = (s[1][0] - J[0], s[1][1] - J[1]); v = (o[1][0] - J[0], o[1][1] - J[1])
            c = (u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
            if c < -0.999:                            # s and o are collinear through J: s is trunk, the other is branch
                trunk_dir = (u[0] / math.hypot(*u), u[1] / math.hypot(*u)); br = segs[j if k == i else i]
    if trunk_dir is None:
        print(f'{net} {J}: no straight trunk; skipped'); continue
    rid, B, w = br
    n = (-trunk_dir[1], trunk_dir[0])
    if (B[0] - J[0]) * n[0] + (B[1] - J[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    done = False
    for Lk in (0.2, 0.3, 0.15, 0.1):
        K = (J[0] + n[0] * Lk, J[1] + n[1] * Lk)
        if lfr._clear_poly(W, net, None, lay, [B, K, J], w, step=0.005):
            a = recs[rid]; drop.add(rid)
            for p, q in ((B, K), (K, J)):
                m1, m2 = to_mil(p), to_mil(q)
                add.append(['LINE', nid(), 0, net, lay, round(m1[0], 4), round(m1[1], 4), round(m2[0], 4), round(m2[1], 4), a[9], 0])
            print(f'{net} {J}: branch bent to 90 deg ({Lk} mm)'); done = True; break
    if not done:
        print(f'{net} {J}: no clear bend found')
out = [l for l in lines if not (l.startswith('["LINE"') and json.loads(l)[1] in drop)]
out = ec.insert_after_last(out, [json.dumps(a, separators=(',', ':')) for a in add], ('LINE',))
ec.make_candidate(P, '\n'.join(out), dst)
print('written', dst)
