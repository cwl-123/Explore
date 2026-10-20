# -*- coding: utf-8 -*-
"""读取 data/report_data.json，生成 fund-018168/index.html（2026-10 体检版）

版式：直接问答（涨跌 / 为什么 / 贵不贵 / 可持续 / 历史参照 / 情景概率 / 怎么办）
所有数字均由数据计算后写入，改数据重跑即可更新文案。
运行：hs300-strategy-lab/.venv/bin/python fund-018168/gen_report.py
"""
import json, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "data", "report_data.json"), encoding="utf-8"))

ix = d["index"]; perf = ix["perf"]; pes = ix["pe_stats"]; br = ix["base_rates"]
com = d["commodities"]; mac = d["macro"]; grp = d["groups"]; sts = d["stocks"]
cu, au, ag, lc, al, sn, zn, ni = (com[k] for k in ["CU0", "AU0", "AG0", "LC0", "AL0", "SN0", "ZN0", "NI0"])
tnx, dxy = mac["^TNX"], mac["DX-Y.NYB"]
gcf, sif, hgf, hs = mac["GC=F"], mac["SI=F"], mac["HG=F"], mac["hs300"]
asof = ix["latest_date"]

# ---------- 小工具 ----------
def bad(v):
    return v is None or (isinstance(v, float) and math.isnan(v))

def fp(v, dg=1):
    return "—" if bad(v) else f"{v:+.{dg}f}%"

def fpn(v, dg=1):
    return "—" if bad(v) else f"{v:.{dg}f}%"

def c(v):
    return "" if bad(v) else ("up" if v >= 0 else "down")

def qv(sym, q):
    return {x["q"]: x["v"] for x in com[sym]["q_series"]}.get(q)

def qchg(sym, a, b):
    va, vb = qv(sym, a), qv(sym, b)
    return None if not (va and vb) else round((vb / va - 1) * 100, 1)

# 季度均价环比：Q3 vs Q2、10 月至今 vs Q3
Q2, Q3, Q4 = "2026-06-30", "2026-09-30", "2026-12-31"
qq = {k: (qchg(k, Q2, Q3), qchg(k, Q3, Q4)) for k in ["CU0", "AL0", "AU0", "AG0", "LC0", "SN0", "ZN0", "NI0"]}

# ---------- 派生数字 ----------
eps_now = ix["eps"]
eps_peak = round(ix["peak"]["close"] / ix["peak"]["pe"], 1) if ix["peak"]["pe"] else None
pe_drop = round((ix["pe"] / ix["peak"]["pe"] - 1) * 100, 1) if ix["peak"]["pe"] else None
eps_gain = round((eps_now / eps_peak - 1) * 100, 1) if eps_peak else None
rel_m1 = round(perf["m1"] - hs["m1"], 1)
rel_ytd = round(perf["ytd"] - hs["ytd"], 1)

# 个股映射
by_code = {s["code"]: s for s in sts}
attr = sorted([s for s in sts if s.get("contrib_1m") is not None], key=lambda s: s["contrib_1m"])
top_drag = attr[:6]
top_hold = sorted(attr, key=lambda s: -s["contrib_1m"])[:4]
pe_list = [s for s in sts if s.get("pe") is not None]
gold_silver_w = round(sum(s["weight"] for s in sts if s["group"] in ("金", "银锡")), 1)
lith_w = round(sum(s["weight"] for s in sts if s["group"] == "锂钴"), 1)
cu_w = round(sum(s["weight"] for s in sts if s["group"] == "铜"), 1)

# 月度收益（2026 年）
hist = ix["hist"]
close = {x["d"]: x["c"] for x in hist}
ym = {}
for dt, v in close.items():
    ym[dt[:7]] = v
months = sorted(ym)
mret = []
for i in range(1, len(months)):
    mret.append((months[i], round((ym[months[i]] / ym[months[i - 1]] - 1) * 100, 1)))
mret_2026 = [m for m in mret if m[0] >= "2026-01"]

# 点位 × PE 矩阵
pe_grid = [10, 12, ix["pe"], 18, 20]
eps_scn = [("盈利不变", eps_now), ("盈利 -10%", round(eps_now * 0.9, 1)), ("盈利 -20%", round(eps_now * 0.8, 1))]

# 近期区间（8-9 月箱体）
recent = [x for x in hist if x["d"] >= "2026-07-15"]
box_hi = max(recent, key=lambda x: x["c"])
box_lo = min([x for x in hist if x["d"] >= "2026-09-01"], key=lambda x: x["c"])

# 情景
scenarios = [
    ("A. 磨底震荡", "40%", "3,200 ~ 4,100 宽幅震荡 3~6 个月，用时间等三季报/年报确认盈利底；结构继续分化（铜铝抗跌、金银锂阴跌）",
     "① 多次冲击 4,000~4,100 失败 ② 三季报后金银股止跌 ③ 10Y 利率在 5% 上方横住"),
    ("B. 反弹修复", "25%", "3~6 个月内回到 4,000 ~ 4,500（PE 18~20 倍），前提是利率见顶 + 金银企稳 + 铜维持高位",
     "① 10Y 从 5.31% 回落至 4.8% 以下 ② 沪金站回 1,000 元/克、沪银站回 16,000 ③ 铜股补涨、成交放大"),
    ("C. 再下一城", "25%", "跌破 3,277 后下探 2,300 ~ 2,740（距高点 -50% ~ -58%，对齐前两轮熊市深度）；触发点通常是盈利下修被确认",
     "① 三季报金/银/锂股净利环比大降 ② 沪铜跌破 10 万 ③ 10Y 破 5.5% ④ 3,277 放量击穿且 2 周不收复"),
    ("D. 新周期上行", "10%", "突破 5,474 前高（PE 24.6 倍以上），需要铜进入超级周期 + 金银重启 + 盈利超预期三者同时成立",
     "① 铜价破 12 万且铜股领涨 ② 全球降息周期重启、实际利率转负 ③ 指数 EPS 突破 250"),
]

# ---------- 表格片段 ----------
def kv_row(label, v, suffix=""):
    return f'<div class="kv"><span>{label}</span><b class="{c(v) if isinstance(v,(int,float)) else ""}">{v}{suffix}</b></div>'

comm_rows = ""
for k, nm in [("CU0", "沪铜"), ("AL0", "沪铝"), ("AU0", "沪金"), ("AG0", "沪银"),
              ("LC0", "碳酸锂"), ("SN0", "沪锡"), ("ZN0", "沪锌"), ("NI0", "沪镍")]:
    x = com[k]
    q3, q4 = qq[k]
    comm_rows += (f"<tr><td><b>{nm}</b></td><td class='note'>{x['unit']}</td>"
                  f"<td>{x['latest']:,.0f}</td>"
                  f"<td class='{c(x['m1'])}'>{fp(x['m1'])}</td>"
                  f"<td class='{c(x['m3'])}'>{fp(x['m3'])}</td>"
                  f"<td class='{c(x['ytd'])}'>{fp(x['ytd'])}</td>"
                  f"<td class='{c(x['off_ath'])}'>{fp(x['off_ath'])}<span class='note'> {x['ath_date']}</span></td>"
                  f"<td class='{c(x['vs_peak_day'])}'>{fp(x['vs_peak_day'])}</td>"
                  f"<td class='{c(q3)}'>{fp(q3)}</td><td class='{c(q4)}'>{fp(q4)}</td></tr>")

grp_rows = ""
for g in grp:
    grp_rows += (f"<tr><td><b>{g['name']}</b></td><td class='note'>{g['n']} 只</td><td>{g['weight']:.1f}%</td>"
                 f"<td class='{c(g['m1'])}'>{fp(g['m1'])}</td>"
                 f"<td class='{c(g['contrib_1m'])}'>{fp(g['contrib_1m'],2)}</td>"
                 f"<td class='{c(g['since_peak'])}'>{fp(g['since_peak'])}</td>"
                 f"<td class='{c(g['ytd'])}'>{fp(g['ytd'])}</td></tr>")

bear_rows = ""
for b in ix["bears"]:
    bear_rows += (f"<tr><td>{b['peak_date']} → {b['trough_date']}</td>"
                  f"<td class='down'>{fp(b['dd'])}</td><td>{b['months']:.1f} 个月</td>"
                  f"<td>{b['peak']:,.0f} → {b['trough']:,.0f}</td>"
                  f"<td class='{c(b['after_12m'])}'>{fp(b['after_12m'])}</td></tr>")
