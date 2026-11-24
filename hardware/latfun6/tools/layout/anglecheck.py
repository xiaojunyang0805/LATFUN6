"""Acute-angle check on a saved file: for every net and layer, every PAIR of track segments that share an endpoint
(any junction degree) -> interior angle. Lists angles < 90 deg (never allowed) and counts 90 deg joints.
    python anglecheck.py EPRJ [NET_REGEX]"""
import sys, os, re, math, collections
sys.path.insert(0, os.environ['PCB_LAYOUT_SCRIPTS']); import eprj_core as ec
B = ec.Board(sys.argv[1]); pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
M = 0.0254
S = collections.defaultdict(list)
for t in B.tracks:
    if pat and not pat.search(t.net or ''):
        continue
    a, b = (t.x1 * M, -t.y1 * M), (t.x2 * M, -t.y2 * M)
    if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-5:
        S[(t.net, t.layer)].append((a, b))
acute, right = [], 0
for (net, lay), ss in S.items():
    E = collections.defaultdict(list)
    k = lambda p: (round(p[0], 3), round(p[1], 3))
    for a, b in ss:
        E[k(a)].append((b[0] - a[0], b[1] - a[1])); E[k(b)].append((a[0] - b[0], a[1] - b[1]))
    for v, dirs in E.items():
        for i in range(len(dirs)):
            for j in range(i + 1, len(dirs)):
                u, w = dirs[i], dirs[j]
                c = (u[0] * w[0] + u[1] * w[1]) / (math.hypot(*u) * math.hypot(*w))
                ang = math.degrees(math.acos(max(-1, min(1, c))))
                if ang < 89:
                    acute.append((net, lay, v, round(ang, 1), len(dirs)))
                elif ang < 91:
                    right += 1
print(f'acute (< 90 deg): {len(acute)} | 90 deg: {right}')
for x in acute[:40]:
    print('  ', x)
