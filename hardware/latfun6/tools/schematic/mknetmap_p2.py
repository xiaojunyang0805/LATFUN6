import json,re
P=json.load(open('pins_p2.json'))
d=json.load(open('hardware/latfun6/board/latfun6.json'))
def san(s):
    m=re.match(r'(.+)\[(\d+)\]$',s)
    if not m: return s.upper()
    b=m.group(1).upper(); return b+('_' if b[-1].isdigit() else '')+m.group(2)
ball2net={v['ball']:san(k) for k,v in d['signals'].items()}
names={n:nm for k,v in P.items() for n,nm,*_ in v['pins']}
pio={nm.split('/')[0]:n for n,nm in names.items() if re.match(r'P[LRTB]\d+[A-D]',nm)}
# implied complements
for pk,nk in (('ddram_clk_p','DDRAM_CLK_N'),('ddram_dqs_p[0]','DDRAM_DQS_N0'),('ddram_dqs_p[1]','DDRAM_DQS_N1')):
    b=d['signals'][pk]['ball']; tru=names[b].split('/')[0]
    comp=[n for n,nm in names.items() if f'Comp_OF_{tru}' in nm][0]
    ball2net[comp]=nk
ball2net.update({'B2':'FPGA_VREF7','K5':'FPGA_VREF6'})
fixed={'VCC':'1V2','VCCAUX':'VCCAUX','VCCAUXA0':'VCCAUXA','VCCAUXA1':'VCCAUXA','VCCA0':'1V2_SER','VCCA1':'1V2_SER',
       'VCCIO0':'3V3','VCCIO1':'3V3','VCCIO2':'3V3','VCCIO3':'3V3','VCCIO8':'3V3','VCCIO6':'1V35','VCCIO7':'1V35','GND':'GND',
       'CFG_0':'GND','CFG_1':'CFG1','CFG_2':'GND','DONE':'DONE','PROGRAMN':'PROGRAMN','CCLK':'CCLK','INITN':'INITN',
       'TMS':'JTAG_TMS','TDI':'JTAG_TDI','TCK':'JTAG_TCK','TDO':'JTAG_TDO',
       'REFCLKP_D0':'REFCLK_D0_P','REFCLKN_D0':'REFCLK_D0_N','REFCLKP_D1':'REFCLK_D1_P','REFCLKN_D1':'REFCLK_D1_N',
       'HDTXP0_D0CH0':'PCIE_HDTX_P','HDTXN0_D0CH0':'PCIE_HDTX_N','HDRXP0_D0CH0':'PCIE_RX_P','HDRXN0_D0CH0':'PCIE_RX_N',
       'HDTXP0_D1CH0':'SFP_HDTX_P','HDTXN0_D1CH0':'SFP_HDTX_N','HDRXP0_D1CH0':'SFP_HDRX_P','HDRXN0_D1CH0':'SFP_HDRX_N',
       'HDTXP0_D1CH1':'SMA_HDTX_P','HDTXN0_D1CH1':'SMA_HDTX_N','HDRXP0_D1CH1':'SMA_HDRX_P','HDRXN0_D1CH1':'SMA_HDRX_N'}
BY={}; NC={}; unk=[]
for k,v in P.items():
    m={}; nc=[]
    for n,nm,*_ in v['pins']:
        base=nm.split('/')[0]
        if n in ball2net: m[n]=ball2net[n]
        elif base in fixed: m[n]=fixed[base]
        elif base.startswith(('VCCHRX','VCCHTX')): m[n]='1V2_SER'
        elif base.startswith(('HDTX','HDRX')) and 'D0CH1' in base: nc.append(nm)
        elif base in ('RESERVED','NC') or re.match(r'P[LRTB]\d+[A-D]',base): nc.append(nm)
        else: unk.append((n,nm))
    BY[k]=m; NC[k]=nc
open('netmap_p2.py','w').write('P2 = {}\nBYNAME = %r\nNC = %r\n' % (BY,NC))
print('mapped',sum(len(m) for m in BY.values()),'nc',sum(len(x) for x in NC.values()),'unknown',unk)
nets=set(n for m in BY.values() for n in m.values())
import netmap_p1 as p1
p1nets=set(p1.P2[k][i] for k in p1.P2 for i in (0,1))|set(n for m in p1.BYNAME.values() for n in m.values())
print('P2 nets not on P1:',sorted(nets-p1nets))
