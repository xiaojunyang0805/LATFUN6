"""LATFUN6 W5b step 2: SERDES / PCIe / reference-clock pairs, routed coupled (lfr.py).
    python route_serdes.py [--only JOB,JOB] [--out CAND.eprj] [--box x0,y0,x1,y1]
Route + render; writes a candidate copy only with --out. The project itself is never written here
(apply a checked candidate with applyplace.py, EDA closed).

Layer plan (layout worknote W5b, after the 2026-11-21 SFP<->SMA and SMA TX/RX swaps):
  Top    : SMA_HDTX/HDRX (U5 rows 13-15, up to the SMA caps), SFP_HDTX/HDRX (rows 16-18), REFCLK_D1, SFP_TD/RD
  Bottom : PCIE_HDTX (via at U5, via at C322/C323), PCIE_RX (via at U5, lands on the A-side fingers), PCIE_REFCLK
  In2    : REFCLK_D0 (via at U5, via at U27)
  Every lane <= 2 vias; each signal via gets a GND return via beside it."""
import sys, os, json, math, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lfr

ROOT = os.path.abspath(os.path.join(HERE, '../../../..'))
SRC = os.environ.get('EPRJ', os.path.join(ROOT, 'hardware/EDA/Latfun6.eprj'))
RUN = os.path.join(ROOT, 'hardware/latfun6/route_ser')
os.makedirs(RUN, exist_ok=True)
arg = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
ONLY = arg('--only'); OUT = arg('--out')

# net-class geometry (layout worknote §5): (track, gap)
C100 = (0.100, 0.203)            # 100 ohm on L1/L6
C100_IN2 = (0.101, 0.203)        # 100 ohm on L3 (In2)
C85 = (0.143, 0.203)             # 85 ohm PCIe on L1/L6
SE50 = 0.110                     # SMA legs: single-ended, ~52 ohm on L1; inside DP100's 0.09-0.11 (EDA DRC 2026-11-21)
TOP, BOT, IN2 = 1, 2, 16

t0 = time.time()
W = lfr.World(SRC, ripup_prefix='e8r')
print(f'ripped up {W.ripped} earlier lfr records (id e8r*)')
W.add_field('U5'); W.add_field('U30')
# keep-out: U5's SERDES-supply decap columns (Bottom, x 64.9 / 67.0) need the Bottom channel to the balls -> no
# SERDES tracks there on Bottom, and no vias (via_ok checks every layer, so a via is kept out too)
W.keep.append((frozenset({2}), 64.3, 42.8, 68.4, 59.2))
print(f'world: {len(W.sh)} shapes, grid {W.NX}x{W.NY}, CLR {W.CLR:.3f} TT {W.TT:.3f} EDGE {W.EDGE:.3f} ({time.time() - t0:.1f} s)')
c = lambda k: lfr.shape_center(W.pad[k]['s'])
P_ = lambda k: c(k) if isinstance(k, str) else k
R = lfr.Router(W)


def fing(k, inset=0.3):
    """J12 finger: a point just inside the finger's top end (traces enter the finger from the board side)"""
    b = lfr.shape_bbox(W.pad[k]['s'])
    return ((b[0] + b[2]) / 2, b[1] + inset)


