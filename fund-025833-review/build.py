#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 025833 电网设备基金复盘页（2026-09-29 报告 → 2026-10-30 复盘）。

数据来源（已落盘 data/）：
  - 基金净值：天天基金 pingzhongdata / lsjz（官方）
  - 指数：中证指数官网 931994 / 932611 日线 + PE(TTM)
  - 个股 / ETF：腾讯行情前复权日线
用法：python3 build.py
"""
import json
import os
import datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(BASE, "data")

def load(name):
    with open(os.path.join(D, name), encoding="utf-8") as f:
        return json.load(f)

nav = {d: v for d, v in load("nav025833.json")}
idx = {x["date"]: x for x in load("idx931994_2026.json")}
idx_full = load("idx931994_full.json")
idx932 = {x["date"]: x for x in load("idx932611_full.json")}
stocks = load("stocks.json")
etf = {d: v for d, v in load("etf159326.json")}
hs = {d: v for d, v in load("sh000300.json")}
cy = {d: v for d, v in load("sz399006.json")}

PES = sorted(x["pe"] for x in idx_full if x.get("pe"))
def pe_pct(v):
    return sum(1 for p in PES if p <= v) / len(PES) * 100

# ---------------- 关键数字 ----------------
NAV0, NAV1 = nav["2026-09-29"], nav["2026-10-29"]
ETF1, ETF_1030 = etf["2026-10-29"], etf["2026-10-30"]
DAY_CHG = ETF_1030 / ETF1 - 1                 # 10/30 指数代理跌幅
NAV_EST = NAV1 * (1 + DAY_CHG)                # 10/30 净值估算
IDX0, IDX1 = idx["20260929"]["close"], idx["20261029"]["close"]
IDX_EST = IDX1 * (1 + DAY_CHG)
PE0, PE1 = idx["20260929"]["pe"], idx["20261029"]["pe"]
PE_EST = PE1 * IDX_EST / IDX1
PEAK = 1.556
IDX_PEAK = 3834.44
HS0, HS1 = hs["2026-09-29"], hs["2026-10-30"]
CY0, CY1 = cy["2026-09-29"], cy["2026-10-30"]
G932_0, G932_1 = idx932["20260929"]["close"], idx932["20261029"]["close"]

def r(a, b):
    return (b / a - 1) * 100

M = dict(
    nav0=NAV0, nav1=NAV1, nav_est=NAV_EST,
    ret1=r(NAV0, NAV1), ret_est=r(NAV0, NAV_EST), ret_peak=r(PEAK, NAV_EST),
    idx0=IDX0, idx1=IDX1, idx_est=IDX_EST, idx_ret=r(IDX0, IDX1), idx_ret_est=r(IDX0, IDX_EST),
    idx_peak_ret=r(IDX_PEAK, IDX_EST),
    hs0=HS0, hs1=HS1, hs_ret=r(HS0, HS1), cy0=CY0, cy1=CY1, cy_ret=r(CY0, CY1),
    g932_ret=r(G932_0, G932_1),
    etf0=etf["2026-09-29"], etf1=ETF1, etf1030=ETF_1030, etf_ret=r(etf["2026-09-29"], ETF_1030),
    pe0=PE0, pe1=PE1, pe_est=PE_EST, pe0_pct=pe_pct(PE0), pe1_pct=pe_pct(PE1), pe_est_pct=pe_pct(PE_EST),
    excess_hs=r(NAV0, NAV_EST) - r(HS0, HS1),
    excess_cy=r(NAV0, NAV_EST) - r(CY0, CY1),
)

# 个股：9/29 收盘 → 10/30 收盘（腾讯实时价），权重取基金 2026Q3 前十大
TOP = [
    ("亨通光电", "sh600487", 57.11, 42.42, 9.77),
    ("中天科技", "sh600522", 31.33, 23.17, 7.63),
    ("特变电工", "sh600089", 17.15, 17.37, 7.78),
    ("国电南瑞", "sh600406", 22.21, 23.16, 7.99),
    ("思源电气", "sz002028", 120.81, 101.97, 6.66),
    ("宏发股份", "sh600885", 33.48, 29.80, 3.67),
    ("东材科技", "sh601208", 50.53, 34.60, 3.44),
    ("中国西电", "sh601179", 11.41, 10.59, 2.63),
    ("正泰电器", "sh601877", 24.381, 24.31, 2.37),
    ("特锐德", "sz300001", 34.30, 28.91, 2.25),
]
OTHERS = [
    ("东方电缆", 35.33, 36.94),
    ("远东股份", 18.03, 14.27),
]
contrib = sum(w * r(a, b) / 100 for _, _, a, b, w in TOP)

# ---------------- 图表 ----------------
def _ord(d):
    return dt.date.fromisoformat(d).toordinal()

def _fmt_date(d, span):
    y, m, dd = d.split("-")
    if span > 200:
        return f"{int(m)}月"
    return f"{int(m)}/{int(dd)}"

def line_chart(series, annotations=(), w=1000, h=400, baseline=None,
               ylab="", end_labels=True, ymin=None, ymax=None):
    """series: list of dict(name,color,pts[(date,value)],dash,width)"""
    L, R, T, B = 62, 118, 34, 42
    allpts = [p for s in series for p in s["pts"]]
    xs = [_ord(p[0]) for p in allpts]
    ys = [p[1] for p in allpts]
    x0, x1 = min(xs), max(xs)
    lo, hi = (min(ys), max(ys)) if ymin is None else (ymin, ymax)
    pad = (hi - lo) * 0.10 or 1
    lo, hi = lo - pad, hi + pad
    span = x1 - x0
    def X(d): return L + (_ord(d) - x0) / span * (w - L - R)
    def Y(v): return T + (hi - v) / (hi - lo) * (h - T - B)

    out = [f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto;display:block" font-family="inherit" role="img">']
    # grid
    n = 5
    for i in range(n + 1):
        v = lo + (hi - lo) * i / n
        y = Y(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{w-R}" y2="{y:.1f}" stroke="#232c38" stroke-width="1"/>')
        out.append(f'<text x="{L-8}" y="{y+4:.1f}" fill="#6b7683" font-size="11" text-anchor="end">{v:.1f}</text>')
    # x ticks
    dates = sorted({p[0] for p in allpts})
    for i in range(7):
        d = dates[round(i * (len(dates) - 1) / 6)]
        out.append(f'<text x="{X(d):.1f}" y="{h-B+20}" fill="#6b7683" font-size="11" text-anchor="middle">{_fmt_date(d, span)}</text>')
        out.append(f'<line x1="{X(d):.1f}" y1="{h-B}" x2="{X(d):.1f}" y2="{h-B+4}" stroke="#2d3644"/>')
    if baseline is not None:
        out.append(f'<line x1="{L}" y1="{Y(baseline):.1f}" x2="{w-R}" y2="{Y(baseline):.1f}" stroke="#5b6675" stroke-width="1" stroke-dasharray="5,5" opacity=".8"/>')
    if ylab:
        out.append(f'<text x="{L-8}" y="{T-12}" fill="#6b7683" font-size="11" text-anchor="start">{ylab}</text>')

    for s in series:
        pts = " ".join(f"{X(d):.1f},{Y(v):.1f}" for d, v in s["pts"])
        dash = f' stroke-dasharray="{s["dash"]}"' if s.get("dash") else ""
        out.append(f'<polyline fill="none" stroke="{s["color"]}" stroke-width="{s.get("width",2.2)}" stroke-linejoin="round" stroke-linecap="round"{dash} points="{pts}"/>')
        d, v = s["pts"][-1]
        out.append(f'<circle cx="{X(d):.1f}" cy="{Y(v):.1f}" r="3.4" fill="{s["color"]}"/>')

    # annotations
    for a in annotations:
        x = X(a["date"]); color = a.get("color", "#e3b341")
        out.append(f'<line x1="{x:.1f}" y1="{T-6}" x2="{x:.1f}" y2="{h-B}" stroke="{color}" stroke-width="1" stroke-dasharray="3,4" opacity=".55"/>')
        ty = a.get("y", T + 14)
        anchor = a.get("anchor", "middle")
        tx = x + a.get("dx", 0)
        label = a["text"]
        bw = len(label) * 11.2 + 10
        bx = tx - bw / 2 if anchor == "middle" else (tx if anchor == "start" else tx - bw)
        out.append(f'<rect x="{bx:.1f}" y="{ty-13}" width="{bw:.1f}" height="19" rx="4" fill="#0d1117" opacity=".82"/>')
        out.append(f'<text x="{tx:.1f}" y="{ty}" fill="{color}" font-size="11.5" text-anchor="{anchor}">{label}</text>')

    # legend（名称 + 末值）
    def tw(t):
        return sum(11.6 if ord(c) > 127 else 6.4 for c in t)
    lx = L
    for s in series:
        if s.get("hide_legend"):
            continue
        label = s["name"] + (f'  {s["end"]}' if s.get("end") else "")
        out.append(f'<line x1="{lx}" y1="{T-18}" x2="{lx+14}" y2="{T-18}" stroke="{s["color"]}" stroke-width="2.4"/>')
        out.append(f'<text x="{lx+19}" y="{T-14}" fill="#9aa7b4" font-size="11.5">{s["name"]}</text>')
        if s.get("end"):
            out.append(f'<text x="{lx+19+tw(s["name"])+6:.1f}" y="{T-14}" fill="{s["color"]}" font-size="11.5" font-weight="700">{s["end"]}</text>')
        lx += 24 + tw(label) + 26
    out.append("</svg>")
    return "".join(out)

def bar_chart(rows, w=1000):
    """rows: (name, pct, note) 横向条形，红涨绿跌"""
    rh, gap, L, R = 27, 7, 108, 90
    h = 48 + len(rows) * (rh + gap)
    lo = min(0, min(r[1] for r in rows)); hi = max(0, max(r[1] for r in rows))
    pad = max(4, (hi - lo) * .08); lo -= pad; hi += pad
    X = lambda v: L + (v - lo) / (hi - lo) * (w - L - R)
    out = [f'<svg viewBox="0 0 {w} {h}" style="width:100%;height:auto;display:block" font-family="inherit">']
    out.append(f'<text x="{w-10}" y="16" fill="#6b7683" font-size="11" text-anchor="end">基金权重</text>')
    out.append(f'<line x1="{X(0):.1f}" y1="26" x2="{X(0):.1f}" y2="{h-16}" stroke="#3a4553" stroke-width="1"/>')
    for i, (name, v, note) in enumerate(rows):
        y = 28 + i * (rh + gap)
        color = "#f85149" if v >= 0 else "#3fb950"
        x1, x2 = sorted([X(0), X(v)])
        out.append(f'<rect x="{x1:.1f}" y="{y}" width="{max(1.5, x2-x1):.1f}" height="{rh}" rx="3" fill="{color}" opacity=".78"/>')
        out.append(f'<text x="{L-10}" y="{y+rh/2+4:.1f}" fill="#c9d3df" font-size="12" text-anchor="end">{name}</text>')
        tx = X(v) + (6 if v >= 0 else -6)
        out.append(f'<text x="{tx:.1f}" y="{y+rh/2+4:.1f}" fill="{color}" font-size="12" font-weight="600" text-anchor="{"start" if v>=0 else "end"}">{v:+.1f}%</text>')
        if note:
            out.append(f'<text x="{w-10}" y="{y+rh/2+4:.1f}" fill="#6b7683" font-size="11" text-anchor="end">{note}</text>')
    out.append("</svg>")
    return "".join(out)

# 图1：报告发布后（9/29=100）
def norm_pts(pts):
    base = pts[0][1]
    return [[d, v / base * 100] for d, v in pts]

def slice_series(dmap, start, end):
    return [[d, v] for d, v in sorted(dmap.items()) if start <= d <= end]

def fix_pts(pts):
    return [[d[:4] + "-" + d[4:6] + "-" + d[6:] if len(d) == 8 and d.isdigit() else d, v] for d, v in pts]

fund_pts = slice_series(nav, "2026-09-29", "2026-10-29")
idx_pts = fix_pts([[d, x["close"]] for d, x in sorted(idx.items()) if "20260929" <= d <= "20261029"])
hs_pts = slice_series(hs, "2026-09-29", "2026-10-29")
cy_pts = slice_series(cy, "2026-09-29", "2026-10-29")
g932_pts = fix_pts([[d, x["close"]] for d, x in sorted(idx932.items()) if "20260929" <= d <= "20261029"])

fund_n = sorted(norm_pts(fund_pts))

def ret29(pts):
    return (pts[-1][1] / pts[0][1] - 1) * 100

chart1 = line_chart([
    dict(name="025833 净值", color="#e3b341", pts=fund_n, width=2.6, end=f'{ret29(fund_pts):+.1f}%'),
    dict(name="931994 指数", color="#58a6ff", pts=sorted(norm_pts(idx_pts)), end=f'{ret29(idx_pts):+.1f}%'),
    dict(name="沪深300", color="#8b949e", pts=sorted(norm_pts(hs_pts)), end=f'{ret29(hs_pts):+.1f}%'),
    dict(name="创业板指", color="#bc8cff", pts=sorted(norm_pts(cy_pts)), end=f'{ret29(cy_pts):+.1f}%'),
    dict(name="932611 纯电网", color="#39c5cf", pts=sorted(norm_pts(g932_pts)), end=f'{ret29(g932_pts):+.1f}%'),
], baseline=100, h=390)

# 图2：从 6/1 起的全貌（6/1=100）
def month_pts(dmap, start="2026-06-01"):
    return [[d, v] for d, v in sorted(dmap.items()) if d >= start]

def to_dash(d):
    return d[:4] + "-" + d[4:6] + "-" + d[6:]

idx_jun = [[to_dash(d), x["close"]] for d, x in sorted(idx.items()) if "20260601" <= d <= "20261029"]
cy_jun = month_pts(cy, "2026-06-01")
cy_jun = [p for p in cy_jun if p[0] <= "2026-10-29"]
fund_jun = month_pts(nav, "2026-06-01")
fund_jun = [p for p in fund_jun if p[0] <= "2026-10-29"]

fn = sorted(norm_pts(fund_jun)); ixn = sorted(norm_pts(idx_jun)); cyn = sorted(norm_pts(cy_jun))
chart2 = line_chart([
    dict(name="025833 净值", color="#e3b341", pts=fn, width=2.6, end=f'{fn[-1][1]-100:+.1f}%'),
    dict(name="931994 指数", color="#58a6ff", pts=ixn, end=f'{ixn[-1][1]-100:+.1f}%'),
    dict(name="创业板指", color="#bc8cff", pts=cyn, end=f'{cyn[-1][1]-100:+.1f}%'),
], baseline=100, h=400, annotations=[
    dict(date="2026-06-22", text="6/22 真顶：指数3834 / PE38.7 / 净值1.556", color="#f85149", y=44, dx=-30),
    dict(date="2026-09-29", text="9/29 报告发布", color="#9aa7b4", y=66, dx=40),
    dict(date="2026-09-22", text="9/22 报告说的“顶”（实为反弹次高）", color="#e3b341", y=96, dx=-140),
])

stock_rows = [(n, r(a, b), f"{w:.1f}%") for n, _, a, b, w in TOP] + [(n, r(a, b), "—") for n, a, b in OTHERS]
stock_rows.sort(key=lambda x: x[1])
chart3 = bar_chart(stock_rows)

# ---------------- 数据表 ----------------
def ret_cls(v):
    return "up" if v > 0 else ("down" if v < 0 else "dim")

stock_table = "".join(
    f'<tr><td>{n}</td><td class="num">{a:.2f}</td><td class="num">{b:.2f}</td>'
    f'<td class="num {ret_cls(r(a,b))}">{r(a,b):+.1f}%</td>'
    f'<td class="num dim">{w:.1f}%</td>'
    f'<td class="num {ret_cls(r(a,b))}">{w*r(a,b)/100:+.2f}pp</td></tr>'
    for n, _, a, b, w in TOP
) + "".join(
    f'<tr><td>{n}</td><td class="num">{a:.2f}</td><td class="num">{b:.2f}</td>'
    f'<td class="num {ret_cls(r(a,b))}">{r(a,b):+.1f}%</td><td class="num dim">—</td><td class="num dim">—</td></tr>'
    for n, a, b in OTHERS
)

# ---------------- 页面 ----------------
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
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
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
.jcard ul{padding-left:17px;margin:6px 0}
.jcard li{font-size:13.5px;color:var(--tx2);margin:5px 0}
.jcard li b{color:var(--tx)}
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
.src a{color:#7f96ad;border-bottom-color:rgba(127,150,173,.3)}
@media(max-width:860px){
  .kpis{grid-template-columns:1fr 1fr}
  .judge,.nums{grid-template-columns:1fr}
  h1{font-size:25px}
  .wrap{padding:24px 16px 70px}
  h2{font-size:19px;margin-top:44px}
}
"""

