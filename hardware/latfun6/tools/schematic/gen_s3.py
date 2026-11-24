import json,ast,re,collections,symlib,datetime
d=json.loads(json.loads(open(__import__('sys').argv[1],encoding='utf-8').read()))
NL={}
for v in d.values(): NL.setdefault(v['props'].get('Designator'),{}).update(ast.literal_eval(v['pins']) if isinstance(v['pins'],str) else v['pins'])
nets=collections.defaultdict(set)
for des,ps in NL.items():
    for p,n in ps.items():
        if n: nets[n].add((des,p))
P={**json.load(open('pins_p1.json')),**json.load(open('pins_p2.json'))}
pname=collections.defaultdict(dict); pos={}
for k,v in P.items():
    dk=k.split('#')[0]; pos.setdefault(dk,(v['x'],v['y']))
    for num,nm,*_ in v['pins']: pname[dk][num]=nm
F=[('B1',40,1200,1720,3280),('B3',40,150,1720,1170),('B4',1735,1190,2935,2440),('B5',1735,40,2935,1160),('B6',1735,2470,2935,3280),
   ('B7',2950,2280,4620,3280),('B8',2950,1080,3775,2250),('B9',3795,1080,4620,2250),('B10',2950,40,3875,1050),('B11',3895,230,4620,1050)]
def blk(des):
    if des=='U5': return 'B2'
    x,y=pos[des]
    for b,x0,y0,x1,y1 in F:
        if x0<=x<=x1 and y0<=y<=y1: return b
    return '?'
def ep(des,p):
    nm=pname[des].get(p,p)
    if list(pname[des].values()).count(nm)>1: return f'{des}.{p}'
    return f'{des}.{nm}' if nm!=p and not re.fullmatch(r'\d+',nm) else f'{des}.{p}'
def nkey(s): return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)',s)]
def others(n):
    e=sorted([x for x in nets[n] if x[0]!='U5'],key=lambda x:(nkey(x[0]),nkey(x[1])))
    bs=sorted({blk(x[0]) for x in e},key=nkey)
    return ', '.join(ep(*x) for x in e), ' '.join(bs)
bf=json.load(open('hardware/latfun6/board/latfun6.json'))
def san(s):
    m=re.match(r'(.+)\[(\d+)\]$',s)
    if not m: return s.upper()
    b=m.group(1).upper(); return b+('_' if b[-1].isdigit() else '')+m.group(2)
GROUPS=[('Clock, UART, flash',r'^(clk_25mhz|uart_|flash_)'),('User I/O: LEDs, buttons, DIP, I²C, audio',r'^(led|btn_n|sw_n|i2c_|audio_)'),
 ('HDMI (GPDI)',r'^gpdi_'),('PMOD, logic-analyser header, loopback, PLL test point',r'^(pmod|la\[|loop_|tp_pll)'),
 ('DDR3L',r'^ddram_'),('Gigabit Ethernet (RGMII)',r'^eth_'),('USB 2.0 ULPI',r'^ulpi_'),('microSD',r'^sd_'),
 ('SFP and PCIe sideband',r'^(sfp_|pcie_)')]
out=[]
out.append('## Section 3 — Inter-Block Net Map\n')
out.append(f'> Regenerated {datetime.date.today()} for v0.2 by `tools/schematic/gen_s3.py` from `board/latfun6.json` (FPGA balls and I/O standards) and the live EasyEDA netlist (endpoints). '
           'Blocks: B1 power · B2 FPGA (P2) · B3 FPGA decoupling/config/clock · B4 FT2232H + flash · B5 user I/O + audio · B6 HDMI · B7 SERDES (REFCLK, PCIe, SFP, SMA) · B8 DDR3L · B9 Ethernet · B10 USB ULPI + microSD · B11 PMOD/LA/TPs. '
           'Endpoints are `designator.pin` (pin name where the symbol has one). Gates C3/C4 compare this table with the canvas.\n')
used=set()
for title,rx in GROUPS:
    rows=[(k,v) for k,v in bf['signals'].items() if re.match(rx,k)]
    if not rows: continue
    out.append(f'### FPGA I/O: {title}\n\n| Net | U5 ball | Bank / standard | Endpoints | Blocks |\n|---|---|---|---|---|')
    for k,v in sorted(rows,key=lambda r:nkey(san(r[0]))):
        n=san(k); used.add(n); e,b=others(n)
        out.append(f"| {n} | {v['ball']} | {v['bank']} / {v['io']} | {e} | {b} |")
    out.append('')
