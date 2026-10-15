# -*- coding: utf-8 -*-
# ashare_drop.py — 2026年10月 A股回调专题：跌在哪、贵不贵、是不是底、怎么办
#
# 输出：ashare_drop.html（自包含 ECharts 分析页，不进入 index.html Tab 框架）
#
# 口径：
#   - 价格/PE 全部用 data/ 本地缓存（先跑 backtest.py --update-data 刷新）
#   - 估值分位 = 滚动 5 年窗口、只用当日及之前数据，无前视（与 backtest.py 一致）
#   - 情景概率为主观判断，非预测；不构成投资建议
# 运行：.venv/bin/python ashare_drop.py

import json
import os

import numpy as np
import pandas as pd

import backtest as bt

DATA_DIR = bt.DATA_DIR
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ashare_drop.html")


def load_price(fname, dcol, vcol):
    df = pd.read_csv(os.path.join(DATA_DIR, fname))
    df = df[[dcol, vcol]].dropna()
    df.columns = ["date", "close"]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def pct_change(p, n):
    return float(p.iloc[-1] / p.iloc[-1 - n] - 1) if len(p) > n else None


def rolling_pctile(dates, vals, years=5):
    """滚动 N 年窗口分位（只用当日及之前），返回与 vals 等长的分位序列"""
    v = np.asarray(vals, dtype=float)
    d = pd.to_datetime(dates)
    out = np.full(len(v), np.nan)
    for i in range(len(v)):
        lo = d[i] - pd.Timedelta(days=365 * years)
        w = v[(d >= lo) & (d <= d[i])]
        w = w[~np.isnan(w)]
        if len(w) >= 20:
            out[i] = (w <= v[i]).mean()
    return out


def series_xy(df, cols, start=None, norm=False, step=1):
    """df: date + value cols -> {col: [[ts, v], ...]}；norm=True 时按起点归一 100"""
    if start is not None:
        df = df[df["date"] >= start].reset_index(drop=True)
    out = {}
    for c in cols:
        sub = df[["date", c]].dropna().iloc[::step]
        base = sub[c].iloc[0] if norm else 1.0
        out[c] = [[int(t.timestamp() * 1000), round(float(v) / base * (100 if norm else 1), 2)]
                  for t, v in zip(sub["date"], sub[c])]
    return out


# ---------------------------------------------------------------- 数据装载
hs = load_price("hs300_price.csv", "date", "close")
cyb = load_price("cyb_price.csv", "date", "close")
kcb = load_price("kcb50.csv", "日期", "收盘")
hldb = load_price("hldb.csv", "日期", "收盘")
a500 = load_price("a500.csv", "日期", "收盘")
hstech = load_price("hstech_price.csv", "date", "close")
ndx = load_price("ndx_price.csv", "date", "close")

hs_pe = pd.read_csv(os.path.join(DATA_DIR, "hs300_pe.csv"), parse_dates=["date"]).sort_values("date")
cyb_pe = pd.read_csv(os.path.join(DATA_DIR, "cyb_pe.csv"))
cyb_pe.columns = ["date", "idx", "pe"]
cyb_pe["date"] = pd.to_datetime(cyb_pe["date"])
cyb_pe = cyb_pe.sort_values("date")


def snapshot(name, df):
    p, d = df["close"], df["date"]
    last = float(p.iloc[-1])
    cutoff = d.iloc[-1] - pd.Timedelta(days=365)
    m = (d >= cutoff).values
    rpeak, rpeak_d = float(p[m].max()), d[m][p[m].idxmax()]
    return dict(name=name, date=str(d.iloc[-1].date()), last=round(last, 1),
                d5=pct_change(p, 5), d20=pct_change(p, 20), d60=pct_change(p, 60),
                rpeak=round(rpeak, 1), rpeak_date=str(rpeak_d.date()),
                dd=last / rpeak - 1)


SNAP = [snapshot("沪深300", hs), snapshot("创业板", cyb), snapshot("科创50", kcb),
        snapshot("中证A500", a500), snapshot("红利低波", hldb), snapshot("恒生科技", hstech)]

