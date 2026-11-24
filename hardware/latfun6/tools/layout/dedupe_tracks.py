"""Remove redundant copper: a track segment that lies entirely on another segment of the same net and layer that is at
least as wide (collinear, both endpoints on it). Then report the acute joints that remain OUTSIDE pads and vias (a
joint inside a pad or via of its own net is covered by that copper).
    python dedupe_tracks.py IN.eprj OUT.eprj"""
import sys, os, json, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

src, dst = sys.argv[1], sys.argv[2]
MIL = 0.0254
P = ec.Project(src)
lines = P.text.split('\n')
recs = [json.loads(l) for l in lines if l.startswith('["LINE"')]
segs = collections.defaultdict(list)
for a in recs:
    p, q = lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])
    segs[(a[3], a[4])].append((a[1], p, q, a[9] * MIL))


def on(p, a, b, tol=0.002):
    return lfr.pt_seg(p[0], p[1], (a, b)) <= tol


drop = set()
for key, ss in segs.items():
    ss = sorted(ss, key=lambda s: -math.hypot(s[2][0] - s[1][0], s[2][1] - s[1][1]))
    for i, (ida, pa, qa, wa) in enumerate(ss):
        if ida in drop:
            continue
        for idb, pb, qb, wb in ss[i + 1:]:
            if idb in drop or wb > wa + 1e-6:
                continue
            if on(pb, pa, qa) and on(qb, pa, qa):
                drop.add(idb)

# partially overlapping collinear segments (same net/layer/width class): merge into one segment spanning both
def collinear(a1, a2, b1, b2, tol=0.002):
    return lfr.pt_seg(b1[0], b1[1], (a1, a2)) <= tol or lfr.pt_seg(b2[0], b2[1], (a1, a2)) <= tol


merged = []
for key, ss in segs.items():
    live = [s for s in ss if s[0] not in drop]
    changed = True
    while changed:
        changed = False
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                ia, pa, qa, wa = live[i]; ib, pb, qb, wb = live[j]
                da = (qa[0] - pa[0], qa[1] - pa[1]); La = math.hypot(*da)
                db = (qb[0] - pb[0], qb[1] - pb[1]); Lb = math.hypot(*db)
                if La < 1e-6 or Lb < 1e-6 or abs(wa - wb) > 1e-6:
                    continue
                if abs(da[0] * db[1] - da[1] * db[0]) / (La * Lb) > 1e-3:
                    continue                                     # not parallel
                if lfr.pt_seg(pb[0], pb[1], ((pa[0] - da[0] * 100, pa[1] - da[1] * 100), (qa[0] + da[0] * 100, qa[1] + da[1] * 100))) > 0.002:
                    continue                                     # parallel but offset
                if not collinear(pa, qa, pb, qb) and not collinear(pb, qb, pa, qa):
                    continue                                     # same line, disjoint
                u = (da[0] / La, da[1] / La)
                pts = [pa, qa, pb, qb]
                ts = [(p[0] - pa[0]) * u[0] + (p[1] - pa[1]) * u[1] for p in pts]
                lo, hi = pts[ts.index(min(ts))], pts[ts.index(max(ts))]
                drop.add(ia); drop.add(ib)
                nidm = f'{ia}m'
                live[i] = (nidm, lo, hi, wa); del live[j]
                merged.append((nidm, key, lo, hi, wa)); changed = True
                break
            if changed:
                break
out = [l for l in lines if not (l.startswith('["LINE"') and json.loads(l)[1] in drop)]
keep_m = {m[0]: m for m in merged}
final = {}
for key, ss in segs.items():
    pass
nidf = P.id_alloc('e9d')
newl = []
alive = set()
for m in merged:
    alive.add(m[0])
# only merged segments that were not merged again later survive
later = {m[0] for m in merged}
for m in merged:
    nm, key, lo, hi, wa = m
    if any(m2[0] != nm and m2[0].startswith(nm) for m2 in merged):
        continue
    mil1 = (round(lo[0] / MIL, 4), round(-lo[1] / MIL, 4)); mil2 = (round(hi[0] / MIL, 4), round(-hi[1] / MIL, 4))
    newl.append(json.dumps(['LINE', nidf(), 0, key[0], key[1], mil1[0], mil1[1], mil2[0], mil2[1], round(wa / MIL, 4), 0], separators=(',', ':')))
out = ec.insert_after_last(out, newl, ('LINE',))
ec.make_candidate(P, '\n'.join(out), dst)
print(f'removed {len(drop)} redundant segments, {len(newl)} merged segments written')

# acute joints outside own pads/vias
W = lfr.World(dst)
cover = collections.defaultdict(list)
for e in W.sh:
    if e['cls'] in ('pad', 'via') and e['net']:
        cover[e['net']].append(e)
S = collections.defaultdict(list)
for t in W.B.tracks:
    a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
    if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-5:
        S[(t.net, t.layer)].append((a, b))
real = []
for (net, lay), ss in S.items():
    E = collections.defaultdict(list)
    k = lambda p: (round(p[0], 3), round(p[1], 3))
    for a, b in ss:
        E[k(a)].append((b[0] - a[0], b[1] - a[1])); E[k(b)].append((a[0] - b[0], a[1] - b[1]))
    for v, dirs in E.items():
        worst = 180
        for i in range(len(dirs)):
            for j in range(i + 1, len(dirs)):
                u, w = dirs[i], dirs[j]
                c = (u[0] * w[0] + u[1] * w[1]) / (math.hypot(*u) * math.hypot(*w))
                worst = min(worst, math.degrees(math.acos(max(-1, min(1, c)))))
        if worst < 89:
            inside = any(lay in e['layers'] and float(lfr.shape_dist(e['s'], np.array([v[0]]), np.array([v[1]]))[0]) <= 0
                         for e in cover.get(net, []))
            if not inside:
                real.append((net, lay, v, round(worst, 1), len(dirs)))
print(f'acute joints outside pads/vias: {len(real)}')
for r in real[:40]:
    print('  ', r)
