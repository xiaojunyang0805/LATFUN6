"""Designator labels: 0.8 mm text, 0.15 mm stroke, centred (align 5). Row parts use the lane tidy.py reserved;
every other part gets the first free spot around its courtyard (no pad, no other part body, no other label, inside
the board). Labels with no legal spot are hidden. Rewrites the Designator ATTR rows of a candidate copy."""
import json, sys, math, os
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
exec(open('placer_geo.py').read())                      # xf, crt_vis, G (only footprint-local data is used), MIL, W, H
SRC = sys.argv[1]; OUT = sys.argv[2]
plan = json.load(open('plan.json')); rowlab = json.load(open('labels_rows.json'))
ONLY = set(os.environ['ONLY'].split(',')) if os.environ.get('ONLY') else None   # relabel only these; keep all other labels
if ONLY: rowlab = {k: v for k, v in rowlab.items() if k in ONLY}
TH_, SW_ = 0.8, 0.10
def tl(d): return len(d) * 0.62 * TH_ + 0.1
Bc = ec.Board(SRC)
def vbox(shape):
    b = ec.bbox(shape); return (b[0] * MIL, -b[3] * MIL, b[2] * MIL, -b[1] * MIL)
pads = {1: [], 2: []}
for p in Bc.pads:
    bb = vbox(p.shape)
    for s in (1, 2):
        if s in p.layers or (s == 2 and 2 in p.layers): pads[s].append((bb, p.des))
crt = {1: [], 2: []}
for d, (x, y, r, s) in plan.items():
    x0, y0, x1, y1 = crt_vis(d, r, s); R = (x + x0, y + y0, x + x1, y + y1)
    for side in ((1, 2) if d in TH else (s,)): crt[side].append((R, d))
placed = {1: [], 2: []}
def hit(r, L, own=None, g=0.1):
    for o, od in L:
        if od == own: continue
        if r[0] < o[2] + g and r[2] > o[0] - g and r[1] < o[3] + g and r[3] > o[1] - g: return True
    return False
def ok(r, side, d):
    if r[0] < 0.3 or r[1] < 0.3 or r[2] > W - 0.3 or r[3] > H - 0.3: return False
    if hit(r, pads[side], g=0.15): return False          # silk never on copper pads (own pads included)
    if hit(r, crt[side], own=d, g=0.05): return False
    if hit(r, placed[side], g=0.15): return False
    return True
def lrect(cx, cy, rot, d):
    w, h = (tl(d), TH_ + 0.1) if rot == 0 else (TH_ + 0.1, tl(d))
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
result = {}
order = sorted(plan, key=lambda d: (d not in rowlab, -((G[d]['crt'][2] - G[d]['crt'][0]) * (G[d]['crt'][3] - G[d]['crt'][1]))))
hidden = []
own_r = {}
if ONLY:                                          # existing labels of untouched parts are obstacles, left as they are
    _P = ec.Project(SRC)
    for l in _P.text.split(chr(10)):
        if l.startswith('["ATTR"'):
            a = json.loads(l)
            if a[7] == 'Designator' and a[10] and a[3] in Bc.des and Bc.des[a[3]] not in ONLY:
                d0 = Bc.des[a[3]]; cx, cy, rot = a[5] * MIL, -a[6] * MIL, a[17] or 0
                w, h = (tl(d0), TH_ + 0.1) if rot in (0, 180) else (TH_ + 0.1, tl(d0))
                placed[3 if False else (1 if a[4] == 3 else 2)].append(((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), d0))
    order = [d for d in order if d in ONLY]
for d, (x, y, r, s) in plan.items():
    x0, y0, x1, y1 = crt_vis(d, r, s); own_r[d] = (x + x0, y + y0, x + x1, y + y1)
def rdist(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0); dy = max(b[1] - a[3], a[1] - b[3], 0); return math.hypot(dx, dy)
def unambiguous(R, d, side):
    """the label must be clearly closer to its own part than to any other part on that side."""
    mine = rdist(R, own_r[d])
    if mine > 0.35: return False                       # the label touches its own part
    for o, od in crt[side]:
        if od == d: continue
        if rdist(R, o) < mine + 0.1 - 1e-6: return False   # nothing else as close to the label as its own part
    return True
for d in order:
    x, y, r, s = plan[d]
    if d in rowlab:
        cx, cy, rot = rowlab[d]; R = lrect(cx, cy, rot, d)
        if ok(R, s, d) and unambiguous(R, d, s):
            placed[s].append((R, d)); result[d] = (cx, cy, rot, 1); continue
    X0, Y0, X1, Y1 = own_r[d]
    cxm, cym = (X0 + X1) / 2, (Y0 + Y1) / 2
    wide = (X1 - X0) >= (Y1 - Y0)
    big = max(X1 - X0, Y1 - Y0) > 4.0
    cands = []
    for g in (0.1, 0.2, 0.3):
        # 1) beside the long side, text parallel to the part, centred; 2) beyond an end, on the part's own axis
        if wide: opts = [('T', 0), ('B', 0), ('L', 0), ('R', 0)]
        else:    opts = [('L', 90), ('R', 90), ('T', 90), ('B', 90)]
        for sd, rot in opts:
            w, h = (tl(d), TH_ + 0.1) if rot == 0 else (TH_ + 0.1, tl(d))
            span = ((X1 - X0) if sd in 'TB' else (Y1 - Y0))
            lim = max(0.0, span / 2 - (w if sd in 'TB' else h) / 2) if big else 0.15
            shifts = [0.0]; k = 0.25
            while k <= lim + 1e-9: shifts += [k, -k]; k += 0.25
            for sh in shifts:
                if sd == 'T': cands.append((cxm + sh, Y0 - g - h / 2, rot))
                if sd == 'B': cands.append((cxm + sh, Y1 + g + h / 2, rot))
                if sd == 'L': cands.append((X0 - g - w / 2, cym + sh, rot))
                if sd == 'R': cands.append((X1 + g + w / 2, cym + sh, rot))
    if big: cands.append((cxm, cym, 0 if wide else 90))           # inside a large body if no pad is under it
    for cx, cy, rot in cands:
        R = lrect(cx, cy, rot, d)
        if ok(R, s, d) and unambiguous(R, d, s):
            placed[s].append((R, d)); result[d] = (cx, cy, rot, 1); break
    else:
        result[d] = (x, y, 0, 0); hidden.append(d)
# write
P = ec.Project(SRC)
rows = [json.loads(l) if l.strip() else None for l in P.text.split('\n')]
cid2d = {cid: d for cid, d in Bc.des.items()}
n = 0
for rr in rows:
    if rr and rr[0] == 'ATTR' and rr[7] == 'Designator' and rr[3] in cid2d:
        d = cid2d[rr[3]]
        if d not in result: continue
        cx, cy, rot, vis = result[d]
        rr[5], rr[6] = round(cx / MIL, 4), round(-cy / MIL, 4)
        rr[10] = vis; rr[12] = round(TH_ / MIL, 3); rr[13] = round(SW_ / MIL, 4); rr[16] = 5; rr[17] = rot
        n += 1
new = '\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) if r is not None else '' for r in rows)
ec.make_candidate(P, new, OUT)
json.dump(result, open('labels_final.json', 'w'))
top_h = [d for d in hidden if plan[d][3] == 1]; bot_h = [d for d in hidden if plan[d][3] == 2]
print('labels written', n, '| hidden top', len(top_h), top_h[:30], '| hidden bottom', len(bot_h))
