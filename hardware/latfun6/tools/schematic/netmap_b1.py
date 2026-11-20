"""B1 power: pin -> net map (by pin NAME for ICs, by pin NUMBER '1'/'2' for 2-pin parts).
Sources: worknote B1 v0.2 tables + v0.1 Block A/B rows kept by v0.2. None/absent = intentional no-connect (listed in NC)."""
G = 'GND'
P2 = {  # two-pin parts: (pin1 net, pin2 net)
    # 12 V jack entry
    'F2': ('JACK_RAW', 'JACK_F'), 'C200': ('VCAP_J', 'JACK_F'), 'C201': ('JACK_F', G),
    'C202': ('VCAP_S', '12V_SLOT'), 'C203': ('12V_SLOT', G), 'R200': ('12V_SLOT', 'SLOT_EN'),
    'R201': ('JACK_F', 'JACK_DET'), 'R202': ('JACK_DET', G), 'C204': ('12V_OR', G),
    # 12 -> 5 V buck
    'C205': ('12V_OR', G), 'C206': ('12V_OR', G), 'C207': ('BOOT_5V', 'SW_5V'), 'C208': ('VCC_5V', G),
    'L20': ('SW_5V', '5V_12'), 'C209': ('5V_12', G), 'C210': ('5V_12', G), 'C211': ('5V_12', G), 'C212': ('5V_12', G),
    'R203': ('5V_12', 'FB_5V'), 'R204': ('FB_5V', G),
    # 5 V mux
    'R205': ('ILM_5V', G), 'R206': ('5V_12', 'PR1_5V'), 'R207': ('PR1_5V', G),
    'R208': ('5V_12', 'OV1_5V'), 'R209': ('OV1_5V', G), 'R210': ('VBUS_F', 'OV2_5V'), 'R211': ('OV2_5V', G),
    'C213': ('SS_5V', G), 'C214': ('VBUS_F', G), 'C215': ('5V_SYS', G),
    # USB-C #1 entry
    'F1': ('VBUS', 'VBUS_F'), 'R1': ('CC1', G), 'R2': ('CC2', G), 'C1': ('5V_SYS', G), 'C2': ('5V_SYS', G),
    # 3V3 (U2)
    'L1': ('SW_3V3', '3V3_PRE'), 'C10': ('5V_SYS', G), 'C11': ('3V3_PRE', G), 'C12': ('3V3_PRE', G),
    'RS1': ('3V3_PRE', '3V3'), 'R10': ('3V3', 'FB_3V3'), 'R11': ('FB_3V3', G), 'C13': ('3V3', 'FB_3V3'),
    # 1V2 core (U3)
    'L2': ('SW_1V2', '1V2_PRE'), 'C14': ('5V_SYS', G), 'C15': ('1V2_PRE', G), 'C19': ('1V2_PRE', G), 'C20': ('1V2_PRE', G),
    'RS2': ('1V2_PRE', '1V2'), 'R12': ('1V2', 'FB_1V2'), 'R13': ('FB_1V2', G), 'C21': ('1V2', 'FB_1V2'),
    'R14': ('3V3', 'EN_1V2'), 'C16': ('EN_1V2', G),
    # 1V35 (U24)
    'L21': ('SW_1V35', '1V35_PRE'), 'C220': ('5V_SYS', G), 'C221': ('1V35_PRE', G), 'C228': ('1V35_PRE', G),
    'RS4': ('1V35_PRE', '1V35'), 'R220': ('1V35', 'FB_1V35'), 'R221': ('FB_1V35', G),
    # 1V8 (U25)
    'L22': ('SW_1V8', '1V8'), 'C222': ('5V_SYS', G), 'C223': ('1V8', G), 'R222': ('1V8', 'FB_1V8'), 'R223': ('FB_1V8', G),
    # 1V2_SER (U26)
    'C224': ('1V8', G), 'C225': ('1V2_SER', G), 'C226': ('NR_SER', G), 'C227': ('1V2_SER', 'FB_SER'),
    'R224': ('1V2_SER', 'FB_SER'), 'R225': ('FB_SER', G),
    # 2V5 (U4) + power LED
    'C17': ('3V3', G), 'C18': ('2V5_PRE', G), 'RS3': ('2V5_PRE', '2V5'), 'R15': ('3V3', 'PWR_LED'),
}
BYNAME = {  # parts mapped by pin name (diodes, ICs, FETs, connectors)
    'D1': {'C': 'VBUS_F', 'A': G}, 'D4': {'K': 'JACK_F', 'A': G}, 'D2': {'A': 'PWR_LED', 'K': G},
    'J11': {'1': 'JACK_RAW', '2': G, '3': G},
    'U20': {'ANODE': 'JACK_F', 'CATHODE': '12V_OR', 'GATE': 'G_JACK', 'EN': 'JACK_F', 'VCAP': 'VCAP_J', 'GND': G},
    'U21': {'ANODE': '12V_SLOT', 'CATHODE': '12V_OR', 'GATE': 'G_SLOT', 'EN': 'SLOT_EN', 'VCAP': 'VCAP_S', 'GND': G},
    'Q20': {'S': 'JACK_F', 'G': 'G_JACK', 'D': '12V_OR'},
    'Q21': {'S': '12V_SLOT', 'G': 'G_SLOT', 'D': '12V_OR'},
    'Q22': {'D': 'SLOT_EN', 'G': 'JACK_DET', 'S': G},
    'U22': {'VIN': '12V_OR', 'EN': '12V_OR', 'PGND': G, 'EP': G, 'SW': 'SW_5V', 'BOOT': 'BOOT_5V',
            'VCC': 'VCC_5V', 'FB': 'FB_5V'},                       # PG: NC
    'U23': {'IN1': '5V_12', 'IN2': 'VBUS_F', 'OUT': '5V_SYS', 'ILM': 'ILM_5V', 'PR1': 'PR1_5V', 'OV1': 'OV1_5V',
            'OV2': 'OV2_5V', 'SS': 'SS_5V', 'CP2': G, 'ST': 'PWR_ST', 'GND': G},
    'J1': {'GND': G, 'VBUS': 'VBUS', 'CC1': 'CC1', 'CC2': 'CC2', 'DP1': 'USB_DP', 'DP2': 'USB_DP',
           'DN1': 'USB_DN', 'DN2': 'USB_DN', 'EH': G},             # SBU1/SBU2: NC
    'U1': {'I/O1': 'USB_DP', 'I/O2': 'USB_DN', 'VBUS': 'VBUS_F', 'GND': G},
    'U2': {'VIN': '5V_SYS', 'EN': '5V_SYS', 'SW': 'SW_3V3', 'FB': 'FB_3V3', 'GND': G},   # PG: NC
    'U3': {'VIN': '5V_SYS', 'EN': 'EN_1V2', 'SW': 'SW_1V2', 'FB': 'FB_1V2', 'GND': G},   # PG: NC
    'U24': {'VIN': '5V_SYS', 'EN': '5V_SYS', 'SW': 'SW_1V35', 'FB': 'FB_1V35', 'GND': G},
    'U25': {'VIN': '5V_SYS', 'EN': '5V_SYS', 'SW': 'SW_1V8', 'FB': 'FB_1V8', 'GND': G},
    'U26': {'IN': '1V8', 'EN': '1V8', 'OUT': '1V2_SER', 'FB': 'FB_SER', 'GND': G, 'EP': G,
            'SS_CTRL': G, 'NR/SS': 'NR_SER'},                        # PG: NC
    'U4': {'IN': '3V3', 'EN': '3V3', 'GND': G, 'OUT': '2V5_PRE'},    # NC pin: NC
}
NC = {'U22': ['PG'], 'U2': ['PG'], 'U3': ['PG'], 'U26': ['PG'], 'U4': ['NC'], 'J1': ['SBU1', 'SBU2']}

# --- A2 fixes 2026-11-20: VCCA (1V2_SER) must be up before VCCAUXA (2V5) -> 2V5 LDO enabled by U26 PG
BYNAME['U26']['PG'] = 'EN_2V5'; NC['U26'] = []
BYNAME['U4']['EN'] = 'EN_2V5'
P2 = dict(P2) if not isinstance(P2, dict) else P2
P2['R450'] = ('EN_2V5', '3V3')          # 100k PG pull-up (TPS7A91 PG is open drain)
