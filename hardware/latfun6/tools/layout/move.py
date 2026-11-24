"""Move parts into a candidate copy (positions in mm, board-up y like plan.json: y_mm = -file_y).
   python move.py OUT.eprj DES:X:Y:ROT[:SIDE] ...    (EPRJ env = source; prints old->new; project untouched)"""
import sys, os, json, math
sys.path.insert(0, os.environ['PCB_LAYOUT_SCRIPTS'])
import eprj_core as ec
MIL = 0.0254
SRC = os.environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj')
OUT = sys.argv[1]
plan = {}
for a in sys.argv[2:]:
    f = a.split(':'); plan[f[0]] = (float(f[1]), float(f[2]), float(f[3]) if '.' in f[3] else int(f[3]), int(f[4]) if len(f) > 4 else None)
P = ec.Project(SRC)
lines = P.text.split('\n')
rj = [json.loads(l) if l.strip() else None for l in lines]
des = {r[3]: r[8] for r in rj if r and r[0] == 'ATTR' and len(r) > 8 and r[7] == 'Designator'}
moved = {}
for i, r in enumerate(rj):
    if r and r[0] == 'COMPONENT' and des.get(r[1]) in plan:
        vx, vy, rot, side = plan[des[r[1]]]; side = side or r[3]
        nx, ny = vx / MIL, -vy / MIL
        print(des[r[1]], 'old', round(r[4]*MIL, 3), round(-r[5]*MIL, 3), r[6], r[3], '-> new', vx, vy, rot, side)
        moved[r[1]] = (r[4], r[5], r[6] or 0, r[3], nx, ny, rot, side)
        r[3], r[4], r[5], r[6] = side, round(nx, 4), round(ny, 4), rot
        lines[i] = json.dumps(r, separators=(',', ':'), ensure_ascii=False)
for i, r in enumerate(rj):
    if r and r[0] == 'ATTR' and r[3] in moved:
        ox, oy, orot, oside, nx, ny, nrot, nside = moved[r[3]]
        if r[5] is not None and r[6] is not None:
            dx, dy = r[5] - ox, r[6] - oy
            a = math.radians(nrot - orot); c, s_ = math.cos(a), math.sin(a)
            r[5], r[6] = round(nx + dx * c - dy * s_, 4), round(ny + dx * s_ + dy * c, 4)
        if r[4] in (3, 4): r[4] = 3 if nside == 1 else 4
        lines[i] = json.dumps(r, separators=(',', ':'), ensure_ascii=False)
assert len(moved) == len(plan), (set(plan) - {des[c] for c in moved})
ec.make_candidate(P, '\n'.join(lines), OUT)
print('candidate', OUT)