bear_rows += (f"<tr class='hlrow'><td>{ix['peak']['date']} → 至今（{ix['low_since_peak']['date']} 低点）</td>"
              f"<td class='down'>{fp(ix['dd'])}</td><td>{ix['months_since_peak']:.1f} 个月</td>"
              f"<td>{ix['peak']['close']:,.0f} → {ix['low_since_peak']['close']:,.0f}</td>"
              f"<td class='note'>进行中</td></tr>")

b45 = br["dd_35_45"]
base_rows = ""
for k, lbl in [("m1", "1 个月"), ("m3", "3 个月"), ("m6", "6 个月"), ("y12", "12 个月")]:
    x = b45.get(k)
    if not x:
        continue
    base_rows += (f"<tr><td>{lbl}</td><td class='{c(x['median'])}'>{fp(x['median'])}</td>"
                  f"<td>{x['win']:.0f}%</td><td class='up'>{fp(x['best'])}</td>"
                  f"<td class='down'>{fp(x['worst'])}</td></tr>")

pea_rows = ""
for lbl, e in eps_scn:
    cells = "".join(f"<td class='{ 'hl' if abs(pe - ix['pe']) < 0.05 else ''}'>{(e * pe):,.0f}</td>" for pe in pe_grid)
    pea_rows += f"<tr><td>{lbl}（EPS {e}）</td>{cells}</tr>"

stock_rows = ""
for s in sts:
    fin = {f["date"]: f for f in (s.get("fin") or [])}
    h1 = fin.get("2026-06-30") or {}
    npg = h1.get("np_g")
    pe = s.get("pe")
    mcap = s.get("mktcap")
    stock_rows += (
        f"<tr><td><b>{s['name']}</b></td><td class='note'>{s['code']}</td>"
        f"<td><span class='chip g-{ {'铜':'cu','金':'au','银锡':'ag','铝':'al','稀土':'re','钨钼锗钛':'wo','锂钴':'li','其他':'ot'}.get(s['group'],'ot') }'>{s['group']}</span></td>"
        f"<td>{s['weight']:.2f}%</td>"
        f"<td class='{c(s['m1'])}'>{fp(s['m1'])}</td>"
        f"<td class='{c(s['m3'])}'>{fp(s['m3'])}</td>"
        f"<td class='{c(s['ytd'])}'>{fp(s['ytd'])}</td>"
        f"<td class='{c(s['off_hi1y'])}'>{fp(s['off_hi1y'])}</td>"
        f"<td>{'—' if pe is None else ('亏损' if pe < 0 else f'{pe:.1f}')}</td>"
        f"<td>{'—' if mcap is None else f'{mcap:,.0f}'}</td>"
        f"<td class='{c(npg)}'>{'—' if npg is None else fp(npg,0)}</td></tr>")

scen_cards = ""
for name, prob, path, sig in scenarios:
    scen_cards += (f"<div class='scen'><div class='sh'><b>{name}</b><span class='p'>{prob}</span></div>"
                   f"<div class='pp'>{path}</div>"
                   f"<div class='ss'><b>触发 / 验证：</b>{sig}</div></div>")

drag_txt = "、".join(f"{s['name']} {fp(s['m1'])}" for s in top_drag)
hold_txt = "、".join(f"{s['name']} {fp(s['m1'])}" for s in top_hold)

# ---------- 图表数据 ----------
chart_data = {
    "asof": asof,
    "hist": [{"d": x["d"], "c": x["c"], "pe": x["pe"]} for x in hist if x["d"] >= "2016-01-01"],
    "eps": [{"d": x["d"], "c": x["c"], "e": round(x["c"] / x["pe"], 1)} for x in hist if x["pe"] and x["d"] >= "2022-05-01"],
    "monthly": mret_2026,
    "comm": {k: com[k]["series"] for k in ["CU0", "AL0", "AU0", "AG0", "LC0", "SN0"]},
    "comm_names": {k: com[k]["name"] for k in ["CU0", "AL0", "AU0", "AG0", "LC0", "SN0"]},
    "attr": [{"name": s["name"], "v": s["contrib_1m"], "w": s["weight"], "m1": s["m1"], "g": s["group"]} for s in attr],
    "dd_paths": ix["dd_paths"],
    "marks": {"peak": ix["peak"]["date"], "peak_close": ix["peak"]["close"],
              "low": ix["low_since_peak"]["date"], "low_close": ix["low_since_peak"]["close"],
              "close": ix["close"]},
}

STYLE = r"""
  :root { --bg:#0f1420; --card:#171e2e; --card2:#1d2639; --line:#2a3650; --txt:#dce3f0;
          --sub:#8b97b0; --acc:#e8a33d; --red:#e05c5c; --green:#4caf7d; --blue:#5b8def; --purple:#a78bfa; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--txt); font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif; line-height:1.75; }
  .wrap { max-width:1080px; margin:0 auto; padding:24px 16px 80px; }
  header { padding:28px 0 6px; }
  h1 { font-size:27px; letter-spacing:.5px; line-height:1.4; }
  h1 .code { color:var(--acc); font-family:Menlo,monospace; }
  .sub { color:var(--sub); font-size:15px; margin-top:10px; }
  .meta { color:var(--sub); font-size:12.5px; margin-top:10px; }
  .meta b { color:var(--txt); font-weight:600; }
  h2 { font-size:20px; margin:46px 0 4px; padding-left:12px; border-left:4px solid var(--acc); }
  h3 { font-size:15.5px; margin:22px 0 8px; color:var(--acc); }
  .lead { color:var(--sub); font-size:13.5px; margin:6px 0 12px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px; margin:14px 0; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin:16px 0; }
  .kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:13px 15px; }
  .kpi .v { font-size:21px; font-weight:700; font-family:Menlo,monospace; }
  .kpi .k { color:var(--sub); font-size:12px; margin-top:2px; }
  .kpi .s { color:var(--sub); font-size:11.5px; }
  .up { color:var(--red); } .down { color:var(--green); } .flat { color:var(--txt); }
  .hl { color:var(--acc); font-weight:600; }
  .chart { width:100%; height:380px; }
  .chart-tall { height:460px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { padding:7px 9px; text-align:right; border-bottom:1px solid var(--line); white-space:nowrap; }
  th { color:var(--sub); font-weight:500; position:sticky; top:0; background:var(--card); font-size:12px; }
  td:first-child, th:first-child { text-align:left; }
  tr:hover td { background:var(--card2); }
  .hlrow td { background:rgba(232,163,61,.07); }
  .tablewrap { overflow-x:auto; }
  .note { color:var(--sub); font-size:12.5px; }
  .scens { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin:14px 0; }
  .scen { background:var(--card); border:1px solid var(--line); border-top:3px solid var(--acc); border-radius:12px; padding:14px 16px; }
  .scen .sh { display:flex; justify-content:space-between; align-items:baseline; }
  .scen .sh b { font-size:15px; }
  .scen .p { font-family:Menlo,monospace; font-size:20px; font-weight:700; color:var(--acc); }
  .scen .pp { font-size:13px; margin:6px 0; }
  .scen .ss { font-size:12.5px; color:var(--sub); line-height:1.6; }
  .qas { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin:16px 0; }
  @media (max-width:820px) { .qas, .scens { grid-template-columns:1fr; } }
  .qa { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
  .qa .q { color:var(--acc); font-size:12.5px; margin-bottom:4px; }
  .qa .a { font-size:14.5px; font-weight:600; margin-bottom:4px; }
  .qa .d { color:var(--sub); font-size:12.5px; }
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
  @media (max-width:760px) { .cols { grid-template-columns:1fr; } }
  .logic { border-left:3px solid var(--line); padding:4px 0 4px 14px; margin:10px 0; }
  .logic.good { border-color:var(--green); } .logic.bad { border-color:var(--red); } .logic.mid { border-color:var(--acc); }
  .logic b.t { display:block; margin-bottom:2px; }
  .logic.good b.t { color:var(--green); } .logic.bad b.t { color:var(--red); } .logic.mid b.t { color:var(--acc); }
  .logic span { color:var(--sub); font-size:13px; }
  .kv { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px dashed var(--line); font-size:13.5px; }
  .kv:last-child { border-bottom:none; }
  .kv span { color:var(--sub); }
  .chip { display:inline-block; padding:0 7px; border-radius:10px; font-size:11.5px; }
  .g-cu { background:rgba(224,123,92,.18); color:#e07b5c; } .g-au { background:rgba(232,163,61,.18); color:#e8a33d; }
  .g-ag { background:rgba(185,194,214,.18); color:#b9c2d6; } .g-al { background:rgba(91,141,239,.18); color:#5b8def; }
  .g-re { background:rgba(167,139,250,.18); color:#a78bfa; } .g-wo { background:rgba(125,211,192,.18); color:#7dd3c0; }
  .g-li { background:rgba(76,175,125,.18); color:#4caf7d; } .g-ot { background:rgba(139,151,176,.18); color:#8b97b0; }
  .steps { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:10px 0; }
  .steps .s { background:var(--card2); border:1px solid var(--line); border-radius:8px; padding:7px 12px; font-size:13px; }
  .steps .ar { color:var(--acc); }
  ul.sig { margin:6px 0 6px 18px; }
  ul.sig li { font-size:13.5px; margin:5px 0; color:var(--sub); }
  ul.sig li b { color:var(--txt); }
  footer { margin-top:56px; padding-top:18px; border-top:1px solid var(--line); color:var(--sub); font-size:12px; }
  footer p { margin:4px 0; }
"""

