import sqlite3,gzip,base64,json,sys,collections
page=sys.argv[1]; todo=json.load(open(sys.argv[2]))
con=sqlite3.connect('file:'+__import__('os').environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro',uri=True)
dec=lambda ds: [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8','replace').splitlines() if l.strip()]
u,ds=con.execute("select updated_at,dataStr from documents where title=?",(page,)).fetchone(); L=dec(ds)
wires={l[1]:l[2] for l in L if l[0]=='WIRE'}
net={l[2]:l[4] for l in L if l[0]=='ATTR' and l[3]=='NET'}
have=collections.Counter()
for wid,segs in wires.items():
    for s in segs:
        x1,y1,x2,y2=s[:4]; k=tuple(sorted([(round(x1,2),round(y1,2)),(round(x2,2),round(y2,2))])); have[(k,net.get(wid))]+=1
missing=[];dup=0
for w in todo:
    x1,y1,x2,y2=w['line']; k=tuple(sorted([(round(x1,2),round(-y1,2)),(round(x2,2),round(-y2,2))]))
    c=have.get((k,w['net']),0)
    if c==0: missing.append(w)
    elif c>1: dup+=1
print(u,'wires in file',len(wires),'| todo',len(todo),'missing',len(missing),'duplicated',dup)
json.dump(missing,open('missing.json','w'))
