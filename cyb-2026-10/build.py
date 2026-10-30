# -*- coding: utf-8 -*-
"""生成创业板 ETF 三季报体检页面（cyb-2026-10/index.html）

数据：data/ 下 CSV（fetch_data.py 抓取 + merged.csv 计算）
运行：hs300-strategy-lab/.venv/bin/python cyb-2026-10/build.py
"""
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

# ---------------------------------------------------------------- 基础数据
idx = pd.read_csv(os.path.join(DATA, "cyb_index.csv"), parse_dates=["date"]).sort_values("date")
idx = idx.drop_duplicates("date").reset_index(drop=True)
last_date = idx["date"].iloc[-1]
last_close = float(idx["close"].iloc[-1])

pe_raw = pd.read_csv(os.path.join(DATA, "index-basic-pe.csv"), parse_dates=["date"]).sort_values("date")
pb_raw = pd.read_csv(os.path.join(DATA, "index-basic-pb.csv"), parse_dates=["date"]).sort_values("date")
pe = pe_raw[["date", "close", "addTtmPe", "ttmPe", "middleTtmPe"]].rename(columns={"addTtmPe": "pe"})
pb = pb_raw[["date", "addPb", "pb", "middlePb"]].rename(columns={"addPb": "pb_cap"})
val = pe.merge(pb, on="date", how="inner").sort_values("date").reset_index(drop=True)

# 用 10/30 收盘把 10/29 的月度估值点替换为最新（PE/PB 按指数涨跌比例折算）
base_date = pd.Timestamp("2026-10-29")
base_row = val[val.date == base_date].iloc[0]
ratio = last_close / float(base_row["close"])
cur_pe = float(base_row["pe"]) * ratio
cur_pb = float(base_row["pb_cap"]) * ratio
cur_roe = cur_pb / cur_pe * 100
cur = pd.DataFrame([{
    "date": last_date, "close": last_close, "pe": cur_pe, "ttmPe": float(base_row["ttmPe"]) * ratio,
    "middleTtmPe": float(base_row["middleTtmPe"]) * ratio, "pb_cap": cur_pb,
    "pb": float(base_row["pb"]) * ratio, "middlePb": float(base_row["middlePb"]) * ratio,
    "roe": cur_roe,
}])
val = pd.concat([val[val.date < base_date], cur], ignore_index=True)
val["e"] = val["close"] / val["pe"]
val["roe"] = val["pb_cap"] / val["pe"] * 100

# ETF 持仓 + 财务
m = pd.read_csv(os.path.join(DATA, "merged.csv"), dtype={"code": str})
d24 = pd.read_csv(os.path.join(DATA, "np2024.csv"), dtype={"code": str})
m["np2024"] = m["code"].map(d24.set_index("code")["np2024"])
m["ttm_np"] = m["np_202512"] + m["np_202609"] - m["np_202509"]
m["pe_calc"] = m["total_cap"] * 1e8 / m["ttm_np"]
m["npq26"] = m["np_202609"] - m["np_202606"]
m["npq25"] = m["np_202509"] - m["np_202506"]
m["npq_yoy"] = m["npq26"] / m["npq25"] - 1
m["h1_yoy"] = m["np_202606"] / m["np_202506"] - 1
m["m9_yoy"] = m["np_202609"] / m["np_202509"] - 1
m["revq26"] = m["rev_202609"] - m["rev_202606"]
m["revq25"] = m["rev_202509"] - m["rev_202506"]
m["revq_yoy"] = m["revq26"] / m["revq25"] - 1
m["contrib"] = m["weight"] * (m["npq26"] - m["npq25"])
base_np = (m["weight"] * m["npq25"]).sum()
m["contrib"] = m["contrib"] / base_np
m["top3"] = m["code"].isin(["300750", "300308", "300502"])
m = m.sort_values("weight", ascending=False).reset_index(drop=True)

W = m["weight"]


def agg(num, den, mask=None):
    s = m if mask is None else m[mask]
    return float((s["weight"] * s[num]).sum() / (s["weight"] * s[den]).sum() - 1)


q3_np_g = agg("npq26", "npq25")
h1_np_g = agg("np_202606", "np_202506")
m9_np_g = agg("np_202609", "np_202509")
q3_rev_g = agg("revq26", "revq25")
h1_rev_g = agg("rev_202606", "rev_202506")
m9_rev_g = agg("rev_202609", "rev_202509")
q3_np_g_ex3 = agg("npq26", "npq25", ~m["top3"])
q3_med = float(m["npq_yoy"].median())
h1_med = float(m["h1_yoy"].median())
m9_med = float(m["m9_yoy"].median())
q3_rev_med = float(m["revq_yoy"].median())
pos_cnt = int((m["npq_yoy"] > 0).sum())
acc_cnt = int((m["npq_yoy"] > m["h1_yoy"]).sum())
pos_w = float(m.loc[m["npq_yoy"] > 0, "weight"].sum())
neg_w = float(m.loc[m["npq_yoy"] < 0, "weight"].sum())
q3_margin = float((W * m["npq26"]).sum() / (W * m["revq26"]).sum())
h1_margin = float((W * m["np_202606"]).sum() / (W * m["rev_202606"]).sum())
top3_w = float(m.loc[m["top3"], "weight"].sum())
top3_np_share = float(m.loc[m["top3"], "ttm_np"].sum() / m["ttm_np"].sum())
top3_pe = float(m.loc[m["top3"], "total_cap"].sum() * 1e8 / m.loc[m["top3"], "ttm_np"].sum())
ex3_pe = float(m.loc[~m["top3"], "total_cap"].sum() * 1e8 / m.loc[~m["top3"], "ttm_np"].sum())
top10_w = float(m["weight"].nlargest(10).sum())
agg_pe = float(m["total_cap"].sum() * 1e8 / m["ttm_np"].sum())
pe2024 = float(m["total_cap"].sum() * 1e8 / m["np2024"].sum())
pe2025 = float(m["total_cap"].sum() * 1e8 / m["np_202512"].sum())
np2024_sum = float(m["np2024"].sum() / 1e8)
np2025_sum = float(m["np_202512"].sum() / 1e8)
ttm_sum = float(m["ttm_np"].sum() / 1e8)

