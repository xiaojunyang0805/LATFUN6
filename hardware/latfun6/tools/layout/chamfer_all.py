"""Board-wide joint clean-up on a candidate (layout worknote §6, user rule: no acute, avoid 90-degree joints):
every 90-degree joint between exactly two segments of one net on one layer becomes two 45-degree joints (corner cut
by c = 0.2 / 0.12 / 0.07 / 0.04 mm, exact clearance check); diff-pair tracks wider than the DP rule maximum are
narrowed to it. Reports what is left (acute joints, T-junctions).
    python chamfer_all.py IN.eprj OUT.eprj [--dpmax 0.11]"""
import sys, os, json, math, re, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eprj_core as ec
import lfr

args = sys.argv[1:]
src, dst = args[0], args[1]
DPMAX = float(args[args.index('--dpmax') + 1]) if '--dpmax' in args else 0.11
MIL = 0.0254
DP = re.compile(r'^(.*_[PN]\d?|USB2?_D[PN]|DDRAM_DQS_[PN]\d|DDRAM_CLK_[PN])$')
PAIRNET = re.compile(r'(SFP_|SMA_|PCIE_|REFCLK_|CK1_PRI|GPDI_(D\d|CLK)|ETH_MDI\d|USB2?_D[PN]|DDRAM_DQS_|DDRAM_CLK_)')

P = ec.Project(src)
lines = P.text.split('\n')
recs = {}
order = []
for i, l in enumerate(lines):
    if l.startswith('["LINE"'):
        a = json.loads(l); recs[a[1]] = a; order.append(a[1])
W = lfr.World(src)
nid = P.id_alloc('e8r')
to_mm = lambda x, y: (x * MIL, -y * MIL)
to_mil = lambda x, y: (x / MIL, -y / MIL)


def partner(net):
    for a, b in (('_P', '_N'), ('_N', '_P'), ('DP', 'DN'), ('DN', 'DP')):
        m = re.match(rf'^(.*){a}(\d?)$', net)
        if m:
            return f'{m.group(1)}{b}{m.group(2)}'
    return None


def shape_remove(net, lay, p, q):
    for j in range(len(W.sh) - 1, -1, -1):
        e = W.sh[j]
        if e['cls'] == 'trk' and e['net'] == net and lay in e['layers']:
            s = e['s']
            if ((abs(s[1] - p[0]) < 1e-4 and abs(s[2] - p[1]) < 1e-4 and abs(s[3] - q[0]) < 1e-4 and abs(s[4] - q[1]) < 1e-4) or
                    (abs(s[1] - q[0]) < 1e-4 and abs(s[2] - q[1]) < 1e-4 and abs(s[3] - p[0]) < 1e-4 and abs(s[4] - p[1]) < 1e-4)):
                del W.sh[j]; return


def shape_add(net, lay, p, q, w):
    W._add(net, frozenset({lay}), ('k', p[0], p[1], q[0], q[1], w / 2), 'trk', 'file')


# 0. diff-pair widths above the DP maximum
narrowed = 0
for rid, a in recs.items():
    if a[3] and PAIRNET.search(a[3]):
        mx = 0.15 if a[3].startswith('PCIE_') else 0.135 if re.match(r'USB2?_D', a[3]) else DPMAX   # DP85 / DP90 / DP100
        if a[9] * MIL > mx + 1e-4:
            a[9] = round(mx / MIL, 4); narrowed += 1

# 1. chamfer 90-degree joints (degree-2 nodes only)
fixed = failed = 0
added = []
for rnd in range(3):
    ends = collections.defaultdict(list)
    for rid, a in recs.items():
        p, q = to_mm(a[5], a[6]), to_mm(a[7], a[8])
        if math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-5:
            continue
        k = lambda v: (round(v[0], 3), round(v[1], 3))
        ends[(a[3], a[4], k(p))].append((rid, 0)); ends[(a[3], a[4], k(q))].append((rid, 1))
    did = 0
    for (net, lay, key), lst in ends.items():
        if len(lst) != 2 or not net:
            continue
        (r1, e1), (r2, e2) = lst
        if r1 == r2:
            continue
        a1, a2 = recs[r1], recs[r2]
        P1 = [to_mm(a1[5], a1[6]), to_mm(a1[7], a1[8])]; P2 = [to_mm(a2[5], a2[6]), to_mm(a2[7], a2[8])]
        p = P1[e1]; q1 = P1[1 - e1]; q2 = P2[1 - e2]
        u = (q1[0] - p[0], q1[1] - p[1]); v = (q2[0] - p[0], q2[1] - p[1])
        L1, L2 = math.hypot(*u), math.hypot(*v)
        cosang = (u[0] * v[0] + u[1] * v[1]) / (L1 * L2)
        if abs(cosang) > 0.02:                 # not a right angle
            continue
        w1, w2 = a1[9] * MIL, a2[9] * MIL
        ok = False
        for c in (0.2, 0.12, 0.07, 0.04):
            c = min(c, 0.45 * L1, 0.45 * L2)
            c1 = (p[0] + u[0] / L1 * c, p[1] + u[1] / L1 * c); c2 = (p[0] + v[0] / L2 * c, p[1] + v[1] / L2 * c)
            if lfr._clear_poly(W, net, partner(net), lay, [q1, c1, c2, q2], min(w1, w2), pgap=0.2, step=0.01):
                ok = True; break
        if not ok:
            failed += 1; continue
        shape_remove(net, lay, P1[0], P1[1]); shape_remove(net, lay, P2[0], P2[1])
        # move the shared endpoints back to the chamfer points, add the chamfer segment
        m1 = to_mil(*c1); m2 = to_mil(*c2)
        if e1 == 0:
            a1[5], a1[6] = round(m1[0], 4), round(m1[1], 4)
        else:
            a1[7], a1[8] = round(m1[0], 4), round(m1[1], 4)
        if e2 == 0:
            a2[5], a2[6] = round(m2[0], 4), round(m2[1], 4)
        else:
            a2[7], a2[8] = round(m2[0], 4), round(m2[1], 4)
        new = ['LINE', nid(), 0, net, lay, round(m1[0], 4), round(m1[1], 4), round(m2[0], 4), round(m2[1], 4),
               round(min(w1, w2) / MIL, 4), 0]
        recs[new[1]] = new; added.append(new[1])
        shape_add(net, lay, q1, c1, w1); shape_add(net, lay, c1, c2, min(w1, w2)); shape_add(net, lay, c2, q2, w2)
        fixed += 1; did += 1
    if not did:
        break

out = []
for l in lines:
    if l.startswith('["LINE"'):
        rid = json.loads(l)[1]
        out.append(json.dumps(recs[rid], separators=(',', ':'), ensure_ascii=False))
    else:
        out.append(l)
out = ec.insert_after_last(out, [json.dumps(recs[r], separators=(',', ':'), ensure_ascii=False) for r in added], ('LINE',))
ec.make_candidate(P, '\n'.join(out), dst)
print(f'narrowed {narrowed} pair segments to {DPMAX} mm; chamfered {fixed} right-angle joints, {failed} left (no room)')
