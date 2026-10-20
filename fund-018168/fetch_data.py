# -*- coding: utf-8 -*-
"""018168 国泰中证有色金属矿业主题ETF联接C —— 数据采集（2026-10 体检版）

数据源：
  中证指数官网      指数历史行情 + 滚动市盈率（931892）、成分权重（月度）、沪深300 对照
  新浪财经          个股日线（不复权，JSON 接口，不走 py_mini_racer）、商品期货主力连续
  百度股市通        个股 PE-TTM / 总市值
  Yahoo Finance     美元指数、美债 10Y、COMEX 金/银/铜

输出：data/report_data.json（gen_report.py 的唯一输入）
运行：hs300-strategy-lab/.venv/bin/python fund-018168/fetch_data.py
"""
import json, os, time
import numpy as np
import pandas as pd
import requests
import akshare as ak

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

IDX = "931892"
PE_START = "2022-05-13"          # 中证该指数滚动 PE 数据起点（此前为空）
SINA_KLINE = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"

# 分组（按主营金属归类，权重合计见报告）
GROUPS = {
    "铜": ["601899", "603993", "601168", "000630", "600362", "000878", "600711", "601020"],
    "金": ["600988", "600489", "600547", "000975", "002155"],
    "银锡": ["000426", "002716", "601212", "000960", "600301"],
    "铝": ["601600", "000807", "002532"],
    "稀土": ["600111", "000831", "600392"],
    "钨钼锗钛": ["000657", "600549", "601958", "002428", "600456", "002167"],
    "锂钴": ["002460", "002466", "603799", "002738", "002756"],
    "其他": ["001280", "002978"],
}
CODE2GROUP = {c: g for g, cs in GROUPS.items() for c in cs}

PE_TOP_N = 20  # 前 N 大权重取百度 PE/市值（覆盖约 85% 权重）


def pct(cur, base):
    return None if not base else round((cur / base - 1) * 100, 1)


def get(url, **kw):
    return requests.get(url, headers=UA, timeout=30, **kw)


