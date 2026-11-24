"""Finish the remaining connections (layout worknote W6b): every split net (except plane-delivered GND) is joined
island to island along a minimum spanning tree of nearest pads, each connection routed by the compiled octilinear A*
(astar_nb) on Top / Inner2 / Bottom with 0.40/0.20 vias outside the BGA fields, against exact rasterised clearance
(lfr). Widths: PWR class 0.30 mm, pair nets keep their impedance width, everything else 0.127 mm.
    python route_rest.py IN.eprj OUT.eprj [--skip NET,..] [--png OUT.png]"""
import sys, os, math, time, re, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec, eprj_check
import lfr, astar_nb
from lfr import G

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst = args[0], args[1]
SKIP = set((opt('--skip') or '').split(',')) | {'GND'}
TOP, BOT, IN2, IN3, IN5 = 1, 2, 16, 17, 19
IN1, IN4, IN6 = 15, 18, 20
RL = [TOP, IN2, IN5, BOT, IN3]            # 8-layer stack; In3 (PWR layer) only for PWR-class nets
LC = {TOP: 1.0, BOT: 1.15, IN2: 1.2, IN5: 1.2, IN3: 1.0}
ALL = '--all-layers' in args              # user 2026-11-23: every layer carries routing; pours only fill what is left
if ALL:
    RL = [TOP, IN2, IN5, BOT, IN3, IN1, IN4, IN6]
    LC = {TOP: 1.0, BOT: 1.15, IN2: 1.2, IN5: 1.2, IN3: 1.3, IN1: 1.5, IN4: 1.5, IN6: 1.5}
# reference layers of the impedance-controlled copper: new copper keeps out of a band under it there
REFL = {TOP: [IN1], IN2: [IN1, IN3], IN5: [IN4, IN6], BOT: [IN6]}
CRIT = re.compile(r'^(DDRAM_|GPDI_(D\d|CLK)_|ETH_MDI\d_|USB2?_D[PN]|SMA_|PCIE_(HD|RX|TX|REFCLK)|REFCLK|SFP_(TX|RX)D|HD[TR]X)')
BAND = float(opt('--band', 0.30))         # mm beyond the critical track's edge
ALT = int(opt('--alt', 0))                 # alternative endpoint pairs tried per failed join
WN, MN = 0.09, 0.002                      # necked width inside the BGA fields (channels between 0.8 mm-pitch vias)
VD, VH = 0.40, 0.20
log = lambda *a: print(*a, flush=True)

B = ec.Board(src)
isl = eprj_check.islands(B)
W = lfr.World(src)
for d in ('U5', 'U30'):
    W.add_field(d)
LIS = [W.LI[l] for l in RL]


def width(net):
    if B.net_class.get(net) == 'PWR':
        return 0.30
    if re.match(r'^(GPDI_(D\d|CLK)_[PN]|ETH_MDI\d_[PN])$', net):
        return 0.10
    if re.match(r'^USB2?_D[PN]$', net):
        return 0.127
    return max(0.127, B.net_width_rule(net)[0] * 0.0254)


def pad_pt(p):
    k = f'{p.des}.{p.num}'
    e = W.pad.get(k)
    if e is None:
        return None
    return lfr.shape_center(e['s']), [l for l in RL if l in e['layers']]


def zone_mask(win):
    ix0, iy0, ix1, iy1 = win
    z = np.zeros((iy1 - iy0 + 1, ix1 - ix0 + 1), bool)
    for (fx0, fy0, fx1, fy1) in W.fields:
        a0, b0 = max(int(math.ceil(fx0 / G)) - ix0, 0), max(int(math.ceil(fy0 / G)) - iy0, 0)
        a1, b1 = int(math.floor(fx1 / G)) - ix0 + 1, int(math.floor(fy1 / G)) - iy0 + 1
        if a1 > 0 and b1 > 0:
            z[b0:b1, a0:a1] = True
    return z


def partner(net):
    for x, y in (('_P', '_N'), ('_N', '_P'), ('DP', 'DN'), ('DN', 'DP')):
        m = re.match(rf'^(.*){x}(\d?)$', net)
        if m and re.match(r'^(GPDI_|ETH_MDI|USB)', net):
            return f'{m.group(1)}{y}{m.group(2)}'
    return None


