# -*- coding: utf-8 -*-
"""沪深300 当前位置判读（独立页面，不进 index.html Tab 框架）
问题：现在该买还是该卖？牛市结束了吗？
方法：复用 backtest.py 的口径（H00300 全收益 + 乐咕 PE + 滚动5年分位，无前视），
输出：当前信号面板 / 历史 >90% 分位事件对照 / 当前状态条件收益统计 / 买回卖出线位。
运行：.venv/bin/python hs300_view.py  ->  hs300_view.html
"""
import json
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT = os.path.join(os.path.dirname(__file__), "hs300_view.html")
WINDOW = 250 * 5
MIN_PERIODS = 250


def load():
    px = pd.read_csv(os.path.join(DATA_DIR, "hs300_price.csv"), parse_dates=["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    pe = pd.read_csv(os.path.join(DATA_DIR, "hs300_pe.csv"), parse_dates=["date"])
    pe_s = pd.Series(pd.to_numeric(pe["pe"], errors="coerce").values,
                     index=pd.to_datetime(pe["date"])).sort_index()
    daily = pd.DatetimeIndex(px["date"])
    df = px.assign(pe=pe_s.reindex(daily, method="ffill").values)
    df = df[df["pe"].notna()].reset_index(drop=True)

    def pctl(w):
        cur = w[-1]
        if not np.isfinite(cur) or cur <= 0:
            return np.nan
        wv = w[np.isfinite(w) & (w > 0)]
        if len(wv) == 0:
            return np.nan
        return (wv <= cur).mean()

    df["pctl"] = df["pe"].rolling(WINDOW, min_periods=MIN_PERIODS).apply(pctl, raw=True)
    for w in (20, 60, 120, 250):
        df[f"ma{w}"] = df["close"].rolling(w).mean()
    return df


def strategy_3090(df):
    """PE·30买90卖 仓位序列（与 backtest.py 同规则），返回 (pos, sells, buys)"""
    p = df["pctl"]
    held, pos, sells, buys = 0, [], [], []
    for k in range(len(df)):
        pk = p.iloc[k]
        if np.isfinite(pk):
            if pk < 0.30 and held == 0:
                held = 1
                buys.append(k)
            elif pk > 0.90 and held == 1:
                held = 0
                sells.append(k)
        pos.append(held)
    return pd.Series(pos, index=df.index), sells, buys


def episodes_90(df):
    """pctl>90% 的连续事件（间隔<60日且未跌破85%则合并）"""
    p, c, dates = df["pctl"], df["close"], df["date"]
    n = len(df)
    above = (p > 0.90).values
    eps, i = [], 0
    while i < n:
        if above[i]:
            j = i
            while j + 1 < n and (above[j + 1] or (np.isfinite(p.iloc[j + 1]) and p.iloc[j + 1] > 0.85)):
                j += 1
            eps.append((i, j))
            i = j + 1
        else:
            i += 1
    # 合并间隔 <60 交易日的事件
    merged = []
    for s, e in eps:
        if merged and s - merged[-1][1] < 60:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    out = []
    for s, e in merged:
        w_end = min(n, s + 500)
        seg = c.iloc[s:w_end]
        pk_i = s + int(np.argmax(seg.values))
        dd = float((seg / seg.cummax() - 1).min())
        fwd12 = None
        if s + 250 < n:
            fwd12 = float(c.iloc[s + 250] / c.iloc[s] - 1)
        so_far = float(c.iloc[-1] / c.iloc[s] - 1) if s + 250 >= n else None
        out.append({
            "first90": str(dates.iloc[s].date()),
            "end": str(dates.iloc[e].date()),
            "days": e - s + 1,
            "peak_date": str(dates.iloc[pk_i].date()),
            "peak": round(float(c.iloc[pk_i])),
            "months_to_peak": round((dates.iloc[pk_i] - dates.iloc[s]).days / 30.4, 1),
            "maxdd_2y": round(dd * 100, 1),
            "fwd12m": round(fwd12 * 100, 1) if fwd12 is not None else None,
            "so_far": round(so_far * 100, 1) if so_far is not None else None,
            "ongoing": s + 250 >= n,
        })
    return out


def fwd_stats(df, mask, label, note=""):
    c, n = df["close"], len(df)
    idx = np.where(mask.fillna(False).values)[0]
    keep = []
    for k in idx:
        if not keep or k - keep[-1] > 21:
            keep.append(k)
    out = {"label": label, "note": note, "n_days": int(len(idx)), "n": len(keep)}
    for h, tag in ((126, "6m"), (250, "12m")):
        r = np.array([c.iloc[min(n - 1, k + h)] / c.iloc[k] - 1 for k in keep if k + h < n])
        if len(r) < 5:
            out[tag] = None
            continue
        out[tag] = {
            "mean": round(float(r.mean()) * 100, 1),
            "med": round(float(np.median(r)) * 100, 1),
            "win": round(float((r > 0).mean()) * 100),
            "p10": round(float(np.percentile(r, 10)) * 100, 1),
            "p90": round(float(np.percentile(r, 90)) * 100, 1),
            "n": int(len(r)),
        }
    return out


def analyze():
    df = load()
    c, p, dates = df["close"], df["pctl"], df["date"]
    last = df.iloc[-1]
    pos, sells, buys = strategy_3090(df)

    # ---- 当前面板 ----
    seg = df[dates >= "2024-01-01"]
    lo_i = seg["close"].idxmin()
    bull_lo, bull_lo_d = float(seg.loc[lo_i, "close"]), seg.loc[lo_i, "date"]
    hi_i = df["close"].idxmax()  # 全史 ATH（2021-02）
    peak_i = seg["close"].idxmax()  # 本轮峰（2026-06）
    E = c / df["pe"]

    panel = {
        "date": str(last["date"].date()),
        "close": round(float(last["close"]), 1),
        "pe": round(float(last["pe"]), 2),
        "pctl": round(float(last["pctl"]) * 100, 1),
        "pctl_peak": round(float(p.iloc[-250:].max()) * 100, 1),
        "pctl_peak_date": str(df.iloc[-250:]["date"].iloc[int(np.nanargmax(p.iloc[-250:].values))].date()),
        "dd_from_bull_peak": round(float(last["close"] / c.iloc[peak_i] - 1) * 100, 1),
        "bull_peak": round(float(c.iloc[peak_i])),
        "bull_peak_date": str(dates.iloc[peak_i].date()),
        "ath": round(float(c.iloc[hi_i])),
        "ath_date": str(dates.iloc[hi_i].date()),
        "dd_from_ath": round(float(last["close"] / c.iloc[hi_i] - 1) * 100, 1),
        "bull_lo": round(bull_lo),
        "bull_lo_date": str(bull_lo_d.date()),
        "bull_gain_peak": round((float(c.iloc[peak_i]) / bull_lo - 1) * 100),
        "gain_from_lo": round(float(last["close"] / bull_lo - 1) * 100),
        "ytd": round(float(last["close"] / c[dates < "2026-01-01"].iloc[-1] - 1) * 100, 1),
        "ret_1y": round(float(last["close"] / c[dates < last["date"] - pd.Timedelta(days=365)].iloc[-1] - 1) * 100, 1),
        "ma_dev": {f"MA{w}": round(float(last["close"] / df[f"ma{w}"].iloc[-1] - 1) * 100, 1) for w in (20, 60, 120, 250)},
        "e_growth_1y": round(float(E.iloc[-1] / E[dates < last["date"] - pd.Timedelta(days=365)].iloc[-1] - 1) * 100, 1),
        "e_growth_since_bull": round(float(E.iloc[-1] / E[dates < pd.Timestamp("2024-09-30")].iloc[-1] - 1) * 100, 1),
        "pe_ath_2021": round(float(pd.Series(df["pe"].values, index=dates).asof(pd.Timestamp("2021-02-10"))), 1),
    }

    # ---- 策略信号状态 ----
    sell_dates = [str(dates.iloc[k].date()) for k in sells]
    buy_dates = [str(dates.iloc[k].date()) for k in buys]
    strategy = {
        "position": int(pos.iloc[-1]),
        "last_sell": sell_dates[-1] if sell_dates else None,
        "last_sell_price": round(float(c.iloc[sells[-1]])) if sells else None,
        "since_sell_ret": round(float(last["close"] / c.iloc[sells[-1]] - 1) * 100, 1) if sells else None,
        "sells": sell_dates,
        "buys": buy_dates,
    }

    # ---- 买回/卖出线位（当前5年窗口，假设盈利不变） ----
    win = df["pe"].iloc[-WINDOW:]
    lines = []
    for q, name in ((0.30, "严格买回线（30买90卖）"), (0.50, "宽松买回线（50买90卖）"),
                    (0.70, "回到偏贵区"), (0.90, "再次触发清仓")):
        pev = float(np.quantile(win, q))
        lines.append({"q": int(q * 100), "name": name, "pe": round(pev, 2),
                      "px": round(float(last["close"]) / (float(last["pe"]) / pev))})

    # ---- 历史 >90% 事件 ----
    eps = episodes_90(df)

    # ---- 条件收益统计 ----
    ma250 = df["ma250"]
    touched90_60 = (p > 0.90).rolling(60, min_periods=1).max().astype(bool)
    state_now = (p > 0.6) & (p < 0.8) & (c < ma250) & touched90_60
    stats = [
        fwd_stats(df, state_now, "当前状态：分位60~80% + 破年线 + 60日内刚触过90%",
                  "与今天完全同构的历史交易日"),
        fwd_stats(df, (c / c.rolling(60).max() - 1 < -0.10) & (p > 0.9).rolling(90, min_periods=1).max().astype(bool) & (p < 0.9),
                  "触90%后从近60日高点回撤>10%", "顶部确认后的下坡段"),
        fwd_stats(df, (p > 0.6) & (p < 0.8), "分位60~80%（不限趋势）", "「不便宜也不极端贵」的中位区"),
        fwd_stats(df, pd.Series(True, index=df.index), "无条件（全部交易日）", "基准对照"),
    ]

    # ---- 图表数据 ----
    d10 = df[dates >= "2010-01-01"]
    chart_hist = {
        "dates": [str(d.date()) for d in d10["date"]],
        "close": [round(v, 1) for v in d10["close"]],
        "pctl": [None if not np.isfinite(v) else round(v * 100, 1) for v in d10["pctl"]],
        "sells": sell_dates,
        "buys": buy_dates,
    }
    d2 = df[dates >= "2024-06-01"]
    chart_now = {
        "dates": [str(d.date()) for d in d2["date"]],
        "close": [round(v, 1) for v in d2["close"]],
        "ma20": [None if not np.isfinite(v) else round(v, 1) for v in d2["ma20"]],
        "ma60": [None if not np.isfinite(v) else round(v, 1) for v in d2["ma60"]],
        "ma250": [None if not np.isfinite(v) else round(v, 1) for v in d2["ma250"]],
        "pctl": [None if not np.isfinite(v) else round(v * 100, 1) for v in d2["pctl"]],
    }

    return {"panel": panel, "strategy": strategy, "lines": lines,
            "episodes": eps, "stats": stats, "hist": chart_hist, "now": chart_now}


HTML = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>沪深300 现在怎么看 · 数据判读</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
:root{--bg:#0f1420;--card:#171e2e;--line:#25304a;--tx:#dce3f0;--mut:#8b97b0;--acc:#4f9cf9;
--red:#f0616d;--green:#3ddc97;--amber:#f5b942}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font:15px/1.75 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;padding:28px 16px 80px}
.wrap{max-width:1080px;margin:0 auto}
h1{font-size:26px;margin-bottom:4px}
h2{font-size:19px;margin:38px 0 12px;padding-left:10px;border-left:4px solid var(--acc)}
.sub{color:var(--mut);font-size:13px;margin-bottom:22px}
.verdict{background:linear-gradient(135deg,#1b2440,#171e2e);border:1px solid var(--line);border-radius:14px;padding:22px 24px;margin:18px 0}
.verdict .tag{display:inline-block;background:var(--amber);color:#20180a;font-weight:700;border-radius:6px;padding:1px 10px;font-size:13px;margin-bottom:10px}
.verdict p{margin:6px 0}
.verdict b{color:var(--amber)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:14px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .k{color:var(--mut);font-size:12px}
.card .v{font-size:21px;font-weight:700;margin-top:2px}
.card .d{font-size:12px;color:var(--mut)}
.neg{color:var(--red)}.pos{color:var(--green)}.amb{color:var(--amber)}
.chart{width:100%;height:420px;background:var(--card);border:1px solid var(--line);border-radius:12px;margin:12px 0}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden;font-size:13.5px;margin:12px 0}
th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);white-space:nowrap}
th{background:#1d2740;color:var(--mut);font-weight:600}
td:first-child,th:first-child{text-align:left}
tr:last-child td{border-bottom:none}
.hl{background:#20293f}
.note{color:var(--mut);font-size:13px;margin:8px 0}
.box{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin:12px 0}
.box ul{padding-left:20px}
.box li{margin:6px 0}
.concl .who{font-weight:700;color:var(--acc)}
.footer{margin-top:44px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
kbd{background:#20293f;border:1px solid var(--line);border-radius:4px;padding:0 6px;font-size:12px}
</style>
</head>
<body><div class="wrap">
<h1>沪深300 现在怎么看？</h1>
<div class="sub">数据截至 __DATE__（H00300 全收益 · 乐咕 PE-TTM · 滚动 5 年分位，无前视）｜由 hs300_view.py 生成，口径与 index.html 回测页一致</div>

<div class="verdict">
<span class="tag">一句话结论</span>
<p><b>本轮牛市的「估值过热加速段」已经结束，但当前不是反手做空的位置，更不是买入的位置。</b></p>
<p>框架信号：PE·30买90卖 已于 <b>__SELLDATE__</b> 触发清仓（分位>90%），此后指数 __SINCESELL__——规则已兑现。当前分位 <b>__PCTL__%</b>（6月底曾达 __PCTLPEAK__%），处在「不便宜、也不再极端贵」的中位区，且指数已跌破全部均线。历史同构状态下，<b>未来 6 个月中位收益约 -16%、胜率仅 20%</b>（短期赔率差）；12 个月中位数才回到 +4% 附近。</p>
<p>操作含义：<b>持币者继续等</b>——严格买回线在分位<30%（约 __PX30__ 点），宽松版<50%（约 __PX50__ 点）；<b>仍满仓未执行规则者</b>，此处已错过最优卖点，理性做法是降到底仓（30%）而非恐慌清零；<b>问「牛市结束了吗」</b>——加速段结束了，是否转入趋势性熊市，历史上此类形态（2008/2015/2018）多数继续下跌，但样本只有 6 段，无法给出确定答案。</p>
</div>

<h2>1. 当前仪表盘</h2>
<div class="cards" id="cards"></div>
<div class="note">隐含盈利 E=点位/PE：近 1 年盈利 +__EG1__%、2024-09 牛市启动以来 +__EGB__%——<b>本轮回撤主要是估值压缩</b>（PE 13.85→__PE__），盈利并未崩塌，这与 2015 年「盈利与估值双杀」不同，是「牛市未确认死亡」的一面证据。</div>

<h2>2. 本轮行情复盘（2024-06 起）</h2>
<div class="chart" id="cNow"></div>
<div class="box"><ul>
<li>本轮牛市：__BULLLO__（2024-02-02）→ 峰值 __BULLPEAK__（__BULLPEAKD__），最大涨幅 +__BULLGAIN__%；现价距峰值 <span class="neg">__DDBULL__%</span>，距低点仍有 +__GAINLO__%</li>
<li>分位路径：2026-04-10 首次突破 90%（策略清仓日）→ 6-22 随指数见顶冲到 __PCTLPEAK__% → 8 月底跌回 90% 下方 → 现在 __PCTL__%。<b>这是 2006 年以来第 5 轮 >90% 事件，前 4 轮之后 2 年内平均最大回撤 -39%</b></li>
<li>趋势：现价低于 MA20/60/120/250 全部均线（-3.9% ~ -7.4%），右侧无任何买入信号</li>
<li>本轮峰值 __BULLPEAK__ 并未超过 2021-02 的历史高点 __ATH__（当时 PE 17.0 vs 本轮峰值 PE 13.9）——本轮是「盈利驱动的温和牛」，泡沫程度远低于 2015/2021</li>
</ul></div>

<h2>3. 十六年全景：买卖点都发生在哪</h2>
<div class="chart" id="cHist"></div>
<div class="note">30买90卖 全部信号：买入 __BUYS__；卖出 __SELLS__。当前处于第三次空仓期。</div>

<h2>4. 历史对照：每次分位突破 90% 之后</h2>
<div id="tblEps"></div>
<div class="note">2026-04 这次形态最接近 <b>2015-04</b>（首次>90% → 约 2 个月后见顶 → 顶部回落）；与 2006/2020 的区别是：那两次触线后价格仍站在年线上方继续主升，这次触线后 5 个月内已破年线跌 13%。</div>

<h2>5. 条件收益：站在今天这个位置，历史上后来怎样</h2>
<div id="tblStats"></div>
<div class="chart" id="cStats" style="height:340px"></div>
<div class="note">聚类采样（同状态 21 日内只取首日）。「当前状态」= 分位 60~80% + 收盘低于 250 日线 + 60 日内分位触过 90%，历史上仅 6 段，置信度有限但方向一致：<b>短期继续消化，一年维度中性偏正</b>。</div>

<h2>6. 关键线位（当前 5 年窗口，假设盈利不变）</h2>
<div id="tblLines"></div>
<div class="note">窗口每月滚动，线位会随时间漂移；盈利若继续增长，对应点位会更高。</div>

<h2>7. 宏观背景</h2>
<div class="box"><ul>
<li>美联储 <b>2026-09-17 开启新一轮加息</b>（25bp，点阵图指向 12 月再加）——fed_cycle 实验：历史上「加息初期」前 12 个月沪深300 中位数 +8%、上涨占比 63%，但加息环境整体期望收益大幅下移（bootstrap 中位 +2.4%、亏损概率 46%）。「赔率变差，而非必跌」</li>
<li>国内盈利端尚未恶化（隐含 E 近 1 年 +__EG1__%），若盈利增速维持，估值消化的压力会小一半</li>
</ul></div>

<h2>8. 结论与操作建议</h2>
<div class="box concl">
<p style="margin-bottom:10px"><b>该买还是该卖？——都不该。这是「持币观望区」。</b></p>
<ul>
<li><span class="who">按框架执行者（已空仓）：</span>什么都不做。等分位 <30%（≈__PX30__ 点）再全仓买回；接受「过早抄底」实验结论的话，可把买回线放宽到 <50%（≈__PX50__ 点，历史代价仅 0.19pp/年）。距当前点位还有 -__GAP30__% / -__GAP50__% 空间，<b>不要试图抄「刚跌 13%」的底</b>——同构状态未来 6 个月中位数还有 -16%</li>
<li><span class="who">仍满仓者：</span>最优卖点（4 月，分位>90%，约 __SELLPX__ 点）已错过。此刻清仓是把「估值择时」做成「追跌杀跌」；建议执行底仓版规则：<b>减仓至 30% 底仓</b>，剩余资金入货基等待买回线，兼顾纪律与「万一是假摔」的容错</li>
<li><span class="who">工资流/定投者：</span>继续投，但按资金池规则降档——分位 60~80% 属「只投当月、不动池子」档；分位跌破 50% 后再开始动用池子加仓</li>
<li><span class="who">牛市结束了吗？</span>诚实回答：<b>「加速段」确定结束了</b>（分位 __PCTLPEAK__%→__PCTL__%、破年线、卖出信号已兑现）；<b>「趋势性熊市」未确认</b>——盈利仍在增长、峰值未超 2021 年高点、泡沫程度温和。历史基准率：同构状态 6 个月胜率 20%、12 个月胜率 60%，即<b>大概率还要磨，但不是 2015 式崩塌的赔率</b>。确认信号二选一：跌到买回线（分位<30~50%）→ 重新进场；或放量站回 MA250 且分位稳在 70% 上方 → 牛市延续，接受踏空成本</li>
</ul>
</div>

<div class="footer">
诚实标注：① 「当前状态」条件样本仅 6 段（2008/2015/2018/2021-22 为主），统计意义有限；② PE 尾部为乐咕月度粒度（ffill 到日）；③ 线位测算假设盈利不变；④ 回测口径：空仓 2%/年计息、无交易费用。本页由 <kbd>hs300_view.py</kbd> 生成，数据 <kbd>--update --update-only</kbd> 刷新。
</div>
</div>
<script>
const D = __DATA__;
const fmtPct = v => (v>0?'+':'')+v+'%';
const cls = v => v>0?'pos':(v<0?'neg':'');

// ---- cards ----
const P = D.panel;
const cards = [
 {k:'收盘（'+P.date+'）',v:P.close,d:'H00300 全收益'},
 {k:'PE-TTM',v:P.pe,d:'2021 年高点时为 '+P.pe_ath_2021},
 {k:'5年滚动分位',v:P.pctl+'%',d:'峰值 '+P.pctl_peak+'%（'+P.pctl_peak_date+'）',c:'amb'},
 {k:'距本轮峰值',v:fmtPct(P.dd_from_bull_peak),d:P.bull_peak_date+' 高点 '+P.bull_peak,c:'neg'},
 {k:'距历史最高',v:fmtPct(P.dd_from_ath),d:P.ath_date+' 高点 '+P.ath,c:'neg'},
 {k:'本轮牛市累计',v:fmtPct(P.gain_from_lo),d:'低点 '+P.bull_lo+'（'+P.bull_lo_date+'）峰值时 +'+P.bull_gain_peak+'%',c:'pos'},
 {k:'年内涨跌',v:fmtPct(P.ytd),d:'近1年 '+fmtPct(P.ret_1y),c:cls(P.ytd)},
 {k:'均线乖离',v:fmtPct(P.ma_dev.MA250),d:'MA20 '+fmtPct(P.ma_dev.MA20)+' / MA60 '+fmtPct(P.ma_dev.MA60)+' / 全部跌破',c:'neg'},
 {k:'策略当前仓位',v:D.strategy.position===0?'空仓':'满仓',d:'自 '+D.strategy.last_sell+' 清仓，此后 '+fmtPct(D.strategy.since_sell_ret),c:D.strategy.position===0?'amb':'pos'},
];
document.getElementById('cards').innerHTML = cards.map(c=>
 `<div class="card"><div class="k">${c.k}</div><div class="v ${c.c||''}">${c.v}</div><div class="d">${c.d}</div></div>`).join('');

const dark = {backgroundColor:'transparent',textStyle:{color:'#dce3f0'}};
const axis = {axisLine:{lineStyle:{color:'#3a4664'}},axisLabel:{color:'#8b97b0'},splitLine:{lineStyle:{color:'#1f2940'}}};

// ---- chart: now ----
(function(){
 const ch = echarts.init(document.getElementById('cNow'));
 const N = D.now;
 ch.setOption({...dark, tooltip:{trigger:'axis'},
  legend:{data:['收盘','MA20','MA60','MA250','分位%'],textStyle:{color:'#8b97b0'},top:4},
  grid:[{left:56,right:56,top:36,height:'52%'},{left:56,right:56,top:'72%',height:'20%'}],
  xAxis:[{type:'category',data:N.dates,...axis},{type:'category',gridIndex:1,data:N.dates,...axis,axisLabel:{show:false}}],
  yAxis:[{type:'value',scale:true,...axis,name:'点位'},{type:'value',gridIndex:1,min:0,max:100,...axis,name:'分位%'}],
  series:[
   {name:'收盘',type:'line',data:N.close,showSymbol:false,lineStyle:{width:2,color:'#4f9cf9'},
    markArea:{itemStyle:{color:'rgba(240,97,109,.08)'},data:[[{xAxis:D.strategy.last_sell},{xAxis:N.dates[N.dates.length-1]}]]},
    markLine:{symbol:'none',lineStyle:{color:'#f0616d',type:'dashed'},label:{color:'#f0616d',formatter:'清仓信号'},data:[{xAxis:D.strategy.last_sell}]}},
   {name:'MA20',type:'line',data:N.ma20,showSymbol:false,lineStyle:{width:1,color:'#f5b942'}},
   {name:'MA60',type:'line',data:N.ma60,showSymbol:false,lineStyle:{width:1,color:'#3ddc97'}},
   {name:'MA250',type:'line',data:N.ma250,showSymbol:false,lineStyle:{width:1.5,color:'#c084fc'}},
   {name:'分位%',type:'line',xAxisIndex:1,yAxisIndex:1,data:N.pctl,showSymbol:false,lineStyle:{width:1.5,color:'#8b97b0'},
    markLine:{symbol:'none',lineStyle:{type:'dashed',color:'#f0616d'},label:{color:'#8b97b0'},data:[{yAxis:90},{yAxis:30,lineStyle:{color:'#3ddc97'}}]}}
  ]});
 addEventListener('resize',()=>ch.resize());
})();

// ---- chart: hist ----
(function(){
 const ch = echarts.init(document.getElementById('cHist'));
 const H = D.hist;
 const mk = (arr,color,name,sym)=>({name,type:'scatter',data:arr.map(d=>{const i=H.dates.indexOf(d);return i<0?null:[i,H.close[i]]}).filter(Boolean),
   symbolSize:11,itemStyle:{color},z:10});
 ch.setOption({...dark, tooltip:{trigger:'axis'},
  legend:{data:['收盘','分位%','卖出(>90%)','买入(<30%)'],textStyle:{color:'#8b97b0'},top:4},
  grid:[{left:56,right:56,top:36,height:'52%'},{left:56,right:56,top:'72%',height:'20%'}],
  xAxis:[{type:'category',data:H.dates,...axis},{type:'category',gridIndex:1,data:H.dates,...axis,axisLabel:{show:false}}],
  yAxis:[{type:'log',logBase:10,...axis,name:'点位(log)'},{type:'value',gridIndex:1,min:0,max:100,...axis,name:'分位%'}],
  dataZoom:[{type:'inside',xAxisIndex:[0,1]}],
  series:[
   {name:'收盘',type:'line',data:H.close,showSymbol:false,lineStyle:{width:1.6,color:'#4f9cf9'}},
   mk(H.sells,'#f0616d','卖出(>90%)','pin'),
   mk(H.buys,'#3ddc97','买入(<30%)'),
   {name:'分位%',type:'line',xAxisIndex:1,yAxisIndex:1,data:H.pctl,showSymbol:false,lineStyle:{width:1.2,color:'#8b97b0'},
    markLine:{symbol:'none',lineStyle:{type:'dashed'},data:[{yAxis:90,lineStyle:{color:'#f0616d'}},{yAxis:30,lineStyle:{color:'#3ddc97'}}]}}
  ]});
 addEventListener('resize',()=>ch.resize());
})();

// ---- episodes table ----
(function(){
 const rows = D.episodes.map(e=>{
  const ong = e.ongoing;
  return `<tr${ong?' class="hl"':''}><td>${e.first90}</td><td>${e.days}</td><td>${e.peak_date}</td><td>${e.peak}</td>
  <td>${e.months_to_peak}</td><td class="neg">${e.maxdd_2y}%</td>
  <td class="${e.fwd12m==null?cls(e.so_far):cls(e.fwd12m)}">${e.fwd12m==null?'进行中（至今 '+fmtPct(e.so_far)+'）':fmtPct(e.fwd12m)}</td></tr>`;
 }).join('');
 document.getElementById('tblEps').innerHTML =
  `<table><tr><th>首次突破90%</th><th>持续交易日</th><th>其后峰值日(2y内)</th><th>峰值</th><th>触线→见顶(月)</th><th>2年内最大回撤</th><th>触线后12个月</th></tr>${rows}</table>`;
})();

// ---- stats table + chart ----
(function(){
 const rows = D.stats.map(s=>{
  const f=(t,h)=>{const r=s[t];return r?`<td class="${cls(r.med)}">${fmtPct(r.med)}</td><td>${fmtPct(r.mean)}</td><td>${r.win}%</td>`:`<td colspan="3">-</td>`};
  return `<tr><td style="text-align:left;white-space:normal">${s.label}<div class="note" style="margin:0">${s.note} · ${s.n} 段样本</div></td>${f('6m')}${f('12m')}</tr>`;
 }).join('');
 document.getElementById('tblStats').innerHTML =
  `<table><tr><th rowspan="2" style="text-align:left">状态</th><th colspan="3">未来 6 个月</th><th colspan="3">未来 12 个月</th></tr>
   <tr><th>中位</th><th>均值</th><th>胜率</th><th>中位</th><th>均值</th><th>胜率</th></tr>${rows}</table>`;
 const ch = echarts.init(document.getElementById('cStats'));
 const labels = D.stats.map(s=>s.label.split('：')[0].slice(0,14));
 const mkBar = (tag,key,color,name)=>({name,type:'bar',data:D.stats.map(s=>s[tag]?s[tag][key]:null),itemStyle:{color},label:{show:true,position:'top',color:'#8b97b0',formatter:p=>p.value+'%'}});
 ch.setOption({...dark,tooltip:{trigger:'axis'},
  legend:{data:['6个月中位','12个月中位','6个月胜率','12个月胜率'],textStyle:{color:'#8b97b0'},top:0},
  grid:{left:50,right:50,top:40,bottom:60},
  xAxis:{type:'category',data:labels,...axis,axisLabel:{color:'#8b97b0',interval:0,rotate:12,fontSize:11}},
  yAxis:[{type:'value',...axis,name:'收益中位%'},{type:'value',...axis,name:'胜率%',min:0,max:100,splitLine:{show:false}}],
  series:[mkBar('6m','med','#4f9cf9','6个月中位'),mkBar('12m','med','#3ddc97','12个月中位'),
   {name:'6个月胜率',type:'line',yAxisIndex:1,data:D.stats.map(s=>s['6m']?s['6m'].win:null),itemStyle:{color:'#f5b942'}},
   {name:'12个月胜率',type:'line',yAxisIndex:1,data:D.stats.map(s=>s['12m']?s['12m'].win:null),itemStyle:{color:'#f0616d'}}]});
 addEventListener('resize',()=>ch.resize());
})();

// ---- lines table ----
(function(){
 document.getElementById('tblLines').innerHTML =
  `<table><tr><th>线位</th><th>分位</th><th>对应 PE</th><th>隐含点位*</th><th>距现价</th></tr>` +
  D.lines.map(l=>`<tr><td style="text-align:left">${l.name}</td><td>${l.q}%</td><td>${l.pe}</td><td>${l.px}</td>
   <td class="${cls(Math.round((l.px/${CLOSE}-1)*1000)/10)}">${fmtPct(Math.round((l.px/${CLOSE}-1)*1000)/10)}</td></tr>`).join('') +
  `</table><div class="note">* 假设隐含盈利 E 不变：点位 = 现价 × (线位PE / 当前PE)</div>`;
})();
</script>
</body></html>
"""


def render(data):
    html = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    reps = {
        "__DATE__": data["panel"]["date"],
        "__SELLDATE__": data["strategy"]["last_sell"],
        "__SINCESELL__": f'指数 {data["strategy"]["since_sell_ret"]:+.1f}%（清仓价 {data["strategy"]["last_sell_price"]}）',
        "__PCTL__": str(data["panel"]["pctl"]),
        "__PCTLPEAK__": str(data["panel"]["pctl_peak"]),
        "__PX30__": str(data["lines"][0]["px"]),
        "__PX50__": str(data["lines"][1]["px"]),
        "__PE__": str(data["panel"]["pe"]),
        "__EG1__": str(data["panel"]["e_growth_1y"]),
        "__EGB__": str(data["panel"]["e_growth_since_bull"]),
        "__BULLLO__": str(data["panel"]["bull_lo"]),
        "__BULLPEAK__": str(data["panel"]["bull_peak"]),
        "__BULLPEAKD__": data["panel"]["bull_peak_date"],
        "__BULLGAIN__": str(data["panel"]["bull_gain_peak"]),
        "__DDBULL__": str(data["panel"]["dd_from_bull_peak"]),
        "__GAINLO__": str(data["panel"]["gain_from_lo"]),
        "__ATH__": str(data["panel"]["ath"]),
        "__BUYS__": "、".join(data["strategy"]["buys"]),
        "__SELLS__": "、".join(data["strategy"]["sells"]),
        "__SELLPX__": str(data["strategy"]["last_sell_price"]),
        "__GAP30__": str(round((1 - data["lines"][0]["px"] / data["panel"]["close"]) * 100, 1)),
        "__GAP50__": str(round((1 - data["lines"][1]["px"] / data["panel"]["close"]) * 100, 1)),
    }
    for k, v in reps.items():
        html = html.replace(k, v)
    html = html.replace("${CLOSE}", str(data["panel"]["close"]))
    with open(OUT, "w") as f:
        f.write(html)
    print("已生成", OUT)


if __name__ == "__main__":
    render(analyze())
