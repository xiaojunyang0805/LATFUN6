"""LATFUN6 initial placement (board-specific, one-off). Visual frame: mm, x right, y DOWN (= -file y).
Board body 0..W x 0..H; bracket at x=0, PCIe tab below y=H.
Writes plan.json {des: [vx, vy, rot, side]}; nothing is written to the project here."""
import json, math, importlib, collections, sys
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
from eprj_core import Board
B = Board(__import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj'))
MIL = 0.0254
W, H = 167.65, 102.75
G = json.load(open('fpgeo.json'))
# ---------------- geometry helpers ----------------
TH = set()
for cid, c in B.comp.items():
    F = B.P.footprints.get(B.attr[cid].get('Footprint'), [])
    if any(a[0] == 'PAD' and a[4] == 12 for a in F):
        TH.add(B.des[cid])
TH.add('J12')
localpads = {}
for cid in B.comp:
    d = B.des[cid]; F = B.P.footprints.get(B.attr[cid].get('Footprint'), [])
    localpads[d] = {str(a[5]): (a[6] * MIL, a[7] * MIL) for a in F if a[0] == 'PAD'}
def xf(u, v, rot, side):
    """footprint local (mm, file orientation) -> visual offset (mm)."""
    if side == 2: v = -v
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    fx, fy = u * c - v * s, u * s + v * c
    return fx, -fy
def crt_vis(d, rot, side, which='crt'):
    b = [v * MIL for v in G[d][which]]
    pts = [xf(u, v, rot, side) for u in (b[0], b[2]) for v in (b[1], b[3])]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
def pin_vis(d, num, pos):
    x, y, rot, side = pos
    u, v = localpads[d][num]
    dx, dy = xf(u, v, rot, side)
    return x + dx, y + dy
plan = {}
def put(d, x, y, rot=0, side=1):
    plan[d] = [x, y, rot, side]
def put_edge(d, rot, edge, along, over=0.0, side=1, which='crt'):
    """align courtyard side with a board edge ('L','T','R','B'); `over` = overhang beyond the edge (mm)."""
    x0, y0, x1, y1 = crt_vis(d, rot, side, which)
    if edge == 'L': put(d, -over - x0, along - (y0 + y1) / 2, rot, side)
    if edge == 'R': put(d, W + over - x1, along - (y0 + y1) / 2, rot, side)
    if edge == 'T': put(d, along - (x0 + x1) / 2, -over - y0, rot, side)
    if edge == 'B': put(d, along - (x0 + x1) / 2, H + over - y1, rot, side)
# ---------------- anchors ----------------
# PCIe edge: key-notch centre 57.15 mm from the bracket end (secondary source, verify); footprint key centre x = 11.5 mm,
# main board edge at footprint y = +4.95 mm (tab tip at -3.45 mm): origin visual y = H + 4.95.
put('J12', 57.15 - 452.76 * MIL, H + 194.88 * MIL, 0, 1)
# bracket column, top -> bottom
put_edge('J3', 270, 'L', 10.5, over=1.0)            # HDMI
put_edge('J1', 270, 'L', 25.5, over=1.0)            # USB-C #1 (FT2232H)
# SFP cage: board edge at footprint x = -23.05 mm (outline mark in the footprint), opening to the bracket
put('J14', 23.05, 42.5, 0, 1)
put_edge('J19', 90, 'L', 62.0, over=2.0)            # RJ45
put_edge('J20', 270, 'L', 80.0, over=1.0)           # USB-C #2 (ULPI)
put_edge('J11', 0, 'L', 93.5, over=0.5)             # 12 V jack
# SFP host connector inside the cage, rear half (verify against TE 2227302-1 drawing)
put('J13', 23.05 + 8.5, 42.5, 90, 1)
# FPGA and DDR3
put('U5', 76.0, 51.0, 270, 1)
put('U30', 76.0, 24.0, 90, 1)
# SERDES neighbours
put('U27', 52.0, 75.0, 0, 1)      # PCIe REFCLK x2 (near fingers A13/A14 and U5 REFCLK_D0)
put('U28', 55.0, 63.0, 0, 1)      # SFP/SMA REFCLK (near U5 lower-left corner)
put('U26', 47.0, 63.0, 0, 1)      # 1V2_SER LDO, SERDES side
for i, d in enumerate(['J15', 'J16', 'J17', 'J18']):  # SMA, top edge, edge launch
    put_edge(d, 180, 'T', 34.5 + i * 12.0, over=0.0, which='pad')
# config / flash / clock
put('U6', 64.0, 37.0, 90, 1)       # QSPI flash, near U5 config corner
put('X1', 92.0, 52.0, 0, 1)        # 25 MHz
put('Q1', 63.0, 29.0, 0, 1)        # DONE LED driver
put('SW1', 100.0, 6.0, 0, 1)       # PROGRAMN button, top edge area
# FT2232H block behind USB-C #1
put('U7', 33.0, 24.0, 0, 1)
put('J2', 38.0, 13.0, 0, 1)         # JTAG header
# HDMI block behind J3
put('U10', 20.0, 6.5, 90, 1); put('U11', 20.0, 14.5, 90, 1)
put('U12', 27.0, 4.0, 0, 1); put('U13', 27.0, 15.0, 0, 1)
# Ethernet / ULPI behind their jacks
put('U31', 33.0, 62.0, 0, 1)
put('U32', 30.0, 80.0, 0, 1)
# power: 12 V entry near jack + slot 12 V pins, bucks bottom right; core buck near U5
put('U20', 22.0, 95.0, 0, 1); put('U21', 38.0, 95.0, 0, 1)
put('U22', 100.0, 92.0, 0, 1); put('U23', 116.0, 92.0, 0, 1)
put('U2', 130.0, 92.0, 0, 1)                         # 3V3
put('U3', 94.0, 66.0, 0, 1)                          # 1V2 core, near U5
put('U24', 96.0, 22.0, 0, 1)                         # 1V35 near DDR3
put('U25', 143.0, 92.0, 0, 1)                        # 1V8
put('U4', 156.0, 92.0, 0, 1)                         # 2V5
# user I/O (right of U5), top-edge connectors
put('U9', 106.0, 40.0, 0, 1)                         # EEPROM
put('R100', 108.0, 52.0, 0, 1)                       # LED array anchor
put('R110', 112.0, 8.0, 0, 1)                        # buttons anchor (near top edge)
put('SW6', 128.0, 8.0, 0, 1)                         # DIP
put_edge('J4', 0, 'T', 140.0, over=0.5)              # audio, top edge
put('R140', 140.0, 18.0, 0, 1)                       # audio filter anchor
put_edge('J21', 180, 'T', 86.0, over=0.0)            # microSD at the top edge (card in from the top)
put('J9', 131.0, 22.0, 0, 1); put('J10', 142.0, 22.0, 0, 1)   # LA header + loopback
for i, d in enumerate(['J5', 'J6', 'J7', 'J8']):    # PMODs, rear edge, facing out
    put_edge(d, 90, 'R', 14.0 + i * 17.5, over=0.0)
put('TP1', 125.0, 40.0, 0, 1)                        # test-point field anchor
# PCIe TX AC caps in the corridor right above the B14/B15 fingers (x = J12 origin + 15 / 16 mm)
jx = plan['J12'][0]
put('C322', jx + 14.6, 98.6, 90, 1); put('C323', jx + 16.4, 98.6, 90, 1)
# SMA AC caps, one under each SMA centre pin
for i, (dj, dc) in enumerate([('J15', 'C340'), ('J16', 'C341'), ('J17', 'C342'), ('J18', 'C343')]):
    put(dc, plan[dj][0], 8.2, 90, 1)
# ---------------- group membership ----------------
parent = {}
for b in ['b1', 'b3', 'b4', 'b5', 'b6', 'b7', 'b8', 'b9', 'b10', 'b11']:
    m = importlib.import_module('groups_' + b)
    for name, main, mem in m.GROUPS:
        for d in mem:
            if d and d != main: parent[d] = (b, name, main)
for d in ['C450', 'C451', 'C452', 'C453', 'C454', 'C455', 'C456', 'C457', 'C458', 'C459', 'C460',
          'C461', 'C462', 'C463', 'C464', 'C466', 'C467', 'C468', 'C469', 'C470', 'C471', 'C472', 'C473',
          'C474', 'C475', 'C476', 'C477']:
    parent[d] = ('b3', 'vcc', 'U5')
for d in ['FB20', 'C465', 'C478']: parent[d] = ('b3', 'ser', 'U5')
parent['R450'] = ('b1', 'rser', 'U26')
# B3 groups anchored on non-placed schematic parts -> U5
for d, p in list(parent.items()):
    if p[2] in ('C36', 'FB2', 'C54', 'C57', 'R31'): parent[d] = (p[0], p[1], 'U5')
for d in ('C36', 'FB2', 'C54', 'C57', 'R31'): parent.setdefault(d, ('b3', 'x', 'U5'))
parent['R100'] = parent.get('R100', ('b5', 'leds', 'R100'));
BGA_DECAP = {'vcc', 'aux', 'io33', 'io135'}
DDR_DECAP = {'C%d' % i for i in range(350, 360)}
# ---------------- occupancy ----------------
occ = {1: [], 2: []}
GAP = 0.60
def rect_of(d, pos):
    x, y, rot, side = pos
    x0, y0, x1, y1 = crt_vis(d, rot, side)
    return (x + x0, y + y0, x + x1, y + y1)
def add_occ(d, pos):
    r = rect_of(d, pos)
    sides = (1, 2) if d in TH else (pos[3],)
    for s in sides: occ[s].append((r, d))
for d, pos in plan.items(): add_occ(d, pos)
# anchor sanity: overlaps between anchors (same side) and anchors inside corridors
def ov(a, b, g=0.0): return a[0] < b[2] + g and a[2] > b[0] - g and a[1] < b[3] + g and a[3] > b[1] - g
AO = []
for s_ in (1, 2):
    L_ = occ[s_]
    for i in range(len(L_)):
        for j in range(i + 1, len(L_)):
            if ov(L_[i][0], L_[j][0], GAP) and L_[i][1] != L_[j][1]: AO.append((s_, L_[i][1], L_[j][1]))
print('anchor overlaps', sorted(set(AO)))
KEEP = {1: [], 2: []}
def field(d, inset):
    x, y, rot, side = plan[d]; x0, y0, x1, y1 = crt_vis(d, rot, side, 'pad')
    return (x + x0 + inset, y + y0 + inset, x + x1 - inset, y + y1 - inset)
KEEP[1] += [field('U5', -1.5), field('U30', -1.5)]       # top: escape-via zones
KEEP[2] += [field('U5', 1.7), field('U30', 1.7)]          # bottom: inner ball field (vias); outer 2 rings escape on top
# routing corridors kept free of top-side parts (W1 rank 1): PCIe to the fingers, SFP to the cage, SMA to the top edge
CORR = [(57.5, 52.0, 65.8, 101.5), (49.8, 43.0, 67.2, 58.8), (50.5, 4.5, 57.0, 43.0)]
KEEP[1] += CORR
print('anchors in corridors', [d for d,p in plan.items() if p[3]==1 and any(ov(rect_of(d,p),c) for c in CORR) and d not in ('J12',)])
def free(r, side, d):
    if r[0] < 0.5 or r[1] < 0.5 or r[2] > W - 0.5 or r[3] > H - 0.5: return False
    for k in KEEP[side]:
        if r[0] < k[2] and r[2] > k[0] and r[1] < k[3] and r[3] > k[1]: return False
    for (o, od) in occ[side]:
        if r[0] < o[2] + GAP and r[2] > o[0] - GAP and r[1] < o[3] + GAP and r[3] > o[1] - GAP: return False
    return True
def spiral(cx, cy, step=0.25, rmax=30):
    yield cx, cy
    r = step
    while r <= rmax:
        n = max(8, int(2 * math.pi * r / step))
        for k in range(n):
            a = 2 * math.pi * k / n
            yield cx + r * math.cos(a), cy + r * math.sin(a)
        r += step
# ---------------- place members ----------------
def nets_of(d): return {n for _, n in G[d]['pads'] if n and n != 'GND'}
pads_by_net = collections.defaultdict(list)
for d in G:
    for num, n in G[d]['pads']:
        if n: pads_by_net[n].append((d, num))
unplaced = [d for d in G if d not in plan]
def area(d):
    c = G[d]['crt']; return (c[2] - c[0]) * (c[3] - c[1])
unplaced.sort(key=lambda d: -area(d))
fails = []
for d in unplaced:
    b, grp, anc = parent.get(d, (None, None, 'U5'))
    if anc not in plan: anc = 'U5'
    ax, ay, arot, aside = plan[anc]
    side = 1
    if grp in BGA_DECAP or (d.startswith('C') and grp == 'vcc' and anc == 'U5') or d in DDR_DECAP:
        side = 2
    if d in DDR_DECAP: anc = 'U30'; ax, ay, arot, aside = plan['U30']
    # target: anchor pin sharing a net (closest to the anchor's edge), else the anchor centre
    shared = [(anc, num) for n in nets_of(d) for (dd, num) in pads_by_net[n] if dd == anc]
    if shared:
        pts = [pin_vis(anc, num, plan[anc]) for _, num in shared]
        tx = sum(p[0] for p in pts) / len(pts); ty = sum(p[1] for p in pts) / len(pts)
    else:
        tx, ty = ax, ay
    # push outward from the anchor centre past its courtyard (top side only)
    if side == 1:
        x0, y0, x1, y1 = rect_of(anc, plan[anc])
        vx, vy = tx - ax, ty - ay
        L = math.hypot(vx, vy) or 1.0
        hw = max(x1 - x0, y1 - y0) / 2
        if not shared or L < 0.3: vx, vy, L = 0.0, 1.0, 1.0
        tx, ty = ax + vx / L * (hw + 1.5), ay + vy / L * (hw + 1.5)
    rot = 0
    if side == 1 and shared:
        rot = 90 if abs(ty - ay) > abs(tx - ax) else 0
    ok = False
    for rr in (rot, (rot + 90) % 180):
        for x, y in spiral(tx, ty):
            r = rect_of(d, [x, y, rr, side])
            if free(r, side, d):
                put(d, round(x, 2), round(y, 2), rr, side); add_occ(d, plan[d]); ok = True; break
        if ok: break
    if not ok: fails.append(d)
json.dump(plan, open('plan.json', 'w'))
print('placed', len(plan), 'of', len(G), '| failed', fails)
print('bottom-side parts', sum(1 for v in plan.values() if v[3] == 2))
