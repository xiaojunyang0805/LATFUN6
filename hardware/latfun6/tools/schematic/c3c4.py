import json,ast,collections,re
import netmap_p1 as m1, netmap_p2 as m2
d=json.loads(json.loads(open(__import__('sys').argv[1],encoding='utf-8').read()))
NL={}  # des -> {pinnum: net}
for uid,v in d.items():
    des=v['props'].get('Designator'); pins=v['pins'] if isinstance(v['pins'],dict) else ast.literal_eval(v['pins'])
    NL.setdefault(des,{}).update(pins)
nets=collections.defaultdict(list)
for des,ps in NL.items():
    for p,n in ps.items():
        if n: nets[n].append(f'{des}.{p}')
print('parts',len(NL),'nets',len(nets))
auto=[n for n in nets if n.startswith('$')]; print('auto-nets',len(auto),auto[:10])
single=sorted(n for n,v in nets.items() if len(v)==1); print('single-pin nets',len(single),single[:40])
empty=[(des,p) for des,ps in NL.items() for p,n in ps.items() if not n]
# pin name lookup
P={**{k:v for k,v in json.load(open('pins_p1.json')).items()},**json.load(open('pins_p2.json'))}
name2num=collections.defaultdict(dict)
for k,v in P.items():
    dk=k.split('#')[0]
    byname=collections.defaultdict(list)
    for num,nm,*_ in v['pins']: byname[nm].append(num)
    for num,nm,*_ in v['pins']:
        name2num[dk].setdefault(nm,[]).append(num)
        if num not in byname: name2num[dk].setdefault(num,[]).append(num)
exp={}  # (des,pinnum)->net
for M in (m1,m2):
    for des,(a,b) in M.P2.items(): exp[(des,'1')]=a; exp[(des,'2')]=b
    for des0,mp in M.BYNAME.items():
        des=des0.split('#')[0]
        for nm,n in mp.items():
            for num in name2num[des].get(nm,[]): exp[(des,num)]=n
mism=[(k,n,NL.get(k[0],{}).get(k[1])) for k,n in exp.items() if NL.get(k[0],{}).get(k[1])!=n]
print('mapped pins',len(exp),'| mismatches vs live netlist',len(mism),mism[:15])
ncset={(des.split('#')[0],num) for M in (m1,m2) for des,lst in M.NC.items() for nm in lst for num in name2num[des.split('#')[0]].get(nm,[])}
unexp=[(des,p,n) for des,ps in NL.items() for p,n in ps.items() if n and (des,p) not in exp]
print('netlist pins with net but not in map',len(unexp),unexp[:10])
empt_unexpl=[e for e in empty if e not in ncset]
print('empty pins',len(empty),'| not declared NC',len(empt_unexpl),empt_unexpl[:20])
# C3 topology
rails={'1V2','1V2_SER','1V35','1V8','3V3','2V5','VCCAUX','VCCAUXA','5V_SYS','5V_HDMI','12V_OR','VBUS_F','USB2_VBUS','CK1_VDDREF','CK2_VDDREF','CK1_VDDO','CK2_VDDO','CK1_VDDVCO','CK2_VDDVCO','3V3_OSC','SLOT_3V3','12V_SLOT','5V_12','1V2_PHY','2V5_PRE'}
bad=[]
for des,ps in NL.items():
    if re.match(r'C\d',des) and len(ps)==2:
        a,b=ps.get('1'),ps.get('2')
        if a==b: bad.append((des,'cap shorted',a))
    if re.match(r'R\d',des) and len(ps)==2:
        a,b=ps.get('1'),ps.get('2')
        if a==b: bad.append((des,'resistor both legs same net',a))
print('C3 same-net two-terminal parts',bad)
json.dump(dict(single=single),open('c4.json','w'))
nog=[(d,ps.get('1'),ps.get('2')) for d,ps in NL.items() if re.match(r'C\d',d) and 'GND' not in ps.values()]
print('caps without a GND leg',len(nog)); [print('  ',x) for x in sorted(nog,key=lambda x:int(re.sub(r'\D','',x[0])))]
