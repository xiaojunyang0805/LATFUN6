"""Per-net blocker diagnosis (pcb-layout W6b step 2: flood fill, name the blockers).
For each net: flood fill from its U5 ball (or own fan-out via) over the free cells of every signal layer (0.10 mm track,
0.09 mm necked inside the BGA fields), changing layer at legal via spots and at its own vias. Reports whether the
destination island is reachable, the size of the reachable region, and the objects that wall it in (nets / kinds of
the copper on the region boundary), counted.
    python diag_nets.py BOARD.eprj NET[,NET...] [--margin 10] [--png DIR]"""
import sys, os, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import ndimage
import eprj_core as ec, eprj_check
import lfr
from lfr import G

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src = args[0]; nets = args[1].split(',')
MARGIN = float(opt('--margin', 10)); PNG = opt('--png')
RL = [1, 16, 19, 2]
W = lfr.World(src); W.add_field('U5'); W.add_field('U30')
B = ec.Board(src); isl = eprj_check.islands(B)
infield = lambda q: any(f[0] - 0.3 <= q[0] <= f[2] + 0.3 and f[1] - 0.3 <= q[1] <= f[3] + 0.3 for f in W.fields)


def pts(x):
    out = []
    for p in x['pads']:
        k = f'{p.des}.{p.num}'
        if k in W.pad:
            out.append((k, lfr.shape_center(W.pad[k]['s']), [l for l in RL if l in W.pad[k]['layers']]))
    for v in x['vias']:
        out.append(('via', lfr.to_mm(v.x, v.y), list(RL)))
    for t in x['tracks']:
        for (xx, yy) in ((t.x1, t.y1), (t.x2, t.y2)):
            q = lfr.to_mm(xx, yy)
            if not infield(q) and t.layer in RL:
                out.append(('trk', q, [t.layer]))
    return out


for net in nets:
    g = [x for x in isl.get(net, []) if x['pads']]
    if len(g) < 2:
        print(f'{net}: joined already'); continue
    u5 = [x for x in g if any(p.des == 'U5' for p in x['pads'])]
    a_isl = u5[0] if u5 else g[0]
    others = [x for x in g if x is not a_isl]
    A = pts(a_isl); Bp = [q for x in others for q in pts(x)]
    (ka, pa, la), (kb, pb, lb) = min(((a_, b_) for a_ in A for b_ in Bp),
                                    key=lambda ab: math.hypot(ab[0][1][0] - ab[1][1][0], ab[0][1][1] - ab[1][1][1]))
    win = W.win([pa, pb], MARGIN)
    ix0, iy0, ix1, iy1 = win
    X, Y = np.meshgrid(np.arange(ix0, ix1 + 1) * G, np.arange(iy0, iy1 + 1) * G)
    zone = np.zeros(X.shape, bool)
    for f in W.fields:
        zone |= (X >= f[0]) & (X <= f[2]) & (Y >= f[1]) & (Y <= f[3])
    own = {net}
    free = {}
    for l in RL:
        fw = ~W.blocked(own, l, 0.05, win)
        m0 = lfr.M; lfr.M = 0.002
        fn = ~W.blocked(own, l, 0.045, win) & zone
        lfr.M = m0
        free[l] = fw | fn
    vok = W.via_ok(own, win, 0.4, 0.2)
    cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    ownv = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net]
    for v in ownv:
        cx, cy = cell(v)
        if 0 <= cy < vok.shape[0] and 0 <= cx < vok.shape[1]:
            vok[cy, cx] = True
            for l in RL:
                free[l][cy, cx] = True
    (sx, sy), (tx, ty) = cell(pa), cell(pb)
    for l in la:
        free[l][sy, sx] = True
    for l in lb:
        free[l][ty, tx] = True
    # 3-D reachability: label per layer, join labels through via cells (union-find)
    lab = {l: ndimage.label(free[l], structure=np.ones((3, 3)))[0] for l in RL}
    par = {}
    def find(k):
        while par.setdefault(k, k) != k:
            par[k] = par[par[k]]; k = par[k]
        return k
    ys, xs = np.nonzero(vok)
    for y, x in zip(ys, xs):
        ks = [(l, int(lab[l][y, x])) for l in RL if lab[l][y, x]]
        for k in ks[1:]:
            par[find(ks[0])] = find(k)
    starts = {find((l, int(lab[l][sy, sx]))) for l in la if lab[l][sy, sx]}
    goals = {find((l, int(lab[l][ty, tx]))) for l in lb if lab[l][ty, tx]}
    reach = bool(starts & goals)
    R = {l: np.zeros(X.shape, bool) for l in RL}
    for l in RL:
        for k in np.unique(lab[l]):
            if k and find((l, int(k))) in starts:
                R[l] |= lab[l] == k
    size = {l: int(R[l].sum()) for l in RL}
    print(f'\n{net}: from {ka} {tuple(round(v, 2) for v in pa)} {la} to {kb} {tuple(round(v, 2) for v in pb)} {lb}  '
          f'd={math.hypot(pa[0] - pb[0], pa[1] - pb[1]):.1f} mm')
    print(f'   destination reachable alone: {reach}; reachable cells per layer {size}; via spots in region '
          f'{int(sum((vok & R[l]).sum() for l in RL))}')
    if reach:
        continue
    gsize = sum(int(sum(((lab[l] > 0) & np.isin(lab[l], [k for (ll, k) in par if ll == l and find((ll, k)) in goals] +
                [int(lab[l][ty, tx])])).sum() for _ in [0])) for l in lb)
    Rg = {l: np.zeros(X.shape, bool) for l in RL}
    for l in RL:
        for k in np.unique(lab[l]):
            if k and find((l, int(k))) in goals:
                Rg[l] |= lab[l] == k
    gs_ = {l: int(Rg[l].sum()) for l in RL}
    print(f'   goal-side region per layer {gs_}')
    if sum(gs_.values()) < sum(size.values()):
        R = Rg; print('   (analysing the GOAL pocket, the smaller one)')
    # who walls the region in: boundary cells of the region (dilated minus region) -> nearest blocking shape
    cnt = collections.Counter()
    for l in RL:
        if not R[l].any():
            continue
        bd = ndimage.binary_dilation(R[l], structure=np.ones((3, 3))) & ~R[l]
        by, bx = np.nonzero(bd)
        if len(bx) > 1500:
            sel = np.random.default_rng(0).choice(len(bx), 1500, replace=False); by, bx = by[sel], bx[sel]
        for y, x in zip(by, bx):
            px, py = (x + ix0) * G, (y + iy0) * G
            if W.edge_dist[min(y + iy0, W.NY - 1), min(x + ix0, W.NX - 1)] < W.EDGE + 0.1:
                cnt[('board edge', '', l)] += 1; continue
            best = None
            for e in W.near((px - 0.5, py - 0.5, px + 0.5, py + 0.5)):
                if l not in e['layers'] or e['net'] == net:
                    continue
                d = float(lfr.shape_dist(e['s'], np.array([px]), np.array([py]))[0])
                if best is None or d < best[0]:
                    best = (d, e)
            if best:
                e = best[1]
                nm = e['src'] if e['cls'] == 'pad' else e['net'] or e['src']
                cnt[(e['cls'], str(nm), l)] += 1
    top = cnt.most_common(12)
    print('   walled in by (kind, net/pad, layer: boundary samples):')
    for (k, nm, l), c in top:
        print(f'      {k:4} {nm:18} L{l:<3} {c}')
