"""List SERDES/PCIe/REFCLK net pads (mm) for routing planning.  python sernets.py [EPRJ]"""
import sys, os, re, collections
sys.path.insert(0, os.environ['PCB_LAYOUT_SCRIPTS'])
import eprj_core as ec
B = ec.Board(sys.argv[1] if len(sys.argv) > 1 else 'hardware/EDA/Latfun6.eprj')
pat = re.compile(sys.argv[2] if len(sys.argv) > 2 else r'^(SFP_|SMA_|PCIE_|REFCLK|CK\d_PRI)')
def ctr(s):
    if s[0] == 'c': return s[1], s[2]
    if s[0] == 'k': return (s[1]+s[3])/2, (s[2]+s[4])/2
    return sum(p[0] for p in s[1])/len(s[1]), sum(p[1] for p in s[1])/len(s[1])
by = collections.defaultdict(list)
for p in B.pads:
    if p.net and pat.match(p.net): by[p.net].append(p)
for n in sorted(by):
    print(n, ' '.join(f"{p.des}.{p.num}({ctr(p.shape)[0]*0.0254:.2f},{ctr(p.shape)[1]*0.0254:.2f})L{''.join(map(str,sorted(p.layers))) if len(p.layers)<3 else 'T'}" for p in by[n]))
