"""SERDES bead split (2026-11-21): place FB21-23 + C479/C480 near C478 (tidy rules) and permute C466-C477 over their
existing under-BGA slots so each cap is nearest a ball of its own rail. Every other part keeps its file position."""
import json, math, itertools, os, re
exec(open('placer_geo.py').read())
cur = {B.des[c]: [B.comp[c][4] * MIL, -B.comp[c][5] * MIL, B.comp[c][6] or 0, B.comp[c][3]] for c in B.comp}
plan = {d: list(p) for d, p in cur.items()}
HOLES = json.load(open('holes.json'))
PASSIVE = lambda d: re.match(r'^(R|C|FB)\d', d) is not None
NEW = ['FB21', 'FB22', 'FB23', 'C479', 'C480']
CAPS = ['C%d' % i for i in range(466, 478)]
nets = {d: {n for _, n in G[d]['pads'] if n} for d in G}
def rect(d, p):
    x, y, r, s = p; x0, y0, x1, y1 = crt_vis(d, r, s); return (x + x0, y + y0, x + x1, y + y1)
# ---- 1. permute the 12 caps over their own slots (same footprint, so pure relabel of positions)
x, y, r, s = cur['U5']
balls = {}
for num, n in G['U5']['pads']:
    if n in ('VCCA_1V2', 'VCCHTX_1V2', 'VCCHRX_1V2'):
        u, v = localpads['U5'][num]; dx, dy = xf(u, v, r, s); balls.setdefault(n, []).append((x + dx, y + dy))
slots = [tuple(cur[c]) for c in CAPS]
rail = {c: [n for n in nets[c] if n != 'GND'][0] for c in CAPS}
def cost(c, sl): return min(math.hypot(sl[0] - bx, sl[1] - by) for bx, by in balls[rail[c]])
try:
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    M_ = np.array([[cost(c, sl) for sl in slots] for c in CAPS]); ri, ci = linear_sum_assignment(M_)
    asg = {CAPS[i]: slots[j] for i, j in zip(ri, ci)}
except ImportError:
    asg = {}; free_s = list(slots)
    for c, sl in sorted(((c, sl) for c in CAPS for sl in slots), key=lambda t: cost(*t)):
        if c not in asg and sl in free_s: asg[c] = sl; free_s.remove(sl)
before = sum(cost(c, tuple(cur[c])) for c in CAPS); after = sum(cost(c, asg[c]) for c in CAPS)
for c in CAPS: plan[c] = list(asg[c])
print('cap->ball distance sum %.1f -> %.1f mm' % (before, after), {c: round(cost(c, asg[c]), 1) for c in CAPS})
# ---- 2. new parts near C478 (top), tidy gap rules
GAP_PP, GAP_PO = 0.2, 0.4
occ = [(rect(d, p), d) for d, p in plan.items() if d not in NEW and (p[3] == 1 or d in TH)]
def field(d, inset):
    x, y, r, s = plan[d]; x0, y0, x1, y1 = crt_vis(d, r, s, 'pad'); return (x + x0 + inset, y + y0 + inset, x + x1 - inset, y + y1 - inset)
KEEP = [field('U5', -1.5), field('U30', -1.5), (57.5, 52.0, 65.8, 101.5), (49.8, 43.0, 67.2, 58.8), (50.5, 4.5, 57.0, 43.0),
        (0, 0, 12.7, 10.1), (0, 85.35, 12.7, H)] + [(hx - 4.3, hy - 4.3, hx + 4.3, hy + 4.3) for hx, hy in HOLES]
LABS = []                                          # existing (visible, top) labels of untouched parts
import eprj_core as _ec
for _l in _ec.Project(os.environ.get('EPRJ', 'E:/2026/LATFUN6/hardware/EDA/Latfun6.eprj')).text.split(chr(10)):
    if _l.startswith('["ATTR"'):
        _a = json.loads(_l)
        if _a[7] == 'Designator' and _a[10] and _a[4] == 3 and _a[3] in B.des and B.des[_a[3]] not in NEW + CAPS:
            _d = B.des[_a[3]]; _w = len(_d) * 0.62 * 0.8 + 0.1; _cx, _cy = _a[5] * MIL, -_a[6] * MIL
            _ww, _hh = (_w, 0.9) if (_a[17] or 0) in (0, 180) else (0.9, _w)
            LABS.append((_cx - _ww / 2, _cy - _hh / 2, _cx + _ww / 2, _cy + _hh / 2))