def pctf(v, d=1):
    return f"{v:+.{d}f}%"

page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>025833 复盘：清仓一个月后，哪些判断成立，哪些是我漏掉的</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">REVIEW · 025833 · 2026-10-30</div>
  <h1>清仓一个月后，回头看那份「还能拿吗」
    <span class="sub">哪些判断兑现了，哪些是我当时没看见的，以及你 9/29 清仓到底对不对</span>
  </h1>
  <div class="meta">
    原报告：<b>2026-09-29</b>（数据截至 9/29 盘中）　｜　复盘：<b>2026-10-30</b> 收盘<br>
    数据口径：基金净值 <b>10/29 官方</b>（10/30 未出，按跟踪 ETF 估算并标注）；指数 / 个股 / ETF 为 <b>10/30 收盘</b>；估值来自中证指数官网 PE(TTM)<br>
    对照标的：中证电网设备主题 <b>931994</b>、中证智选电网 <b>932611</b>、电网设备ETF华夏 <b>159326</b>、沪深300、创业板指
  </div>
</header>

<div class="card verdict">
  <span class="tag">复盘结论</span>
  <p><b class="hl">你清仓，是对的。</b>9/29 之后一个月，025833 官方净值从 1.0910 跌到 0.9775（<b>{pctf(M['ret1'])}</b>），10/30 再跌约 2.7%，累计约 <b>{pctf(M['ret_est'])}</b>。同期沪深300 {pctf(M['hs_ret'])}、创业板 {pctf(M['cy_ret'])}——你避开的主要是"高 β 成长"，而不只是"电网设备"。</p>
  <p>但这份报告<b class="hl">结论对、坐标系错了一半</b>：真正的顶在 <b>6/22</b>（指数 3834、PE 38.7、基金净值 1.556），而不是报告写的 9/22。报告发布时，净值已经距顶 <b>-29.9%</b>，它却用"年内仅 +3.0%"来描述位置。把"熊市反弹结束"讲成"周期顶部初现"，直接导致建议只敢"减 1/3~1/2"，而不是清仓。</p>
  <p>最值钱的一句仍然是：<b class="hlb">"这不是一只电网基金，而是一只光纤 β。"</b> 10/12"十五五"5 万亿电网投资落地、保变电气涨停那天，这只基金跟踪的指数反而跌了 1.24%——这句话被一次免费的自然实验证实了。</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="v cyan">{pctf(M['ret_est'])}</div><div class="k">你避开的跌幅（9/29→10/30 估算）</div><div class="s">10 万元 ≈ 少亏 1.29 万元</div></div>
  <div class="kpi"><div class="v gold">{pctf(M['ret_peak'])}</div><div class="k">基金距 6/22 真顶</div><div class="s">1.556 → {M['nav_est']:.4f}（估算）</div></div>
  <div class="kpi"><div class="v down">{M['excess_hs']:+.1f}pp</div><div class="k">相对沪深300</div><div class="s">跑输：它不是避风港</div></div>
  <div class="kpi"><div class="v up">{M['excess_cy']:+.1f}pp</div><div class="k">相对创业板</div><div class="s">跑赢：不是最惨的那一类</div></div>
