"""Render a saved .eprj's copper (tracks by layer, vias, pads) for review.
    python viewcopper.py EPRJ OUT.png [x0,y0,x1,y1] [--nets REGEX]"""
import sys, os, re, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import lfr
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon as Pg
a = [x for x in sys.argv[1:] if not x.startswith('--')]
W = lfr.World(a[0]); out = a[1]; box = tuple(map(float, a[2].split(','))) if len(a) > 2 else None
pat = re.compile(sys.argv[sys.argv.index('--nets') + 1]) if '--nets' in sys.argv else None
col = {1: '#d62728', 2: '#1f77b4', 15: '#2ca02c', 16: '#9467bd', 17: '#ff7f0e', 18: '#8c564b'}
fig, ax = plt.subplots(figsize=(16, 12), dpi=120)
inb = lambda b: not box or not (b[2] < box[0] or b[0] > box[2] or b[3] < box[1] or b[1] > box[3])
for e in W.sh:
    if not inb(e['bbox']):
        continue
    s = e['s']
    if e['cls'] == 'pad':
        fc = '#bbbbbb' if 1 in e['layers'] else '#e6c3c3'
        ax.add_patch(Circle((s[1], s[2]), s[3], fc=fc, ec='none') if s[0] == 'c' else Pg(s[1] if s[0] == 'p' else [(s[1], s[2]), (s[3], s[4])], fc=fc, ec='none'))
    elif e['cls'] == 'trk':
        hl = pat is None or (e['net'] and pat.search(e['net']))
        lay = next(iter(e['layers']))
        ax.plot([s[1], s[3]], [s[2], s[4]], color=col.get(lay, 'k') if hl else '#999999', lw=max(2 * s[5] * 72 / 25.4 * (12 * 120 / 72) / max((box[2] - box[0]) if box else 150, 1) * 1.0, 0.4), solid_capstyle='round', alpha=0.9 if hl else 0.5)
    elif e['cls'] == 'via':
        ax.add_patch(Circle((s[1], s[2]), s[3], fc='none', ec='k', lw=0.6))
if box:
    ax.set_xlim(box[0], box[2]); ax.set_ylim(box[3], box[1])
else:
    ax.set_xlim(-2, 148); ax.set_ylim(111, -2)
ax.set_aspect('equal'); ax.set_title(os.path.basename(a[0]) + (f'  {box}' if box else ''))
fig.savefig(out, bbox_inches='tight'); print('wrote', out)
