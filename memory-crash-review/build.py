#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「存储股崩盘」报告复盘页（2026-10-15 报告 → 2026-10-30 复盘）。

先跑 fetch.py 抓数，再跑本脚本生成 index.html。
数据全部来自 data/：
  - 韩股：Naver 日线（10 年）+ 当前 PER/PBR/外资持股
  - 美股：新浪美股日线（Yahoo 2026-10-30 起 403）
  - A股：腾讯前复权日线
  - 电网设备：中证官网指数 + 天天基金净值 + 159326 ETF（复用 fund-025833-review/data）
"""
import json
import os
import math
import datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "data")


def load(name):
    with open(os.path.join(D, name), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ 数据
kr10 = {c: [(x["date"], x["close"], x.get("foreign")) for x in load("naver10y_%s.json" % c)]
        for c in ("005930", "000660")}
krx = {c: [(d, cl) for d, cl, f in kr10[c]] for c in ("005930", "000660")}
kr_val = {c: load("naver_val_%s.json" % c) for c in ("005930", "000660")}
us = {s: [(x["date"], x["close"]) for x in load("us_%s.json" % s)]
      for s in ("MU", "SNDK", "STX", "WDC")}
ixic = [(x["date"], x["close"]) for x in load("us__IXIC.json")]
kospi = [(x["date"], x["close"]) for x in load("naver_index_KOSPI.json")]
CN = [("兆易创新", "sh603986"), ("澜起科技", "sh688008"), ("佰维存储", "sh688525"),
      ("江波龙", "sz301308"), ("深科技", "sz000021"), ("北京君正", "sz300223"),
      ("香农芯创", "sz300475")]
cn = {c: [(x["date"], x["close"]) for x in load("cn_%s.json" % c)] for _, c in CN}
HT, ZT = "sh600487", "sh600522"
ht = [(x["date"], x["close"]) for x in load("cn_%s.json" % HT)]
zt = [(x["date"], x["close"]) for x in load("cn_%s.json" % ZT)]

nav = {d: v for d, v in load("nav025833.json")}
etf = {d: v for d, v in load("etf159326.json")}
idx = {x["date"]: x for x in load("idx931994_full.json")}
hs = {d: v for d, v in load("sh000300.json")}
cy = {d: v for d, v in load("sz399006.json")}

REP = "2026-10-15"       # 原报告数据截止日
TODAY = "2026-10-30"


# ------------------------------------------------------------------ 工具
def at(series, date):
    """<= date 的最后一个收盘。"""
    best = None
    for d, c in series:
        if d <= date:
            best = (d, c)
    return best


def ret(a, b):
    return (b / a - 1) * 100


def pc(v, d=1):
    return f"{v:+.{d}f}%"


def pct(v, d=1):
    return f"{v:.{d}f}%"


def num(v):
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


# ------------------------------------------------------------------ 个券指标
TICKERS = [
    ("三星电子", "005930.KS", "kr", krx["005930"]),
    ("SK海力士", "000660.KS", "kr", krx["000660"]),
    ("美光 MU", "MU", "us", us["MU"]),
    ("闪迪 SNDK", "SNDK", "us", us["SNDK"]),
    ("希捷 STX", "STX", "us", us["STX"]),
    ("西数 WDC", "WDC", "us", us["WDC"]),
] + [(n, c, "cn", cn[c]) for n, c in CN]

GROUP = {"kr": "韩股", "us": "美股", "cn": "A股"}

rows = []
for name, sym, g, s in TICKERS:
    s = sorted(s)
    dates = [d for d, c in s]
    closes = [c for d, c in s]
    cur = closes[-1]
    rep = at(s, REP)[1]
    # 6 月峰值（本轮周期）
    jun = [(d, c) for d, c in s if "2026-06-01" <= d <= "2026-07-15"]
    peak_d, peak = max(jun, key=lambda x: x[1])
    after = [(d, c) for d, c in s if d > REP]
    low_d, low = min(after, key=lambda x: x[1]) if after else (dates[-1], cur)
    sub = [(d, c) for d, c in after if d > low_d]
    hi_after = max(c for _, c in sub) if sub else None
    rows.append(dict(name=name, sym=sym, g=g, date=dates[-1], cur=cur, rep=rep,
                     ret=ret(rep, cur), peak=peak, peak_d=peak_d,
                     dd=ret(peak, cur), dd_rep=ret(peak, rep),
                     low=low, low_d=low_d, bounce=ret(low, hi_after) if hi_after else None,
                     relow=ret(low, cur)))

grp_ret = {}
for g in ("kr", "us", "cn"):
    vals = [r["ret"] for r in rows if r["g"] == g]
    grp_ret[g] = sum(vals) / len(vals)

kr_names = [r for r in rows if r["g"] == "kr"]
cn_rows = [r for r in rows if r["g"] == "cn"]
us_rows = [r for r in rows if r["g"] == "us"]

# ------------------------------------------------------------------ 估值
VAL = {}
for code, nm in (("005930", "三星电子"), ("000660", "SK海力士")):
    v = kr_val[code]
    s = sorted(krx[code])
    cur = s[-1][1]
    VAL[code] = dict(name=nm, per=v["per"], pbr=v["pbr"], bps=v["bps"], eps=v["eps"],
                     pbr_price_15=cur and v["bps"] * 1.5,
                     pbr_price_20=v["bps"] * 2.0,
                     cur=cur,
                     to15=ret(cur, v["bps"] * 1.5),
                     to20=ret(cur, v["bps"] * 2.0),
                     f0=at([(d, f) for d, c, f in kr10[code]], REP)[1],
                     f1=kr10[code][-1][2])

# ------------------------------------------------------------------ 外资持股路径
def foreign_path(code):
    return [(d, f) for d, c, f in kr10[code] if f and d >= "2026-06-01"]

# ------------------------------------------------------------------ 历史回撤事件
def episodes(s, min_depth=0.30, enter=0.05):
    s = sorted(s)
    out = []
    i, n = 1, len(s)
    peak, peak_d = s[0][1], s[0][0]
    while i < n:
        d, c = s[i]
        if c > peak:
            peak, peak_d = c, d
        if c / peak - 1 <= -enter:
            trough, trough_d, j, rec = c, d, i, None
            while j < n:
                d2, c2 = s[j]
                if c2 < trough:
                    trough, trough_d = c2, d2
                if c2 >= peak:
                    rec = (d2, j)
                    break
                j += 1
            if trough / peak - 1 <= -min_depth:
                out.append(dict(peak_d=peak_d, peak=peak, trough_d=trough_d,
                                trough=trough, depth=(trough / peak - 1) * 100,
                                rec_d=rec[0] if rec else None,
                                days_to_trough=(dt.date.fromisoformat(trough_d) -
                                                dt.date.fromisoformat(peak_d)).days,
                                days_to_rec=(dt.date.fromisoformat(rec[0]) -
                                             dt.date.fromisoformat(peak_d)).days if rec else None))
            if rec:
                i = rec[1]
                peak, peak_d = s[i][1], s[i][0]
                i += 1
            else:
                break
        i += 1
    return out


EP = []
for nm, s, isfull in (("SK海力士", krx["000660"], False), ("三星电子", krx["005930"], False),
                      ("美光 MU", us["MU"], True), ("西数 WDC", us["WDC"], True)):
    for e in episodes(s if isfull else s):
        e["name"] = nm
        EP.append(e)
EP.sort(key=lambda e: e["peak_d"])

# 回撤深度 vs 收复时间统计
def med(xs):
    xs = sorted(xs)
    n = len(xs)
    return (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2)


SHALLOW = [e for e in EP if -37.5 < e["depth"] <= -29.5 and e["days_to_rec"]]
DEEP = [e for e in EP if e["depth"] <= -37.5 and e["days_to_rec"]]
STAT = dict(
    s_n=len(SHALLOW), s_med=med([e["days_to_rec"] for e in SHALLOW]) / 365,
    s_min=min(e["days_to_rec"] for e in SHALLOW) / 365,
    s_max=max(e["days_to_rec"] for e in SHALLOW) / 365,
    d_n=len(DEEP), d_med=med([e["days_to_rec"] for e in DEEP]) / 365,
    d_min=min(e["days_to_rec"] for e in DEEP) / 365,
    d_max=max(e["days_to_rec"] for e in DEEP) / 365,
)

# ------------------------------------------------------------------ 电网设备口径
nav_est = nav["2026-10-29"] * (etf["2026-10-30"] / etf["2026-10-29"])
IDX_EST = idx["20261029"]["close"] * (etf["2026-10-30"] / etf["2026-10-29"])
GRID = dict(nav_est=nav_est, etf_chg=ret(etf["2026-10-29"], etf["2026-10-30"]),
            nav_peak=nav["2026-06-22"])


def g_ret(start):
    return dict(nav=ret(nav[start], nav_est), etf=ret(etf[start], etf["2026-10-30"]),
                hs=ret(hs[start], hs["2026-10-30"]), cy=ret(cy[start], cy["2026-10-30"]))


SC = {k: g_ret(k) for k in ("2026-06-22", "2026-09-29", "2026-10-15", "2026-10-16")}

# ------------------------------------------------------------------ 相关性
def rets(m):
    ks = sorted(m)
    return {ks[i]: m[ks[i]] / m[ks[i - 1]] - 1 for i in range(1, len(ks))}


rh = rets(dict(krx["000660"]))
rs = rets(dict(krx["005930"]))
rht = rets(dict(ht))
rzt = rets(dict(zt))
rcy = rets(cy)


def corr(a, b, lo, hi):
    ds = [d for d in sorted(set(a) & set(b)) if lo <= d <= hi]
    xs = [a[d] for d in ds]
    ys = [b[d] for d in ds]
    n = len(xs)
    if n < 8:
        return 0, n
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return (cov / (sx * sy) if sx * sy else 0), n


COR = {}
for lab, lo, hi in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-30"),
                    ("15d", "2026-10-08", "2026-10-30")):
    COR[lab] = dict(
        hy_ht=corr(rh, rht, lo, hi)[0], hy_zt=corr(rh, rzt, lo, hi)[0],
        hy_cy=corr(rh, rcy, lo, hi)[0], ht_cy=corr(rht, rcy, lo, hi)[0],
        ss_ht=corr(rs, rht, lo, hi)[0], n=corr(rh, rht, lo, hi)[1],
    )

# 10/30 当天同步下跌
DAY = {}
for nm, m in (("SK海力士", dict(krx["000660"])),
              ("三星电子", dict(krx["005930"])),
              ("亨通光电", dict(ht)), ("中天科技", dict(zt)),
              ("创业板指", cy), ("沪深300", hs)):
    ks = [d for d in sorted(m) if d <= "2026-10-30"]
    if ks[-1] == "2026-10-30":
        DAY[nm] = (ret(m[ks[-2]], m[ks[-1]]), m[ks[-2]], m[ks[-1]])

# ------------------------------------------------------------------ 指数
def idx_ret(series):
    s = sorted(series)
    rep = at(s, REP)[1]
    return ret(rep, s[-1][1]), s[-1][0]


KOSPI_R = idx_ret(kospi)
IXIC_R = idx_ret(ixic)


# ------------------------------------------------------------------ 图表
def _ord(d):
    return dt.date.fromisoformat(d).toordinal()


def _fmt_date(d, span):
    y, m, dd = d.split("-")
    if span > 200:
        return f"{int(m)}月"
    return f"{int(m)}/{int(dd)}"


def nice_ticks(lo, hi, want=5):
    span = max(hi - lo, 1e-9)
    raw = span / want
    mag = 10 ** math.floor(math.log10(raw))
    step = mag * 10
    for m in (1, 2, 2.5, 5, 10):
        if span / (mag * m) <= want + 0.4:
            step = mag * m
            break
    v = math.ceil(lo / step) * step
    out = []
    while v <= hi + 1e-9:
        out.append(round(v, 6))
        v += step
    return out, step


def _textw(t):
    return sum(11.6 if ord(ch) > 127 else 6.4 for ch in t)


def line_chart(series, annotations=(), w=1000, h=400, baseline=None,
               ylab="", ymin=None, ymax=None):
    L, R, B = 62, 122, 46
    # ---- 图例排版（先算行数，再决定上边距）
    items = [s for s in series if not s.get("hide_legend")]
    rows, cur, lx = 1, [], 0.0
    for s in items:
        label = s["name"] + (f'  {s["end"]}' if s.get("end") else "")
        wdt = 24 + _textw(label) + 26
        if lx + wdt > w - R - L and cur:
            rows += 1
            cur, lx = [], 0.0
        cur.append((s, wdt))
        lx += wdt
    T = 26 + 20 * rows

    allpts = [p for s in series for p in s["pts"]]
    xs = [_ord(p[0]) for p in allpts]
    ys = [p[1] for p in allpts]
    x0, x1 = min(xs), max(xs)
    lo, hi = (min(ys), max(ys)) if ymin is None else (ymin, ymax)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    span = x1 - x0
    def X(d): return L + (_ord(d) - x0) / span * (w - L - R)
    def Y(v): return T + (hi - v) / (hi - lo) * (h - T - B)

    out = [f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto;display:block" font-family="inherit" role="img">']
    ticks, step = nice_ticks(lo, hi, 5)
    for v in ticks:
        y = Y(v)
        if y < T - 1 or y > h - B + 1:
            continue
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-R}" y2="{y:.1f}" stroke="#232c38" stroke-width="1"/>')
        out.append(f'<text x="{L-9}" y="{y+4:.1f}" fill="#6b7683" font-size="11" text-anchor="end">{v:g}</text>')
    dates = sorted({p[0] for p in allpts})
    for i in range(7):
        d = dates[round(i * (len(dates) - 1) / 6)]
        out.append(f'<text x="{X(d):.1f}" y="{h-B+20}" fill="#6b7683" font-size="11" text-anchor="middle">{_fmt_date(d, span)}</text>')
        out.append(f'<line x1="{X(d):.1f}" y1="{h-B}" x2="{X(d):.1f}" y2="{h-B+4}" stroke="#2d3644"/>')
    if baseline is not None:
        out.append(f'<line x1="{L}" y1="{Y(baseline):.1f}" x2="{w-R}" y2="{Y(baseline):.1f}" stroke="#5b6675" stroke-width="1" stroke-dasharray="5,5" opacity=".8"/>')
    if ylab:
        out.append(f'<text x="{L}" y="{T-8}" fill="#6b7683" font-size="10.5" text-anchor="start">{ylab}</text>')

    for s in series:
        pts = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in s["pts"])
        dash = f' stroke-dasharray="{s["dash"]}"' if s.get("dash") else ""
        out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="{s.get("width",2.2)}" stroke-linejoin="round" stroke-linecap="round"{dash} points="{pts}"/>')
        d, v = s["pts"][-1]
        out.append(f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="3.2" fill="{s["color"]}"/>')

    for a in annotations:
        x = X(a["date"])
        color = a.get("color", "#e3b341")
        out.append(f'<line x1="{x:.1f}" y1="{T-4}" x2="{x:.1f}" y2="{h-B}" stroke="{color}" stroke-width="1" stroke-dasharray="3,4" opacity=".5"/>')
        ty = a.get("y", T + 14)
        anchor = a.get("anchor", "middle")
        tx = x + a.get("dx", 0)
        label = a["text"]
        bw = _textw(label) + 10
        bx = tx - bw / 2 if anchor == "middle" else (tx if anchor == "start" else tx - bw)
        bx = max(L, min(bx, w - 6 - bw))
        out.append(f'<rect x="{bx:.1f}" y="{ty-13}" width="{bw:.1f}" height="19" rx="4" fill="#0d1117" opacity=".86"/>')
        out.append(f'<text x="{tx:.1f}" y="{ty}" fill="{color}" font-size="11.5" text-anchor="{anchor}">{label}</text>')

    # 图例
    lx, ly, n = L, 16, 0
    for s in items:
        label = s["name"] + (f'  {s["end"]}' if s.get("end") else "")
        wdt = 24 + _textw(label) + 26
        if lx + wdt > w - R - L and n:
            lx, ly, n = L, ly + 20, 0
        out.append(f'<line x1="{lx}" y1="{ly-4}" x2="{lx+14}" y2="{ly-4}" stroke="{s["color"]}" stroke-width="2.4"/>')
        out.append(f'<text x="{lx+19}" y="{ly}" fill="#9aa7b4" font-size="11.5">{s["name"]}</text>')
        if s.get("end"):
            out.append(f'<text x="{lx+19+_textw(s["name"])+6:.1f}" y="{ly}" fill="{s["color"]}" font-size="11.5" font-weight="700">{s["end"]}</text>')
        lx += wdt
        n += 1
    out.append("</svg>")
    return "".join(out)


def bar_chart(rows, w=1000, left=104, right=86):
    rh, gap = 26, 7
    h = 46 + len(rows) * (rh + gap)
    lo = min(0, min(r[1] for r in rows)) - 3
    hi = max(0, max(r[1] for r in rows)) + 3
    X = lambda v: left + (v - lo) / (hi - lo) * (w - left - right)
    out = [f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto;display:block" font-family="inherit">']
    out.append(f'<text x="{w-10}" y="16" fill="#6b7683" font-size="11" text-anchor="end">分组</text>')
    out.append(f'<line x1="{X(0):.1f}" y1="26" x2="{X(0):.1f}" y2="{h-16}" stroke="#3a4553" stroke-width="1"/>')
    for i, (name, v, note) in enumerate(rows):
        y = 28 + i * (rh + gap)
        color = "#f85149" if v >= 0 else "#3fb950"
        x1, x2 = sorted([X(0), X(v)])
        out.append(f'<rect x="{x1:.1f}" y="{y}" width="{max(1.5, x2-x1):.1f}" height="{rh}" rx="3" fill="{color}" opacity=".78"/>')
        out.append(f'<text x="{left-10}" y="{y+rh/2+4:.1f}" fill="#c9d3df" font-size="12" text-anchor="end">{name}</text>')
        tx = X(v) + (6 if v >= 0 else -6)
        out.append(f'<text x="{tx:.1f}" y="{y+rh/2+4:.1f}" fill="{color}" font-size="12" font-weight="600" text-anchor="{"start" if v>=0 else "end"}">{v:+.1f}%</text>')
        if note:
            out.append(f'<text x="{w-10}" y="{y+rh/2+4:.1f}" fill="#6b7683" font-size="11" text-anchor="end">{note}</text>')
    out.append("</svg>")
    return "".join(out)


def norm(pts, base_date=None):
    base = at(pts, base_date)[1] if base_date else pts[0][1]
    return [(d, c / base * 100) for d, c in pts if d >= (base_date or pts[0][0])]


# 图1：报告日 = 100
SER1 = [
    ("SK海力士", "#2f6fed", kr10["000660"]),
    ("三星电子", "#39c5cf", kr10["005930"]),
    ("美光 MU", "#e3b341", us["MU"]),
    ("A股存储链等权", "#f85149", None),
    ("创业板指", "#bc8cff", [(d, v) for d, v in sorted(cy.items())]),
]
# A股等权指数
cn_dates = sorted(set.intersection(*[set(d for d, _ in cn[c]) for _, c in CN]))
cn_eq = []
start = at([(d, 0) for d in cn_dates], REP)[0]
for d in cn_dates:
    if d < start:
        continue
    vals = []
    for _, c in CN:
        m = dict(cn[c])
        vals.append(m[d] / at(cn[c], REP)[1])
    cn_eq.append((d, sum(vals) / len(vals) * 100))

chart1 = line_chart([
    dict(name="SK海力士", color="#2f6fed", pts=norm(krx["000660"], REP), width=2.6,
         end=pc(rows[1]["ret"])),
    dict(name="三星电子", color="#39c5cf", pts=norm(krx["005930"], REP), width=2.4,
         end=pc(rows[0]["ret"])),
    dict(name="美光 MU", color="#e3b341", pts=norm(us["MU"], REP), end=pc(rows[2]["ret"])),
    dict(name="A股存储链等权", color="#f85149", pts=[(d, v) for d, v in cn_eq], end=pc(grp_ret["cn"])),
    dict(name="创业板指", color="#bc8cff", pts=norm([(d, v) for d, v in sorted(cy.items())], REP), end=pc(ret(cy[REP], cy["2026-10-30"])), dash="4,3"),
], baseline=100, h=400, annotations=[
    dict(date="2026-10-20", text="10/20 韩股二次探底（海力士 1,190,000）", color="#8b949e", y=340, dx=-8, anchor="end"),
])

# 图2：6/1 全景
chart2 = line_chart([
    dict(name="SK海力士", color="#2f6fed", pts=norm(krx["000660"], "2026-06-01"),
         end=pc(ret(at(krx["000660"], "2026-06-01")[1], krx["000660"][-1][1]))),
    dict(name="三星电子", color="#39c5cf", pts=norm(krx["005930"], "2026-06-01"),
         end=pc(ret(at(krx["005930"], "2026-06-01")[1], krx["005930"][-1][1]))),
    dict(name="美光 MU", color="#e3b341", pts=norm(us["MU"], "2026-06-01"), end=pc(ret(at(us["MU"], "2026-06-01")[1], us["MU"][-1][1]))),
    dict(name="创业板指", color="#bc8cff", pts=norm([(d, v) for d, v in sorted(cy.items())], "2026-06-01"),
         end=pc(ret(at([(d, v) for d, v in sorted(cy.items())], "2026-06-01")[1], cy["2026-10-30"])), dash="4,3"),
], baseline=100, h=420, ylab="6/1=100", annotations=[
    dict(date="2026-06-22", text="6/22 存储三巨头同步见顶", color="#f85149", y=66, dx=10, anchor="start"),
    dict(date="2026-07-30", text="7/30 第一只脚", color="#8b949e", y=90, dx=-8, anchor="end"),
    dict(date="2026-10-15", text="10/15 报告发布（第二只脚）", color="#e3b341", y=64, dx=-8, anchor="end"),
])

# 图3：电网设备净值（6/1 起）
chart3 = line_chart([
    dict(name="025833 净值", color="#e3b341", pts=[(d, v / nav["2026-06-01"] * 100) for d, v in sorted(nav.items()) if d >= "2026-06-01"],
         width=2.6, end=pc(ret(nav["2026-06-01"], nav_est))),
    dict(name="931994 指数", color="#58a6ff",
         pts=[(d[:4] + "-" + d[4:6] + "-" + d[6:], x["close"] / idx["20260601"]["close"] * 100)
              for d, x in sorted(idx.items()) if d >= "20260601"],
         end=pc(ret(idx["20260601"]["close"], IDX_EST))),
    dict(name="创业板指", color="#bc8cff", pts=[(d, v / cy["2026-06-01"] * 100) for d, v in sorted(cy.items()) if d >= "2026-06-01"],
         end=pc(ret(cy["2026-06-01"], cy["2026-10-30"])), dash="4,3"),
], baseline=100, h=400, ylab="6/1=100", annotations=[
    dict(date="2026-09-29", text="9/29 电网报告", color="#8b949e", y=66, dx=8, anchor="start"),
    dict(date="2026-10-15", text="10/15 存储报告 → 你清仓", color="#e3b341", y=92, dx=-8, anchor="end"),
])

# 图4：个券条形
BAR = bar_chart([(r["name"], r["ret"], GROUP[r["g"]]) for r in
                 sorted(rows, key=lambda x: x["ret"])])

# ------------------------------------------------------------------ HTML 片段
row_html = ""
for r in sorted(rows, key=lambda x: (x["g"] != "kr", x["g"] != "us", -x["ret"])):
    row_html += (
        f'<tr><td>{r["name"]}<span class="tag-mini">{GROUP[r["g"]]}</span></td>'
        f'<td class="num dim">{r["date"]}</td>'
        f'<td class="num">{r["rep"]:,.2f}</td>'
        f'<td class="num">{r["cur"]:,.2f}</td>'
        f'<td class="num {"up" if r["ret"] > 0 else "down"}">{pc(r["ret"])}</td>'
        f'<td class="num dim">{r["peak_d"][5:]}</td>'
        f'<td class="num {"up" if r["dd"] > -50 else "down"}">{pc(r["dd"])}</td>'
        f'<td class="num dim">{r["low_d"][5:]}</td>'
        f'<td class="num {"up" if (r["bounce"] or 0) > 0 else "down"}">{pc(r["bounce"]) if r["bounce"] is not None else "新低中"}</td>'
        f'<td class="num {"up" if r["relow"] > 0 else "down"}">{pc(r["relow"])}</td></tr>'
    )

ep_html = ""
for e in EP:
    rec = e["rec_d"] if e["rec_d"] else "未收复"
    yrs = f'{e["days_to_rec"]/365:.1f} 年' if e["days_to_rec"] else "—"
    cur_ep = e["peak_d"] >= "2026-06"
    tr_cls = ' class="hl-row"' if cur_ep else ""
    ep_html += (
        f'<tr{tr_cls}><td>{e["name"]}</td>'
        f'<td class="num dim">{e["peak_d"]}</td><td class="num">{num(e["peak"])}</td>'
        f'<td class="num dim">{e["trough_d"]}</td><td class="num">{num(e["trough"])}</td>'
        f'<td class="num down">{e["depth"]:.1f}%</td>'
        f'<td class="num dim">{rec}</td><td class="num">{yrs}</td></tr>'
    )

sc_html = ""
for lab, key, note in (("6/22 起一直持有", "2026-06-22", "从真顶拿到今天的反面参照"),
                       ("9/29 电网报告后", "2026-09-29", "原报告建议减仓"),
                       ("10/15 存储报告后", "2026-10-15", "你说清仓的那天"),
                       ("10/16 次日开盘", "2026-10-16", "实际成交更可能在这天")):
    v = SC[key]
    sc_html += (
        f'<tr><td>{lab}<div class="tag-mini">{note}</div></td>'
        f'<td class="num">{nav[key]:.4f}</td>'
        f'<td class="num dim">{nav_est:.4f}</td>'
        f'<td class="num down">{pc(v["nav"])}</td>'
        f'<td class="num down">{pc(v["etf"])}</td>'
        f'<td class="num {"down" if v["hs"] < 0 else "up"}">{pc(v["hs"])}</td>'
        f'<td class="num {"down" if v["cy"] < 0 else "up"}">{pc(v["cy"])}</td>'
        f'<td class="num {"up" if v["nav"] - v["hs"] > 0 else "down"}">{(v["nav"] - v["hs"]):+.1f}pp</td></tr>'
    )

day_html = ""
for nm, (chg, p, c) in DAY.items():
    day_html += f'<tr><td>{nm}</td><td class="num dim">{p:,.2f}</td><td class="num">{c:,.2f}</td><td class="num {"up" if chg > 0 else "down"}">{pc(chg, 2)}</td></tr>'

CSS = """
:root{
  --bg:#0b0f14;--card:#141a22;--card2:#1a212b;--line:#26303c;
  --tx:#e6edf3;--tx2:#9aa7b4;--tx3:#6b7683;
  --red:#f85149;--green:#3fb950;--blue:#58a6ff;--gold:#e3b341;--purple:#bc8cff;--cyan:#39c5cf;
}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;line-height:1.78;font-size:15px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:34px 22px 90px}
a{color:var(--blue);text-decoration:none;border-bottom:1px solid rgba(88,166,255,.25)}
a:hover{border-bottom-color:var(--blue)}
header{padding:30px 0 26px;border-bottom:1px solid var(--line);margin-bottom:8px}
.kicker{font-size:12px;letter-spacing:2.4px;color:var(--gold);font-weight:700;margin-bottom:12px}
h1{font-size:31px;line-height:1.35;font-weight:800;letter-spacing:.2px}
h1 .sub{display:block;font-size:17px;font-weight:500;color:var(--tx2);margin-top:8px;letter-spacing:0}
.meta{color:var(--tx3);font-size:12.5px;margin-top:16px;line-height:1.9}
.meta b{color:var(--tx2);font-weight:600}
h2{font-size:21px;margin:56px 0 6px;display:flex;align-items:baseline;gap:12px;letter-spacing:.2px}
h2 .no{font-size:13px;color:var(--gold);font-weight:800;letter-spacing:1px;font-variant-numeric:tabular-nums}
h2::after{content:"";flex:1;height:1px;background:var(--line);margin-left:4px}
h3{font-size:16px;margin:26px 0 8px;color:var(--tx)}
p{margin:9px 0;color:#d5dee8}
.lead{font-size:15.5px;color:var(--tx2)}
small,.small{font-size:12.5px;color:var(--tx2)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0}
.card.tight{padding:14px 16px}
.verdict{border-left:4px solid var(--gold);background:linear-gradient(90deg,rgba(227,179,65,.10),rgba(20,26,34,0) 62%);border-radius:0 12px 12px 0;padding:20px 24px}
.verdict .tag{display:inline-block;background:var(--gold);color:#111;font-weight:800;font-size:11.5px;padding:2px 11px;border-radius:20px;margin-bottom:10px;letter-spacing:.6px}
.verdict p{font-size:16px;line-height:1.85;color:#e9eff6;margin:6px 0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0 6px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:15px 14px;text-align:center}
.kpi .v{font-size:25px;font-weight:800;letter-spacing:-.3px;font-variant-numeric:tabular-nums}
.kpi .k{font-size:11.5px;color:var(--tx2);margin-top:4px;line-height:1.5}
.kpi .s{font-size:11px;color:var(--tx3);margin-top:2px}
.up{color:var(--red)}.down{color:var(--green)}.dim{color:var(--tx3)}
.gold{color:var(--gold)}.blue{color:var(--blue)}.cyan{color:var(--cyan)}.purple{color:var(--purple)}
.hl{color:var(--gold);font-weight:700}
.hlb{color:var(--blue);font-weight:700}
.hlg{color:var(--green);font-weight:700}
.hlr{color:var(--red);font-weight:700}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th{background:var(--card2);color:var(--tx2);font-weight:600;padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap;font-size:12.5px}
td{padding:7px 10px;text-align:right;border-bottom:1px solid #1d2530;white-space:nowrap;vertical-align:middle}
th:first-child,td:first-child{text-align:left;white-space:normal}
td.num{font-variant-numeric:tabular-nums}
tr:hover td{background:rgba(88,166,255,.04)}
tr.hl-row td{background:rgba(227,179,65,.06)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tag-mini{display:inline-block;font-size:10.5px;color:var(--tx3);border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-left:6px;vertical-align:1px;font-weight:400}
.timeline{margin:16px 0 0;padding-left:22px;border-left:1px solid var(--line)}
.tl{position:relative;padding:0 0 18px 18px}
.tl::before{content:"";position:absolute;left:-26px;top:7px;width:8px;height:8px;border-radius:50%;background:var(--tx3);box-shadow:0 0 0 3px var(--bg)}
.tl.key::before{background:var(--gold);box-shadow:0 0 0 3px var(--bg),0 0 0 5px rgba(227,179,65,.18)}
.tl .d{font-size:12px;color:var(--gold);font-weight:700;letter-spacing:.5px;font-variant-numeric:tabular-nums}
.tl .t{font-size:14px;color:var(--tx);margin-top:1px}
.tl .t b{color:#fff}
.tl .t span{color:var(--tx2)}
.judge{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:14px 0}
.jcard{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:var(--card)}
.jcard.ok{border-top:3px solid var(--green)}
.jcard.no{border-top:3px solid var(--red)}
.jcard.mid{border-top:3px solid var(--gold)}
.jcard h4{font-size:14.5px;margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;gap:8px}
.jcard h4 .badge{font-size:11px;font-weight:800;padding:1px 8px;border-radius:20px;letter-spacing:.4px}
.badge.ok{background:rgba(63,185,80,.16);color:var(--green)}
.badge.no{background:rgba(248,81,73,.16);color:var(--red)}
.badge.mid{background:rgba(227,179,65,.16);color:var(--gold)}
.jcard p{font-size:13.5px;color:var(--tx2);margin:6px 0}
.jcard p b{color:var(--tx)}
.quote{border-left:3px solid var(--blue);background:rgba(88,166,255,.05);padding:10px 16px;margin:14px 0;border-radius:0 8px 8px 0;color:#c8d6e6;font-size:14px}
.quote b{color:#fff}
.nums{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
.num-box{background:var(--card2);border-radius:10px;padding:13px 15px;border:1px solid var(--line)}
.num-box .t{font-size:11.5px;color:var(--tx3);letter-spacing:.4px}
.num-box .v{font-size:20px;font-weight:800;margin-top:3px;font-variant-numeric:tabular-nums}
.num-box .s{font-size:12px;color:var(--tx2);margin-top:2px}
.lesson{margin:16px 0;padding:16px 18px 15px 20px;background:var(--card);border:1px solid var(--line);border-radius:12px;border-left:3px solid var(--cyan)}
.lesson .n{font-size:11.5px;color:var(--cyan);font-weight:800;letter-spacing:1.4px}
.lesson h4{font-size:15.5px;margin:3px 0 6px}
.lesson p{font-size:13.5px;color:var(--tx2);margin:5px 0}
.lesson p b{color:var(--tx)}
.lesson .act{font-size:13px;color:#cfe6ea;background:rgba(57,197,207,.07);border-radius:7px;padding:7px 12px;margin-top:9px}
.lesson .act b{color:var(--cyan)}
.check{list-style:none;padding:0;margin:10px 0}
.check li{position:relative;padding:9px 0 9px 30px;border-bottom:1px dashed #222c38;font-size:13.8px;color:var(--tx2)}
.check li:last-child{border-bottom:0}
.check li::before{content:"";position:absolute;left:4px;top:15px;width:12px;height:12px;border:1.5px solid var(--tx3);border-radius:3px}
.check li b{color:var(--tx)}
.tagrow{display:flex;flex-wrap:wrap;gap:7px;margin:8px 0 0}
.pill{display:inline-block;font-size:11.5px;padding:1px 9px;border-radius:20px;font-weight:600;letter-spacing:.2px}
.pill.red{background:rgba(248,81,73,.14);color:var(--red)}
.pill.green{background:rgba(63,185,80,.14);color:var(--green)}
.pill.gold{background:rgba(227,179,65,.14);color:var(--gold)}
.pill.blue{background:rgba(88,166,255,.14);color:var(--blue)}
.note{font-size:12px;color:var(--tx3);margin-top:7px;line-height:1.7}
.hr{height:1px;background:var(--line);margin:34px 0}
footer{margin-top:60px;padding-top:20px;border-top:1px solid var(--line);font-size:12.3px;color:var(--tx3);line-height:1.85}
footer b{color:var(--tx2)}
.src{font-size:12.3px;color:var(--tx3);line-height:1.9}
@media(max-width:860px){
  .kpis{grid-template-columns:1fr 1fr}
  .judge,.nums{grid-template-columns:1fr}
  h1{font-size:25px}
  .wrap{padding:24px 16px 70px}
  h2{font-size:19px;margin-top:44px}
}
"""

KR = {r["name"]: r for r in rows}
HY, SS, MU, WDC = KR["SK海力士"], KR["三星电子"], KR["美光 MU"], KR["西数 WDC"]
v_ss, v_hy = VAL["005930"], VAL["000660"]

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>存储股复盘：说“别接飞刀”15 天后，韩股反弹了 13%</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">REVIEW · 存储股 · 2026-10-30</div>
  <h1>说“别接飞刀”的 15 天后：韩股反弹 13%，A 股还在创新低
    <span class="sub">回头看 10/15 那份三星 / 海力士报告——对在哪一步、错在哪一步、偏差多大，以及你顺手清掉电网设备这一笔</span>
  </h1>
  <div class="meta">
    原报告：<b>2026-10-15</b>（韩股/A 股当日收盘，美股 10/14）　｜　复盘：<b>2026-10-30</b> 收盘<br>
    数据口径：韩股 <b>Naver 日线</b>（含外资持股）、美股 <b>新浪财经日线</b>（Yahoo 自 10/30 起大陆 403）、A 股 <b>腾讯前复权</b>、电网设备 <b>中证官网 + 天天基金</b><br>
    <b>注意收盘时点</b>：美股数据截至 10/29（今日未开盘），韩股/A 股为 10/30 收盘
  </div>
</header>

<div class="card verdict">
  <span class="tag">复盘结论</span>
  <p><b class="hl">框架对了，时间尺度错了。</b>“PER 便宜是峰值利润的幻觉、要用 PBR 和周期位置判断”——这套逻辑今天依然成立，海力士 PBR 从 3.43 涨到 <b>3.79</b>、三星 2.44 → <b>2.57</b>，离报告自己定的“安全边际”（1.5 / 2.0）反而更远了。<b class="hlr">但报告是在二次探底当天说“恐慌加速段、别接飞刀”的</b>：三星 10/15 收 207,500 韩元，正好落在 7/30 的低点 207,000 上；海力士 3 个交易日后见底（10/20），随后 7 个交易日反弹 <b>+27.4%</b>。</p>
  <p>15 天成绩单：<b class="hlb">海力士 {pc(HY['ret'])}、三星 {pc(SS['ret'])}、A 股存储链等权 {pc(grp_ret['cn'])}</b>（7 只里 5 只今天创出新低）。“存储崩盘”从来不是一个板块，而是三条节奏完全不同的链。</p>
  <p>你清掉电网设备：<b class="hlg">结果对</b>——10/15 之后它又跌了 {pc(SC['2026-10-15']['nav'])}，你少亏了这些钱；<b class="hlr">但归因错了</b>——你躲开的不是“存储崩盘”，是“高 β 成长杀估值”。存储与电网的日收益相关性只有 <b>0.27~0.53</b>，而它们各自与创业板的相关性是 <b>0.55~0.72</b>。</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="v up">{pc(HY['ret'])}</div><div class="k">SK 海力士 · 报告日→今</div><div class="s">期间最高 {pc(HY['bounce'])}</div></div>
  <div class="kpi"><div class="v up">{pc(SS['ret'])}</div><div class="k">三星电子 · 报告日→今</div><div class="s">10/15 正好是二次探底</div></div>
  <div class="kpi"><div class="v down">{pc(grp_ret['cn'])}</div><div class="k">A 股存储链等权</div><div class="s">7 只里 5 只今日新低</div></div>
  <div class="kpi"><div class="v down">{pc(SC['2026-10-15']['nav'])}</div><div class="k">025833 · 报告日→今</div><div class="s">你避开的这一段</div></div>
</div>
<p class="note">“期间最高”= 报告日后最低点 → 其后最高收盘，衡量反弹力度，而非你的实际收益。海力士 10/20 见 1,190,000，10/29 收 1,516,000。</p>

<h2><span class="no">01</span>这 15 天，数字上发生了什么</h2>
<p class="lead">先看结果。所有收益都以 <b>10/15 收盘</b>（报告数据截止日）为起点，终点为各市场最新收盘。</p>

<div class="card tight">
{chart1}
<p class="note">归一化：10/15 = 100。虚线为创业板指（同期 {pc(ret(cy[REP], cy['2026-10-30']))}），用来对照“高 β 成长”这条共同因子。A 股存储链等权为 7 只等权平均（佰维、江波龙等权重相同，不代表真实仓位）。</p>
</div>

<div class="scroll">
<table>
<thead><tr><th>标的</th><th>数据日</th><th>10/15</th><th>10/30</th><th>报告日→今</th><th>6 月顶</th><th>距顶</th><th>报告后最低</th><th>低点→最高</th><th>距低点</th></tr></thead>
<tbody>{row_html}</tbody>
</table>
</div>
<p class="note">“6 月顶”取 2026-06-01~07-15 的最高收盘；“报告后最低”取 10/15 之后的收盘最低点及其日期；“距低点”= 现价相对那个最低点。<br>
数据源从 Yahoo 换成 Naver 后，与原报告有约 1 个百分点的差异（原报告：三星 -42.1%、海力士 -56.7%；本页按 Naver 收盘为 -42.8% / -57.6%），属于数据商收盘价差异，不影响结论。</p>

{chart2}
<p class="note">6/1 = 100 的全景。三巨头 6 月中旬同步见顶，7 月底第一只脚，10 月中第二只脚——<b>10/15 那份报告，恰好写在第二只脚的脚底上</b>。三星二次探底 207,500 vs 7/30 的 207,000，差 0.24%。</p>

<div class="nums">
  <div class="num-box"><div class="t">KOSPI（同期）</div><div class="v up">{pc(KOSPI_R[0])}</div><div class="s">存储崩了，大盘没崩</div></div>
  <div class="num-box"><div class="t">纳斯达克（同期）</div><div class="v down">{pc(IXIC_R[0])}</div><div class="s">截至 {IXIC_R[1]}</div></div>
  <div class="num-box"><div class="t">海力士最大反弹</div><div class="v up">{pc(HY['bounce'])}</div><div class="s">7 个交易日（10/20→10/29）</div></div>
</div>

<h2><span class="no">02</span>分析对了什么：六条，都有事后证据</h2>

<div class="judge">
  <div class="jcard ok">
    <h4>① “板块性崩盘，不是系统性危机” <span class="badge ok">对，A</span></h4>
    <p>当时说：纳指只跌 3.3%，存储股跌 25~70%，这是行业周期反转而非宏观危机。</p>
    <p>后来：同期 KOSPI <b>{pc(KOSPI_R[0])}</b>、纳指 <b>{pc(IXIC_R[0])}</b>，存储三巨头从高点回撤 23%~52%。<b>大盘确实没跟着崩</b>。这条判断决定了后面的操作方向：这是“换仓”问题，不是“清仓离场”问题。</p>
  </div>
  <div class="jcard ok">
    <h4>② “PER 9.4 / 5.6 是峰值利润的幻觉” <span class="badge ok">对，A</span></h4>
    <p>当时说：看着便宜，但 EPS 是周期顶的 EPS；真正该看 PBR 和周期位置。</p>
    <p>后来：15 天过去，三星 EPS 仍是 <b>{v_ss['eps']:,.0f} 韩元</b>（2026.06 口径）、海力士 <b>{v_hy['eps']:,.0f}</b>，一个季度都没更新。所谓“9.4 倍 PE 的便宜货”（今天 9.9 倍），分母还是峰值。<b>用 PER 抄底存储，等于用峰值利润骗自己</b>——这条今天仍在保护你。</p>
  </div>
  <div class="jcard ok">
    <h4>③ “A 股存储链弹性最大、最脆弱” <span class="badge ok">对，A</span></h4>
    <p>当时说：A 股存储链最深 -70%，比韩股 -57% 更极端。</p>
    <p>后来：15 天内 A 股等权 <b>{pc(grp_ret['cn'])}</b>，韩股 <b>{pc(grp_ret['kr'])}</b>、美股 <b>{pc(grp_ret['us'])}</b>；7 只 A 股里 5 只今天创出新低，而三星、海力士都没跌破 10/20 的低点。<b>“最深回撤”确实等于“最脆弱”</b>。</p>
    <p>但要补一句当时没说的：<b>脆弱 ≠ 反弹弱</b>。10/15 之后 A 股这些名字也弹过一段——北京君正现在仍比报告日高 <b>{pc(KR['北京君正']['ret'])}</b>，澜起只差 {pc(KR['澜起科技']['ret'])}。区别不在弹性大小，在<b>反弹能不能站住</b>：韩股 10/20 的低点至今没破，A 股弹 3 天就被卖回来，今天 5 只创新低。<b>高 β 在下跌和反弹两端都放大，但只有站住的那一端算数。</b></p>
  </div>
  <div class="jcard mid">
    <h4>④ “外资在持续流出” <span class="badge mid">一半对，B</span></h4>
    <p>当时说：三星外资持股 90 日 47.81%→46.16%、海力士 51.27%→49.02%，资金在撤。</p>
    <p>后来：三星 <b>46.16% → {v_ss['f1']:.2f}%</b>（<b>几乎没动，流出停了</b>），海力士 <b>49.02% → {v_hy['f1']:.2f}%</b>（继续小幅流出）。海力士对，三星错——<b>把两只股票的外资行为当成一个“板块资金流”</b>，是当时一个粗糙的合并，而“外资在撤”这个结论对两只股票的含义并不一样。</p>
  </div>
  <div class="jcard mid">
    <h4>⑤ “只有需求没坏的短调才 9~15 个月 V 回” <span class="badge mid">未被触发，B+</span></h4>
    <p>当时说：过去 10 年 ≥30% 回撤全部对应周期顶，短调（2020、2024）才在 9~15 个月内 V 回。</p>
    <p>后来：这波反弹只用了 <b>7 个交易日</b>，远快于“9~15 个月的 V 回”，所以它<b>不属于</b>报告定义的“健康 V 回”，更像熊市里的高波动反抽。这条历史框架没有被证伪，但也没帮你赚到钱——见 04 节。</p>
  </div>
  <div class="jcard ok">
    <h4>⑥ 数据准确性 <span class="badge ok">对，A-</span></h4>
    <p>13 个标的、峰值日、区间涨跌、外资持股，逐项对得上，误差多在 1pp 以内（数据商差异）。<b>没有算错的数</b>——错的都是判断，不是算术。这一点其实很重要：它说明复盘该盯“推理链”，不是“数字”。</p>
  </div>
</div>

<h2><span class="no">03</span>分析错了什么：五条，第一条最贵</h2>

<div class="judge">
  <div class="jcard no">
    <h4>① 在二次探底当天说“恐慌加速段” <span class="badge no">错，致命</span></h4>
    <p>报告用“近 5 日三星 -21.8%、海力士 -26.6%”证明“恐慌还在加速”，隐含结论是<b>还要跌</b>。但 10/15 的位置是：三星 207,500 = 7/30 低点上方 0.24%；海力士 1,238,000 = 距 7 月底部只差 -6.4%。<b>这不是“加速段”，这是“第二只脚踩在第一只脚上”</b>。</p>
    <p>结果：10/16 起韩股直接反转，海力士 10/20 再插一根 -3.9% 后见底。<b>报告的“别接飞刀”，在最低点前 3 个交易日发出。</b>买在报告日：海力士 {pc(HY['ret'])}、三星 {pc(SS['ret'])}。</p>
  </div>
  <div class="jcard no">
    <h4>② “等缩量止跌 + 合约价企稳”没有可执行定义 <span class="badge no">错，方法论</span></h4>
    <p>报告给了两个信号：缩量止跌、存储合约价企稳。但<b>没给阈值、没给数据源、没给时间窗</b>。合约价是月度/季度数据，等它“企稳”通常落后股价 4~8 周——按这条执行，你会错过整段反弹，然后在合约价确认时买在更高位。</p>
    <p>等价于：报告写着“等确认”，实际含义是“永远不买”。<b>一个不可执行的信号，比一个错误的信号更危险，因为它看起来是谨慎的。</b></p>
  </div>
  <div class="jcard no">
    <h4>③ 把三条链当成一个板块 <span class="badge no">错，最影响操作</span></h4>
    <p>报告用“存储股”一个词覆盖韩股、美股、A 股。但 15 天内：韩股 <b>{pc(grp_ret['kr'])}</b>、美股 <b>{pc(grp_ret['us'])}</b>、A 股 <b>{pc(grp_ret['cn'])}</b>——<b>方向相反</b>。</p>
    <p>子因子不同：韩股定价 HBM/AI 存储的<b>当期盈利</b>（跌 59% 后估值先到位）；A 股定价国产替代的<b>想象空间 + 筹码结构</b>（跌 70% 后仍在挤泡沫）；美股定价<b>资本开支周期</b>。同一个“崩盘”标题，三种交易。</p>
  </div>
  <div class="jcard no">
    <h4>④ 历史类比越界：-59% 已破历史极值 <span class="badge no">错，置信度</span></h4>
    <p>报告说“同级别回撤（≥30%）过去 10 年全部对应周期顶”，用 4~5 个样本推出“1~3 年盈利下行”。但海力士本轮最大回撤 <b>-59.2%</b>（现价距顶 {HY['dd']:.1f}%），<b>超过 10 年最深记录 -49.7%（2015）</b>；三星 -42.9%，也追平了它自己的 -45.2%。</p>
    <p>历史样本被击穿之后，“按历史规律该跌 1~3 年”这句话的<b>概率含义已经模糊</b>：你既可以说“跌得比历史都深，所以还没完”，也可以说“跌得比历史都深，所以坏消息已透支”。<b>同一个事实支持两个相反结论时，它就不是证据。</b></p>
  </div>
  <div class="jcard no">
    <h4>⑤ 只给定性判断，没给概率 <span class="badge no">错，可证伪性</span></h4>
    <p>报告的原话是“长趋势开始的概率远大于短期回调”。没有数字、没有情景、没有“如果错了会怎样”。</p>
    <p>对比 <a href="../fund-025833-review/index.html">025833 复盘</a> 里那套“磨底 40% / 二次探底 27% / 修复 25% / 反转 8%”——<b>有概率的报告才能被打分</b>。没有概率的判断，事后只能靠“感觉它对不对”来评价，这等于放弃了复盘。</p>
  </div>
</div>

<h2><span class="no">04</span>预估 vs 实际：偏差量化</h2>
<p class="lead">把报告里可检验的说法逐条拆出来打分。评分只看“15 天内是否被数据支持”，长周期判断标“待验证”。</p>

<div class="scroll">
<table>
<thead><tr><th>报告的说法（10/15）</th><th>15 天后的实际</th><th>判定</th></tr></thead>
<tbody>
<tr><td>“这不是普通回调，是泡沫破裂”</td><td>海力士 -59.2% 后反弹 27.4%，仍距顶 {HY['dd']:.1f}%；三星距顶 {SS['dd']:.1f}%</td><td class="gold">部分兑现</td></tr>
<tr><td>“长趋势开始的概率远大于短期回调”</td><td>韩股 {pc(grp_ret['kr'])}、纳指 {pc(IXIC_R[0])}；两周期证据不足</td><td class="dim">待验证</td></tr>
<tr><td>“现在不接飞刀”</td><td>韩股 {pc(grp_ret['kr'])}（最高 {pc(HY['bounce'])}）、美股 {pc(grp_ret['us'])}、A 股 {pc(grp_ret['cn'])}</td><td class="gold">韩美错 / A 股对</td></tr>
<tr><td>“三星 PBR 回到 1.5 以下、海力士 2 以下才有安全边际”</td><td>现在 {v_ss['pbr']} / {v_hy['pbr']}；对应股价还要跌 {v_ss['to15']:.0f}% / {v_hy['to20']:.0f}%</td><td class="up">规则有效</td></tr>
<tr><td>“外资持续流出”</td><td>三星 46.16→{v_ss['f1']:.2f}（停）、海力士 49.02→{v_hy['f1']:.2f}（续）</td><td class="dim">一半对</td></tr>
<tr><td>“A 股存储链最深 -70%”</td><td>佰维 {KR['佰维存储']['dd']:.1f}%、江波龙 {KR['江波龙']['dd']:.1f}%，今日 5 只创新低</td><td class="up">对</td></tr>
<tr><td>“板块性而非系统性”</td><td>KOSPI {pc(KOSPI_R[0])}、纳指 {pc(IXIC_R[0])}</td><td class="up">对</td></tr>
<tr><td>“其后 1~3 年盈利下行、2~4.7 年才收复前高”</td><td>15 天无法检验；但当前跌幅已破 10 年极值</td><td class="dim">待验证</td></tr>
</tbody>
</table>
</div>

<div class="card">
<h3>偏差最大的那一条，其实是“时间”</h3>
<p>报告对<b>方向</b>的判断，15 天后看是对的：存储仍在 -40%~-74% 的深坑里，A 股还在新低，PBR 没到安全边际。报告对<b>节奏</b>的判断，15 天后看是错的：它在最不该说“还要跌”的那一天说了“还要跌”。</p>
<p>这两件事的<b>赔率完全不同</b>：方向错了，你损失的是几倍的估值差；节奏错了，你损失的是 13%（海力士）到 27%（反弹幅度）的<b>入场机会</b>，而且是在你最想买的时候。</p>
<p class="note">如果把报告当成“3 年持有的入场判断”，它至今没错；如果当成“什么时候买”的判断，它错了 3 个交易日。同一份报告，两种读法，两种结局——这就是为什么报告必须写清楚<b>它回答的是哪个问题</b>。</p>
</div>

<h2><span class="no">05</span>历史坐标复查：那套“周期顶”规律还站得住吗</h2>
<p class="lead">10 年、四个标的、所有 ≥30% 的回撤。这张表是报告立论的底座，值得单独验一遍。</p>

<div class="scroll">
<table>
<thead><tr><th>标的</th><th>峰值日</th><th>峰值</th><th>谷底日</th><th>谷底</th><th>深度</th><th>收复前高</th><th>历时</th></tr></thead>
<tbody>{ep_html}</tbody>
</table>
</div>
<p class="note">口径：收盘价；“收复”= 收盘重新站上峰值；“历时”= 峰值到收复的自然年。三星 2015 年前数据未纳入（Naver 10 年窗口），样本共 20 个，仍是小样本——所有“历史概率”都该按 ±1 个标准误读。<br>
美光 2011/2014 两行的绝对价格是复权前的历史价（美光未拆股），与现在的 900 美元不可直接比较，只看百分比。</p>

<div class="card">
<h3>三条能用的结论</h3>
<p><b>1. “深度”确实是分水岭，但报告说得太整齐。</b>浅回撤（-30%~-37%，n={STAT['s_n']}）收复时间中位数 <b>{STAT['s_med']:.1f} 年</b>（{STAT['s_min']:.1f}~{STAT['s_max']:.1f} 年）；深回撤（≤-37%，n={STAT['d_n']}）中位数 <b>{STAT['d_med']:.1f} 年</b>（{STAT['d_min']:.1f}~{STAT['d_max']:.1f} 年，西数 10.8 年是 HDD 结构性衰退的异常值）。</p>
<p>两个例外值得记住：三星 2017 那次只跌 -34.6%，却用了 <b>2.2 年</b>才收复——因为它紧接着撞上了 2018 年的存储下行；美光 2021 那次只跌 -30.6%，<b>0.7 年</b>就回来了。<b>同样的跌幅，差 3 倍时间</b>，取决于你是在周期中部还是尾部受伤。</p>
<p><b>2. 但“周期顶”这个标签，这次被跌穿了。</b>海力士 10 年最深 -49.7%，本轮 <b>-59.2%</b>；三星 10 年最深 -45.2%，本轮 <b>-42.9%</b>（还没破）。<b>“历史最深”不是底，只是标尺</b>——标尺被折断时，它既不能证明“还要跌”，也不能证明“到底了”。</p>
<p><b>3. 反弹速度不能当反转证据。</b>历史上熊市里的反抽同样凶：海力士 2021-22 那轮 -49.5% 的大熊，中途也有 +27.7% 的 10 日反弹；本轮是 +27.4%（7 个交易日）。<b>只差 0.3pp。</b>所以“反弹 27%”这个事实，对“底部”和“死猫跳”两种假设<b>完全没有区分力</b>。</p>
</div>

<h2><span class="no">06</span>你清掉电网设备，这一笔到底对不对</h2>
<p class="lead">先给结论：<b class="hlg">结果对，钱是真省下来了；但让你赚钱的不是存储报告。</b>下面把四种口径都摊开。</p>

<div class="scroll">
<table>
<thead><tr><th>清仓时点</th><th>基金净值</th><th>10/30 估算</th><th>基金</th><th>ETF 159326</th><th>沪深300</th><th>创业板指</th><th>相对沪深300</th></tr></thead>
<tbody>{sc_html}</tbody>
</table>
</div>
<p class="note">10/30 基金净值未公布，估算 = 10/29 官方净值 {nav['2026-10-29']:.4f} ×（1 + 跟踪 ETF 10/30 涨跌 {GRID['etf_chg']:+.2f}%）= {nav_est:.4f}；指数用同一跌幅估算。<br>
“相对沪深300”= 基金跌幅 − 沪深300 跌幅，正值表示清仓比换到沪深300更划算（现金收益按 0% 计；放货基按年化 1.3~1.5% 折算约 +0.2%，可忽略）。</p>

{chart3}
<p class="note">025833 净值（6/1=100）。真正的顶是 6/22 的 1.556，你 10/15 清仓时它已经在 -35% 的位置。9/29 那份电网报告已经指出“这不是电网基金、是光纤 β”，10/15 的存储报告只是让你<b>下了最后决心</b>。</p>

<div class="judge">
  <div class="jcard ok">
    <h4>结果：对 <span class="badge ok">+{abs(SC['2026-10-15']['nav']):.1f}pp 的避险</span></h4>
    <p>10/15 之后两周，025833 又跌 <b>{pc(SC['2026-10-15']['nav'])}</b>，同期沪深300 {pc(SC['2026-10-15']['hs'])}、创业板 {pc(SC['2026-10-15']['cy'])}。<b>清仓=把“下跌”换成“不跌”</b>，10 万元少亏约 {abs(SC['2026-10-15']['nav'])*1000:,.0f} 元。</p>
    <p>如果更早（9/29 报告后）就清，避开的跌幅是 <b>{pc(SC['2026-09-29']['nav'])}</b>——晚清两周，避险效果只剩一半。<b>“减仓”这件事的价值随时间衰减</b>，因为跌得越深，剩下的空间越小。</p>
  </div>
  <div class="jcard no">
    <h4>归因：错 <span class="badge no">相关性只有 0.27~0.53</span></h4>
    <p>如果卖出的理由是“存储崩了 → AI 资本开支见顶 → 我持有的东西也会跌”，那 15 天的数据直接反驳了它：<b>存储反弹 {pc(grp_ret['kr'])} 的同时，电网设备继续跌 {pc(SC['2026-10-15']['nav'])}</b>。同一条“AI 链”，走出了相反方向。</p>
    <p>真实的相关性（日收益，2026 年 7-10 月）：海力士 vs 亨通 <b>{COR['H2']['hy_ht']:.2f}</b>、vs 中天 <b>{COR['H2']['hy_zt']:.2f}</b>；而亨通 vs 创业板 <b>{COR['H2']['ht_cy']:.2f}</b>、海力士 vs 创业板 <b>{COR['H2']['hy_cy']:.2f}</b>。<b>存储和电网不是一条链上的上下游，它们只是挂在“创业板/AI 成长”这一个共同因子上。</b></p>
  </div>
</div>

<h3>10/30 那天，两条链又同步了</h3>
<div class="scroll">
<table>
<thead><tr><th>标的</th><th>10/29</th><th>10/30</th><th>涨跌</th></tr></thead>
<tbody>{day_html}</tbody>
</table>
</div>
<p>今天是“共同因子回归”的一天：海力士 {pc(DAY['SK海力士'][0], 2)}、三星 {pc(DAY['三星电子'][0], 2)}、亨通 {pc(DAY['亨通光电'][0], 2)}、中天 {pc(DAY['中天科技'][0], 2)}、创业板 {pc(DAY['创业板指'][0], 2)} 一起跌。<b>这恰恰说明问题所在：它们的同步是“偶发”的，不是“结构性”的。</b>你在 10/15 用存储的信号做了电网的决策，赚了钱，但赚的是<b>β 的钱</b>——如果哪天存储涨、电网也涨，同一个推理会让你在错误的时候买入。</p>

<div class="quote">
<b>一句话总结这一笔：</b>你卖对了东西（高 β、光纤 β、拥挤交易），但记账时把功劳记在了“存储崩盘”头上。下次如果只记“看到别的板块崩就清仓”，会在一个真正对冲的组合里亏钱。
</div>

<h2><span class="no">07</span>收获：七条能带走的规则</h2>

<div class="lesson">
  <div class="n">RULE 01</div>
  <h4>把“2 周”和“2 年”写成两句话，永远不要合成一句</h4>
  <p>“长趋势开始的概率远大于短期回调”——这句话把两个<b>赌注期不同</b>的判断压进一个句子，结果读者只能二选一：全信（错过 27% 反弹）或全不信（在 -59% 时抄底）。</p>
  <p><b>正确写法：</b>“未来 2 周：中性偏空，因为二次探底可能失败；未来 2 年：偏空，因为 EPS 要下修 2~3 个季度。”两句话、两种仓位、互不干扰。</p>
</div>

<div class="lesson">
  <div class="n">RULE 02</div>
  <h4>跌得急 ≠ 还要跌，这是两件独立的事</h4>
  <p>报告把“近 5 日 -21.8%”当作“恐慌加速”的证据，又由此推出“现在别买”。但<b>波动率放大是双向的</b>：这波下跌 5 天 -26.6%，反弹 7 天 +27.4%。急跌之后，赔率通常改善、胜率不变——把赔率改善当成“更危险”，是 10/15 最贵的一次混淆。</p>
</div>

<div class="lesson">
  <div class="n">RULE 03</div>
  <h4>给“触发价”，不要给“态度”</h4>
  <p>报告自己给出了可执行的锚：<b>三星 PBR&lt;1.5、海力士 PBR&lt;2.0</b>。按现价倒推，那是三星 {v_ss['pbr_price_15']:,.0f} 韩元（比现价再跌 {abs(v_ss['to15']):.0f}%）、海力士 {v_hy['pbr_price_20']:,.0f} 韩元（再跌 {abs(v_hy['to20']):.0f}%）。这个锚今天依然有效，而且比“别接飞刀”有用一万倍——因为<b>它可以挂单</b>。</p>
  <div class="act"><b>做法：</b>把这类阈值写成价格提醒，而不是写成一句评论。到价就买 1/3，再跌 15% 买第二个 1/3，剩下的等季度 EPS 确认。</div>
</div>

<div class="lesson">
  <div class="n">RULE 04</div>
  <h4>跨品种迁移决策前，先算一次相关性</h4>
  <p>这次 0.27~0.53 的相关性，意味着“存储崩→电网跌”只在<b>共同因子（创业板）发威</b>时成立，概率大约一半。用 50% 的传导去下 100% 的仓位决策，是运气不是方法。</p>
  <div class="act"><b>做法：</b>下次想“因为 A 崩了所以卖 B”时，先问三件事：相关性是否 &gt;0.7？有没有共同的现金流驱动？A 的下跌是不是 B 的<b>上游价格</b>？三条都不满足，就当噪音。</div>
</div>

<div class="lesson">
  <div class="n">RULE 05</div>
  <h4>结果对 ≠ 逻辑对，复盘必须分开记分</h4>
  <p>这一笔：结果 +{abs(SC['2026-10-15']['nav']):.1f}pp（对），逻辑 0.27 相关性（错）。如果只记结果，你会在下次加倍使用这个错误逻辑；如果只记逻辑，你会否定一次本来正确的减仓。</p>
  <div class="act"><b>做法：</b>每笔交易记两栏——“结果分”和“过程分”。过程分低而结果分高的交易，是<b>最危险的成功</b>。</div>
</div>

<div class="lesson">
  <div class="n">RULE 06</div>
  <h4>“历史最深”不是底，是标尺；标尺会被折断</h4>
  <p>海力士 -59.2% 已破 10 年极值 -49.7%。这时候再用“历史上最多跌 50%”来算下跌空间，等于用一个已经被证伪的分布做风险管理。</p>
  <div class="act"><b>做法：</b>历史分位数只用来定<b>仓位大小</b>，不用来定<b>方向</b>；一旦现价突破历史极值区间，把“历史概率”降级为“参考”，改用估值锚（PBR）+ 现金流验证。</div>
</div>

<div class="lesson">
  <div class="n">RULE 07</div>
  <h4>一份报告只回答一个问题，写清楚它不回答什么</h4>
  <p>10/15 那份报告回答的是“现在还值不值得<b>长期投资</b>”，答案是“不值得，等 PBR 到位”。但它被读成了“<b>现在别买</b>”，于是错过了 13%~27%。报告没写“本报告不构成入场时点建议”，读者就会自己补上。</p>
  <div class="act"><b>做法：</b>报告开头加一行“本报告回答 X，不回答 Y”。X = 3 年维度值不值得配；Y = 下周会不会反弹。</div>
</div>

<h2><span class="no">08</span>现在：一张可执行的观察清单</h2>

<div class="card">
<p>不给建议，只给<b>可验证的条件</b>。每条都能在行情软件里盯住，到点就动，不到点就不动。</p>
<ul class="check">
  <li><b>海力士 PBR ≤ 2.0</b>　对应股价约 <b>{v_hy['pbr_price_20']:,.0f} 韩元</b>（现价 {v_hy['cur']:,.0f}，还需 {v_hy['to20']:.0f}%）；三星 PBR ≤ 1.5 对应 <b>{v_ss['pbr_price_15']:,.0f}</b>（还需 {v_ss['to15']:.0f}%）。</li>
  <li><b>或者</b>三条同时成立：① 不破关键低点（海力士 1,190,000〔10/20〕／三星 207,000〔7/30〕）；② 成交额较高峰期萎缩 60% 以上；③ DRAM/NAND 合约价月度环比转正。</li>
  <li><b>A 股存储链</b>：今天 5 只创新低，明显还在“第二波杀跌”，与韩股背离。看 <b>10/30 低点能否守住 3 个交易日</b> + 成交额萎缩，再谈右侧。</li>
  <li><b>电网设备（已清仓）</b>：不要在存储反弹时反手买回。它的问题（光纤供给重估、亨通/中天扩产 400 亿）与存储无关，看的是 G.652.D 现货价和 Q4 招标，不是海力士。</li>
  <li><b>如果一定要参与存储</b>：1/3 起步、按价格触发加仓、单标的不超过总仓位 5%——因为这轮跌幅已破历史极值，<b>任何“跌够了”的判断都没有历史依据</b>。</li>
</ul>
</div>

<div class="card verdict" style="border-left-color:var(--cyan);background:linear-gradient(90deg,rgba(57,197,207,.08),rgba(20,26,34,0) 62%)">
  <span class="tag" style="background:var(--cyan)">最后一句</span>
  <p>这份报告的<b>框架值得留着</b>（周期位置 + PBR + 峰值利润陷阱），<b>节奏判断应该扔掉</b>（“恐慌加速段”“别接飞刀”）。它教给你的最重要一件事，不是“存储不能买”，而是：<b class="hlb">一份好的周期报告，应该让你知道“在什么价格买、买多少”，而不是让你“感觉现在很危险”。</b></p>
</div>

<footer>
  <p class="src"><b>口径与数据源</b><br>
  · 韩股：Naver Finance 日线（2015-01 起，收盘价）与外资持股比例；当前 PER/PBR/EPS/BPS 来自 Naver 移动端 integration 接口（10/30 快照）。<br>
  · 美股：新浪财经 US_MinKService 日线（Yahoo 自 2026-10-30 起对大陆 403），截至 10/29 收盘。<br>
  · A 股：腾讯前复权日线（10/30 收盘）；电网设备 025833 净值来自天天基金，指数 931994 来自中证指数官网，ETF 159326 来自腾讯行情。<br>
  · 原报告数据：<a href="./index.html">2026-10-15 存储股崩盘报告</a>；电网设备原报告：<a href="../fund-025833/index.html">025833 还能拿吗</a>、<a href="../fund-025833-review/index.html">025833 复盘</a>。<br>
  · 相关性为日收益的皮尔逊相关系数，按两市场共同交易日对齐（韩股与 A 股假期不同，样本 n 见各段说明）。<br>
  · 本页为个人研究记录，不构成投资建议。所有“如果”情景均为事后推演，实际成交价、税费、汇率均未计入。</p>
</footer>

</div>
</body>
</html>
"""

out = os.path.join(BASE, "index.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(page)
print("✓ 生成 %s（%.1f KB）" % (out, len(page.encode()) / 1024))