# ---------------------------------------------------------------- 估值分位
def pctl(series, v):
    return float((series.dropna() <= v).mean() * 100)

pe_all = val["pe"]
pb_all = val["pb_cap"]
pe_10 = val.loc[val.date >= val.date.max() - pd.DateOffset(years=10), "pe"]
pe_5 = val.loc[val.date >= val.date.max() - pd.DateOffset(years=5), "pe"]
pb_10 = val.loc[val.date >= val.date.max() - pd.DateOffset(years=10), "pb_cap"]
pb_5 = val.loc[val.date >= val.date.max() - pd.DateOffset(years=5), "pb_cap"]
pe_pct = pctl(pe_all, cur_pe)
pe_pct10 = pctl(pe_10, cur_pe)
pe_pct5 = pctl(pe_5, cur_pe)
pb_pct = pctl(pb_all, cur_pb)
pb_pct10 = pctl(pb_10, cur_pb)
pb_pct5 = pctl(pb_5, cur_pb)

# 创业板 / 沪深300 相对估值
hs = pd.read_csv("/Users/chenweilong/Explore/hs300-strategy-lab/data/hs300_pe.csv", parse_dates=["date"]).rename(columns={"pe": "hs300"})
rel = pd.merge_asof(
    val[["date", "pe"]].sort_values("date"), hs.sort_values("date"), on="date", direction="backward"
).dropna()
rel["ratio"] = rel["pe"] / rel["hs300"]
# 沪深300 10/30 收盘 3985.50（10/29 4041.84），PE 按 -1.39% 折算
rel_cur_ratio = cur_pe / (12.37 * 3985.50 / 4041.84)
rel_cur = pd.DataFrame([{"date": last_date, "ratio": rel_cur_ratio}])
rel = pd.concat([rel[rel.date < base_date], rel_cur], ignore_index=True)
rel_pct = pctl(rel["ratio"], rel_cur_ratio)
rel_med = float(rel["ratio"].median())

# ---------------------------------------------------------------- 走势 / 技术面
c = idx.set_index("date")["close"]
peak = float(c.max())
peak_date = c.idxmax()
dd = last_close / peak - 1
days_since_peak = (last_date - peak_date).days
ret_1m = last_close / c.iloc[-22] - 1
ret_3m = last_close / c.iloc[-64] - 1
ret_6m = last_close / c.iloc[-127] - 1
ret_1y = last_close / c.iloc[-253] - 1
ytd_base = float(c[c.index.year == 2026].iloc[0])
ret_ytd = last_close / ytd_base - 1
ma20 = float(c.rolling(20).mean().iloc[-1])
ma60 = float(c.rolling(60).mean().iloc[-1])
ma200 = float(c.rolling(200).mean().iloc[-1])
dist_ma20 = last_close / ma20 - 1
dist_ma60 = last_close / ma60 - 1
dist_ma200 = last_close / ma200 - 1
amt = idx.set_index("date")["amount"]
amt20 = float(amt.rolling(20).mean().iloc[-1])
amt_ratio = float(amt.iloc[-1] / amt20)
etf = pd.read_csv(os.path.join(DATA, "etf_159915.csv"), parse_dates=["date"])
etf_last = 2.435  # 2026-10-30 收盘（腾讯行情；kline 两位小数会四舍五入到 2.44）
etf_high = float(etf["close"].max())
etf_dd = etf_last / etf_high - 1

# ---------------------------------------------------------------- 预测收益统计
f = val.copy()
f["ret6"] = f["close"].shift(-6) / f["close"] - 1
f["ret12"] = f["close"].shift(-12) / f["close"] - 1
f["dd1y"] = f["close"] / f["close"].rolling(12, min_periods=1).max() - 1
f["e_yoy"] = f["e"].pct_change(12)
fwd_min = f["close"][::-1].rolling(12, min_periods=1).min()[::-1].shift(-1)
f["mdd12"] = fwd_min / f["close"] - 1

buckets = [(0, 25, "PE<25"), (25, 30, "25–30"), (30, 40, "30–40"), (40, 60, "40–60"), (60, 999, ">60")]
forward = []
for lo, hi, lab in buckets:
    s = f[(f.pe >= lo) & (f.pe < hi)]
    r = s["ret12"].dropna()
    forward.append({
        "label": lab,
        "med": round(float(r.median() * 100), 1) if len(r) else 0,
        "win": int(round(float((r > 0).mean() * 100))) if len(r) else 0,
        "n": int(len(r)),
    })

# ---------------------------------------------------------------- 图表数据
pe_chart = [{"d": x.date.strftime("%Y-%m-%d"), "pe": round(float(x.pe), 2)} for x in val.itertuples()]
pbroe = [{
    "d": x.date.strftime("%Y-%m-%d"), "roe": round(float(x.roe), 2),
    "pb": round(float(x.pb_cap), 2), "pe": round(float(x.pe), 2),
} for x in val.itertuples()]

# 2024-01 起的价格 / 隐含 EPS（2024-12-31 = 100）
pe_base = val[(val.date >= "2024-01-01") & (val.date <= last_date)].copy()
base_px = float(pe_base.loc[pe_base.date == pd.Timestamp("2024-12-31"), "close"].iloc[0])
base_e = float(pe_base.loc[pe_base.date == pd.Timestamp("2024-12-31"), "e"].iloc[0])
price_eps = []
for x in pe_base.itertuples():
    price_eps.append({
        "d": x.date.strftime("%Y-%m-%d"),
        "price": round(float(x.close / base_px * 100), 1),
        "eps": round(float(x.e / base_e * 100), 1),
        "pe": round(float(x.pe), 1),
    })