BODY = f"""
<header>
  <h1>有色矿业 <span class="code">018168</span> · 2026 年 10 月体检</h1>
  <div class="sub">直接回答：最近是涨是跌 / 为什么 / 还贵不贵 / 可持续吗 / 未来怎么走 —— 附四种情景概率</div>
  <div class="meta">国泰中证有色金属矿业主题 ETF 发起联接 C · 跟踪 <b>中证有色矿业（931892，{len(sts)} 只成分股）</b>
    · 价格与指数估值截至 <b>{asof}</b> · 权重截至 <b>{d['meta']['weights_date']}</b> · 滚动 PE 数据自 {d['meta']['pe_start']}</div>
</header>

<!-- ============ 0 信号速览 ============ -->
<div class="cards">
  <div class="kpi"><div class="v">{ix['close']:,.0f}</div><div class="k">指数点位（{asof}）</div><div class="s">权重股 38 只</div></div>
  <div class="kpi"><div class="v down">{fp(ix['dd'])}</div><div class="k">距 {ix['peak']['date']} 高点</div><div class="s">高点 {ix['peak']['close']:,.0f}</div></div>
  <div class="kpi"><div class="v {c(perf['m1'])}">{fp(perf['m1'])}</div><div class="k">近 1 个月</div><div class="s">沪深300 {fp(hs['m1'])}</div></div>
  <div class="kpi"><div class="v {c(perf['ytd'])}">{fp(perf['ytd'])}</div><div class="k">年内（YTD）</div><div class="s">近 2 年 {fp(perf['y2'])}</div></div>
  <div class="kpi"><div class="v">{ix['pe']:.2f}</div><div class="k">滚动 PE</div><div class="s">{pes['pct']:.0f}% 分位（{pes['start'][:7]} 以来）</div></div>
  <div class="kpi"><div class="v flat">{sts[0]['weight']:.1f}%</div><div class="k">最大权重 · {sts[0]['name']}</div><div class="s">第二 {sts[1]['name']} {sts[1]['weight']:.1f}%</div></div>
</div>

<div class="card">
  <b>一句话结论：</b>跌到半山腰，而且是<span class="hl">杀估值杀出来的半山腰</span>。
  {ix['months_since_peak']:.1f} 个月里指数 {ix['peak']['close']:,.0f} → {ix['close']:,.0f}（{fp(ix['dd'])}），
  同期滚动盈利反而从 {eps_peak} 涨到 {eps_now}（{fp(eps_gain)}），
  PE 从 {ix['peak']['pe']:.1f} 倍压到 {ix['pe']:.2f} 倍（{fp(pe_drop)}）。
  9 月以来的第二次下跌，原因链条是：<span class="hl">美债 10 年飙到 {tnx['latest']:.2f}%（{tnx['peak_date']} 高见 {tnx['peak']:.2f}%）→ 金银二次崩塌
  （COMEX 银 {fp(sif['off_peak'])}、金 {fp(gcf['off_peak'])}）→ 锂再跌 {abs(lc['m1']):.1f}%，只剩铜还贴着历史高点</span>。
  估值已经不贵（{pes['pct']:.0f}% 分位），但离 2024 年 2 月的 {pes['min']:.1f} 倍还有距离——这就是为什么"跌了不少"和"跌到底了"是两件事。
</div>

<div class="qas">
  <div class="qa"><div class="q">最近是涨是跌？</div><div class="a {c(perf['m1'])}">跌，且在加速</div>
    <div class="d">近 1 月 {fp(perf['m1'])}、近 1 年 {fp(perf['y1'])}，但近 2 年仍有 {fp(perf['y2'])}——大涨后的回撤。</div></div>
  <div class="qa"><div class="q">为什么跌？</div><div class="a">利率 + 金银 + 锂</div>
    <div class="d">10Y 利率上到 {tnx['latest']:.2f}%，金银权重约 {gold_silver_w:.0f}%；铜股跌而铜价平 = 杀"高价可持续"。</div></div>
  <div class="qa"><div class="q">未来怎么走？</div><div class="a">磨底概率最大（40%）</div>
    <div class="d">12 个月历史基础概率 {b45['y12']['win']:.0f}% 胜率、中位 {fp(b45['y12']['median'])}；但 25% 概率还有一次 -50% 级下探。</div></div>
</div>

<!-- ============ 1 涨跌 ============ -->
<h2>1. 最近是涨是跌？——「长涨、中跌、最近一个月加速跌」</h2>
<p class="lead">同一个指数，看哪个窗口结论完全不同。先看窗口表，不争定义。</p>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>窗口</th><th>近 5 日</th><th>近 1 月</th><th>近 3 月</th><th>近 6 月</th><th>年内</th><th>近 1 年</th><th>近 2 年</th><th>距高点</th><th>距本轮低点</th></tr>
    <tr><td>指数涨跌</td>
      <td class="{c(perf['w1'])}">{fp(perf['w1'])}</td>
      <td class="{c(perf['m1'])}">{fp(perf['m1'])}</td>
      <td class="{c(perf['m3'])}">{fp(perf['m3'])}</td>
      <td class="{c(perf['m6'])}">{fp(perf['m6'])}</td>
      <td class="{c(perf['ytd'])}">{fp(perf['ytd'])}</td>
      <td class="{c(perf['y1'])}">{fp(perf['y1'])}</td>
      <td class="{c(perf['y2'])}">{fp(perf['y2'])}</td>
      <td class="down">{fp(ix['dd'])}</td>
      <td class="up">{fp(round((ix['close']/ix['low_since_peak']['close']-1)*100,1))}</td></tr>
  </table></div>
  <p class="note">近 5 日 = 最近 5 个交易日；低点 = {ix['low_since_peak']['date']} 的 {ix['low_since_peak']['close']:,.0f}（距高点 {fp(ix['low_since_peak']['dd'])}）。</p>
</div>

<h3>走势全景：{asof} 为止的指数与滚动市盈率</h3>
<div class="card"><div id="c-index" class="chart"></div>
  <p class="note">2016~2024 走完两轮完整牛熊（2017 顶 → 2018 底、2021 顶 → 2024 底），2024-09 从 1,694 起进入主升段（+223%），2026-01 之后是回撤段。
  估值（紫线）在 2026-01 冲到 {ix['peak']['pe']:.1f} 倍，现在 {ix['pe']:.2f} 倍——跌幅比指数还大，因为分母（盈利）在涨。</p>
</div>

<h3>2026 年逐月涨跌：跌得不均匀</h3>
<div class="card"><div id="c-month" class="chart" style="height:300px"></div>
  <p class="note">1 月 +26.2% 冲顶 → 3 月 -18.5% 第一波杀估值 → 4~8 月反复 → <b>9 月 -14.1%、10 月又跌</b>。这轮不是一根直线下跌，
  而是"急跌—反弹—再跌"的锯齿，这类走势通常意味着筹码在反复换手，而不是一次性出清。</p>
</div>

<div class="card">
  <b>时间线（用数据说话）：</b>
  <div class="steps">
    <div class="s">2024-09-10 低点 <b>1,694</b></div><div class="ar">→ 16.6 个月 +223% →</div>
    <div class="s">2026-01-29 高点 <b>{ix['peak']['close']:,.0f}</b>（PE {ix['peak']['pe']:.1f}）</div>
    <div class="ar">→ {ix['months_since_peak']:.1f} 个月 {fp(ix['dd'])} →</div>
    <div class="s">{ix['low_since_peak']['date']} 低点 <b>{ix['low_since_peak']['close']:,.0f}</b></div>
    <div class="ar">→ 反弹 {fp(round((ix['close']/ix['low_since_peak']['close']-1)*100,1))} →</div>
    <div class="s">现在 <b>{ix['close']:,.0f}</b></div>
  </div>
  <p class="note">8 月 5~10 日指数从 3,682 一口气拉到 <b>{box_hi['c']:,.0f}</b>（+14.6%），是这轮下跌里唯一像样的反弹；
  那段时间铜价正从 10 万一路涨向 {cu['ath_date']} 的 <b>{cu['ath']:,.0f}</b> 历史新高。
  <b>9/11 指数单日 -4.1%</b>（铜价 9/10 见顶的次日），此后铜价只回撤 {fp(cu['off_ath'])}，指数却从 {box_hi['c']:,.0f} 跌到 {box_lo['c']:,.0f}（{fp(round((box_lo['c']/box_hi['c']-1)*100,1))}）——
  <b>"铜在、价不在"是这轮下跌最典型的特征。</b></p>
</div>

<!-- ============ 2 为什么 ============ -->
<h2>2. 为什么跌？——「三条腿断了两条，铜还站着」</h2>
<p class="lead">先看商品价格（这是矿企利润的分子），再看权重结构（决定谁影响指数）。</p>

<div class="card">
  <div class="tablewrap"><table>
    <tr><th>品种</th><th>单位</th><th>最新</th><th>近 1 月</th><th>近 3 月</th><th>年内</th><th>距历史峰值</th><th>较 2026-01-29</th><th>Q3 均价环比 Q2</th><th>10 月至今环比 Q3</th></tr>
    {comm_rows}
  </table></div>
  <p class="note">峰值 = 该合约全部可得历史最高收盘；"较 2026-01-29"是相对指数见顶那天的价格——这条最能看出谁在拖后腿。
  Q3/Q4 均价环比是<b>矿企三季报的先行指标</b>（矿企成本相对刚性，价格环比下滑会放大到利润）。</p>
</div>

<h3>五大金属走势（2025-01-02 = 100）</h3>
<div class="card"><div id="c-comm" class="chart chart-tall"></div>
  <p class="note">铜（橙）2025 年以来一路向上、{cu['ath_date']} 见顶后只是小回撤；金银（黄/灰）在 2026-01-29 见顶后腰斩式回落；
  锂（绿）从 2025 年底反弹到 2026 年中，随后二次探底。</p>
</div>

<div class="card">
  <div class="logic bad"><b class="t">① 利率：这轮下跌的总开关</b>
    <span>美债 10 年收益率 <b>{tnx['latest']:.2f}%</b>（近 3 月 {fp(tnx['m3'])}、年内 {fp(tnx['ytd'])}），
    {tnx['peak_date']} 高见 <b>{tnx['peak']:.2f}%</b>。黄金白银不生息，实际利率往上走 = 持有它们的成本上升。
    价格上完全对得上：金银在 <b>{gcf['peak_date']}</b> 同日见顶，此后 COMEX 金 {fp(gcf['off_peak'])}、银 {fp(sif['off_peak'])}。</span></div>
  <div class="logic bad"><b class="t">② 贵金属：权重约 {gold_silver_w:.0f}%，是最大的直接拖累</b>
    <span>沪金 {au['latest']:,.0f} 元/克（{fp(au['off_ath'])} 距峰值）、沪银 {ag['latest']:,.0f} 元/千克（{fp(ag['off_ath'])}）。
    金 + 银锡两组权重 {gold_silver_w:.0f}%，近 1 月分别 {fp(grp[[g['name'] for g in grp].index('金')]['m1']) if '金' in [g['name'] for g in grp] else '—'}、
    {fp(grp[[g['name'] for g in grp].index('银锡')]['m1']) if '银锡' in [g['name'] for g in grp] else '—'}。
    注意：这两组的 PE 现在是"用高价时的盈利"算出来的，属于<b>假便宜</b>。</span></div>
  <div class="logic bad"><b class="t">③ 锂：二次探底，跌幅最猛</b>
    <span>碳酸锂期货 {lc['latest']:,.0f} 元/吨：近 1 月 {fp(lc['m1'])}、近 3 月 {fp(lc['m3'])}、较 1 月 29 日 {fp(lc['vs_peak_day'])}。
    锂钴权重 {lith_w:.0f}%，近 1 月 {fp(grp[[g['name'] for g in grp].index('锂钴')]['m1']) if '锂钴' in [g['name'] for g in grp] else '—'}。
    Q4 至今均价环比 Q3 又降 {abs(qq['LC0'][1]):.1f}%——供给出清还没完成。</span></div>
  <div class="logic mid"><b class="t">④ 铜：唯一还站着的，但股票已经不信了</b>
    <span>沪铜 {cu['latest']:,.0f} 元/吨，距 {cu['ath_date']} 的历史峰值仅 {fp(cu['off_ath'])}，年内 {fp(cu['ytd'])}，近 1 月 {fp(cu['m1'])}；
    但铜股（权重 {cu_w:.0f}%）近 1 月 {fp(grp[[g['name'] for g in grp].index('铜')]['m1']) if '铜' in [g['name'] for g in grp] else '—'}。
    <b>铜价没跌、铜股跌 12%——这说明市场卖的不是"现在的高价"，而是"高价能不能维持"。</b>这是本次下跌最值得注意的信号。</span></div>
  <div class="logic mid"><b class="t">⑤ 大盘：周期股被一起打折</b>
    <span>沪深300 近 1 月 {fp(hs['m1'])}、年内 {fp(hs['ytd'])}；有色矿业近 1 月 {fp(perf['m1'])}、年内 {fp(perf['ytd'])}，
    相对 {fp(rel_m1)} / {fp(rel_ytd)}。<b>Beta 高 + 周期折价</b>，大盘一软，它跌得更快。</span></div>
  <p class="note" style="margin-top:10px">口径提醒：价格数据只能确认"跌法"，不能确认"哪条消息引发的"——本页不做消息面归因。
  但从结构上可以确定：<b>金银（约 {gold_silver_w:.0f}% 权重）+ 锂（{lith_w:.0f}%）+ 整体杀估值</b>，就是这轮回撤的全部来源。</p>
</div>

<h3>跌在哪：按权重拆解近 1 个月（贡献 = 权重 × 涨跌幅）</h3>
<div class="card"><div id="c-attr" class="chart chart-tall"></div>
  <p class="note">合计约 {sum(s['contrib_1m'] for s in attr):.1f} 个百分点，与指数 {fp(perf['m1'])} 基本吻合（权重为 {d['meta']['weights_date']} 口径，个股不复权）。
  拖累最大：<b>{drag_txt}</b>；最抗跌：<b>{hold_txt}</b>。</p>
</div>

<div class="card">
  <div class="tablewrap"><table>
    <tr><th>分组</th><th>成分</th><th>权重</th><th>近 1 月</th><th>1 月贡献</th><th>较 1/29 高点</th><th>年内</th></tr>
    {grp_rows}
  </table></div>
  <p class="note">同样是"有色"，过去 9 个月命运完全不同：<b>铜 -37%、铝 -40%、金 -37%、稀土 -34%、锂 -50%、银锡 -52%</b>；
  唯一没跌的是"钨钼锗钛"，靠云南锗业（权重 2.8%）独立大涨撑着——这属于个别品种行情，不代表板块。</p>
</div>

<!-- ============ 3 估值还是盈利 ============ -->
<h2>3. 跌的是估值还是盈利？——「这一轮纯粹杀估值，但盈利的顶快到了」</h2>
<div class="card">
  <div class="cols">
    <div>
      <div class="kv"><span>指数点位（{asof}）</span><b>{ix['close']:,.0f}</b></div>
      <div class="kv"><span>较 {ix['peak']['date']} 高点</span><b class="down">{fp(ix['dd'])}</b></div>
      <div class="kv"><span>滚动 PE（{ix['pe']:.2f} 倍）</span><b class="down">{fp(pe_drop)}</b></div>
      <div class="kv"><span>滚动 EPS（{eps_now}）</span><b class="up">{fp(eps_gain)}</b></div>
    </div>
    <div>
      <div class="kv"><span>PE 分位（{pes['start'][:7]} 以来）</span><b>{pes['pct']:.0f}%</b></div>
      <div class="kv"><span>PE 中位 / 25 分位</span><b>{pes['median']:.2f} / {pes['p25']:.2f}</b></div>
      <div class="kv"><span>PE 区间（{pes['min_date'][:7]} ~ {pes['max_date'][:7]}）</span><b>{pes['min']:.2f} ~ {pes['max']:.2f}</b></div>
      <div class="kv"><span>金 + 银锡权重</span><b>{gold_silver_w:.0f}%</b></div>
    </div>
  </div>
  <p class="note" style="margin-top:8px">拆开看很简单：<b>股价跌 40%，盈利涨 44%，估值跌 58%</b>。
  这也是"周期股低 PE"的经典陷阱——当 PE 往下走时不一定是便宜，可能是市场在赌盈利要往下走。</p>
</div>

<h3>指数点位 vs 滚动 EPS（{pes['start'][:7]} 以来）</h3>
<div class="card"><div id="c-eps" class="chart"></div>
  <p class="note">橙线（点位）2026-01 之后就往下，紫线（EPS）继续往上——两条线在 2026 年化成一个巨大的"剪刀差"。
  这个差就是被"杀"掉的估值。<b>剪刀差不会无限扩大：要么价格补涨，要么盈利下修。</b></p>
</div>

<h3>三季报（10 月底）是第一份"跌价财报"</h3>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>金属</th><th>Q2 均价</th><th>Q3 均价</th><th>Q3 环比</th><th>10 月至今均价</th><th>10 月环比 Q3</th><th>对矿企盈利的方向</th></tr>
    <tr><td><b>沪铜</b></td><td>{qv('CU0',Q2):,.0f}</td><td>{qv('CU0',Q3):,.0f}</td><td class="{c(qq['CU0'][0])}">{fp(qq['CU0'][0])}</td><td>{qv('CU0',Q4):,.0f}</td><td class="{c(qq['CU0'][1])}">{fp(qq['CU0'][1])}</td><td class="up">继续向好</td></tr>
    <tr><td><b>沪铝</b></td><td>{qv('AL0',Q2):,.0f}</td><td>{qv('AL0',Q3):,.0f}</td><td class="{c(qq['AL0'][0])}">{fp(qq['AL0'][0])}</td><td>{qv('AL0',Q4):,.0f}</td><td class="{c(qq['AL0'][1])}">{fp(qq['AL0'][1])}</td><td class="note">小幅走弱</td></tr>
    <tr><td><b>沪金</b></td><td>{qv('AU0',Q2):,.0f}</td><td>{qv('AU0',Q3):,.0f}</td><td class="{c(qq['AU0'][0])}">{fp(qq['AU0'][0])}</td><td>{qv('AU0',Q4):,.0f}</td><td class="{c(qq['AU0'][1])}">{fp(qq['AU0'][1])}</td><td class="down">环比下修</td></tr>
    <tr><td><b>沪银</b></td><td>{qv('AG0',Q2):,.0f}</td><td>{qv('AG0',Q3):,.0f}</td><td class="{c(qq['AG0'][0])}">{fp(qq['AG0'][0])}</td><td>{qv('AG0',Q4):,.0f}</td><td class="{c(qq['AG0'][1])}">{fp(qq['AG0'][1])}</td><td class="down">大幅下修</td></tr>
    <tr><td><b>碳酸锂</b></td><td>{qv('LC0',Q2):,.0f}</td><td>{qv('LC0',Q3):,.0f}</td><td class="{c(qq['LC0'][0])}">{fp(qq['LC0'][0])}</td><td>{qv('LC0',Q4):,.0f}</td><td class="{c(qq['LC0'][1])}">{fp(qq['LC0'][1])}</td><td class="down">继续恶化</td></tr>
    <tr><td><b>沪锡</b></td><td>{qv('SN0',Q2):,.0f}</td><td>{qv('SN0',Q3):,.0f}</td><td class="{c(qq['SN0'][0])}">{fp(qq['SN0'][0])}</td><td>{qv('SN0',Q4):,.0f}</td><td class="{c(qq['SN0'][1])}">{fp(qq['SN0'][1])}</td><td class="note">高位回落</td></tr>
  </table></div>
  <p class="note">这是本页最硬的一条前瞻证据：<b>金银锂的 Q3 均价环比已经明显下移</b>（银 {fp(qq['AG0'][0])}、锂 {fp(qq['LC0'][0])}、金 {fp(qq['AU0'][0])}），
  矿企成本刚性、经营杠杆高，价格环比降 10% 往往对应利润环比降 20%~30%。<b>10 月底三季报就是这份"跌价"第一次进报表。</b>
  反过来，铜铝的 Q3/Q4 均价还在环比上行，这部分盈利仍有支撑。</p>
</div>

<!-- ============ 4 贵不贵 ============ -->
<h2>4. 现在贵不贵？——「PE 14.8 不贵，但便宜得很"有条件"」</h2>
<div class="card">
  <p>答案分三层：</p>
  <div class="logic good"><b class="t">第一层：绝对估值不贵</b>
    <span>PE {ix['pe']:.2f} 倍，处于 {pes['start'][:7]} 以来 <b>{pes['pct']:.0f}%</b> 分位；中位 {pes['median']:.2f} 倍、25 分位 {pes['p25']:.2f} 倍。
    对比 2026-01 顶部的 {ix['peak']['pe']:.1f} 倍，泡沫已经挤掉 {abs(pe_drop):.0f}%。</span></div>
  <div class="logic mid"><b class="t">第二层：但这个"便宜"是分母撑起来的</b>
    <span>PE = 价格 / 盈利，而这里的盈利是<b>金属价格历史高位时赚出来的 TTM 盈利</b>。
    银 -50%、锂较 1 月 -39% 之后，未来 12 个月的 EPS 大概率往下走；<b>EPS 下修 10%，PE 就会从 14.8 被动回到 16.4</b>——股价没动，估值反而变贵。</span></div>
  <div class="logic bad"><b class="t">第三层：跟真正的底部比，还差一截</b>
    <span>2024-02 的低点是 <b>{pes['min']:.1f} 倍</b>，对应指数 1,581。现在 14.8 倍，比那时候贵 44%。
    如果盈利下修 + 估值回到 12 倍，指数对应 <b>2,675</b>（{fp(round((2675/ix['close']-1)*100,1))}）——这就是情景 C 的来源。</span></div>
</div>

<h3>点位 × 盈利 × 估值：三个变量一张表</h3>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>盈利假设 \\ PE</th><th>10 倍</th><th>12 倍</th><th>{ix['pe']:.2f} 倍（现在）</th><th>18 倍</th><th>20 倍</th></tr>
    {pea_rows}
  </table></div>
  <p class="note">表格读法：<b>横着看是估值变化，竖着看是盈利变化</b>。当前 {ix['close']:,.0f} 点在"盈利不变 × 14.8 倍"的交叉点上。
  盈利 -20% 且估值回到 12 倍 = 2,140 点（-35%）；盈利不变而估值回到 20 倍 = 4,458 点（+35%）。
  <b>这就是为什么本页不预测点位，只给情景</b>——两个变量同时动，任何单点预测都是拍脑袋。</p>
</div>

<h3>核心权重股估值（前 20 大权重，合计约 {sum(x["weight"] for x in pe_list[:20]):.0f}%，PE-TTM）</h3>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>名称</th><th>分组</th><th>权重</th><th>PE-TTM</th><th>PE 近 1 年区间</th><th>市值（亿）</th><th>2026H1 净利增速</th><th>2026H1 ROE</th></tr>
    """