def via_pair(P, N, bp, bn, near, w, r=1.6, gnd=True,
             axes=((0, 0.35), (0.35, 0), (0.25, 0.25), (0.25, -0.25))):
    """Signal via pair near `near` (both legal, pitch 0.7 mm), Top breakouts from bp/bn to them, GND return vias
    beside. Candidates nearest first; commits the first whose breakouts route. Returns (vP, vN) or None."""
    G = lfr.G
    win = W.win([near], r + 0.6)
    okP, okN = W.via_ok({P}, win), W.via_ok({N}, win)
    ix0, iy0 = win[0], win[1]
    H, Wd = okP.shape
    idx = lambda p: (int(round(p[0] / G)) - ix0, int(round(p[1] / G)) - iy0)
    inb = lambda i, j: 0 <= i < Wd and 0 <= j < H
    cands = []
    for yy in range(H):
        for xx in range(Wd):
            cx, cy = (xx + ix0) * G, (yy + iy0) * G
            dd = math.hypot(cx - near[0], cy - near[1])
            if dd > r:
                continue
            for ax, ay in axes:
                q1, q2 = (cx - ax, cy - ay), (cx + ax, cy + ay)
                for vp, vn in ((q1, q2), (q2, q1)):
                    (i1, j1), (i2, j2) = idx(vp), idx(vn)
                    if inb(i1, j1) and inb(i2, j2) and okP[j1, i1] and okN[j2, i2]:
                        lb = math.hypot(vp[0] - bp[0], vp[1] - bp[1]) + math.hypot(vn[0] - bn[0], vn[1] - bn[1])
                        cands.append((dd + 0.1 * lb, vp, vn))
    cands.sort()
    for k, (_, vp, vn) in enumerate(cands[:60]):
        done = False
        for order in (((P, bp, vp), (N, bn, vn)), ((N, bn, vn), (P, bp, vp))):
            m = W.mark()
            W.add_via(P, *vp); W.add_via(N, *vn)
            ok = True
            for net, bb, v in order:
                pn = N if net == P else P
                rr = R.route_net(net, bb, v, [TOP], w, margin=1.5, bend=0.2, partner=pn)
                if rr is None or not all(lfr._clear_poly(W, net, pn, lay, pts, w) for lay, pts in rr):
                    ok = False
                    break
            if ok:
                done = True
                break
            W.rollback(m)
        if not done:
            continue
        if gnd:
            ux, uy = vn[0] - vp[0], vn[1] - vp[1]; L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
            for v, sgn, nm in ((vp, -1, P), (vn, 1, N)):
                g = R.via_near('GND', v[0] + sgn * 0.7 * ux, v[1] + sgn * 0.7 * uy, r=0.8)
                if g:
                    W.add_via('GND', *g)
                gnd_log.append((nm, g))
        print(f'    via pair {P}/{N}: {tuple(round(t, 2) for t in vp)} {tuple(round(t, 2) for t in vn)} (candidate {k})')
        return vp, vn
    print(f'    via pair {P}/{N}: FAILED ({len(cands)} candidates)')
    return None


