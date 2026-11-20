# -*- coding: utf-8 -*-
"""生成「恒生科技 20% 仓位：该割肉，还是该减仓？」报告（单文件 HTML）。

数据全部来自仓库内已缓存的 CSV：
  ../hs300-strategy-lab/data/{hstech_price,hstech_pe,hsi_price,hsi_pe,
                              hs300_price,hs300_pe,ndx_price,sp500_pe,
                              ndx_cape,ust10y}.csv

运行：
  hs300-strategy-lab/.venv/bin/python hstech-2026-11-20/build.py
  cd .. && python3 build_site.py     # 注册门户 + 注入导航
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, "hs300-strategy-lab", "data")
OUT = os.path.join(HERE, "index.html")


def load_close(path):
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    return df.set_index("date")["close"].dropna()


def pct_le(series, v):
    series = pd.Series(series).dropna()
    return float((series <= v).mean() * 100)


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def sg(x, d=1):
    return f"{x:+.{d}f}%"


# ---------------------------------------------------------------- 恒生科技
px = load_close(os.path.join(D, "hstech_price.csv"))
px_last, px_date = float(px.iloc[-1]), px.index[-1]
px_1030 = float(px.loc["2026-10-30"])

pe = pd.read_csv(os.path.join(D, "hstech_pe.csv"), parse_dates=["date"]).sort_values("date")
pe = pe[pe["pe"] > 0].copy()
pe["earn"] = pe["close"] / pe["pe"]

pe_last = 25.43                       # 2026-10-31 官方月度 PE
E_last = px_1030 / pe_last            # 用 10-30 收盘反推的隐含盈利
pe_eff = px_last / E_last             # 把 PE 折算到 11-16 收盘
E_prev = 5908.08 / 25.79              # 2025-10-31 隐含盈利

high_2026 = float(px[px.index >= "2026-01-01"].max())
high_2026_date = px[px.index >= "2026-01-01"].idxmax()
peak_2021 = float(px.max())
peak_2021_date = px.idxmax()
dd_2026 = px_last / high_2026 - 1
dd_all = px_last / peak_2021 - 1

ma20 = float(px.tail(20).mean())
ma60 = float(px.tail(60).mean())
ma120 = float(px.tail(120).mean())
ma200 = float(px.tail(200).mean())
rsi14 = float(rsi(px).iloc[-1])
ret_1y = float(px.iloc[-1] / px[px.index >= px.index[-1] - pd.Timedelta(days=365)].iloc[0] - 1)
vol_1y = float(px.pct_change().tail(252).std() * np.sqrt(252))
vol_3y = float(px.pct_change().tail(756).std() * np.sqrt(252))

pe_pos = pe.copy()
pe_clean = pe[(pe["pe"] > 15) & (pe["pe"] < 60)]
pe_2023 = pe[pe["date"] >= "2023-01-01"]
pe_2023_clean = pe[(pe["date"] >= "2023-01-01") & (pe["pe"] > 15) & (pe["pe"] < 60)]
pct_all = pct_le(pe_pos["pe"], pe_eff)
pct_clean = pct_le(pe_clean["pe"], pe_eff)
pct_2023 = pct_le(pe_2023["pe"], pe_eff)
pct_2023_clean = pct_le(pe_2023_clean["pe"], pe_eff)
dv_last = 1.23
dv_pct = pct_le(pe["dv"], dv_last)
ey = 1 / pe_eff * 100

# ---------------------------------------------------------------- 对照
hsi = load_close(os.path.join(D, "hsi_price.csv"))
hsi_last = float(hsi.iloc[-1])
hsi_pe = pd.read_csv(os.path.join(D, "hsi_pe.csv"), parse_dates=["date"]).sort_values("date")
hsi_pe = hsi_pe[hsi_pe["pe"] > 0]
hsi_pe_last = float(hsi_pe["pe"].iloc[-1])
hsi_pe_pct = pct_le(hsi_pe["pe"], hsi_pe_last)
hsi_dv = float(hsi_pe["dv"].iloc[-1])
hsi_dd = hsi_last / hsi.max() - 1

hs300 = load_close(os.path.join(D, "hs300_price.csv"))
hs300_pe = pd.read_csv(os.path.join(D, "hs300_pe.csv"), parse_dates=["date"]).sort_values("date")
hs300_pe_last = float(hs300_pe["pe"].iloc[-1])
hs300_pe5 = hs300_pe[hs300_pe["date"] >= hs300_pe["date"].iloc[-1] - pd.Timedelta(days=365 * 5)]
hs300_pe_pct5 = pct_le(hs300_pe5["pe"], hs300_pe_last)

ndx = load_close(os.path.join(D, "ndx_price.csv"))
ndx_ret_1y = float(ndx.iloc[-1] / ndx[ndx.index >= ndx.index[-1] - pd.Timedelta(days=365)].iloc[0] - 1)

sp_pe = pd.read_csv(os.path.join(D, "sp500_pe.csv"), parse_dates=["date"]).sort_values("date")
sp_pe = sp_pe[sp_pe["value"] > 0]
sp_pe_last = float(sp_pe["value"].iloc[-1])
sp_pe_pct = pct_le(sp_pe["value"], sp_pe_last)
cape = pd.read_csv(os.path.join(D, "ndx_cape.csv"), parse_dates=["date"]).sort_values("date")
cape = cape[cape["value"] > 0]
cape_last = float(cape["value"].iloc[-1])
cape_pct = pct_le(cape["value"], cape_last)

ust = pd.read_csv(os.path.join(D, "ust10y.csv")).sort_values("date")
ust["date"] = pd.to_datetime(ust["date"])
ust_last = float(ust["close"].iloc[-1])
ust_jan = float(ust[ust["date"] <= "2026-01-01"]["close"].iloc[-1])
china10y = 1.59  # macro-2026-10：2026-11-13 中国 10Y 国债

corr_hsi = float(pd.DataFrame({"h": px.pct_change(), "i": hsi.pct_change()}).dropna().corr().iloc[0, 1])

# ---------------------------------------------------------------- 图：PE / 盈利
pe_chart = pe[pe["date"] >= "2024-03-31"].copy()
pe_chart = pd.concat([
    pe_chart[["date", "pe"]].rename(columns={"pe": "v"}),
    pd.DataFrame([{"date": px_date, "v": pe_eff}]),
], ignore_index=True).sort_values("date")

earn_chart = pe[pe["date"] >= "2025-09-30"].copy()
earn_chart = earn_chart[["date", "earn"]].rename(columns={"earn": "v"}).dropna(subset=["v"])
earn_chart = pd.concat([
    earn_chart,
    pd.DataFrame([{"date": px_date, "v": E_last}]),
], ignore_index=True).sort_values("date")

# ---------------------------------------------------------------- 图：归一化
series_map = {"恒生科技": px, "恒生指数": hsi, "沪深300": hs300, "纳指100": ndx}
frame = pd.DataFrame(series_map)
frame = frame[(frame.index >= "2026-01-02") & (frame.index <= px_date)].sort_index().ffill().dropna()
base = frame.iloc[0]
norm = (frame / base * 100).round(2)

# ---------------------------------------------------------------- 情景
E = E_last
scen = [
    ("深熊", "盈利再降 15%，PE 20x", 0.85, 20, 0.30, "战争升级 + 芯片约束加剧 + 回购停"),
    ("偏熊", "盈利再降 10%，PE 22x", 0.90, 22, 0.25, "盈利继续下修，估值小幅收缩"),
    ("基准", "盈利持平，PE 25.7x", 1.00, 25.7, 0.30, "Q4 企稳，横盘磨底"),
    ("修复", "盈利 +8%，PE 30x", 1.08, 30, 0.12, "外卖/EV 战争降温 + AI 变现"),
    ("反转", "盈利 +15%，PE 35x", 1.15, 35, 0.03, "政策/技术突破，风险偏好回来"),
]
scen_rows = []
ev = 0.0
for name, assumption, e_mult, target_pe, prob, note in scen:
    target = E * e_mult * target_pe
    ret = target / px_last - 1
    ev += prob * ret
    scen_rows.append(dict(name=name, assumption=assumption, target=target, ret=ret, prob=prob, note=note))

scen_cycle = [(0.15, 0.85, 20), (0.20, 0.90, 22), (0.35, 1.00, 25.7), (0.25, 1.08, 30), (0.05, 1.15, 35)]
ev_cycle = sum(p * (E * m * pe_ / px_last - 1) for p, m, pe_ in scen_cycle)

scen_html = "".join(
    '<tr><td><b>{}</b></td><td class="wrapcell">{}</td><td>{:,.0f}</td><td class="{}"><b>{}</b></td><td>{:.0f}%</td><td class="wrapcell">{}</td></tr>'.format(
        r["name"], r["assumption"], r["target"], "down" if r["ret"] < 0 else "up",
        sg(r["ret"] * 100), r["prob"] * 100, r["note"]
    )
    for r in scen_rows
)

risk_moves = [-0.30, -0.40, -0.60]

chart_data = {
    "price": {
        "dates": [d.strftime("%Y-%m-%d") for d in px.index],
        "values": [round(float(v), 1) for v in px.values],
        "peak2021": {"date": peak_2021_date.strftime("%Y-%m-%d"), "value": round(peak_2021, 1)},
        "high2026": {"date": high_2026_date.strftime("%Y-%m-%d"), "value": round(high_2026, 1)},
        "current": {"date": px_date.strftime("%Y-%m-%d"), "value": round(px_last, 1)},
    },
    "pe": {
        "dates": [d.strftime("%Y-%m-%d") for d in pe_chart["date"]],
        "values": [round(float(v), 2) for v in pe_chart["v"]],
        "current": round(pe_eff, 2),
    },
    "earn": {
        "dates": [d.strftime("%Y-%m-%d") for d in earn_chart["date"]],
        "values": [round(float(v), 1) for v in earn_chart["v"]],
    },
    "norm": {
        "dates": [d.strftime("%Y-%m-%d") for d in norm.index],
        "series": {c: norm[c].tolist() for c in norm.columns},
    },
    "pct": {
        "cats": ["恒生科技 PE", "恒生指数 PE", "沪深300 PE", "标普500 PE", "美股 CAPE"],
        "values": [round(pct_2023, 1), round(hsi_pe_pct, 1), round(hs300_pe_pct5, 1), round(sp_pe_pct, 1), round(cape_pct, 1)],
    },
    "scen": {
        "names": [s[0] for s in scen],
        "rets": [round(r["ret"] * 100, 1) for r in scen_rows],
        "probs": [round(r["prob"] * 100, 0) for r in scen_rows],
    },
    "risk": {
        "moves": [round(m * 100, 0) for m in risk_moves],
        "series": {
            "20% 仓位": [round(0.20 * m * 100, 1) for m in risk_moves],
            "12% 仓位": [round(0.12 * m * 100, 1) for m in risk_moves],
            "8% 仓位": [round(0.08 * m * 100, 1) for m in risk_moves],
        },
    },
}

CSS = """
:root{
  --bg:#f7f7f5; --card:#fff; --ink:#1c1c1e; --sub:#6b6b70; --line:#e6e4df;
  --up:#d9363e; --down:#1a9c5b; --accent:#1f4fd8; --warn:#b8791a; --purple:#7a4fb5;
  --mono:"SFMono-Regular",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1080px;margin:0 auto;padding:48px 24px 80px}
