import json, math, importlib, collections, sys
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
from eprj_core import Board
B = Board(__import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj'))
MIL = 0.0254
W, H = float(__import__('os').environ.get('BOARD_W', '167.65')), float(__import__('os').environ.get('BOARD_H', '102.75'))
G = json.load(open('fpgeo.json'))
# ---------------- geometry helpers ----------------
TH = set()
for cid, c in B.comp.items():
    F = B.P.footprints.get(B.attr[cid].get('Footprint'), [])
    if any(a[0] == 'PAD' and a[4] == 12 for a in F):
        TH.add(B.des[cid])
TH.add('J12')
localpads = {}
for cid in B.comp:
    d = B.des[cid]; F = B.P.footprints.get(B.attr[cid].get('Footprint'), [])
    localpads[d] = {str(a[5]): (a[6] * MIL, a[7] * MIL) for a in F if a[0] == 'PAD'}
def xf(u, v, rot, side):
    """footprint local (mm, file orientation) -> visual offset (mm)."""
    if side == 2: v = -v
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    fx, fy = u * c - v * s, u * s + v * c
    return fx, -fy
def crt_vis(d, rot, side, which='crt'):
    b = [v * MIL for v in G[d][which]]
    pts = [xf(u, v, rot, side) for u in (b[0], b[2]) for v in (b[1], b[3])]
    return min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)
