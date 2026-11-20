"""P1 blocks B3-B11: pin -> net map. FPGA-facing net names = board/latfun6.json signal names, upper-case,
'[n]' -> 'n' (led[0] -> LED0, pmod1[7] -> PMOD1_7). ✱ = to confirm at Gate A2."""
G = 'GND'
P2 = {}
BYNAME = {}
NC = {}

# ---------------- B3: FPGA supply decoupling, configuration, 25 MHz clock ----------------
P2.update({'FB2': ('2V5', 'VCCAUX'), 'FB5': ('3V3', '3V3_OSC'), 'C58': ('3V3_OSC', G)})
for c in ('C30', 'C31', 'C32', 'C33', 'C34', 'C35', 'C36', 'C37'): P2[c] = ('1V2', G)        # VCC core
for c in ('C38', 'C39', 'C40'): P2[c] = ('VCCAUX', G)
for c in ('C41', 'C42', 'C43', 'C44', 'C45', 'C46', 'C47', 'C48', 'C49', 'C54', 'C55', 'C56'): P2[c] = ('3V3', G)  # VCCIO0-3,8
for c in ('C50', 'C51', 'C52', 'C53', 'C57'): P2[c] = ('1V35', G)   # VCCIO6/7 (DDR3L) ✱ ball count at A2
P2.update({'R30': ('PROGRAMN', '3V3'), 'R31': ('INITN', '3V3'), 'R32': ('DONE', '3V3'), 'R33': ('CCLK', '3V3'),
           'R34': ('CCLK', 'FLASH_CLK'), 'R35': ('CFG1', '3V3'), 'R36': ('JTAG_TDI', '3V3'), 'R37': ('JTAG_TMS', '3V3'),
           'R38': ('JTAG_TDO', '3V3'), 'R39': ('JTAG_TCK', G), 'R40': ('DONE_LED_G', G), 'R41': ('3V3', 'DONE_LED_A'),
           'R42': ('DONE', 'DONE_LED_G'), 'C59': ('PROGRAMN', G)})
BYNAME.update({'D3': {'A': 'DONE_LED_A', 'K': 'DONE_LED_K', '1': 'DONE_LED_A', '2': 'DONE_LED_K'},
               'Q1': {'D': 'DONE_LED_K', 'G': 'DONE_LED_G', 'S': G},
               'SW1': {'A': 'PROGRAMN', 'B': 'PROGRAMN', 'C': G, 'D': G},          # ✱ 1-2 / 3-4 internally joined
               'X1': {'OE/NC': '3V3_OSC', 'GND': G, 'OUT': 'CLK_25MHZ', 'VDD': '3V3_OSC'}})

# ---------------- B4: FT2232H USB JTAG/UART, config flash, external JTAG ----------------
BYNAME['U6'] = {'CS#': 'FLASH_CS_N', 'DO': 'FLASH_MISO', 'IO2': 'FLASH_IO2', 'GND': G, 'DI': 'FLASH_MOSI',
                'CLK': 'FLASH_CLK', 'IO3': 'FLASH_IO3', 'VCC': '3V3'}
P2.update({'C60': ('3V3', G), 'R60': ('FLASH_CS_N', '3V3'), 'R61': ('FLASH_IO2', '3V3'), 'R62': ('FLASH_IO3', '3V3')})
BYNAME['U7'] = {'VCORE': '1V8_FT', 'VREGOUT': '1V8_FT', 'VREGIN': '3V3', 'VCCIO': '3V3', 'VPHY': '3V3_FTA', 'VPLL': '3V3_FTA',
                'GND': G, 'AGND': G, 'TEST': G, 'RESET#': 'FT_RESET_N', 'REF': 'FT_REF', 'DM': 'USB_DN', 'DP': 'USB_DP',
                'OSCI': 'FT_OSCI', 'OSCO': 'FT_OSCO', 'EECS': 'FT_EECS', 'EECLK': 'FT_EECLK', 'EEDATA': 'FT_EEDATA',
                'ADBUS0': 'FT_AD0', 'ADBUS1': 'FT_AD1', 'ADBUS2': 'FT_AD2', 'ADBUS3': 'FT_AD3',
                'BDBUS0': 'FT_BD0', 'BDBUS1': 'FT_BD1', 'BDBUS2': 'FT_BD2', 'BDBUS3': 'FT_BD3'}
