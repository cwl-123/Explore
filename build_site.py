#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Explore 个人金融探索站 —— 静态门户生成器（仅用标准库）

用法：
    python3 build_site.py            # 生成门户 index.html + 给每个报告页注入顶部导航
    python3 build_site.py --no-nav   # 只生成门户，不改动报告页

新增内容（3 步）：
    1. 把报告 HTML / 图片放进仓库（图片放 images/）
    2. 在下面 REGISTRY 里加一条记录（title / path / category / tags / summary）
    3. 运行 python3 build_site.py

说明：
    - 门户首页 = 仓库根目录 index.html（分类分区 + 卡片）
    - 各报告页顶部由本脚本注入统一导航（幂等：重复运行不会叠加）
    - 报告页如果是生成产物（如 index.html / *_view.html），重新生成后需再跑一次本脚本
"""

from __future__ import annotations

import os
import re
import sys
import html
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 分类（顺序即门户展示顺序；新增分类在此追加即可）
# ---------------------------------------------------------------------------
CATEGORIES = [
    ("strategy", "指数策略回测", "用长历史数据检验买卖规则与估值择时", "#2f6fed"),
    ("valuation", "估值 · 持仓分析", "指数 / ETF / 基金成分股与估值拆解", "#2c9e63"),
    ("topics", "市场专题", "一个命题、一组图，用数据给答案", "#e0a300"),
    ("gallery", "图表速览", "独立图表与图片", "#d94a4a"),
]
CAT_LABEL = {key: label for key, label, _, _ in CATEGORIES}
CAT_COLOR = {key: color for key, _, _, color in CATEGORIES}

# ---------------------------------------------------------------------------
# 内容注册表（唯一事实来源：新增报告 / 图片只改这里）
#   path    : 相对仓库根目录的路径（报告 HTML 或图片）
#   kind    : "report"（默认）或 "image"
#   date    : 展示用的数据/产出月份（可省略）
# ---------------------------------------------------------------------------
REGISTRY = [
    # —— 指数策略回测 ——
    dict(
        title="指数策略对比 · 多指数回测",
        path="hs300-strategy-lab/index.html",
        category="strategy",
        tags=["估值择时", "回测", "多指数"],
        summary="在沪深300 / 恒生科技 / 纳指100 / 标普500 / 恒生 / 创业板 / 科创50 / 红利低波 / 中证A500 / 黄金 上，"
                "横评低买高卖、躺平、组合搭配等策略的长历史表现。",
        date="2026-10",
    ),
    # —— 估值 · 持仓分析 ——
    dict(
        title="恒生指数 (HSI) 成分股与估值报告",
        path="hsi-valuation.html",
        category="valuation",
        tags=["恒指", "成分股", "PE", "股息率"],
        summary="恒生指数 95 只成分股的估值与股息率拆解（官方月度 PE-TTM / 股息率），识别高息、低估标的。",
        date="2026-10",
    ),
    dict(
        title="中概互联 ETF (513050) 重仓股估值报告",
        path="china-internet-valuation.html",
        category="valuation",
        tags=["中概互联", "ETF", "估值"],
        summary="易方达中概互联网 ETF 重仓股估值报告，看龙头相对贵贱。",
        date="2026-09",
    ),
    dict(
        title="化工ETF (012538) 还能拿吗？",
        path="etf-012538-analysis/index.html",
        category="valuation",
        tags=["化工ETF", "成分股", "估值"],
        summary="华宝细分化工产业主题 ETF 的成分股、估值与配置逻辑全拆解（跟踪 000813，50 只成分股）。",
        date="2026-09",
    ),
    dict(
        title="有色矿业 018168 · 成分股拆解与持有逻辑",
        path="fund-018168/index.html",
        category="valuation",
        tags=["有色", "基金", "成分股"],
        summary="有色矿业主题基金 018168 的成分股拆解与持有逻辑。",
        date="2026-09",
    ),
    dict(
        title="电网设备主题基金 (025833) 还能拿吗？",
        path="fund-025833/index.html",
        category="valuation",
        tags=["电网设备", "基金", "光纤"],
        summary="天弘中证电网设备主题 C，光纤含量、估值与持有逻辑（跟踪 931994）。",
        date="2026-09",
    ),
    # —— 市场专题 ——
    dict(
        title="存储股崩盘：三星/海力士还值得投资吗？",
        path="memory-crash-2026/index.html",
        category="topics",
        tags=["存储周期", "三星", "海力士", "回撤"],
        summary="AI 存储超级周期见顶后的板块性崩盘：韩股 vs 美股 vs A股存储链对比，"
                "用 10 年周期数据判断短调还是长熊。",
        date="2026-10",
    ),
    dict(
        title="费城半导体 (SOX) 怎么看 · 2026年10月体检",
        path="sox-semiconductor.html",
        category="topics",
        tags=["费城半导体", "SOX", "估值", "情景分析"],
        summary="直接回答：现在是涨是跌（长涨中跌短崩）、估值贵吗（远期18x不贵但有条件）、跌在哪（NVDA以外普跌）、"
                "是底吗/能抄吗（历史同位置12个月胜率90%）、要割肉吗、历史像哪次，附四种情景概率。",
        date="2026-10",
    ),
    dict(
        title="A股这轮下跌怎么看 · 2026年10月体检",
        path="hs300-strategy-lab/ashare_drop.html",
        category="topics",
        tags=["A股", "回撤", "估值", "情景分析"],
        summary="跌在哪（科技 -32% vs 红利 +6%）、贵不贵（分位 70%）、是不是底、高仓位怎么办，"
                "附历史类比与四种情景概率。",
        date="2026-10",
    ),
    dict(
        title="沪深300 现在怎么看 · 数据判读",
        path="hs300-strategy-lab/hs300_view.html",
        category="topics",
        tags=["沪深300", "分位", "判读"],
        summary="沪深300 当前估值与买卖点判读（H00300 全收益 · 乐咕 PE-TTM · 滚动 5 年分位，无前视）。",
        date="2026-09",
    ),
    dict(
        title="黄金 -21% 回撤：持有、卖出还是加仓？",
        path="hs300-strategy-lab/gold_now.html",
        category="topics",
        tags=["黄金", "回撤", "择时"],
        summary="用 26 年数据回答黄金深度回撤后该怎么办。",
        date="2026-09",
    ),
    dict(
        title="「盈利涨 30%、股价只涨 20%」差的 10% 会补涨吗？",
        path="hs300-strategy-lab/earn_price.html",
        category="topics",
        tags=["盈利", "估值", "恒等式"],
        summary="用估值恒等式分解净利润与股价的关系，检验「补涨」命题。",
        date="2026-09",
    ),
    dict(
        title="创业板 / 红利「矛与盾」比值择时",
        path="hs300-strategy-lab/cyb_div_ratio.html",
        category="topics",
        tags=["创业板", "红利", "择时"],
        summary="用创业板红利比值判断、现在在哪 / 什么时候可以再度关注创业板。",
        date="2026-10",
    ),
    dict(
        title="跟随美联储周期投资 A 股，靠谱吗？",
        path="hs300-strategy-lab/fed_cycle.html",
        category="topics",
        tags=["美联储", "周期", "验证"],
        summary="「加息尾声买入、降息尾声卖出」——用 20 年数据验证一个流行命题。",
        date="2026-09",
    ),
    # —— 图表速览（图片）：把图放进 images/ 后按下面格式登记 ——
    # dict(
    #     title="示例图表标题",
    #     path="images/example.png",
    #     category="gallery",
    #     kind="image",
    #     tags=["示例"],
    #     summary="一句话说明这张图揭示了什么。",
    #     date="2026-10",
    # ),
]

SITE_TITLE = "金融探索站"
SITE_SUB = "个人金融研究 · 跑数 / 报告 / 图表 —— 用数据回答投资问题"


# ---------------------------------------------------------------------------
# 顶部导航（注入到各报告页的内容容器内，仅左侧「返回首页」，随页面宽度自然左对齐）
# ---------------------------------------------------------------------------
NAV_START = "<!-- SITE_NAV_START -->"
NAV_END = "<!-- SITE_NAV_END -->"

NAV_CSS = (
    "#site-nav{margin:2px 0 18px;font:13.5px/1.5 -apple-system,BlinkMacSystemFont,"
    "'PingFang SC','Microsoft YaHei',sans-serif;}"
    "#site-nav a{display:inline-flex;align-items:center;gap:7px;text-decoration:none;"
    "color:#6b7686;background:#fff;border:1px solid #e6e9ee;border-radius:999px;"
    "padding:5px 14px 5px 12px;transition:.15s;}"
    "#site-nav a:hover{color:#2f6fed;border-color:#c9d7f5;background:#f5f8ff;}"
    "#site-nav a b{font-weight:600;color:#1c2430;}"
    "#site-nav a:hover b{color:#2f6fed;}"
)

CONTAINER_HINTS = ["page", "wrap", "container", "content", "main", "root"]


def build_nav(rel_home: str) -> str:
    return (
        f'{NAV_START}\n'
        f'<style>{NAV_CSS}</style>\n'
        f'<div id="site-nav"><a href="{rel_home}">← 返回首页 · <b>{SITE_TITLE}</b></a></div>\n'
        f'{NAV_END}'
    )


def _css_rules(style_text: str):
    return re.findall(r"([^{}]+)\{([^{}]*)\}", style_text)


def _has_maxwidth(style_text: str, selector: str) -> bool:
    for sel, rule in _css_rules(style_text):
        if "max-width" not in rule:
            continue
        if selector in [s.strip() for s in sel.split(",")]:
            return True
    return False


def _maxwidth_classes(style_text: str):
    out = set()
    for sel, rule in _css_rules(style_text):
        if "max-width" not in rule:
            continue
        out.update(re.findall(r"\.([A-Za-z0-9_\-]+)", sel))
    return out


def _insert_pos(html_text: str) -> int:
    """返回导航插入位置（内容容器起始处），使导航与正文左对齐。"""
    styles = "".join(re.findall(r"<style[^>]*>(.*?)</style>", html_text, flags=re.S | re.I))
    bm = re.search(r"<body[^>]*>", html_text, flags=re.I)
    if not bm:
        return -1
    end = bm.end()
    # 1) body 自身限宽（正文直接放在 body 内）→ 插在 body 之后
    if _has_maxwidth(styles, "body"):
        return end
    body_html = html_text[end:]
    # 2) 找限宽的内容容器 div（.page / .wrap / ...）
    for name in CONTAINER_HINTS:
        if not _has_maxwidth(styles, "." + name):
            continue
        m = re.search(
            r'<div\b[^>]*\bclass="[^"]*\b' + re.escape(name) + r'\b[^"]*"[^>]*>',
            body_html,
            flags=re.I,
        )
        if m:
            return end + m.end()
    # 3) 兜底：任一「限宽 class」的 div
    mw = _maxwidth_classes(styles)
    for m in re.finditer(r'<div\b[^>]*\bclass="([^"]*)"[^>]*>', body_html, flags=re.I):
        if set(m.group(1).split()) & mw:
            return end + m.end()
    return end


def inject_nav(path: str) -> bool:
    abs_path = os.path.join(ROOT, path)
    if not os.path.isfile(abs_path):
        print(f"  ! 跳过（文件不存在）：{path}")
        return False
    with open(abs_path, encoding="utf-8") as f:
        content = f.read()

    body = re.sub(re.escape(NAV_START) + r".*?" + re.escape(NAV_END), "", content, flags=re.S)
    rel_home = os.path.relpath(os.path.join(ROOT, "index.html"), os.path.dirname(abs_path))
    rel_home = rel_home.replace(os.sep, "/")

    idx = _insert_pos(body)
    if idx < 0:
        print(f"  ! 跳过（无 <body>）：{path}")
        return False
    new = body[:idx] + build_nav(rel_home) + body[idx:]

    if new != content:
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"  ✓ 注入导航：{path}")
        return True
    print(f"  = 导航已是最新：{path}")
    return False


# ---------------------------------------------------------------------------
# 门户首页
# ---------------------------------------------------------------------------
PORTAL_CSS = """
:root{
  --bg:#f6f7f9; --card:#ffffff; --ink:#1c2430; --muted:#6b7686; --line:#e6e9ee; --blue:#2f6fed;
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
  line-height:1.6;-webkit-font-smoothing:antialiased;}