</div>
<p class="note">注：10/30 基金净值尚未公布，估算方法 = 10/29 净值 ×（1 + 跟踪 ETF 159326 10/30 涨跌幅 {DAY_CHG*100:+.2f}%）。误差通常在 ±0.3pp 内。</p>

<h2><span class="no">01</span>这一个月，数字上发生了什么</h2>
<p class="lead">先看结果，再看过程。所有区间收益都用 9/29 收盘为起点。</p>

<div class="card tight">
{chart1}
<p class="note">归一化：9/29 = 100，均截至 10/29（基金官方净值日），图例数字为 9/29→10/29 涨跌；10/30 的估算见上表。</p>
</div>

<div class="scroll">
<table>
<tr><th>标的</th><th>9/29</th><th>10/29</th><th>10/30</th><th>9/29→10/30</th><th>距 6/22 顶</th></tr>
<tr><td><b>025833 基金净值</b></td><td class="num">{M['nav0']:.4f}</td><td class="num">{M['nav1']:.4f}</td><td class="num gold">≈{M['nav_est']:.4f}</td><td class="num down"><b>{pctf(M['ret_est'])}</b></td><td class="num down">{pctf(M['ret_peak'])}</td></tr>
<tr><td>931994 电网设备指数</td><td class="num">{M['idx0']:.2f}</td><td class="num">{M['idx1']:.2f}</td><td class="num">≈{M['idx_est']:.0f}</td><td class="num down">{pctf(M['idx_ret_est'])}</td><td class="num down">{pctf(M['idx_peak_ret'])}</td></tr>
<tr><td>932611 智选电网（纯电网）</td><td class="num">{G932_0:.2f}</td><td class="num">{G932_1:.2f}</td><td class="num dim">—</td><td class="num down">{pctf(M['g932_ret'])}</td><td class="num dim">—</td></tr>
<tr><td>159326 电网设备ETF</td><td class="num">{M['etf0']:.3f}</td><td class="num">{M['etf1']:.3f}</td><td class="num">{M['etf1030']:.3f}</td><td class="num down">{pctf(M['etf_ret'])}</td><td class="num down">-40.6%</td></tr>
<tr><td>沪深300</td><td class="num">{M['hs0']:.2f}</td><td class="num">4041.84</td><td class="num">{M['hs1']:.2f}</td><td class="num down">{pctf(M['hs_ret'])}</td><td class="num down">-21.2%</td></tr>
<tr><td>创业板指</td><td class="num">{M['cy0']:.2f}</td><td class="num">2517.59</td><td class="num">{M['cy1']:.2f}</td><td class="num down">{pctf(M['cy_ret'])}</td><td class="num down">-44.8%</td></tr>
</table>
</div>
<p class="note">6/22 顶：931994 收 3834.44（PE 38.7）；025833 净值 1.556；159326 收 2.258。指数/基金距顶为估值与净值口径，ETF 为价格口径。</p>