gnd_log = []
# step 1: transitions next to U5 (vias between the ball field and the Top SMA corridor), Top breakouts
TRANS = [   # name, P, N, balls, near, width at the BGA (top)
    ('PCIE_HDTX', 'PCIE_HDTX_P', 'PCIE_HDTX_N', ('U5.W4', 'U5.W5'), (63.5, 45.4), C85[0]),
    ('PCIE_RX', 'PCIE_RX_P', 'PCIE_RX_N', ('U5.Y5', 'U5.Y6'), (63.5, 47.8), C85[0]),
    ('REFCLK_D0', 'REFCLK_D0_P', 'REFCLK_D0_N', ('U5.Y11', 'U5.Y12'), (63.5, 51.6), C100[0]),
]
# step 2: Top pairs (name, P, N, A pads, B pads, layer, class, kwargs); kwargs 'keep' = temporary keep-outs for that job
# SMA stays in its channel (x >= 58.5) until it is above the SFP caps, so SFP can pass on its left (worknote W5b)
SMA_KEEP = (frozenset({1}), 20.0, 31.0, 58.5, 60.0)
# SFP_HDRX leaves U5 at y 55.4-56.2: reserve that exit while SFP_HDTX (routed first, outer) is placed
SFP_RX_EXIT = (frozenset({1}), 56.0, 54.9, 67.7, 56.45)
TOPP = [
    ('SMA_HDTX', 'SMA_HDTX_P', 'SMA_HDTX_N', ('U5.W13', 'U5.W14'), ('C343.2', 'C342.2'), TOP, C100, dict(wleg=(C100[0], SE50), Rb=1.5, bmid=(64.5, 8.5), keep=[SMA_KEEP])),
    ('SMA_HDRX', 'SMA_HDRX_P', 'SMA_HDRX_N', ('U5.Y14', 'U5.Y15'), ('C341.1', 'C340.1'), TOP, C100, dict(wleg=(C100[0], SE50), Rb=1.5, bmid=(40.5, 8.5), keep=[SMA_KEEP])),
    # SFP (TX caps east, RX caps west since 2026-11-21): J13-side pairs first, then HDTX (drops into the east caps),
    # then HDRX (inner at U5, passes north of HDTX's drop into the west caps). RX lane: one P/N twist -> gateware RX invert
    ('SFP_TD', 'SFP_TD_P', 'SFP_TD_N', ('R310.2', 'R311.2'), ('J13.18', 'J13.19'), TOP, C100, dict(Ra=1.0, Rb=0.8, amid=(43.2, 38.3), bmid=(36.5, 44.5))),
    ('SFP_RD', 'SFP_RD_P', 'SFP_RD_N', ('R312.1', 'R313.1'), ('J13.13', 'J13.12'), TOP, C100, dict(Ra=2.0, Rb=2.0)),
    ('SFP_HDTX', 'SFP_HDTX_P', 'SFP_HDTX_N', ('U5.W17', 'U5.W18'), ('R310.1', 'R311.1'), TOP, C100, dict(Rb=0.8, bmid=(43.2, 34.4), Ra=0.6, amid=(67.2, 56.85), keep=[SFP_RX_EXIT])),
    ('SFP_HDRX', 'SFP_HDRX_P', 'SFP_HDRX_N', ('U5.Y16', 'U5.Y17'), ('R313.2', 'R312.2'), TOP, C100, dict(Rb=0.8, bmid=(32.9, 34.4), Ra=0.6, amid=(67.2, 55.8))),
    ('REFCLK_D1', 'REFCLK_D1_P', 'REFCLK_D1_N', ('U5.Y19', 'U5.W20'), ('U28.22', 'U28.21'), TOP, C100, {}),
]
# step 3: Bottom / In2 pairs. far end: ('fing', kP, kN) | ('vias', near, (padP, padN))
LOWP = [
    # RX first: it ends right (A16/A17), HDTX passes the RX vias on their left and ends left (C322/C323 vias)
    ('PCIE_RX', 'PCIE_RX_P', 'PCIE_RX_N', BOT, C85, ('fing', 'J12.A16', 'J12.A17')),
    ('PCIE_HDTX', 'PCIE_HDTX_P', 'PCIE_HDTX_N', BOT, C85, ('vias', (61.15, 99.6), ('C322.1', 'C323.1'))),
    ('REFCLK_D0', 'REFCLK_D0_P', 'REFCLK_D0_N', IN2, C100_IN2, ('vias', (52.0, 71.8), ('U27.22', 'U27.21'))),
    ('PCIE_REFCLK', 'PCIE_REFCLK_P', 'PCIE_REFCLK_N', BOT, C85, ('vias', (44.9, 78.7), ('C320.1', 'C321.1'))),
]
LEGS = [
    ('PCIE_TX', [('PCIE_TX_P', 'C322.2', 'FING:J12.B14', C85[0]), ('PCIE_TX_N', 'C323.2', 'FING:J12.B15', C85[0])], TOP),
    ('CK1_PRI', [('CK1_PRI_P', 'C320.2', 'U27.5', C100[0]), ('CK1_PRI_N', 'C321.2', 'U27.6', C100[0])], TOP),
    ('SMA_TX', [('SMA_TX_P', 'C343.1', 'J18.1', SE50), ('SMA_TX_N', 'C342.1', 'J17.1', SE50)], TOP),
    ('SMA_RX', [('SMA_RX_P', 'C341.2', 'J16.1', SE50), ('SMA_RX_N', 'C340.2', 'J15.1', SE50)], TOP),
]
def _chk(net, k):
    if isinstance(k, str) and '.' in k and not k.startswith('FING:'):
        assert W.pad[k]['net'] == net, f'job table: pad {k} is on {W.pad[k]["net"]}, not {net}'
    if isinstance(k, str) and k.startswith('FING:'):
        assert W.pad[k[5:]]['net'] == net, f'job table: finger {k} is not on {net}'
for name, P, N, balls, near, w in TRANS:
    _chk(P, balls[0]); _chk(N, balls[1])
for name, P, N, A, Bb, *_ in TOPP:
    _chk(P, A[0]); _chk(N, A[1]); _chk(P, Bb[0]); _chk(N, Bb[1])
for name, P, N, layer, cls, far in LOWP:
    if far[0] == 'fing':
        _chk(P, far[1]); _chk(N, far[2])
    else:
        _chk(P, far[2][0]); _chk(N, far[2][1])
for name, legs, layer in LEGS:
    for net, a, b, w in legs:
        _chk(net, a); _chk(net, b)
PAIRS = [(j[0], j[1], j[2]) for j in TOPP] + [(j[0], j[1], j[2]) for j in LOWP]
W.pair_nets = {n for j in PAIRS for n in j[1:]} | {n for j in LEGS for n, *_ in j[1]}
W.PAIR_SEP = float(arg('--sep', 0.3))
want = lambda name: not ONLY or name in ONLY.split(',')
res, vA = {}, {}

