# -*- coding: utf-8 -*-
# gold_now.py — 黄金现况体检：继续持有 / 卖出 / 加仓的数据化答案
#
# 输出：gold_now.html（自包含 ECharts 分析页，不进入 index.html Tab 框架）
#
# 口径：
#   - 金价：Yahoo GC=F 历史缓存 + 新浪外盘期货 GC 日线增量（Yahoo 直连 403 时的备源，
#     两者同为 COMEX 主连，衔接处有 ~0.6% 快照口径差，不影响回撤/均线结论）
#   - 实际利率近似 = 名义 10Y（Yahoo ^TNX 缓存 + FRED DGS10 增量）− CPI 同比（multpl 月频）
#   - 回测起点 2001-06-01（与 backtest.py 黄金页一致），空仓 2%/年、债基 3%/年
#   - 全部信号只用当日及之前数据，无前视
# 运行：.venv/bin/python gold_now.py

import json
import os
import re

import numpy as np
import pandas as pd
import requests

import backtest as bt

DATA_DIR = bt.DATA_DIR
START = pd.Timestamp("2001-06-01")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


# ---------------------------------------------------------------- 数据增量刷新

def _session():
    s = requests.Session()
    s.trust_env = False  # 本机系统代理常年失效，直连
    s.headers.update(UA)
    return s


def refresh_data():
    """黄金=新浪GC日线、10Y=FRED DGS10、CPI=multpl，增量刷新缓存；失败保留旧缓存"""
    s = _session()
    # 1) 黄金
    try:
        r = s.get("https://stock2.finance.sina.com.cn/futures/api/jsonp.php/"
                  "var%20_GC=/GlobalFuturesService.getGlobalFuturesDailyKLine?symbol=GC",
                  headers={"Referer": "https://finance.sina.com.cn"}, timeout=20)
        arr = json.loads(r.text[r.text.index("(") + 1: r.text.rindex(")")])
        sina = pd.DataFrame([{"date": x["date"], "close": float(x["close"])} for x in arr])
        sina["date"] = pd.to_datetime(sina["date"])
        path = os.path.join(DATA_DIR, "gold_price.csv")
        g = pd.read_csv(path, parse_dates=["date"])
        new = sina[sina["date"] > g["date"].max()]
        if len(new):
            pd.concat([g, new]).sort_values("date").drop_duplicates("date").to_csv(path, index=False)
        print(f"gold +{len(new)} -> {sina['date'].max().date()}")
    except Exception as e:
        print("gold 刷新失败，用旧缓存:", e)
    # 2) 美债 10Y
    try:
        txt = s.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10", timeout=30).text
        rows = [l.split(",") for l in txt.strip().split("\n")[1:] if l and not l.startswith("DATE")]
        fred = pd.DataFrame([(d, float(v)) for d, v in rows if v not in (".", "")],
                            columns=["date", "close"])
        fred["date"] = pd.to_datetime(fred["date"])
        path = os.path.join(DATA_DIR, "ust10y.csv")
        u = pd.read_csv(path, parse_dates=["date"])
        new = fred[fred["date"] > u["date"].max()]
        if len(new):
            pd.concat([u, new]).sort_values("date").drop_duplicates("date").to_csv(path, index=False)
        print(f"ust10y +{len(new)} -> {fred['date'].max().date()}")
    except Exception as e:
        print("ust10y 刷新失败，用旧缓存:", e)
    # 3) CPI
    try:
        t = s.get("https://www.multpl.com/cpi/table/by-month", timeout=20).text
        rows = re.findall(r"<td>\s*([A-Za-z]+ \d{1,2}, \d{4})\s*</td>\s*<td>\s*"
                          r"(?:(?:<abbr[^>]*>\s*[^<]*\s*</abbr>)|\s*|&#x2002;)+\s*([0-9.]+)\s*</td>", t)
        cpi = pd.DataFrame(rows, columns=["date", "value"])
        cpi["date"] = pd.to_datetime(cpi["date"])
        cpi["value"] = pd.to_numeric(cpi["value"])
        cpi.sort_values("date").to_csv(os.path.join(DATA_DIR, "cpi.csv"), index=False)
        print(f"cpi -> {cpi['date'].max().date()}")
    except Exception as e:
        print("cpi 刷新失败，用旧缓存:", e)


# ---------------------------------------------------------------- 分析

