import json
import os
import re
import sys
import types
from datetime import datetime
from hashlib import md5

import numpy as np
import pandas as pd
import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CASH_RATE = 0.02
BOND_RATE = 0.03
BUY_PCTL = 0.20
SELL_PCTL = 0.80
WINDOW = 250 * 5
MIN_PERIODS = 250
STOCK_WEIGHT = 0.7
START_ANCHOR = "2010-01-01"
INCOME = 10000.0

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# sina 港股指数日线是加密 js，用 quickjs 跑 akshare 的解码函数（py_mini_racer 在 mac arm64 没有可用库）
try:  # noqa
    import py_mini_racer  # type: ignore
    _probe = py_mini_racer.MiniRacer()  # 探活：arm64 缺 .dylib 时 import 不报错、实例化才报
    del _probe
    _need_shim = False
except Exception:
    _need_shim = True

if _need_shim:
    import quickjs  # type: ignore

    class _MiniRacer:
        def __init__(self):
            self._ctx = quickjs.Context()

        def eval(self, code):
            self._ctx.eval(code)

        def call(self, fn, *args):
            v = self._ctx.eval(fn)(*args)
            if isinstance(v, quickjs.Object):
                return json.loads(v.json())
            return v

    _m = types.ModuleType("py_mini_racer")
    _m.__path__ = []
    _m.MiniRacer = _MiniRacer
    _mp = types.ModuleType("py_mini_racer.py_mini_racer")
    _mp.MiniRacer = _MiniRacer
    sys.modules["py_mini_racer"] = _m
    sys.modules["py_mini_racer.py_mini_racer"] = _mp

# sina 港股指数日线的解密 js（来自 akshare 的 hk_js_decode，用于拉取恒生科技日线）
SINA_HK_DECODE_JS = r"""

function d(t) {
            var e, i, n, r, a, o, s, l = (arguments,
            864e5), u = 7657, c = [], d = [], h = ~(3 << 30), f = 1 << 30, m = [0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 20, 23, 24, 27, 29, 30], p = Math, g = function() {
                var l, u;
                for (l = 0; 64 > l; l++)
                    d[l] = p.pow(2, l),
                    26 > l && (c[l] = v(l + 65),
                    c[l + 26] = v(l + 97),
                    10 > l && (c[l + 52] = v(l + 48)));
                for (c.push("+", "/"),
                c = c.join(""),
                i = t.split(""),
                n = i.length,
                l = 0; n > l; l++)
                    i[l] = c.indexOf(i[l]);
                return r = {},
                e = o = 0,
                a = {},
                u = w([12, 6]),
                s = 63 ^ u[1],
                {
                    _1479: D,
                    _136: _,
                    _200: C,
                    _139: R,
                    _197: A,
                    _3466: O
                }["_" + u[0]] || function() {
                    return []
                }
            }, v = String.fromCharCode, b = function(t) {
                return t === {}._
            }, N = function() {
                var t, e;
                for (t = y(),
                e = 1; ; ) {
                    if (!y())
                        return e * (2 * t - 1);
                    e++
                }
            }, y = function() {
                var t;
                return e >= n ? 0 : (t = i[e] & 1 << o,
                o++,
                o >= 6 && (o -= 6,
                e++),
                !!t)
            }, w = function(t, r, a) {
                var s, l, u, c, h;
                for (l = [],
                u = 0,
                r || (r = []),
                a || (a = []),
                s = 0; s < t.length; s++)
                    if (c = t[s],
                    u = 0,
                    c) {
                        if (e >= n)
                            return l;
                        if (t[s] <= 0)
                            u = 0;
                        else if (t[s] <= 30) {
                            for (; h = 6 - o,
                            h = c > h ? h : c,
                            u |= (i[e] >> o & (1 << h) - 1) << t[s] - c,
                            o += h,
                            o >= 6 && (o -= 6,
                            e++),
                            c -= h,
                            !(0 >= c); )
                                ;
                            r[s] && u >= d[t[s] - 1] && (u -= d[t[s]])
                        } else
                            u = w([30, t[s] - 30], [0, r[s]]),
                            a[s] || (u = u[0] + u[1] * d[30]);
                        l[s] = u
                    } else
                        l[s] = 0;
                return l
            }, x = function() {
                var t;
                return t = w([3])[0],
                1 == t ? (r.d = w([18], [1])[0],
                t = 0) : t || (t = w([6])[0]),
                t
            }, S = function(t) {
                var e, i, n;
                for (t > 1 && (e = 0),
                e = 0; t > e; e++)
                    r.d++,
                    n = r.d % 7,
                    (3 == n || 4 == n) && (r.d += 5 - n);
                return i = new Date,
                i.setTime((u + r.d) * l),
                i
            }, k = function(t) {
                var e, i, n;
                for (n = r.wd || 62,
                e = 0; t > e; e++)
                    do
                        r.d++;
                    while (!(n & 1 << (r.d % 7 + 10) % 7));
                return i = new Date,
                i.setTime((u + r.d) * l),
                i
            }, T = function(t) {
                var e, i, n;
                return t ? 0 > t ? (e = T(-t),
                [-e[0], -e[1]]) : (e = t % 3,
                i = (t - e) / 3,
                n = [i, i],
                e && n[e - 1]++,
                n) : [0, 0]
            }, P = function(t, e, i) {
                var n, r, a;
                for (r = "number" == typeof e ? T(e) : e,
                a = T(i),
                n = [a[0] - r[0], a[1] - r[1]],
                r = 1; n[0] < n[1]; )
                    r *= 5,
                    n[1]--;
                for (; n[1] < n[0]; )
                    r *= 2,
                    n[0]--;
                if (r > 1 && (t *= r),
                n = n[0],
                t = E(t),
                0 > n) {
                    for (; t.length + n <= 0; )
                        t = "0" + t;
                    return n += t.length,
                    r = t.substr(0, n) - 0,
                    void 0 === i ? r + "." + t.substr(n) - 0 : (a = t.charAt(n) - 0,
                    a > 5 ? r++ : 5 == a && (t.substr(n + 1) - 0 > 0 ? r++ : r += 1 & r),
                    r)
                }
                for (; n > 0; n--)
                    t += "0";
                return t - 0
            }, C = function() {
                var t, i, a, o, l;
                if (s >= 1)
                    return [];
                for (r.d = w([18], [1])[0] - 1,
                a = w([3, 3, 30, 6]),
                r.p = a[0],
                r.ld = a[1],
                r.cd = a[2],
                r.c = a[3],
                r.m = p.pow(10, r.p),
                r.pc = r.cd / r.m,
                i = [],
                t = 0; o = {
                    d: 1
                },
                y() && (a = w([3])[0],
                0 == a ? o.d = w([6])[0] : 1 == a ? (r.d = w([18])[0],
                o.d = 0) : o.d = a),
                l = {
                    date: S(o.d)
                },
                y() && (r.ld += N()),
                a = w([3 * r.ld], [1]),
                r.cd += a[0],
                l.close = r.cd / r.m,
                i.push(l),
                !(e >= n) && (e != n - 1 || 63 & (r.c ^ t + 1)); t++)
                    ;
                return i[0].prevclose = r.pc,
                i
            }, _ = function() {
                var t, i, a, o, l, u, c, d, h, f, m;
                if (s > 2)
                    return [];
                for (c = [],
                h = {
                    v: "volume",
                    p: "price",
                    a: "avg_price"
                },
                r.d = w([18], [1])[0] - 1,
                d = {
                    date: S(1)
                },
                a = w(1 > s ? [3, 3, 4, 1, 1, 1, 5] : [4, 4, 4, 1, 1, 1, 3]),
                t = 0; 7 > t; t++)
                    r[["la", "lp", "lv", "tv", "rv", "zv", "pp"][t]] = a[t];
                for (r.m = p.pow(10, r.pp),
                s >= 1 ? (a = w([3, 3]),
                r.c = a[0],
                a = a[1]) : (a = 5,
                r.c = 2),
                r.pc = w([6 * a])[0],
                d.pc = r.pc / r.m,
                r.cp = r.pc,
                r.da = 0,
                r.sa = r.sv = 0,
                t = 0; !(e >= n) && (e != n - 1 || 7 & (r.c ^ t)); t++) {
                    for (l = {},
                    o = {},
                    f = r.tv ? y() : 1,
                    i = 0; 3 > i; i++)
                        if (m = ["v", "p", "a"][i],
                        (f ? y() : 0) && (a = N(),
                        r["l" + m] += a),
                        u = "v" == m && r.rv ? y() : 1,
                        a = w([3 * r["l" + m] + ("v" == m ? 7 * u : 0)], [!!i])[0] * (u ? 1 : 100),
                        o[m] = a,
                        "v" == m) {
                            if (!(l[h[m]] = a) && (s > 1 || 241 > t) && (r.zv ? !y() : 1)) {
                                o.p = 0;
                                break
                            }
                        } else
                            "a" == m && (r.da = (1 > s ? 0 : r.da) + o.a);
                    r.sv += o.v,
                    l[h.p] = (r.cp += o.p) / r.m,
                    r.sa += o.v * r.cp,
                    l[h.a] = b(o.a) ? t ? c[t - 1][h.a] : l[h.p] : r.sv ? ((p.floor((r.sa * (2e3 / r.m) + r.sv) / r.sv) >> 1) + r.da) / 1e3 : l[h.p] + r.da / 1e3,
                    c.push(l)
                }
                return c[0].date = d.date,
                c[0].prevclose = d.pc,
                c
            }, D = function() {
                var t, e, i, n, a, o, l;
                if (s >= 1)
                    return [];
                for (r.lv = 0,
                r.ld = 0,
                r.cd = 0,
                r.cv = [0, 0],
                r.p = w([6])[0],
                r.d = w([18], [1])[0] - 1,
                r.m = p.pow(10, r.p),
                a = w([3, 3]),
                r.md = a[0],
                r.mv = a[1],
                t = []; a = w([6]),
                a.length; ) {
                    if (i = {
                        c: a[0]
                    },
                    n = {},
                    i.d = 1,
                    32 & i.c)
                        for (; ; ) {
                            if (a = w([6])[0],
                            63 == (16 | a)) {
                                l = 16 & a ? "x" : "u",
                                a = w([3, 3]),
                                i[l + "_d"] = a[0] + r.md,
                                i[l + "_v"] = a[1] + r.mv;
                                break
                            }
                            if (32 & a) {
                                o = 8 & a ? "d" : "v",
                                l = 16 & a ? "x" : "u",
                                i[l + "_" + o] = (7 & a) + r["m" + o];
                                break
                            }
                            if (o = 15 & a,
                            0 == o ? i.d = w([6])[0] : 1 == o ? (r.d = o = w([18])[0],
                            i.d = 0) : i.d = o,
                            !(16 & a))
                                break
                        }
                    n.date = S(i.d);
                    for (o in {
                        v: 0,
                        d: 0
                    })
                        b(i["x_" + o]) || (r["l" + o] = i["x_" + o]),
                        b(i["u_" + o]) && (i["u_" + o] = r["l" + o]);
                    for (i.l_l = [i.u_d, i.u_d, i.u_d, i.u_d, i.u_v],
                    l = m[15 & i.c],
                    1 & i.u_v && (l = 31 - l),
                    16 & i.c && (i.l_l[4] += 2),
                    e = 0; 5 > e; e++)
                        l & 1 << 4 - e && i.l_l[e]++,
                        i.l_l[e] *= 3;
                    i.d_v = w(i.l_l, [1, 0, 0, 1, 1], [0, 0, 0, 0, 1]),
                    o = r.cd + i.d_v[0],
                    n.open = o / r.m,
                    n.high = (o + i.d_v[1]) / r.m,
                    n.low = (o - i.d_v[2]) / r.m,
                    n.close = (o + i.d_v[3]) / r.m,
                    a = i.d_v[4],
                    "number" == typeof a && (a = [a, a >= 0 ? 0 : -1]),
                    r.cd = o + i.d_v[3],
                    l = r.cv[0] + a[0],
                    r.cv = [l & h, r.cv[1] + a[1] + !!((r.cv[0] & h) + (a[0] & h) & f)],
                    n.volume = (r.cv[0] & f - 1) + r.cv[1] * f,
                    t.push(n)
                }
                return t
            }, R = function() {
                var t, e, i, n;
                if (s > 1)
                    return [];
                for (r.l = 0,
                n = -1,
                r.d = w([18])[0] - 1,
                i = w([18])[0]; r.d < i; )
                    e = S(1),
                    0 >= n ? (y() && (r.l += N()),
                    n = w([3 * r.l], [0])[0] + 1,
                    t || (t = [e],
                    n--)) : t.push(e),
                    n--;
                return t
            }, A = function() {
                var t, i, a, o;
                if (s >= 1)
                    return [];
                for (r.f = w([6])[0],
                r.c = w([6])[0],
                a = [],
                r.dv = [],
                r.dl = [],
                t = 0; t < r.f; t++)
                    r.dv[t] = 0,
                    r.dl[t] = 0;
                for (t = 0; !(e >= n) && (e != n - 1 || 7 & (r.c ^ t)); t++) {
                    for (o = [],
                    i = 0; i < r.f; i++)
                        y() && (r.dl[i] += N()),
                        r.dv[i] += w([3 * r.dl[i]], [1])[0],
                        o[i] = r.dv[i];
                    a.push(o)
                }
                return a
            }, O = function() {
                if (r = {
                    b_avp: 1,
                    b_ph: 0,
                    b_phx: 0,
                    b_sep: 0,
                    p_p: 6,
                    p_v: 0,
                    p_a: 0,
                    p_e: 0,
                    p_t: 0,
                    l_o: 3,
                    l_h: 3,
                    l_l: 3,
                    l_c: 3,
                    l_v: 5,
                    l_a: 5,
                    l_e: 3,
                    l_t: 0,
                    u_p: 0,
                    u_v: 0,
                    u_a: 0,
                    wd: 62,
                    d: 0
                },
                s > 0)
                    return [];
                var t, i, a, o, l, u, c;
                for (t = []; ; ) {
                    if (e >= n)
                        return void 0;
                    if (a = {
                        d: 1,
                        c: 0
                    },
                    y())
                        if (y()) {
                            if (y()) {
                                for (a.c++,
                                a.a = r.b_avp,
                                y() && (r.b_avp ^= y(),
                                r.b_ph ^= y(),
                                r.b_phx ^= y(),
                                a.s = r.b_sep,
                                r.b_sep ^= y(),
                                y() && (r.wd = w([7])[0]),
                                a.s ^ r.b_sep && (a.s ? r.u_p = r.u_c : r.u_o = r.u_h = r.u_l = r.u_c = r.u_p)),
                                u = 0; u < 3 + 2 * r.b_ph; u++)
                                    if (y() && (l = "pvaet".charAt(u),
                                    o = r["p_" + l],
                                    r["p_" + l] += N(),
                                    r["u_" + l] = P(r["u_" + l], o, r["p_" + l]) - 0,
                                    r.b_sep && !u))
                                        for (c = 0; 4 > c; c++)
                                            l = "ohlc".charAt(c),
                                            r["u_" + l] = P(r["u_" + l], o, r.p_p) - 0;
                                !r.b_avp && a.a && (r.u_a = P(i && i.amount || 0, 0, r.p_a))
                            }
                            if (y())
                                for (a.c++,
                                u = 0; u < 7 + r.b_ph + r.b_phx; u++)
                                    y() && (6 == u ? a.d = x() : r["l_" + "ohlcva*et".charAt(u)] += N());
                            if (y() && (a.c++,
                            l = r.l_o + (y() && N()),
                            o = w([3 * l], [1])[0],
                            a.p = r.b_sep ? r.u_c + o : r.u_p += o),
                            !a.c)
                                break
                        } else
                            y() ? y() ? y() ? a.d = x() : r.l_v += N() : r.b_ph && y() ? r["l_" + "et".charAt(r.b_phx && y())] += N() : r.l_a += N() : r["l_" + "ohlc".charAt(w([2])[0])] += N();
                    for (u = 0; u < 6 + r.b_ph + r.b_phx; u++)
                        c = "ohlcvaet".charAt(u),
                        o = (r.b_sep ? 191 : 185) >> u & 1,
                        a["v_" + c] = w([3 * r["l_" + c]], [o])[0];
                    i = {
                        date: k(a.d)
                    },
                    a.p && (i.prevclose = P(a.p, r.p_p)),
                    r.b_sep ? (i.open = P(r.u_o += a.v_o, r.p_p),
                    i.high = P(r.u_h += a.v_h, r.p_p),
                    i.low = P(r.u_l += a.v_l, r.p_p),
                    i.close = P(r.u_c += a.v_c, r.p_p)) : (a.o = r.u_p + a.v_o,
                    i.open = P(a.o, r.p_p),
                    i.high = P(a.o + a.v_h, r.p_p),
                    i.low = P(a.o - a.v_l, r.p_p),
                    i.close = P(r.u_p = a.o + a.v_c, r.p_p)),
                    i.volume = P(r.u_v += a.v_v, r.p_v),
                    r.b_avp ? (o = T(r.p_p),
                    l = T(r.p_v),
                    i.amount = P(P(Math.floor((r.b_sep ? (r.u_o + r.u_h + r.u_l + r.u_c) / 4 : a.o + (a.v_h - a.v_l + a.v_c) / 4) * r.u_v + .5), [o[0] + l[0], o[1] + l[1]], r.p_a) + a.v_a, r.p_a)) : (r.u_a += a.v_a,
                    i.amount = P(r.u_a, r.p_a)),
                    r.b_ph && (i.postVol = P(a.v_e, r.p_e),
                    i.postAmt = P(Math.floor(i.postVol * i.close + (r.b_phx ? P(a.v_t, r.p_t) : 0) + .5), 0)),
                    t.push(i)
                }
                return t
            }, E = function(t) {
                var e, i, n;
                if (t = (t || 0).toString(),
                n = [],
                i = t.toLowerCase().indexOf("e"),
                i > 0) {
                    for (e = t.substr(i + 1) - 0; e >= 0; e--)
                        n.push(Math.floor(e * Math.pow(10, -e) + .5) - 0);
                    return n.join("")
                }
                return t
            };
            return g()()
        }
        ;
"""