# 财报分布
edges = [-999, -50, -20, 0, 20, 50, 100, 999]
labels = ["<-50%", "-50~-20%", "-20~0%", "0~20%", "20~50%", "50~100%", ">100%"]
dist = []
for i in range(len(labels)):
    s = m[(m.npq_yoy * 100 >= edges[i]) & (m.npq_yoy * 100 < edges[i + 1])]
    dist.append({"cat": labels[i], "count": int(len(s)), "weight": round(float(s.weight.sum()), 1)})

# 贡献 Top / Bottom
top_pos = m.sort_values("contrib", ascending=False).head(10)
bot_neg = m.sort_values("contrib").head(5)
contrib = []
for x in pd.concat([top_pos, bot_neg]).itertuples():
    contrib.append({"name": x.name, "v": round(float(x.contrib * 100), 1)})
contrib = sorted(contrib, key=lambda z: z["v"])

# ---------------------------------------------------------------- 情景
def scen_level(eps_g, pe_x):
    return float(last_close * (1 + eps_g / 100) * (pe_x / cur_pe))

scen = [
    dict(key="A", name="盈利韧性 + 估值修复", prob=30, eps=20, pe=28,
         desc="Q4 环比不降、AI 资本开支上修、指数站上 2800 并放量",
         color="#2c9e63"),
    dict(key="B", name="盈利兑现 + 估值横盘", prob=40, eps=10, pe=24,
         desc="Q4 增速 10–20%，指数 2400–2800 区间震荡，用时间换空间",
         color="#2f6fed"),
    dict(key="C", name="增速失速 + 杀估值", prob=20, eps=0, pe=18,
         desc="Top3 Q4 增速 <10%，跌破 2200，PB 向 2024 年低点靠拢",
         color="#d99a00"),
    dict(key="D", name="AI 资本开支断崖", prob=10, eps=-20, pe=15,
         desc="北美云厂砍单，中际/新易盛单季环比 -30%，盈利与估值双杀",
         color="#d94a4a"),
]
for s in scen:
    s["level"] = scen_level(s["eps"], s["pe"])
    s["ret"] = s["level"] / last_close - 1
exp_ret = sum(s["prob"] / 100 * s["ret"] for s in scen)

# ---------------------------------------------------------------- 表格数据
def q3_tag(row):
    if row["pe_ttm"] < 0:
        return "亏损"
    if row["npq_yoy"] < 0:
        return "负增长"
    if row["npq_yoy"] >= 0.5:
        return "高增长"
    if row["npq_yoy"] < row["h1_yoy"]:
        return "减速"
    if row["pe_ttm"] > 60:
        return "高估值"
    return "稳健"


stocks = []
for x in m.itertuples():
    peg = None
    if x.pe_ttm and x.pe_ttm > 0 and x.npq_yoy > 0:
        peg = min(float(x.pe_ttm / (x.npq_yoy * 100)), 9.99)
    stocks.append({
        "code": x.code, "name": x.name, "industry": x.industry,
        "weight": round(float(x.weight), 2), "pe": round(float(x.pe_ttm), 2),
        "pb": round(float(x.pb), 2), "q3": round(float(x.npq_yoy * 100), 1),
        "h1": round(float(x.h1_yoy * 100), 1), "m9": round(float(x.m9_yoy * 100), 1),
        "peg": None if peg is None else round(peg, 2),
        "contrib": round(float(x.contrib * 100), 1),
    })

# 历史类比表
analog_dates = ["2012-11-30", "2015-05-29", "2018-12-28", "2022-10-31", "2024-01-31", "2026-06-30"]
analog = []
for ds in analog_dates:
    row = val[val.date == pd.Timestamp(ds)]
    if not len(row):
        continue
    row = row.iloc[0]
    i = val.index[val.date == pd.Timestamp(ds)][0]
    f12 = None
    if i + 12 < len(val):
        f12 = float(val.loc[i + 12, "close"] / row["close"] - 1)
    if ds == "2026-06-30":
        f12 = last_close / float(row["close"]) - 1
    analog.append({
        "date": ds[:7], "close": int(round(float(row["close"]))),
        "pe": round(float(row["pe"]), 1), "pb": round(float(row["pb_cap"]), 2),
        "roe": round(float(row["roe"]), 1),
        "f12": None if f12 is None else round(f12 * 100, 1),
        "now": ds == "2026-06-30",
    })

# ---------------------------------------------------------------- 文本工具
def fp(v, d=1, sign=True):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return (f"{v:+.{d}f}%" if sign else f"{v:.{d}f}%")


def cls(v):
    return "g" if v >= 0 else "r"


def num(v, d=1):
    return f"{v:,.{d}f}"


# ---------------------------------------------------------------- 页面片段
kpis = f'''
<div class="kpis">
  <div class="kpi"><div class="k">创业板指</div><div class="v">{last_close:,.0f}</div><div class="s">距 6/25 高点 {fp(dd*100)}</div></div>
  <div class="kpi"><div class="k">PE-TTM</div><div class="v">{cur_pe:.1f}x</div><div class="s">历史 {pe_pct:.1f}% 分位</div></div>
  <div class="kpi"><div class="k">PB</div><div class="v">{cur_pb:.1f}x</div><div class="s">历史 {pb_pct:.0f}% 分位</div></div>
  <div class="kpi"><div class="k">Q3 净利增速</div><div class="v g">{fp(q3_np_g*100)}</div><div class="s">H1 为 {fp(h1_np_g*100)}</div></div>
  <div class="kpi"><div class="k">前三季净利增速</div><div class="v g">{fp(m9_np_g*100)}</div><div class="s">营收 {fp(m9_rev_g*100)}</div></div>
  <div class="kpi"><div class="k">Top3 集中度</div><div class="v">{top3_w:.1f}%</div><div class="s">利润占比 {top3_np_share*100:.1f}%</div></div>
</div>
'''