def episodes(dfx, dd_th=-0.15, min_days=10, merge_gap=45):
    """「回撤≤dd_th 且 收于 MA200 下方」的连续段落，相邻间隔<merge_gap 天合并"""
    cond = (dfx["dd"] <= dd_th) & (dfx["close"] < dfx["ma200"])
    eps, inep = [], False
    for i in range(len(dfx)):
        if cond.iloc[i] and not inep:
            a, inep = i, True
        elif not cond.iloc[i] and inep:
            eps.append([a, i - 1]); inep = False
    if inep:
        eps.append([a, len(dfx) - 1])
    merged = []
    for a, b in eps:
        if merged and (dfx["date"].iloc[a] - dfx["date"].iloc[merged[-1][1]]).days <= merge_gap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    return [(a, b) for a, b in merged if b - a >= min_days]


def era_of(d):
    if d < pd.Timestamp("2010-01-01"):
        return "牛市中段回调"
    if d < pd.Timestamp("2016-06-01"):
        return "牛市终结·深熊"
    if d < pd.Timestamp("2020-01-01"):
        return "高位横盘"
    if d < pd.Timestamp("2025-01-01"):
        return "牛市中段回调"
    return "当前(2026)"


ERA_COLOR = {"牛市中段回调": "#c0392b", "牛市终结·深熊": "#27ae60",
             "高位横盘": "#95a5a6", "当前(2026)": "#e67e22"}


