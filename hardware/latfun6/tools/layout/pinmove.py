"""Move U5 nets to unused balls and drop nets from U5 (user decision 2026-11-23: re-pin to free balls, drop test-only
nets), on schematic page P2 AND the PCB in one copy of the project:
  schematic: the pin's wire stub + NET label is removed (old ball) / created at the new ball's pin end (part position +
             symbol pin offset, 20 mil stub to the left, label at its midpoint, as the existing stubs);
  PCB:       PAD_NET of U5 old ball -> '', new ball -> net; the net's copper within --fan mm of U5's ball field is
             removed (old fan-out); for dropped nets ALL their copper is removed.
    python pinmove.py IN.eprj OUT.eprj --move NET:OLD:NEW[,..] --drop NET:BALL[,..]"""
import sys, os, json, sqlite3, shutil
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import eprj_core as ec
import lfr

args = sys.argv[1:]
opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
src, dst = args[0], args[1]
MOVES = [m.split(':') for m in (opt('--move') or '').split(',') if m]
DROPS = [d.split(':') for d in (opt('--drop') or '').split(',') if d]
FAN = float(opt('--fan', 1.0))
J = lambda r: json.dumps(r, separators=(',', ':'), ensure_ascii=False)
shutil.copy2(src, dst)
con = sqlite3.connect(dst)
# ---- symbol pin offsets
sym = [d for t, d in con.execute("select display_title, dataStr from components") if t == 'LFE5UM5G-45F-8BG381C'][0]
part = None; pins = {}; num = {}
for l in ec.decode(sym).split('\n'):
    a = json.loads(l)
    if a[0] == 'PART':
        part = a[1]
    elif a[0] == 'PIN':
        pins[a[1]] = (part, a[4], a[5])
    elif a[0] == 'ATTR' and a[3] == 'NUMBER' and a[2] in pins:
        num[a[4]] = pins[a[2]]
uid, st = con.execute("select uuid, dataStr from documents where docType=1 and display_title='P2'").fetchone()
L = ec.decode(st).split('\n')
comp = {json.loads(l)[2]: json.loads(l) for l in L if l.startswith('["COMPONENT"')}


def pin_end(ball):
    pt, px, py = num[ball]
    c = comp[pt]
    return c[3] + px, c[4] + py


wires = {json.loads(l)[1]: (i, json.loads(l)) for i, l in enumerate(L) if l.startswith('["WIRE"')}


def stub_at(ball):
    x, y = pin_end(ball)
    for wid, (i, w) in wires.items():
        s = w[2][0]
        if (s[2], s[3]) == (x, y) or (s[0], s[1]) == (x, y):
            lab = [k for k, l in enumerate(L) if l.startswith('["ATTR"') and json.loads(l)[2] == wid]
            return i, lab
    return None, []


drop_lines = set(); new = []
ids = [int(json.loads(l)[1][1:]) for l in L if l.startswith('[') and isinstance(json.loads(l)[1], str)
       and json.loads(l)[1][:1] == 'e' and json.loads(l)[1][1:].isdigit()]
nxt = [max(ids) + 1]


def nid():
    nxt[0] += 1
    return f'e{nxt[0] - 1}'


for net, old, *rest in [(m[0], m[1], m[2]) for m in MOVES] + [(d[0], d[1]) for d in DROPS]:
    i, lab = stub_at(old)
    assert i is not None and lab, (net, old, 'no stub at old ball')
    assert json.loads(L[lab[0]])[4] == net, (net, old, json.loads(L[lab[0]])[4])
    drop_lines |= {i, *lab}
    if rest:
        newb = rest[0]
        assert stub_at(newb)[0] is None, (newb, 'already has a stub')
        x, y = pin_end(newb)
        w = nid(); a = nid()
        new += [J(['WIRE', w, [[x - 20, y, x, y]], 'st9', 0]), J(['ATTR', a, w, 'NET', net, 0, 1, x - 10, y, 0, 'st4', 0])]
        print(f'P2: {net} stub {old} -> {newb} at ({x},{y})')
    else:
        print(f'P2: {net} stub at {old} removed')
L2 = [l for k, l in enumerate(L) if k not in drop_lines]
k = max(i for i, l in enumerate(L2) if l.startswith('["ATTR"') or l.startswith('["WIRE"'))
L2[k + 1:k + 1] = new
nt = '\n'.join(L2); assert ec.decode(ec.encode(nt)) == nt
con.execute("update documents set dataStr=? where uuid=?", (ec.encode(nt), uid))
con.commit(); con.close()

# ---- PCB
P = ec.Project(dst); L = P.text.split('\n')
des = {}
for l in L:
    if l.startswith('["ATTR"'):
        r = json.loads(l)
        if len(r) > 8 and r[7] == 'Designator':
            des[r[3]] = r[8]
want = {}
for net, old, newb in MOVES:
    want[old] = ('', net); want[newb] = (net, '')
for net, old in DROPS:
    want[old] = ('', net)
for i, l in enumerate(L):
    if l.startswith('["PAD_NET"'):
        r = json.loads(l)
        if des.get(r[1]) == 'U5' and r[2] in want:
            to, frm = want[r[2]]
            assert r[3] == frm, (r, frm)
            r[3] = to; L[i] = J(r); print(f'PCB U5.{r[2]}: {frm!r} -> {to!r}')
W = lfr.World(src); W.add_field('U5'); f = W.fields[0]
box = (f[0] - FAN, f[1] - FAN, f[2] + FAN, f[3] + FAN)
inb = lambda p: box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]
moved = {m[0] for m in MOVES}; dropped = {d[0] for d in DROPS}
out = []; n = 0
for l in L:
    if l.startswith(('["LINE"', '["VIA"')):
        r = json.loads(l)
        if r[3] in dropped:
            n += 1; continue
        if r[3] in moved:
            pts = [lfr.to_mm(r[5], r[6])] + ([lfr.to_mm(r[7], r[8])] if r[0] == 'LINE' else [])
            if any(inb(p) for p in pts):
                n += 1; continue
    out.append(l)
ec.make_candidate(P, '\n'.join(out), dst + '.tmp')
shutil.move(dst + '.tmp', dst)
print(f'removed {n} copper records; written {dst}')