top3_contrib = float(m.loc[m["top3"], "contrib"].sum() * 100)
median_pe = float(np.median([x["pe"] for x in stocks if x["pe"] > 0]))
ai_basket = ["300308", "300502", "300394", "300476", "300408", "300604", "300475", "300857", "300442", "300620", "300383"]
ai_w = float(m.loc[m["code"].isin(ai_basket), "weight"].sum())

concl = f'''
<div class="concl">
  <div class="c"><div class="t"><i style="background:#2f6fed"></i>贵不贵</div><div class="h">PE 便宜，PB 不便宜</div>
    <p>PE {cur_pe:.1f}x 是历史 {pe_pct:.1f}% 分位；但 PB {cur_pb:.1f}x 只是 {pb_pct:.0f}% 分位。用 2024 年盈利算，PE 是 {pe2024:.1f}x。低 PE 是高 ROE（{cur_roe:.1f}%）造出来的，不是资产打折。</p></div>
  <div class="c"><div class="t"><i style="background:#2c9e63"></i>盈利</div><div class="h">真的强，但在减速</div>
    <p>Q3 单季净利 {fp(q3_np_g*100)}，H1 是 {fp(h1_np_g*100)}；中位股 Q3 只有 {fp(q3_med*100)}，{pos_cnt}/76 正增长。Top3 贡献 {top3_contrib:.1f}pp，剔除后 {fp(q3_np_g_ex3*100)}。</p></div>
  <div class="c"><div class="t"><i style="background:#d94a4a"></i>风险</div><div class="h">不是“创业板”风险<br>是“三只股票”风险</div>
    <p>宁德 + 中际 + 新易盛 = {top3_w:.1f}% 权重、{top3_np_share*100:.1f}% 利润；AI 算力链约 {ai_w:.1f}%。三只里任何一只逻辑破了，指数 PE 会立刻变贵。</p></div>
  <div class="c"><div class="t"><i style="background:#d99a00"></i>3% 怎么办</div><div class="h">持有不加，设三档</div>
    <p>当前不追（低于 200 日线 {abs(dist_ma200)*100:.0f}%）；2150–2200 加 1%，1850–1950 加 1%；反弹 3200–3400 减 1%。上限 6%。</p></div>
</div>
'''

growth_rows = ""
for x in m.nlargest(12, "weight").itertuples():
    growth_rows += f'''<tr>
      <td><b>{x.name}</b><br><span class="muted">{x.code}</span></td>
      <td>{x.weight:.2f}%</td>
      <td class="num {cls(x.npq_yoy*100)}"><b>{fp(x.npq_yoy*100)}</b></td>
      <td class="num {cls(x.h1_yoy*100)}">{fp(x.h1_yoy*100)}</td>
      <td class="num">{x.pe_ttm:.1f}</td>
      <td class="num {cls(x.contrib*100)}">{x.contrib*100:+.1f}pp</td>
    </tr>'''

analog_rows = ""
for a in analog:
    f12 = "—" if a["f12"] is None else fp(a["f12"])
    analog_rows += f'''<tr class="{'hlrow' if a['now'] else ''}">
      <td>{a['date']}</td><td class="num">{a['close']:,}</td><td class="num">{a['pe']:.1f}x</td>
      <td class="num">{a['pb']:.2f}x</td><td class="num">{a['roe']:.1f}%</td>
      <td class="num {cls(a['f12'] or 0)}">{f12}</td></tr>'''
analog_rows += f'''<tr class="hlrow">
  <td><b>现在</b></td><td class="num"><b>{last_close:,.0f}</b></td><td class="num"><b>{cur_pe:.1f}x</b></td>
  <td class="num"><b>{cur_pb:.2f}x</b></td><td class="num"><b>{cur_roe:.1f}%</b></td><td class="num">?</td></tr>'''

scen_html = ""
for s in scen:
    scen_html += f'''<div class="s {s['key'].lower()}">
      <div class="p" style="color:{s['color']}">{s['prob']}%</div>
      <div class="n">{s['key']}. {s['name']}</div>
      <div class="d">{s['desc']}</div>
      <div class="lv">EPS {s['eps']:+d}% · PE {s['pe']}x → <b>{s['level']:,.0f}</b> 点<br>
        <span class="{cls(s['ret']*100)}">{fp(s['ret']*100)}</span></div>
      <div class="bar"><span style="width:{s['prob']}%;background:{s['color']}"></span></div>
    </div>'''

# 3% 仓位阶梯
ladder = f'''
<div class="ladder">
  <div class="h">位置</div><div class="h">触发</div><div class="h">动作</div><div class="h">仓位</div>
  <div class="lvl">现在</div><div>{last_close:,.0f} 点 / ETF {etf_last:.3f}</div><div class="act">持有，不追</div><div>3%</div>
  <div class="lvl">左侧一档</div><div>2,150–2,200 点（PE≈21，ETF 2.17–2.22）</div><div class="act g">加 1%</div><div>4%</div>
  <div class="lvl">左侧二档</div><div>1,850–1,950 点（PE≈18，ETF 1.87–1.97）</div><div class="act g">加 1%</div><div>5%</div>
  <div class="lvl">右侧确认</div><div>站上 20 日线（≈2,800）且 5 日不破</div><div class="act g">加 1%</div><div>6%</div>
  <div class="lvl">减仓一档</div><div>3,200–3,400 点（PE 31–33，ETF 3.23–3.43）</div><div class="act r">减 1%</div><div>2–3%</div>
  <div class="lvl">减仓二档</div><div>3,800 点以上（PE≈37）</div><div class="act r">减到 1–2%</div><div>1–2%</div>
  <div class="lvl">暂停/复盘</div><div>跌破 2,200 且 Q4 Top3 增速 &lt;10%</div><div class="act a">暂停加仓，减 1%</div><div>2%</div>
</div>
'''