STOCK_DESC = {
    "满仓躺平": "躺平基准。假设起点把 100 万一次性买入指数基金，之后不管涨跌都不卖、不加仓。用来回答：完全不折腾能拿多少。",
    "PE·20买80卖": "简单波段，本实验的对照基准。每天看指数的 PE 在过去的分位：分位 <20%（比过去便宜）时把全部钱买成股票；分位 >80% 时全部卖出，钱放货基吃 2% 利息，等下次低估再买回来。",
    "股7债3·月再平衡": "70% 的钱买指数、30% 买债基（假设年化 3%）。每月底检查一次再平衡回 70/30，靠『被动低买高卖』降低波动。",
    "阶梯仓位·越便宜越重仓": "不清仓也不满仓，仓位随估值分档：分位 <10% 时满仓，10~30% 时八成仓，30~50% 六成，50~70% 四成，70~90% 两成，>90% 空仓。缺点：估值中位时长期半仓，容易踏空。",
    "趋势确认·30买90卖": "右侧交易，专治『接飞刀』和『卖飞』。买入要同时满足：分位 <30%（便宜）且指数站上 250 日均线；卖出要同时满足：分位 >90%（极端贵）且指数跌破 60 日均线。",
    "PE·30买90卖": "新一代对照基准（替换 20买80卖）。买入放宽到分位 <30%（不追深度低估，避免等坑踏空 2019 式低位启动），卖出收紧到 >90%（贵不是卖的理由，极端贵才是）。曾与带 126 天冷静期版本逐日重合（冷静期实测 0 贡献），冷静期版已下线。",
    "30买90卖·30%底仓": "PE·30买90卖 的『人性化版』：规则不变，但仓位最低只能降到 30%，永不清仓。",
    "PE·50%买90%卖": "『过早抄底』对照组：卖出线不变（分位 >90% 清仓），但买回线放宽到分位 <50% 就全仓买回——比基准 PE·30买90卖 早一大截，验证大跌后『接飞刀』的代价。实质是只有极端高估才空仓。",
    "破线卖·深跌买（纯价格）": "完全不用 PE 的价格趋势策略：① 卖：连续 ≥10 个交易日站上 20 日均线（确认先有一波拉升）后跌破均线就卖；② 买：从历史高点回撤 ≥20% 且距上次卖出满 10 个交易日就买回（深跌+间隔，避免接飞刀）。专为估值分位失效的指数（恒生科技）设计。",
    "货币基金": "全程只买货币基金（假设年化 2%），不碰股票。无风险基准线。",
}

