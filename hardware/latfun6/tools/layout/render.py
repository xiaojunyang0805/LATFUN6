import json, sys, math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
exec(open('placer_geo.py').read())
plan = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'plan.json'))
out = sys.argv[2] if len(sys.argv) > 2 else 'preview.png'
fig, ax = plt.subplots(figsize=(22, 14.5), dpi=90)
# outline: body + tab
J = plan['J12']; tab_x0 = J[0] + (-25.59) * MIL; tab_x1 = J[0] + 1324.8 * MIL
ax.add_patch(Rectangle((0, 0), W, H, fill=False, lw=2, ec='k'))
ax.add_patch(Rectangle((tab_x0, H), tab_x1 - tab_x0, 111.15 - H, fill=False, lw=2, ec='k'))
for d, (x, y, rot, side) in plan.items():
    x0, y0, x1, y1 = crt_vis(d, rot, side)
    col = '#1f6fd1' if side == 1 else '#d1361f'
    big = (x1 - x0) * (y1 - y0) > 20
    ax.add_patch(Rectangle((x + x0, y + y0), x1 - x0, y1 - y0, fill=side == 1 and big, alpha=0.18 if big else 1,
                           fc=col, ec=col, lw=0.8 if big else 0.5, ls='-' if side == 1 else '--'))
    for num, (u, v) in localpads[d].items():
        px, py = xf(u, v, rot, side)
        ax.plot(x + px, y + py, '.', ms=1.2, color='#444' if side == 1 else '#c66')
    if False:
        ax.text(x, y, d, fontsize=7 if big else 5, ha='center', va='center', color='k', weight='bold' if big else None)
import os
if os.path.exists('labels_final.json'):
    LB=json.load(open('labels_final.json'))
    for d,(cx,cy,rot,vis) in LB.items():
        if vis: ax.text(cx,cy,d,fontsize=3.2,rotation=rot,ha='center',va='center',color='#0a7d22' if plan[d][3]==1 else '#b8860b')
ax.set_xlim(-12, W + 6); ax.set_ylim(114, -8); ax.set_aspect('equal')
ax.set_title('LATFUN6 placement draft (top: blue, bottom: red dashed). Bracket = left edge, PCIe fingers = bottom tab')
ax.grid(alpha=0.2)
plt.tight_layout(); plt.savefig(out); print('wrote', out)
