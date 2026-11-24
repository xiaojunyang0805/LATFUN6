"""GND (or any pour net) connectivity through EDA's REAL fill: rasterises the POURED records saved after Rebuild All
Copper (even-odd over each pour's paths; ARC drawn as true arcs), labels fill fragments per layer, and joins the net's
islands (eprj_check) whose copper touches the same fragment. Lists islands outside the main group.
    python poured_conn.py BOARD.eprj [--net GND]"""
import sys, os, json, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import ndimage
from matplotlib.path import Path
import eprj_core as ec, eprj_check
import lfr
from lfr import G

args = sys.argv[1:]
NET = args[args.index('--net') + 1] if '--net' in args else 'GND'
MIL = 0.0254
PU = 0.254                                  # POURED paths are stored in 10-mil units
P = ec.Project(args[0]); W = lfr.World(args[0]); B = ec.Board(args[0])
recs = [json.loads(l) for l in P.text.split('\n') if l.startswith('["POUR')]
pour_layer = {a[1]: a[4] for a in recs if a[0] == 'POUR' and a[3] == NET}


def path_pts(p):
    """EDA path [x,y,'L',x,y,...,'ARC',ang,x,y,...] in mil -> list of (x_mm, y_mm) (y down)"""
    out = [(p[0], p[1])]; i = 2; mode = 'L'
    while i < len(p):
        if isinstance(p[i], str):
            mode = p[i]; i += 1; continue
        if mode == 'ARC':
            ang = math.radians(p[i]); x1, y1 = p[i + 1], p[i + 2]; i += 3
            x0, y0 = out[-1]
            if abs(ang) > 1e-6:
                d = math.hypot(x1 - x0, y1 - y0); r = d / 2 / math.sin(abs(ang) / 2)
                mx, my = (x0 + x1) / 2, (y0 + y1) / 2
                h = math.sqrt(max(r * r - d * d / 4, 0)); ux, uy = -(y1 - y0) / d, (x1 - x0) / d
                s = 1 if ang > 0 else -1
                cx, cy = mx + s * ux * h * (1 if abs(ang) <= math.pi else -1), my + s * uy * h * (1 if abs(ang) <= math.pi else -1)
                a0 = math.atan2(y0 - cy, x0 - cx); n = max(int(abs(ang) / math.radians(10)), 2)
                # choose direction that ends at x1,y1
                for sg in (1, -1):
                    pts = [(cx + r * math.cos(a0 + sg * ang * k / n), cy + r * math.sin(a0 + sg * ang * k / n)) for k in range(1, n + 1)]
                    if math.hypot(pts[-1][0] - x1, pts[-1][1] - y1) < max(0.05 * r, 0.05):
                        out.extend(pts); break
                else:
                    out.append((x1, y1))
            else:
                out.append((x1, y1))
        else:
            out.append((p[i], p[i + 1])); i += 2
    return [(x * PU, -y * PU) for x, y in out]


NX, NY = W.NX, W.NY
XC, YC = np.meshgrid(np.arange(NX) * G, np.arange(NY) * G)
QP = np.column_stack([XC.ravel(), YC.ravel()])
CACHE = args[args.index('--cache') + 1] if '--cache' in args else None
fill = {}
if CACHE and os.path.exists(CACHE):
    z = np.load(CACHE); fill = {int(k): z[k] for k in z.files}; recs_f = []
else:
    recs_f = sorted(recs, key=lambda a: a[0] == 'POURED' and a[4] is False)
