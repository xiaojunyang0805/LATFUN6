"""Absolute pin positions for every part on a page (PAGE env, default p1).
Output pins.json: {designator: {"id": eN, "part": name, "x","y","rot", "pins": [[num, name, ax, ay, outdir_deg]]}}
Symbol PIN record: ['PIN', id, ?, ?, x, y, length, rot, ...]; (x,y) is the connection end; the pin body
extends from there in direction rot (0 => +x). Outward direction = rot+180.
Component rotation is applied CCW in the creation (y-up) frame — verified against sch_get_component_pins."""
import sqlite3, gzip, base64, json, os, collections, math

PAGE = os.environ.get('PAGE', 'p1')
con = sqlite3.connect('file:'+__import__('os').environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro', uri=True)
dec = lambda ds: [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8', 'replace').splitlines() if l.strip()]
sympins = {}
for uuid, ds, dt in con.execute("select uuid,dataStr,docType from components"):
    if dt != 2: continue
    try: L = dec(ds)
    except Exception: continue
    cur = None; pins = {}; attrs = collections.defaultdict(dict); order = []
    for l in L:
        if l[0] == 'PART':
            cur = l[1]; sympins.setdefault(cur, [])
        elif l[0] == 'PIN' and cur:
            pins[l[1]] = (cur, l[4], l[5], l[6], l[7]); order.append(l[1])
        elif l[0] == 'ATTR' and l[2] in pins:
            attrs[l[2]][l[3]] = l[4]
    for pid in order:
        part, x, y, ln, r = pins[pid]
        sympins[part].append((attrs[pid].get('NUMBER'), attrs[pid].get('NAME'), x, y, r))

L = dec(con.execute("select dataStr from documents where title=?", (PAGE,)).fetchone()[0])
comps = {l[1]: l for l in L if l[0] == 'COMPONENT' and l[2]}
a = collections.defaultdict(dict)
for l in L:
    if l[0] == 'ATTR' and l[2] in comps: a[l[2]][l[3]] = l[4]
out = {}
for cid, c in comps.items():
    part, X, Y, rot = c[2], c[3], c[4], c[5]
    mirror = bool(c[6]) if len(c) > 6 and isinstance(c[6], (bool, int)) else False
    ps = []
    for num, name, px, py, pr in sympins.get(part, []):
        if mirror: px, pr = -px, (180 - pr) % 360
        t = math.radians(rot)
        ax = X + px * math.cos(t) - py * math.sin(t)
        ay = Y + px * math.sin(t) + py * math.cos(t)
        outdir = (pr + 180 + rot) % 360
        ps.append([num, name, round(ax, 2), round(ay, 2), outdir])
    d = a[cid].get('Designator')
    key = d if d not in out else f"{d}#{cid}"
    out[key] = {'id': cid, 'part': part, 'x': X, 'y': Y, 'rot': rot, 'pins': ps}
json.dump(out, open(f'pins_{PAGE}.json', 'w'))
print(PAGE, len(out), 'parts;', sum(len(v['pins']) for v in out.values()), 'pins;', 'no-symbol:', [k for k, v in out.items() if not v['pins']][:10])