def route(net, a, al, b, bl, w, margin):
    win = W.win([a, b], margin)
    pn = partner(net)
    ix0, iy0 = win[0], win[1]
    own = {net}
    zone = zone_mask(win)
    pwr = B.net_class.get(net) == 'PWR'
    NOREF = np.zeros(zone.shape, bool)           # critical nets are not fenced by their own reference bands
    wide, frees = [], []
    for l in RL:
        if l == IN3 and not pwr and '--in3-signals' not in args:
            wide.append(np.zeros(zone.shape, bool)); frees.append(np.zeros(zone.shape, bool)); continue
        wf = ~W.blocked(own, l, w / 2, win, partner=pn, pgap=0.203) & ~(NOREF if CRIT.match(net) else REFM[l][win[1]:win[3] + 1, win[0]:win[2] + 1])
        m0 = lfr.M; lfr.M = MN
        try:
            nf = ~W.blocked(own, l, WN / 2, win, partner=pn, pgap=0.203) & zone & ~(NOREF if CRIT.match(net) else REFM[l][win[1]:win[3] + 1, win[0]:win[2] + 1])
        finally:
            lfr.M = m0
        wide.append(wf); frees.append(wf | nf)
    vok = W.via_ok(own, win, dia=VD, hole=VH)
    cell = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    # the net's own existing vias (fan-out, earlier routes) are free layer changes: no new via is placed there
    ownv = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net]
    H_, W_ = vok.shape
    for (vx, vy) in ownv:
        cx, cy = cell((vx, vy))
        if 0 <= cx < W_ and 0 <= cy < H_:
            vok[cy, cx] = True
            for f in frees:
                if f.any():
                    f[cy, cx] = True
    (sx, sy), (tx, ty) = cell(a), cell(b)
    for i, l in enumerate(RL):
        if l in al:
            frees[i][sy, sx] = True
        if l in bl:
            frees[i][ty, tx] = True
    free = np.ascontiguousarray(np.stack(frees))
    if os.environ.get('RRDBG'):
        from scipy import ndimage as _nd
        for _i, _l in enumerate(RL):
            _lab, _ = _nd.label(free[_i], structure=np.ones((3, 3)))
            log(f'   dbg L{_l}: start free {bool(free[_i][sy, sx])} comp {int((_lab == _lab[sy, sx]).sum()) if _lab[sy, sx] else 0}, goal free {bool(free[_i][ty, tx])} comp {int((_lab == _lab[ty, tx]).sum()) if _lab[ty, tx] else 0}, same {bool(_lab[sy, sx] and _lab[sy, sx] == _lab[ty, tx])}; vok start {bool(vok[sy, sx])} goal {bool(vok[ty, tx])}')
    cost = np.ascontiguousarray(np.stack([np.full(frees[0].shape, LC[l], np.float32) for l in RL]))
    slay = np.array([l in al for l in RL]); glay = np.array([l in bl for l in RL])
    ones = np.ones((len(RL), 8), bool)
    path = astar_nb.astar(free, cost, np.ascontiguousarray(vok), sx, sy, slay, ones, tx, ty, glay, ones,
                          0.3 / G, 1.5 / G, 1.5, 12_000_000, np.zeros(vok.shape, np.float32))
    if len(path) == 0:
        return None
    path = [(int(x), int(y), int(i)) for x, y, i in path]
    runs = [[path[0]]]
    for p in path[1:]:
        (runs[-1].append(p) if p[2] == runs[-1][-1][2] else runs.append([p]))
    L = 0.0
    for ri, run in enumerate(runs):
        li = run[0][2]; lay = RL[li]
        segs = []                                   # [dir, width, start cell, end cell]; narrow where wide is blocked
        for p, q in zip(run, run[1:]):
            k = (q[0] - p[0], q[1] - p[1])
            wd = w if (wide[li][p[1], p[0]] and wide[li][q[1], q[0]]) else WN
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
                W.add_track(net, lay, p, q, sg[1]); L += math.hypot(q[0] - p[0], q[1] - p[1])
        if ri + 1 < len(runs):
            vx, vy = (run[-1][0] + ix0) * G, (run[-1][1] + iy0) * G
            if not any(math.hypot(vx - ox, vy - oy) < 0.04 for ox, oy in ownv):
                W.add_via(net, vx, vy, VD, VH)
    return L


REFM = {l: np.zeros((W.NY, W.NX), bool) for l in RL}
_nb = 0
for e in W.sh:
    if e['cls'] == 'trk' and e['net'] and CRIT.match(e['net']):
        hw = e['s'][5] if e['s'][0] == 'k' else 0.05
        for sl in e['layers']:
            for rl in REFL.get(sl, []):
                if rl in REFM:
                    b = lfr.shape_bbox(e['s']); R = BAND + hw + 0.15
                    jx0 = max(int((b[0] - R) / G), 0); jx1 = min(int((b[2] + R) / G) + 1, W.NX - 1)
                    jy0 = max(int((b[1] - R) / G), 0); jy1 = min(int((b[3] + R) / G) + 1, W.NY - 1)
                    X_, Y_ = np.meshgrid(np.arange(jx0, jx1 + 1) * G, np.arange(jy0, jy1 + 1) * G)
                    REFM[rl][jy0:jy1 + 1, jx0:jx1 + 1] |= lfr.shape_dist(e['s'], X_, Y_) < R
                    _nb += 1