# ---------------------------------------------------------------- 指数
def fetch_index():
    df = ak.stock_zh_index_hist_csindex(symbol=IDX, start_date="20160101", end_date="20261231")
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").drop_duplicates("日期", keep="last")
    df["收盘"] = pd.to_numeric(df["收盘"], errors="coerce")
    df["滚动市盈率"] = pd.to_numeric(df["滚动市盈率"], errors="coerce")
    df = df.dropna(subset=["收盘"]).set_index("日期")
    df[["收盘", "滚动市盈率", "成交量"]].to_csv(os.path.join(DATA, "index_931892_hist.csv"))
    close = df["收盘"].astype(float)
    pe = df["滚动市盈率"]
    eps = close / pe                      # 指数点位 / PE = 滚动 EPS（指数点口径）
    last = close.iloc[-1]
    peak_date = close.idxmax()
    peak = close.max()
    post = close[close.index >= peak_date]
    perf = {}
    for n, k in [(5, "w1"), (10, "w2"), (20, "m1"), (60, "m3"), (120, "m6"), (244, "y1"), (488, "y2")]:
        perf[k] = pct(last, close.iloc[-n - 1]) if len(close) > n else None
    ytd_base = close[close.index >= "2026-01-01"].iloc[0]
    perf["ytd"] = pct(last, ytd_base)

    # 历史两轮大熊（数据实测的峰谷）
    def seg(a, b):
        s = close.loc[a:b]
        return {"peak_date": str(s.idxmax().date()), "peak": round(float(s.max()), 0),
                "trough_date": str(s.idxmin().date()), "trough": round(float(s.min()), 0),
                "dd": round((float(s.min()) / float(s.max()) - 1) * 100, 1),
                "months": round((s.idxmin() - s.idxmax()).days / 30.44, 1)}
    bears = [seg("2017-01-01", "2019-01-31"), seg("2021-06-01", "2024-06-30")]
    for b in bears:
        t = pd.Timestamp(b["trough_date"])
        fut = close[close.index >= t]
        b["after_12m"] = pct(float(fut.iloc[min(244, len(fut) - 1)]), float(fut.iloc[0])) if len(fut) > 60 else None
    # 回撤对齐（画图用）：每轮熊市从峰值起算的月度路径
    dd_paths = []
    for b in bears + [{"peak_date": str(peak_date.date()), "label": "本轮"}]:
        s = close[close.index >= b["peak_date"]]
        base = float(s.iloc[0])
        months, vals, last_m = [], [], None
        for d, v in s.items():
            m = round((d - s.index[0]).days / 30.44, 2)
            if m != last_m:
                months.append(m); vals.append(round(v / base * 100, 1)); last_m = m
        dd_paths.append({"peak_date": b["peak_date"], "label": b.get("label", ""), "m": months, "v": vals})

    # 基础概率：距高点同一回撤区间，未来 1/3/6/12 个月
    ddser = (close / close.cummax() - 1) * 100
    def fwd(lo, hi):
        mask = (ddser >= lo) & (ddser <= hi)
        idxs = close.index[mask.values]
        out = {}
        for h, k in [(20, "m1"), (60, "m3"), (120, "m6"), (244, "y12")]:
            rets = []
            for d in idxs:
                p = close.index.get_loc(d)
                if p + h < len(close):
                    rets.append((close.iloc[p + h] / close.iloc[p] - 1) * 100)
            if not rets:
                continue
            a = np.array(rets)
            out[k] = {"median": round(float(np.median(a)), 1), "win": round(float((a > 0).mean() * 100), 0),
                      "best": round(float(a.max()), 1), "worst": round(float(a.min()), 1), "n": int(len(a))}
        return out
    base = {"dd_35_45": fwd(-45, -35), "dd_40_50": fwd(-50, -40), "dd_45_60": fwd(-60, -45)}

    # 年度收益
    ann = (df["收盘"].resample("Y").last().pct_change() * 100).dropna().round(1)

    hist = [{"d": str(d.date()), "c": round(float(v), 2),
             "pe": None if pd.isna(pe.loc[d]) else round(float(pe.loc[d]), 2)}
            for d, v in close.items()]
    pev = pe.dropna()
    return {
        "code": IDX, "name": "中证有色金属矿业主题指数",
        "latest_date": str(close.index[-1].date()), "close": round(float(last), 2),
        "pe": round(float(pev.iloc[-1]), 2), "eps": round(float(eps.dropna().iloc[-1]), 1),
        "pe_date": str(pev.index[-1].date()),
        "peak": {"date": str(peak_date.date()), "close": round(float(peak), 0),
                 "pe": round(float(pe.loc[peak_date]), 2) if pd.notna(pe.loc[peak_date]) else None},
        "dd": round(float(last / peak - 1) * 100, 1),
        "low_since_peak": {"date": str(post.idxmin().date()), "close": round(float(post.min()), 0),
                           "dd": round(float(post.min() / peak - 1) * 100, 1)},
        "months_since_peak": round((close.index[-1] - peak_date).days / 30.44, 1),
        "pe_stats": {"median": round(float(pev.median()), 2), "p25": round(float(pev.quantile(.25)), 2),
                     "p75": round(float(pev.quantile(.75)), 2), "min": round(float(pev.min()), 2),
                     "min_date": str(pev.idxmin().date()), "max": round(float(pev.max()), 2),
                     "max_date": str(pev.idxmax().date()), "start": PE_START,
                     "pct": round(float((pev <= pev.iloc[-1]).mean() * 100), 1)},
        "perf": perf, "annual": {str(k.year): v for k, v in ann.items()},
        "bears": bears, "dd_paths": dd_paths, "base_rates": base, "hist": hist,
    }


# ---------------------------------------------------------------- 权重
def fetch_weights():
    w = ak.index_stock_cons_weight_csindex(symbol=IDX)
    w = w[["成分券代码", "成分券名称", "权重", "日期"]].copy()
    w["权重"] = w["权重"].astype(float)
    d = str(pd.Timestamp(w.iloc[0]["日期"]).date())
    items = [{"code": r["成分券代码"], "name": r["成分券名称"], "weight": round(float(r["权重"]), 2),
              "group": CODE2GROUP.get(r["成分券代码"], "其他")}
             for _, r in w.sort_values("权重", ascending=False).iterrows()]
    return {"date": d, "items": items}


# ---------------------------------------------------------------- 个股行情
def fetch_stock_px(codes):
    out = {}
    for code in codes:
        sym = ("sh" if code[0] in "67" else "sz") + code
        try:
            r = get(SINA_KLINE, params={"symbol": sym, "scale": 240, "ma": "no", "datalen": 1600})
            arr = json.loads(r.text)
            s = pd.Series([float(x["close"]) for x in arr],
                          index=pd.to_datetime([x["day"] for x in arr])).sort_index()
            out[code] = s[~s.index.duplicated()]
        except Exception as e:
            print("px err", code, type(e).__name__, str(e)[:80])
    return out