left=[k for k in bf['signals'] if san(k) not in used]
assert not left,left
# complements + dedicated
DED=[('DDR3L complements (pin pair of board-file signals)',['DDRAM_CLK_N','DDRAM_DQS_N0','DDRAM_DQS_N1']),
 ('Configuration and JTAG',['CCLK','CFG1','DONE','INITN','PROGRAMN','JTAG_TCK','JTAG_TDI','JTAG_TDO','JTAG_TMS']),
 ('DDR3 VREF to FPGA',['FPGA_VREF6','FPGA_VREF7']),
 ('SERDES (DCU0 CH0 = PCIe, DCU1 CH0 = SFP, DCU1 CH1 = SMA; DCU0 CH1 unused)',['REFCLK_D0_P','REFCLK_D0_N','REFCLK_D1_P','REFCLK_D1_N','PCIE_HDTX_P','PCIE_HDTX_N','PCIE_RX_P','PCIE_RX_N','SFP_HDTX_P','SFP_HDTX_N','SFP_HDRX_P','SFP_HDRX_N','SMA_HDTX_P','SMA_HDTX_N','SMA_HDRX_P','SMA_HDRX_N'])]
for title,L in DED:
    out.append(f'### FPGA dedicated: {title}\n\n| Net | U5 ball(s) | Endpoints | Blocks |\n|---|---|---|---|')
    for n in L:
        balls=' '.join(sorted((p for x,p in nets[n] if x=='U5'),key=nkey)); e,b=others(n); used.add(n)
        out.append(f'| {n} | {balls} | {e} | {b} |')
    out.append('')
out.append('CFG0 and CFG2 balls are tied to GND (no named net): CFG[2:0] = 010, SPI master. Unused FPGA balls, RESERVED W10/W11 and NC K16/K17 are no-connect.\n')
RAILS=['12V_OR','12V_SLOT','5V_SYS','3V3','1V2','1V35','1V8','1V2_SER','2V5','VCCAUX','VCCAUXA','5V_HDMI','USB2_VBUS','SLOT_3V3','EN_2V5','GND']
used|=set(RAILS)
out.append('### Power rails\n\n| Rail | Pins | U5 balls | Blocks | Source / notes |\n|---|---|---|---|---|')
SRC={'12V_OR':'U20/U21 LM74700 ideal-diode OR of 12 V jack and slot 12 V','12V_SLOT':'J12 PCIe edge +12V (via U21)','5V_SYS':'U23 TPS2121 mux: U22 LMR33630 5 V buck / USB-C #1 VBUS',
 '3V3':'U2 TPS62826','1V2':'U3 TPS62827 (FPGA VCC)','1V35':'U24 TLV62569 via RS4 (DDR3L, VCCIO6/7)','1V8':'U25 TLV62569 (USB3320 VDD18, feeds U26)',
 '1V2_SER':'U26 TPS7A91 LDO from 1V8 (VCCA, VCCHRX, VCCHTX)','2V5':'U4 AP2112-2.5 via RS3; enabled by EN_2V5','VCCAUX':'2V5 via FB2','VCCAUXA':'2V5 via FB20 (SERDES aux)',
 '5V_HDMI':'U13 TPS2051 from 5V_SYS','USB2_VBUS':'J20 VBUS; U33 TPS2051 sources it in host mode','SLOT_3V3':'J12 +3.3V (slot)','EN_2V5':'U26 PG (open drain) + R450 100 k to 3V3 → U4 EN: VCCA before VCCAUXA','GND':'all'}
for n in RAILS:
    balls=sum(1 for x,_ in nets[n] if x=='U5'); bs=sorted({blk(x) for x,_ in nets[n]},key=nkey)
    out.append(f'| {n} | {len(nets[n])} | {balls or "—"} | {" ".join(bs)} | {SRC.get(n,"")} |')
out.append('')
# other inter-block nets
rest=[]
for n,s in nets.items():
    if n in used: continue
    bs={blk(x) for x,_ in s}
    if len(bs)>1: rest.append(n)
out.append('### Other inter-block nets (no FPGA ball)\n\n| Net | Endpoints | Blocks |\n|---|---|---|')
for n in sorted(rest,key=nkey):
    e,b=others(n); out.append(f'| {n} | {e} | {b} |')
out.append('')
open(__import__('sys').argv[2],'w',encoding='utf-8').write('\n'.join(out))
print(len(out),'lines; other inter-block nets:',len(rest))
