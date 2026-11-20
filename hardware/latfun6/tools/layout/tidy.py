"""Passive tidy pass. Reads CURRENT positions from the project file (keeps every GUI move), re-places R/C/FB in
aligned rows at the pin they serve, BGA decaps in a slot ring, LEDs as a row. Writes plan_tidy.json."""
import json, math, collections, re
exec(open('placer_geo.py').read())          # B (current file), G (fpgeo.json must be regenerated first), xf, crt_vis, localpads, TH
import importlib
# ---------- current positions ----------
cur = {}
for cid, c in B.comp.items():
    cur[B.des[cid]] = [c[4] * MIL, -c[5] * MIL, c[6] or 0, c[3]]
holes = [(round(B._place(('c', 0, 0, 0), 0, 0, 0, False)[1], 1),) for _ in []]
HOLES = [(ec_c[0] * MIL, -ec_c[1] * MIL) for ec_c in [__import__('eprj_core').shape_center(p.shape) for p in B.pads if p.des.startswith('PAD_')]]
import os
DELTA = float(os.environ.get('DELTA', '0')); X0 = float(os.environ.get('X0', '120'))
if DELTA:
    W = W - DELTA
    for d, p in cur.items():
        if p[0] > X0 and not re.match(r'^(R|C|FB)\d', d): p[0] -= DELTA
    HOLES = [(hx - DELTA if hx > X0 else hx, hy) for hx, hy in HOLES]
if os.path.exists(os.environ.get('OVR', '__none__')):
    _o = json.load(open(os.environ['OVR']))
    W = _o['W']
    for d, p in _o['O'].items(): cur[d] = list(p)
    HOLES = [tuple(h) for h in _o['HOLES']]
PASSIVE = lambda d: re.match(r'^(R|C|FB)\d', d) is not None
LEDS = ['D%d' % i for i in range(10, 18)]
moveable = {d for d in cur if PASSIVE(d)} | set(LEDS)
fixed = {d: p for d, p in cur.items() if d not in moveable}
POWER = {'GND', '1V2', '3V3', '1V35', '1V8', '1V2_SER', '2V5', 'VCCAUX', 'VCCAUXA', '5V_SYS', '12V_OR', '5V_12', '5V_HDMI',
         'USB2_VBUS', 'VBUS_F', 'SLOT_3V3', '12V_SLOT', 'ETH_1V0', '1V8_FT', '3V3_FTA', 'CK1_VDDO', 'CK2_VDDO',
         'CK1_VDDREF', 'CK2_VDDREF', 'CK1_VDDVCO', 'CK2_VDDVCO', '3V3_OSC', '2V5_PRE', 'JACK_F'}
nets = {d: {n for _, n in G[d]['pads'] if n} for d in G}
pins_on = collections.defaultdict(list)             # net -> [(des, num)]
for d in G:
    for num, n in G[d]['pads']:
        if n: pins_on[n].append((d, num))