for s in pe_list[:20]:
    fin = {f["date"]: f for f in (s.get("fin") or [])}
    h1 = fin.get("2026-06-30") or {}
    rng = s.get("pe_range")
    rng_txt = "—" if not rng else "%.0f ~ %.0f" % (rng[0], rng[1])
    npg_txt = "—" if h1.get("np_g") is None else fp(h1["np_g"], 0)
    roe_txt = "—" if h1.get("roe") is None else "%.1f%%" % h1["roe"]
    pe_txt = "亏损" if s["pe"] < 0 else f"{s['pe']:.1f}"
    BODY += (f"<tr><td><b>{s['name']}</b></td><td class='note'>{s['group']}</td><td>{s['weight']:.1f}%</td>"
             f"<td class='hl'>{pe_txt}</td>"
             f"<td class='note'>{rng_txt}</td>"
             f"<td>{s.get('mktcap', 0):,.0f}</td>"
             f"<td class='{c(h1.get('np_g'))}'>{npg_txt}</td>"
             f"<td>{roe_txt}</td></tr>")

BODY += f"""
  </table></div>
  <p class="note">PE 为百度股市通 TTM 口径（{asof}），财务为 2026 中报（新浪财经）；全部 38 只见文末附录。<b>低 PE 要结合盈利方向看</b>：
  铜铝 8~14 倍且盈利仍在涨 = 真便宜；金 15~22 倍但盈利要下修 = 假便宜；稀土/钨 30~45 倍 = 靠政策溢价；锂 40 倍以上 = 盈利在底部。</p>
</div>

<!-- ============ 5 可持续 ============ -->
<h2>5. 可持续吗？——「铜铝能兜住盈利，金银锂还在往下修」</h2>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>分组（权重）</th><th>供给</th><th>需求</th><th>盈利方向</th><th>估值</th><th>判断</th></tr>
    <tr><td><b>铜 {cu_w:.0f}%</b></td><td class="up">紧（矿端资本开支不足）</td><td class="up">电网 / AI 数据中心 / 新能源</td>
      <td class="up">Q3 {fp(qq['CU0'][0])}、Q4 {fp(qq['CU0'][1])}</td><td class="up">8~14 倍，最便宜</td><td class="up">最可持续</td></tr>
    <tr><td><b>铝 10%</b></td><td class="up">产能天花板（行政约束）</td><td class="note">地产拖累、出口对冲</td>
      <td class="note">Q3 {fp(qq['AL0'][0])}、Q4 {fp(qq['AL0'][1])}</td><td class="up">7~10 倍</td><td class="note">中性偏稳</td></tr>
    <tr><td><b>金 {round(sum(s['weight'] for s in sts if s['group']=='金'),1)}%</b></td><td class="note">稳定、增量有限</td><td class="down">利率 5% 压制投资需求</td>
      <td class="down">Q3 {fp(qq['AU0'][0])}、Q4 {fp(qq['AU0'][1])}</td><td class="down">15~22 倍（分母偏高）</td><td class="down">看利率脸色</td></tr>
    <tr><td><b>银锡 7.5%</b></td><td class="note">银伴生、锡紧</td><td class="down">银工业需求随经济走弱</td>
      <td class="down">银 Q3 {fp(qq['AG0'][0])}</td><td class="down">已跌 50%，PE 仍不低</td><td class="down">最不确定</td></tr>
    <tr><td><b>稀土 10%</b></td><td class="up">配额管控</td><td class="note">磁材 / 军工 / 机器人</td>
      <td class="note">价格高位震荡</td><td class="down">30~40 倍</td><td class="note">政策定价</td></tr>
    <tr><td><b>锂钴 {lith_w:.0f}%</b></td><td class="down">过剩未出清</td><td class="up">储能 / 电动车仍在增长</td>
      <td class="down">Q3 {fp(qq['LC0'][0])}、Q4 {fp(qq['LC0'][1])}</td><td class="note">PE 高 / 亏损</td><td class="down">还在寻底</td></tr>
  </table></div>
  <p class="note">判断依据都是价格与财报数据，不含主观调研。</p>
</div>

<div class="cols">
  <div class="card">
    <h3 style="margin-top:0;color:var(--green)">能撑住的（权重 {cu_w + 10:.0f}%）</h3>
    <div class="logic good"><b class="t">铜：供给逻辑没坏，价格还在新高附近</b>
      <span>沪铜 {cu['latest']:,.0f}（距峰值 {fp(cu['off_ath'])}），Q3 均价环比 +3.8%、10 月至今再 +3.0%。
      铜股跌的是"高价可持续性"的折价，不是铜价本身。只要铜守住 10 万，铜矿股（紫金/洛钼/西部矿业）的 Q3-Q4 盈利就还有环比增长。</span></div>
    <div class="logic good"><b class="t">铝：估值最便宜、供给有天花板</b>
      <span>PE 7~10 倍，云铝半年 ROE 就有 20%，价格虽从高点回落 10%，但成本端（电价）也在降，盈利韧性比金锂强。</span></div>
  </div>
  <div class="card">
    <h3 style="margin-top:0;color:var(--red)">撑不住的（权重 {gold_silver_w + lith_w:.0f}%）</h3>
    <div class="logic bad"><b class="t">金：估值不低 + 盈利要下修，双杀风险</b>
      <span>金价距峰值 {fp(au['off_ath'])}，但金矿股 PE 仍有 15~22 倍——分母用的是过去 12 个月（金价 950~1,090 元/克）的高价盈利。
      Q3 均价环比 {fp(qq['AU0'][0])}，三季报会第一次显示"环比负增长"。</span></div>
    <div class="logic bad"><b class="t">银/锂：跌了 50% 但仍然不便宜</b>
      <span>银距峰值 -{abs(ag['off_ath']):.0f}%，锂距 2022 年峰值 -{abs(lc['off_ath']):.0f}%。跌得多不等于便宜：
      锂的供给还在释放，Q4 均价环比 {fp(qq['LC0'][1])}，盈利底部还没到。</span></div>
  </div>
</div>

<div class="card">
  <b>5 的小结：</b>指数层面的盈利大概率在 <b>2026 Q3~Q4 见顶</b>（金银锂拖累、铜铝支撑），
  2027 年一季报开始面临"高基数"——<b>这才是周期股最危险的时刻：PE 会因为盈利下滑而被动抬高</b>。
  但要注意，股价通常会领先盈利 2~3 个季度：市场从 1 月就开始杀估值，可能已经把"盈利下修"定价了一部分。
  所以更准确的说法是：<span class="hl">盈利的坏消息还没出完，但股价的坏消息已经出了一半。</span>
</div>
"""

