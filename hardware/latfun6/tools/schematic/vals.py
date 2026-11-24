import sqlite3,symlib,os
con=sqlite3.connect('file:'+os.environ.get('EPRJ','hardware/EDA/Latfun6.eprj')+'?mode=ro',uri=True)
DA={}
for u,k,v in con.execute("select device_uuid,key,value from attributes"):
    DA.setdefault(u,{})[k]=v
def values(page):
    L,C,A=symlib.page(page); out={}
    for cid,a in A.items():
        d=a.get('Designator'); dev=DA.get(a.get('Device'),{})
        out[d]=(dev.get('Value') or dev.get('Manufacturer Part'), dev.get('Supplier Part'))
    return out
