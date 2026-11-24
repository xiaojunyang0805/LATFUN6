"""Pads inside a window (mm):  python near.py X1 Y1 X2 Y2 [EPRJ]"""
import sys, os
sys.path.insert(0, os.environ['PCB_LAYOUT_SCRIPTS'])
import eprj_core as ec
x1, y1, x2, y2 = map(float, sys.argv[1:5])
B = ec.Board(sys.argv[5] if len(sys.argv) > 5 else 'hardware/EDA/Latfun6.eprj')
def ctr(s):
    if s[0] == 'c': return s[1], s[2]
    if s[0] == 'k': return (s[1]+s[3])/2, (s[2]+s[4])/2
    return sum(p[0] for p in s[1])/len(s[1]), sum(p[1] for p in s[1])/len(s[1])
for p in sorted(B.pads, key=lambda p: (p.des, p.num)):
    x, y = (v*0.0254 for v in ctr(p.shape))
    if x1 <= x <= x2 and y1 <= y <= y2:
        print(f"{p.des}.{p.num} {p.net} ({x:.2f},{y:.2f}) L{sorted(p.layers) if len(p.layers)<3 else 'T'}")
for v in B.vias:
    x, y = v.x*0.0254, v.y*0.0254
    if x1 <= x <= x2 and y1 <= y <= y2: print('VIA', v.net, f"({x:.2f},{y:.2f})")
