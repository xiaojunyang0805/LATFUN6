"""Cluster layout: main IC + its passives placed horizontally beside the IC pin they connect to.
usage: python cluster.py netmap_b1 groups_b1 [page]  -> layout_<groups>.json (moves with rotation) + report
Coordinates: creation convention (y up). Passives get rotation 0/180 (horizontal), oriented so the pin
on the anchor net faces the parent. Level-2 passives (connected only to a level-1 passive) go one column further out."""
import json, sys, importlib, sqlite3, gzip, base64, collections, math
nm = importlib.import_module(sys.argv[1]); gm = importlib.import_module(sys.argv[2])
page = sys.argv[3] if len(sys.argv) > 3 else 'p1'
P = json.load(open(f'pins_{page}.json'))
con = sqlite3.connect('file:'+__import__('os').environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro', uri=True)
dec = lambda ds: [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8', 'replace').splitlines() if l.strip()]
SYM, BB = {}, {}
for uuid, ds, dt in con.execute("select uuid,dataStr,docType from components"):
    if dt != 2: continue
    try: L = dec(ds)
    except Exception: continue
    cur = None; pins = {}; at = collections.defaultdict(dict); order = []
    for l in L:
        if l[0] == 'PART': cur = l[1]; BB[cur] = l[2]['BBOX']; SYM.setdefault(cur, [])
        elif l[0] == 'PIN' and cur: pins[l[1]] = (cur, l[4], l[5], l[7]); order.append(l[1])
        elif l[0] == 'ATTR' and l[2] in pins: at[l[2]][l[3]] = l[4]
    for pid in order:
        c, x, y, r = pins[pid]; SYM[c].append((at[pid].get('NUMBER'), at[pid].get('NAME'), x, y, r))

def netof(des, num, name):
    if des in nm.P2: return nm.P2[des][int(num) - 1] if num in ('1', '2') else None
    m = nm.BYNAME.get(des, {}); return m.get(name, m.get(num))

import symlib
_L, _C, _A = symlib.page(page)
def _sym(des):
    cid = P[des]['id']; return symlib.lookup(_A[cid].get('Device'), P[des]['part'], _A[cid].get('Symbol'))
def rel_pins(des, rot):
    """pins relative to origin for rotation rot: [(num,name,x,y,outdir,net)]"""
    out = []
    for num, name, x, y, r in _sym(des)['pins']:
        t = math.radians(rot); ax = x * math.cos(t) - y * math.sin(t); ay = x * math.sin(t) + y * math.cos(t)
        out.append((num, name, ax, ay, (r + 180 + rot) % 360, netof(des, num, name)))
    return out

def rel_box(des, rot):
    x0, y0, x1, y1 = _sym(des)['bbox']
    pts = [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]; t = math.radians(rot)
    q = [(x * math.cos(t) - y * math.sin(t), x * math.sin(t) + y * math.cos(t)) for x, y in pts]
    xs = [a for a, _ in q]; ys = [b for _, b in q]
    # include 20-unit stubs on pin sides
    for _, _, px, py, od, net in rel_pins(des, rot):
        if net is None: continue
        dx, dy = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[int(od) % 360]
        xs.append(px + dx * 20); ys.append(py + dy * 20)
    return min(xs), min(ys), max(xs), max(ys)

TWO = set(nm.P2) | {d for d in nm.BYNAME if len(P[d]['pins']) == 2}
COLW, ROWH = 100, 40
layout = {}   # des -> (x, y, rot) relative to cluster origin
clusters = []
for gname, main, members in gm.GROUPS:
    def okrot(d, want=None):
        cur = P[d]['rot'] % 360
        if d in TWO or len(P[d]['pins']) <= 2: return (want if want in (0, 180) and cur == 0 else (0 if cur == 0 and want is None else 180))
        return cur
    GRID = getattr(gm, 'GRID', {}); GP = getattr(gm, 'GRIDP', {})
    if gname in GRID:
        ncol = GRID[gname]; dx, dy = GP.get(gname, (100, 45)); rel = {}
        for i, m in enumerate(members):
            if m is None: continue
            rel[m] = ((i % ncol) * dx, -(i // ncol) * dy, okrot(m))
        bx = []
        for d, (x, y, r) in rel.items():
            b = rel_box(d, r); bx.append((x + b[0], y + b[1], x + b[2], y + b[3]))
        clusters.append((gname, rel, (min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx))))
        continue
    rel = {main: (0, 0, okrot(main))}
    mp = rel_pins(main, rel[main][2]); mb = rel_box(main, rel[main][2])
    placed = {main}; extra_mains = [m for m in members if m not in TWO and m != main]
    # secondary multi-pin parts (FETs, connectors, other ICs) placed by hand offsets in groups file
    for m in extra_mains:
        ox, oy = gm.OFFSETS[m]; rel[m] = (ox, oy, okrot(m)); placed.add(m)
    passives = [m for m in members if m in TWO and m != main]
    # anchor nets: net -> list of (anchor x, y, side) from placed multi-pin parts
    def anchors():
        A = collections.defaultdict(list)
        for d in placed:
            if d in TWO: continue
            ox, oy, r = rel[d]
            for num, name, px, py, od, net in rel_pins(d, r):
                if net and net != 'GND':
                    side = 1 if od == 0 else -1 if od == 180 else (1 if px >= 0 else -1)
                    A[net].append((ox + px, oy + py, side, d))
        return A
    A = anchors()
    level = {}
    todo = list(passives)
    # level 1: shares a non-GND net with a placed multi-pin part
    for p in todo:
        nets = [n for n in nm.P2.get(p, ()) if n and n != 'GND'] if p in nm.P2 else [n for n in nm.BYNAME[p].values() if n != 'GND']
        hit = [(n, a) for n in nets for a in A.get(n, [])]
        if hit: level[p] = (1, hit[0])
    # level 2+: shares a net with a level-1 passive
    for it in range(3):
        for p in todo:
            if p in level: continue
            nets = [n for n in (nm.P2.get(p) or nm.BYNAME[p].values()) if n and n != 'GND']
            for q, (lv, (n0, a0)) in list(level.items()):
                qn = [n for n in (nm.P2.get(q) or nm.BYNAME[q].values()) if n and n != 'GND']
                common = [n for n in nets if n in qn]
                if common:
                    level[p] = (lv + 1, (common[0], (a0[0], a0[1], a0[2], q))); break
    unanch = [p for p in passives if p not in level]
    # slot assignment: per (side, level) column, greedy vertical packing near anchor y
    cols = collections.defaultdict(list)
    for p, (lv, (net, (ax, ay, side, parent))) in level.items():
        cols[(side, lv)].append((ay, p, net))
    ucol = (1, 1) if not any(k == (1, 1) for k in cols) else (1, 4)
    for p in unanch: cols[ucol].append((0, p, None))
    edge = {1: mb[2], -1: mb[0]}
    for (side, lv), items in cols.items():
        items.sort(key=lambda t: -t[0])
        x = edge[side] + side * (40 + (lv - 1) * COLW + 30)
        last = None
        for ay, p, net in items:
            y = ay if last is None else min(ay, last - ROWH)
            last = y
            # orientation: pin on anchor net faces the parent (toward -side)
            best = okrot(p)
            for rot in ((0, 180) if P[p]['rot'] % 360 == 0 else (180,)):
                pp = rel_pins(p, rot)
                np_ = [px for _, _, px, _, _, n in pp if n == net]
                if np_ and (np_[0] * side) < 0: best = rot; break
            rel[p] = (round(x / 10) * 10, round(y / 5) * 5, best)
    # cluster bbox
    bx = []
    for d, (x, y, r) in rel.items():
        b = rel_box(d, r); bx.append((x + b[0], y + b[1], x + b[2], y + b[3]))
    box = (min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx))
    clusters.append((gname, rel, box))

# pack clusters into the frame, rows given in groups file
F = gm.FRAME; GAP = 70
rowh = [max(c[2][3] - c[2][1] for c in clusters if c[0] in row) for row in gm.ROWS]
VGAP = min(220, max(GAP, ((F[3] - F[1] - 160) - sum(rowh)) / (len(gm.ROWS) + 1)))
y_top = F[3] - 90 - VGAP + GAP
placed_boxes = []
for row in gm.ROWS:
    cl = [c for c in clusters if c[0] in row]
    w = sum(c[2][2] - c[2][0] for c in cl); h = max(c[2][3] - c[2][1] for c in cl)
    free = (F[2] - F[0] - 120) - w
    gap = max(GAP, free / (len(cl) + 1)) if len(cl) else GAP
    x = F[0] + 60 + gap
    for gname, rel, box in cl:
        ox = x - box[0]; oy = y_top - box[3]
        for d, (rx, ry, r) in rel.items():
            layout[d] = (round((ox + rx) / 5) * 5, round((oy + ry) / 5) * 5, r)
        placed_boxes.append((gname, (x, y_top - (box[3] - box[1]), x + box[2] - box[0], y_top)))
        x += (box[2] - box[0]) + gap
    y_top -= h + VGAP
print('rows bottom at y', y_top + GAP, 'frame bottom', F[1])
for g, b in placed_boxes: print(f'  {g:10} {[round(v) for v in b]}')
# overlap check of part boxes
bxs = []
for d, (x, y, r) in layout.items():
    b = rel_box(d, r); bxs.append((d, (x + b[0], y + b[1], x + b[2], y + b[3])))
bad = [(a[0], b[0]) for i, a in enumerate(bxs) for b in bxs[i + 1:]
       if a[1][0] < b[1][2] and b[1][0] < a[1][2] and a[1][1] < b[1][3] and b[1][1] < a[1][3]]
out_f = [d for d, b in bxs if not (F[0] + 5 <= b[0] and b[2] <= F[2] - 5 and F[1] + 5 <= b[1] and b[3] <= F[3] - 30)]
print('parts', len(layout), 'overlaps(incl stubs)', len(bad), bad[:12], 'outside', out_f)
rot1 = [{'primitiveId': '$1I' + P[d]['id'][1:], 'rotation': r} for d, (x, y, r) in layout.items() if r != P[d]['rot'] % 360]
xy = [{'primitiveId': '$1I' + P[d]['id'][1:], 'x': x, 'y': y} for d, (x, y, r) in layout.items() if (x, y) != (round(P[d]['x']), round(P[d]['y'])) or r != P[d]['rot'] % 360]
json.dump({'rot': rot1, 'xy': xy, 'plan': {d: v for d, v in layout.items()}}, open(f'layout_{sys.argv[2]}.json', 'w'))
print('rotate', len(rot1), 'move', len(xy))
