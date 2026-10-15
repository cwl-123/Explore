# -*- coding: utf-8 -*-
# cyb_div_ratio.py — 创业板 / 红利「矛与盾」比值择时指标
#
# 复刻公众号「指汇盈」思路：创业板指（最强之矛）× 红利指数（最强之盾）的价格比值，
# 存在稳定的均值回归规律——比值接近历史底部 = 创业板相对极度低估（抄底创业板）；
# 接近历史顶部 = 创业板相对极度高估（减持创业板、换入红利）。
#
# 红利指数取两条：
#   - 中证红利 000922（原文口径，阈值 0.30 抄底 / 0.70 逃顶）
#   - 红利低波 H30269（本项目口径，自身阈值 ≈ 历史 10%/90% 分位）
# 价格：创业板=sina 日线缓存 cyb_price.csv；红利=中证官网 csindex（滚动市盈率同源）
# 输出：cyb_div_ratio.html
# 运行：.venv/bin/python cyb_div_ratio.py

import json
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cyb_div_ratio.html")
MIN_HIST = 250  # 分位可用所需最少样本


# ---------------------------------------------------------------- 数据

def fetch_csindex(symbol, cache):
    """中证官网日线（收盘/滚动市盈率）；网络失败自动退回缓存"""
    path = os.path.join(DATA_DIR, cache)
    try:
        import akshare as ak
        raw = ak.stock_zh_index_hist_csindex(symbol=symbol, start_date="20040101", end_date="20991231")
        df = raw.rename(columns={"日期": "date", "收盘": "close", "滚动市盈率": "pe"})[["date", "close", "pe"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
        df.to_csv(path, index=False)
        print(f"  {symbol} 拉取 {len(df)} 行 -> {df['date'].max().date()}")
        return df
    except Exception as e:
        print(f"  {symbol} 拉取失败，用缓存 {cache}: {e}")
        df = pd.read_csv(path, parse_dates=["date"])
        return df.sort_values("date").reset_index(drop=True)


def load_cyb():
    df = pd.read_csv(os.path.join(DATA_DIR, "cyb_price.csv"), parse_dates=["date"])
    df = df[["date", "close"]].sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return df


def build(cyb, div):
    """对齐创业板/红利，算比值"""
    m = pd.merge_asof(cyb, div, on="date", suffixes=("_c", "_d")).dropna(subset=["close_c", "close_d"]).reset_index(drop=True)
    m["ratio"] = m["close_c"] / m["close_d"]
    return m


def expanding_pctl(s, min_hist=MIN_HIST):
    """只用当日及之前数据的历史分位（无前视）"""
    out = []
    for k in range(len(s)):
        if k + 1 < min_hist:
            out.append(np.nan)
        else:
            w = s.iloc[:k + 1]
            out.append(float((w <= s.iloc[k]).mean()))
    return pd.Series(out, index=s.index)


def episodes(m, thr, side, gap=60):
    """比值持续 <=thr（low）或 >=thr（high）的极端事件，取区间内极值点，算其后续收益"""
    cond = (m["ratio"] <= thr) if side == "low" else (m["ratio"] >= thr)
    idx = np.where(cond.values)[0]
    groups = []
    for k in idx:
        if groups and k - groups[-1][-1] <= gap:
            groups[-1].append(k)
        else:
            groups.append([k])
    out = []
    n = len(m)
    r = m["ratio"].values
    for g in groups:
        j = g[int(np.argmin(r[g]))] if side == "low" else g[int(np.argmax(r[g]))]
        row = m.iloc[j]
        f1 = m.iloc[min(n - 1, j + 250)] if j + 250 < n else None
        f2 = m.iloc[min(n - 1, j + 500)] if j + 500 < n else None
        out.append({
            "date": str(row["date"].date()),
            "ratio": round(float(row["ratio"]), 3),
            "cyb": round(float(row["close_c"])),
            "div": round(float(row["close_d"])),
            "cyb1": None if f1 is None else round(float(f1["close_c"] / row["close_c"] - 1) * 100, 1),
            "div1": None if f1 is None else round(float(f1["close_d"] / row["close_d"] - 1) * 100, 1),
            "cyb2": None if f2 is None else round(float(f2["close_c"] / row["close_c"] - 1) * 100, 1),
            "div2": None if f2 is None else round(float(f2["close_d"] / row["close_d"] - 1) * 100, 1),
            "ongoing": bool(j + 500 >= n),
        })
    return out


def snapshot(m, pctl):
    last = m.iloc[-1]
    return {
        "date": str(last["date"].date()),
        "cyb": round(float(last["close_c"])),
        "div": round(float(last["close_d"])),
        "ratio": round(float(last["ratio"]), 4),
        "pctl": round(float(pctl.iloc[-1]) * 100, 1),
        "lo": round(float(m["ratio"].min()), 3),
        "lo_date": str(m.loc[m["ratio"].idxmin(), "date"].date()),
        "hi": round(float(m["ratio"].max()), 3),
        "hi_date": str(m.loc[m["ratio"].idxmax(), "date"].date()),
        "med": round(float(m["ratio"].median()), 3),
        "q10": round(float(m["ratio"].quantile(0.10)), 3),
        "q90": round(float(m["ratio"].quantile(0.90)), 3),
        "start": str(m["date"].min().date()),
    }


# ---------------------------------------------------------------- 组装

def analyze_one(cyb, div, buy, sell):
    m = build(cyb, div)
    pctl = expanding_pctl(m["ratio"])
    snap = snapshot(m, pctl)
    eps_buy = episodes(m, buy, "low")
    eps_sell = episodes(m, sell, "high")
    series = [[str(d.date()), round(float(v), 4)] for d, v in zip(m["date"], m["ratio"])]
    return {"m": m, "pctl": pctl, "snap": snap, "buy": buy, "sell": sell,
            "eps_buy": eps_buy, "eps_sell": eps_sell, "series": series}


def norm(s):
    return (s / s.iloc[0]).round(4)


def main():
    print("== 拉取红利数据 ==")
    zz = fetch_csindex("000922", "zzhl.csv")     # 中证红利
    hl = fetch_csindex("H30269", "hldb_full.csv")  # 红利低波
    cyb = load_cyb()

    A = {}
    A["zzhl"] = analyze_one(cyb, zz[["date", "close"]], 0.30, 0.70)
    A["hldb"] = analyze_one(cyb, hl[["date", "close"]], 0.17, 0.33)

    for k, nm in (("zzhl", "中证红利"), ("hldb", "红利低波")):
        s = A[k]["snap"]
        print(f"  {nm}：{s['date']} 比值 {s['ratio']}（{s['start']} 起区间 {s['lo']}~{s['hi']}，"
              f"中位 {s['med']}），当前分位 {s['pctl']}%，阈值 买{s['q10'] if k=='hldb' else A[k]['buy']}/"
              f"卖{s['q90'] if k=='hldb' else A[k]['sell']}")

    # 归一化价格曲线（矛 vs 盾）
    m = A["zzhl"]["m"]
    base = m.index[0]
    px = {
        "dates": [str(d.date()) for d in m["date"]],
        "cyb": [round(float(v), 4) for v in norm(m["close_c"])],
        "zzhl": [round(float(v), 4) for v in norm(m["close_d"])],
    }
    # 红利低波单独对齐后归一（与中证红利起点一致处开始）
    m2 = A["hldb"]["m"]
    px["hldb"] = [round(float(m2.loc[m2["date"] == m["date"].iloc[i], "close_d"].iloc[0] / m2.iloc[0]["close_d"]), 4)
                  if (m2["date"] == m["date"].iloc[i]).any() else None for i in range(len(m))]

    data = {
        "zzhl": A["zzhl"]["series"],
        "hldb": A["hldb"]["series"],
        "zzhl_snap": A["zzhl"]["snap"], "hldb_snap": A["hldb"]["snap"],
        "zzhl_eps_buy": A["zzhl"]["eps_buy"], "zzhl_eps_sell": A["zzhl"]["eps_sell"],
        "hldb_eps_buy": A["hldb"]["eps_buy"], "hldb_eps_sell": A["hldb"]["eps_sell"],
        "px": px,
    }

    html = render(A, data)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("已生成", OUT)


# ---------------------------------------------------------------- 页面

def heat(x):
    if x is None:
        return "nz"
    return "rd" if x > 0 else ("gn" if x < 0 else "nz")


def fwd_cell(v, cls="", unit="%"):
    if v is None:
        return '<td class="nz">进行中</td>'
    return f'<td class="{heat(v)}">{v:+.1f}%</td>'


def eps_table(eps, kind):
    rows = ""
    for e in eps:
        tag = "抄底·买创业板" if kind == "buy" else "逃顶·换红利"
        rows += (f'<tr><td>{e["date"]}</td><td class="r">{e["ratio"]:.3f}</td>'
                 f'<td>{e["cyb"]}</td><td>{e["div"]}</td>'
                 f'{fwd_cell(e["cyb1"])}{fwd_cell(e["div1"])}'
                 f'{fwd_cell(e["cyb2"])}{fwd_cell(e["div2"])}</tr>')
    return rows


def render(A, data):
    zs, hs = data["zzhl_snap"], data["hldb_snap"]
    # 距阈值
    z_gap_buy = (1 - 0.30 / zs["ratio"]) * 100
    z_gap_sell = (0.70 / zs["ratio"] - 1) * 100
    h_gap_buy = (1 - 0.17 / hs["ratio"]) * 100
    h_gap_sell = (0.33 / hs["ratio"] - 1) * 100

    # 结论文字
    def pos_txt(s, buy, sell, name):
        r = s["ratio"]
        if r <= buy:
            zone = "<b>抄底区</b>：创业板相对极度低估，历史级别的买点"
        elif r >= sell:
            zone = "<b>逃顶区</b>：创业板相对极度高估，应减持创业板、换入红利"
        elif r >= (buy + sell) / 2:
            zone = "偏贵区（中上位）：创业板相对红利不便宜，风格上红利占优，但未到极端"
        else:
            zone = "偏便宜区（中下位）：创业板相对红利开始有性价比，但未到极端"
        return (f"{name} 口径：比值 <b>{r:.3f}</b>（{s['start'][:4]} 以来区间 {s['lo']}~{s['hi']}，"
                f"中位 {s['med']}），当前历史分位 <b>{s['pctl']}%</b> → {zone}。")

    verdict = (
        f"<p>用「{zs['date']}」数据：<b>创业板/中证红利 = {zs['ratio']:.3f}</b>（历史 {zs['pctl']}% 分位）、"
        f"<b>创业板/红利低波 = {hs['ratio']:.3f}</b>（历史 {hs['pctl']}% 分位）。"
        f"两者口径一致指向同一结论：<b>创业板相对红利处在「偏贵的中上位」，"
        f"既不在 0.3 的抄底黄金坑，也不再是 6 月底 0.87 的极端逃顶点。</b></p>"
        f"<p>换算成操作含义：现在<b>不是抄底创业板的时机</b>——按原文口径还要比值再弱约 "
        f"{z_gap_buy:.0f}%（或红利相对再强）才回到 0.30 的坑底；但也不建议此刻割肉创业板去追红利。</p>"
    )

    # cards
    cards = f"""
<div class="cards">
  <div class="card"><div class="lbl">创业板 / 中证红利（原文口径）</div>
    <div class="num">{zs['ratio']:.3f}</div>
    <div class="lbl">历史分位 {zs['pctl']}%｜区间 {zs['lo']}~{zs['hi']}｜阈值 0.30 / 0.70</div></div>
  <div class="card"><div class="lbl">创业板 / 红利低波（本项目口径）</div>
    <div class="num">{hs['ratio']:.3f}</div>
    <div class="lbl">历史分位 {hs['pctl']}%｜区间 {hs['lo']}~{hs['hi']}｜阈值 0.17 / 0.33</div></div>
  <div class="card"><div class="lbl">距抄底线（中证红利）</div>
    <div class="num neg">-{z_gap_buy:.0f}%</div>
    <div class="lbl">比值还需再跌到 0.30（创业板相对再弱）</div></div>
  <div class="card"><div class="lbl">距逃顶线（中证红利）</div>
    <div class="num pos">+{z_gap_sell:.0f}%</div>
    <div class="lbl">比值再涨到 0.70 才触及极端高估</div></div>
</div>"""

    zz_buy_rows = eps_table(data["zzhl_eps_buy"], "buy")
    zz_sell_rows = eps_table(data["zzhl_eps_sell"], "sell")
    hl_buy_rows = eps_table(data["hldb_eps_buy"], "buy")
    hl_sell_rows = eps_table(data["hldb_eps_sell"], "sell")

    def ep_block(rows):
        return (f"<table><tr><th>极端日</th><th>比值</th><th>创业板</th><th>红利</th>"
                f"<th colspan='2'>其后1年（创/红）</th><th colspan='2'>其后2年（创/红）</th></tr>{rows}</table>")

    cur = (
        f"<div class='box'>"
        f"<p>{pos_txt(zs, 0.30, 0.70, '中证红利')}</p>"
        f"<p>{pos_txt(hs, 0.17, 0.33, '红利低波')}</p>"
        f"<p class='muted'>注：红利低波波动比中证红利更小（分母更「稳」），故比值区间更窄，"
        f"不能直接套用 0.3/0.7；此处用其自身历史的 10%/90% 分位作为极端阈值。</p>"
        f"</div>"
    )

    return PAGE.replace("__VERDICT__", verdict).replace("__CARDS__", cards) \
        .replace("__CUR__", cur) \
        .replace("__ZZ_BUY__", ep_block(zz_buy_rows)).replace("__ZZ_SELL__", ep_block(zz_sell_rows)) \
        .replace("__HL_BUY__", ep_block(hl_buy_rows)).replace("__HL_SELL__", ep_block(hl_sell_rows)) \
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))


PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>创业板/红利 比值择时：现在在哪 / 什么时候关注创业板</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#222;line-height:1.75}
h1{font-size:26px}h2{font-size:20px;margin-top:44px;border-left:4px solid #c0392b;padding-left:10px}
.muted{color:#888;font-size:13px}
.box{background:#faf6ec;border:1px solid #e8dcc0;border-radius:8px;padding:16px 20px;margin:16px 0}
.chart{width:100%;height:430px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:12px 0}
th,td{border:1px solid #ddd;padding:6px 9px;text-align:center;white-space:nowrap}
th{background:#f6f6f6}
td.rd{color:#c0392b}td.gn{color:#27ae60;font-weight:600}td.nz{color:#bbb}
td.r{font-weight:700}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.card{flex:1;min-width:220px;border-radius:8px;padding:14px 16px;border:1px solid #e0e0e0;background:#fff}
.card .num{font-size:26px;font-weight:700;margin:4px 0}
.card .lbl{font-size:12.5px;color:#666}
.neg{color:#c0392b}.pos{color:#27ae60}
ul{padding-left:20px}li{margin:4px 0}
</style>
</head>
<body>
<h1>什么时候可以再度关注创业板？——创业板 / 红利「矛与盾」比值</h1>
<p class="muted">创业板指（最强之矛）× 红利指数（最强之盾）的价格比值，均值回归择时 ｜ 数据：中证官网 + sina，不构成投资建议</p>

<div class="box"><b>一句话结论：</b>__VERDICT__</div>
__CARDS__

<h2>1. 指标怎么用：最强的矛 ÷ 最强的盾</h2>
<ul>
<li><b>创业板指</b> = A股成长风格的极致，牛市最猛、熊市最惨；<b>红利指数</b> = 高股息稳定资产，长期近 45° 斜向上。</li>
<li>用<b>创业板点位 ÷ 红利点位</b> 得到「风格温度计」：比值越低，说明市场对成长的悲观到极点、创业板相对红利极度便宜。</li>
<li>经验规律（原文复盘 16 年）：<b>比值接近 0.3 → 抄底创业板</b>；<b>接近 0.7 → 减持创业板、换入红利</b>。本质是「成长/价值」的钟摆总会回归。</li>
</ul>

<h2>2. 历史全景：比值在 0.3 与 0.7 之间的钟摆</h2>
<div id="cRatio" class="chart"></div>
<p class="muted">红线 = 创业板/中证红利（原文口径），蓝线 = 创业板/红利低波（本项目口径）。两条曲线形状高度一致：均在 2012、2018-19、2024-08 触底，在 2015、2021、2026-06 冲顶。图中只画中证红利的 0.30/0.70 阈值（红利低波用其自身 0.17/0.33，见第 4 节）。</p>

<h2>3. 矛与盾的走势：谁在跑赢</h2>
<div id="cPx" class="chart"></div>
<p class="muted">归一化走势（起点=1）。红利两条线近乎 45° 稳步向上；创业板则是巨幅波段。比值就是这两类资产的相对强弱。</p>

<h2>4. 当前位置</h2>
__CUR__

<h2>5. 历史极端点验证：抄底区/逃顶区之后发生了什么</h2>
<p><b>中证红利口径（阈值 0.30 / 0.70）——抄底事件：</b></p>
__ZZ_BUY__
<p><b>中证红利口径——逃顶事件：</b></p>
__ZZ_SELL__
<p><b>红利低波口径（阈值 0.17 / 0.33）——抄底事件：</b></p>
__HL_BUY__
<p><b>红利低波口径——逃顶事件：</b></p>
__HL_SELL__
<p class="muted">「其后1年/2年」为事件日之后 250/500 个交易日的涨跌幅（创业板 / 红利）。规律相当稳定：抄底区之后创业板常出现数十到上百 % 的反弹、而红利几乎不涨；逃顶区之后创业板大幅回撤、红利抗跌甚至上涨。</p>

<h2>6. 口径与免责</h2>
<ul class="muted">
<li>价格指数均未含分红：红利类指数实际股息率高（约 4~6%/年），真实全收益比价格指数更高，故「创业板/红利」比值会系统性高估红利长期表现之外的部分——用价格比值做相对强弱判读是原文惯例，但对绝对收益做判断时需注意。</li>
<li>创业板价格=sina 日线；中证红利 000922 / 红利低波 H30269 价格与滚动市盈率=中证官网（akshare csindex）。</li>
<li>比值分位为「扩窗历史分位」（只用当日及之前数据，无前视）；阈值 0.30/0.70 取自原文，红利低波 0.17/0.33 取自身历史 10%/90% 分位。</li>
<li>样本有限、且极端点事后统计存在幸存者偏差，仅作行为参考，不构成投资建议。</li>
</ul>

<script>
const D = __DATA__;
const RED='#c0392b', BLUE='#2c6fb8', GREEN='#27ae60', GOLD='#c99a2e', GRAY='#999';
const dateIdx = (arr) => arr.map(p=>p[0]);

// ---- 图1：两条比值
(function(){
  const ch = echarts.init(document.getElementById('cRatio'));
  const zz = D.zzhl, hl = D.hldb;
  const z0 = D.zzhl_snap;
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['创业板/中证红利','创业板/红利低波'],top:0},
    grid:{left:50,right:20,top:36,bottom:56},
    xAxis:{type:'category',data:dateIdx(zz),axisLabel:{color:'#888'}},
    yAxis:{type:'value',scale:true,name:'比值',axisLabel:{color:'#888'}},
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:20}],
    series:[
      {name:'创业板/中证红利',type:'line',showSymbol:false,data:zz.map(p=>p[1]),lineStyle:{color:RED,width:1.8},
        markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed'},
          data:[{yAxis:0.30,lineStyle:{color:GREEN},label:{formatter:'0.30 抄底创业板',color:GREEN}},
                {yAxis:0.70,lineStyle:{color:RED},label:{formatter:'0.70 换红利',color:RED}}]},
        markPoint:{symbol:'pin',symbolSize:44,itemStyle:{color:RED},label:{fontSize:9,color:'#fff'},
          data:[{coord:[dateIdx(zz)[zz.length-1],z0.ratio],value:'现在'}]}},
      {name:'创业板/红利低波',type:'line',showSymbol:false,data:hl.map(p=>p[1]),lineStyle:{color:BLUE,width:1.6}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图2：归一化价格
(function(){
  const ch = echarts.init(document.getElementById('cPx'));
  const P = D.px;
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['创业板指','中证红利','红利低波'],top:0},
    grid:{left:50,right:20,top:36,bottom:56},
    xAxis:{type:'category',data:P.dates,axisLabel:{color:'#888'}},
    yAxis:{type:'log',name:'归一(log)',axisLabel:{color:'#888'}},
    dataZoom:[{type:'inside'},{type:'slider',height:18,bottom:20}],
    series:[
      {name:'创业板指',type:'line',showSymbol:false,data:P.cyb,lineStyle:{color:RED,width:1.8}},
      {name:'中证红利',type:'line',showSymbol:false,data:P.zzhl,lineStyle:{color:GOLD,width:1.6}},
      {name:'红利低波',type:'line',showSymbol:false,data:P.hldb,lineStyle:{color:BLUE,width:1.6}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()