# 各市场核心经验（展示在页面顶部）
LESSONS = {
    "沪深300": "牛短熊长——PE 过高（分位>90%）一定要逃顶，但卖出别太灵敏，绝大部分涨幅都在极端高估（≥90% 分位档贡献 +116%）的位置取得。买入可以稍早抄底，分位 <50% 就够（实测 30% 买回与 50% 买回相差仅 0.2pp/年）；如果非要等深度低估（<20%）再买，反而会踏空机会、空仓时间过长（本项目最长达 4.7 年），非常反人性。",
    "中证A500": "2024-09 才发布的宽基，**只用发布后的真实数据**（价格与官方 PE 均 2024-09 起，不采用回填历史），窗口约 2 年、样本短。分位用上市以来 expanding（约 250 个交易日后才出信号），故前半段估值策略基本等同躺平；结论是「早期行为画像」，不可外推。行业更均衡、风格介于沪深300 与中证500 之间，可当作「A 股核心资产」的另一把尺子。",
    "恒生科技": "盈利高波动的科技指数，PE 估值择时在这里几乎失效——本窗口 expanding 分位被早年极端 PE 钉死、从未越 80% 卖出线，估值类策略全部 0 交易=躺平；**纯价格趋势「破线卖·深跌买」才是效果最好的**（累计 +71% vs 躺平 +12%，年化 20% / 回撤 -23%）：连续拉升后跌破 20 日均线就走、从高点回撤 20% 再接。注意它只在恒生科技这类高波动趋势指数成立，沪深300/纳指会被反复假突破打脸。",
    "纳斯达克100": "盈利驱动型市场——躺平 + 坚持定投完胜所有择时（普通定投 XIRR 15.5%）；估值不是卖的理由（2009-2021 主升浪绝大多数时间标普分位 >80%，择时长期空仓踏空）；控仓只降回撤、择时拖后腿。",
    "标普500": "美股成熟宽基：结论与纳指一致但更极致——躺平+定投最优，择时（含 PE 分位/趋势）在长牛市里全是拖后腿；估值信号天然滞后，股价先于 PE 定价。",
    "恒生指数": "港股宽基，估值信号仅 2019 起可回测（窗口短）；低股息率+盈利波动，PE 择时区分度有限，控仓/再平衡仍是主要风险工具。",
    "创业板指": "A股成长风格：弹性大、牛熊切换急，PE 分位择时比沪深300 更有效（成长股估值回归猛烈）；但本页用市场整体 PE 近似 399006，交叉口径需打折。",
    "科创50": "2020 起的高波动成长指数，回测窗口 2021-07 起（约 5 年，起点分位 27%）：起点正好在高位回落前，**躺平 5 年小幅转负（-1.7%、回撤 -60%）**；纯价格趋势「破线卖·深跌买」再次最优（+54% / 年化 8.9%）——高波动成长指数，趋势追踪 > PE 择时 > 躺平。",
    "红利低波": "低波动红利风格，2018 起：天然抗跌（回撤小）、熊市里是避风港，估值分位择时收益有限——特征是'慢涨抗跌'而非'高弹性'。",
    "黄金": "黄金没有 PE，估值择时先天不可用——涨跌只能靠价格自身：200 日单均线/双均线吃主升段、抄底网格在长牛里左侧上车、波动率目标自动降仓防回撤。26 年里黄金'牛长熊短但熊市很磨人'（2012-2016、2020-2022 高位横盘回撤 20-40%），纯躺平波动大；趋势型策略跑赢与否取决于区间里有多少段'沿之势'可吃。",
}

FLOW_DESC = {
    "普通定投(立即投)": "每月发工资 1 万，到账当天立刻全买指数，不择时不等待。",
    "PE·30买90卖·流量版": "工资版 PE·30买90卖：每月按 30买90卖 信号决定总资产的股票比例，增量工资自动跟随。",
    "PE·20买80卖·流量版": "工资版 PE择时：每月到账的钱看信号行事——策略处于『持有』状态就直接买入，处于『空仓』状态就攒进货基池；触发买入信号时池子存款一起投进去；触发卖出信号时卖成货基。",
    "阶梯仓位·流量版": "工资版阶梯仓位：每月把『股票+池子』的总资产按阶梯档位重新配比。",
    "趋势确认·流量版": "工资版趋势确认：每月按趋势确认信号决定总资产的股票比例，增量工资自动跟随。",
    "30买90卖·30%底仓·流量版": "工资版 30买90卖·底仓：每月按 30买90卖 信号再平衡，但股票仓位最低保持在 30%，永不卖干净。",
    "PE·50%买90%卖·流量版": "工资版『过早抄底』：卖出后分位回落 <50% 就恢复投入（基准为 <30%），验证发力流里早抄底/晚抄底的差异。",
    "破线卖·深跌买·流量版": "工资版纯价格趋势（破线卖·深跌买）：每月按该信号决定总资产的股票比例，增量工资自动跟随——专为恒生科技等高波动趋势指数设计。",
    "智能定投": "每月投，但金额随估值变：分位 50% 时投 1 万，分位 0% 时投 2 万，分位 100% 时不投。钱当月必须花掉。",
    "资金池跨期调配": "工资先全部攒进货基池（2% 利息），投放节奏看估值：分位 >80% 一分不投；50~80% 只投当月；20~50% 投当月 + 池子的 10%；<20% 投 2 倍当月 + 池子的 20%。只买不卖。",
    "Buy The Dip·流量版": "工资先攒进货基池，平时不买；买点只认「指数距历史高点回撤」：回撤 ≥5% 投池子15%、≥10% 投40%、≥20% 投70%、≥30% 近乎满仓抄——跌得越深买得越猛，只买不卖。",
}


# ---------- 数据加载 ----------

def _write_cache(path, df):
    df.to_csv(path, index=False)


def _merge_cache(path, new_df, key="date"):
    """按月新增点并入既有缓存：保留旧日频行，追加新日期（乐咕指数 PE 从日频退化为月度时用）"""
    if os.path.exists(path):
        old = pd.read_csv(path, parse_dates=[key])
        df = pd.concat([old, new_df], ignore_index=True)
    else:
        df = new_df
    df = df.drop_duplicates(subset=[key], keep="first").sort_values(key).reset_index(drop=True)
    df.to_csv(path, index=False)
    return df


def load_hs300():
    pe_path = os.path.join(DATA_DIR, "hs300_pe.csv")
    px_path = os.path.join(DATA_DIR, "hs300_price.csv")
    if os.path.exists(pe_path) and os.path.exists(px_path):
        pe = pd.read_csv(pe_path, parse_dates=["date"])
        px = pd.read_csv(px_path, parse_dates=["date"])
    else:
        import akshare as ak  # 仅 csindex 价格走 akshare（不依赖 py_mini_racer）
        raw_pe = legu_index_pe("000300.SH", "https://legulegu.com/stockdata/sz50-ttm-lyr")
        pe = raw_pe
        raw_px = ak.stock_zh_index_hist_csindex(symbol="H00300", start_date="20050101", end_date="20991231")
        px = pd.DataFrame({"date": pd.to_datetime(raw_px["日期"]), "close": raw_px["收盘"].astype(float)})
        pe.to_csv(pe_path, index=False)
        px.to_csv(px_path, index=False)
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    daily = pd.DatetimeIndex(px["date"])
    pe_s = pd.Series(pd.to_numeric(pe["pe"], errors="coerce").values, index=pd.to_datetime(pe["date"])).sort_index()
    pe_d = pe_s.reindex(daily, method="ffill")
    df = px.assign(pe=pe_d.values, div_yield=0.0)
    df = df[df["pe"].notna()].reset_index(drop=True)  # 剔除首个 PE 点之前的空估日期（对齐旧 inner-merge 起点）
    return df


