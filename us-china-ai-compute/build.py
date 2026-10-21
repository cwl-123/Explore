#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中美 AI 算力 · 月度估算对照 —— 生成 index.html

数据分三层：
  1) 公开锚点（硬数据，见 ANCHORS 与文末来源）
  2) 月内/季内：对数线性插值
  3) 2026 年及以后：按假设外推（页面上用阴影区标出）

运行：python3 build.py
输出：同目录 index.html（单文件，ECharts 走 CDN）
注意：页面顶部导航由 ../build_site.py 注入，重新生成后需再跑一次 python3 ../build_site.py
"""

from __future__ import annotations

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "index.html")

# ---------------------------------------------------------------------------
# 时间轴：2023-12 ~ 2026-12（用于插值），页面只展示 2024-01 ~ 2026-10
# ---------------------------------------------------------------------------
def month_seq(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out

AXIS = month_seq("2023-12", "2026-12")
SHOW = month_seq("2024-01", "2026-10")
IDX = {m: i for i, m in enumerate(AXIS)}


def interp(anchors: list[tuple[str, float]], log: bool = True) -> list[float]:
    """在 AXIS 上做锚点插值（默认对数线性）。"""
    pts = sorted(((IDX[m], v) for m, v in anchors))
    out = []
    for i in range(len(AXIS)):
        if i <= pts[0][0]:
            out.append(pts[0][1])
            continue
        if i >= pts[-1][0]:
            out.append(pts[-1][1])
            continue
        for (i0, v0), (i1, v1) in zip(pts, pts[1:]):
            if i0 <= i <= i1:
                t = (i - i0) / (i1 - i0)
                if log:
                    out.append(math.exp(math.log(v0) + t * (math.log(v1) - math.log(v0))))
                else:
                    out.append(v0 + t * (v1 - v0))
                break
    return out


def show(series: list[float]) -> list[float]:
    return [series[IDX[m]] for m in SHOW]


def rnd(series: list[float], nd: int = 0) -> list[float]:
    return [round(v, nd) for v in series]


# ---------------------------------------------------------------------------
# 1. 算力存量（累计交付，H100e）
#    来源：Epoch AI《AI chip owners》（2026-05 更新），按季度累加
#      - 美国 = Amazon+Microsoft+Meta+Google+Oracle+CoreWeave+xAI+Other
#      - 中国官方 = Nvidia+华为昇腾+寒武纪+AMD
#      - 中国含走私 = 官方 + Epoch 走私中位估计（2024 起）
# ---------------------------------------------------------------------------
US_COMPUTE = [
    ("2023-12", 1_400_000), ("2024-03", 2_150_000), ("2024-06", 3_090_000),
    ("2024-09", 4_410_000), ("2024-12", 6_120_000), ("2025-03", 8_470_000),
    ("2025-06", 11_090_000), ("2025-09", 14_880_000), ("2025-12", 19_110_000),
    ("2026-12", 29_600_000),  # 外推：+55%（2026 capex 约 8000 亿美元，但单位算力更贵）
]
CN_COMPUTE = [
    ("2023-12", 180_000), ("2024-03", 244_000), ("2024-06", 323_000),
    ("2024-09", 410_000), ("2024-12", 509_000), ("2025-03", 700_000),
    ("2025-06", 862_000), ("2025-09", 1_004_000), ("2025-12", 1_155_000),
    ("2026-12", 1_675_000),  # 外推：+45%
]
CN_SMUGGLE = [
    ("2024-03", 27_761), ("2024-06", 63_970), ("2024-09", 106_643),
    ("2024-12", 158_675), ("2025-03", 246_884), ("2025-06", 411_461),
    ("2025-09", 547_010), ("2025-12", 662_048),
]

us_c = show(interp(US_COMPUTE))
cn_c = show(interp(CN_COMPUTE))
smug = show(interp([("2023-12", 0)] + CN_SMUGGLE + [("2026-12", 662_048 * 1.45)], log=False))
cn_all = [a + b for a, b in zip(cn_c, smug)]
ratio = [a / b for a, b in zip(us_c, cn_all)]

# ---------------------------------------------------------------------------
# 2. 日均 Token（万亿/天）
#    中国：国家数据局官方口径（调用量），锚点为公开披露
#    美国：全球指数 × 非中国份额拆分（低置信，给区间）
# ---------------------------------------------------------------------------
CN_TOKEN = [
    ("2024-01", 0.1), ("2025-06", 30), ("2025-12", 100),
    ("2026-03", 140), ("2026-06", 175), ("2026-10", 200),
]
US_TOKEN = [
    ("2024-01", 0.8), ("2024-06", 3.0), ("2024-12", 12), ("2025-03", 30),
    ("2025-06", 55), ("2025-09", 75), ("2025-12", 95), ("2026-03", 105),
    ("2026-06", 118), ("2026-10", 127),
]
cn_t = show(interp(CN_TOKEN))
us_t = show(interp(US_TOKEN))
us_lo = [v * 0.72 for v in us_t]
us_hi = [v * 1.32 for v in us_t]

CN_ANCHORS_SHOW = [(m, v) for m, v in CN_TOKEN if m in SHOW]
cn_pts = [[SHOW.index(m), round(v, 3)] for m, v in CN_ANCHORS_SHOW]

cross = next((i for i, (c, u) in enumerate(zip(cn_t, us_t)) if c >= u), None)

# 全球 token 份额：中国官方 / 美国估算 / 其他（= 中美合计 × 0.25，模型假设）
rest_t = [(c + u) * 0.25 for c, u in zip(cn_t, us_t)]
total_t = [c + u + r for c, u, r in zip(cn_t, us_t, rest_t)]
cn_share = [c / t * 100 for c, t in zip(cn_t, total_t)]
us_share = [u / t * 100 for u, t in zip(us_t, total_t)]
rest_share = [r / t * 100 for r, t in zip(rest_t, total_t)]

# ---------------------------------------------------------------------------
# 3. 资本开支（年化，十亿美元）与数据中心容量（GW）
# ---------------------------------------------------------------------------
US_CAPEX = [("2024-01", 200), ("2024-06", 220), ("2024-12", 240),
            ("2025-06", 330), ("2025-12", 400), ("2026-06", 650), ("2026-12", 800)]
CN_CAPEX = [("2024-01", 32), ("2024-06", 36), ("2024-12", 42),
            ("2025-06", 52), ("2025-12", 63), ("2026-06", 90), ("2026-12", 110)]
us_capex = [v / 12 for v in show(interp(US_CAPEX))]
cn_capex = [v / 12 for v in show(interp(CN_CAPEX))]

US_GW = [("2024-01", 28), ("2024-12", 35), ("2025-06", 43), ("2025-12", 50), ("2026-12", 56)]
CN_GW = [("2024-01", 18), ("2024-12", 25), ("2025-12", 31), ("2026-12", 38)]
us_gw = show(interp(US_GW, log=False))
cn_gw = show(interp(CN_GW, log=False))

# ---------------------------------------------------------------------------
# 4. 当前快照（2026-10）
# ---------------------------------------------------------------------------
LAST = -1
snap = {
    "us_compute": us_c[LAST],
    "cn_compute": cn_all[LAST],
    "ratio": ratio[LAST],
    "cn_token": cn_t[LAST],
    "us_token": us_t[LAST],
    "token_ratio": cn_t[LAST] / us_t[LAST],
    "cn_share": cn_share[LAST],
    "us_gw": us_gw[LAST],
    "cn_gw": cn_gw[LAST],
    "us_capex": us_capex[LAST] * 12,
    "cn_capex": cn_capex[LAST] * 12,
}

# 100% 堆叠：供给 / 使用 / 投入
share_bars = {
    "compute": [us_c[LAST] / (us_c[LAST] + cn_all[LAST]) * 100,
                cn_all[LAST] / (us_c[LAST] + cn_all[LAST]) * 100],
    "capex": [snap["us_capex"] / (snap["us_capex"] + snap["cn_capex"]) * 100,
              snap["cn_capex"] / (snap["us_capex"] + snap["cn_capex"]) * 100],
    "token": [us_t[LAST] / (us_t[LAST] + cn_t[LAST]) * 100,
              cn_t[LAST] / (us_t[LAST] + cn_t[LAST]) * 100],
}

DATA = {
    "months": SHOW,
    "compute": {
        "us": rnd(us_c),
        "cn": rnd(cn_c),
        "cnAll": rnd(cn_all),
        "ratio": rnd(ratio, 2),
    },
    "tokens": {
        "cn": rnd(cn_t, 1),
        "us": rnd(us_t, 1),
        "usLo": rnd(us_lo, 1),
        "usHi": rnd(us_hi, 1),
        "cnPts": cn_pts,
        "crossIdx": cross,
    },
    "shares": {
        "cn": rnd(cn_share, 1),
        "us": rnd(us_share, 1),
        "rest": rnd(rest_share, 1),
    },
    "capex": {"us": rnd(us_capex, 1), "cn": rnd(cn_capex, 1)},
    "gw": {"us": rnd(us_gw, 1), "cn": rnd(cn_gw, 1)},
    "bars": share_bars,
}

# ---------------------------------------------------------------------------
# 5. 月度明细表（季度抽样）
# ---------------------------------------------------------------------------
rows = []
for m in SHOW:
    if (int(m[5:]) - 1) % 3 != 0:
        continue
    i = SHOW.index(m)
    def tok(v):
        return f"{v:.1f}" if v < 10 else f"{v:.0f}"

    rows.append(
        "<tr><td class='mon'>%s</td><td>%.1f</td><td>%.2f</td><td class='hl'>%.1f×</td>"
        "<td>%s</td><td>%s</td><td>%.2f×</td></tr>"
        % (m, us_c[i] / 1e6, cn_all[i] / 1e6, ratio[i],
           tok(us_t[i]), tok(cn_t[i]), cn_t[i] / us_t[i])
    )
TABLE_ROWS = "\n".join(rows)


def fmt(v: float, nd: int = 1) -> str:
    return f"{v:,.{nd}f}"


KPIS = f"""
<div class="kpi"><div class="k">AI 算力存量 · 2026-10</div>
  <div class="v"><span class="us">{snap['us_compute']/1e6:.1f}M</span> <i>vs</i> <span class="cn">{snap['cn_compute']/1e6:.2f}M</span></div>
  <div class="s">H100 等效 · 美国约为中国 {snap['ratio']:.1f} 倍</div></div>
