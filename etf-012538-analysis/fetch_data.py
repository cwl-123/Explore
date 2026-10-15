# -*- coding: utf-8 -*-
"""化工ETF(516020/012538) 成分股数据抓取"""
import json, time
import pandas as pd
import akshare as ak

OUT = '/Users/chenweilong/Explore/etf-012538-analysis/data'

hold = pd.read_csv(f'{OUT}/holdings_516020.csv', dtype={'股票代码': str})
hold['股票代码'] = hold['股票代码'].str.zfill(6)
top = hold.sort_values('占净值比例', ascending=False).head(15)
codes = top['股票代码'].tolist()
names = dict(zip(top['股票代码'], top['股票名称']))
weights = dict(zip(top['股票代码'], top['占净值比例']))

# 1) 业绩报表: 2024年报 / 2025各季 / 2026各季
report = {}
for date in ['20241231', '20250331', '20250630', '20250930', '20251231', '20260331', '20260630']:
    try:
        df = ak.stock_yjbb_em(date=date)
        df['股票代码'] = df['股票代码'].astype(str).str.zfill(6)
        sub = df[df['股票代码'].isin(codes)][['股票代码', '营业总收入-营业总收入', '营业总收入-同比增长', '净利润-净利润', '净利润-同比增长', '净资产收益率', '销售毛利率']]
        report[date] = sub.set_index('股票代码').to_dict('index')
        print('yjbb', date, len(sub))
    except Exception as e:
        print('yjbb ERR', date, repr(e)[:100])
    time.sleep(1)
json.dump(report, open(f'{OUT}/yjbb.json', 'w'), ensure_ascii=False, default=float)

# 2) 百度估值: PE-TTM 当前+历史, 市净率, 总市值
val = {}
for c in codes:
    d = {}
    for ind in ['市盈率(TTM)', '市净率', '总市值']:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=c, indicator=ind, period='近五年')
            d[ind] = {'latest': float(df.iloc[-1]['value']), 'date': str(df.iloc[-1]['date']),
                      'series': [[str(r['date']), float(r['value'])] for _, r in df.iterrows()]}
        except Exception as e:
            print('val ERR', c, ind, repr(e)[:80])
        time.sleep(0.5)
    val[c] = d
    print('val', c, names[c], {k: v.get('latest') for k, v in d.items()})
json.dump(val, open(f'{OUT}/valuation.json', 'w'), ensure_ascii=False)

# 3) ETF 516020 价格(新浪)
try:
    df = ak.fund_etf_hist_sina(symbol='sh516020')
    df.to_csv(f'{OUT}/etf_516020_hist.csv', index=False)
    print('etf hist', len(df), df.tail(1).to_string())
except Exception as e:
    print('etf ERR', repr(e)[:150])

json.dump({'codes': codes, 'names': names, 'weights': weights}, open(f'{OUT}/meta.json', 'w'), ensure_ascii=False)
print('DONE')