NC['U7'] = ['PWREN#', 'SUSPEND#'] + [f'{b}{i}' for b in ('ADBUS', 'BDBUS') for i in range(4, 8)] + \
           [f'{b}{i}' for b in ('ACBUS', 'BCBUS') for i in range(8)]
P2.update({'R70': ('FT_REF', G), 'R71': ('FT_RESET_N', '3V3'), 'R72': ('FT_EECS', '3V3'), 'R73': ('FT_EECLK', '3V3'),
           'R74': ('FT_EEDATA', 'EE_DO'), 'R75': ('FT_EEDATA', '3V3'),
           'R76': ('FT_AD0', 'JTAG_TCK'), 'R77': ('FT_AD1', 'JTAG_TDI'), 'R78': ('FT_AD2', 'JTAG_TDO'), 'R79': ('FT_AD3', 'JTAG_TMS'),
           'R80': ('FT_BD1', 'UART_TX'), 'R81': ('FT_BD0', 'UART_RX'), 'R82': ('FT_BD2', 'UART_CTS_N'), 'R83': ('FT_BD3', 'UART_RTS_N'),
           'C70': ('FT_OSCI', G), 'C71': ('FT_OSCO', G), 'C72': ('3V3', G), 'C81': ('3V3', G), 'C80': ('1V8_FT', G),
           'C73': ('1V8_FT', G), 'C74': ('1V8_FT', G), 'C75': ('1V8_FT', G),
           'C76': ('3V3', G), 'C77': ('3V3', G), 'C78': ('3V3', G), 'C79': ('3V3', G), 'FB4': ('3V3', '3V3_FTA'),
           'C83': ('3V3_FTA', G), 'C84': ('3V3_FTA', G), 'C85': ('3V3_FTA', G), 'C86': ('3V3_FTA', G), 'C82': ('3V3', G)})
BYNAME['U8'] = {'CS': 'FT_EECS', 'CLK': 'FT_EECLK', 'DI': 'FT_EEDATA', 'DO': 'EE_DO', 'VCC': '3V3', 'VSS': G}
BYNAME['Y1'] = {'OSC1': 'FT_OSCI', 'OSC2': 'FT_OSCO', 'GND': G}
BYNAME['J2'] = {'1': 'JTAG_TCK', '2': 'JTAG_TDI', '3': 'JTAG_TDO', '4': 'JTAG_TMS', '5': G, '6': '3V3'}

# ---------------- B5: user I/O, I2C EEPROM, audio ----------------
for i in range(8):
    BYNAME[f'D{10 + i}'] = {'A': f'LED{i}_A', 'K': G, '1': f'LED{i}_A', '2': G}
    P2[f'R{100 + i}'] = (f'LED{i}', f'LED{i}_A')
for i in range(4):
    BYNAME[f'SW{2 + i}'] = {'A': f'BTN_N{i}', 'B': f'BTN_N{i}', 'C': G, 'D': G}
    P2[f'R{110 + i}'] = (f'BTN_N{i}', '3V3'); P2[f'R{114 + i}'] = (f'SW_N{i}', '3V3')
