# -*- coding: utf-8 -*-
# fed_cycle.py — 美联储加息/降息周期跟随策略的验证与前瞻分析
#
# 验证命题（来自公众号文章）：「在加息的尾声买入，在降息的尾声卖出」
# 输出：fed_cycle.html（自包含 ECharts 分析页）
#
# 口径：
#   - 联邦基金利率：FRED FEDFUNDS 月度（data/fedfunds.csv），月度均值与真实 FOMC
#     决议日存在 ±1 个月偏差；2026-09-17 的加息 FRED 尚未发布，手工补录（见 MANUAL_HIKE）
#   - 沪深300 用全收益指数 H00300（含分红，data/hs300_price.csv）
#   - 纳指100 为价格指数（data/ndx_price.csv，不含分红，仅作美股参照）
#   - 空仓资金按 2%/年计息（与 backtest.py 一致）
#   - 信号在月末确认，次月首个交易日执行
# 运行：.venv/bin/python fed_cycle.py

import json
import math
import os
import urllib.request

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CASH_RATE = 0.02
FEDFUNDS_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"
MANUAL_HIKE = ("2026-09-01", 3.88)  # 2026-09-17 FOMC 加息 25bp（FRED 月度尚未发布）
MOVE_TH = 0.05      # 月度利率变动超过 5bp 记为一次加息/降息
CONFIRM = 0.25      # 反向累计 25bp 才确认周期转向（过滤 2009-02 这类噪音）
STALE_MONTHS = 24   # 确认转向时丢弃 24 个月前的零星反向动作


# ---------------------------------------------------------------- 数据

def load_fedfunds():
    path = os.path.join(DATA_DIR, "fedfunds.csv")
    if not os.path.exists(path):
        print("下载 FEDFUNDS ...")
        urllib.request.urlretrieve(FEDFUNDS_URL, path)
    df = pd.read_csv(path, parse_dates=["observation_date"])
    s = pd.Series(df["FEDFUNDS"].values, index=df["observation_date"])
    s = s[~s.index.duplicated()]
    d, v = MANUAL_HIKE
    if s.index.max() < pd.Timestamp(d):
        s[pd.Timestamp(d)] = v
    return s.sort_index()


def load_price(name):
    df = pd.read_csv(os.path.join(DATA_DIR, name), parse_dates=["date"])
    return pd.Series(df["close"].values, index=df["date"]).sort_index()


def load_hs300_pe():
    df = pd.read_csv(os.path.join(DATA_DIR, "hs300_pe.csv"), parse_dates=["date"])
    return pd.Series(df["pe"].values, index=df["date"]).sort_index()


# ---------------------------------------------------------------- 周期识别

def detect_phases(ff):
    """把月度利率序列切成加息/降息阶段。返回 [(sign, first_move, last_move), ...]，
    sign=+1 加息阶段, -1 降息阶段。阶段内的「最后一次动作」即转向点。"""
    d = ff.diff().dropna()
    moves = [(dt, 1, v) for dt, v in d.items() if v > MOVE_TH]
    moves += [(dt, -1, v) for dt, v in d.items() if v < -MOVE_TH]
    moves.sort(key=lambda x: x[0])
    phase, phase_moves, opp_moves, opp_cum = 0, [], [], 0.0
    phases = []
    for dt, s, v in moves:
        if phase == 0 or s == phase:
            phase = s
            phase_moves.append((dt, v))
            opp_moves, opp_cum = [], 0.0
        else:
            opp_moves.append((dt, v))
            opp_cum += v
            if abs(opp_cum) >= CONFIRM:
                cutoff = dt - pd.DateOffset(months=STALE_MONTHS)
                fresh = [m for m in opp_moves if m[0] >= cutoff]
                phases.append((phase, phase_moves[0][0], phase_moves[-1][0]))
                phase = s
                phase_moves = fresh if fresh else [(dt, v)]
                opp_moves, opp_cum = [], 0.0
    if phase_moves:
        phases.append((phase, phase_moves[0][0], phase_moves[-1][0]))
    return phases


def turning_points(phases):
    """(sign, first, last) -> 末次加息日列表 / 末次降息日列表（月末确认）"""
    last_hikes = [p[2] for p in phases if p[0] == 1]
    last_cuts = [p[2] for p in phases if p[0] == -1]
    return last_hikes, last_cuts


def regime_of(date, phases):
    """某天所处的 regime：hike/pause_top/cut/pause_bot"""
    for i, (s, first, last) in enumerate(phases):
        nxt_first = phases[i + 1][1] if i + 1 < len(phases) else pd.Timestamp("2100-01-01")
        if s == 1:
            if first <= date <= last:
                return "hike"
            if last < date < nxt_first:
                return "pause_top"
        else:
            if first <= date <= last:
                return "cut"
            if last < date < nxt_first:
                return "pause_bot"
    return "pre"


# ---------------------------------------------------------------- 回测

def first_td_after(idx, date):
    i = idx.searchsorted(date + pd.Timedelta(days=1))
    return idx[i] if i < len(idx) else None


def build_position(idx, last_hikes, last_cuts, lag_months=0):
    """命题策略仓位：末次加息(月末确认)后买入，末次降息后卖出。lag=可执行确认滞后月数"""
    pos = pd.Series(0.0, index=idx)
    events = [(d, 1) for d in last_hikes] + [(d, 0) for d in last_cuts]
    events.sort()
    held = False
    for d, target in events:
        exec_from = d + pd.DateOffset(months=1 + lag_months)
        if target == 1 and not held:
            pos.loc[pos.index >= exec_from] = 1.0
            held = True
        elif target == 0 and held:
            pos.loc[pos.index >= exec_from] = 0.0
            held = False
    return pos


