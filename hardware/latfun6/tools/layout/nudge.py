"""Nudge parts to the nearest legal spot (exact sampled clearance): every pad point clears all other copper on the pad
layer (other nets, and same-net copper of other parts' pads) by CLR + 0.01, holes by the hole rule, and other parts'
pads by --pp mm. Prints move.py arguments (centre = origin for 2-pad passives).
    python nudge.py BOARD.eprj DES[,DES..] [--r 3] [--pp 0.5]"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import lfr
args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
W = lfr.World(args[0]); des = args[1].split(',')
R = float(opt('--r', 3.0)); PP = float(opt('--pp', 0.5))
placed = []                                    # pad point sets of parts already nudged
for d in des:
    pads = [(k, e) for k, e in W.pad.items() if k.split('.')[0] == d]
    pts = []
    for k, e in pads:
        b = lfr.shape_bbox(e['s'])
        X, Y = np.meshgrid(np.linspace(b[0], b[2], 9), np.linspace(b[1], b[3], 9))
        X, Y = X.ravel(), Y.ravel()
        m = lfr.shape_dist(e['s'], X, Y) <= 1e-6
        pts.append((e, X[m], Y[m]))
    c0 = np.mean([lfr.shape_center(e['s']) for _, e in pads], axis=0)
    cands = sorted(((math.hypot(dx, dy), dx, dy) for dx in np.arange(-R, R + 1e-9, 0.05) for dy in np.arange(-R, R + 1e-9, 0.05)
                    if math.hypot(dx, dy) <= R))
    found = None
    for dist, dx, dy in cands:
        ok = True
        for e, xs, ys in pts:
            xs2, ys2 = xs + dx, ys + dy
            bb = (xs2.min() - 1, ys2.min() - 1, xs2.max() + 1, ys2.max() + 1)
            for o in W.near(bb):
                if o['cls'] == 'pad' and o['src'].split('.')[0] == d:
                    continue
                lay_hit = bool(set(o['layers']) & set(e['layers']))
                if o['cls'] == 'pad':
                    need = PP if lay_hit else -1
                    if o['net'] and o['net'] == e['net']:
                        need = PP if lay_hit else -1
                elif o['cls'] == 'npth':
                    need = W.EDGE
                else:
                    if not lay_hit or (o['net'] and o['net'] == e['net'] and o['cls'] != 'pad'):
                        need = W.CLR + 0.01 if lay_hit and o['net'] != e['net'] else -1
                    else:
                        need = W.CLR + 0.01
                if need < 0:
                    continue
                if float(lfr.shape_dist(o['s'], xs2, ys2).min()) < need:
                    ok = False; break
            if not ok:
                break
            for (pxs, pys) in placed:
                if np.min(np.hypot(pxs[:, None] - xs2[None, :], pys[:, None] - ys2[None, :])) < PP:
                    ok = False; break
            if not ok:
                break
        if ok:
            found = (dx, dy); break
    if not found:
        print(f'{d}: no legal spot within {R} mm'); continue
    for e, xs, ys in pts:
        placed.append((xs + found[0], ys + found[1]))
    print(f'{d}: nudge ({found[0]:+.2f},{found[1]:+.2f}) -> centre {c0[0] + found[0]:.2f},{c0[1] + found[1]:.2f}')
