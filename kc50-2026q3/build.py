# -*- coding: utf-8 -*-
"""生成科创50 2026Q3 体检报告（单文件 HTML）。"""
import json, math
import pandas as pd
import numpy as np

ASOF = "2026-10-30"
IDX_CLOSE = 1160.84
IDX_PREV = 1228.09
IDX_PEAK = 2207.86
PE_1030 = 55.211478  # 58.41 * 1160.84/1228.09
PE_ALL_1030 = 76.39  # 80.82 * 1160.84/1228.09
ETF_CLOSE = 1.228
ETF_CHG = -5.03

# ---------- data ----------
r = pd.read_csv("data/merged.csv", dtype={"code": str})
r["权重"] = pd.to_numeric(r["权重"], errors="coerce")
r["cal_pe"] = pd.to_numeric(r["cal_pe"], errors="coerce")
r["np_yoy"] = pd.to_numeric(r["np_yoy"], errors="coerce")
r["single_q"] = pd.to_numeric(r["single_q"], errors="coerce")
r["rev_yoy"] = pd.to_numeric(r["rev_yoy"], errors="coerce")
r["PB_MRQ"] = pd.to_numeric(r["PB_MRQ"], errors="coerce")
r["TOTAL_MARKET_CAP"] = pd.to_numeric(r["TOTAL_MARKET_CAP"], errors="coerce")
r["CHANGE_RATE"] = pd.to_numeric(r["CHANGE_RATE"], errors="coerce")
r["CLOSE_PRICE"] = pd.to_numeric(r["CLOSE_PRICE"], errors="coerce")
r["ttm"] = pd.to_numeric(r["ttm"], errors="coerce")

# history
d = pd.read_csv("data/index_hist.csv")
d["date"] = pd.to_datetime(d["tradeDate"].astype(str), format="%Y%m%d")
d["pe"] = pd.to_numeric(d["peg"], errors="coerce")
d = d.sort_values("date").reset_index(drop=True)
if d["date"].iloc[-1] < pd.Timestamp(ASOF):
    d = pd.concat([d, pd.DataFrame([{"date": pd.Timestamp(ASOF), "close": IDX_CLOSE, "pe": PE_1030}])], ignore_index=True)
d["dd"] = d["close"] / d["close"].cummax() - 1
d["ma20"] = d["close"].rolling(20).mean()
d["ma60"] = d["close"].rolling(60).mean()
d["ma200"] = d["close"].rolling(200).mean()
d["eps"] = d["close"] / d["pe"]

# aggregates
s = r[r["latest"] == "2026-09-30"].copy()
cov_n = len(s); cov_w = s["权重"].sum()
q3_growth = s["q3_profit"].sum() / s["q3_profit_ly"].sum() - 1
s_ex = s[s["code"] != "688525"]
q3_growth_ex = s_ex["q3_profit"].sum() / s_ex["q3_profit_ly"].sum() - 1
rev_growth = s["rev_q3"].sum() / s["rev_q3ly"].sum() - 1 if "rev_q3" in s else np.nan
# rev_q3 not saved in merged; recompute from financials
f = pd.read_csv("data/financials.csv", dtype={"SECURITY_CODE": str})
f["REPORTDATE"] = pd.to_datetime(f["REPORTDATE"]).dt.strftime("%Y-%m-%d")
rev = f.pivot_table(index="SECURITY_CODE", columns="REPORTDATE", values="TOTAL_OPERATE_INCOME", aggfunc="first")
revq = []
for c in s["code"]:
    try:
        revq.append((rev.loc[c, "2026-09-30"] - rev.loc[c, "2026-06-30"],
                     rev.loc[c, "2025-09-30"] - rev.loc[c, "2025-06-30"]))
    except Exception:
        revq.append((np.nan, np.nan))
s["rev_q3"] = [x[0] for x in revq]; s["rev_q3ly"] = [x[1] for x in revq]
rev_growth = s["rev_q3"].sum() / s["rev_q3ly"].sum() - 1

# QoQ: single-quarter Q3 2026 vs Q2 2026, and Q3 revenue vs Q2 revenue.
# Q3 = 9M - H1; Q2 = H1 - Q1. Only positive comparable bases are used.
p = f.pivot_table(index="SECURITY_CODE", columns="REPORTDATE", values="PARENT_NETPROFIT", aggfunc="first")

def fv(df, code, dt):
    try:
        v = df.loc[code, dt]
        return float(v) if pd.notna(v) else np.nan
    except Exception:
        return np.nan

qrows = []
for c in r["code"]:
    q3 = fv(p, c, "2026-09-30") - fv(p, c, "2026-06-30")
    q2 = fv(p, c, "2026-06-30") - fv(p, c, "2026-03-31")
    r3 = fv(rev, c, "2026-09-30") - fv(rev, c, "2026-06-30")
    r2 = fv(rev, c, "2026-06-30") - fv(rev, c, "2026-03-31")
    qrows.append({
        "code": c, "q3": q3, "q2": q2, "r3": r3, "r2": r2,
        "qoq": (q3 / q2 - 1) if (pd.notna(q2) and q2 > 0 and pd.notna(q3) and q3 > 0) else np.nan,
        "qoq_rev": (r3 / r2 - 1) if (pd.notna(r2) and r2 > 0 and pd.notna(r3) and r3 > 0) else np.nan,
    })
qdf = pd.DataFrame(qrows)
qmap = qdf.set_index("code").to_dict("index")
qp = qdf.dropna(subset=["q3", "q2"])
qr = qdf.dropna(subset=["r3", "r2"])
qoq_growth = qp["q3"].sum() / qp["q2"].sum() - 1
qp_ex = qp[qp["code"] != "688525"]
qoq_growth_ex = qp_ex["q3"].sum() / qp_ex["q2"].sum() - 1
qoq_rev = qr["r3"].sum() / qr["r2"].sum() - 1
qr_ex = qr[qr["code"] != "688525"]
qoq_rev_ex = qr_ex["r3"].sum() / qr_ex["r2"].sum() - 1
qoq_median = qdf["qoq"].median()
qoq_rev_median = qdf["qoq_rev"].median()
qoq_pos = int((qdf["qoq"] > 0).sum()); qoq_n = int(qdf["qoq"].notna().sum())
qoq_rev_pos = int((qdf["qoq_rev"] > 0).sum()); qoq_rev_n = int(qdf["qoq_rev"].notna().sum())

pos = r[r["ttm"] > 0]
pe_agg_all = r["TOTAL_MARKET_CAP"].sum() / r["ttm"].sum()
pe_agg_ex = pos["TOTAL_MARKET_CAP"].sum() / pos["ttm"].sum()
pe_median = pos["cal_pe"].median()
pb_median = r["PB_MRQ"].median()

def wmedian(df, col):
    x = df[[col, "权重"]].dropna().sort_values(col)
    c = x["权重"].cumsum() / x["权重"].sum()
    return float(x.loc[c >= 0.5, col].iloc[0])
pe_wmedian = wmedian(pos, "cal_pe")

def bucket(row):
    if row["ttm"] <= 0: return "亏损"
    p = row["cal_pe"]
    if p < 30: return "<30x"
    if p < 60: return "30-60x"
    if p < 100: return "60-100x"
    return ">100x"
r["bucket"] = r.apply(bucket, axis=1)
buckets = []
for k in ["<30x", "30-60x", "60-100x", ">100x", "亏损"]:
    g = r[r["bucket"] == k]
    buckets.append({"name": k, "weight": round(float(g["权重"].sum()), 2), "n": int(len(g))})

pe_gt100_w = float(r.loc[r["cal_pe"] > 100, "权重"].sum())
loss_w = float(r.loc[r["ttm"] <= 0, "权重"].sum())
top5 = float(r.nlargest(5, "权重")["权重"].sum())
top10 = float(r.nlargest(10, "权重")["权重"].sum())
semi_w = float(r.loc[r["BOARD_NAME"] == "半导体", "权重"].sum())

# percentiles
hist = d[d["date"] < pd.Timestamp(ASOF)]
pct_2020 = float((hist[hist["date"] >= "2020-07-22"]["pe"].dropna() < PE_1030).mean() * 100)
pct_2023 = float((hist[hist["date"] >= "2023-01-01"]["pe"].dropna() < PE_1030).mean() * 100)

