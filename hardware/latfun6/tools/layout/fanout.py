"""LATFUN6 BGA fan-out (layout worknote W5b): dogbone via + top stub for U5 (BG381) and U30 (DDR3L FBGA-96).
Method after the SmartPrint reference (pcbc_fanout.py), checked with eprj_core's exact shapes:
  U5 : ring 0-1 SIGNAL balls get no via (they escape on TOP between the outer balls, SERDES included);
       ring 0 power/GND: via straight out, 0.8 mm beyond the ball (in line, never in an escape gap);
       ring 1 power/GND: inward diagonal; ring >= 2: outward diagonal (alternatives if the site is taken).
  U30: every connected ball: diagonal, outward in x per column group, outward in y per half.
Via 0.40/0.20 mm (rule BGA_VIA). Stub 0.10 mm (signal) / 0.15 mm (power, GND).
    python fanout.py [SRC] [--out CAND]     plan + checks; writes a candidate copy only with --out"""
import sys, os, math, json, collections
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', '')))
import eprj_core as ec

SRC = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else os.environ.get('EPRJ', __import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj'))
OUT = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
MIL = 0.0254
mm = lambda v: v / MIL
DIA, HOLE = mm(0.40), mm(0.20)
W_SIG, W_PWR, W_RAIL = mm(0.10), mm(0.15), mm(0.25)
# nets in net class PWR (rule PWR: min 0.25 mm) get 0.25 mm stubs; GND and VREF/bead-fed rails 0.15 mm
PWRCLASS = {'12V_SLOT', '12V_OR', '5V_12', '5V_SYS', '5V_HDMI', 'VBUS', 'VBUS_F', 'USB2_VBUS', 'JACK_RAW', 'SLOT_3V3',
            '3V3_PRE', '3V3', '1V2_PRE', '1V2', '1V35_PRE', '1V35', '1V8', '1V2_SER', '2V5_PRE', '2V5', 'VCCAUX',
            'VCCAUXA', 'SW_3V3', 'SW_1V2', 'SW_1V35', 'SW_1V8', 'SW_5V'}
B = ec.Board(SRC)
R = B.rules
CLR = R.copper
TT = R.track_track
POWER = {'GND', '1V2', '1V35', '3V3', 'VCCAUX', 'VCCAUXA', 'VCCA_1V2', 'VCCHTX_1V2', 'VCCHRX_1V2', '1V2_SER',
         'DDR_VREFCA', 'DDR_VREFDQ', 'FPGA_VREF6', 'FPGA_VREF7'}
PITCH = 31.4961


def cluster(vals, tol=2.0):
    out = []
    for v in sorted(vals):
        if not out or v - out[-1][-1] > tol:
            out.append([v])
        else:
            out[-1].append(v)
    return [sum(g) / len(g) for g in out]


def comp(d):
    return next(c for c in B.comp if B.des[c] == d)


def fan(d, want):
    cid = comp(d)
    c = B.comp[cid]
    x0, y0, rot, bot = c[4], c[5], (c[6] or 0), c[3] == 2
    F = [a for a in B.P.footprints[B.attr[cid]['Footprint']] if a[0] == 'PAD']
    XS, YS = cluster([a[6] for a in F]), cluster([a[7] for a in F])
    gi = lambda v, S: int(round((v - S[0]) / PITCH))
    for S in (XS, YS):
        assert all(abs((v - S[0]) / PITCH - round((v - S[0]) / PITCH)) < 0.02 for v in S), (d, 'not on 0.8 mm grid')
    NX, NY = gi(XS[-1], XS), gi(YS[-1], YS)
    net = {p.num: p.net for p in B.pads if p.des == d}
    T = lambda u, v: ec.Board._place(('c', u, v, 0), x0, y0, rot, bot)[1:3]
    ringf = lambda i, j: min(i, j, NX - i, NY - j)
    out, used = [], set()
    for a in sorted(F, key=lambda a: -ringf(gi(a[6], XS), gi(a[7], YS))):   # inner rings choose first
        n = net.get(str(a[5]))
        if not n:
            continue
        i, j = gi(a[6], XS), gi(a[7], YS)
        cands = want(i, j, NX, NY, n)
        if cands is None:
            continue
        pick = next(((su, sv) for su, sv in cands if (i * 2 + su, j * 2 + sv) not in used), None)
        assert pick, ('no free site', d, a[5])
        su, sv = pick
        used.add((i * 2 + su, j * 2 + sv))
        bx, by = T(a[6], a[7])
        vx, vy = T(a[6] + su * PITCH / 2, a[7] + sv * PITCH / 2)
        out.append(dict(d=d, num=str(a[5]), net=n, ball=(bx, by), via=(vx, vy),
                        w=W_RAIL if n in PWRCLASS else (W_PWR if n in POWER else W_SIG), ring=ringf(i, j)))
    return out


def u5_want(i, j, NX, NY, n):
    ring = min(i, j, NX - i, NY - j)
    su = 1 if i * 2 >= NX else -1
    sv = 1 if j * 2 >= NY else -1
    if ring <= 1 and n not in POWER:
        return None
    if ring == 0:
        ex = -2 if i == 0 else (2 if i == NX else 0)
        ey = -2 if j == 0 else (2 if j == NY else 0)
        return [(ex // 2, ey // 2)] if ex and ey else [(ex, ey)]
    if ring == 1:
        return [(-su, -sv), (su if i in (1, NX - 1) else -su, -sv if i in (1, NX - 1) else sv)]
    return [(su, sv), (-su, sv), (su, -sv), (-su, -sv)]


def u30_want(i, j, NX, NY, n):
    ox = -1 if i * 2 < NX else 1
    oy = 1 if j * 2 >= NY else -1
    return [(ox, oy), (ox, -oy)]


FAN = fan('U5', u5_want) + fan('U30', u30_want)
cnt = collections.Counter(f['d'] for f in FAN)
L = [math.dist(f['ball'], f['via']) * MIL for f in FAN]
print('fan-outs', dict(cnt), '| stub %.3f..%.3f mm' % (min(L), max(L)))
assert min(L) > 0.5

V = [('c', f['via'][0], f['via'][1], DIA / 2) for f in FAN]
S = [('k', f['ball'][0], f['ball'][1], f['via'][0], f['via'][1], f['w'] / 2) for f in FAN]
pads = list(B.pads)
grid = ec.Grid(60.0)
for k, p in enumerate(pads):
    grid.add(k, ec.bbox(p.shape))
viol = []
bottom_hits = collections.defaultdict(list)
minv = 1e9
for k, f in enumerate(FAN):
    tag = f['d'] + '.' + f['num']
    for q in grid.near(ec.bbox(V[k]), CLR + 1):
        p = pads[q]
        if p.net == f['net']:
            continue
        g = ec.gap(V[k], p.shape)
        minv = min(minv, g)
        if g < CLR:
            if p.layers == frozenset({2}):
                bottom_hits[p.des].append(round(g * MIL, 3))
            else:
                viol.append(('via-pad', tag, p.des + '.' + p.num, round(g * MIL, 3)))
        if p.hole is not None and p.hole[-1] > 1.0 and ec.gap(('c', f['via'][0], f['via'][1], HOLE / 2), p.hole) < R.hole_hole:
            viol.append(('hole-hole', tag, p.des, 0))
    for q in grid.near(ec.bbox(S[k]), CLR + 1):
        p = pads[q]
        if p.net == f['net'] or 1 not in p.layers:
            continue
        g = ec.gap(S[k], p.shape)
        if g < CLR:
            viol.append(('stub-pad', tag, p.des + '.' + p.num, round(g * MIL, 3)))
vg = ec.Grid(40.0)
for k in range(len(FAN)):
    vg.add(k, ec.bbox(S[k]))
    vg.add(k, ec.bbox(V[k]))
for k, f in enumerate(FAN):
    for m in set(vg.near(ec.bbox(S[k]), CLR + 1)) | set(vg.near(ec.bbox(V[k]), CLR + 1)):
        if m <= k or FAN[m]['net'] == f['net']:
            continue
        for A_, nA in ((V[k], 'via'), (S[k], 'stub')):
            for B_, nB in ((V[m], 'via'), (S[m], 'stub')):
                g = ec.gap(A_, B_)
                need = TT if (nA == nB == 'stub') else CLR
                if g < need:
                    viol.append((nA + '-' + nB, f['d'] + '.' + f['num'], FAN[m]['d'] + '.' + FAN[m]['num'], round(g * MIL, 3)))
print('violations (top copper / vias):', len(viol), viol[:10])
print('min via-to-foreign-pad gap %.3f mm' % (minv * MIL))
print('bottom-side parts whose pads a via hits:', len(bottom_hits), sorted(bottom_hits))
json.dump({'fan': FAN, 'bottom_hits': dict(bottom_hits)}, open('fanout_plan.json', 'w'))

if OUT:
    assert not viol, viol[:5]
    P = ec.Project(SRC)
    lines = P.text.split('\n')
    have = [l for l in lines if l.startswith(('["LINE",', '["VIA",'))]
    cu = [l for l in have if l.startswith('["VIA",') or json.loads(l)[4] in (1, 2, 15, 16, 17, 18)]
    assert not cu, ('board already has copper tracks/vias', len(cu))
    nid = P.id_alloc('e9')
    J = lambda a: json.dumps(a, separators=(',', ':'), ensure_ascii=False)
    r4 = lambda v: round(v, 4)
    new = []
    for f in FAN:
        (bx, by), (vx, vy) = f['ball'], f['via']
        new.append(J(['LINE', nid(), 0, f['net'], 1, r4(bx), r4(by), r4(vx), r4(vy), r4(f['w']), 0]))
        new.append(J(['VIA', nid(), 0, f['net'], '', r4(vx), r4(vy), r4(HOLE), r4(DIA), 0, None, None, 0, []]))
    lines = ec.insert_after_last(lines, new, ('COMPONENT', 'ATTR', 'PAD_NET', 'LINE', 'VIA'))
    ec.make_candidate(P, '\n'.join(lines), OUT)
    print('candidate', OUT, len(new) // 2, 'vias + stubs')