.wrap{max-width:1120px;margin:0 auto;padding:40px 22px 90px;}
header.hero{margin-bottom:34px;}
header.hero .brand{font-size:30px;font-weight:800;letter-spacing:.5px;margin:0 0 8px;}
header.hero .brand span{font-size:14px;font-weight:500;color:var(--muted);letter-spacing:1px;
  margin-left:10px;text-transform:uppercase;}
header.hero .lead{color:var(--muted);font-size:15px;margin:0 0 14px;}
header.hero .stats{font-size:13px;color:#8a93a3;
  border-top:1px solid var(--line);padding-top:14px;}
section{margin-bottom:40px;scroll-margin-top:64px;}
section h2{font-size:19px;margin:0 0 4px;display:flex;align-items:center;gap:9px;}
section h2 .dot{width:10px;height:10px;border-radius:50%;display:inline-block;}
section h2 small{font-size:12.5px;font-weight:400;color:var(--muted);margin-left:6px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-top:16px;}
.card{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:18px 20px;text-decoration:none;color:inherit;
  box-shadow:0 1px 2px rgba(20,30,50,.03);transition:.16s;}
.card:hover{transform:translateY(-2px);box-shadow:0 8px 22px rgba(20,30,50,.10);border-color:#d5dbe6;}
.card .top{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;}
.card .chip{font-size:11.5px;font-weight:600;padding:2px 9px;border-radius:999px;}
.card .date{font-size:12px;color:#9aa3b2;}
.card h3{font-size:16px;margin:0 0 8px;line-height:1.45;}
.card p{margin:0;color:var(--muted);font-size:13.5px;flex:1;}
.card .tags{margin-top:12px;font-size:12px;color:#98a1b0;}
.card .tags span{margin-right:8px;}
.card .go{margin-top:12px;font-size:13px;font-weight:600;color:var(--blue);}
.gallery-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-top:16px;}
.gallery-grid a{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;
  overflow:hidden;text-decoration:none;color:inherit;}
.gallery-grid img{width:100%;height:150px;object-fit:cover;display:block;background:#eef1f5;}
.gallery-grid .cap{padding:10px 12px;font-size:13px;}
.gallery-grid .cap small{color:var(--muted);display:block;margin-top:3px;}
.empty{color:var(--muted);font-size:13.5px;background:var(--card);border:1px dashed var(--line);
  border-radius:14px;padding:18px 20px;margin-top:16px;}
footer{color:#9aa3b2;font-size:12.5px;border-top:1px solid var(--line);padding-top:18px;margin-top:10px;}
"""


def _card(item: dict) -> str:
    cat = item["category"]
    color = CAT_COLOR.get(cat, "#2f6fed")
    tags = "".join(f"<span>#{html.escape(t)}</span>" for t in item.get("tags", []))
    date = html.escape(item.get("date", "")) if item.get("date") else ""
    return (
        f'<a class="card" href="{html.escape(item["path"])}">'
        f'<div class="top">'
        f'<span class="chip" style="color:{color};background:{color}18;">{html.escape(CAT_LABEL.get(cat, cat))}</span>'
        f'<span class="date">{date}</span></div>'
        f'<h3>{html.escape(item["title"])}</h3>'
        f'<p>{html.escape(item.get("summary", ""))}</p>'
        f'<div class="tags">{tags}</div>'
        f'<div class="go">查看报告 →</div>'
        f'</a>'
    )


def _image_card(item: dict) -> str:
    path = html.escape(item["path"])
    cap = html.escape(item.get("summary", ""))
    date = html.escape(item.get("date", ""))
    return (
        f'<a href="{path}" target="_blank">'
        f'<img src="{path}" alt="{html.escape(item["title"])}" loading="lazy">'
        f'<div class="cap">{html.escape(item["title"])}<small>{cap} {date}</small></div>'
        f'</a>'
    )


def build_portal() -> str:
    today = datetime.date.today().isoformat()
    reports = [x for x in REGISTRY if x.get("kind", "report") == "report"]
    images = [x for x in REGISTRY if x.get("kind") == "image"]

    sections = []
    for key, label, desc, color in CATEGORIES:
        if key == "gallery":
            body = (
                f'<div class="gallery-grid">{"".join(_image_card(x) for x in images)}</div>'
                if images
                else '<div class="empty">暂无图片。把图表放进 <code>images/</code>，并在 '
                     '<code>build_site.py</code> 的 REGISTRY 里登记（kind="image"）即可。</div>'
            )
        else:
            items = [x for x in reports if x.get("category") == key]
            body = (
                f'<div class="grid">{"".join(_card(x) for x in items)}</div>'
                if items
                else '<div class="empty">暂无内容。</div>'
            )
        sections.append(
            f'<section id="{key}"><h2><span class="dot" style="background:{color}"></span>'
            f'{html.escape(label)}<small>{html.escape(desc)}</small></h2>{body}</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(SITE_TITLE)} · 个人金融探索</title>
<style>{PORTAL_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="hero">
    <div class="brand">🔍 {html.escape(SITE_TITLE)}<span>Personal Finance Lab</span></div>
    <p class="lead">{html.escape(SITE_SUB)}</p>
    <div class="stats">{len(reports)} 篇报告 · {len(images)} 张图表 · 更新于 {today}</div>
  </header>
  {''.join(sections)}
  <footer>由 <code>build_site.py</code> 生成（注册表驱动）· 新增报告/图片见脚本顶部说明</footer>
</div>
</body>
</html>
"""


def main() -> None:
    do_nav = "--no-nav" not in sys.argv

    if do_nav:
        print("注入报告页导航：")
        for item in REGISTRY:
            if item.get("kind") == "image":
                continue
            inject_nav(item["path"])
    else:
        print("（--no-nav：跳过导航注入）")

    portal_path = os.path.join(ROOT, "index.html")
    with open(portal_path, "w", encoding="utf-8") as f:
        f.write(build_portal())
    n = sum(1 for x in REGISTRY if x.get("kind", "report") == "report")
    print(f"\n门户已生成：index.html（{n} 篇报告）")


if __name__ == "__main__":
    main()