# industry chart data
ind_map = {
    "半导体": "半导体", "军工电子Ⅱ": "军工电子", "光伏设备": "光伏", "医疗器械": "医疗器械",
    "软件开发": "软件", "自动化设备": "自动化", "元件": "元件", "消费电子": "消费电子",
    "化学制药": "化学制药", "小家电": "小家电", "轨交设备Ⅱ": "轨交", "航空装备Ⅱ": "航空",
    "摩托车及其他": "两轮车", "通信设备": "通信", "生物制品": "生物制品", "计算机设备": "计算机",
    "IT服务Ⅱ": "IT服务",
}
ind_rows = []
for name, g in r.groupby("BOARD_NAME"):
    sg = s[s["BOARD_NAME"] == name]
    base = sg["q3_profit_ly"].sum()
    growth = (sg["q3_profit"].sum() / base - 1) * 100 if (len(sg) and base > 0) else -100
    ind_rows.append({"name": ind_map.get(name, name), "weight": float(g["权重"].sum()),
                     "growth": max(-100, min(300, growth)), "raw": growth,
                     "n": len(g), "disc": len(sg)})
ind_rows.sort(key=lambda x: -x["weight"])
ind_rows = ind_rows[:9]

# stocks payload
stocks = []
for _, x in r.iterrows():
    loss = bool(x["ttm"] <= 0)
    pe = None if loss else float(x["cal_pe"])
    stocks.append({
        "code": x["code"], "name": x["成分券名称"], "weight": round(float(x["权重"]), 3),
        "industry": ind_map.get(x["BOARD_NAME"], x["BOARD_NAME"]),
        "price": round(float(x["CLOSE_PRICE"]), 2), "chg": round(float(x["CHANGE_RATE"]), 2),
        "mcap": round(float(x["TOTAL_MARKET_CAP"]) / 1e8, 0),
        "pe": None if pe is None else round(pe, 1), "loss": loss,
        "pb": None if pd.isna(x["PB_MRQ"]) else round(float(x["PB_MRQ"]), 2),
        "growth": None if pd.isna(x["np_yoy"]) else round(float(x["np_yoy"]), 1),
        "qoq": None if pd.isna(qmap[x["code"]]["qoq"]) else round(float(qmap[x["code"]]["qoq"]) * 100, 1),
        "single": None if pd.isna(x["single_q"]) else round(float(x["single_q"]) * 100, 1),
        "rev": None if pd.isna(x["rev_yoy"]) else round(float(x["rev_yoy"]), 1),
        "qoq_rev": None if pd.isna(qmap[x["code"]]["qoq_rev"]) else round(float(qmap[x["code"]]["qoq_rev"]) * 100, 1),
        "period": "Q3" if x["latest"] == "2026-09-30" else "H1",
    })
stocks.sort(key=lambda z: -z["weight"])
qoq_chart = [z for z in stocks if z["qoq"] is not None and z["single"] is not None][:10]

hist_payload = []
for _, x in d.iterrows():
    hist_payload.append({"date": x["date"].strftime("%Y-%m-%d"),
                         "close": round(float(x["close"]), 2),
                         "pe": None if pd.isna(x["pe"]) else round(float(x["pe"]), 2),
                         "dd": round(float(x["dd"]) * 100, 2),
                         "ma20": None if pd.isna(x["ma20"]) else round(float(x["ma20"]), 2),
                         "ma60": None if pd.isna(x["ma60"]) else round(float(x["ma60"]), 2)})

DATA = {
    "asof": ASOF,
    "index": {
        "close": IDX_CLOSE, "chg": round((IDX_CLOSE / IDX_PREV - 1) * 100, 2),
        "peak": IDX_PEAK, "dd": round((IDX_CLOSE / IDX_PEAK - 1) * 100, 1),
        "rsi": 22.7, "ma20": 1371.36, "ma60": 1555.79, "ma200": 1586.95,
        "ret20": -28.4, "pe": round(PE_1030, 1), "pe_all": round(PE_ALL_1030, 1),
        "pe_pct_2020": round(pct_2020, 1), "pe_pct_2023": round(pct_2023, 1),
        "pe_median": round(float(hist[hist["date"] >= "2020-07-22"]["pe"].median()), 1),
        "pe_min": round(float(hist["pe"].min()), 1), "pe_max": round(float(hist["pe"].max()), 1),
        "eps": round(PE_1030 and IDX_CLOSE / PE_1030, 2),
        "etf": ETF_CLOSE, "etf_chg": ETF_CHG,
        "vol": 42.0, "maxdd": -62.7,
    },
    "q3": {
        "cov_n": cov_n, "cov_w": round(float(cov_w), 1), "total_n": len(r),
        "growth": round(float(q3_growth) * 100, 1),
        "growth_ex": round(float(q3_growth_ex) * 100, 1),
        "rev_growth": round(float(rev_growth) * 100, 1),
        "median": round(float(s["np_yoy"].median()), 1),
        "single_median": round(float(s["single_q"].median()) * 100, 1),
        "breadth": round(float((s["np_yoy"] > 0).mean()) * 100, 1),
        "single_breadth": round(float((s["single_q"] > 0).sum() / s["single_q"].notna().sum()) * 100, 1),
        "qoq": round(float(qoq_growth) * 100, 1),
        "qoq_ex": round(float(qoq_growth_ex) * 100, 1),
        "qoq_rev": round(float(qoq_rev) * 100, 1),
        "qoq_rev_ex": round(float(qoq_rev_ex) * 100, 1),
        "qoq_median": round(float(qoq_median) * 100, 1),
        "qoq_rev_median": round(float(qoq_rev_median) * 100, 1),
        "qoq_pos": qoq_pos, "qoq_n": qoq_n,
        "qoq_rev_pos": qoq_rev_pos, "qoq_rev_n": qoq_rev_n,
        "qoq_chart": qoq_chart,
    },
    "valuation": {
        "pe": round(PE_1030, 1), "pe_all": round(PE_ALL_1030, 1),
        "pe_agg_all": round(float(pe_agg_all), 1), "pe_agg_ex": round(float(pe_agg_ex), 1),
        "pe_median": round(float(pe_median), 1), "pe_wmedian": round(float(pe_wmedian), 1),
        "pb_median": round(float(pb_median), 2), "div_yield": 0.31,
        "pe_gt100_w": round(pe_gt100_w, 1), "loss_w": round(loss_w, 1),
        "top5": round(top5, 1), "top10": round(top10, 1), "semi_w": round(semi_w, 1),
    },
    "buckets": buckets,
    "industries": ind_rows,
    "stocks": stocks,
    "history": hist_payload,
}

# ---------- HTML ----------
def fmt_pct(v, digits=1):
    if v is None: return "—"
    return f"{v:+.{digits}f}%"

top10_rows = ""
for x in stocks[:10]:
    growth = "—" if x["growth"] is None else (f"{x['growth']:+.0f}%" if abs(x["growth"]) < 1000 else ">+1000%")
    qoq = "—" if x["qoq"] is None else f"{x['qoq']:+.0f}%"
    pe = "亏损" if x["loss"] else f"{x['pe']:.1f}x"
    tag = "Q3" if x["period"] == "Q3" else "H1*"
    gcls = "up" if (x["growth"] or 0) > 0 else "down"
    qcls = "up" if (x["qoq"] or 0) > 0 else ("down" if x["qoq"] is not None else "muted")
    top10_rows += f"<tr><td class='nm'>{x['name']}</td><td>{x['weight']:.2f}%</td><td>{pe}</td><td class='{gcls}'>{growth}</td><td class='{qcls}'>{qoq}</td><td class='muted'>{tag}</td></tr>"

