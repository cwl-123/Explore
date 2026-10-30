import json, time, urllib.parse, urllib.request
import pandas as pd
import akshare as ak

UA={"User-Agent":"Mozilla/5.0","Referer":"https://data.eastmoney.com/"}
def get(url, params=None, headers=UA):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')

# constituents & weights
cons = ak.index_stock_cons_csindex(symbol="000688")
w = ak.index_stock_cons_weight_csindex(symbol="000688")
print(cons.shape, w.shape, w['日期'].iloc[0])
codes = [str(x) for x in w['成分券代码']]
cons.to_csv('data/cons.csv', index=False)
w.to_csv('data/weights.csv', index=False)

# valuation all on latest date
rows=[]
for i in range(1, 60):
    u=("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_VALUEANALYSIS_DET"
       "&columns=ALL&pageNumber=%d&pageSize=500&sortColumns=SECURITY_CODE&sortTypes=1"
       "&filter=(TRADE_DATE%%3D%%272026-10-30%%27)" % i)
    d=json.loads(get(u))
    data=d.get('result',{}).get('data') or []
    rows += [x for x in data if x['SECURITY_CODE'] in codes]
    if not data or i >= (d.get('result',{}).get('pages') or 0): break
val=pd.DataFrame(rows)
print('val', val.shape, val['SECURITY_CODE'].nunique())
val.to_csv('data/valuation.csv', index=False)

# per-stock reports
out=[]
for j,c in enumerate(codes):
    u=("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_LICO_FN_CPD"
       "&columns=ALL&pageNumber=1&pageSize=30&sortColumns=REPORTDATE&sortTypes=-1"
       "&filter=(SECURITY_CODE%%3D%%22%s%%22)" % c)
    try:
        d=json.loads(get(u))
        recs=d.get('result',{}).get('data') or []
        for x in recs:
            out.append({k:x.get(k) for k in ['SECURITY_CODE','SECURITY_NAME_ABBR','REPORTDATE','DATATYPE','TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','YSTZ','SJLTZ','WEIGHTAVG_ROE','BASIC_EPS','BPS','BOARD_NAME','NOTICE_DATE','UPDATE_DATE']})
        print(j+1, c, recs[0]['REPORTDATE'][:10] if recs else None)
    except Exception as e:
        print('ERR', c, e)
    time.sleep(0.12)
fin=pd.DataFrame(out)
fin.to_csv('data/financials.csv', index=False)
print('fin', fin.shape)