<div class="quote">
  <b>一句话读表：</b>基金跌 {abs(M['ret_est']):.1f}%，指数跌 {abs(M['idx_ret_est']):.1f}%，两者几乎一致——它就是个指数基金，别指望"主动管理"帮你躲。真正值得注意的是：它比创业板少跌 <b>{M['excess_cy']:.1f}pp</b>，比沪深300多跌 <b>{abs(M['excess_hs']):.1f}pp</b>。所以 10 月的下跌，一半是"AI/成长杀估值"，一半才是"光纤自己的事"。
</div>

<h2><span class="no">02</span>时间线：决定结果的六个交易日</h2>
<div class="timeline">
  <div class="tl key"><div class="d">09-29</div><div class="t"><b>报告发布</b>：净值 1.0910，指数 2624.15，PE 26.82（76% 分位）。结论"不清仓、不加仓，先减 1/3~1/2"。</div></div>
  <div class="tl"><div class="d">10-08</div><div class="t">节后首日，亨通定增细节发酵，<b>亨通 -3.94%</b>、主力净流出 7.52 亿；基金 -0.32%。</div></div>
  <div class="tl key"><div class="d">10-12</div><div class="t"><b>"十五五"电网投资超 5 万亿</b>，金冠电气 20CM 涨停、保变电气/长城电工涨停；同一天 931994 反而 <b>-1.24%</b>。亨通定增获股东会通过。<span>——"名字"与"暴露"在这一天分道扬镳。</span></div></div>
  <div class="tl"><div class="d">10-14 ~ 10-15</div><div class="t">A 股成长股集体杀估值，创业板两日 <b>-5.9%</b>，指数 -2.38%、-2.57%，基金两日 -2.3%、-2.5%。</div></div>
  <div class="tl"><div class="d">10-23</div><div class="t">盘中"惊天逆转"：创业板早盘一度跌 3.2%，午后直线拉升，收盘 <b>+4.16%</b>；指数 +1.66%。反弹给了最后一次体面离场的机会。</div></div>
  <div class="tl key"><div class="d">10-28 晚</div><div class="t"><b>三季报炸裂</b>：亨通前三季净利 61.63 亿（<b>+159.4%</b>）、Q3 单季 <b>+299.1%</b>；中天前三季 40.01 亿（<b>+71.1%</b>）、Q3 单季 <b>+109%</b>。</div></div>
  <div class="tl key"><div class="d">10-29</div><div class="t"><b>业绩最好的那天，股价跌最多</b>：亨通 -8.0%、中天 -5.6%、指数 -2.79%、基金 -2.69%。</div></div>
  <div class="tl key"><div class="d">10-30</div><div class="t">谷歌财报后 -12%、纳指 -1.4%，"AI 投入回报"再被审视；创业板 <b>-4.13%</b>、亨通 -4.89%、中天 -7.95%，指数估算 -2.75%。</div></div>
</div>

<h2><span class="no">03</span>分析对了什么：六条，且都有事后证据</h2>