def load_a500():
    """中证A500（000510）：价格 + 官方滚动市盈率均取中证官网，仅保留 2024-09 指数发布后的真实数据
    （2024-09 之前的回填历史不用，含幸存者/后视偏差，无参考意义）"""
    px_path = os.path.join(DATA_DIR, "a500.csv")
    if not os.path.exists(px_path):
        import akshare as ak
        raw = ak.stock_zh_index_hist_csindex(symbol="000510", start_date="20240923", end_date="20991231")
        raw.to_csv(px_path, index=False)
    else:
        raw = pd.read_csv(px_path)
    df = pd.DataFrame({
        "date": pd.to_datetime(raw["日期"]),
        "close": pd.to_numeric(raw["收盘"], errors="coerce"),
        "pe": pd.to_numeric(raw["滚动市盈率"], errors="coerce"),
    })
    df = df.dropna(subset=["close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df = df[df["date"] >= "2024-09-23"].reset_index(drop=True)
    df = df[df["pe"].notna()].reset_index(drop=True)
    df["div_yield"] = 0.0
    return df


def sina_hk_daily(symbol):
    import quickjs  # noqa: 直接依赖 quickjs 解密，不走 py_mini_racer（mac 无 arm64 库）
    js_code = SINA_HK_DECODE_JS
    res = requests.get(f"https://finance.sina.com.cn/stock/hkstock/{symbol}/klc2_kl.js", params={"d": "2023_5_01"})
    enc = res.text.split("=")[1].split(";")[0].replace('"', "")
    ctx = quickjs.Context()
    ctx.eval(js_code)
    rows = ctx.eval("d")(enc)
    lst = json.loads(rows.json())
    df = pd.DataFrame(lst)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df[["date", "close"]].copy()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df


def legu_hsidata(index_code):
    sess = requests.Session()
    sess.headers.update({"User-Agent": _UA})
    page = sess.get(f"https://legulegu.com/stockdata/hsi-theme-index?indexCode={index_code}", timeout=15)
    csrf = re.search(r'name="_csrf"\s+content="([^"]+)"', page.text).group(1)
    token = md5(datetime.now().date().isoformat().encode()).hexdigest()
    h = dict(sess.headers)
    h["X-CSRF-Token"] = csrf
    rr = sess.get("https://legulegu.com/api/stockdata/hsidata",
                  params={"indexCode": index_code, "token": token}, headers=h, timeout=15)
    data = rr.json()["data"]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df["pe"] = pd.to_numeric(df["pe"], errors="coerce")
    df["dv"] = pd.to_numeric(df["dv"], errors="coerce")
    return df


def _legu_token():
    """乐咕所有数据接口的 token = md5(today ISO 日期)（等价 akshare 用 py_mini_racer 跑 hash_code 的 hex 函数）"""
    return md5(datetime.now().date().isoformat().encode()).hexdigest()


def legu_get(url, params, csrf_page):
    sess = requests.Session()
    sess.headers.update({"User-Agent": _UA})
    page = sess.get(csrf_page, timeout=15)
    csrf = re.search(r'name="_csrf"\s+content="([^"]+)"', page.text).group(1)
    h = dict(sess.headers)
    h["X-CSRF-Token"] = csrf
    rr = sess.get(url, params=params, headers=h, timeout=15)
    return rr


def legu_index_pe(index_code, csrf_page):
    """乐咕指数市盈率（月度，当月为月中实时值）：返回 date, pe 两列
    替代 akshare stock_index_pe_lg（其依赖 py_mini_racer，mac arm64 不可用）"""
    res = legu_get("https://legulegu.com/api/stockdata/index-basic-pe",
                   {"token": _legu_token(), "indexCode": index_code}, csrf_page)
    d = res.json()["data"]
    df = pd.DataFrame(d)
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    # index-basic-pe 的 addTtmPe = akshare 的"滚动市盈率"
    return pd.DataFrame({"date": df["date"], "pe": pd.to_numeric(df["addTtmPe"], errors="coerce")})


def legu_market_pe(market_id, csrf_page):
    """乐咕市场整体市盈率（月度）：返回 date, pe（列名对齐 akshare stock_market_pe_lg 的 日期/平均市盈率）"""
    res = legu_get("https://legulegu.com/api/stock-data/market-pe",
                   {"token": _legu_token(), "marketId": market_id}, csrf_page)
    d = res.json()["data"]
    df = pd.DataFrame(d)
    df["date"] = pd.to_datetime(df["date"])
    if df["date"].dt.tz is not None:
        df["date"] = df["date"].dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    return df[["date", "close", "pe"]].rename(columns={"date": "日期", "close": "指数", "pe": "平均市盈率"})


def sina_index_daily(symbol):
    """sina A股指数日线（hisdata 加密 js，quickjs 解密；同 sina_hk_daily 一套 JS）
    替代 akshare stock_zh_index_daily（依赖 py_mini_racer 不可用）"""
    js_code = SINA_HK_DECODE_JS
    res = requests.get(f"https://finance.sina.com.cn/realstock/company/{symbol}/hisdata/klc_kl.js",
                       params={"d": "2020_2_4"}, headers={"User-Agent": _UA}, timeout=20)
    enc = res.text.split("=")[1].split(";")[0].replace('"', "")
    m = _MiniRacer()
    m.eval(js_code)
    rows = m.call("d", enc)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    keep = [c for c in ("date", "open", "high", "low", "close", "volume") if c in df.columns]
    df = df[keep]
    for c in keep[1:]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_hstech():
    px_path = os.path.join(DATA_DIR, "hstech_price.csv")
    pe_path = os.path.join(DATA_DIR, "hstech_pe.csv")
    if os.path.exists(px_path):
        px = pd.read_csv(px_path, parse_dates=["date"])
    else:
        px = sina_hk_daily("HSTECH")
        px.to_csv(px_path, index=False)
    if os.path.exists(pe_path):
        raw = pd.read_csv(pe_path, parse_dates=["date"])
    else:
        raw = legu_hsidata("HSTECH")
        raw.to_csv(pe_path, index=False)
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    daily = pd.DatetimeIndex(px["date"])
    pe_series = pd.Series(raw["pe"].values, index=raw["date"]).sort_index()
    dv_series = pd.Series(raw["dv"].values, index=raw["date"]).sort_index()
    pe_d = pe_series.reindex(daily, method="ffill").shift(1)
    dv_d = dv_series.reindex(daily, method="ffill").shift(1)
    df = px.assign(pe=pe_d.values, div_yield=(dv_d.values / 100.0))
    return df


def fetch_yahoo_daily(symbol, cache_path, start_year=1995):
    import datetime as _dt
    p1 = int(_dt.datetime(start_year, 1, 1).timestamp())
    p2 = int(_dt.datetime(2027, 1, 1).timestamp())
    r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                     params={"period1": p1, "period2": p2, "interval": "1d"},
                     headers={"User-Agent": _UA}, timeout=30)
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    dates = [_dt.datetime.utcfromtimestamp(t).date() for t in ts]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": pd.to_numeric(closes, errors="coerce")})
    df = df.dropna().sort_values("date").reset_index(drop=True)
    df.to_csv(cache_path, index=False)
    return df


def multpl_monthly_pe(cache_path, slug):
    url = f"https://www.multpl.com/{slug}/table/by-month"
    t = requests.get(url, headers={"User-Agent": _UA}, timeout=20).text
    # 当月/近月标 Estimate（<abbr title="Estimate">†</abbr>），旧正则漏掉这些行导致 PE 停滞在数月前
    rows = re.findall(r"<td>\s*([A-Za-z]+ \d{1,2}, \d{4})\s*</td>\s*<td>\s*(?:(?:<abbr[^>]*>\s*[^<]*\s*</abbr>)|\s*|&#x2002;)+\s*([0-9.]+)\s*</td>", t)
    df = pd.DataFrame(rows, columns=["date", "value"])
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"])
    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(cache_path, index=False)
    return df


def load_ndx():
    px_path = os.path.join(DATA_DIR, "ndx_price.csv")
    pe_path = os.path.join(DATA_DIR, "ndx_pe.csv")  # 信号 = 标普500 市盈率
    cape_path = os.path.join(DATA_DIR, "ndx_cape.csv")  # 参考 = 标普500 席勒CAPE
    px = fetch_yahoo_daily("%5ENDX", px_path) if not os.path.exists(px_path) else pd.read_csv(px_path, parse_dates=["date"])
    pe = multpl_monthly_pe(pe_path, "s-p-500-pe-ratio") if not os.path.exists(pe_path) else pd.read_csv(pe_path, parse_dates=["date"])
    cape = multpl_monthly_pe(cape_path, "shiller-pe") if not os.path.exists(cape_path) else pd.read_csv(cape_path, parse_dates=["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    daily = pd.DatetimeIndex(px["date"])
    pe_s = pd.Series(pe["value"].values, index=pe["date"]).sort_index()
    cape_s = pd.Series(cape["value"].values, index=cape["date"]).sort_index()
    pe_d = pe_s.reindex(daily, method="ffill").shift(1)
    cape_d = cape_s.reindex(daily, method="ffill").shift(1)
    df = px.assign(pe=pe_d.values, cape=cape_d.values, div_yield=0.0)
    return df


def load_csindex(symbol, cache_path, start="19900101", pe_col="滚动市盈率"):
    """中证指数官网日线（含官方滚动市盈率），用于科创50(000688)/红利低波(H30269)"""
    import akshare as ak
    if not os.path.exists(cache_path):
        raw = ak.stock_zh_index_hist_csindex(symbol=symbol, start_date=start, end_date="20991231")
        raw.to_csv(cache_path, index=False)
    else:
        raw = pd.read_csv(cache_path)
    df = pd.DataFrame({
        "date": pd.to_datetime(raw["日期"]),
        "close": pd.to_numeric(raw["收盘"], errors="coerce"),
        "pe": pd.to_numeric(raw.get(pe_col, raw["滚动市盈率"]), errors="coerce"),
    })
    df = df.dropna(subset=["close"]).sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["div_yield"] = 0.0
    return df


def load_kcb50():
    path = os.path.join(DATA_DIR, "kcb50.csv")
    return load_csindex("000688", path, start="20190101")


def load_hldb():
    path = os.path.join(DATA_DIR, "hldb.csv")
    return load_csindex("H30269", path, start="20180101")


def load_cyb():
    """创业板指：价格=sina 日线（quickjs 解密）；PE=乐咕『创业板』市场整体市盈率（近似口径，非399006自身；月度）"""
    px_path = os.path.join(DATA_DIR, "cyb_price.csv")
    pe_path = os.path.join(DATA_DIR, "cyb_pe.csv")
    if not os.path.exists(px_path):
        raw = sina_index_daily("sz399006")
        raw.to_csv(px_path, index=False)
    else:
        raw = pd.read_csv(px_path, parse_dates=["date"])
    if not os.path.exists(pe_path):
        rawpe = legu_market_pe("4", "https://legulegu.com/stockdata/cybPE")
        rawpe.to_csv(pe_path, index=False)
    else:
        rawpe = pd.read_csv(pe_path)
    px = raw.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    px["date"] = pd.to_datetime(px["date"])
    daily = pd.DatetimeIndex(px["date"])
    pe_s = pd.Series(pd.to_numeric(rawpe[rawpe.columns[-1]], errors="coerce").values, index=pd.to_datetime(rawpe["日期"])).sort_index()
    pe_d = pe_s.reindex(daily, method="ffill").shift(1)
    df = px.assign(pe=pe_d.values, div_yield=0.0)
    return df


def load_sp500():
    """标普500：价格=Yahoo ^GSPC；估值=标普500 PE(与纳指同源 multpl)"""
    import datetime as _dt
    px_path = os.path.join(DATA_DIR, "sp500_price.csv")
    pe_path = os.path.join(DATA_DIR, "sp500_pe.csv")
    px = fetch_yahoo_daily("%5EGSPC", px_path, start_year=1995) if not os.path.exists(px_path) else pd.read_csv(px_path, parse_dates=["date"])
    pe = multpl_monthly_pe(pe_path, "s-p-500-pe-ratio") if not os.path.exists(pe_path) else pd.read_csv(pe_path, parse_dates=["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    daily = pd.DatetimeIndex(px["date"])
    pe_s = pd.Series(pd.to_numeric(pe["value"], errors="coerce").values, index=pe["date"]).sort_index()
    pe_d = pe_s.reindex(daily, method="ffill").shift(1)
    df = px.assign(pe=pe_d.values, div_yield=0.0)
    return df


def load_hsi():
    """恒生指数：价格=Yahoo ^HSI；PE/股息率=乐咕 hsidata 官方月度(2019 起)"""
    px_path = os.path.join(DATA_DIR, "hsi_price.csv")
    pe_path = os.path.join(DATA_DIR, "hsi_pe.csv")
    px = fetch_yahoo_daily("%5EHSI", px_path, start_year=1986) if not os.path.exists(px_path) else pd.read_csv(px_path, parse_dates=["date"])
    if not os.path.exists(pe_path):
        raw = legu_hsidata("HSI")
        raw.to_csv(pe_path, index=False)
    else:
        raw = pd.read_csv(pe_path, parse_dates=["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    daily = pd.DatetimeIndex(px["date"])
    pe_s = pd.Series(pd.to_numeric(raw["pe"], errors="coerce").values, index=pd.to_datetime(raw["date"])).sort_index()
    dv_s = pd.Series(pd.to_numeric(raw["dv"], errors="coerce").values, index=pd.to_datetime(raw["date"])).sort_index()
    pe_d = pe_s.reindex(daily, method="ffill").shift(1)
    dv_d = dv_s.reindex(daily, method="ffill").shift(1)
    df = px.assign(pe=pe_d.values, div_yield=(dv_d.values / 100.0))
    return df


def load_ust10y():
    """美国 10 年期国债名义收益率（%）：Yahoo ^TNX 日频"""
    path = os.path.join(DATA_DIR, "ust10y.csv")
    if not os.path.exists(path):
        return fetch_yahoo_daily("%5ETNX", path, start_year=2000)
    return pd.read_csv(path, parse_dates=["date"])


def load_cpi():
    """美国 CPI 水平值（月频，1871 起，multpl；发布通常滞后 1~2 个月，天然无前视）"""
    path = os.path.join(DATA_DIR, "cpi.csv")
    if not os.path.exists(path):
        return multpl_monthly_pe(path, "cpi")
    return pd.read_csv(path, parse_dates=["date"])


def load_gold():
    """黄金：COMEX 期货连续（GC=F，美元/盎司）。无 PE/股息，价格策略专用。
    额外并入 y10（名义 10Y 收益率）、cpi（月频水平）两列，供美债轮动策略做实际利率近似"""
    px_path = os.path.join(DATA_DIR, "gold_price.csv")
    px = fetch_yahoo_daily("GC%3DF", px_path, start_year=2000) if not os.path.exists(px_path) else pd.read_csv(px_path, parse_dates=["date"])
    px = px.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df = px.assign(pe=float("nan"), div_yield=0.0)
    y10 = load_ust10y()[["date", "close"]].rename(columns={"close": "y10"})
    cpi = load_cpi()[["date", "value"]].rename(columns={"value": "cpi"})
    df = df.merge(y10, on="date", how="left").merge(cpi, on="date", how="left")
    df["y10"] = df["y10"].ffill()
    df["cpi"] = df["cpi"].ffill()
    return df


MARKETS = {
    "hs300": {
        "name": "沪深300",
        "asset": "沪深300全收益指数 H00300（含分红）",
        "pe_desc": "PE-TTM：乐咕乐股（历史日频缓存，更新时月度追加）",
        "percentile": "rolling5y",
        "start_mode": "neutral",
        "start_anchor": "2010-01-01",
        "loader": load_hs300,
    },
    "a500": {
        "name": "中证A500",
        "asset": "中证A500指数 000510（价格指数，未含分红）；仅 2024-09 指数发布后的真实数据，不用回填历史",
        "pe_desc": "PE-TTM：中证官网官方滚动市盈率（2024-09 指数发布起）",
        "percentile": "expanding",
        "start_mode": "data",
        "start_anchor": "2024-09-23",
        "loader": load_a500,
    },
    "hstech": {
        "name": "恒生科技",
        "asset": "恒生科技指数（价格指数 + 官方股息率近似总收益）",
        "pe_desc": "PE-TTM：乐咕乐股/恒生科技官方月度数据",
        "percentile": "expanding",
        "start_mode": "neutral_band",
        "start_anchor": "2020-01-01",
        "loader": load_hstech,
    },
    "ndx": {
        "name": "纳斯达克100",
        "asset": "纳斯达克100指数（价格指数，未含分红）",
        "pe_desc": "估值信号 = 标普500 市盈率（multpl 月度，1871 至今；非纳指自身 PE，因公开源无长史）",
        "percentile": "rolling5y",
        "start_mode": "neutral",
        "start_anchor": "2000-01-03",
        "loader": load_ndx,
    },
    "sp500": {
        "name": "标普500",
        "asset": "标普500指数（价格指数，未含分红）",
        "pe_desc": "PE-TTM：标普500 市盈率（multpl 月度，1871 至今）",
        "percentile": "rolling5y",
        "start_mode": "neutral",
        "start_anchor": "2000-01-03",
        "loader": load_sp500,
    },
    "hsi": {
        "name": "恒生指数",
        "asset": "恒生指数（价格指数 + 官方股息率近似总收益）",
        "pe_desc": "PE-TTM：乐咕乐股/恒生指数官方月度数据（2019-04 起，仅在此后窗口有效）",
        "percentile": "expanding",
        "start_mode": "neutral_band",
        "start_anchor": "2019-01-01",
        "loader": load_hsi,
    },
    "cyb": {
        "name": "创业板指",
        "asset": "创业板指（价格指数，未含分红）",
        "pe_desc": "PE=乐咕『创业板』市场整体市盈率（近似口径，非 399006 自身；月度，2010-06 起）",
        "percentile": "rolling5y",
        "start_mode": "neutral_band",
        "start_anchor": "2014-01-01",
        "loader": load_cyb,
    },
    "kcb50": {
        "name": "科创50",
        "asset": "科创50指数（价格指数，未含分红，2020-07 起交易）",
        "pe_desc": "PE-TTM：中证官网官方滚动市盈率（2020-07 起）",
        "percentile": "expanding",
        "start_mode": "neutral",
        "start_anchor": "2020-01-01",
        "loader": load_kcb50,
    },
    "hldb": {
        "name": "红利低波",
        "asset": "中证红利低波动 H30269（价格指数，未含分红）",
        "pe_desc": "PE-TTM：中证官网官方滚动市盈率（2018-05 起）",
        "percentile": "rolling5y",
        "start_mode": "neutral_band",
        "start_anchor": "2019-06-01",
        "loader": load_hldb,
    },
    "gold": {
        "name": "黄金",
        "asset": "COMEX 黄金期货连续 GC=F（美元/盎司；无股息、无 PE，全部为纯价格策略）",
        "pe_desc": "黄金无 PE/股息/收益，估值无法定义——本页不使用分位，改用价格本身（均线 / 回撤 / 波动率）做信号",
        "percentile": "rolling5y",  # pe_free=True 时该字段不参与
        "start_mode": "fixed",
        "start_date": "2001-06-01",
        "loader": load_gold,
        "pe_free": True,
    },
}


# ---------- 回测引擎 ----------

def stock_daily_ret(df):
    r = df["close"].pct_change().fillna(0)
    if "div_yield" in df.columns:
        r = r + df["div_yield"].fillna(0) / 252.0
    return r


def percentile_series(pe, mode="rolling5y"):
    def pctl(w):
        cur = w[-1]
        if not np.isfinite(cur) or cur <= 0:
            return np.nan
        wv = w[np.isfinite(w) & (w > 0)]
        if len(wv) == 0:
            return np.nan
        return (wv <= cur).mean()

    if mode == "expanding":
        return pe.expanding(min_periods=MIN_PERIODS).apply(pctl, raw=True)
    return pe.rolling(WINDOW, min_periods=MIN_PERIODS).apply(pctl, raw=True)


def backtest(df, position, idle_rate=None):
    if idle_rate is None:
        idle_rate = CASH_RATE
    stock_ret = stock_daily_ret(df)
    prev_pos = position.shift(1).fillna(position.iloc[0])
    daily_ret = prev_pos * stock_ret + (1 - prev_pos) * (idle_rate / 252)
    nav = (1 + daily_ret).cumprod()
    return nav


def strategy_hold(df):
    return pd.Series(1.0, index=df.index), backtest(df, pd.Series(1.0, index=df.index))


def strategy_timing(df, pctl, buy=BUY_PCTL, sell=SELL_PCTL):
    pos = pd.Series(float("nan"), index=df.index)
    pos[pctl < buy] = 1.0
    pos[pctl > sell] = 0.0
    pos = pos.ffill().fillna(1.0)
    return pos, backtest(df, pos)


def strategy_stock_bond(df, weight=STOCK_WEIGHT):
    stock_ret = stock_daily_ret(df)
    bond_ret = BOND_RATE / 252
    stock_val, bond_val = weight, 1 - weight
    navs = []
    month = None
    for d, r in zip(df["date"], stock_ret):
        stock_val *= 1 + r
        bond_val *= 1 + bond_ret
        if (d.year, d.month) != month:
            month = (d.year, d.month)
            total = stock_val + bond_val
            stock_val, bond_val = total * weight, total * (1 - weight)
        navs.append(stock_val + bond_val)
    return pd.Series(navs, index=df.index)


def strategy_ladder(pctl):
    conds = [pctl < 0.1, pctl < 0.3, pctl < 0.5, pctl < 0.7, pctl < 0.9]
    vals = [1.0, 0.8, 0.6, 0.4, 0.2]
    pos = pd.Series(np.select(conds, vals, default=0.0), index=pctl.index)
    pos[pctl.isna()] = 1.0
    return pos


def strategy_trend(df, pctl, buy=0.30, sell=0.80):
    buy_sig = (pctl < buy) & (df["close"] > df["ma250"])
    sell_sig = (pctl > sell) & (df["close"] < df["ma60"])
    pos = pd.Series(np.nan, index=df.index)
    pos[buy_sig] = 1.0
    pos[sell_sig] = 0.0
    return pos.ffill().fillna(1.0)


def strategy_break_buy(df, sell_ma=20, up_days=10, buy_dd=0.20, cooldown=10):
    """纯价格趋势（不看PE）：
    卖：连续 ≥up_days 日站上 MA{sell_ma}（确认先有拉升段），此后收盘跌破 MA 即卖；
    买：从历史高点回撤 ≥buy_dd（如 20%）且距上次卖出 ≥cooldown 个交易日——深跌+间隔，避免接飞刀。
    """
    close = df["close"]
    ma = close.rolling(sell_ma).mean()
    run_max = close.cummax()
    in_mkt, streak, cd = True, 0, 0
    pos = np.zeros(len(df))
    for i in range(len(df)):
        c, m = close.iloc[i], ma.iloc[i]
        if pd.isna(m) or c > m:
            streak += 1
        else:
            if in_mkt and streak >= up_days:
                in_mkt, cd = False, cooldown
            streak = 0
        if not in_mkt:
            cd -= 1
            if cd <= 0 and c / run_max.iloc[i] - 1 <= -buy_dd:
                in_mkt = True
        pos[i] = 1.0 if in_mkt else 0.0
    return pd.Series(pos, index=df.index)


def strategy_cooldown(pctl, buy=0.30, sell=0.90, cooldown_days=126, cooldown_buy=0.20):
    pos, cooldown, out = 1.0, 0, []
    for p in pctl:
        if cooldown > 0:
            cooldown -= 1
            if not pd.isna(p) and p < cooldown_buy:
                pos, cooldown = 1.0, 0
        elif not pd.isna(p):
            if p < buy:
                pos = 1.0
            elif p > sell and pos > 0:
                pos, cooldown = 0.0, cooldown_days
        out.append(pos)
    return pd.Series(out, index=pctl.index)


# ---------- 黄金专用纯价格策略（无 PE，信号都来自价格自身） ----------

def strategy_ma_trend(df, ma=200):
    """单均线趋势：收盘站上 MA{ma} 满仓、跌破空仓（经典 200 日线，无过滤）"""
    return (df["close"] > df["close"].rolling(ma).mean()).astype(float)


def strategy_ma_cross(df, fast=50, slow=200):
    """双均线：快线 > 慢线满仓（金叉）、快线 < 慢线空仓（死叉）"""
    f = df["close"].rolling(fast).mean()
    s = df["close"].rolling(slow).mean()
    return (f > s).astype(float)


def strategy_dip_grid(df, base=0.3, t1=0.08, t2=0.18, t3=0.30):
    """抄底网格·越跌越买（只买不卖）：平时 30% 底仓，距历史高点回撤 ≥8% → 加仓 60%、
    ≥18% → 80%、≥30% → 满仓。留给长牛中左侧上车，不做右侧止损"""
    run_max = df["close"].cummax()
    dd = df["close"] / run_max - 1
    pos = np.where(dd < -t3, 1.0, np.where(dd < -t2, 0.8, np.where(dd < -t1, 0.6, base)))
    return pd.Series(pos, index=df.index)


def strategy_vol_target(df, target=0.12, window=20):
    """波动率目标：仓位 = 目标年化波动 / 滚动{window}日年化波动（cap 100%）——高波动自动降仓"""
    r = df["close"].pct_change()
    vol = r.rolling(window).std() * (252 ** 0.5)
    pos = (target / vol.replace(0, np.nan)).clip(0, 1)
    return pos.fillna(1.0)


def strategy_rate_rotation(df, horizon=252, level=0.5):
    """黄金↔美债轮动：实际利率近似 = 名义 10Y − CPI 同比（month-yoy）。
    实际利率滚动 5 年分位 ≤ level → 持黄金；> level → 持美债（吃息 + 久期价格波动）。不赌金价方向，只吃利差。
    只用当日及之前数据（CPI 滞后发布 + shift 12 个月），无前视"""
    infl = (df["cpi"] / df["cpi"].shift(horizon) - 1).replace([np.inf, -np.inf], np.nan)
    real = df["y10"] - infl * 100.0
    pctl = percentile_series(pd.Series(real, index=df.index))
    pos = (pctl <= level).astype(float)
    return pos.ffill().fillna(1.0)


def backtest_rotation(df, pos, duration=7.0):
    """两资产回测：pos=1 持黄金，pos=0 持美债（票息 3%/年 + 久期×名义 10Y 日变化的价格波动，duration≈7 年）"""
    gold_ret = stock_daily_ret(df)
    bond_ret = pd.Series(BOND_RATE / 252, index=df.index)
    if "y10" in df.columns:
        bond_ret = bond_ret + (-duration * df["y10"].diff().fillna(0) / 100.0)
    prev = pos.shift(1).fillna(pos.iloc[0])
    daily = prev * gold_ret + (1 - prev) * bond_ret
    return (1 + daily).cumprod()


def human_overlay(df, pos, floor=0.0, step=None, monthly_signal=False):
    cur, tgt, month = None, pos.iloc[0], None
    out = []
    for i in range(len(df)):
        d = df["date"].iloc[i]
        new_month = (d.year, d.month) != month
        if new_month:
            month = (d.year, d.month)
        if not monthly_signal or new_month:
            tgt = pos.iloc[i]
        if step is None:
            cur = tgt
        elif cur is None or new_month:
            cur = tgt if cur is None else cur + float(np.clip(tgt - cur, -step, step))
        out.append(max(cur, floor))
    return pd.Series(out, index=df.index)


def flow_target(df, target_pos, income=INCOME):
    stock, pool, totals, flows = 0.0, 0.0, [], []
    month = None
    rets = stock_daily_ret(df).values
    tpos = target_pos.values
    for i in range(len(df)):
        stock *= 1 + rets[i]
        pool *= 1 + CASH_RATE / 252
        d = df["date"].iloc[i]
        if (d.year, d.month) != month:
            month = (d.year, d.month)
            pool += income
            flows.append((d, -income))
            delta = tpos[i] * (stock + pool) - stock
            delta = min(delta, pool) if delta > 0 else delta
            stock += delta
            pool -= delta
        totals.append(stock + pool)
    flows.append((df["date"].iloc[-1], totals[-1]))
    return pd.Series(totals, index=df.index), flows


def flow_inject(df, pctl, amount_fn, income=INCOME):
    stock, pool, totals, flows = 0.0, 0.0, [], []
    month = None
    rets = stock_daily_ret(df).values
    for i in range(len(df)):
        stock *= 1 + rets[i]
        pool *= 1 + CASH_RATE / 252
        d = df["date"].iloc[i]
        if (d.year, d.month) != month:
            month = (d.year, d.month)
            pool += income
            flows.append((d, -income))
            buy = min(max(amount_fn(pctl.iloc[i], pool, income), 0.0), pool)
            stock += buy
            pool -= buy
        totals.append(stock + pool)
    flows.append((df["date"].iloc[-1], totals[-1]))
    return pd.Series(totals, index=df.index), flows


def flow_dip(df, deploy_fn, income=INCOME):
    """Buy The Dip 流量版：每月工资攒进货基池，只按「指数距历史高点回撤幅度」加仓，只买不卖。"""
    stock, pool, totals, flows = 0.0, 0.0, [], []
    month = None
    rets = stock_daily_ret(df).values
    close = df["close"].values
    run_max = pd.Series(close).cummax().to_numpy()
    for i in range(len(df)):
        stock *= 1 + rets[i]
        pool *= 1 + CASH_RATE / 252
        d = df["date"].iloc[i]
        if (d.year, d.month) != month:
            month = (d.year, d.month)
            pool += income
            flows.append((d, -income))
            dd = close[i] / run_max[i] - 1.0
            buy = min(max(deploy_fn(pool, dd), 0.0), pool)
            stock += buy
            pool -= buy
        totals.append(stock + pool)
    flows.append((df["date"].iloc[-1], totals[-1]))
    return pd.Series(totals, index=df.index), flows


def dip_amount(pool, dd):
    """平时不买（回撤<5%），跌幅越深越猛抄（只买不卖）：
    回撤≥5% 投池子15%、≥10% 投40%、≥20% 投70%、≥30% 近乎满仓抄。"""
    if dd <= -0.30:
        return pool
    if dd <= -0.20:
        return pool * 0.7
    if dd <= -0.10:
        return pool * 0.4
    if dd <= -0.05:
        return pool * 0.15
    return 0.0


def smart_amount(p, pool, income):
    return income if pd.isna(p) else income * max(0.0, 2 * (1 - p))


def pool_amount(p, pool, income):
    if pd.isna(p):
        return income
    if p > 0.8:
        return 0.0
    if p > 0.5:
        return income
    if p > 0.2:
        return income + 0.1 * pool
    return 2 * income + 0.2 * pool


def xirr(flows):
    d0 = flows[0][0]

    def npv(r):
        return sum(a / (1 + r) ** ((d - d0).days / 365) for d, a in flows)

    lo, hi = -0.99, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def longest_true(mask):
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def metrics(nav, pos=None, bench=None):
    days = len(nav)
    total = nav.iloc[-1] / nav.iloc[0] - 1
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (252 / days) - 1
    ret = nav.pct_change().dropna()
    vol = ret.std() * (252 ** 0.5)
    sharpe = (cagr - CASH_RATE) / vol if vol > 1e-8 else None
    dd = (nav / nav.cummax() - 1).min()
    m = {"total": total, "cagr": cagr, "mdd": dd, "vol": vol, "sharpe": sharpe}
    if pos is not None:
        m["trades"] = int((pos.diff().abs() > 0).sum())
        m["cash_pct"] = float((pos == 0).mean())
        m["avg_pos"] = float(pos.mean())
        m["cash_streak"] = longest_true((pos <= 0.3).tolist())
    if bench is not None:
        rel = nav / bench
        m["underperf_days"] = longest_true((rel < rel.cummax() - 1e-12).tolist())
    return m


# ---------- 跑单个指数 ----------

def _js_num(values, nd=4):
    return [None if pd.isna(v) else round(float(v), nd) for v in values]


def run_index(key, cfg):
    if cfg.get("pe_free"):
        return run_gold(key, cfg)
    buy_p = BUY_PCTL
    sell_p = SELL_PCTL
    df_full = cfg["loader"]()
    pctl_full = percentile_series(df_full["pe"], mode=cfg["percentile"])
    anchor = df_full["date"] >= cfg.get("start_anchor", "1900-01-01")
    mode = cfg.get("start_mode", "neutral")
    if mode == "neutral":
        neutral = df_full.index[anchor & (pctl_full <= 0.5)]
        start_date = df_full.loc[neutral[0], "date"] if len(neutral) else df_full.loc[anchor, "date"].iloc[0]
    elif mode == "neutral_band":  # expanding 分位早期噪音大，取首个落在 45%~55% 的中性点
        band = df_full.index[anchor & (pctl_full >= 0.45) & (pctl_full <= 0.55) & df_full["pe"].notna()]
        if len(band):
            start_date = df_full.loc[band[0], "date"]
        else:
            neutral = df_full.index[anchor & (pctl_full <= 0.5) & df_full["pe"].notna()]
            start_date = df_full.loc[neutral[0], "date"] if len(neutral) else df_full.loc[anchor & df_full["pe"].notna(), "date"].iloc[0]
    elif mode == "data":
        start_date = df_full.loc[anchor & df_full["pe"].notna(), "date"].iloc[0]
    else:  # fixed
        start_date = pd.to_datetime(cfg["start_date"])
    mask = df_full["date"] >= start_date
    df = df_full[mask].reset_index(drop=True)
    pctl = pctl_full[mask].reset_index(drop=True)
    df["ma250"] = df_full["close"].rolling(250).mean()[mask].reset_index(drop=True)
    df["ma60"] = df_full["close"].rolling(60).mean()[mask].reset_index(drop=True)
    start_pctl = pctl.iloc[0]
    start_pe = df["pe"].iloc[0]
    print(f"[{cfg['name']}] 起点({mode}): {start_date.date()}, PE {start_pe:.1f}, 分位 {('nan' if pd.isna(start_pctl) else format(start_pctl, '.0%'))}")
    print(f"[{cfg['name']}] 数据区间: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)} 个交易日")

    name = cfg["name"]
    desc = {
        "stock": {k: v.replace("指数", name).replace("沪深300", name) for k, v in STOCK_DESC.items()},
        "flow": {k: v.replace("指数", name).replace("沪深300", name) for k, v in FLOW_DESC.items()},
    }

    _, nav_hold = strategy_hold(df)
    pos_t, nav_timing = strategy_timing(df, pctl)
    nav_sb = strategy_stock_bond(df)
    pos_a1 = strategy_ladder(pctl)
    nav_a1 = backtest(df, pos_a1, idle_rate=(CASH_RATE + BOND_RATE) / 2)
    pos_b1 = strategy_trend(df, pctl, sell=0.90)
    nav_b1 = backtest(df, pos_b1)
    pos_c0, nav_c0 = strategy_timing(df, pctl, buy=0.30, sell=0.90)
    pos_h2 = human_overlay(df, pos_c0, floor=0.3)
    nav_h2 = backtest(df, pos_h2)
    pos_e1, nav_e1 = strategy_timing(df, pctl, buy=0.50, sell=0.90)
    pos_v1 = strategy_break_buy(df)
    nav_v1 = backtest(df, pos_v1)
    nav_cash = pd.Series([(1 + CASH_RATE / 252) ** i for i in range(len(df))], index=df.index)

    one = pd.Series(1.0, index=df.index)
    flow_runs = {
        "普通定投(立即投)": flow_target(df, one),
        "PE·30买90卖·流量版": flow_target(df, pos_c0),
        "PE·20买80卖·流量版": flow_target(df, pos_t),
        "阶梯仓位·流量版": flow_target(df, pos_a1),
        "趋势确认·流量版": flow_target(df, pos_b1),
        "30买90卖·30%底仓·流量版": flow_target(df, pos_h2),
        "PE·50%买90%卖·流量版": flow_target(df, pos_e1),
        "破线卖·深跌买·流量版": flow_target(df, pos_v1),
        "智能定投": flow_inject(df, pctl, smart_amount),
        "资金池跨期调配": flow_inject(df, pctl, pool_amount),
        "Buy The Dip·流量版": flow_dip(df, dip_amount),
    }
    n_months = len(flow_runs["普通定投(立即投)"][1]) - 1
    income_total = n_months * INCOME
    cum_income = []
    m = None
    acc = 0.0
    for d in df["date"]:
        if (d.year, d.month) != m:
            m = (d.year, d.month)
            acc += INCOME
        cum_income.append(acc / 1e4)
    flow_table = {}
    flow_curves = {}
    for fname, (totals, flows) in flow_runs.items():
        flow_curves[fname] = (totals / 1e4).round(2).tolist()
        flow_table[fname] = {
            "final": round(float(totals.iloc[-1]) / 1e4, 1),
            "ret": round(float(totals.iloc[-1] / income_total - 1), 4),
            "xirr": round(xirr(flows), 4),
        }

    trades = []
    for i in df.index[pos_t.diff().fillna(0) != 0]:
        trades.append({
            "date": df.loc[i, "date"].strftime("%Y-%m-%d"),
            "action": "买" if pos_t[i] > 0 else "卖",
            "pe": round(float(df.loc[i, "pe"]), 2),
            "pctl": round(float(pctl[i]), 3),
            "nav": round(float(nav_timing[i]), 3),
        })

    stats = {
        "满仓躺平": metrics(nav_hold),
        "PE·30买90卖": metrics(nav_c0, pos_c0, nav_hold),
        f"PE·{buy_p:.0%}买{sell_p:.0%}卖": metrics(nav_timing, pos_t, nav_hold),
        f"股{int(STOCK_WEIGHT*10)}债{10-int(STOCK_WEIGHT*10)}·月再平衡": metrics(nav_sb),
        "阶梯仓位·越便宜越重仓": metrics(nav_a1, pos_a1, nav_hold),
        "趋势确认·30买90卖": metrics(nav_b1, pos_b1, nav_hold),
        "30买90卖·30%底仓": metrics(nav_h2, pos_h2, nav_hold),
        "PE·50%买90%卖": metrics(nav_e1, pos_e1, nav_hold),
        "破线卖·深跌买（纯价格）": metrics(nav_v1, pos_v1, nav_hold),
        "货币基金": metrics(nav_cash),
    }

    _extra = ""
    if "cape" in df_full.columns:
        _c = df_full["cape"].dropna()
        if len(_c):
            _extra = f"席勒CAPE（美股整体）现值 {_c.iloc[-1]:.1f}"
    _sp_pe = df["pe"].iloc[0]
    _sp_pctl = pctl.iloc[0]

    out = {
        "name": name,
        "asset": cfg["asset"],
        "pe_desc": cfg["pe_desc"],
        "pct_desc": "滚动 5 年（1250 个交易日）窗口，约 250 个交易日起才出信号" if cfg["percentile"] == "rolling5y" else "上市以来 expanding 窗口，约 250 个交易日起才出信号",
        "pct_explain": "每个交易日把当天 PE 与最近 5 年（1250 个交易日）的 PE 比大小取排名——分位是「近 5 年的相对贵贱」，不是绝对估值高低（PE 绝对值不高也可能排到历史高位）" if cfg["percentile"] == "rolling5y" else "每个交易日把当天 PE 与上市以来所有 PE 比大小取排名——分位是「历史以来的相对贵贱」，不是绝对估值高低",
        "start_mode": cfg.get("start_mode", "neutral"),
        "start": df["date"].iloc[0].strftime("%Y-%m-%d"),
        "end": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "days": len(df),
        "start_pe": float(_sp_pe) if not pd.isna(_sp_pe) else None,
        "start_pctl": float(_sp_pctl) if not pd.isna(_sp_pctl) else None,
        "extra": _extra,
        "lesson": LESSONS.get(name, ""),
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "series": {
            "满仓躺平": nav_hold.round(4).tolist(),
            "PE·30买90卖": nav_c0.round(4).tolist(),
            "PE·20买80卖": nav_timing.round(4).tolist(),
            "股7债3·月再平衡": nav_sb.round(4).tolist(),
            "阶梯仓位·越便宜越重仓": nav_a1.round(4).tolist(),
            "趋势确认·30买90卖": nav_b1.round(4).tolist(),
            "30买90卖·30%底仓": nav_h2.round(4).tolist(),
            "PE·50%买90%卖": nav_e1.round(4).tolist(),
            "破线卖·深跌买（纯价格）": nav_v1.round(4).tolist(),
            "货币基金": nav_cash.round(4).tolist(),
        },
        "flow": {
            "curves": flow_curves,
            "income": [round(v, 2) for v in cum_income],
            "income_total": round(income_total / 1e4, 1),
            "table": flow_table,
        },
        "pe": _js_num(df["pe"], 2),
        "pctl": _js_num(pctl),
        "trades": trades,
        "stats": {k: {kk: round(vv, 4) if vv is not None else None for kk, vv in v.items()} for k, v in stats.items()},
        "desc": desc,
    }
    return out, stats


GOLD_FLOW_DESC = {
    "普通定投(立即投)": "每月发工资 1 万，当天立刻买入黄金，不择时不等待。",
    "趋势·200日线·流量版": "工资版 200 日单均线趋势：站上均线跟着买、跌破均线攒进货基池。",
    "双均线50/200·流量版": "工资版金叉死叉：50/200 均线金叉时投入、死叉时攒池。",
    "抄底网格·流量版": "工资版抄底网格：平时小额买，黄金从历史高点回撤越深，当月投入比例越高（只买不卖）。",
    "波动率目标·流量版": "工资版波动率目标：按目标年化波动反推仓位，高波动期少买多攒。",
    "破线卖·深跌买·流量版": "工资版纯价格趋势（破线卖·深跌买）：按该信号决定总资产的黄金比例，增量工资自动跟随。",
    "黄金↔美债轮动·流量版": "工资版美债轮动：实际利率（名义10Y−CPI同比）偏高时把增量攒进美债吃息，实际利率偏低时买黄金。",
    "Buy The Dip·流量版": "工资先攒进货基池，平时不买；买点只认「金价距历史高点回撤」：回撤 ≥5% 投 15%、≥10% 投 40%、≥20% 投 70%、≥30% 近乎满仓——只买不卖。",
}

GOLD_STOCK_DESC = {
    "满仓躺平": "买入持有黄金，不择时不卖。",
    "货币基金": "全程 2%/年货基——所有择时策略空仓资金的比较基准（零息资产的机会成本）。",
    "金7债3·月再平衡": "70% 黄金 + 30% 债基（3%/年），每月再平衡——不择时，纯降波动，适合把黄金当组合压舱。",
    "趋势·站上200日线": "经典单均线 CTA：收盘站上 200 日均线就满仓持有、跌破就清仓转货基。中期趋势拐点反应慢、但过滤大部分噪音。",
    "双均线50/200·金叉死叉": "50 日上穿 200 日（金叉）满仓、下穿（死叉）空仓：比 200 日单线更早确认趋势，代价是假信号更多。",
    "抄底网格·越跌越买": "只买不卖：平时 30% 底仓，距历史高点回撤 ≥8% 加仓到 60%、≥18% 到 80%、≥30% 满仓——左侧抄底，赌的是黄金长牛。",
    "波动率目标·控波动": "把年化波动压到 12%：仓位 = 12% / 20 日实际年化波动（上限满仓）——波动越大仓位越低，专治优化高波动。",
    "黄金↔美债轮动": "实际利率近似 = 名义 10Y（Yahoo ^TNX）− CPI 同比（multpl 月频）：实际利率滚动 5 年分位 ≤50% 持黄金、>50% 持美债（票息 3%/年 + 久期≈7 年×名义利率变动的价格波动）——不赌金价方向，只切换'零息黄金 vs 生息美债'。",
    "破线卖·深跌买（纯价格）": "连续 ≥10 日站上 20 日均线后跌破即卖；从历史高点回撤 ≥20% 且距上次卖出 ≥10 日再买回——与其他页面横评的同款纯价格策略。",
}


def run_gold(key, cfg):
    """黄金页：无 PE，纯价格策略。起点 fixed（无估值中性锚可选），策略见 GOLD_STOCK_DESC"""
    name = cfg["name"]
    df_full = cfg["loader"]()
    start_date = pd.to_datetime(cfg.get("start_date"))
    f = df_full["date"] >= start_date
    df = df_full[f].reset_index(drop=True)
    df["ma250"] = df_full["close"].rolling(250).mean()[f].reset_index(drop=True)
    df["ma60"] = df_full["close"].rolling(60).mean()[f].reset_index(drop=True)
    print(f"[{name}] 起点(fixed, 无估值锚): {start_date.date()}")
    print(f"[{name}] 数据区间: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)} 个交易日")

    _, nav_hold = strategy_hold(df)
    nav_cash = pd.Series([(1 + CASH_RATE / 252) ** i for i in range(len(df))], index=df.index)
    nav_sb = strategy_stock_bond(df)
    nav_ma = backtest(df, strategy_ma_trend(df))
    nav_cr = backtest(df, strategy_ma_cross(df))
    nav_grid = backtest(df, strategy_dip_grid(df))
    nav_vol = backtest(df, strategy_vol_target(df))
    pos_v1 = strategy_break_buy(df)
    nav_v1 = backtest(df, pos_v1)
    pos_rot = strategy_rate_rotation(df)
    nav_rot = backtest_rotation(df, pos_rot)

    navs = {
        "满仓躺平": nav_hold,
        "货币基金": nav_cash,
        "金7债3·月再平衡": nav_sb,
        "趋势·站上200日线": nav_ma,
        "双均线50/200·金叉死叉": nav_cr,
        "抄底网格·越跌越买": nav_grid,
        "波动率目标·控波动": nav_vol,
        "黄金↔美债轮动": nav_rot,
        "破线卖·深跌买（纯价格）": nav_v1,
    }
    pos_lut = {
        "趋势·站上200日线": strategy_ma_trend(df),
        "双均线50/200·金叉死叉": strategy_ma_cross(df),
        "抄底网格·越跌越买": strategy_dip_grid(df),
        "波动率目标·控波动": strategy_vol_target(df),
        "黄金↔美债轮动": pos_rot,
        "破线卖·深跌买（纯价格）": pos_v1,
    }
    stats = {
        "满仓躺平": metrics(nav_hold),
        "货币基金": metrics(nav_cash),
        "金7债3·月再平衡": metrics(nav_sb),
    }
    for k, p in pos_lut.items():
        stats[k] = metrics(navs[k], p, nav_hold)

    one = pd.Series(1.0, index=df.index)
    pos_ma = pos_lut["趋势·站上200日线"]
    pos_cr = pos_lut["双均线50/200·金叉死叉"]
    pos_grid = pos_lut["抄底网格·越跌越买"]
    pos_vol = pos_lut["波动率目标·控波动"]
    pos_rot = pos_lut["黄金↔美债轮动"]
    flow_runs = {
        "普通定投(立即投)": flow_target(df, one),
        "趋势·200日线·流量版": flow_target(df, pos_ma),
        "双均线50/200·流量版": flow_target(df, pos_cr),
        "抄底网格·流量版": flow_target(df, pos_grid),
        "波动率目标·流量版": flow_target(df, pos_vol),
        "黄金↔美债轮动·流量版": flow_target(df, pos_rot),
        "破线卖·深跌买·流量版": flow_target(df, pos_v1),
        "Buy The Dip·流量版": flow_dip(df, dip_amount),
    }
    n_months = len(flow_runs["普通定投(立即投)"][1]) - 1
    income_total = n_months * INCOME
    cum_income, m, acc = [], None, 0.0
    for d in df["date"]:
        if (d.year, d.month) != m:
            m = (d.year, d.month)
            acc += INCOME
        cum_income.append(acc / 1e4)
    flow_table, flow_curves = {}, {}
    for fname, (totals, flows) in flow_runs.items():
        flow_curves[fname] = (totals / 1e4).round(2).tolist()
        flow_table[fname] = {
            "final": round(float(totals.iloc[-1]) / 1e4, 1),
            "ret": round(float(totals.iloc[-1] / income_total - 1), 4),
            "xirr": round(xirr(flows), 4),
        }

    out = {
        "name": name,
        "asset": cfg["asset"],
        "pe_desc": cfg["pe_desc"],
        "pct_desc": "黄金无 PE，不使用估值分位——策略信号全部来自价格自身（200 日均线趋势 / 50-200 金叉死叉 / 历史高点回撤 / 20 日波动率）",
        "pct_explain": "黄金是零息资产，没有盈利和估值可言，任何用 PE/分位判断贵贱的逻辑都不适用；本页用「价格和它的均线、回撤、波动率」做机械信号（严格只用当日及之前数据，无前视）。",
        "start_mode": cfg.get("start_mode", "fixed"),
        "start": df["date"].iloc[0].strftime("%Y-%m-%d"),
        "end": df["date"].iloc[-1].strftime("%Y-%m-%d"),
        "days": len(df),
        "start_pe": None,
        "start_pctl": None,
        "extra": f"COMEX 黄金现价 ${df['close'].iloc[-1]:,.0f}/盎司（数据截至 {df['date'].iloc[-1].date()}）",
        "lesson": LESSONS.get(name, ""),
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "series": {k: v.round(4).tolist() for k, v in navs.items()},
        "flow": {
            "curves": flow_curves,
            "income": [round(v, 2) for v in cum_income],
            "income_total": round(income_total / 1e4, 1),
            "table": flow_table,
        },
        "pe": [None] * len(df),
        "pctl": [None] * len(df),
        "trades": [],
        "stats": {k: {kk: round(vv, 4) if vv is not None else None for kk, vv in v.items()} for k, v in stats.items()},
        "desc": {"stock": GOLD_STOCK_DESC, "flow": GOLD_FLOW_DESC},
    }
    return out, stats


def main():
    indices = {}
    for key, cfg in MARKETS.items():
        out, stats = run_index(key, cfg)
        indices[key] = out
        print()
        for k, v in stats.items():
            print(k, {kk: (f"{vv:.2%}" if isinstance(vv, float) and kk not in ("sharpe",) else vv) for kk, vv in v.items()})
        print("工资流实验:", out["flow"]["table"])
        print("-" * 60)
    render(indices)


def render(indices):
    tpl_path = os.path.join(os.path.dirname(__file__), "template.html")
    with open(tpl_path, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("__DATA__", json.dumps({"indices": indices}, ensure_ascii=False))
    out_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {out_path}")


def _P(name):
    return os.path.join(DATA_DIR, name)


def _slice_fresh(df):
    """取 loader 结果中最新的价格/PE 日期（消除首次的 NaN 行）"""
    px = df.loc[:, "date"].max()
    pe = df.loc[df["pe"].notna(), "date"]
    return px, (pe.max() if len(pe) else None)


def refresh_all():
    """全量重拉各数据源并入缓存；失败自动保留旧缓存。输出逐文件状态 + 每指数新鲜度表"""
    today = pd.Timestamp.today().normalize()
    print("== 刷新数据缓存（失败自动保留旧缓存） ==")
    report = {}

    def step(name, fn):
        try:
            df = fn()
            report[name] = df
            col = "date" if "date" in df.columns else "日期"
            last = pd.to_datetime(df[col]).max()
            print(f"  [{name}] ok  last={last.date()}")
        except Exception as e:
            report[name] = None
            print(f"  [{name}] FAIL {type(e).__name__}: {e}")

    def save(path, df):
        df.to_csv(path, index=False)
        return df

    def csindex_raw(symbol, start):
        """kcb50/hldb 缓存保持 load_csindex 期望的原始列结构（日期/收盘/滚动市盈率…）"""
        import akshare as ak
        return ak.stock_zh_index_hist_csindex(symbol=symbol, start_date=start, end_date="20991231")

    def hs300_job():
        raw = csindex_raw("H00300", "20050101")
        px = pd.DataFrame({"date": pd.to_datetime(raw["日期"]), "close": raw["收盘"].astype(float)})
        save(_P("hs300_price.csv"), px)
        _merge_cache(_P("hs300_pe.csv"), legu_index_pe("000300.SH", "https://legulegu.com/stockdata/sz50-ttm-lyr"))
        return px

    step("hs300(价格+PE月度追加)", hs300_job)
    step("a500", lambda: save(_P("a500.csv"), csindex_raw("000510", "20240923")))
    step("hstech_price", lambda: save(_P("hstech_price.csv"), sina_hk_daily("HSTECH")))
    step("hstech_pe(月度)", lambda: save(_P("hstech_pe.csv"), legu_hsidata("HSTECH")))
    step("ndx_price", lambda: fetch_yahoo_daily("%5ENDX", _P("ndx_price.csv")))
    step("ndx_pe(标普500/月度)", lambda: multpl_monthly_pe(_P("ndx_pe.csv"), "s-p-500-pe-ratio"))
    step("ndx_cape", lambda: multpl_monthly_pe(_P("ndx_cape.csv"), "shiller-pe"))
    step("sp500_price", lambda: fetch_yahoo_daily("%5EGSPC", _P("sp500_price.csv")))
    step("sp500_pe", lambda: multpl_monthly_pe(_P("sp500_pe.csv"), "s-p-500-pe-ratio"))
    step("hsi_price", lambda: fetch_yahoo_daily("%5EHSI", _P("hsi_price.csv"), start_year=1986))
    step("hsi_pe(月度)", lambda: save(_P("hsi_pe.csv"), legu_hsidata("HSI")))
    step("cyb_price", lambda: save(_P("cyb_price.csv"), sina_index_daily("sz399006")))
    step("cyb_pe(月度)", lambda: save(_P("cyb_pe.csv"), legu_market_pe("4", "https://legulegu.com/stockdata/cybPE")))
    step("kcb50", lambda: save(_P("kcb50.csv"), csindex_raw("000688", "20190101")))
    step("gold_price", lambda: fetch_yahoo_daily("GC%3DF", _P("gold_price.csv"), start_year=2000))
    step("ust10y", lambda: fetch_yahoo_daily("%5ETNX", _P("ust10y.csv"), start_year=2000))
    step("cpi(月)", lambda: multpl_monthly_pe(_P("cpi.csv"), "cpi"))
    step("hldb", lambda: save(_P("hldb.csv"), csindex_raw("H30269", "20180101")))

    print()
    print(f"{'指数':<10}{'价格最新':<12}{'PE最新':<12}{'落后(天)':<8}")
    for key, cfg in MARKETS.items():
        try:
            df = cfg["loader"]()
            px_last, pe_last = _slice_fresh(df)
            lag = (today - pd.Timestamp(px_last)).days
            flag = " ✓" if lag <= 5 else " ⚠"
            pe_s = str(pd.Timestamp(pe_last).date()) if pe_last is not None else "-"
            print(f"{cfg['name']:<10}{str(pd.Timestamp(px_last).date()):<12}{pe_s:<12}{lag:<8}{flag}")
        except Exception as e:
            print(f"{cfg['name']:<10}读取失败 {type(e).__name__}: {e}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--update-data" in args or "--update" in args:
        refresh_all()
        if "--update-only" in args:
            sys.exit(0)
    main()