header.top{border-bottom:2px solid var(--ink);padding-bottom:22px;margin-bottom:32px}
.kicker{font-size:13px;letter-spacing:.18em;color:var(--sub);text-transform:uppercase;margin-bottom:10px}
h1{font-size:34px;line-height:1.3;margin:0 0 12px;letter-spacing:-.01em}
.lede{font-size:17px;color:var(--sub);margin:0;max-width:860px}
.meta{font-size:13px;color:var(--sub);margin-top:14px;font-family:var(--mono)}
h2{font-size:23px;margin:56px 0 6px;letter-spacing:-.01em;display:flex;align-items:baseline;gap:12px}
h2 .no{font-family:var(--mono);font-size:14px;color:var(--accent);letter-spacing:.06em}
h2 + .sub{color:var(--sub);font-size:15px;margin:0 0 20px}
h3{font-size:17px;margin:26px 0 8px}
p{margin:10px 0}
.tiles{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.tile .name{font-size:13px;color:var(--sub)}
.tile .px{font-family:var(--mono);font-size:26px;font-weight:600;line-height:1.25}
.tile .chg{font-family:var(--mono);font-size:14px}
.tile .note{font-size:12px;color:var(--sub);margin-top:6px}
.up{color:var(--up)} .down{color:var(--down)}
.note{font-size:13px;color:var(--sub);margin-top:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:18px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid2 .card{margin:0}
.verdict{background:linear-gradient(180deg,#fff,#fbfaf6);border:1px solid var(--line);
  border-left:5px solid var(--accent);border-radius:12px;padding:18px 22px;margin:22px 0}
.verdict p{margin:9px 0}
.verdict b{color:var(--ink)}
.tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--accent);
  background:#eef3ff;border-radius:999px;padding:2px 10px;margin-bottom:8px}
.chart{width:100%;height:390px}
.chart.mid{height:320px}
.chart.small{height:280px}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:12px}
th,td{text-align:right;padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap;vertical-align:top}
th:first-child,td:first-child{text-align:left;white-space:normal}
th{font-size:12.5px;color:var(--sub);font-weight:600;background:#faf9f6}
td.wrapcell{white-space:normal;line-height:1.6}
.badge{display:inline-block;font-size:12px;padding:1px 9px;border-radius:999px;font-weight:600;white-space:nowrap}
.badge.hot{background:#fdecec;color:#c0392b}
.badge.mid{background:#fbf3e2;color:#b7791f}
.badge.cold{background:#e8f5ee;color:#1f7a5c}
.badge.gray{background:#f0f0f0;color:#666}
ul{margin:8px 0 8px 22px;padding:0}
li{margin:6px 0}
.quote{border-left:3px solid var(--warn);background:#fdfaf3;padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0}
.callout{background:#f3f6ff;border:1px solid #dce5ff;border-radius:12px;padding:14px 18px;margin:16px 0}
.callout b{color:var(--accent)}
.big{font-family:var(--mono);font-size:22px;font-weight:700}
.rule{display:grid;grid-template-columns:96px 1fr;gap:14px;padding:12px 0;border-bottom:1px dashed var(--line)}
.rule:last-child{border-bottom:none}
.rule .k{font-family:var(--mono);font-size:13px;color:var(--accent);font-weight:600}
footer{margin-top:48px;border-top:1px solid var(--line);padding-top:16px;font-size:13px;color:var(--sub)}
@media(max-width:760px){
  .tiles{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
  h1{font-size:27px}
  .chart{height:330px}
  .chart.mid{height:300px}
  .wrap{padding:32px 16px 60px}
  table{font-size:12.5px}
  th,td{padding:7px 6px}
}
"""

NORM_CARD = f"""
<div class="card">
  <div id="cNorm" class="chart mid"></div>
  <div class="note">2026 年初 = 100 归一化。恒生科技是这轮里跌得最深的主要指数之一；恒指、沪深300 也在跌，但幅度小得多。这不是“全球科技同步熊市”，而是“中国资产 + 高 beta 成长”的双重折价。</div>
</div>
"""

PCT_CARD = f"""
<div class="card">
  <div id="cPct" class="chart mid"></div>
  <div class="note">各自历史分位（越高越贵）：恒生科技 PE 取 2023 年以来（{pct_2023:.0f}%），恒指/沪深300/标普取各自历史或近 5 年口径。恒科在自己的历史里不算贵，但绝对 PE 与标普 500 接近；恒指 {hsi_pe_last:.1f}x 却处在 {hsi_pe_pct:.0f}% 分位，也是“盈利下滑导致 PE 分位失真”的例子。</div>
</div>
"""

BODY = f"""
<header class="top">
  <div class="kicker">HANG SENG TECH · 2026-11-20 · POSITION REVIEW</div>
  <h1>恒生科技 20% 仓位：<br>该割肉，还是该减仓？</h1>
  <p class="lede">你说“知道的越多，越觉得哪怕跌了这么多还是没价值”。这句话里其实混了三个问题：基本面是不是永久坏了、当前价格有没有反映、20% 的仓位该不该由你承担。把三件事拆开，答案会比“割 / 不割”清楚得多。</p>
  <div class="meta">数据截止 {px_date.strftime('%Y-%m-%d')} 收盘｜恒生科技 {px_last:,.2f}｜PE {pe_eff:.1f}x｜不构成投资建议</div>
</header>

<div class="tiles">
  <div class="tile">
    <div class="name">恒生科技</div>
    <div class="px">{px_last:,.0f}</div>
    <div class="chg down">距 2026 高点 {sg(dd_2026*100)}</div>
    <div class="note">距 2021 峰值 {sg(dd_all*100)}</div>
  </div>
  <div class="tile">
    <div class="name">PE-TTM</div>
    <div class="px">{pe_eff:.1f}x</div>
    <div class="chg down">分位 {pct_2023:.0f}%（2023 起）</div>
    <div class="note">全样本 {pct_all:.0f}%｜剔除失真 {pct_clean:.0f}%</div>
  </div>
  <div class="tile">
    <div class="name">隐含盈利（P÷PE 反推）</div>
    <div class="px down">{sg((E_last/E_prev-1)*100)}</div>
    <div class="chg down">过去 12 个月</div>
    <div class="note">股价 {sg((px_1030/5908.08-1)*100)}，PE 几乎没动</div>
  </div>
  <div class="tile">
    <div class="name">你的仓位</div>
    <div class="px">20%</div>
    <div class="chg">单一板块</div>
    <div class="note">再跌 40% ≈ 总仓位 -8%</div>
  </div>
</div>

<div class="verdict">
  <span class="tag">一句话结论</span>
  <p><b>你的基本面判断，大部分成立，而且数据比你感觉的更差。</b>过去 12 个月，恒生科技股价 {sg((px_1030/5908.08-1)*100)}，隐含盈利 {sg((E_last/E_prev-1)*100)}，PE 从 25.8x 到 25.4x（最新 25.7x）——几乎没动。这不是“跌出便宜”，是“盈利和股价一起塌”。</p>
  <p><b>但“割肉”是错的问题。</b>20% 压在一个年化波动 {vol_3y*100:.0f}%、和恒指相关 {corr_hsi:.2f} 的单一板块上，本身就已经超出大多数人的风险预算。先把它降到 <b>8%–10%</b>，这是仓位问题，不需要预测底部。</p>
  <p><b>剩下的 8%–10%，用证据而不是价格决定。</b>Q4 盈利同比企稳、FCF 回升、回购恢复、价格站上 200 日线，才加；否则继续减。不要把“跌得多”当持有理由，也不要把“坏消息多”当清仓理由——<b>这些坏消息，市场也在定价</b>。</p>
</div>

<h2><span class="no">01</span>先把“该不该割”拆成三个问题</h2>
<p class="sub">“割不割”是一个二选一，但你的焦虑其实来自三个不同层级的问题；它们需要不同的解法。</p>

<div class="card">
  <table>
    <thead><tr><th>问题</th><th>你的答案</th><th>数据怎么说</th><th>该怎么处理</th></tr></thead>
    <tbody>
      <tr>
        <td><b>① 基本面是否永久受损？</b></td>
        <td>是，“看不到反转”</td>
        <td class="wrapcell">隐含盈利 12 个月 {sg((E_last/E_prev-1)*100)}；外卖/EV 战争在真实烧钱；芯片约束是硬的。但腾讯/网易的现金流仍在，capex 和补贴都是<b>可裁支出</b>，不是永久消失。</td>
        <td class="wrapcell">需要持续跟踪，<b>无法用一次判断解决</b>。用财报验证“周期性”还是“结构性”。</td>
      </tr>
      <tr>
        <td><b>② 当前价格是否已反映？</b></td>
        <td>“跌了这么多，还是不便宜”</td>
        <td class="wrapcell">PE {pe_eff:.1f}x，12 个月持平；不是极端便宜，也不是 2021 年的 60x。个股层面腾讯 15.3x、阿里 16.5x、网易 16.6x；指数股息率 {dv_last:.2f}% 处在历史 {dv_pct:.0f}% 分位。</td>
        <td class="wrapcell">已定价很多，但 25x 在盈利下滑期<b>不构成“白送”</b>。不要用“便宜”作为满仓理由。</td>
      </tr>
      <tr>
        <td><b>③ 20% 仓位是否合适？</b></td>
        <td>“有点慌”</td>
        <td class="wrapcell">{vol_3y*100:.0f}% 年化波动、与恒指相关 {corr_hsi:.2f}；再跌 40% 就是总仓位 -8%，再跌 60% 就是 -12%。若你还持有中概/港股互联网，实际敞口更高。</td>
        <td class="wrapcell"><b>这是唯一现在就能解决的问题</b>：先降到能睡着的大小，再谈看多看空。</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="quote"><b>关键：</b>三个问题里，只有②需要“预测”；①需要“跟踪”；③现在就能“执行”。绝大多数人在①和②之间反复纠结，却让③一直裸奔。先把③解决，你的判断力会立刻恢复一半。</div>

<h2><span class="no">02</span>数据体检：跌了多少，便宜了吗</h2>
<p class="sub">先不看观点，只看数字。恒生科技现在的状态是“跌幅很大、估值不贵、盈利在塌、趋势仍弱”。</p>

<div class="card">
  <div id="cPrice" class="chart"></div>
  <div class="note">恒生科技指数 2020-08 至 {px_date.strftime('%Y-%m-%d')}。2021-02 峰值 {peak_2021:,.0f}，2026-01 高点 {high_2026:,.0f}，现价 {px_last:,.0f}；距 2021 峰值 {sg(dd_all*100)}，距 2026 高点 {sg(dd_2026*100)}。</div>
</div>

{NORM_CARD}

<div class="grid2">
  <div class="card">
    <h3 style="margin-top:0">四个读数，别混在一起</h3>
    <table>
      <tbody>
        <tr><td>PE-TTM</td><td><b>{pe_eff:.1f}x</b></td><td>12 个月前 25.8x</td></tr>
        <tr><td>PE 分位（2023 起）</td><td><b>{pct_2023:.0f}%</b></td><td>全样本 {pct_all:.0f}%</td></tr>
        <tr><td>股息率</td><td><b>{dv_last:.2f}%</b></td><td>历史 {dv_pct:.0f}% 分位</td></tr>
        <tr><td>隐含盈利同比</td><td class="down"><b>{sg((E_last/E_prev-1)*100)}</b></td><td>仍在负区间</td></tr>
        <tr><td>年化波动（1 年 / 3 年）</td><td><b>{vol_1y*100:.0f}% / {vol_3y*100:.0f}%</b></td><td>高波动</td></tr>
        <tr><td>与恒指日收益相关</td><td><b>{corr_hsi:.2f}</b></td><td>分散效果有限</td></tr>
      </tbody>
    </table>
    <div class="note">PE 分位对口径极敏感：全样本（2021-22 负 PE 已剔除）{pct_all:.0f}%、剔除 15x 以下/60x 以上失真值 {pct_clean:.0f}%、2023 年起 {pct_2023:.0f}%、2023 年起再剔除失真 {pct_2023_clean:.0f}%。无论哪个口径，都<b>不是极端便宜</b>。</div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">趋势：仍在 200 日线下方</h3>
    <table>
      <tbody>
        <tr><td>MA20 / MA60</td><td><b>{ma20:,.0f} / {ma60:,.0f}</b></td><td>{sg((px_last/ma20-1)*100)} / {sg((px_last/ma60-1)*100)}</td></tr>
        <tr><td>MA120 / MA200</td><td><b>{ma120:,.0f} / {ma200:,.0f}</b></td><td>{sg((px_last/ma120-1)*100)} / {sg((px_last/ma200-1)*100)}</td></tr>
        <tr><td>RSI14</td><td><b>{rsi14:.1f}</b></td><td>未到极端超卖</td></tr>
        <tr><td>近 1 年</td><td class="down"><b>{sg(ret_1y*100)}</b></td><td>相对纳指 {(ret_1y - ndx_ret_1y)*100:.0f}pct</td></tr>
      </tbody>
    </table>
    <div class="note">价格在 MA20/60/120/200 全部下方，属于“下跌趋势中的反弹”，不是趋势反转。RSI {rsi14:.0f} 说明还没到“人人恐慌”的极端读数——这本身也是“别急着一次性清仓”的理由之一。</div>
  </div>
</div>

<div class="callout">
  <b>最该盯住的一组数：</b>过去 12 个月，股价 {sg((px_1030/5908.08-1)*100)}、隐含盈利 {sg((E_last/E_prev-1)*100)}、PE {sg((pe_last/25.79-1)*100)}。三个数放在一起，说明<b>下跌没有让你买到更便宜的估值</b>——你买到的是“更低的股价 + 更低的盈利”。这正是你直觉里“跌了也没价值”的数据基础。
</div>

<h2><span class="no">03</span>你说的八条，逐条对账</h2>
<p class="sub">把“感觉”换成“可验证的陈述”。哪几条成立、哪几条被市场过度交易、哪几条其实是可逆的，分开看。</p>

<div class="card">
  <table>
    <thead><tr><th style="width:19%">你的判断</th><th>数据/事实怎么说</th><th style="width:11%">判定</th></tr></thead>
    <tbody>
      <tr>
        <td><b>阿里主业开始衰退</b></td>
        <td class="wrapcell">电商成熟、份额被拼多多/抖音分走是真的；但阿里 FCF 转负（约 -766 亿）主要来自<b>闪购补贴 + AI capex</b>，是“主动失血”而不是“主业消失”。核心电商 EBITA 正常化后仍有约 1,700 亿；市场给 16.5x，已经在定价低增长。</td>
        <td><span class="badge mid">半对</span><br><span class="note">可逆性被低估</span></td>
      </tr>
      <tr>
        <td><b>腾讯疯狂买卡投 AI，看不到产出</b></td>
        <td class="wrapcell">capex 压 FCF 是真的，AI 收入还没接上也是真的；但腾讯的核心游戏/广告仍是现金牛，PE 15.3x，市场<b>并没有给 AI 溢价</b>。capex 是可选支出，ROI 不及预期可以砍——这和“造车/建厂”那种刚性资本开支不同。</td>
        <td><span class="badge mid">对一半</span><br><span class="note">有现金流托底</span></td>
      </tr>
      <tr>
        <td><b>快手拉完了</b></td>
        <td class="wrapcell">短视频份额向抖音集中，快手是结构性输家，这条基本成立。但快手在恒科里不是主导权重，把它当成“整个指数完蛋”的理由，权重上不成立。</td>
        <td><span class="badge cold">对</span><br><span class="note">但影响被高估</span></td>
      </tr>
      <tr>
        <td><b>网易游戏大跌，份额被短视频挤占</b></td>
        <td class="wrapcell">网易 52 周约 -22%，股价弱是真的；但毛利 67%、净利率 28%、净现金约等于市值 30%、EV/EBIT 8.6x、股息 2.5%。这是“杀估值”，不是“生意崩了”。</td>
        <td><span class="badge mid">半对</span><br><span class="note">“没价值”过了</span></td>
      </tr>
      <tr>
        <td><b>美国封芯片，国产卡效率差，商业闭环更难</b></td>
        <td class="wrapcell">数据支持：中国 AI 算力存量约为美国 1/11（不含走私约 1/17）；华为 2026 年有效算力产出不足英伟达 4%；中国头部 AI 收入约为美国 1/10。单位算力成本更高、折旧更重、ROI 更薄——这是<b>最硬的结构性利空</b>。</td>
        <td><span class="badge hot">成立</span><br><span class="note">但非“完全不可能”</span></td>
      </tr>
      <tr>
        <td><b>新能源血战、外卖没停、AI 看不到收益</b></td>
        <td class="wrapcell">真利空，而且是“利润黑洞”：美团 FY25 从盈利约 358 亿转为亏损约 234 亿、FCF 约 -393 亿；阿里 FCF 约 -766 亿。这是指数盈利下滑的主因之一，不是情绪。</td>
        <td><span class="badge hot">成立</span><br><span class="note">指数 E 下滑的主因</span></td>
      </tr>
      <tr>
        <td><b>回购分红必然减少，看不到自由现金流</b></td>
        <td class="wrapcell">要分开看：腾讯/网易仍有强 FCF 和大额净现金；阿里/美团是“FCF 被战争和 capex 吃掉”，不是“没有现金流”。指数股息率 {dv_last:.2f}% 处在历史 {dv_pct:.0f}% 分位。回购是摇摆项，不是已经消失。</td>
        <td><span class="badge mid">半对</span><br><span class="note">别把投入期当永久失血</span></td>
      </tr>
      <tr>
        <td><b>现在还是美股加息周期</b></td>
        <td class="wrapcell">标签不准确：缓存数据显示联邦基金利率 3.63%（数据至 8 月），自 2026-01 未动，谈不上“加息周期”。但 10Y 从 {ust_jan:.2f}% 升到 {ust_last:.2f}%（+{(ust_last-ust_jan)*100:.0f}bp），折现率压力是真的。更准确的说法是<b>长端利率高位上行、降息预期落空</b>。</td>
        <td><span class="badge mid">方向对，标签错</span></td>
      </tr>
    </tbody>
  </table>
  <div class="note">个股数据来自 513050 中概互联报告（2026-09-24，TTM 截至 2026-06-30，stockanalysis.com 口径）与恒指成分股报告（2026-10-13）；指数与利率数据来自本仓库缓存。个股 PE/财务为当时快照，可能与最新财报有差异。</div>
</div>

<div class="grid2">
  <div class="card">
    <h3 style="margin-top:0" class="down">你说对了什么</h3>
    <ul>
      <li><b>盈利在塌，不只是杀估值。</b>隐含盈利 12 个月 {sg((E_last/E_prev-1)*100)}，这比“股价跌”严重得多。</li>
      <li><b>战争在真实烧钱。</b>外卖/即时零售 + EV 价格战合计蒸发数千亿利润，不是“情绪杀”。</li>
      <li><b>芯片是硬约束。</b>国产卡效率差 → 单位算力成本高 → AI ROI 更薄，这条是结构性的。</li>
      <li><b>20% 太重了。</b>你自己“有点慌”，就是仓位超过风险预算的最诚实信号。</li>
      <li><b>高利率压估值。</b>10Y {ust_last:.2f}%，对长期现金流资产不友好。</li>
      <li><b>地缘折价可能长期化。</b>芯片只是其中一条；如果中国资产的风险溢价中枢上移，25x 的“合理 PE”本身也会下移——这是比盈利下滑更慢、但更致命的变量。</li>
    </ul>
  </div>
  <div class="card">
    <h3 style="margin-top:0" class="up">你可能高估了什么</h3>
    <ul>
      <li><b>“所有坏消息都不可逆”。</b>capex、补贴、买卡都是管理层可裁的支出；战争会结束，虽然没人知道何时。</li>
      <li><b>“坏消息多 = 还会跌”。</b>市场也知道这些坏消息；从 5,908 跌到 3,801 就是定价过程。信息本身不是 edge，<b>“是否被过度定价”才是</b>。</li>
      <li><b>“PE 分位低 = 便宜”。</b>分母塌了，PE 会失真。25x 对“盈利下滑的指数”不便宜。</li>
      <li><b>“每家公司都很差”。</b>腾讯 15x、网易 16.6x、阿里 16.5x——指数里不全是烧钱机器。</li>
      <li><b>“必须现在做全有或全无”。</b>你可以在 20% 和 0% 之间选 8%–10%，这不是懦弱，是风险预算。</li>
    </ul>
  </div>
</div>

<h2><span class="no">04</span>为什么 25x 在盈利下滑期不便宜</h2>
<p class="sub">这是你直觉最强、也最容易被“分位低”误导的地方。把 P = PE × E 拆开看，结论会反过来。</p>

<div class="grid2">
  <div class="card">
    <div id="cPE" class="chart mid"></div>
    <div class="note">恒生科技月度 PE（2024-03 起，之前的亏损期 PE 失真已剔除）。当前 {pe_eff:.1f}x，处在 2023 年以来约 {pct_2023:.0f}% 分位——不是 2021 年的 60x，但也不是 2024 年 22–27x 的绝对底部。</div>
  </div>
  <div class="card">
    <div id="cEarn" class="chart mid"></div>
    <div class="note">隐含盈利 = 指数点位 ÷ PE（月度，反推值）。2026-03 财报季后从约 236 掉到 159，最新约 148；12 个月 {sg((E_last/E_prev-1)*100)}。这是“PE 没降”的原因。</div>
  </div>
</div>

{PCT_CARD}

<div class="card">
  <h3 style="margin-top:0">三个恒等式，把“便宜”拆穿</h3>
  <div class="rule"><div class="k">长期</div><div>2020–2026 年化：价格 <b>-7.8%</b>、盈利 <b>+0.7%</b>、PE <b>-8.5%</b>。过去六年的下跌，几乎全部来自“杀估值”；盈利本身没怎么增长，但也没崩。<span class="note">（来源：earn_price.py，2026-09）</span></div></div>
  <div class="rule"><div class="k">过去 12 个月</div><div>价格 <b>{sg((px_1030/5908.08-1)*100)}</b>、盈利 <b>{sg((E_last/E_prev-1)*100)}</b>、PE <b>{sg((pe_last/25.79-1)*100)}</b>。驱动因素从“杀估值”切换成“杀盈利”——这是性质变化，不是同一件事的延续。</div></div>
  <div class="rule"><div class="k">当下</div><div>PE {pe_eff:.1f}x → 盈利收益率 <b>{ey:.2f}%</b>。对美元资金，低于 10Y 美债 {ust_last:.2f}%（股债性价比 {ey-ust_last:+.2f}pct）；对人民币资金，高于中国 10Y {china10y:.2f}%（+{ey-china10y:.2f}pct）。<b>“便宜”是相对谁而言，必须先说清楚。</b></div></div>
  <div class="rule"><div class="k">要多少增长</div><div>若要求 10% 年化回报、股东回报（股息+回购）约 3%，在 PE 不变的前提下，需要盈利长期增长约 <b>7%</b>。如果你相信盈利会继续下滑，25x 就是“贵”，不是“便宜”。</div></div>
</div>

<div class="quote"><b>所以你的直觉是对的：</b>在“盈利永久受损”的前提下，25x 确实不便宜，“跌了这么多”不能说服你，也不应该说服你。真正的问题不是你的逻辑，而是<b>“永久”这个前提</b>——它既不能被今天的财报证明，也不能被证伪，只能用后面的数据跟踪。这就是为什么操作上要“减仓 + 留观察仓”，而不是“清仓 + 永不回头”。</div>

<h2><span class="no">05</span>20% 仓位的风险账</h2>
<p class="sub">你问“该不该割”，但真正的风险不是“卖错”，而是“仓位大到让你在底部拿不住”。</p>

<div class="grid2">
  <div class="card">
    <div id="cRisk" class="chart mid"></div>
    <div class="note">不同仓位下，恒生科技再跌 30% / 40% / 60% 对总组合的冲击。20% 仓位遇 -40% = 总仓位 -8%；-60% = -12%。这还没算你其他港股/中概仓位的同向下跌。</div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">三个容易忽略的集中度</h3>
    <ul>
      <li><b>波动集中：</b>{vol_3y*100:.0f}% 年化波动，20% 仓位单独贡献约 {0.20*vol_3y*100:.1f}% 的组合波动（未相关性调整）。</li>
      <li><b>相关性集中：</b>与恒指日收益相关 {corr_hsi:.2f}。恒科跌的时候，你的其他港股大概率也在跌。</li>
      <li><b>风格集中：</b>恒科 = 中国互联网 + EV + 少数硬件。它不是“科技宽基”，是一个高 beta 的中国成长风格篮子。</li>
    </ul>
    <div class="callout" style="margin-top:14px"><b>仓位规则（建议）：</b>单一高波动卫星板块 ≤ <b>8%–10%</b>；即使你再看好，也不超过 12%。20% 只适用于“这是你的核心 thesis 且有信息/研究优势”的情况——而你现在的问题恰恰是“越研究越没底”，这不算优势。</div>
  </div>
</div>

<h2><span class="no">06</span>情景与期望值：赔率支持“减”，不支持“赌”</h2>
<p class="sub">不预测底部，只把“如果发生什么、对应什么价格、概率多少”摆出来。概率是主观的，你可以自己改。</p>

<div class="card">
  <table>
    <thead><tr><th>情景</th><th>假设</th><th>目标点位</th><th>相对现价</th><th>主观概率</th><th>备注</th></tr></thead>
    <tbody>
      {scen_html}
    </tbody>
  </table>
  <div class="note">目标点位 = 当前隐含盈利（约 {E:,.0f} 点）× 盈利变动 × 目标 PE。概率为本文主观设定，不是市场隐含概率；你可以按自己的判断替换。加回股息/回购约 1%–3%，各情景总回报会略高。</div>
</div>

<div class="grid2">
  <div class="card">
    <div id="cScen" class="chart small"></div>
    <div class="note">五种情景的相对现价涨跌幅（括号内为主观概率）。</div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">期望值说明了什么</h3>
    <p>按上表概率，期望价格回报约 <b class="down">{sg(ev*100)}</b>；即使把“修复+反转”的概率提高到 30%（相应压缩熊市权重），期望值仍在 0 附近；要把它拉到明显为正，需要给“修复+反转”接近 <b>45%</b> 的概率。</p>
    <p>如果你真的相信自己的判断（盈利继续下修、战争不停、芯片约束加剧），那么 30% 的深熊概率并不离谱——对应的期望值就是负的。<b>负期望 + 20% 仓位 = 不应该继续满仓。</b></p>
    <p>但同一组数也说明：现价已经计入了一部分悲观（否则回撤不会是 {abs(dd_2026)*100:.0f}%，而会更接近 -60%）。所以“减”比“清”更符合赔率——你保留的是“周期性修复”的期权，卖掉的是“仓位过大”的风险。</p>
    <p><b>还有一层机会成本：</b>美国 10Y {ust_last:.2f}%，对能配置美元无风险资产的人，这是一个很高的门槛；恒科按上表情景的期望回报并不明显高于它，却承担 {vol_3y*100:.0f}% 的波动。对纯人民币账户，中国 10Y 只有 {china10y:.2f}%，门槛低得多，但汇率和可及性是另一回事。</p>
  </div>
</div>

<h2><span class="no">07</span>操作方案：把“割肉”换成“分批降仓 + 规则”</h2>
<p class="sub">目标不是卖在最高点，而是让仓位回到“再跌 40% 也能睡着”的水平，同时保留一部分反转期权。</p>

<div class="card">
  <div class="rule"><div class="k">现在</div><div><b>20% → 12%–13%，先减 7–8 个百分点。</b>分 2–3 个交易日执行，不要一笔砸。理由不是“预测还要跌”，而是“20% 超出风险预算”；这一步不需要看对基本面。</div></div>
  <div class="rule"><div class="k">反弹</div><div>若反弹到 <b>4,200–{ma60:,.0f}</b>（MA60/前期密集区），再减到 <b>10%</b>。不要在反弹时加仓，除非下面的“加仓条件”同时满足。</div></div>
  <div class="rule"><div class="k">破位</div><div>若跌破 <b>3,400</b> 且 Q4 盈利同比仍 &lt; -10%，再减到 <b>5%–6%</b>。这不是“止损”，是“基本面继续恶化”的确认。</div></div>
  <div class="rule"><div class="k">保留</div><div>长期核心 <b>8%–10%</b>，把它当成“中国互联网现金流 + AI 期权”的组合，而不是“必须回本”的仓位。成本价不进入任何期望收益公式。</div></div>
  <div class="rule"><div class="k">加回</div><div>必须同时看到：① Q4 盈利同比 &gt; -5%；② FCF 同比转正/回购恢复；③ 价格站上 MA200 且 20 个交易日不破。满足两条先加 2%，三条全满足加到 12% 上限。</div></div>
  <div class="rule"><div class="k">清仓</div><div>只有这几种情况值得清零：连续两个季度盈利同比 &lt; -20%、回购停止 + 分红下调、政策/退市级冲击、或“你发现自己每天睡不着”。最后一条是风险预算，不是基本面。</div></div>
</div>

<div class="callout">
  <b>如果你只想做一件事：</b>今天把 20% 降到 10%–12%，剩下的用上面的规则管理。这样你既不会在反弹时后悔“卖飞”，也不会在再跌 40% 时被迫割在底部。<b>“分批”不是优柔寡断，是把“判断对错”与“仓位生死”解耦。</b>
</div>

<h2><span class="no">08</span>什么会证明你对了 / 错了</h2>
<p class="sub">把你的论点变成可跟踪的指标，而不是每天刷新闻。下面每一条都能在财报或行情里验证。</p>

<div class="grid2">
  <div class="card">
    <h3 style="margin-top:0" class="up">证明你对了（继续减）</h3>
    <ul>
      <li>腾讯/阿里 Q4 capex 继续上升，但 AI 收入增速没有同步加速；FCF 继续为负。</li>
      <li>美团亏损扩大、外卖/即时零售补贴没有降温迹象；EV 价格战延续到 2027。</li>
      <li>回购金额同比下降 &gt; 30%，或分红率下调。</li>
      <li>美国 10Y 升破 5.5%，港股风险溢价继续走阔。</li>
      <li>指数跌破 3,400 且 2 周收不回，同时盈利预期还在下修。</li>
    </ul>
  </div>
  <div class="card">
    <h3 style="margin-top:0" class="down">证明你错了（加回）</h3>
    <ul>
      <li>Q4 盈利同比转正或跌幅收窄到 -5% 以内；管理层明确下调 capex 指引。</li>
      <li>外卖/即时零售战争出现“停战”信号（补贴率下降、亏损环比收窄）。</li>
      <li>回购恢复/加码，股息率维持或上升。</li>
      <li>国产算力/模型效率出现可验证的突破，AI 收入增速追上 capex 增速。</li>
      <li>价格站上 MA200（当前 {ma200:,.0f}）并保持 20 个交易日，同时南向资金持续流入。</li>
    </ul>
  </div>
</div>

<h2><span class="no">09</span>把“知道的越多越悲观”翻译成决策</h2>
<p class="sub">信息多不等于判断准。真正的问题不是“还有多少坏消息”，而是“这些坏消息有多少已经进了价格”。</p>

<div class="card">
  <p>你现在掌握的证据，足以支持一个结论：<b>恒生科技不是一个可以“闭眼满仓”的资产</b>。盈利在下修、战争在烧钱、芯片是硬约束、利率在高位——这些都不是噪音。</p>
  <p>但这些证据不足以支持另一个结论：<b>“必须现在清仓”</b>。因为价格已经从 2021 年峰值跌了 {abs(dd_all)*100:.0f}%、从 2026 年高点跌了 {abs(dd_2026)*100:.0f}%；腾讯 15x、网易 16.6x、阿里 16.5x；指数股息率处在历史 98% 分位。市场不是没看见坏消息，它已经用价格投票了。</p>
  <p>所以最诚实的答案是：<b>减仓，而不是割肉；留观察仓，而不是赌反转；用规则，而不是用情绪。</b>把 20% 降到 8%–10%，你既没有在底部清仓，也没有把全部身家押在“AI 会救回来”上。这个仓位，才是你能拿着它等财报验证的大小。</p>
</div>

<footer>
  <p><b>数据与口径：</b>恒生科技价格=新浪港股指数日线（2020-08 起），PE-TTM/股息率=乐咕乐股官方月度（2020-07 起），当前 PE 按 2026-10-31 官方 PE 与 10-30 收盘折算到 11-16；PE 分位为历史序列中 ≤ 当前值的比例，含当前点，负 PE 月份已剔除；隐含盈利=指数点位÷PE，为反推值，不等于官方净利润。恒指/沪深300/纳指/标普/美债数据来自本仓库缓存。个股估值与财务来自《中概互联 ETF 513050 重仓股估值报告》（2026-09-24，TTM 截至 2026-06-30）与《恒生指数成分股估值报告》（2026-10-13）。AI 算力数据来自《中美 AI 算力月度估算对照》（2026-10-21，Epoch AI / BCG 口径）。</p>
  <p><b>局限：</b>① 恒生科技 PE 序列短（2020 起）且受亏损公司、指数调仓、财报更新影响，分位只能当参考；② 隐含盈利是 P/PE 反推，2024-03、2026-03 等财报月的跳变包含口径变化，不宜当真实单季增速；③ 个股 PE/财务为 2026-09 快照，可能与最新财报有差异；④ 情景概率为主观设定，不是市场隐含概率；⑤ 本文为数据研究，不构成投资建议，仓位决策需结合你的总资产、负债、现金流与风险承受能力。</p>
</footer>
"""

SCRIPT = """
<script>
var DATA = __DATA__;
var charts = [];
function mk(id, opt){ var el=document.getElementById(id); if(!el) return; var c=echarts.init(el); c.setOption(opt); charts.push(c); }
function axis(extra){ return Object.assign({axisLine:{lineStyle:{color:'#d8d5ce'}},axisLabel:{color:'#6b6b70',fontSize:11},splitLine:{lineStyle:{color:'#efede8'}}}, extra||{}); }

mk('cPrice', {
  tooltip:{trigger:'axis'},
  grid:{left:58,right:24,top:26,bottom:34},
  xAxis: axis({type:'category', data:DATA.price.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(0,7);}}}),
  yAxis: axis({type:'value', name:'点位', scale:true, nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[{name:'恒生科技', type:'line', data:DATA.price.values, showSymbol:false, lineStyle:{width:1.8,color:'#7a4fb5'},
    areaStyle:{color:'rgba(122,79,181,.06)'},
    markPoint:{symbolSize:56, data:[
      {coord:[DATA.price.peak2021.date, DATA.price.peak2021.value], value:'2021峰值\\n'+DATA.price.peak2021.value, itemStyle:{color:'#9b59b6'}, label:{color:'#fff',fontSize:10,lineHeight:13}},
      {coord:[DATA.price.high2026.date, DATA.price.high2026.value], value:'2026高点\\n'+DATA.price.high2026.value, itemStyle:{color:'#d9363e'}, label:{color:'#fff',fontSize:10,lineHeight:13}},
      {coord:[DATA.price.current.date, DATA.price.current.value], value:'现在\\n'+DATA.price.current.value, itemStyle:{color:'#1f4fd8'}, label:{color:'#fff',fontSize:10,lineHeight:13}}
    ]}}]
});

mk('cPE', {
  tooltip:{trigger:'axis'},
  grid:{left:44,right:16,top:22,bottom:34},
  xAxis: axis({type:'category', data:DATA.pe.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(0,7);}}}),
  yAxis: axis({type:'value', name:'PE', min:18, max:45, nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[{name:'PE-TTM', type:'line', data:DATA.pe.values, showSymbol:false, lineStyle:{width:2,color:'#1f4fd8'}, areaStyle:{color:'rgba(31,79,216,.06)'},
    markPoint:{symbolSize:48, data:[{coord:[DATA.pe.dates[DATA.pe.dates.length-1], DATA.pe.current], value:DATA.pe.current, itemStyle:{color:'#1f4fd8'}, label:{color:'#fff',fontSize:11}}]}}]
});

mk('cEarn', {
  tooltip:{trigger:'axis'},
  grid:{left:52,right:16,top:22,bottom:34},
  xAxis: axis({type:'category', data:DATA.earn.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(0,7);}}}),
  yAxis: axis({type:'value', name:'隐含盈利', scale:true, nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[{name:'隐含盈利', type:'line', data:DATA.earn.values, showSymbol:true, symbolSize:4, lineStyle:{width:2,color:'#d9363e'}, itemStyle:{color:'#d9363e'}, areaStyle:{color:'rgba(217,54,62,.08)'},
    markPoint:{symbolSize:48, data:[{coord:[DATA.earn.dates[DATA.earn.dates.length-1], DATA.earn.values[DATA.earn.values.length-1]], value:DATA.earn.values[DATA.earn.values.length-1], itemStyle:{color:'#d9363e'}, label:{color:'#fff',fontSize:11}}]}}]
});

mk('cNorm', {
  tooltip:{trigger:'axis', valueFormatter:function(v){return v.toFixed(1);}},
  legend:{top:0, textStyle:{fontSize:12}},
  grid:{left:44,right:18,top:42,bottom:34},
  xAxis: axis({type:'category', data:DATA.norm.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(5);}}}),
  yAxis: axis({type:'value', name:'2026-01=100', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[
    {name:'恒生科技', type:'line', data:DATA.norm.series['恒生科技'], showSymbol:false, smooth:true, lineStyle:{width:2.4,color:'#7a4fb5'}, itemStyle:{color:'#7a4fb5'}},
    {name:'恒生指数', type:'line', data:DATA.norm.series['恒生指数'], showSymbol:false, smooth:true, lineStyle:{width:1.8,color:'#d9363e'}, itemStyle:{color:'#d9363e'}},
    {name:'沪深300', type:'line', data:DATA.norm.series['沪深300'], showSymbol:false, smooth:true, lineStyle:{width:1.8,color:'#b8791a'}, itemStyle:{color:'#b8791a'}},
    {name:'纳指100', type:'line', data:DATA.norm.series['纳指100'], showSymbol:false, smooth:true, lineStyle:{width:1.8,color:'#1f4fd8'}, itemStyle:{color:'#1f4fd8'}}
  ]
});

mk('cPct', {
  tooltip:{trigger:'axis', axisPointer:{type:'shadow'}},
  grid:{left:104,right:66,top:18,bottom:26},
  xAxis: axis({type:'value', max:100, name:'各自历史分位 %', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  yAxis: axis({type:'category', data:DATA.pct.cats, splitLine:{show:false}}),
  series:[{type:'bar', data:DATA.pct.values.map(function(v,i){
      var cols=['#7a4fb5','#d9363e','#b8791a','#1f4fd8','#5b7bd5'];
      return {value:v, itemStyle:{color:cols[i], borderRadius:[0,5,5,0]}};
    }), barWidth:22, label:{show:true, position:'right', formatter:function(p){return p.value+'%';}, color:'#1c1c1e', fontSize:12, fontWeight:600}}]
});

mk('cScen', {
  tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, valueFormatter:function(v){return v+'%';}},
  grid:{left:64,right:20,top:16,bottom:26},
  xAxis: axis({type:'category', data:DATA.scen.names, axisLabel:{color:'#6b6b70',fontSize:11}}),
  yAxis: axis({type:'value', name:'相对现价 %', nameTextStyle:{color:'#6b6b70',fontSize:11}, axisLabel:{formatter:'{value}%'}}),
  series:[{type:'bar', barWidth:34, data:DATA.scen.rets.map(function(v,i){
      return {value:v, itemStyle:{color:v>=0?'#1a9c5b':'#d9363e', borderRadius:v>=0?[4,4,0,0]:[0,0,4,4]}};
    }), label:{show:true, position:'top', formatter:function(p){return p.value+'%\\n('+DATA.scen.probs[p.dataIndex]+'%)';}, color:'#1c1c1e', fontSize:11, lineHeight:14}}]
});

mk('cRisk', {
  tooltip:{trigger:'axis', axisPointer:{type:'shadow'}, valueFormatter:function(v){return v+'%';}},
  legend:{top:0, textStyle:{fontSize:12}},
  grid:{left:48,right:16,top:40,bottom:30},
  xAxis: axis({type:'category', data:DATA.risk.moves.map(function(v){return '恒科 '+v+'%';}), axisLabel:{color:'#6b6b70',fontSize:11}}),
  yAxis: axis({type:'value', name:'总组合影响 %', nameTextStyle:{color:'#6b6b70',fontSize:11}, axisLabel:{formatter:'{value}%'}}),
  series:[
    {name:'20% 仓位', type:'bar', data:DATA.risk.series['20% 仓位'], itemStyle:{color:'#d9363e', borderRadius:[0,0,4,4]}, label:{show:true, position:'bottom', formatter:'{c}%', color:'#d9363e', fontSize:10}},
    {name:'12% 仓位', type:'bar', data:DATA.risk.series['12% 仓位'], itemStyle:{color:'#e08a00', borderRadius:[0,0,4,4]}, label:{show:true, position:'bottom', formatter:'{c}%', color:'#b8791a', fontSize:10}},
    {name:'8% 仓位', type:'bar', data:DATA.risk.series['8% 仓位'], itemStyle:{color:'#1a9c5b', borderRadius:[0,0,4,4]}, label:{show:true, position:'bottom', formatter:'{c}%', color:'#1a9c5b', fontSize:10}}
  ]
});

window.addEventListener('resize', function(){ charts.forEach(function(c){ c.resize(); }); });
</script>
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>恒生科技 20% 仓位：该割肉，还是该减仓？· 2026-11-20</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">
__BODY__
</div>
__SCRIPT__
</body>
</html>
"""

html = (HTML.replace("__CSS__", CSS)
            .replace("__BODY__", BODY)
            .replace("__SCRIPT__", SCRIPT.replace("__DATA__", json.dumps(chart_data, ensure_ascii=False))))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✓ 生成 {os.path.relpath(OUT, ROOT)}")
print(f"  恒生科技 {px_last:.2f} ({px_date.date()})  PE {pe_eff:.2f}  分位 2023+ {pct_2023:.1f}%")
print(f"  隐含盈利 {E_last:.1f} vs 12M 前 {E_prev:.1f} ({sg((E_last/E_prev-1)*100)})")
print(f"  情景期望值 {sg(ev*100)}  周期性假设 {sg(ev_cycle*100)}")