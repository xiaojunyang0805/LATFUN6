"""Negotiated congestion (PathFinder) over every unprotected net of the board (layout worknote W6b).
FIXED board = protected copper (SERDES, DDR3, BGA fan-out, GND vias, routed MDI/USB pairs); every other net is routed
island to island (MST over pads / fixed track ends / vias), starting from the CURRENT routing as initial solution.
Each iteration rips and re-routes whole nets; overlaps with other soft nets cost pres x count (growing) + history;
fixed copper is hard. Board-wide count rasters (fixed and dynamic, per layer and width class) are kept and updated
incrementally, so a route costs a window slice + the compiled A* (astar_nb).
    python negotiate_all.py FIXED.eprj CURRENT.eprj OUT.eprj [--iters 30]"""
import sys, os, math, time, re, json, copy, random, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec, eprj_check
import lfr, astar_nb
from lfr import G

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
FIXED, CUR, OUT = args[0], args[1], args[2]
ITERS = int(opt('--iters', 30))
TOP, BOT, IN2, IN5 = 1, 2, 16, 19          # 8-layer stack: signal layers Top / In2 / In5 / Bottom
RL = [TOP, IN2, IN5, BOT]
LI = {l: i for i, l in enumerate(RL)}
LC = {TOP: 1.0, IN2: 1.1, IN5: 1.1, BOT: 1.2}
if '--in3' in args:                         # In3 (PWR plane layer) for signals too: cuts the pour locally
    RL.append(17); LI[17] = len(RL) - 1; LC[17] = 1.3
SKIPN = set((opt('--skip') or '').split(','))
CLS = {'w': 0.127 / 2, 'p': 0.20 / 2, 'n': 0.09 / 2}           # half widths of the width classes
WOF = {'w': 0.127, 'p': 0.20, 'n': 0.09}
M, MN = lfr.M, 0.002
VD, VH = 0.40, 0.20
log = lambda *a: print(*a, flush=True)

W = lfr.World(FIXED)
W.add_field('U5'); W.add_field('U30')
NX, NY = W.NX, W.NY
B0 = ec.Board(FIXED)
isl0 = eprj_check.islands(B0)
infield = lambda q, mg=0.3: any(f[0] - mg <= q[0] <= f[2] + mg and f[1] - mg <= q[1] <= f[3] + mg for f in W.fields)
PWR = lambda n: B0.net_class.get(n) == 'PWR'


def partner(net):
    for x_, y_ in (('_P', '_N'), ('_N', '_P'), ('DP', 'DN'), ('DN', 'DP')):
        m = re.match(r'^(.*)' + x_ + r'(\d?)$', net)
        if m and re.match(r'^(GPDI_|ETH_MDI|USB)', net):
            return m.group(1) + y_ + m.group(2)
    return None


# ---------------------------------------------------------------- rasters
def stamp(arr, s, R, val, box=None):
    """add val to arr (board grid) where a point is closer than R to shape s"""
    b = lfr.shape_bbox(s)
    jx0 = max(int(math.floor((b[0] - R) / G)), 0); jx1 = min(int(math.ceil((b[2] + R) / G)), NX - 1)
    jy0 = max(int(math.floor((b[1] - R) / G)), 0); jy1 = min(int(math.ceil((b[3] + R) / G)), NY - 1)
    if jx1 < jx0 or jy1 < jy0:
        return
    X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
    m = lfr.shape_dist(s, X, Y) < R
    arr[jy0:jy1 + 1, jx0:jx1 + 1] += m.astype(arr.dtype) * val


def radius(cls_, kind, c):
    """clearance radius around a shape of kind (trk / pad / via / npth) for a centreline of class c"""
    m = MN if c == 'n' else M
    hw = CLS[c]
    base = W.TT if kind == 'trk' else W.EDGE if kind == 'npth' else W.CLR
    return base + hw + m


FX = {(l, c): np.zeros((NY, NX), np.int16) for l in RL for c in CLS}
FV = np.zeros((NY, NX), np.int16)                         # via forbidden (fixed): copper, holes, fields, edge
t0 = time.time()
for e in W.sh:
    for l in RL:
        if l in e['layers']:
            for c in CLS:
                stamp(FX[(l, c)], e['s'], radius(c, e['cls'], c), 1)
    # via: any layer copper (tracks with the general rule)
    if any(l in e['layers'] for l in W.layers):
        Rv = (W.EDGE if e['cls'] == 'npth' else W.CLR) + VD / 2 + 0.001
        stamp(FV, e['s'], Rv, 1)
