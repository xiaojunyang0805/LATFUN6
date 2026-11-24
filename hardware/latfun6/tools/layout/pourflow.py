"""Offline estimate of pour connectivity (EDA computes the real fill on Rebuild All Copper): for each POUR record, the
fill area = pour polygon (rectangle 'R' paths or outline) minus clearance (general rule + half the minimum fill width)
to every other-net copper on that layer and to the board edge; copper of the pour's own net counts as connected where
it touches the fill. Flood fill per fill fragment; reports, per pour net, which islands (eprj_check) are joined through
the fill of each layer, and fragments that would be isolated (no own-net copper).
    python pourflow.py BOARD.eprj [--minw 0.15] [--nets N1,N2]"""
import sys, os, json, math, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import ndimage
import eprj_core as ec, eprj_check
import lfr
from lfr import G

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src = args[0]
MINW = float(opt('--minw', 0.15))
ONLY = set((opt('--nets') or '').split(',')) - {''}
MIL = 0.0254
P = ec.Project(src)
W = lfr.World(src)
B = ec.Board(src)
isl = eprj_check.islands(B)
pours = [json.loads(l) for l in P.text.split('\n') if l.startswith('["POUR",')]
NX, NY = W.NX, W.NY
X, Y = np.meshgrid(np.arange(NX) * G, np.arange(NY) * G)


def poly_mask(path):
    if path and path[0] == 'R':
        x0, y0 = path[1] * MIL, -path[2] * MIL
        return (X >= x0) & (X <= x0 + path[3] * MIL) & (Y >= y0) & (Y <= y0 + path[4] * MIL)
    return W.edge_dist >= 0          # outline pour: whole board (edge clearance applied below)


UNION = {}
by = collections.defaultdict(list)
for p in pours:
    if not ONLY or p[3] in ONLY:
        by[(p[3], p[4])].append(p)
for (net, lay), ps in sorted(by.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    area = np.zeros((NY, NX), bool)
    for p in ps:
        area |= poly_mask(p[8][0])
    blocked = W.blocked({net}, lay, MINW / 2, (0, 0, NX - 1, NY - 1))
    fill = area & ~blocked
    lab, nfrag = ndimage.label(fill, structure=np.ones((3, 3)))
    # own copper on this layer: which fragment(s) does each island touch
    frag_isl = collections.defaultdict(set)
    g = [x for x in isl.get(net, []) if x['pads']]
    for k, x in enumerate(g):
        pts = []
        for v in x['vias']:
            pts.append(lfr.to_mm(v.x, v.y))
        for pd in x['pads']:
            key = f'{pd.des}.{pd.num}'
            if key in W.pad and lay in W.pad[key]['layers']:
                pts.append(lfr.shape_center(W.pad[key]['s']))
        for t in B.tracks:
            if t.net == net and t.layer == lay:
                pass
        for (px, py) in pts:
            cx, cy = int(round(px / G)), int(round(py / G))
            r = 6                                  # look within 0.3 mm (via/pad body + clearance gap)
            win = lab[max(cy - r, 0):cy + r + 1, max(cx - r, 0):cx + r + 1]
            for f in set(win[win > 0].ravel().tolist()):
                frag_isl[f].add(k)
    UNION.setdefault(net, []).extend((lay, f, frozenset(v)) for f, v in frag_isl.items())
    big = [(int((lab == f).sum()) * G * G, f) for f in range(1, nfrag + 1)]
    big.sort(reverse=True)
    joined = [sorted(v) for f, v in frag_isl.items() if len(v) > 1]
    touched = set().union(*frag_isl.values()) if frag_isl else set()
    print(f'{net:11} L{lay:<3} fill {sum(a for a, _ in big):7.1f} mm2 in {nfrag} fragments; '
          f'islands {len(g)}, touched {len(touched)}, joined groups {joined}')
    dead = [round(a, 1) for a, f in big if f not in frag_isl and a > 1.0]
    if dead:
        print(f'            isolated fragments > 1 mm2 (no own copper): {dead[:10]}')

for net, groups in UNION.items():
    g = [x for x in isl.get(net, []) if x['pads']]
    par = list(range(len(g)))
    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for _, _, v in groups:
        v = sorted(v)
        for k in v[1:]:
            par[find(k)] = find(v[0])
    roots = collections.Counter(find(k) for k in range(len(g)))
    main = roots.most_common(1)[0][0]
    off = [sorted(f'{p.des}.{p.num}' for p in g[k]['pads'])[:3] for k in range(len(g)) if find(k) != main]
    print(f'{net}: all layers combined -> {len(roots)} groups; main group {roots[main]} of {len(g)} islands; outside main: {len(off)}')
    print('   ', off[:40])
