import sqlite3,gzip,base64,json,collections,sys
page=sys.argv[1] if len(sys.argv)>1 else 'p1'
con=sqlite3.connect('file:'+__import__('os').environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro',uri=True)
dec=lambda ds: [json.loads(l) for l in gzip.decompress(base64.b64decode(ds[6:])).decode('utf-8').splitlines() if l.strip()]
u,ds=con.execute("select updated_at,dataStr from documents where title=?",(page,)).fetchone(); L=dec(ds)
comps={l[1]:l for l in L if l[0]=='COMPONENT' and l[2]}
a=collections.defaultdict(dict)
for l in L:
    if l[0]=='ATTR' and l[2] in comps: a[l[2]][l[3]]=l[4]
SKIP={'Reuse Block','Group ID','Channel ID','Name','Designator','Device','Unique ID','Symbol'}
dmg=[a[c].get('Designator') for c in comps if any(v=='' and k not in SKIP for k,v in a[c].items()) or ('Supplier Part' in a[c] and a[c].get('Designator')!='J12')]
extra=collections.Counter(k for c in comps for k,v in a[c].items() if k not in SKIP and v!='')
print(u,page,'parts',len(comps),'still damaged',len(dmg),dmg[:10],'| non-blank overrides',extra.most_common(6))
