"""Post-process the DDR3 routing (Freerouting result): 90-degree corners -> two 45-degree joints, P/N skew of the CK and
DQS pairs, then length matching per group with octilinear serpentines.
    python tune_ddr.py CAND.eprj OUT.eprj [--png OUT.png] [--tol-dq 2.54] [--tol-ad 5.0]

Targets (worknote §6 DDR3): pairs P/N <= 0.05 mm; DQ/DM to own DQS within --tol-dq; ADDR/CMD to CK within --tol-ad.
TN-02038's +-1.27 / +-2.54 mm are full-speed figures; the board runs LiteDRAM ECP5DDRPHY at 150 MHz DDR (sys 75 MHz),
where 5 mm is ~35 ps of a 3.3 ns bit. Only lengthening is possible: the strobe/clock is lengthened when a member is
longer than it plus the tolerance.
"""
import sys, os, math, re, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
CAND, OUT = args[0], args[1]
TOL_DQ = float(opt('--tol-dq', 2.54)); TOL_AD = float(opt('--tol-ad', 5.0))
SEP = 0.13                                # serpentine edge gap to other DDR tracks
PG = 0.203
DDR = re.compile(r'^DDRAM_')
log = lambda *a: print(*a, flush=True)
MIL = 0.0254

PFX = ('e70', 'e8r')
W = lfr.World(CAND, ripup_prefix=PFX, ripup_nets=lambda n: bool(n) and bool(DDR.match(n)))
for t in W.B.tracks:
    if t.id.startswith(PFX) and DDR.match(t.net):
        (x1, y1), (x2, y2) = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
        if math.hypot(x2 - x1, y2 - y1) > 1e-6:
            W.add_track(t.net, t.layer, (x1, y1), (x2, y2), t.width * MIL)
for v in W.B.vias:
    if v.id.startswith(PFX) and DDR.match(v.net):
        x, y = lfr.to_mm(v.x, v.y)
        W.add_via(v.net, x, y, v.dia * MIL, v.hole * MIL)
NETS = sorted({t[0] for t in W.new_tracks})
DDRSET = set(NETS)
log(f'loaded {len(W.new_tracks)} DDR tracks, {len(W.new_vias)} vias, {len(NETS)} nets (ripped {W.ripped})')
PAIRS = {'CLK': ('DDRAM_CLK_P', 'DDRAM_CLK_N'), 'DQS0': ('DDRAM_DQS_P0', 'DDRAM_DQS_N0'),
         'DQS1': ('DDRAM_DQS_P1', 'DDRAM_DQS_N1')}
PARTNER = {}
for P, N in PAIRS.values():
    PARTNER[P] = N; PARTNER[N] = P


# ---------------------------------------------------------------- 1. 90-degree corners -> 45-degree chamfers
def chamfer_all():
    fixed = failed = 0
    for _ in range(3):
        acute, right = lfr.acute_check(W, DDRSET)
        if not right:
            break
        for net, lay, k in right:
            idx = [i for i, (n, l, s, w) in enumerate(W.new_tracks) if n == net and l == lay and
                   ((round(s[0], 3), round(s[1], 3)) == k or (round(s[2], 3), round(s[3], 3)) == k)]
            if len(idx) != 2:
                continue
            segs = [W.new_tracks[i] for i in idx]
            p = None; far = []
            for n, l, s, w in segs:
                a, b = (s[0], s[1]), (s[2], s[3])
                if (round(a[0], 3), round(a[1], 3)) == k:
                    p = a; far.append((b, w))
                else:
                    p = b; far.append((a, w))
            (q1, w1), (q2, w2) = far
            L1 = math.hypot(q1[0] - p[0], q1[1] - p[1]); L2 = math.hypot(q2[0] - p[0], q2[1] - p[1])
            done = False
            for c in (0.2, 0.12, 0.07, 0.04):
                c = min(c, 0.45 * L1, 0.45 * L2)
                a1 = (p[0] + (q1[0] - p[0]) / L1 * c, p[1] + (q1[1] - p[1]) / L1 * c)
                a2 = (p[0] + (q2[0] - p[0]) / L2 * c, p[1] + (q2[1] - p[1]) / L2 * c)
                w = min(w1, w2)
                if lfr._clear_poly(W, net, PARTNER.get(net), lay, [q1, a1, a2, q2], w, pgap=PG, step=0.01):
                    for i in sorted(idx, reverse=True):
                        W.remove_new_track(i)
                    W.add_track(net, lay, q1, a1, w1); W.add_track(net, lay, a1, a2, w); W.add_track(net, lay, a2, q2, w2)
                    done = True
                    break
            fixed += done; failed += not done
    log(f'chamfered {fixed} right-angle joints, {failed} could not be chamfered')