# 估值分位（当前）
hs_pct = rolling_pctile(hs_pe["date"], hs_pe["pe"])
cyb_pct = rolling_pctile(cyb_pe["date"], cyb_pe["pe"])
HS_PE_NOW, HS_PCT_NOW = float(hs_pe["pe"].iloc[-1]), float(hs_pct[-1])
CYB_PE_NOW, CYB_PCT_NOW = float(cyb_pe["pe"].iloc[-1]), float(cyb_pct[-1])
HS_PCT_PEAK26 = float(np.nanmax(hs_pct[hs_pe["date"] >= "2026-01-01"]))
HS_PCT_2021 = float(hs_pct[np.argmin(np.abs(hs_pe["date"] - pd.Timestamp("2021-02-10")))])

# 历史回撤段（HS300 峰值->谷底）
EPISODES = [("2007-10", "2008-11"), ("2009-08", "2012-12"), ("2015-06", "2016-01"),
            ("2018-01", "2019-01"), ("2021-02", "2024-02"), ("2026-06-22", None)]
eps_rows = []
for a, b in EPISODES:
    a = pd.Timestamp(a)
    seg = hs[hs["date"] >= a]
    seg = seg if b is None else seg[seg["date"] <= pd.Timestamp(b) + pd.Timedelta(days=40)]
    pk = hs.loc[hs["date"] <= a, "close"].iloc[-60:].max()
    tr = float(seg["close"].min())
    trd = seg.loc[seg["close"].idxmin(), "date"]
    dur = (trd - a).days // 30
    eps_rows.append(dict(start=str(a.date()), trough_date=str(trd.date()),
                         peak=round(pk), trough=round(tr), dd=tr / pk - 1, months=dur))

# 图表数据
merged = hs.merge(cyb, on="date", suffixes=("_hs", "_cyb")).merge(
    kcb.rename(columns={"close": "kcb"}), on="date").merge(
    hldb.rename(columns={"close": "hldb"}), on="date").merge(
    a500.rename(columns={"close": "a500"}), on="date")
merged = merged.rename(columns={"close_hs": "hs300"})
NORM = series_xy(merged, ["hs300", "close_cyb", "kcb", "hldb", "a500"],
                 start=pd.Timestamp("2025-01-01"), norm=True)

hs2y = series_xy(hs, ["close"], start=pd.Timestamp("2024-06-01"))
dd_full = hs.assign(dd=hs["close"] / hs["close"].cummax() - 1)
DD = [[int(t.timestamp() * 1000), round(float(v) * 100, 1)]
      for t, v in zip(dd_full["date"].iloc[::2], dd_full["dd"].iloc[::2])]

pct_s = pd.DataFrame({"date": hs_pe["date"], "pct": hs_pct}).dropna()
PCT5Y = [[int(t.timestamp() * 1000), round(float(v) * 100, 1)]
         for t, v in zip(pct_s["date"], pct_s["pct"]) if t >= pd.Timestamp("2010-01-01")]

AS_OF = max(s["date"] for s in SNAP)


def fp(x, nd=1):
    return f"{x * 100:+.{nd}f}%" if x is not None else "—"


def snap_table():
    rows = []
    for s in SNAP:
        color = "#c0392b" if s["dd"] > -0.10 else ("#b3541e" if s["dd"] > -0.20 else "#8e1b1b")
        rows.append(
            f"<tr><td>{s['name']}</td><td>{s['date']}</td><td>{s['last']:,.1f}</td>"
            f"<td>{fp(s['d5'])}</td><td>{fp(s['d20'])}</td><td>{fp(s['d60'])}</td>"
            f"<td>{s['rpeak']:,.1f}（{s['rpeak_date']}）</td>"
            f"<td style='color:{color};font-weight:600'>{fp(s['dd'])}</td></tr>")
    return "".join(rows)


def eps_table():
    rows = []
    for i, e in enumerate(eps_rows):
        tag = " <b style='color:#c0392b'>← 本次</b>" if i == len(eps_rows) - 1 else ""
        rows.append(f"<tr><td>{e['start']} → {e['trough_date']}{tag}</td>"
                    f"<td>{e['peak']:,} → {e['trough']:,}</td>"
                    f"<td style='font-weight:600'>{fp(e['dd'])}</td><td>约 {e['months']} 个月</td></tr>")
    return "".join(rows)