<div class="kpi"><div class="k">日均 Token · 2026-10</div>
  <div class="v"><span class="cn">{snap['cn_token']:.0f}</span> <i>vs</i> <span class="us">{snap['us_token']:.0f}</span></div>
  <div class="s">万亿/天 · 中国约为美国 {snap['token_ratio']:.1f} 倍</div></div>
<div class="kpi"><div class="k">数据中心容量 · 2026-10</div>
  <div class="v"><span class="us">{snap['us_gw']:.0f}</span> <i>vs</i> <span class="cn">{snap['cn_gw']:.0f}</span></div>
  <div class="s">GW · 美国约为中国 {snap['us_gw']/snap['cn_gw']:.1f} 倍</div></div>
<div class="kpi"><div class="k">AI 资本开支 · 年化</div>
  <div class="v"><span class="us">${snap['us_capex']:.0f}B</span> <i>vs</i> <span class="cn">${snap['cn_capex']:.0f}B</span></div>
  <div class="s">run-rate · 美国约为中国 {snap['us_capex']/snap['cn_capex']:.1f} 倍</div></div>
<div class="kpi"><div class="k">单 Token 价格</div>
  <div class="v"><span class="us">$11.25</span> <i>vs</i> <span class="cn">$1.71</span></div>
  <div class="s">美元/百万 token · GPT-5.5 vs Kimi K2.6</div></div>
<div class="kpi"><div class="k">前沿模型能力差</div>
  <div class="v"><span class="us">~7</span> <i>个月</i></div>
  <div class="s">Epoch ECI 均值（区间 4-14 个月）</div></div>
