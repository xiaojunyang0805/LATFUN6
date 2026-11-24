"""Free U5's escape band (layout worknote W6b): the GND pads of parts within --band mm of the U5 field had a new via
each (gndvias.py), and those vias block every layer exactly where the FPGA's signals escape. Here each such pad is
re-joined to the NEAREST EXISTING GND via (normally a U5 fan-out via at the field edge) by a short track on the pad's
layer; its own via + stub are removed. Pads that cannot reach one keep their via.
    python perimeter_gnd.py IN.eprj OUT.eprj [--band 3.0] [--r 3.0]"""
import sys, os, math, json
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst = args[0], args[1]
BAND = float(opt('--band', 3.0)); R = float(opt('--r', 3.0))
MIL = 0.0254
P = ec.Project(src)
lines = P.text.split('\n')
W0 = lfr.World(src)
W0.add_field('U5')
fx0, fy0, fx1, fy1 = W0.fields[0]
dist_out = lambda q: max(fx0 - q[0], q[0] - fx1, fy0 - q[1], q[1] - fy1)

# GND pads in the band, and the via + stub that gndvias.py gave each of them
recs = [json.loads(l) for l in lines if l.startswith('["LINE"') or l.startswith('["VIA"')]
gvias = [(a[1], lfr.to_mm(a[5], a[6])) for a in recs if a[0] == 'VIA' and a[3] == 'GND']
gtrk = [(a[1], lfr.to_mm(a[5], a[6]), lfr.to_mm(a[7], a[8])) for a in recs if a[0] == 'LINE' and a[3] == 'GND']
pads = [(k, e) for k, e in W0.pad.items() if e['net'] == 'GND' and len(e['layers']) == 1
        and not k.startswith('U5.') and 0 < dist_out(lfr.shape_center(e['s'])) < BAND]
drop = set(); plan = []
for k, e in pads:
    c = lfr.shape_center(e['s'])
    for tid, p, q in gtrk:
        for a_, b_ in ((p, q), (q, p)):
            if lfr.shape_dist(e['s'], np.array([a_[0]]), np.array([a_[1]]))[0] <= 0.01:
                v = [vid for vid, vc in gvias if math.hypot(vc[0] - b_[0], vc[1] - b_[1]) < 0.02 and dist_out(vc) > 0]
                if v:
                    plan.append((k, e, c, tid, v[0], b_))
print(f'{len(pads)} GND pads in the {BAND} mm band, {len(plan)} with their own via + stub')
# remove those vias + stubs, then re-route each pad to the nearest remaining GND via
rm = {t for *_, t, v, b in plan} | {v for *_, t, v, b in plan}
lines2 = [l for l in lines if not ((l.startswith('["LINE"') or l.startswith('["VIA"')) and json.loads(l)[1] in rm)]
tmp = dst + '.tmp.eprj'
ec.make_candidate(P, '\n'.join(lines2), tmp)
W = lfr.World(tmp)
W.add_field('U5'); W.add_field('U30')
Rt = lfr.Router(W, log=lambda *a: None)
ok = back = 0
for k, e, c, tid, vid, vpos in plan:
    lay = next(iter(e['layers']))
    vias = [lfr.shape_center(s['s']) for s in W.sh if s['cls'] == 'via' and s['net'] == 'GND']
    cand = sorted((math.hypot(v[0] - c[0], v[1] - c[1]), v) for v in vias)
    done = False
    for d, v in cand[:8]:
        if d > R:
            break
        for w in (0.2, 0.15, 0.1):
            m = W.mark()
            r = Rt.route_net('GND', c, v, [lay], w, margin=0.8, bend=0.3, maxexp=150_000)
            if r is not None:
                Ls = sum(math.hypot(q[0] - p[0], q[1] - p[1]) for _, pts in r for p, q in zip(pts, pts[1:]))
                if Ls <= 2.0 * d + 0.4:
                    done = True; break
            W.rollback(m)
        if done:
            break
    if done:
        ok += 1
    else:                                   # keep the original via + stub
        W.add_track('GND', lay, c, vpos, 0.2); W.add_via('GND', vpos[0], vpos[1], 0.4, 0.2); back += 1
print(f're-joined {ok} pads to existing GND vias, {back} kept their own via')
p, n = lfr.write_candidate(W, dst)
os.remove(tmp)
print(f'candidate {p}: {n} records')
