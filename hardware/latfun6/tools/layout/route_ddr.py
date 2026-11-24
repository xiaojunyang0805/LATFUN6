"""LATFUN6 DDR3L routing (layout worknote W5b step 2): U5 banks 6/7 <-> U30 on the existing BGA fan-out.
    python route_ddr.py [--out CAND.eprj] [--iters N] [--png OUT.png]

Rules (worknote §1 row 2, §5 widths):
  - DDR_SE 0.125 mm outside the ball fields, necked to 0.09 inside (only 0.09 fits between 0.8 mm-pitch vias).
  - DQ/DM/DQS prefer Inner2 (stripline next to the In1 GND plane); ADDR/CMD/CK prefer Bottom, then Top.
  - <= 3 vias FPGA -> memory: the fan-out gives 1-2, at most 1 new via per net (2 for a via-less U5 ball).
  - 0.2 mm edge gap between DDR tracks outside the fields (TT rule 0.102 inside).
  - CK and DQS pairs: coupled 0.100 / 0.203 where possible, P/N gap >= 0.200 everywhere (EDA DP check).
  - Lengths: DQ/DM within +-1.27 mm of own DQS; ADDR/CMD within +-2.54 mm of CK; P/N skew <= 0.05 mm.
  - No acute or 90-degree joints (also against the fan-out stub at a via on the same layer).
"""
import sys, os, math, time, re, json, collections, random
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr
from lfr import G, DIRS, DLEN

SRC = os.environ.get('EPRJ', 'E:/2026/LATFUN6/hardware/EDA/Latfun6.eprj')
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
OUT = opt('--out'); ITERS = int(opt('--iters', 4)); PNG = opt('--png')
TOP, BOT, IN2 = 1, 2, 16
RL = [TOP, IN2, BOT]
WW, WN = 0.125, 0.09               # DDR_SE pref / neck
SEPV = 0.20                        # DDR-to-DDR edge gap outside the fields
VD, VH = 0.40, 0.20                # new via = BGA_VIA (as the fan-out)
PG = 0.203                         # P/N gap (EDA flags < 0.200)
DDR = re.compile(r'^DDRAM_')

log = print
W = lfr.World(SRC, ripup_prefix='e8r', ripup_nets=lambda n: bool(n) and bool(DDR.match(n)))
log(f'ripped {W.ripped} earlier DDR records')
# ---------------------------------------------------------------- fields: U5 one block, U30 two halves (3 rows each)
W.add_field('U5')
u30 = [(k, lfr.shape_center(e['s'])) for k, e in W.pad.items() if k.startswith('U30.')]
for half in (lambda y: y < 24.0, lambda y: y >= 24.0):
    pts = [c for k, c in u30 if half(c[1])]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    W.fields.append((min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5))
log('fields', [tuple(round(v, 2) for v in f) for f in W.fields])

NETS = sorted({e['net'] for e in W.sh if e['net'] and DDR.match(e['net'])})
W.pair_nets = set(NETS); W.PAIR_SEP = SEPV


DDRSET = set(NETS)
GW = W.win([(56.0, 12.0), (98.0, 62.0)], 0)
NONDDR = [e for e in W.sh if e['net'] not in DDRSET]
CACHE = {}


def clamp(win):
    return (max(win[0], GW[0]), max(win[1], GW[1]), min(win[2], GW[2]), min(win[3], GW[3]))


def _with(shapes, fn):
    sh = W.sh; W.sh = shapes
    try:
        return fn()
    finally:
        W.sh = sh


ORIG = W.blocked


MN = 0.002          # sampling margin for the necked (0.09) masks: channels between 0.8 mm-pitch vias run on grid
#                     lines (exact); diagonal steps there are re-checked exactly afterwards