def stock_stats(code, s, w, peak_date):
    last = float(s.iloc[-1])
    def chg(n):
        return pct(last, float(s.iloc[-n - 1])) if len(s) > n else None
    ytd = s[s.index >= "2026-01-01"]
    hi = s.loc[s.index >= s.index[-1] - pd.Timedelta(days=365)]
    pk = s.loc[:peak_date].iloc[-1] if len(s.loc[:peak_date]) else None
    return {
        "code": code, "weight": w, "last": round(last, 2),
        "m1": chg(20), "m3": chg(60), "m6": chg(120), "y1": chg(244),
        "ytd": pct(last, float(ytd.iloc[0])) if len(ytd) else None,
        "off_hi1y": pct(last, float(hi.max())),
        "hi1y_date": str(hi.idxmax().date()),
        "since_peak": pct(last, float(pk)) if pk else None,
    }


# ---------------------------------------------------------------- 个股估值 / 财务
def fetch_valuation(code):
    rec = {}
    try:
        p = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="近一年")
        v = pd.to_numeric(p["value"], errors="coerce").dropna()
        rec["pe"] = round(float(v.iloc[-1]), 2)
        rec["pe_range"] = [round(float(v.min()), 1), round(float(v.max()), 1)]
    except Exception as e:
        print("pe err", code, type(e).__name__)
    time.sleep(0.8)
    try:
        m = ak.stock_zh_valuation_baidu(symbol=code, indicator="总市值", period="近一年")
        rec["mktcap"] = round(float(pd.to_numeric(m["value"], errors="coerce").dropna().iloc[-1]), 0)
    except Exception:
        pass
    time.sleep(0.8)
    try:
        f = ak.stock_financial_analysis_indicator(symbol=code, start_year="2025").sort_values("日期")
        def num(x):
            try:
                return None if x in ("", None, "--") else round(float(x), 1)
            except Exception:
                return None
        rows = [{"date": str(r["日期"])[:10],
                 "rev_g": num(r["主营业务收入增长率(%)"]),
                 "np_g": num(r["净利润增长率(%)"]),
                 "roe": num(r["净资产收益率(%)"])} for _, r in f.iterrows()]
        rec["fin"] = rows
    except Exception as e:
        rec["fin"] = []
        print("fin err", code, type(e).__name__)
    return rec


# ---------------------------------------------------------------- 商品
FUT = [("CU0", "沪铜", "元/吨"), ("AL0", "沪铝", "元/吨"), ("AU0", "沪金", "元/克"),
       ("AG0", "沪银", "元/千克"), ("LC0", "碳酸锂", "元/吨"), ("SN0", "沪锡", "元/吨"),
       ("ZN0", "沪锌", "元/吨"), ("NI0", "沪镍", "元/吨")]


def fetch_commodities():
    out = {}
    for sym, name, unit in FUT:
        try:
            d = ak.futures_zh_daily_sina(symbol=sym)
            d["date"] = pd.to_datetime(d["date"])
            c = pd.to_numeric(d.set_index("date").sort_index()["close"], errors="coerce").dropna()
            last = float(c.iloc[-1])
            def chg(n):
                return pct(last, float(c.iloc[-n - 1])) if len(c) > n else None
            def at(ts):
                s = c.loc[:ts]
                return float(s.iloc[-1]) if len(s) else None
            q = c.resample("Q").mean()
            out[sym] = {
                "name": name, "unit": unit, "latest": round(last, 2),
                "w1": chg(5), "m1": chg(20), "m3": chg(60), "m6": chg(120), "y1": chg(244),
                "ytd": pct(last, float(c[c.index >= "2026-01-01"].iloc[0])),
                "ath": round(float(c.max()), 2), "ath_date": str(c.idxmax().date()),
                "off_ath": pct(last, float(c.max())),
                "vs_peak_day": pct(last, at("2026-01-29")),
                "q_series": [{"q": str(i.date()), "v": round(float(v), 1)} for i, v in q.dropna().tail(8).items()],
                "series": [{"d": str(d.date()), "c": round(float(v), 2)} for d, v in c.items()
                           if d >= pd.Timestamp("2024-01-01")],
            }
        except Exception as e:
            print("comm err", sym, type(e).__name__, str(e)[:80])
    return out


# ---------------------------------------------------------------- 宏观 / 对照
def yahoo(sym, rng="3y"):
    r = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d")
    j = r.json()["chart"]["result"][0]
    s = pd.Series(j["indicators"]["quote"][0]["close"],
                  index=pd.to_datetime(j["timestamp"], unit="s").tz_localize(None).normalize()).dropna()
    return s[~s.index.duplicated()]


