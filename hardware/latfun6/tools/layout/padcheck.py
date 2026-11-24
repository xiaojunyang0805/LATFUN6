import sys, collections, json
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
from eprj_core import Board, gap, bbox
f = sys.argv[1]; LIM = 0.6 / 0.0254
Bc = Board(f)
EDGE_OK = {'J1','J3','J11','J12','J14','J15','J16','J17','J18','J19','J20','J21','J4','J5','J6','J7','J8'}
pads = list(Bc.pads)
print('board-level pads:', [(p.des, p.num, p.net, round(ec.shape_center(p.shape)[0]*0.0254,2), round(-ec.shape_center(p.shape)[1]*0.0254,2)) for p in Bc.pads if p.des.startswith('PAD_')])
grid = ec.Grid(60.0)
for i, p in enumerate(pads): grid.add(i, bbox(p.shape))
bad = collections.defaultdict(lambda: 1e9)
for i, p in enumerate(pads):
    for j in grid.near(bbox(p.shape), LIM):
        if j <= i: continue
        q = pads[j]
        if q.comp_id == p.comp_id or not (p.layers & q.layers): continue
        if {p.des, q.des} == {'J13', 'J14'}: continue
        g = gap(p.shape, q.shape)
        if g < LIM:
            k = tuple(sorted((p.des, q.des))); bad[k] = min(bad[k], g)
print('pad pairs closer than 0.6 mm:', len(bad))
for k, g in sorted(bad.items(), key=lambda x: x[1])[:40]: print('  ', k, round(g * 0.0254, 3), 'mm')
# off-board pads
o = Bc.outline['pts']; xs=[p[0] for p in o]; ys=[p[1] for p in o]
offb = sorted({p.des for p in pads if p.des not in EDGE_OK and (lambda b: b[0] < min(xs) or b[2] > max(xs) or b[1] < min(ys) or b[3] > max(ys))(bbox(p.shape))})
print('non-edge parts with pads off the body outline:', offb)
