"""Hand fixes for the three DDR joints the chamfer pass could not fix (see layout worknote §6, DDR3):
  - DQ5 / DQS_N0: the Top track passes over its own U30 ball before reaching the fan-out via at 45/90 degrees ->
    end the track on the ball pad, delete the now-redundant fan-out stub + via.
  - CKE at R340.1: vertical pad stub + horizontal run (90 degrees) -> one 45-degree leg from the pad.
    python ddr_fixjoints.py IN.eprj OUT.eprj"""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
import eprj_core as ec

MIL = 0.0254
src, dst = sys.argv[1], sys.argv[2]
P = ec.Project(src)
lines = P.text.split('\n')
to_mm = lambda x, y: (x * MIL, -y * MIL)
to_mil = lambda x, y: (x / MIL, -y / MIL)
J = lambda a: json.dumps(a, separators=(',', ':'), ensure_ascii=False)


def near(p, q, tol=0.003):
    return math.hypot(p[0] - q[0], p[1] - q[1]) < tol


out, removed = [], []
recs = []
for l in lines:
    if l.startswith('["LINE"') or l.startswith('["VIA"'):
        recs.append(json.loads(l))
nid = P.id_alloc('e8r')


def fix_end_on_ball(net, via, ball):
    """drop LINE/VIA records of `net` that touch `via` (track ends at the via, stub, the via itself); return the far
    end of the track that came in, so it can be continued onto the ball"""
    drop, far = set(), None
    for a in recs:
        if a[0] == 'LINE' and a[3] == net:
            p, q = to_mm(a[5], a[6]), to_mm(a[7], a[8])
            if near(p, via) or near(q, via):
                o = q if near(p, via) else p
                drop.add(a[1])
                if not near(o, ball):
                    far = (o, a[4], a[9])
        elif a[0] == 'VIA' and a[3] == net and near(to_mm(a[5], a[6]), via):
            drop.add(a[1])
    return drop, far


drops = set(); adds = []
for net, via, ball in (('DDRAM_DQ5', (75.2, 21.2), (75.6, 21.6)), ('DDRAM_DQS_N0', (74.4, 26.0), (74.8, 25.6))):
    d, far = fix_end_on_ball(net, via, ball)
    # DQS_N0: the incoming track ends in two tiny pieces next to the via; walk back to the long segment
    if net == 'DDRAM_DQS_N0':
        for a in recs:
            if a[0] == 'LINE' and a[3] == net:
                p, q = to_mm(a[5], a[6]), to_mm(a[7], a[8])
                if near(p, (74.5, 26.05), 0.01) or near(q, (74.5, 26.05), 0.01):
                    d.add(a[1])
                    o = q if near(p, (74.5, 26.05), 0.01) else p
                    if not near(o, (74.45, 26.05), 0.01):
                        far = (o, a[4], a[9])
    drops |= d
    (fx, fy), lay, w = far
    a, b = to_mil(fx, fy), to_mil(*ball)
    adds.append(['LINE', nid(), 0, net, lay, round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4), w, 0])
    print(f'{net}: dropped {sorted(d)}, new leg {(round(fx, 3), round(fy, 3))} -> {ball}')
# CKE at R340.1
pad, corner, far = (70.5, 18.533), (70.5, 19.014), (68.728, 19.014)
for a in recs:
    if a[0] == 'LINE' and a[3] == 'DDRAM_CKE':
        p, q = to_mm(a[5], a[6]), to_mm(a[7], a[8])
        if (near(p, corner, 0.005) or near(q, corner, 0.005)):
            drops.add(a[1]); lay, w = a[4], a[9]
d = corner[1] - pad[1]
mid = (pad[0] - d, corner[1])
for p, q in ((pad, mid), (mid, far)):
    a, b = to_mil(*p), to_mil(*q)
    adds.append(['LINE', nid(), 0, 'DDRAM_CKE', lay, round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4), w, 0])
print(f'CKE: 45-degree leg {pad} -> {mid} -> {far}')
for l in lines:
    if (l.startswith('["LINE"') or l.startswith('["VIA"')) and json.loads(l)[1] in drops:
        continue
    out.append(l)
out = ec.insert_after_last(out, [J(a) for a in adds], ('LINE', 'VIA'))
ec.make_candidate(P, '\n'.join(out), dst)
print('dropped', len(drops), 'added', len(adds), '->', dst)
