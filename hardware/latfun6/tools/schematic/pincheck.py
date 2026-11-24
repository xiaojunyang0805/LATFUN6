import json,sys,importlib,symlib
page=sys.argv[1]; nm=importlib.import_module(sys.argv[2])
L,C,A=symlib.page(page); P=json.load(open(f'pins_{page}.json'))
pinpos={}
for d,v in P.items():
    for n,name,x,y,_ in v['pins']: pinpos.setdefault((round(x,1),round(y,1)),[]).append((d,n,name))
def planned(d,n,name):
    if d in nm.P2: return nm.P2[d][int(n)-1] if n in ('1','2') else None
    m=nm.BYNAME.get(d,{}); return m.get(name,m.get(n))
net={l[2]:l[4] for l in L if l[0]=='ATTR' and l[3]=='NET'}
W=[l for l in L if l[0]=='WIRE']; bad=[]; nopin=[]; touched=set()
for l in W:
    for s in l[2]:
        hits=[h for e in ((round(s[0],1),round(s[1],1)),(round(s[2],1),round(s[3],1))) for h in pinpos.get(e,[])]
        if not hits: nopin.append((l[1],net.get(l[1]),s)); continue
        for d,n,name in hits:
            touched.add((d,n))
            if planned(d,n,name)!=net.get(l[1]): bad.append((l[1],net.get(l[1]),d,n,name,planned(d,n,name)))
unwired=[(d,n,name) for d,v in P.items() for n,name,*_ in v['pins'] if planned(d,n,name) and (d,n) not in touched]
print(page,'wires',len(W),'| wires touching no pin',len(nopin),nopin[:5],'| net mismatches',len(bad),bad[:8],'| mapped pins without wire',len(unwired),unwired[:10])
