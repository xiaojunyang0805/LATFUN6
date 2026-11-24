"""Find free Top positions for small parts boxed in by routing (pcb-layout W6b), placed one after another so each
part sees the ones before it. A position is legal when every pad clears all copper (general rule), stays >= 0.6 mm
from other parts' pads (assembly) and every signal pad has a legal via spot within 0.8 mm. Prints move.py arguments.
    python placefree.py BOARD.eprj DES:TX:TY [DES:TX:TY ...] [--box x0,y0,x1,y1]   (target = point to stay near)"""
import sys, math
import numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import lfr
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src = args[0]
jobs = [(a.split(':')[0], float(a.split(':')[1]), float(a.split(':')[2])) for a in args[1:] if ':' in a and not a.startswith('--')]
box = tuple(float(v) for v in (opt('--box') or '56,12,96,48').split(','))
LAY = int(opt('--layer', 1))                 # 1 Top, 2 Bottom (side of the movers)
NEAR = float(opt('--near', 0))              # > 0: each part searches only within NEAR mm of its target
VR = float(opt('--vr', 0.8))                # via spot within VR mm of each pad
W = lfr.World(src); W.add_field('U5'); W.add_field('U30')
G = lfr.G
mine = {k for d, _, _ in jobs for k in W.pad if k.split('.')[0] == d}
win = W.win([(box[0], box[1]), (box[2], box[3])], 0)
ix0, iy0 = win[0], win[1]
own_nets = {W.pad[k]['net'] for k in mine}
_sh = W.sh; W.sh = [e for e in _sh if not (e['cls'] == 'pad' and e['src'] in mine)]   # only the movers' own pads exempt
blk = W.blocked(set(), LAY, 0.0, win)                       # Top copper within the general rule
VOK = {n: W.via_ok({n}, win, 0.4, 0.2) for n in own_nets}
W.sh = _sh
obst = [e['bbox'] for e in W.sh if e['cls'] == 'pad' and LAY in e['layers'] and e['src'] not in mine]
placed = []
for d, tx, ty in jobs:
    pads = [(k, W.pad[k]) for k in W.pad if k.split('.')[0] == d]
    c0 = np.mean([lfr.shape_center(e['s']) for _, e in pads], axis=0)
    best = None
    bx = (tx - NEAR, ty - NEAR, tx + NEAR, ty + NEAR) if NEAR > 0 else box
    for dx in np.arange(bx[0] - c0[0], bx[2] - c0[0], 0.1):
        for dy in np.arange(bx[1] - c0[1], bx[3] - c0[1], 0.1):
            nx, ny = c0[0] + dx, c0[1] + dy
            dist = math.hypot(nx - tx, ny - ty)
            if best and dist >= best[0]:
                continue
            good = True
            for k, e in pads:
                b = lfr.shape_bbox(e['s'])
                for (x, y) in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3]), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)):
                    X, Y = int(round((x + dx) / G)) - ix0, int(round((y + dy) / G)) - iy0
                    if not (0 <= Y < blk.shape[0] and 0 <= X < blk.shape[1]) or blk[Y, X]:
                        good = False; break
                if not good:
                    break
                bb = (b[0] + dx - 0.6, b[1] + dy - 0.6, b[2] + dx + 0.6, b[3] + dy + 0.6)
                if any(not (o[2] < bb[0] or o[0] > bb[2] or o[3] < bb[1] or o[1] > bb[3]) for o in obst + placed):
                    good = False; break
                if True:
                    vok = VOK[e['net']]
                    cx, cy = lfr.shape_center(e['s']); cx += dx; cy += dy
                    X0, X1 = int((cx - VR) / G) - ix0, int((cx + VR) / G) - ix0
                    Y0, Y1 = int((cy - VR) / G) - iy0, int((cy + VR) / G) - iy0
                    if X0 < 0 or Y0 < 0 or not vok[Y0:Y1 + 1, X0:X1 + 1].any():
                        good = False; break
            if good:
                best = (dist, nx, ny, dx, dy)
    if best is None:
        print(f'{d}: no legal spot in box {box}'); continue
    dist, nx, ny, dx, dy = best
    for k, e in pads:
        b = lfr.shape_bbox(e['s']); placed.append((b[0] + dx, b[1] + dy, b[2] + dx, b[3] + dy))
    print(f'{d}: move by ({dx:+.2f},{dy:+.2f}) to centre ({nx:.2f},{ny:.2f}), {dist:.1f} mm from target')
