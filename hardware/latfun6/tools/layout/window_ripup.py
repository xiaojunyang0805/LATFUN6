"""Rip up the copper of chosen nets inside a window (shove step of pcb-layout W6b), keeping each net's ball / pad
escapes: vias within --keep mm of one of its own pads, and short stubs (<= --keep + 0.3 mm) joining such a pad to such a
via. Copper partly outside the window is cut where it crosses the window edge? No: a segment with either end inside the
window is removed; route_rest re-joins from the remaining track ends.
    python window_ripup.py IN.eprj OUT.eprj NET[,NET...] x0,y0,x1,y1 [--keep 0.8]"""
import sys, os, json, math
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst, nets = args[0], args[1], set(args[2].split(','))
x0, y0, x1, y1 = (float(v) for v in args[3].split(','))
KEEP = float(opt('--keep', 0.8))
P = ec.Project(src); lines = P.text.split('\n')
W = lfr.World(src)
pads = {}
for k, e in W.pad.items():
    if e['net'] in nets:
        pads.setdefault(e['net'], []).append(lfr.shape_center(e['s']))
inw = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
near_pad = lambda n, p, r: any(math.hypot(p[0] - q[0], p[1] - q[1]) <= r for q in pads.get(n, []))
drop = set(); keepv = []
for l in lines:
    if l.startswith('["VIA"'):
        a = json.loads(l)
        if a[3] in nets:
            c = lfr.to_mm(a[5], a[6])
            if inw(c):
                if near_pad(a[3], c, KEEP):
                    keepv.append((a[3], c))
                else:
                    drop.add(a[1])
for l in lines:
    if l.startswith('["LINE"'):
        a = json.loads(l)
        if a[3] not in nets:
            continue
        p, q = lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])
        if not (inw(p) or inw(q)):
            continue
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        stub = L <= KEEP + 0.3 and any(
            (near_pad(a[3], u, 0.05) or any(n == a[3] and math.hypot(u[0] - c[0], u[1] - c[1]) < 0.02 for n, c in keepv)) and
            (near_pad(a[3], v, 0.05) or any(n == a[3] and math.hypot(v[0] - c[0], v[1] - c[1]) < 0.02 for n, c in keepv))
            for u, v in ((p, q),))
        if not stub:
            drop.add(a[1])
out = [l for l in lines if not ((l.startswith('["LINE"') or l.startswith('["VIA"')) and json.loads(l)[1] in drop)]
ec.make_candidate(P, '\n'.join(out), dst)
print(f'ripped {len(drop)} records of {len(nets)} nets in window; kept {len(keepv)} escape vias')