def inter(a, b, g): return a[0] < b[2] + g and a[2] > b[0] - g and a[1] < b[3] + g and a[3] > b[1] - g
def free(R):
    if R[0] < 0.5 or R[1] < 0.5 or R[2] > W - 0.5 or R[3] > H - 0.5: return False
    if any(inter(R, k, 0) for k in KEEP): return False
    for o, od in occ:
        if inter(R, o, GAP_PP if PASSIVE(od) else GAP_PO): return False
    if any(inter(R, l, 0.15) for l in LABS): return False
    return True
ax, ay = plan['C478'][:2]
bx_, by_ = sum(b[0] for v in balls.values() for b in v) / 12, sum(b[1] for v in balls.values() for b in v) / 12
ROW = ['FB21', 'C478x', 'FB22', 'C479', 'FB23', 'C480']          # bead then its 10 uF; VCCA's 10 uF is C478 itself
ROW = ['FB21', 'FB22', 'C479', 'FB23', 'C480']
def tl(d): return len(d) * 0.62 * 0.8 + 0.1
best = None
for rot in (90, 0):
    sz = {d: crt_vis(d, rot, 1) for d in ROW}
    if rot == 90: pitch = max(b[2] - b[0] for b in sz.values()) + GAP_PP
    else:         pitch = max(b[3] - b[1] for b in sz.values()) + GAP_PP
    lane = max(tl(d) for d in ROW) + 0.2 + 0.5
    for i in range(-100, 101):
        for j in range(-100, 101):
            x0, y0 = bx_ + i * 0.25, by_ + j * 0.25
            ps = {d: ([round(x0 + k * pitch, 2), round(y0, 2), rot, 1] if rot == 90 else [round(x0, 2), round(y0 + k * pitch, 2), rot, 1]) for k, d in enumerate(ROW)}
            rs = {d: rect(d, p) for d, p in ps.items()}
            if not all(free(r) for r in rs.values()): continue
            for side in ('T', 'B') if rot == 90 else ('L', 'R'):
                if rot == 90: lanes = {d: ((r[0], r[1] - lane, r[2], r[1]) if side == 'T' else (r[0], r[3], r[2], r[3] + lane)) for d, r in rs.items()}
                else:         lanes = {d: ((r[0] - lane, r[1], r[0], r[3]) if side == 'L' else (r[2], r[1], r[2] + lane, r[3])) for d, r in rs.items()}
                if not all(free(l) for l in lanes.values()): continue
                cx_ = sum((r[0] + r[2]) / 2 for r in rs.values()) / len(rs); cy_ = sum((r[1] + r[3]) / 2 for r in rs.values()) / len(rs)
                k_ = math.hypot(cx_ - bx_, cy_ - by_)
                if best is None or k_ < best[0]: best = (k_, ps, lanes, side, rot)
k_, ps, lanes, side, rot = best
lab = {}
for d, p in ps.items():
    plan[d] = p; occ.append((rect(d, p), d))
    l = lanes[d]; L_ = tl(d) + 0.2
    if side == 'T': c = ((l[0] + l[2]) / 2, l[3] - L_ / 2)
    elif side == 'B': c = ((l[0] + l[2]) / 2, l[1] + L_ / 2)
    elif side == 'L': c = (l[2] - L_ / 2, (l[1] + l[3]) / 2)
    else: c = (l[0] + L_ / 2, (l[1] + l[3]) / 2)
    lab[d] = [c[0], c[1], 90 if rot == 90 else 0]
json.dump(lab, open('labels_rows.json', 'w'))
print('row', ROW, 'at', ps[ROW[0]][:2], 'rot', rot, 'label lane', side, 'row centre %.1f mm from the SERDES balls (C478: %.1f)' % (k_, math.hypot(ax - bx_, ay - by_)))
json.dump(plan, open('plan.json', 'w'))
