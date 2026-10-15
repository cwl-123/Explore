#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存储股崩盘专题报告生成器（仅标准库，与 build_site.py 同哲学）

用法：
    python3 build.py          # 抓数（当日缓存）→ 计算 → 生成 index.html
                              # 生成后记得回仓库根目录跑一次 python3 build_site.py（注入导航+登记门户）

数据源：
    - 行情：Yahoo finance chart API（韩股 .KS / 美股 / A股 .SS .SZ），缓存 data/yahoo_<sym>.json
    - 韩股外资持股比例 + PER/PBR：Naver finance，缓存 data/naver_*.txt
    - 抓取失败自动回退旧缓存
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0"}

# (展示名, Yahoo代码, 分组)  分组: kr=韩股 us=美股 cn=A股 idx=指数
TICKERS = [
    ("三星电子", "005930.KS", "kr"),
    ("SK海力士", "000660.KS", "kr"),
    ("美光 MU", "MU", "us"),
    ("闪迪 SNDK", "SNDK", "us"),
    ("希捷 STX", "STX", "us"),
    ("西数 WDC", "WDC", "us"),
    ("兆易创新", "603986.SS", "cn"),
    ("澜起科技", "688008.SS", "cn"),
    ("佰维存储", "688525.SS", "cn"),
    ("江波龙", "301308.SZ", "cn"),
    ("深科技", "000021.SZ", "cn"),
    ("北京君正", "300223.SZ", "cn"),
    ("香农芯创", "300475.SZ", "cn"),
    ("KOSPI", "^KS11", "idx"),
    ("纳斯达克", "^IXIC", "idx"),
]
GROUP_COLOR = {"kr": "#2f6fed", "us": "#e0a300", "cn": "#d94a4a", "idx": "#95a5a6"}
GROUP_LABEL = {"kr": "韩股", "us": "美股", "cn": "A股", "idx": "指数"}


def http_get(url, timeout=25):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        # Naver 对部分网络环境的 python TLS 握手不友好，回退 curl
        import subprocess
        out = subprocess.run(["curl", "-s", "--max-time", str(timeout), url,
                              "-H", "User-Agent: Mozilla/5.0",
                              "-H", "Referer: https://finance.naver.com/"],
                             capture_output=True, text=True)
        if out.returncode != 0 or not out.stdout.strip():
            raise
        return out.stdout


def cache_path(name):
    return os.path.join(DATA, name)


def cache_is_today(path):
    if not os.path.isfile(path):
        return False
    return time.strftime("%Y%m%d") == time.strftime("%Y%m%d", time.localtime(os.path.getmtime(path)))