chamfer_all()
L = lambda: lfr.net_lengths(W, DDRSET)
Ls = L()
log('before tuning: ' + ', '.join(f'{k} skew {Ls[P] - Ls[N]:+.2f}' for k, (P, N) in PAIRS.items()))

# ---------------------------------------------------------------- 2. P/N skew
for k, (P, N) in PAIRS.items():
    sk = lfr.tune_pair(W, P, N, tol=0.05, hmax=0.8)
    log(f'  {k}: P/N skew {sk:+.3f} mm')

# ---------------------------------------------------------------- 3. groups
BYTE0 = [f'DDRAM_DQ{i}' for i in range(8)] + ['DDRAM_DM0']
BYTE1 = [f'DDRAM_DQ{i}' for i in range(8, 16)] + ['DDRAM_DM1']
ADDR = [n for n in NETS if n not in BYTE0 + BYTE1 and n not in PARTNER]
report = {}
GROUPS = [] if '--no-groups' in args else [('DQS0', BYTE0, TOL_DQ), ('DQS1', BYTE1, TOL_DQ), ('CLK', ADDR, TOL_AD)]
for ref, members, tol in GROUPS:
    P, N = PAIRS[ref]
    Ls = L(); Lr = (Ls[P] + Ls[N]) / 2
    longest = max(Ls[n] for n in members)
    if longest > Lr + 0.7 * tol:
        dl = longest - 0.5 * tol - Lr
        log(f'  {ref}: lengthening the pair by {dl:.2f} mm (longest member {longest:.2f}, pair {Lr:.2f})')
        for a, b in ((P, N), (N, P)):
            miss = lfr.tune_len(W, a, dl, partner=b, pgap=PG, sepnets=DDRSET, sep=SEP, wmin=0.08, log=log)
        lfr.tune_pair(W, P, N, tol=0.05, hmax=0.8)
        Ls = L(); Lr = (Ls[P] + Ls[N]) / 2
    for n in sorted(members, key=lambda n: Ls[n]):
        short = (Lr - 0.5 * tol) - Ls[n]
        if short > 0:
            lfr.tune_len(W, n, short + 0.2, sepnets=DDRSET, sep=SEP, wmin=0.08, log=log)
    Ls = L(); dev = {n: Ls[n] - Lr for n in members}
    bad = {n[6:]: round(v, 2) for n, v in dev.items() if abs(v) > tol}
    report[ref] = (Lr, min(dev.values()), max(dev.values()), bad)
    log(f'  group {ref}: ref {Lr:.2f} mm, members {min(dev.values()):+.2f}..{max(dev.values()):+.2f} mm, out of +-{tol}: {bad}')
Ls = L()
log('pair skews after: ' + ', '.join(f'{k} {Ls[P] - Ls[N]:+.3f}' for k, (P, N) in PAIRS.items()))
acute, right = lfr.acute_check(W, DDRSET)
log(f'acute {len(acute)}, right {len(right)}')
if opt('--png'):
    lfr.render(W, opt('--png'), box=(60, 14, 95, 50), title='DDR3 (Freerouting + tuning)')
p, n = lfr.write_candidate(W, OUT)
log(f'candidate {p}: {n} records')