<div class="judge">
  <div class="jcard ok">
    <h4>① 结构诊断：名字是电网，暴露是光纤 <span class="badge ok">A</span></h4>
    <p><b>当时说：</b>"亨通+中天合计约 20% 权重，贡献了近 30 日几乎全部弹性；'电网设备'这个名字只描述了 45% 的资产，却描述了 0% 的波动来源。"</p>
    <p><b>后来：</b>10/12 电网 5 万亿利好，保变、金冠、长城电工涨停，<b>931994 当天 -1.24%</b>。9/29 以来，南瑞 <b class="up">+4.3%</b>、东方电缆 <b class="up">+4.6%</b>、特变 <b class="up">+1.3%</b>，而亨通 <b class="down">-25.7%</b>、中天 <b class="down">-26.0%</b>、东材 <b class="down">-31.5%</b>。</p>
    <p><b>为什么值钱：</b>它让你在"电网大利好"的日子里没有加仓，也没有因为"板块涨了"而怀疑自己。</p>
  </div>

  <div class="jcard ok">
    <h4>② 压舱石托不住 <span class="badge ok">A</span></h4>
    <p><b>当时说：</b>"真电网设备约 45%，便宜且稳，但今年在跌，是拖油瓶；它们只能提供安全垫，提供不了弹性。"</p>
    <p><b>后来：</b>压舱石确实抗跌（10 只重仓里 4 只正收益/基本走平），但基金仍跌 {abs(M['ret_est']):.1f}%。<b>安全垫是真的，托不住也是真的。</b></p>
  </div>

  <div class="jcard ok">
    <h4>③ 题材尾部最先被卖 <span class="badge ok">A</span></h4>
    <p><b>当时说：</b>"东材 PE 123x、远东 PE 332x，纯泡沫定价，退潮时跌得最快。"</p>
    <p><b>后来：</b>东材 <b class="down">-31.5%</b>、远东 <b class="down">-20.9%</b>、特锐德 <b class="down">-15.7%</b>，全部跑输指数。高估值 + 低净利率的"算力光缆"故事，确实是第一批被清算的。</p>
  </div>

  <div class="jcard ok">
    <h4>④ 供给重估才刚开始 <span class="badge ok">A-</span></h4>
    <p><b>当时说：</b>"9/28 亨通定增跌停是市场第一次抢跑供给重估，这种抢跑之后还会有很多次。"</p>
    <p><b>后来：</b>10/12 定增过会；Q3 全行业扩产约 <b>400 亿</b>；亨通从 57.1 跌到 42.4，中天从 31.3 跌到 23.2。跌停不是终点，是起点。</p>
  </div>

  <div class="jcard ok">
    <h4>⑤ "别等基本面变坏再卖" <span class="badge ok">A-</span></h4>
    <p><b>当时说：</b>"股价顶领先基本面；等价格转跌、业绩变脸再卖，通常已经晚了。"</p>
    <p><b>后来：</b>9 月 G.652.D 现货 88.4 元、环比还 <b>+2.8%</b>；Q3 业绩 <b>+159%</b>。基本面一条都没坏，股价先跌了 26%。这条判断在方向上完全兑现。</p>
  </div>

  <div class="jcard ok">
    <h4>⑥ 替代方案有效 <span class="badge ok">B+</span></h4>
    <p><b>当时说：</b>"如果你要的是纯电网，这只基金给不了；可看 932611 或直接持有南瑞/思源。"</p>
    <p><b>后来：</b>932611 同期 <b class="down">{M['g932_ret']:.1f}%</b>，比 931994 少跌 3.0pp；纯电网个股多数正收益。换仓建议有效，只是幅度不大。</p>
  </div>
</div>

<h2><span class="no">04</span>分析错了什么：六个偏差，第一个最致命</h2>

<div class="card tight">
{chart2}
<p class="note">归一化：6/1 = 100。这张图是本次复盘最重要的证据——<b>6/22 才是顶</b>，7 月一个月指数 -24%、基金 -23%；8-9 月是反弹，9/22 只是反弹次高。报告在 9/29 把"次高"写成了"顶"。</p>
</div>

<div class="judge">
  <div class="jcard no">
    <h4>① 坐标系错了：真顶是 6/22，不是 9/22 <span class="badge no">D</span></h4>
    <p><b>报告原文：</b>"亨通 9/22 见顶后 5 日回撤 -22%"、"指数年内仅 +3.0%"、"股价顶 2026-09？"</p>
    <p><b>事实：</b>6/22 指数 3834.44、PE <b>38.7（99.6% 分位）</b>、基金净值 <b>1.556</b>；到 9/29 已回撤 <b>-31.6%</b>（基金 -29.9%）。"年内 +3.0%"是真的，但它掩盖了"从顶部跌掉三分之一"这个更重要的事实。</p>
    <p><b>后果：</b>把"熊市反弹的次高点"误判成"周期顶部初现"，风险等级被说低了一档——所以建议是"减 1/3~1/2"，而不是"清仓"。</p>
  </div>

  <div class="jcard no">
    <h4>② "股价顶领先商品价 2~4 个季度"本轮失效 <span class="badge no">D+</span></h4>
    <p><b>报告原文：</b>把它当作"两条历史规律"之一，用来论证"现在就该卖"。</p>
    <p><b>事实：</b>本轮商品价 <b>2026-04</b> 见顶（G.652.D 99~112 元），股价 <b>6/22</b> 才见顶——<b>股价滞后约 2 个月</b>，方向反了。原因是这次是全市场 AI 泡沫去杠杆，不是商品周期主导。</p>
    <p><b>教训：</b>历史规律只能当"假设"，不能当"论据"；每一轮都要问"这次的主导变量还是它吗"。</p>
  </div>

  <div class="jcard no">
    <h4>③ "现货价连续 5 个月不创新高 / 走平"事实不准 <span class="badge no">C+</span></h4>
    <p><b>报告原文：</b>"G.652.D 现货 4 月见顶后，连续 5 个月没有再创新高"、"5-9 月回调→反抽→宽幅震荡"。</p>
    <p><b>事实（瑞银 10/6 月报）：</b>9 月 G.652.D <b>88.4 元、环比 +2.8%</b>（8 月 +5.2%），<b>还在涨</b>；真正转跌的是 G.657.A1，<b>133.1 元、环比 -1.6%</b>（8 月 +3.5%）。"不创新高"成立，"走平"不成立。</p>
    <p><b>结论没错，证据有瑕疵：</b>涨势放缓、特种纤先转弱是对的；但用"走平"描述，会让读者以为价格已经横死。</p>
  </div>

  <div class="jcard no">
    <h4>④ 归因过度单一：把大盘 β 记到了光纤账上 <span class="badge no">C</span></h4>
    <p><b>报告原文：</b>卖出逻辑几乎全部围绕"光纤周期 + 供给重估"。</p>
    <p><b>事实：</b>10 月是 AI/成长系统性杀估值——创业板 <b>{M['cy_ret']:.1f}%</b>、沪深300 <b>{M['hs_ret']:.1f}%</b>、谷歌财报后 -12%、纳指回调。基金相对创业板还 <b>跑赢 {M['excess_cy']:.1f}pp</b>，说明它不是"光纤独跌"。</p>
    <p><b>含义：</b>你这一把躲过的，更多是"高 β 成长"的系统性风险；如果其他持仓也是 AI/成长，只清这一只并不能保住组合。</p>
  </div>

  <div class="jcard no">
    <h4>⑤ 建议偏软：只减 1/3~1/2 <span class="badge no">C+</span></h4>
    <p><b>报告原文：</b>"不清仓、不加仓、按计划分批降；近期先减 1/3~1/2。"理由是"短期景气不支持恐慌性清仓"。</p>
    <p><b>事实：</b>一个月又跌 {abs(M['ret1']):.1f}%。按建议执行：留一半再亏 5.2%，留 2/3 再亏 6.9%；你全清，比建议多保住 6~9pp。</p>
    <p><b>自相矛盾之处：</b>同一篇里既写"顶部盈利 × 低 PE 是陷阱"，又把"2026E PE 20x，不贵"放进持有理由。事实站在"陷阱"那一边。</p>
  </div>

  <div class="jcard no">
    <h4>⑥ 没写"再入场条件" <span class="badge no">D+</span></h4>
    <p><b>报告原文：</b>给了 4 个"减仓触发器"，但一个"什么条件下回来"都没有。</p>
    <p><b>后果：</b>卖出变成单腿动作，很容易演化成两种结局——永久空仓，或者在反弹里追高买回。<b>这次你卖对了，但下一次买回来的规则是空的。</b></p>
  </div>
