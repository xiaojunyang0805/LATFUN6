import os
import sqlite3,gzip,base64,json,sys
page=sys.argv[1]; pts=[tuple(map(float,a.split(','))) for a in sys.argv[2:]]
con=sqlite3.connect('file:'+os.environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro',uri=True)
dec=lambda ds: [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8','replace').splitlines() if l.strip()]
L=dec(con.execute("select dataStr from documents where title=?",(page,)).fetchone()[0])
net={l[2]:l[4] for l in L if l[0]=='ATTR' and l[3]=='NET'}
for l in L:
    if l[0]!='WIRE': continue
    for s in l[2]:
        for (x,y) in pts:
            if (abs(s[0]-x)<.1 and abs(s[1]-y)<.1) or (abs(s[2]-x)<.1 and abs(s[3]-y)<.1): print((x,y),l[1],s[:4],net.get(l[1]))