log(f'reference keep-out bands: {_nb} critical segments, band {BAND} mm (+0.15 for the new track)')
U5P = [lfr.shape_center(e['s']) for k, e in W.pad.items() if k.startswith('U5.')]
U5B = (min(p[0] for p in U5P), min(p[1] for p in U5P), max(p[0] for p in U5P), max(p[1] for p in U5P))
jobs = []
for net, g in isl.items():
    if net in SKIP or not net:
        continue
    def ipts(x):
        out = [pad_pt(p) for p in x['pads']]
        inf = lambda q: any(f[0] - 0.3 <= q[0] <= f[2] + 0.3 and f[1] - 0.3 <= q[1] <= f[3] + 0.3 for f in W.fields)
        for t in x['tracks']:                     # track ends outside the BGA fields (escape ends) are connection points
            for (xx, yy) in ((t.x1, t.y1), (t.x2, t.y2)):
                q = lfr.to_mm(xx, yy)
                if not inf(q):
                    out.append((q, [t.layer] if t.layer in RL else []))
        for v in x['vias']:                      # vias are connection points even inside the fields (fan-out vias:
            out.append((lfr.to_mm(v.x, v.y), list(RL)))   # decaps under the BGAs reach their rail through them)
        return out
    groups = [ipts(x) for x in g if x['pads']]
    groups = [[q for q in grp if q and q[1]] for grp in groups]
    groups = [grp for grp in groups if grp]
    if len(groups) < 2:
        continue
    pts = [q[0] for grp in groups for q in grp]
    span = max(p[0] for p in pts) - min(p[0] for p in pts) + max(p[1] for p in pts) - min(p[1] for p in pts)
    # phase 1: nets with a U5 ball, outer rings first, tree grown from the U5 island; phase 2: the rest by span
    ring = None
    for gi, x in enumerate([x for x in g if x['pads']]):
        for p_ in x['pads']:
            if p_.des == 'U5':
                c_ = lfr.shape_center(W.pad[f'U5.{p_.num}']['s'])
                r_ = min(c_[0] - U5B[0], U5B[2] - c_[0], c_[1] - U5B[1], U5B[3] - c_[1]) / 0.8
                if ring is None or r_ < ring[0]:
                    ring = (r_, gi)
    if ring is not None:
        groups = [groups[ring[1]]] + [x for k_, x in enumerate(groups) if k_ != ring[1]]
        jobs.append(((0, round(ring[0], 2), span), net, groups))
    else:
        jobs.append(((1, 0, span), net, groups))
GPADS = [x for x in (opt('--gnd-pads') or '').split(',') if x]
if GPADS:                                         # GND pads with no own via: join each to the nearest GND via of the
    gi_ = {}                                      # (pour-connected) main group; island members of a listed pad stay out
    for k_, x in enumerate(isl.get('GND', [])):
        for p_ in x['pads']:
            if f'{p_.des}.{p_.num}' in GPADS:
                gi_[f'{p_.des}.{p_.num}'] = k_
    excl = set(gi_.values())
    main = [(lfr.to_mm(v.x, v.y), list(RL)) for k_, x in enumerate(isl.get('GND', [])) if k_ not in excl for v in x['vias']]
    for pk in GPADS:
        if pk not in gi_:
            continue
        x = isl['GND'][gi_[pk]]
        own = [pad_pt(p_) for p_ in x['pads'] if pad_pt(p_) and pad_pt(p_)[1]]
        own += [(lfr.to_mm(v.x, v.y), list(RL)) for v in x['vias']]
        c_ = own[0][0]
        near_ = sorted(main, key=lambda q: math.hypot(q[0][0] - c_[0], q[0][1] - c_[1]))[:40]
        jobs.append(((-2, 0, 0), 'GND', [own, near_]))
PRIO = [x for x in (opt('--first') or '').split(',') if x]
if PRIO:                                         # failures of an earlier pass go first, in that order
    jobs = [((-1, PRIO.index(n), 0), n, g_) if n in PRIO else (k, n, g_) for k, n, g_ in jobs]
jobs.sort()
ONLY = set((opt('--only') or '').split(',')) - {''}
if ONLY:
    jobs = [j_ for j_ in jobs if j_[1] in ONLY]