</div>

<h2><span class="no">05</span>预估 vs 实际：偏差量化</h2>
<div class="scroll">
<table>
<tr><th style="text-align:left">维度</th><th style="text-align:left">报告当时的表述 / 预估</th><th style="text-align:left">实际发生</th><th style="text-align:left">偏差</th></tr>
<tr><td>一个月方向</td><td style="text-align:left">继续减仓（看跌）</td><td style="text-align:left">基金 {pctf(M['ret1'])}</td><td style="text-align:left"><span class="pill green">方向对</span></td></tr>
<tr><td>跌幅量级</td><td style="text-align:left">未给目标；暗示"等基本面变脸已跌 30-50%"</td><td style="text-align:left">一个月 {pctf(M['ret_est'])}</td><td style="text-align:left"><span class="pill gold">量级接近，但归因不同</span></td></tr>
<tr><td>顶的位置</td><td style="text-align:left">9/22 见顶；"年内 +3.0%"</td><td style="text-align:left">真顶 6/22，9/29 已距顶 -31.6%</td><td style="text-align:left"><span class="pill red">晚 3 个月</span></td></tr>
<tr><td>估值</td><td style="text-align:left">PE 27.0x / 76% 分位</td><td style="text-align:left">PE 24.0x / 69% 分位（10/29）</td><td style="text-align:left"><span class="pill green">数据准，方向对</span></td></tr>
<tr><td>商品价</td><td style="text-align:left">"连续 5 个月不创新高 / 走平"</td><td style="text-align:left">9 月 G.652.D 环比 +2.8%，仍在涨</td><td style="text-align:left"><span class="pill gold">表述不准</span></td></tr>
<tr><td>业绩</td><td style="text-align:left">"H1 兑现，可持续性存疑"</td><td style="text-align:left">Q3 亨通 +159%、中天 +71%，继续加速</td><td style="text-align:left"><span class="pill green">"存疑"对，但股价照跌</span></td></tr>
<tr><td>系统性风险</td><td style="text-align:left">未讨论大盘 / AI 泡沫</td><td style="text-align:left">创业板 -23.2%，自 6 月 -44.8%</td><td style="text-align:left"><span class="pill red">漏项</span></td></tr>
<tr><td>替代方案</td><td style="text-align:left">换 932611 / 纯电网个股</td><td style="text-align:left">932611 {pctf(M['g932_ret'])}，南瑞 +4.3%</td><td style="text-align:left"><span class="pill green">对</span></td></tr>
<tr><td>建议强度</td><td style="text-align:left">先减 1/3~1/2，不清仓</td><td style="text-align:left">全清更优 6~9pp</td><td style="text-align:left"><span class="pill red">偏保守</span></td></tr>
</table>
</div>

<h2><span class="no">06</span>你 9/29 清仓，到底对不对</h2>
<p class="lead">分三个口径看，结论不一样。混在一起谈，就会把"运气"误认为"能力"。</p>

<div class="nums">
  <div class="num-box"><div class="t">绝对收益（避开的亏损）</div><div class="v cyan">{pctf(M['ret_est'])}</div><div class="s">持有 10 万 → {10*(1+M['ret_est']/100):.2f} 万；你保住 10 万</div></div>
  <div class="num-box"><div class="t">相对沪深300</div><div class="v down">{M['excess_hs']:+.1f}pp</div><div class="s">如果 9/29 换成沪深300，只亏 8.3%</div></div>
  <div class="num-box"><div class="t">相对创业板</div><div class="v up">{M['excess_cy']:+.1f}pp</div><div class="s">如果换成创业板，要亏 23.2%</div></div>
</div>

<h3>6.1 四种做法的事后对比</h3>
<div class="scroll">
<table>
<tr><th style="text-align:left">做法</th><th>一个月组合损益</th><th style="text-align:left">说明</th></tr>
<tr><td>你：全部清仓</td><td class="num gold"><b>0.0%</b></td><td style="text-align:left">避开 {abs(M['ret_est']):.1f}% 下跌；忽略赎回费（C 类持有 &gt;7 天通常为 0）</td></tr>
<tr><td>按报告：减 1/2</td><td class="num down">{M['ret_est']/2:.1f}%</td><td style="text-align:left">剩余一半继续跌，组合再亏约 6.4%</td></tr>
<tr><td>按报告：减 1/3</td><td class="num down">{M['ret_est']*2/3:.1f}%</td><td style="text-align:left">留 2/3 仓位，组合再亏约 8.6%</td></tr>
<tr><td>不动</td><td class="num down"><b>{M['ret_est']:.1f}%</b></td><td style="text-align:left">10 万 → {10*(1+M['ret_est']/100):.2f} 万</td></tr>
<tr><td>换 932611（纯电网）</td><td class="num down">{M['g932_ret']:.1f}%</td><td style="text-align:left">少亏 3.0pp，但仍未躲过系统性下跌</td></tr>
<tr><td>换沪深300</td><td class="num down">{M['hs_ret']:.1f}%</td><td style="text-align:left">比清仓差，比持有好</td></tr>
</table>
</div>
<p class="note">口径：9/29 收盘等权切换，不计交易费用与赎回费；基金用 10/30 估算净值 {M['nav_est']:.4f}。</p>