BYNAME['SW6'] = {'1': 'SW_N0', '2': 'SW_N1', '3': 'SW_N2', '4': 'SW_N3', '5': G, '6': G, '7': G, '8': G}  # ✱ k <-> 9-k
P2.update({'R120': ('I2C_SCL', '3V3'), 'R121': ('I2C_SDA', '3V3'), 'C90': ('3V3', G)})
BYNAME['U9'] = {'A0': G, 'A1': G, 'A2': G, 'GND': G, 'SDA': 'I2C_SDA', 'SCL': 'I2C_SCL', 'WP': G, 'VCC': '3V3'}
P2.update({'R140': ('AUDIO_L', 'AUD_L1'), 'C140': ('AUD_L1', G), 'R141': ('AUD_L1', 'AUD_L2'), 'C141': ('AUD_L2', G),
           'C142': ('AUD_L2', 'JACK_L'), 'R142': ('AUDIO_R', 'AUD_R1'), 'C143': ('AUD_R1', G), 'R143': ('AUD_R1', 'AUD_R2'),
           'C144': ('AUD_R2', G), 'C145': ('AUD_R2', 'JACK_R')})
BYNAME['J4'] = {'1': G, '2': 'JACK_L', '3': 'JACK_R'}       # ✱ PJ-313D pin order (sleeve/tip/ring)

# ---------------- B6: HDMI ----------------
BYNAME['J3'] = {'TMDS Data 2+': 'GPDI_D2_P', 'TMDS Data 2-': 'GPDI_D2_N', 'TMDS Data 1+': 'GPDI_D1_P', 'TMDS Data 1-': 'GPDI_D1_N',
                'TMDS Data 0+': 'GPDI_D0_P', 'TMDS Data 0-': 'GPDI_D0_N', 'TMDS Clock+': 'GPDI_CLK_P', 'TMDS Clock-': 'GPDI_CLK_N',
                'TMDS Data 2 Shield': G, 'TMDS Data 1 Shield': G, 'TMDS Data 0 Shield': G, 'TMDS Clock Shield': G,
                'SCL': 'HDMI_SCL_5V', 'SDA': 'HDMI_SDA_5V', 'DDC/CEC Ground': G, '+5V Power': '5V_HDMI',
                'Hot Plug Detect': 'HDMI_HPD', 'GND': G}
NC['J3'] = ['CEC', 'Reserved (N.C.)']
BYNAME['U10'] = {'D1+': 'GPDI_CLK_P', 'D1-': 'GPDI_CLK_N', 'D2+': 'GPDI_D0_P', 'D2-': 'GPDI_D0_N', 'GND': G}
BYNAME['U11'] = {'D1+': 'GPDI_D1_P', 'D1-': 'GPDI_D1_N', 'D2+': 'GPDI_D2_P', 'D2-': 'GPDI_D2_N', 'GND': G}
NC['U10'] = NC['U11'] = ['NC']
BYNAME['U12'] = {'GND': G, 'VREF1': '3V3', 'SCL1': 'GPDI_SCL', 'SDA1': 'GPDI_SDA', 'SDA2': 'HDMI_SDA_5V',
                 'SCL2': 'HDMI_SCL_5V', 'VREF2': 'PCA_EN', 'EN': 'PCA_EN'}
BYNAME['U13'] = {'IN': '5V_SYS', 'OUT': '5V_HDMI', 'EN(EN#)': '5V_SYS', 'GND': G}
NC['U13'] = ['FLT#']
P2.update({'C130': ('5V_SYS', G), 'C131': ('5V_HDMI', G), 'C132': ('3V3', G), 'R130': ('HDMI_SCL_5V', '5V_HDMI'),
           'R131': ('HDMI_SDA_5V', '5V_HDMI'), 'R132': ('GPDI_SCL', '3V3'), 'R133': ('GPDI_SDA', '3V3'),
           'R134': ('PCA_EN', '5V_HDMI'), 'R135': ('HDMI_HPD', 'GPDI_HPD'), 'R136': ('GPDI_HPD', G)})

# ---------------- B7: SERDES clocks, PCIe edge, SFP, SMA ----------------
P2.update({'FB10': ('3V3', 'CK1_VDDREF'), 'FB11': ('3V3', 'CK1_VDDVCO'), 'FB12': ('1V8', 'CK1_VDDO'),
           'FB13': ('3V3', 'CK2_VDDREF'), 'FB14': ('3V3', 'CK2_VDDVCO'), 'FB15': ('1V8', 'CK2_VDDO')})