parent = {}
for b in ['b1', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9', 'b10', 'b11']:
    m = importlib.import_module('groups_' + b)
    for name, main, mem in m.GROUPS:
        for d in mem:
            if d and d != main: parent[d] = (name, main)
for d in [f'C{i}' for i in range(450, 479)] + ['FB20']: parent[d] = ('vcc', 'U5')
parent['R450'] = ('rser', 'U26')
B3DECAP = {'vcc', 'aux', 'io33', 'io135'}
def rect(d, p):
    x, y, r, s = p; x0, y0, x1, y1 = crt_vis(d, r, s); return (x + x0, y + y0, x + x1, y + y1)
def pinpos(d, num, p=None):
    p = p or fixed.get(d) or cur[d]; x, y, r, s = p; u, v = localpads[d][num]; dx, dy = xf(u, v, r, s); return (x + dx, y + dy)
# ---------- occupancy / keep-outs ----------
GAP = 0.6
occ = {1: [], 2: []}
def add(d, p):
    for s in ((1, 2) if d in TH else (p[3],)): occ[s].append((rect(d, p), d))
for d, p in fixed.items(): add(d, p)
KEEP = {1: [], 2: []}
def field(d, inset):
    x, y, r, s = fixed[d]; x0, y0, x1, y1 = crt_vis(d, r, s, 'pad'); return (x + x0 + inset, y + y0 + inset, x + x1 - inset, y + y1 - inset)
KEEP[1] += [field('U5', -1.5), field('U30', -1.5)]
KEEP[1] += [(57.5, 52.0, 65.8, 101.5), (49.8, 43.0, 67.2, 58.8), (50.5, 4.5, 57.0, 43.0)]       # SERDES corridors
for hx, hy in HOLES:
    for s in (1, 2): KEEP[s].append((hx - 4.3, hy - 4.3, hx + 4.3, hy + 4.3))
for s in (1, 2): KEEP[s] += [(0, 0, 12.7, 10.1), (0, 85.35, 12.7, H)]
KEEP[2].append((0, 0, 2.6, H))
def free(r, s, ignore_keep=False):
    if r[0] < 0.5 or r[1] < 0.5 or r[2] > W - 0.5 or r[3] > H - 0.5: return False
    if not ignore_keep:
        for k in KEEP[s]:
            if r[0] < k[2] and r[2] > k[0] and r[1] < k[3] and r[3] > k[1]: return False
    for o, _ in occ[s]:
        if r[0] < o[2] + GAP and r[2] > o[0] - GAP and r[1] < o[3] + GAP and r[3] > o[1] - GAP: return False
    return True
plan = {d: list(p) for d, p in fixed.items()}
def commit(d, p): plan[d] = p; add(d, p)
# ---------- 1. BGA decap slot rings (bottom) ----------
def bga_ring(anchor, members):
    fx0, fy0, fx1, fy1 = field(anchor, 0)
    slots = []
    for ring, inset in ((0, 0.85), (1, -1.25), (2, -3.35)):      # under the outer two ball rings, then outside the field
        for edge in 'TBLR':
            if edge in 'TB':
                y = (fy0 + inset) if edge == 'T' else (fy1 - inset)
                L = fx1 - fx0 + (0 if ring == 0 else 2 * abs(inset)); n = int(L // 2.4)
                x_start = (fx0 + fx1) / 2 - (n - 1) * 2.4 / 2
                slots += [(x_start + k * 2.4, y, 0, ring) for k in range(n)]
            else:
                x = (fx0 + inset) if edge == 'L' else (fx1 - inset)
                L = fy1 - fy0 + (0 if ring == 0 else 2 * abs(inset)); n = int(L // 2.4)
                y_start = (fy0 + fy1) / 2 - (n - 1) * 2.4 / 2
                slots += [(x, y_start + k * 2.4, 90, ring) for k in range(n)]
    used = set()
    # big caps last; each cap goes to the free slot nearest a ball of its rail, inner ring preferred
    for d in sorted(members, key=lambda d: (('10u' in str(d)), d)):
        rails = [n for n in nets[d] if n != 'GND']
        balls = [pinpos(anchor, num) for (dd, num) in pins_on[rails[0]] if dd == anchor] if rails else []
        if not balls: balls = [((fx0 + fx1) / 2, (fy0 + fy1) / 2)]
        best = None
        for i, (sx, sy, sr, ring) in enumerate(slots):
            if i in used: continue
            p = [round(sx, 2), round(sy, 2), sr, 2]
            if not free(rect(d, p), 2, ignore_keep=True): continue
            cost = min(math.hypot(sx - bx, sy - by) for bx, by in balls) + ring * 3.0
            if best is None or cost < best[0]: best = (cost, i, p)
        if best: used.add(best[1]); commit(d, best[2])
    return [d for d in members if d not in plan]
u5_dec = [d for d, (g, a) in parent.items() if a in ('U5', 'C36', 'FB2', 'C54', 'C57', 'R31') and g in B3DECAP | {'vcc'} and d.startswith('C') and d not in ('C465', 'C478')]
u30_dec = ['C%d' % i for i in range(350, 360)]
left = bga_ring('U5', u5_dec) + bga_ring('U30', u30_dec)
# ---------- 2. LED array: 8 LED/R pairs in one row (anchor = current D10 area) ----------
lx, ly = cur['D10'][0], cur['D10'][1]
for i, (dl, dr) in enumerate(zip(LEDS, ['R%d' % (100 + i) for i in range(8)])):
    commit(dl, [round(lx + i * 2.6, 2), round(ly, 2), 90, 1])
    commit(dr, [round(lx + i * 2.6, 2), round(ly + 3.0, 2), 90, 1])
# ---------- 3. rows at the serving pin ----------
def serving(d):
    """(anchor, pin) this passive serves: a non-passive sharing a SIGNAL net first, else the group anchor's power pin."""
    sig = [n for n in nets[d] if n not in POWER]
    cands = []
    for n in sig:
        for dd, num in pins_on[n]:
            if dd != d and dd in fixed and not PASSIVE(dd): cands.append((dd, num, n))
    g = parent.get(d, (None, 'U5'))[1]
    if cands:
        cands.sort(key=lambda c: (c[0] != g, len(pins_on[c[2]])))
        return cands[0][0], cands[0][1]
    # signal net reaches only passives: follow one hop (e.g. RC filters) to a non-passive
    for n in sig:
        for dd, _ in pins_on[n]:
            if dd != d and PASSIVE(dd):
                for n2 in nets[dd] - {n}:
                    for d3, num3 in pins_on[n2]:
                        if d3 in fixed and not PASSIVE(d3) and n2 not in POWER: return d3, num3
    pw = [n for n in nets[d] if n != 'GND']
    if g in fixed and pw:
        pins = [num for dd, num in pins_on[pw[0]] if dd == g]
        if pins: return g, pins
    return (g if g in fixed else 'U5'), None
todo = [d for d in moveable if d not in plan]
groups = collections.defaultdict(list)
for d in todo:
    a, pin = serving(d)
    groups[a].append((d, pin))
def side_of(a, px, py):
    x0, y0, x1, y1 = rect(a, fixed[a])
    dists = {'L': px - x0, 'R': x1 - px, 'T': py - y0, 'B': y1 - py}
    return min(dists, key=dists.get)
fails = []
for a, mem in groups.items():
    ax0, ay0, ax1, ay1 = rect(a, fixed[a])
    # distribute decaps of one power net over that net's pins
    assigned = []
    bynet = collections.defaultdict(list)
    for d, pin in mem:
        if isinstance(pin, list): bynet[tuple(pin)].append(d)
        else: assigned.append((d, pin))
    for pins, ds in bynet.items():
        for i, d in enumerate(sorted(ds)): assigned.append((d, pins[i % len(pins)]))
    rows = collections.defaultdict(list)
    for d, pin in assigned:
        if pin is None:
            px, py = (ax0 + ax1) / 2, ay1
        else:
            px, py = pinpos(a, pin)
        rows[side_of(a, px, py)].append((d, px, py))
    for sd, items in rows.items():
        horiz = sd in 'TB'                 # row runs along x
        items.sort(key=lambda t: t[1] if horiz else t[2])
        rot = 90 if horiz else 0           # pads point at the IC
        # greedy 1-D packing along the row, centred on the pins
        sizes = []
        for d, px, py in items:
            x0, y0, x1, y1 = crt_vis(d, rot, 1)
            sizes.append(((x1 - x0) if horiz else (y1 - y0), (y1 - y0) if horiz else (x1 - x0)))
        pos = []
        for i, (d, px, py) in enumerate(items):
            t = px if horiz else py
            if pos: t = max(t, pos[-1] + (sizes[i - 1][0] + sizes[i][0]) / 2 + GAP)
            pos.append(t)
        tgt = [(px if horiz else py) for _, px, py in items]
        shift = (sum(tgt) - sum(pos)) / len(pos)
        pos = [p + shift for p in pos]
        depth = max(s[1] for s in sizes)
        base = {'L': ax0, 'R': ax1, 'T': ay0, 'B': ay1}[sd]
        sign = -1 if sd in 'LT' else 1
        placed = False
        for k in range(0, 40):              # push the whole row outward until it is free
            off = 0.6 + depth / 2 + 0.25 * k
            cand = []
            for (d, px, py), p in zip(items, pos):
                c = base + sign * off
                xy = (round(p / 0.05) * 0.05, round(c / 0.05) * 0.05) if horiz else (round(c / 0.05) * 0.05, round(p / 0.05) * 0.05)
                cand.append((d, [xy[0], xy[1], rot, 1]))
            rects = [rect(d, p) for d, p in cand]
            ok = all(free(r, 1) for r in rects)
            # members must not overlap each other either
            if ok:
                for i in range(len(rects)):
                    for j in range(i + 1, len(rects)):
                        r1, r2 = rects[i], rects[j]
                        if r1[0] < r2[2] + GAP and r1[2] > r2[0] - GAP and r1[1] < r2[3] + GAP and r1[3] > r2[1] - GAP: ok = False
            if ok:
                for d, p in cand: commit(d, p)
                placed = True; break
        if not placed:                       # fall back: one by one, spiral from its row slot
            for (d, px, py), p in zip(items, pos):
                c = base + sign * (0.6 + depth / 2)
                tx, ty = (p, c) if horiz else (c, p)
                done = False
                for rr in range(0, 120):
                    rad = rr * 0.25
                    for kk in range(max(1, int(2 * math.pi * rad / 0.25))):
                        an = 2 * math.pi * kk / max(1, int(2 * math.pi * rad / 0.25))
                        q = [round(tx + rad * math.cos(an), 2), round(ty + rad * math.sin(an), 2), rot, 1]
                        if free(rect(d, q), 1): commit(d, q); done = True; break
                    if done: break
                if not done: fails.append(d)
# leftovers from the BGA rings: place next to the field on the bottom by spiral
for d in left:
    fx0, fy0, fx1, fy1 = field('U5' if d not in u30_dec else 'U30', 0)
    done = False
    for rr in range(0, 160):
        rad = rr * 0.25
        n = max(1, int(2 * math.pi * rad / 0.25))
        for kk in range(n):
            an = 2 * math.pi * kk / n
            q = [round((fx0 + fx1) / 2 + (abs(fx1 - fx0) / 2 + 2 + rad) * math.cos(an), 2),
                 round((fy0 + fy1) / 2 + (abs(fy1 - fy0) / 2 + 2 + rad) * math.sin(an), 2), 0, 2]
            if free(rect(d, q), 2): commit(d, q); done = True; break
        if done: break
    if not done: fails.append(d)
missing = [d for d in cur if d not in plan]
json.dump(plan, open(os.environ.get('OUTPLAN','plan_tidy.json'), 'w')); json.dump({'W':W,'HOLES':HOLES}, open(os.environ.get('OUTPLAN','plan_tidy.json')+'.meta','w'))
print('moveable', len(moveable), '| placed', len([d for d in moveable if d in plan]), '| fails', fails, '| missing', missing)
print('bottom', sum(1 for p in plan.values() if p[3] == 2))
