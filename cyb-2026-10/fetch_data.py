# -*- coding: utf-8 -*-
"""cyb-2026-10 数据抓取：创业板指成分权重 / 三季报 / 估值 / ETF

数据源：
  - 国证指数（cnindex）：成分股与权重、399006 日线
  - 乐咕乐股：399006 PE-TTM / PB / 股息率（月度）
  - 东方财富（akshare stock_yjbb_em）：2026Q3 及历史业绩报表
  - 腾讯行情：个股 PE/PB/市值、ETF 日线
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def get(url, **kw):
    kw.setdefault("headers", {"User-Agent": UA})
    kw.setdefault("timeout", 30)
    r = requests.get(url, **kw)
    r.raise_for_status()
    return r


def fetch_constituents():
    url = "https://www.cnindex.com.cn/sample-detail/detail"
    params = {"indexcode": "399006", "dateStr": "", "pageNum": 1, "rows": 200}
    d = get(url, params=params).json()
    rows = d["data"]["rows"]
    df = pd.DataFrame(rows)[["seccode", "secname", "trade", "weight", "dateStr"]]
    df.columns = ["code", "name", "industry", "weight", "date"]
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df = df.sort_values("weight", ascending=False).reset_index(drop=True)
    df.to_csv(os.path.join(DATA, "constituents.csv"), index=False, encoding="utf-8-sig")
    print("constituents", df.shape, "date", df["date"].iloc[0], "sum weight", round(df["weight"].sum(), 2))
    return df


def fetch_index_history():
    url = "https://hq.cnindex.com.cn/market/market/getIndexDailyData"
    params = {"indexCode": "399006", "startDate": "2010-06-01", "endDate": "2026-10-30"}
    d = get(url, params=params).json()["data"]
    df = pd.DataFrame(d["data"], columns=d["item"])
    df["date"] = pd.to_datetime(df["timestamp"], unit="ms") + pd.Timedelta(hours=8)
    df["date"] = df["date"].dt.normalize()
    df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df.to_csv(os.path.join(DATA, "cyb_index.csv"), index=False)
    print("index", df.shape, df["date"].min().date(), "->", df["date"].max().date(), "close", df["close"].iloc[-1])
    return df


def fetch_legu():
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    page = sess.get("https://legulegu.com/stockdata/index-basic?indexCode=399006.SZ", timeout=30)
    csrf = re.search(r'name="_csrf"\s+content="([^"]+)"', page.text).group(1)
    token = hashlib.md5(datetime.now().date().isoformat().encode()).hexdigest()
    h = dict(sess.headers)
    h["X-CSRF-Token"] = csrf
    r = sess.get("https://legulegu.com/api/stockdata/index-basic",
                 params={"indexCode": "399006.SZ", "freq": "month", "token": token},
                 headers=h, timeout=30)
    j = r.json()
    data = j["data"] if isinstance(j, dict) and "data" in j else j
    df = pd.DataFrame(data)
    print("legu cols", df.columns.tolist())
    df["date"] = pd.to_datetime(df["date"])
    keep = ["date", "close", "addTtmPe", "ttmPe", "middleTtmPe", "addPb", "pb",
            "middlePb", "addDvTtm", "dvTtm", "addLyrPe"]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].sort_values("date").reset_index(drop=True)
    for c in keep[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df.to_csv(os.path.join(DATA, "cyb_valuation_monthly.csv"), index=False)
    print("legu", df.shape, df.tail(2).to_string())
    return df


def tx_quotes(codes):
    out = []
    for i in range(0, len(codes), 50):
        batch = codes[i:i + 50]
        q = ",".join(("sz" if c.startswith(("30", "00", "15")) else "sh") + c for c in batch)
        txt = get("https://qt.gtimg.cn/q=" + q).content.decode("gbk", errors="ignore")
        for line in txt.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            body = line.split("=", 1)[1].strip().strip('"')
            f = body.split("~")
            if len(f) < 54:
                continue
            def num(k):
                try:
                    return float(f[k])
                except Exception:
                    return None
            out.append({
                "code": f[2], "name": f[1], "price": num(3), "prev": num(4),
                "pct": num(32), "turnover": num(38), "pe_ttm": num(39),
                "float_cap": num(44), "total_cap": num(45), "pb": num(46),
                "pe_dyn": num(52), "pe_static": num(53),
            })
        time.sleep(0.4)
    df = pd.DataFrame(out)
    df.to_csv(os.path.join(DATA, "quotes.csv"), index=False, encoding="utf-8-sig")
    print("quotes", df.shape)
    return df


def fetch_earnings():
    import akshare as ak
    for date in ["20260930", "20260630", "20250930", "20250630", "20251231"]:
        path = os.path.join(DATA, f"yjbb_{date}.csv")
        if os.path.exists(path):
            print("skip", date)
            continue
        for attempt in range(3):
            try:
                df = ak.stock_yjbb_em(date=date)
                df.to_csv(path, index=False, encoding="utf-8-sig")
                print("earnings", date, df.shape)
                break
            except Exception as e:
                print("retry", date, repr(e)[:200])
                time.sleep(5)


def fetch_etf():
    # 日线（前复权），最多约 640 根
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {"param": "sz159915,day,,,1800,qfq"}
    j = get(url, params=params).json()
    d = j["data"]["sz159915"]
    rows = d.get("qfqday") or d.get("day")
    df = pd.DataFrame(rows)
    df = df.iloc[:, :6]
    df.columns = ["date", "open", "close", "high", "low", "volume"]
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open", "close", "high", "low", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df.to_csv(os.path.join(DATA, "etf_159915.csv"), index=False)
    print("etf", df.shape, df["date"].min().date(), "->", df["date"].max().date(), "close", df["close"].iloc[-1])
    return df


if __name__ == "__main__":
    c = fetch_constituents()
    fetch_index_history()
    fetch_legu()
    tx_quotes(c["code"].tolist())
    fetch_earnings()
    fetch_etf()