for k, cs in (('CK1', ('C300', 'C301', 'C302', 'C303', 'C304', 'C305', 'C306', 'C307')),
              ('CK2', ('C308', 'C309', 'C310', 'C311', 'C312', 'C313', 'C314', 'C315'))):
    nets = [f'{k}_VDDREF'] * 2 + [f'{k}_VDDVCO'] * 3 + [f'{k}_VDDO'] * 3
    for c, n in zip(cs, nets): P2[c] = (n, G)
BYNAME['U27'] = {'SECREF_P': 'CK1_XIN', 'SECREF_N': 'CK1_XOUT', 'VDD_REF': 'CK1_VDDREF', 'REFSEL': 'SLOT_DET',
                 'PRIREF_P': 'CK1_PRI_P', 'PRIREF_N': 'CK1_PRI_N', 'PDN': 'CK1_VDDREF', 'SCL/GPIO3': 'I2C_SCL',
                 'SDA/GPIO2': 'I2C_SDA', 'VDDO_34': 'CK1_VDDO', 'VDDO_12': 'CK1_VDDO', 'OUT1_P': 'REFCLK_D0_P',
                 'OUT1_N': 'REFCLK_D0_N', 'HW_SW_CTRL': 'SLOT_DET', 'VDD_VCO': 'CK1_VDDVCO', 'DAP': G}
BYNAME['U28'] = {'SECREF_P': 'CK2_XIN', 'SECREF_N': 'CK2_XOUT', 'VDD_REF': 'CK2_VDDREF', 'REFSEL': 'CK2_REFSEL',
                 'PDN': 'CK2_VDDREF', 'SCL/GPIO3': 'SFP_SCL', 'SDA/GPIO2': 'SFP_SDA', 'VDDO_34': 'CK2_VDDO',
                 'VDDO_12': 'CK2_VDDO', 'OUT1_P': 'REFCLK_D1_P', 'OUT1_N': 'REFCLK_D1_N', 'HW_SW_CTRL': 'CK2_HWSW',
                 'VDD_VCO': 'CK2_VDDVCO', 'DAP': G}
NC['U27'] = ['OUT0', 'OUT2_P', 'OUT2_N', 'OUT3_P', 'OUT3_N', 'OUT4_P', 'OUT4_N', 'GPIO1', 'GPIO4']
NC['U28'] = NC['U27'] + ['PRIREF_P', 'PRIREF_N']
BYNAME['Y2'] = {'1': 'CK1_XIN', '3': 'CK1_XOUT', 'GND': G}
BYNAME['Y3'] = {'1': 'CK2_XIN', '3': 'CK2_XOUT', 'GND': G}
P2.update({'R300': ('SLOT_3V3', 'SLOT_DET'), 'R301': ('SLOT_DET', G), 'R302': ('CK2_REFSEL', G), 'R303': ('CK2_HWSW', '3V3'),
           'R304': ('PCIE_PERST_N', '3V3'), 'R305': ('PCIE_CLKREQ_N', G),
           'C320': ('PCIE_REFCLK_P', 'CK1_PRI_P'), 'C321': ('PCIE_REFCLK_N', 'CK1_PRI_N'),
           'C322': ('PCIE_HDTX_P', 'PCIE_TX_P'), 'C323': ('PCIE_HDTX_N', 'PCIE_TX_N')})
BYNAME['J12'] = {'~PRSNT1~': 'PCIE_PRSNT', '+12V': '12V_SLOT', 'GND': G, '+3.3V': 'SLOT_3V3', '~PERST~': 'PCIE_PERST_N',
                 'REFCLK+': 'PCIE_REFCLK_P', 'REFCLK-': 'PCIE_REFCLK_N', 'PERp0': 'PCIE_RX_P', 'PERn0': 'PCIE_RX_N',
                 'PETp0': 'PCIE_TX_P', 'PETn0': 'PCIE_TX_N', '~WAKE~': 'PCIE_WAKE_N', 'B31': 'PCIE_PRSNT', 'B12': 'PCIE_CLKREQ_N'}