for (hx, hy, hr) in W.holes:
    stamp(FV, ('c', hx, hy, 0.0), VH / 2 + hr + W.HH, 1)
for c in CLS:
    edge_bad = (W.edge_dist < W.EDGE + CLS[c] + (MN if c == 'n' else M))
    for l in RL:
        FX[(l, c)][edge_bad] += 1000
FV[W.edge_dist < W.EDGE + VD / 2 + M] += 1000
for (fx0, fy0, fx1, fy1) in W.fields:
    FV[int(fy0 / G):int(fy1 / G) + 1, int(fx0 / G):int(fx1 / G) + 1] += 1000
ZONE = np.zeros((NY, NX), bool)
for (fx0, fy0, fx1, fy1) in W.fields:
    ZONE[int(math.ceil(fy0 / G)):int(fy1 / G) + 1, int(math.ceil(fx0 / G)):int(fx1 / G) + 1] = True
log(f'fixed rasters: {len(W.sh)} shapes, {time.time() - t0:.0f} s')
OWN = collections.defaultdict(list)                        # fixed shapes per net
for e in W.sh:
    if e['net']:
        OWN[e['net']].append(e)

DY = {(l, c): np.zeros((NY, NX), np.int16) for l in RL for c in CLS}
DV = np.zeros((NY, NX), np.int16)
HIST = {l: np.zeros((NY, NX), np.float32) for l in RL}


def stamp_net(d, val):
    for lay, (x1, y1, x2, y2), w in d['trk']:
        s = ('k', x1, y1, x2, y2, w / 2)
        for c in CLS:
            stamp(DY[(lay, c)], s, radius(c, 'trk', c), val)
        stamp(DV, s, W.CLR + VD / 2 + M, val)
    for (x, y) in d['via']:
        s = ('c', x, y, VD / 2)
        for l in RL:
            for c in CLS:
                stamp(DY[(l, c)], s, radius(c, 'via', c), val)
        stamp(DV, s, VD + W.HH, val)


# ---------------------------------------------------------------- nets and their islands (on the fixed board)
def island_points(x):
    out = []
    for p in x['pads']:
        k = f'{p.des}.{p.num}'
        if k in W.pad:
            out.append((lfr.shape_center(W.pad[k]['s']), [l for l in RL if l in W.pad[k]['layers']]))
    for t in x['tracks']:
        for (xx, yy) in ((t.x1, t.y1), (t.x2, t.y2)):
            q = lfr.to_mm(xx, yy)
            if not infield(q) and t.layer in RL:
                out.append((q, [t.layer]))
    for v in x['vias']:
        out.append((lfr.to_mm(v.x, v.y), list(RL)))
    return [o for o in out if o[1]]


NETS = {}
for net, g in isl0.items():
    if not net or net == 'GND' or net in SKIPN:
        continue
    gs = [island_points(x) for x in g if x['pads']]
    gs = [x for x in gs if x]
    if len(gs) >= 2:
        NETS[net] = gs
log(f'{len(NETS)} nets to negotiate')

# initial solution: CURRENT minus FIXED copper
k3 = lambda v: round(v, 3)
fixed_t = set(); fixed_v = set()
for t in B0.tracks:
    a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
    fixed_t.add((t.net, t.layer, k3(a[0]), k3(a[1]), k3(b[0]), k3(b[1]))); fixed_t.add((t.net, t.layer, k3(b[0]), k3(b[1]), k3(a[0]), k3(a[1])))
for v in B0.vias:
    q = lfr.to_mm(v.x, v.y); fixed_v.add((v.net, k3(q[0]), k3(q[1])))
NEW = {n: dict(trk=[], via=[]) for n in NETS}
BC = ec.Board(CUR)
for t in BC.tracks:
    if t.net in NETS:
        a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
        if (t.net, t.layer, k3(a[0]), k3(a[1]), k3(b[0]), k3(b[1])) not in fixed_t and t.layer in RL:
            NEW[t.net]['trk'].append((t.layer, (a[0], a[1], b[0], b[1]), t.width * lfr.MIL))
for v in BC.vias:
    if v.net in NETS:
        q = lfr.to_mm(v.x, v.y)
        if (v.net, k3(q[0]), k3(q[1])) not in fixed_v:
            NEW[v.net]['via'].append(q)
for n in NETS:
    stamp_net(NEW[n], 1)
log(f'initial solution from {os.path.basename(CUR)}: {sum(len(d["trk"]) for d in NEW.values())} tracks, '
    f'{sum(len(d["via"]) for d in NEW.values())} vias')


