"""Shove step for a boxed pad (pcb-layout W6b): choose the via spot within --r mm of the pad whose blockers are fewest
and all removable (track segments of non-critical, non-power nets; never pads, vias, critical or power copper), remove
exactly those segments, and place the via + an octilinear stub on the pad's layer. The cut nets are re-joined
afterwards by route_rest (track ends are connection points). Prints the cut nets.
    python shove_via.py IN.eprj OUT.eprj PAD[,PAD..] [--r 1.0] [--dia 0.25] [--hole 0.15]"""
import sys, os, json, math, re
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst, keys = args[0], args[1], args[2].split(',')
R = float(opt('--r', 1.0)); VD = float(opt('--dia', 0.25)); VH = float(opt('--hole', 0.15))
CRIT = re.compile(r'^(GND|DDRAM_|GPDI_(D\d|CLK)_|ETH_MDI\d_|USB2?_D[PN]|SMA_|PCIE_(HD|RX|TX|REFCLK)|REFCLK|SFP_(TX|RX)D|HD[TR]X)')
MIL = 0.0254
P = ec.Project(src); lines = P.text.split('\n')
recs = {json.loads(l)[1]: json.loads(l) for l in lines if l.startswith('["LINE"')}
W = lfr.World(src)
B = ec.Board(src)
PWR = lambda n: B.net_class.get(n) == 'PWR'
seg_of = {}
for rid, a in recs.items():
    seg_of[rid] = (a[3], a[4], lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8]), a[9] * MIL)
drop = set(); cut = set(); add = []
nid = P.id_alloc('e9s')
to_mil = lambda p: (round(p[0] / MIL, 4), round(-p[1] / MIL, 4))


def seg_dist(c, s):
    return lfr.pt_seg(c[0], c[1], (s[2], s[3])) - s[4] / 2


def blockers(net, lay, spot, stub):
    """objects violating clearance for a via at spot (all layers) + stub segment on lay; None if a hard blocker"""
    hard = False; soft = set()
    for e in W.near((spot[0] - 1.0, spot[1] - 1.0, spot[0] + 1.0, spot[1] + 1.0)):
        if e['net'] == net and e['cls'] != 'npth':
            continue
        d = float(lfr.shape_dist(e['s'], np.array([spot[0]]), np.array([spot[1]]))[0]) - VD / 2
        need = W.EDGE if e['cls'] == 'npth' else W.CLR
        if d < need:
            if e['cls'] == 'trk' and e['net'] and not CRIT.match(e['net']) and not PWR(e['net']):
                soft.add(e['src'] if e['src'] != 'file' else None)
                soft.add(('trk', e['net'], e['s']))
            else:
                return None
    for (hx, hy, hr) in W.holes:
        if math.hypot(hx - spot[0], hy - spot[1]) - hr - VH / 2 < W.HH:
            return None
    # stub on lay
    for e in W.near((min(stub[0][0], stub[1][0]) - 0.5, min(stub[0][1], stub[1][1]) - 0.5,
                     max(stub[0][0], stub[1][0]) + 0.5, max(stub[0][1], stub[1][1]) + 0.5)):
        if e['net'] == net or lay not in e['layers']:
            continue
        xs = np.linspace(stub[0][0], stub[1][0], 12); ys = np.linspace(stub[0][1], stub[1][1], 12)
        d = float(lfr.shape_dist(e['s'], xs, ys).min()) - 0.05
        need = W.TT if e['cls'] == 'trk' else W.CLR
        if d < need:
            if e['cls'] == 'trk' and e['net'] and not CRIT.match(e['net']) and not PWR(e['net']):
                soft.add(('trk', e['net'], e['s']))
            else:
                return None
    return {x for x in soft if isinstance(x, tuple)}


for key in keys:
    e = W.pad[key]; net = e['net']; lay = min(e['layers'])
    c = lfr.shape_center(e['s'])
    best = None
    for dx in np.arange(-R, R + 1e-9, 0.05):
        for dy in np.arange(-R, R + 1e-9, 0.05):
            spot = (c[0] + dx, c[1] + dy)
            dist = math.hypot(dx, dy)
            if dist > R:
                continue
            # stub: from the pad centre straight (or 45) to the spot
            bl = blockers(net, lay, spot, (c, spot))
            if bl is None:
                continue
            score = (len({b[1] for b in bl}), len(bl), dist)
            if best is None or score < best[0]:
                best = (score, spot, bl)
    if best is None:
        print(f'{key}: no spot with only removable blockers'); continue
    score, spot, bl = best
    # map blocker shapes to LINE records
    for b in bl:
        s = b[2]
        for rid, sg in seg_of.items():
            if sg[0] == b[1] and abs(sg[2][0] - s[1]) < 1e-3 and abs(sg[2][1] - s[2]) < 1e-3 and \
               abs(sg[3][0] - s[3]) < 1e-3 and abs(sg[3][1] - s[4]) < 1e-3:
                drop.add(rid); cut.add(b[1])
    m1, m2 = to_mil(c), to_mil(spot)
    add.append(['VIA', nid(), 0, net, '', m2[0], m2[1], round(VH / MIL, 4), round(VD / MIL, 4), 0, None, None, 0])
    if math.hypot(spot[0] - c[0], spot[1] - c[1]) > 1e-3:
        add.append(['LINE', nid(), 0, net, lay, m1[0], m1[1], m2[0], m2[1], round(0.1 / MIL, 4), 0])
    print(f'{key} ({net}): via at ({spot[0]:.2f},{spot[1]:.2f}), cut {sorted({b[1] for b in bl})} ({len(bl)} segments)')
# VIA record layout: copy an existing via record's shape for the fields we do not set
tmpl = next(json.loads(l) for l in lines if l.startswith('["VIA"'))
fixed = []
for a in add:
    if a[0] == 'VIA':
        v = list(tmpl); v[1], v[3], v[5], v[6] = a[1], a[3], a[5], a[6]
        v[7], v[8] = a[7], a[8]
        fixed.append(v)
    else:
        fixed.append(a)
out = [l for l in lines if not (l.startswith('["LINE"') and json.loads(l)[1] in drop)]
out = ec.insert_after_last(out, [json.dumps(a, separators=(',', ':')) for a in fixed], ('LINE', 'VIA'))
ec.make_candidate(P, '\n'.join(out), dst)
print('cut nets:', ','.join(sorted(cut)))
