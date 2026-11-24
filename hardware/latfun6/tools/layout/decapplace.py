"""Re-place the bottom decaps that the BGA fan-out vias would hit (fanout_plan.json 'bottom_hits').
Each goes to the via-free bottom spot nearest a ball of its own rail on U5 (or U30 for C350-C357).
Rules: pad-to-pad >= 0.6 mm to every other part (assembly); pad-to-via >= 0.152 mm for a foreign via and
>= 0.05 mm for its own net (no via-in-pad); courtyards do not overlap (0.2 mm gap); hole keep-outs; board edge.
Every other part keeps its file position.  Writes plan.json (positions) for writecand.py."""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', '')))
import eprj_core as ec
exec(open('placer_geo.py').read())          # B, G, xf, crt_vis, TH, W, H, MIL
FP = json.load(open('fanout_plan.json'))
TARGET = sorted(FP['bottom_hits'])
VIAS = [(f['via'], f['net']) for f in FP['fan']]           # file mil coords
plan = {B.des[c]: [B.comp[c][4] * MIL, -B.comp[c][5] * MIL, B.comp[c][6] or 0, B.comp[c][3]] for c in B.comp}
HOLES = json.load(open('holes.json'))
CLR = B.rules.copper
ASM = 0.6 / MIL
VR = 0.40 / MIL / 2
# ---- obstacles: other parts' pads on the bottom (incl. through-hole), in file mil
obst = [p for p in B.pads if p.des not in TARGET and (2 in p.layers)]
og = ec.Grid(60.0)
for k, p in enumerate(obst): og.add(k, ec.bbox(p.shape))
vg = ec.Grid(40.0)
for k, ((vx, vy), n) in enumerate(VIAS): vg.add(k, (vx - VR, vy - VR, vx + VR, vy + VR))
crt_bot = [((lambda r: (x + r[0], y + r[1], x + r[2], y + r[3]))(crt_vis(d, rr, s)), d)
           for d, (x, y, rr, s) in plan.items() if (s == 2 or d in TH) and d not in TARGET]
KEEP = [(hx - 4.3, hy - 4.3, hx + 4.3, hy + 4.3) for hx, hy in HOLES] + [(0, 0, 2.6, H)]
# ---- local pad shapes of each target footprint
def local_pads(d):
    cid = next(c for c in B.comp if B.des[c] == d)
    F = B.P.footprints[B.attr[cid]['Footprint']]
    net = {p.num: p.net for p in B.pads if p.des == d}
    return [(B._pad_local_shape(a), net.get(str(a[5]))) for a in F if a[0] == 'PAD']
def balls(anchor, rail):
    return [ec.shape_center(p.shape) for p in B.pads if p.des == anchor and p.net == rail]
def inter(a, b, g): return a[0] < b[2] + g and a[2] > b[0] - g and a[1] < b[3] + g and a[3] > b[1] - g
placed_pads = []          # (shape, des)
placed_crt = []
res = {}
order = sorted(TARGET)
for d in order:
    anchor = 'U30' if d in ['C%d' % i for i in range(350, 360)] else 'U5'
    rail = [n for _, n in G[d]['pads'] if n and n != 'GND'][0]
    BL = balls(anchor, rail)
    LP = local_pads(d)
    bx0 = min(b[0] for b in BL) - 6 / MIL; bx1 = max(b[0] for b in BL) + 6 / MIL
    by0 = min(b[1] for b in BL) - 6 / MIL; by1 = max(b[1] for b in BL) + 6 / MIL
    best = None
    step = 0.2 / MIL
    nx = int((bx1 - bx0) / step); ny = int((by1 - by0) / step)
    cands = []
    for ix in range(nx + 1):
        for iy in range(ny + 1):
            x, y = bx0 + ix * step, by0 + iy * step
            cost = min(math.hypot(x - b[0], y - b[1]) for b in BL)
            cands.append((cost, x, y))
    cands.sort()
    for cost, x, y in cands:
        for rot in (0, 90):
            ok = True
            shapes = [(ec.Board._place(s, x, y, rot, True), n) for s, n in LP]
            # courtyard (visual mm) check
            vx, vy = x * MIL, -y * MIL
            c0 = crt_vis(d, rot, 2); R_ = (vx + c0[0], vy + c0[1], vx + c0[2], vy + c0[3])
            if R_[0] < 0.5 or R_[1] < 0.5 or R_[2] > W - 0.5 or R_[3] > H - 0.5: ok = False
            if ok and any(inter(R_, k, 0) for k in KEEP): ok = False
            if ok and any(inter(R_, o, 0.2) for o, _ in crt_bot + placed_crt): ok = False
            if ok:
                for sh, n in shapes:
                    bb = ec.bbox(sh)
                    for q in og.near(bb, ASM + 1):
                        if ec.gap(sh, obst[q].shape) < ASM: ok = False; break
                    if not ok: break
                    for q in vg.near(bb, CLR + 1):
                        (vx_, vy_), vn = VIAS[q]
                        g = ec.gap(sh, ('c', vx_, vy_, VR))
                        if g < (0.05 / MIL if vn == n else CLR): ok = False; break
                    if not ok: break
                    for ps, pd in placed_pads:
                        if ec.gap(sh, ps) < ASM: ok = False; break
                    if not ok: break
            if ok:
                best = (cost, x, y, rot, shapes, R_)
                break
        if best: break
    assert best, ('no spot', d)
    cost, x, y, rot, shapes, R_ = best
    placed_pads += [(sh, d) for sh, _ in shapes]
    placed_crt.append((R_, d))
    plan[d] = [round(x * MIL, 3), round(-y * MIL, 3), rot, 2]
    res[d] = round(cost * MIL, 2)
print('re-placed', len(res), '| distance to nearest own-rail ball (mm):', res)
json.dump(plan, open('plan.json', 'w'))