# 动态数字
content = f'''
<div class="hero">
  <div class="eyebrow">CHINEXT ETF · 2026 Q3 REVIEW</div>
  <h1>创业板 ETF 三季报体检：<br>PE 23.6 倍，便宜还是陷阱？</h1>
  <div class="sub">数据截至 2026-10-30 收盘 · 创业板指 399006 · 创业板ETF 159915 · 76 只持仓覆盖 87.5% 净值</div>
  <div class="verdict"><span class="tagline">结论</span>估值确实便宜，但便宜集中在 3 只股票身上。Q3 净利 {fp(q3_np_g*100)}，剔除宁德/中际/新易盛后是 <b>{fp(q3_np_g_ex3*100)}</b>。3% 仓位：<b>持有不加</b>，跌到 2,150 / 1,850 分两档加，反弹到 3,200 以上再减。</div>
</div>
{kpis}

<div class="card">
  <h2><span class="no">1</span>先看结论</h2>
  <p class="lede">把“估值、盈利、集中度、仓位”四件事分开看，答案会比一句“贵/便宜”清楚得多。</p>
  {concl}
</div>

<div class="card">
  <h2><span class="no">2</span>Q3 财报：增长是真的，但只属于三家公司</h2>
  <p class="lede">76 只 ETF 持仓 76/76 已披露三季报。单三季度 = 前三季 − 上半年，避免用累计增速掩盖 Q3 的减速。</p>
  <div class="grid3" style="margin-bottom:6px">
    <div class="box"><div class="k">Q3 单季营收增速</div><div class="v g">{fp(q3_rev_g*100)}</div><div class="s">中位股 {fp(q3_rev_med*100)}</div></div>
    <div class="box"><div class="k">Q3 单季净利增速</div><div class="v g">{fp(q3_np_g*100)}</div><div class="s">H1 {fp(h1_np_g*100)} → Q3 {fp(q3_np_g*100)}</div></div>
    <div class="box"><div class="k">Q3 净利率</div><div class="v">{q3_margin*100:.1f}%</div><div class="s">H1 为 {h1_margin*100:.1f}%，压缩 {(h1_margin-q3_margin)*100:.1f}pp</div></div>
  </div>
  <div id="g-growth" class="chart"></div>
  <p class="chart-note">营收增速（+61.8%）远高于净利增速（+32.3%），说明增长更多来自“量”和低毛利业务；中位股净利增速从 H1 的 {fp(h1_med*100)} 掉到 Q3 的 {fp(q3_med*100)}。</p>

  <div class="callout red"><b>增长高度集中：</b>中际旭创贡献 +{m.loc[m.code=='300308','contrib'].iloc[0]*100:.1f}pp、宁德时代 +{m.loc[m.code=='300750','contrib'].iloc[0]*100:.1f}pp、新易盛 +{m.loc[m.code=='300502','contrib'].iloc[0]*100:.1f}pp，三者合计 <b>+{top3_contrib:.1f}pp</b>，正好等于指数的 {fp(q3_np_g*100)}。其余 73 只合计 <b>{fp(q3_np_g_ex3*100)}</b>。</div>

  <div class="grid2">
    <div>
      <h3>谁在贡献增长，谁在拖后腿</h3>
      <div id="g-contrib" class="chart tall"></div>
      <p class="chart-note">单位：对 Q3 单季净利增速的贡献（pp）。仅列正向前 10 + 负向前 5。</p>
    </div>
    <div>
      <h3>增速分布：一半公司在收缩</h3>
      <div id="g-dist" class="chart tall"></div>
      <p class="chart-note">{pos_cnt}/76 家正增长（权重 {pos_w:.1f}%），{76-pos_cnt}/76 家负增长（权重 {neg_w:.1f}%）；只有 {acc_cnt}/76 家 Q3 增速快于 H1。</p>
    </div>
  </div>

  <h3>前 12 大持仓：权重、增速与贡献</h3>
  <div class="tbl-wrap" style="max-height:480px">
    <table>
      <thead><tr><th>持仓</th><th>权重</th><th>Q3 净利增速</th><th>H1 净利增速</th><th>PE-TTM</th><th>Q3 贡献</th></tr></thead>
      <tbody>{growth_rows}</tbody>
    </table>
  </div>
  <p class="src">注：Q3 单季 = 2026 前三季 − 2026 上半年；增速为单季同比。权重为 159915 2026 Q3 披露的占净值比例，合计 87.5%（其余为现金/其他资产）。</p>

  <h3 style="margin-top:24px">全部 76 只持仓（可搜索 / 排序）</h3>
  <div class="toolbar">
    <input id="q" placeholder="搜索名称或代码" autocomplete="off">
    <button data-sort="weight" class="on">按权重</button>
    <button data-sort="q3">按 Q3 增速</button>
    <button data-sort="pe">按 PE</button>
    <span class="sp"></span><span id="stock-count" class="tick">76 / 76 只</span>
  </div>
  <div class="tbl-wrap" style="max-height:620px">
    <table style="min-width:980px">
      <thead><tr>
        <th>#</th><th>名称 / 代码</th><th>行业</th><th data-sort="weight">权重</th>
        <th data-sort="pe">PE</th><th>PB</th><th data-sort="q3">Q3 增速</th>
        <th data-sort="m9">前三季</th><th>PEG*</th><th data-sort="contrib">Q3 贡献</th><th>标签</th>
      </tr></thead>
      <tbody id="stock-rows"></tbody>
    </table>
  </div>
  <p class="src">PE 为 TTM；亏损公司 PE 显示“亏损”。PEG* = PE / Q3 增速（仅对正增长公司计算，上限 9.99；单季增速波动大，PEG 仅供参考）。点击表头或上方按钮切换排序。</p>
</div>

<div class="card">
  <h2><span class="no">3</span>估值：PE 很低，但 PB 和“正常化盈利”不低</h2>
  <p class="lede">同一个指数，四个估值镜头给出的答案并不一样。低 PE 不是没有原因。</p>
  <div class="grid2">
    <div class="box"><div class="k">TTM PE（官方 399006）</div><div class="v bl">{cur_pe:.1f}x</div><div class="s">2010 年以来 {pe_pct:.1f}% 分位 · 近 5 年 {pe_pct5:.1f}% 分位</div></div>
    <div class="box"><div class="k">PB（官方 399006）</div><div class="v">{cur_pb:.1f}x</div><div class="s">历史 {pb_pct:.0f}% 分位 · 2024 低点 3.18x</div></div>
    <div class="box"><div class="k">正常化 PE（当前价 / 2024 年利润）</div><div class="v a">{pe2024:.1f}x</div><div class="s">用 2025 年利润算 {pe2025:.1f}x；用 TTM 算 {agg_pe:.1f}x</div></div>
    <div class="box"><div class="k">成分股 PE 中位数</div><div class="v r">{median_pe:.1f}x</div><div class="s">等权 PE 48.8x；指数 PE 被三只巨头拉低</div></div>
  </div>
  <div id="g-pe" class="chart"></div>
  <p class="chart-note">PE-TTM 月度序列，2010-06 至 2026-10-30。绿色区域为 PE&lt;30；当前 {cur_pe:.1f}x 仅高于 2024 年的 22.1–22.7x 低点区域。</p>

  <div class="grid2" style="margin-top:10px">
    <div>
      <h3>PE = PB / ROE：低 PE 是高 ROE 造出来的</h3>
      <div id="g-pbroe" class="chart"></div>
      <p class="chart-note">每个点是一个月。现在 ROE {cur_roe:.1f}%（历史最高），PB {cur_pb:.1f}x；2024 低点是 ROE 14.4%、PB 3.18x。ROE 回到 14%，同样的 PB 对应 PE 约 {cur_pb/0.14:.0f}x。</p>
    </div>
    <div>
      <h3>相对沪深300：{rel_cur_ratio:.2f}x，历史 0.5% 分位</h3>
      <div id="g-relative" class="chart"></div>
      <p class="chart-note">创业板 PE / 沪深300 PE 当前 {rel_cur_ratio:.2f}x，历史中位数 {rel_med:.2f}x。这是“相对便宜”的最强证据，也说明市场不再给创业板成长溢价。</p>
    </div>
  </div>

  <h3>估值分位：不同口径，差异很大</h3>
  <div class="tbl-wrap" style="max-height:none">
    <table>
      <thead><tr><th>指标</th><th>当前</th><th>全历史</th><th>近 10 年</th><th>近 5 年</th><th>读法</th></tr></thead>
      <tbody>
        <tr><td><b>PE-TTM（市值加权）</b></td><td>{cur_pe:.1f}x</td><td class="g">{pe_pct:.1f}%</td><td class="g">{pe_pct10:.1f}%</td><td class="g">{pe_pct5:.1f}%</td><td>历史级便宜</td></tr>
        <tr><td><b>PB（市值加权）</b></td><td>{cur_pb:.1f}x</td><td>{pb_pct:.1f}%</td><td>{pb_pct10:.1f}%</td><td>{pb_pct5:.1f}%</td><td>不贵，但离地板还有距离</td></tr>
        <tr><td><b>PE / 2024 年盈利</b></td><td>{pe2024:.1f}x</td><td>—</td><td>—</td><td>—</td><td>盈利正常化后并不便宜</td></tr>
        <tr><td><b>成分股 PE 中位数</b></td><td>{median_pe:.1f}x</td><td>—</td><td>—</td><td>—</td><td>典型成分股 30 倍以上</td></tr>
        <tr><td><b>创业板 / 沪深300 PE</b></td><td>{rel_cur_ratio:.2f}x</td><td class="g">{rel_pct:.1f}%</td><td>—</td><td>—</td><td>相对大盘历史级便宜</td></tr>
      </tbody>
    </table>
  </div>
  <div class="callout blue"><b>把四个数字放在一起：</b>PE {cur_pe:.1f}x 是“权重股便宜”，PB {cur_pb:.1f}x 是“资产不便宜”，正常化 PE {pe2024:.1f}x 是“盈利在周期高位”，中位股 {median_pe:.1f}x 是“典型股票不便宜”。所以不是全面便宜，而是<b>三只低估值巨头 + 一群 30–50 倍小盘</b>的加权平均。</div>
  <p class="src">Top3（宁德/中际/新易盛）权重 {top3_w:.1f}%、TTM 利润占比 {top3_np_share*100:.1f}%，PE {top3_pe:.1f}x；其余 73 只 PE {ex3_pe:.1f}x。</p>
</div>

<div class="card">
  <h2><span class="no">4</span>便宜是怎么来的：股价没涨，盈利把估值消化了</h2>
  <p class="lede">这不是“杀资产”，是“杀估值 + 盈利兑现”。但市场杀的是未来的盈利，不是过去的盈利。</p>
  <div id="g-price-eps" class="chart"></div>
  <div class="grid3" style="margin-top:6px">
    <div class="box"><div class="k">2024 年底 → 现在</div><div class="v g">+{(last_close/2141.6-1)*100:.1f}%</div><div class="s">指数涨幅；隐含 EPS +{(val['e'].iloc[-1]/val.loc[val.date=='2024-12-31','e'].iloc[0]-1)*100:.1f}%，PE 31.9x → {cur_pe:.1f}x</div></div>
    <div class="box"><div class="k">6/25 高点 → 现在</div><div class="v r">{fp(dd*100)}</div><div class="s">127 天；PE 48.0x → {cur_pe:.1f}x（{fp((cur_pe/47.95-1)*100)}）</div></div>
    <div class="box"><div class="k">盈利（TTM，76 只持仓）</div><div class="v">{ttm_sum:,.0f} 亿</div><div class="s">2024 年 {np2024_sum:,.0f} 亿 → 2025 年 {np2025_sum:,.0f} 亿 → TTM {ttm_sum:,.0f} 亿</div></div>
  </div>
  <div class="callout"><b>关键差别：</b>2024 年底到现在，指数只涨了 {(last_close/2141.6-1)*100:.1f}%，但隐含 EPS 涨了 {(val['e'].iloc[-1]/val.loc[val.date=='2024-12-31','e'].iloc[0]-1)*100:.1f}%，PE 从 31.9x 降到 {cur_pe:.1f}x。6 月高点以来则相反：指数 {fp(dd*100)}，EPS 还在涨（+{(val['e'].iloc[-1]/val.loc[val.date=='2026-06-30','e'].iloc[0]-1)*100:.1f}%），跌的全是估值。</div>
</div>

<div class="card">
  <h2><span class="no">5</span>历史经验：低 PE 之后发生过什么</h2>
  <p class="lede">把过去 16 年几次“低 PE / 深回撤”拉出来对照。结论不是“这次一定涨”，而是“赔率站在你这边，但需要时间”。</p>
  <div class="tbl-wrap" style="max-height:none">
    <table>
      <thead><tr><th>时点</th><th>指数</th><th>PE</th><th>PB</th><th>隐含 ROE</th><th>之后 12 个月</th></tr></thead>
      <tbody>{analog_rows}</tbody>
    </table>
  </div>
  <div id="g-forward" class="chart short"></div>
  <p class="chart-note">按月末 PE 分组，统计之后 12 个月收益中位数与胜率；样本为 2010-06 至 2026-10 的月度数据，存在重叠，不是独立样本。</p>
  <div class="rule"><div class="rn">1</div><div><b>低 PE 不等于马上涨。</b>2012-11、2018-12、2024-01 三次低点后，都先磨了几个月，12 个月才兑现；当前 20 日线还在 2,800，趋势没转。</div></div>
  <div class="rule"><div class="rn">2</div><div><b>PB 比 PE 更诚实。</b>2022-10 PE 34.1x 看着不高，但 PB 4.98x、ROE 14.6%，之后 12 个月 -13%；现在 PB {cur_pb:.1f}x 比那时低，但比 2024 年的 3.18x 高。</div></div>
  <div class="rule"><div class="rn">3</div><div><b>盈利方向决定一切。</b>2012/2018/2024 的低 PE 后面盈利都企稳或回升；2022 的低 PE 后面盈利继续下修。当前盈利还在增长，但 Q3 已从 +59.9% 减速到 +32.3%，这是最大的不确定。</div></div>
  <div class="callout blue"><b>PE&lt;30 的 23 个完整月度样本里，22 次 12 个月正收益，中位 +25.2%。</b>唯一失败是 2023-08（PE 29.6x，之后盈利下修，12 个月 -24.8%）。样本少、重叠多，别把 96% 当成胜率保证；它只说明一件事：在这个估值买，长期赔率不差。</div>
</div>

<div class="card">
  <h2><span class="no">6</span>未来 12 个月：四种情景与概率</h2>
  <p class="lede">用“EPS × PE”做情景，不给单点预测。概率是主观赔率排序，不是精确预测。</p>
  <div class="scen">{scen_html}</div>
  <div class="grid3" style="margin-top:14px">
    <div class="box"><div class="k">概率加权期望</div><div class="v {cls(exp_ret*100)}">{fp(exp_ret*100)}</div><div class="s">12 个月，按上表概率加权</div></div>
    <div class="box"><div class="k">正收益概率</div><div class="v g">70%</div><div class="s">A+B；但 B 只有 +12% 左右</div></div>
    <div class="box"><div class="k">再探底概率</div><div class="v a">30%</div><div class="s">C+D；D 概率低但损失大</div></div>
  </div>
  <div class="callout"><b>短期（1–3 个月）：</b>10/30 放量 2.5 倍、单日 -4.1%，超跌反弹概率约 60%；但 20 日线 2,800 没站上之前，反弹都先按“下跌中继”处理。不要用“PE 低”去接飞刀，等价格给确认。</div>
</div>

<div class="card">
  <h2><span class="no">7</span>3% 仓位怎么办：一套可执行的规则</h2>
  <p class="lede">3% 是很小的仓位。最大的风险不是这点仓位亏钱，而是“因为便宜”把它加成重仓。</p>
  <div class="callout blue"><b>当前判断：</b>持有 3%，不加。理由：估值便宜（PE {cur_pe:.1f}x / {pe_pct:.1f}% 分位），但趋势没止跌（低于 200 日线 {abs(dist_ma200)*100:.0f}%）、Q3 增速腰斩、Top3 占 {top3_w:.1f}%。现在加仓是“猜底”，不是“配置”。</div>
  {ladder}
  <h3 style="margin-top:18px">为什么不在 -45% 割，也不现在满仓</h3>
  <div class="rule"><div class="rn">1</div><div><b>不在 -45% 割：</b>3% 仓位即使再跌 30%，对总组合只有 -0.9%；但在 PE 历史 {pe_pct:.1f}% 分位割掉，失去的是未来 12 个月 70% 概率的正收益。除非 thesis 破了（见下），否则割在这里是情绪操作。</div></div>
  <div class="rule"><div class="rn">2</div><div><b>不现在满仓：</b>指数低于 200 日线 {abs(dist_ma200)*100:.0f}%、20 日线还在往下、Q3 增速从 +59.9% 掉到 +32.3%。估值便宜可以让你“不卖”，但不能让你“买在下跌趋势里”。</div></div>
  <div class="rule"><div class="rn">3</div><div><b>加仓只加两档：</b>2,150–2,200（PE≈21，接近 2024 低点估值）和 1,850–1,950（PE≈18，PB 接近 2024 低点 3.1x）。每档 1%，上限 6%。</div></div>
  <div class="rule"><div class="rn">4</div><div><b>减仓看估值，不看成本：</b>反弹到 3,200–3,400（PE 31–33）减 1%；3,800 点以上（PE≈37）减到 1–2%。不要因为“回本了”就卖，也不要因为“还亏”就不卖。</div></div>
  <h3>什么情况说明 thesis 破了（无条件减仓）</h3>
  <div class="rule"><div class="rn">!</div><div>中际/新易盛 Q4 单季净利环比下滑 &gt;20%，或北美云厂 2027 capex guidance 明显下修；</div></div>
  <div class="rule"><div class="rn">!</div><div>宁德时代毛利率跌破 20%，或出现明确价格战；</div></div>
  <div class="rule"><div class="rn">!</div><div>指数跌破 2,200 后 2 周内收不回来，且 Q4 Top3 增速 &lt;10%；</div></div>
  <div class="rule"><div class="rn">!</div><div>AI 硬件出口/贸易限制直接冲击光模块订单。</div></div>
  <h3>不要做的事</h3>
  <div class="rule"><div class="rn">×</div><div>不要因为“PE 历史最低”一次加到 10% 以上——指数 PE 低是因为 Top3 利润占一半，不是整个创业板便宜。</div></div>
  <div class="rule"><div class="rn">×</div><div>不要用杠杆/融资盘去接；-45% 之后波动率仍在高位，杠杆会先把你洗出去。</div></div>
  <div class="rule"><div class="rn">×</div><div>不要把“反弹 10%”当成反转；先看能否站上 2,800（20 日线）和 3,220（60 日线）。</div></div>
</div>

<div class="card">
  <h2><span class="no">8</span>数据与口径</h2>
  <div class="foot">
    <p><b>指数：</b>创业板指 399006，收盘/成交额来自国证指数（cnindex），2026-10-30 收盘 2,413.63；ETF 为易方达创业板ETF 159915，10/30 收盘 2.435，规模约 886 亿元（腾讯行情口径），距 52 周高点 -44.6%。</p>
    <p><b>成分/持仓：</b>ETF 2026 Q3 披露持仓 76 只，合计占净值 87.5%；权重为占净值比例，未归一化。指数前 10 权重来自国证指数 2026-10-29 样本数据。</p>
    <p><b>财务：</b>2026 三季报、2026 半年报、2025 三季报/半年报、2025 年报、2024 年报，东方财富业绩报表；单三季度 = 前三季 − 上半年；TTM = 2025 年报 + 2026 前三季 − 2025 前三季。76/76 持仓均已披露 2026 三季报。</p>
    <p><b>估值：</b>PE-TTM / PB 为乐咕乐股 399006 月度序列（2010-06 起）；10/30 PE/PB 按指数当日涨跌从 10/29 折算，为估算值。分位为“历史序列中 ≤ 当前值的比例”，含当前点。PE/2024 盈利、PE/2025 盈利为“当前总市值 ÷ 对应年度净利润”，与官方加权 PE 口径略有差异。</p>
    <p><b>行情/个股：</b>个股 PE-TTM、PB、市值来自腾讯行情 2026-10-30 收盘；历史条件收益用月度收盘，2010-06 至 2026-10，样本存在重叠，仅供赔率参考。</p>
    <p><b>局限：</b>① ETF 持仓为 Q3 末披露，10 月价格变动后实际权重已变化；② 单季增速在低基数/亏损转正时会被放大，表内已用“亏损/负增长”标注；③ 历史只有 16 年、两轮半牛熊，条件样本小；④ 本文是数据研究，不构成投资建议。</p>
  </div>
</div>
'''