def blocked2(own, l, hw, win, sep=0.0, partner=None, via=False, pgap=PG, m=None):
    """W.blocked, with the non-DDR obstacles rasterised once over GW and cached"""
    if m is not None:
        m0 = lfr.M; lfr.M = m
        try:
            return blocked2(own, l, hw, win, sep, partner, via, pgap)
        finally:
            lfr.M = m0
    if win[0] < GW[0] or win[1] < GW[1] or win[2] > GW[2] or win[3] > GW[3] or (own - DDRSET):
        return ORIG(own, l, hw, win, sep_extra=sep, partner=partner, pgap=pgap, via=via)
    key = (l, round(hw, 5), sep, via, lfr.M)
    if key not in CACHE:
        CACHE[key] = _with(NONDDR, lambda: ORIG(set(), l, hw, GW, sep_extra=sep, via=via))
    base = CACHE[key][win[1] - GW[1]:win[3] - GW[1] + 1, win[0] - GW[0]:win[2] - GW[0] + 1]
    ddr = [e for e in W.sh if e['net'] in DDRSET]
    dyn = _with(ddr, lambda: ORIG(own, l, hw, win, sep_extra=sep, partner=partner, pgap=pgap, via=via))
    return base | dyn


W.blocked = lambda own, layer, hw, w, sep_extra=0.0, partner=None, pgap=0.18, via=False:     blocked2(own, layer, hw, w, sep=sep_extra, partner=partner, via=via, pgap=pgap)


def via_ok2(own, win, dia=VD, hole=VH):
    ix0, iy0, ix1, iy1 = win
    r = dia / 2
    ok = np.ones((iy1 - iy0 + 1, ix1 - ix0 + 1), bool)
    for l in W.layers:
        ok &= ~blocked2(own, l, r - lfr.M + 0.001, win, via=True)
    X, Y = np.meshgrid(np.arange(ix0, ix1 + 1) * G, np.arange(iy0, iy1 + 1) * G)
    for (hx, hy, hr) in W.holes:
        Rh = hole / 2 + hr + W.HH
        if ix0 * G - Rh <= hx <= ix1 * G + Rh and iy0 * G - Rh <= hy <= iy1 * G + Rh:
            ok &= np.hypot(X - hx, Y - hy) >= Rh
    for (fx0, fy0, fx1, fy1) in W.fields:
        a0, b0 = int(fx0 / G) - ix0, int(fy0 / G) - iy0
        a1, b1 = int(fx1 / G) - ix0 + 1, int(fy1 / G) - iy0 + 1
        ok[max(b0, 0):max(b1, 0), max(a0, 0):max(a1, 0)] = False
    return ok


def zone_mask(win):
    ix0, iy0, ix1, iy1 = win
    z = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), bool)
    for (fx0, fy0, fx1, fy1) in W.fields:
        a0, b0 = max(int(math.ceil(fx0 / G)) - ix0, 0), max(int(math.ceil(fy0 / G)) - iy0, 0)
        a1, b1 = int(math.floor(fx1 / G)) - ix0 + 1, int(math.floor(fy1 / G)) - iy0 + 1
        if a1 > 0 and b1 > 0:
            z[b0:b1, a0:a1] = True
    return z


def ends(net):
    pads = {k: lfr.shape_center(e['s']) for k, e in W.pad.items() if e['net'] == net}
    vias = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net and e['src'] == 'file']
    u5 = [c for k, c in pads.items() if k.startswith('U5.')][0]
    u30 = [c for k, c in pads.items() if k.startswith('U30.')][0]
    near = lambda p: min(vias, key=lambda v: math.hypot(v[0] - p[0], v[1] - p[1]), default=None)
    v5, v30 = near(u5), near(u30)
    A = (v5, RL) if v5 and math.hypot(v5[0] - u5[0], v5[1] - u5[1]) < 0.8 else (u5, [TOP])
    B = (v30, RL)
    return A, B


def stubs(net, p):
    """unit vectors (layer, (ux, uy)) from point p along the file tracks of `net` that end at p"""
    out = []
    for e in W.sh:
        if e['cls'] != 'trk' or e['src'] != 'file' or e['net'] != net:
            continue
        s = e['s']
        for (x, y), (ox, oy) in (((s[1], s[2]), (s[3], s[4])), ((s[3], s[4]), (s[1], s[2]))):
            if math.hypot(x - p[0], y - p[1]) < 0.01:
                L = math.hypot(ox - x, oy - y)
                if L > 1e-6:
                    out.append((next(iter(e['layers'])), ((ox - x) / L, (oy - y) / L)))
    return out