<h3>6.2 结论：结果 9/10，过程 7.5/10</h3>
<div class="card">
  <p><b class="hlg">对的部分：</b>方向对，动作也比报告建议更彻底。在一个 PE 76% 分位、供给冲击刚出现、股价结构已经破坏的品种上，"先出来"的期望值明显为正。你没有因为"景气还在、订单排到 2028"这种话留下来。</p>
  <p><b class="hl">要扣分的部分：</b>这次少亏的 12.9 个百分点里，大约 <b>六成来自大盘/AI 杀估值的 β</b>，四成来自板块自身（定增、扩产、光纤双雄）。换句话说，<b>你赢在动作，不全是赢在逻辑</b>。如果 10 月大盘反弹、只有光纤跌，基金可能只跌 4~6%，那时候"全清"看起来就不会这么英明。</p>
  <p><b class="hlb">更值得反思的：</b>不是"9/29 该不该卖"，而是"<b>6/22 为什么没卖</b>"。6/22 净值 1.556、PE 38.7（99.6% 分位）、全市场同时见顶——那才是真正该有一份报告的日子。9/29 的清仓，本质是<b>止损</b>，不是<b>逃顶</b>；止损是对的，但它不该被记成"判断精准"。</p>
  <p><b>还有一个没解决的问题：</b>卖出之后，你的钱去了哪里？如果转手又买入了别的 AI/成长，那这次清仓只是换了个代码。10 月创业板 -23.2%，说明系统性风险没有躲掉。</p>
</div>

<h2><span class="no">07</span>个股层面：光纤杀估值，电网在收租</h2>
<div class="card tight">
{chart3}
<p class="note">9/29 收盘 → 10/30 收盘；右侧数字为基金 2026Q3 权重（占净值），"—"为未进前十大。红涨绿跌。</p>
</div>

<div class="scroll">
<table>
<tr><th>成分股</th><th>9/29</th><th>10/30</th><th>涨跌</th><th>基金权重</th><th>组合贡献</th></tr>
{stock_table}
</table>
</div>
<p class="note">前十大合计贡献约 <b>{contrib:.2f}pp</b>（基金整体 {M['ret_est']:.2f}%），其中亨通+中天两只就贡献 <b>{9.77*r(57.11,42.42)/100 + 7.63*r(31.33,23.17)/100:.2f}pp</b>。电网四只（南瑞、特变、正泰、西电）合计仅 {sum(w*r(a,b)/100 for n,_,a,b,w in TOP if n in ("国电南瑞","特变电工","正泰电器","中国西电")):+.2f}pp——"压舱石"确实在托，但托不住光纤那 17% 的权重。</p>

<h2><span class="no">08</span>收获：七条可复用的规则</h2>

<div class="lesson">
  <div class="n">LESSON 01</div>
  <h4>先给坐标，再给结论</h4>
  <p>任何"顶/底"判断，第一行必须是<b>"距 X 日高点 -Y%、PE 分位 Z%"</b>，而不是"年内涨跌"。这次如果第一行写的是"距 6/22 高点 -31.6%，PE 从 38.7 降到 26.8"，读者对赔率的理解会完全不同。</p>
  <div class="act"><b>下次怎么写：</b>报告开头固定三行——① 距 3 年高点；② 距 3 年低点；③ PE/PB 分位。缺一行不发。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 02</div>
  <h4>名字是包装，暴露是事实</h4>
  <p>"电网设备"这个名字在 10/12 被一次自然实验拆穿了：5 万亿投资、保变涨停，基金跟踪的指数却跌 1.24%。判断一只基金，看的是<b>波动贡献</b>，不是权重表，更不是名字。</p>
  <div class="act"><b>下次怎么做：</b>用"近 30 日相关性 × 权重"排一张<b>波动贡献表</b>；如果前两大贡献 &gt; 50%，就按那两只股票的逻辑给它定价。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 03</div>
  <h4>触发器要分层：领先、同步、滞后</h4>
  <p>现货价是<b>滞后确认</b>，不是领先指标；股价领先现货价，现货价领先财报。这次 9 月现货还在涨、Q3 业绩还在加速，股价已经跌了 26%。真正领先的是：估值分位、拥挤度、定增/解禁、股价结构（不再新高）。</p>
  <div class="act"><b>下次怎么做：</b>每个标的列 3 个领先 + 2 个同步 + 1 个滞后；只允许"领先"触发减仓，"滞后"只用于复核。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 04</div>
  <h4>周期股：盈利加速 + PE 下降 + 股价滞涨 = 卖出</h4>
  <p>亨通 Q3 单季 +299%，PE 从 26.8 降到 24.0，股价 -25.7%。这不是"便宜"，这是<b>顶部盈利把 PE 做低了</b>。报告识破了这个陷阱，却又把"2026E PE 20x 不贵"写进持有理由——<b>认知和执行打架，输的永远是执行</b>。</p>
  <div class="act"><b>下次怎么做：</b>周期股禁止用"动态 PE"做买入理由；只看 PB、毛利率位置、供给投放节奏。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 05</div>
  <h4>单月涨跌不能证明逻辑，要做归因</h4>
  <p>这次"清仓对了"，约六成归因于大盘 β。如果不拆 β / 行业 / 个股，就会把"躲过大盘"记成"看对光纤"，下一次在同样逻辑下重复下注，迟早还回去。</p>
  <div class="act"><b>下次怎么做：</b>复盘时先算"同期沪深300、创业板、行业指数"三个基准，再谈个股选择；超额收益才算 α。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 06</div>
  <h4>建议要可执行：给决策树，不给模糊区间</h4>
  <p>"先减 1/3~1/2"听起来稳健，实际是把最难的决定推回给读者。对一只已经 -30%、PE 76% 分位、供给冲击刚出现的基金，更合适的写法是："<b>若你买它的理由是电网投资 → 清仓换 932611；若你买的是光纤景气 → 设 57 元为止损，跌破无条件清</b>。"</p>
  <div class="act"><b>下次怎么写：</b>每条建议都带"如果…就…否则…"，并给出明确比例、价位、时间窗。</div>
</div>

<div class="lesson">
  <div class="n">LESSON 07</div>
  <h4>卖出必须有下半场：再入场条件</h4>
  <p>这次报告给了 4 个减仓触发器，却没给 1 个再入场条件。结果是你现在拿着一笔现金，面对一个跌了 40% 的指数，既不敢买、也不知道什么价位该买——这等于把"择时"做了一半。</p>
  <div class="act"><b>下次怎么做：</b>卖出同时写下"估值、价格、筹码、业绩"四类再入场条件，并规定"最多等多久、否则放弃"。</div>
</div>

<h2><span class="no">09</span>现在的坐标（不是买入建议）</h2>
<p class="lead">既然你已经空仓，问题就从"还能拿吗"变成了"什么条件下才值得重新看它"。先把坐标摆出来。</p>