for a in recs_f:
    if a[0] != 'POURED' or a[2] not in pour_layer:
        continue
    lay = pour_layer[a[2]]
    m = fill.setdefault(lay, np.zeros((NY, NX), bool))
    if a[4] is False:                       # thermal spoke: a stroked line (EDA default spoke 10 mil)
        for pth in a[5]:
            pts = path_pts(pth)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                s_ = ('k', x0, y0, x1, y1, 0.127)
                bb = lfr.shape_bbox(s_)
                jx0, jx1 = max(int(bb[0] / G) - 1, 0), min(int(bb[2] / G) + 2, NX)
                jy0, jy1 = max(int(bb[1] / G) - 1, 0), min(int(bb[3] / G) + 2, NY)
                m[jy0:jy1, jx0:jx1] |= lfr.shape_dist(s_, XC[jy0:jy1, jx0:jx1], YC[jy0:jy1, jx0:jx1]) <= 0
        continue
    for pth in a[5]:
        if not pth or len(pth) < 6:
            continue
        pts = path_pts(pth)
        xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
        ix0, ix1 = max(int(min(xs) / G) - 1, 0), min(int(max(xs) / G) + 2, NX)
        iy0, iy1 = max(int(min(ys) / G) - 1, 0), min(int(max(ys) / G) + 2, NY)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        sub = np.column_stack([XC[iy0:iy1, ix0:ix1].ravel(), YC[iy0:iy1, ix0:ix1].ravel()])
        ins = Path(pts).contains_points(sub).reshape(iy1 - iy0, ix1 - ix0)
        m[iy0:iy1, ix0:ix1] ^= ins
if CACHE and not os.path.exists(CACHE):
    np.savez_compressed(CACHE, **{str(k): v for k, v in fill.items()})
isl = [x for x in eprj_check.islands(B).get(NET, [])]
par = list(range(len(isl)))
def find(a):
    while par[a] != a:
        par[a] = par[par[a]]; a = par[a]
    return a
for lay, m in fill.items():
    lab, nf = ndimage.label(m, structure=np.ones((3, 3)))
    print(f'layer {lay}: fill {m.sum() * G * G:.0f} mm2, {nf} fragments')
    touch = collections.defaultdict(set)
    for k, x in enumerate(isl):
        shapes = []
        for v in x['vias']:
            c = lfr.to_mm(v.x, v.y)
            shapes += [e['s'] for e in W.near((c[0] - .01, c[1] - .01, c[0] + .01, c[1] + .01)) if e['cls'] == 'via' and e['net'] == NET]
        for pd in x['pads']:
            e = W.pad.get(f'{pd.des}.{pd.num}')
            if e and lay in e['layers']:
                shapes.append(e['s'])
        for t in x['tracks']:
            if t.layer == lay:
                a_, b_ = lfr.to_mm(t.x1, t.y1), lfr.to_mm(t.x2, t.y2)
                shapes.append(('k', a_[0], a_[1], b_[0], b_[1], t.width * MIL / 2))
        for s_ in shapes:
            bb = lfr.shape_bbox(s_)
            ix0, ix1 = max(int(bb[0] / G) - 2, 0), min(int(bb[2] / G) + 3, NX)
            iy0, iy1 = max(int(bb[1] / G) - 2, 0), min(int(bb[3] / G) + 3, NY)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            near_ = lfr.shape_dist(s_, XC[iy0:iy1, ix0:ix1], YC[iy0:iy1, ix0:ix1]) <= 0.07
            sub = lab[iy0:iy1, ix0:ix1][near_]
            for f in set(sub[sub > 0].ravel().tolist()):
                touch[f].add(k)
    for f, ks in touch.items():
        ks = sorted(ks)
        for k in ks[1:]:
            par[find(k)] = find(ks[0])
roots = collections.Counter(find(k) for k in range(len(isl)))
main = roots.most_common(1)[0][0]
off = [k for k in range(len(isl)) if find(k) != main]
print(f'{NET}: {len(isl)} islands -> {len(roots)} groups; outside main: {len(off)}')
for k in off:
    x = isl[k]
    print('   ', sorted(f'{p.des}.{p.num}' for p in x['pads'])[:4], 'vias', [tuple(round(v, 2) for v in lfr.to_mm(v.x, v.y)) for v in x['vias']][:3])
