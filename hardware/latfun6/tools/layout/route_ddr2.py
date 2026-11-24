"""LATFUN6 DDR3L routing by negotiated congestion (PathFinder), U5 banks 6/7 <-> U30 on the existing BGA fan-out.
    python route_ddr2.py [--out CAND.eprj] [--iters N] [--png OUT.png]

Why negotiation: greedy sequential routing (route_ddr.py) closed 14/46 jobs. The escape channels between the
0.8 mm-pitch via columns carry one 0.09 mm track per layer each, and nets routed early took channels that later nets
needed. Here every net is re-routed each iteration; other DDR nets' NEW copper is a soft cost (present overlap x
pres_fac, growing each iteration, plus a history cost on cells that stay congested), everything else is hard.
Done when an iteration routes every net without touching another net's copper.

Rules (worknote §1 row 2, §5):
  - DDR_SE 0.125 mm outside the ball fields, necked to 0.09 inside them.
  - DQ/DM/DQS prefer Inner2 (stripline on the In1 GND plane), ADDR/CMD/CK prefer Bottom, then Top.
  - <= 3 vias FPGA -> memory: the fan-out gives 1-2; new vias only outside the BGA fields.
  - DDR-to-DDR edge gap SEPV outside the fields (soft); TT rule 0.102 everywhere (hard via the exact re-check).
  - CK / DQS legs: P/N gap >= 0.203 (hard), N attracted to the coupled pitch next to P.
  - Lengths: DQ/DM within +-1.27 mm of own DQS; ADDR/CMD within +-2.54 mm of CK; P/N skew <= 0.05 mm.
  - No acute or 90-degree joints (A* turns 45 degrees per step; at a via the fan-out stub on the same layer counts).
"""
import sys, os, math, time, re, json, heapq, random
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr
from lfr import G, DIRS, DLEN

SRC = os.environ.get('EPRJ', 'E:/2026/LATFUN6/hardware/EDA/Latfun6.eprj')
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
OUT = opt('--out'); ITERS = int(opt('--iters', 12)); PNG = opt('--png')
TOP, BOT, IN2 = 1, 2, 16
RL = [TOP, IN2, BOT]
WW, WN = 0.125, 0.09
SEPV = 0.15
VD, VH = 0.40, 0.20
PG = 0.203
MN = 0.002
DEBUG = '--debug' in sys.argv
DDR = re.compile(r'^DDRAM_')
log = lambda *a: print(*a, flush=True)

W = lfr.World(SRC, ripup_prefix='e8r', ripup_nets=lambda n: bool(n) and bool(DDR.match(n)))
log(f'ripped {W.ripped} earlier DDR records')
W.add_field('U5')
u30 = [lfr.shape_center(e['s']) for k, e in W.pad.items() if k.startswith('U30.')]
for half in (lambda y: y < 24.0, lambda y: y >= 24.0):
    pts = [c for c in u30 if half(c[1])]
    W.fields.append((min(p[0] for p in pts) - 0.5, min(p[1] for p in pts) - 0.5,
                     max(p[0] for p in pts) + 0.5, max(p[1] for p in pts) + 0.5))
NETS = sorted({e['net'] for e in W.sh if e['net'] and DDR.match(e['net'])})
DDRSET = set(NETS)
GW = W.win([(56.0, 12.0), (98.0, 62.0)], 0)
GX0, GY0 = GW[0], GW[1]
GH, GWD = GW[3] - GW[1] + 1, GW[2] - GW[0] + 1
NONDDR = [e for e in W.sh if e['net'] not in DDRSET]
DDRFILE = [e for e in W.sh if e['net'] in DDRSET]           # pads, fan-out vias + stubs (fixed)
ORIG = W.blocked


def _with(shapes, fn):
    sh = W.sh; W.sh = shapes
    try:
        return fn()
    finally:
        W.sh = sh


def _m(m, fn):
    m0 = lfr.M; lfr.M = m
    try:
        return fn()
    finally:
        lfr.M = m0


BASE = {}


def base(l, hw, m, via=False):
    k = (l, round(hw, 5), m, via)
    if k not in BASE:
        BASE[k] = _m(m, lambda: _with(NONDDR, lambda: ORIG(set(), l, hw, GW, via=via)))
    return BASE[k]


def sl(a, win):
    return a[win[1] - GY0:win[3] - GY0 + 1, win[0] - GX0:win[2] - GX0 + 1]


def zone_mask(win):
    ix0, iy0, ix1, iy1 = win
    z = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), bool)
    for (fx0, fy0, fx1, fy1) in W.fields:
        a0, b0 = max(int(math.ceil(fx0 / G)) - ix0, 0), max(int(math.ceil(fy0 / G)) - iy0, 0)
        a1, b1 = int(math.floor(fx1 / G)) - ix0 + 1, int(math.floor(fy1 / G)) - iy0 + 1
        if a1 > 0 and b1 > 0:
            z[b0:b1, a0:a1] = True
    return z


