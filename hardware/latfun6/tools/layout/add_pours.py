"""Write the W8 pours as POUR records (record format as eprj_pours.py, copied from GUI-made pours):
GND full-outline on every copper layer except In3; In3 (PWR) split into non-overlapping rectangles: 1V35 over U30 +
the DDR3 corridor, 1V2 under U5's core, 3V3 everywhere else (several rectangles of one net). EDA computes the fill:
the user runs Rebuild All Copper afterwards.
    python add_pours.py IN.eprj OUT.eprj [--gnd-only]"""
import sys, os, json
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
import eprj_core as ec
from eprj_pours import outline_polygon

src, dst = sys.argv[1], sys.argv[2]
MIL = 0.0254
P = ec.Project(src)
B = ec.Board(src)
lines = [l for l in P.text.split('\n') if not (l.startswith('["POUR",') or l.startswith('["POURED",'))]
nid = P.id_alloc('e8p')
J = lambda a: json.dumps(a, separators=(',', ':'), ensure_ascii=False)
new = []
outline = outline_polygon(B, 0.0)
# 2026-11-23: EDA v2.2.47 did not load path-form POUR polygons (Copper Manager empty); GUI-made pours use the
# rectangle form ["R", x, top_y, w, h, 0, 0] -- use the board's bounding rectangle (EDA clips to the outline).
_v = [v for v in outline if not isinstance(v, str)]
outline = ['R', round(min(_v[0::2]), 4), round(max(_v[1::2]), 4), round(max(_v[0::2]) - min(_v[0::2]), 4),
           round(max(_v[1::2]) - min(_v[1::2]), 4), 0, 0]
ALLGND = '--gnd-only' in sys.argv          # user 2026-11-23: every layer routed; GND fills what is left on all layers
for l in B.layers:
    if l != 17 or ALLGND:
        new.append(J(['POUR', nid(), 0, 'GND', l, 0.2, f'GND_{B.layer_name[l]}', 0, [outline], ['SOLID', 8], 0, 0]))


def rect(x0, y0, x1, y1):            # board-view mm (y down) -> file mil rectangle path (top-left x, top y, w, h)
    return ['R', round(x0 / MIL, 4), round(-y0 / MIL, 4), round((x1 - x0) / MIL, 4), round((y1 - y0) / MIL, 4), 0, 0]


GAP = 0.6                             # mm between regions of different nets
regions = [('1V35', (64.0, 14.0, 90.0, 46.6)),
           ('1V2', (72.8, 46.6 + GAP, 90.0, 61.0)),                 # U5 core balls (x 74-78)
           ('VCCHTX_1V2', (64.0, 46.6 + GAP, 72.8 - GAP, 61.0))]    # SERDES TX supply: balls x 70-71.6 + decaps left of U5
X0, X1, Y0, Y1 = 0.3, 144.7, 0.3, 101.7
regions += [('3V3', (X0, Y0, 64.0 - GAP, Y1)), ('3V3', (90.0 + GAP, Y0, X1, Y1)),
            ('3V3', (64.0 - GAP, 61.0 + GAP, 90.0 + GAP, Y1)), ('3V3', (64.0 - GAP, Y0, 90.0 + GAP, 14.0 - GAP))]
for k, (net, r) in enumerate([] if ALLGND else regions):
    new.append(J(['POUR', nid(), 0, net, 17, 0.2, f'{net}_In3_{k}', 0, [rect(*r)], ['SOLID', 8], 0, 0]))
out = ec.insert_after_last(lines, new, ('LINE', 'VIA', 'COMPONENT', 'POUR'))
ec.make_candidate(P, '\n'.join(out), dst)
print(f'{len(new)} pours written' + (' (GND on every layer)' if ALLGND else ''))
