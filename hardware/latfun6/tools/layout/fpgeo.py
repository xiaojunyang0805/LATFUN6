"""Local footprint geometry per PCB component: pad bbox, courtyard bbox (pads U body U silk), in mil, footprint frame."""
import json,math
exec(open('brd.py').read())
from eprj_core import path_points
def local(fpu):
    F=B.P.footprints.get(fpu,[])
    pads=[];allp=[]
    for a in F:
        if a[0]=='PAD':
            s=B._pad_local_shape(a)
            if not s: continue
            if s[0]=='c': pts=[(s[1]-s[3],s[2]-s[3]),(s[1]+s[3],s[2]+s[3])]
            elif s[0]=='k': r=s[5]; pts=[(min(s[1],s[3])-r,min(s[2],s[4])-r),(max(s[1],s[3])+r,max(s[2],s[4])+r)]
            else: pts=s[1]
            pads+=pts
        elif a[0] in ('POLY','FILL') and len(a)>6 and a[4] in (3,48,13,1,2,12):   # silk top, body/outline, doc
            p=a[6] if a[0]=='POLY' else a[7]
            try:
                if isinstance(p,list) and p and isinstance(p[0],list): p=p[0]
                allp+=path_points(p)
            except Exception: pass
    bb=lambda P:(min(x for x,_ in P),min(y for _,y in P),max(x for x,_ in P),max(y for _,y in P)) if P else None
    pb=bb(pads); cb=bb(pads+allp) if pads else bb(allp)
    return pb,cb
G={}
for cid,c in B.comp.items():
    d=B.des.get(cid); fpu=B.attr[cid].get('Footprint')
    pb,cb=local(fpu)
    G[d]=dict(id=cid,layer=c[3],x=c[4],y=c[5],rot=c[6] or 0,pad=pb,crt=cb,pads=[(p.num,p.net) for p in B.pads if p.comp_id==cid])
json.dump(G,open('fpgeo.json','w'))
print(len(G))
for d in ['U5','U30','J14','J19','J3','J1','J20','J11','J12','J4','J5','J9','J21','J15','R30','C30','U31','U7']:
    g=G[d]; m=lambda b:[round(v*0.0254,1) for v in b] if b else None
    print(d,'pad',m(g['pad']),'crt',m(g['crt']))
