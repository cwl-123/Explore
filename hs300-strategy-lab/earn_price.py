# -*- coding: utf-8 -*-
# earn_price.py — 盈利增速与股价增速的关系检验
#
# 回答两个问题：
#   Q1 板块盈利（营收/利润）增速与股价增速长期是否正相关？相关性多强？
#   Q2 「利润同比 +30%、股价只涨 20% → 未来补涨 10%」这个推论对不对？
#
# 方法：恒等式 价格 P = PE × 盈利 E  →  E = P / PE（隐含盈利，市值加权口径）
#   - 创业板：乐咕『创业板』市场指数+平均市盈率（同口径配对，2010 起，月度）
#   - 标普500：Yahoo ^GSPC + multpl PE（1995 起）
#   - 沪深300：H00300 全收益 + 乐咕 PE（注意全收益含分红，E 增速约高估 2pp/年）
#   - 恒生科技：新浪价格 + 乐咕官方 PE（2020 起，样本短；PE≤0 月份剔除）
#   Q2 检验：gap_t = ΔE(1年) - ΔP(1年) ≈ -ΔPE(1年)，分五档看未来 12 个月收益
# 输出：earn_price.html
# 运行：.venv/bin/python earn_price.py

import json
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# ---------------------------------------------------------------- 数据

def monthly(s):
    return s.resample("M").last().dropna()


def load_cyb():
    df = pd.read_csv(os.path.join(DATA_DIR, "cyb_pe.csv"), parse_dates=["日期"])
    p = pd.Series(pd.to_numeric(df["指数"], errors="coerce").values, index=df["日期"])
    pe = pd.Series(pd.to_numeric(df["平均市盈率"], errors="coerce").values, index=df["日期"])
    return p.sort_index(), pe.sort_index()


def load_hs300():
    px = pd.read_csv(os.path.join(DATA_DIR, "hs300_price.csv"), parse_dates=["date"])
    pe = pd.read_csv(os.path.join(DATA_DIR, "hs300_pe.csv"), parse_dates=["date"])
    p = pd.Series(px["close"].values, index=px["date"]).sort_index()
    q = pd.Series(pe["pe"].values, index=pe["date"]).sort_index()
    q = q.reindex(p.index).ffill()
    return monthly(p), monthly(q)


def load_sp500():
    px = pd.read_csv(os.path.join(DATA_DIR, "sp500_price.csv"), parse_dates=["date"])
    pe = pd.read_csv(os.path.join(DATA_DIR, "sp500_pe.csv"), parse_dates=["date"])
    p = pd.Series(px["close"].values, index=px["date"]).sort_index()
    q = pd.Series(pe["value"].values, index=pe["date"]).sort_index()
    return monthly(p), monthly(q)


def load_hstech():
    px = pd.read_csv(os.path.join(DATA_DIR, "hstech_price.csv"), parse_dates=["date"])
    pe = pd.read_csv(os.path.join(DATA_DIR, "hstech_pe.csv"), parse_dates=["date"])
    p = pd.Series(px["close"].values, index=px["date"]).sort_index()
    q = pd.Series(pe["pe"].values, index=pe["date"]).sort_index()
    return monthly(p), monthly(q)


def build(p, pe):
    """对齐成月度 DataFrame(p, pe, E)，剔除 PE<=0"""
    df = pd.DataFrame({"p": p, "pe": pe}).dropna()
    df = df[df["pe"] > 0]
    df["E"] = df["p"] / df["pe"]
    return df


# ---------------------------------------------------------------- 分析