def unit(k):
    dx, dy = DIRS[k]; L = math.hypot(dx, dy); return dx / L, dy / L


def route_se(net, A, B, layers, lcost, vias=True, partner=None, margin=6.0, maxexp=800_000, via_cost=3.0, maxvias=1):
    (a, al), (b, bl) = A, B
    al = [l for l in al if l in layers]; bl = [l for l in bl if l in layers]
    if not al or not bl:
        return None
    win = clamp(W.win([a, b], margin))
    ix0, iy0 = win[0], win[1]
    own = {net}
    zone = zone_mask(win)
    fw, fr = {}, {}
    for l in layers:
        li = W.LI[l]
        wf = ~blocked2(own, l, WW / 2, win, sep=SEPV, partner=partner)
        nf = ~blocked2(own, l, WN / 2, win, partner=partner, m=MN)
        fw[li] = wf; fr[li] = wf | (nf & zone)
    vok = via_ok2(own, win) if vias and len(layers) > 1 else None
    cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    (sx, sy), (tx, ty) = cell(a), cell(b)
    for l in al:
        fr[W.LI[l]][sy, sx] = True
    for l in bl:
        fr[W.LI[l]][ty, tx] = True
    sa, sb = stubs(net, a), stubs(net, b)

    def sok(k, x, y, li):
        if (x, y) != (sx, sy):
            return True
        u = unit(k); lay = W.layers[li]
        return all(u[0] * v[0] + u[1] * v[1] < -1e-6 for sl, v in sa if sl == lay)

    bli = {W.LI[l] for l in bl}

    def goal(x, y, li, d):
        if (x, y) != (tx, ty) or li not in bli or d < 0:
            return None
        u = unit(d); lay = W.layers[li]
        return 0.0 if all(u[0] * v[0] + u[1] * v[1] > 1e-6 for sl, v in sb if sl == lay) else None

    starts = [(sx, sy, W.LI[l], 0.0) for l in al]
    lc = {W.LI[k]: v for k, v in lcost.items()}
    path = lfr.astar(fr, vok, starts, goal, (tx, ty), win, bend=0.4, via_cost=via_cost, maxexp=maxexp, lcost=lc,
                     start_ok=sok)
    if path is None:
        return None
    nv = sum(1 for p, q in zip(path, path[1:]) if p[2] != q[2])
    if nv > maxvias:
        return 'vias'
    # commit: runs per layer, width per step (narrow where the wide track does not fit)
    runs = [[path[0]]]
    for p in path[1:]:
        if p[2] == runs[-1][-1][2]:
            runs[-1].append(p)
        else:
            runs.append([p])
    out = []
    for run in runs:
        li = run[0][2]; lay = W.layers[li]
        segs = []                          # [dir, width, start cell, end cell]
        for p, q in zip(run, run[1:]):
            k = (q[0] - p[0], q[1] - p[1])
            wd = WW if (fw[li][p[1], p[0]] and fw[li][q[1], q[0]]) else WN
            if segs and segs[-1][0] == k and segs[-1][1] == wd:
                segs[-1][3] = q
            else:
                segs.append([k, wd, p, q])
        out.append((lay, [(((s[2][0] + ix0) * G, (s[2][1] + iy0) * G), ((s[3][0] + ix0) * G, (s[3][1] + iy0) * G), s[1])
                          for s in segs], run[-1]))
    L = 0.0
    for ri, (lay, segs, last) in enumerate(out):
        for p, q, wd in segs:
            W.add_track(net, lay, p, q, wd); L += math.hypot(q[0] - p[0], q[1] - p[1])
        if ri + 1 < len(out):
            W.add_via(net, (last[0] + ix0) * G, (last[1] + iy0) * G, VD, VH)
    return dict(layers=[o[0] for o in out], vias=nv, L=L)


# ---------------------------------------------------------------- groups
BYTE0 = [f'DDRAM_DQ{i}' for i in range(8)] + ['DDRAM_DM0']
BYTE1 = [f'DDRAM_DQ{i}' for i in range(8, 16)] + ['DDRAM_DM1']
PAIRS = {'CLK': ('DDRAM_CLK_P', 'DDRAM_CLK_N'), 'DQS0': ('DDRAM_DQS_P0', 'DDRAM_DQS_N0'),
         'DQS1': ('DDRAM_DQS_P1', 'DDRAM_DQS_N1')}