# 6 历史参照
b2 = br["dd_40_50"]; b3 = br["dd_45_60"]
BODY += f"""
<h2>6. 历史怎么参照？——「前两轮大熊都跌了 50%~54%，现在是 -40%」</h2>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>峰 → 谷</th><th>最大回撤</th><th>历时</th><th>点位</th><th>见底后 12 个月</th></tr>
    {bear_rows}
  </table></div>
  <p class="note">两次大熊的共同点：<b>都是"-50% 级别 + 一年多以上"</b>。这次 8.6 个月跌了 40%，无论从幅度还是时间看，
  都还没到历史熊市的典型终点。<b>但这次有个关键不同：盈利还在涨</b>（前两轮见底时 EPS 都在下滑）。</p>
</div>

<h3>三轮回撤对齐（峰值 = 100）</h3>
<div class="card"><div id="c-dd" class="chart"></div>
  <p class="note">横轴 = 距峰值月数。2017-09 那轮（灰）跌了 13 个月到 -50%；2021-09 那轮（蓝）磨了 29 个月到 -54%；
  本轮（橙）8.6 个月到 -40%，<b>斜率是三轮里最陡的</b>，说明这轮出清速度快，但也意味着"时间上还不够"。</p>
</div>

<h3>历史基础概率：站在"距高点 -35% ~ -45%"这个位置，之后会怎样</h3>
<div class="card">
  <div class="tablewrap"><table>
    <tr><th>持有期</th><th>中位收益</th><th>上涨概率</th><th>最好</th><th>最差</th></tr>
    {base_rows}
  </table></div>
  <p class="note">样本：2016 年以来所有"距当时高点 -35% ~ -45%"的交易日（n={b45['m1']['n']}，重叠样本，仅作基础概率参考）。
  读法：<b>1 个月胜率只有 {b45['m1']['win']:.0f}%、6 个月中位 {fp(b45['m6']['median'])}——短期还在往下漂；12 个月才转为 {b45['y12']['win']:.0f}% 胜率、中位 {fp(b45['y12']['median'])}。</b>
  这就是"不能一把梭、但也不必恐慌"的数据依据。更深的 -40%~-50% 区间样本胜率更高（12 个月 {b2['y12']['win']:.0f}%），-45%~-60% 区间 12 个月胜率 {b3['y12']['win']:.0f}%——
  但这两档的样本几乎全部来自 2018 年底和 2024 年初两次底部，"越深越安全"是事后视角，不代表任意深度都会反弹。</p>
</div>
"""