def main():
    refresh_data()
    df_full = bt.load_gold()
    close_all = df_full["close"]
    df_full["ma200"] = close_all.rolling(200).mean()
    df_full["ma50"] = close_all.rolling(50).mean()
    df_full["dd"] = close_all / close_all.cummax() - 1
    df = df_full[df_full["date"] >= START].reset_index(drop=True)

    # ---------------- 当前状态
    last = df_full["close"].iloc[-1]
    d_last = df_full["date"].iloc[-1]
    ma200_now = df_full["ma200"].iloc[-1]
    ma50_now = df_full["ma50"].iloc[-1]
    ath = close_all.cummax().iloc[-1]
    ath_date = df_full["date"].iloc[close_all.values.argmax()]
    dd_now = last / ath - 1
    r_all = close_all.pct_change()
    vol_now = r_all.rolling(20).std().iloc[-1] * np.sqrt(252)
    vol_hist = (r_all.rolling(20).std() * np.sqrt(252)).dropna()
    vol_pctl = float((vol_hist < vol_now).mean())
    infl = (df_full["cpi"] / df_full["cpi"].shift(252) - 1).replace([np.inf, -np.inf], np.nan)
    real = df_full["y10"] - infl * 100
    real_pctl = bt.percentile_series(pd.Series(real, index=df_full.index))
    grid_pos = 1.0 if dd_now < -0.30 else 0.8 if dd_now < -0.18 else 0.6 if dd_now < -0.08 else 0.3
    lvl_full = ath * 0.70          # 网格满仓线（-30%）
    lvl_ma200 = ma200_now          # 右侧确认线

    print(f"\n== 当前状态 {d_last.date()} ==")
    print(f"金价 {last:,.0f} | ATH {ath:,.0f}({ath_date.date()}) 回撤 {dd_now:+.1%}")
    print(f"vs MA200 {last/ma200_now-1:+.1%} | 死叉 {ma50_now < ma200_now} | "
          f"vol20 {vol_now:.1%}(分位{vol_pctl:.0%}) | 实际利率 {real.iloc[-1]:.2f}%(分位{real_pctl.iloc[-1]:.0%})")

    # ---------------- 策略回测（与黄金页同口径）
    _, nav_hold = bt.strategy_hold(df)
    pos_ma = bt.strategy_ma_trend(df)
    pos_cr = bt.strategy_ma_cross(df)
    pos_grid = bt.strategy_dip_grid(df)
    pos_vol = bt.strategy_vol_target(df)
    pos_rot = bt.strategy_rate_rotation(df)
    navs = {
        "满仓躺平": (nav_hold, None),
        "趋势·站上200日线": (bt.backtest(df, pos_ma), pos_ma),
        "双均线50/200": (bt.backtest(df, pos_cr), pos_cr),
        "抄底网格·越跌越买": (bt.backtest(df, pos_grid), pos_grid),
        "波动率目标12%": (bt.backtest(df, pos_vol), pos_vol),
        "黄金↔美债轮动": (bt.backtest_rotation(df, pos_rot), pos_rot),
        "金7债3·月再平衡": (bt.strategy_stock_bond(df, 0.7), None),
    }
    stats = {k: bt.metrics(v[0], v[1], nav_hold) for k, v in navs.items()}
    cur_pos = {"满仓躺平": 1.0, "趋势·站上200日线": pos_ma.iloc[-1], "双均线50/200": pos_cr.iloc[-1],
               "抄底网格·越跌越买": pos_grid.iloc[-1], "波动率目标12%": pos_vol.iloc[-1],
               "黄金↔美债轮动": pos_rot.iloc[-1], "金7债3·月再平衡": 0.7}
    print("\n== 策略(2001-06 起) ==")
    for k, m in stats.items():
        print(f"  {k}: 累计{m['total']*100:.0f}% 年化{m['cagr']*100:.1f}% 回撤{m['mdd']*100:.0f}% "
              f"夏普{m['sharpe']:.2f} | 当前仓位 {cur_pos[k]:.0%}")

    # ---------------- 历史类比段落
    dfx = df_full[["date", "close", "ma200", "dd"]].dropna().reset_index(drop=True)
    monthly = dfx.set_index("date")["close"].resample("M").last()
    eps = episodes(dfx)
    rows = []
    for a, b in eps:
        d0, p0 = dfx["date"].iloc[a], dfx["close"].iloc[a]
        d1 = dfx["date"].iloc[b]
        era = era_of(d0)
        seg12 = dfx[(dfx["date"] >= d0) & (dfx["date"] <= d0 + pd.DateOffset(months=12))]["close"]
        worse = seg12.min() / p0 - 1
        def fwd(mn):
            fut = monthly[monthly.index >= d0 + pd.DateOffset(months=mn)]
            return fut.iloc[0] / p0 - 1 if len(fut) else np.nan
        rows.append({"start": d0, "end": d1, "era": era, "dd0": dfx["dd"].iloc[a],
                     "months": (d1 - d0).days / 30.4, "worse": worse,
                     "f6": fwd(6), "f12": fwd(12), "ongoing": pd.isna(fwd(12))})
    done = [r for r in rows if not r["ongoing"]]
    f12 = np.array([r["f12"] for r in done])
    print("\n== 历史类比段（回撤≤-15% 且破 MA200）==")
    for r in rows:
        tag = "（进行中）" if r["ongoing"] else ""
        f6s = "-" if pd.isna(r["f6"]) else f"{r['f6']*100:+.0f}%"
        f12s = "-" if r["ongoing"] else f"{r['f12']*100:+.0f}%"
        print(f"  {r['start'].date()}~{r['end'].date()} [{r['era']}] 起点回撤{r['dd0']:+.0%} "
              f"12M内再跌{r['worse']:+.0%} 6M后{f6s} 12M后{f12s}{tag}")
    print(f"  12M后收益: 中位 {np.median(f12)*100:+.0f}% 均值 {f12.mean()*100:+.0f}% "
          f"为正占比 {(f12>0).mean()*100:.0f}%")

    # 无条件 12M 远期收益分布（对照）
    mret = monthly.pct_change(12).dropna()
    uncond = mret[mret.index >= START].values

    # ---------------- HTML
    def fp(x, sign=True):
        s = f"{x*100:+.1f}%" if sign else f"{x*100:.1f}%"
        return f'<span class="{"good" if x > 0 else "bad"}">{s}</span>'

    cards = f"""<div class="cards">
<div class="card hot"><div class="lbl">① 趋势 · 价格 vs MA200（{ma200_now:,.0f}）</div>
<div class="num bad">{last/ma200_now-1:+.1%}，线下 + 50/200 死叉</div>
<div class="lbl">单均线、双均线两套趋势策略当前均为<b>空仓/卖出</b>信号</div></div>
<div class="card hot"><div class="lbl">② 实际利率（10Y {df_full['y10'].iloc[-1]:.2f}% − CPI {infl.iloc[-1]*100:.1f}%）</div>
<div class="num bad">{real.iloc[-1]:.2f}%，5年分位 {real_pctl.iloc[-1]*100:.0f}%</div>
<div class="lbl">持金机会成本 5 年最高，轮动策略指向<b>持美债</b>；美联储 2026-09 重启加息</div></div>
<div class="card hot"><div class="lbl">③ 波动率 · 20日年化</div>
<div class="num bad">{vol_now:.0%}（历史 {vol_pctl*100:.0f}% 分位）</div>
<div class="lbl">波动率目标(12%)策略机械降仓至 <b>{min(0.12/vol_now,1)*100:.0f}%</b></div></div>
<div class="card cold"><div class="lbl">④ 回撤 · 距 ATH（{ath:,.0f}，{ath_date.date()}）</div>
<div class="num bad">{dd_now:+.1%}</div>
<div class="lbl">已进入抄底网格 <b>{grid_pos*100:.0f}% 档</b>（≥18%）；满仓线 ${lvl_full:,.0f}（-30%）</div></div>
</div>"""

    strat_rows = ""
    order = ["满仓躺平", "金7债3·月再平衡", "波动率目标12%", "双均线50/200", "趋势·站上200日线",
             "抄底网格·越跌越买", "黄金↔美债轮动"]
    for k in order:
        m = stats[k]
        cp = cur_pos[k]
        sig = "空仓/卖出" if cp <= 0.01 else ("满仓" if cp >= 0.99 else f"{cp*100:.0f}% 仓")
        cls = ' style="background:#fdf0ef"' if cp <= 0.55 and k not in ("满仓躺平", "金7债3·月再平衡") else ""
        strat_rows += (f"<tr{cls}><td>{k}</td><td>{m['total']*100:+,.0f}%</td>"
                       f"<td>{m['cagr']*100:.1f}%</td><td>{m['mdd']*100:.0f}%</td>"
                       f"<td>{m['sharpe']:.2f}</td><td><b>{sig}</b></td></tr>")
    strat_table = f"""<table>
<tr><th>策略（2001-06 起，与黄金页同口径）</th><th>累计</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>当前信号</th></tr>{strat_rows}</table>"""

    ep_rows = ""
    for r in rows:
        color = ERA_COLOR[r["era"]]
        f6s = "-" if pd.isna(r["f6"]) else fp(r["f6"])
        f12s = '<b>进行中</b>' if r["ongoing"] else fp(r["f12"])
        hl = ' style="outline:2px solid #e67e22;outline-offset:-2px"' if r["ongoing"] else ""
        ep_rows += (f"<tr{hl}><td>{r['start'].date()} → {r['end'].date()}（{r['months']:.0f} 个月）</td>"
                    f"<td><span style='color:{color}'>●</span> {r['era']}</td>"
                    f"<td>{r['dd0']*100:+.0f}%</td><td>{r['worse']*100:+.0f}%</td>"
                    f"<td>{f6s}</td><td>{f12s}</td></tr>")
    ep_table = f"""<table>
<tr><th>类比段（回撤≤-15% 且收于 MA200 下方）</th><th>时代背景</th><th>起点回撤</th><th>其后12M内再深跌</th><th>6个月后</th><th>12个月后</th></tr>{ep_rows}</table>"""

    decision = f"""<table>
<tr><th>动作</th><th>逻辑</th><th>触发条件（机械）</th><th>当前状态</th></tr>
<tr><td><b>继续持有</b><br><span class="muted">躺平 / 定投派</span></td>
<td style="text-align:left">26 年长牛年化 {stats['满仓躺平']['cagr']*100:.1f}%，回测里躺平总收益第一、定投流量版 XIRR 第一——长趋势资产「躲回撤的成本是踏空」。持有 = 赌央行购金/法币贬值叙事未变，与择时信号无关</td>
<td style="text-align:left">无卖出信号：这两个策略从不主动卖。代价：实际利率 {real.iloc[-1]:.1f}% 意味着持有的机会成本是 5 年最高</td>
<td>✓ 可执行，但要有「再磨 1 年」的心理预算（唯一的深亏样本 2012-2016 段 12M 后 -13%~-18%、期间再深跌 -25%）</td></tr>
<tr><td><b>卖出 / 减仓</b><br><span class="muted">趋势派</span></td>
<td style="text-align:left">趋势已确认破坏：跌破 MA200 + 50/200 死叉 + 波动率 88 分位 + 实际利率 93 分位且美联储重启加息——四信号齐发，与 2012-2016 那轮（唯一深亏样本：12M 后 -13%~-18%、期间再深跌 -25%）的宏观组合最像</td>
<td style="text-align:left">已触发（MA200 下方 {abs(last/ma200_now-1)*100:.1f}%）；趋势派回场条件 = 收盘重新站上 MA200（${lvl_ma200:,.0f}）或 50/200 金叉</td>
<td>✗ 信号成立——纯趋势账户此刻应为空仓/轻仓</td></tr>
<tr><td><b>换持美债</b><br><span class="muted">轮动派</span></td>
<td style="text-align:left">不赌金价方向，只切换「零息黄金 vs 生息美债」：实际利率高 = 黄金的持有劣势最大</td>
<td style="text-align:left">实际利率滚动 5 年分位 &gt;50% 持美债；当前 {real_pctl.iloc[-1]*100:.0f}%，票息 {df_full['y10'].iloc[-1]:.2f}%</td>
<td>✗ 信号指向美债；分位回落 ≤50% 才切回黄金</td></tr>
<tr><td><b>加仓</b><br><span class="muted">左侧网格</span></td>
<td style="text-align:left">只买不卖、越跌越买，赌长牛中的深回撤是黄金坑。回测里它回撤最浅但总收益跑输躺平（均仓 56% 踏空）——加仓的钱必须是「套三年也不动」的钱</td>
<td style="text-align:left">当前 -21.5% → <b>80% 仓档</b>（≥18%）；跌到 ${lvl_full:,.0f}（-30%）→ 满仓</td>
<td>△ 纪律执行中；再跌 8.5% 才到最后一档，左侧不猜底</td></tr>
<tr><td><b>加仓</b><br><span class="muted">右侧确认</span></td>
<td style="text-align:left">多付几个点买「趋势重新成立」的确定性：历史类比段里 V 型反转（2008/2021/2022）都伴随快速收复 MA200，右侧进场吃到主升；磨底段（2013-2015）则不会被假突破骗进去</td>
<td style="text-align:left">收盘站上 MA200（${lvl_ma200:,.0f}，还需 +{(lvl_ma200/last-1)*100:.0f}%）或 50 日上穿 200 日金叉</td>
<td>✗ 未触发——当前是「左侧已买、右侧未确认」的中间地带</td></tr>
</table>"""

    n_pos = int((f12 > 0.05).sum()); n_neg = int((f12 < -0.05).sum()); n_flat = len(f12) - n_pos - n_neg
    verdict = (
        f"黄金正处在 26 年来又一次<b>「深度回调 + 趋势破坏」</b>：现价 ${last:,.0f}，距 ATH 回撤 "
        f"{dd_now:.0%}，MA200 线下 {abs(last/ma200_now-1)*100:.0f}%、50/200 死叉、波动率 {vol_pctl*100:.0f} 分位、"
        f"实际利率 {real_pctl.iloc[-1]*100:.0f} 分位——<b>四个择时信号全部指向减仓</b>，背景是美联储 2026-09 重启加息。"
        f"历史类比段（{len(done)} 段已完结）12 个月后 {(f12>0).mean()*100:.0f}% 为正、中位 {np.median(f12)*100:+.0f}%"
        f"——<b>深回撤不是末日（胜率仍有 {(f12>0).mean()*100:.0f}%），但赢面被压薄：中位收益只有无条件持有"
        f"（中位 {np.median(uncond)*100:+.0f}%）的约三分之一</b>；"
        f"且两段深亏（2012、2013-2016：12M 后 -13%/-18%、期间再深跌 -25%）全部发生在「实际利率持续上行 + 加息」时代，"
        f"当前实际利率 93 分位 + 加息重启恰是这一类组合。<b>趋势派应减仓/离场，等右侧确认"
        f"（收盘站回 MA200 = ${lvl_ma200:,.0f} 或 50/200 金叉）；信仰派可持有、左侧网格按纪律执行"
        f"（当前 80% 档、满仓线 ${lvl_full:,.0f}），但要做好再磨一年的预算</b>。"
    )

    current_html = (
        f"<b>价格：</b>${last:,.0f}/盎司（{d_last.date()}，COMEX 主连）；ATH ${ath:,.0f}（{ath_date.date()}），"
        f"回撤 {dd_now:.1%}；7 月中曾最深 -25%。<br>"
        f"<b>利率：</b>名义 10Y {df_full['y10'].iloc[-1]:.2f}%（美联储 09-17 重启加息后快速上行），"
        f"CPI 同比 {infl.iloc[-1]*100:.2f}%，实际利率近似 {real.iloc[-1]:.2f}%，滚动 5 年分位 {real_pctl.iloc[-1]*100:.0f}%。<br>"
        f"<b>波动率：</b>20 日年化 {vol_now:.0%}（历史 {vol_pctl*100:.0f}% 分位），波动率目标策略自动降仓至 {min(0.12/vol_now,1)*100:.0f}%。<br>"
        f"<b>关键价位：</b>右侧确认线 MA200 = ${lvl_ma200:,.0f}（+{(lvl_ma200/last-1)*100:.0f}%）；"
        f"网格满仓线 = ${lvl_full:,.0f}（-30%，再跌 {(1-lvl_full/last)*100:.0f}%）；7 月低点 $3,986 为下方参照。"
    )

    edges = [-1, -0.3, -0.2, -0.1, 0, 0.1, 0.2, 0.3, 0.5, 10]
    labels = ["<-30%", "-30~-20", "-20~-10", "-10~0", "0~+10", "+10~+20", "+20~+30", "+30~+50", ">+50%"]
    h_ep, _ = np.histogram(f12, bins=edges)
    h_un, _ = np.histogram(uncond, bins=edges)

    # ---------------- 图数据
    dfp = df_full[df_full["date"] >= pd.Timestamp("2000-09-01")]
    data = {
        "price": [[str(d.date()), round(v, 1)] for d, v in zip(dfp["date"], dfp["close"])],
        "ma200": [[str(d.date()), None if pd.isna(v) else round(v, 1)] for d, v in zip(dfp["date"], dfp["ma200"])],
        "ma50": [[str(d.date()), None if pd.isna(v) else round(v, 1)] for d, v in zip(dfp["date"], dfp["ma50"])],
        "dd": [[str(d.date()), round(v * 100, 1)] for d, v in zip(dfp["date"], dfp["dd"])],
        "navs": {k: [[str(d.date()), round(v, 4)] for d, v in zip(df["date"], navs[k][0])] for k in navs},
        "real": [[str(d.date()), None if pd.isna(v) else round(v, 2)]
                 for d, v in zip(dfp["date"], pd.Series(real, index=df_full.index).reindex(dfp.index))],
        "ep_bars": [{"name": str(r["start"].year), "v": None if r["ongoing"] else round(r["f12"] * 100, 1),
                     "era": r["era"], "start": str(r["start"].date())} for r in rows],
        "ep_colors": ERA_COLOR,
        "hist_labels": labels,
        "hist_ep": [round(x / len(f12) * 100, 1) for x in h_ep],
        "hist_un": [round(x / len(uncond) * 100, 1) for x in h_un],
        "last": round(last, 0), "ma200_now": round(ma200_now, 0), "lvl_full": round(lvl_full, 0),
        "ath": round(ath, 0),
    }

    html = (PAGE
            .replace("__GEN__", pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__DATA_END__", str(d_last.date()))
            .replace("__VERDICT__", verdict)
            .replace("__CARDS__", cards)
            .replace("__CURRENT__", current_html)
            .replace("__STRAT_TABLE__", strat_table)
            .replace("__EP_TABLE__", ep_table)
            .replace("__DECISION__", decision)
            .replace("__N_POS__", str(n_pos)).replace("__N_NEG__", str(n_neg))
            .replace("__N_FLAT__", str(n_flat))
            .replace("__N_EP__", str(len(rows)))
            .replace("__REAL_NOW__", f"{real.iloc[-1]:.2f}%（5 年分位 {real_pctl.iloc[-1]*100:.0f}%）")
            .replace("__REAL_PCTL__", f"{real_pctl.iloc[-1]*100:.0f}%")
            .replace("__F12_MED__", f"{np.median(f12)*100:+.0f}%")
            .replace("__UNCOND_MED__", f"{np.median(uncond)*100:+.0f}%")
            .replace("__POS_RATE__", f"{(f12>0).mean()*100:.0f}%")
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold_now.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n已生成 {out}")


PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>黄金 -21% 回撤：持有、卖出还是加仓？</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#222;line-height:1.75}
h1{font-size:26px}h2{font-size:20px;margin-top:48px;border-left:4px solid #b8860b;padding-left:10px}
.chart{width:100%;height:420px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th,td{border:1px solid #ddd;padding:6px 10px;text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}
th{background:#f6f6f6}
.good{color:#c0392b}.bad{color:#27ae60}
.box{background:#faf6ec;border:1px solid #e8dcc0;border-radius:8px;padding:16px 20px;margin:16px 0}
.warn{background:#fdf0ef;border:1px solid #eec5c0}
.muted{color:#888;font-size:13px}
ul{padding-left:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.card{flex:1;min-width:230px;border-radius:8px;padding:14px 16px;border:1px solid #e0e0e0;background:#fff}
.card .num{font-size:22px;font-weight:700;margin:4px 0}
.card .lbl{font-size:13px;color:#666}
.card.hot{background:#fdf0ef;border-color:#eec5c0}
.card.cold{background:#eef7f0;border-color:#bfe3cb}
</style>
</head>
<body>
<h1>黄金 -21% 回撤：继续持有、卖出还是加仓？——用 26 年数据回答</h1>
<p class="muted">生成时间：__GEN__ ｜ 金价：COMEX 主连（Yahoo GC=F 缓存 + 新浪 GC 增量，至 __DATA_END__）｜ 利率：^TNX+FRED DGS10 ｜ CPI：multpl ｜ 口径见文末</p>

<div class="box">
<b>一句话结论：</b>__VERDICT__
</div>

<h2>0. 信号速览（4 个仪表盘）</h2>
__CARDS__

<h2>1. 现在处于什么位置？</h2>
<div class="box warn">
__CURRENT__
</div>
<div id="c1" class="chart" style="height:480px"></div>
<p class="muted">上图：金价（log）与 200 日/50 日均线；下图：距历史高点回撤。橙色虚线 = 当前网格满仓线（-30%）。</p>

<h2>2. 七套策略此刻在做什么（2001-06 起回测）</h2>
__STRAT_TABLE__
<div id="c2" class="chart"></div>
<p class="muted">红底行 = 当前给出减仓/空仓信号。回测印证黄金页老结论：躺平总收益第一，波动率目标夏普最高；此刻除躺平/金7债3/网格外全部在防守。</p>

<h2>3. 机制：黄金是实际利率的镜像</h2>
<p>实际利率近似 = 名义 10Y − CPI 同比（滚动 5 年分位，无前视）。实际利率低位 → 持零息黄金无成本 → 金价牛；实际利率上行 → 黄金的最大敌人。当前实际利率 __REAL_NOW__，分位 __REAL_PCTL__——2013 年（黄金见顶转熊）与 2020 年（黄金见顶）都发生在实际利率触底回升之后，本轮与之同构，且叠加美联储 2026-09 重启加息。</p>
<div id="c3" class="chart" style="height:440px"></div>

<h2>4. 历史类比：上一次「回撤≥15% + 跌破 MA200」之后发生了什么</h2>
<p>26 年里满足「回撤≤-15% 且跌破 MA200」的段落共 __N_EP__ 段（相邻 &lt;45 天合并），全部列出。结论不是「必跌」而是<b>赔率恶化</b>：12 个月后为正 __N_POS__ 段、明显为负 __N_NEG__ 段、±5% 内 __N_FLAT__ 段——胜率（__POS_RATE__）与无条件持有（76%）相当，但<b>中位收益只有 __F12_MED__，约为无条件持有中位 __UNCOND_MED__ 的一半</b>，赢面被显著压薄；而两段深亏（2012、2013-2016）都出现在「实际利率持续上行 + 加息」的宏观组合里，正是当下的处境。换言之：破趋势后硬扛，多数时候小赚、偶尔重伤，期望值明显不如平时。</p>
__EP_TABLE__
<div id="c4" class="chart" style="height:360px"></div>
<div id="c5" class="chart" style="height:360px"></div>
<p class="muted">左图：各段 12 个月后收益（橙 = 当前段，进行中）。右图：类比段 12M 远期收益分布 vs 无条件分布——「深回撤+破趋势」后买入的赔率整体左移。</p>

<h2>5. 决策框架：持有 / 卖出 / 加仓的触发条件</h2>
__DECISION__

<h2>6. 口径与免责</h2>
<ul class="muted">
<li>金价 2026-09-10 起为新浪外盘期货 GC 主连增量（Yahoo 直连不可达），与 Yahoo GC=F 衔接处有约 0.6% 快照口径差，不影响回撤/均线/信号结论。</li>
<li>实际利率 = 名义 10Y − CPI 同比，是近似（非 TIPS）；CPI 月频滞后发布，天然无前视。分位为滚动 5 年。</li>
<li>回测与 backtest.py 黄金页同口径：2001-06-01 起，空仓 2%/年、债基 3%/年，未计交易费用、展期成本与税费。</li>
<li>历史类比段仅 __N_EP__ 段，样本小，双峰结论是「情景分类」而非概率预测。</li>
<li>本页为数据整理与机械信号呈现，不构成投资建议。</li>
</ul>

<script>
const DATA = __DATA__;
const RED='#c0392b', GREEN='#27ae60', GOLD='#b8860b', GRAY='#95a5a6', BLUE='#2c3e50', ORANGE='#e67e22';

// ---- 图1：价格 + 均线 + 回撤
(function(){
  const ch = echarts.init(document.getElementById('c1'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['金价','MA200','MA50','距ATH回撤(右)']},
    grid:[{left:60,right:60,top:40,height:'52%'},{left:60,right:60,top:'72%',height:'20%'}],
    xAxis:[{type:'time',gridIndex:0},{type:'time',gridIndex:1,axisLabel:{show:false}}],
    yAxis:[{type:'log',name:'$/oz (log)',gridIndex:0},{type:'value',name:'回撤%',gridIndex:1,max:0,min:-50}],
    dataZoom:[{type:'inside',xAxisIndex:[0,1]},{type:'slider',xAxisIndex:[0,1]}],
    series:[
      {name:'金价',type:'line',showSymbol:false,data:DATA.price,lineStyle:{width:1.6,color:GOLD},
       markLine:{silent:true,symbol:'none',lineStyle:{type:'dashed'},
         data:[{yAxis:DATA.ath,label:{formatter:'ATH '+DATA.ath},lineStyle:{color:RED}},
               {yAxis:DATA.ma200_now,label:{formatter:'MA200 '+DATA.ma200_now},lineStyle:{color:BLUE}},
               {yAxis:DATA.lvl_full,label:{formatter:'网格满仓线 '+DATA.lvl_full},lineStyle:{color:ORANGE}}]}},
      {name:'MA200',type:'line',showSymbol:false,data:DATA.ma200,lineStyle:{width:1,color:BLUE}},
      {name:'MA50',type:'line',showSymbol:false,data:DATA.ma50,lineStyle:{width:1,color:GRAY}},
      {name:'距ATH回撤(右)',type:'line',xAxisIndex:1,yAxisIndex:1,showSymbol:false,data:DATA.dd,
       areaStyle:{color:'rgba(39,174,96,0.25)'},lineStyle:{width:1,color:GREEN}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图2：策略净值
(function(){
  const names = Object.keys(DATA.navs);
  const colors = {'满仓躺平':GOLD,'金7债3·月再平衡':'#d4a017','波动率目标12%':RED,'双均线50/200':BLUE,
                  '趋势·站上200日线':'#8e44ad','抄底网格·越跌越买':GREEN,'黄金↔美债轮动':ORANGE};
  const ch = echarts.init(document.getElementById('c2'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:names},
    grid:{left:60,right:20},
    xAxis:{type:'time'},
    yAxis:{type:'log',name:'净值(log)'},
    dataZoom:[{type:'inside'},{type:'slider'}],
    series:names.map(n=>({name:n,type:'line',showSymbol:false,data:DATA.navs[n],
      lineStyle:{width:n==='满仓躺平'?2:1.3,color:colors[n]}}))
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图3：实际利率 vs 金价
(function(){
  const ch = echarts.init(document.getElementById('c3'));
  ch.setOption({
    tooltip:{trigger:'axis'},
    legend:{data:['金价(log)','实际利率近似(右)']},
    grid:{left:60,right:60},
    xAxis:{type:'time'},
    yAxis:[{type:'log',name:'$/oz (log)'},{type:'value',name:'%',gridIndex:0}],
    dataZoom:[{type:'inside'},{type:'slider'}],
    series:[
      {name:'金价(log)',type:'line',showSymbol:false,data:DATA.price,lineStyle:{width:1.5,color:GOLD}},
      {name:'实际利率近似(右)',type:'line',yAxisIndex:1,showSymbol:false,data:DATA.real,
       lineStyle:{width:1.2,color:BLUE},
       markLine:{silent:true,symbol:'none',lineStyle:{color:GRAY,type:'dashed'},data:[{yAxis:0}]}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图4：各段 12M 后收益
(function(){
  const bars = DATA.ep_bars;
  const ch = echarts.init(document.getElementById('c4'));
  ch.setOption({
    tooltip:{trigger:'axis',formatter:p=>{const b=bars[p[0].dataIndex];return b.start+' 段<br>12M后: '+(b.v==null?'进行中':b.v+'%')+'<br>'+b.era;}},
    grid:{left:60,right:20},
    xAxis:{type:'category',data:bars.map(b=>b.v==null?b.name+'(当前)':b.name)},
    yAxis:{type:'value',name:'12个月后收益%'},
    series:[{type:'bar',data:bars.map(b=>({value:b.v==null?0:b.v,
        itemStyle:{color:b.v==null?ORANGE:(DATA.ep_colors[b.era]||GRAY),opacity:b.v==null?0.4:0.85}})),
      markLine:{silent:true,symbol:'none',lineStyle:{color:'#333'},data:[{yAxis:0}]}}]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

// ---- 图5：分布对比
(function(){
  const ch = echarts.init(document.getElementById('c5'));
  ch.setOption({
    tooltip:{},
    legend:{data:['类比段后12M','无条件任意时点12M']},
    grid:{left:60,right:20},
    xAxis:{type:'category',data:DATA.hist_labels,name:'12个月收益'},
    yAxis:{type:'value',name:'占比%',axisLabel:{formatter:'{value}%'}},
    series:[
      {name:'类比段后12M',type:'bar',data:DATA.hist_ep,itemStyle:{color:ORANGE}},
      {name:'无条件任意时点12M',type:'bar',data:DATA.hist_un,itemStyle:{color:GRAY}}
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
