"""LATFUN6 part availability check against the JLCPCB parts API (no auth).
Usage: python lcsc_stock_check.py "kw1" "kw2" ...   (or no args = default list)"""
import json, sys, urllib.request

URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"

def search(kw, n=4):
    req = urllib.request.Request(URL, data=json.dumps({"keyword": kw, "pageSize": n, "currentPage": 1}).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["data"]["componentPageInfo"]

def cls(it):
    if it["stockCount"] == 0: return "ZERO_STOCK"
    return "BASIC" if it["componentLibraryType"] == "base" else "EXTENDED"

DEFAULT = ["LFE5U-25F-6BG256C", "LFE5U-45F-6BG256C", "FT2232HL", "FT2232HQ", "93LC56BT-I/OT",
           "W25Q128JVSIQ", "AT24C02C-SSHM-T", "25MHz oscillator 3225", "12MHz crystal 3225",
           "TLV62569DBVR", "SY8089AAAC", "RT9013-25GB", "AP2112K-2.5TRG1", "TYPE-C-31-M-12",
           "HDMI-001", "TPD4E05U06DQAR", "PCA9306DCUR", "TPS2051CDBVR", "PJ-320A", "SMF5.0A",
           "USBLC6-2SC6", "SN74LVC1T45"]

for kw in (sys.argv[1:] or DEFAULT):
    try:
        info = search(kw)
    except Exception as e:
        print(f"## {kw}: ERROR {e}"); continue
    print(f"## {kw}  (total {info['total']})")
    for it in (info["list"] or [])[:4]:
        c = it.get("componentCode") or ("C" + (it.get("lcscGoodsUrl") or "_C?").split("_C")[-1].replace(".html", ""))
        p = it["componentPrices"][0]["productPrice"] if it.get("componentPrices") else None
        print(f"   {c:<10} {cls(it):<10} stock={it['stockCount']:<8} ${p}  {it.get('componentModelEn','')} | {it['erpComponentName'][:70]}")
