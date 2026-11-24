"""Write LATFUN6 net-class rule values (worknote Section 5) into the PCB document and bind them to the class /
diff-pair selectors that EDA created over the MCP. EDA must be CLOSED. Values are mil in the file (unit field 'mm'
is display only); via sizes are stored as radii."""
import sys, json
sys.path.insert(0, __import__('os').environ.get('PCB_LAYOUT_SCRIPTS', ''))
import eprj_core as ec
F = __import__('os').environ.get('EPRJ', 'hardware/EDA/Latfun6.eprj')
MODE = sys.argv[1] if len(sys.argv) > 1 else 'dry'
m = lambda mm: round(mm / 0.0254, 4)
r = lambda dia: round(dia / 2 / 0.0254, 4)
NEW = [  # (type, name, values)
    ('3', 'DDR_SE',  ['mm', m(0.09), m(0.125), m(0.20)]),
    ('3', 'PWR',     ['mm', m(0.25), m(0.50), m(3.00)]),
    # differentialPair: [wmin, wpref, wmax, gap_min, gap_pref, gap_max(0 = none), intra-pair length tolerance]
    ('10', 'DP100',  ['mm', m(0.09), m(0.100), m(0.110), m(0.18), m(0.203), 0, m(0.127)]),
    ('10', 'DP85',   ['mm', m(0.09), m(0.143), m(0.150), m(0.18), m(0.203), 0, m(0.127)]),
    ('10', 'DP90',   ['mm', m(0.09), m(0.127), m(0.135), m(0.18), m(0.203), 0, m(0.254)]),
    # viaSize: [outer min, outer pref, outer max, hole min, hole pref, hole max] as radii
    ('5', 'BGA_VIA', ['mm', r(0.30), r(0.40), r(10.0), r(0.20), r(0.20), r(6.30)]),
]
DEFAULT_TRACK = ['mm', m(0.09), m(0.15), m(2.54)]        # copperThickness1oz (active default): BGA escape needs 0.09
DEFAULT_VIA = ['mm', r(0.30), r(0.60), r(10.0), r(0.20), r(0.30), r(6.30)]
CLASS_BIND = {'DDR': {'3': 'DDR_SE', '5': 'BGA_VIA'}, 'PWR': {'3': 'PWR'}}
PAIR_CLASS = {
    'DP85': ['PCIE_HDTX', 'PCIE_TX', 'PCIE_RX', 'PCIE_REFCLK'],
    'DP90': ['USB1', 'USB2'],
    'DP100': ['SFP_HDTX', 'SFP_HDRX', 'SFP_TD', 'SFP_RD', 'SMA_HDTX', 'SMA_HDRX', 'SMA_TX', 'SMA_RX', 'REFCLK_D0',
              'REFCLK_D1', 'CK1_PRI', 'DDR_CLK', 'DDR_DQS0', 'DDR_DQS1', 'HDMI_D0', 'HDMI_D1', 'HDMI_D2', 'HDMI_CLK',
              'ETH_MDI0', 'ETH_MDI1', 'ETH_MDI2', 'ETH_MDI3'],
}
P = ec.Project(F)
lines = P.text.split('\n')
out = []; seen_new = set(); nb = 0
for l in lines:
    if not l.startswith('['): out.append(l); continue
    a = json.loads(l)
    if a[0] == 'RULE' and (a[1], a[2]) in {(t, n) for t, n, _ in NEW}:
        continue                                            # idempotent: drop an earlier copy, re-added below
    if a[0] == 'RULE' and a[1] == '3' and a[2] == 'copperThickness1oz': a[4] = DEFAULT_TRACK
    if a[0] == 'RULE' and a[1] == '5' and a[2] == 'viaSize': a[4] = DEFAULT_VIA
    if a[0] == 'RULE' and a[1] == '12':                     # insert new rules before the Common row
        for t, n, v in NEW: out.append(json.dumps(['RULE', t, n, 0, v], separators=(',', ':')))
    if a[0] == 'RULE_SELECTOR':
        k, name = a[1]
        if k == 'NET_CLASS' and name in CLASS_BIND: a[3] = CLASS_BIND[name]; nb += 1
        if k == 'DIFF_PAIR':
            for rule, pairs in PAIR_CLASS.items():
                if name in pairs: a[3] = {'10': rule}; nb += 1
    out.append(json.dumps(a, ensure_ascii=False, separators=(',', ':')))
new = '\n'.join(out)
print('bindings set:', nb, '(expected', len(CLASS_BIND) + sum(len(v) for v in PAIR_CLASS.values()), ')')
for l in out:
    if l.startswith('["RULE",') and any(f'"{n}"' in l for _, n, _ in NEW + [(0, 'copperThickness1oz', 0), (0, 'viaSize', 0)]): print(' ', l)
if MODE == 'write': P.write(new, 'netclass_rules'); print('written')
else: ec.make_candidate(P, new, 'rules_cand.eprj'); print('dry run -> rules_cand.eprj')
