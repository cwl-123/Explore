# -*- coding: utf-8 -*-
# ashare_leverage.py — A股杠杆资金与筹码结构体检（2026-10）
#
# 回答：两融杠杆到哪一步了 / 这轮下跌谁在撤 / 全A·创业板·科创50 的筹码结构
# 输出：ashare_leverage.html（自包含 ECharts 页）+ data/lev_*.csv
#
# 口径：
#   - 两融：akshare stock_margin_account_info（沪深北合计，亿元，2012-09 起），
#          板块拆分用交易所个股明细 stock_margin_detail_sse / szse 逐日快照
#   - 全A = 中证全指 000985（中证官网，成交金额亿元）
#   - 创业板 = 创业板指 399006（国证指数官网，含成交额）
#   - 科创50 = 000688（中证官网）
#   - 筹码分布为「成交额分布」(VPVR) 口径：某价位上历史成交额越大，视为该价位筹码越厚。
#     这是可复现的成交量分布算法，**不是真实持仓成本**（后者无公开数据）。
#   - 融资盘成本线 = 以每日融资买入额为权重、对指数点位做加权平均（120/250/500 日）
# 运行：.venv/bin/python ashare_leverage.py

import json
import os

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ashare_leverage.html")

AS_OF = "2026-10-21"


# ---------------------------------------------------------------- 数据准备
def ensure_margin_daily():
    """两融账户信息日序列（亿元口径）"""
    p = os.path.join(DATA, "margin_daily.csv")
    if not os.path.exists(p):
        import akshare as ak

        df = ak.stock_margin_account_info()
        df.to_csv(p, index=False, encoding="utf-8-sig")
    df = pd.read_csv(p)
    df["日期"] = pd.to_datetime(df["日期"])
    num = ["融资余额", "融券余额", "融资买入额", "融券卖出额", "担保物总价值",
           "平均维持担保比例", "有融资融券负债的投资者数量", "参与交易的投资者数量",
           "个人投资者数量", "机构投资者数量"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("日期").reset_index(drop=True)


def ensure_cyb_cni():
    """创业板指 399006（国证指数，含成交额/成交量）"""
    p = os.path.join(DATA, "cyb_cni.csv")
    if not os.path.exists(p):
        import akshare as ak

        df = ak.index_hist_cni(symbol="399006", start_date="20190101", end_date="20991231")
        df.to_csv(p, index=False, encoding="utf-8-sig")
    df = pd.read_csv(p)
    df.columns = ["date", "open", "high", "low", "close", "chg", "volume", "amount"]
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


def load_csindex(fname, dcol="日期", ccol="收盘"):
    df = pd.read_csv(os.path.join(DATA, fname))
    df = df[[dcol, ccol, "成交金额"]].copy()
    df.columns = ["date", "close", "amount"]
    df["date"] = pd.to_datetime(df["date"])
    for c in ["close", "amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------- 工具
def board_of(code):
    c = str(code).split(".")[0].zfill(6)
    if c[:3] in ("688", "689"):
        return "科创板"
    if c[:3] in ("300", "301"):
        return "创业板"
    if c[:1] in ("8", "4") or c[:3] == "920":
        return "北交所"
    if c[:1] == "6":
        return "沪市主板"
    return "深市主板"


BOARD_ORDER = ["沪市主板", "深市主板", "创业板", "科创板", "北交所"]


def _norm_detail(df, is_sse):
    if is_sse:
        df = df.rename(columns={"标的证券代码": "code", "标的证券简称": "name",
                                "融资余额": "bal"})[["code", "name", "bal"]]
    else:
        df = df.rename(columns={"证券代码": "code", "证券简称": "name",
                                "融资余额": "bal"})[["code", "name", "bal"]]
    df["bal"] = pd.to_numeric(df["bal"], errors="coerce") / 1e8  # 元 -> 亿元
    return df


def load_detail_snapshots(md=None):
    """个股两融明细快照（长表 date/code/name/bal/board）
    优先读压缩缓存 data/margin_detail.csv.gz；缺失则按 15 个交易日从交易所重拉。"""
    gz = os.path.join(DATA, "margin_detail.csv.gz")
    if os.path.exists(gz):
        out = pd.read_csv(gz, parse_dates=["date"])
    else:
        import akshare as ak
        if md is None:
            md = ensure_margin_daily()
        ds = md[md["日期"] >= "2026-06-20"]["日期"].dt.strftime("%Y%m%d").tolist()
        pick = ds[::6]
        if ds[-1] not in pick:
            pick.append(ds[-1])
        frames = []
        for dt in pick:
            for fn, is_sse in ((ak.stock_margin_detail_sse, True),
                               (ak.stock_margin_detail_szse, False)):
                try:
                    frames.append(_norm_detail(fn(date=dt), is_sse)
                                  .assign(date=pd.Timestamp(dt)))
                except Exception:
                    pass
        out = pd.concat(frames, ignore_index=True)
        out.to_csv(gz, index=False, compression="gzip", encoding="utf-8-sig")
    out["bal"] = pd.to_numeric(out["bal"], errors="coerce")
    out["board"] = out["code"].map(board_of)
    return out


def vpvr(price, weight, n_bins=64):
    """成交额分布：把价格轴等分，累计每档的成交额"""
    lo, hi = float(price.min()), float(price.max())
    edges = np.linspace(lo, hi, n_bins + 1)
    idx = np.clip(np.digitize(price, edges) - 1, 0, n_bins - 1)
    w = np.bincount(idx, weights=weight, minlength=n_bins)
    centers = (edges[:-1] + edges[1:]) / 2
    return centers, w / w.sum(), edges


def chip_metrics(df, years=3.0, n_bins=64):
    """按成交额分布算筹码结构：获利盘比例、上方套牢、筹码峰、90%成本区间"""
    cur = float(df["close"].iloc[-1])
    start = df["date"].iloc[-1] - pd.Timedelta(days=365 * years)
    w = df[df["date"] >= start]
    centers, share, edges = vpvr(w["close"].values, w["amount"].values, n_bins)
    below = share[centers <= cur].sum()
    # 上方套牢盘：现价上方 0-10% / 10-20% / 20-30%
    def band(lo_pct, hi_pct):
        m = (centers > cur * (1 + lo_pct)) & (centers <= cur * (1 + hi_pct))
        return share[m].sum()

    # 90% 成本区间（按成交额加权的 5%/95% 分位）
    order = np.argsort(centers)
    cum = np.cumsum(share[order])
    lo_p = centers[order][np.searchsorted(cum, 0.05)]
    hi_p = centers[order][np.searchsorted(cum, 0.95)]
    # 筹码峰：成交额最厚的那一档
    peak_i = int(np.argmax(share))
    return dict(
        cur=cur, n=len(w), below=below, above=1 - below,
        band10=band(0, 0.10), band20=band(0.10, 0.20), band30=band(0.20, 0.30),
        peak=centers[peak_i], peak_share=share[peak_i],
        lo90=lo_p, hi90=hi_p,
        top5share=np.sort(share)[-5:].sum(),
        centers=centers, share=share,
    )


def cost_line(m, idx, days):
    """融资盘成本线：以融资买入额为权重，对指数点位加权平均"""
    mm = m[["日期", "融资买入额"]].merge(idx[["date", "close"]], left_on="日期", right_on="date")
    mm = mm.dropna().tail(days)
    w = mm["融资买入额"].values
    p = mm["close"].values
    return float((w * p).sum() / w.sum())


# ---------------------------------------------------------------- 主计算
md = ensure_margin_daily()
cyb = ensure_cyb_cni()
allA = load_csindex("zzall.csv")
kcb = load_csindex("kcb50.csv")

mdx = md[md["日期"] <= AS_OF].copy()
last = mdx.iloc[-1]

# —— 杠杆全景
peak_i = int(mdx["融资余额"].idxmax())
peak_bal = float(mdx.loc[peak_i, "融资余额"])
peak_date = mdx.loc[peak_i, "日期"]
cur_bal = float(last["融资余额"])
cur_lend = float(last["融券余额"])
total_lev = cur_bal + cur_lend

mm = mdx.merge(allA[["date", "amount"]], left_on="日期", right_on="date", how="left")
mm["ratio"] = mm["融资买入额"] / mm["amount"]
cur_ratio = float(mm["ratio"].iloc[-1])
ratio_pct = float((mm["ratio"].dropna() <= cur_ratio).mean())

# 归一化杠杆存量：融资余额 / 滚动250日全A成交额（消除市场规模漂移）
allA_idx = allA.set_index("date")["amount"]
roll_amt = allA_idx.rolling(250, min_periods=120).sum()
lev_norm = (mdx.set_index("日期")["融资余额"] / roll_amt.reindex(mdx["日期"]).values)
lev_norm = pd.Series(lev_norm.values, index=mdx["日期"]).dropna()

cur_ratio_norm = float(lev_norm.iloc[-1])
norm_pct = float((lev_norm <= cur_ratio_norm).mean())

cur_ratio_maint = float(last["平均维持担保比例"])
maint_pct = float((mdx["平均维持担保比例"].dropna() <= cur_ratio_maint).mean())

debtors = float(last["有融资融券负债的投资者数量"])
debtors_peak = float(mdx["有融资融券负债的投资者数量"].max())

# 当前 融资余额 / 流通市值（快照：沪 58.26万亿 + 深 33.41万亿，2026-10-21 交易所口径）
FLOAT_MV = 582640.46 + 334127.24  # 亿元
lev_on_float = total_lev / FLOAT_MV

# —— 板块融资余额
det = load_detail_snapshots()
if len(det):
    dates = sorted(det["date"].unique())
    board_bal = det.groupby(["date", "board"])["bal"].sum().unstack().reindex(columns=BOARD_ORDER).fillna(0)
    board_bal["合计"] = board_bal.sum(axis=1)
    first_d, last_d = dates[0], dates[-1]
    board_chg = pd.DataFrame({
        "起始(亿)": board_bal.loc[first_d],
        "最新(亿)": board_bal.loc[last_d],
    })
    board_chg["变化(亿)"] = board_chg["最新(亿)"] - board_chg["起始(亿)"]
    board_chg["变化(%)"] = board_chg["变化(亿)"] / board_chg["起始(亿)"]
    board_chg["占比(%)"] = board_chg["最新(亿)"] / board_chg.loc["合计", "最新(亿)"] * 100

    # 个股：起始 vs 最新
    p0 = det[det["date"] == first_d].set_index("code")
    p1 = det[det["date"] == last_d].set_index("code")
    cmp_df = pd.concat([p0[["name", "bal"]].add_suffix("_0"), p1[["bal"]].add_suffix("_1")], axis=1)
    cmp_df = cmp_df.dropna()
    cmp_df["chg"] = cmp_df["bal_1"] - cmp_df["bal_0"]
    cmp_df["pct"] = cmp_df["chg"] / cmp_df["bal_0"]
    cmp_df["board"] = [board_of(i) for i in cmp_df.index]
    big_cut = cmp_df[cmp_df["bal_0"] > 5].sort_values("chg").head(12)
    big_add = cmp_df[cmp_df["bal_0"] > 5].sort_values("chg", ascending=False).head(8)
else:
    dates, board_bal, board_chg, cmp_df = [], pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    big_cut = big_add = pd.DataFrame()
    first_d = last_d = None

# —— 指数走势
def window(df, start="2026-01-01"):
    return df[df["date"] >= pd.Timestamp(start)].reset_index(drop=True)


allA_w, cyb_w, kcb_w = window(allA), window(cyb), window(kcb)


def dd_of(df):
    p = df["close"].values
    peak = np.maximum.accumulate(p)
    return p / peak - 1


def norm_series(df, base=100.0):
    d = df["date"]
    p = df["close"]
    return [[int(t.timestamp() * 1000), round(float(v) / float(p.iloc[0]) * base, 2)] for t, v in zip(d, p)]


def dd_series(df):
    d = df["date"]
    return [[int(t.timestamp() * 1000), round(float(v) * 100, 2)] for t, v in zip(d, dd_of(df))]


# 2026 年内高点回撤
def ytd_drawdown(df):
    p = df["close"]
    i = int(p.values.argmax())
    return df["date"].iloc[i], float(p.iloc[i]), float(p.iloc[-1] / p.iloc[i] - 1)


allA_peak_d, allA_peak_p, allA_dd = ytd_drawdown(allA_w)
cyb_peak_d, cyb_peak_p, cyb_dd = ytd_drawdown(cyb_w)
kcb_peak_d, kcb_peak_p, kcb_dd = ytd_drawdown(kcb_w)

# —— 筹码结构
chip_all = chip_metrics(allA, 3.0)
chip_cyb = chip_metrics(cyb, 3.0)
chip_kcb = chip_metrics(kcb, 3.0)
chip_all1 = chip_metrics(allA, 1.0)
chip_cyb1 = chip_metrics(cyb, 1.0)
chip_kcb1 = chip_metrics(kcb, 1.0)
chip_all5 = chip_metrics(allA, 5.0)
chip_cyb5 = chip_metrics(cyb, 5.0)

# —— 融资盘成本线
c_all = {n: cost_line(mdx, allA, n) for n in (120, 250, 500)}
allA_now = float(allA["close"].iloc[-1])
c_cyb = {n: cost_line(mdx, cyb, n) for n in (120, 250, 500)}
cyb_now = float(cyb["close"].iloc[-1])
c_kcb = {n: cost_line(mdx, kcb, n) for n in (120, 250, 500)}
kcb_now = float(kcb["close"].iloc[-1])

# —— 量能：成交额相对 60 日均值
def energy(df):
    a = df["amount"]
    ma60 = a.rolling(60).mean()
    return float(a.iloc[-1] / ma60.iloc[-1]), float((a <= a.iloc[-1]).mean())


e_all, e_all_pct = energy(allA)
e_cyb, e_cyb_pct = energy(cyb)
e_kcb, e_kcb_pct = energy(kcb)

# ---------------------------------------------------------------- 输出 CSV
os.makedirs(DATA, exist_ok=True)

pd.DataFrame([
    ("数据截止", AS_OF, ""),
    ("融资余额(亿)", round(cur_bal, 1), f"距峰值 {(cur_bal/peak_bal-1)*100:+.2f}%"),
    ("融券余额(亿)", round(cur_lend, 1), ""),
    ("两融余额合计(亿)", round(total_lev, 1), ""),
    ("融资余额峰值(亿)", round(peak_bal, 1), str(pd.Timestamp(peak_date).date())),
    ("两融/流通市值(%)", round(lev_on_float * 100, 2), "沪+深流通市值 91.68万亿"),
    ("融资买入额/全A成交额(%)", round(cur_ratio * 100, 2), f"2012以来分位 {ratio_pct:.1%}"),
    ("融资余额/250日成交额(%)", round(cur_ratio_norm * 100, 2), f"分位 {norm_pct:.1%}"),
    ("平均维持担保比例(%)", round(cur_ratio_maint, 2), f"分位 {maint_pct:.1%}"),
    ("有负债投资者(万)", round(debtors / 1e4, 2), f"峰值 {debtors_peak/1e4:.2f}万"),
    ("全A(000985)", round(allA_now, 2), f"年内高点回撤 {allA_dd*100:+.2f}%"),
    ("创业板(399006)", round(cyb_now, 2), f"年内高点回撤 {cyb_dd*100:+.2f}%"),
    ("科创50(000688)", round(kcb_now, 2), f"年内高点回撤 {kcb_dd*100:+.2f}%"),
], columns=["指标", "数值", "备注"]).to_csv(os.path.join(DATA, "lev_summary.csv"),
                                            index=False, encoding="utf-8-sig")

if len(det):
    board_bal.round(2).to_csv(os.path.join(DATA, "lev_board_margin.csv"), encoding="utf-8-sig")
    cmp_df.sort_values("chg").round(3).to_csv(os.path.join(DATA, "lev_stock_margin_change.csv"),
                                              encoding="utf-8-sig")

pd.DataFrame([
    dict(指数="全A(000985)", 窗口="3年", **{k: round(v, 4) for k, v in chip_all.items()
                                        if k not in ("centers", "share")}),
    dict(指数="创业板(399006)", 窗口="3年", **{k: round(v, 4) for k, v in chip_cyb.items()
                                          if k not in ("centers", "share")}),
    dict(指数="科创50(000688)", 窗口="3年", **{k: round(v, 4) for k, v in chip_kcb.items()
                                          if k not in ("centers", "share")}),
]).to_csv(os.path.join(DATA, "lev_chip_structure.csv"), index=False, encoding="utf-8-sig")


# ---------------------------------------------------------------- 页面
def kpi(label, value, note, tone=""):
    return (f'<div class="kpi {tone}"><div class="kl">{label}</div>'
            f'<div class="kv">{value}</div><div class="kn">{note}</div></div>')


def chip_bars(c):
    """VPVR 横向柱状数据：[[价格, 占比%], ...]"""
    return [[round(float(p), 2), round(float(s) * 100, 3)]
            for p, s in zip(c["centers"], c["share"])]


def board_table():
    if not len(det):
        return "<p class='muted'>明细数据缺失</p>"
    tr = []
    for b in BOARD_ORDER:
        r = board_chg.loc[b]
        if abs(r["最新(亿)"]) < 1 and abs(r["起始(亿)"]) < 1:
            continue  # 明细未覆盖（如北交所），不展示全 0 行
        tr.append(f"<tr><td>{b}</td><td>{r['起始(亿)']:,.0f}</td><td>{r['最新(亿)']:,.0f}</td>"
                  f"<td class='{'neg' if r['变化(亿)']<0 else 'pos'}'>{r['变化(亿)']:+,.0f}</td>"
                  f"<td class='{'neg' if r['变化(%)']<0 else 'pos'}'>{r['变化(%)']:+.1%}</td>"
                  f"<td>{r['占比(%)']:.1f}%</td></tr>")
    return "".join(tr)


def stock_table(df, title):
    if not len(df):
        return ""
    tr = []
    for code, r in df.iterrows():
        nm = str(r["name_0"])[:8]
        tr.append(f"<tr><td>{code}</td><td>{nm}</td><td>{r['bal_0']:.1f}</td>"
                  f"<td>{r['bal_1']:.1f}</td>"
                  f"<td class='{'neg' if r['chg']<0 else 'pos'}'>{r['chg']:+.1f}</td>"
                  f"<td class='{'neg' if r['pct']<0 else 'pos'}'>{r['pct']:+.1%}</td>"
                  f"<td>{r['board']}</td></tr>")
    return (f"<h3>{title}</h3><table><tr><th>代码</th><th>简称</th><th>起始(亿)</th>"
            f"<th>最新(亿)</th><th>变化(亿)</th><th>变化%</th><th>板块</th></tr>{''.join(tr)}</table>")


def chip_table():
    rows = []
    for name, c in [("全A(000985)", chip_all), ("创业板(399006)", chip_cyb), ("科创50(000688)", chip_kcb)]:
        rows.append(
            f"<tr><td>{name}</td><td class='pos'>{c['below']:.1%}</td><td>{c['band10']:.1%}</td>"
            f"<td>{c['band10']+c['band20']:.1%}</td>"
            f"<td>{c['band10']+c['band20']+c['band30']:.1%}</td>"
            f"<td>{c['peak']:.0f}（{c['peak_share']:.1%}）</td>"
            f"<td>{c['lo90']:.0f} – {c['hi90']:.0f}</td>"
            f"<td>{c['top5share']:.1%}</td></tr>")
    return "".join(rows)


HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>A股杠杆资金与筹码结构体检 · 2026-10</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
:root{--ink:#1a1a1a;--muted:#6b7280;--line:#e5e7eb;--bg:#fbfbfc;--red:#c0392b;--green:#1f8a4c;--blue:#2f6fed;--amber:#e0a300;--purple:#7c3aed;--orange:#e67e22}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.75 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 22px 80px}
h1{font-size:27px;line-height:1.35;margin:6px 0 4px;letter-spacing:-.3px}
.sub{color:var(--muted);font-size:13.5px;margin-bottom:18px}
h2{font-size:20px;margin:38px 0 10px;padding-top:14px;border-top:1px solid var(--line)}
h3{font-size:16px;margin:22px 0 6px}
p{margin:10px 0}
ul,ol{margin:8px 0 8px 22px;padding:0}
li{margin:5px 0}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px;background:#fff}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:right}
th{background:#f3f4f6;font-weight:600;text-align:center}
td:first-child,th:first-child{text-align:left}
td:nth-child(2),th:nth-child(2){text-align:left}
.neg{color:var(--red);font-weight:600}
.pos{color:var(--green);font-weight:600}
.chart{width:100%;height:340px;background:#fff;border:1px solid var(--line);border-radius:8px;margin:12px 0}
.chart.tall{height:430px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));gap:9px;margin:16px 0}
.kpi{background:#fff;border:1px solid var(--line);border-radius:9px;padding:12px 13px}
.kpi .kl{font-size:12px;color:var(--muted)}
.kpi .kv{font-size:22px;font-weight:700;letter-spacing:-.5px;margin:2px 0}
.kpi .kn{font-size:11.5px;color:var(--muted);line-height:1.45}
.kpi.warn .kv{color:var(--red)}.kpi.ok .kv{color:var(--green)}.kpi.blue .kv{color:var(--blue)}
.box{border-radius:10px;padding:14px 16px;margin:16px 0;font-size:14.5px}
.note{background:#fff7ed;border:1px solid #fed7aa}
.key{background:#eff6ff;border:1px solid #bfdbfe}
.muted{color:var(--muted);font-size:13px}
.tag{display:inline-block;background:#eef2ff;color:#4338ca;border-radius:5px;padding:1px 7px;font-size:12px;margin-right:6px}
</style>
</head>
<body>
<div class="wrap">

<h1>A股杠杆资金与筹码结构体检</h1>
<div class="sub">数据截止 @@AS_OF@@ ｜ 全A=中证全指 000985，创业板=399006，科创50=000688 ｜ 个人研究笔记，不构成投资建议</div>

<div class="box key">
<b>三句话结论。</b><br>
① <b>杠杆规模撤了一大截，但「杠杆密度」已经很低了</b>——融资余额从 @@PEAK_DATE@@ 的 @@PEAK_BAL@@ 万亿降到 @@CUR_BAL@@ 万亿（<b>@@BAL_CHG@@</b>，@@BAL_ABS@@ 亿），更关键的是密度指标：两融/流通市值仅 @@LEV_FLOAT@@、融资余额/250日成交额 @@NORM_VAL@@（历史 @@NORM_PCT@@ 分位）。<b>杠杆已不是当前的主要矛盾。</b><br>
② <b>但撤退过程中有个刺眼的细节：杠杆是「追高的最后一棒」。</b>全A 在 2026-05-13 就见顶了，融资余额却逆势又加了 <b>@@JUMP_ABS@@ 亿（@@JUMP_PCT@@）</b>，直到 6-25 才见顶——<b>指数跌了一个多月还在加杠杆</b>。这批筹码浮亏最深，也正是最近一个月加速减仓（单月 @@BAL_1M_D@@ 亿）的主力。撤退高度集中在创业板（@@CYB_CHG@@）与科创板（@@KCB_CHG@@）。<br>
③ <b>真正的约束在筹码，而且三个市场的「天花板」位置完全不同</b>——获利盘只剩 @@ALL_BELOW@@（全A）/ @@CYB_BELOW@@（创业板）/ @@KCB_BELOW@@（科创50）；但上方最厚的套牢区，全A 在 @@ALL_PEAK_CHG@@（@@ALL_PEAK@@）、科创50 在 @@KCB_PEAK_CHG@@（@@KCB_PEAK@@）、创业板却在 <b>@@CYB_PEAK_CHG@@</b>（@@CYB_PEAK@@）。<b>所以反弹不是没有空间，是每个市场有明确且高低不同的盖子。</b>
</div>

<div class="kpis">
@@KPIS@@
</div>

<h2>1. 杠杆资金到哪一步了</h2>
<p>两融余额是本轮行情最灵敏的杠杆温度计。这一轮的特征很清楚：<b>先冲到历史峰值，再持续单边去化</b>，而且去化速度在最近一个月还在加快。</p>
<table>
<tr><th>时点</th><th>融资余额(万亿)</th><th>较高点</th><th>期间变化</th><th>读法</th></tr>
<tr><td>@@PEAK_DATE@@（峰值）</td><td>@@PEAK_BAL@@</td><td>—</td><td>—</td><td>杠杆见顶，与创业板/科创50 指数高点几乎同期</td></tr>
<tr><td>3 个月前</td><td>@@BAL_3M@@</td><td>@@BAL_3M_CHG@@</td><td>@@BAL_3M_D@@ 亿</td><td>去杠杆启动，市场仍在高位震荡</td></tr>
<tr><td>1 个月前</td><td>@@BAL_1M@@</td><td>@@BAL_1M_CHG@@</td><td>@@BAL_1M_D@@ 亿</td><td>指数加速下跌，融资盘开始被动减</td></tr>
<tr><td>1 周前</td><td>@@BAL_1W@@</td><td>@@BAL_1W_CHG@@</td><td>@@BAL_1W_D@@ 亿</td><td>单周降幅占全月三分之一以上，<b>去化在加速</b></td></tr>
<tr><td><b>@@AS_OF@@（最新）</b></td><td><b>@@CUR_BAL@@</b></td><td><b>@@BAL_CHG@@</b></td><td>—</td><td>名义仍在 93% 分位，但<b>密度已到低位</b>（见下）</td></tr>
</table>
<div class="chart" id="c_bal"></div>

<div class="box note">
<b>一个容易被忽略、但很重要的细节：杠杆资金是「追高的最后一棒」。</b><br>
全A（中证全指）在 <b>2026-05-13</b> 就见了年内高点 @@ALLA_PEAK_P@@；但融资余额在那之后<b>还在继续加</b>——从 5-13 的 @@BAL_0513@@ 万亿加到 6-25 的 @@BAL_0625@@ 万亿，<b>逆势增加了 @@JUMP_ABS@@ 亿（@@JUMP_PCT@@）</b>，而同期指数已经跌了 @@ALLA_JUMP_PCT@@。<br>
这说明：<b>6 月那波加的杠杆，是在指数已经转弱的情况下加的</b>。这批资金的成本大致集中在 6,100~6,700 区间，按现价（@@ALLA_NOW@@）估算浮亏约 13%~21%——它们既是浮亏最深的筹码，也是最近一个月减仓最急迫的主体（近一周 @@WEEK_D@@ 亿，占近一月降幅的 @@WEEK_SHARE@@）。<b>「谁在撤退」的答案，很大一部分就是这批 6 月追高的杠杆盘。</b>
</div>

<h3>杠杆的「质地」：不是 2015 那种杠杆</h3>
<p>名义余额 @@CUR_BAL@@ 万亿看着吓人（为本数据区间 2012 年以来最高），但「名义值的 93% 分位」很大程度上是被<b>市场规模增长</b>顶上去的——同样的余额，在 2015 年撬动的市值占比和今天完全不同。用三个指标校正后再看：</p>
<ul>
<li><b>占流通市值 @@LEV_FLOAT@@</b>：当前两融余额 @@TOTAL_LEV@@ 万亿 / 沪深流通市值 91.68 万亿。市场普遍估算 2015 年 6 月该比值在 4%~5% 区间，<b>现在只有当时的一半左右</b>——股票池大了、市值涨了，同样的钱撬动的比例低得多。</li>
<li><b>融资买入占成交额 @@CUR_RATIO@@</b>（历史分位 @@RATIO_PCT@@）：这是最干净的「杠杆交易热度」指标，已经回到中性偏低的位置。它说明<b>新增杠杆已经明显收手</b>，市场不再是杠杆资金主导的定价。</li>
<li><b>平均维持担保比例 @@MAINT@@</b>（历史分位 @@MAINT_PCT@@）：这是「会不会爆」的核心。强平线通常在 130%，当前 256% 意味着<b>平均账户还有近一倍的安全垫</b>——这不是 2015 年那种「跌到 130% 被迫平仓」的螺旋，而是「浮亏后主动降杠杆」的慢过程。</li>
</ul>
<div class="box note">
<b>关键区分：主动去杠杆 ≠ 被动平仓螺旋。</b>被动平仓的特征是——维保比例快速下滑、融资余额断崖式下跌、成交额异常放大。当前看到的是：维保比例温和下行（仍在 256%）、余额匀速下降、成交额反而在缩。<b>这是「杠杆资金撤退」，不是「杠杆资金崩盘」</b>，前者是估值消化，后者才是系统性风险。
</div>
<div class="chart" id="c_ratio"></div>
<div class="chart" id="c_maint"></div>
<p class="muted">注：右图为「融资余额 / 滚动 250 日全A成交额」，用来消除市场规模增长带来的名义值漂移。当前 @@NORM_VAL@@，历史分位 @@NORM_PCT@@ —— 校正后杠杆存量处于<b>历史低位</b>，与「名义值 93% 分位」形成鲜明对比。<b>但要留个心眼</b>：这个比值偏低，既有「杠杆撤了」的成分，也有「分母变大了」的成分——2026 上半年成交额创天量，近 250 日日均成交额 2.32 万亿，远高于当前的 1.38 万亿。所以密度指标里，<b>两融/流通市值（@@LEV_FLOAT@@）比这个更干净</b>。</p>

<h2>2. 这轮下跌，谁在撤退</h2>
<p>先看跌了多少。2026 年内高点至今：全A @@ALLA_DD@@（@@ALLA_PEAK_D@@ 见顶）、创业板 @@CYB_DD@@（@@CYB_PEAK_D@@ 见顶）、科创50 @@KCB_DD@@（@@KCB_PEAK_D@@ 见顶）。<b>越成长、越杠杆密集的板块，跌得越狠</b>，这个排序本身就是答案。</p>
<div class="chart" id="c_norm"></div>
<div class="chart" id="c_dd"></div>

<h3>撤退的主力：创业板 + 科创板的融资盘</h3>
<p>把交易所个股两融明细按板块汇总（@@DET_FIRST@@ → @@AS_OF@@，共 @@DET_N@@ 个快照），融资余额的迁移非常集中：</p>
<table>
<tr><th>板块</th><th>起始(亿)</th><th>最新(亿)</th><th>变化(亿)</th><th>变化%</th><th>占比</th></tr>
@@BOARD_TABLE@@
</table>
<div class="chart" id="c_board"></div>
<p>解读：<b>创业板 + 科创板合计贡献了近一半的降幅</b>——两者只占存量 @@CYB_KCB_SHARE@@，却贡献了 <b>@@CYB_KCB_CONTRIB@@</b> 的融资余额蒸发（@@CYB_D@@ 亿 + @@KCB_D@@ 亿）；降幅也最陡（@@CYB_CHG@@ / @@KCB_CHG@@），明显快于沪市主板（@@SSE_CHG@@）和深市主板（@@SZSE_CHG@@）。这不是「全市场一起降杠杆」，而是<b>结构性撤离：杠杆资金从高波动成长板块撤出</b>。这也解释了为什么全A 只跌 @@ALLA_DD@@ 而创业板跌 @@CYB_DD@@——杠杆盘的分布本来就是偏成长的，去杠杆的痛感也就集中在成长端。</p>
<p class="muted">注：板块拆分为沪、深交易所个股两融明细汇总，不含北交所（余额约 79 亿）及其他统计差异，合计约 2.40 万亿，低于全市场口径的 @@CUR_BAL@@ 万亿约 2%。</p>

<h3>个股层面：谁被抽走了杠杆</h3>
<p class="muted">按「融资余额减少额」排序，仅列起始余额 &gt; 5 亿的标的，单位亿元。</p>
@@BIG_CUT@@
@@BIG_ADD@@

<h2>3. 筹码结构：三个市场的成本分布</h2>
<p class="muted">口径说明：下图为 <b>成交额分布（VPVR）</b>——把过去 3 年每个交易日的成交额按其价格归档，某个价位累计的成交额越多，说明历史上在该价位换手的筹码越厚。这是可复现的成交量分布算法，<b>不等于真实持仓成本</b>（后者无公开数据），但足以刻画「套牢盘在哪」。</p>
<table>
<tr><th>指数</th><th>获利盘</th><th>上方 0-10%</th><th>上方 0-20%</th><th>上方 0-30%</th><th>筹码峰（占比）</th><th>90% 成本区间</th><th>前 5 档集中度</th></tr>
@@CHIP_TABLE@@
</table>

<h3>全A（中证全指 000985）</h3>
<div class="chart tall" id="c_chip_all"></div>
<p>获利盘 @@ALL_BELOW@@，上方 0-20% 区间压着 @@ALL_B20@@、0-30% 区间压着 @@ALL_B30@@ 的筹码，筹码峰在 @@ALL_PEAK@@（现价上方约 @@ALL_PEAK_CHG@@）。<b>全A 的「盖子」很近也很硬</b>——只要反弹 10% 摸到 5,800 一带，就撞上最厚的一层解套盘。这也是为什么大盘的反弹总显得「没劲」：不是没资金，是那个位置有太多人等回本。</p>

<h3>创业板（399006）</h3>
<div class="chart tall" id="c_chip_cyb"></div>
<p>创业板的形态最特殊：<b>近处轻、远处重</b>。获利盘只剩 @@CYB_BELOW@@（三个市场最低），但上方 0-20% 区间只有 @@CYB_B20@@——<b>紧贴着现价的位置反而没什么套牢盘</b>；真正的重压在 20-30% 那一段（单独就占 @@CYB_B2030@@），筹码峰在 @@CYB_PEAK@@（上方约 @@CYB_PEAK_CHG@@）。<br>
这正好解释了创业板「<b>弹得急、但很短</b>」的形态：<b>因为近处没有解套盘，所以一有买盘就能弹得很快；但一到 3,200~3,330 就撞上厚墙，弹势立刻熄火。</b></p>

<h3>科创50（000688）</h3>
<div class="chart tall" id="c_chip_kcb"></div>
<p>科创50 恰好相反：<b>头顶就近处最重</b>。获利盘 @@KCB_BELOW@@，但上方 0-10% 这一小段就堆了 @@KCB_B10@@ 的筹码，筹码峰 @@KCB_PEAK@@ 只在现价上方 @@KCB_PEAK_CHG@@。<br>
翻译：<b>弹 5%~9% 就会撞墙</b>。这个板块持有人里杠杆和短线资金占比更高、筹码「松动度」最大，一旦反弹抛压释放得比创业板更急——这也是它 10 月以来跌得最凶（-39.2%）的结构原因。</p>

<div class="box note">
<b>筹码结构给的三条推论：</b>
<ul>
<li><b>反弹的天花板由「套牢盘密度」决定，不是估值。</b>三个市场盖子的位置完全不同：科创50 在 +9%、全A 在 +10%、创业板在 +24%。<b>这意味着「跌得多」的创业板反而反弹空间最大</b>（上方 20% 以内几乎没有筹码），而「跌得少」的全A 反而离压力最近——这一点和直觉相反，但很关键。</li>
<li><b>换手是否充分决定磨底时长。</b>当前量能 @@ENERGY_ALL@@（全A 成交额 / 60 日均值）。低于 1 意味着<b>缩量阴跌</b>而非放量出清——筹码还处在「不愿割」的状态，通常需要更长时间、或一次放量恐慌来完成交换。</li>
<li><b>获利盘比例是反向指标，但别过度解读。</b>当前 @@ALL_BELOW@@ / @@CYB_BELOW@@ / @@KCB_BELOW@@ 属于偏低区间（想卖的基本卖了一批），但<b>还没到历史上「极端低位」的程度</b>。真正危险的是获利盘高企时的下跌（那才是刚开始）；而获利盘低只是「跌了不少」的必要条件，不是见底的充分条件。</li>
</ul>
</div>

<h2>4. 融资盘现在浮亏多少</h2>
<p>用「以每日融资买入额为权重、对指数点位加权平均」估算融资盘的平均建仓成本（这是估算，不是真实成本，仅用于判断杠杆盘的心理位置）：</p>
<table>
<tr><th>指数</th><th>现价</th><th>融资盘成本(120日)</th><th>浮亏</th><th>成本(250日)</th><th>浮亏</th><th>成本(500日)</th><th>浮亏</th></tr>
@@COST_TABLE@@
</table>
<div class="chart" id="c_cost"></div>
<p><b>读法：</b>如果现价已经显著低于 250 日融资盘成本，说明<b>大部分杠杆资金处于浮亏状态</b>，这时候的减仓多半是「止损」而不是「止盈」——这类卖出往往不计成本、不看估值，也是下跌末段容易加速的原因。反过来，当浮亏收窄到成本线附近，抛压会明显减轻。</p>

<h2>5. 结论：去杠杆进行到哪一步，接下来看什么</h2>
<h3>当前位置的判断</h3>
<ol>
<li><b>杠杆「密度」上已经很低，但绝对规模还在缩。</b>两融/流通市值 @@LEV_FLOAT@@、融资余额/250日成交额 @@NORM_VAL@@（@@NORM_PCT@@ 分位）——按密度看，<b>杠杆已经不是当前的主要风险来源</b>。但近一周仍降了 553 亿、占近一月降幅的 37%，<b>去化的尾部还没走完</b>。</li>
<li><b>本轮杠杆是「滞后确认」而不是「领先预警」。</b>全A 5-13 见顶，融资余额 6-25 才见顶——<b>它是在指数转弱之后才停止加仓的</b>。这有个重要推论：<b>别把「融资余额不再下降」当成抄底信号</b>，它更可能是滞后确认；真正值得盯的领先变量是融资买入占比与维保比例的变化方向。</li>
<li><b>筹码结构决定了反弹的形态，而且三个市场的「盖子」位置不同</b>：全A 最近（+10%）、科创50 次之（+9%）但最黏、创业板最远（+24%）且近处阻力最小。所以更可能的路径是<b>大盘磨底、创业板弹性更大但一到 3,200~3,300 就遇阻</b>，而不是齐涨。</li>
<li><b>没有系统性风险特征</b>：维保比例 256%、无被动平仓螺旋、成交额缩量。<b>这是估值消化，不是流动性危机。</b></li>
</ol>

<h3>接下来盯这 5 个信号（按重要性排序）</h3>
<table>
<tr><th>#</th><th>信号</th><th>当前值</th><th>阈值 / 触发条件</th><th>含义</th></tr>
<tr><td>1</td><td>融资余额连续 2-3 周不再创新低</td><td>@@CUR_BAL@@ 万亿</td><td>周度环比转正</td><td><b>滞后确认信号</b>（本轮它是追高盘，别当领先指标用）</td></tr>
<tr><td>2</td><td>平均维持担保比例</td><td>@@MAINT@@</td><td>跌破 240% 需警惕；跌破 220% 是危险区</td><td>被动平仓压力的直接度量</td></tr>
<tr><td>3</td><td>融资买入额 / 成交额</td><td>@@CUR_RATIO@@</td><td>回升至 10% 以上</td><td>杠杆资金重新参与，风险偏好修复</td></tr>
<tr><td>4</td><td>成交额（放量出清）</td><td>@@ENERGY_ALL@@（vs 60 日均）</td><td>单日成交额 &gt; 60 日均值 1.5 倍且指数收涨</td><td>筹码完成交换，磨底结束的必要条件</td></tr>
<tr><td>5</td><td>创业板获利盘比例</td><td>@@CYB_BELOW@@</td><td>回升至 40% 以上</td><td>上方套牢盘被消化，成长板块具备持续性</td></tr>
</table>

<h3>什么情况下这个判断是错的（证伪清单）</h3>
<ul>
<li><b>若融资余额重新快速上升而指数不涨</b>——说明杠杆资金在「抄底加杠杆」，这是风险积累而非出清，后续下跌会更猛。</li>
<li><b>若维保比例跌破 220%</b>——「主动去杠杆」叙事失效，进入被动平仓螺旋，届时任何筹码分析都失效。</li>
<li><b>若成交额持续萎缩但指数创新低</b>——缩量阴跌没有尽头，说明买盘彻底缺席，磨底时间会远超预期。</li>
<li><b>若创业板在筹码峰下方反复冲高回落超过 3 次</b>——上方套牢盘确认无法消化，需要更长时间或更大跌幅来重构筹码。</li>
</ul>

<h2>口径与免责</h2>
<p class="muted">
<b>数据来源：</b>两融余额 / 融资买入额 / 维持担保比例 / 投资者数量 = 交易所两融账户统计（akshare <code>stock_margin_account_info</code>，2012-09 起，沪深北合计）；个股两融明细 = 上交所 / 深交所每日披露（<code>stock_margin_detail_sse/szse</code>，15 个交易日快照）；全A = 中证全指 000985（中证官网，成交金额亿元）；创业板 = 创业板指 399006（国证指数官网，含成交额）；科创50 = 000688（中证官网）。流通市值快照 = 上交所 / 深交所市场统计（2026-10-21）。<br>
<b>口径局限：</b>① 筹码分布为「成交额分布（VPVR）」算法估算，<b>不是真实持仓成本</b>；② 融资盘成本线为「融资买入额加权平均」，是估算值；③ 场外配资、雪球、DMA 等隐性杠杆<b>无公开数据，本页未纳入</b>；④ 板块拆分基于 15 个交易日快照，非连续日频；⑤ 北向资金自 2024-08 起不再披露实时净买入，本页未纳入。<br>
<b>本页为个人研究笔记，不构成投资建议。</b>历史规律不代表未来，情景与判断均可能出错。
</p>

</div>
<script>
const C = {red:'#c0392b',green:'#1f8a4c',blue:'#2f6fed',amber:'#e0a300',purple:'#7c3aed',orange:'#e67e22',gray:'#9ca3af'};
const AX = {axisLine:{lineStyle:{color:'#d1d5db'}},axisLabel:{color:'#6b7280',fontSize:11},splitLine:{lineStyle:{color:'#f1f2f4'}}};

// 1 两融余额
echarts.init(document.getElementById('c_bal')).setOption({
  title:{text:'两融余额：融资余额（红）与融券余额（灰）· 亿元',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},legend:{bottom:0,textStyle:{fontSize:11}},
  grid:{left:64,right:56,top:46,bottom:46},
  xAxis:{type:'time',...AX},
  yAxis:[{type:'value',name:'融资',...AX},{type:'value',name:'融券',...AX}],
  series:[
    {name:'融资余额',type:'line',showSymbol:false,color:C.red,lineStyle:{width:2},data:@@BAL_SERIES@@},
    {name:'融券余额',type:'line',showSymbol:false,color:C.gray,yAxisIndex:1,data:@@LEND_SERIES@@}
  ]
});

// 2 融资买入占成交额
echarts.init(document.getElementById('c_ratio')).setOption({
  title:{text:'融资买入额 / 全A成交额（%）· 杠杆交易热度',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},grid:{left:56,right:24,top:46,bottom:38},
  xAxis:{type:'time',...AX},yAxis:{type:'value',...AX,axisLabel:{color:'#6b7280',fontSize:11,formatter:'{value}%'}},
  series:[{type:'line',showSymbol:false,color:C.blue,areaStyle:{color:'#2f6fed18'},data:@@RATIO_SERIES@@,
    markLine:{silent:true,symbol:'none',lineStyle:{color:C.amber,type:'dashed'},
      data:[{yAxis:@@CUR_RATIO_NUM@@,label:{formatter:'当前 @@CUR_RATIO@@',position:'insideEndTop',fontSize:11}}]}}]
});

// 3 维保比例
echarts.init(document.getElementById('c_maint')).setOption({
  title:{text:'平均维持担保比例（%）· 130% 是常见强平线',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},grid:{left:56,right:24,top:46,bottom:38},
  xAxis:{type:'time',...AX},yAxis:{type:'value',scale:true,...AX},
  series:[{type:'line',showSymbol:false,color:C.purple,data:@@MAINT_SERIES@@,
    markLine:{silent:true,symbol:'none',lineStyle:{color:C.red,type:'dashed'},
      data:[{yAxis:130,label:{formatter:'强平线 130%',position:'insideEndTop',fontSize:11}},
            {yAxis:150,label:{formatter:'警戒 150%',position:'insideEndTop',fontSize:11}}]}}]
});

// 4 三指数归一化
echarts.init(document.getElementById('c_norm')).setOption({
  title:{text:'2026 年以来走势（起点=100）· 谁跌得最狠',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},legend:{bottom:0,textStyle:{fontSize:11}},
  grid:{left:52,right:24,top:46,bottom:46},
  xAxis:{type:'time',...AX},yAxis:{type:'value',scale:true,...AX},
  series:[
    {name:'全A(000985)',type:'line',showSymbol:false,color:C.blue,lineStyle:{width:2.2},data:@@NORM_ALL@@},
    {name:'创业板(399006)',type:'line',showSymbol:false,color:C.orange,data:@@NORM_CYB@@},
    {name:'科创50(000688)',type:'line',showSymbol:false,color:C.purple,data:@@NORM_KCB@@}
  ]
});

// 5 回撤
echarts.init(document.getElementById('c_dd')).setOption({
  title:{text:'回撤曲线（水下，%）· 距 2026 年内高点',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},legend:{bottom:0,textStyle:{fontSize:11}},
  grid:{left:56,right:24,top:46,bottom:46},
  xAxis:{type:'time',...AX},yAxis:{type:'value',max:0,...AX},
  series:[
    {name:'全A',type:'line',showSymbol:false,color:C.blue,areaStyle:{color:'#2f6fed15'},data:@@DD_ALL@@},
    {name:'创业板',type:'line',showSymbol:false,color:C.orange,data:@@DD_CYB@@},
    {name:'科创50',type:'line',showSymbol:false,color:C.purple,data:@@DD_KCB@@}
  ]
});

// 6 板块融资余额
echarts.init(document.getElementById('c_board')).setOption({
  title:{text:'分板块融资余额（亿元）· 撤退的集中度',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},legend:{bottom:0,textStyle:{fontSize:11}},
  grid:{left:64,right:24,top:46,bottom:46},
  xAxis:{type:'time',...AX},yAxis:{type:'value',...AX},
  series:[
    {name:'沪市主板',type:'line',showSymbol:true,symbolSize:4,color:C.blue,data:@@BOARD_SSE@@},
    {name:'深市主板',type:'line',showSymbol:true,symbolSize:4,color:C.green,data:@@BOARD_SZSE@@},
    {name:'创业板',type:'line',showSymbol:true,symbolSize:4,color:C.orange,data:@@BOARD_CYB@@},
    {name:'科创板',type:'line',showSymbol:true,symbolSize:4,color:C.purple,data:@@BOARD_KCB@@}
  ]
});

// 7-9 筹码分布（横向：价格在纵轴，成交额占比在横轴）
function chipOption(el, data, cur, title){
  const prices = data.map(d => d[0]);
  const shares = data.map(d => d[1]);
  let best = 0, bd = 1e9;
  for (let i = 0; i < prices.length; i++) {
    const dd = Math.abs(prices[i] - cur);
    if (dd < bd) { bd = dd; best = i; }
  }
  echarts.init(document.getElementById(el)).setOption({
    title:{text:title,left:'center',textStyle:{fontSize:13}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},
      formatter:p=>'价位 '+prices[p[0].dataIndex].toFixed(0)+'<br/>成交额占比 '+shares[p[0].dataIndex].toFixed(2)+'%'},
    grid:{left:74,right:78,top:46,bottom:34},
    xAxis:{type:'value',...AX,axisLabel:{color:'#6b7280',fontSize:11,formatter:'{value}%'}},
    yAxis:{type:'category',data:prices.map(v=>v.toFixed(0)),...AX,
      axisLabel:{color:'#6b7280',fontSize:9,interval:5},axisTick:{show:false}},
    series:[{type:'bar',data:shares,color:C.blue,barWidth:'88%',
      markLine:{silent:true,symbol:'none',lineStyle:{color:C.red,width:2,type:'solid'},
        label:{formatter:'现价 '+cur,position:'end',fontSize:11,color:C.red,fontWeight:'bold'},
        data:[{yAxis:best}]}}]
  });
}
@@CHIP_JS@@

// 10 融资盘成本线
echarts.init(document.getElementById('c_cost')).setOption({
  title:{text:'现价 vs 融资盘估算成本 · 谁在浮亏',left:'center',textStyle:{fontSize:13}},
  tooltip:{trigger:'axis'},legend:{bottom:0,textStyle:{fontSize:11}},
  grid:{left:52,right:24,top:46,bottom:46},
  xAxis:{type:'category',data:['全A','创业板','科创50'],...AX},
  yAxis:{type:'value',scale:true,...AX},
  series:[
    {name:'现价',type:'bar',data:@@COST_NOW@@,color:C.blue,barWidth:'42%'},
    {name:'融资成本(120日)',type:'bar',data:@@COST_120@@,color:C.amber,barWidth:'42%'},
    {name:'融资成本(250日)',type:'bar',data:@@COST_250@@,color:C.orange,barWidth:'42%'}
  ]
});
</script>
</body>
</html>
"""


def series_xy(df, col="close"):
    d = df["date"] if "date" in df.columns else df["日期"]
    return [[int(t.timestamp() * 1000), round(float(v), 3)] for t, v in zip(d, df[col])]


# —— 组装
bal3 = float(mdx["融资余额"].iloc[-61])
bal1 = float(mdx["融资余额"].iloc[-21])
bal1w = float(mdx["融资余额"].iloc[-6])

# 「追高」证据：全A 高点 2026-05-13 → 融资余额峰值 2026-06-25
bal_0513 = float(mdx.loc[mdx["日期"] == pd.Timestamp("2026-05-13"), "融资余额"].iloc[0])
allA_0513 = float(allA.loc[allA["date"] == pd.Timestamp("2026-05-13"), "close"].iloc[0])
allA_0625 = float(allA.loc[allA["date"] == pd.Timestamp("2026-06-25"), "close"].iloc[0])
jump_abs = peak_bal - bal_0513
jump_pct = peak_bal / bal_0513 - 1
allA_jump_pct = allA_0625 / allA_0513 - 1
week_share = (bal1w - cur_bal) / (bal1 - cur_bal)


def chg_pct(v):
    return f"{v/cur_bal-1:+.1%}"


KPIS = "".join([
    kpi("融资余额", f"{cur_bal/1e4:.2f} 万亿", f"距峰值 {cur_bal/peak_bal-1:+.1%}，名义分位 {float((mdx['融资余额']<=cur_bal).mean()):.0%}", "warn"),
    kpi("两融 / 流通市值", f"{lev_on_float:.2%}", "市场估算 2015 年峰值约 4%~5%", "ok"),
    kpi("融资买入 / 成交额", f"{cur_ratio:.2%}", f"历史分位 {ratio_pct:.0%}，杠杆交易已降温", "blue"),
    kpi("平均维持担保比例", f"{cur_ratio_maint:.0f}%", f"强平线 130%，分位 {maint_pct:.0%}", "ok"),
    kpi("全A 年内回撤", f"{allA_dd:+.1%}", f"高点 {allA_peak_d.strftime('%m-%d')}", "warn"),
    kpi("创业板 / 科创50 回撤", f"{cyb_dd:+.0%} / {kcb_dd:+.0%}", "越成长跌越狠 = 杠杆分布的证据", "warn"),
])

BOARD_SERIES_JS = {}
if len(det):
    for b, key in [("沪市主板", "SSE"), ("深市主板", "SZSE"), ("创业板", "CYB"), ("科创板", "KCB")]:
        s = board_bal[b] if b in board_bal.columns else pd.Series(0, index=board_bal.index)
        BOARD_SERIES_JS[key] = [[int(pd.Timestamp(t).timestamp() * 1000), round(float(v), 1)]
                                for t, v in s.items()]

CHIP_JS = ""
chip_js_parts = []
for el, c, title in [
    ("c_chip_all", chip_all, f"全A 筹码分布（近3年成交额，%）· 现价 {chip_all['cur']:.0f}"),
    ("c_chip_cyb", chip_cyb, f"创业板 筹码分布（近3年成交额，%）· 现价 {chip_cyb['cur']:.0f}"),
    ("c_chip_kcb", chip_kcb, f"科创50 筹码分布（近3年成交额，%）· 现价 {chip_kcb['cur']:.0f}"),
]:
    chip_js_parts.append(f"chipOption('{el}', {json.dumps(chip_bars(c))}, {c['cur']:.2f}, "
                         f"{json.dumps(title)}, {c['peak']:.2f});")
CHIP_JS = "\n".join(chip_js_parts)


def cost_row(name, now, costs):
    cells = "".join(f"<td>{costs[n]:.0f}</td><td class='neg'>{now/costs[n]-1:+.1%}</td>"
                    for n in (120, 250, 500))
    return f"<tr><td>{name}</td><td>{now:.0f}</td>{cells}</tr>"


COST_TABLE = "".join([
    cost_row("全A(000985)", allA_now, c_all),
    cost_row("创业板(399006)", cyb_now, c_cyb),
    cost_row("科创50(000688)", kcb_now, c_kcb),
])

repl = {
    "@@AS_OF@@": AS_OF,
    "@@PEAK_DATE@@": pd.Timestamp(peak_date).strftime("%Y-%m-%d"),
    "@@PEAK_BAL@@": f"{peak_bal/1e4:.2f}",
    "@@CUR_BAL@@": f"{cur_bal/1e4:.2f}",
    "@@TOTAL_LEV@@": f"{total_lev/1e4:.2f}",
    "@@BAL_CHG@@": f"{cur_bal/peak_bal-1:+.1%}",
    "@@BAL_CHG_ABS@@": f"{cur_bal-peak_bal:+.0f}",
    "@@BAL_ABS@@": f"{cur_bal-peak_bal:,.0f}",
    "@@BAL_PCT@@": f"{float((mdx['融资余额']<=cur_bal).mean()):.0%}",
    "@@BAL_3M@@": f"{bal3/1e4:.2f}",
    "@@BAL_1M@@": f"{bal1/1e4:.2f}",
    "@@BAL_1W@@": f"{bal1w/1e4:.2f}",
    "@@BAL_3M_CHG@@": f"{bal3/peak_bal-1:+.1%}",
    "@@BAL_1M_CHG@@": f"{bal1/peak_bal-1:+.1%}",
    "@@BAL_1W_CHG@@": f"{bal1w/peak_bal-1:+.1%}",
    "@@BAL_3M_D@@": f"{cur_bal-bal3:+,.0f}",
    "@@BAL_1M_D@@": f"{cur_bal-bal1:+,.0f}",
    "@@BAL_1W_D@@": f"{cur_bal-bal1w:+,.0f}",
    "@@BAL_0513@@": f"{bal_0513/1e4:.2f}",
    "@@BAL_0625@@": f"{peak_bal/1e4:.2f}",
    "@@JUMP_ABS@@": f"{jump_abs:,.0f}",
    "@@JUMP_PCT@@": f"{jump_pct:+.1%}",
    "@@ALLA_JUMP_PCT@@": f"{allA_jump_pct:.1%}",
    "@@ALLA_PEAK_P@@": f"{allA_peak_p:,.2f}",
    "@@ALLA_NOW@@": f"{allA_now:,.0f}",
    "@@WEEK_D@@": f"{cur_bal-bal1w:+,.0f}",
    "@@WEEK_SHARE@@": f"{week_share:.0%}",
    "@@LEV_FLOAT@@": f"{lev_on_float:.2%}",
    "@@CUR_RATIO@@": f"{cur_ratio:.2%}",
    "@@RATIO_PCT@@": f"{ratio_pct:.0%}",
    "@@MAINT@@": f"{cur_ratio_maint:.1f}%",
    "@@MAINT_PCT@@": f"{maint_pct:.0%}",
    "@@NORM_VAL@@": f"{cur_ratio_norm:.2%}",
    "@@NORM_PCT@@": f"{norm_pct:.0%}",
    "@@ALLA_DD@@": f"{allA_dd:+.1%}",
    "@@ALLA_PEAK_D@@": allA_peak_d.strftime("%Y-%m-%d"),
    "@@CYB_DD@@": f"{cyb_dd:+.1%}",
    "@@CYB_PEAK_D@@": cyb_peak_d.strftime("%Y-%m-%d"),
    "@@KCB_DD@@": f"{kcb_dd:+.1%}",
    "@@KCB_PEAK_D@@": kcb_peak_d.strftime("%Y-%m-%d"),
    "@@DET_FIRST@@": pd.Timestamp(first_d).strftime("%Y-%m-%d") if first_d is not None else "—",
    "@@DET_N@@": str(len(dates)),
    "@@BOARD_TABLE@@": board_table(),
    "@@CYB_KCB_SHARE@@": f"{((board_chg.loc['创业板','最新(亿)']+board_chg.loc['科创板','最新(亿)'])/board_chg.loc['合计','最新(亿)']):.0%}" if len(det) else "—",
    "@@CYB_KCB_CONTRIB@@": f"{((board_chg.loc['创业板','变化(亿)']+board_chg.loc['科创板','变化(亿)'])/board_chg.loc['合计','变化(亿)']):.0%}" if len(det) else "—",
    "@@CYB_D@@": f"{board_chg.loc['创业板','变化(亿)']:+.0f}" if len(det) else "—",
    "@@KCB_D@@": f"{board_chg.loc['科创板','变化(亿)']:+.0f}" if len(det) else "—",
    "@@CYB_CHG@@": f"{board_chg.loc['创业板','变化(%)']:+.1%}" if len(det) else "—",
    "@@KCB_CHG@@": f"{board_chg.loc['科创板','变化(%)']:+.1%}" if len(det) else "—",
    "@@SSE_CHG@@": f"{board_chg.loc['沪市主板','变化(%)']:+.1%}" if len(det) else "—",
    "@@SZSE_CHG@@": f"{board_chg.loc['深市主板','变化(%)']:+.1%}" if len(det) else "—",
    "@@BIG_CUT@@": stock_table(big_cut, "杠杆撤得最猛的个股（融资余额减少额 Top 12）"),
    "@@BIG_ADD@@": stock_table(big_add, "逆势加杠杆的个股（融资余额增加额 Top 8）"),
    "@@CHIP_TABLE@@": chip_table(),
    "@@ALL_BELOW@@": f"{chip_all['below']:.1%}",
    "@@ALL_PEAK@@": f"{chip_all['peak']:.0f}",
    "@@ALL_B20@@": f"{chip_all['band10']+chip_all['band20']:.0%}",
    "@@ALL_B30@@": f"{chip_all['band10']+chip_all['band20']+chip_all['band30']:.0%}",
    "@@ALL_PEAK_CHG@@": f"{chip_all['peak']/chip_all['cur']-1:+.0%}",
    "@@CYB_BELOW@@": f"{chip_cyb['below']:.1%}",
    "@@CYB_B20@@": f"{chip_cyb['band10']+chip_cyb['band20']:.0%}",
    "@@CYB_B2030@@": f"{chip_cyb['band30']:.0%}",
    "@@CYB_PEAK@@": f"{chip_cyb['peak']:.0f}",
    "@@CYB_PEAK_CHG@@": f"{chip_cyb['peak']/chip_cyb['cur']-1:+.0%}",
    "@@KCB_BELOW@@": f"{chip_kcb['below']:.1%}",
    "@@KCB_B10@@": f"{chip_kcb['band10']:.0%}",
    "@@KCB_PEAK@@": f"{chip_kcb['peak']:.0f}",
    "@@KCB_PEAK_CHG@@": f"{chip_kcb['peak']/chip_kcb['cur']-1:+.0%}",
    "@@ENERGY_ALL@@": f"{e_all:.2f}×",
    "@@COST_TABLE@@": COST_TABLE,
    "@@KPIS@@": KPIS,
    # —— JS 数据
    "@@BAL_SERIES@@": json.dumps(series_xy(mdx, "融资余额")),
    "@@LEND_SERIES@@": json.dumps(series_xy(mdx, "融券余额")),
    "@@PEAK_TS@@": str(int(pd.Timestamp(peak_date).timestamp() * 1000)),
    "@@PEAK_BAL_NUM@@": f"{peak_bal:.1f}",
    "@@RATIO_SERIES@@": json.dumps(series_xy(mm.dropna(subset=["ratio"]), "ratio")),
    "@@CUR_RATIO_NUM@@": f"{cur_ratio*100:.3f}",
    "@@MAINT_SERIES@@": json.dumps(series_xy(mdx.dropna(subset=["平均维持担保比例"]), "平均维持担保比例")),
    "@@NORM_ALL@@": json.dumps(norm_series(allA_w)),
    "@@NORM_CYB@@": json.dumps(norm_series(cyb_w)),
    "@@NORM_KCB@@": json.dumps(norm_series(kcb_w)),
    "@@DD_ALL@@": json.dumps(dd_series(allA_w)),
    "@@DD_CYB@@": json.dumps(dd_series(cyb_w)),
    "@@DD_KCB@@": json.dumps(dd_series(kcb_w)),
    "@@BOARD_SSE@@": json.dumps(BOARD_SERIES_JS.get("SSE", [])),
    "@@BOARD_SZSE@@": json.dumps(BOARD_SERIES_JS.get("SZSE", [])),
    "@@BOARD_CYB@@": json.dumps(BOARD_SERIES_JS.get("CYB", [])),
    "@@BOARD_KCB@@": json.dumps(BOARD_SERIES_JS.get("KCB", [])),
    "@@CHIP_JS@@": CHIP_JS,
    "@@COST_NOW@@": json.dumps([round(allA_now, 1), round(cyb_now, 1), round(kcb_now, 1)]),
    "@@COST_120@@": json.dumps([round(c_all[120], 1), round(c_cyb[120], 1), round(c_kcb[120], 1)]),
    "@@COST_250@@": json.dumps([round(c_all[250], 1), round(c_cyb[250], 1), round(c_kcb[250], 1)]),
}

html = HTML
for k, v in repl.items():
    html = html.replace(k, v)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

left = [k for k in repl if k in html]
print("已生成", OUT)
print(f"融资余额 {cur_bal/1e4:.2f}万亿 (峰值 {peak_bal/1e4:.2f} @ {pd.Timestamp(peak_date).date()}, {cur_bal/peak_bal-1:+.1%})")
print(f"两融/流通市值 {lev_on_float:.2%} | 融资买入占比 {cur_ratio:.2%} (分位 {ratio_pct:.0%}) | 维保 {cur_ratio_maint:.1f}%")
print(f"回撤: 全A {allA_dd:+.1%} 创业板 {cyb_dd:+.1%} 科创50 {kcb_dd:+.1%}")
print(f"获利盘: 全A {chip_all['below']:.1%} 创业板 {chip_cyb['below']:.1%} 科创50 {chip_kcb['below']:.1%}")
if left:
    print("!! 未替换的占位符:", left[:5])
