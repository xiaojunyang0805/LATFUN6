"""U5 nets routed ball -> destination by negotiated congestion (PathFinder), extending escape.py: an escape
alone was walled in by later routes (rest9: 166 failed, escape ends sealed in 300-2000-cell pockets), so the
whole U5 connection is negotiated: goal = the nearest point of the net's nearest other island (pad, or track end /
via outside the BGA fields). Per-net windows, static masks bit-packed, history board-wide. Pair nets keep
P/N >= 0.203 mm (soft).
escape.py description: U5 BGA escape for the remaining FPGA signals (layout worknote W6b), by negotiated congestion (PathFinder).
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
WW, WN, MN = float(opt("--ww", 0.127)), 0.09, 0.002
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

infield = lambda q: any(f[0] - 0.3 <= q[0] <= f[2] + 0.3 and f[1] - 0.3 <= q[1] <= f[3] + 0.3 for f in W.fields)
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
            cands = []
            for y in gs:
                if y is x:
                    continue
                for p in y['pads']:
                    k = f'{p.des}.{p.num}'
                    if k in W.pad:
                        cands.append((lfr.shape_center(W.pad[k]['s']), [l for l in RL if l in W.pad[k]['layers']]))
                for t in y['tracks']:
                    for (xx, yy) in ((t.x1, t.y1), (t.x2, t.y2)):
                        q = lfr.to_mm(xx, yy)
                        if not infield(q) and t.layer in RL:
                            cands.append((q, [t.layer]))
                for v in y['vias']:
                    q = lfr.to_mm(v.x, v.y)
                    if not infield(q):
                        cands.append((q, list(RL)))
            cands = [c_ for c_ in cands if c_[1]]
            if not cands:
                continue
            dest, dl = min(cands, key=lambda c_: math.hypot(c_[0][0] - ball[0], c_[0][1] - ball[1]))
            jobs[net] = dict(ball=ball, dest=dest, dl=dl, num=u5[0].num)
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
WIN = (0, 0, W.NX - 1, W.NY - 1)                 # board-wide frame for the history cost
pk = lambda a: (np.packbits(a, axis=None), a.shape)
uk = lambda t: np.unpackbits(t[0], count=t[1][0] * t[1][1]).reshape(t[1]).astype(bool)


def partner(net):
    import re as _re
    for x_, y_ in (('_P', '_N'), ('_N', '_P'), ('DP', 'DN'), ('DN', 'DP')):
        m = _re.match(r'^(.*)' + x_ + r'(\d?)$', net)
        if m and _re.match(r'^(GPDI_|ETH_MDI|USB)', net):
            return m.group(1) + y_ + m.group(2)
    return None


def static(net):
    if net in STATIC:
        return STATIC[net]
    j = jobs[net]
    win = W.win([j['ball'], j['dest']], 4.0)
    ix0, iy0, ix1, iy1 = win
    hgt, wid = iy1 - iy0 + 1, ix1 - ix0 + 1
    X, Y = np.meshgrid(np.arange(ix0, ix1 + 1) * G, np.arange(iy0, iy1 + 1) * G)
    zone = np.zeros(X.shape, bool)
    for f in W.fields:
        zone |= (X >= f[0]) & (X <= f[2]) & (Y >= f[1]) & (Y <= f[3])
    own = {net}
    fw, fn = {}, {}
    pn = partner(net)
    ownp = own | ({pn} if pn else set())          # partner copper is a soft (P/N gap) cost, not hard
    for l in RL:
        fw[l] = ~ORIG(ownp, l, WW / 2, win)
        fn[l] = ~_m(MN, lambda: ORIG(ownp, l, WN / 2, win)) & zone
    vok = W.via_ok(own, win, dia=VD, hole=VH)
    # start: own fan-out via within 0.8 mm of the ball (any layer), else the ball on Top
    ov = [v for v in own_vias(net) if math.hypot(v[0] - j['ball'][0], v[1] - j['ball'][1]) < 0.8]
    start = (ov[0], RL) if ov else (j['ball'], [TOP])
    # Top stub at the via: no turn sharper than 90 degrees against it
    stub = []
    if ov:
        u = (j['ball'][0] - ov[0][0], j['ball'][1] - ov[0][1]); L = math.hypot(*u)
        stub = [(u[0] / L, u[1] / L)]
    # goal: a 0.12 mm disc at the destination point, on its layers
    band = np.hypot(X - j['dest'][0], Y - j['dest'][1]) <= 0.12
    hx = min(max(int(round(j['dest'][0] / G)) - ix0, 0), wid - 1); hy = min(max(int(round(j['dest'][1] / G)) - iy0, 0), hgt - 1)
    STATIC[net] = dict(win=win, zone=pk(zone), fw={l: pk(v) for l, v in fw.items()}, fn={l: pk(v) for l, v in fn.items()},
                       vok=pk(vok & ~zone), start=start, stub=stub, band=pk(band), dl=j['dl'],
                       h=(hx, hy), ownv=own_vias(net))
    return STATIC[net]


NEW = {n: dict(trk=[], via=[]) for n in NETS}
HIST = {l: np.zeros((WIN[3] - WIN[1] + 1, WIN[2] - WIN[0] + 1), np.float32) for l in RL}


def stamp(arr, s, R, val=1, win=None):
    ix0, iy0, ix1, iy1 = win or WIN
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
    win = STATIC[net]['win']; pn = partner(net)
    shp = (win[3] - win[1] + 1, win[2] - win[0] + 1)
    stamp_ = lambda arr, s, R, val=1: stamp(arr, s, R, val, win)
    cw = {l: np.zeros(shp, np.int16) for l in RL}; cn = {l: np.zeros(shp, np.int16) for l in RL}
    vbad = np.zeros(shp, bool)
    for o, d in NEW.items():
        if o == net:
            continue
        for lay, (x1, y1, x2, y2), w in d['trk']:
            s = ('k', x1, y1, x2, y2, w / 2)
            rr = 0.206 if o == pn else W.TT
            stamp_(cw[lay], s, rr + WW / 2 + lfr.M); stamp_(cn[lay], s, rr + WN / 2 + MN)
            stamp_(vbad, s, W.CLR + VD / 2 + lfr.M, True)
        for (x, y) in d['via']:
            s = ('c', x, y, VD / 2)
            for l in RL:
                stamp_(cw[l], s, W.CLR + WW / 2 + lfr.M); stamp_(cn[l], s, W.CLR + WN / 2 + MN)
            stamp_(vbad, s, VD + W.HH, True)
    return cw, cn, vbad


def route_one(net, pres, hardall=False, maxexp=12_000_000):
    st = static(net)
    ix0, iy0, ix1, iy1 = st['win']
    cw, cn, vbad = dynamic(net)
    frees, cost, wide = [], [], []
    for l in RL:
        fwi = uk(st['fw'][l]); fni = uk(st['fn'][l])
        if hardall:
            fwi &= cw[l] == 0; fni &= cn[l] == 0
        frees.append(fwi | fni); wide.append(fwi)
        cnt = np.where(fwi, cw[l], cn[l]).astype(np.float32)
        hs = HIST[l][iy0:iy1 + 1, ix0:ix1 + 1]
        cost.append(np.maximum(LC[l] + float(opt("--hist", 0.6)) * hs + pres * cnt, 0.3).astype(np.float32))
    vok = uk(st['vok']) & (~vbad if hardall else True)
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
    band = uk(st['band'])
    gmask = np.ascontiguousarray(np.stack([band if l in st['dl'] else np.zeros_like(band) for l in RL]))
    for i, l in enumerate(RL):
        if l in st['dl']:
            frees[i] |= band
    viac = ((pres / G) * vbad).astype(np.float32)
    best = None
    for vc in (2.0, 8.0):
        path = astar_nb.astar_region(np.ascontiguousarray(np.stack(frees)), np.ascontiguousarray(np.stack(cost)),
                                     np.ascontiguousarray(vok), sx, sy, slay, sdir, st['h'][0], st['h'][1], gmask,
                                     0.4 / G, vc / G, 1.5, maxexp, viac)
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
            over += 1; HIST[l][y + iy0, x + ix0] += 1.0
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
    pres = min(pres * float(opt("--pgrow", 1.6)), 400.0)
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
    lfr.render(W, opt('--png'), box=(0, 0, 145, 111), title='U5 nets')
p, nrec = lfr.write_candidate(W, dst)
log(f'candidate {p}: {nrec} records')
