"""Swap net names on one schematic page (wire NET labels) and on chosen PCB parts' pad nets, in ONE transaction.
EDA must be closed; backup first; read-back verified. Each swapped label must appear exactly once on the page.
    python netswap.py EPRJ PAGE DES1,DES2,... A=B[,C=D...] [--write]
Used 2026-11-21 (user decision): SMA roles swapped, J17/J18 = TX, J15/J16 = RX:
    python netswap.py hardware/EDA/Latfun6.eprj P1 C340,C341,C342,C343,J15,J16,J17,J18 \\
        SMA_HDTX_P=SMA_HDRX_P,SMA_HDTX_N=SMA_HDRX_N,SMA_TX_P=SMA_RX_P,SMA_TX_N=SMA_RX_N --write"""
import sys, os, json, sqlite3, shutil, time
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
import eprj_core as ec

a = [x for x in sys.argv[1:] if not x.startswith('--')]
SRC, PAGE, DES, PAIRS = a[0], a[1], set(a[2].split(',')), [p.split('=') for p in a[3].split(',')]
WRITE = '--write' in sys.argv
SW = {}
for x, y in PAIRS:
    SW[x], SW[y] = y, x
J = lambda r: json.dumps(r, separators=(',', ':'), ensure_ascii=False)

con = sqlite3.connect(SRC)
docs = con.execute("select uuid, docType, display_title, dataStr from documents").fetchall()
pg = [d for d in docs if d[1] == 1 and d[2] == PAGE]
pcb = [d for d in docs if d[1] == 3]
assert len(pg) == 1 and len(pcb) == 1
out = {}
# every other schematic page must not carry these labels near the swapped parts: report where each name appears
for d in docs:
    if d[1] == 1:
        t = ec.decode(d[3])
        n = {k: sum(1 for l in t.split('\n') if l.startswith('["ATTR"') and json.loads(l)[3] == 'NET' and json.loads(l)[4] == k) for k in SW}
        print(f'page {d[2]}: label counts {n}')

t = ec.decode(pg[0][3]); L = t.split('\n')
wires = {json.loads(l)[1] for l in L if l.startswith('["WIRE"')}
hits = {}
for i, l in enumerate(L):
    if l.startswith('["ATTR"'):
        r = json.loads(l)
        if r[3] == 'NET' and r[4] in SW:
            assert r[2] in wires, ('NET attr not on a wire', r)
            hits.setdefault(r[4], []).append(i)
# a label may repeat on the page only if every PCB pad of that net belongs to the swapped parts (pure rename)
_t = ec.decode(pcb[0][3]).split('\n')
_des = {json.loads(l)[3]: json.loads(l)[8] for l in _t if l.startswith('["ATTR"') and len(json.loads(l)) > 8 and json.loads(l)[7] == 'Designator'}
_owners = {}
for l in _t:
    if l.startswith('["PAD_NET"'):
        r = json.loads(l); _owners.setdefault(r[3], set()).add(_des.get(r[1]))
assert sorted(hits) == sorted(SW), hits
for n, v in hits.items():
    assert len(v) == 1 or _owners.get(n, set()) <= DES, ('label repeats and net reaches other parts', n, _owners.get(n))
for n, idx in hits.items():
    for i in idx:
        r = json.loads(L[i]); r[4] = SW[n]; L[i] = J(r)
        print(f'{PAGE} wire {r[2]}: {n} -> {SW[n]}')
nt = '\n'.join(L); assert ec.decode(ec.encode(nt)) == nt
out[pg[0][0]] = nt

t = ec.decode(pcb[0][3]); L = t.split('\n')
des = {}
for l in L:
    if l.startswith('["ATTR"'):
        r = json.loads(l)
        if len(r) > 8 and r[7] == 'Designator':
            des[r[3]] = r[8]
n_pad = 0
for i, l in enumerate(L):
    if l.startswith('["PAD_NET"'):
        r = json.loads(l)
        if r[3] in SW:
            if des.get(r[1]) in DES:
                print(f'PCB {des[r[1]]}.{r[2]}: {r[3]} -> {SW[r[3]]}')
                r[3] = SW[r[3]]; L[i] = J(r); n_pad += 1
            else:
                print(f'PCB {des.get(r[1])}.{r[2]}: {r[3]} kept')
if '--swap-copper' in sys.argv:
    # copper of swapped nets may only be the parts' own fan-out (stub + via next to their pads): renamed with the swap
    Bd = ec.Board(SRC)
    box = [1e9, 1e9, -1e9, -1e9]
    for p in Bd.pads:
        if p.des in DES:
            b = ec.bbox(p.shape); box = [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
    m = 1.2 / 0.0254
    n_cu = 0
    for i, l in enumerate(L):
        if l.startswith(('["LINE"', '["VIA"')):
            r = json.loads(l)
            if r[3] in SW:
                xy = [(r[5], r[6])] + ([(r[7], r[8])] if r[0] == 'LINE' else [])
                assert all(box[0] - m <= x <= box[2] + m and box[1] - m <= y <= box[3] + m for x, y in xy), \
                    ('copper of a swapped net outside the parts (routed?)', l[:80])
                r[3] = SW[r[3]]; L[i] = J(r); n_cu += 1
    print('fan-out copper renamed:', n_cu)
for l in L:
    if l.startswith(('["LINE"', '["VIA"')):
        assert json.loads(l)[3] not in SW or '--swap-copper' in sys.argv, ('routed copper on a swapped net', l[:80])
nt = '\n'.join(L); assert ec.decode(ec.encode(nt)) == nt
out[pcb[0][0]] = nt
con.close()
print('pads changed:', n_pad)
if not WRITE:
    print('dry run: nothing written'); sys.exit()
ec.assert_eda_closed(os.path.abspath(SRC))
bak = f'{SRC}.bak_netswap_{time.strftime("%Y%m%d-%H%M%S")}'
shutil.copy2(SRC, bak)
con = sqlite3.connect(SRC)
with con:
    for uid, text in out.items():
        con.execute("update documents set dataStr=? where uuid=?", (ec.encode(text), uid))
ok = con.execute('pragma integrity_check').fetchone()[0]
for uid, text in out.items():
    assert ec.decode(con.execute("select dataStr from documents where uuid=?", (uid,)).fetchone()[0]) == text
con.close()
print('written', SRC, '| backup', bak, '| integrity', ok, '| read-back identical')
