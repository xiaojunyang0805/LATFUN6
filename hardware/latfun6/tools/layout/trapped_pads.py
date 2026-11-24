"""List the boxed-in ends of failing nets (diag_nets.py, batch form): for each net, flood fill from both ends of its
nearest island pair over every signal layer; an end whose region is small (< --cells) with no legal via spot is
trapped. Prints the trapped pad keys (DES.NUM) and the nets that are routable alone.
    python trapped_pads.py BOARD.eprj NET[,NET...] [--cells 4000]"""
import sys, os, math
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
CELLS = int(opt('--cells', 4000))
RL = [1, 16, 19, 2] + ([17] if '--in3' in args else [])
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
    return out


trapped, alone = [], []
for net in nets:
    g = [x for x in isl.get(net, []) if x['pads']]
    if len(g) < 2:
        continue
    best = None
    for i, x in enumerate(g):
        for y in g[i + 1:]:
            for a in pts(x):
                for b in pts(y):
                    d = math.hypot(a[1][0] - b[1][0], a[1][1] - b[1][1])
                    if best is None or d < best[0]:
                        best = (d, a, b)
    d, A, Bp = best
    win = W.win([A[1], Bp[1]], 6.0)
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
    for e in W.sh:
        if e['cls'] == 'via' and e['net'] == net:
            c = lfr.shape_center(e['s']); cx, cy = int(round(c[0] / G)) - ix0, int(round(c[1] / G)) - iy0
            if 0 <= cy < vok.shape[0] and 0 <= cx < vok.shape[1]:
                vok[cy, cx] = True
                for l in RL:
                    free[l][cy, cx] = True
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
    res = []
    for (k, p, ls) in (A, Bp):
        cx, cy = int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0
        for l in ls:
            free[l][cy, cx] = True
        roots = set()
        for l in ls:
            if lab[l][cy, cx] == 0:          # the end cell itself was blocked: label its neighbourhood
                nb = {int(lab[l][yy, xx]) for yy in range(cy - 2, cy + 3) for xx in range(cx - 2, cx + 3) if lab[l][yy, xx]}
                roots |= {find((l, n)) for n in nb}
            else:
                roots.add(find((l, int(lab[l][cy, cx]))))
        size = sum(int((lab[l] == kk).sum()) for (l, kk) in [r for r in par] + [(l, int(lab[l][cy, cx])) for l in ls]
                   if find((l, kk)) in roots) if roots else 0
        vs = sum(int((vok & np.isin(lab[l], [kk for (ll, kk) in par if ll == l and find((ll, kk)) in roots])).sum()) for l in RL)
        res.append((k, roots, size, vs))
    reach = bool(res[0][1] & res[1][1])
    if reach:
        alone.append(net)
    for k, roots, size, vs in res:
        if not reach and size < CELLS and vs == 0 and k != 'via':
            trapped.append(k)
    print(f'{net:16} {A[0]} <-> {Bp[0]}  reachable alone {reach}; end regions {[(r[0], r[2], r[3]) for r in res]}', flush=True)
print('\nTRAPPED', ','.join(trapped))
print('ALONE', ','.join(alone))