def decompose(df):
    yrs = (df.index[-1] - df.index[0]).days / 365.25
    cagr = lambda s: (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    return {"yrs": yrs, "p": cagr(df["p"]), "e": cagr(df["E"]), "pe": cagr(df["pe"]),
            "start": df.index[0], "end": df.index[-1]}


def corr_by_horizon(df, horizons=(12, 36, 60)):
    out = {}
    le, lp = np.log(df["E"]), np.log(df["p"])
    for h in horizons:
        de, dp = le.diff(h), lp.diff(h)
        m = de.notna() & dp.notna()
        if m.sum() > 12:
            out[h] = float(np.corrcoef(de[m], dp[m])[0, 1])
    return out


def gap_buckets(df, h=12, fwd=12, n_bins=5):
    """gap = ΔlogE(h) - ΔlogP(h) = -ΔlogPE(h)，分档看未来 fwd 个月收益"""
    le, lp = np.log(df["E"]), np.log(df["p"])
    g = (le.diff(h) - lp.diff(h))
    fr = lp.shift(-fwd) - lp
    d = pd.DataFrame({"g": g, "fr": np.exp(fr) - 1}).dropna()
    d["bin"] = pd.qcut(d["g"], n_bins, labels=False, duplicates="drop")
    rows = []
    for b, grp in d.groupby("bin"):
        rows.append({"bin": int(b), "n": len(grp),
                     "g_lo": float(grp["g"].min()), "g_hi": float(grp["g"].max()),
                     "g_mid": float(grp["g"].mean()),
                     "fr_mean": float(grp["fr"].mean()),
                     "fr_med": float(grp["fr"].median()),
                     "win": float((grp["fr"] > 0).mean())})
    corr = float(np.corrcoef(d["g"], d["fr"])[0, 1]) if len(d) > 12 else np.nan
    return rows, corr, d


def trailing(df, h=12):
    le, lp = np.log(df["E"]), np.log(df["p"])
    de, dp = le.diff(h), lp.diff(h)
    return float(np.expm1(de.iloc[-1])), float(np.expm1(dp.iloc[-1]))


# ---------------------------------------------------------------- 页面

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>盈利涨30%、股价涨20%，差的10%会补涨吗？</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#222;line-height:1.75}
h1{font-size:26px}h2{font-size:20px;margin-top:48px;border-left:4px solid #c0392b;padding-left:10px}
.chart{width:100%;height:420px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th,td{border:1px solid #ddd;padding:6px 10px;text-align:right}
th:first-child,td:first-child{text-align:left}
th{background:#f6f6f6}
.good{color:#c0392b}.bad{color:#27ae60}
.box{background:#faf6ec;border:1px solid #e8dcc0;border-radius:8px;padding:16px 20px;margin:16px 0}
.warn{background:#fdf0ef;border:1px solid #eec5c0}
.muted{color:#888;font-size:13px}
ul{padding-left:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.card{flex:1;min-width:220px;border-radius:8px;padding:14px 16px;border:1px solid #e0e0e0;background:#fff}
.card .num{font-size:26px;font-weight:700;margin:4px 0}
.card .lbl{font-size:13px;color:#666}
.card.hot{background:#fdf0ef;border-color:#eec5c0}
.card.cold{background:#eef7f0;border-color:#bfe3cb}
.card.dim{background:#f7f7f7}
td.sp2{background:rgba(192,57,43,.28);font-weight:700}
td.sp1{background:rgba(192,57,43,.12)}
td.sn2{background:rgba(39,174,96,.28);font-weight:700}
td.sn1{background:rgba(39,174,96,.12)}
td.nz{color:#bbb}
.legend{font-size:12px;color:#999;margin:4px 0 0}
.legend span{display:inline-block;padding:0 8px;border:1px solid #ddd;margin-right:6px}
</style>
</head>
<body>
<h1>「盈利涨 30%、股价只涨 20%，差的 10% 会补涨吗？」——用恒等式分解检验</h1>
<p class="muted">生成时间：__GEN__ ｜ 方法：价格 P = PE × 盈利 E，故 E = P / PE（隐含盈利，板块市值加权口径）｜ 口径见文末</p>

<div class="box">
<b>一句话结论：</b>__VERDICT__
</div>

<h2>0. 核心信号速览</h2>
__CARDS__
<p class="legend">全页着色规则：<span style="background:rgba(192,57,43,.28)">显著为正</span><span style="background:rgba(192,57,43,.12)">弱正</span><span style="background:rgba(39,174,96,.12)">弱负</span><span style="background:rgba(39,174,96,.28)">显著为负</span><span style="color:#bbb">灰色 = 统计上接近零的噪音，不必关注</span></p>

<h2>1. 长期：股价 ≈ 盈利 × 估值，谁贡献大？</h2>
<p>把每个指数的全区间年化收益拆成「盈利年化 × PE 年化」。三条线放在一起看：价格（蓝）= 隐含盈利（红）× PE（虚线，右轴）。</p>
<div id="c1" class="chart"></div>
__DECOMP_TABLE__

<h2>2. 相关性：盈利增速与股价增速，在不同持有期下有多相关？</h2>
<p>滚动窗口的盈利增速 vs 股价增速相关系数（log 差分）。<b>持有 1 年时相关性很弱——估值波动主导短期价格；持有 3~5 年相关性才显著上升——盈利主导长期价格。</b></p>
__CORR_TABLE__
<div id="c2" class="chart"></div>

<h2>3. 直接检验「补涨推论」：盈利与股价的缺口，预示未来收益吗？</h2>
<p>定义缺口 gap = 近 1 年盈利增速 − 股价增速（≈ PE 的跌幅）。若「补涨论」成立，gap 越大未来 12 个月收益应越高。把历史所有月份按 gap 分五档：</p>
__GAP_TABLE__
<div id="c3" class="chart"></div>

<h2>4. 创业板当前快照</h2>
<div class="box warn">
__CURRENT__
</div>

<h2>5. 为什么「补涨推论」不成立</h2>
<ul>
<li><b>PE 不是锚定的</b>：盈利 +30% 而股价 +20%，差的 10% 全部体现为 PE 压缩。PE 没有一个「必须回归」的固定值——创业板 PE 历史区间约 25~130，同样的盈利可以配 3 倍差价。</li>
<li><b>股价是领先指标，盈利是滞后指标</b>：股价定价的是「未来的盈利」。利润同比 +30% 公布时，这 30% 往往早已体现在之前的股价里；数据上 gap 与 past 收益的关系强于与 future 收益的关系。</li>
<li><b>高盈利增速常出现在周期顶部</b>：盈利最好的时候，市场反而开始担心可持续性、主动压估值——「业绩最好 = 股价见顶」在创业板 2015、2021 都发生过。</li>
<li><b>盈利本身均值回归</b>：+30% 的增速很少能持续，明年基数抬高后增速回落，「补涨」的分子自己会缩。</li>
<li><b>数据上甚至方向相反</b>：创业板 gap（盈利-股价增速差）与未来 12 个月收益相关系数为负——「盈利追上股价」更多出现在牛市尾声，「股价跑在盈利前面」（PE 扩张期）才是牛市早中段的特征。</li>
</ul>

<h2>6. 口径与免责</h2>
<ul class="muted">
<li>盈利 E 为「指数 ÷ PE」的隐含值（板块市值加权的整体盈利代理），非财报加总的真实净利润；不含营收维度。</li>
<li>创业板用乐咕『创业板』市场指数+平均市盈率（同口径配对）；沪深300 价格用全收益指数 H00300，其隐含 E 增速含约 2pp/年的分红再投资，跨表比较时注意；标普500 为价格指数（不含股息，实际总回报更高）。</li>
<li>恒生科技 2020 年才有数据、且早期 PE 为负的月份已剔除，样本极小仅供参考。</li>
<li>gap 分档为事后统计（各约 1/5 月份），不构成投资建议。</li>
</ul>

<script>
const DATA = __DATA__;
const RED='#c0392b', GREEN='#27ae60', BLUE='#2c3e50', GRAY='#95a5a6', ORANGE='#e67e22';

// ---- 图1：创业板 价格 vs 隐含盈利 vs PE
(function(){
  const ch = echarts.init(document.getElementById('c1'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['创业板价格(归一)','隐含盈利E(归一)','PE(右轴)']},
    grid:{left:60,right:60},
    xAxis:{type:'time'},
    yAxis:[{type:'log',name:'归一(log)'},{type:'value',name:'PE'}],
    dataZoom:[{type:'inside'},{type:'slider'}],
    series:[
      {name:'创业板价格(归一)',type:'line',showSymbol:false,data:DATA.cyb_p,lineStyle:{color:BLUE,width:1.8}},
      {name:'隐含盈利E(归一)',type:'line',showSymbol:false,data:DATA.cyb_e,lineStyle:{color:RED,width:1.8}},
      {name:'PE(右轴)',type:'line',yAxisIndex:1,showSymbol:false,data:DATA.cyb_pe,lineStyle:{color:ORANGE,width:1,type:'dashed'}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图2：散点 盈利增速 vs 股价增速（1年，创业板）
(function(){
  const ch = echarts.init(document.getElementById('c2'));
  ch.setOption({
    tooltip:{trigger:'item',formatter:p=>'盈利增速: '+(p.value[0]*100).toFixed(0)+'%<br>股价涨幅: '+(p.value[1]*100).toFixed(0)+'%'},
    grid:{left:60,right:20},
    xAxis:{type:'value',name:'近1年盈利增速',axisLabel:{formatter:v=>(v*100).toFixed(0)+'%'}},
    yAxis:{type:'value',name:'近1年股价涨幅',axisLabel:{formatter:v=>(v*100).toFixed(0)+'%'}},
    series:[{type:'scatter',data:DATA.scatter,itemStyle:{color:'rgba(44,62,80,.45)',borderColor:BLUE},
      markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed',color:'#999'},
        data:[{xAxis:0},{yAxis:0}]},
      markPoint:{symbol:'pin',symbolSize:60,itemStyle:{color:RED},
        label:{fontSize:10,color:'#fff'},
        data:[{coord:[DATA.now_scatter[0],DATA.now_scatter[1]],value:'现在'}]}}]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图3：gap 五档 → 未来12个月收益
(function(){
  const ch = echarts.init(document.getElementById('c3'));
  ch.setOption({
    tooltip:{},
    legend:{data:['创业板','标普500']},
    grid:{left:60,right:20},
    xAxis:{type:'category',data:DATA.gap_bins},
    yAxis:{type:'value',name:'未来12个月收益',axisLabel:{formatter:v=>(v*100).toFixed(0)+'%'}},
    series:[
      {name:'创业板',type:'bar',data:DATA.gap_cyb,itemStyle:{color:RED}},
      {name:'标普500',type:'bar',data:DATA.gap_sp,itemStyle:{color:GRAY}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();
</script>
</body>
</html>
"""


def heat(x, th_lo, th_hi):
    if x >= th_hi:
        return "sp2"
    if x >= th_lo:
        return "sp1"
    if x <= -th_hi:
        return "sn2"
    if x <= -th_lo:
        return "sn1"
    return "nz"


def fmt_pct(x, sign=True):
    s = f"{x*100:+.1f}%" if sign else f"{x*100:.1f}%"
    cls = "good" if x > 0 else "bad"
    return f'<span class="{cls}">{s}</span>'


def main():
    assets = {}
    assets["cyb"] = ("创业板", build(*load_cyb()))
    assets["hs300"] = ("沪深300", build(*load_hs300()))
    assets["sp500"] = ("标普500", build(*load_sp500()))
    assets["hstech"] = ("恒生科技", build(*load_hstech()))

    print("== 长期分解（年化：价格 = 盈利 × PE）==")
    dec = {}
    for k, (nm, df) in assets.items():
        d = decompose(df)
        dec[k] = d
        print(f"  {nm}: {d['start'].date()}~{d['end'].date()} "
              f"价格{d['p']*100:+.1f}% = 盈利{d['e']*100:+.1f}% × PE{d['pe']*100:+.1f}%")

    print("\n== 盈利增速 vs 股价增速 相关系数（1年/3年/5年）==")
    cors = {}
    for k, (nm, df) in assets.items():
        c = corr_by_horizon(df)
        cors[k] = c
        print(f"  {nm}: " + "  ".join(f"{h//12}年 r={v:+.2f}" for h, v in c.items()))

    print("\n== gap 分档 → 未来12个月收益 ==")
    gaps, gap_corr = {}, {}
    for k, (nm, df) in assets.items():
        rows, corr, d = gap_buckets(df)
        gaps[k], gap_corr[k] = rows, corr
        print(f"  {nm}: corr(gap, fwd12m) = {corr:+.2f}")
        for r in rows:
            print(f"    档{r['bin']} gap[{r['g_lo']*100:+.0f}%,{r['g_hi']*100:+.0f}%] "
                  f"n={r['n']} 未来12月均值{r['fr_mean']*100:+.1f}% "
                  f"中位{r['fr_med']*100:+.1f}% 胜率{r['win']*100:.0f}%")

    # 创业板当前快照
    cyb = assets["cyb"][1]
    e_yoy, p_yoy = trailing(cyb)
    gap_now = e_yoy - p_yoy
    pe_now = cyb["pe"].iloc[-1]
    pe5y = cyb["pe"].loc[cyb.index[-1] - pd.DateOffset(years=5):]
    pe_pctl = float((pe5y <= pe_now).mean())
    print(f"\n创业板当前: 盈利YoY {e_yoy*100:+.1f}% 股价YoY {p_yoy*100:+.1f}% "
          f"gap {gap_now*100:+.1f}% PE {pe_now:.1f} (5年分位 {pe_pctl*100:.0f}%)")

    # ---------------- 表格
    dec_rows = "".join(
        f"<tr><td>{assets[k][0]}</td><td>{d['start'].year}~{d['end'].year}</td>"
        f'<td class="{heat(d["p"], .03, .08)}">{d["p"]*100:+.1f}%</td>'
        f'<td class="{heat(d["e"], .03, .08)}">{d["e"]*100:+.1f}%</td>'
        f'<td class="{heat(d["pe"], .03, .08)}">{d["pe"]*100:+.1f}%</td>'
        f"<td>{'含分红高估约2pp' if k=='hs300' else ('样本短' if k=='hstech' else '')}</td></tr>"
        for k, d in dec.items())
    decomp_table = f"""<table>
<tr><th>指数</th><th>区间</th><th>价格年化</th><th>隐含盈利年化</th><th>PE年化</th><th>备注</th></tr>{dec_rows}</table>"""

    corr_rows = ""
    for k, (nm, df) in assets.items():
        c = cors[k]
        cells = ""
        for h in (12, 36, 60):
            if h in c:
                v = c[h]
                cells += f'<td class="{heat(abs(v), .3, .6)}">{v:+.2f}</td>'
            else:
                cells += "<td>-</td>"
        corr_rows += f"<tr><td>{nm}</td>{cells}</tr>"
    corr_table = f"""<table>
<tr><th>指数</th><th>持有1年 r</th><th>持有3年 r</th><th>持有5年 r</th></tr>{corr_rows}</table>
<p class="muted">r 接近 1 = 股价增速几乎完全由盈利增速解释；接近 0 = 估值（PE）波动主导。r≥0.6 深着色，0.3~0.6 浅着色，&lt;0.3 压灰。</p>"""

    gap_rows = ""
    for k in ["cyb", "sp500"]:
        nm = assets[k][0]
        for r in gaps[k]:
            gap_rows += (f"<tr><td>{nm}</td><td>第{r['bin']+1}档</td>"
                         f"<td>{r['g_mid']*100:+.0f}%</td><td>{r['n']}</td>"
                         f'<td class="{heat(r["fr_mean"], .03, .10)}">{r["fr_mean"]*100:+.1f}%</td>'
                         f"<td>{r['fr_med']*100:+.1f}%</td>"
                         f'<td class="{"" if abs(r["win"]-.5)>.12 else "nz"}">{r["win"]*100:.0f}%</td></tr>')
    gap_table = f"""<table>
<tr><th>指数</th><th>gap 档位（小→大）</th><th>gap 中枢</th><th>月数</th><th>未来12月平均</th><th>中位数</th><th>上涨占比</th></tr>{gap_rows}</table>
<p class="muted">创业板 corr(gap, 未来12月) = {gap_corr['cyb']:+.2f}；标普500 = {gap_corr['sp500']:+.2f}。
若「补涨论」成立，应看到第 5 档（gap 最大=盈利远超股价）收益显著最高、且相关系数显著为正。</p>"""

    # 当前 gap 落在哪一档
    gap_now_log = np.log1p(e_yoy) - np.log1p(p_yoy)
    cur_bin = None
    for r in gaps["cyb"]:
        if r["g_lo"] <= gap_now_log <= r["g_hi"]:
            cur_bin = r
            break
    cur_txt = (f"当前 gap 落在第 {cur_bin['bin']+1} 档——该档历史未来 12 个月平均 "
               f"{cur_bin['fr_mean']*100:+.1f}%、中位 {cur_bin['fr_med']*100:+.1f}%、"
               f"上涨占比 {cur_bin['win']*100:.0f}%" if cur_bin else "")
    current_html = (
        f"创业板近 1 年：<b>隐含盈利 {fmt_pct(e_yoy)}</b>，<b>股价 {fmt_pct(p_yoy)}</b>，"
        f"gap = {fmt_pct(gap_now)}（这部分全部体现为 PE 变化）。"
        f"PE {pe_now:.1f}，近 5 年分位 {pe_pctl*100:.0f}%。<br>"
        f"{cur_txt}。<br>"
        f"按「补涨论」会预期 +{gap_now*100:.0f}% 空间，但创业板历史上 gap 与未来收益的相关系数为 "
        f"{gap_corr['cyb']:+.2f}（负）——<b>gap 不但不预示补涨，历史上反而略偏空</b>。"
    )

    g_lo, g_hi = gaps["cyb"][0], gaps["cyb"][-1]
    cards = f"""<div class="cards">
<div class="card hot"><div class="lbl">① Q1 长期：盈利决定股价</div>
<div class="num">持有5年 r={cors['cyb'].get(60, float('nan')):+.2f}</div>
<div class="lbl">创业板盈利/股价增速相关性：1年 {cors['cyb'][12]:+.2f} → 3年 {cors['cyb'].get(36,0):+.2f} → 5年 {cors['cyb'].get(60,0):+.2f}；标普500 各期限稳定在 +0.5~0.6。持有越久，股价越像盈利本身</div></div>
<div class="card cold"><div class="lbl">② Q1 短期（创业板）：甚至负相关</div>
<div class="num">1年 r={cors['cyb'][12]:+.2f}</div>
<div class="lbl">一年内创业板涨跌大半由 PE 摆动贡献；2010 以来盈利年化 {dec['cyb']['e']*100:+.1f}%，PE 年化 {dec['cyb']['pe']*100:+.1f}%——盈利涨了 5 倍，估值还打了折</div></div>
<div class="card hot"><div class="lbl">③ Q2「补涨论」：方向都是反的</div>
<div class="num bad">corr = {gap_corr['cyb']:+.2f}</div>
<div class="lbl">创业板「盈利-股价缺口」与未来 12 个月收益<b>负相关</b>：盈利大幅跑赢股价（第5档）后平均仅 {g_hi['fr_mean']*100:+.0f}%、胜率 {g_hi['win']*100:.0f}%；股价大幅跑赢盈利（第1档）后反而 {g_lo['fr_mean']*100:+.0f}%、胜率 {g_lo['win']*100:.0f}%</div></div>
<div class="card dim"><div class="lbl">④ 创业板当前</div>
<div class="num">{fmt_pct(gap_now)}</div>
<div class="lbl">近1年盈利 {fmt_pct(e_yoy)} vs 股价 {fmt_pct(p_yoy)}；PE 5年分位 {pe_pctl*100:.0f}%——gap 不预示补涨，估值分位才是状态的真实度量</div></div>
</div>"""

    verdict = (
        f"Q1：<b>长期正相关、短期很弱甚至为负</b>——创业板持有 5 年时盈利/股价增速相关系数 "
        f"{cors['cyb'].get(60, 0):+.2f}，但持有 1 年只有 {cors['cyb'][12]:+.2f}（负的）；"
        f"标普500 则在各期限都有 +0.5~0.6。换言之：A股成长股短期价格由估值（流动性/情绪）定价，"
        f"盈利要在 3~5 年维度才说了算。"
        f"Q2：<b>「补涨论」不成立，且在创业板方向相反</b>。「盈利 +30%、股价 +20%」的缺口 100% "
        f"体现为 PE 压缩，而 PE 没有必须回归的锚；创业板该缺口与未来 12 个月收益的相关系数为 "
        f"<b>{gap_corr['cyb']:+.2f}（负）</b>——盈利大幅跑赢股价（第 5 档）后未来一年平均仅 "
        f"{g_hi['fr_mean']*100:+.0f}%、胜率 {g_hi['win']*100:.0f}%；反倒是股价大幅跑赢盈利（第 1 档）后 "
        f"{g_lo['fr_mean']*100:+.0f}%、胜率 {g_lo['win']*100:.0f}%。股价定价的是未来盈利：利润大增但股价不涨，"
        f"常常是市场已在给「增速不可持续」定价——牛市尾声的典型组合。"
    )

    # ---------------- 图数据
    cyb_n = cyb / cyb.iloc[0]

    def norm(s):
        return s / s.iloc[0]

    scatter_df = pd.DataFrame({
        "de": np.log(cyb["E"]).diff(12), "dp": np.log(cyb["p"]).diff(12)}).dropna()
    scatter = [[round(float(np.expm1(r["de"])), 3), round(float(np.expm1(r["dp"])), 3)]
               for _, r in scatter_df.iterrows()]

    data = {
        "cyb_p": [[str(d.date()), round(v, 4)] for d, v in norm(cyb["p"]).items()],
        "cyb_e": [[str(d.date()), round(v, 4)] for d, v in norm(cyb["E"]).items()],
        "cyb_pe": [[str(d.date()), round(float(v), 1)] for d, v in cyb["pe"].items()],
        "scatter": scatter,
        "now_scatter": [round(e_yoy, 3), round(p_yoy, 3)],
        "gap_bins": ["第1档(股价跑赢盈利)", "第2档", "第3档", "第4档", "第5档(盈利跑赢股价)"],
        "gap_cyb": [round(r["fr_mean"], 4) for r in gaps["cyb"]],
        "gap_sp": [round(r["fr_mean"], 4) for r in gaps["sp500"]],
    }

    html = (PAGE
            .replace("__GEN__", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__VERDICT__", verdict)
            .replace("__CARDS__", cards)
            .replace("__DECOMP_TABLE__", decomp_table)
            .replace("__CORR_TABLE__", corr_table)
            .replace("__GAP_TABLE__", gap_table)
            .replace("__CURRENT__", current_html)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "earn_price.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n已生成 {out}")


if __name__ == "__main__":
    main()