buckets_json = json.dumps(DATA, ensure_ascii=False, separators=(",", ":"))
html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>科创50 2026Q3 体检：泡沫挤掉一半，便宜还谈不上</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
:root{
  --ink:#18222e; --ink2:#354255; --muted:#7b8796; --line:#e5e8ec;
  --bg:#f5f3ee; --card:#fff; --red:#c0392b; --red2:#a93226; --green:#1f7a5c;
  --blue:#2f5f8f; --amber:#b7791f; --soft:#fbfaf7;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:36px 22px 80px}
.kicker{font-size:12px;letter-spacing:.16em;color:var(--muted);font-weight:700;text-transform:uppercase}
h1{font-size:42px;line-height:1.22;letter-spacing:-.02em;margin:10px 0 12px;font-weight:800}
h1 em{font-style:normal;color:var(--red)}
.dek{font-size:17px;color:var(--ink2);max-width:850px;margin:0 0 14px}
.meta{font-size:12.5px;color:var(--muted)}
.hero{display:grid;grid-template-columns:1.35fr .9fr;gap:16px;margin:26px 0 18px}
.concl{background:linear-gradient(145deg,#1d2a38,#27384a);color:#fff;border-radius:18px;padding:24px 26px;box-shadow:0 14px 40px rgba(24,34,46,.16)}
.concl .tag{display:inline-block;font-size:11.5px;letter-spacing:.1em;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.18);padding:3px 9px;border-radius:999px;margin-bottom:12px}
.concl p{font-size:15.3px;color:#e8edf3;margin:8px 0}
.concl b{color:#fff}
.concl .hl{color:#ffd27a;font-weight:700}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 16px;box-shadow:0 3px 14px rgba(24,34,46,.04)}
.card .lbl{font-size:12px;color:var(--muted);margin-bottom:2px}
.card .num{font-size:25px;font-weight:800;letter-spacing:-.02em;line-height:1.35}
.card .sub{font-size:11.5px;color:var(--muted);margin-top:1px}
.red{color:var(--red)} .green{color:var(--green)} .amber{color:var(--amber)} .blue{color:var(--blue)}
.up{color:var(--red);font-weight:600} .down{color:var(--green);font-weight:600}
.section{margin-top:42px}
h2{font-size:24px;letter-spacing:-.01em;margin:0 0 6px;padding-left:13px;border-left:5px solid var(--red);line-height:1.35}
h3{font-size:16.5px;margin:24px 0 8px}
.lead{color:var(--ink2);font-size:14.5px;margin:0 0 14px;max-width:960px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:14px 0;box-shadow:0 3px 14px rgba(24,34,46,.035)}
.chart{width:100%;height:430px}
.chart.small{height:170px}
.chart.mid{height:360px}
.chart.qoq{height:470px}
.note{font-size:12px;color:var(--muted);line-height:1.65;margin:8px 0 0}
.note b{color:var(--ink2)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.mini{font-size:13px;color:var(--ink2)}
.thermo{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:14px 0}
.tbar{position:relative;height:14px;border-radius:999px;background:linear-gradient(90deg,#2e8b6d 0%,#8bbf7a 24%,#e5c15a 48%,#e08b45 72%,#c0392b 100%);margin:16px 0 8px}
.tmark{position:absolute;top:-9px;width:4px;height:32px;background:#18222e;border-radius:2px;box-shadow:0 0 0 3px #fff}
.tmark:after{content:attr(data-label);position:absolute;top:-24px;left:50%;transform:translateX(-50%);font-size:11.5px;font-weight:800;color:#18222e;white-space:nowrap;background:#fff;border:1px solid var(--line);border-radius:5px;padding:1px 6px}
.tlabels{display:flex;justify-content:space-between;font-size:11px;color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid #eceef1;padding:8px 9px;text-align:right;white-space:nowrap}
th{font-size:11.5px;color:var(--muted);font-weight:700;background:#fafbfc;position:sticky;top:0;cursor:pointer;user-select:none}
th:first-child,td:first-child{text-align:left}
td.nm{font-weight:650;color:var(--ink)}
tr:hover td{background:#fcfbf8}
.tablewrap{max-height:760px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:#fff}
.tablewrap.full{max-height:none}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0}
.btn{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 12px;font-size:12.5px;color:var(--ink2);cursor:pointer}
.btn.on{background:#18222e;color:#fff;border-color:#18222e}
input.search{border:1px solid var(--line);background:#fff;border-radius:999px;padding:6px 13px;font-size:13px;min-width:180px;outline:none}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;background:#f1f3f5;color:var(--ink2);margin-left:4px}
.badge.hot{background:#fbe9e7;color:var(--red)}
.badge.cold{background:#e8f4ef;color:var(--green)}
.badge.mid{background:#fdf3e1;color:var(--amber)}
.scen{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}
.scard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;position:relative;overflow:hidden}
.scard:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px}
.scard.base:before{background:var(--amber)} .scard.bear:before{background:var(--green)} .scard.bull:before{background:var(--red)}
.scard .p{font-size:30px;font-weight:800;line-height:1.15}
.scard .t{font-size:14px;font-weight:750;margin-top:2px}
.scard .r{font-size:13px;color:var(--ink2);margin-top:8px}
.scard .why{font-size:12px;color:var(--muted);margin-top:8px;line-height:1.6}
.pbar{height:6px;background:#eef0f2;border-radius:999px;margin-top:12px;overflow:hidden}
.pbar i{display:block;height:100%;border-radius:999px}
.plan{display:grid;grid-template-columns:1.1fr .9fr;gap:16px}
.planbox{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}
.planbox h3{margin-top:0}
.rule{display:flex;gap:10px;align-items:flex-start;padding:9px 0;border-bottom:1px dashed #e9ebee;font-size:13.5px}
.rule:last-child{border-bottom:0}
.rule .k{min-width:96px;font-weight:750;color:var(--ink)}
.rule .v{color:var(--ink2)}
.quote{background:#fbf6ea;border:1px solid #eadfc5;border-radius:12px;padding:14px 16px;font-size:13.5px;color:#5c4a28;margin:14px 0}
.quote b{color:#3d2f17}
ul{padding-left:20px;margin:8px 0} li{margin:5px 0;color:var(--ink2);font-size:14px}
.footer{margin-top:44px;padding-top:16px;border-top:1px solid #dfe2e6;font-size:12px;color:var(--muted)}
@media(max-width:900px){.hero,.grid2,.plan{grid-template-columns:1fr}.scen,.grid3{grid-template-columns:1fr}h1{font-size:32px}.cards{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.wrap{padding:24px 14px 60px}h1{font-size:28px}.cards{grid-template-columns:1fr}.chart{height:360px}.chart.qoq{height:420px}.tablewrap{max-height:560px}}
</style>
</head>
<body>
<div class="wrap">

<div class="kicker">STAR 50 · 2026 Q3 EARNINGS &amp; VALUATION REVIEW</div>
<h1>科创50：泡沫挤掉一半，<br><em>“便宜”还谈不上</em></h1>
<p class="dek">4 个月跌 47%，PE 从 105x 压到 55x；Q3 净利同比还在 +49%，但单季环比已经 -25%。市场杀的是边际减速，不是同比。现在该加、该减，还是拿着不动？</p>
<div class="meta">数据截止 2026-10-30 收盘｜指数 1160.84（-5.48%）｜ETF 588000 收盘 1.228（-5.03%）｜不构成投资建议</div>

<div class="hero">
  <div class="concl">
    <span class="tag">一句话结论</span>
    <p><b>这不是“盈利崩了”，是“估值崩了”。</b>6/30 高点 2207.86 → 10/30 1160.84，<span class="hl">-47.4%</span>；同期 PE 104.75x → 55.2x，指数 TTM EPS 几乎没动。</p>
    <p>但 55x 仍在上市以来 <span class="hl">58% 分位</span>，远高于 2022/2024 年底部的 36x/23x。Q3 已披露成分股净利同比 <span class="hl">+49%</span>，但单季环比 <span class="hl">-24.7%</span>（剔除佰维 -14.3%）；覆盖权重只有 70.3%，且半导体占指数 79.4%。</p>
    <p><b>操作：4% 仓位保留，不追、不割；跌到 1000 以下再分批加，反弹到 1450 以上再分批减。</b>把它当卫星仓，不是抄底工具。</p>
  </div>
  <div class="cards">
    <div class="card"><div class="lbl">距 6/30 高点</div><div class="num red">-47.4%</div><div class="sub">2207.86 → 1160.84｜20日 -28.4%</div></div>
    <div class="card"><div class="lbl">PE-TTM（剔除亏损，估算）</div><div class="num">55.2x</div><div class="sub">整体法约 76.4x｜历史 58% 分位</div></div>
    <div class="card"><div class="lbl">单季净利同比 / 环比</div><div class="num red">+49.2%</div><div class="sub">环比 -24.7%｜剔除佰维 -14.3%｜36/50</div></div>
    <div class="card"><div class="lbl">Q3 营收同比 / 环比</div><div class="num amber">+9.8%</div><div class="sub">环比 -2.2%｜22/36 环比为正</div></div>
  </div>
</div>

<div class="section">
<h2>1. 先看发生了什么：4 个月 -47%，纯杀估值</h2>
<p class="lead">从 6 月 30 日到 10 月 30 日，科创50 几乎腰斩。把价格拆成“估值 × 盈利”后，答案很直接：<b>盈利没怎么掉，掉的是市场愿意给的倍数。</b></p>

<div class="panel"><div id="cMain" class="chart"></div>
<div class="note">左轴：指数收盘；右轴：中证官网 PE 序列（与“剔除亏损”口径接近，当前为估算值）。虚线为 MA20/MA60。数据：中证指数、新浪财经。</div></div>

<div class="grid3">
  <div class="card"><div class="lbl">指数收盘</div><div class="num">1160.84</div><div class="sub">10/30 -5.48%｜RSI 22.7｜20日 -28.4%</div></div>
  <div class="card"><div class="lbl">TTM EPS（价格/PE）</div><div class="num">21.03</div><div class="sub">6/30 为 21.08，几乎持平；同比约 +13%</div></div>
  <div class="card"><div class="lbl">最大回撤（2021-2024）</div><div class="num red">-62.7%</div><div class="sub">本轮 -47.4%，历史极端底部尚未触及</div></div>
</div>

<div class="panel"><div id="cDD" class="chart small"></div>
<div class="note">回撤曲线：当前 -47.4%，距 2021-2024 年 -62.7% 的历史最大回撤还有约 15 个百分点（若以高点计，对应指数约 824 点）。</div></div>

<div class="quote"><b>关键判断：</b>这更像 2021-2022 年的“挤泡沫”，而不是 2024 年的“盈利底”。区别在于：2024 年底部 PE 只有 23-30x，现在仍有 55x；跌了很多，不等于跌到了历史底部。</div>
</div>

<div class="section">
<h2>2. Q3 成绩单：强，但强得很集中</h2>
<p class="lead">截至 10/30，50 只成分股中 36 只已披露三季报，覆盖权重 70.3%。已披露公司单季净利合计同比 <b>+49.2%</b>，剔除佰维存储后 <b>+36.6%</b>；收入合计同比 +9.8%。<b>但同比是后视镜：单季净利环比 Q2 为 -24.7%，见 2.5。</b></p>

<div class="grid3">
  <div class="card"><div class="lbl">单季净利合计同比</div><div class="num red">+49.2%</div><div class="sub">14.81B vs 9.92B｜36 家已披露</div></div>
  <div class="card"><div class="lbl">单季净利同比中位数</div><div class="num red">+34.7%</div><div class="sub">26 家有可比单季数据｜18 家为正</div></div>
  <div class="card"><div class="lbl">增长广度</div><div class="num amber">52.8%</div><div class="sub">累计净利同比为正的公司占比</div></div>
</div>

<div class="grid2" style="margin-top:14px">
  <div class="panel"><div id="cInd" class="chart mid"></div><div class="note">按申万行业分组，柱长为 Q3 净利合计同比（为展示效果，负值下限截断至 -100%），标签为指数总权重；柱长为已披露公司 Q3 净利合计同比，按 -100%~+300% 截断。半导体权重 79.4%，是绝对主角。</div></div>
  <div class="panel"><h3 style="margin-top:0">权重前十：估值与增速</h3>
    <table><thead><tr><th>成分股</th><th>权重</th><th>PE</th><th>累计净利同比</th><th>单季净利环比</th><th>期</th></tr></thead><tbody>__TOP10__</tbody></table>
    <div class="note">前十大权重合计 59.7%，前五大 39.6%。同比为累计口径（Q3=9M、H1=半年报），环比为单季 Q3/Q2；两者口径不同，只看方向。*H1 表示三季报尚未披露。</div>
  </div>
</div>

<div class="quote"><b>盈利的两个“但是”：</b>① 增长高度集中——半导体已披露公司合计 +147.5%，但光伏、医疗器械、自动化等仍在拖累；② 指数 TTM EPS 同比只有约 +13%，远低于成分股 Q3 合计 +49%，说明<b>不能把 +49% 直接外推成指数盈利增速</b>。增长是真的，但没有那么均匀。</div>

<h3>行业与个股的冷热差</h3>
<ul>
<li><b>强：</b>半导体设备/算力链——中微公司 Q3 净利 +241%、拓荆科技 +337%、澜起科技 +98%、寒武纪 +131%、睿创微纳 +225%；佰维存储受存储涨价影响，同比 +28,728%（低基数，参考意义有限）。</li>
<li><b>弱：</b>光伏（大全能源 -87%、阿特斯 -110%、晶科能源 -6%）、医疗器械（联影医疗 -7.6%）、自动化（中控技术 -56%）、部分军工（国博电子 -68%、西部超导 -60%）。</li>
<li><b>分化：</b>同样是半导体，华虹宏力 +437%、中芯国际 +94%，但盛美上海 -15%、晶合集成 -14%、格科微 -75%。选指数≠选对赛道。</li>
</ul>
</div>

<div class="section">
<h2>2.5 环比：同比是后视镜，环比才是边际</h2>
<p class="lead">Q3 单季净利同比 <b>+49.2%</b> 很好看，但环比 Q2 <b>-24.7%</b>（剔除佰维 -14.3%），营收环比 -2.2%。<b>收入几乎持平、利润明显下滑</b>，说明毛利率/费用在恶化，或 Q2 本身是不可持续的高基数。市场杀的正是这个边际减速，而不是同比。</p>

<div class="grid3">
  <div class="card"><div class="lbl">Q3 净利合计环比</div><div class="num red">-24.7%</div><div class="sub">14.81B vs 19.68B｜36 家可比</div></div>
  <div class="card"><div class="lbl">Q3 营收合计环比</div><div class="num amber">-2.2%</div><div class="sub">110.6B vs 113.1B｜36 家可比</div></div>
  <div class="card"><div class="lbl">净利环比正增长</div><div class="num amber">11 / 25</div><div class="sub">44%｜营收 22/36（61%）</div></div>
</div>

<div class="grid2" style="margin-top:14px">
  <div class="panel"><div id="cQoQ" class="chart qoq"></div><div class="note">单季同比 = 2026Q3 / 2025Q3 - 1；单季环比 = 2026Q3 / 2026Q2 - 1。佰维同比 +525% 截断至 +200%，负值柱不标数字，精确值见 tooltip 或文末全表。纵轴标签为“名称 + 指数权重”。数据：东方财富，2026-10-30。</div></div>
  <div class="panel"><h3 style="margin-top:0">同比 vs 环比：收入还在，利润先掉</h3>
    <table><thead><tr><th>指标</th><th>同比（单季）</th><th>环比（单季）</th><th>说明</th></tr></thead><tbody>
      <tr><td>净利合计</td><td class="up">+49.2%</td><td class="down">-24.7%</td><td>14.81B vs 19.68B</td></tr>
      <tr><td>营收合计</td><td class="up">+9.8%</td><td class="down">-2.2%</td><td>110.6B vs 113.1B</td></tr>
      <tr><td>净利中位数</td><td class="up">+34.7%</td><td class="down">-12.4%</td><td>25 家可比</td></tr>
      <tr><td>营收中位数</td><td class="up">+17.1%</td><td class="up">+4.2%</td><td>36 家可比</td></tr>
      <tr><td>正增长家数</td><td>18/26</td><td>11/25</td><td>营收 27/36；环比 22/36</td></tr>
    </tbody></table>
    <div class="note">同比为 2026Q3 vs 2025Q3，环比为 2026Q3 vs 2026Q2；均为单季、未年化、未季调。净利同比/环比只统计正基数，故分母小于 36，避免负基数失真。</div>
  </div>
</div>

<div class="quote"><b>为什么跌：</b>不是 Q3 同比差，而是环比动能断了。收入端还在（合计 -2.2%、中位数 +4.2%），利润端却环比 -24.7%；<b>佰维、金山、盛美、中微、联影五家合计减少约 64 亿</b>，超过整体 49 亿的降幅，拓荆、睿创、晶晨等增长只够部分对冲。市场提前交易的是 Q4/2027 的增速下修，而不是已经兑现的 Q3。</div>

<h3>环比的冷热差：谁在失速，谁在加速</h3>
<ul>
<li><b>加速：</b>晶晨股份 +56.0%、拓荆科技 +40.9%、睿创微纳 +33.3%、寒武纪 +8.2%、澜起科技 +7.8%；这些是少数 Q3 环比还在改善的权重股。</li>
<li><b>失速：</b>盛美上海 -90.8%（设备验收节奏）、联影医疗 -72.3%（收入环比 -14.8%）、金山办公 -63.0%（Q3 是软件淡季）、佰维存储 -62.4%（Q2 42.7 亿的高基数）、中微公司 -30.9%（收入仅 -3.7%，利润跌更多，毛利率承压）。</li>
<li><b>关键差异：</b>营收环比中位数 +4.2%，但净利环比中位数 -12.4%——这不是“需求崩了”，更像“价格/毛利率/费用”在挤利润。对科技股，后者同样能杀估值，而且比收入下滑更隐蔽。</li>
</ul>
<div class="note">环比也有季节性：Q3 对软件是淡季、对设备是验收波动，单季不能定论。要看连续 2-3 个季度，以及营收环比是否同步转负；如果营收环比仍正、利润环比继续负，才是真正的毛利率问题。</div>
</div>

<div class="section">
<h2>3. 估值：55x 是贵还是便宜？</h2>
<p class="lead">把“亏损股”和“盈利股”分开看，会得到两个截然不同的数字：整体法 PE 约 <b>76x</b>（亏损股抬高），剔除亏损后约 <b>55x</b>。无论哪个口径，都不是历史底部。</p>

<div class="thermo">
  <div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px">
    <div><span class="mini">上市以来 PE 分位</span> <b style="font-size:22px">58%</b> <span class="muted">｜近三年 66%</span></div>
    <div class="mini">当前 55.2x｜中位数 49.6x｜区间 23.4x–104.8x</div>
  </div>
  <div class="tbar"><span class="tmark" style="left:58%" data-label="现在 55.2x"></span></div>
  <div class="tlabels"><span>23x 极便宜</span><span>36x 2022底</span><span>50x 中位</span><span>60x</span><span>80x</span><span>105x 极贵</span></div>
</div>

<div class="grid2">
  <div class="panel"><div id="cPE" class="chart mid"></div><div class="note">按当前权重统计：PE &gt;100x 的股票占 38.9%，亏损股占 14.3%，两者合计 53.2%；PE &lt;30x 的只有 14.4%。这是一个“哑铃型”结构，不是整体便宜。</div></div>
  <div class="panel"><div id="cScatter" class="chart mid"></div><div class="note">横轴 Q3 净利同比（截断 -100%~+300%），纵轴 PE（对数，10x–500x），气泡大小=权重。右上角是“高增长但很贵”，左下角是“低估值但低增长”。佰维（+28,728%）、沐曦（20,238x）、中科飞测（亏损）未入图。</div></div>
</div>

<h3>历史坐标：同样的跌幅，不一样的估值</h3>
<div class="tablewrap" style="max-height:none">
<table>
<thead><tr><th>时点</th><th>指数</th><th>PE</th><th>之后 12 个月</th><th>含义</th></tr></thead>
<tbody>
<tr><td>2021-07-08 高点</td><td>1610.77</td><td>77.2x</td><td class="down">-31.5%</td><td>高估值 + 盈利下修，戴维斯双杀</td></tr>
<tr><td>2022-04-26 低点</td><td>868.07</td><td>36.1x</td><td class="up">+23.1%</td><td>估值先见底，盈利仍在磨</td></tr>
<tr><td>2024-02-02 低点</td><td>673.41</td><td>23.4x</td><td class="up">+45.9%</td><td>历史级便宜，随后 AI 周期启动</td></tr>
<tr><td>2024-09-23 低点</td><td>643.04</td><td>30.6x</td><td class="up">+118.9%</td><td>政策底 + 产业周期共振</td></tr>
<tr><td>2026-06-30 高点</td><td>2207.86</td><td>104.8x</td><td class="down">-47.4%（至 10/30）</td><td>估值顶，4 个月完成大部分回撤</td></tr>
<tr style="background:#fbf6ea"><td><b>2026-10-30 现在</b></td><td><b>1160.84</b></td><td><b>55.2x</b></td><td>—</td><td><b>中性偏贵，不是历史大底</b></td></tr>
</tbody></table>
</div>
<div class="note">“之后 12 个月”为对应时点起算的价格涨跌幅，不含分红；历史不代表未来。PE 为官网接口口径（接近剔除亏损），与整体法 76x 不可直接混用。</div>

<div class="quote"><b>结论：</b>如果只看“跌了多少”，-47% 很像底部；如果看“估值在哪”，55x 只是从极端贵回到中性偏贵。历史大底（2022/2024）对应 23-36x，按当前 EPS 不变估算，对应指数约 <b>490-760 点</b>——这不是预测，而是说明“便宜”离现在还有多远。</div>
</div>

<div class="section">
<h2>4. 贵还是便宜：一张记分卡</h2>
<div class="tablewrap" style="max-height:none">
<table>
<thead><tr><th>维度</th><th>读数</th><th>判断</th></tr></thead>
<tbody>
<tr><td>绝对估值</td><td>PE 55.2x（剔除亏损）/ 76.4x（整体法）；PB 中位 5.68x；股息率 0.31%</td><td><span class="badge hot">贵</span></td></tr>
<tr><td>历史分位</td><td>上市以来 58%，近三年 66%</td><td><span class="badge mid">中性偏贵</span></td></tr>
<tr><td>价格回撤</td><td>距 6/30 高点 -47.4%，20 日 -28.4%</td><td><span class="badge cold">已大幅释放</span></td></tr>
<tr><td>盈利增速</td><td>Q3 已披露合计 +49.2%；单季中位 +34.7%</td><td><span class="badge cold">强</span></td></tr>
<tr><td>盈利广度</td><td>累计同比为正仅 52.8%；14 只亏损（权重 14.3%）</td><td><span class="badge mid">一般</span></td></tr>
<tr><td>PEG（粗算）</td><td>55x ÷ 49% ≈ 1.1；用 TTM EPS +13% 则约 4.2</td><td><span class="badge mid">取决于增速能否持续</span></td></tr>
<tr><td>趋势</td><td>低于 MA20（1371）/MA60（1556）/MA200（1587）；RSI 22.7</td><td><span class="badge hot">弱，超卖</span></td></tr>
</tbody></table>
</div>
<p class="lead" style="margin-top:14px"><b>综合：</b>“估值中性偏贵 + 盈利强 + 趋势弱”的组合，对应的是<b>持有/观察</b>，不是重仓抄底，也不是恐慌清仓。真正决定下一段的不是“跌了多少”，而是 Q4 和 2027 年半导体盈利能不能接上。</p>
</div>

<div class="section">
<h2>5. 未来走势概率：三种情景</h2>
<p class="lead">下面是主观情景分析，不是模型预测。概率按“未来 6-12 个月”设定，核心变量是盈利兑现、估值中枢和风险偏好。</p>
<div class="scen">
  <div class="scard base"><div class="p amber">45%</div><div class="t">基准：震荡筑底</div><div class="r">指数 1100–1400｜PE 50–60x</div><div class="why">Q3/Q4 盈利保持 20-40% 增长，估值不再压缩；市场等待新的产业催化。对应 12 个月约 -5%~+21%。</div><div class="pbar"><i style="width:45%;background:#b7791f"></i></div></div>
  <div class="scard bear"><div class="p green">30%</div><div class="t">熊市：二次探底</div><div class="r">指数 820–1000｜PE 38–45x</div><div class="why">AI 资本开支下修、解禁/IPO 供给、或盈利不及预期；估值向 2022 年中枢靠拢。对应 -14%~-29%。</div><div class="pbar"><i style="width:30%;background:#1f7a5c"></i></div></div>
  <div class="scard bull"><div class="p red">25%</div><div class="t">牛市：超跌反弹</div><div class="r">指数 1500–1800｜PE 65–80x</div><div class="why">Q4 业绩超预期 + 政策/流动性宽松 + 站上 MA20；空头回补带来快速修复。对应 +29%~+55%。</div><div class="pbar"><i style="width:25%;background:#c0392b"></i></div></div>
</div>
<div class="grid3">
  <div class="card"><div class="lbl">概率加权期望（12个月）</div><div class="num green">约 +7%</div><div class="sub">按区间中值粗算，分布很宽</div></div>
  <div class="card"><div class="lbl">上行触发</div><div class="num blue">站上 1371</div><div class="sub">MA20 + Q4 指引上修 + PE 回到 60x 以上</div></div>
  <div class="card"><div class="lbl">下行触发</div><div class="num red">跌破 1000</div><div class="sub">PE 向 45x 靠拢，可能加速赎回/止损</div></div>
</div>
<div class="note">概率加权：0.45×(+8%) + 0.30×(-22%) + 0.25×(+42%) ≈ +7%。这只是把情景中值按主观概率相加，不构成收益承诺。</div>
</div>

<div class="section">
<h2>6. 4% 仓位，具体怎么做</h2>
<p class="lead">4% 对科创50 这种年化波动 42%、历史最大回撤 -63% 的资产，已经是“合适的卫星仓”，不是“必须重仓的核心资产”。<b>当前动作：持有，不追加，也不在恐慌里割。</b></p>

<div class="plan">
  <div class="planbox">
    <h3>分批计划（按指数点位）</h3>
    <div class="rule"><div class="k">现在 1161</div><div class="v"><b>持有 4%</b>，不加。RSI 22.7 超卖，但趋势未反转，等止跌确认。</div></div>
    <div class="rule"><div class="k">1050–1100</div><div class="v">若出现“收盘不再创新低 / 站上 5 日线”，加 <b>0.5%</b> → 4.5%。</div></div>
    <div class="rule"><div class="k">900–950</div><div class="v">加 <b>1.0%</b> → 5.5%；只加一次，不 daily 补。</div></div>
    <div class="rule"><div class="k">800–850</div><div class="v">加 <b>1.0%</b> → 6.5%；对应历史最大回撤附近，仓位上限 7%。</div></div>
    <div class="rule"><div class="k">1450–1500</div><div class="v">减 <b>1.0%</b> → 3.0%；反弹到 MA60 附近先收回一部分。</div></div>
    <div class="rule"><div class="k">1650–1750</div><div class="v">再减 <b>1.0%</b> → 2.0%；PE 回到 75x 以上，赔率变差。</div></div>
    <div class="rule"><div class="k">1900+</div><div class="v">只留 <b>1%</b> 或清仓；接近前高，风险收益不对称。</div></div>
  </div>
  <div class="planbox">
    <h3>三条纪律</h3>
    <ul>
      <li><b>不要一把梭。</b>4% 的仓位，最大回撤再 30% 对组合影响约 1.2 个百分点；但加到 10% 就是 3 个百分点，性质变了。</li>
      <li><b>不要用“跌了很多”当买入理由。</b>从 2208 跌到 1161 是 -47%，但 PE 还有 55x；估值没到历史底部。</li>
      <li><b>不要每天看。</b>给 6-12 个月，按季度财报和点位规则操作；中间的小波动不构成信号。</li>
    </ul>
    <h3 style="margin-top:18px">按成本分情况</h3>
    <div class="rule"><div class="k">成本 &gt;1500</div><div class="v">浮亏 23%+：不补仓；反弹到 1400-1500 先减 1/4，剩余按计划。</div></div>
    <div class="rule"><div class="k">成本 1100–1300</div><div class="v">浮亏 0-10%：持有，按上面的点位计划执行。</div></div>
    <div class="rule"><div class="k">成本 &lt;1000</div><div class="v">有浮盈：持有；跌破 1100 止盈 1/3，跌破 1000 再止盈 1/3。</div></div>
    <div class="note">以上是仓位管理框架，不构成个性化投资建议；你的风险承受能力、其他持仓和现金流不同，比例要相应调整。</div>
  </div>
</div>
</div>

<div class="section">
<h2>7. 什么会改变观点</h2>
<div class="grid2">
  <div class="panel"><h3 style="margin-top:0" class="green">转多信号</h3><ul>
    <li>Q3 剩余 14 家（权重 29.7%）披露后，全样本净利增速仍 ≥40%，且半导体设备/算力链没有下修。</li>
    <li>Q4 单季净利环比转正（≥0），且营收环比 &gt;0；连续两个季度不再恶化，才算拐点确认。</li>
    <li>指数收盘站上 MA20（当前 1371）并 3 个交易日不破，同时 PE 回到 60x 以上（说明是盈利驱动，不是纯情绪）。</li>
    <li>PE 回落到 45x 以下，或价格到 950 以下且盈利预期不再下修——赔率明显改善。</li>
  </ul></div>
  <div class="panel"><h3 style="margin-top:0" class="red">转空信号</h3><ul>
    <li>AI 资本开支/订单被下修，2027 年半导体盈利预期集体下调；Q4 指引低于预期。</li>
    <li>Q4 净利环比继续为负（尤其半导体设备/存储），毛利率同步下修——从“杀估值”转向“杀盈利”。</li>
    <li>指数跌破 1000，且亏损股数量增加、成交额萎缩——从“杀估值”转向“杀盈利”。</li>
    <li>解禁/IPO 供给超预期，或 ETF 出现持续大额赎回，流动性负反馈。</li>
  </ul></div>
</div>
<div class="quote"><b>下一个检查点：</b>10/31 三季报最后一批（中芯国际、源杰科技、华虹宏力、华海清科等，合计权重约 19.8%）；以及 2027 年 4 月的年报/一季报。前者决定“Q3 成绩单”是否完整，后者决定“2027 年增速”是否接得上。</div>
</div>

<div class="section">
<h2>8. 全部 50 只成分股</h2>
<p class="lead">按权重排序；可搜索、筛选、点击表头排序（表格可滚动）。PE 为负/亏损的标“亏损”；增速为“—”表示无可比数据；期=H1 表示三季报未披露，增速用半年报。</p>
<div class="toolbar">
  <input class="search" id="q" placeholder="搜索代码 / 名称">
  <button class="btn on" data-f="all">全部</button>
  <button class="btn" data-f="profit">盈利</button>
  <button class="btn" data-f="loss">亏损</button>
  <button class="btn" data-f="high">高增长 ≥50%</button>
  <button class="btn" data-f="qoqdown">环比下降</button>
  <button class="btn" data-f="expensive">PE ≥100x</button>
  <button class="btn" data-f="cheap">PE &lt;30x</button>
  <span class="mini" id="cnt" style="margin-left:auto"></span>
</div>
<div class="tablewrap full">
<table id="stockTable">
<thead><tr>
<th data-k="name">成分股</th><th data-k="weight">权重</th><th data-k="industry">行业</th>
<th data-k="price">收盘</th><th data-k="chg">今日</th><th data-k="mcap">市值(亿)</th>
<th data-k="pe">PE-TTM</th><th data-k="pb">PB</th><th data-k="growth">Q3累计净利同比</th>
<th data-k="qoq">单季净利环比</th><th data-k="rev">Q3累计营收同比</th><th data-k="qoq_rev">单季营收环比</th>
<th data-k="single">单季净利同比</th><th data-k="period">期</th>
</tr></thead>
<tbody></tbody>
</table>
</div>
<div class="note">市值=总市值（亿元）；PE=总市值/TTM归母净利，亏损股不显示 PE；同比/环比均为单季，仅在有正的可比基数时计算。数据：东方财富（2026-10-30 收盘），权重：中证指数（2026-09-30）。</div>
</div>

<div class="section">
<h2>9. 方法与数据说明</h2>
<div class="panel">
<ul>
<li><b>成分与权重：</b>中证指数官网 000688 成分券与权重，权重日期 2026-09-30。</li>
<li><b>价格与估值：</b>东方财富 2026-10-30 收盘快照；指数收盘/PE 来自中证指数官网与新浪财经。官方估值文件 10/29 整体法 PE 80.82x，按 10/30 指数涨跌估算为 76.4x；用于历史分位的官网接口 PE 序列 10/29 为 58.41x，按涨跌估算 55.2x。</li>
<li><b>Q3 财报：</b>东方财富业绩报表（RPT_LICO_FN_CPD），截至 2026-10-30 16:30；36/50 已披露，覆盖权重 70.3%。未披露公司用 2026 半年报，表内标“H1”。</li>
<li><b>环比口径：</b>单季 = 累计差（Q3 = 9M − H1；Q2 = H1 − Q1）；环比 = 2026Q3 / 2026Q2 − 1，同比 = 2026Q3 / 2025Q3 − 1。只统计正基数，未年化、未季调；环比受季节性影响，不单独作为买卖依据。</li>
<li><b>口径差异：</b>自下而上按总市值/TTM 归母净利合计，整体法约 89x、剔除亏损约 56x；官方整体法 76x 更低，差异来自股本/样本口径与 Q3 覆盖。页面正文以官方口径 76x 与官网 PE 序列 55x 为主，表格用自下而上个股 PE。</li>
<li><b>指数 TTM EPS：</b>用“指数收盘 ÷ 官网 PE”反推，仅用于观察方向，不是官方 EPS。它同比约 +13%，与成分股 Q3 合计 +49% 的差异，来自权重、亏损股、季度 vs TTM、以及成分调整。</li>
<li><b>历史分位：</b>2020-07-22 至 2026-10-29，官网接口 PE 序列；当前值为估算。分位仅代表估值在自身历史中的位置，不代表未来收益。</li>
<li><b>情景概率：</b>主观设定，用于组织讨论，不是统计模型输出；不构成投资建议。</li>
</ul>
</div>
<div class="footer">© 2026 个人金融探索 · 科创50 2026Q3 体检 · 生成于 2026-10-30 · 数据来源：中证指数 / 东方财富 / 新浪财经 · 投资有风险，决策需独立。</div>
</div>
</div>

<script>
const DATA = __DATA__;
const C = {red:'#c0392b', green:'#1f7a5c', amber:'#b7791f', blue:'#2f5f8f', ink:'#18222e', muted:'#7b8796', line:'#e5e8ec'};
const fmt = (v,d=1)=> v==null?'—':(v>0?'+':'')+Number(v).toFixed(d)+'%';

/* main chart */
(function(){
  const el=document.getElementById('cMain'); if(!el) return;
  const ch=echarts.init(el);
  const h=DATA.history;
  const dates=h.map(x=>x.date), close=h.map(x=>x.close), pe=h.map(x=>x.pe);
  const ma20=h.map(x=>x.ma20), ma60=h.map(x=>x.ma60);
  ch.setOption({
    animationDuration:700,
    grid:{left:52,right:58,top:36,bottom:52},
    legend:{top:4,left:0,textStyle:{color:C.muted,fontSize:11},itemWidth:14,itemHeight:2},
    tooltip:{trigger:'axis',backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},
      formatter:p=>{const i=p[0].dataIndex;return `<b>${dates[i]}</b><br>收盘 ${close[i]}<br>PE ${pe[i]==null?'—':pe[i]+'x'}`;}},
    xAxis:{type:'category',data:dates,boundaryGap:false,axisLine:{lineStyle:{color:'#cfd4da'}},axisLabel:{color:C.muted,fontSize:10,formatter:v=>v.slice(0,7)},axisTick:{show:false}},
    yAxis:[
      {type:'value',scale:true,name:'指数',nameTextStyle:{color:C.muted,fontSize:11},axisLabel:{color:C.muted,fontSize:10},splitLine:{lineStyle:{color:'#eef0f3'}}},
      {type:'value',scale:true,name:'PE',nameTextStyle:{color:C.muted,fontSize:11},axisLabel:{color:C.muted,fontSize:10,formatter:'{value}x'},splitLine:{show:false}}
    ],
    dataZoom:[{type:'inside',start:0,end:100},{type:'slider',height:16,bottom:10,borderColor:'transparent',fillerColor:'rgba(47,95,143,.12)',handleStyle:{color:'#2f5f8f'},textStyle:{color:C.muted,fontSize:10}}],
    series:[
      {name:'科创50',type:'line',data:close,symbol:'none',lineStyle:{width:2,color:C.ink},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(24,34,46,.16)'},{offset:1,color:'rgba(24,34,46,0)'}])},
        markPoint:{symbolSize:9,label:{fontSize:10,color:C.ink,backgroundColor:'rgba(255,255,255,.9)',padding:[2,4],borderRadius:3},data:[
          {name:'2026高点',coord:['2026-06-30',2207.86],value:'2208'},
          {name:'现在',coord:['2026-10-30',1160.84],value:'1161',itemStyle:{color:C.red}},
          {name:'2024底',coord:['2024-02-02',673.41],value:'673',itemStyle:{color:C.green}},
          {name:'2022底',coord:['2022-04-26',868.07],value:'868',itemStyle:{color:C.green}}
        ]}},
      {name:'MA20',type:'line',data:ma20,symbol:'none',lineStyle:{width:1,color:'#9aa6b2',type:'dashed'}},
      {name:'MA60',type:'line',data:ma60,symbol:'none',lineStyle:{width:1,color:'#c2a36b',type:'dotted'}},
      {name:'PE',type:'line',yAxisIndex:1,data:pe,symbol:'none',lineStyle:{width:1.6,color:C.red,opacity:.9}}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* drawdown */
(function(){
  const el=document.getElementById('cDD'); if(!el) return;
  const ch=echarts.init(el); const h=DATA.history;
  ch.setOption({
    grid:{left:48,right:20,top:14,bottom:26},
    tooltip:{trigger:'axis',backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},formatter:p=>`${p[0].axisValue}<br>回撤 ${p[0].data}%`},
    xAxis:{type:'category',data:h.map(x=>x.date),boundaryGap:false,axisLine:{lineStyle:{color:'#cfd4da'}},axisLabel:{color:C.muted,fontSize:9,formatter:v=>v.slice(0,7)},axisTick:{show:false}},
    yAxis:{type:'value',max:0,min:-70,axisLabel:{color:C.muted,fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#eef0f3'}}},
    series:[{type:'line',data:h.map(x=>x.dd),symbol:'none',lineStyle:{width:1.4,color:C.red},areaStyle:{color:'rgba(192,57,43,.14)'},
      markLine:{silent:true,symbol:'none',lineStyle:{color:'#c9a227',type:'dashed'},label:{position:'insideStartTop',color:'#8a6d1d',fontSize:10,formatter:'历史最大 -62.7%'},data:[{yAxis:-62.7}]}
    }]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* industry */
(function(){
  const el=document.getElementById('cInd'); if(!el) return;
  const ch=echarts.init(el); const a=DATA.industries.slice().reverse();
  ch.setOption({
    grid:{left:118,right:64,top:10,bottom:26},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},
      formatter:p=>{const i=a[p[0].dataIndex];return `<b>${i.name}</b><br>总权重 ${i.weight.toFixed(1)}%｜共 ${i.n} 家，已披露 ${i.disc} 家<br>Q3净利合计 ${i.raw>0?'+':''}${i.raw.toFixed(1)}%`;}},
    xAxis:{type:'value',axisLabel:{color:C.muted,fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#eef0f3'}}},
    yAxis:{type:'category',data:a.map(x=>`${x.name} ${x.weight.toFixed(1)}%`),axisLabel:{color:C.ink,fontSize:10.5},axisLine:{show:false},axisTick:{show:false}},
    series:[{type:'bar',data:a.map(x=>({value:x.growth,itemStyle:{color:x.growth>=0?'#c0392b':'#3d8b72',borderRadius:[0,4,4,0]}})),barWidth:15,
      label:{show:true,position:'right',color:C.ink,fontSize:10,formatter:p=>{const z=a[p.dataIndex];return z.raw<-100?'亏损扩大':(z.raw>0?'+':'')+z.raw.toFixed(0)+'%';}}
    }]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* PE bucket donut */
(function(){
  const el=document.getElementById('cPE'); if(!el) return;
  const ch=echarts.init(el);
  const colors={'<30x':'#2e8b6d','30-60x':'#7fb08b','60-100x':'#e0a34a','>100x':'#c0392b','亏损':'#8d99a6'};
  ch.setOption({
    tooltip:{trigger:'item',backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},formatter:p=>`${p.name}<br>权重 ${p.value}%｜${p.data.n} 只`},
    legend:{bottom:0,left:'center',icon:'circle',itemWidth:8,itemHeight:8,textStyle:{color:C.muted,fontSize:11}},
    series:[{type:'pie',radius:['42%','66%'],center:['50%','44%'],avoidLabelOverlap:true,
      label:{formatter:p=>`${p.name}\n${p.value}%`,color:C.ink,fontSize:11,lineHeight:16},
      labelLine:{length:8,length2:8},
      data:DATA.buckets.map(x=>({name:x.name,value:x.weight,n:x.n,itemStyle:{color:colors[x.name]}}))
    }]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* scatter */
(function(){
  const el=document.getElementById('cScatter'); if(!el) return;
  const ch=echarts.init(el);
  const pts=DATA.stocks.filter(s=>!s.loss && s.pe!=null && s.pe<=500 && s.growth!=null && s.growth>=-100 && s.growth<=300);
  ch.setOption({
    grid:{left:48,right:20,top:16,bottom:42},
    tooltip:{backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},
      formatter:p=>{const s=p.data.s;return `<b>${s.name} ${s.code}</b><br>PE ${s.pe}x｜Q3净利 ${fmt(s.growth)}<br>权重 ${s.weight}%｜${s.industry}`;}},
    xAxis:{type:'value',min:-100,max:300,name:'Q3净利同比',nameLocation:'middle',nameGap:26,nameTextStyle:{color:C.muted,fontSize:10},axisLabel:{color:C.muted,fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#eef0f3'}}},
    yAxis:{type:'log',min:10,max:500,name:'PE',nameTextStyle:{color:C.muted,fontSize:10},axisLabel:{color:C.muted,fontSize:10,formatter:'{value}x'},splitLine:{lineStyle:{color:'#eef0f3'}}},
    series:[{type:'scatter',data:pts.map(s=>({value:[s.growth,s.pe],s:s,symbolSize:Math.max(8,Math.sqrt(s.weight)*4.2),
      itemStyle:{color:s.growth>=50&&s.pe<60?'#2e8b6d':(s.pe>=100?'#c0392b':'#b7791f'),opacity:.82,borderColor:'#fff',borderWidth:.6}})),
      markLine:{silent:true,symbol:'none',lineStyle:{color:'#b9c0c8',type:'dashed',width:1},label:{color:C.muted,fontSize:9},data:[{xAxis:30},{yAxis:60}]},
      label:{show:true,position:'top',color:C.ink,fontSize:10,formatter:p=>{const s=p.data.s; return (s.weight>=3||s.name==='佰维存储')?s.name:'';}}
    }]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* QoQ: single-quarter YoY vs QoQ */
(function(){
  const el=document.getElementById('cQoQ'); if(!el) return;
  const ch=echarts.init(el); const a=DATA.q3.qoq_chart.slice().reverse();
  ch.setOption({
    grid:{left:118,right:62,top:34,bottom:38},
    legend:{top:0,right:0,itemWidth:10,itemHeight:8,textStyle:{color:C.muted,fontSize:10}},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'rgba(24,34,46,.94)',borderWidth:0,textStyle:{color:'#fff',fontSize:12},
      formatter:p=>{const z=a[p[0].dataIndex];return `<b>${z.name}</b><br>权重 ${z.weight.toFixed(1)}%<br>单季净利同比 ${fmt(z.single)}<br>Q3净利环比 ${fmt(z.qoq)}<br>Q3营收环比 ${fmt(z.qoq_rev)}`;}},
    xAxis:{type:'value',min:-100,max:200,axisLabel:{color:C.muted,fontSize:10,formatter:'{value}%'},splitLine:{lineStyle:{color:'#eef0f3'}}},
    yAxis:{type:'category',data:a.map(x=>`${x.name} ${x.weight.toFixed(1)}%`),axisLabel:{color:C.ink,fontSize:10.5},axisLine:{show:false},axisTick:{show:false}},
    series:[
      {name:'单季净利同比',type:'bar',barWidth:8,barGap:'25%',
       data:a.map(x=>({value:Math.max(-100,Math.min(200,x.single))})),
       itemStyle:{color:'#9aa9b8',borderRadius:[0,3,3,0]}},
      {name:'Q3净利环比',type:'bar',barWidth:8,
       data:a.map(x=>{return {value:x.qoq,itemStyle:{color:x.qoq>=0?'#c0392b':'#3d8b72',borderRadius:x.qoq>=0?[0,3,3,0]:[3,0,0,3]},
         label:{show:x.qoq>=0,position:'right',color:'#a93226',fontSize:10,formatter:fmt(x.qoq)}};})}
    ]
  });
  window.addEventListener('resize',()=>ch.resize());
})();

/* table */
(function(){
  const tbody=document.querySelector('#stockTable tbody');
  const cnt=document.getElementById('cnt');
  let sortKey='weight', sortDir=-1, filter='all', query='';
  const fmtPe=s=>s.loss?'亏损':(s.pe==null?'—':s.pe.toFixed(1)+'x');
  const fmtGrowth=v=>v==null?'—':(v>1000?'>+1000%':fmt(v));
  function pass(s){
    if(query && !(s.name.includes(query)||s.code.includes(query))) return false;
    if(filter==='profit') return !s.loss;
    if(filter==='loss') return s.loss;
    if(filter==='high') return s.growth!=null && s.growth>=50;
    if(filter==='qoqdown') return s.qoq!=null && s.qoq<0;
    if(filter==='expensive') return !s.loss && s.pe!=null && s.pe>=100;
    if(filter==='cheap') return !s.loss && s.pe!=null && s.pe<30;
    return true;
  }
  function render(){
    let rows=DATA.stocks.filter(pass).slice();
    rows.sort((a,b)=>{
      let av=a[sortKey], bv=b[sortKey];
      if(av==null) av=-999999; if(bv==null) bv=-999999;
      if(typeof av==='string') return av.localeCompare(bv,'zh')*sortDir;
      return (av-bv)*sortDir;
    });
    tbody.innerHTML=rows.map(s=>{
      const gcls=(s.growth||0)>0?'up':((s.growth||0)<0?'down':'');
      const qcls=s.qoq==null?'':(s.qoq>0?'up':'down');
      const rcls=s.rev==null?'muted':(s.rev>0?'up':'down');
      const qrcls=s.qoq_rev==null?'':(s.qoq_rev>0?'up':'down');
      const scls=(s.single||0)>0?'up':((s.single||0)<0?'down':'');
      const tag=s.loss?'<span class="badge hot">亏损</span>':(s.pe>=100?'<span class="badge hot">&gt;100x</span>':(s.pe<30?'<span class="badge cold">&lt;30x</span>':''));
      return `<tr><td class="nm">${s.name}<span class="badge">${s.code}</span>${tag}</td>
      <td>${s.weight.toFixed(2)}%</td><td style="text-align:left;color:#5b6673">${s.industry}</td>
      <td>${s.price.toFixed(2)}</td><td class="${s.chg>0?'up':'down'}">${s.chg>0?'+':''}${s.chg.toFixed(2)}%</td>
      <td>${s.mcap.toFixed(0)}</td><td>${fmtPe(s)}</td><td>${s.pb==null?'—':s.pb.toFixed(1)}</td>
      <td class="${gcls}">${fmtGrowth(s.growth)}</td><td class="${qcls}">${fmtGrowth(s.qoq)}</td>
      <td class="${rcls}">${fmt(s.rev)}</td><td class="${qrcls}">${fmtGrowth(s.qoq_rev)}</td>
      <td class="${scls}">${fmtGrowth(s.single)}</td><td class="muted">${s.period}</td></tr>`;
    }).join('');
    cnt.textContent=`显示 ${rows.length} / ${DATA.stocks.length} 只`;
  }
  document.querySelectorAll('.btn[data-f]').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('.btn[data-f]').forEach(x=>x.classList.remove('on'));
    b.classList.add('on'); filter=b.dataset.f; render();
  }));
  document.getElementById('q').addEventListener('input',e=>{query=e.target.value.trim();render();});
  document.querySelectorAll('#stockTable th').forEach(th=>th.addEventListener('click',()=>{
    const k=th.dataset.k; if(!k) return;
    if(sortKey===k) sortDir*=-1; else {sortKey=k; sortDir=(k==='name'||k==='industry')?1:-1;}
    render();
  }));
  render();
})();
</script>
</body>
</html>
"""
html = html.replace("__DATA__", buckets_json).replace("__TOP10__", top10_rows)
with open("index.html", "w", encoding="utf-8") as fp:
    fp.write(html)
print("wrote index.html", len(html), "bytes")
print("Q3 coverage", cov_n, round(cov_w,1), "growth", round(q3_growth*100,1), "ex", round(q3_growth_ex*100,1))
print("PE", PE_1030, "pct", pct_2020, pct_2023)
