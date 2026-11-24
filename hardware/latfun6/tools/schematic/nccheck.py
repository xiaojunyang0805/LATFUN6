import os
import sqlite3,gzip,base64,json,sys
con=sqlite3.connect('file:'+os.environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro',uri=True)
for pg in sys.argv[1:]:
    L=[json.loads(l) for l in gzip.decompress(base64.b64decode(con.execute("select dataStr from documents where title=?",(pg,)).fetchone()[0][6:])).decode().splitlines() if l.strip()]
    ends=set()
    for l in L:
        if l[0]=='WIRE':
            for s in l[2]: ends|={(round(s[0]),round(s[1])),(round(s[2]),round(s[3]))}
    nc=[(round(l[7]),round(l[8])) for l in L if l[0]=='ATTR' and l[3]=='NO_CONNECT' and l[4]=='yes']
    print(pg,'NC flags',len(nc),'| flagged pins that also have a wire:',[p for p in nc if p in ends])
