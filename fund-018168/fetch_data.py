# -*- coding: utf-8 -*-
"""018168 国泰中证有色金属矿业主题ETF联接C 数据采集
数据源: 中证官网(指数历史/成分权重) + 百度股市通(个股PE/市值) + 新浪(财务指标/锂期货) + Yahoo(金属期货)
输出: data/report_data.json
"""
import json, os, time, re
import pandas as pd
import numpy as np
import requests
import akshare as ak

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)

TOP_STOCKS = [
    ("601899", "紫金矿业"), ("603993", "洛阳钼业"), ("600111", "北方稀土"),
    ("600988", "赤峰黄金"), ("601600", "中国铝业"), ("600489", "中金黄金"),
    ("600547", "山东黄金"), ("601168", "西部矿业"), ("002460", "赣锋锂业"),
    ("603799", "华友钴业"), ("000657", "中钨高新"), ("600549", "厦门钨业"),
    ("000807", "云铝股份"), ("000426", "兴业银锡"),
]

def fetch_yahoo(symbol, start_year=2015):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {"period1": int(pd.Timestamp(f"{start_year}-01-01").timestamp()),
              "period2": int(time.time()), "interval": "1d", "events": "div"}
    h = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    r = requests.get(url, params=params, headers=h, timeout=30)
    j = r.json()["chart"]["result"][0]
    ts = j["timestamp"]; close = j["indicators"]["quote"][0]["close"]
    df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").tz_localize(None).normalize(),
                       "close": close}).dropna()
    return df.drop_duplicates("date").set_index("date")["close"]

def main():
    out = {}
    # ---- 指数历史 + PE ----
    idx = pd.read_csv(os.path.join(DATA, "index_931892_hist.csv"), parse_dates=["日期"])
    idx = idx.sort_values("日期")
    last = idx.iloc[-1]
    out["index"] = {
        "code": "931892", "name": "中证有色金属矿业主题指数(有色矿业)",
        "latest_date": str(last["日期"].date()), "latest_close": float(last["收盘"]),
        "latest_pe": float(last["滚动市盈率"]) if pd.notna(last["滚动市盈率"]) else None,
    }
    pe = idx["滚动市盈率"].dropna()
    out["index"]["pe_percentile_since2016"] = round(float((pe <= pe.iloc[-1]).mean() * 100), 1)
    def perf(days_back=None, start=None):
        if start:
            base = idx[idx["日期"] >= start].iloc[0]
        else:
            if len(idx) <= days_back: return None
            base = idx.iloc[-days_back - 1]
        return round((float(last["收盘"]) / float(base["收盘"]) - 1) * 100, 1)
    out["index"]["perf"] = {
        "ytd_2026": perf(start="2026-01-01"),
        "y_1": perf(244), "y_2": perf(488), "y_3": perf(730),
        "since_inception_20230811": perf(start="2023-08-11"),
    }
    out["index"]["hist"] = [{"d": str(r["日期"].date()), "c": float(r["收盘"]),
                             "pe": None if pd.isna(r["滚动市盈率"]) else float(r["滚动市盈率"])}
                            for _, r in idx.iterrows()]
    # ---- 成分权重 ----
    w = ak.index_stock_cons_weight_csindex(symbol="931892")
    w = w[["成分券代码", "成分券名称", "权重", "日期"]].copy()
    w["权重"] = w["权重"].astype(float)
    out["weights"] = {"date": str(w.iloc[0]["日期"]),
                      "items": [{"code": r["成分券代码"], "name": r["成分券名称"],
                                 "weight": round(float(r["权重"]), 2)}
                                for _, r in w.sort_values("权重", ascending=False).iterrows()]}
    # ---- 个股 PE/市值/财务增速 ----
    stocks = []
    for code, name in TOP_STOCKS:
        rec = {"code": code, "name": name}
        try:
            p = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="近一年")
            rec["pe_ttm"] = float(p.iloc[-1]["value"])
            pv = p["value"].astype(float).dropna()
            rec["pe_range_1y"] = [round(float(pv.min()),1), round(float(pv.max()),1)]
        except Exception as e:
            rec["pe_ttm"] = None; print(code, name, "pe err", e)
        time.sleep(1.0)
        try:
            m = ak.stock_zh_valuation_baidu(symbol=code, indicator="总市值", period="近一年")
            rec["mktcap_yi"] = float(m.iloc[-1]["value"])
        except Exception:
            rec["mktcap_yi"] = None
        time.sleep(1.0)
        try:
            f = ak.stock_financial_analysis_indicator(symbol=code, start_year="2025")
            f = f.sort_values("日期")
            rows = []
            for _, fr in f.iterrows():
                rows.append({"date": str(fr["日期"])[:10],
                             "rev_g": None if fr["主营业务收入增长率(%)"] in ("", None) else float(fr["主营业务收入增长率(%)"]),
                             "np_g": None if fr["净利润增长率(%)"] in ("", None) else float(fr["净利润增长率(%)"]),
                             "roe": None if fr["净资产收益率(%)"] in ("", None) else float(fr["净资产收益率(%)"])})
            rec["fin"] = rows
        except Exception as e:
            rec["fin"] = []; print(code, name, "fin err", type(e).__name__)
        stocks.append(rec)
        print("done", code, name, rec.get("pe_ttm"), rec.get("mktcap_yi"))
    out["stocks"] = stocks
    # ---- 商品期货价格 ----
    comm = {}
    for key, sym, cn in [("gold","GC%3DF","COMEX黄金(美元/盎司)"),("silver","SI%3DF","COMEX白银(美元/盎司)"),
                          ("copper","HG%3DF","COMEX铜(美元/磅)"),("aluminum","ALI%3DF","COMEX铝(美元/吨)")]:
        try:
            s = fetch_yahoo(sym)
            comm[key] = {"name": cn, "series": [{"d": str(d.date()), "c": round(float(v),3)} for d, v in s.items() if d >= pd.Timestamp("2019-01-01")]}
            latest = float(s.iloc[-1])
            comm[key]["latest"] = round(latest, 2)
            comm[key]["chg_1y"] = round((latest/float(s.iloc[-245])-1)*100, 1) if len(s)>245 else None
            comm[key]["chg_3y"] = round((latest/float(s.iloc[-730])-1)*100, 1) if len(s)>730 else None
            comm[key]["ath"] = round(float(s.max()), 2)
            comm[key]["off_ath_pct"] = round((latest/float(s.max())-1)*100, 1)
        except Exception as e:
            print("comm err", key, e)
    # 碳酸锂 新浪
    try:
        lc = ak.futures_zh_daily_sina(symbol="LC0")
        lc["date"] = pd.to_datetime(lc["date"])
        lc = lc.set_index("date").sort_index()
        s = lc["close"].astype(float)
        comm["lithium"] = {"name": "碳酸锂期货(广期所,元/吨)",
                           "series": [{"d": str(d.date()), "c": round(float(v))} for d, v in s.items()],
                           "latest": round(float(s.iloc[-1])),
                           "chg_1y": round((float(s.iloc[-1])/float(s.iloc[-245])-1)*100,1) if len(s)>245 else None,
                           "high_2022": round(float(s.loc[:'2023'].max())),
                           }
    except Exception as e:
        print("lithium err", e)
    out["commodities"] = comm
    with open(os.path.join(DATA, "report_data.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False)
    print("saved report_data.json")

if __name__ == "__main__":
    main()
