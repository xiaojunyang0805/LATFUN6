"""Absolute pin positions for every part on a page (PAGE env, default p1).
Output pins.json: {designator: {"id": eN, "part": name, "x","y","rot", "pins": [[num, name, ax, ay, outdir_deg]]}}
Symbol PIN record: ['PIN', id, ?, ?, x, y, length, rot, ...]; (x,y) is the connection end; the pin body
extends from there in direction rot (0 => +x). Outward direction = rot+180.
Component rotation is applied CCW in the creation (y-up) frame — verified against sch_get_component_pins."""
import sqlite3, gzip, base64, json, os, collections, math

PAGE = os.environ.get('PAGE', 'p1')
import symlib
L, comps, a = symlib.page(PAGE)
out = {}
for cid, c in comps.items():
    part, X, Y, rot = c[2], c[3], c[4], c[5]
    mirror = bool(c[6]) if len(c) > 6 and isinstance(c[6], (bool, int)) else False
    ps = []
    for num, name, px, py, pr in symlib.lookup(a[cid].get('Device'), part, a[cid].get('Symbol'))['pins']:
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
