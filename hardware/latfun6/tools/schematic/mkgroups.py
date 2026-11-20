import pprint
open('netmap_p1.py', 'w').write("import netmap_b1 as a, netmap_rest as b\nP2 = {**a.P2, **b.P2}; BYNAME = {**a.BYNAME, **b.BYNAME}; NC = {**a.NC, **b.NC}\n")
R = lambda a, b: ['R%d' % i for i in range(a, b + 1)]
C = lambda a, b: ['C%d' % i for i in range(a, b + 1)]
B = {
 'b3': dict(FRAME=(40, 150, 1720, 1170),
   GROUPS=[('x1', 'X1', ['X1', 'FB5', 'C58']), ('done', 'Q1', ['Q1', 'D3', 'R40', 'R41', 'R42']),
           ('prog', 'SW1', ['SW1', 'R30', 'C59']), ('cfg', 'R31', R(31, 39)),
           ('vcc', 'C36', ['C36', 'C37'] + C(30, 35)), ('aux', 'FB2', ['FB2', 'C40', 'C38', 'C39']),
           ('io33', 'C54', ['C54', 'C55', 'C56'] + C(41, 49)), ('io135', 'C57', ['C57'] + C(50, 53))],
   GRID={'cfg': 3, 'vcc': 4, 'aux': 4, 'io33': 4, 'io135': 3}, OFFSETS={},
   ROWS=[['x1', 'done', 'prog', 'cfg'], ['vcc', 'aux'], ['io33', 'io135']]),
 'b4': dict(FRAME=(1735, 1190, 2935, 2440),
   GROUPS=[('ft', 'U7', ['U7', 'Y1', 'U8'] + R(70, 83) + C(70, 86) + ['FB4']), ('flash', 'U6', ['U6', 'C60'] + R(60, 62)),
           ('jtag', 'J2', ['J2'])],
   OFFSETS={'Y1': (-400, 330), 'U8': (60, 300)}, ROWS=[['ft'], ['flash', 'jtag']]),
 'b5': dict(FRAME=(1735, 40, 2935, 1160),
   GROUPS=[('leds', 'R100', sum([['R%d' % (100 + i), 'D%d' % (10 + i)] for i in range(8)], [])),
           ('btn', 'R110', sum([['R%d' % (110 + i), 'SW%d' % (2 + i)] for i in range(4)], [])),
           ('dip', 'SW6', ['SW6'] + R(114, 117)), ('eep', 'U9', ['U9', 'R120', 'R121', 'C90']),
           ('audio', 'R140', ['R140', 'C140', 'R141', 'C141', 'C142', 'J4', 'R142', 'C143', 'R143', 'C144', 'C145', None])],
   GRID={'leds': 2, 'btn': 2, 'audio': 6}, GRIDP={'leds': (100, 40), 'btn': (100, 60), 'audio': (100, 60)},
   OFFSETS={}, ROWS=[['leds', 'btn', 'dip', 'eep'], ['audio']]),
 'b6': dict(FRAME=(1735, 2470, 2935, 3280),
   GROUPS=[('hdmi', 'J3', ['J3', 'U10', 'U11', 'R135', 'R136']), ('ddc', 'U12', ['U12'] + R(130, 134) + ['C132']),
           ('p5v', 'U13', ['U13', 'C130', 'C131'])],
   OFFSETS={'U10': (-460, 60), 'U11': (-460, -90)}, ROWS=[['ddc', 'p5v'], ['hdmi']]),
 'b7': dict(FRAME=(2950, 2280, 4620, 3280),
   GROUPS=[('ck1', 'U27', ['U27', 'Y2', 'FB10', 'FB11', 'FB12'] + C(300, 307) + ['R300', 'R301', 'C320', 'C321']),
           ('ck2', 'U28', ['U28', 'Y3', 'FB13', 'FB14', 'FB15'] + C(308, 315) + ['R302', 'R303']),
           ('pcie', 'J12', ['J12', 'C322', 'C323', 'R304', 'R305']),
           ('sfp', 'J13', ['J13', 'J14'] + R(310, 313) + ['L30', 'L31'] + C(330, 335) + R(320, 324)),
           ('sma', 'J15', ['J15', 'C340', 'J16', 'C341', 'J17', 'C342', 'J18', 'C343'])],
   GRID={'sma': 2}, GRIDP={'sma': (140, 100)}, OFFSETS={'Y2': (-330, 120), 'Y3': (-330, 120), 'J14': (330, 0)},
   ROWS=[['ck1', 'ck2'], ['pcie', 'sfp', 'sma']]),
 'b8': dict(FRAME=(2950, 1080, 3775, 2250),
   GROUPS=[('ddr', 'U30', ['U30'] + C(350, 364) + R(330, 342))], OFFSETS={}, ROWS=[['ddr']]),
 'b9': dict(FRAME=(3795, 1080, 4620, 2250),
   GROUPS=[('phy', 'U31', ['U31', 'Y4', 'L32'] + C(370, 380) + R(350, 362)), ('jack', 'J19', ['J19', 'C381', 'R363', 'R364'])],
   OFFSETS={'Y4': (-360, 220)}, ROWS=[['phy'], ['jack']]),
 'b10': dict(FRAME=(2950, 40, 3875, 1050),
   GROUPS=[('ulpi', 'U32', ['U32', 'Y5'] + C(390, 397) + R(370, 373)),
           ('usbc', 'J20', ['J20', 'U33'] + R(374, 377) + C(398, 400)), ('sd', 'J21', ['J21'] + R(380, 386) + ['C401', 'C402'])],
   OFFSETS={'Y5': (-380, 170), 'U33': (0, -300)}, ROWS=[['ulpi'], ['usbc', 'sd']]),
 'b11': dict(FRAME=(3895, 230, 4620, 1050),
   GROUPS=[('pmod', 'J5', ['J5', 'J6', 'J7', 'J8']), ('la', 'J9', ['J9', 'J10']), ('tp', 'TP1', ['TP%d' % i for i in range(1, 13)])],
   GRID={'pmod': 2, 'la': 2, 'tp': 4}, GRIDP={'pmod': (200, 110), 'la': (150, 100), 'tp': (120, 55)},
   OFFSETS={}, ROWS=[['pmod'], ['la'], ['tp']]),
}
for k, d in B.items():
    with open('groups_%s.py' % k, 'w') as f:
        for kk, vv in d.items(): f.write('%s = %s\n' % (kk, pprint.pformat(vv, width=140)))
print('ok', list(B))