"""

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>中美 AI 算力 · 月度估算对照（2024-01 ~ 2026-10）</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>window.echarts||document.write('<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"><\/script>')</script>
<style>
  :root{
    --bg:#f6f7f9; --card:#fff; --ink:#1c2430; --muted:#6b7686; --line:#e6e9ee;
    --us:#2f6fed; --us-soft:#eef3fe; --cn:#d94a4a; --cn-soft:#fdeeee;
    --amber:#e0a300; --green:#2c9e63;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--ink);line-height:1.7;-webkit-font-smoothing:antialiased;
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
  .wrap{max-width:1120px;margin:0 auto;padding:28px 20px 90px;}
  header.top{margin-bottom:20px;}
  header.top h1{font-size:27px;line-height:1.35;margin:0 0 8px;letter-spacing:.2px;}
  header.top .sub{color:var(--muted);font-size:13.5px;}
  .pill{display:inline-block;font-size:12px;padding:2px 10px;border-radius:999px;background:var(--us-soft);color:var(--us);margin-left:8px;vertical-align:2px;}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 24px;margin-bottom:18px;
    box-shadow:0 1px 2px rgba(20,30,50,.03);}
  h2{font-size:19px;margin:0 0 6px;display:flex;align-items:center;gap:9px;flex-wrap:wrap;}
  h2 .n{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:8px;
    background:var(--ink);color:#fff;font-size:12.5px;font-weight:700;flex:none;}
  h3{font-size:15px;margin:18px 0 8px;}
  p{margin:9px 0;font-size:14px;}
  .lead{color:var(--muted);font-size:13.5px;margin:0 0 14px;}
  .muted{color:var(--muted);font-size:12.5px;}
  .kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:16px 0 6px;}
  .kpi{background:#fafbfc;border:1px solid var(--line);border-radius:13px;padding:14px 15px;}
  .kpi .k{font-size:11.5px;color:var(--muted);letter-spacing:.2px;}
  .kpi .v{font-size:21px;font-weight:750;margin-top:5px;font-variant-numeric:tabular-nums;line-height:1.25;}
  .kpi .v i{font-style:normal;font-size:12px;font-weight:500;color:var(--muted);margin:0 2px;}
  .kpi .s{font-size:11.5px;color:var(--muted);margin-top:4px;}
  .us{color:var(--us);} .cn{color:var(--cn);} .am{color:var(--amber);}
  .verdict{background:linear-gradient(135deg,#f7faff,#fff);border:1px solid #dbe5fb;border-radius:13px;padding:15px 17px;font-size:14px;margin:14px 0 2px;}
  .verdict b.t{display:block;font-size:12px;letter-spacing:1px;color:var(--us);margin-bottom:5px;}
  .verdict ul{margin:6px 0 0;padding-left:19px;}
  .verdict li{margin:5px 0;}
  .chart{width:100%;height:380px;}
  .chart.sm{height:300px;}
  .ch-note{font-size:12px;color:var(--muted);margin:8px 0 0;line-height:1.75;}
  .ch-note b{color:#41506a;}
  .tag{display:inline-block;font-size:11px;padding:1px 8px;border-radius:999px;background:#eef1f5;color:#41506a;margin-right:6px;}
  .tag.us{background:var(--us-soft);color:var(--us);}
  .tag.cn{background:var(--cn-soft);color:var(--cn);}
  table{width:100%;border-collapse:collapse;font-size:13px;}
  th,td{padding:9px 8px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap;font-variant-numeric:tabular-nums;}
  th:first-child,td:first-child{text-align:left;}
  th{color:var(--muted);font-weight:600;font-size:11.5px;background:#fafbfc;}
  tr:last-child td{border-bottom:none;}
  td.mon{font-weight:600;}
  td.hl{color:var(--amber);font-weight:700;}
  .scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;}
  .two{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  .note{background:#fafbfc;border:1px solid var(--line);border-radius:12px;padding:13px 15px;font-size:12.5px;color:#4b5768;line-height:1.8;}
  .note b{color:var(--ink);}
  .range{display:grid;grid-template-columns:150px 1fr 130px;gap:14px;align-items:center;padding:11px 0;border-bottom:1px dashed var(--line);font-size:13px;}
  .range:last-child{border-bottom:none;}
  .range .lab{color:#41506a;line-height:1.4;}
  .range .lab small{display:block;color:var(--muted);font-size:11px;}
  .track{position:relative;height:12px;border-radius:6px;background:#eef1f5;}
  .track .band{position:absolute;height:12px;border-radius:6px;background:rgba(217,74,74,.22);}
  .track .mid{position:absolute;top:-3px;width:3px;height:18px;border-radius:2px;background:var(--cn);}
  .range .val{text-align:right;font-weight:650;font-variant-numeric:tabular-nums;}
  .range .val small{display:block;font-weight:400;color:var(--muted);font-size:11px;}
  .score td.who{text-align:left;font-weight:600;white-space:nowrap;width:260px;}
  .bw{display:inline-block;width:64px;height:7px;border-radius:4px;background:#eef1f5;margin-right:8px;vertical-align:middle;overflow:hidden;}
  .bw i{display:block;height:7px;border-radius:4px;background:var(--us);}
  .src{font-size:12.5px;color:#4b5768;line-height:1.9;padding-left:20px;}
  .src li{margin:3px 0;}
  .src a{color:var(--us);text-decoration:none;border-bottom:1px solid #cfdcfa;}
  .src a:hover{border-color:var(--us);}
  footer{color:var(--muted);font-size:12px;line-height:1.9;margin-top:24px;}
  .disc{display:flex;gap:10px;align-items:flex-start;background:#fffaf0;border:1px solid #f3e2bd;border-radius:12px;
    padding:12px 15px;font-size:12.5px;color:#6a5528;line-height:1.75;margin:0 0 16px;}
  .disc b{color:#8a6a1f;}
  .legendhint{font-size:11.5px;color:#9aa3b2;margin-left:auto;font-weight:400;}
  @media(max-width:860px){
    .kpis{grid-template-columns:repeat(2,1fr);}
    .two{grid-template-columns:1fr;}
    .chart{height:340px;}
    header.top h1{font-size:22px;}
    .range{grid-template-columns:110px 1fr 96px;}
  }
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>中美 AI 算力 · 月度估算对照<span class="pill">市场专题</span></h1>
    <div class="sub">算力存量 / 日均 Token / 资本开支 / 电力 / 价格与收入 —— 2024-01 ~ 2026-10，逐月估算；数据截至 2026-10-21</div>
  </header>

  <div class="disc">
    <div>⚠️</div>
    <div><b>先看口径：</b>只有中国官方 token 数、Epoch 的芯片存量、各国 capex 是硬锚点，其余月份为<b>对数线性插值</b>，2026 年为<b>外推</b>（图中阴影）；美国 token 为按全球指数拆分的<b>区间估算</b>（低置信）。中美“token”统计范围并不等价，绝对倍数请当作量级参考，不要当会计数字。</div>
  </div>

  <div class="card">
    <h2><span class="n">0</span>信号速览</h2>
    <div class="kpis">__KPIS__</div>
    <div class="verdict"><b class="t">一句话结论</b>
      <ul>
        <li><b>供给端美国仍在拉开：</b>算力存量约为中国 <b>11 倍</b>（含走私估算；不含则约 17 倍），2026 年美国 AI capex 接近 <b>8000 亿美元</b>、中国约 <b>1100 亿（估算）</b>，差距没有收敛迹象。</li>
        <li><b>使用端中国已经反超：</b>日均 token 中国 <b>约 200 万亿</b>、美国 <b>约 127 万亿</b>，中国约占全球 <b>四到五成</b>；但单价只有美国 <b>1/6.6</b>、AI 收入约为 <b>1/10</b>——是“以量补价”，不是“以量补质”。</li>
        <li><b>最接近的维度是电和机房：</b>美国数据中心容量约 1.5 倍于中国，中国发电装机约为美国 2.8 倍，电力是中国少有的结构性优势。</li>
        <li><b>真正的变量在芯片：</b>华为 2026 年算力产出不足英伟达 4%，走私累计 29 万 ~ 160 万 H100e（中位 66 万）——这条灰色通道的量级，直接决定中国 2027 年算力增速会不会掉档。</li>
      </ul>
    </div>
  </div>

  <div class="card">
    <h2><span class="n">1</span>算力存量：美国约 11 倍，且还在拉大<span class="legendhint">点击图例可切换曲线</span></h2>
    <p class="lead">累计交付的 AI 芯片折算成 H100 等效（H100e，按 FP8/INT8 稠密算力）；含“其他厂商/主权 AI”口径，美国=7 家美国持有者+Other，中国=官方可得+走私中位估计。</p>
    <div id="c1" class="chart"></div>
    <div class="ch-note"><b>读数：</b>2024-01 美国 1.4M / 中国 0.18M（约 7.8 倍）→ 2025-12 美国 19.1M / 中国 1.82M（10.5 倍）→ 2026-10 估算 27.5M / 2.48M（<b>11.1 倍</b>）。2026 年阴影为外推：美国按 +55%、中国按 +45%。若剔除走私，2026-10 差距约 <b>17 倍</b>；若再剔除“Other（主权 AI/新云）”类，2025-12 差距约 <b>8.7 倍</b>，与 BCG / Exponential View 的“8 倍”互相印证。</div>
  </div>

  <div class="card">
    <h2><span class="n">2</span>日均 Token：中国反超，约 1.6 倍</h2>
    <p class="lead">中国为国家数据局“日均词元调用量”官方口径；美国为全球 token 指数按非中国份额拆分的估算（虚线=中值，浅带=±30% 区间）。红色圆点为官方披露节点。</p>
    <div id="c2" class="chart"></div>
    <div class="ch-note"><b>读数：</b>中国 2024-01 仅 0.1 万亿/天 → 2025-06 30 万亿 → 2025-12 100 万亿 → 2026-03 140 万亿 → 2026-06 <b>175 万亿</b>，两年半增长约 1750 倍；美国同期从约 0.8 万亿增至约 127 万亿（约 160 倍）。<b>交叉点约在 2025 年 Q4</b>，此后中国持续领先。</div>
  </div>

  <div class="card">
    <h2><span class="n">3</span>份额错位：8% 的算力，供着四到五成的 token</h2>
    <p class="lead">同一时点（2026-10 估算）的三组 100% 堆叠：供给（算力存量）、投入（2026 capex）、使用（日均 token）。</p>
    <div id="c3" class="chart sm"></div>
    <div class="two" style="margin-top:6px">
      <div class="note"><b>怎么读：</b>美国用约 <b>92%</b> 的算力、<b>88%</b> 的资本开支，只产出约 <b>39%</b> 的 token；中国用 <b>8%</b> 的算力、<b>12%</b> 的投入，产出约 <b>61%</b> 的 token（中美合计口径）。折算“每 H100e 每天产出 token”，中国约为美国的 <b>15~20 倍</b>。</div>
      <div class="note"><b>为什么不是 bug：</b>① 美国算力大量用于训练与前沿模型，不直接产 token；② 中国以中小参数模型、低价 API、Agent/短视频/电商场景跑量；③ 中国“调用量”含缓存命中与输入 token，统计更宽。这条“错位”是结构差异，不是效率奇迹。</div>
    </div>
    <div id="c4" class="chart sm" style="margin-top:10px"></div>
    <div class="ch-note"><b>全球份额：</b>图中曲线从 2024-01 的约 7% 升至 2026-10 的 <b>约 50%</b>，前提是“其他地区 = 中美合计 × 0.25”。若改用 Tokens Per Day 的全球 444.6 万亿/天口径、中国沿用 6 月官方值，则中国约占 <b>39%</b>；BCG 则判断 2026 Q2 已 <b>过半</b>。合理区间 <b>39%~55%</b>，但方向一致：中国已是全球最大的 token 消费国。</div>
  </div>

  <div class="card">
    <h2><span class="n">4</span>钱：资本开支差 7 倍，且在加速</h2>
    <p class="lead">月度年化 run-rate（十亿美元/月）。美国=五大云厂+Oracle 的 capex 口径；中国=阿里/腾讯/字节/百度等合计估算。</p>
    <div id="c5" class="chart"></div>
    <div class="ch-note"><b>读数：</b>2024 年美国约 <b>170 亿美元/月</b>、中国约 <b>30 亿美元/月</b>；2026-10 美国约 <b>620 亿美元/月</b>、中国约 <b>85 亿美元/月</b>。美国 2026 全年 capex 指引 6600~6900 亿美元（BCG 口径 &gt;8000 亿），中国约 1100 亿美元；但中国单美元形成的算力更高（电价、建设成本、国产芯片单价低）。</div>
  </div>

  <div class="card">
    <h2><span class="n">5</span>电与机房：差距最小的维度</h2>
    <p class="lead">数据中心总容量（含超大规模/托管/企业，GW），不是 AI 专用容量；AI 专用容量目前没有国际可比口径。</p>
    <div class="two">
      <div><div id="c6" class="chart sm"></div></div>
      <div>
        <div class="note" style="margin-bottom:12px"><b>电力：中国真正的底牌</b><br>
        2024 年中国新增发电装机 <b>543 GW</b>，超过美国有史以来新增装机总和；中国总装机约 <b>3.6 TW</b>，美国约 <b>1.3 TW</b>。到 2030 年中国预计有约 <b>400 GW</b> 冗余电力，是全球数据中心届时需求的约 3 倍。</div>
        <div class="note"><b>但电不是算力：</b>美国受并网排队、变压器交期约束，2026 年约 12 GW 新增容量中仅约 5 GW 在建设中；中国受先进制程与 HBM 约束，<b>有电也未必有卡</b>。两边卡在不同的瓶颈上。</div>
        <div class="note" style="margin-top:12px"><b>用电量对比：</b>中国数据中心用电 2025 年 <b>1960 亿 kWh</b>（占全社会 1.9%），2030 年预计 8000 亿 kWh（6%）；美国数据中心用电占比已约 4%，更高但增速受电网限制。</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2><span class="n">6</span>价格、收入与模型：以量补价</h2>
    <div class="two">
      <div>
        <h3 style="margin-top:0">年化 AI 收入（十亿美元）</h3>
        <div id="c7" class="chart sm"></div>
      </div>
      <div>
        <div class="note" style="margin-bottom:12px"><b>单 token 价格：</b>Kimi K2.6 <b>$1.71</b> / 百万 token，GPT-5.5 <b>$11.25</b>，差 <b>6.6 倍</b>。中国模型用 1/6 的价格提供“接近前沿”的能力，这是 token 量能反超的价格基础。</div>
        <div class="note" style="margin-bottom:12px"><b>收入：</b>OpenAI 2026 年底 ARR 指引 <b>700 亿美元</b>，Anthropic 7 月 run-rate <b>650 亿美元</b>，合计约 <b>1350 亿</b>；中国六家头部 AI 公司合计仅为两者的 <b>约 10%</b>（约 135 亿美元），高盛口径的中国模型 API+订阅收入 2026 年仅约 <b>350 亿元人民币</b>。</div>
        <div class="note"><b>能力：</b>Epoch ECI 口径，中国模型平均落后美国前沿 <b>7 个月</b>（区间 4~14 个月）；Stanford AI Index 2026 的判断更激进——“性能差距已基本闭合”。分歧本身说明：<b>能力在收敛，算力和收入没有</b>。</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2><span class="n">7</span>芯片与供应链：三条灰色/红色曲线</h2>
    <p class="lead">这是整张图里误差最大、也最能改变结论的部分。</p>
    <div class="range">
      <div class="lab">走私入境累计<small>2024-01 ~ 2025-12，H100e</small></div>
      <div class="track"><div class="band" style="left:16.1%;width:72.8%"></div><div class="mid" style="left:36.7%"></div></div>
      <div class="val">29 万 ~ 160 万<small>中位 66 万</small></div>
    </div>
    <div class="range">
      <div class="lab">华为 2026 算力产出<small>相对英伟达</small></div>
      <div class="track"><div class="band" style="left:0;width:4%;background:rgba(217,74,74,.35)"></div><div class="mid" style="left:3.8%"></div></div>
      <div class="val">&lt; 4%<small>约 1/25</small></div>
    </div>
    <div class="range">
      <div class="lab">中国官方口径 Nvidia 存量<small>2025-12，H100e</small></div>
      <div class="track"><div class="band" style="left:0;width:22%;background:rgba(47,111,237,.22)"></div><div class="mid" style="left:21.8%;background:var(--us)"></div></div>
      <div class="val">40 万<small>已连续 3 季持平</small></div>
    </div>
    <div class="note" style="margin-top:14px"><b>解读：</b>① 走私中位 66 万 H100e，相当于中国官方存量的一半以上——美国出口管制“漏”出的算力，是中国 2025 年算力增长的重要来源；② 华为昇腾 2026 年计划产出 160 万片裸芯片（其中 910C 约 60 万片），但单卡算力与良率受限，折算 H100e 仍不足英伟达 4%；③ 中国官方 Nvidia 存量 2025Q3 后走平，说明合规渠道基本关闭，增量只能靠国产+走私。</div>
  </div>

  <div class="card">
    <h2><span class="n">8</span>综合记分卡：十个维度，谁领先</h2>
    <div class="scroll">
      <table class="score">
        <thead><tr><th>维度</th><th>美国</th><th>中国</th><th style="text-align:left">领先方 / 倍数</th></tr></thead>
        <tbody>
          <tr><td>AI 算力存量（H100e）</td><td>27.5M</td><td>2.5M</td><td class="who"><span class="bw"><i style="width:100%"></i></span>美国 · 11.1×</td></tr>
          <tr><td>数据中心容量（GW）</td><td>55</td><td>37</td><td class="who"><span class="bw"><i style="width:22%"></i></span>美国 · 1.5×</td></tr>
          <tr><td>2026 AI 资本开支</td><td>~$800B</td><td>~$110B</td><td class="who"><span class="bw"><i style="width:78%"></i></span>美国 · 7.3×</td></tr>
          <tr><td>前沿模型能力（ECI）</td><td>前沿</td><td>落后 7 个月</td><td class="who"><span class="bw"><i style="width:9%"></i></span>美国 · 约 7 个月</td></tr>
          <tr><td>日均 Token</td><td>127 万亿</td><td>200 万亿</td><td class="who"><span class="bw"><i style="width:24%;background:var(--cn)"></i></span>中国 · 1.6×</td></tr>
          <tr><td>单 token 价格</td><td>$11.25</td><td>$1.71</td><td class="who"><span class="bw"><i style="width:66%;background:var(--cn)"></i></span>中国便宜 · 6.6×</td></tr>
          <tr><td>头部 AI 年化收入</td><td>~$135B</td><td>~$13.5B</td><td class="who"><span class="bw"><i style="width:90%"></i></span>美国 · 10×</td></tr>
          <tr><td>大型 AI 数据中心数量</td><td>~10×</td><td>1×</td><td class="who"><span class="bw"><i style="width:85%"></i></span>美国 · 约 10×</td></tr>
          <tr><td>发电装机（TW）</td><td>1.3</td><td>3.6</td><td class="who"><span class="bw"><i style="width:64%;background:var(--cn)"></i></span>中国 · 2.8×</td></tr>
          <tr><td>AI 芯片有效算力产出</td><td>英伟达 100%</td><td>华为 &lt;4%</td><td class="who"><span class="bw"><i style="width:96%"></i></span>美国 · 约 25×</td></tr>
        </tbody>
      </table>
    </div>
    <div class="ch-note">倍数按“领先方 / 落后方”计算；算力为中国含走私口径，若不含则美国领先约 17×。收入为 OpenAI+Anthropic 合计 vs 中国六家头部公司。</div>
  </div>

  <div class="card">
    <h2><span class="n">9</span>月度估算明细<span class="legendhint">季度抽样，单位：M H100e / 万亿 token·天</span></h2>
    <div class="scroll">
      <table>
        <thead><tr><th>月份</th><th>美国算力</th><th>中国算力*</th><th>算力倍数</th><th>美国 token</th><th>中国 token</th><th>Token 倍数</th></tr></thead>
        <tbody>
__TABLE__
        </tbody>
      </table>
    </div>
    <div class="ch-note">* 中国算力含走私中位估计；2026 年 1 月起为外推值。源数据与插值脚本见仓库 <code>us-china-ai-compute/build.py</code>。</div>
  </div>

  <div class="card">
    <h2><span class="n">10</span>方法、误差与来源</h2>
    <h3>三层数据</h3>
    <ul style="font-size:13.5px;padding-left:20px;margin:6px 0">
      <li><b>硬锚点：</b>Epoch 每季度芯片存量（截至 2025-12 完整）、中国官方 token（2024-01 / 2025-06 / 2025-12 / 2026-03 / 2026-06）、BCG 的 capex 与 GW、SemiAnalysis 的 2026 GW。</li>
      <li><b>插值：</b>锚点之间对数线性（资本开支与 GW 用线性），月度点为“估算”。</li>
      <li><b>外推：</b>2026-01 起美国算力 +55%/年、中国 +45%/年；token 中国 2026-06 后按约 4%/月、美国按约 3%/月减速。</li>
    </ul>
    <h3>已知误差（按影响排序）</h3>
    <ul style="font-size:13.5px;padding-left:20px;margin:6px 0">
      <li><b>美国 token ±30%：</b>没有官方统计，靠全球指数与 OpenRouter 账单地域份额拆分；Google 单家披露就有“月度 3.2Q”与“每分钟 220 亿”两种口径。</li>
      <li><b>中国算力 ±25%：</b>走私量的 5%~95% 区间是 29 万~160 万 H100e；华为芯片的 H100e 折算系数也缺公开校验。</li>
      <li><b>capex 口径：</b>美国 8000 亿含非 AI 基建；中国 1100 亿含互联网大厂+运营商，二者不完全可比。</li>
      <li><b>“算力倍数”与“token 倍数”不可相乘：</b>训练/推理结构、模型大小、统计范围都不同。</li>
    </ul>
    <h3>来源</h3>
    <ol class="src">
      <li>Epoch AI, <a href="https://epoch.ai/data/ai-chip-owners" target="_blank" rel="noopener">AI chip owners</a>（2026-05 更新，季度存量与走私拆分）</li>
      <li>Epoch AI, <a href="https://epoch.ai/publications/chip-smuggling" target="_blank" rel="noopener">Diversion and resale: estimating compute smuggling to China</a>（2026-04）</li>
      <li>Epoch AI, <a href="https://epoch.ai/publications/huaweis-roadmap-to-2031" target="_blank" rel="noopener">Will Huawei catch up to Nvidia by 2030?</a>（2026-09）</li>
      <li>RFI, <a href="https://www.rfi.fr/cn/%E4%B8%AD%E5%9B%BD/20250929-%E5%8D%8E%E4%B8%BA%E6%8B%9F%E6%98%8E%E5%B9%B4%E7%94%9F%E4%BA%A7%E7%BA%A660%E4%B8%87%E6%9E%9A%E6%98%87%E8%85%BE910c%E8%8A%AF%E7%89%87-%E4%BA%A7%E9%87%8F%E7%BA%A6%E4%B8%BA%E4%BB%8A%E5%B9%B4%E4%B8%A4%E5%80%8D" target="_blank" rel="noopener">华为 2026 年昇腾产量约 160 万片</a>（2025-09）</li>
      <li>Epoch AI, <a href="https://epoch.ai/publications/how-do-chinese-ai-companies-make-money" target="_blank" rel="noopener">How do Chinese AI companies make money?</a>（2026-10）</li>
      <li>Epoch AI, <a href="https://epoch.ai/data-insights/us-vs-china-eci" target="_blank" rel="noopener">US vs China ECI gap</a>（2026-01）</li>
      <li>BCG, <a href="https://www.bcg.com/publications/2026/us-and-china-ai-strategy-causing-global-ai-divide" target="_blank" rel="noopener">The Great Divide</a>（2026-06，capex / GW / 价格）</li>
      <li>国家数据局 / 新华社, <a href="https://www.news.cn/tech/20260326/8026bd54df3f489a8c79d4438cac96b3/c.html" target="_blank" rel="noopener">日均 Token 调用量达 140 万亿</a>（2026-03）</li>
      <li>中国信通院（WAIC 2026）/ 钛媒体, <a href="https://www.tmtpost.com/8075990.html" target="_blank" rel="noopener">2026-06 日均近 175 万亿</a></li>
      <li>新华网, <a href="https://www.news.cn/info/20250814/bc764f22819c4087bfc5939cfedc7f49/c.html" target="_blank" rel="noopener">2025-06 突破 30 万亿</a>（2025-08）</li>
      <li>Tokens Per Day, <a href="https://tokensperday.com/" target="_blank" rel="noopener">AI inference demand index</a>（2026-10-21，全球 444.6T/天、国别拆分）</li>
      <li>SemiAnalysis, <a href="https://newsletter.semianalysis.com/p/the-chinese-ai-infrastructure-boom" target="_blank" rel="noopener">The Chinese AI Infrastructure Boom</a>（美国 56GW / 2026YE）</li>
      <li>CNN, <a href="https://www.cnn.com/2026/10/13/china/china-data-centers-ai-race-intl-hnk-dst" target="_blank" rel="noopener">The US is fighting over data centers. China is building them fast</a>（2026-10）</li>
      <li>Stanford HAI, <a href="https://hai.stanford.edu/ai-index/2026-ai-index-report" target="_blank" rel="noopener">AI Index 2026</a></li>
      <li>Futurum, <a href="https://futurumgroup.com/insights/ai-capex-2026-the-690b-infrastructure-sprint/" target="_blank" rel="noopener">AI Capex 2026: The $690B Infrastructure Sprint</a></li>
      <li>Bloomberg, <a href="https://www.bloomberg.com/news/articles/2026-10-09/openai-expects-70-billion-in-annualized-revenue-by-end-of-2026" target="_blank" rel="noopener">OpenAI Expects $70 Billion Annualized Revenue</a>（2026-10）</li>
      <li>Reuters, <a href="https://www.reuters.com/technology/anthropic-revenue-run-rate-tops-65-billion-source-says-2026-08-17/" target="_blank" rel="noopener">Anthropic run rate tops $65B</a>（2026-08）</li>
      <li>新华网, <a href="https://www.news.cn/tech/20260608/05f785a31b4241d2a3abd6454c0fa9b0/c.html" target="_blank" rel="noopener">数据中心用电量 1960 亿 kWh</a>（2026-06）</li>
      <li>IEEE ComSoc, <a href="https://techblog.comsoc.org/2026/02/16/china-vs-u-s-generating-power-for-ai-data-centers-as-demand-soars/" target="_blank" rel="noopener">China vs US: generating power for AI data centers</a></li>
    </ol>
    <footer>本页为个人研究性质的估算，不构成投资建议。所有“月度”点除标注锚点外均为模型插值/外推；引用请以原始来源为准。<br>
    生成脚本：<code>us-china-ai-compute/build.py</code> · 页面数据快照：2026-10-21</footer>
  </div>
</div>

<script>
const D = __DATA__;
const C = {us:'#2f6fed', cn:'#d94a4a', amber:'#e0a300', ink:'#1c2430', muted:'#6b7686', line:'#e6e9ee'};
const FONT = '-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif';
const fmtM = v => (v/1e6).toFixed(v<1e7?1:0) + 'M';
const fmtT = v => (v/1e12).toFixed(0);
const charts = [];
function mk(id, opt){
  const el = document.getElementById(id);
  const ch = echarts.init(el, null, {renderer:'canvas'});
  ch.setOption(opt);
  charts.push(ch);
  return ch;
}
const baseTip = {
  backgroundColor:'rgba(255,255,255,.97)', borderColor:'#e6e9ee', borderWidth:1,
  textStyle:{color:'#1c2430', fontSize:12, fontFamily:FONT},
  extraCssText:'box-shadow:0 6px 24px rgba(20,30,50,.10);border-radius:10px;padding:9px 11px;'
};
const axisCommon = {
  axisLine:{lineStyle:{color:'#dfe4ec'}}, axisTick:{show:false},
  axisLabel:{color:C.muted, fontSize:11, fontFamily:FONT},
  splitLine:{lineStyle:{color:'#eef1f5'}}
};
const legendCommon = {type:'scroll', top:0, right:0, itemWidth:14, itemHeight:8, textStyle:{color:'#41506a', fontSize:11.5}};

/* ---------- 1. 算力存量 ---------- */
mk('c1', {
  animationDuration: 700,
  grid:{left:58, right:52, top:52, bottom:32},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'cross', label:{backgroundColor:'#41506a'}},
    formatter: p => {
      let s = '<b>'+p[0].axisValue+'</b>';
      p.forEach(x => {
        if (x.seriesName === '差距倍数') s += '<br>'+x.marker+' 差距：<b>'+x.value+'×</b>';
        else s += '<br>'+x.marker+' '+x.seriesName+'：<b>'+fmtM(x.value)+'</b> H100e';
      });
      return s;
    }}, baseTip),
  legend:Object.assign({data:['美国','中国（官方）','中国（含走私中位）','差距倍数'], left:0, right:'auto'}, legendCommon),
  xAxis:Object.assign({type:'category', data:D.months, boundaryGap:false,
    axisLabel:{color:C.muted, fontSize:10.5, interval:'auto', hideOverlap:true, fontFamily:FONT}}, {axisLine:axisCommon.axisLine, axisTick:axisCommon.axisTick}),
  yAxis:[
    {type:'log', min:1e5, max:5e7, name:'H100e（对数）', nameTextStyle:{color:C.muted, fontSize:10.5},
      axisLabel:{color:C.muted, fontSize:10.5, formatter:v=> (v>=1e6? (v/1e6)+'M' : (v/1e3)+'k')}, splitLine:{lineStyle:{color:'#eef1f5'}}},
    {type:'value', min:0, max:20, name:'倍数', nameTextStyle:{color:C.amber, fontSize:10.5, padding:[0,0,0,-8]},
      axisLabel:{color:C.amber, fontSize:10.5, formatter:'{value}×'}, splitLine:{show:false}}
  ],
  series:[
    {name:'美国', type:'line', data:D.compute.us, symbol:'none', smooth:.15,
      lineStyle:{width:2.6, color:C.us}, itemStyle:{color:C.us},
      areaStyle:{color:'rgba(47,111,237,.07)'},
      markArea:{silent:true, itemStyle:{color:'rgba(47,111,237,.045)'},
        label:{show:true, position:'insideBottom', color:'#8a93a3', fontSize:10, formatter:'2026 外推'},
        data:[[{xAxis:'2026-01'},{xAxis:'2026-10'}]]}},
    {name:'中国（官方）', type:'line', data:D.compute.cn, symbol:'none', smooth:.15,
      lineStyle:{width:1.8, color:'#eaa6a6', type:'dashed'}, itemStyle:{color:'#eaa6a6'}},
    {name:'中国（含走私中位）', type:'line', data:D.compute.cnAll, symbol:'none', smooth:.15,
      lineStyle:{width:2.6, color:C.cn}, itemStyle:{color:C.cn},
      areaStyle:{color:'rgba(217,74,74,.07)'}},
    {name:'差距倍数', type:'line', yAxisIndex:1, data:D.compute.ratio, symbol:'none', smooth:.1,
      lineStyle:{width:1.6, color:C.amber, type:'dotted'}, itemStyle:{color:C.amber}}
  ]
});

/* ---------- 2. 日均 token ---------- */
const band = D.tokens.usHi.map((v,i)=> +(v-D.tokens.usLo[i]).toFixed(1));
mk('c2', {
  animationDuration: 700,
  grid:{left:58, right:26, top:46, bottom:32},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'line', lineStyle:{color:'#c9d1de'}},
    formatter: p => {
      let s = '<b>'+p[0].axisValue+'</b>';
      p.forEach(x => {
        if (x.seriesName === '美国（区间估算）' || x.seriesName === '区间下沿') return;
        s += '<br>'+x.marker+' '+x.seriesName+'：<b>'+x.value.toFixed(1)+'</b> 万亿/天';
      });
      return s;
    }}, baseTip),
  legend:Object.assign({data:['中国（官方口径）','中国官方披露点','美国（区间估算）']}, legendCommon),
  xAxis:Object.assign({type:'category', data:D.months, boundaryGap:false,
    axisLabel:{color:C.muted, fontSize:10.5, interval:'auto', hideOverlap:true, fontFamily:FONT}}, {axisLine:axisCommon.axisLine, axisTick:axisCommon.axisTick}),
  yAxis:{type:'value', name:'万亿 token / 天', nameTextStyle:{color:C.muted, fontSize:10.5},
    axisLabel:{color:C.muted, fontSize:10.5, formatter:v=> String(Math.round(v))}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  series:[
    {name:'区间下沿', type:'line', data:D.tokens.usLo, stack:'usband', symbol:'none', lineStyle:{opacity:0}, areaStyle:{opacity:0}, silent:true, tooltip:{show:false}},
    {name:'美国区间', type:'line', data:band, stack:'usband', symbol:'none', lineStyle:{opacity:0}, areaStyle:{color:'rgba(47,111,237,.13)'}, silent:true, tooltip:{show:false}},
    {name:'美国（区间估算）', type:'line', data:D.tokens.us, symbol:'none', smooth:.15,
      lineStyle:{width:2.2, color:C.us, type:'dashed'}, itemStyle:{color:C.us}},
    {name:'中国（官方口径）', type:'line', data:D.tokens.cn, symbol:'none', smooth:.15,
      lineStyle:{width:2.8, color:C.cn}, itemStyle:{color:C.cn},
      areaStyle:{color:'rgba(217,74,74,.08)'},
      markPoint:{silent:true, symbol:'circle', symbolSize:7, itemStyle:{color:C.cn, borderColor:'#fff', borderWidth:1.5},
        label:{show:true, position:'top', distance:8, color:C.cn, fontSize:10.5, formatter:'中国反超'},
        data:[{coord:[D.tokens.crossIdx, D.tokens.cn[D.tokens.crossIdx]]}]}},
    {name:'中国官方披露点', type:'scatter', data:D.tokens.cnPts, symbolSize:8,
      itemStyle:{color:C.cn, borderColor:'#fff', borderWidth:1.5}, z:5,
      tooltip:{formatter: p => '官方披露<br><b>'+p.value[1]+'</b> 万亿/天'}}
  ]
});

/* ---------- 3. 三组 100% 堆叠 ---------- */
mk('c3', {
  animationDuration: 600,
  grid:{left:96, right:40, top:30, bottom:26},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'},
    formatter: p => '<b>'+p[0].axisValue+'</b>'+p.map(x=>'<br>'+x.marker+' '+x.seriesName+'：<b>'+x.value.toFixed(1)+'%</b>').join('')}, baseTip),
  legend:Object.assign({data:['美国','中国']}, legendCommon),
  xAxis:{type:'value', max:100, axisLabel:{color:C.muted, fontSize:10.5, formatter:'{value}%'}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  yAxis:{type:'category', data:['日均 Token','2026 资本开支','AI 算力存量'],
    axisLabel:{color:'#41506a', fontSize:12, fontFamily:FONT}, axisLine:{show:false}, axisTick:{show:false}},
  series:[
    {name:'美国', type:'bar', stack:'t', barWidth:24, data:[D.bars.token[0], D.bars.capex[0], D.bars.compute[0]],
      itemStyle:{color:C.us, borderRadius:[6,0,0,6]},
      label:{show:true, position:'inside', color:'#fff', fontSize:11, fontWeight:600, formatter:p=> p.value.toFixed(0)+'%'}},
    {name:'中国', type:'bar', stack:'t', barWidth:24, data:[D.bars.token[1], D.bars.capex[1], D.bars.compute[1]],
      itemStyle:{color:C.cn, borderRadius:[0,6,6,0]},
      label:{show:true, position:'inside', color:'#fff', fontSize:11, fontWeight:600, formatter:p=> p.value.toFixed(0)+'%'}}
  ]
});

/* ---------- 4. 全球 token 份额 ---------- */
mk('c4', {
  animationDuration: 700,
  grid:{left:44, right:22, top:38, bottom:30},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'line'},
    formatter: p => '<b>'+p[0].axisValue+'</b>'+p.map(x=>'<br>'+x.marker+' '+x.seriesName+'：<b>'+x.value.toFixed(1)+'%</b>').join('')}, baseTip),
  legend:Object.assign({data:['中国','美国','其他地区']}, legendCommon),
  xAxis:Object.assign({type:'category', data:D.months, boundaryGap:false,
    axisLabel:{color:C.muted, fontSize:10.5, interval:'auto', hideOverlap:true, fontFamily:FONT}}, {axisLine:axisCommon.axisLine, axisTick:axisCommon.axisTick}),
  yAxis:{type:'value', max:100, axisLabel:{color:C.muted, fontSize:10.5, formatter:'{value}%'}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  series:[
    {name:'中国', type:'line', stack:'s', data:D.shares.cn, symbol:'none', smooth:.2,
      lineStyle:{width:0}, areaStyle:{color:'rgba(217,74,74,.55)'}, itemStyle:{color:C.cn}},
    {name:'美国', type:'line', stack:'s', data:D.shares.us, symbol:'none', smooth:.2,
      lineStyle:{width:0}, areaStyle:{color:'rgba(47,111,237,.45)'}, itemStyle:{color:C.us}},
    {name:'其他地区', type:'line', stack:'s', data:D.shares.rest, symbol:'none', smooth:.2,
      lineStyle:{width:0}, areaStyle:{color:'rgba(150,160,175,.28)'}, itemStyle:{color:'#96a0af'}}
  ]
});

/* ---------- 5. capex ---------- */
mk('c5', {
  animationDuration: 700,
  grid:{left:52, right:24, top:44, bottom:32},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'},
    formatter: p => '<b>'+p[0].axisValue+'</b>'+p.map(x=>'<br>'+x.marker+' '+x.seriesName+'：<b>$'+x.value.toFixed(1)+'B/月</b>').join('')}, baseTip),
  legend:Object.assign({data:['美国','中国']}, legendCommon),
  xAxis:Object.assign({type:'category', data:D.months,
    axisLabel:{color:C.muted, fontSize:10.5, interval:'auto', hideOverlap:true, fontFamily:FONT}}, {axisLine:axisCommon.axisLine, axisTick:{show:false}}),
  yAxis:{type:'value', name:'US$bn / 月（年化）', nameTextStyle:{color:C.muted, fontSize:10.5},
    axisLabel:{color:C.muted, fontSize:10.5}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  series:[
    {name:'美国', type:'bar', data:D.capex.us, barWidth:'46%', itemStyle:{color:'rgba(47,111,237,.85)', borderRadius:[3,3,0,0]}},
    {name:'中国', type:'bar', data:D.capex.cn, barWidth:'46%', itemStyle:{color:'rgba(217,74,74,.85)', borderRadius:[3,3,0,0]}}
  ]
});

/* ---------- 6. GW ---------- */
mk('c6', {
  animationDuration: 700,
  grid:{left:44, right:20, top:44, bottom:30},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'line'},
    formatter: p => '<b>'+p[0].axisValue+'</b>'+p.map(x=>'<br>'+x.marker+' '+x.seriesName+'：<b>'+x.value.toFixed(0)+' GW</b>').join('')}, baseTip),
  legend:Object.assign({data:['美国','中国']}, legendCommon),
  xAxis:Object.assign({type:'category', data:D.months, boundaryGap:false,
    axisLabel:{color:C.muted, fontSize:10, interval:'auto', hideOverlap:true, fontFamily:FONT}}, {axisLine:axisCommon.axisLine, axisTick:axisCommon.axisTick}),
  yAxis:{type:'value', max:60, name:'GW', nameTextStyle:{color:C.muted, fontSize:10.5},
    axisLabel:{color:C.muted, fontSize:10.5}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  series:[
    {name:'美国', type:'line', data:D.gw.us, symbol:'none', smooth:.2,
      lineStyle:{width:2.6, color:C.us}, areaStyle:{color:'rgba(47,111,237,.10)'}, itemStyle:{color:C.us}},
    {name:'中国', type:'line', data:D.gw.cn, symbol:'none', smooth:.2,
      lineStyle:{width:2.6, color:C.cn}, areaStyle:{color:'rgba(217,74,74,.10)'}, itemStyle:{color:C.cn}}
  ]
});

/* ---------- 7. AI 收入 ---------- */
mk('c7', {
  animationDuration: 600,
  grid:{left:96, right:56, top:14, bottom:26},
  tooltip:Object.assign({trigger:'axis', axisPointer:{type:'shadow'},
    formatter: p => '<b>'+p[0].axisValue+'</b><br>年化收入：<b>$'+p[0].value+'B</b>'}, baseTip),
  xAxis:{type:'value', max:80, axisLabel:{color:C.muted, fontSize:10.5, formatter:'${value}B'}, splitLine:{lineStyle:{color:'#eef1f5'}}},
  yAxis:{type:'category', data:['中国六家合计','Anthropic','OpenAI'],
    axisLabel:{color:'#41506a', fontSize:11.5, fontFamily:FONT}, axisLine:{show:false}, axisTick:{show:false}},
  series:[{
    type:'bar', barWidth:18,
    data:[
      {value:13.5, itemStyle:{color:C.cn}},
      {value:65, itemStyle:{color:'#7aa2f7'}},
      {value:70, itemStyle:{color:C.us}}
    ],
    itemStyle:{borderRadius:[0,5,5,0]},
    label:{show:true, position:'right', color:'#41506a', fontSize:11, formatter:'${c}B'}
  }]
});

window.addEventListener('resize', () => charts.forEach(c => c.resize()));
</script>
</body>
</html>
"""

html = (HTML.replace("__KPIS__", KPIS)
            .replace("__TABLE__", TABLE_ROWS)
            .replace("__DATA__", json.dumps(DATA, ensure_ascii=False)))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"wrote {OUT} ({len(html)/1024:.0f} KB)")
print(f"snapshot 2026-10: US compute {snap['us_compute']/1e6:.1f}M, CN {snap['cn_compute']/1e6:.2f}M, "
      f"ratio {snap['ratio']:.1f}x; CN token {snap['cn_token']:.0f}T, US {snap['us_token']:.0f}T")
print("share bars:", {k: [round(x,1) for x in v] for k, v in share_bars.items()})