def fetch_macro():
    out = {}
    for sym, name, unit in [("DX-Y.NYB", "美元指数", ""), ("^TNX", "美债10Y收益率", "%"),
                            ("GC=F", "COMEX黄金", "美元/盎司"), ("SI=F", "COMEX白银", "美元/盎司"),
                            ("HG=F", "COMEX铜", "美元/磅")]:
        try:
            s = yahoo(sym)
            last = float(s.iloc[-1])
            y = s[s.index >= "2026-01-01"]
            out[sym] = {"name": name, "unit": unit, "latest": round(last, 2),
                        "m1": pct(last, float(s.iloc[-21])), "m3": pct(last, float(s.iloc[-61])),
                        "ytd": pct(last, float(y.iloc[0])) if len(y) else None,
                        "peak": round(float(s.max()), 2), "peak_date": str(s.idxmax().date()),
                        "off_peak": pct(last, float(s.max())), "date": str(s.index[-1].date())}
        except Exception as e:
            print("macro err", sym, type(e).__name__, str(e)[:80])
    try:
        d = ak.stock_zh_index_hist_csindex(symbol="000300", start_date="20240101", end_date="20261231")
        d["日期"] = pd.to_datetime(d["日期"])
        c = pd.to_numeric(d.set_index("日期").sort_index()["收盘"], errors="coerce").dropna()
        last = float(c.iloc[-1])
        out["hs300"] = {"name": "沪深300", "latest": round(last, 0), "date": str(c.index[-1].date()),
                        "m1": pct(last, float(c.iloc[-21])), "m3": pct(last, float(c.iloc[-61])),
                        "ytd": pct(last, float(c[c.index >= "2026-01-01"].iloc[0])),
                        "y1": pct(last, float(c.iloc[-245]))}
    except Exception as e:
        print("hs300 err", type(e).__name__)
    return out


# ---------------------------------------------------------------- 汇总
def main():
    idx = fetch_index()
    print("index", idx["latest_date"], idx["close"], "PE", idx["pe"], "dd", idx["dd"])
    weights = fetch_weights()
    print("weights", weights["date"], len(weights["items"]))
    codes = [x["code"] for x in weights["items"]]
    px = fetch_stock_px(codes)
    name2 = {x["code"]: x["name"] for x in weights["items"]}

    stocks = []
    for it in weights["items"]:
        c = it["code"]
        if c not in px:
            continue
        rec = stock_stats(c, px[c], it["weight"], idx["peak"]["date"])
        rec["name"] = it["name"]; rec["group"] = it["group"]
        stocks.append(rec)

    # 估值 / 财务：前 N 大权重
    for i, s in enumerate(sorted(stocks, key=lambda x: -x["weight"])[:PE_TOP_N]):
        v = fetch_valuation(s["code"])
        s.update(v)
        print("val", i + 1, s["code"], s["name"], s.get("pe"), s.get("mktcap"))

    # 贡献度（贡献 = 权重 × 涨跌幅 / 100）
    for s in stocks:
        s["contrib_1m"] = round(s["weight"] * (s["m1"] or 0) / 100, 2)
        s["contrib_since"] = round(s["weight"] * (s["since_peak"] or 0) / 100, 2)

    groups = []
    for g, cs in GROUPS.items():
        sub = [s for s in stocks if s["code"] in cs]
        if not sub:
            continue
        wsum = sum(s["weight"] for s in sub)
        def wavg(k):
            return round(sum(s["weight"] * (s[k] or 0) for s in sub) / wsum, 1)
        groups.append({"name": g, "n": len(sub), "weight": round(wsum, 1), "m1": wavg("m1"), "m3": wavg("m3"),
                       "ytd": wavg("ytd"), "y1": wavg("y1"), "since_peak": wavg("since_peak"),
                       "off_hi1y": wavg("off_hi1y")})
    for g in groups:
        g["contrib_1m"] = round(g["weight"] * g["m1"] / 100, 1)
        g["contrib_since"] = round(g["weight"] * g["since_peak"] / 100, 1)
    groups.sort(key=lambda x: -x["weight"])

    out = {
        "meta": {"asof": idx["latest_date"], "weights_date": weights["date"],
                 "pe_start": PE_START, "fund": "018168 国泰中证有色金属矿业主题ETF联接C",
                 "index": "931892 中证有色金属矿业主题指数（38 只成分股）"},
        "index": idx,
        "weights": weights,
        "groups": groups,
        "stocks": sorted(stocks, key=lambda x: -x["weight"]),
        "commodities": fetch_commodities(),
        "macro": fetch_macro(),
    }
    with open(os.path.join(DATA, "report_data.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    print("saved", os.path.join(DATA, "report_data.json"),
          "%.0f KB" % (os.path.getsize(os.path.join(DATA, "report_data.json")) / 1024))


if __name__ == "__main__":
    main()