def backtest(price, pos):
    ret = price.pct_change().fillna(0.0)
    prev = pos.shift(1).fillna(0.0)
    nav = (1 + prev * ret + (1 - prev) * CASH_RATE / 252).cumprod()
    return nav


def metrics(nav, pos=None):
    n = len(nav)
    yrs = (nav.index[-1] - nav.index[0]).days / 365.25
    total = nav.iloc[-1] - 1
    cagr = nav.iloc[-1] ** (1 / yrs) - 1 if yrs > 0 else np.nan
    mdd = (nav / nav.cummax() - 1).min()
    out = {"total": total, "cagr": cagr, "mdd": mdd}
    if pos is not None:
        out["invested_pct"] = float(pos.mean())
    return out


def window_stats(price, last_hikes, last_cuts, start):
    """逐持有窗口：末次加息->买入，末次降息->卖出"""
    rows = []
    events = [(d, 1) for d in last_hikes] + [(d, 0) for d in last_cuts]
    events.sort()
    open_buy = None
    for d, t in events:
        if t == 1 and open_buy is None:
            open_buy = first_td_after(price.index, d)
        elif t == 0 and open_buy is not None:
            sell = first_td_after(price.index, d)
            if sell is None:
                break
            if open_buy < start:
                open_buy = None
                continue
            seg = price.loc[open_buy:sell]
            if len(seg) < 2:
                open_buy = None
                continue
            ret = seg.iloc[-1] / seg.iloc[0] - 1
            mdd = (seg / seg.cummax() - 1).min()
            rows.append({"buy": open_buy, "sell": sell, "ret": ret, "mdd": mdd,
                         "days": (sell - open_buy).days})
            open_buy = None
    return rows


# ---------------------------------------------------------------- 条件统计 & 前瞻

def monthly_returns(price):
    m = price.resample("M").last()
    return m.pct_change().dropna()


def cond_stats(price, phases):
    mr = monthly_returns(price)
    groups = {"hike": [], "pause_top": [], "cut": [], "pause_bot": []}
    for dt, v in mr.items():
        r = regime_of(dt - pd.DateOffset(months=1) + pd.Timedelta(days=1), phases)
        if r in groups:
            groups[r].append(v)
    out = {}
    for k, vals in groups.items():
        vals = np.array(vals)
        if len(vals) == 0:
            continue
        out[k] = {"n": len(vals), "mean_m": float(vals.mean()),
                  "win": float((vals > 0).mean()),
                  "ann": float((1 + vals.mean()) ** 12 - 1),
                  "p25": float(np.percentile(vals, 25)),
                  "p75": float(np.percentile(vals, 75))}
    return out


def forward_returns(price, phases, horizon_m=12, only_early_hike=False):
    """处于加息阶段的每个月末，未来 horizon_m 个月收益"""
    m = price.resample("M").last()
    res = []
    for i in range(len(m)):
        dt = m.index[i]
        r = regime_of(dt, phases)
        if r != "hike":
            continue
        if only_early_hike:
            firsts = [p[1] for p in phases if p[0] == 1]
            if not any(f <= dt <= f + pd.DateOffset(months=12) for f in firsts):
                continue
        j = i + horizon_m
        if j < len(m):
            res.append(float(m.iloc[j] / m.iloc[i] - 1))
    return res


def mc_bootstrap(pool, horizon_m=12, n_paths=20000, seed=42):
    rng = np.random.default_rng(seed)
    pool = np.asarray(pool)
    draws = rng.choice(pool, size=(n_paths, horizon_m), replace=True)
    return np.prod(1 + draws, axis=1) - 1


def rolling_pctl(pe, window=1250, min_periods=250):
    return pe.rolling(window, min_periods=min_periods).apply(
        lambda x: (x <= x[-1]).mean(), raw=True)


# ---------------------------------------------------------------- 页面

PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>跟随美联储周期投资A股，靠谱吗？</title>
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
tr.maxrow td{outline:2px solid #c0392b;outline-offset:-2px}
tr.minrow td{outline:2px solid #27ae60;outline-offset:-2px}
.legend{font-size:12px;color:#999;margin:4px 0 0}
.legend span{display:inline-block;padding:0 8px;border:1px solid #ddd;margin-right:6px}
</style>
</head>
<body>
<h1>「加息尾声买入，降息尾声卖出」——用 20 年数据验证一个流行命题</h1>
<p class="muted">生成时间：__GEN__ ｜ 数据：FRED 联邦基金利率（月度）、沪深300全收益 H00300（__HS_END__ 止）、纳指100 ｜ 口径见文末</p>

<div class="box">
<b>一句话结论：</b>__VERDICT__
</div>

<h2>0. 核心信号速览（只看这 4 个数字）</h2>
__CARDS__
<p class="legend">全页着色规则：<span style="background:rgba(192,57,43,.28)">强正收益信号</span><span style="background:rgba(192,57,43,.12)">弱正</span><span style="background:rgba(39,174,96,.12)">弱负</span><span style="background:rgba(39,174,96,.28)">强负收益信号</span><span style="color:#bbb">灰色 = 胜率 45%~55% 或 |月均|&lt;0.5%，统计噪音，不必关注</span></p>

<h2>1. 美联储利率周期与沪深300</h2>
<p>红底=加息阶段，绿底=降息阶段。命题的买点（末次加息，▼红）与卖点（末次降息，▲绿）标注在图上。</p>
<div id="c1" class="chart"></div>

<h2>2. 策略回测：完美择时 vs 滞后确认 vs 满仓躺平</h2>
<p>「完美择时」假设你事后知道每次周期的最后一次加/降息（月末确认、次月执行）；「滞后6个月」模拟现实中等趋势确认后再行动；空仓资金按 2%/年计息。</p>
<div id="c2" class="chart"></div>
__BT_TABLE__
<p class="muted">__BT_NOTE__</p>

<h2>3. 逐窗口复盘：每次都赚钱吗？</h2>
__WIN_TABLE__

<h2>4. 沪深300 在周期各阶段的表现（2005 以来月度收益）</h2>
__COND_TABLE__
<p class="muted">加息阶段样本仅约 __N_HIKE__ 个月（3 轮加息），统计意义有限，结论需保留余地。</p>

<h2>4.5 港股对照：恒生指数（1986 起）与恒生科技（2020 起）</h2>
<p>港币联系汇率制下，香港利率被迫跟随美联储，港股对美元流动性的敏感度理论上高于 A 股。恒指为价格指数（不含股息，实际总回报更高）；恒生科技仅覆盖约 1.5 轮周期，样本极小、仅供参考。</p>
__HK_COND_TABLE__
__HK_WIN_TABLE__
<p class="muted">__HK_NOTE__</p>

<h2>5. 现在处于什么位置？</h2>
<div class="box warn">
__CURRENT__
</div>

<h2>6. 前瞻：未来 12 个月沪深300 收益的概率分布</h2>
<p>方法：以历史上「加息阶段」的月度收益为总体，bootstrap 抽样 12 个月 × 20000 条路径；对照组为同期全部月份。当前估值分位单独列出。</p>
<div id="c3" class="chart"></div>
__FWD_TABLE__

<h2>7. 口径与免责</h2>
<ul class="muted">
<li>利率周期由 FEDFUNDS 月度均值识别（变动&gt;5bp 记为一次动作，反向累计≥25bp 确认转向），与真实 FOMC 日期存在数月以内的边界偏差（如 2018-12 的末次加息在月度均值上落在 2019-01）；2026-09-17 的加息为手工补录。</li>
<li>沪深300 用全收益指数 H00300（含分红）；纳指100 为价格指数（不含分红），两者绝对收益不可直接对比。</li>
<li>「完美择时」含事后视角，仅用于度量命题上限；「滞后6个月」也不代表现实可稳定执行（周期尾声事前不可知）。</li>
<li>加息阶段历史样本仅 3 轮，前瞻分布是情景参考而非预测。</li>
<li>空仓收益 2%/年，未计交易费用与税费。本页不构成投资建议。</li>
</ul>

<script>
const DATA = __DATA__;
const pct = x => (x*100).toFixed(1) + '%';
const RED='#c0392b', GREEN='#27ae60', BLUE='#2c3e50', GRAY='#95a5a6';

// ---- 图1：周期 + 沪深300
(function(){
  const ph = DATA.phases.map(p => ({
    itemStyle:{color: p.type==='hike' ? 'rgba(192,57,43,0.10)' : 'rgba(39,174,96,0.10)'},
    xAxis: p.start
  }));
  const phEnd = DATA.phases.map(p => ({xAxis: p.end}));
  const marks = [];
  DATA.buys.forEach(b => marks.push({coord:[b.d, b.v], value:'买', itemStyle:{color:RED}}));
  DATA.sells.forEach(s => marks.push({coord:[s.d, s.v], value:'卖', itemStyle:{color:GREEN}}));
  const ch = echarts.init(document.getElementById('c1'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['沪深300全收益','联邦基金利率(右)']},
    grid:{left:60,right:60},
    xAxis:{type:'time'},
    yAxis:[{type:'log',name:'净值(log)'},{type:'value',name:'%',max:8}],
    dataZoom:[{type:'inside'},{type:'slider'}],
    series:[
      {name:'沪深300全收益',type:'line',showSymbol:false,data:DATA.hs300,lineStyle:{width:1.5,color:BLUE},
       markArea:{silent:true,data: ph.map((s,i)=>[s, phEnd[i]])},
       markPoint:{symbolSize:46,label:{fontSize:11},data:marks}},
      {name:'联邦基金利率(右)',type:'line',yAxisIndex:1,showSymbol:false,step:'end',
       data:DATA.ff,lineStyle:{width:1,color:'#e67e22',type:'dashed'}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图2：回测净值
(function(){
  const ch = echarts.init(document.getElementById('c2'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['完美择时(加息末买/降息末卖)','滞后6个月确认','满仓躺平']},
    grid:{left:60,right:20},
    xAxis:{type:'time'},
    yAxis:{type:'log',name:'净值(log)'},
    dataZoom:[{type:'inside'},{type:'slider'}],
    series:[
      {name:'完美择时(加息末买/降息末卖)',type:'line',showSymbol:false,data:DATA.bt_perfect,lineStyle:{color:RED,width:1.8}},
      {name:'滞后6个月确认',type:'line',showSymbol:false,data:DATA.bt_lag,lineStyle:{color:'#e67e22',width:1.5}},
      {name:'满仓躺平',type:'line',showSymbol:false,data:DATA.bt_hold,lineStyle:{color:GRAY,width:1.5}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图3：前瞻分布
(function(){
  const ch = echarts.init(document.getElementById('c3'));
  ch.setOption({
    tooltip:{},
    legend:{data:['加息阶段抽样(对应现在)','全部月份抽样(无条件)']},
    grid:{left:60,right:20},
    xAxis:{type:'category',data:DATA.fwd_bins,name:'未来12个月收益'},
    yAxis:{type:'value',name:'概率%',axisLabel:{formatter:'{value}%'}},
    series:[
      {name:'加息阶段抽样(对应现在)',type:'bar',data:DATA.fwd_hike,itemStyle:{color:RED},
       markLine:{silent:true,symbol:'none',lineStyle:{color:'#333',type:'solid'},
                 label:{formatter:'盈亏分界',position:'end'},
                 data:[{xAxis:'-10~0'}]},
       markPoint:{symbol:'pin',symbolSize:56,itemStyle:{color:RED},
                  label:{formatter:'P(亏损) '+DATA.fwd_pneg+'%',fontSize:10,color:'#fff'},
                  data:[{coord:['-10~0', Math.max.apply(null,DATA.fwd_hike)]}]}},
      {name:'全部月份抽样(无条件)',type:'bar',data:DATA.fwd_all,itemStyle:{color:GRAY}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();
</script>
</body>
</html>
"""


def fmt_pct(x, sign=True):
    s = f"{x*100:+.1f}%" if sign else f"{x*100:.1f}%"
    cls = "good" if x > 0 else "bad"
    return f'<span class="{cls}">{s}</span>'


def heat(mean_m, win=None):
    """月均收益 -> (css类, 文本前缀)。|月均|<0.5% 或胜率为 45~55% 视为噪音压灰"""
    if win is not None and 0.45 <= win <= 0.55:
        return "nz"
    if mean_m >= 0.015:
        return "sp2"
    if mean_m >= 0.005:
        return "sp1"
    if mean_m <= -0.015:
        return "sn2"
    if mean_m <= -0.005:
        return "sn1"
    return "nz"


def ret_cell(v, win=None, scale=1.0):
    return f'<td class="{heat(v * scale, win)}">{v*100:+.2f}%</td>'


def win_cell(win):
    cls = "" if (win >= 0.58 or win <= 0.42) else "nz"
    return f'<td class="{cls}">{win*100:.0f}%</td>'


def main():
    ff = load_fedfunds()
    hs = load_price("hs300_price.csv")
    ndx = load_price("ndx_price.csv")
    pe = load_hs300_pe()

    phases = detect_phases(ff)
    completed = phases[:-1]  # 最后一段（2026-09 起的加息）仍在进行，其「末次动作」事后才知
    last_hikes, last_cuts = turning_points(completed)
    print("== 周期阶段 ==")
    name = {1: "加息", -1: "降息"}
    for s, a, b in phases:
        print(f"  {name[s]}: {a.date()} ~ {b.date()}")
    print("  末次加息:", [str(d.date()) for d in last_hikes])
    print("  末次降息:", [str(d.date()) for d in last_cuts])

    # ---------------- 回测（沪深300，2005 起）
    start = hs.index[0]
    pos_p = build_position(hs.index, last_hikes, last_cuts, lag_months=0)
    pos_l = build_position(hs.index, last_hikes, last_cuts, lag_months=6)
    nav_p, nav_l = backtest(hs, pos_p), backtest(hs, pos_l)
    nav_h = hs / hs.iloc[0]
    m_p, m_l, m_h = metrics(nav_p, pos_p), metrics(nav_l, pos_l), metrics(nav_h)

    # 纳指参照（1995 起）
    ndx95 = ndx.loc["1995-01-01":]
    pos_np = build_position(ndx95.index, last_hikes, last_cuts)
    nav_np = backtest(ndx95, pos_np)
    nav_nh = ndx95 / ndx95.iloc[0]
    m_np, m_nh = metrics(nav_np, pos_np), metrics(nav_nh)

    print("\n== 回测（沪深300 全收益, 2005 起）==")
    for k, m in [("完美择时", m_p), ("滞后6月", m_l), ("满仓躺平", m_h)]:
        print(f"  {k}: 累计{m['total']*100:.0f}% 年化{m['cagr']*100:.1f}% "
              f"回撤{m['mdd']*100:.1f}%" +
                  (f" 在场{m['invested_pct']*100:.0f}%" if "invested_pct" in m else ""))
    print("== 纳指100 (1995 起) ==")
    for k, m in [("完美择时", m_np), ("满仓躺平", m_nh)]:
        print(f"  {k}: 累计{m['total']*100:.0f}% 年化{m['cagr']*100:.1f}% 回撤{m['mdd']*100:.1f}%")

    # ---------------- 逐窗口
    wins = window_stats(hs, last_hikes, last_cuts, start)
    print("\n== 沪深300 逐持有窗口（加息末买->降息末卖）==")
    for w in wins:
        print(f"  {w['buy'].date()} -> {w['sell'].date()}: "
              f"{w['ret']*100:+.1f}% (回撤{w['mdd']*100:.1f}%)")
    wins_ndx = window_stats(ndx95, last_hikes, last_cuts, ndx95.index[0])
    print("== 纳指100 逐窗口 ==")
    for w in wins_ndx:
        print(f"  {w['buy'].date()} -> {w['sell'].date()}: {w['ret']*100:+.1f}%")

    # ---------------- 条件统计
    cond = cond_stats(hs.loc["2005-01-01":], phases)
    print("\n== 沪深300 分 regime 月度收益 ==")
    for k, v in cond.items():
        print(f"  {k}: n={v['n']} 月均{v['mean_m']*100:+.2f}% 胜率{v['win']*100:.0f}% "
              f"年化{v['ann']*100:+.1f}%")

    # ---------------- 港股对照
    hsi = load_price("hsi_price.csv")
    hstech = load_price("hstech_price.csv")
    cond_hsi = cond_stats(hsi, phases)
    cond_hstech = cond_stats(hstech, phases)
    print("\n== 恒生指数(价格, 1986 起) 分 regime ==")
    for k, v in cond_hsi.items():
        print(f"  {k}: n={v['n']} 月均{v['mean_m']*100:+.2f}% 胜率{v['win']*100:.0f}% "
              f"年化{v['ann']*100:+.1f}%")
    print("== 恒生科技(价格, 2020 起) 分 regime ==")
    for k, v in cond_hstech.items():
        print(f"  {k}: n={v['n']} 月均{v['mean_m']*100:+.2f}% 胜率{v['win']*100:.0f}% "
              f"年化{v['ann']*100:+.1f}%")
    pos_hsi = build_position(hsi.index, last_hikes, last_cuts)
    nav_hsi, nav_hsi_h = backtest(hsi, pos_hsi), hsi / hsi.iloc[0]
    m_hsi, m_hsi_h = metrics(nav_hsi, pos_hsi), metrics(nav_hsi_h)
    print(f"  恒指 完美择时: 累计{m_hsi['total']*100:.0f}% 年化{m_hsi['cagr']*100:.1f}% "
          f"回撤{m_hsi['mdd']*100:.1f}% | 满仓: 年化{m_hsi_h['cagr']*100:.1f}% "
          f"回撤{m_hsi_h['mdd']*100:.1f}%")
    wins_hsi = window_stats(hsi, last_hikes, last_cuts, hsi.index[0])
    wins_hst = window_stats(hstech, last_hikes, last_cuts, hstech.index[0])
    print("  恒指逐窗口:", "、".join(f"{w['buy'].year}年{w['ret']*100:+.0f}%" for w in wins_hsi))
    print("  恒生科技逐窗口:", "、".join(
        f"{w['buy'].date()}~{w['sell'].date()} {w['ret']*100:+.0f}%" for w in wins_hst))
    fwd_hsi_hike = forward_returns(hsi, phases, 12)
    fwd_hsi_hike_early = forward_returns(hsi, phases, 12, only_early_hike=True)
    e = np.array(fwd_hsi_hike_early)
    print(f"  恒指加息初期12M: n={len(e)} 中位{np.median(e)*100:+.0f}% "
          f"上涨占比{(e>0).mean()*100:.0f}%")

    # ---------------- 前瞻
    mr = monthly_returns(hs)
    hike_months = [float(v) for dt, v in mr.items()
                   if regime_of(dt - pd.DateOffset(months=1) + pd.Timedelta(days=1),
                                phases) == "hike"]
    all_months = [float(v) for v in mr]
    mc_hike = mc_bootstrap(hike_months)
    mc_all = mc_bootstrap(all_months)
    hist_12m = forward_returns(hs.loc["2005-01-01":], phases, 12)
    hist_12m_early = forward_returns(hs.loc["2005-01-01":], phases, 12,
                                     only_early_hike=True)

    def probs(x):
        x = np.asarray(x)
        return {"p5": float(np.percentile(x, 5)), "p25": float(np.percentile(x, 25)),
                "p50": float(np.percentile(x, 50)), "p75": float(np.percentile(x, 75)),
                "p95": float(np.percentile(x, 95)),
                "p_neg": float((x < 0).mean()), "p_dn20": float((x < -0.2).mean()),
                "p_up10": float((x > 0.1).mean()), "p_up20": float((x > 0.2).mean())}

    pr_h, pr_a = probs(mc_hike), probs(mc_all)
    print("\n== 前瞻12M (bootstrap) ==")
    print("  加息期抽样:", {k: round(v, 3) for k, v in pr_h.items()})
    print("  无条件抽样:", {k: round(v, 3) for k, v in pr_a.items()})
    print("  历史加息期12M实际:", [f"{r*100:+.0f}%" for r in hist_12m])
    print("  其中加息初期(首12个月)样本:", [f"{r*100:+.0f}%" for r in hist_12m_early])

    # 当前估值
    pctl = rolling_pctl(pe.reindex(hs.index).ffill())
    cur_pe, cur_pctl = pe.iloc[-1], pctl.iloc[-1]
    print(f"\n当前: PE={cur_pe:.2f}, 5y分位={cur_pctl*100:.0f}%, "
          f"H00300={hs.iloc[-1]:.0f} ({hs.index[-1].date()})")

    # ---------------- 前瞻分布直方图
    edges = [-1, -0.4, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.4, 10]
    labels = ["<-40%", "-40~-30", "-30~-20", "-20~-10", "-10~0", "0~+10",
              "+10~+20", "+20~+30", "+30~+40", ">+40%"]
    h_h, _ = np.histogram(mc_hike, bins=edges)
    h_a, _ = np.histogram(mc_all, bins=edges)

    # ---------------- 判定文案
    early_arr = np.array(hist_12m_early)
    verdict = (
        f"命题<b>在美股部分成立、在 A 股整体不成立</b>。沪深300 的 {len(wins)} 个持有窗口"
        f"全部盈利（" + "、".join(f"{w['ret']*100:+.0f}%" for w in wins) + f"），"
        f"但第一个窗口（2006-07 → 2008-12）中途最大回撤 {fmt_pct(wins[0]['mdd'], False)}，"
        f"且策略整体年化仅 {m_p['cagr']*100:.1f}%，大幅跑输满仓躺平的 {m_h['cagr']*100:.1f}%"
        f"——因为 A 股的大行情（2009、2014-15、2024-25）多由国内流动性与政策驱动，"
        f"恰好落在命题要求「空仓」的时段。机制层面更直接的反驳：沪深300 在美联储<b>降息阶段</b>"
        f"的月均收益为 {fmt_pct(cond['cut']['mean_m'])}（降息往往对应全球衰退而非「流动性红包」）。"
        f"美股那边，2000-06 与 2006-07 两轮「加息尾声买入」分别吞下 "
        f"{wins_ndx[2]['ret']*100:+.0f}% 与 {wins_ndx[3]['ret']*100:+.0f}%。"
        f"该命题的本质是赌软着陆，且选错了对 A 股定价权最大的变量。"
    )

    current_html = (
        f"<b>周期位置：</b>2024-09 开启的降息周期历时约 16 个月、累计降息约 170bp，"
        f"于 2026-01 见底（3.63%）；<b>2026-09-17 美联储加息 25bp，点阵图指向 12 月再加一次"
        f"——新一轮加息周期已开启，当前处于「加息初期」</b>，恰是命题中「应空仓观望」的阶段。<br>"
        f"<b>估值位置：</b>沪深300 PE {cur_pe:.2f}，近 5 年分位 {cur_pctl*100:.0f}%"
        f"（全收益指数 {hs.iloc[-1]:.0f} 点，{hs.index[-1].date()}）——估值不便宜。<br>"
        f"<b>历史同类情形：</b>加息阶段开启后的前 12 个月内，沪深300 历史样本共 {len(early_arr)} 个，"
        f"12 个月远期收益中位数 {np.median(early_arr)*100:+.0f}%，"
        f"上涨占比 {(early_arr>0).mean()*100:.0f}%——涨跌互现，「加息初期必跌」不成立；"
        f"真正稳定为负的是「加息中后期 + 高估值」的组合（2018、2022）。"
    )

    # ---------------- 表格 HTML
    bt_table = f"""<table>
<tr><th>沪深300（2005 起，全收益）</th><th>累计收益</th><th>年化</th><th>最大回撤</th><th>在场时间</th></tr>
<tr><td>完美择时：加息末买 / 降息末卖</td><td>{fmt_pct(m_p['total'],False)}</td><td>{fmt_pct(m_p['cagr'],False)}</td><td>{fmt_pct(m_p['mdd'],False)}</td><td>{m_p['invested_pct']*100:.0f}%</td></tr>
<tr><td>滞后 6 个月确认（可执行版）</td><td>{fmt_pct(m_l['total'],False)}</td><td>{fmt_pct(m_l['cagr'],False)}</td><td>{fmt_pct(m_l['mdd'],False)}</td><td>{m_l['invested_pct']*100:.0f}%</td></tr>
<tr><td>满仓躺平（基准）</td><td>{fmt_pct(m_h['total'],False)}</td><td>{fmt_pct(m_h['cagr'],False)}</td><td>{fmt_pct(m_h['mdd'],False)}</td><td>100%</td></tr>
<tr><td colspan="5" style="text-align:left"><b>美股参照（纳指100，1995 起，价格指数）：</b>完美择时 累计{fmt_pct(m_np['total'],False)} / 年化{fmt_pct(m_np['cagr'],False)} / 回撤{fmt_pct(m_np['mdd'],False)}；满仓躺平 累计{fmt_pct(m_nh['total'],False)} / 年化{fmt_pct(m_nh['cagr'],False)} / 回撤{fmt_pct(m_nh['mdd'],False)}</td></tr>
</table>"""

    win_notes = ["加息加出了金融危机（硬着陆）", "降息尾声撞上新冠流动性危机",
                 "软着陆 + 国内政策转向，命题的标准答案"]
    best_i = max(range(len(wins)), key=lambda i: wins[i]["ret"])
    worst_i = min(range(len(wins)), key=lambda i: wins[i]["mdd"])
    win_rows = ""
    for i, (w, note) in enumerate(zip(wins, win_notes)):
        cls = ' class="maxrow"' if i == best_i else (' class="minrow"' if i == worst_i else "")
        tag = "（本轮最赚）" if i == best_i else ("（体验最差：中途回撤 -72%）" if i == worst_i else "")
        win_rows += (f"<tr{cls}><td>{w['buy'].date()} → {w['sell'].date()}{tag}</td>"
                     f"<td>{(w['days'])/365:.1f} 年</td><td>{fmt_pct(w['ret'])}</td>"
                     f"<td>{fmt_pct(w['mdd'],False)}</td><td>{note}</td></tr>")
    win_table = f"""<table>
<tr><th>持有窗口（买入→卖出）</th><th>时长</th><th>窗口收益</th><th>窗口最大回撤</th><th>备注</th></tr>{win_rows}</table>"""

    cond_name = {"hike": "加息阶段", "pause_top": "高位暂停（末次加息→首次降息）",
                 "cut": "降息阶段", "pause_bot": "低位暂停（末次降息→首次加息）"}
    cond_rows = "".join(
        f"<tr><td>{cond_name[k]}</td><td>{v['n']}</td>"
        f"{ret_cell(v['mean_m'], v['win'])}{win_cell(v['win'])}"
        f'<td class="{heat(v["mean_m"], v["win"])}">{v["ann"]*100:+.1f}%</td>'
        f"<td>{v['p25']*100:+.1f}% ~ {v['p75']*100:+.1f}%</td></tr>"
        for k, v in cond.items())
    cond_table = f"""<table>
<tr><th>阶段</th><th>月数</th><th>月均收益</th><th>月胜率</th><th>年化(均值复合)</th><th>25~75分位</th></tr>{cond_rows}</table>"""

    def hk_rows(cd):
        cells = []
        for k in ["hike", "pause_top", "cut", "pause_bot"]:
            if k in cd:
                v = cd[k]
                cells.append(f"<td>{v['n']}</td>{ret_cell(v['mean_m'], v['win'])}"
                             f"{win_cell(v['win'])}"
                             f'<td class="{heat(v["mean_m"], v["win"])}">'
                             f'{v["ann"]*100:+.1f}%</td>')
            else:
                cells.append("<td>-</td>" * 4)
        return "".join(cells)

    hk_cond_table = f"""<table>
<tr><th></th><th colspan="4">加息阶段</th><th colspan="4">高位暂停</th><th colspan="4">降息阶段</th><th colspan="4">低位暂停</th></tr>
<tr><th>指数</th><th>月数</th><th>月均</th><th>胜率</th><th>年化</th><th>月数</th><th>月均</th><th>胜率</th><th>年化</th><th>月数</th><th>月均</th><th>胜率</th><th>年化</th><th>月数</th><th>月均</th><th>胜率</th><th>年化</th></tr>
<tr><td>恒生指数（1986 起，价格）</td>{hk_rows(cond_hsi)}</tr>
<tr><td>恒生科技（2020 起，价格）</td>{hk_rows(cond_hstech)}</tr>
<tr><td>沪深300 全收益（2005 起，参照）</td>{hk_rows(cond)}</tr>
</table>"""

    hk_win_rows = ""
    hsi_best = max(range(len(wins_hsi)), key=lambda i: wins_hsi[i]["ret"])
    hsi_worst = min(range(len(wins_hsi)), key=lambda i: wins_hsi[i]["ret"])
    for i, w in enumerate(wins_hsi):
        cls = ' class="maxrow"' if i == hsi_best else (' class="minrow"' if i == hsi_worst else "")
        tag = "（最赚）" if i == hsi_best else ("（最亏）" if i == hsi_worst else "")
        hk_win_rows += (f"<tr{cls}><td>{w['buy'].date()} → {w['sell'].date()}{tag}</td>"
                        f"<td>{fmt_pct(w['ret'])}</td>"
                        f"<td>{fmt_pct(w['mdd'], False)}</td></tr>")
    hst_txt = "；".join(
        f"{w['buy'].date()}→{w['sell'].date()} {fmt_pct(w['ret'])}（回撤{fmt_pct(w['mdd'], False)}）"
        for w in wins_hst) or "无完整窗口"
    hk_win_table = f"""<table>
<tr><th>恒指持有窗口（加息末买→降息末卖）</th><th>窗口收益</th><th>窗口最大回撤</th></tr>{hk_win_rows}</table>"""

    hk_note = (
        f"恒指「完美择时」回测（1986 起）：累计 {fmt_pct(m_hsi['total'], False)}、"
        f"年化 {fmt_pct(m_hsi['cagr'], False)}、回撤 {fmt_pct(m_hsi['mdd'], False)}；"
        f"满仓躺平：年化 {fmt_pct(m_hsi_h['cagr'], False)}、回撤 {fmt_pct(m_hsi_h['mdd'], False)}"
        f"（价格指数口径，不含股息）。恒生科技的命题窗口：{hst_txt}。"
        f"恒指在「加息初期」的未来 12 个月历史样本 {len(e)} 个，中位数 {np.median(e)*100:+.0f}%、"
        f"上涨占比 {(e>0).mean()*100:.0f}%。"
    )

    fwd_table = f"""<table>
<tr><th>未来 12 个月（沪深300）</th><th>5分位</th><th>25分位</th><th>中位数</th><th>75分位</th><th>95分位</th><th>P(亏损)</th><th>P(跌超20%)</th><th>P(涨超10%)</th><th>P(涨超20%)</th></tr>
<tr style="background:#fdf0ef"><td><b>按「加息阶段」抽样（对应当前）</b></td><td>{pr_h['p5']*100:+.0f}%</td><td>{pr_h['p25']*100:+.0f}%</td><td><b>{pr_h['p50']*100:+.0f}%</b></td><td>{pr_h['p75']*100:+.0f}%</td><td>{pr_h['p95']*100:+.0f}%</td><td><b style="font-size:18px">{pr_h['p_neg']*100:.0f}%</b></td><td>{pr_h['p_dn20']*100:.0f}%</td><td>{pr_h['p_up10']*100:.0f}%</td><td>{pr_h['p_up20']*100:.0f}%</td></tr>
<tr class="nz"><td>无条件抽样（任意月份，对照）</td><td>{pr_a['p5']*100:+.0f}%</td><td>{pr_a['p25']*100:+.0f}%</td><td>{pr_a['p50']*100:+.0f}%</td><td>{pr_a['p75']*100:+.0f}%</td><td>{pr_a['p95']*100:+.0f}%</td><td>{pr_a['p_neg']*100:.0f}%</td><td>{pr_a['p_dn20']*100:.0f}%</td><td>{pr_a['p_up10']*100:.0f}%</td><td>{pr_a['p_up20']*100:.0f}%</td></tr>
</table>"""

    cards = f"""<div class="cards">
<div class="card hot"><div class="lbl">① 最强规律 · 港股吃降息（n={cond_hsi['cut']['n']} 个月，样本最足）</div>
<div class="num good">恒指降息期 +{cond_hsi['cut']['ann']*100:.0f}%/年</div>
<div class="lbl">同一时期沪深300 为 <b class="bad">{cond['cut']['ann']*100:+.0f}%/年</b>——同一美元流动性，港股是直接红包，A股是衰退拖累</div></div>
<div class="card hot"><div class="lbl">② 胜率最高 · 沪深300「高位暂停」（末次加息→首次降息）</div>
<div class="num good">胜率 {cond['pause_top']['win']*100:.0f}%，月均 +{cond['pause_top']['mean_m']*100:.1f}%</div>
<div class="lbl">但 n={cond['pause_top']['n']} 且 2007 泡沫贡献大半——可参考，不可全信</div></div>
<div class="card cold"><div class="lbl">③ 最疼的坑 · 加息尾声买在硬着陆</div>
<div class="num bad">纳指 2000 窗口 {wins_ndx[2]['ret']*100:.0f}%</div>
<div class="lbl">恒指 1987 窗口 {min(w['ret'] for w in wins_hsi)*100:.0f}%；沪深300 2006 窗口中途回撤 -72%</div></div>
<div class="card dim"><div class="lbl">④ 对现在 · 加息刚重启，未来 12 个月沪深300</div>
<div class="num">P(亏损) {pr_h['p_neg']*100:.0f}%，中位 {pr_h['p50']*100:+.0f}%</div>
<div class="lbl">赔率变差而非必跌；A股命题策略年化 {m_p['cagr']*100:.1f}% 仍跑输满仓 {m_h['cagr']*100:.1f}%</div></div>
</div>"""

    # ---------------- 图数据
    buys, sells = [], []
    open_b = None
    ev = [(d, 1) for d in last_hikes] + [(d, 0) for d in last_cuts]
    ev.sort()
    for d, t in ev:
        if d < start - pd.DateOffset(months=1):
            continue
        td = first_td_after(hs.index, d)
        if td is None:
            continue
        if t == 1 and open_b is None:
            buys.append({"d": str(td.date()), "v": round(float(hs.loc[td]), 1)})
            open_b = td
        elif t == 0 and open_b is not None:
            sells.append({"d": str(td.date()), "v": round(float(hs.loc[td]), 1)})
            open_b = None

    data = {
        "hs300": [[str(d.date()), round(v, 1)] for d, v in hs.items()],
        "ff": [[str(d.date()), round(float(v), 2)] for d, v in ff.loc["2005-01-01":].items()],
        "phases": [{"type": "hike" if s == 1 else "cut",
                    "start": str(a.date()), "end": str(b.date())}
                   for s, a, b in phases if b >= pd.Timestamp("2005-01-01")],
        "buys": buys, "sells": sells,
        "bt_perfect": [[str(d.date()), round(v, 4)] for d, v in nav_p.items()],
        "bt_lag": [[str(d.date()), round(v, 4)] for d, v in nav_l.items()],
        "bt_hold": [[str(d.date()), round(v, 4)] for d, v in nav_h.items()],
        "fwd_bins": labels,
        "fwd_hike": [round(x / len(mc_hike) * 100, 1) for x in h_h],
        "fwd_all": [round(x / len(mc_all) * 100, 1) for x in h_a],
        "fwd_pneg": round(pr_h["p_neg"] * 100),
    }

    html = (PAGE
            .replace("__GEN__", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__HS_END__", str(hs.index[-1].date()))
            .replace("__VERDICT__", verdict)
            .replace("__CARDS__", cards)
            .replace("__BT_TABLE__", bt_table)
            .replace("__BT_NOTE__",
                     f"完美择时 {len(wins)} 次持仓共在场 {m_p['invested_pct']*100:.0f}% 的时间；"
                     "纳指窗口：" + "、".join(
                         f"{w['buy'].year}年{w['ret']*100:+.0f}%" for w in wins_ndx) + "。")
            .replace("__WIN_TABLE__", win_table)
            .replace("__COND_TABLE__", cond_table)
            .replace("__N_HIKE__", str(cond.get("hike", {}).get("n", 0)))
            .replace("__HK_COND_TABLE__", hk_cond_table)
            .replace("__HK_WIN_TABLE__", hk_win_table)
            .replace("__HK_NOTE__", hk_note)
            .replace("__CURRENT__", current_html)
            .replace("__FWD_TABLE__", fwd_table)
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fed_cycle.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n已生成 {out}")


if __name__ == "__main__":
    main()
