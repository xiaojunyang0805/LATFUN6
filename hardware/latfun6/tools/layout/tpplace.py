"""Place rail test points TP13-TP19 next to their regulator output (after the sense resistor where one exists).
Same rules as tidy.py: courtyard gap 0.6 mm, SERDES corridors, hole keep-outs, BGA fields; also avoids existing labels."""
import json, math, os
os.environ.setdefault('BOARD_W', '145.65')
exec(open('placer_geo.py').read())
plan = json.load(open('plan.json')); LB = json.load(open('labels_final.json'))
HOLES = json.load(open('holes.json'))
ANCH = {'TP13': ('RS2', '1V2'), 'TP14': ('RS4', '1V35'), 'TP15': ('L22', '1V8'), 'TP16': ('RS1', '3V3'),
        'TP17': ('RS3', '2V5'), 'TP18': ('U23', '5V_SYS'), 'TP19': ('C227', '1V2_SER')}
GAP = 0.6
def rect(d, p):
    x, y, r, s = p; x0, y0, x1, y1 = crt_vis(d, r, s); return (x + x0, y + y0, x + x1, y + y1)
occ = [(rect(d, p), d) for d, p in plan.items() if (p[3] == 1 or d in TH) and d not in ANCH]
def field(d, inset):
    x, y, r, s = plan[d]; x0, y0, x1, y1 = crt_vis(d, r, s, 'pad'); return (x + x0 + inset, y + y0 + inset, x + x1 - inset, y + y1 - inset)
KEEP = [field('U5', -1.5), field('U30', -1.5), (57.5, 52.0, 65.8, 101.5), (49.8, 43.0, 67.2, 58.8), (50.5, 4.5, 57.0, 43.0),
        (0, 0, 12.7, 10.1), (0, 85.35, 12.7, H)] + [(hx - 4.3, hy - 4.3, hx + 4.3, hy + 4.3) for hx, hy in HOLES]
def tl(d): return len(d) * 0.62 * 0.8 + 0.1
labs = []
for d, (cx, cy, rot, vis) in LB.items():
    if vis and plan[d][3] == 1:
        w, h = (tl(d), 0.9) if rot == 0 else (0.9, tl(d)); labs.append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
def inter(a, b, g): return a[0] < b[2] + g and a[2] > b[0] - g and a[1] < b[3] + g and a[3] > b[1] - g
def free(r):
    if r[0] < 0.5 or r[1] < 0.5 or r[2] > W - 0.5 or r[3] > H - 0.5: return False
    if any(inter(r, k, 0) for k in KEEP): return False
    if any(inter(r, o, GAP) for o, _ in occ): return False
    if any(inter(r, l, 0.15) for l in labs): return False
    return True
def pin(d, net):
    x, y, r, s = plan[d]
    for num, n in G[d]['pads']:
        if n == net: u, v = localpads[d][num]; dx, dy = xf(u, v, r, s); return x + dx, y + dy
res = {}
for tp, (a, net) in ANCH.items():
    px, py = pin(a, net); best = None
    for i in range(-48, 49):
        for j in range(-48, 49):
            x, y = px + i * 0.25, py + j * 0.25
            for rot in (0, 90):
                p = [round(x, 3), round(y, 3), rot, 1]; R = rect(tp, p)
                # keep a label slot (TP label 0.8 mm text) above or below
                if not free(R): continue
                lab = (R[0], R[1] - 1.3, R[2], R[1] - 0.2)
                d2 = (x - px) ** 2 + (y - py) ** 2 + (0 if rot == 0 else 0.5)
                if best is None or d2 < best[0]: best = (d2, p)
    if best is None: print(tp, 'NO SPOT'); continue
    p = best[1]; res[tp] = p; plan[tp] = p; occ.append((rect(tp, p), tp))
    print(tp, net, 'near', a, (round(px, 1), round(py, 1)), '->', p, 'dist %.1f mm' % math.sqrt(best[0]))
json.dump(plan, open('plan.json', 'w'))
json.dump(res, open('tp_rail.json', 'w'))