NC['J12'] = ['JTAG1', 'JTAG2', 'JTAG3', 'JTAG4', 'JTAG5', 'SMCLK', 'SMDAT', '3.3Vaux', 'RSVD', '~PRSNT2~',
             'PERp1', 'PERn1', 'PERp2', 'PERn2', 'PERp3', 'PERn3', 'PETp1', 'PETn1', 'PETp2', 'PETn2', 'PETp3', 'PETn3']
BYNAME['J13'] = {'1': G, '2': 'SFP_TX_FAULT', '3': 'SFP_TX_DISABLE', '4': 'SFP_SDA', '5': 'SFP_SCL', '6': 'SFP_MOD_ABS',
                 '7': 'SFP_RS', '8': 'SFP_LOS', '9': 'SFP_RS', '10': G, '11': G, '12': 'SFP_RD_N', '13': 'SFP_RD_P',
                 '14': G, '15': 'SFP_VCCR', '16': 'SFP_VCCT', '17': G, '18': 'SFP_TD_P', '19': 'SFP_TD_N', '20': G}
BYNAME['J14'] = {str(i): G for i in range(1, 21)}
P2.update({'R310': ('SFP_HDTX_P', 'SFP_TD_P'), 'R311': ('SFP_HDTX_N', 'SFP_TD_N'), 'R312': ('SFP_RD_P', 'SFP_HDRX_P'),
           'R313': ('SFP_RD_N', 'SFP_HDRX_N'), 'L30': ('3V3', 'SFP_VCCT'), 'L31': ('3V3', 'SFP_VCCR'),
           'C330': ('SFP_VCCT', G), 'C331': ('SFP_VCCT', G), 'C332': ('3V3', G), 'C333': ('SFP_VCCR', G),
           'C334': ('SFP_VCCR', G), 'C335': ('3V3', G),
           'R320': ('SFP_TX_FAULT', '3V3'), 'R321': ('SFP_LOS', '3V3'), 'R322': ('SFP_MOD_ABS', '3V3'),
           'R323': ('SFP_SCL', '3V3'), 'R324': ('SFP_SDA', '3V3'),
           'C340': ('SMA_HDTX_P', 'SMA_TX_P'), 'C341': ('SMA_HDTX_N', 'SMA_TX_N'), 'C342': ('SMA_RX_P', 'SMA_HDRX_P'),
           'C343': ('SMA_RX_N', 'SMA_HDRX_N')})
for j, n in (('J15', 'SMA_TX_P'), ('J16', 'SMA_TX_N'), ('J17', 'SMA_RX_P'), ('J18', 'SMA_RX_N')):
    BYNAME[j] = {'1': n, '2': G, '3': G, '4': G, '5': G}

# ---------------- B8: DDR3L ----------------
d = {'VDD': '1V35', 'VDDQ': '1V35', 'VSS': G, 'VSSQ': G, 'VREFCA': 'DDR_VREFCA', 'VREFDQ': 'DDR_VREFDQ', 'ZQ': 'DDR_ZQ',
     'A10/AP': 'DDRAM_A10', 'A12/BC#': 'DDRAM_A12', 'BA0': 'DDRAM_BA0', 'BA1': 'DDRAM_BA1', 'BA2': 'DDRAM_BA2',
     'RAS#': 'DDRAM_RAS_N', 'CAS#': 'DDRAM_CAS_N', 'WE#': 'DDRAM_WE_N', 'CS#': 'DDRAM_CS_N', 'CKE': 'DDRAM_CKE',
     'ODT': 'DDRAM_ODT', 'RESET#': 'DDRAM_RESET_N', 'CK': 'DDRAM_CLK_P', 'CK#': 'DDRAM_CLK_N',
     'LDQS': 'DDRAM_DQS_P0', 'LDQS#': 'DDRAM_DQS_N0', 'UDQS': 'DDRAM_DQS_P1', 'UDQS#': 'DDRAM_DQS_N1',
     'LDM': 'DDRAM_DM0', 'UDM': 'DDRAM_DM1'}