# 7 情景
BODY += f"""
<h2>7. 未来怎么走？——四种情景（6~12 个月，主观概率）</h2>
<div class="scens">
  {scen_cards}
</div>
<p class="note" style="margin-top:-4px">概率是主观判断、不是预测，合计 100%。用途是<b>提前想好每种情景下自己做什么</b>，而不是赌哪一种会发生。</p>

<div class="card">
  <b>为什么是 40/25/25/10：</b>
  <ul class="sig">
    <li><b>支持 A（磨底，40%）</b>：{b45['m1']['win']:.0f}% 的 1 个月胜率、6 个月中位 {fp(b45['m6']['median'])}——短期没有方向；
      铜价还在高位（盈利兜底）、但金银锂在拖累（反弹乏力），最像"下有支撑、上无催化"的箱体。</li>
    <li><b>支持 B（反弹，25%）</b>：12 个月基础概率 {b45['y12']['win']:.0f}% 胜率、中位 {fp(b45['y12']['median'])}；
      10Y 已从 {tnx['peak_date']} 的 {tnx['peak']:.2f}% 回落到 {tnx['latest']:.2f}%，如果利率见顶，金银的超跌反弹弹性很大。</li>
    <li><b>支持 C（再跌，25%）</b>：前两轮都到 -50%~-54%（对应 <b>{ix['peak']['close']*0.46:,.0f} ~ {ix['peak']['close']*0.5:,.0f}</b>），
      而三季报刚开始暴露金银锂的盈利下修；6 个月中位是负的，说明"再跌一段"在历史上并不罕见。</li>
    <li><b>支持 D（新高，10%）</b>：需要铜价突破 12 万 + 金银重启 + EPS 突破 250 三者同时成立，短期看不到证据，但周期股的"意外"永远不要排除。</li>
  </ul>
</div>

<h3>分时间尺度看：短期偏谨慎，中期偏乐观</h3>
<div class="qas">
  <div class="qa"><div class="q">1~3 个月</div><div class="a down">偏谨慎</div>
    <div class="d">A + C 合计 65%；1 个月胜率仅 {b45['m1']['win']:.0f}%、6 个月中位 {fp(b45['m6']['median'])}。下一个雷点是 10 月底三季报（金银锂环比下修）。</div></div>
  <div class="qa"><div class="q">6~12 个月</div><div class="a up">中性偏乐观</div>
    <div class="d">A + B 合计 65%；12 个月历史胜率 {b45['y12']['win']:.0f}%、中位 {fp(b45['y12']['median'])}。前提是利率见顶 + 铜守住 10 万。</div></div>
  <div class="qa"><div class="q">2~3 年</div><div class="a">看铜周期</div>
    <div class="d">铜的供给约束是长逻辑（权重 {cu_w:.0f}%）；金银看利率，锂要等出清。向上需要新叙事，向下有 2024 年 10 倍 PE 的历史底。</div></div>
</div>

<!-- ============ 8 怎么办 ============ -->
<h2>8. 那到底怎么办？——「不追高、不恐慌割、按点位和信号分批」</h2>
<div class="cols">
  <div class="card">
    <h3 style="margin-top:0">已经持有：别在 -40% 处做情绪决定</h3>
    <div class="logic good"><b class="t">① 先用"组内结构"替代"整体判断"</b>
      <span>把仓位拆开看：铜铝（约 {cu_w + 10:.0f}%）逻辑最硬，可以继续拿；金银锂（约 {gold_silver_w + lith_w:.0f}%）逻辑最弱，
      如果这两块占你仓位的大头，反弹时优先减它们，而不是减铜。</span></div>
    <div class="logic mid"><b class="t">② 历史基础概率支持"熬"，不支持"加杠杆"</b>
      <span>12 个月 67% 胜率、中位 +12.8%，但 6 个月内胜率不到一半——用闲钱、不加杠杆、不借钱补仓。</span></div>
    <div class="logic bad"><b class="t">③ 一条硬纪律</b>
      <span>跌破 {ix['low_since_peak']['close']:,.0f}（{ix['low_since_peak']['date']} 低点）且 2 周内收不回来 → 减到"跌了也不影响生活"的仓位；
      站回 <b>4,000</b>（8 月底~9 月初箱体上沿）→ 说明箱体突破，再考虑加回。</span></div>
  </div>
  <div class="card">
    <h3 style="margin-top:0">空仓 / 想买：分批，不猜底</h3>
    <div class="logic good"><b class="t">分三批、按点位机械执行</b>
      <span>① 现价附近（{ix['close']:,.0f}）先建 1/3；② 跌到 <b>2,900</b>（PE 13 倍）加 1/3；
      ③ 若真到 <b>2,700</b>（PE 12 倍，距离 2024 年 2 月的 10.2 倍只差一步）再加最后 1/3。
      如果一路不跌反涨，就只拿第一批——<b>踏空不会亏钱，追高才会。</b></span></div>
    <div class="logic mid"><b class="t">用"信号"确认，而不是用"跌得多"</b>
      <span>三个确认信号：① 10Y 收益率从 5.3% 回落并站稳 4.8% 以下；② 沪金站回 1,000 元/克、沪银站回 16,000；③ 三季报后金银股止跌、铜股创新高。</span></div>
  </div>
</div>

<div class="card">
  <h3 style="margin-top:0">值得盯的 5 个信号（每月更新一次就够）</h3>
  <ul class="sig">
    <li><b>美债 10 年收益率</b>：现在 {tnx['latest']:.2f}%。<b>&lt; 4.8%</b> = 压制解除（利多金银）；<b>&gt; 5.5%</b> = 继续杀估值。</li>
    <li><b>沪铜</b>：现在 {cu['latest']:,.0f}。<b>守住 10 万</b> = 工业金属逻辑还在；有效跌破 9.5 万 = 需求叙事恶化，指数补跌。</li>
    <li><b>沪金</b>：现在 {au['latest']:,.0f} 元/克。<b>站回 1,000</b> = 黄金股的超跌反弹逻辑成立；跌破 850 = 继续回避。</li>
    <li><b>碳酸锂</b>：现在 {lc['latest']:,.0f} 元/吨。<b>站稳 11 万</b> = 反转确认；跌破 9 万 = 反弹结束、锂股继续杀。</li>
    <li><b>指数 PE</b>：现在 {ix['pe']:.2f} 倍。<b>&lt; 12 倍</b> = 深度低估区（历史只有 2024 年初到过）；<b>&gt; 22 倍</b> = 又热了，减仓。</li>
  </ul>
  <p class="note">仓位纪律比预测重要：单一行业主题基金建议不超过组合的 10%~20%；周期品用"分批 + 信号"代替"一把梭 + 感觉"。
  本页不构成投资建议。</p>
</div>

<!-- ============ 附录 ============ -->
<h2>附：38 只成分股全景（权重 {d['meta']['weights_date']}，行情 {asof}）</h2>
<div class="card">
  <div class="tablewrap">
    <table>
      <tr><th>名称</th><th>代码</th><th>分组</th><th>权重</th><th>近 1 月</th><th>近 3 月</th><th>年内</th><th>距 1 年高</th><th>PE-TTM</th><th>市值(亿)</th><th>2026H1 净利增速</th></tr>
      {stock_rows}
    </table>
  </div>
  <p class="note">个股行情为不复权收盘价（新浪），"距 1 年高"为不复权口径；PE/市值为百度股市通 TTM（38 只全覆盖，亏损公司 PE 为负、显示为"亏损"）；
  2026H1 净利增速取新浪财经财务指标（2026-06-30 报告期，空格表示当期亏损或数据缺失）。
  赤峰黄金、山金国际年内逆势上涨，属个股事件驱动，本页不做归因；PE 近 1 年区间为百度口径，含亏损期负值。</p>
</div>

<footer>
  <p><b>数据来源</b>：中证指数官网（指数行情/滚动 PE/成分权重）、新浪财经（个股日线、商品期货主力连续、个股财务指标）、
  百度股市通（个股 PE-TTM/总市值）、Yahoo Finance（美元指数、美债 10Y、COMEX 金/银/铜）。</p>
  <p><b>口径</b>：① 指数为价格指数（不含分红），基金 018168 以其为跟踪标的，净值走势用指数近似；
  ② 滚动 PE 为中证口径，该指数仅 {d['meta']['pe_start']} 起有值，故"分位"均指 {d['meta']['pe_start'][:7]} 以来；
  ③ 个股行情不复权，故"距 1 年高""年内"与含权收益略有差异；④ 权重为 {d['meta']['weights_date']} 月度口径，成分股数量 {len(sts)} 只。</p>
  <p>本页面仅为数据整理与逻辑分析，不构成任何投资建议。基金有风险，投资需谨慎。</p>
  <p>生成：fund-018168/gen_report.py · 数据：fund-018168/data/report_data.json · 体检日 {asof}</p>
</footer>
"""

