import json,sys,symlib
L,C,A=symlib.page('p1')
d=json.load(open(sys.argv[1])); P=json.load(open('pins_p1.json'))
id2des={P[k]['id']:k for k in P}
cur={id2des[c]:(round(l[3]),round(l[4]),l[5]%360) for c,l in C.items() if c in id2des}
plan=d['plan']
rot=[{'primitiveId':'$1I'+P[k]['id'][1:],'rotation':v[2]} for k,v in plan.items() if cur[k][2]!=v[2]]
xy=[{'primitiveId':'$1I'+P[k]['id'][1:],'x':v[0],'y':v[1]} for k,v in plan.items() if (cur[k][0],cur[k][1])!=(v[0],v[1])]
print('rot left',len(rot),'xy left',len(xy))
json.dump({'rot':rot,'xy':xy},open('left.json','w'))