for i in range(15): d.setdefault(f'A{i}', f'DDRAM_A{i}')
for i in range(16): d[f'DQ{i}'] = f'DDRAM_DQ{i}'
BYNAME['U30'] = d; NC['U30'] = ['NC']
for c in ('C350', 'C351', 'C352', 'C353', 'C354', 'C355', 'C356', 'C357', 'C358', 'C359'): P2[c] = ('1V35', G)
for r1, r2, cc, n in (('R330', 'R331', 'C360', 'DDR_VREFCA'), ('R332', 'R333', 'C361', 'DDR_VREFDQ'),
                      ('R334', 'R335', 'C362', 'FPGA_VREF6'), ('R336', 'R337', 'C363', 'FPGA_VREF7')):
    P2[r1] = ('1V35', n); P2[r2] = (n, G); P2[cc] = (n, G)
P2.update({'R338': ('DDR_ZQ', G), 'R339': ('DDRAM_RESET_N', G), 'R340': ('DDRAM_CKE', G),
           'R341': ('DDRAM_CLK_P', 'DDR_CK_TERM'), 'R342': ('DDRAM_CLK_N', 'DDR_CK_TERM'), 'C364': ('DDR_CK_TERM', G)})

# ---------------- B9: Gigabit Ethernet ----------------
BYNAME['U31'] = {'MDIP0': 'ETH_MDI0_P', 'MDIN0': 'ETH_MDI0_N', 'MDIP1': 'ETH_MDI1_P', 'MDIN1': 'ETH_MDI1_N',
                 'MDIP2': 'ETH_MDI2_P', 'MDIN2': 'ETH_MDI2_N', 'MDIP3': 'ETH_MDI3_P', 'MDIN3': 'ETH_MDI3_N',
                 'AVDD10': 'ETH_1V0', 'DVDD10': 'ETH_1V0', 'AVDD33': '3V3', 'DVDD33': '3V3', 'DVDD_RG': '3V3',
                 'REG_OUT': 'ETH_REGOUT', 'PHYRSTB': 'ETH_RST_N', 'MDC': 'ETH_MDC', 'MDIO': 'ETH_MDIO',
                 'TXD3': 'ETH_TX_DATA3', 'TXD2': 'ETH_TX_DATA2', 'TXD1': 'ETH_TX_DATA1', 'TXD0': 'ETH_TX_DATA0',
                 'TXCTL': 'ETH_TX_CTL', 'TXC': 'ETH_TX_CLK', 'PHYAD0/RXD3': 'ETH_RX_DATA3', 'PLLOFF/RXD2': 'ETH_RX_DATA2',
                 'TXDLY/RXD1': 'ETH_RX_DATA1', 'RXDLY/RXD0': 'ETH_RX_DATA0', 'PHYAD2/RXCTL': 'ETH_RX_CTL',
                 'PHYAD1/RXC': 'ETH_RX_CLK', 'INTB/PMEB': 'ETH_INT_N', 'CFG_EXT/LED0': 'ETH_LED0',
                 'CFG_LDO0/LED1': 'ETH_LED1', 'CFG_LDO1/LED2': 'ETH_LED2', 'XTAL_IN': 'ETH_XI',
                 'XTAL_OUT/EXT_CLK': 'ETH_XO', 'RSET': 'ETH_RSET', 'GND': G}
