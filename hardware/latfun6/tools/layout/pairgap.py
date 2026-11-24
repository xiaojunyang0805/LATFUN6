"""Diff-pair check on a saved file (what EDA's differentialPair DRC looks at): per *_P/*_N pair, minimum P-N edge gap on
a shared layer (DP100/DP85 gap_min 0.18 mm) with its location, and the track widths used.
    python pairgap.py EPRJ [gap_min]"""
import sys, os, collections
sys.path.insert(0, os.environ['PCB_LAYOUT_SCRIPTS']); import eprj_core as ec
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import lfr
B = ec.Board(sys.argv[1]); GMIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.18
M = 0.0254
T = collections.defaultdict(list)
for t in B.tracks:
    T[t.net].append(t)
bad = 0
for base in sorted(n[:-2] for n in T if n.endswith('_P') and n[:-2] + '_N' in T):
    best = (1e9, None)
    for a in T[base + '_P']:
        for b in T[base + '_N']:
            if a.layer != b.layer:
                continue
            d = lfr._segseg((a.x1 * M, -a.y1 * M), (a.x2 * M, -a.y2 * M), (b.x1 * M, -b.y1 * M), (b.x2 * M, -b.y2 * M)) - (a.width + b.width) * M / 2
            if d < best[0]:
                best = (d, (round(a.x1 * M, 2), round(-a.y1 * M, 2), round(a.x2 * M, 2), round(-a.y2 * M, 2), a.layer))
    flag = '  <-- below gap_min' if best[0] < GMIN - 1e-4 else ''
    bad += bool(flag)
    print(f'{base:12} min gap {best[0]:.3f} mm at P seg {best[1]}  widths {sorted({round(t.width * M, 3) for t in T[base + "_P"] + T[base + "_N"]})}{flag}')
print('pairs below gap_min:', bad)
