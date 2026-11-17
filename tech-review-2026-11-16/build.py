# -*- coding: utf-8 -*-
"""生成「科创50 × 创业板 · 2026-11-16 复检」报告（单文件 HTML）。

数据全部来自仓库内已缓存的 CSV：
  ../hs300-strategy-lab/data/{kcb50,cyb_price,ndx_price,sp500_price,sp500_pe,ndx_cape,hstech_price,gold_price}.csv
  ../cyb-2026-10/data/{index-basic-pe,index-basic-pb,merged}.csv

运行：
  hs300-strategy-lab/.venv/bin/python tech-review-2026-11-16/build.py
  cd .. && python3 build_site.py     # 注册门户 + 注入导航
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
D = os.path.join(ROOT, "hs300-strategy-lab", "data")
CYBD = os.path.join(ROOT, "cyb-2026-10", "data")
OUT = os.path.join(HERE, "index.html")

PEAK_DOM = pd.Timestamp("2026-06-30")
BASE_REPORT = pd.Timestamp("2026-10-30")


def load_close(path):
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date")
    return df.set_index("date")["close"].dropna()


def rsi(s, n=14):
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def pct_le(series, v):
    series = pd.Series(series).dropna()
    return float((series <= v).mean() * 100)


def fmt_signed(x):
    return ("+" if x >= 0 else "") + f"{x:.1f}%"


# ---------------------------------------------------------------- 科创50
k = pd.read_csv(os.path.join(D, "kcb50.csv"), parse_dates=["日期"]).set_index("日期").sort_index()
kc = k["收盘"].dropna()
kc = kc[kc.index >= pd.Timestamp("2019-07-22")]
kpe = k["滚动市盈率"].dropna()
kpe = kpe[kpe > 0]
kc_last, kc_date = float(kc.iloc[-1]), kc.index[-1]
kc_prev = float(kc.loc[BASE_REPORT])
kc_peak = float(kc[kc.index >= PEAK_DOM].max())
kc_peak_date = kc[kc.index >= PEAK_DOM].idxmax()
kc_pe = float(kpe.iloc[-1])
kc_pe_pct = pct_le(kpe, kc_pe)
kpe5 = kpe[kpe.index >= kpe.index[-1] - pd.Timedelta(days=365 * 5)]
kc_pe_pct5 = pct_le(kpe5, kc_pe)
kc_ma20 = float(kc.tail(20).mean())
kc_ma60 = float(kc.tail(60).mean())
kc_ma200 = float(kc.tail(200).mean())
kc_rsi = float(rsi(kc).iloc[-1])

# ---------------------------------------------------------------- 创业板
cp = load_close(os.path.join(D, "cyb_price.csv"))
cyb_last, cyb_date = float(cp.iloc[-1]), cp.index[-1]
cyb_prev = float(cp.loc[BASE_REPORT])
cyb_peak = float(cp[cp.index >= PEAK_DOM].max())
cyb_peak_date = cp[cp.index >= PEAK_DOM].idxmax()
cyb_ma20 = float(cp.tail(20).mean())
cyb_ma60 = float(cp.tail(60).mean())
cyb_ma200 = float(cp.tail(200).mean())
cyb_rsi = float(rsi(cp).iloc[-1])

pe_raw = pd.read_csv(os.path.join(CYBD, "index-basic-pe.csv"), parse_dates=["date"]).set_index("date").sort_index()
pb_raw = pd.read_csv(os.path.join(CYBD, "index-basic-pb.csv"), parse_dates=["date"]).set_index("date").sort_index()
pe_base = pd.Timestamp("2026-10-29")
cyb_ratio = cyb_last / float(pe_raw.loc[pe_base, "close"])
cyb_pe = float(pe_raw.loc[pe_base, "addTtmPe"]) * cyb_ratio
cyb_pb = float(pb_raw.loc[pe_base, "addPb"]) * cyb_ratio
cyb_roe = cyb_pb / cyb_pe * 100
pe_hist = pe_raw["addTtmPe"].dropna()
pe_hist = pe_hist[pe_hist > 0]
pe_hist_ext = pd.concat([pe_hist, pd.Series({cyb_date: cyb_pe})]).sort_index()
cyb_pe_pct = pct_le(pe_hist_ext, cyb_pe)
pe5 = pe_hist_ext[pe_hist_ext.index >= cyb_date - pd.Timedelta(days=365 * 5)]
cyb_pe_pct5 = pct_le(pe5, cyb_pe)
pb_hist = pb_raw["addPb"].dropna()
pb_hist = pb_hist[pb_hist > 0]
cyb_pb_pct = pct_le(pb_hist, cyb_pb)

# Top3 集中度（宁德 / 中际 / 新易盛）
m = pd.read_csv(os.path.join(CYBD, "merged.csv"), dtype={"code": str})
m["ttm_np"] = m["np_202512"] + m["np_202609"] - m["np_202509"]
m["top3"] = m["code"].isin(["300750", "300308", "300502"])
W = m["weight"]
cyb_w_sum = float(W.sum())
top3_w = float(W[m.top3].sum())
top3_np_share = float((W[m.top3] * m.loc[m.top3, "ttm_np"]).sum() / (W * m["ttm_np"]).sum() * 100)
ex3_pe = float((W[~m.top3] * m.loc[~m.top3, "total_cap"] * 1e8).sum() /
               (W[~m.top3] * m.loc[~m.top3, "ttm_np"]).sum())
med_pe = float(m["pe_calc"].median())

# ---------------------------------------------------------------- 海外 / 对照
ndx = load_close(os.path.join(D, "ndx_price.csv"))
ndx_last, ndx_date = float(ndx.iloc[-1]), ndx.index[-1]
ndx_high = float(ndx.max())
ndx_high_date = ndx.idxmax()
ndx_ma200 = float(ndx.tail(200).mean())
ndx_ret_high = ndx_last / ndx_high - 1

s = load_close(os.path.join(D, "sp500_price.csv"))
s_last = float(s.iloc[-1])
sp_pe = pd.read_csv(os.path.join(D, "sp500_pe.csv"), parse_dates=["date"]).set_index("date").iloc[:, 0].dropna()
sp_pe = sp_pe[sp_pe > 0]
sp_pe_last = float(sp_pe.iloc[-1])
sp_pe_pct = pct_le(sp_pe, sp_pe_last)
cape = pd.read_csv(os.path.join(D, "ndx_cape.csv"), parse_dates=["date"]).set_index("date").iloc[:, 0].dropna()
cape = cape[cape > 0]
cape_last = float(cape.iloc[-1])
cape_pct = pct_le(cape, cape_last)

hst = load_close(os.path.join(D, "hstech_price.csv"))
hst_last = float(hst.iloc[-1])
gold = load_close(os.path.join(D, "gold_price.csv"))
gold_last = float(gold.iloc[-1])

# ---------------------------------------------------------------- 归一化走势
series_map = {
    "科创50": kc,
    "创业板指": cp,
    "纳指100": ndx,
    "标普500": s,
    "恒生科技": hst,
}
frame = pd.DataFrame({name: ser for name, ser in series_map.items()})
frame = frame[frame.index >= pd.Timestamp("2026-06-01")]
frame = frame.sort_index().ffill().dropna()
base_row = frame[frame.index >= PEAK_DOM].iloc[0]
norm = frame / base_row * 100
norm = norm.round(2)

# 回撤（各自历史区间内）
dd = pd.DataFrame({
    "科创50": kc / kc.cummax() - 1,
    "创业板指": cp / cp.cummax() - 1,
    "纳指100": ndx / ndx.cummax() - 1,
})
dd = dd[dd.index >= pd.Timestamp("2026-01-01")].ffill().dropna().round(4)

# PE 曲线（月/日）
kc_pe_ser = kpe[kpe.index >= pd.Timestamp("2019-07-01")]
cyb_pe_ser = pe_hist_ext

chart_data = {
    "norm": {
        "dates": [d.strftime("%Y-%m-%d") for d in norm.index],
        "series": {c: norm[c].tolist() for c in norm.columns},
    },
    "dd": {
        "dates": [d.strftime("%Y-%m-%d") for d in dd.index],
        "series": {c: (dd[c] * 100).round(2).tolist() for c in dd.columns},
    },
    "kcpe": {
        "dates": [d.strftime("%Y-%m-%d") for d in kc_pe_ser.index],
        "values": kc_pe_ser.round(2).tolist(),
        "current": round(kc_pe, 2),
        "currentDate": kc_date.strftime("%Y-%m-%d"),
    },
    "cybpe": {
        "dates": [d.strftime("%Y-%m-%d") for d in cyb_pe_ser.index],
        "values": cyb_pe_ser.round(2).tolist(),
        "current": round(cyb_pe, 2),
        "currentDate": cyb_date.strftime("%Y-%m-%d"),
    },
    "pct": {
        "cats": ["创业板指 PE", "科创50 PE", "标普500 PE", "美股 CAPE"],
        "values": [round(cyb_pe_pct, 1), round(kc_pe_pct, 1), round(sp_pe_pct, 1), round(cape_pct, 1)],
    },
}

CSS = """
:root{
  --bg:#f7f7f5; --card:#fff; --ink:#1c1c1e; --sub:#6b6b70; --line:#e6e4df;
  --up:#d9363e; --down:#1a9c5b; --accent:#1f4fd8; --warn:#b8791a;
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
.lede{font-size:17px;color:var(--sub);margin:0;max-width:840px}
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
.verdict b{color:var(--ink)}
.tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--accent);
  background:#eef3ff;border-radius:999px;padding:2px 10px;margin-bottom:8px}
