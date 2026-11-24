"""Write plan.json positions (+ new outline) into a COPY of the project. EDA may stay open: the project file is not touched."""
import json, math, sys, shutil
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
MIL = 0.0254; W, H = float(__import__('os').environ.get('BOARD_W', '167.65')), float(__import__('os').environ.get('BOARD_H', '102.75'))
SRC = __import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj')
OUT = sys.argv[1] if len(sys.argv) > 1 else 'cand.eprj'
plan = json.load(open('plan.json'))
P = ec.Project(SRC)
lines = P.text.split('\n')
rowsj = [json.loads(l) if l.strip() else None for l in lines]
des = {}
for r in rowsj:
    if r and r[0] == 'ATTR' and len(r) > 8 and r[7] == 'Designator': des[r[3]] = r[8]
comp = {r[1]: r for r in rowsj if r and r[0] == 'COMPONENT'}
moved = {}
for cid, r in comp.items():
    d = des.get(cid)
    if d not in plan: continue
    vx, vy, rot, side = plan[d]
    nx, ny = vx / MIL, -vy / MIL
    moved[cid] = (r[4], r[5], r[6] or 0, r[3], nx, ny, rot, side)
    r[3], r[4], r[5], r[6] = side, round(nx, 4), round(ny, 4), rot
for r in rowsj:
    if r and r[0] == 'ATTR' and r[3] in moved:
        ox, oy, orot, oside, nx, ny, nrot, nside = moved[r[3]]
        if r[5] is not None and r[6] is not None:
            dx, dy = r[5] - ox, r[6] - oy
            a = math.radians(nrot - orot); c, s_ = math.cos(a), math.sin(a)
            r[5], r[6] = round(nx + dx * c - dy * s_, 4), round(ny + dx * s_ + dy * c, 4)
        if r[4] in (3, 4): r[4] = 3 if nside == 1 else 4
# outline: body rectangle with 5 mm corner radius, open across the PCIe tab (J12's footprint draws the tab edge)
jx = plan['J12'][0]
tx0, tx1 = (jx + (-25.59055) * MIL) / MIL, (jx + 1324.80315 * MIL) / MIL
Wm, Hm, R = W / MIL, H / MIL, 5.0 / MIL
def arc(cx, cy, a0, a1, n=8):
    return [(cx + R * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + R * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(1, n + 1)]
# file coords: y from 0 (top) to -Hm (bottom)
pts = [(tx0, -Hm), (R, -Hm)] + arc(R, -Hm + R, 270, 180) + [(0, -R)] + arc(R, -R, 180, 90) + [(Wm - R, 0)] \
      + arc(Wm - R, -R, 90, 0) + [(Wm, -Hm + R)] + arc(Wm - R, -Hm + R, 0, -90) + [(tx1, -Hm)]
path = [round(pts[0][0], 4), round(pts[0][1], 4), 'L']
for x, y in pts[1:]: path += [round(x, 4), round(y, 4)]
for r in rowsj:
    if r and r[0] == 'POLY' and len(r) > 6 and r[4] == 11: r[6] = path
# mounting holes: 4 x M3, plated (field 15 = 1), GND, hole 3.2 mm, pad 6.0 mm (template: a GUI-made board PAD)
rowsj = [r for r in rowsj if not (r and r[0] == 'PAD' and str(r[5]).startswith('MH'))]
holes = json.load(open('holes.json'))
nid = P.id_alloc('e8mh')
padrows = []
for k, (hx, hy) in enumerate(holes, 1):
    padrows.append(['PAD', nid(), 0, 'GND', 12, f'MH{k}', round(hx / MIL, 4), round(-hy / MIL, 4), 0,
                    ['ROUND', round(3.2 / MIL, 4), round(3.2 / MIL, 4)], ['ELLIPSE', round(6.0 / MIL, 4), round(6.0 / MIL, 4)],
                    [], 0, 0, 0, 1, 0, None, None, None, None, 0, None, None, None, None, []])
new_lines = [json.dumps(r, ensure_ascii=False, separators=(',', ':')) if r is not None else '' for r in rowsj]
new_lines = ec.insert_after_last(new_lines, [json.dumps(r, separators=(',', ':')) for r in padrows], ('COMPONENT', 'PAD'))
new = chr(10).join(new_lines)
ec.make_candidate(P, new, OUT)
print('moved', len(moved), 'components; outline points', len(pts), '->', OUT)