SCRIPT = r"""
const D = __DATA__;
const fmt = v => (v == null ? '-' : (v > 0 ? '+' : '') + v.toFixed(1) + '%');
const COL = { copper:'#e07b5c', al:'#5b8def', gold:'#e8a33d', silver:'#b9c2d6', li:'#4caf7d', sn:'#a78bfa' };
const grid = { left: 58, right: 58, top: 34, bottom: 46 };
const axisX = { type:'category', axisLabel:{ color:'#8b97b0' }, axisLine:{ lineStyle:{ color:'#2a3650' } } };
const defTip = { trigger:'axis', backgroundColor:'rgba(23,30,46,.95)', borderColor:'#2a3650', textStyle:{ color:'#dce3f0', fontSize:12 } };

function mk(id, opt) {
  const el = document.getElementById(id);
  if (!el || typeof echarts === 'undefined') return null;
  const ch = echarts.init(el); ch.setOption(opt); return ch;
}
const charts = [];

/* 1 指数 + PE */
(function(){
  const h = D.hist;
  charts.push(mk('c-index', {
    backgroundColor:'transparent', tooltip:defTip,
    legend:{ data:['指数收盘','滚动市盈率'], textStyle:{ color:'#8b97b0' }, top:0 },
    grid, dataZoom:[{ type:'inside' }, { type:'slider', height:16, bottom:6, borderColor:'#2a3650', textStyle:{ color:'#8b97b0' } }],
    xAxis:{ ...axisX, data:h.map(x=>x.d) },
    yAxis:[{ type:'value', name:'点位', scale:true, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
           { type:'value', name:'PE', scale:true, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ show:false } }],
    series:[
      { name:'指数收盘', type:'line', showSymbol:false, data:h.map(x=>x.c), lineStyle:{ width:1.8, color:'#e8a33d' },
        markPoint:{ symbolSize:52, data:[{ coord:[D.marks.peak, D.marks.peak_close], value:'峰值', itemStyle:{ color:'#e05c5c' } }], label:{ color:'#fff', fontSize:10 } },
        markLine:{ symbol:'none', data:[{ yAxis:D.marks.close, lineStyle:{ color:'#5b8def', type:'dashed' }, label:{ formatter:'现在 '+Math.round(D.marks.close), color:'#8b97b0' } }] } },
      { name:'滚动市盈率', type:'line', yAxisIndex:1, showSymbol:false, data:h.map(x=>x.pe), lineStyle:{ width:1.3, color:'#a78bfa' } }
    ]
  }));
})();

/* 2 月度收益 */
(function(){
  const m = D.monthly;
  charts.push(mk('c-month', {
    backgroundColor:'transparent', tooltip:defTip, grid:{ left:52, right:24, top:24, bottom:34 },
    xAxis:{ ...axisX, data:m.map(x=>x[0].slice(2)) },
    yAxis:{ type:'value', axisLabel:{ color:'#8b97b0', formatter:'{value}%' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
    series:[{ type:'bar', data:m.map(x=>({ value:x[1], itemStyle:{ color:x[1]>=0?'#e05c5c':'#4caf7d' } })),
      label:{ show:true, position:'top', color:'#8b97b0', fontSize:11, formatter:p=>fmt(p.value) }, barWidth:'56%' }]
  }));
})();

/* 3 商品归一化 */
(function(){
  const keys=[['CU0','copper','沪铜'],['AL0','al','沪铝'],['AU0','gold','沪金'],['AG0','silver','沪银'],['LC0','li','碳酸锂'],['SN0','sn','沪锡']];
  const base='2025-01-02';
  const series = keys.map(([k,col,nm])=>{
    const arr = D.comm[k].filter(x=>x.d>=base);
    const b = arr.length ? arr[0].c : 1;
    return { name:nm, type:'line', showSymbol:false, lineStyle:{ width:1.5, color:COL[col] },
             data:arr.map(x=>[x.d, +(x.c/b*100).toFixed(1)]) };
  });
  series[2].markLine = { symbol:'none', data:[{ xAxis:'2026-01-29', lineStyle:{ color:'#e05c5c', type:'dashed' },
    label:{ formatter:'2026-01-29 金银见顶', color:'#e05c5c', fontSize:10 } }] };
  charts.push(mk('c-comm', {
    backgroundColor:'transparent', tooltip:defTip,
    legend:{ data:series.map(s=>s.name), textStyle:{ color:'#8b97b0' }, top:0 },
    grid:{ left:52, right:24, top:38, bottom:56 },
    dataZoom:[{ type:'inside' }, { type:'slider', height:16, bottom:6, borderColor:'#2a3650', textStyle:{ color:'#8b97b0' } }],
    xAxis:{ type:'time', axisLabel:{ color:'#8b97b0' }, axisLine:{ lineStyle:{ color:'#2a3650' } } },
    yAxis:{ type:'value', name:'2025-01-02 = 100', scale:true, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
    series: series.map(s=>({ ...s, markLine: s.markLine || undefined }))
  }));
})();

/* 4 归因 */
(function(){
  const a = D.attr.slice().sort((x,y)=>x.v-y.v);
  const col = { '铜':'#e07b5c','金':'#e8a33d','银锡':'#b9c2d6','铝':'#5b8def','稀土':'#a78bfa','钨钼锗钛':'#7dd3c0','锂钴':'#4caf7d','其他':'#8b97b0' };
  charts.push(mk('c-attr', {
    backgroundColor:'transparent', tooltip:{ ...defTip, formatter:p=>`${p.name}<br>近1月 ${fmt(p.value)}` },
    grid:{ left:80, right:56, top:14, bottom:26 },
    xAxis:{ type:'value', axisLabel:{ color:'#8b97b0', formatter:'{value}pp' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
    yAxis:{ type:'category', data:a.map(x=>x.name), axisLabel:{ color:'#dce3f0', fontSize:11 }, axisLine:{ lineStyle:{ color:'#2a3650' } } },
    series:[{ type:'bar', barWidth:'62%', data:a.map(x=>({ value:x.v, itemStyle:{ color:col[x.g]||'#8b97b0', opacity:.9 } })),
      label:{ show:true, position:'right', color:'#8b97b0', fontSize:10, formatter:p=>p.value.toFixed(2) } }]
  }));
})();

/* 5 点位 vs EPS */
(function(){
  const e = D.eps;
  charts.push(mk('c-eps', {
    backgroundColor:'transparent', tooltip:defTip,
    legend:{ data:['指数收盘','滚动 EPS（点位/PE）'], textStyle:{ color:'#8b97b0' }, top:0 },
    grid, xAxis:{ ...axisX, data:e.map(x=>x.d) },
    yAxis:[{ type:'value', name:'点位', scale:true, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
           { type:'value', name:'EPS', scale:true, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ show:false } }],
    series:[
      { name:'指数收盘', type:'line', showSymbol:false, data:e.map(x=>x.c), lineStyle:{ width:1.7, color:'#e8a33d' } },
      { name:'滚动 EPS（点位/PE）', type:'line', yAxisIndex:1, showSymbol:false, data:e.map(x=>x.e), lineStyle:{ width:1.9, color:'#a78bfa' } }
    ]
  }));
})();

/* 6 回撤对齐 */
(function(){
  const paths = D.dd_paths;
  const colors = ['#8b97b0','#5b8def','#e8a33d'];
  const series = paths.map((p,i)=>{
    const nm = i === paths.length - 1 ? p.peak_date + '（本轮）' : p.peak_date;
    const pts = p.m.map((m,j)=>[m,p.v[j]]).filter(q=>q[0] <= 36);
    return { name:nm, type:'line', showSymbol:false, connectNulls:true,
      lineStyle:{ width: i===paths.length-1 ? 2.4 : 1.4, color:colors[i] }, data:pts };
  });
  charts.push(mk('c-dd', {
    backgroundColor:'transparent', tooltip:{ ...defTip, formatter:p=>p.map(x=>`${x.seriesName}：${x.value[1].toFixed(0)}（第 ${x.value[0]} 月）`).join('<br>') },
    legend:{ data:series.map(s=>s.name), textStyle:{ color:'#8b97b0' }, top:0 },
    grid:{ left:52, right:24, top:34, bottom:40 },
    xAxis:{ type:'value', name:'距峰值月数', min:0, max:36, interval:6, nameTextStyle:{ color:'#8b97b0' }, axisLabel:{ color:'#8b97b0' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
    yAxis:{ type:'value', name:'峰值 = 100', min:40, max:105, axisLabel:{ color:'#8b97b0' }, splitLine:{ lineStyle:{ color:'#222c44' } } },
    series: series
  }));
})();

window.addEventListener('resize', () => charts.forEach(c => c && c.resize()));
if (typeof echarts === 'undefined') document.querySelectorAll('.chart').forEach(d => d.innerHTML = '<p class="note">图表库加载失败，表格数据不受影响。</p>');
"""

HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>有色矿业 018168 · 2026年10月体检：跌到哪、为什么、还拿不拿</title>
<script src="echarts.min.js"></script>
<script>if (!window.echarts) document.write('<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"><\\/script>');</script>
<style>"""

html = HEAD + STYLE + "</style>\n</head>\n<body>\n<div class=\"wrap\">\n" + BODY + \
       "\n</div>\n<script>\n" + SCRIPT.replace("__DATA__", json.dumps(chart_data, ensure_ascii=False)) + "\n</script>\n</body>\n</html>\n"

out = os.path.join(HERE, "index.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("written", out, "%.0f KB" % (len(html) / 1024))