<div class="nums">
  <div class="num-box"><div class="t">基金净值（10/29）</div><div class="v">{M['nav1']:.4f}</div><div class="s">已跌破 1 元面值；距顶 {pctf(M['ret_peak'])}</div></div>
  <div class="num-box"><div class="t">指数 PE(TTM)</div><div class="v">{M['pe1']:.1f}x</div><div class="s">2013 以来 {M['pe1_pct']:.0f}% 分位，中位 22.2</div></div>
  <div class="num-box"><div class="t">距 6/22 顶</div><div class="v down">{M['idx_peak_ret']:.1f}%</div><div class="s">指数 3834 → {M['idx_est']:.0f}（估算）</div></div>
</div>

<div class="card">
  <p><b>① 估值：便宜了，但没到"便宜"。</b>PE 从 38.7 杀到 24.0，分位从 99.6% 降到 69.3%；历史中位数是 22.2。按 10/30 估算约 23.3（66% 分位）。<b>跌了很多 ≠ 跌到位。</b></p>
  <p><b>② 盈利：E 在周期顶部。</b>亨通前三季 +159%、中天 +71%。Q3 财报并表后，PE 会"机械性"再降一截——看起来更便宜，实际是<b>顶部 E</b>。2027 年如果光纤价格回落，E 会反过来杀 PE。</p>
  <p><b>③ 价格：涨势放缓，但没崩。</b>9 月 G.652.D 88.4 元（+2.8% MoM）、G.657.A1 133.1 元（-1.6% MoM）。报告期待的是"连续 2 个月环比转负"，目前只满足一半。</p>
  <p><b>④ 供给：还没开始释放。</b>Q3 全行业约 400 亿扩产，光棒 18-24 个月周期，投放集中在 <b>2027 底~2028</b>；66 亿定增还会带来摊薄。也就是说，<b>供给冲击的"预期"已经杀了一轮，"现实"还没到。</b></p>
  <p><b>⑤ 市场：AI 资本开支正在被重新定价。</b>谷歌 -12%、纳指回调、创业板自 6 月 -44.8%。这类系统性去杠杆，个股基本面再好也扛不住。</p>
</div>

<h3>如果以后还想碰它：一份再入场检查表</h3>
<ul class="check">
  <li><b>估值</b>：PE 分位回到 50% 以下（约 22.2x 以下），或 PB 回到历史 30% 分位。</li>
  <li><b>价格</b>：G.652.D 现货连续 2 个月环比转负，<b>且</b>指数不再创新低（预期出清，而不是"跌得多"）。</li>
  <li><b>筹码</b>：定增落地、解禁/摊薄冲击消化，成交额萎缩到 6 月高峰的 1/3 以下。</li>
  <li><b>业绩</b>：单季毛利率见顶回落后的第一份"洗大澡"财报——不是业绩最好的那季。</li>
  <li><b>纪律</b>：先写止损位（例如再跌 15% 无条件走），再决定仓位；不要用"景气还在"当持有理由。</li>
</ul>
<p class="note">以上四条不必全满足；但若只满足"跌得多"这一条，那不是再入场，是接飞刀。</p>

<div class="quote">
  <b>三个情景（主观概率，仅供讨论）：</b>超跌反弹 30%（AI 资本开支重新加速 / 光纤价格再超预期）；磨底 45%（估值在 20-24x 反复，等 2027 供给落地）；二次探底 25%（AI 开支下修 + 2027 产能提前投放，PE 与 E 双杀）。<b>三种情景里，有两种不需要现在买。</b>
</div>

<div class="hr"></div>

<h2><span class="no">10</span>一句话总结</h2>
<div class="card verdict">
  <p><b class="hl">这份报告赢了结论，输了坐标。</b>它正确识别了"这是一只光纤 β"，也正确地让你在 9/29 离场；但它把 6 月的真顶看漏了，把一场全市场 AI 去杠杆讲成了光纤周期见顶，还在"减一半"和"全清"之间选了前者。</p>
  <p><b class="hlg">你赢在动作，不是赢在逻辑。</b>全清比报告建议多保住 6~9 个百分点，但其中约六成是大盘帮忙。下次真正要练的，是在 6/22 那种"PE 99.6% 分位、全市场同时见顶"的位置就动手，而不是等跌了 30% 再止损。</p>
</div>

<footer>
  <p><b>数据与口径说明</b>：基金净值为天天基金官方披露（10/29 为最新，10/30 未出，按跟踪 ETF 涨跌幅估算）；指数收盘与 PE(TTM) 来自中证指数官网；个股与 ETF 为腾讯行情前复权收盘价；个股权重为基金 2026 年三季报前十大持仓（占净值比例）。区间收益均以 2026-09-29 收盘为起点，不计交易费用。所有"估算"均已标注。</p>
  <p style="margin-top:10px"><b>主要来源</b>：</p>
  <p class="src">
    ① 天天基金 025833 净值、2026Q3 持仓　｜　② 中证指数官网 931994、932611 日线与 PE(TTM)　｜　③ 腾讯行情个股 / ETF 159326 前复权日线<br>
    ④ 瑞银《月度光纤价格追踪》2026-10-06（东方财富财富号转载）：9 月 G.652.D 88.4 元、G.657.A1 133.1 元、环比与需求数据<br>
    ⑤ 亨通光电 66.36 亿定增预案（2026-09-24）及 2026 三季报（10-28）：前三季净利 61.63 亿、+159.4%，Q3 单季 +299.1%<br>
    ⑥ 中天科技 2026 三季报（10-29）：前三季净利 40.01 亿、+71.1%，Q3 单季 +109%　｜　⑦ 21 世纪经济报道《5 万亿元电网投资蓝图下，电网设备板块强势大涨》（2026-10-12）<br>
    ⑧ 联合早报、东方财富 2026-10-30 盘面：谷歌 -12%、纳指 -1.4%、创业板 -4.13%
  </p>
  <p style="margin-top:14px">免责声明：本页为个人研究复盘，基于公开数据整理，不构成投资建议。所有情景概率为主观判断，可能完全错误。基金有风险，决策需独立。</p>
  <p style="margin-top:10px">生成时间：2026-10-30 16:50　｜　文件：Explore/fund-025833-review/index.html　｜　原报告：<a href="../fund-025833/index.html">fund-025833/index.html</a></p>
</footer>

</div>
</body>
</html>
"""

with open(os.path.join(BASE, "index.html"), "w", encoding="utf-8") as f:
    f.write(page)

print("written", os.path.join(BASE, "index.html"), len(page))
print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in M.items()})
print("top10 contribution", round(contrib, 2))