# 修正：content 里引用了 top3_contrib / ai_w 在定义前，先重排（Python 顺序执行）

# ---------------------------------------------------------------- 图表数据打包
growth = {
    "cats": ["2026 H1", "2026 Q3", "2026 前三季"],
    "rev": [round(h1_rev_g * 100, 1), round(q3_rev_g * 100, 1), round(m9_rev_g * 100, 1)],
    "np": [round(h1_np_g * 100, 1), round(q3_np_g * 100, 1), round(m9_np_g * 100, 1)],
    "med": [round(h1_med * 100, 1), round(q3_med * 100, 1), round(m9_med * 100, 1)],
}

chart_data = {
    "growth": growth,
    "contrib": contrib,
    "dist": {"cats": [d["cat"] for d in dist], "count": [d["count"] for d in dist], "weight": [d["weight"] for d in dist]},
    "pe": pe_chart,
    "pbroe": pbroe,
    "pbroe_now": {
        "roe": round(cur_roe, 2), "pb": round(cur_pb, 2),
        "d": last_date.strftime("%Y-%m-%d"), "pe": round(cur_pe, 2),
    },
    "price_eps": price_eps,
    "forward": forward,
    "relative": [{"d": x.date.strftime("%Y-%m-%d"), "ratio": round(float(x.ratio), 3)} for x in rel[rel.date >= "2010-06-01"].itertuples()],
    "stocks": stocks,
}

# ---------------------------------------------------------------- 渲染
with open(os.path.join(HERE, "template.html"), encoding="utf-8") as f:
    html = f.read()
html = html.replace("__CONTENT__", content)
html = html.replace("__DATA__", json.dumps(chart_data, ensure_ascii=False, separators=(",", ":")))
out = os.path.join(HERE, "index.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("written", out, round(len(html) / 1024), "KB")
print("index", last_date.date(), last_close, "PE", round(cur_pe, 2), "PB", round(cur_pb, 2))
print("Q3 np", round(q3_np_g * 100, 1), "H1", round(h1_np_g * 100, 1), "ex-top3", round(q3_np_g_ex3 * 100, 1))
print("scenarios", [(s["key"], s["prob"], round(s["ret"] * 100, 1)) for s in scen], "expected", round(exp_ret * 100, 1))