if opt('--probe'):
    from scipy import ndimage
    pn_ = opt('--probe')
    for key, net, groups in jobs:
        if net != pn_:
            continue
        (pa, la), (pb, lb) = groups[0][0], groups[1][0]
        best = min(((math.hypot(a_[0][0] - b_[0][0], a_[0][1] - b_[0][1]), a_, b_) for a_ in groups[0] for b_ in groups[1]))
        (pa, la), (pb, lb) = best[1], best[2]
        log(net, 'key', key, 'from', pa, la, 'to', pb, lb, 'width', width(net))
        win = W.win([pa, pb], 6.0); zone = zone_mask(win)
        c = lambda p: (int(round(p[0] / G)) - win[0], int(round(p[1] / G)) - win[1])
        for l in RL[:3]:
            wf = ~W.blocked({net}, l, width(net) / 2, win)
            m0 = lfr.M; lfr.M = MN; nf = ~W.blocked({net}, l, WN / 2, win) & zone; lfr.M = m0
            fr = wf | nf
            lab, _ = ndimage.label(fr, structure=np.ones((3, 3)))
            (sx, sy), (tx, ty) = c(pa), c(pb)
            nb = lambda x, y: {int(lab[yy, xx]) for yy in range(y - 2, y + 3) for xx in range(x - 2, x + 3) if lab[yy, xx]}
            vok = W.via_ok({net}, win, dia=VD, hole=VH)
            cs = nb(sx, sy)
            log(f'  layer {l}: start comps {cs} sizes {[int((lab == k).sum()) for k in cs]}, goal comps {nb(tx, ty)}, '
                f'via spots in start comps {int(sum((vok & (lab == k)).sum() for k in cs))}')
        ownv = [lfr.shape_center(e['s']) for e in W.sh if e['cls'] == 'via' and e['net'] == net]
        log('  own vias', [tuple(round(v, 2) for v in o) for o in ownv])
        for wt, mg in ((width(net), 6.0), (0.1, 6.0), (0.1, 14.0)):
            m = W.mark(); L = route(net, pa, la, pb, lb, wt, mg); log(f'  route w={wt} margin={mg} ->', L); W.rollback(m)
    sys.exit()
log(f'{len(jobs)} split nets to join')
t0 = time.time(); okc = failc = 0; failed = collections.defaultdict(int)
for span, net, groups in jobs:
    w = width(net)
    tree = [0]; rest = list(range(1, len(groups)))
    while rest:                                       # Prim over islands: nearest pad pair between tree and rest
        best = None
        for i in tree:
            for j in rest:
                for (pa, la) in groups[i]:
                    for (pb, lb) in groups[j]:
                        d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
                        if best is None or d < best[0]:
                            best = (d, i, j, pa, la, pb, lb)
        d, i, j, pa, la, pb, lb = best
        L = None
        for ww, margin in [(w, 2.5), (w, 6.0)] + [(x, 6.0) for x in (0.2, 0.127, 0.1) if x < w] +                 [(min(w, 0.127), 14.0)]:
            m = W.mark()
            L = route(net, pa, la, pb, lb, ww, margin)
            if L is not None:
                break
            W.rollback(m)
        if L is None and ALT:                         # other endpoint pairs, spread out (nearest pair may sit in a jam)
            cand = sorted((math.hypot(qa[0] - qb[0], qa[1] - qb[1]), qa, qla, qb, qlb)
                          for i2 in tree for (qa, qla) in groups[i2] for (qb, qlb) in groups[j])
            tried = [(pa, pb)]; n_alt = 0
            for dd, qa, qla, qb, qlb in cand:
                if n_alt >= ALT or dd > d + 25.0:
                    break
                if any(math.hypot(qa[0] - ta[0], qa[1] - ta[1]) < 1.5 and math.hypot(qb[0] - tb[0], qb[1] - tb[1]) < 1.5
                       for ta, tb in tried):
                    continue
                tried.append((qa, qb)); n_alt += 1
                for ww, margin in [(min(w, 0.2), 6.0), (min(w, 0.127), 14.0)]:
                    m = W.mark()
                    L = route(net, qa, qla, qb, qlb, ww, margin)
                    if L is not None:
                        break
                    W.rollback(m)
                if L is not None:
                    break
        if L is None:
            failc += 1; failed[net] += 1
        else:
            okc += 1
        tree.append(j); rest.remove(j)
    if (okc + failc) % 50 == 0:
        log(f'  {okc + failc} connections, {failc} failed ({time.time() - t0:.0f} s)')
log(f'connections routed {okc}, failed {failc} ({time.time() - t0:.0f} s); failed nets: {dict(failed)}')
open(dst + '.failed.txt', 'w').write(','.join(failed))
log(f'edge check: {W.edge_check()[:5]}')
acute, right = lfr.acute_check(W)
log(f'new copper: acute joints {len(acute)}, right {len(right)}')
p, n = lfr.write_candidate(W, dst)
log(f'candidate {p}: {n} records')
