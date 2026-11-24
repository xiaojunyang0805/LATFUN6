"""U5 BGA escape for the remaining FPGA signals (layout worknote W6b), by negotiated congestion (PathFinder).
Every U5 ball whose net is not yet joined to the rest of its net is routed from the ball (or its own fan-out via) to
an ESCAPE BAND around the U5 field (1.0 - 2.6 mm outside it), on the side facing the net's destination (+-55 deg).
Inside the field tracks neck to 0.09 mm (on-grid channels between 0.8 mm-pitch vias, sampling margin 0.002 mm),
outside 0.127 mm; new vias only outside the field, at most one per net. Other escapes are a soft cost (present
overlap x pres, growing, + history); everything already on the board is hard. route_rest.py then joins the escape
ends to their destinations across the open board.
    python escape.py IN.eprj OUT.eprj [--iters 30] [--png OUT.png]"""
import sys, os, math, time, json, copy, random
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec, eprj_check
import lfr, astar_nb
from lfr import G, DIRS

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst = args[0], args[1]
ITERS = int(opt('--iters', 30))
TOP, BOT, IN2, IN5 = 1, 2, 16, 19          # 8-layer stack: signal layers Top / In2 / In5 / Bottom
RL = [TOP, IN2, IN5, BOT]
LC = {TOP: 1.0, IN2: 1.1, IN5: 1.1, BOT: 1.2}
WW, WN, MN = 0.127, 0.09, 0.002
VD, VH = 0.40, 0.20
SECTOR = float(opt('--sector', 80))
B1, B2 = 1.0, 2.6                         # escape band, mm outside the U5 field
log = lambda *a: print(*a, flush=True)

B = ec.Board(src)
isl = eprj_check.islands(B)
W = lfr.World(src)
W.add_field('U5'); W.add_field('U30')
FX0, FY0, FX1, FY1 = W.fields[0]
CX, CY = (FX0 + FX1) / 2, (FY0 + FY1) / 2
ORIG = W.blocked

# ---------------------------------------------------------------- which nets need an escape
jobs = {}
for net, g in isl.items():
    if not net or net == 'GND':
        continue
    gs = [x for x in g if x['pads']]
    if len(gs) < 2:
        continue
    for x in gs:
        u5 = [p for p in x['pads'] if p.des == 'U5']
        if u5 and len(x['pads']) == 1 and len(x['tracks']) <= 2:
            others = [lfr.shape_center(W.pad[f'{p.des}.{p.num}']['s']) for y in gs if y is not x for p in y['pads']
                      if f'{p.des}.{p.num}' in W.pad]
            if not others:
                continue
            ball = lfr.shape_center(W.pad[f'U5.{u5[0].num}']['s'])
            dest = min(others, key=lambda q: math.hypot(q[0] - ball[0], q[1] - ball[1]))
            jobs[net] = dict(ball=ball, dest=dest, num=u5[0].num)
NETS = sorted(jobs)
log(f'{len(NETS)} U5 nets need an escape')
NSET = set(NETS)


def own_vias(net):
    return [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net]


def unit(k):
    dx, dy = DIRS[k]; L = math.hypot(dx, dy); return dx / L, dy / L


def _m(m, fn):
    m0 = lfr.M; lfr.M = m
    try:
        return fn()
    finally:
        lfr.M = m0


STATIC = {}
WIN = W.win([(FX0, FY0), (FX1, FY1)], B2 + 3.0)


def static(net):
    if net in STATIC:
        return STATIC[net]
    j = jobs[net]
    win = WIN
    ix0, iy0, ix1, iy1 = win
    hgt, wid = iy1 - iy0 + 1, ix1 - ix0 + 1
    X, Y = np.meshgrid(np.arange(ix0, ix1 + 1) * G, np.arange(iy0, iy1 + 1) * G)
    zone = (X >= FX0) & (X <= FX1) & (Y >= FY0) & (Y <= FY1)
    own = {net}
    fw, fn = {}, {}
    for l in RL:
        fw[l] = ~ORIG(own, l, WW / 2, win)
        fn[l] = ~_m(MN, lambda: ORIG(own, l, WN / 2, win)) & zone
    vok = W.via_ok(own, win, dia=VD, hole=VH)
    # start: own fan-out via within 0.8 mm of the ball (any layer), else the ball on Top
    ov = [v for v in own_vias(net) if math.hypot(v[0] - j['ball'][0], v[1] - j['ball'][1]) < 0.8]
    start = (ov[0], RL) if ov else (j['ball'], [TOP])
    # Top stub at the via: no turn sharper than 90 degrees against it
    stub = []
    if ov:
        u = (j['ball'][0] - ov[0][0], j['ball'][1] - ov[0][1]); L = math.hypot(*u)
        stub = [(u[0] / L, u[1] / L)]
    # goal band on the destination side
    dx, dy = j['dest'][0] - CX, j['dest'][1] - CY
    ang = math.atan2(dy, dx)
    A = np.arctan2(Y - CY, X - CX)
    dang = np.abs((A - ang + math.pi) % (2 * math.pi) - math.pi)
    dist_out = np.maximum.reduce([FX0 - X, X - FX1, FY0 - Y, Y - FY1])
    band = (dist_out >= B1) & (dist_out <= B2) & (dang <= math.radians(SECTOR))
    hx = int(round((CX + math.cos(ang) * ((FX1 - FX0) / 2 + B2)) / G)) - ix0
    hy = int(round((CY + math.sin(ang) * ((FY1 - FY0) / 2 + B2)) / G)) - iy0
    hx = min(max(hx, 0), wid - 1); hy = min(max(hy, 0), hgt - 1)
    STATIC[net] = dict(win=win, zone=zone, fw=fw, fn=fn, vok=vok & ~zone, start=start, stub=stub, band=band,
                       h=(hx, hy), ownv=own_vias(net))
    return STATIC[net]


