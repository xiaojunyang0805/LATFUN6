"""User decision 2026-11-21: swap the SFP and SMA lanes inside DCU1 (D1CH0 <-> D1CH1), so the U5 SERDES corner
routes on two layers (layout worknote W5b). Both lanes stay on REFCLK_D1; PCIe (DCU0 CH0) is untouched.
Changes, in ONE sqlite transaction (EDA must be closed; backup first; read-back verified):
  schematic page P2: the NET attribute of the 8 pin-stub wires at U5 (each label appears exactly once on P2)
  PCB: U5's PAD_NET rows for W13/W14/Y14/Y15/W17/W18/Y16/Y17
    python swap_sfp_sma.py [EPRJ]            dry run;  --write to apply"""
import sys, os, json, sqlite3, shutil, time
sys.path.insert(0, os.environ.get('PCB_LAYOUT_SCRIPTS', os.path.expanduser('~/.claude/skills/pcb-layout/scripts')))
import eprj_core as ec

SRC = next((a for a in sys.argv[1:] if not a.startswith('--')), 'hardware/EDA/Latfun6.eprj')
WRITE = '--write' in sys.argv
PAIRS = [('SFP_HDTX_P', 'SMA_HDTX_P'), ('SFP_HDTX_N', 'SMA_HDTX_N'), ('SFP_HDRX_P', 'SMA_HDRX_P'), ('SFP_HDRX_N', 'SMA_HDRX_N')]
SW = {}
for a, b in PAIRS:
    SW[a], SW[b] = b, a
J = lambda r: json.dumps(r, separators=(',', ':'), ensure_ascii=False)

con = sqlite3.connect(SRC)
docs = con.execute("select uuid, docType, display_title, dataStr from documents").fetchall()
p2 = [d for d in docs if d[1] == 1 and d[2] == 'P2']
pcb = [d for d in docs if d[1] == 3]
assert len(p2) == 1 and len(pcb) == 1, (len(p2), len(pcb))
out = {}

# ---- schematic P2
t = ec.decode(p2[0][3]); L = t.split('\n')
wires = {json.loads(l)[1] for l in L if l.startswith('["WIRE"')}
hits = {}
for i, l in enumerate(L):
    if l.startswith('["ATTR"'):
        r = json.loads(l)
        if r[3] == 'NET' and r[4] in SW:
            assert r[2] in wires, ('NET attr not on a wire', r)
            hits.setdefault(r[4], []).append(i)
assert sorted(hits) == sorted(SW) and all(len(v) == 1 for v in hits.values()), hits
for n, (i,) in hits.items():
    r = json.loads(L[i]); r[4] = SW[n]; L[i] = J(r)
    print(f'P2  wire {r[2]}: {n} -> {SW[n]}')
nt = '\n'.join(L); assert ec.decode(ec.encode(nt)) == nt
out[p2[0][0]] = nt

# ---- PCB
t = ec.decode(pcb[0][3]); L = t.split('\n')
des = {}
for l in L:
    if l.startswith('["ATTR"'):
        r = json.loads(l)
        if len(r) > 8 and r[7] == 'Designator':
            des[r[3]] = r[8]
u5 = next(k for k, v in des.items() if v == 'U5')
n_pad = 0
for i, l in enumerate(L):
    if l.startswith('["PAD_NET"'):
        r = json.loads(l)
        if r[1] == u5 and r[3] in SW:
            print(f'PCB U5.{r[2]}: {r[3]} -> {SW[r[3]]}')
            r[3] = SW[r[3]]; L[i] = J(r); n_pad += 1
assert n_pad == 8, n_pad
# no copper on these pads yet (ring 0/1 signals: no fan-out); refuse if any track/via carries the nets
for l in L:
    if l.startswith(('["LINE"', '["VIA"')):
        assert json.loads(l)[3] not in SW, ('routed copper on a swapped net', l[:80])
nt = '\n'.join(L); assert ec.decode(ec.encode(nt)) == nt
out[pcb[0][0]] = nt
con.close()

if not WRITE:
    print('dry run: nothing written'); sys.exit()
ec.assert_eda_closed(os.path.abspath(SRC))
bak = f'{SRC}.bak_swap_sfp_sma_{time.strftime("%Y%m%d-%H%M%S")}'
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
