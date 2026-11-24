"""Generate 20-unit net stubs for a block from pins_<page>.json and a netmap module.
usage: python stubs.py netmap_b1 [page]   -> stubs_<netmap>.json  (wire lines in READBACK coords: y = -y_up)
Checks: every non-NC pin mapped; no stub end/segment touches a pin or stub of another net."""
import json, sys, importlib
mod = importlib.import_module(sys.argv[1]); page = sys.argv[2] if len(sys.argv) > 2 else 'p1'
P = json.load(open(f'pins_{page}.json'))
L = 20
D = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}   # y-up frame
stubs, unmapped, extra = [], [], []
for des in list(mod.P2) + list(mod.BYNAME):
    if des not in P: extra.append(des); continue
    for num, name, x, y, od in P[des]['pins']:
        if des in mod.P2:
            net = mod.P2[des][int(num) - 1] if num in ('1', '2') else None
        else:
            m = mod.BYNAME[des]; net = m.get(name, m.get(num))
        if net is None:
            if name not in mod.NC.get(des, []): unmapped.append((des, num, name))
            continue
        dx, dy = D[int(od) % 360]
        x2, y2 = x + dx * L, y + dy * L
        stubs.append({'des': des, 'pin': num, 'name': name, 'net': net, 'seg': [x, y, x2, y2]})
# conflicts: any stub point (either end) lying on another stub segment / pin end of a different net
allpins = [(d, n, x, y) for d, v in P.items() for n, _, x, y, _ in v['pins']]
pinnet = {(s['des'], s['pin']): s['net'] for s in stubs}
def on_seg(px, py, s):
    x1, y1, x2, y2 = s
    if min(x1, x2) - 0.5 <= px <= max(x1, x2) + 0.5 and min(y1, y2) - 0.5 <= py <= max(y1, y2) + 0.5:
        return abs((x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)) < 0.5
    return False
conf = []
for s in stubs:
    for (d, n, px, py) in allpins:          # foreign pin on my stub
        if (d, n) == (s['des'], s['pin']): continue
        if on_seg(px, py, s['seg']) and pinnet.get((d, n)) != s['net']:
            conf.append(('pin', s['des'], s['pin'], s['net'], d, n, pinnet.get((d, n))))
    for t in stubs:                          # stub ends touching other-net stubs
        if t is s or t['net'] == s['net']: continue
        for px, py in ((s['seg'][2], s['seg'][3]), (s['seg'][0], s['seg'][1])):
            if on_seg(px, py, t['seg']):
                conf.append(('stub', s['des'], s['pin'], s['net'], t['des'], t['pin'], t['net']))
# shorten conflicting stubs to 8 units and re-check
bad = {(c[1], c[2]) for c in conf}
for st in stubs:
    if (st['des'], st['pin']) in bad:
        x, y, x2, y2 = st['seg']; ux, uy = (x2 - x) / L, (y2 - y) / L
        st['seg'] = [x, y, x + ux * 8, y + uy * 8]
conf2 = []
for s_ in stubs:
    for t in stubs:
        if t is s_ or t['net'] == s_['net']: continue
        for px, py in ((s_['seg'][2], s_['seg'][3]), (s_['seg'][0], s_['seg'][1])):
            if on_seg(px, py, t['seg']): conf2.append((s_['des'], s_['pin'], t['des'], t['pin']))
    for (d, n, px, py) in allpins:
        if (d, n) != (s_['des'], s_['pin']) and on_seg(px, py, s_['seg']) and pinnet.get((d, n)) != s_['net']: conf2.append((s_['des'], d, n))
print('after shortening', len(bad), 'stubs; conflicts left', conf2)
out = [{'line': [s['seg'][0], -s['seg'][1], s['seg'][2], -s['seg'][3]], 'net': s['net'], 'des': s['des'], 'pin': s['pin']} for s in stubs]
json.dump(out, open(f'stubs_{sys.argv[1]}.json', 'w'))
nets = sorted({s['net'] for s in stubs})
print('stubs', len(stubs), 'nets', len(nets), '| unmapped', unmapped, '| not on page', extra, '| conflicts', len(conf))
for c in conf[:20]: print('  ', c)
single = [n for n in nets if sum(1 for s in stubs if s['net'] == n) == 1]
print('single-pin nets (need other block/page):', single)