def fetch_yahoo(sym):
    """返回 [(date_str, close)]，当日缓存优先，抓失败回退旧缓存。"""
    name = "yahoo_%s.json" % sym.replace("^", "")
    path = cache_path(name)
    raw = None
    if not cache_is_today(path):
        try:
            url = ("https://query1.finance.yahoo.com/v8/finance/chart/%s"
                   "?range=10y&interval=1d" % urllib.parse.quote(sym))
            raw = http_get(url)
            with open(path, "w") as f:
                f.write(raw)
            print("  ✓ 抓取 %s" % sym)
        except Exception as e:
            print("  ! 抓取 %s 失败(%s)，回退缓存" % (sym, str(e)[:60]))
    if raw is None:
        if not os.path.isfile(path):
            raise RuntimeError("无数据：%s" % sym)
        raw = open(path).read()
    res = json.loads(raw)["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    out = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        out.append((time.strftime("%Y-%m-%d", time.localtime(t)), round(float(c), 2)))
    return out


def fetch_naver_hist(code):
    """Naver 日线（含外资持股比例），返回 [(date, close, foreign_pct)]"""
    path = cache_path("naver_%s.txt" % code)
    raw = None
    if not cache_is_today(path):
        try:
            url = ("https://api.finance.naver.com/siseJson.naver?symbol=%s"
                   "&requestType=1&startTime=20150101&endTime=%s&timeframe=day"
                   % (code, time.strftime("%Y%m%d")))
            raw = http_get(url)
            with open(path, "w") as f:
                f.write(raw)
            print("  ✓ 抓取 Naver %s" % code)
        except Exception as e:
            print("  ! 抓取 Naver %s 失败(%s)，回退缓存" % (code, str(e)[:60]))
    if raw is None:
        if not os.path.isfile(path):
            return []
        raw = open(path).read()
    rows = re.findall(r'\["(\d{8})", ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+), (\d+), ([\d.]+)\]', raw)
    return [(r[0][:4] + "-" + r[0][4:6] + "-" + r[0][6:], float(r[4]), float(r[6])) for r in rows]


def fetch_naver_val(code):
    """Naver 实时估值 {per, pbr, eps, rate, now}，失败回退缓存。"""
    path = cache_path("naver_val_%s.json" % code)
    raw = None
    if not cache_is_today(path):
        try:
            raw = http_get("https://api.finance.naver.com/service/itemSummary.nhn?itemcode=" + code)
            with open(path, "w") as f:
                f.write(raw)
        except Exception as e:
            print("  ! Naver 估值 %s 失败(%s)" % (code, str(e)[:60]))
    if raw is None and os.path.isfile(path):
        raw = open(path).read()
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# 计算
# ---------------------------------------------------------------------------
def stats(series):
    """series: [(date, close)] -> dict"""
    dates = [d for d, _ in series]
    closes = [c for _, c in series]
    cur = closes[-1]
    peak = max(closes)
    peak_i = closes.index(peak)

    def ret(n):
        return cur / closes[-1 - n] - 1 if len(closes) > n else None

    yr = dates[-1][:4]
    ytd_i = next((i for i, d in enumerate(dates) if d >= yr + "-01-01"), 0)
    return {
        "date": dates[-1], "cur": cur, "today": cur / closes[-2] - 1,
        "peak": peak, "peak_date": dates[peak_i], "dd": cur / peak - 1,
        "r5": ret(5), "r21": ret(21), "r63": ret(63), "r126": ret(126),
        "r1y": cur / closes[max(0, len(closes) - 252)] - 1,
        "ytd": cur / closes[ytd_i] - 1,
        "_dates": dates, "_closes": closes,
    }


def find_episodes(dates, closes, enter=-0.05, exit_=-0.02, min_trough=-0.25):
    """回撤事件：跌破前高-5% 进入，回到前高-2% 视为收复。"""
    eps = []
    peak = closes[0]
    peak_i = 0
    in_ep = False
    start = trough_i = ep_peak_i = 0
    trough = 0.0
    for i, c in enumerate(closes):
        dd = c / peak - 1
        if not in_ep and dd < enter:
            in_ep, start, trough, trough_i = True, i, dd, i
            ep_peak_i = peak_i  # 锁定本事件的顶部（收复日可能创新高，不能事后取）
        elif in_ep:
            if dd < trough:
                trough, trough_i = dd, i
            if dd > exit_:
                in_ep = False
                if trough <= min_trough:
                    eps.append(dict(peak_i=ep_peak_i, trough_i=trough_i, end_i=i,
                                    trough=trough, done=True))
        if c > peak:
            peak, peak_i = c, i
    if in_ep and trough <= min_trough:
        eps.append(dict(peak_i=ep_peak_i, trough_i=trough_i, end_i=len(closes) - 1,
                        trough=trough, done=False))
    for e in eps:
        e.update(peak_date=dates[e["peak_i"]], trough_date=dates[e["trough_i"]],
                 end_date=dates[e["end_i"]] if e["done"] else None)
    return eps


def dd_curve(closes, start_i, n=320):
    peak = closes[start_i]
    out = []
    for j in range(start_i, min(start_i + n, len(closes))):
        out.append([j - start_i, round((closes[j] / peak - 1) * 100, 2)])
    return out


def fmt_pct(v, digits=1):
    return "—" if v is None else "%+.*f%%" % (digits, v * 100)


def cls_pct(v):
    if v is None:
        return ""
    return "good" if v >= 0 else "bad"


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------
def build():
    os.makedirs(DATA, exist_ok=True)
    print("抓取行情：")
    series = {}
    for label, sym, grp in TICKERS:
        pairs = fetch_yahoo(sym)
        series[label] = {"dates": [d for d, _ in pairs], "closes": [c for _, c in pairs]}
        time.sleep(0.2)
    st = {label: stats(list(zip(v["dates"], v["closes"]))) for label, v in series.items()}

    print("抓取 Naver（外资持股 / 估值）：")
    foreign = {}
    for label, code in [("三星电子", "005930"), ("SK海力士", "000660")]:
        rows = fetch_naver_hist(code)
        foreign[label] = rows[-90:]
    val_ss, val_hy = fetch_naver_val("005930"), fetch_naver_val("000660")

    # ---- 图表数据 ----
    # c1 距峰回撤条形图
    bars = []
    for label, sym, grp in TICKERS:
        if grp == "idx":
            continue
        bars.append({"name": label, "dd": round(st[label]["dd"] * 100, 1),
                     "grp": GROUP_LABEL[grp], "color": GROUP_COLOR[grp]})
    bars.sort(key=lambda x: x["dd"])

    # c2 近一年归一走势（log）
    trend_labels = ["三星电子", "SK海力士", "美光 MU", "闪迪 SNDK", "兆易创新", "KOSPI", "纳斯达克"]
    n1y = 252
    base = series["三星电子"]["dates"][-n1y]
    trend_dates = series["三星电子"]["dates"][-n1y:]
    trend = {}
    for lb in trend_labels:
        ds, cs = series[lb]["dates"], series[lb]["closes"]
        i0 = next(i for i, d in enumerate(ds) if d >= base)
        sub_d, sub_c = ds[i0:], cs[i0:]
        b = sub_c[0]
        trend[lb] = {"dates": sub_d, "vals": [round(c / b * 100, 1) for c in sub_c]}

    # c3 近60交易日崩盘节奏（6月峰值=100）+ 外资持股
    recent_labels = ["三星电子", "SK海力士", "美光 MU", "闪迪 SNDK", "兆易创新"]
    recent = {}
    for lb in recent_labels:
        ds, cs = series[lb]["dates"], series[lb]["closes"]
        peak_i = cs.index(max(cs))
        sub_d, sub_c = ds[-60:], cs[-60:]
        b = cs[peak_i]
        recent[lb] = {"dates": sub_d, "vals": [round(c / b * 100, 1) for c in sub_c]}
    recent_dates = series["三星电子"]["dates"][-60:]
    fo = {}
    for lb, rows in foreign.items():
        m = dict((r[0], r[2]) for r in rows)
        fo[lb] = [m.get(d) for d in recent_dates]

    # c4 十年回撤曲线（周采样）
    dd10y = {}
    for lb in ["三星电子", "SK海力士", "美光 MU"]:
        ds, cs = series[lb]["dates"], series[lb]["closes"]
        peak, out = cs[0], []
        for i, c in enumerate(cs):
            peak = max(peak, c)
            if i % 5 == 0:
                out.append([ds[i], round((c / peak - 1) * 100, 1)])
        dd10y[lb] = out

    # c5 周期对齐（距峰值交易日数 vs 回撤%）
    aligned = []
    ep_all = {}
    palette = {"三星电子": "#2f6fed", "SK海力士": "#8e44ad", "美光 MU": "#e67e22"}
    for lb in ["三星电子", "SK海力士", "美光 MU"]:
        ds, cs = series[lb]["dates"], series[lb]["closes"]
        eps = find_episodes(ds, cs, min_trough=-0.30)
        ep_all[lb] = eps
        for e in eps:
            tag = "%s %s顶" % (lb, e["peak_date"][:7])
            aligned.append({
                "name": tag + ("（进行中）" if not e["done"] else "（%+.0f%%）" % (e["trough"] * 100)),
                "color": palette[lb], "cur": not e["done"],
                "pts": dd_curve(cs, e["peak_i"]),
            })

    # ---- 表格 ----
    def row_overview(label, sym, grp):
        s = st[label]
        cells = ["<td><span style='color:%s'>●</span> %s <span class='muted'>%s</span></td>"
                 % (GROUP_COLOR[grp], label, sym),
                 "<td>%s</td>" % s["date"],
                 "<td class='%s'>%s</td>" % (cls_pct(s["today"]), fmt_pct(s["today"])),
                 "<td>%s (%s)</td>" % ("{:,.0f}".format(s["peak"]), s["peak_date"][:7]),
                 "<td class='%s'><b>%s</b></td>" % (cls_pct(s["dd"]), fmt_pct(s["dd"]))]
        for key in ["r5", "r21", "r63"]:
            cells.append("<td class='%s'>%s</td>" % (cls_pct(s[key]), fmt_pct(s[key])))
        for key in ["r1y", "ytd"]:
            cells.append("<td class='%s'>%s</td>" % (cls_pct(s[key]), fmt_pct(s[key], 0)))
        hot = ' style="background:#fdf0ef"' if s["dd"] <= -0.40 else ""
        return "<tr%s>%s</tr>" % (hot, "".join(cells))

    tbl_overview = "".join(row_overview(l, s, g) for l, s, g in TICKERS)

    def row_ep(lb, e):
        rec = ("%s（%d 天）" % (e["end_date"],
               (time.mktime(time.strptime(e["end_date"], "%Y-%m-%d")) -
                time.mktime(time.strptime(e["peak_date"], "%Y-%m-%d"))) / 86400)) if e["done"] else \
              "<b style='color:#e67e22'>进行中（已 %d 天）</b>" % (
                  (time.mktime(time.strptime(st[lb]["date"], "%Y-%m-%d")) -
                   time.mktime(time.strptime(e["peak_date"], "%Y-%m-%d"))) / 86400)
        return ("<tr><td>%s</td><td>%s → %s</td><td class='bad'><b>%+.0f%%</b></td><td>%s</td></tr>") % (
            lb, e["peak_date"], e["trough_date"], e["trough"] * 100, rec)

    tbl_ep = ""
    for lb in ["三星电子", "SK海力士", "美光 MU"]:
        for e in ep_all[lb]:
            tbl_ep += row_ep(lb, e)

    def val_cell(v, suffix=""):
        return "—" if v in (None, "") else "%s%s" % (v, suffix)

    tbl_val = (
        "<tr><td>三星电子</td><td>%s</td><td>%s</td><td>%s</td><td>约 1.0 ~ 1.5</td><td class='bad'><b>仍高于历史底部区</b></td></tr>"
        "<tr><td>SK海力士</td><td>%s</td><td>%s</td><td>%s</td><td>约 1.0 ~ 1.8</td><td class='bad'><b>仍高于历史底部区</b></td></tr>"
    ) % (
        val_cell(val_ss.get("per")), val_cell(val_ss.get("pbr")), "{:,.0f}".format(val_ss["eps"]) if val_ss.get("eps") else "—",
        val_cell(val_hy.get("per")), val_cell(val_hy.get("pbr")), "{:,.0f}".format(val_hy["eps"]) if val_hy.get("eps") else "—",
    )

    ss, hy = st["三星电子"], st["SK海力士"]
    kpi = {
        "ss_dd": fmt_pct(ss["dd"], 0), "ss_today": fmt_pct(ss["today"]),
        "ss_5d": fmt_pct(ss["r5"]), "ss_peak": "{:,.0f}".format(ss["peak"]),
        "hy_dd": fmt_pct(hy["dd"], 0), "hy_today": fmt_pct(hy["today"]),
        "hy_5d": fmt_pct(hy["r5"]), "hy_peak": "{:,.0f}".format(hy["peak"]),
        "ndx_dd": fmt_pct(st["纳斯达克"]["dd"]),
        "mu_1y": fmt_pct(st["美光 MU"]["r1y"], 0),
        "ss_per": val_cell(val_ss.get("per")), "ss_pbr": val_cell(val_ss.get("pbr")),
        "hy_per": val_cell(val_hy.get("per")), "hy_pbr": val_cell(val_hy.get("pbr")),
        "date": ss["date"],
        "fo_ss": "%.2f%% → %.2f%%" % (foreign["三星电子"][0][2], foreign["三星电子"][-1][2]),
        "fo_hy": "%.2f%% → %.2f%%" % (foreign["SK海力士"][0][2], foreign["SK海力士"][-1][2]),
    }

    data = {"bars": bars, "trend": trend, "trendDates": trend_dates,
            "recent": recent, "recentDates": recent_dates, "foreign": fo,
            "dd10y": dd10y, "aligned": aligned,
            "colors": {"三星电子": "#2f6fed", "SK海力士": "#8e44ad", "美光 MU": "#e67e22",
                       "闪迪 SNDK": "#16a085", "兆易创新": "#d94a4a",
                       "KOSPI": "#7f8c8d", "纳斯达克": "#2c3e50"}}

    html = TEMPLATE
    for k, v in kpi.items():
        html = html.replace("__%s__" % k.upper(), str(v))
    html = html.replace("__TBL_OVERVIEW__", tbl_overview)
    html = html.replace("__TBL_EPISODES__", tbl_ep)
    html = html.replace("__TBL_VAL__", tbl_val)
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out = os.path.join(HERE, "index.html")
    with open(out, "w") as f:
        f.write(html)
    print("\n已生成：%s" % out)


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>存储股崩盘：三星/海力士还值得投资吗？</title>
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<style>
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;max-width:1080px;margin:0 auto;padding:24px;color:#222;line-height:1.75}
h1{font-size:26px}h2{font-size:20px;margin-top:48px;border-left:4px solid #2f6fed;padding-left:10px}
.chart{width:100%;height:420px;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:12px 0}
th,td{border:1px solid #ddd;padding:5px 8px;text-align:right;vertical-align:top}
th:first-child,td:first-child{text-align:left}
th{background:#f6f6f6}
.good{color:#c0392b}.bad{color:#27ae60}
.box{background:#eef3fd;border:1px solid #c9d7f5;border-radius:8px;padding:16px 20px;margin:16px 0}
.warn{background:#fdf0ef;border:1px solid #eec5c0}
.muted{color:#888;font-size:12.5px}
ul{padding-left:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0}
.card{flex:1;min-width:230px;border-radius:8px;padding:14px 16px;border:1px solid #e0e0e0;background:#fff}
.card .num{font-size:21px;font-weight:700;margin:4px 0}
.card .lbl{font-size:13px;color:#666}
.card.hot{background:#fdf0ef;border-color:#eec5c0}
.card.cold{background:#eef7f0;border-color:#bfe3cb}
.scroll{overflow-x:auto}
</style>
</head>
<body>
<h1>存储股崩盘：三星 / 海力士还值得投资吗？——与美股、A股存储链对比，用 10 年周期数据回答</h1>
<p class="muted">生成时间：__DATE__（韩股/A股为当日行情，美股为前一交易日收盘）｜ 行情：Yahoo Finance（日线，10 年）｜ 外资持股 / PER / PBR：Naver Finance ｜ 口径见文末</p>

<div class="box warn">
<b>一句话结论：</b>这不是普通回调，而是 <b>2026-06 下旬全板块同步见顶后的泡沫破裂</b>：三星距峰值 <b>__SS_DD__</b>（今日 __SS_TODAY__）、海力士 <b>__HY_DD__</b>（今日 __HY_TODAY__）、A股存储链最深 -70%，而纳斯达克仅 __NDX_DD__ —— 纯板块性崩盘。历史规律：过去 10 年存储股<b>同级别回撤（≥30%）全部对应周期顶</b>，其后是 1~3 年盈利下行、2~4.7 年才收复前高；只有需求没坏的短调（2020、2024）才在 9~15 个月内 V 回。当前下跌仍在<b>恐慌加速段</b>（近 5 日三星 __SS_5D__、海力士 __HY_5D__，外资持续流出），<b>长趋势开始的概率远大于短期回调，现在不接飞刀</b>；想长线布局 AI 存储，等缩量止跌 + 存储合约价企稳，三星 PBR 回到 1.5 以下、海力士 2 以下才有历史级安全边际。
</div>

<h2>0. 信号速览</h2>
<div class="cards">
<div class="card hot"><div class="lbl">① 三星电子 · 距 6 月峰值（₩__SS_PEAK__）</div>
<div class="num bad">__SS_DD__（今日 __SS_TODAY__）</div>
<div class="lbl">近 5 日 __SS_5D__，恐慌加速段；外资持股 90 日 __FO_SS__ 持续流出</div></div>
<div class="card hot"><div class="lbl">② SK海力士 · 距 6 月峰值（₩__HY_PEAK__）</div>
<div class="num bad">__HY_DD__（今日 __HY_TODAY__）</div>
<div class="lbl">近 5 日 __HY_5D__；外资持股 90 日 __FO_HY__。幅度已达历史「周期顶级别」</div></div>
<div class="card hot"><div class="lbl">③ 板块性 vs 系统性</div>
<div class="num bad">纳指仅 __NDX_DD__</div>
<div class="lbl">大盘几乎没跌、存储股跌 25~70% —— <b>行业周期反转</b>而非宏观危机</div></div>
<div class="card cold"><div class="lbl">④ 估值（Naver，当日）</div>
<div class="num">三星 PBR __SS_PBR__ ｜ 海力士 PBR __HY_PBR__</div>
<div class="lbl">PER __SS_PER__ / __HY_PER__ 看着便宜，但那是<b>峰值利润</b>；PBR 仍在历史底部区之上</div></div>
</div>

<h2>1. 现在处于什么位置？</h2>
<div class="scroll">
<table>
<tr><th>标的</th><th>数据日</th><th>今日</th><th>10年峰值（日期）</th><th>距峰回撤</th><th>近5日</th><th>近1月</th><th>近3月</th><th>近1年</th><th>YTD</th></tr>
__TBL_OVERVIEW__
</table>
</div>
<p class="muted">红底 = 距峰回撤 ≥40%。排序按页面表格默认（韩股 → 美股 → A股 → 指数）。近1年涨幅越大的标的，本轮跌得越狠——典型的「涨多少、还多少」。</p>
<div id="c1" class="chart" style="height:460px"></div>
<div id="c2" class="chart" style="height:480px"></div>
<p class="muted">上：距 10 年峰值回撤（按市场着色）。下：近一年归一走势（=100，对数轴）——闪迪一年 10 倍、海力士 3 倍，然后 3 个半月集体腰斩。</p>

<h2>2. 崩盘节奏：还在加速，没有企稳信号</h2>
<div id="c3" class="chart" style="height:440px"></div>
<div id="c3b" class="chart" style="height:300px"></div>
<p class="muted">上：近 60 个交易日走势（6 月峰值=100）——10 月以来近乎垂直下杀。下：三星/海力士外资持股比例（近 90 日），外资在持续卖出而非抄底。</p>
<div class="box">
<b>底部形态判断：</b>历史上存储股的底通常要「缩量 + 横盘数周 + 合约价企稳」三件套。当前是放量单边下杀（三星 10-15 成交 2,863 万股，为平日 1.5~2 倍）、外资持股逐日下降、近 5 日再跌 2 成以上——<b>三个特征全部相反</b>，属于恐慌加速段，左侧接刀风险极高。
</div>

<h2>3. 韩股 vs 美股 vs A股：基本面梯队决定回撤深度</h2>
<table>
<tr><th>梯队</th><th>标的</th><th>产业链位置</th><th>本轮回撤</th><th>点评</th></tr>
<tr><td><b>上游寡头（韩/美）</b></td><td>三星、海力士、美光</td><td>DRAM/NAND/HBM 制造，全球份额 &gt;90%</td><td>-25% ~ -57%</td><td>有真实利润与 HBM 壁垒；跌的是「峰值利润不可持续」的预期</td></tr>
<tr><td><b>中游品牌（美）</b></td><td>闪迪、西数、希捷</td><td>NAND 模组 / HDD</td><td>-35% ~ -51%</td><td>闪迪一年 +10 倍最妖，弹性大；HDD（希捷）受益 AI 冷数据、跌幅相对浅</td></tr>
<tr><td><b>利基设计 / 模组（A股）</b></td><td>兆易、澜起、佰维、江波龙、深科技、君正、香农</td><td>利基存储设计、接口芯片、模组与分销</td><td class="bad"><b>-49% ~ -70%</b></td><td>离上游最远、利润最薄、投机溢价最高——一年才涨 36%（兆易），三个月跌掉 55%</td></tr>
</table>
<p><b>结论：</b>回撤深度与基本面成反比。若要布局存储长线，优先级 = 寡头（海力士 HBM 弹性最大、三星最稳）&gt; 美光 &gt; 中游品牌 &gt; A股链。A股存储本轮是「跟跌不跟涨」的最弱一环（近1年涨幅最小、距峰回撤最深）。</p>

<h2>4. 估值：低 PER 是周期股的陷阱</h2>
<table>
<tr><th>标的</th><th>PER（TTM）</th><th>PBR</th><th>EPS</th><th>历史底部 PBR 区间*</th><th>判断</th></tr>
__TBL_VAL__
</table>
<p class="muted">* 历史底部区间为 2016 / 2019 / 2023 周期谷值附近的近似值，仅作量级参考。</p>
<div class="box">
<b>为什么 PER 5.6 倍不是买入理由：</b>存储是强周期行业，<b>周期顶时 E（利润）最大、PER 最低；周期底时 E 亏损、PER 反而无穷大</b>。2018 顶时海力士 PER 也只有 3~4 倍，随后利润腰斩再腰斩、股价 -49%。当前 EPS（三星 ₩22,292 / 海力士 ₩224,313）是 HBM 超级周期的峰值利润，若 2027 年存储价进入下行周期，E 可能缩水 50%+，「9 倍三星」会瞬间变「20 倍三星」。看存储股估值要用 <b>PBR × 历史区间</b>：三星 2.44、海力士 3.43，都还在历史底部区（1.0~1.8）之上。
</div>

<h2>5. 历史验证：同级别回撤之后发生了什么</h2>
<div id="c4" class="chart" style="height:440px"></div>
<p class="muted">10 年回撤曲线（周采样）。存储股的回撤不是「偶发」而是「节律」：约每 3~4 年一轮，深 30~60%。</p>
<div class="scroll">
<table>
<tr><th>标的</th><th>顶 → 底</th><th>最深回撤</th><th>收复前高</th></tr>
__TBL_EPISODES__
</table>
</div>
<div id="c5" class="chart" style="height:480px"></div>
<p class="muted">周期对齐图：x = 距峰值交易日数，y = 回撤 %。粗实线 = 本轮（进行中）；虚线 = 历史各轮。</p>
<div class="box">
<b>历史规律（10 年、三大标的、全部 ≥30% 回撤段）：</b>
<ul>
<li><b>短调型</b>（需求没坏：2020 疫情、2024 年中）：跌 30~37%，<b>9~15 个月收复</b>，其后创新高；</li>
<li><b>周期顶型</b>（供给过剩：2018、2021-22）：跌 35~58%，<b>2~4.7 年才收复</b>，期间在谷底横盘 1 年以上；</li>
<li>本轮幅度（三星 -43%、海力士 -57%）<b>已达周期顶级别</b>，但时间才走 3.5 个月——参照历史，这种级别的下跌从不一次性出清，从对齐图看本轮曲线正贴着 2018 / 2021-22 的路径走，而不是 2024 短调的路径。</li>
<li><b>区分两种情形的关键变量</b>：Q4 DRAM/NAND 合约价与 2027 资本开支。若 AI/HBM 需求把价格撑住（E 不崩），本轮更像 2024 式「估值压缩」，明年可收复；若合约价转跌，就是 2018 式周期顶，按年计时间。</li>
</ul>
</div>

<h2>6. 决策框架</h2>
<table>
<tr><th>动作</th><th>逻辑</th><th>触发条件（机械）</th><th>当前状态</th></tr>
<tr><td><b>买入 / 抄底</b></td><td style="text-align:left">赌 AI 存储长逻辑，越跌越买</td><td style="text-align:left">左侧：三星 PBR ≤1.5 或海力士 PBR ≤2.0；右侧：缩量止跌 + 周线站回 10 周线 + Q4 合约价环比转正</td><td class="bad">✗ 均未触发（PBR 2.44 / 3.43；仍在放量加速下跌）</td></tr>
<tr><td><b>持有</b></td><td style="text-align:left">已有仓位、长线信仰</td><td style="text-align:left">历史周期顶型回撤后 2~4.7 年才回前高，需评估机会成本；反弹至 10 周线附近减仓是周期股常规操作</td><td>△ 可持有但降低预期，利用反弹减仓优于死扛</td></tr>
<tr><td><b>卖出 / 回避</b></td><td style="text-align:left">趋势派：破位即离场，不猜底</td><td style="text-align:left">距峰回撤 &gt;30% + 外资持续流出 + 5 日跌 20%+，三信号齐发</td><td class="good"><b>✓ 当前最优：空仓观望，等右侧信号</b></td></tr>
<tr><td><b>换仓</b></td><td style="text-align:left">存储链内部择优</td><td style="text-align:left">若必须持有存储敞口：寡头 &gt; 中游 &gt; A股链；HBM 含量（海力士）与 HDD 冷数据（希捷）是本轮需求最硬的两块</td><td>△ A股存储持仓者可利用反弹向寡头切换</td></tr>
</table>

<h2>7. 口径与免责</h2>
<p class="muted">
· 行情为 Yahoo Finance 日线（近 10 年，未复权口径以 Yahoo qfq 为准）；韩股 / A股为 __DATE__ 当日行情，美股为前一交易日收盘。<br>
· 外资持股比例、PER / PBR / EPS 来自 Naver Finance 当日快照；历史底部 PBR 区间为周期谷值附近的近似读数。<br>
· 「距峰回撤」以近 10 年数据内最高收盘价为基准；周期事件识别规则：收盘跌破前高 -5% 进入事件、回到前高 -2% 视为收复，仅列最深回撤 ≥30% 的事件。<br>
· 新闻源不可达，本页不含本轮下跌的消息面催化剂核实，全部判断基于量价与历史周期数据。<br>
· 本页仅为个人数据研究，不构成投资建议。存储为强周期行业，历史规律不代表未来。
</p>

<script>
const D = __DATA__;
const C = D.colors;
function mk(id){ return echarts.init(document.getElementById(id)); }
const axisTime = {type:'category',axisLabel:{color:'#666'}};

// c1 距峰回撤条形
mk('c1').setOption({
  title:{text:'距 10 年峰值回撤（%，__DATE__）',left:'center',textStyle:{fontSize:15}},
  grid:{left:90,right:60,top:40,bottom:30},
  tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
  xAxis:{type:'value',max:0,axisLabel:{formatter:'{value}%'}},
  yAxis:{type:'category',data:D.bars.map(b=>b.name),inverse:true,axisLabel:{fontSize:12}},
  series:[{type:'bar',data:D.bars.map(b=>({value:b.dd,itemStyle:{color:b.color}})),
    label:{show:true,position:'right',formatter:'{c}%',fontSize:11},barWidth:'62%'}]
});

// c2 近一年归一（log，时间轴，各标的日期可不同）
mk('c2').setOption({
  title:{text:'近一年走势（起点=100，对数轴）',left:'center',textStyle:{fontSize:15}},
  tooltip:{trigger:'axis'},
  legend:{top:26,textStyle:{fontSize:12}},
  grid:{left:60,right:30,top:70,bottom:40},
  xAxis:{type:'time'},
  yAxis:{type:'log',logBase:10},
  series:Object.keys(D.trend).map(k=>({name:k,type:'line',showSymbol:false,
    data:D.trend[k].dates.map((d,i)=>[d,D.trend[k].vals[i]]),
    lineStyle:{width:(k==='纳斯达克'||k==='KOSPI')?1.2:2,type:(k==='纳斯达克'||k==='KOSPI')?'dashed':'solid'},
    itemStyle:{color:C[k]},emphasis:{focus:'series'}}))
});

// c3 近60日（峰值=100）
mk('c3').setOption({
  title:{text:'近 60 个交易日（6 月峰值=100）',left:'center',textStyle:{fontSize:15}},
  tooltip:{trigger:'axis'},
  legend:{top:26},
  grid:{left:55,right:30,top:70,bottom:40},
  xAxis:{type:'category',data:D.recentDates},
  yAxis:{type:'value',scale:true},
  series:Object.keys(D.recent).map(k=>({name:k,type:'line',showSymbol:false,
    data:D.recent[k].vals,lineStyle:{width:2},itemStyle:{color:C[k]}}))
});

// c3b 外资持股
mk('c3b').setOption({
  title:{text:'外资持股比例（近 90 个交易日，%）',left:'center',textStyle:{fontSize:14}},
  tooltip:{trigger:'axis'},
  legend:{top:24},
  grid:{left:55,right:30,top:60,bottom:40},
  xAxis:{type:'category',data:D.recentDates},
  yAxis:{type:'value',scale:true,axisLabel:{formatter:'{value}%'}},
  series:[
    {name:'三星电子',type:'line',showSymbol:false,data:D.foreign['三星电子'],itemStyle:{color:C['三星电子']}},
    {name:'SK海力士',type:'line',showSymbol:false,data:D.foreign['SK海力士'],itemStyle:{color:C['SK海力士']}}
  ]
});

// c4 十年回撤
mk('c4').setOption({
  title:{text:'距历史高点回撤（10 年，周采样，%）',left:'center',textStyle:{fontSize:15}},
  tooltip:{trigger:'axis',valueFormatter:v=>v+'%'},
  legend:{top:26},
  grid:{left:55,right:30,top:70,bottom:40},
  dataZoom:[{type:'inside'}],
  xAxis:{type:'time'},
  yAxis:{type:'value',max:0,axisLabel:{formatter:'{value}%'}},
  series:Object.keys(D.dd10y).map(k=>({name:k,type:'line',showSymbol:false,
    data:D.dd10y[k],lineStyle:{width:1.6},itemStyle:{color:C[k]}}))
});

// c5 周期对齐
mk('c5').setOption({
  title:{text:'历次 ≥30% 回撤的路径对齐（x=距峰值交易日数）',left:'center',textStyle:{fontSize:15}},
  tooltip:{trigger:'axis',valueFormatter:v=>v==null?'':v+'%'},
  legend:{top:26,type:'scroll',textStyle:{fontSize:11}},
  grid:{left:55,right:30,top:80,bottom:40},
  xAxis:{type:'value',name:'交易日',max:320},
  yAxis:{type:'value',max:0,axisLabel:{formatter:'{value}%'}},
  series:D.aligned.map(a=>({name:a.name,type:'line',showSymbol:false,data:a.pts,
    lineStyle:{width:a.cur?3.5:1.4,type:a.cur?'solid':'dashed',color:a.color,opacity:a.cur?1:0.65},
    itemStyle:{color:a.color},emphasis:{focus:'series'}}))
});
window.addEventListener('resize',()=>{document.querySelectorAll('.chart').forEach(e=>{const c=echarts.getInstanceByDom(e);c&&c.resize();});});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    build()