PAIRNETS = {n for p in PAIRS.values() for n in p}
ADDR = [n for n in NETS if n not in BYTE0 + BYTE1 and n not in PAIRNETS]
LC_DQ = {IN2: 1.0, TOP: 1.25, BOT: 1.6}
LC_AD = {BOT: 1.0, TOP: 1.15, IN2: 1.7}
log(f'{len(NETS)} DDR nets: byte0 {len(BYTE0)}, byte1 {len(BYTE1)}, addr/cmd {len(ADDR)}, pairs {len(PAIRS)}')

PAIR_LAYERS = {'CLK': [BOT, TOP, IN2], 'DQS0': [IN2, TOP], 'DQS1': [IN2, TOP, BOT]}


def route_pair_job(name):
    P, N = PAIRS[name]
    (aP, alP), (bP, _) = ends(P); (aN, alN), (bN, _) = ends(N)
    lc = LC_AD if name == 'CLK' else LC_DQ
    if alP == RL and alN == RL:
        R = lfr.Router(W, log=lambda *a: None)
        for lay in PAIR_LAYERS[name]:
            m = W.mark()
            r = R.route_pair(P, N, (aP, aN), (bP, bN), lay, 0.100, PG, wleg=(WN, WN), Ra=4.0, Rb=2.2, margin=5.0,
                             retries=4, maxexp=1_500_000)
            if r and r.get('ok'):
                return f'coupled on {lay}'
            W.rollback(m)
    # fallback: two single tracks, N keeps the partner gap from P
    m = W.mark()
    rp = route_se(P, ends(P)[0], ends(P)[1], RL, lc, maxvias=2)
    if isinstance(rp, dict):
        rn = route_se(N, ends(N)[0], ends(N)[1], RL, lc, partner=P, maxvias=2)
        if isinstance(rn, dict):
            return f'single legs {rp["layers"]} / {rn["layers"]}'
    W.rollback(m)
    return None


def route_all(order):
    res = {}
    for job in order:
        t0 = time.time()
        if job in PAIRS:
            r = route_pair_job(job)
            res[job] = r
            log(f'  {job:14} {r or "FAILED"} ({time.time() - t0:.1f} s)')
            continue
        lc = LC_AD if job in ADDR else LC_DQ
        A, B = ends(job)
        m = W.mark()
        r = route_se(job, A, B, RL, lc, maxvias=2 if A[1] == [TOP] else 1)
        if r == 'vias' or r is None:
            W.rollback(m)
            r = route_se(job, A, B, RL, lc, maxvias=2 if A[1] == [TOP] else 1, via_cost=8.0) if r == 'vias' else None
            if not isinstance(r, dict):
                W.rollback(m); r = None
        res[job] = r
        log(f'  {job:14} {("L=%.1f %s vias+%d" % (r["L"], r["layers"], r["vias"])) if r else "FAILED"} ({time.time() - t0:.1f} s)')
    return res


if opt('--debug'):
    from scipy import ndimage
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    net = opt('--debug'); A, B = ends(net)
    win = clamp(W.win([A[0], B[0]], 6.0)); zone = zone_mask(win)
    fig, axs = plt.subplots(1, 3, figsize=(24, 12))
    for ax, l in zip(axs, RL):
        wf = ~blocked2({net}, l, WW / 2, win, sep=SEPV); nf = ~blocked2({net}, l, WN / 2, win, m=MN)
        fr = wf | (nf & zone)
        c = lambda p: (int(round(p[0] / G)) - win[0], int(round(p[1] / G)) - win[1])
        lab, _ = ndimage.label(fr, structure=np.ones((3, 3)))
        sa, sb = c(A[0]), c(B[0])
        img = fr.astype(float) * 0.5
        for (x, y) in (sa, sb):
            if lab[y, x]:
                img[lab == lab[y, x]] = 1.0
        ax.imshow(img, extent=(win[0] * G, (win[2] + 1) * G, (win[3] + 1) * G, win[1] * G), cmap='gray', vmin=0, vmax=1)
        ax.plot([A[0][0], B[0][0]], [A[0][1], B[0][1]], 'r.', ms=10)
        ax.set_title(f'{net} layer {l}: start comp {lab[sa[1], sa[0]]} goal comp {lab[sb[1], sb[0]]}')
    fig.savefig(opt('--png'), bbox_inches='tight'); sys.exit()