print('step 1: transitions at U5')
for name, P, N, balls, near, w in TRANS:
    if want(name):
        vA[name] = via_pair(P, N, c(balls[0]), c(balls[1]), near, w)
        res[name + ':viasA'] = bool(vA[name])

print('step 2: Top pairs')
for name, P, N, A, Bb, layer, (w, g), kw in TOPP:
    if not want(name):
        continue
    t1 = time.time()
    kw = dict(kw); tmp = kw.pop('keep', [])
    W.keep.extend(tmp)
    r = R.route_pair(P, N, (P_(A[0]), P_(A[1])), (P_(Bb[0]), P_(Bb[1])), layer, w, g, sep=1.0, **kw)
    for k in tmp:
        W.keep.remove(k)
    res[name] = bool(r and r.get('ok'))
    print(f'  {name}: {"OK" if res[name] else "FAIL"} ({time.time() - t1:.1f} s)', '' if res[name] else (r or {}).get('fail'), flush=True)

print('step 3: Bottom / In2 pairs')
for name, P, N, layer, (w, g), far in LOWP:
    if not want(name):
        continue
    t1 = time.time()
    if name == 'PCIE_REFCLK':
        ea = (fing('J12.A13'), fing('J12.A14'))
    elif vA.get(name):
        ea = vA[name]
    else:
        print(f'  {name}: skipped (no transition vias)'); res[name] = False; continue
    if far[0] == 'fing':
        eb = (fing(far[1]), fing(far[2]))
    else:
        pk = far[2]
        eb = via_pair(P, N, c(pk[0]), c(pk[1]), far[1], C100[0] if layer == IN2 else w)
        if not eb:
            res[name] = False; continue
    r = R.route_pair(P, N, ea, eb, layer, w, g, sep=1.0)
    res[name] = bool(r and r.get('ok'))
    print(f'  {name}: {"OK" if res[name] else "FAIL"} ({time.time() - t1:.1f} s)', '' if res[name] else (r or {}).get('fail'), flush=True)

print('step 4: short legs')
for name, legs, layer in LEGS:
    if not want(name):
        continue
    for net, a, b, w in legs:
        pa = fing(a[5:]) if a.startswith('FING:') else c(a)
        pb = fing(b[5:]) if b.startswith('FING:') else c(b)
        rr = R.route_net(net, pa, pb, [layer], w, margin=2.5)
        res[name + ':' + net] = bool(rr)
        print(f'  {name}:{net}: {"OK" if rr else "FAIL"}')
print('step 5: P/N skew tuning (serpentines on the shorter leg, target 0.05 mm, DP rule tolerance 0.127 mm)')
for name, P, N in PAIRS:
    if want(name) and res.get(name):
        sk = lfr.tune_pair(W, P, N, tol=0.05)
        print(f'  {name:12} skew after tuning {sk:+.3f} mm')
ac, rt = lfr.acute_check(W)
print(f'acute joints (interior < 90 deg): {len(ac)}', ac[:8], f'| 90-degree joints: {len(rt)}')
for x in rt: print('   90deg', x)
eb = W.edge_check()
print(f'exact edge check vs closed outline (main + J12 tab/notch, {len(W.board_poly)} pts): {len(eb)} violations', eb[:6])
print('GND return vias missing for:', [n for n, g in gnd_log if not g] or 'none')
print('FAILED:', [k for k, v in res.items() if not v] or 'none')

L = lfr.net_lengths(W, W.pair_nets)
for name, P, N in PAIRS:
    if P in L:
        print(f'  {name:12} P {L[P]:7.2f} mm  N {L.get(N, 0):7.2f} mm  skew {L[P] - L.get(N, 0):+.3f} mm')
BOX = tuple(map(float, arg('--box').split(','))) if arg('--box') else None
lfr.render(W, os.path.join(RUN, 'serdes_zoom.png' if BOX else 'serdes_routes.png'), box=BOX, title='SERDES pairs (lfr)')
if OUT:
    p, n = lfr.write_candidate(W, OUT)
    print('candidate', p, n, 'records')
if '--dump' in sys.argv:
    q = tuple(map(float, arg('--dump').split(',')))
    for net, lay, (x1, y1, x2, y2), w in W.new_tracks:
        if min(math.hypot(x1 - q[0], y1 - q[1]), math.hypot(x2 - q[0], y2 - q[1])) < 0.8:
            print('  seg', net, lay, round(x1, 3), round(y1, 3), '->', round(x2, 3), round(y2, 3), w)
