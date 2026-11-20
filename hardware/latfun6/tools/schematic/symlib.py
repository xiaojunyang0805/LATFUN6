"""Symbol lookup per instance: instance Device attr -> device 'Symbol' attr -> symbol document -> PART."""
import sqlite3, gzip, base64, json, collections, os
DB = 'file:' + os.environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj') + '?mode=ro'
con = sqlite3.connect(DB, uri=True)
def _dec(ds): return [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8', 'replace').splitlines() if l.strip()]
DEVSYM = {d: v for k, v, d in con.execute("select key,value,device_uuid from attributes") if k == 'Symbol'}
SYMS = {}   # symbol uuid -> {part: {'bbox':..., 'pins':[(num,name,x,y,rot)]}}
for uuid, ds, dt in con.execute("select uuid,dataStr,docType from components"):
    if dt != 2: continue
    try: L = _dec(ds)
    except Exception: continue
    parts = {}; cur = None; pins = {}; at = collections.defaultdict(dict); order = []
    for l in L:
        if l[0] == 'PART': cur = l[1]; parts[cur] = {'bbox': l[2]['BBOX'], 'pins': []}
        elif l[0] == 'PIN' and cur: pins[l[1]] = (cur, l[4], l[5], l[7]); order.append(l[1])
        elif l[0] == 'ATTR' and l[2] in pins: at[l[2]][l[3]] = l[4]
    for pid in order:
        c, x, y, r = pins[pid]; parts[c]['pins'].append((at[pid].get('NUMBER'), at[pid].get('NAME'), x, y, r))
    SYMS[uuid] = parts
BYPART = collections.defaultdict(list)
for su, parts in SYMS.items():
    for p in parts: BYPART[p].append(su)
def lookup(device_uuid, part, inst_symbol=None):
    su = inst_symbol or DEVSYM.get(device_uuid)
    if su in SYMS and part in SYMS[su]: return SYMS[su][part]
    c = BYPART.get(part, [])
    return SYMS[c[0]][part] if c else {'bbox': [0, 0, 0, 0], 'pins': []}
def page(title):
    L = _dec(con.execute("select dataStr from documents where title=?", (title,)).fetchone()[0])
    comps = {l[1]: l for l in L if l[0] == 'COMPONENT' and l[2]}
    a = collections.defaultdict(dict)
    for l in L:
        if l[0] == 'ATTR' and l[2] in comps: a[l[2]][l[3]] = l[4]
    return L, comps, a