NEW = {n: dict(trk=[], via=[]) for n in NETS}
HIST = {l: np.zeros((WIN[3] - WIN[1] + 1, WIN[2] - WIN[0] + 1), np.float32) for l in RL}


def stamp(arr, s, R, val=1):
    ix0, iy0, ix1, iy1 = WIN
    b = lfr.shape_bbox(s)
    jx0 = max(int(math.floor((b[0] - R) / G)), ix0); jx1 = min(int(math.ceil((b[2] + R) / G)), ix1)
    jy0 = max(int(math.floor((b[1] - R) / G)), iy0); jy1 = min(int(math.ceil((b[3] + R) / G)), iy1)
    if jx1 < jx0 or jy1 < jy0:
        return
    Xs, Ys = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
    m = lfr.shape_dist(s, Xs, Ys) < R
    if val is True:
        arr[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] |= m
    else:
        arr[jy0 - iy0:jy1 - iy0 + 1, jx0 - ix0:jx1 - ix0 + 1] += m.astype(arr.dtype)


def dynamic(net):
    shp = (WIN[3] - WIN[1] + 1, WIN[2] - WIN[0] + 1)
    cw = {l: np.zeros(shp, np.int16) for l in RL}; cn = {l: np.zeros(shp, np.int16) for l in RL}
    vbad = np.zeros(shp, bool)
    for o, d in NEW.items():
        if o == net:
            continue
        for lay, (x1, y1, x2, y2), w in d['trk']:
            s = ('k', x1, y1, x2, y2, w / 2)
            stamp(cw[lay], s, W.TT + WW / 2 + lfr.M); stamp(cn[lay], s, W.TT + WN / 2 + MN)
            stamp(vbad, s, W.CLR + VD / 2 + lfr.M, True)
        for (x, y) in d['via']:
            s = ('c', x, y, VD / 2)
            for l in RL:
                stamp(cw[l], s, W.CLR + WW / 2 + lfr.M); stamp(cn[l], s, W.CLR + WN / 2 + MN)
            stamp(vbad, s, VD + W.HH, True)
    return cw, cn, vbad