HTML = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A股这轮下跌怎么看 · 2026年10月数据体检</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
body{{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#222;line-height:1.75}}
h1{{font-size:26px}}h2{{font-size:20px;margin-top:48px;border-left:4px solid #c0392b;padding-left:10px}}
h3{{font-size:16px;margin-top:28px}}
.chart{{width:100%;height:420px;margin:16px 0}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:right;vertical-align:top}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#f6f6f6}}
.up{{color:#c0392b}}.down{{color:#27ae60}}
.box{{background:#fdf6f4;border:1px solid #eed2cc;border-radius:8px;padding:16px 20px;margin:16px 0}}
.note{{background:#f4f7fd;border:1px solid #ccd9f0}}
.muted{{color:#888;font-size:13px}}
ul,ol{{padding-left:22px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}}
.card{{flex:1;min-width:230px;border-radius:8px;padding:14px 16px;border:1px solid #e0e0e0;background:#fff}}
.card .num{{font-size:22px;font-weight:700;margin:4px 0}}
.card .lbl{{font-size:13px;color:#666}}
.card.hot{{background:#fdf0ef;border-color:#eec5c0}}
.card.cold{{background:#eef7f0;border-color:#bfe3cb}}
.card.mid{{background:#faf6ec;border-color:#e8dcc0}}
.tag{{display:inline-block;font-size:12px;background:#f0f0f0;border-radius:4px;padding:1px 7px;margin-right:6px;color:#555}}
</style>
</head>
<body>

<h1>A股这轮下跌怎么看——跌在哪、贵不贵、是不是底、怎么办</h1>
<p class="muted">数据截至 {AS_OF}（价格/PE 均为本地缓存实测值）｜ 估值分位 = 滚动 5 年窗口、无前视 ｜ 生成：ashare_drop.py</p>

<div class="box">
<b>一句话结论：</b>这不是一场「系统性崩盘」，而是一轮<b>以科技/成长为震中的结构性杀估值</b>——沪深300 自 6 月峰值 7,517 点回撤 <b>-13.8%</b>，但创业板 <b>-32%</b>、科创50 <b>-34%</b>，同期红利低波 <b>逆势 +6%</b>。流动性危机说不成立（危机里红利不会涨）；更像「拥挤的科技交易出清 + 资金切向防御」，历史上最像 <b>2021 年初</b>。估值上，沪深300 PE {HS_PE_NOW:.1f}、5年分位 {HS_PCT_NOW:.0%}——<b>不便宜、也不算泡沫</b>，按本实验室「30% 分位以下才买」的纪律，<b>尚未进入抄底区</b>；当前 -14% 的回撤深度在历史上的五次大回撤（-31% ~ -72%）面前只算「中段」。高仓位是否割肉取决于持有什么：宽基/红利在这个分位恐慌卖出历史上大概率是错的，高估值科技仓位则应按风险预算机械处理，而不是按情绪处理。
</div>

<h2>0. 信号速览</h2>
<div class="cards">
<div class="card mid"><div class="lbl">① 沪深300 回撤（峰值 7,517 · 2026-06-22）</div>
<div class="num up">-13.8%</div>
<div class="lbl">近 5 日 -4.5%、近 20 日 -5.0%——<b>最近一周在加速</b></div></div>
<div class="card hot"><div class="lbl">② 震中在科技（自 6 月峰值）</div>
<div class="num up">创业板 -32% · 科创50 -34%</div>
<div class="lbl">恒生科技自去年 10 月峰值已 <b>-37.5%</b></div></div>
<div class="card cold"><div class="lbl">③ 防御资产在涨（近 60 日）</div>
<div class="num down">红利低波 +6.2%</div>
<div class="lbl">分化剧烈 = 结构性调整，<b>不是流动性危机</b>的典型形态</div></div>
<div class="card mid"><div class="lbl">④ 估值 · 沪深300 PE-TTM</div>
<div class="num">{HS_PE_NOW:.1f} 倍（5年分位 {HS_PCT_NOW:.0%}）</div>
<div class="lbl">中性偏上，<b>未到 ≤30% 的买点区</b>；2021 年顶部时约 {HS_PCT_2021:.0%}</div></div>
</div>

<h2>1. 跌了多少、跌在哪？</h2>
<table>
<tr><th>指数</th><th>数据至</th><th>收盘</th><th>近5日</th><th>近20日</th><th>近60日</th><th>近1年峰值</th><th>距峰值回撤</th></tr>
{snap_table()}
</table>
<div class="chart" id="c_norm"></div>
<p>一句话读图：<b>同样的「A股下跌」，买的是不同东西，体验完全不同</b>。2025 年以来创业板/科创50 最多时翻倍有余，6 月见顶后吐出大半涨幅；红利低波几乎是另一条水平线。所以「下跌主要跌在哪」的答案非常清楚：<b>跌在前期涨幅最大、估值最贵的科技与成长，大盘价值和红利基本没跌</b>。</p>

<h2>2. 这个点位，A股贵不贵？</h2>
<table>
<tr><th>指数</th><th>当前 PE-TTM</th><th>5年滚动分位</th><th>读法</th></tr>
<tr><td>沪深300</td><td>{HS_PE_NOW:.1f}</td><td>{HS_PCT_NOW:.0%}</td><td>中性偏上。不是 2021 年顶部（分位约 {HS_PCT_2021:.0%}）那种泡沫，但离「便宜」（≤30%）还有距离</td></tr>
<tr><td>创业板</td><td>{CYB_PE_NOW:.1f}</td><td>{CYB_PCT_NOW:.0%}</td><td>跌了三成<b>仍不便宜</b>——因为之前涨得更多，盈利增速消化估值需要时间</td></tr>
</table>
<div class="chart" id="c_pct"></div>
<p>结论：<b>「跌了很多」≠「便宜」</b>。沪深300 从 6 月高点 14 倍 PE 回到 {HS_PE_NOW:.1f} 倍，只是从「偏贵」回到「中性偏上」；按本实验室的历史回测纪律（30 买 90 卖），现在既不是卖点（90% 以上）也不是买点（30% 以下），属于<b>持有观望区</b>。</p>

<h2>3. 下跌的原因：流动性？国家队？还是别的？</h2>
<p class="muted">以下为基于价格结构的推断（本页不含新闻数据），按证据强度排序：</p>
<h3>① 拥挤的科技交易出清（证据最强）</h3>
<ul>
<li>创业板/科创50 从 2025 年初到 2026 年 6 月涨幅超过一倍，PE 分位一度逼近区间顶部，积累了大量获利盘；</li>
<li>6 月见顶后持续阴跌、最近一周加速（科创50 近 5 日 -12.3%），是典型的高位股「多杀多」形态；</li>
<li>恒生科技（同样是中国科技资产）从 2025 年 10 月就已见顶、至今 -37.5%——<b>这轮调整实际上从去年四季度就在港股开始了</b>，A股科技是滞后补跌。</li>
</ul>
<h3>② 不像流动性危机（反向证据）</h3>
<ul>
<li>流动性危机的特征是<b>无差别抛售</b>：股票、信用债、红利、黄金一起跌（参考 2008、2020 年 3 月）；</li>
<li>当前红利低波近 60 日 <b>+6.2%</b>、沪深300 仅 -14%，资金明显是从高估值板块<b>搬家</b>到防御板块，而不是离场——这更像风格再平衡。</li>
</ul>
<h3>③ 「国家队没托市？」——无法直接观测，但有两个事实</h3>
<ul>
<li>沪深300/大盘明显比科技抗跌，与历史上「稳定资金护大盘蓝筹、不护题材股」的行为模式一致（如 2024 年初微盘崩盘期间）；</li>
<li>即便有托底资金，其目标是「防系统性风险」而非「保住个股成本价」——<b>把抄底决策建立在国家队一定会救的假设上，历史上代价很高</b>。</li>
</ul>
<h3>④ 外部对照：不是全球 risk-off</h3>
<ul>
<li>同期纳指100 创历史新高（10 月 6 日）、标普500 新高——全球风险偏好并不差；</li>
<li>黄金自 1 月峰值 -21%。资金在全球范围内仍偏向风险资产，A股科技的下跌是<b>中国成长资产自身的估值消化</b>，不是被外部带崩。</li>
</ul>

<h2>4. 历史上有类似的情况吗？</h2>
<table>
<tr><th>回撤段（峰值 → 谷底）</th><th>沪深300 点位</th><th>最大跌幅</th><th>下跌时长</th></tr>
{eps_table()}
</table>
<div class="chart" id="c_dd"></div>
<p>当前 -13.8% 的回撤，在历史上的五次大调整（-31% ~ -72%）面前<b>只走到中段偏浅的位置</b>。结构上最像的两段：</p>
<ul>
<li><b>2021 年初（相似度最高）</b>：结构牛见顶 → 前期抱团资产（当时是白酒/医药，现在是科技）杀估值 → 红利/价值相对抗跌 → 最终演变成三年熊市、指数 -42%。不同点：当前沪深300 整体分位（{HS_PCT_NOW:.0%}）明显低于 2021 年 2 月（约 {HS_PCT_2021:.0%}），<b>整体泡沫程度更轻，全面转熊的估值基础比那次弱</b>。</li>
<li><b>2015 年 7-8 月</b>：同样是杠杆牛后成长股崩、大盘蓝筹抗跌。不同点：2015 年 6 月沪深300 分位接近 100%，当前估值水位低得多。</li>
</ul>
<p>历史给的两个教训：<b>①结构牛结束后的第一波下跌，通常不是最后一波；②但只要整体估值不在极值区，宽基在 -15% 附近恐慌割肉，事后看大概率是错的</b>（2018 年 10 月、2024 年 2 月皆是）。</p>

<h2>5. 这里是底部吗？能抄底吗？</h2>
<div class="box note">
<b>底部无法预测，但可以用纪律替代预测。</b>按本实验室的回测框架：
<ul>
<li><b>估值维度</b>：沪深300 分位 {HS_PCT_NOW:.0%}，未到 ≤30% 的买点线；按「阶梯仓位·越便宜越重仓」，当前档位只配中等仓位，<b>不是梭哈的位置</b>。</li>
<li><b>深度维度</b>：-14% 在历史回撤谱中是中段；若真进入买点区（分位 ≤30%），对应沪深300 大约还要再跌一段——抄底资金应<b>分批、按估值档位加仓</b>，而不是一次打满。</li>
<li><b>结构维度</b>：想抄「跌得最狠的」（创业板 -32%）？注意其 PE 分位仍有 {CYB_PCT_NOW:.0%}——<b>跌得多和便宜是两回事</b>，历史上接飞刀的亏损大多来自这个混淆。</li>
<li><b>右侧信号</b>（出现任何一个都说明环境在变好）：沪深300 分位回到 40% 以下；科技缩量企稳且红利开始跑输（风格再切回）；政策层面出现明确的稳增长/流动性信号。</li>
</ul>
</div>

<h2>6. 仓位很高，要割肉吗？</h2>
<p>没有一个答案适合所有人，但有一套<b>检查清单</b>（按顺序过一遍）：</p>
<ol>
<li><b>持有什么？</b> 宽基（沪深300/中证A500/红利）在 {HS_PCT_NOW:.0%} 分位 + -14% 回撤的位置恐慌卖出，历史上大概率错；高估值科技个股/主题基金则是另一套风险预算逻辑，不能把「宽基的经验」套上去。</li>
<li><b>集中度多少？</b> 单一行业/主题超过总仓位 30% 的，问题不是「割不割」，而是<b>本来就不该这么集中</b>——反弹中降集中度，比下跌中割在恐慌里好。</li>
<li><b>钱有没有期限？</b> 未来 12 个月内要用的钱不该在权益里；这部分无论涨跌都应撤出。剩下的长钱，才谈得上「扛波动」。</li>
<li><b>能不能机械执行？</b> 与其纠结「割肉还是死扛」，不如定一条规则（如「分位 ≥90% 卖、≤30% 买、中间不动」）并执行——本实验室的回测显示，<b>有纪律的中等策略长期跑赢无纪律的聪明判断</b>。</li>
</ol>

<h2>7. 后续怎么演变？四种情景（未来 6-12 个月，主观概率）</h2>
<table>
<tr><th>情景</th><th>路径</th><th>主观概率</th><th>触发/验证信号</th></tr>
<tr><td><b>A. 风格切换型调整延续</b>（类 2021 上半年）</td><td>科技继续补跌或阴跌磨人，红利/价值扛跌，沪深300 在 6,000-6,800 区间震荡磨底</td><td><b>45%</b></td><td>分化延续：红利跑赢、科技缩量</td></tr>
<tr><td><b>B. 中级熊市开启</b>（类 2021-2024 全程）</td><td>杀估值扩散到全市场，沪深300 再跌 20%+ 至 5,000-5,500 区间，历时 1 年以上</td><td><b>25%</b></td><td>盈利下修 + 分位跌破 30% 仍无承接</td></tr>
<tr><td><b>C. 牛市中继、快速修复</b></td><td>政策/流动性催化，科技止跌，指数 1-2 个季度内重回 7,500 上方</td><td><b>20%</b></td><td>放量收复 6,800 + 分位不再创新低</td></tr>
<tr><td><b>D. 外部系统性冲击</b></td><td>全球 risk-off 共振（美股从历史新高转跌），A股短期急跌 -25%+</td><td><b>10%</b></td><td>纳指跌破年线、红利/黄金同跌</td></tr>
</table>
<p class="muted">概率是主观判断而非预测，合计 100%；用处是<b>提前想好每种情景下自己做什么</b>，而不是赌哪一种会发生。当前证据最支持 A：分化剧烈、防御走强、整体估值不在极值。</p>

<h2>口径与免责</h2>
<p class="muted">
数据：沪深300/创业板/科创50/红利低波/中证A500 价格与 PE 来自本地缓存（中证官网/乐咕/新浪，至 {AS_OF}）；估值分位为滚动 5 年窗口、只用当日及之前数据，无前视。恒生科技/纳指为 Yahoo/新浪缓存。<br>
本页为个人研究笔记，<b>不构成投资建议</b>；情景概率为主观判断。历史规律不代表未来。
</p>

<script>
const pal = {{hs300:'#c0392b', close_cyb:'#e67e22', kcb:'#8e44ad', hldb:'#27ae60', a500:'#2f6fed'}};
const nameMap = {{hs300:'沪深300', close_cyb:'创业板', kcb:'科创50', hldb:'红利低波', a500:'中证A500'}};
const NORM = {json.dumps(NORM)};
echarts.init(document.getElementById('c_norm')).setOption({{
  title:{{text:'2025年以来各指数走势（2025-01 起点 = 100）——跌在哪，一目了然',left:'center',textStyle:{{fontSize:14}}}},
  tooltip:{{trigger:'axis'}}, legend:{{bottom:0}},
  grid:{{left:50,right:20,top:50,bottom:50}},
  xAxis:{{type:'time'}}, yAxis:{{type:'value',scale:true}},
  series:Object.keys(NORM).map(k=>({{name:nameMap[k],type:'line',showSymbol:false,
    lineStyle:{{width:k==='hs300'?2.4:1.6}},color:pal[k],data:NORM[k]}}))
}});

echarts.init(document.getElementById('c_pct')).setOption({{
  title:{{text:'沪深300 PE-TTM 滚动5年分位（%）——当前 {HS_PCT_NOW:.0%}，30% 以下才是买点区',left:'center',textStyle:{{fontSize:14}}}},
  tooltip:{{trigger:'axis'}}, grid:{{left:50,right:20,top:50,bottom:40}},
  xAxis:{{type:'time'}}, yAxis:{{type:'value',min:0,max:100}},
  series:[{{type:'line',showSymbol:false,color:'#2f6fed',data:{json.dumps(PCT5Y)},
    markLine:{{data:[{{yAxis:30,label:{{formatter:'买点线 30%'}}}},{{yAxis:90,label:{{formatter:'卖点线 90%'}}}}],
      lineStyle:{{color:'#c0392b',type:'dashed'}}}}}}]
}});

const HS2Y = {json.dumps(hs2y["close"])};
echarts.init(document.getElementById('c_dd')).setOption({{
  title:{{text:'沪深300 历史回撤（水下曲线，%）——当前 -14% 在历史中的位置',left:'center',textStyle:{{fontSize:14}}}},
  tooltip:{{trigger:'axis'}}, grid:{{left:50,right:20,top:50,bottom:40}},
  xAxis:{{type:'time'}}, yAxis:{{type:'value',max:0}},
  series:[{{type:'line',showSymbol:false,color:'#c0392b',areaStyle:{{color:'#c0392b22'}},
    data:{json.dumps(DD)}}}]
}});
</script>
</body>
</html>
"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)
print("已生成", OUT)
print(f"沪深300 PE {HS_PE_NOW:.1f} 分位 {HS_PCT_NOW:.0%} | 创业板 PE {CYB_PE_NOW:.1f} 分位 {CYB_PCT_NOW:.0%}")
print("回撤段:", [(e['start'], f"{e['dd']:.1%}") for e in eps_rows])