base = W.mark()
order = ['CLK', 'DQS1', 'DQS0'] + BYTE1 + BYTE0 + ADDR
best = None
for it in range(ITERS):
    W.rollback(base)
    log(f'--- pass {it + 1}: order {order[:6]}...')
    res = route_all(order)
    fails = [k for k, v in res.items() if not v]
    log(f'pass {it + 1}: {len(res) - len(fails)}/{len(res)} routed, failed {fails}')
    if best is None or len(fails) < len(best[0]):
        best = (fails, W.mark(), list(order), res)
        snap = (list(W.sh), list(W.new_tracks), list(W.new_vias), list(W.holes))
    if not fails:
        break
    order = fails + [k for k in order if k not in fails]

fails, _, order, res = best
W.sh[:], W.new_tracks[:], W.new_vias[:], W.holes[:] = snap
log(f'best: {len(res) - len(fails)}/{len(res)}, failed {fails}')
json.dump({'order': order, 'fails': fails}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_order.json'), 'w'))


# ---------------------------------------------------------------- length tuning
def tune_groups():
    L = lambda: lfr.net_lengths(W, set(NETS))
    for name, (P, N) in PAIRS.items():
        if res.get(name):
            sk = lfr.tune_pair(W, P, N, tol=0.05)
            log(f'  skew {name}: {sk:+.3f} mm')
    groups = [('DQS0', BYTE0, 1.27), ('DQS1', BYTE1, 1.27), ('CLK', ADDR, 2.54)]
    for ref, members, tol in groups:
        P, N = PAIRS[ref]
        Ls = L(); Lr = (Ls.get(P, 0) + Ls.get(N, 0)) / 2
        routed = [n for n in members if res.get(n)]
        longest = max([Ls[n] for n in routed] + [Lr])
        if longest > Lr + 0.6 * tol:              # strobe/clock too short: lengthen both legs equally
            dl = longest - 0.4 * tol - Lr
            for a, b in ((P, N), (N, P)):
                lfr.tune_len(W, a, dl, partner=b, pgap=PG, sepnets=W.pair_nets, sep=SEPV, wmin=WW, log=log)
            lfr.tune_pair(W, P, N, tol=0.05)
            Ls = L(); Lr = (Ls.get(P, 0) + Ls.get(N, 0)) / 2
        for n in routed:
            short = (Lr - 0.4 * tol) - Ls[n]
            if short > 0:
                lfr.tune_len(W, n, short + 0.1, sepnets=W.pair_nets, sep=SEPV, wmin=WW, log=log)
        Ls = L()
        dev = {n: Ls[n] - Lr for n in routed}
        bad = {n: round(v, 2) for n, v in dev.items() if abs(v) > tol}
        log(f'  group {ref}: ref {Lr:.2f} mm, spread {min(dev.values()):+.2f}..{max(dev.values()):+.2f}, out of tol {bad}')


log('length tuning')
tune_groups()

acute, right = lfr.acute_check(W, set(NETS))
log(f'acute {len(acute)} right {len(right)} {acute[:5]} {right[:5]}')
log(f'edge {W.edge_check()[:5]}')
Ls = lfr.net_lengths(W, set(NETS))
for n in NETS:
    vs = sum(1 for v in W.new_vias if v[0] == n)
    log(f'  {n:16} {Ls.get(n, 0):6.2f} mm  new vias {vs}  layers {sorted({t[1] for t in W.new_tracks if t[0] == n})}')
if PNG:
    lfr.render(W, PNG, box=(60, 14, 95, 50), title='DDR3 routing')
if OUT:
    p, n = lfr.write_candidate(W, OUT)
    log(f'candidate {p}: {n} records')
