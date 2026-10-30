#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""存储股复盘报告数据抓取（仅标准库）。

数据源（2026-10-30 实测可用）：
  - 韩股日线 + 外资持股：Naver siseJson（api.finance.naver.com）
  - 韩股当前 PER/PBR/52周高低：Naver 移动端 integration API
  - 美股日线（含指数）：新浪美股 US_MinKService.getDailyK（Yahoo 已 403）
  - A股日线（前复权）：腾讯 web.ifzq.gtimg.cn fqkline
  - 电网设备基金净值/指数：由 fund-025833-review/data 复用（中证官网 + 天天基金）

用法：python3 fetch.py
"""
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}


def http_get(url, referer=None, timeout=25):
    hdrs = dict(UA)
    if referer:
        hdrs["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        cmd = ["curl", "-s", "-L", "--max-time", str(timeout),
               "-H", "User-Agent: " + UA["User-Agent"]]
        if referer:
            cmd += ["-H", "Referer: " + referer]
        cmd.append(url)
        out = subprocess.run(cmd, capture_output=True, text=True)
        if out.returncode != 0 or not out.stdout.strip():
            raise RuntimeError("fetch failed: " + url[:80])
        return out.stdout


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    print("  ✓ %s" % name)


def is_today(path):
    return os.path.isfile(path) and time.strftime("%Y%m%d") == time.strftime(
        "%Y%m%d", time.localtime(os.path.getmtime(path)))


# ---------------------------------------------------------------- 韩股
def naver_daily(code, start="20250101"):
    name = "naver_%s.json" % code
    path = os.path.join(DATA, name)
    if is_today(path):
        print("  = %s (缓存)" % name)
        return json.load(open(path, encoding="utf-8"))
    end = time.strftime("%Y%m%d")
    url = ("https://api.finance.naver.com/siseJson.naver?symbol=%s"
           "&requestType=1&startTime=%s&endTime=%s&timeframe=day" % (code, start, end))
    raw = http_get(url, referer="https://finance.naver.com/")
    rows = re.findall(r'\["(\d{8})", ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+), (\d+), ([\d.]+)\]', raw)
    out = [dict(date=r[0][:4] + "-" + r[0][4:6] + "-" + r[0][6:],
                close=float(r[4]), foreign=float(r[6])) for r in rows]
    if not out:
        raise RuntimeError("naver parse empty: %s" % code)
    save(name, out)
    return out


def naver_index(symbol="KOSPI", start="20250101"):
    name = "naver_index_%s.json" % symbol
    path = os.path.join(DATA, name)
    if is_today(path):
        print("  = %s (缓存)" % name)
        return json.load(open(path, encoding="utf-8"))
    end = time.strftime("%Y%m%d")
    url = ("https://api.finance.naver.com/siseJson.naver?symbol=%s"
           "&requestType=1&startTime=%s&endTime=%s&timeframe=day" % (symbol, start, end))
    raw = http_get(url, referer="https://finance.naver.com/")
    rows = re.findall(r'\["(\d{8})", ([\d.]+), ([\d.]+), ([\d.]+), ([\d.]+), (\d+), ([\d.]+)\]', raw)
    out = [dict(date=r[0][:4] + "-" + r[0][4:6] + "-" + r[0][6:], close=float(r[4])) for r in rows]
    save(name, out)
    return out


def naver_val(code):
    """当前 PER / PBR / 外资持股 / 52 周高低。"""
    name = "naver_val_%s.json" % code
    path = os.path.join(DATA, name)
    if is_today(path):
        print("  = %s (缓存)" % name)
        return json.load(open(path, encoding="utf-8"))
    raw = http_get("https://m.stock.naver.com/api/stock/%s/integration" % code)
    d = json.loads(raw)
    kv = {i["key"]: i["value"] for i in d.get("totalInfos", [])}
    num = lambda k: float(re.sub(r"[^\d.\-]", "", kv.get(k, "") or "0") or 0)
    out = dict(per=num("PER"), pbr=num("PBR"), eps=num("EPS"), bps=num("BPS"),
               foreign=num("외인소진율"), high52=num("52주 최고"), low52=num("52주 최저"),
               mcap=kv.get("시총", ""), per_est=num("추정PER"), div=num("배당수익률"))
    save(name, out)
    return out


# ---------------------------------------------------------------- 美股
def us_daily(sym):
    name = "us_%s.json" % sym.replace(".", "_").replace("^", "")
    path = os.path.join(DATA, name)
    if is_today(path):
        print("  = %s (缓存)" % name)
        return json.load(open(path, encoding="utf-8"))
    url = ("https://stock.finance.sina.com.cn/usstock/api/json_v2.php/"
           "US_MinKService.getDailyK?symbol=%s&type=daily" % urllib.parse.quote(sym))
    raw = http_get(url, referer="https://stock.finance.sina.com.cn")
    arr = json.loads(raw)
    out = [dict(date=x["d"], close=float(x["c"])) for x in arr]
    save(name, out)
    return out


# ---------------------------------------------------------------- A股
def cn_daily(code):
    name = "cn_%s.json" % code
    path = os.path.join(DATA, name)
    if is_today(path):
        print("  = %s (缓存)" % name)
        return json.load(open(path, encoding="utf-8"))
    url = ("https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           "param=%s,day,,,400,qfq" % code)
    raw = http_get(url)
    d = json.loads(raw)["data"][code]
    rows = d.get("qfqday") or d.get("day") or []
    out = [dict(date=r[0], close=float(r[2])) for r in rows]
    save(name, out)
    return out


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
]
CN_CODE = {"603986.SS": "sh603986", "688008.SS": "sh688008", "688525.SS": "sh688525",
           "301308.SZ": "sz301308", "000021.SZ": "sz000021", "300223.SZ": "sz300223",
           "300475.SZ": "sz300475", "sh600487": "sh600487", "sh600522": "sh600522",
           "sh600406": "sh600406", "sh600089": "sh600089", "sz002028": "sz002028",
           "sh000300": "sh000300", "sz399006": "sz399006"}


def main():
    os.makedirs(DATA, exist_ok=True)
    print("韩股：")
    for code in ("005930", "000660"):
        naver_daily(code)
        naver_val(code)
    naver_index("KOSPI")

    print("美股：")
    for sym in ("MU", "SNDK", "STX", "WDC", ".IXIC"):
        us_daily(sym)

    print("A股：")
    for _, sym, g in TICKERS:
        if g == "cn":
            cn_daily(CN_CODE[sym])
    for extra in ("sh600487", "sh600522"):     # 电网基金里的光纤/光缆弹性来源
        try:
            cn_daily(extra)
        except Exception as e:
            print("  ! %s %s" % (extra, str(e)[:50]))

    print("完成，数据落盘 %s" % DATA)


if __name__ == "__main__":
    main()