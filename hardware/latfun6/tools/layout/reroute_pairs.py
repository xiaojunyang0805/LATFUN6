"""Re-route ETH_MDI1 and USB2 as coupled pairs (lfr.Router.route_pair), replacing their uncoupled Freerouting paths.
Keeps copper of those nets within --keep-r of the listed keep pads (USB-C A/B tie at J20); everything else of the
nets is ripped. Tries Top first, then L16 with a via pair beside the SMD end (+ GND return vias).
    python reroute_pairs.py IN.eprj OUT.eprj"""
import sys, os, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lfr

SRC, OUT = sys.argv[1], sys.argv[2]
MIL = 0.0254
TOP, IN2 = 1, 16
# name, P, N, A ends (P, N), B ends (P, N), width, gap, layers to try, keep-zone (centre, r) or None
JOBS = [
    ('USB2', 'USB2_DP', 'USB2_DN', ((5.70, 79.75), (7.71, 79.59)), ('U32.18', 'U32.19'), 0.127, 0.203, [TOP],
     ((6.6, 80.0), 1.3)),
    ('ETH_MDI1', 'ETH_MDI1_P', 'ETH_MDI1_N', ('U31.4', 'U31.5'), ('J19.P4', 'J19.P7'), 0.100, 0.203, [17, TOP, IN2, 2, 18, 19, 20, 15], None),
]
NETS = {n for j in JOBS for n in j[1:3]}
KEEP = {j[1]: j[8] for j in JOBS} | {j[2]: j[8] for j in JOBS}


def kept(net, pts):
    z = KEEP.get(net)
    return z is not None and all(math.hypot(p[0] - z[0][0], p[1] - z[0][1]) <= z[1] for p in pts)


W = lfr.World(SRC, ripup_prefix=('',), ripup_nets=lambda n: n in NETS)
for t in W.B.tracks:                       # put back the kept stubs as editable copper
    if t.net in NETS:
        a, b = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
        if kept(t.net, (a, b)) and math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-6:
            W.add_track(t.net, t.layer, a, b, t.width * MIL)
print(f'ripped {W.ripped} records; kept {len(W.new_tracks)} stub segments')
W.pair_nets = set(NETS)
R = lfr.Router(W)
c = lambda k: lfr.shape_center(W.pad[k]['s']) if isinstance(k, str) else k


def via_pair(P, N, bp, bn, near, w, r=1.8):
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
            for ax, ay in ((0, 0.35), (0.35, 0), (0.25, 0.25), (0.25, -0.25)):
                for vp, vn in (((cx - ax, cy - ay), (cx + ax, cy + ay)), ((cx + ax, cy + ay), (cx - ax, cy - ay))):
                    (i1, j1), (i2, j2) = idx(vp), idx(vn)
                    if inb(i1, j1) and inb(i2, j2) and okP[j1, i1] and okN[j2, i2]:
                        lb = math.hypot(vp[0] - bp[0], vp[1] - bp[1]) + math.hypot(vn[0] - bn[0], vn[1] - bn[1])
                        cands.append((lb + 0.3 * dd, vp, vn))
    cands.sort()
    for _, vp, vn in cands[:60]:
        m = W.mark()
        W.add_via(P, *vp); W.add_via(N, *vn)
        ok = True
        for net, bb, v in ((P, bp, vp), (N, bn, vn)):
            pn = N if net == P else P
            rr = R.route_net(net, bb, v, [TOP], w, margin=1.5, bend=0.2, partner=pn)
            if rr is None or not all(lfr._clear_poly(W, net, pn, lay, pts, w) for lay, pts in rr):
                ok = False
                break
        if ok:
            ux, uy = vn[0] - vp[0], vn[1] - vp[1]; L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
            for v, sgn in ((vp, -1), (vn, 1)):
                g = R.via_near('GND', v[0] + sgn * 0.7 * ux, v[1] + sgn * 0.7 * uy, r=0.8)
                if g:
                    W.add_via('GND', *g)
            return vp, vn
        W.rollback(m)
    return None


res = {}
for name, P, N, A, B, w, g, layers, _ in JOBS:
    ea, eb = (c(A[0]), c(A[1])), (c(B[0]), c(B[1]))
    best = None
    for lay in layers:
        m = W.mark()
        a2 = ea
        if lay != TOP:                     # SMD end A on Top: via pair next to it
            mid = ((ea[0][0] + ea[1][0]) / 2, (ea[0][1] + ea[1][1]) / 2 + 0.9)
            vv = via_pair(P, N, ea[0], ea[1], mid, w)
            if not vv:
                print(f'  {name} L{lay}: no via pair'); W.rollback(m); continue
            a2 = vv
        r = R.route_pair(P, N, a2, eb, lay, w, g, sep=0.3)
        ok = bool(r and r.get('ok'))
        L = lfr.net_lengths(W, {P, N})
        print(f'  {name} L{lay}: {"OK" if ok else "FAIL"}  P {L.get(P, 0):.2f} N {L.get(N, 0):.2f}', '' if ok else (r or {}).get('fail'))
        if ok:
            best = lay
            break
        W.rollback(m)
    res[name] = best
    if best is not None:
        sk = lfr.tune_pair(W, P, N, tol=0.05, log=lambda *a: None)
        for cc, top, gb, mg in ((0.07, 0.2, 0.2, 0.1), (0.05, 0.15, 0.15, 0.05)):
            for hm in (0.6, 0.45, 0.3, 0.2):
                if abs(sk) > 0.05:
                    sk = lfr.tune_pair(W, P, N, tol=0.05, c=cc, top=top, gapb=gb, hmax=hm, margin=mg, log=lambda *a: None)
        print(f'  {name}: skew after tuning {sk:+.3f}')
ac, rt = lfr.acute_check(W, NETS)
print('acute', ac, 'right', rt)
print('RESULT', res)
if all(v is not None for v in res.values()):
    p, n = lfr.write_candidate(W, OUT)
    print('candidate', p, n)
