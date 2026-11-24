import json,ast,re,collections
d=json.loads(json.loads(open(__import__('sys').argv[1],encoding='utf-8').read()))
NL={}
for v in d.values():
    NL.setdefault(v['props'].get('Designator'),{}).update(v['pins'] if isinstance(v['pins'],dict) else ast.literal_eval(v['pins']))
nets=collections.defaultdict(set)
for des,ps in NL.items():
    for p,n in ps.items():
        if n: nets[n].add((des,p))
# 1) board file record
bf=json.load(open('hardware/latfun6/board/latfun6.json'))
def san(s):
    m=re.match(r'(.+)\[(\d+)\]$',s)
    if not m: return s.upper()
    b=m.group(1).upper(); return b+('_' if b[-1].isdigit() else '')+m.group(2)
wrong=[];fpga_only=[];ok=0
for sig,v in bf['signals'].items():
    n=san(sig); actual=NL['U5'].get(v['ball'])
    if actual!=n: wrong.append((sig,v['ball'],actual)); continue
    others={des for des,p in nets[n] if des!='U5'}
    if not others: fpga_only.append(n)
    else: ok+=1
print('board-file signals',len(bf['signals']),'| OK',ok,'| ball carries wrong net',wrong,'| reaches only the FPGA',fpga_only)
# dedicated FPGA nets must reach the board
ded=['CCLK','CFG1','DONE','INITN','PROGRAMN','JTAG_TCK','JTAG_TDI','JTAG_TDO','JTAG_TMS','FPGA_VREF6','FPGA_VREF7',
     'REFCLK_D0_P','REFCLK_D0_N','REFCLK_D1_P','REFCLK_D1_N','PCIE_HDTX_P','PCIE_HDTX_N','PCIE_RX_P','PCIE_RX_N',
     'SFP_HDTX_P','SFP_HDTX_N','SFP_HDRX_P','SFP_HDRX_N','SMA_HDTX_P','SMA_HDTX_N','SMA_HDRX_P','SMA_HDRX_N',
     '1V2','1V2_SER','VCCAUX','VCCAUXA','3V3','1V35','GND']
print('dedicated FPGA nets reaching no other part',[n for n in ded if not {x for x,_ in nets[n] if x!='U5'}])
for n in ['SFP_HDTX_P','SFP_HDRX_P','PCIE_RX_P','PCIE_HDTX_P','SMA_HDTX_P','SMA_HDRX_P','REFCLK_D0_P','REFCLK_D1_P','VCCAUXA','EN_2V5']:
    print('  ',n,sorted(nets[n]))
# 2) names declared in the old Section 3
w=open('hardware/latfun6/latfun6_worknote.md',encoding='utf-8').read().split('\n')
sec='\n'.join(w[517:580])
names=set()
for row in re.findall(r'^\| ([^|]+) \|',sec,re.M):
    for tok in re.split(r'[ /,→]+',row.strip()):
        m=re.match(r'^([A-Z][A-Z0-9_]*)\[(\d)\.\.(\d)\]$',tok)
        if m: names|={f'{m.group(1)}{i}' for i in range(int(m.group(2)),int(m.group(3))+1)}
        elif re.match(r'^[A-Z][A-Z0-9_]+$',tok): names.add(tok)
for base in ('PMOD1','PMOD2','PMOD3','PMOD4'): names.discard(base)
print('Section 3 names',len(names),'| ABSENT in netlist:',sorted(n for n in names if n not in nets))