def route_one(net, pres, hardall=False, maxexp=3_000_000):
    st = static(net)
    ix0, iy0 = st['win'][0], st['win'][1]
    cw, cn, vbad = dynamic(net)
    frees, cost, wide = [], [], []
    for l in RL:
        fwi = st['fw'][l].copy(); fni = st['fn'][l].copy()
        if hardall:
            fwi &= cw[l] == 0; fni &= cn[l] == 0
        frees.append(fwi | fni); wide.append(fwi)
        cnt = np.where(fwi, cw[l], cn[l]).astype(np.float32)
        cost.append(np.maximum(LC[l] + 0.6 * HIST[l] + pres * cnt, 0.3).astype(np.float32))
    vok = st['vok'] & (~vbad if hardall else True)
    for (vx, vy) in st['ownv']:                   # own vias: free layer change
        cx, cy = int(round(vx / G)) - ix0, int(round(vy / G)) - iy0
        if 0 <= cy < vok.shape[0] and 0 <= cx < vok.shape[1]:
            vok[cy, cx] = True
            for f in frees:
                f[cy, cx] = True
    (a, al) = st['start']
    sx, sy = int(round(a[0] / G)) - ix0, int(round(a[1] / G)) - iy0
    slay = np.array([l in al for l in RL])
    for i, l in enumerate(RL):
        if l in al:
            frees[i][sy, sx] = True
    sdir = np.ones((len(RL), 8), bool)
    for k in range(8):
        u = unit(k)
        sdir[0, k] = all(u[0] * v[0] + u[1] * v[1] < -1e-6 for v in st['stub'])
    gmask = np.ascontiguousarray(np.stack([st['band'] & f for f in frees]))
    viac = ((pres / G) * vbad).astype(np.float32)
    best = None
    for vc in (2.0, 8.0):
        path = astar_nb.astar_region(np.ascontiguousarray(np.stack(frees)), np.ascontiguousarray(np.stack(cost)),
                                     np.ascontiguousarray(vok), sx, sy, slay, sdir, st['h'][0], st['h'][1], gmask,
                                     0.4 / G, vc / G, 1.3, maxexp, viac)
        if len(path) == 0:
            continue
        path = [(int(x), int(y), int(i)) for x, y, i in path]
        newv = [(p[0], p[1]) for p, q in zip(path, path[1:]) if p[2] != q[2] and not any(
            abs(p[0] - (int(round(vx / G)) - ix0)) < 1 and abs(p[1] - (int(round(vy / G)) - iy0)) < 1 for vx, vy in st['ownv'])]
        if best is None or len(newv) < best[0]:
            best = (len(newv), path)
        if len(newv) <= 1:
            break
    if best is None:
        return None
    path = best[1]
    over = 0
    for (x, y, li) in path:
        l = RL[li]
        c = cw[l][y, x] if wide[li][y, x] else cn[l][y, x]
        if c > 0:
            over += 1; HIST[l][y, x] += 1.0
    runs = [[path[0]]]
    for p in path[1:]:
        (runs[-1].append(p) if p[2] == runs[-1][-1][2] else runs.append([p]))
    trk, via = [], []
    for ri, run in enumerate(runs):
        li = run[0][2]; lay = RL[li]
        segs = []
        for p, q in zip(run, run[1:]):
            k = (q[0] - p[0], q[1] - p[1])
            wd = WW if (wide[li][p[1], p[0]] and wide[li][q[1], q[0]]) else WN
            if segs and segs[-1][0] == k and segs[-1][1] == wd:
                segs[-1][3] = q
            else:
                segs.append([k, wd, p, q])
        for si, sg in enumerate(segs):
            p = ((sg[2][0] + ix0) * G, (sg[2][1] + iy0) * G); q = ((sg[3][0] + ix0) * G, (sg[3][1] + iy0) * G)
            if ri == 0 and si == 0:
                p = a
            trk.append((lay, (p[0], p[1], q[0], q[1]), sg[1]))
        if ri + 1 < len(runs):
            vx, vy = (run[-1][0] + ix0) * G, (run[-1][1] + iy0) * G
            if not any(math.hypot(vx - ox, vy - oy) < 0.04 for ox, oy in st['ownv']):
                via.append((vx, vy))
    NEW[net] = dict(trk=trk, via=via)
    return dict(over=over, vias=len(via))


t0 = time.time()
for n in NETS:
    static(n)
log(f'static masks {time.time() - t0:.0f} s')
pres = 0.5; res = {}; best = None
order = sorted(NETS, key=lambda n: -min(jobs[n]['ball'][0] - FX0, FX1 - jobs[n]['ball'][0],
                                         jobs[n]['ball'][1] - FY0, FY1 - jobs[n]['ball'][1]))   # inner balls first
for it in range(ITERS):
    t1 = time.time()
    seq = order if it == 0 else random.Random(it).sample(order, len(order))
    for n in seq:
        r = route_one(n, pres)
        res[n] = r
        if r is None:
            NEW[n] = dict(trk=[], via=[])
    conf = [n for n in NETS if res[n] and res[n]['over']]; fails = [n for n in NETS if not res[n]]
    tot = sum(res[n]['over'] for n in NETS if res[n])
    log(f'iter {it + 1}: pres {pres:.1f} overlap {tot} conflicted {len(conf)} failed {len(fails)} ({time.time() - t1:.0f} s)')
    score = (len(conf) + len(fails)) * 100 + tot
    if best is None or score < best[0]:
        best = (score, copy.deepcopy(NEW), copy.deepcopy(res))
    if not conf and not fails:
        break
    pres = min(pres * 1.6, 400.0)
NEW.clear(); NEW.update(best[1]); res = best[2]
# leftovers: re-route hard against everything; drop if impossible
for n in [n for n in NETS if not res[n] or res[n]['over']]:
    NEW[n] = dict(trk=[], via=[])
for n in [n for n in NETS if not res[n] or res[n]['over']]:
    r = route_one(n, 1.0, hardall=True)
    res[n] = r
    if r is None:
        NEW[n] = dict(trk=[], via=[])
fails = [n for n in NETS if not res[n]]
log(f'escapes: {len(NETS) - len(fails)}/{len(NETS)} ok; no escape: {fails}')
for n in NETS:
    for lay, (x1, y1, x2, y2), w in NEW[n]['trk']:
        if math.hypot(x2 - x1, y2 - y1) > 1e-6:
            W.add_track(n, lay, (x1, y1), (x2, y2), w)
    for (x, y) in NEW[n]['via']:
        W.add_via(n, x, y, VD, VH)
acute, right = lfr.acute_check(W)
log(f'acute {len(acute)} right {len(right)}; edge {W.edge_check()[:3]}')
if opt('--png'):
    lfr.render(W, opt('--png'), box=(FX0 - 6, FY0 - 6, FX1 + 6, FY1 + 6), title='U5 escapes')
p, nrec = lfr.write_candidate(W, dst)
log(f'candidate {p}: {nrec} records')
