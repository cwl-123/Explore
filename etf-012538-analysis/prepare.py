# -*- coding: utf-8 -*-
import json, math
import pandas as pd, numpy as np

D = '/Users/chenweilong/Explore/etf-012538-analysis/data'
meta = json.load(open(f'{D}/meta.json'))
val = json.load(open(f'{D}/valuation.json'))
yjbb = json.load(open(f'{D}/yjbb.json'))

# ---- 指数 000813 ----
idx = pd.read_csv(f'{D}/index_000813.csv', parse_dates=['日期'])
idx = idx.sort_values('日期').reset_index(drop=True)
idx['pct'] = idx['滚动市盈率'].expanding().rank(pct=True) * 100
w = idx[idx['日期'] >= '2012-01-01'].copy()
w = w.iloc[::3]  # 每3个交易日取1个
idx_series = [[r['日期'].strftime('%Y-%m-%d'), round(float(r['收盘']),1),
               round(float(r['滚动市盈率']),2) if pd.notna(r['滚动市盈率']) else None,
               round(float(r['pct']),1) if pd.notna(r['pct']) else None] for _, r in w.iterrows()]
last = idx.iloc[-1]
idx_now = {'date': last['日期'].strftime('%Y-%m-%d'), 'close': float(last['收盘']),
           'pe': float(last['滚动市盈率']), 'pct': float(last['pct'])}
# 近10年分位
sub = idx[idx['日期'] >= '2016-09-01']
idx_now['pct10y'] = float((sub['滚动市盈率'] < last['滚动市盈率']).mean() * 100)

# ---- ETF 516020 日线 ----
etf = pd.read_csv(f'{D}/etf_516020_hist.csv', parse_dates=['date'])
etf_series = [[r['date'].strftime('%Y-%m-%d'), round(float(r['close']),4)] for _, r in etf.iloc[::2].iterrows()]
if etf_series[-1][0] != etf.iloc[-1]['date'].strftime('%Y-%m-%d'):
    etf_series.append([etf.iloc[-1]['date'].strftime('%Y-%m-%d'), round(float(etf.iloc[-1]['close']),4)])

# ---- 012538 净值 ----
nav = json.load(open(f'{D}/nav_012538.json'))

# ---- 原油(周采样) ----
def weekly(path):
    rows = json.load(open(f'{D}/{path}.json'))
    df = pd.DataFrame(rows, columns=['date','close']).sort_values('date').reset_index(drop=True)
    df = df.iloc[::5]
    if df.iloc[-1]['date'] != rows[-1][0]:
        df = pd.concat([df, df.iloc[[-1]]])
    return [[r['date'][:10], r['close']] for _, r in df.iterrows()]
wti = weekly('wti'); brent = weekly('brent')

# ---- 个股 ----
def g(date, code, field):
    v = yjbb.get(date, {}).get(code)
    return None if v is None or v.get(field) is None else round(float(v[field]), 2)

stocks = []
for c in meta['codes']:
    v = val.get(c, {})
    pe_s = v.get('市盈率(TTM)', {}).get('series', [])
    pe_vals = [x[1] for x in pe_s if x[1] is not None]
    pe_now = v.get('市盈率(TTM)', {}).get('latest')
    pe_pct = round(sum(1 for x in pe_vals if x <= pe_now) / len(pe_vals) * 100, 1) if pe_vals and pe_now else None
    # 2026Q2 单季净利同比
    q2 = None
    try:
        h1_26 = yjbb['20260630'][c]['净利润-净利润']; q1_26 = yjbb['20260331'][c]['净利润-净利润']
        h1_25 = yjbb['20250630'][c]['净利润-净利润']; q1_25 = yjbb['20250331'][c]['净利润-净利润']
        s26, s25 = h1_26 - q1_26, h1_25 - q1_25
        if s25 and abs(s25) > 1e6:
            q2 = round((s26 / s25 - 1) * 100, 1) if s25 > 0 else (None if s26 <= 0 else 999)
        elif s26 and s26 > 0:
            q2 = 999
    except Exception:
        pass
    stocks.append({
        'code': c, 'name': meta['names'][c], 'weight': meta['weights'][c],
        'mktcap': v.get('总市值', {}).get('latest'),
        'pe': pe_now, 'pb': v.get('市净率', {}).get('latest'), 'pe_pct5y': pe_pct,
        'rev_25': g('20251231', c, '营业总收入-同比增长'), 'np_25': g('20251231', c, '净利润-同比增长'),
        'rev_26q1': g('20260331', c, '营业总收入-同比增长'), 'np_26q1': g('20260331', c, '净利润-同比增长'),
        'rev_26h1': g('20260630', c, '营业总收入-同比增长'), 'np_26h1': g('20260630', c, '净利润-同比增长'),
        'np_26q2': q2,
        'roe_26h1': g('20260630', c, '净资产收益率'), 'gm_26h1': g('20260630', c, '销售毛利率'),
        'roe_25': g('20251231', c, '净资产收益率'),
    })

# 2025Q1 vs 2026Q2 权重对比(取两期都在前列的)
h25 = pd.read_csv(f'{D}/holdings_516020.csv', dtype={'股票代码': str})  # 已是2026Q2
data = {
    'meta': {
        'fund': '华宝中证细分化工产业主题ETF联接C（012538）',
        'etf': '化工ETF（516020，成立2021-02-26）',
        'index': '中证细分化工产业主题指数（000813，50只成分股）',
        'nav': nav[-1][1], 'nav_date': nav[-1][0],
        'inception': '2021-06-24',
        'idx_now': idx_now,
        'gen_date': '2026-09-29',
    },
    'idx_series': idx_series, 'etf_series': etf_series, 'nav': nav,
    'wti': wti, 'brent': brent, 'stocks': stocks,
}
json.dump(data, open(f'{D}/page_data.json', 'w'), ensure_ascii=False)
print('idx_now', idx_now)
for s in stocks:
    print(s['name'], s['weight'], s['pe'], s['pe_pct5y'], s['np_25'], s['np_26q1'], s['np_26h1'], s['np_26q2'], s['roe_26h1'])
