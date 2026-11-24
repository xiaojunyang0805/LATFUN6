import json,sys,re
exec(open('placer_geo.py').read())
for f in sys.argv[1:]:
    plan=json.load(open(f)); meta=json.load(open(f+'.meta')); Wm=meta['W']
    R={d:(lambda p:(p[0]+crt_vis(d,p[2],p[3])[0],p[1]+crt_vis(d,p[2],p[3])[1],p[0]+crt_vis(d,p[2],p[3])[2],p[1]+crt_vis(d,p[2],p[3])[3]))(p) for d,p in plan.items()}
    bad=set()
    ds=list(plan)
    for i,a in enumerate(ds):
        for b in ds[i+1:]:
            if {a,b}=={'J13','J14'}: continue
            sa={1,2} if a in TH else {plan[a][3]}; sb={1,2} if b in TH else {plan[b][3]}
            if not sa&sb: continue
            r1,r2=R[a],R[b]
            if r1[0]<r2[2]+0.3 and r1[2]>r2[0]-0.3 and r1[1]<r2[3]+0.3 and r1[3]>r2[1]-0.3: bad.add(tuple(sorted((a,b))))
    # holes vs parts
    hb=[d for d in ds for hx,hy in meta['HOLES'] if R[d][0]<hx+4.3 and R[d][2]>hx-4.3 and R[d][1]<hy+4.3 and R[d][3]>hy-4.3]
    print(f, 'W', round(Wm,2), 'overlaps', sorted(bad), 'on holes', hb)