NC['U31'] = ['CLKOUT']
BYNAME['J19'] = {'MDI0+': 'ETH_MDI0_P', 'MDI0-': 'ETH_MDI0_N', 'MDI1+': 'ETH_MDI1_P', 'MDI1-': 'ETH_MDI1_N',
                 'MDI2+': 'ETH_MDI2_P', 'MDI2-': 'ETH_MDI2_N', 'MDI3+': 'ETH_MDI3_P', 'MDI3-': 'ETH_MDI3_N',
                 'P1': 'ETH_CT', 'P10': 'ETH_CT', 'SHIELD0': G, 'SHIELD1': G,
                 '11': '3V3', '12': 'ETH_LED0_K', '13': 'ETH_LED1_A', '14': G}    # ✱ magjack CT/LED pins at A2
BYNAME['Y4'] = {'1': 'ETH_XI', '3': 'ETH_XO', 'GND': G}
P2.update({'C370': ('ETH_XI', G), 'C371': ('ETH_XO', G), 'L32': ('ETH_REGOUT', 'ETH_1V0'), 'C372': ('ETH_1V0', G),
           'C373': ('ETH_1V0', G), 'C374': ('ETH_1V0', G), 'C375': ('ETH_1V0', G), 'C376': ('3V3', G), 'C377': ('3V3', G),
           'C378': ('3V3', G), 'C379': ('3V3', G), 'C380': ('3V3', G), 'C381': ('ETH_CT', G), 'R350': ('ETH_RSET', G),
           'R351': ('ETH_RX_DATA3', '3V3'), 'R352': ('ETH_RX_CLK', G), 'R353': ('ETH_RX_CTL', G),
           'R354': ('ETH_RX_DATA2', G), 'R355': ('ETH_RX_DATA1', '3V3'), 'R356': ('ETH_RX_DATA0', '3V3'),
           'R357': ('ETH_LED0', '3V3'), 'R358': ('ETH_LED1', G), 'R359': ('ETH_LED2', G), 'R360': ('ETH_MDIO', '3V3'),
           'R361': ('ETH_RST_N', G), 'R362': ('ETH_INT_N', '3V3'), 'R363': ('ETH_LED0_K', 'ETH_LED0'),
           'R364': ('ETH_LED1', 'ETH_LED1_A')})

# ---------------- B10: USB 2.0 ULPI PHY, USB-C #2, microSD ----------------
u = {'CLKOUT': 'ULPI_CLK', 'NXT': 'ULPI_NXT', 'STP': 'ULPI_STP', 'DIR': 'ULPI_DIR', 'REFSEL0': '3V3', 'REFSEL1': '3V3',
     'REFSEL2': '3V3', 'CPEN': 'USB2_CPEN', 'DP': 'USB2_DP', 'DM': 'USB2_DN', 'VDD33': '3V3', 'VBAT': '3V3',
     'VBUS': 'USB2_VBUS_PHY', 'RBIAS': 'USB_RBIAS', 'XO': 'USB_XO', 'REFCLK': 'USB_XI', 'RESETB': 'ULPI_RST',
     'VDD18': '1V8', 'VDDIO': '3V3', 'EXP': G}            # REFSEL=111 -> 24 MHz (DS00001792A T5-10)
for i in range(8): u[f'DATA{i}'] = f'ULPI_DATA{i}'
BYNAME['U32'] = u; NC['U32'] = ['N/C', 'SPK_L', 'SPK_R', 'ID']
BYNAME['Y5'] = {'OSC1': 'USB_XI', 'OSC2': 'USB_XO', 'GND': G}
BYNAME['J20'] = {'GND': G, 'VBUS': 'USB2_VBUS', 'CC1': 'USB2_CC1', 'CC2': 'USB2_CC2', 'DP1': 'USB2_DP', 'DP2': 'USB2_DP',
                 'DN1': 'USB2_DN', 'DN2': 'USB2_DN', 'EH': G}