# ---------------------------------------------------------------- routing one net
def own_counts(net, win, c, l):
    ix0, iy0, ix1, iy1 = win
    a = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), np.int16)
    for e in OWN.get(net, []):
        if l in e['layers']:
            b = e['bbox']; R = radius(c, e['cls'], c)
            if b[2] < ix0 * G - R or b[0] > ix1 * G + R or b[3] < iy0 * G - R or b[1] > iy1 * G + R:
                continue
            tmp = np.zeros((NY, NX), np.int16) if False else None
            jx0 = max(int(math.floor((b[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b[2] + R) / G)), ix1)
            jy0 = max(int(math.floor((b[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b[3] + R) / G)), iy1)
            if jx1 < jx0 or jy1 < jy0:
                continue
            X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
            a[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] += (lfr.shape_dist(e['s'], X, Y) < R).astype(np.int16)
    return a


def own_via_counts(net, win):
    ix0, iy0, ix1, iy1 = win
    a = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), np.int16)
    for e in OWN.get(net, []):
        b = e['bbox']; R = (W.EDGE if e['cls'] == 'npth' else W.CLR) + VD / 2 + 0.001
        jx0 = max(int(math.floor((b[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b[2] + R) / G)), ix1)
        jy0 = max(int(math.floor((b[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b[3] + R) / G)), iy1)
        if jx1 < jx0 or jy1 < jy0:
            continue
        X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
        a[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] += (lfr.shape_dist(e['s'], X, Y) < R).astype(np.int16)
    return a


def route_edge(net, a, al, b, bl, pres, hard, margin, wcls, hist=1.0):
    win = W.win([a, b], margin)
    ix0, iy0, ix1, iy1 = win
    sl = (slice(iy0, iy1 + 1), slice(ix0, ix1 + 1))
    zone = ZONE[sl]
    frees, cost, wide, dyn_used = [], [], [], []
    pn = partner(net)
    pst = {}                                    # partner copper: P/N gap >= 0.203 (soft, hard in the final pass)
    if pn and pn in NEW:
        for l in RL:
            for c in ('n', wcls):
                arr = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), np.int16)
                for lay, (x1, y1, x2, y2), w in NEW[pn]['trk']:
                    if lay != l:
                        continue
                    s_ = ('k', x1, y1, x2, y2, w / 2); R = 0.206 + CLS[c] + (MN if c == 'n' else M); b_ = lfr.shape_bbox(s_)
                    jx0 = max(int(math.floor((b_[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b_[2] + R) / G)), ix1)
                    jy0 = max(int(math.floor((b_[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b_[3] + R) / G)), iy1)
                    if jx1 < jx0 or jy1 < jy0:
                        continue
                    X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
                    arr[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] += (lfr.shape_dist(s_, X, Y) < R).astype(np.int16)
                pst[(l, c)] = arr
    for l in RL:
        fw = (FX[(l, wcls)][sl] - own_counts(net, win, wcls, l)) == 0
        fn = ((FX[(l, 'n')][sl] - own_counts(net, win, 'n', l)) == 0) & zone
        dw = DY[(l, wcls)][sl]; dn = DY[(l, 'n')][sl]
        if pst:
            dw = dw + pst[(l, wcls)]; dn = dn + pst[(l, 'n')]
        if hard:
            fw &= dw == 0; fn &= dn == 0
        fr = fw | fn
        frees.append(fr); wide.append(fw)
        cnt = np.where(fw, dw, dn).astype(np.float32)
        dyn_used.append(cnt)
        cost.append(np.maximum(LC[l] + hist * HIST[l][sl] + pres * cnt, 0.3).astype(np.float32))
    vok = (FV[sl] - own_via_counts(net, win)) == 0
    if hard:
        vok &= DV[sl] == 0
    viac = ((pres / G) * (DV[sl] > 0)).astype(np.float32)
    ownv = [lfr.shape_center(e['s']) for e in OWN.get(net, []) if e['cls'] == 'via'] + list(NEW[net]['via'])
    cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    H_, W_ = vok.shape
    for (vx, vy) in ownv:
        cx, cy = cell((vx, vy))
        if 0 <= cx < W_ and 0 <= cy < H_:
            vok[cy, cx] = True
            for f in frees:
                f[cy, cx] = True
    (sx, sy), (tx, ty) = cell(a), cell(b)
    dd = math.hypot(a[0] - b[0], a[1] - b[1])
    if pres == 0.0 and hist == 0.0:            # pure-length fallback: cheap search, big budget
        HW, MX = 1.8, 20_000_000
    else:                                       # congestion-aware: bounded budget
        HW, MX = (1.8, 4_000_000) if dd > 20 else (1.5, 2_000_000)
    for i, l in enumerate(RL):
        if l in al:
            frees[i][sy, sx] = True
        if l in bl:
            frees[i][ty, tx] = True
    ones = np.ones((len(RL), 8), bool)
    FR = np.ascontiguousarray(np.stack(frees)); CO = np.ascontiguousarray(np.stack(cost))
    slay = np.array([l in al for l in RL]); glay = np.array([l in bl for l in RL])
    path = []
    if dd > 10 and not (pres == 0.0 and hist == 0.0):
        # global route on a coarse grid (F x F fine cells), then the detailed search inside its corridor
        F = 8
        L_, H_, W_ = FR.shape
        Hc, Wc = -(-H_ // F), -(-W_ // F)
        pad = lambda a, v: np.pad(a, [(0, 0)] * (a.ndim - 2) + [(0, Hc * F - a.shape[-2]), (0, Wc * F - a.shape[-1])],
                                  constant_values=v)
        FRp = pad(FR, False).reshape(L_, Hc, F, Wc, F)
        COp = pad(np.where(FR, CO, 0.0).astype(np.float32), 0.0).reshape(L_, Hc, F, Wc, F)
        nfree = FRp.sum(axis=(2, 4))
        frc = nfree >= 2
        coc = np.where(nfree > 0, COp.sum(axis=(2, 4)) / np.maximum(nfree, 1), 1.0).astype(np.float32)
        vokc = pad(vok, False).reshape(Hc, F, Wc, F).any(axis=(1, 3))
        vcc = np.zeros((Hc, Wc), np.float32)
        csx, csy, ctx, cty = sx // F, sy // F, tx // F, ty // F
        for i in range(L_):
            if slay[i]:
                frc[i, csy, csx] = True
            if glay[i]:
                frc[i, cty, ctx] = True
        cpath = astar_nb.astar(np.ascontiguousarray(frc), np.ascontiguousarray(coc), np.ascontiguousarray(vokc),
                               csx, csy, slay, ones, ctx, cty, glay, ones, 0.3 / (G * F), 1.2 / (G * F), 1.5, 2_000_000, vcc)
        if len(cpath):
            corr = np.zeros((Hc, Wc), bool)
            for (x, y, i) in cpath:
                corr[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3] = True       # +-2 coarse cells (~ +-1.2 mm incl. cell)
            corr_f = np.repeat(np.repeat(corr, F, axis=0), F, axis=1)[:H_, :W_]
            FRc = np.ascontiguousarray(FR & corr_f[None])
            for i in range(L_):
                if slay[i]:
                    FRc[i, sy, sx] = True
                if glay[i]:
                    FRc[i, ty, tx] = True
            path = astar_nb.astar(FRc, CO, np.ascontiguousarray(vok & corr_f), sx, sy, slay, ones, tx, ty, glay, ones,
                                  0.3 / G, 1.2 / G, 1.5, 3_000_000, viac)
    if len(path) == 0:
        path = astar_nb.astar(FR, CO, np.ascontiguousarray(vok), sx, sy, slay, ones, tx, ty, glay, ones,
                              0.3 / G, 1.2 / G, HW, MX, viac)
    if len(path) == 0:
        return None
    path = [(int(x), int(y), int(i)) for x, y, i in path]
    over = 0
    for (x, y, li) in path:
        if dyn_used[li][y, x] > 0:
            over += 1; HIST[RL[li]][y + iy0, x + ix0] += 1.0
    runs = [[path[0]]]
    for p in path[1:]:
        (runs[-1].append(p) if p[2] == runs[-1][-1][2] else runs.append([p]))
    trk, via = [], []
    for ri, run in enumerate(runs):
        li = run[0][2]; lay = RL[li]
        segs = []
        for p, q in zip(run, run[1:]):
            k = (q[0] - p[0], q[1] - p[1])
            wd = WOF[wcls] if (wide[li][p[1], p[0]] and wide[li][q[1], q[0]]) else WOF['n']
            if segs and segs[-1][0] == k and segs[-1][1] == wd:
                segs[-1][3] = q
            else:
                segs.append([k, wd, p, q])
        for si, sg in enumerate(segs):
            p = ((sg[2][0] + ix0) * G, (sg[2][1] + iy0) * G); q = ((sg[3][0] + ix0) * G, (sg[3][1] + iy0) * G)
            if ri == 0 and si == 0:
                p = a
            if ri == len(runs) - 1 and si == len(segs) - 1:
                q = b
            if math.hypot(q[0] - p[0], q[1] - p[1]) > 1e-6:
                trk.append((lay, (p[0], p[1], q[0], q[1]), sg[1]))
        if ri + 1 < len(runs):
            vx, vy = (run[-1][0] + ix0) * G, (run[-1][1] + iy0) * G
            if not any(math.hypot(vx - ox, vy - oy) < 0.04 for ox, oy in ownv):
                via.append((vx, vy))
    return trk, via, over


FAILED_EDGES = []


def route_net(net, pres, hard=False):
    stamp_net(NEW[net], -1)
    NEW[net] = dict(trk=[], via=[])
    groups = NETS[net]
    wcls = 'p' if PWR(net) else 'w'
    tree = [0]; rest = list(range(1, len(groups)))
    over = 0; fails = 0
    while rest:
        best = None
        for i in tree:
            for j in rest:
                for (pa, la) in groups[i]:
                    for (pb, lb) in groups[j]:
                        d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                        if best is None or d < best[0]:
                            best = (d, j, pa, la, pb, lb)
        d, j, pa, la, pb, lb = best
        r = None
        if not hard:          # negotiation: bounded searches; an edge that fails stays out this iteration (space free)
            for margin, wc in ((3.0, wcls), (8.0, 'w')):
                r = route_edge(net, pa, la, pb, lb, pres, False, margin, wc)
                if r is not None:
                    break
        else:                 # final pass: everything else hard, pure length, big budget
            for margin, wc in ((3.0, wcls), (8.0, wcls), (8.0, 'w'), (14.0, 'w')):
                r = route_edge(net, pa, la, pb, lb, 0.0, True, margin, wc, hist=0.0)
                if r is not None:
                    break
        if r is None:
            fails += 1; FAILED_EDGES.append((net, pa, la, pb, lb))
        else:
            trk, via, ov = r
            NEW[net]['trk'] += trk; NEW[net]['via'] += via; over += ov
        tree.append(j); rest.remove(j)
    stamp_net(NEW[net], 1)
    return dict(over=over, fails=fails)


# ---------------------------------------------------------------- negotiation
order = sorted(NETS)
if '--diag' in args:                  # one hard pass over the initial solution: list edges that cannot route
    for n in order:
        r = route_net(n, 1.0)
    log(f'failed edges: {len(FAILED_EDGES)}')
    for n, pa, la, pb, lb in FAILED_EDGES:
        log(f'  {n:16} ({pa[0]:.2f},{pa[1]:.2f}) {la} -> ({pb[0]:.2f},{pb[1]:.2f}) {lb}  d={math.hypot(pa[0]-pb[0], pa[1]-pb[1]):.1f}')
    sys.exit()
pres = 1.0; best = None; res = {}
for it in range(ITERS):
    t1 = time.time()
    for n in random.Random(it).sample(order, len(order)):
        res[n] = route_net(n, pres)
    conf = [n for n in order if res[n]['over']]; fl = [n for n in order if res[n]['fails']]
    tot = sum(res[n]['over'] for n in order); nf = sum(res[n]['fails'] for n in order)
    log(f'iter {it + 1}: pres {pres:.1f} overlap {tot} conflicted {len(conf)} failed edges {nf} ({len(fl)} nets) '
        f'({time.time() - t1:.0f} s)')
    score = (len(conf) + len(fl)) * 100 + tot
    if best is None or score < best[0]:
        best = (score, copy.deepcopy(NEW), copy.deepcopy(res))
        json.dump({n: NEW[n] for n in order}, open(OUT + '.routes.json', 'w'))
    if not conf and not fl:
        break
    pres = min(pres * 1.5, 500.0)
# restore best, then hard re-route of whatever still conflicts or fails
for n in order:
    stamp_net(NEW[n], -1)
NEW.clear(); NEW.update(best[1]); res = best[2]
for n in order:
    stamp_net(NEW[n], 1)
for n in [n for n in order if res[n]['over'] or res[n]['fails']]:
    res[n] = route_net(n, pres, hard=True)
fl = {n: res[n]['fails'] for n in order if res[n]['fails']}
log(f'final: nets with unrouted edges {len(fl)}: {fl}')
for n in order:
    for lay, (x1, y1, x2, y2), w in NEW[n]['trk']:
        W.add_track(n, lay, (x1, y1), (x2, y2), w)
    for (x, y) in NEW[n]['via']:
        W.add_via(n, x, y, VD, VH)
log(f'edge {W.edge_check()[:3]}')
p, nrec = lfr.write_candidate(W, OUT)
log(f'candidate {p}: {nrec} records')