FV = {}                                    # --field-via NET:x,y  extra fan-out via inside a BGA field
for spec in (opt('--field-via') or '').split(';'):
    if spec:
        n_, xy = spec.split(':'); FV[n_] = tuple(float(v) for v in xy.split(','))
FIXN = {}


def ends(net):
    pads = {k: lfr.shape_center(e['s']) for k, e in W.pad.items() if e['net'] == net}
    if net in FV:
        u5 = [c for k, c in pads.items() if k.startswith('U5.')][0]
        FIXN[net] = dict(trk=[(TOP, (u5[0], u5[1], FV[net][0], FV[net][1]), 0.1)], via=[FV[net]])
        vias = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net]
        u30 = [c for k, c in pads.items() if k.startswith('U30.')][0]
        v30 = min(vias, key=lambda v: math.hypot(v[0] - u30[0], v[1] - u30[1]))
        return (FV[net], RL), (v30, RL)
    vias = [lfr.shape_center(e['s']) for e in DDRFILE if e['cls'] == 'via' and e['net'] == net]
    u5 = [c for k, c in pads.items() if k.startswith('U5.')][0]
    u30 = [c for k, c in pads.items() if k.startswith('U30.')][0]
    near = lambda p: min(vias, key=lambda v: math.hypot(v[0] - p[0], v[1] - p[1]), default=None)
    v5, v30 = near(u5), near(u30)
    A = (v5, RL) if v5 and math.hypot(v5[0] - u5[0], v5[1] - u5[1]) < 0.8 else (u5, [TOP])
    return A, (v30, RL)


def stubs(net, p):
    out = []
    for e in DDRFILE:
        if e['cls'] != 'trk' or e['net'] != net:
            continue
        s = e['s']
        for (x, y), (ox, oy) in (((s[1], s[2]), (s[3], s[4])), ((s[3], s[4]), (s[1], s[2]))):
            if math.hypot(x - p[0], y - p[1]) < 0.01 and math.hypot(ox - x, oy - y) > 1e-6:
                L = math.hypot(ox - x, oy - y)
                out.append((next(iter(e['layers'])), ((ox - x) / L, (oy - y) / L)))
    return out


def unit(k):
    dx, dy = DIRS[k]; L = math.hypot(dx, dy); return dx / L, dy / L


# ---------------------------------------------------------------- per-net static data (computed once)
BYTE0 = [f'DDRAM_DQ{i}' for i in range(8)] + ['DDRAM_DM0']
BYTE1 = [f'DDRAM_DQ{i}' for i in range(8, 16)] + ['DDRAM_DM1']
PAIRS = {'CLK': ('DDRAM_CLK_P', 'DDRAM_CLK_N'), 'DQS0': ('DDRAM_DQS_P0', 'DDRAM_DQS_N0'),
         'DQS1': ('DDRAM_DQS_P1', 'DDRAM_DQS_N1')}
PARTNER = {}
for P, N in PAIRS.values():
    PARTNER[P] = N; PARTNER[N] = P
ADDR = [n for n in NETS if n not in BYTE0 + BYTE1 and n not in PARTNER]
LC_DQ = {IN2: 1.0, TOP: 1.25, BOT: 1.5}
LC_AD = {BOT: 1.0, TOP: 1.1, IN2: 1.6}
LCOST = {n: (LC_AD if (n in ADDR or 'CLK' in n) else LC_DQ) for n in NETS}

STATIC = {}
BYTE0S = set(BYTE0) | {'DDRAM_DQS_P0', 'DDRAM_DQS_N0'}
ALLOWED = {n: ([BOT, TOP] if (n in ADDR or 'CLK' in n) else [TOP] if n in BYTE0S else [IN2, TOP]) for n in NETS}
if '--any-layer' in args:
    ALLOWED = {n: RL for n in NETS}
STRICT = '--greedy' in args or '--from' in args


def static(net):
    """hard free masks per layer (wide, narrow) + via-ok over the net's window, excluding other nets' NEW copper"""
    if net in STATIC:
        return STATIC[net]
    A, B = ends(net)
    win = W.win([A[0], B[0]], 6.0)
    win = (max(win[0], GX0), max(win[1], GY0), min(win[2], GW[2]), min(win[3], GW[3]))
    own = {net}
    others = [e for e in DDRFILE if e['net'] != net]
    zone = zone_mask(win)
    fw, fn = {}, {}
    for l in RL:
        li = W.LI[l]
        bw = sl(base(l, WW / 2, lfr.M), win) | _with(others, lambda: ORIG(own, l, WW / 2, win))
        bn = sl(base(l, WN / 2, MN), win) | _m(MN, lambda: _with(others, lambda: ORIG(own, l, WN / 2, win)))
        fw[li] = ~bw; fn[li] = ~bn & zone
    vok = np.ones_like(zone)
    for l in W.layers:
        hw = VD / 2 - lfr.M + 0.001
        vok &= ~(sl(base(l, hw, lfr.M, True), win) | _with(others, lambda: ORIG(own, l, hw, win, via=True)))
    X, Y = np.meshgrid(np.arange(win[0], win[2] + 1) * G, np.arange(win[1], win[3] + 1) * G)
    for (hx, hy, hr) in W.holes:
        Rh = VH / 2 + hr + W.HH
        if win[0] * G - Rh <= hx <= win[2] * G + Rh and win[1] * G - Rh <= hy <= win[3] * G + Rh:
            vok &= np.hypot(X - hx, Y - hy) >= Rh
    vok &= ~zone
    STATIC[net] = dict(win=win, zone=zone, fw=fw, fn=fn, vok=vok, A=A, B=B, sa=stubs(net, A[0]), sb=stubs(net, B[0]))
    return STATIC[net]


