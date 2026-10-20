#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""化工行业体检报告（2026 年 10 月）生成器 —— 仅标准库

用法：
    python3 build.py            # 抓数（当日缓存，失败回退旧缓存）→ 计算 → 生成 index.html
    python3 build.py --offline  # 只用本地缓存，不联网
    # 生成后回仓库根目录跑一次：python3 build_site.py（注入导航 + 更新门户）

数据源：
    - 指数：中证指数官网 index-perf API（000813 中证细分化工 / 000300 沪深300，含官方滚动市盈率）
    - 行情：新浪财经（516020 ETF、20 只成分股日线、商品期货连续合约、布伦特原油连续）
    - 业绩：复用上一版 2026 中报缓存 etf-012538-analysis/data/yjbb.json（2026Q3 报 10 月底才披露）
    - 权重：etf-012538-analysis/data/holdings_516020.csv（2026Q2）

口径：
    - 隐含 TTM EPS = 收盘价 / 官方滚动市盈率，用于把涨跌拆成「盈利」与「估值」两部分
    - PE 分位用滚动窗口（全样本 / 10 年 / 5 年 / 2.5 年），只用当日及之前数据，无前视
    - 情景概率为主观判断（依据估值分位 + 历史同类样本），不是预测，不构成投资建议
"""
import csv
import json
import os
import sys
import time
import datetime as dt
import statistics as st
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "index.html")
OLD = os.path.join(ROOT, "..", "etf-012538-analysis", "data")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
OFFLINE = "--offline" in sys.argv
TODAY = dt.date.today()


# --------------------------------------------------------------------- 抓取
def _get(url, referer="https://finance.sina.com.cn", timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def _path(name):
    return os.path.join(DATA, name)


def _fresh(path):
    return os.path.exists(path) and dt.date.fromtimestamp(os.path.getmtime(path)) == TODAY


def fetch(name, url, parser, referer="https://finance.sina.com.cn"):
    """当日缓存直接用；否则抓取，失败回退旧缓存"""
    path = _path(name)
    if OFFLINE or _fresh(path):
        if not os.path.exists(path):
            raise SystemExit("缺少缓存：%s（先联网跑一次）" % path)
        return json.load(open(path))
    try:
        rows = parser(_get(url, referer))
        json.dump(rows, open(path, "w"), ensure_ascii=False)
        return rows
    except Exception as e:  # noqa: BLE001
        print("  ! %s 抓取失败（%s），回退旧缓存" % (name, repr(e)[:90]))
        return json.load(open(path))


def p_csindex(t):
    """压缩存储：[[日期, 收盘, 滚动PE, 成交额(亿元)]]"""
    out = []
    for r in json.loads(t)["data"]:
        out.append([r.get("tradeDate"), r.get("close"),
                    r.get("peg"), r.get("tradingValue")])
    return out


def p_sina_futures(t):
    """压缩存储：[[日期, 收盘]]"""
    rows = json.loads(t.split("=(", 1)[1].rsplit(");", 1)[0])
    return [[r["d"], float(r["c"])] for r in rows]


def p_brent(t):
    rows = json.loads(t.split("=(", 1)[1].rsplit(");", 1)[0])
    return [[r["date"], float(r["close"])] for r in rows]


def load_index(code):
    rows = fetch("csindex_%s.json" % code,
                 "https://www.csindex.com.cn/csindex-home/perf/index-perf"
                 "?indexCode=%s&startDate=20120101&endDate=20991231" % code,
                 p_csindex, referer="https://www.csindex.com.cn/")
    rows = [r for r in rows if r[1] and r[0]]
    rows.sort(key=lambda r: r[0])
    return {
        "date": [r[0].replace("-", "") for r in rows],
        "close": [float(r[1]) for r in rows],
        "pe": [float(r[2]) if r[2] else None for r in rows],
        "turnover": [float(r[3] or 0) for r in rows],
    }


STOCK_LIST = [
    ("600309", "万华化学", "聚氨酯·一体化"),
    ("600160", "巨化股份", "制冷剂"),
    ("603379", "三美股份", "制冷剂"),
    ("600378", "昊华科技", "氟化工·含氟材料"),
    ("002709", "天赐材料", "锂电材料"),
    ("002407", "多氟多", "六氟磷酸锂"),
    ("002812", "恩捷股份", "隔膜"),
    ("300037", "新宙邦", "电解液"),
    ("601208", "东材科技", "电子材料"),
    ("600989", "宝丰能源", "煤制烯烃"),
    ("600426", "华鲁恒升", "煤化工"),
    ("002648", "卫星化学", "轻烃·C2C3"),
    ("000792", "盐湖股份", "钾肥·锂"),
    ("000408", "藏格矿业", "钾肥·锂"),
    ("600096", "云天化", "磷化工·化肥"),
    ("600141", "兴发集团", "磷化工"),
    ("600346", "恒力石化", "炼化"),
    ("601233", "桐昆股份", "涤纶长丝"),
    ("603077", "和邦生物", "纯碱·双甘膦"),
    ("605589", "圣泉集团", "合成树脂"),
]


def fetch_stocks():
    path = _path("stocks.json")
    if OFFLINE or _fresh(path):
        return json.load(open(path))
    out = {}
    for code, name, seg in STOCK_LIST:
        sym = ("sh" if code[0] == "6" else "sz") + code
        try:
            rows = json.loads(_get("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                                   "CN_MarketData.getKLineData?symbol=%s&scale=240&ma=no&datalen=1500" % sym))
            out[code] = {"name": name, "seg": seg,
                         "data": [[r["day"], float(r["close"])] for r in rows if r.get("close")]}
            print("  · %s %s %s" % (code, name, out[code]["data"][-1]))
        except Exception as e:  # noqa: BLE001
            print("  ! %s 抓取失败 %s" % (code, repr(e)[:70]))
        time.sleep(0.2)
    if out:
        json.dump(out, open(path, "w"), ensure_ascii=False)
        return out
    return json.load(open(path))


FUTURES = ["SC0", "MA0", "TA0", "PP0", "SA0", "UR0"]
FUT_NAMES = {"SC0": "原油 SC", "MA0": "甲醇", "TA0": "PTA", "PP0": "聚丙烯",
             "SA0": "纯碱", "UR0": "尿素"}


def load_futures():
    out = {}
    for sym in FUTURES:
        rows = fetch("fut_%s.json" % sym,
                     "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%%20_%s=/"
                     "InnerFuturesNewService.getDailyKLine?symbol=%s" % (sym, sym),
                     p_sina_futures, referer="https://finance.sina.com.cn/futures/")
        out[sym] = {"date": [r[0] for r in rows], "close": [r[1] for r in rows]}
    return out


def load_brent():
    rows = fetch("brent.json",
                 "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20_hf_OIL=/"
                 "GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=OIL",
                 p_brent, referer="https://finance.sina.com.cn/futures/")
    return {"date": [r[0] for r in rows], "close": [r[1] for r in rows]}


def load_weights():
    w = {}
    path = os.path.join(OLD, "holdings_516020.csv")
    if os.path.exists(path):
        for r in csv.DictReader(open(path, encoding="utf-8")):
            code = (r.get("股票代码") or "").strip().zfill(6)
            try:
                w[code] = float(r.get("占净值比例") or 0)
            except ValueError:
                pass
    return w


def load_earnings():
    path = os.path.join(OLD, "yjbb.json")
    if not os.path.exists(path):
        return {}
    y = json.load(open(path))

    def g(date, code, field):
        o = y.get(date, {}).get(code)
        return o.get(field) if o else None

    out = {}
    for code, name, _ in STOCK_LIST:
        h1, q1 = g("20260630", code, "净利润-净利润"), g("20260331", code, "净利润-净利润")
        h1p, q1p = g("20250630", code, "净利润-净利润"), g("20250331", code, "净利润-净利润")
        rev, np_ = g("20260630", code, "营业总收入-同比增长"), g("20260630", code, "净利润-同比增长")
        q2 = (h1 - q1) if (h1 is not None and q1 is not None) else None
        q2p = (h1p - q1p) if (h1p is not None and q1p is not None) else None
        q2g = (q2 / q2p - 1) * 100 if (q2 is not None and q2p and q2p > 0) else None
        if rev is None and np_ is None and q2g is None:
            continue
        out[code] = {"rev": rev, "np": np_, "q2": q2g}
    return out


# --------------------------------------------------------------------- 工具
def at(dates, ds):
    ds = ds.replace("-", "")
    for i in range(len(dates) - 1, -1, -1):
        if dates[i].replace("-", "") <= ds:
            return i
    return 0


def ret(c, dates, i, days):
    di = dates[i].replace("-", "")
    t = (dt.date(int(di[:4]), int(di[4:6]), int(di[6:8]))
         - dt.timedelta(days=days)).strftime("%Y%m%d")
    return c[i] / c[at(dates, t)] - 1


def pctile(vals, v):
    vals = [x for x in vals if x]
    return sum(1 for x in vals if x <= v) / len(vals)


def pct(v, digits=1):
    return ("%+." + str(digits) + "f%%") % (v * 100)


def cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "")


def dstr(s):
    return s[:4] + "-" + s[4:6] + "-" + s[6:8]


# --------------------------------------------------------------------- 计算
def build_data():
    print("载入数据 …")
    idx = load_index("000813")
    hs = load_index("000300")
    stocks = fetch_stocks()
    futs = load_futures()
    brent = load_brent()
    weights = load_weights()
    earn = load_earnings()

    d, c, pe = idx["date"], idx["close"], idx["pe"]
    L = len(c) - 1
    eps = [(c[i] / pe[i]) if pe[i] else None for i in range(len(c))]
    last = d[L]

    # 2026 高低点
    seg = [(d[i], c[i]) for i in range(at(d, "20260101"), L + 1)]
    hi = max(seg, key=lambda x: x[1])
    lo = min(seg, key=lambda x: x[1])
    i_peak = d.index(hi[0])

    # 收益窗口
    perf = []
    for days, lab in [(7, "近 1 周"), (30, "近 1 月"), (90, "近 3 月"),
                      (180, "近 6 月"), (365, "近 1 年")]:
        r = ret(c, d, L, days)
        rh = ret(hs["close"], hs["date"], len(hs["close"]) - 1, days)
        perf.append({"lab": lab, "v": r, "h": rh, "rel": (1 + r) / (1 + rh) - 1})
    r_ytd = c[L] / c[at(d, "20251231")] - 1
    h_ytd = hs["close"][-1] / hs["close"][at(hs["date"], "20251231")] - 1
    perf.append({"lab": "今年以来", "v": r_ytd, "h": h_ytd, "rel": (1 + r_ytd) / (1 + h_ytd) - 1})
    dd = c[L] / hi[1] - 1
    perf.append({"lab": "距 2026 高点", "v": dd, "h": None, "rel": None})

    # 估值分位
    pe_now = pe[L]
    q_all = pctile([x for x in pe if x], pe_now)
    q10 = pctile([x for x in pe if x][-2500:], pe_now)
    q5 = pctile([x for x in pe if x][-1250:], pe_now)
    q25 = pctile([x for x in pe if x][-630:], pe_now)

    eps_now = eps[L]
    eps_peak = max([x for x in eps if x])
    eps_peak_date = d[eps.index(eps_peak)]

    def eps_yoy(i):
        j = at(d, (dt.date(int(d[i][:4]), int(d[i][4:6]), int(d[i][6:8]))
                   - dt.timedelta(days=365)).strftime("%Y%m%d"))
        return eps[i] / eps[j] - 1 if eps[j] else None

    eps_g = eps_yoy(L)

    # 盈利 vs 估值拆分
    split = []
    lastd = dt.date(int(last[:4]), int(last[4:6]), int(last[6:8]))
    for days, lab in [(365, "近 1 年"), (180, "近 6 月"), (90, "近 3 月"), (30, "近 1 月")]:
        j = at(d, (lastd - dt.timedelta(days=days)).strftime("%Y%m%d"))
        split.append({"lab": lab, "price": c[L] / c[j] - 1,
                      "pe": pe[L] / pe[j] - 1, "eps": eps[L] / eps[j] - 1})
    split_peak = {"date": dstr(d[i_peak]), "price": c[L] / c[i_peak] - 1,
                  "pe": pe[L] / pe[i_peak] - 1, "eps": eps[L] / eps[i_peak] - 1,
                  "pe_peak": pe[i_peak], "eps_peak_val": eps[i_peak]}

    # 历史同类样本（滚动 5 年分位，无前视）
    win = 1250
    sig, seen = [], set()
    for i in range(250, len(c) - 250):
        if not pe[i]:
            continue
        p5 = pctile(pe[max(0, i - win):i + 1], pe[i])
        ey = eps_yoy(i)
        if p5 < 0.25 and ey is not None and ey > 0.15:
            k = d[i][:6]
            if k in seen:
                continue
            seen.add(k)
            sig.append(i)

    def fwd(i, days):
        t = (dt.date(int(d[i][:4]), int(d[i][4:6]), int(d[i][6:8]))
             + dt.timedelta(days=days)).strftime("%Y%m%d")
        for j in range(i, len(c)):
            if d[j] >= t:
                return c[j] / c[i] - 1
        return None

    r6 = [x for x in (fwd(i, 182) for i in sig) if x is not None]
    r12 = [x for x in (fwd(i, 365) for i in sig) if x is not None]
    sig_eps_ratio = [eps[i] / max(eps[max(0, i - win):i + 1]) for i in sig]

    # 唯一相似的「低 PE + 盈利恢复中段」环境：2019 年初（EPS 约为当时峰值 60%）
    i19 = at(d, "20190102")
    case19 = {
        "date": dstr(d[i19]),
        "c6": c[at(d, "20190703")] / c[i19] - 1,
        "c12": c[at(d, "20200102")] / c[i19] - 1,
        "hs6": hs["close"][at(hs["date"], "20190703")] / hs["close"][at(hs["date"], "20190102")] - 1,
        "hs12": hs["close"][at(hs["date"], "20200102")] / hs["close"][at(hs["date"], "20190102")] - 1,
        "eps_ratio": eps[i19] / max([x for x in eps[max(0, i19 - win):i19 + 1] if x]),
        "yoy": eps_yoy(i19),
    }

    dd_idx, seen = [], set()
    for i in range(250, len(c) - 130):
        hi1y = max(c[max(0, i - 250):i + 1])
        if c[i] / hi1y - 1 < -0.25:
            k = d[i][:6]
            if k in seen:
                continue
            seen.add(k)
            dd_idx.append(i)
    dd6 = [x for x in (fwd(i, 182) for i in dd_idx) if x is not None]
    base12 = [x for x in (fwd(i, 365) for i in range(0, len(c) - 365, 20)) if x is not None]

    analog = {
        "sig_n": len(sig), "sig_dates": [dstr(d[i]) for i in sig],
        "sig6_mean": st.mean(r6), "sig6_win": sum(1 for x in r6 if x > 0) / len(r6),
        "sig12_mean": st.mean(r12) if r12 else 0,
        "sig12_win": (sum(1 for x in r12 if x > 0) / len(r12)) if r12 else 0,
        "sig_eps_peak_min": min(sig_eps_ratio) if sig_eps_ratio else 0,
        "dd_n": len(dd_idx), "dd6_mean": st.mean(dd6),
        "dd6_win": sum(1 for x in dd6 if x > 0) / len(dd6),
        "base12_mean": st.mean(base12), "base12_win": sum(1 for x in base12 if x > 0) / len(base12),
        "eps_ratio": eps_now / eps_peak, "eps_peak": eps_peak, "eps_peak_date": dstr(eps_peak_date),
    }
    D_case19 = case19

    # 商品（统一 2025-01-02 = 100，按周取样）
    comm = {}
    for sym in FUTURES:
        sd = [x.replace("-", "") for x in futs[sym]["date"]]
        sc = futs[sym]["close"]
        k0 = at(sd, "20250102")
        pts = {}
        for k in range(k0, len(sd)):
            pts[sd[k]] = round(sc[k] / sc[k0] * 100, 1)
        comm[sym] = pts
    grid = sorted(set().union(*[set(v) for v in comm.values()]))
    grid = [g for g in grid if g >= "20250102"]
    grid = grid[::5] + [grid[-1]]
    comm_axis = [dstr(g) for g in grid]
    comm_series = []
    for sym in FUTURES:
        vals, lastv = [], None
        for g in grid:
            if g in comm[sym]:
                lastv = comm[sym][g]
            vals.append(lastv)
        comm_series.append({"name": FUT_NAMES[sym], "values": vals, "last": list(comm[sym].values())[-1]})
    comm_vals = {sym: futs[sym]["close"][-1] for sym in FUTURES}

    # 个股
    rows = []
    for code, name, segname in STOCK_LIST:
        s = stocks.get(code)
        if not s:
            continue
        sd = [x[0] for x in s["data"]]
        sc = [x[1] for x in s["data"]]
        iL = len(sc) - 1
        seg26 = [(sd[i], sc[i]) for i in range(len(sc)) if sd[i] >= "2025-12-31"]
        pk = max(seg26, key=lambda x: x[1]) if seg26 else (sd[0], sc[0])
        rows.append({"code": code, "name": name, "seg": segname, "w": weights.get(code, 0),
                     "r1m": ret(sc, sd, iL, 30), "r3m": ret(sc, sd, iL, 90),
                     "r1y": ret(sc, sd, iL, 365),
                     "ytd": sc[iL] / sc[at(sd, "20251231")] - 1,
                     "dd": sc[iL] / pk[1] - 1, "pk": pk[0], "px": sc[iL],
                     "e": earn.get(code)})
    rows.sort(key=lambda x: x["dd"])

    # 月度
    me = []
    cur = None
    for i, x in enumerate(d):
        if x < "20251231":
            continue
        if cur is not None and x[:6] != cur:
            me.append(i - 1)
        cur = x[:6]
    me.append(L)
    months = [{"lab": d[i][:4] + "-" + d[i][4:6], "v": c[i] / c[me[k - 1]] - 1}
              for k, i in enumerate(me) if k > 0]

    # 图表序列
    idx_series = [[dstr(d[i]), round(c[i], 2)] for i in range(len(d)) if d[i] >= "20240101"]
    i0 = at(d, "20210104")
    split_series = [[dstr(d[i]), round(c[i] / c[i0] * 100, 1),
                     round(eps[i] / eps[i0] * 100, 1), round(pe[i] / pe[i0] * 100, 1)]
                    for i in range(i0, len(d))]
    brent_series = [[x, round(v, 2)] for x, v in zip(brent["date"], brent["close"])
                    if x.replace("-", "") >= "20250102"]
    oil_idx = [[dstr(d[i]), round(c[i], 1)] for i in range(len(d)) if d[i] >= "20250102"]

    # PE 月度（每月最后一个交易日）
    pe_series, seenm = [], set()
    for i in range(len(d)):
        if not pe[i]:
            continue
        k = d[i][:6]
        if k in seenm:
            if pe_series and pe_series[-1][0] == d[i][:4] + "-" + d[i][4:6]:
                pe_series[-1][1] = round(pe[i], 2)
            continue
        seenm.add(k)
        pe_series.append([d[i][:4] + "-" + d[i][4:6], round(pe[i], 2)])
    i_old = at(d, "20260928")
    old_chg = c[L] / c[i_old] - 1
    old_pct = pctile([x for x in pe if x][:i_old + 1], pe[i_old])
    vol20 = sum(idx["turnover"][-20:]) / 20
    vol250 = sum(idx["turnover"][-250:]) / 250

    return {
        "asof": dstr(last), "gen": TODAY.strftime("%Y-%m-%d"),
        "now": {"close": c[L], "pe": pe_now, "eps": eps_now},
        "hi": {"d": dstr(hi[0]), "v": hi[1]}, "lo": {"d": dstr(lo[0]), "v": lo[1]},
        "dd": dd, "eps_g": eps_g, "perf": perf, "months": months,
        "split": split, "split_peak": split_peak, "old_chg": old_chg, "old_pct": old_pct,
        "pct": {"all": q_all, "y10": q10, "y5": q5, "y25": q25},
        "analog": analog, "stocks": rows,
        "comm": {"axis": comm_axis, "series": comm_series}, "comm_vals": comm_vals,
        "charts": {"idx": idx_series, "split": split_series, "brent": brent_series,
                   "oil_idx": oil_idx, "pe": pe_series},
        "vol": {"v20": vol20, "v250": vol250},
        "oil": {"now": brent["close"][-1],
                "yoy": brent["close"][-1] / brent["close"][at([x.replace("-", "") for x in brent["date"]], "20251017")] - 1,
                "d3m": brent["close"][-1] / brent["close"][at([x.replace("-", "") for x in brent["date"]], "20260721")] - 1,
                "jun": brent["close"][at([x.replace("-", "") for x in brent["date"]], "20260630")],
                "hi3y": max(brent["close"][-750:])},
        "earn": earn, "weights": weights, "case19": D_case19,
    }


# --------------------------------------------------------------------- 页面
CSS = """
:root{--bg:#f6f7fb;--card:#fff;--ink:#1c2333;--sub:#5a6478;--line:#e6e9f0;
--blue:#2f6fed;--red:#e5484d;--green:#18a058;--orange:#f08c00;--purple:#7c5cd6}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue","Microsoft YaHei",sans-serif;line-height:1.78}
.wrap{max-width:1080px;margin:0 auto;padding:28px 18px 60px}
header{background:linear-gradient(135deg,#0f2f57 0%,#1f6fb2 62%,#2f9e8f 100%);border-radius:16px;color:#fff;padding:32px 30px;margin-bottom:20px}
header h1{font-size:26px;letter-spacing:.3px}
header .sub{opacity:.88;margin-top:6px;font-size:13.5px}
.verdict{display:inline-block;margin-top:16px;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);border-radius:10px;padding:11px 16px;font-size:14.5px}
.verdict b{color:#ffe08a}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.card .k{font-size:11.5px;color:var(--sub)}
.card .v{font-size:21px;font-weight:700;margin-top:2px}
.card .n{font-size:11px;color:var(--sub);margin-top:2px}
.up{color:var(--red)}.down{color:var(--green)}
section{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px 26px;margin-bottom:22px}
h2{font-size:20px;margin-bottom:6px;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
h2 .tag{background:var(--blue);color:#fff;border-radius:8px;font-size:12.5px;padding:2px 9px;font-weight:600}
h3{font-size:16px;margin:22px 0 8px;color:#0f2f57}
p{margin:8px 0;font-size:14.5px}
.muted{color:var(--sub);font-size:13px}
.chart{width:100%;height:400px;margin:10px 0}
.chart-sm{height:320px}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{background:#f0f3fa;color:#334;font-weight:600;position:sticky;top:0}
td:first-child,th:first-child,td:nth-child(2),th:nth-child(2){text-align:left}
tr:hover td{background:#f8faff}
.tbl-scroll{overflow-x:auto}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.grid2{grid-template-columns:1fr}}
.box{border-radius:12px;padding:15px 18px;font-size:14px}
.box h4{font-size:15px;margin-bottom:7px}
.box ul{padding-left:20px}
.box li{margin:6px 0}
.hold{background:#eef7f1;border:1px solid #cde9d8}.hold h4{color:var(--green)}
.sell{background:#fdf0f0;border:1px solid #f2d4d5}.sell h4{color:var(--red)}
.story{background:#f4f7ff;border-left:4px solid var(--blue);border-radius:0 10px 10px 0;padding:12px 16px;margin:10px 0;font-size:14px}
.warn{background:#fff8ec;border-left:4px solid var(--orange);border-radius:0 10px 10px 0;padding:12px 16px;margin:10px 0;font-size:14px}
.key{background:#f3f0ff;border-left:4px solid var(--purple);border-radius:0 10px 10px 0;padding:12px 16px;margin:10px 0;font-size:14px}
.num{font-variant-numeric:tabular-nums}
footer{color:var(--sub);font-size:12px;text-align:center;margin-top:8px;line-height:1.9}
.pill{display:inline-block;background:#eef2fb;color:#3a5bd0;border-radius:99px;padding:2px 11px;font-size:12px;margin:2px 4px 2px 0}
.small{font-size:12.5px}
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>化工行业体检 · 2026年10月：跌到哪一步了？</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<script>if(!window.echarts)document.write('<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"><\\/script>');</script>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>化工行业体检 · 2026 年 10 月：跌到哪一步了？</h1>
  <div class="sub">中证细分化工产业主题指数（000813，50 只成分股）· 行情截至 __ASOF__ · 商品期货 10-19 收盘 · 布伦特 __BRENT__.0f 美元（10-20）</div>
  <div class="verdict">结论：<b>还在跌</b> —— 距 3 月高点 <b>__DD__</b>、近 1 月 <b>__M1__</b>；但跌的是<b>估值</b>（PE 砍掉 __PECUTABS__），盈利 TTM 还在 <b>__EPSG__</b>。<br>
  便宜是真的（PE __PE__.1f 倍，2012 年以来 __PCTALL__ 分位），但抄底还不到时候 —— 油价 110 美元 + 风格逆风未解，属于「赔率不错、胜率未到」：分批比一次性好，Q3 报和油价是分水岭。</div>
</header>

<div class="cards">
  <div class="card"><div class="k">指数点位</div><div class="v num">__CLOSE__</div><div class="n">距 __HID__ 高点 __DD__</div></div>
  <div class="card"><div class="k">近 1 月</div><div class="v num __M1CLS__">__M1__</div><div class="n">沪深300 __H1M__</div></div>
  <div class="card"><div class="k">今年以来</div><div class="v num __YTDCLS__">__YTD__</div><div class="n">沪深300 __HYTD__</div></div>
  <div class="card"><div class="k">PE-TTM</div><div class="v num">__PE__.1f<small style="font-size:12px">x</small></div><div class="n">全样本 __PCTALL__ 分位 · 近2.5年 __PCT25__</div></div>
  <div class="card"><div class="k">TTM 盈利同比</div><div class="v num up">__EPSG__</div><div class="n">隐含 EPS __EPS__.0f 点</div></div>
  <div class="card"><div class="k">重仓股 Q2 单季净利中位</div><div class="v num up">__Q2MED__</div><div class="n">2026 中报（Q3 未出）</div></div>
  <div class="card"><div class="k">布伦特原油</div><div class="v num">__BRENT__.0f</div><div class="n">同比 __BRENTYOY__ · 距 3 年高点 __BRENTGAP__</div></div>
  <div class="card"><div class="k">成交额</div><div class="v num">__V20__.0f<small style="font-size:12px">亿</small></div><div class="n">20 日均 / 250 日均 __V250__.0f 亿</div></div>
</div>

<section>
  <h2><span class="tag">问题一</span>最近是涨是跌？</h2>
  <p><b>跌。而且是「从 3 月见顶后一路下台阶、最近一个月还在加速」的跌。</b>从 __HID__ 的 __HIV__.0f 点高点算起，指数已经回撤 <b>__DD__</b>，10-15 最低见 __LOV__.0f 点；年内 <b class="down">__YTD__</b>，同期沪深300 __HYTD__ —— 相对收益 __UNDER__。</p>
  <p>换个说法：2025 年那波 <b class="up">+41%</b> 的行情，2026 年还回去大半 —— 现在的点位和一年前基本持平（近 1 年 __Y1__）。所以这不是「见顶后崩盘」，更像<b>一轮涨完之后的估值消化</b>。</p>
  <div class="tbl-scroll"><table>
    <tr><th>时间窗口</th><th>细分化工</th><th>沪深300</th><th>相对强弱</th></tr>
    __PERFROWS__
  </table></div>
  <div id="c-idx" class="chart"></div>
  <h3>2026 年：单边下跌 + 月度级别跳水</h3>
  <p class="muted">今年以来 10 个月里 5 个下跌月，其中 4 个月跌幅在 -9.6% ~ -14.5%，说明是趋势性资金流出，不是单日情绪杀跌。10 月至今 __DDM__。</p>
  <div class="tbl-scroll"><table>
    <tr><th>月份</th><th>月度涨跌</th></tr>
    __MONTHROWS__
  </table></div>
</section>

<section>
  <h2><span class="tag">问题二</span>跌在哪？—— 跌的正是上半年涨最猛的那几条线</h2>
  <p>指数跌 __DD__，但内部差异极大（下表 20 只代表性成分股，权重取 2026Q2 基金持仓）：</p>
  <div class="tbl-scroll"><table>
    <tr><th>个股</th><th>方向</th><th>权重</th><th>近 1 月</th><th>近 3 月</th><th>近 1 年</th><th>距 2026 高点</th></tr>
    __STOCKROWS__
  </table></div>
  <div id="c-breadth" class="chart"></div>
  <div class="grid2">
    <div class="box sell">
      <h4>近 3 个月跌最狠：景气叙事最贵的部分</h4>
      <ul>__WORST3__</ul>
      <p class="small muted">共同点：2026 上半年涨幅最大（东材近 1 年 +133%、天赐/多氟多 Q2 净利翻倍以上），估值提前把「涨价 + 出清」的好消息打满。</p>
    </div>
    <div class="box hold">
      <h4>近 3 个月抗跌：低估值 + 成本优势</h4>
      <ul>__BEST3__</ul>
      <p class="small muted">共同点：估值处于历史低位、成本曲线靠左（煤化工、轻烃、钾肥资源），没有「高增长故事」要还。</p>
    </div>
  </div>
  <div class="story"><b>一句话总结这一节：</b>跌的是<b>拥挤度</b>，不是行业本身 —— 前期涨 40%~130% 的题材股回撤 45%~58%，而低估值、低预期的传统龙头基本走平（卫星化学近 3 月 +6.7%、藏格 +2.0%、宝丰 -0.3%）。</div>
</section>

<section>
  <h2><span class="tag">问题三</span>为什么跌？—— 四条原因，按证据强弱排</h2>

  <h3>① 主因：杀估值，不是杀盈利 <span class="pill">数据可证</span></h3>
  <p>把涨跌拆成「盈利 × 估值」（隐含 TTM EPS = 收盘价 ÷ 官方滚动 PE）：</p>
  <div class="tbl-scroll"><table>
    <tr><th>区间</th><th>指数涨跌</th><th>PE 变化</th><th>隐含 EPS 变化</th></tr>
    __SPLITROWS__
    <tr><td>__SPDATE__ 高点 → 现在</td><td class="num">__SPPRICE__</td><td class="num">__SPPE__</td><td class="num">__SPEPS__</td></tr>
  </table></div>
  <p>过去一年：盈利 <b class="up">__EPSG__</b>、PE <b class="down">__PE1Y__</b>、股价只剩 __Y1__ —— <b>估值压缩吃掉了全部盈利增长</b>。从 3 月高点看更极端：PE 从 __PEPEAK__.1f 倍砍到 __PE__.1f 倍（__SPPE__），盈利还涨了 __SPEPSABS__。</p>
  <div id="c-split" class="chart"></div>
  <p class="muted">看这张图：橙线（PE）一路下台阶，红线（盈利）一路向上，蓝线（股价）被夹在中间 —— 这就是「盈利兑现、估值还债」的典型形态。</p>

  <h3>② 油价二次冲击：从 73 美元冲到 110 美元 <span class="pill">部分解释</span></h3>
  <p>布伦特从 6 月底的 __OILJUN__.0f 美元涨到现在的 <b>__BRENT__.0f 美元</b>（近 3 月 __OIL3M__、同比 __BRENTYOY__，距 3 年高点 __BRENTHI__.1f 只差 __BRENTGAPABS__）。高油价对化工是「三杀」：油头装置成本上升 → 下游被高价抑制 → 通胀预期压制整体估值。</p>
  <p class="muted">但注意口径：油价与化工指数的<b>月频相关性只有 0.19</b>，不是简单的线性关系。真正杀伤的是「盈利已在兑现、油价还往上冲」这个组合 —— 近 3 个月油价 +20%、指数 -8%，背离非常明显。</p>
  <div id="c-oil" class="chart chart-sm"></div>
  <p class="small">反证：成本曲线靠左的公司基本没跌 —— 煤化工（宝丰近 3 月 -0.3%）、轻烃（卫星 +6.7%）、钾肥（藏格 +2.0%）。这恰恰说明市场在按「成本」定价，而不是无差别抛售。</p>

  <h3>③ 地产链没起来：纯碱 / 尿素还在往下走 <span class="pill">结构性拖累</span></h3>
  <p>纯碱期货 __COMMSA__.0f 元（同比 <span class="down">-21%</span>，距多年高点 -64%）、尿素 __COMMUR__.0f 元（距高点 -30%）；和邦生物距高点 __HEBANG__。地产 → 玻璃 → 纯碱这条链子没改善，是「传统化工」这一半的拖累项，也解释了为什么指数跌得比油价涨得更狠。</p>
  <div id="c-comm" class="chart"></div>
  <p class="muted">油头链在涨（甲醇近 3 月 +16%、PTA +10%、聚丙烯 +13%、塑料 +10%），地产链在跌（纯碱 -6%、尿素 -2%）—— <b>不是全面复苏，是成本推动的结构性行情</b>。这也是「盈利在涨、股价却不涨」的深层原因：市场不相信涨价能传导到终端需求。</p>

  <h3>④ 拥挤度出清 + 风格逆风 <span class="pill">解释下跌速度</span></h3>
  <p>9 月单月 -11.4%、10 月至今 __DDM__，而同期沪深300 近 1 月 __H1M__ —— 化工<b>跑输大盘</b>。背景是 A 股 10 月的科技回调（参考本站《A股这轮下跌怎么看》：科技板块自高点 -32%），风险偏好整体下移时，前期涨幅大、持仓拥挤的方向被优先卖出。成交额也能印证：20 日均 __V20__.0f 亿，比 250 日均 __V250__.0f 亿<b>缩量 __VOLCUT__</b> —— 是「没人接」的阴跌，不是恐慌性放量出清。</p>

  <div class="warn"><b>还有一个「卖事实」因素：</b>8 月 31 日中报落地后，TTM 盈利一次性抬升 24%（EPS 从 167 跳到 207 点），PE 当天从 23.1 掉到 18.3 倍。按常理这是利好，但市场把它解读成「周期盈利已在高位」—— 于是出现了「业绩越好、估值杀得越狠」的怪现象。这是周期股在盈利兑现期的典型反应。</div>
</section>

<section>
  <h2><span class="tag">问题四</span>可持续吗？—— 盈利可持续，估值修复还缺催化剂</h2>

  <h3>4.1 盈利是真的，而且还在加速</h3>
  <p class="muted">2026 中报（Q3 报 10 月底才披露）：有可比数据的 13 只里，Q2 单季净利同比中位数 <b class="up">__Q2MED__</b>；除圣泉（-8%）、云天化（+2%）外全部正增长，万华 +109%、卫星 +250%、天赐 +920%。</p>
  <div class="tbl-scroll"><table>
    <tr><th>个股</th><th>方向</th><th>H1 营收同比</th><th>H1 净利同比</th><th>Q2 单季净利同比</th></tr>
    __EARNROWS__
  </table></div>
  <p class="small muted">「—」= 上年同期为亏损或基数异常，单季同比不可比（多氟多、恩捷 2025 上半年仍处于亏损修复期）。</p>
  <p>也就是说：<b>跌的不是基本面</b>。TTM 盈利同比 __EPSG__、Q2 单季还在加速 —— 盈利这条腿是站得住的。市场真正在赌的是「这个增速是不是已经见顶」。</p>

  <h3>4.2 估值确实便宜，但便宜分两种</h3>
  <div class="tbl-scroll"><table>
    <tr><th>估值口径</th><th>当前 PE</th><th>历史分位</th><th>区间（最低 ~ 最高）</th></tr>
    <tr><td>2012 年以来全样本</td><td class="num">__PE__.1f x</td><td class="num">__PCTALL__</td><td class="num">10.0 ~ 46.9</td></tr>
    <tr><td>近 10 年</td><td class="num">__PE__.1f x</td><td class="num">__PCT10__</td><td class="num">10.9 ~ 39.5</td></tr>
    <tr><td>近 5 年</td><td class="num">__PE__.1f x</td><td class="num">__PCT5__</td><td class="num">10.9 ~ 30.2</td></tr>
    <tr><td>近 2.5 年</td><td class="num">__PE__.1f x</td><td class="num">__PCT25__</td><td class="num">13.3 ~ 30.2</td></tr>
  </table></div>
  <div id="c-pe" class="chart chart-sm"></div>
  <p>PE __PE__.1f 倍，绝对值不贵；但<b>「便宜」在化工里经常是盈利见顶的副产品</b>。检验：2012 年以来，「PE 处于滚动 5 年 25% 分位以下」且「盈利同比 &gt;15%」同时出现（__SIGN__ 个独立样本月），未来 6 个月平均 <b class="down">__SIGMEAN__</b>、胜率仅 <b>__SIGWIN__</b>，12 个月平均 __SIG12__。</p>
  <div class="key"><b>为什么？</b>因为这些样本 <b>100% 出现在 EPS 已达到历史峰值 __SIGMIN__ 以上的时候</b>（2017-11 ~ 2019-04、2022-01 ~ 2022-10）—— 盈利最好的一年，PE 被分母压到最低，看起来最「便宜」，实际上最危险。<b>这次的关键区别：</b>当前 EPS __EPS__.0f 点，只有 2021-22 峰值 __EPSPEAK__.0f 点的 <b>__EPSRATIO__</b>，盈利还在爬坡，不是顶部低 PE。</div>
  <p class="muted">换句话说：<b>这次不一定是「陷阱」，但也没有足够的历史样本背书</b> —— 27 个低 PE 样本全部出现在「盈利已达峰值」的阶段，而这次是 2012 年以来<b>第一次</b>出现在盈利恢复中段（EPS 仅为 5 年峰值的 62%）。最接近的对照是 __C19DATE__（同样极低 PE、盈利同比 __C19YOY__，但 EPS 已回到 5 年峰值的 __C19EPS__）：随后 6 个月化工 __C19_6__、沪深300 __C19HS_6__；12 个月化工 __C19_12__、沪深300 __C19HS_12__ —— <b>便宜能托底，但跑不赢宽基</b>。</p>

  <h3>4.3 那么「可持续」的到底是哪一部分？</h3>
  <div class="grid2">
    <div class="box hold">
      <h4>可持续（概率高）</h4>
      <ul>
        <li><b>盈利</b>：Q3 大概率仍正增长（低基数 + 涨价滞后传导），但增速会从 __EPSG__ 回落到 +20% 上下</li>
        <li><b>供给端逻辑</b>：制冷剂配额制、行业资本开支连续两年负增长、反内卷政策 —— 不因股价下跌而消失</li>
        <li><b>估值下限</b>：PE __PE__.1f 倍、龙头现金流健康，再杀 30% 需要盈利崩塌配合，当前看不到</li>
      </ul>
    </div>
    <div class="box sell">
      <h4>不可持续 / 需要新条件</h4>
      <ul>
        <li><b>「便宜就会涨」</b>：过去 4 个月已经证伪 —— 估值分位仍在 __PCTALL__ 附近，指数却又跌了 __OLDCHGABS__</li>
        <li><b>油价 110 美元下的利润扩张</b>：油头成本高企、价差压缩；油价再上台阶 = 需求与估值双杀</li>
        <li><b>地产链反转</b>：纯碱 / 尿素 / 玻璃没有任何见底信号</li>
      </ul>
    </div>
  </div>
  <div class="story"><b>小结：</b>基本面（盈利 + 供给格局）可持续；股价可持续上涨<b>需要新增条件</b> —— 油价回落、或 Q3 超预期、或政策（反内卷/供给侧）落地。三者目前都还没出现，所以现在的位置适合「分批」，不适合「梭哈」。</div>
</section>

<section>
  <h2><span class="tag">问题五</span>未来怎么走？—— 四条路与概率</h2>
  <p>概率的来源不是拍脑袋，是三组数据：① 当前估值分位（__PCTALL__，历史偏低）；② 盈利方向（TTM __EPSG__，仍在向上）；③ 历史回撤样本（-25% 回撤后 6 个月胜率 __DDWIN__、平均 __DDMEAN__，基本等于抛硬币）；④ 外部约束（油价 110 美元、风格逆风）。</p>
  <div id="c-scn" class="chart"></div>
  <div class="tbl-scroll"><table>
    <tr><th>情景</th><th>概率</th><th>指数区间</th><th>触发条件</th><th>应对</th></tr>
    <tr><td><b>A 磨底震荡</b><br><span class="muted small">最可能</span></td><td class="num">40%</td><td class="num">3100 ~ 3600</td><td>油价 95~115 横盘；Q3 增速回落但仍正；无政策催化</td><td>持有不动，用时间换空间；网格/定投</td></tr>
    <tr><td><b>B 二次探底</b><br><span class="muted small">风险情景</span></td><td class="num">27%</td><td class="num">2700 ~ 3000</td><td>布伦特破 120；Q3 不及预期；地产链继续恶化；风格继续杀高估值</td><td>保留子弹，跌到 PE 12x 附近再加</td></tr>
    <tr><td><b>C 修复反弹</b><br><span class="muted small">需催化</span></td><td class="num">25%</td><td class="num">3600 ~ 4000</td><td>油价回落至 90 以下 + 反内卷/供给侧政策落地 + Q3 超预期</td><td>右侧确认后加仓（站上 60 日线）</td></tr>
    <tr><td><b>D 周期反转</b><br><span class="muted small">低概率</span></td><td class="num">8%</td><td class="num">4300+</td><td>供给端大出清 + 全球补库 + 油价回到 80 区间；需要 1~2 年</td><td>不押注，作为期权</td></tr>
  </table></div>
  <h3>时间维度上更可能的样子</h3>
  <p><b>未来 1~3 个月（短）：</b>磨底概率最高。下跌趋势未破（指数在 20 日均线下方），但成交已缩量 __VOLCUT__，下方空间被估值和盈利封住一部分 —— <b>更可能是 3100~3400 反复</b>，等 Q3 报（10 月底前）给方向。</p>
  <p><b>未来 6~12 个月（中）：</b>关键变量是油价。若布伦特回到 90 以下，化工的「成本下降 + 需求修复」双击能带来 __CUP__ 以上的修复；若油价维持 110 以上，则大概率是「盈利增长但估值不涨」的横盘市。</p>
  <div class="warn"><b>概率的诚实说明：</b>四条路的概率是我按「估值分位 + 盈利方向 + 历史回撤样本 + 油价/风格约束」加权的主观判断，不是模型输出，也不构成投资建议。真正会改变概率的只有两个变量：<b>油价</b>和<b>Q3 业绩</b>。任一出现，重算。</div>
</section>

<section>
  <h2><span class="tag">问题六</span>现在该怎么做？</h2>
  <div class="grid2">
    <div class="box hold">
      <h4>如果已经持有</h4>
      <ul>
        <li><b>别在这个位置割。</b>PE __PE__.1f 倍 / 2012 年以来 __PCTALL__ 分位，杀跌的赔率不好；盈利还是正的</li>
        <li><b>也别加满。</b>下跌趋势 + 油价高位，右侧信号没出现</li>
        <li>加仓的钱分 3 份：分别在「Q3 报落地」「油价回到 95 以下」「指数站上 60 日线」各加一份</li>
      </ul>
    </div>
    <div class="box sell">
      <h4>如果空仓想买</h4>
      <ul>
        <li>现在买 = 左侧。可以接受，但仓位控制在 1/3 以内</li>
        <li>两个右侧信号出现其一再加：布伦特 &lt; 95 美元，或 PE 分位 &lt; 10%（对应指数约 2950 点）</li>
        <li>更稳的做法：等 Q3 报（10 月底）确认「增速没有断崖」，再决定</li>
      </ul>
    </div>
  </div>
  <h3>跟踪清单（每周看一次就够）</h3>
  <table>
    <tr><th>指标</th><th>现在</th><th>看什么</th></tr>
    <tr><td>布伦特原油</td><td class="num">__BRENT__.0f 美元</td><td>跌破 90 = 最强利好；破 120 = 情景 B</td></tr>
    <tr><td>指数 PE（000813）</td><td class="num">__PE__.1f 倍</td><td>跌破 13 倍进入历史极值区</td></tr>
    <tr><td>纯碱期货</td><td class="num">__COMMSA__.0f 元</td><td>地产链是否见底（连涨 2 个月）</td></tr>
    <tr><td>甲醇 / PTA / 聚丙烯</td><td class="num">__COMMMA__.0f / __COMMTA__.0f / __COMMPP__.0f</td><td>油头价差是否被压缩（跌 = 成本传导失败）</td></tr>
    <tr><td>2026Q3 财报</td><td>10 月底前</td><td>净利同比是否 &gt; +15%（断崖 = 情景 B 概率上调）</td></tr>
  </table>
</section>

<section>
  <h2><span class="tag">附</span>与上一版的差异 + 口径</h2>
  <div class="story"><b>上一版（2026-09）的结论是「可以拿」</b>：逻辑是「盈利 +50%~900% + PE 16.5 倍（24% 分位）」。此后指数又跌了 __OLDCHGABS__ —— 不是逻辑错，而是<b>「低估值 + 盈利增长」不足以对抗油价与风险偏好</b>。这一版因此把结论从「能拿」改成「分情景、分批」：同样的便宜，在趋势下行里要慢慢买，而不是一次买完。</div>
  <h3>数据口径</h3>
  <ul class="small" style="padding-left:20px;color:var(--sub)">
    <li>指数：中证指数官网 000813 日线 + <b>官方滚动市盈率</b>；隐含 TTM EPS = 收盘 ÷ PE，用于拆分「盈利 vs 估值」</li>
    <li>PE 分位：滚动窗口（全样本 / 10 年 / 5 年 / 2.5 年），只用当日及之前数据，无前视</li>
    <li>沪深300：000300 价格指数（与 000813 同为价格指数，可比）</li>
    <li>个股：新浪财经日线（20 只代表性成分股，权重取 2026Q2 基金持仓）</li>
    <li>商品：新浪期货连续合约收盘（2025-01 → 现在），按周取样</li>
    <li>业绩：2026 中报（akshare 缓存，2026-09 抓取）；Q3 报未披露。Q2 单季 = H1 累计 − Q1 累计</li>
    <li>历史样本：2012-01 至今，月度去重；「低 PE + 盈利高增长」样本 __SIGN__ 个，「-25% 回撤」样本 __DDN__ 个；12 个月基准胜率 __BASE12__</li>
  </ul>
  <p class="small muted">上一版报告（2026-09，成分股与估值拆解）：<a href="../etf-012538-analysis/index.html">化工ETF 012538 还能拿吗</a>。数据来源：中证指数官网、新浪财经；本页为个人研究记录，不构成投资建议。</p>
</section>

<footer>由 chem-2026-10/build.py 生成 · 数据截至 __ASOF__ · 生成于 __GEN__</footer>
</div>

<script>
const D = __DATA__;
const AXIS = {axisLine:{lineStyle:{color:'#c9d0e0'}},axisLabel:{color:'#5a6478',fontSize:11},splitLine:{lineStyle:{color:'#eef1f7'}}};
function mk(id){const el=document.getElementById(id);return el?echarts.init(el):null;}

// 1) 指数走势
(function(){
  const c=mk('c-idx'); if(!c) return;
  const dd=D.charts.idx.map(x=>x[0]), vv=D.charts.idx.map(x=>x[1]);
  c.setOption({
    tooltip:{trigger:'axis'},
    grid:{left:56,right:20,top:24,bottom:54},
    xAxis:{type:'category',data:dd,...AXIS},
    yAxis:{type:'value',scale:true,...AXIS},
    dataZoom:[{type:'inside'},{type:'slider',height:15,bottom:6}],
    series:[{type:'line',data:vv,showSymbol:false,lineStyle:{width:1.6,color:'#2f6fed'},
      areaStyle:{color:'rgba(47,111,237,.10)'},
      markPoint:{symbolSize:44,label:{fontSize:10,color:'#fff'},data:[
        {coord:[D.hi.d,D.hi.v],value:'高 '+D.hi.v.toFixed(0)},
        {coord:[D.lo.d,D.lo.v],value:'低 '+D.lo.v.toFixed(0)}
      ]},
      markLine:{symbol:'none',label:{formatter:'现在 '+D.now.close.toFixed(0),color:'#e5484d',fontSize:11},
        lineStyle:{color:'#e5484d',type:'dashed'},data:[{yAxis:D.now.close}]}
    }]
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 2) 盈利 vs 估值
(function(){
  const c=mk('c-split'); if(!c) return;
  const s=D.charts.split;
  c.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['指数（价格）','TTM 盈利','PE（估值）'],top:0,textStyle:{color:'#5a6478',fontSize:11}},
    grid:{left:52,right:20,top:36,bottom:38},
    xAxis:{type:'category',data:s.map(x=>x[0]),...AXIS,axisLabel:{...AXIS.axisLabel,hideOverlap:true}},
    yAxis:{type:'value',...AXIS},
    series:[
      {name:'指数（价格）',type:'line',data:s.map(x=>x[1]),showSymbol:false,lineStyle:{width:1.8,color:'#2f6fed'}},
      {name:'TTM 盈利',type:'line',data:s.map(x=>x[2]),showSymbol:false,lineStyle:{width:1.8,color:'#e5484d'}},
      {name:'PE（估值）',type:'line',data:s.map(x=>x[3]),showSymbol:false,lineStyle:{width:1.8,color:'#f08c00'}}
    ]
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 3) 油价 vs 指数
(function(){
  const c=mk('c-oil'); if(!c) return;
  const bd=D.charts.brent.map(x=>x[0]), bv=D.charts.brent.map(x=>x[1]);
  const m={}; D.charts.oil_idx.forEach(x=>m[x[0]]=x[1]);
  let lastv=null;
  const ix=bd.map(d=>{ if(m[d]!==undefined) lastv=m[d]; return lastv; });
  c.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['布伦特原油（美元）','细分化工指数'],top:0,textStyle:{fontSize:11,color:'#5a6478'}},
    grid:{left:48,right:52,top:36,bottom:34},
    xAxis:{type:'category',data:bd,...AXIS,axisLabel:{...AXIS.axisLabel,hideOverlap:true}},
    yAxis:[{type:'value',name:'美元',nameTextStyle:{fontSize:11},...AXIS},
           {type:'value',name:'指数',nameTextStyle:{fontSize:11},...AXIS,splitLine:{show:false}}],
    series:[
      {name:'布伦特原油（美元）',type:'line',data:bv,showSymbol:false,lineStyle:{width:1.6,color:'#333'}},
      {name:'细分化工指数',type:'line',data:ix,yAxisIndex:1,showSymbol:false,lineStyle:{width:1.6,color:'#2f9e8f'}}
    ]
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 4) 商品
(function(){
  const c=mk('c-comm'); if(!c) return;
  const colors={'原油 SC':'#333','甲醇':'#7c5cd6','PTA':'#2f6fed','聚丙烯':'#e5484d','纯碱':'#18a058','尿素':'#f08c00'};
  c.setOption({
    tooltip:{trigger:'axis'},
    legend:{top:0,textStyle:{fontSize:11,color:'#5a6478'}},
    grid:{left:48,right:20,top:36,bottom:34},
    xAxis:{type:'category',data:D.comm.axis,...AXIS,axisLabel:{...AXIS.axisLabel,hideOverlap:true}},
    yAxis:{type:'value',...AXIS},
    series:D.comm.series.map(s=>({name:s.name,type:'line',data:s.values,connectNulls:true,showSymbol:false,
      lineStyle:{width:1.8,color:colors[s.name]}}))
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 5) 个股距高点
(function(){
  const c=mk('c-breadth'); if(!c) return;
  const rows=D.stocks.slice().sort((a,b)=>a.dd-b.dd);
  c.setOption({
    tooltip:{trigger:'axis',formatter:p=>{const s=rows[p[0].dataIndex];
      return s.name+'<br/>距高点 '+(s.dd*100).toFixed(1)+'%<br/>近1年 '+(s.r1y*100).toFixed(1)+'%<br/>近3月 '+(s.r3m*100).toFixed(1)+'%';}},
    grid:{left:78,right:60,top:14,bottom:30},
    xAxis:{type:'value',...AXIS,axisLabel:{...AXIS.axisLabel,formatter:v=>v+'%'}},
    yAxis:{type:'category',data:rows.map(s=>s.name),...AXIS,axisLabel:{...AXIS.axisLabel,fontSize:11}},
    series:[{type:'bar',barWidth:'62%',
      data:rows.map(s=>({value:+(s.dd*100).toFixed(1),itemStyle:{color:s.r1y>0?'#e5484d':'#18a058',opacity:.85}})),
      label:{show:true,position:'right',fontSize:10,color:'#5a6478',formatter:p=>p.value+'%'}}]
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 6) PE 历史
(function(){
  const c=mk('c-pe'); if(!c) return;
  c.setOption({
    tooltip:{trigger:'axis'},
    grid:{left:48,right:20,top:20,bottom:30},
    xAxis:{type:'category',data:D.charts.pe.map(x=>x[0]),...AXIS,axisLabel:{...AXIS.axisLabel,hideOverlap:true}},
    yAxis:{type:'value',name:'PE-TTM',nameTextStyle:{fontSize:11},...AXIS},
    series:[{type:'line',data:D.charts.pe.map(x=>x[1]),showSymbol:false,lineStyle:{width:1.4,color:'#7c5cd6'},
      areaStyle:{color:'rgba(124,92,214,.10)'},
      markLine:{symbol:'none',label:{fontSize:10,position:'insideEndTop'},data:[
        {yAxis:24,name:'中位 24x'},{yAxis:D.now.pe,name:'现在 '+D.now.pe.toFixed(1)+'x'}]}}]
  });
  window.addEventListener('resize',()=>c.resize());
})();

// 7) 情景概率
(function(){
  const c=mk('c-scn'); if(!c) return;
  const S=[{name:'A 磨底震荡',p:40,lo:3100,hi:3600,c:'#2f6fed'},
           {name:'B 二次探底',p:27,lo:2700,hi:3000,c:'#e5484d'},
           {name:'C 修复反弹',p:25,lo:3600,hi:4000,c:'#18a058'},
           {name:'D 周期反转',p:8,lo:4300,hi:4800,c:'#7c5cd6'}];
  c.setOption({
    tooltip:{trigger:'axis',formatter:p=>{const s=S[p[0].dataIndex];return s.name+'<br/>概率 '+s.p+'%<br/>区间 '+s.lo+'~'+s.hi;}},
    grid:{left:92,right:150,top:12,bottom:26},
    xAxis:{type:'value',max:56,interval:10,...AXIS,axisLabel:{...AXIS.axisLabel,formatter:v=>v+'%'}},
    yAxis:{type:'category',data:S.map(s=>s.name),...AXIS},
    series:[{type:'bar',barWidth:'52%',data:S.map(s=>({value:s.p,itemStyle:{color:s.c,opacity:.82}})),
      label:{show:true,position:'right',fontSize:11,color:'#5a6478',
        formatter:p=>S[p.dataIndex].p+'%  ('+S[p.dataIndex].lo+'~'+S[p.dataIndex].hi+')'}}]
  });
  window.addEventListener('resize',()=>c.resize());
})();
</script>
</body>
</html>
"""


def render(D):
    n, a, oil = D["now"], D["analog"], D["oil"]
    pf = {x["lab"]: x for x in D["perf"]}
    q2s = [s["e"]["q2"] for s in D["stocks"] if s["e"] and s["e"].get("q2") is not None]
    q2med = st.median(q2s) if q2s else 0.0

    def cell(v):
        return '<span class="%s">%s</span>' % (cls(v), pct(v)) if v is not None else "—"

    perf_rows = "".join(
        "<tr><td>%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td></tr>"
        % (x["lab"], cell(x["v"]), cell(x["h"]) if x["h"] is not None else "—",
           cell(x["rel"]) if x["rel"] is not None else "—") for x in D["perf"])

    month_rows = "".join("<tr><td>%s</td><td class=\"num\">%s</td></tr>" % (m["lab"], cell(m["v"]))
                         for m in D["months"])

    split_rows = "".join(
        "<tr><td>%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td></tr>"
        % (x["lab"], cell(x["price"]), cell(x["pe"]), cell(x["eps"])) for x in D["split"])

    stock_rows = "".join(
        "<tr><td>%s</td><td><span class=\"muted small\">%s</span></td><td class=\"num\">%s</td>"
        "<td class=\"num\">%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td></tr>"
        % (s["name"], s["seg"], ("%.1f%%" % s["w"]) if s["w"] else "—",
           cell(s["r1m"]), cell(s["r3m"]), cell(s["r1y"]), cell(s["dd"])) for s in D["stocks"])

    earn_rows = ""
    for s in D["stocks"]:
        e = s["e"]
        if not e:
            continue

        def p3(v):
            if v is None:
                return "—"
            if abs(v) > 999:
                return '<span class="up">&gt;999%</span>'
            return '<span class="%s">%+.1f%%</span>' % (cls(v), v)

        earn_rows += ("<tr><td>%s</td><td><span class=\"muted small\">%s</span></td>"
                      "<td class=\"num\">%s</td><td class=\"num\">%s</td><td class=\"num\">%s</td></tr>"
                      % (s["name"], s["seg"], p3(e.get("rev")), p3(e.get("np")), p3(e.get("q2"))))

    s3 = sorted(D["stocks"], key=lambda x: x["r3m"])
    worst3, best3 = s3[:4], s3[-4:][::-1]

    def lst(items):
        return "".join("<li><b>%s</b>　近 3 月 <span class=\"%s\">%s</span></li>"
                       % (x["name"], cls(x["r3m"]), pct(x["r3m"])) for x in items)

    hebang = [s for s in D["stocks"] if s["code"] == "603077"]
    under = (pf["今年以来"]["h"] - pf["今年以来"]["v"]) * 100
    vol_cut = (1 - D["vol"]["v20"] / D["vol"]["v250"]) * 100
    cup = (4000 / n["close"] - 1) * 100

    R = {
        "CSS": CSS,
        "ASOF": D["asof"], "GEN": D["gen"],
        "DD": pct(D["dd"]), "M1": pct(pf["近 1 月"]["v"]), "M1CLS": cls(pf["近 1 月"]["v"]),
        "HID": D["hi"]["d"], "HIV": D["hi"]["v"], "LOV": D["lo"]["v"],
        "PECUT": pct(D["split_peak"]["pe"]), "PECUTABS": "%.1f%%" % (abs(D["split_peak"]["pe"]) * 100), "PE1Y": pct(D["split"][0]["pe"]), "EPSG": pct(D["eps_g"]),
        "PE": n["pe"], "CLOSE": "%.0f" % n["close"],
        "PCTALL": "%.0f%%" % (D["pct"]["all"] * 100),
        "PCT10": "%.0f%%" % (D["pct"]["y10"] * 100),
        "PCT5": "%.0f%%" % (D["pct"]["y5"] * 100),
        "PCT25": "%.0f%%" % (D["pct"]["y25"] * 100),
        "YTD": pct(pf["今年以来"]["v"]), "YTDCLS": cls(pf["今年以来"]["v"]),
        "HYTD": pct(pf["今年以来"]["h"]), "H1M": pct(pf["近 1 月"]["h"]),
        "Y1": pct(pf["近 1 年"]["v"]), "UNDER": pct((1 + pf["今年以来"]["v"]) / (1 + pf["今年以来"]["h"]) - 1),
        "Q2MED": "%+.0f%%" % q2med,
        "BRENT": oil["now"], "BRENTYOY": pct(oil["yoy"]),
        "BRENTGAP": pct(oil["now"] / oil["hi3y"] - 1),
        "BRENTGAP2": pct(oil["now"] / oil["hi3y"] - 1), "BRENTGAPABS": "%.1f%%" % (abs(oil["now"] / oil["hi3y"] - 1) * 100),
        "BRENTHI": oil["hi3y"], "OILJUN": oil["jun"], "OIL3M": pct(oil["d3m"]),
        "V20": D["vol"]["v20"], "V250": D["vol"]["v250"], "VOLCUT": "%.0f%%" % vol_cut,
        "DDM": pct(D["months"][-1]["v"]),
        "PERFROWS": perf_rows, "MONTHROWS": month_rows,
        "STOCKROWS": stock_rows, "EARNROWS": earn_rows,
        "WORST3": lst(worst3), "BEST3": lst(best3),
        "SPDATE": D["split_peak"]["date"], "SPPRICE": pct(D["split_peak"]["price"]),
        "SPPE": pct(D["split_peak"]["pe"]), "SPEPS": pct(D["split_peak"]["eps"]),
        "SPEPSABS": "%+.1f%%" % (D["split_peak"]["eps"] * 100),
        "SPLITROWS": split_rows, "PEPEAK": D["split_peak"]["pe_peak"],
        "EPS": n["eps"], "EPSPEAK": a["eps_peak"], "EPSRATIO": "%.0f%%" % (a["eps_ratio"] * 100),
        "SIGN": a["sig_n"], "SIGMIN": "%.0f%%" % (a["sig_eps_peak_min"] * 100), "SIGMEAN": pct(a["sig6_mean"]), "SIGWIN": "%.0f%%" % (a["sig6_win"] * 100),
        "SIG12": pct(a["sig12_mean"]), "DDWIN": "%.0f%%" % (a["dd6_win"] * 100),
        "DDMEAN": pct(a["dd6_mean"]), "DDN": a["dd_n"],
        "BASE12": "%.0f%%" % (a["base12_win"] * 100),
        "C19DATE": D["case19"]["date"], "C19EPS": "%.0f%%" % (D["case19"]["eps_ratio"] * 100),
        "C19_6": pct(D["case19"]["c6"]), "C19YOY": pct(D["case19"]["yoy"]), "C19_12": pct(D["case19"]["c12"]),
        "C19HS_6": pct(D["case19"]["hs6"]), "C19HS_12": pct(D["case19"]["hs12"]),
        "COMMSA": D["comm_vals"]["SA0"], "COMMUR": D["comm_vals"]["UR0"],
        "COMMMA": D["comm_vals"]["MA0"], "COMMTA": D["comm_vals"]["TA0"],
        "COMMPP": D["comm_vals"]["PP0"],
        "HEBANG": pct(hebang[0]["dd"]) if hebang else "—",
        "CUP": "%+.0f%%" % cup,
        "OLDCHG": pct(D["old_chg"]), "OLDCHGABS": "%.1f%%" % (abs(D["old_chg"]) * 100), "OLDPCT": "%.0f%%" % (D["old_pct"] * 100),
        "DATA": json.dumps({"now": n, "hi": D["hi"], "lo": D["lo"], "charts": D["charts"],
                            "comm": D["comm"], "stocks": D["stocks"]}, ensure_ascii=False),
    }

    import re

    def sub_num(mo):
        key, spec = mo.group(1), mo.group(2)
        val = R.get(key)
        if val is None:
            return "—"
        if isinstance(val, str):
            try:
                val = float(val)
            except ValueError:
                return val
        try:
            return ("%." + spec + "f") % float(val)
        except (TypeError, ValueError):
            return "—"

    # 先处理带精度后缀的（__BRENT__.0f），再替换纯 token
    html = re.sub(r"__([A-Z0-9]+)__\.(\d)f", sub_num, HTML)
    INT_KEYS = {"SIGN", "DDN"}
    for k, v in R.items():
        if isinstance(v, str):
            val = v
        elif k in INT_KEYS or float(v).is_integer():
            val = "%.0f" % float(v)
        else:
            val = "%g" % float(v)
        html = html.replace("__%s__" % k, val)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成 %s（%.0f KB）" % (OUT, os.path.getsize(OUT) / 1024))


def main():
    D = build_data()
    render(D)
    print("\n接下来：python3 ../build_site.py  # 注入导航 + 更新门户")


if __name__ == "__main__":
    main()