NC['J20'] = ['SBU1', 'SBU2']
BYNAME['U33'] = {'IN': '5V_SYS', 'OUT': 'USB2_VBUS', 'EN(EN#)': 'USB2_CPEN', 'GND': G}
NC['U33'] = ['FLT#']
BYNAME['J21'] = {'DAT2(RSV)': 'SD_DAT2', 'CDDAT3(CS)': 'SD_DAT3', 'CMD(DI)': 'SD_CMD', 'VDD': '3V3', 'CLK(SCLK)': 'SD_CLK_CARD',
                 'VSS': G, 'DAT0(D0)': 'SD_DAT0', 'DAT1(RSV)': 'SD_DAT1', 'GND': G, 'CD': 'SD_DET_N'}
P2.update({'C390': ('USB_XI', G), 'C391': ('USB_XO', G), 'R370': ('USB_XI', 'USB_XO'), 'R371': ('USB_RBIAS', G),
           'C392': ('3V3', G), 'C393': ('1V8', G), 'C394': ('1V8', G), 'C395': ('1V8', G), 'C396': ('3V3', G),
           'C397': ('3V3', G), 'R372': ('USB2_VBUS', 'USB2_VBUS_PHY'), 'C398': ('USB2_VBUS', G), 'R373': ('ULPI_RST', G),
           'R374': ('USB2_CC1', G), 'R375': ('USB2_CC2', G), 'R376': ('USB2_CC1', '5V_SYS'), 'R377': ('USB2_CC2', '5V_SYS'),
           'C399': ('5V_SYS', G), 'C400': ('USB2_VBUS', G), 'R380': ('SD_CMD', '3V3'), 'R381': ('SD_DAT0', '3V3'),
           'R382': ('SD_DAT1', '3V3'), 'R383': ('SD_DAT2', '3V3'), 'R384': ('SD_DAT3', '3V3'), 'R385': ('SD_DET_N', '3V3'),
           'R386': ('SD_CLK', 'SD_CLK_CARD'), 'C401': ('3V3', G), 'C402': ('3V3', G)})

# ---------------- B11: PMODs, LA header, loopback, test points ----------------
for j, k in (('J5', 1), ('J6', 2), ('J7', 3), ('J8', 4)):
    m = {str(p): f'PMOD{k}_{p}' for p in (1, 2, 3, 4, 7, 8, 9, 10)}; m.update({'5': G, '11': G, '6': '3V3', '12': '3V3'})
    BYNAME[j] = m
BYNAME['J9'] = {str(p): f'LA{p - 1}' for p in range(1, 9)}; BYNAME['J9'].update({'9': G, '10': G})
P2['J10'] = ('LOOP_A', 'LOOP_B')
for i, n in enumerate(['CLK_25MHZ', 'BTN_N0', 'UART_TX', 'UART_RX', 'I2C_SCL', 'I2C_SDA', 'FLASH_CLK', 'FLASH_CS_N',
                       'TP_PLL', 'DONE', 'INITN', 'PWR_ST'], 1):
    BYNAME[f'TP{i}'] = {'1': n}

# --- A2 fixes 2026-11-20 (datasheet checks)
BYNAME['J4'] = {'1': G, '2': 'JACK_R', '3': 'JACK_L'}         # PJ-313D: pad1=A sleeve, pad2=B ring, pad3=C tip
BYNAME['J19'].update({'P10': G, '14': '3V3', '13': 'ETH_LED1_K'})  # HR911130C: P10 = chassis side of 1nF/2kV; yellow LED 14 anode, 13 cathode
P2['R364'] = ('ETH_LED1', 'ETH_LED1_K')
# extra FPGA decoupling (B3) and SERDES aux rail
for i in range(450, 454): P2[f'C{i}'] = ('1V2', G)
for i in (454, 455): P2[f'C{i}'] = ('VCCAUX', G)
for i in range(456, 459): P2[f'C{i}'] = ('3V3', G)
for i in (459, 460): P2[f'C{i}'] = ('1V35', G)
P2['FB20'] = ('2V5', 'VCCAUXA')
for i in range(461, 466): P2[f'C{i}'] = ('VCCAUXA', G)
for i in range(466, 479): P2[f'C{i}'] = ('1V2_SER', G)