# ---------------------------------------------------------------- dynamic copper (new tracks / vias per net)
NEW = {n: dict(trk=[], via=[]) for n in NETS}       # trk: (layer, (x1,y1,x2,y2), w); via: (x, y)


def stamp(arr, win, s, R, val=1):
    ix0, iy0 = win[0], win[1]
    b = lfr.shape_bbox(s)
    jx0 = max(int(math.floor((b[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b[2] + R) / G)), win[2])
    jy0 = max(int(math.floor((b[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b[3] + R) / G)), win[3])
    if jx1 < jx0 or jy1 < jy0:
        return
    X, Y = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
    m = lfr.shape_dist(s, X, Y) < R
    if val is True:
        arr[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] |= m
    else:
        arr[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] += m.astype(arr.dtype) * val


def dynamic(net, st):
    """soft counts (per layer, per width class) from other nets' NEW copper; partner copper is hard (P/N gap);
    vias may not touch any other new copper; attraction band next to the partner"""
    win = st['win']; shp = st['zone'].shape
    cw = {W.LI[l]: np.zeros(shp, np.int16) for l in RL}; cn = {W.LI[l]: np.zeros(shp, np.int16) for l in RL}
    cs = {W.LI[l]: np.zeros(shp, np.int16) for l in RL}
    hard = {W.LI[l]: np.zeros(shp, bool) for l in RL}; vbad = np.zeros(shp, bool)
    attract = {W.LI[l]: np.zeros(shp, bool) for l in RL}
    p = PARTNER.get(net)
    for o, d in NEW.items():
        if o == net:
            continue
        for lay, (x1, y1, x2, y2), w in d['trk']:
            li = W.LI[lay]
            s = ('k', x1, y1, x2, y2, w / 2)
            if o == p:                       # P/N gap: soft as well, so the two legs negotiate
                stamp(cw[li], win, s, PG + 0.003 + WW / 2 + lfr.M)
                stamp(cn[li], win, s, PG + 0.003 + WN / 2 + MN)
                stamp(attract[li], win, s, w / 2 + PG + WW / 2 + 0.06, True)
            else:
                stamp(cw[li], win, s, W.TT + WW / 2 + lfr.M)
                stamp(cs[li], win, s, SEPV + WW / 2 + lfr.M)
                stamp(cn[li], win, s, W.TT + WN / 2 + MN)
            stamp(vbad, win, s, W.CLR + VD / 2 + lfr.M, True)
        for (x, y) in d['via']:
            s = ('c', x, y, VD / 2)
            for l in RL:
                li = W.LI[l]
                stamp(cw[li], win, s, W.CLR + WW / 2 + lfr.M); stamp(cn[li], win, s, W.CLR + WN / 2 + MN)
            stamp(vbad, win, s, VD + W.HH, True)
    if p:
        for li in attract:
            near_inner = np.zeros(shp, bool)
            for lay, (x1, y1, x2, y2), w in NEW[p]['trk']:
                if W.LI[lay] == li:
                    stamp(near_inner, win, ('k', x1, y1, x2, y2, w / 2), w / 2 + PG + WW / 2 - 0.04, True)
            attract[li] &= ~near_inner
    return cw, cn, cs, hard, vbad, attract


HIST = {W.LI[l]: np.zeros((GH, GWD), np.float32) for l in RL}


def astar_cc(frees, cc, vok, starts, goal_fn, hpt, bend, via_cost, maxexp, lc, start_ok, hweight=1.4):
    BEND, VIA = bend / G, via_cost / G
    tx, ty = hpt
    H = lambda x, y: hweight * (max(abs(x - tx), abs(y - ty)) + 0.41421356 * min(abs(x - tx), abs(y - ty)))
    openq, came, gs = [], {}, {}
    for (x, y, l, g0) in starts:
        if frees[l][y, x]:
            st = (x, y, l, -1); gs[st] = g0; came[st] = None
            heapq.heappush(openq, (g0 + H(x, y), g0, st))
    nexp = 0
    Ls = list(frees)
    hgt, wid = next(iter(frees.values())).shape
    while openq:
        f, gc, cur = heapq.heappop(openq)
        if cur == 'GOAL':
            path = []; c = came['GOAL']
            while c is not None:
                path.append(c[:3]); c = came[c]
            return path[::-1]
        if gc > gs.get(cur, 1e18):
            continue
        nexp += 1
        if nexp > maxexp:
            return None
        x, y, l, d = cur
        ge = goal_fn(x, y, l, d)
        if ge is not None and gc + ge < gs.get('GOAL', 1e18):
            gs['GOAL'] = gc + ge; came['GOAL'] = cur
            heapq.heappush(openq, (gc + ge, gc + ge, 'GOAL'))
        fr = frees[l]; c_l = cc[l]; lcl = lc.get(l, 1.0)
        for k in (range(8) if d < 0 else (d, (d + 1) % 8, (d - 1) % 8)):
            if d < 0 and start_ok is not None and not start_ok(k, x, y, l):
                continue
            dx, dy = DIRS[k]; nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= wid or ny >= hgt or not fr[ny, nx]:
                continue
            if dx and dy and not (fr[y, nx] and fr[ny, x]):
                continue
            ng = gc + DLEN[k] * max(lcl + c_l[ny, nx], 0.3) + (BEND if d >= 0 and k != d else 0)
            st = (nx, ny, l, k)
            if ng < gs.get(st, 1e18):
                gs[st] = ng; came[st] = cur
                heapq.heappush(openq, (ng + H(nx, ny), ng, st))
        if vok is not None and vok[y, x]:
            for l2 in Ls:
                if l2 != l and frees[l2][y, x]:
                    st = (x, y, l2, -1); ng = gc + VIA + max(cc[l2][y, x], 0)
                    if ng < gs.get(st, 1e18):
                        gs[st] = ng; came[st] = cur
                        heapq.heappush(openq, (ng + H(x, y), ng, st))
    return None


import astar_nb
LIS = [W.LI[l] for l in RL]


def run_nb(frees, cc, vok, sx, sy, al, sa, tx, ty, bl, sb, lc, vc, maxexp, viac):
    free = np.ascontiguousarray(np.stack([frees[li] for li in LIS]))
    cost = np.ascontiguousarray(np.stack([np.maximum(lc.get(li, 1.0) + cc[li], 0.3) for li in LIS]).astype(np.float32))
    slay = np.array([l in al for l in RL]); glay = np.array([l in bl for l in RL])
    sdir = np.ones((len(RL), 8), bool); gdir = np.ones((len(RL), 8), bool)
    for i, l in enumerate(RL):
        for k in range(8):
            u = unit(k)
            sdir[i, k] = all(u[0] * v[0] + u[1] * v[1] < -1e-6 for s_l, v in sa if s_l == l)
            gdir[i, k] = all(u[0] * v[0] + u[1] * v[1] > 1e-6 for s_l, v in sb if s_l == l)
    out = astar_nb.astar(free, cost, np.ascontiguousarray(vok), sx, sy, slay, sdir, tx, ty, glay, gdir,
                         0.4 / G, vc / G, 1.4, maxexp, np.ascontiguousarray(viac, dtype=np.float32))
    if len(out) == 0:
        return None
    return [(int(x), int(y), LIS[int(i)]) for x, y, i in out]


def route_one(net, pres, maxvias, via_cost=3.0, maxexp=6_000_000, hardall=False):
    st = static(net)
    win = st['win']; zone = st['zone']; ix0, iy0 = win[0], win[1]
    cw, cn, cs, hard, vbad, attract = dynamic(net, st)
    frees, cc, wide = {}, {}, {}
    for li in st['fw']:
        hs = sl(HIST[li], win)
        fwi = st['fw'][li] & ~hard[li]; fni = st['fn'][li] & ~hard[li]
        if hardall:
            fwi &= cw[li] == 0; fni &= cn[li] == 0
        frees[li] = fwi | fni
        if W.layers[li] not in ALLOWED[net]:
            frees[li] = np.zeros_like(fwi)
        wide[li] = fwi
        cnt = np.where(fwi, cw[li], cn[li]).astype(np.float32)
        cc[li] = 0.6 * hs + pres * cnt + 0.8 * (fwi & (cs[li] > 0)) - 0.35 * (attract[li] & ~zone)
    vok = st['vok'] if not hardall else st['vok'] & ~vbad
    viac = (pres / G) * vbad.astype(np.float32)
    (a, al), (b, bl) = st['A'], st['B']
    cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    (sx, sy), (tx, ty) = cell(a), cell(b)
    al = [l for l in al if l in ALLOWED[net]]; bl = [l for l in bl if l in ALLOWED[net]]
    for l in al:
        frees[W.LI[l]][sy, sx] = True
    for l in bl:
        frees[W.LI[l]][ty, tx] = True
    sa, sb = st['sa'], st['sb']

    def sok(k, x, y, li):
        if (x, y) != (sx, sy):
            return True
        u = unit(k); lay = W.layers[li]
        return all(u[0] * v[0] + u[1] * v[1] < -1e-6 for s_l, v in sa if s_l == lay)

    bli = {W.LI[l] for l in bl}

    def goal(x, y, li, d):
        if (x, y) != (tx, ty) or li not in bli or d < 0:
            return None
        u = unit(d); lay = W.layers[li]
        return 0.0 if all(u[0] * v[0] + u[1] * v[1] > 1e-6 for s_l, v in sb if s_l == lay) else None

    lc = {W.LI[k]: v for k, v in LCOST[net].items()}
    starts = [(sx, sy, W.LI[l], 0.0) for l in al]
    path = None
    best = None
    for vc in (via_cost, via_cost * 4, via_cost * 13):
        path = run_nb(frees, cc, vok, sx, sy, al, sa, tx, ty, bl, sb, lc, vc, maxexp, viac)
        nvp = None if path is None else sum(1 for p, q in zip(path, path[1:]) if p[2] != q[2])
        if DEBUG:
            log(f'    {net} via_cost {vc}: ' + ('no path' if path is None else f'{len(path)} cells, {nvp} vias'))
        if path is not None and (best is None or nvp < best[0]):
            best = (nvp, path)
        if path is not None and nvp <= maxvias:
            break
    if best is None or (STRICT and best[0] > maxvias):
        return None
    path = best[1]
    # conflicts on the path (cells where another net's copper is within its rule; vias touching other copper)
    over = 0
    for p, q in zip(path, path[1:]):
        if p[2] != q[2] and vbad[p[1], p[0]]:
            over += 5
    for (x, y, li) in path:
        c = cw[li][y, x] if wide[li][y, x] else cn[li][y, x]
        if c > 0:
            over += 1
            HIST[li][y + iy0 - GY0, x + ix0 - GX0] += 1.0
    # geometry
    runs = [[path[0]]]
    for p in path[1:]:
        if p[2] == runs[-1][-1][2]:
            runs[-1].append(p)
        else:
            runs.append([p])
    trk, via = [], []
    for ri, run in enumerate(runs):
        li = run[0][2]; lay = W.layers[li]
        segs = []
        for p, q in zip(run, run[1:]):
            k = (q[0] - p[0], q[1] - p[1])
            wd = WW if (wide[li][p[1], p[0]] and wide[li][q[1], q[0]]) else WN
            if segs and segs[-1][0] == k and segs[-1][1] == wd:
                segs[-1][3] = q
            else:
                segs.append([k, wd, p, q])
        for s in segs:
            trk.append((lay, ((s[2][0] + ix0) * G, (s[2][1] + iy0) * G, (s[3][0] + ix0) * G, (s[3][1] + iy0) * G), s[1]))
        if ri + 1 < len(runs):
            via.append(((run[-1][0] + ix0) * G, (run[-1][1] + iy0) * G))
    if net in FIXN:
        trk = FIXN[net]['trk'] + trk; via = FIXN[net]['via'] + via
    NEW[net] = dict(trk=trk, via=via)
    L = sum(math.hypot(t[1][2] - t[1][0], t[1][3] - t[1][1]) for t in trk)
    return dict(over=over, vias=len(via), layers=sorted({t[0] for t in trk}), L=L)


if opt('--reach'):
    from scipy import ndimage
    net = opt('--reach'); st = static(net); win = st['win']
    (a, al), (b, bl) = st['A'], st['B']
    c = lambda p: (int(round(p[0] / G)) - win[0], int(round(p[1] / G)) - win[1])
    for l in RL:
        li = W.LI[l]; fr = st['fw'][li] | st['fn'][li]
        lab, nlab = ndimage.label(fr, structure=np.ones((3, 3)))
        (sx, sy), (tx, ty) = c(a), c(b)
        def comp(x, y):
            nb = {lab[yy, xx] for yy in range(y - 1, y + 2) for xx in range(x - 1, x + 2) if lab[yy, xx]}
            return nb
        cs, cg = comp(sx, sy), comp(tx, ty)
        vk = {lab[y, x] for y, x in zip(*np.nonzero(st['vok'])) if lab[y, x]}
        log(l, 'start comps', cs, 'goal comps', cg, 'start comp has via spots', bool(cs & vk), 'goal comp has via spots', bool(cg & vk),
            'stubs', st['sa'], st['sb'])
    log('vok cells', int(st['vok'].sum()))
    sys.exit()

if opt('--probe'):
    net = opt('--probe')
    st = static(net)
    for mx in (900_000, 6_000_000):
        t = time.time()
        r = route_one(net, 0.5, maxvias=2 if st['A'][1] == [TOP] else 1, maxexp=mx)
        log(net, mx, r, f'{time.time() - t:.1f} s')
        if r:
            break
    sys.exit()

order = ['DDRAM_CLK_P', 'DDRAM_CLK_N', 'DDRAM_DQS_P1', 'DDRAM_DQS_N1', 'DDRAM_DQS_P0', 'DDRAM_DQS_N0'] + BYTE1 + BYTE0 + ADDR
t0 = time.time()
for n in order:
    static(n)
log(f'static masks for {len(order)} nets: {time.time() - t0:.0f} s')
import copy
if opt('--greedy'):
    # hard sequential routing in shuffled orders; keep the order with most nets routed, then shortest total length
    NG = int(opt('--greedy'))
    if opt('--only'):
        order = [n for n in order if n in set(opt('--only').split(','))]
    bestg = None
    for k in range(NG):
        t1 = time.time()
        for n in NETS:
            NEW[n] = dict(trk=[], via=[])
        seq = order if k == 0 else random.Random(1000 + k).sample(order, len(order))
        rr = {}
        for n in seq:
            A = STATIC[n]['A']
            r = route_one(n, 1.0, maxvias=2 if A[1] == [TOP] else 1, hardall=True)
            rr[n] = r
            if r is None:
                NEW[n] = dict(trk=[], via=[])
        fl = [n for n in order if not rr[n]]
        totL = sum(r['L'] for r in rr.values() if r)
        log(f'greedy {k + 1}: routed {len(order) - len(fl)}/{len(order)}  total L {totL:.0f} mm  failed {fl}  ({time.time() - t1:.0f} s)')
        sc = (len(fl), totL)
        if bestg is None or sc < bestg[0]:
            bestg = (sc, copy.deepcopy(NEW), copy.deepcopy(rr), seq)
            json.dump({n: NEW[n] for n in NETS}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_routes_greedy.json'), 'w'))
    NEW.clear(); NEW.update(bestg[1]); res = bestg[2]
    log(f'greedy best: {bestg[0]}')
    ITERS = 0


def net_len(n):
    return sum(math.hypot(t[1][2] - t[1][0], t[1][3] - t[1][1]) for t in NEW[n]['trk'])


def connected(n):
    """U5 end reaches U30 end through the fan-out stubs/vias and NEW copper (points within 0.01 mm join)"""
    segs = [(t[1][0], t[1][1], t[1][2], t[1][3]) for t in NEW[n]['trk']]
    for e in DDRFILE:
        if e['net'] == n and e['cls'] == 'trk':
            segs.append(tuple(e['s'][1:5]))
    pts = [(x, y) for x, y in NEW[n]['via']] + [lfr.shape_center(e['s']) for e in DDRFILE if e['net'] == n and e['cls'] == 'via']
    A, B = STATIC[n]['A'][0], STATIC[n]['B'][0]
    nodes = [A, B] + pts + [(s_[0], s_[1]) for s_ in segs] + [(s_[2], s_[3]) for s_ in segs]
    key = lambda p: (round(p[0] / 0.01), round(p[1] / 0.01))
    par = {}
    def find(k):
        while par.setdefault(k, k) != k:
            par[k] = par[par[k]]; k = par[k]
        return k
    for s_ in segs:
        par[find(key((s_[0], s_[1])))] = find(key((s_[2], s_[3])))
    for p in nodes:
        find(key(p))
    return find(key(A)) == find(key(B))


if opt('--from'):
    import eprj_core as ec
    BC = ec.Board(opt('--from'))
    k3 = lambda v: round(v, 3)
    fixed_t = set(); fixed_v = set()
    for e in DDRFILE:
        if e['cls'] == 'trk':
            s_ = e['s']; l_ = next(iter(e['layers']))
            fixed_t.add((e['net'], l_, k3(s_[1]), k3(s_[2]), k3(s_[3]), k3(s_[4])))
            fixed_t.add((e['net'], l_, k3(s_[3]), k3(s_[4]), k3(s_[1]), k3(s_[2])))
        elif e['cls'] == 'via':
            c_ = lfr.shape_center(e['s']); fixed_v.add((e['net'], k3(c_[0]), k3(c_[1])))
    for n in NETS:
        NEW[n] = dict(trk=[], via=[])
    for t in BC.tracks:
        if t.net in DDRSET:
            (x1, y1), (x2, y2) = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
            if (t.net, t.layer, k3(x1), k3(y1), k3(x2), k3(y2)) not in fixed_t and math.hypot(x2 - x1, y2 - y1) > 1e-6:
                NEW[t.net]['trk'].append((t.layer, (x1, y1, x2, y2), t.width * 0.0254))
    for v in BC.vias:
        if v.net in DDRSET:
            x, y = lfr.to_mm(v.x, v.y)
            if (v.net, k3(x), k3(y)) not in fixed_v:
                NEW[v.net]['via'].append((x, y))
    res = {}
    for n in NETS:
        ok = connected(n)
        res[n] = dict(over=0, vias=len(NEW[n]['via']), layers=sorted({t[0] for t in NEW[n]['trk']}), L=net_len(n)) if ok else None
        if not ok:
            NEW[n] = dict(trk=[], via=[])
    log(f'loaded routes from {opt("--from")}: open {[n for n in NETS if not res[n]]}')
    ITERS = 0
pres = 0.5
if not opt('--greedy') and not opt('--from'):
    res = {}
best = None
for it in range(ITERS):
    t1 = time.time()
    tot_over, fails = 0, []
    seq = order if it == 0 else random.Random(it).sample(order, len(order))
    for n in seq:
        A = STATIC[n]['A']
        r = route_one(n, pres, maxvias=2 if A[1] == [TOP] else 1)
        res[n] = r
        if r is None:
            fails.append(n); NEW[n] = dict(trk=[], via=[])
        else:
            tot_over += r['over']
    conf = [n for n in order if res[n] and res[n]['over']]
    log(f'iter {it + 1}: pres {pres:.2f}  overlap cells {tot_over}  conflicted {len(conf)} {conf[:8]}  failed {fails}  '
        f'({time.time() - t1:.0f} s)')
    score = (len(conf) + len(fails)) * 100 + tot_over
    if best is None or score < best[0]:
        best = (score, copy.deepcopy(NEW), copy.deepcopy(res))
        json.dump({n: NEW[n] for n in NETS}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_routes.json'), 'w'))
    if not conf and not fails:
        break
    pres = min(pres * 1.6, 400.0)
if best is not None:
    NEW.clear(); NEW.update(best[1]); res = best[2]
conf = [n for n in order if res[n] and res[n]['over']]; fails = [n for n in order if not res[n]]
log(f'best: conflicted {conf}, failed {fails}')
def overlap_nets(net):
    """other nets whose NEW copper violates the rule against `net`'s NEW copper (exact segment distances)"""
    out = set()
    p = PARTNER.get(net)
    mine = NEW[net]
    for o, d in NEW.items():
        if o == net:
            continue
        hit = False
        for lay, a, w in mine['trk']:
            for lay2, b, w2 in d['trk']:
                if lay != lay2:
                    continue
                need = (PG if o == p else W.TT) + (w + w2) / 2 - 1e-4
                if lfr._segseg((a[0], a[1]), (a[2], a[3]), (b[0], b[1]), (b[2], b[3])) < need:
                    hit = True; break
            if hit:
                break
        if not hit:
            for (vx, vy) in mine['via']:
                for lay2, b, w2 in d['trk']:
                    if lfr.pt_seg(vx, vy, ((b[0], b[1]), (b[2], b[3]))) < W.CLR + VD / 2 + w2 / 2 - 1e-4:
                        hit = True; break
                for (ux, uy) in d['via']:
                    if math.hypot(ux - vx, uy - vy) < VD + W.HH:
                        hit = True
                if hit:
                    break
        if not hit:
            for lay, a, w in mine['trk']:
                for (ux, uy) in d['via']:
                    if lfr.pt_seg(ux, uy, ((a[0], a[1]), (a[2], a[3]))) < W.CLR + VD / 2 + w / 2 - 1e-4:
                        hit = True; break
                if hit:
                    break
        if hit:
            out.add(o)
    return out



for n_ in FV:                               # place the field via, rip what it touches; the hard pass re-routes them
    NEW[n_] = copy.deepcopy(FIXN[n_]); res[n_] = None
    vic = sorted(overlap_nets(n_))
    for v in vic:
        NEW[v] = dict(trk=[], via=[]); res[v] = None
    log(f'field via for {n_} at {FV[n_]}: ripped {vic}')
MVO = {k: int(v) for k, v in (x.split('=') for x in (opt('--mv') or '').split(',') if x)}
MV = lambda n: MVO.get(n, 2 if STATIC[n]['A'][1] == [TOP] else 1)


def shorten_pass():
    GROUPS = [BYTE0 + ['DDRAM_DQS_P0', 'DDRAM_DQS_N0'], BYTE1 + ['DDRAM_DQS_P1', 'DDRAM_DQS_N1'], ADDR + ['DDRAM_CLK_P', 'DDRAM_CLK_N']]
    for rnd in range(2):
        for g in GROUPS:
            ls = sorted(net_len(n) for n in g if res.get(n))
            med = ls[len(ls) // 2]
            for n in sorted((n for n in g if res.get(n) and n not in PARTNER), key=net_len, reverse=True):
                L0 = net_len(n)
                if L0 < med + 3.0:
                    break
                old = copy.deepcopy(NEW[n]); NEW[n] = dict(trk=[], via=[])
                r = route_one(n, 1.0, maxvias=MV(n), hardall=True)
                if r and r['L'] < L0 - 1.0:
                    res[n] = r; log(f'  shorten {n}: {L0:.1f} -> {r["L"]:.1f} mm')
                else:
                    NEW[n] = old


if '--shorten' in args:
    shorten_pass()
# hard pass: open / conflicted nets only, everything else hard
for rnd in range(2):
    todo = [n for n in order if not res.get(n) or res[n]['over']]
    for n in todo:
        NEW[n] = dict(trk=[], via=[])
        r = route_one(n, 1.0, maxvias=MV(n), hardall=True)
        res[n] = r
        if r is None:
            NEW[n] = dict(trk=[], via=[])
        log(f'  hard pass {rnd + 1}: {n} ' + ('FAILED' if r is None else f'ok L={r["L"]:.1f} {r["layers"]} vias+{r["vias"]}'))
# transactional rip-up: route the open net soft, rip what it touches, re-route those hard; undo unless all succeed
for rnd in range(4):
    todo = [n for n in order if not res.get(n)]
    if not todo:
        break
    for n in todo:
        snapN, snapR = copy.deepcopy(NEW), copy.deepcopy(res)
        r = route_one(n, 3.0, maxvias=MV(n))
        if r is None:
            log(f'  rip-up {rnd + 1}: {n} has no path even soft'); continue
        victims = sorted(overlap_nets(n))
        res[n] = dict(r, over=0)
        okall = True
        for v in victims:
            NEW[v] = dict(trk=[], via=[])
        for v in victims:
            rv = route_one(v, 1.0, maxvias=MV(v), hardall=True)
            res[v] = rv
            if rv is None:
                okall = False; break
        if okall and not overlap_nets(n):
            log(f'  rip-up {rnd + 1}: {n} routed, re-routed {victims}')
        else:
            NEW.clear(); NEW.update(snapN); res.clear(); res.update(snapR)
            log(f'  rip-up {rnd + 1}: {n} undone (victims {victims})')
conf = [n for n in order if res.get(n) and res[n]['over']]; fails = [n for n in order if not res.get(n)]
audit = {n: sorted(overlap_nets(n)) for n in NETS if NEW[n]['trk']}
log(f'final: open {fails}, conflicted {conf}, exact overlap audit {[n for n, v in audit.items() if v]}')
json.dump({n: NEW[n] for n in NETS}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_routes.json'), 'w'))

# ---------------------------------------------------------------- commit to the World, tune, check, write
for n in NETS:
    for lay, (x1, y1, x2, y2), w in NEW[n]['trk']:
        W.add_track(n, lay, (x1, y1), (x2, y2), w)
    for (x, y) in NEW[n]['via']:
        W.add_via(n, x, y, VD, VH)
for n in NETS:
    r = res.get(n)
    log(f'  {n:16} ' + (f'L={r["L"]:.1f} layers {r["layers"]} vias+{r["vias"]} over {r["over"]}' if r else 'FAILED'))

if not conf and not fails and '--no-tune' not in args:
    log('length tuning')
    L = lambda: lfr.net_lengths(W, DDRSET)
    for name, (P, N) in PAIRS.items():
        log(f'  skew {name}: {lfr.tune_pair(W, P, N, tol=0.05):+.3f} mm')
    for ref, members, tol in (('DQS0', BYTE0, 1.27), ('DQS1', BYTE1, 1.27), ('CLK', ADDR, 2.54)):
        P, N = PAIRS[ref]
        Ls = L(); Lr = (Ls[P] + Ls[N]) / 2
        longest = max([Ls[n] for n in members] + [Lr])
        if longest > Lr + 0.6 * tol:
            dl = longest - 0.4 * tol - Lr
            for a, b in ((P, N), (N, P)):
                lfr.tune_len(W, a, dl, partner=b, pgap=PG, sepnets=DDRSET, sep=SEPV, wmin=WW, log=log)
            lfr.tune_pair(W, P, N, tol=0.05)
            Ls = L(); Lr = (Ls[P] + Ls[N]) / 2
        for n in members:
            short = (Lr - 0.4 * tol) - Ls[n]
            if short > 0:
                lfr.tune_len(W, n, short + 0.1, sepnets=DDRSET, sep=SEPV, wmin=WW, log=log)
        Ls = L(); dev = {n: Ls[n] - Lr for n in members}
        log(f'  group {ref}: ref {Lr:.2f} mm, spread {min(dev.values()):+.2f}..{max(dev.values()):+.2f}, '
            f'out of tol {[(n, round(v, 2)) for n, v in dev.items() if abs(v) > tol]}')
    Ls = L()
    log('  pair skews ' + ', '.join(f'{k} {Ls[P] - Ls[N]:+.3f}' for k, (P, N) in PAIRS.items()))

acute, right = lfr.acute_check(W, DDRSET)
log(f'acute {len(acute)} right {len(right)} {acute[:5]} {right[:5]}')
log(f'edge {W.edge_check()[:5]}')
if PNG:
    lfr.render(W, PNG, box=(60, 14, 95, 50), title='DDR3 routing (negotiated)')
if OUT:
    p, n = lfr.write_candidate(W, OUT)
    log(f'candidate {p}: {n} records')
