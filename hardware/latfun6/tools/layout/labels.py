"""Designator labels: 0.8 mm text, 0.15 mm stroke, centred (align 5). Row parts use the lane tidy.py reserved;
every other part gets the first free spot around its courtyard (no pad, no other part body, no other label, inside
the board). Labels with no legal spot are hidden. Rewrites the Designator ATTR rows of a candidate copy."""
import json, sys, math, os
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
exec(open('placer_geo.py').read())                      # xf, crt_vis, G (only footprint-local data is used), MIL, W, H
SRC = sys.argv[1]; OUT = sys.argv[2]
plan = json.load(open('plan.json')); rowlab = json.load(open('labels_rows.json'))
TH_, SW_ = 0.8, 0.15
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
for d in order:
    x, y, r, s = plan[d]
    if d in rowlab:
        cx, cy, rot = rowlab[d]; R = lrect(cx, cy, rot, d)
        if ok(R, s, d):
            placed[s].append((R, d)); result[d] = (cx, cy, rot, 1); continue
    x0, y0, x1, y1 = crt_vis(d, r, s); X0, Y0, X1, Y1 = x + x0, y + y0, x + x1, y + y1
    cxm, cym = (X0 + X1) / 2, (Y0 + Y1) / 2
    vertical_part = (Y1 - Y0) > (X1 - X0)
    cands = []
    for g in (0.25, 0.6, 1.2):
        sides = (('L', 90), ('R', 90), ('T', 0), ('B', 0)) if vertical_part else (('T', 0), ('B', 0), ('L', 90), ('R', 90))
        for sd, rot in sides + (('T', 90), ('B', 90), ('L', 0), ('R', 0)):
            w, h = (tl(d), TH_ + 0.1) if rot == 0 else (TH_ + 0.1, tl(d))
            for sh in (0, 0.5, -0.5, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0):
                if sd == 'T': cands.append((cxm + sh, Y0 - g - h / 2, rot))
                if sd == 'B': cands.append((cxm + sh, Y1 + g + h / 2, rot))
                if sd == 'L': cands.append((X0 - g - w / 2, cym + sh, rot))
                if sd == 'R': cands.append((X1 + g + w / 2, cym + sh, rot))
    for cx, cy, rot in cands:
        R = lrect(cx, cy, rot, d)
        if ok(R, s, d):
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