.chart{width:100%;height:380px}
.chart.mid{height:330px}
table{width:100%;border-collapse:collapse;font-size:14px;margin-top:12px}
th,td{text-align:right;padding:9px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th:first-child,td:first-child{text-align:left;white-space:normal}
th{font-size:12.5px;color:var(--sub);font-weight:600;background:#faf9f6}
.badge{display:inline-block;font-size:12px;padding:1px 9px;border-radius:999px;font-weight:600}
.badge.hot{background:#fdecec;color:#c0392b}
.badge.mid{background:#fbf3e2;color:#b7791f}
.badge.cold{background:#e8f5ee;color:#1f7a5c}
ul{margin:8px 0 8px 22px;padding:0}
li{margin:6px 0}
.rule{display:grid;grid-template-columns:88px 1fr;gap:14px;padding:11px 0;border-bottom:1px dashed var(--line)}
.rule:last-child{border-bottom:none}
.rule .k{font-family:var(--mono);font-size:13px;color:var(--accent);font-weight:600}
.quote{border-left:3px solid var(--warn);background:#fdfaf3;padding:12px 16px;margin:16px 0;border-radius:0 8px 8px 0}
.src{font-size:12.5px;color:var(--sub);line-height:1.7}
footer{margin-top:48px;border-top:1px solid var(--line);padding-top:16px;font-size:13px;color:var(--sub)}
@media(max-width:720px){
  .tiles{grid-template-columns:1fr 1fr}
  .grid2{grid-template-columns:1fr}
  h1{font-size:28px}
  .chart{height:320px}
  .wrap{padding:32px 16px 60px}
}
"""

BODY = f"""
<header class="top">
  <div class="kicker">STAR 50 × CHINEXT · 2026-11-16 REVIEW</div>
  <h1>科创50 跌出“便宜”了吗？<br>创业板已是 16 年最低估值</h1>
  <p class="lede">10-30 那两份报告之后，两个指数又走了一段反向行情：科创50 反弹后再跌、创业板继续创估值新低。用 11-16 收盘数据把结论重算一遍，并回答一个问题——现在该清仓双创、换到海外科技吗？</p>
  <div class="meta">数据截止 {cyb_date.strftime('%Y-%m-%d')} 收盘｜科创50 {kc_last:.2f}｜创业板指 {cyb_last:.2f}｜不构成投资建议</div>
</header>

<div class="tiles">
  <div class="tile">
    <div class="name">科创50</div>
    <div class="px">{kc_last:.0f}</div>
    <div class="chg {('up' if kc_last >= kc_prev else 'down')}">{fmt_signed((kc_last/kc_prev-1)*100)} 较 10-30</div>
    <div class="note">PE {kc_pe:.1f}x｜分位 {kc_pe_pct:.1f}%</div>
  </div>
  <div class="tile">
    <div class="name">创业板指</div>
    <div class="px">{cyb_last:.0f}</div>
    <div class="chg {('up' if cyb_last >= cyb_prev else 'down')}">{fmt_signed((cyb_last/cyb_prev-1)*100)} 较 10-30</div>
    <div class="note">PE {cyb_pe:.1f}x｜分位 {cyb_pe_pct:.1f}%</div>
  </div>
  <div class="tile">
    <div class="name">纳指100</div>
    <div class="px">{ndx_last:,.0f}</div>
    <div class="chg down">距 10/6 高点 {fmt_signed(ndx_ret_high*100)}</div>
    <div class="note">200 日线 {fmt_signed((ndx_last/ndx_ma200-1)*100)}</div>
  </div>
  <div class="tile">
    <div class="name">美股估值</div>
    <div class="px">{sp_pe_pct:.0f}%</div>
    <div class="chg up">标普500 PE 分位</div>
    <div class="note">CAPE {cape_last:.1f}｜分位 {cape_pct:.0f}%</div>
  </div>
</div>

<div class="verdict">
  <span class="tag">一句话结论</span>
  <p><b>科创50：不便宜，趋势仍向下。</b>PE {kc_pe:.1f}x 仍在上市以来 {kc_pe_pct:.0f}% 分位、近 5 年 {kc_pe_pct5:.0f}% 分位；价格低于 200 日线 {abs((kc_last/kc_ma200-1)*100):.0f}%。可以减，但不建议在 -{(1-kc_last/kc_peak)*100:.0f}% 的位置一次性砸。</p>
  <p><b>创业板：确实是历史级便宜。</b>PE {cyb_pe:.1f}x 处于 2010 年以来 <b>{cyb_pe_pct:.0f}% 分位</b>，PB {cyb_pb:.2f}x（2024 低点 3.18x），隐含 ROE {cyb_roe:.1f}%。但便宜高度集中在 3 只权重股：Top3 占 {top3_w:.1f}% 权重、<b>{top3_np_share:.0f}% 的 TTM 利润</b>，其余 73 只加权 PE 约 {ex3_pe:.0f}x、中位 {med_pe:.0f}x。<b>这里清仓，是卖在 16 年最便宜处。</b></p>
  <p><b>操作：减科创50 可以，创业板保留小仓位不加；海外科技可以定投，但别把“卖便宜买贵”当成理由</b>——标普 PE {sp_pe_pct:.0f}% 分位、CAPE {cape_pct:.0f}% 分位，海外在高位不是低位。</p>
</div>

<h2><span class="no">01</span>最新读数：10-30 → 11-16 发生了什么</h2>
<p class="sub">同一套口径下，两个指数走出了完全不同的边际：科创50 估值没降多少，创业板跌出了新低分位。</p>

<div class="card">
  <table>
    <thead><tr><th>指标</th><th>科创50（10-30 → 11-16）</th><th>创业板指（10-30 → 11-16）</th></tr></thead>
    <tbody>
      <tr><td>指数点位</td><td>1160.84 → <b>{kc_last:.2f}</b>（{fmt_signed((kc_last/kc_prev-1)*100)}）</td><td>2413.63 → <b>{cyb_last:.2f}</b>（{fmt_signed((cyb_last/cyb_prev-1)*100)}）</td></tr>
      <tr><td>PE-TTM</td><td>55.2x → <b>{kc_pe:.1f}x</b>（{kc_pe_pct:.1f}% 分位）</td><td>23.6x → <b>{cyb_pe:.1f}x</b>（{cyb_pe_pct:.1f}% 分位）</td></tr>
      <tr><td>PB / 隐含 ROE</td><td>—</td><td>3.84x → <b>{cyb_pb:.2f}x</b>（{cyb_pb_pct:.0f}% 分位）／ROE {cyb_roe:.1f}%</td></tr>
      <tr><td>距 6 月高点</td><td>{fmt_signed((kc_last/kc_peak-1)*100)}（{kc_peak:.0f} @ {kc_peak_date.strftime('%m-%d')}）</td><td>{fmt_signed((cyb_last/cyb_peak-1)*100)}（{cyb_peak:.0f} @ {cyb_peak_date.strftime('%m-%d')}）</td></tr>
      <tr><td>均线位置</td><td>MA20 {kc_ma20:.0f} / MA60 {kc_ma60:.0f} / MA200 {kc_ma200:.0f}，价格低于 MA200 {abs((kc_last/kc_ma200-1)*100):.0f}%</td><td>MA20 {cyb_ma20:.0f} / MA60 {cyb_ma60:.0f} / MA200 {cyb_ma200:.0f}，价格低于 MA200 {abs((cyb_last/cyb_ma200-1)*100):.0f}%</td></tr>
      <tr><td>RSI14</td><td>{kc_rsi:.1f}</td><td>{cyb_rsi:.1f}</td></tr>
    </tbody>
  </table>
  <div class="note">PE 为官方滚动 PE（科创50=中证官网；创业板=国证 addTtmPe，按指数当日涨跌从 10-29 折算到最新收盘）。分位含当前点；科创50 自 2019-07，创业板自 2010-06。PB 分位为创业板全历史。</div>
</div>

<div class="card">
  <div id="cNorm" class="chart"></div>
  <div class="note">以 2026-06-30 = 100 归一化。A 股双创在 7 月后大幅跑输，纳指/标普只是温和回调——这不是一个“全球 AI 同步熊市”。</div>
</div>

<h2><span class="no">02</span>科创50：跌了很多，但“便宜”还没到</h2>
<p class="sub">它的核心矛盾不是跌幅，而是 54x 的估值 + 79% 的半导体权重 + 已经转负的单季环比。</p>

<div class="grid2">
  <div class="card">
    <div id="cKCPE" class="chart mid"></div>
    <div class="note">科创50 滚动 PE，2019-07 至今。当前 {kc_pe:.1f}x，位于 {kc_pe_pct:.0f}% 分位；历史底部区域在 23–36x。</div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">记分卡</h3>
    <table>
      <tbody>
        <tr><td>绝对估值</td><td><b>{kc_pe:.1f}x</b></td><td><span class="badge hot">贵</span></td></tr>
        <tr><td>历史分位</td><td>上市以来 {kc_pe_pct:.0f}%，近 5 年 {kc_pe_pct5:.0f}%</td><td><span class="badge mid">中性偏贵</span></td></tr>
        <tr><td>价格回撤</td><td>距 6/30 高点 {fmt_signed((kc_last/kc_peak-1)*100)}</td><td><span class="badge cold">已释放</span></td></tr>
        <tr><td>趋势</td><td>低于 MA200 {abs((kc_last/kc_ma200-1)*100):.0f}%，RSI {kc_rsi:.1f}</td><td><span class="badge hot">弱</span></td></tr>
        <tr><td>结构</td><td>半导体权重约 79%，单季净利环比已转负</td><td><span class="badge mid">集中</span></td></tr>
      </tbody>
    </table>
  </div>
</div>

<div class="quote"><b>结论：</b>科创50 已经从“极端贵”回到“中性偏贵”，但离历史底部（23–36x）还很远。如果判断 AI 硬件进入下行周期，减仓是合理的；但“跌了 {(1-kc_last/kc_peak)*100:.0f}%”本身不是买入理由，同样的逻辑也不能反过来当“必须马上清仓”的理由——更优的是反弹到 MA20（{kc_ma20:.0f}）附近分批减。</div>

<h2><span class="no">03</span>创业板：1% 分位，但便宜是“三只股票”的便宜</h2>
<p class="sub">PE 22.7x 是 2010 年以来最低 1%，但这是权重股（尤其宁德/中际/新易盛）把指数 PE 拉下来的结果。</p>

<div class="grid2">
  <div class="card">
    <div id="cCYBPE" class="chart mid"></div>
    <div class="note">创业板指 PE-TTM，2010-06 至今（月度 + 最新点）。当前 {cyb_pe:.1f}x，{cyb_pe_pct:.1f}% 分位；2024 年低点约 22.1–22.7x。</div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">四个估值镜头，答案不一样</h3>
    <table>
      <tbody>
        <tr><td>PE-TTM（加权）</td><td><b>{cyb_pe:.1f}x</b></td><td>{cyb_pe_pct:.1f}% 分位</td></tr>
        <tr><td>PB（加权）</td><td><b>{cyb_pb:.2f}x</b></td><td>{cyb_pb_pct:.0f}% 分位</td></tr>
        <tr><td>隐含 ROE</td><td><b>{cyb_roe:.1f}%</b></td><td>历史高位</td></tr>
        <tr><td>Top3 之外加权 PE</td><td><b>{ex3_pe:.0f}x</b></td><td>并不便宜</td></tr>
        <tr><td>成分股 PE 中位数</td><td><b>{med_pe:.0f}x</b></td><td>典型股票 30x+</td></tr>
      </tbody>
    </table>
    <div class="note">Top3（宁德时代/中际旭创/新易盛）占 {top3_w:.1f}% 权重、{top3_np_share:.0f}% 的 TTM 利润。PE 低，是因为高 ROE（{cyb_roe:.0f}%）+ 三只巨头低估值，不是整个创业板都便宜。</div>
  </div>
</div>

<div class="quote"><b>结论：</b>创业板是“估值便宜 + 趋势破位 + 盈利集中”的组合。在 {cyb_pe_pct:.0f}% 分位清仓，等于把 16 年最便宜的位置卖给别人；但也不该因为便宜就重仓——PB {cyb_pb:.2f}x 离 2024 年地板 3.18x 还有 {(cyb_pb/3.18-1)*100:.0f}% 的空间，且 ROE 一旦回到 14%，同样 PB 对应的 PE 就是约 {cyb_pb/0.14:.0f}x。原计划“持有 3%、2150/1850 分档加”仍然成立。</div>

<h2><span class="no">04</span>“国内科技性价比远差于海外”？——按估值恰好相反</h2>
<p class="sub">把“估值分位”和“趋势/盈利质量”分开看，会得到两个相反的答案。</p>

<div class="card">
  <div id="cPct" class="chart mid"></div>
  <div class="note">各指标自身历史分位（越高越贵）。创业板 {cyb_pe_pct:.0f}% vs 标普500 PE {sp_pe_pct:.0f}%、美股 CAPE {cape_pct:.0f}%。跨市场会计口径不同，只比“贵在自身历史的哪个位置”，不做绝对 PE 对比。</div>
</div>

<div class="grid2">
  <div class="card">
    <h3 style="margin-top:0">支持“海外更强”的证据</h3>
    <ul>
      <li>纳指100 距高点仅 {fmt_signed(ndx_ret_high*100)}，200 日线 {fmt_signed((ndx_last/ndx_ma200-1)*100)}；创业板低于 200 日线 {abs((cyb_last/cyb_ma200-1)*100):.0f}%。</li>
      <li>盈利质量与全球定价权：海外科技龙头现金流、回购、AI 资本开支仍在扩张。</li>
      <li>A 股 AI 硬件（光模块/存储/设备）是这轮下跌的重灾区，趋势确实坏了。</li>
    </ul>
  </div>
  <div class="card">
    <h3 style="margin-top:0">支持“国内更便宜”的证据</h3>
    <ul>
      <li>创业板 PE {cyb_pe:.1f}x / {cyb_pe_pct:.0f}% 分位 vs 标普 PE {sp_pe_last:.1f}x / {sp_pe_pct:.0f}% 分位。</li>
      <li>美股 CAPE {cape_last:.1f}，历史 {cape_pct:.0f}% 分位——长期预期回报处于历史最差区间之一。</li>
      <li>“卖 1% 分位、买 98% 分位”是一个很大的相对价值赌注，不是均值回归。</li>
    </ul>
  </div>
</div>

<div class="quote"><b>关键区分：</b>“AI 趋势完全破了”对美国不成立（纳指只是回调），对 A 股 AI 硬件成立（-46%）。而“国内性价比远差于海外”在估值维度是反的：国内在历史底部，海外在历史顶部。真正差的是<b>盈利质量与趋势</b>，不是价格。把这两件事混在一起，容易做出“低点清仓、高点追买”的操作。</div>

<h2><span class="no">05</span>如果一定要动：一套可执行的框架</h2>
<p class="sub">目标不是预测底部，而是让“减什么、留什么、怎么换”有规则，避免在情绪里做全有或全无。</p>

<div class="card">
  <div class="rule"><div class="k">科创50</div><div><b>可减，不追、不急砸。</b>当前 {kc_last:.0f}，54x 不便宜、趋势破位；若仓位超过卫星仓上限（约 4%），反弹到 MA20（{kc_ma20:.0f}）附近先减一半；跌破 1000 才考虑按原计划加一次。不要在 RSI {kc_rsi:.0f} 的位置一次性清空。</div></div>
  <div class="rule"><div class="k">创业板</div><div><b>保留 3% 左右，不加也不清。</b>PE {cyb_pe:.1f}x / {cyb_pe_pct:.0f}% 分位是 16 年最便宜；第一加仓档 2150（距现价 {(2150/cyb_last-1)*100:.0f}%）、第二档 1850。反弹到 3200（PE≈31）以上再考虑减。</div></div>
  <div class="rule"><div class="k">海外科技</div><div><b>可以定投，但要放慢、控比例。</b>标普 PE {sp_pe_pct:.0f}% 分位、CAPE {cape_pct:.0f}% 分位，起点在历史高位；用宽基/分散标的而非单一 AI，注意 QDII 溢价与汇率。资金优先来自“减科创50”，而不是“清创业板”。</div></div>
  <div class="rule"><div class="k">纪律</div><div>不要一次性完成切换；不要用“跌得多”当买入理由，也不要用“贵”当唯一卖出理由；单指数卫星仓上限 4%–6%，跨市场切换按月分批。</div></div>
</div>

<h2><span class="no">06</span>什么会改变上面的判断</h2>
<div class="grid2">
  <div class="card">
    <h3 style="margin-top:0" class="down">转多 / 便宜被确认</h3>
    <ul>
      <li>科创50 PE 回到 45x 以下，或价格跌到 950 以下且盈利预期不再下修。</li>
      <li>创业板站上 MA20（当前 {cyb_ma20:.0f}）并 5 日不破，同时 Q4 单季净利环比转正。</li>
      <li>Top3 之外的公司盈利增速回升（当前它们贡献很弱，是最大的脆弱点）。</li>
    </ul>
  </div>
  <div class="card">
    <h3 style="margin-top:0" class="up">转空 / thesis 破裂</h3>
    <ul>
      <li>美股 AI 资本开支（2027 capex guidance）集体下修，纳指跌破 200 日线且不收回。</li>
      <li>中际/新易盛 Q4 单季净利环比下滑 &gt;20%，或北美云厂砍单。</li>
      <li>创业板跌破 2200 后 2 周收不回，且 PB 向 2024 年 3.18x 靠拢。</li>
    </ul>
  </div>
</div>

<footer>
  <p><b>数据与口径：</b>科创50 价格/滚动 PE=中证官网 000688（2019-07 起）；创业板指价格=国证 399006 日线，PE/PB=国证指数官网 addTtmPe/addPb 月度序列（2010-06 起），最新点按指数涨跌从 2026-10-29 折算到 {cyb_date.strftime('%Y-%m-%d')}；持仓与集中度=创业板 ETF 159915 2026 Q3 披露（76 只，占净值 {cyb_w_sum:.1f}%）；纳指100=Yahoo ^NDX；标普500 PE / CAPE=multpl 月度序列。分位=历史序列中 ≤ 当前值的比例，含当前点。</p>
  <p><b>局限：</b>① 跨市场 PE 会计口径不同，只比各自历史分位；② 创业板 PE 低是 Top3 拉低，不能代表全指数；③ 情景与仓位均为框架性讨论，不构成投资建议；④ 数据为收盘快照，盘中会变。</p>
</footer>
"""

SCRIPT = """
<script>
var DATA = __DATA__;
var charts = [];
function mk(id, opt){ var el=document.getElementById(id); if(!el) return; var c=echarts.init(el); c.setOption(opt); charts.push(c); }
function axis(extra){ return Object.assign({axisLine:{lineStyle:{color:'#d8d5ce'}},axisLabel:{color:'#6b6b70',fontSize:11},splitLine:{lineStyle:{color:'#efede8'}}}, extra||{}); }

mk('cNorm', {
  tooltip:{trigger:'axis', valueFormatter:function(v){return v.toFixed(1);}},
  legend:{top:0, textStyle:{fontSize:12}},
  grid:{left:44,right:18,top:42,bottom:34},
  xAxis: axis({type:'category', data:DATA.norm.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(5);}}}),
  yAxis: axis({type:'value', name:'6/30=100', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[
    {name:'科创50', type:'line', data:DATA.norm.series['科创50'], showSymbol:false, smooth:true, lineStyle:{width:2.2,color:'#d9363e'}, itemStyle:{color:'#d9363e'}},
    {name:'创业板指', type:'line', data:DATA.norm.series['创业板指'], showSymbol:false, smooth:true, lineStyle:{width:2.2,color:'#e08a00'}, itemStyle:{color:'#e08a00'}},
    {name:'纳指100', type:'line', data:DATA.norm.series['纳指100'], showSymbol:false, smooth:true, lineStyle:{width:2,color:'#1f4fd8'}, itemStyle:{color:'#1f4fd8'}},
    {name:'标普500', type:'line', data:DATA.norm.series['标普500'], showSymbol:false, smooth:true, lineStyle:{width:1.6,color:'#5b7bd5'}, itemStyle:{color:'#5b7bd5'}},
    {name:'恒生科技', type:'line', data:DATA.norm.series['恒生科技'], showSymbol:false, smooth:true, lineStyle:{width:1.6,color:'#9b59b6'}, itemStyle:{color:'#9b59b6'}}
  ]
});

mk('cKCPE', {
  tooltip:{trigger:'axis'},
  grid:{left:48,right:20,top:24,bottom:34},
  xAxis: axis({type:'category', data:DATA.kcpe.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(0,7);}}}),
  yAxis: axis({type:'value', name:'PE', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[{name:'科创50 PE', type:'line', data:DATA.kcpe.values, showSymbol:false, lineStyle:{width:2,color:'#d9363e'}, areaStyle:{color:'rgba(217,54,62,.07)'},
    markPoint:{symbolSize:46, data:[{coord:[DATA.kcpe.currentDate, DATA.kcpe.current], value:DATA.kcpe.current, itemStyle:{color:'#d9363e'}, label:{color:'#fff',fontSize:11}}]}}]
});

mk('cCYBPE', {
  tooltip:{trigger:'axis'},
  grid:{left:46,right:20,top:24,bottom:34},
  xAxis: axis({type:'category', data:DATA.cybpe.dates, boundaryGap:false, axisLabel:{color:'#6b6b70',fontSize:10.5, formatter:function(v){return v.slice(0,4);}}}),
  yAxis: axis({type:'value', name:'PE', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  series:[{name:'创业板 PE', type:'line', data:DATA.cybpe.values, showSymbol:false, lineStyle:{width:2,color:'#e08a00'}, areaStyle:{color:'rgba(224,138,0,.07)'},
    markPoint:{symbolSize:46, data:[{coord:[DATA.cybpe.currentDate, DATA.cybpe.current], value:DATA.cybpe.current, itemStyle:{color:'#e08a00'}, label:{color:'#fff',fontSize:11}}]}}]
});

mk('cPct', {
  tooltip:{trigger:'axis', axisPointer:{type:'shadow'}},
  grid:{left:96,right:42,top:18,bottom:26},
  xAxis: axis({type:'value', max:100, name:'历史分位 %', nameTextStyle:{color:'#6b6b70',fontSize:11}}),
  yAxis: axis({type:'category', data:DATA.pct.cats, splitLine:{show:false}}),
  series:[{type:'bar', data:DATA.pct.values.map(function(v,i){
      var cols=['#e08a00','#d9363e','#1f4fd8','#7a5af8'];
      return {value:v, itemStyle:{color:cols[i], borderRadius:[0,5,5,0]}};
    }), barWidth:22, label:{show:true, position:'right', formatter:'{c}%', color:'#1c1c1e', fontSize:12, fontWeight:600}}]
});

window.addEventListener('resize', function(){ charts.forEach(function(c){ c.resize(); }); });
</script>
"""

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>科创50 × 创业板 · 2026-11-16 复检：跌到便宜了吗？</title>
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
print(f"  科创50 {kc_last:.2f} PE {kc_pe:.2f} ({kc_pe_pct:.1f}%ile)")
print(f"  创业板 {cyb_last:.2f} PE {cyb_pe:.2f} ({cyb_pe_pct:.1f}%ile) PB {cyb_pb:.2f}")
print(f"  标普PE {sp_pe_last:.2f} ({sp_pe_pct:.1f}%ile) CAPE {cape_last:.2f} ({cape_pct:.1f}%ile)")