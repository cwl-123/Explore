# -*- coding: utf-8 -*-
"""读取 data/report_data.json，生成单文件 fund-018168/index.html"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "data", "report_data.json"), encoding="utf-8"))

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>有色矿业 018168 · 还能拿吗？</title>
<script src="echarts.min.js"></script>
<script>if (!window.echarts) document.write('<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"><\/script>');</script>
<style>
  :root {
    --bg: #0f1420; --card: #171e2e; --card2: #1d2639; --line: #2a3650;
    --txt: #dce3f0; --sub: #8b97b0; --acc: #e8a33d; --red: #e05c5c;
    --green: #4caf7d; --blue: #5b8def; --purple: #a78bfa;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: var(--bg); color: var(--txt); font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; line-height: 1.7; }
  .wrap { max-width: 1080px; margin: 0 auto; padding: 24px 16px 80px; }
  header { padding: 36px 0 8px; }
  h1 { font-size: 26px; letter-spacing: .5px; }
  h1 .code { color: var(--acc); font-family: Menlo, monospace; }
  .meta { color: var(--sub); font-size: 13px; margin-top: 8px; }
  .meta b { color: var(--txt); font-weight: 600; }
  h2 { font-size: 20px; margin: 44px 0 6px; padding-left: 12px; border-left: 4px solid var(--acc); }
  h3 { font-size: 16px; margin: 22px 0 8px; color: var(--acc); }
  .lead { color: var(--sub); font-size: 14px; margin-bottom: 14px; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; margin: 14px 0; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(158px, 1fr)); gap: 10px; margin: 16px 0; }
  .kpi { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
  .kpi .v { font-size: 22px; font-weight: 700; font-family: Menlo, monospace; }
  .kpi .k { color: var(--sub); font-size: 12px; margin-top: 2px; }
  .up { color: var(--red); } .down { color: var(--green); } .flat { color: var(--txt); }
  .chart { width: 100%; height: 400px; }
  .chart-tall { height: 440px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { padding: 8px 10px; text-align: right; border-bottom: 1px solid var(--line); white-space: nowrap; }
  th { color: var(--sub); font-weight: 500; position: sticky; top: 0; background: var(--card); }
  td:first-child, th:first-child, td:nth-child(2), th:nth-child(2) { text-align: left; }
  tr:hover td { background: var(--card2); }
  .tablewrap { overflow-x: auto; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 20px; font-size: 12px; }
  .tag.cheap { background: rgba(76,175,125,.15); color: var(--green); }
  .tag.mid { background: rgba(232,163,61,.15); color: var(--acc); }
  .tag.exp { background: rgba(224,92,92,.15); color: var(--red); }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 760px) { .cols { grid-template-columns: 1fr; } }
  .logic { border-left: 3px solid var(--line); padding: 4px 0 4px 14px; margin: 10px 0; }
  .logic.good { border-color: var(--green); } .logic.bad { border-color: var(--red); }
  .logic b.t { display: block; margin-bottom: 2px; }
  .logic.good b.t { color: var(--green); } .logic.bad b.t { color: var(--red); }
  .logic span { color: var(--sub); font-size: 13.5px; }
  .note { color: var(--sub); font-size: 12.5px; margin-top: 8px; }
  .hl { color: var(--acc); font-weight: 600; }
  .chain { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 12px 0; }
  .chain .step { background: var(--card2); border: 1px solid var(--line); border-radius: 8px; padding: 8px 14px; font-size: 13.5px; }
  .chain .arrow { color: var(--acc); font-size: 18px; }
  .signal-list li { margin: 6px 0 6px 18px; font-size: 14px; }
  footer { margin-top: 60px; padding-top: 18px; border-top: 1px solid var(--line); color: var(--sub); font-size: 12px; }
  .pill-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
  .pill { background: var(--card2); border: 1px solid var(--line); border-radius: 20px; padding: 3px 12px; font-size: 12.5px; color: var(--sub); }
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>有色矿业 <span class="code">018168</span> · 成分股拆解与持有逻辑</h1>
  <div class="meta">
    <b>国泰中证有色金属矿业主题ETF发起联接C</b> · 跟踪 <b>中证有色金属矿业主题指数（931892，38只成分股）</b> ·
    成立 2023-08-11 · 最新规模 7.51 亿 · 数据截至 <b id="asof"></b>
  </div>
</header>

<div class="cards" id="kpis"></div>

<div class="card">
  <b>一句话结论：</b>这只基金<span class="hl">不是"一直在涨价"</span>——金属价格在 2025 年确实翻倍式大涨，但指数已在
  <span class="hl">2026-01-29 见顶（5473 点 / PE 35.4 倍）</span>，至今回撤 <span class="hl">-37%</span>。
  当前 PE 15.4 倍回到 2016 年以来 36% 分位，估值泡沫已基本消化；但内部分化剧烈：<span class="hl">铜、铝仍在历史高位附近（基本面最硬），
  金、银从峰值崩跌 28%~52%（拖累约 20% 权重的黄金股），锂反弹了 62% 但只有 2022 年高点一半，稀土/钨估值仍贵</span>。
  能否继续拿，取决于你对"贵金属企稳 + 工业金属高位可持续"的判断，详见第三部分。
</div>

<!-- ================= Q1 ================= -->
<h2>Q1 · 矿业的逻辑是什么？周期股，为什么"一直在涨价"？</h2>
<p class="lead">矿业股 = 商品价格 × 经营杠杆 的放大器。逻辑链条如下：</p>

<div class="card">
  <div class="chain">
    <div class="step">金属供给刚性<br><span class="note">矿山投资周期 5~10 年</span></div>
    <div class="arrow">→</div>
    <div class="step">需求超预期<br><span class="note">电网 / AI / 新能源 / 避险</span></div>
    <div class="arrow">→</div>
    <div class="step">金属价格上涨</div>
    <div class="arrow">→</div>
    <div class="step">矿企利润爆发<br><span class="note">成本刚性 → 涨价大部分变利润</span></div>
    <div class="arrow">→</div>
    <div class="step">股价"戴维斯双击"<br><span class="note">盈利 E ↑ × 估值 PE ↑</span></div>
  </div>
  <p style="font-size:14px; margin-top:8px;">
    矿企的成本（采矿、冶炼、能源）相对固定，金属价格每涨 10%，利润可能涨 30%~50%——这就是<b>经营杠杆</b>。
    2025 年这轮行情正是如此：铜、金、银、锂全线大涨，指数从 2024 年中的 ~1900 点翻倍到 2026-01-29 的 5473 点，
    PE 也从 15 倍炒到 <b>35.4 倍</b>——价格和估值同时膨胀，典型的周期股顶部特征。
  </p>
  <p style="font-size:14px; margin-top:8px;">
    周期股估值的反直觉之处：<span class="hl">"高 PE 买入、低 PE 卖出"</span>。PE 极高时往往是盈利低谷（值得布局），
    PE 极低时往往是盈利顶峰（危险信号）。<b>当前指数 PE 15.4 倍处于中低位</b>，但注意：成分股 2026H1 净利润增速普遍 +50%~290%，
    盈利仍在兑现高峰期——财报是"后视镜"，股价定价的是<b>未来的金属价格</b>。
  </p>
</div>

<h3>指数走势 vs 滚动市盈率（2016 至今）</h3>
<div class="card"><div id="chart-index" class="chart"></div>
  <p class="note">虚线峰值 2026-01-29：收盘 5473 / PE 35.4。此后 8 个月指数 -37%、PE 回落 56%，估值已回到历史中低区间（36% 分位）。</p>
</div>

<h3>"一直在涨价"吗？——五大金属现价对比（2024 年初 = 100）</h3>
<div class="card"><div id="chart-comm" class="chart chart-tall"></div></div>

<div class="card">
  <div class="tablewrap"><table id="tbl-comm"></table></div>
  <p class="note">结论：<b>涨价是真的，但已是"上半场"</b>。工业金属（铜 +37%/年、铝 +16%/年）仍贴着历史高点，
  供给逻辑未破坏；贵金属（金 -27.6%、银 -51.5% 距峰值）在 2026-01-29 与股市同日崩跌，是本轮回撤的主因；
  锂反弹 62% 但仅为 2022 年高点的一半，属于底部修复。</p>
</div>

<!-- ================= Q2 ================= -->
<h2>Q2 · 重仓成分股拆解：增速、PE，贵不贵？可持续吗？</h2>
<p class="lead">前 14 大成分股合计权重约 <b id="top14w"></b>（权重截至 2026-08-31，估值/财报截至 2026-09-28 与 2026 中报）。</p>

<div class="card"><div id="chart-weight" class="chart chart-tall"></div></div>

<h3>估值-增速全景图（气泡大小 = 指数权重）</h3>
<div class="card"><div id="chart-scatter" class="chart chart-tall"></div>
  <p class="note">左下角 = 便宜且高增长（理想区）；右上角 = 贵且增速放缓（危险区）。注意：中报增速是已发生的事实，横轴隐含"市场愿意为它付多少倍"。</p>
</div>

<h3>核心成分股明细</h3>
<div class="card"><div class="tablewrap"><table id="tbl-stocks"></table></div></div>

<h3>分组点评：贵不贵、可持续吗</h3>
<div class="card">
  <div class="logic good"><b class="t">铜（紫金 11.0% + 洛钼 8.7% + 西部矿业 3.4% + 铜陵/云铜/江铜 ≈ 6.8%）—— 全场最硬，权重约 30%</b>
    <span>紫金 PE 11.6 / 洛钼 PE 12.9，中报净利 +74% / +87%，量价齐升（卡莫阿、巨龙二期、KFM 放量）。
    铜价距历史高点仅 -2.5%：矿端长期资本开支不足 + 电网/AI 数据中心/新能源车需求，供给约束是所有金属里最强的。
    <b>可持续性：高</b>。主要风险是紫金同时是金矿龙头，金价拖累会在 H2 财报体现。</span></div>
  <div class="logic good"><b class="t">铝（中铝 4.0% + 云铝 2.9% + 天山铝业 2.2%）—— 最便宜，权重约 9.2%</b>
    <span>中铝 PE 8.5 / 云铝 PE 8.0，中报净利 +94% / +178%，云铝半年 ROE 就有 20%。
    国内 4500 万吨产能天花板锁死供给，电价下行改善成本。<b>可持续性：高</b>，低估值提供安全垫；风险在地产链需求。</span></div>
  <div class="logic bad"><b class="t">黄金（赤峰 4.1% + 中金黄金 3.9% + 山东黄金 3.6% + 山金国际 2.3% + 湖南黄金 1.6%）—— 回撤主因，权重约 15.5%</b>
    <span>金价从峰值崩跌 -27.6%（沪金 1249→905 元/克），但股价 PE 仍有 15~22 倍——因为分母（中报盈利）是金价高位时赚的。
    <b>若金价继续下探，这批股票存在"盈利下修 + 估值不低"的双杀风险</b>；反之若降息/避险重启、金价企稳，超跌弹性也最大。可持续性：取决于金价，目前最不确定。</span></div>
  <div class="logic bad"><b class="t">稀土/钨（北方稀土 5.4% + 中钨高新 3.1% + 厦钨 3.1% + 中国稀土 2.4% 等）—— 战略小金属，估值最贵，权重约 16%</b>
    <span>北方稀土 PE 38、中钨高新 PE 42.6——盈利大涨（+97% / +294%）之后估值依然贵，定价的是出口管制、配额管控的"战略溢价"。
    这类逻辑靠政策而非供需，<b>政策预期一旦退潮，杀估值幅度可以很深</b>（北方稀土 1 年内 PE 最高到过 110 倍）。可持续性：中，波动极大。</span></div>
  <div class="logic good"><b class="t">锂/钴（赣锋 3.2% + 华友 3.1% + 天齐 2.7% + 中矿 2.0%）—— 底部反转，权重约 11%</b>
    <span>碳酸锂 11.9 万元/吨、一年 +62%，但仍只有 2022 年高点（23 万）的一半；赣锋营收 +176% 扭亏、华友 PE 仅 9.4。
    <b>位置低、赔率好，但需要确认反弹不是又一次过剩</b>。可持续性：中，看供给出清进度。</span></div>
</div>

<div class="card">
  <b>Q2 小结：</b>指数整体 PE 15.4 倍（历史 36% 分位）<span class="hl">不算贵</span>，且成分股盈利仍在高速增长期。
  但结构上：<b>铜铝（~39% 权重）便宜 + 逻辑硬；黄金（~16%）是最大变数；稀土钨（~16%）贵、靠政策；锂（~11%）低位高赔率</b>。
  换句话说，这不是一个"贵不贵"能概括的组合，而是一篮子处于周期不同阶段的资产。
</div>

<!-- ================= Q3 ================= -->
<h2>Q3 · 继续持有 vs 卖出：各自的逻辑是什么？</h2>

<div class="cols">
  <div class="card">
    <h3 style="margin-top:0; color:var(--green);">继续持有的逻辑</h3>
    <div class="logic good"><b class="t">① 估值泡沫已消化大半</b><span>PE 从峰值 35.4 → 15.4（-56%），回到 2016 年以来 36% 分位；指数 -37% 已计入了相当多悲观预期。</span></div>
    <div class="logic good"><b class="t">② 供给端长逻辑未破坏</b><span>铜矿资本开支不足是 10 年级别的问题；电解铝产能天花板是行政硬约束；稀土钨受配额管制。这些不会因为 8 个月回调而改变。</span></div>
    <div class="logic good"><b class="t">③ 需求端有新叙事</b><span>电网投资、AI 数据中心用电与铜消耗、新能源车/光伏，叠加全球再工业化，工业金属需求韧性强。</span></div>
    <div class="logic good"><b class="t">④ 盈利动能仍在</b><span>2026 中报：前 14 大成分股净利增速普遍 +50%~290%，铜铝价格仍贴历史高位，H2 盈利有支撑。</span></div>
    <div class="logic good"><b class="t">⑤ 锂/贵金属的期权价值</b><span>锂反弹 62% 确认底部；黄金若因降息/地缘重启，超跌的金矿股弹性最大——持有相当于保留这份期权。</span></div>
  </div>
  <div class="card">
    <h3 style="margin-top:0; color:var(--red);">卖出（或减仓）的逻辑</h3>
    <div class="logic bad"><b class="t">① 低 PE 可能是"盈利顶部陷阱"</b><span>周期股铁律：PE 最低时往往是盈利顶峰。中报 +50%~290% 的增速本身不可持续，2027 年基数效应下增速大概率转负。</span></div>
    <div class="logic bad"><b class="t">② 贵金属趋势已走坏</b><span>金银与指数同日（2026-01-29）见顶，金 -27.6%、银 -51.5%，跌势未见明确底部。~16% 权重的黄金股盈利下修才刚开始，H2 财报会难看。</span></div>
    <div class="logic bad"><b class="t">③ 高估值组的政策依赖</b><span>稀土/钨 PE 38~43 倍靠"战略溢价"支撑，出口管制若缓和或配额放松，杀估值空间大（北方稀土 1 年 PE 区间 38~110）。</span></div>
    <div class="logic bad"><b class="t">④ 指数形态破位</b><span>8 个月内 -37%，近两日再跌 -3.6%/-3.9%，趋势明确向下，左侧持有需要承受继续下跌的煎熬。</span></div>
    <div class="logic bad"><b class="t">⑤ 宏观需求风险</b><span>若海外衰退或国内地产/电网投资不及预期，贴着历史高位的铜铝补跌空间不小（铜仅比峰值低 2.5%）。</span></div>
  </div>
</div>

<h3>怎么办：一个简单的决策框架（非投资建议）</h3>
<div class="card">
  <div class="chain">
    <div class="step">相信"铜铝供给紧张 + 金价能企稳"<br><b style="color:var(--green)">→ 持有，甚至分批低吸</b></div>
    <div class="arrow">·</div>
    <div class="step">认为"全球衰退、金属全面下行"<br><b style="color:var(--red)">→ 卖出，等周期重启再回来</b></div>
    <div class="arrow">·</div>
    <div class="step">看不清（大多数人）<br><b style="color:var(--acc)">→ 减仓一半留观察仓，按信号行动</b></div>
  </div>
  <h3>值得盯的量化信号</h3>
  <ul class="signal-list">
    <li><b>指数 PE 分位</b>（本页更新）：跌破 20% 分位 ≈ 深度低估区，可加仓；反弹回 30 倍以上 ≈ 再次过热，减仓。</li>
    <li><b>沪铜主力价</b>：守住 10 万元/吨 = 工业金属逻辑仍在；有效跌破 9 万 = 需求叙事恶化，警惕补跌。</li>
    <li><b>沪金价</b>：900 元/克下方止跌企稳（连续 1~2 个月不再创新低）= 黄金股权利金解除；跌破 800 = 继续回避。</li>
    <li><b>碳酸锂</b>：站稳 12 万上方 = 反转确认；跌回 9 万以下 = 反弹结束。</li>
    <li><b>季报验证</b>：2026 三季报（10 月底）重点看黄金股盈利下修幅度、紫金/洛钼铜业务是否维持增速。</li>
  </ul>
  <p class="note">仓位纪律比预测重要：单一行业主题基金建议不超过组合的 10%~20%；周期品用"分批 + 信号"代替"一把梭 + 感觉"。</p>
</div>

<footer>
  <p>数据来源：中证指数官网（指数行情/滚动PE/成分权重，权重截至 2026-08-31）、百度股市通（个股 PE-TTM/总市值）、
  新浪财经（个股财务指标、沪铜/沪铝/沪银/沪金/碳酸锂期货日线）。黄金 COMEX 口径截至 2026-09-09，其余截至 2026-09-28。</p>
  <p>本页面仅为数据整理与逻辑分析，不构成任何投资建议。基金有风险，投资需谨慎。</p>
  <p>生成：fund-018168/gen_report.py · 数据：data/report_data.json</p>
</footer>
</div>

<script>
const DATA = __DATA__;

const fmtPct = v => v == null ? '-' : (v > 0 ? '+' : '') + v.toFixed(1) + '%';
const cls = v => v == null ? 'flat' : (v >= 0 ? 'up' : 'down');
const el = id => document.getElementById(id);
const safeChart = id => (typeof echarts === 'undefined' ? null : echarts.init(el(id)));

document.getElementById('asof').textContent = DATA.index.latest_date;

/* ---------- KPI cards ---------- */
const idx = DATA.index, p = idx.perf;
const kpis = [
  { k: '指数收盘 (' + idx.latest_date + ')', v: idx.latest_close.toFixed(0), c: 'flat' },
  { k: '2026 年内涨跌', v: fmtPct(p.ytd_2026), c: cls(p.ytd_2026) },
  { k: '近 1 年', v: fmtPct(p.y_1), c: cls(p.y_1) },
  { k: '近 2 年', v: fmtPct(p.y_2), c: cls(p.y_2) },
  { k: '距峰值 (2026-01-29)', v: '-37.1%', c: 'down' },
  { k: '滚动 PE', v: idx.latest_pe, c: 'flat' },
  { k: 'PE 分位 (2016 以来)', v: idx.pe_percentile_since2016 + '%', c: 'flat' },
  { k: '成立 (2023-08-11) 以来', v: fmtPct(p.since_inception_20230811), c: cls(p.since_inception_20230811) },
];
el('kpis').innerHTML = kpis.map(x =>
  `<div class="kpi"><div class="v ${x.c}">${x.v}</div><div class="k">${x.k}</div></div>`).join('');

/* ---------- chart 1: index close + PE ---------- */
const hist = DATA.index.hist;
const c1 = safeChart('chart-index');
c1 && c1.setOption({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  legend: { data: ['指数收盘', '滚动市盈率'], textStyle: { color: '#8b97b0' }, top: 0 },
  grid: { left: 60, right: 60, top: 40, bottom: 60 },
  dataZoom: [{ type: 'inside', start: 0 }, { type: 'slider', height: 18, bottom: 8, borderColor: '#2a3650', textStyle: { color: '#8b97b0' } }],
  xAxis: { type: 'category', data: hist.map(x => x.d), axisLabel: { color: '#8b97b0' }, axisLine: { lineStyle: { color: '#2a3650' } } },
  yAxis: [
    { type: 'value', name: '点位', scale: true, axisLabel: { color: '#8b97b0' }, splitLine: { lineStyle: { color: '#222c44' } } },
    { type: 'value', name: 'PE', scale: true, axisLabel: { color: '#8b97b0' }, splitLine: { show: false } },
  ],
  series: [
    { name: '指数收盘', type: 'line', data: hist.map(x => x.c), showSymbol: false, lineStyle: { width: 1.6, color: '#e8a33d' },
      markPoint: { data: [{ coord: ['2026-01-29', 5473.53], value: '峰值 5473\nPE 35.4', itemStyle: { color: '#e05c5c' } }], label: { color: '#fff', fontSize: 10 } },
      markLine: { symbol: 'none', data: [{ yAxis: 3442, label: { formatter: '当前 3442', color: '#8b97b0' }, lineStyle: { color: '#5b8def', type: 'dashed' } }] } },
    { name: '滚动市盈率', type: 'line', yAxisIndex: 1, data: hist.map(x => x.pe), showSymbol: false, lineStyle: { width: 1.2, color: '#a78bfa' } },
  ],
});

/* ---------- chart 2: commodities normalized ---------- */
const commOrder = ['copper', 'aluminum', 'lithium', 'gold', 'silver'];
const commColors = { copper: '#e07b5c', aluminum: '#5b8def', lithium: '#4caf7d', gold: '#e8a33d', silver: '#b9c2d6' };
const baseDate = '2024-01-02';
const commSeries = commOrder.map(k => {
  const c = DATA.commodities[k];
  const arr = c.series.filter(x => x.d >= baseDate);
  const base = arr.length ? arr[0].c : 1;
  return { name: c.name, type: 'line', showSymbol: false, lineStyle: { width: 1.5, color: commColors[k] },
           data: arr.map(x => [x.d, +(x.c / base * 100).toFixed(1)]) };
});
const c2 = safeChart('chart-comm');
c2 && c2.setOption({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  legend: { data: commSeries.map(s => s.name), textStyle: { color: '#8b97b0' }, top: 0 },
  grid: { left: 55, right: 25, top: 40, bottom: 60 },
  dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8, borderColor: '#2a3650', textStyle: { color: '#8b97b0' } }],
  xAxis: { type: 'time', axisLabel: { color: '#8b97b0' }, axisLine: { lineStyle: { color: '#2a3650' } } },
  yAxis: { type: 'value', scale: true, axisLabel: { color: '#8b97b0' }, splitLine: { lineStyle: { color: '#222c44' } } },
  series: commSeries.map(s => ({ ...s, markLine: s === commSeries[0] ? { symbol: 'none', data: [{ yAxis: 100, lineStyle: { color: '#8b97b0', type: 'dashed' }, label: { formatter: '基准=100', color: '#8b97b0' } }] } : undefined })),
});
/* 关键竖线：2026-01-29 贵金属崩跌起点 */
commSeries[3].markLine = { symbol: 'none', data: [{ xAxis: '2026-01-29', lineStyle: { color: '#e05c5c', type: 'dashed' }, label: { formatter: '2026-01-29\n金/银/指数同日见顶', color: '#e05c5c', fontSize: 10 } }] };
c2 && c2.setOption({ series: commSeries });

/* ---------- commodities table ---------- */
const commTblRows = commOrder.map(k => {
  const c = DATA.commodities[k];
  const ath = c.ath != null ? c.ath : Math.max(...c.series.map(x => x.c));
  const off = c.off_ath_pct != null ? c.off_ath_pct : (c.latest / ath - 1) * 100;
  return `<tr><td>${c.name}</td><td class="flat">${c.latest}</td>
    <td class="${cls(c.chg_1y)}">${fmtPct(c.chg_1y)}</td>
    <td class="${cls(c.chg_3y)}">${fmtPct(c.chg_3y)}</td>
    <td>${ath}</td>
    <td class="${off < -15 ? 'down' : 'flat'}">${fmtPct(off)}</td></tr>`;
}).join('');
el('tbl-comm').innerHTML =
  `<tr><th>品种</th><th>最新价</th><th>近1年</th><th>近3年</th><th>历史峰值*</th><th>距峰值</th></tr>${commTblRows}
   <tr><td colspan="6" class="note" style="text-align:left">* 峰值为区间高点：沪金/沪铝/沪银/沪铜为国内期货主力连续（2019 年以来），碳酸锂为广期所主力（2023 年上市以来）。</td></tr>`;

/* ---------- chart 3: weights ---------- */
const wItems = DATA.weights.items.slice(0, 15).reverse();
const groupColor = { '紫金矿业':'#e07b5c','洛阳钼业':'#e07b5c','西部矿业':'#e07b5c','铜陵有色':'#e07b5c','江西铜业':'#e07b5c','云南铜业':'#e07b5c','中金黄金':'#e8a33d','赤峰黄金':'#e8a33d','山东黄金':'#e8a33d','山金国际':'#e8a33d','湖南黄金':'#e8a33d','北方稀土':'#a78bfa','中国稀土':'#a78bfa','盛和资源':'#a78bfa','中钨高新':'#a78bfa','厦门钨业':'#a78bfa','赣锋锂业':'#4caf7d','天齐锂业':'#4caf7d','华友钴业':'#4caf7d','中矿资源':'#4caf7d','永兴材料':'#4caf7d','中国铝业':'#5b8def','云铝股份':'#5b8def','天山铝业':'#5b8def','兴业银锡':'#b9c2d6','锡业股份':'#b9c2d6','云南锗业':'#7dd3c0','驰宏锌锗':'#7dd3c0' };
const c3 = safeChart('chart-weight');
c3 && c3.setOption({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: p => `${p[0].name}：${p[0].value}%` },
  grid: { left: 90, right: 50, top: 10, bottom: 30 },
  xAxis: { type: 'value', axisLabel: { color: '#8b97b0', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#222c44' } } },
  yAxis: { type: 'category', data: wItems.map(x => x.name), axisLabel: { color: '#dce3f0' }, axisLine: { lineStyle: { color: '#2a3650' } } },
  series: [{ type: 'bar', data: wItems.map(x => ({ value: x.weight, itemStyle: { color: groupColor[x.name] || '#8b97b0' } })),
    barWidth: '62%', label: { show: true, position: 'right', color: '#8b97b0', formatter: '{c}%' } }],
});

/* ---------- chart 4: scatter PE vs growth ---------- */
const nameByCode = {}; DATA.weights.items.forEach(w => nameByCode[w.code] = { name: w.name, weight: w.weight });
const scData = DATA.stocks.map(s => {
  const fin = s.fin && s.fin.length ? s.fin[s.fin.length - 1] : {};
  const w = nameByCode[s.code] ? nameByCode[s.code].weight : 1;
  return { code: s.code, name: s.name, pe: s.pe_ttm, np: fin.np_g, roe: fin.roe, w };
}).filter(x => x.pe != null && x.np != null && !isNaN(x.np));
const c4 = safeChart('chart-scatter');
c4 && c4.setOption({
  backgroundColor: 'transparent',
  tooltip: { formatter: p => `<b>${p.data.name}</b> (${p.data.code})<br>PE-TTM: ${p.data.pe}<br>2026H1净利增速: ${p.data.np.toFixed(0)}%<br>权重: ${p.data.w}%` },
  grid: { left: 60, right: 30, top: 30, bottom: 45 },
  xAxis: { type: 'value', name: 'PE-TTM', nameTextStyle: { color: '#8b97b0' }, max: 50, axisLabel: { color: '#8b97b0' }, splitLine: { lineStyle: { color: '#222c44' } } },
  yAxis: { type: 'value', name: '2026H1 净利增速 %', nameTextStyle: { color: '#8b97b0' }, max: 310, axisLabel: { color: '#8b97b0' }, splitLine: { lineStyle: { color: '#222c44' } } },
  series: [{
    type: 'scatter',
    data: scData.map(x => ({ value: [Math.min(x.pe, 48), Math.min(x.np, 300)], name: x.name, code: x.code, pe: x.pe, np: x.np, w: x.w,
      itemStyle: { color: groupColor[x.name] || '#8b97b0', opacity: .85 },
      symbolSize: Math.max(10, Math.sqrt(x.w) * 11),
      label: { show: true, position: 'top', color: '#dce3f0', fontSize: 11, formatter: x.name } })),
    markArea: { silent: true, itemStyle: { color: 'rgba(76,175,125,.06)' },
      data: [[{ coord: [0, 40] }, { coord: [16, 310] }]],
      label: { show: true, color: '#4caf7d', fontSize: 11, formatter: '便宜且高增长' } },
  }],
});

/* ---------- stocks table ---------- */
const verdict = {
  '601899': ['mid','铜金双龙头；PE 处 1 年最低，金价是 H2 变量'],
  '603993': ['cheap','铜钴量价齐升，PE 不贵，逻辑最顺'],
  '600111': ['exp','PE 38 靠战略溢价；稀土价格弹性大、波动大'],
  '600988': ['mid','高成长金矿股，但金价崩跌后盈利将下修'],
  '601600': ['cheap','PE 8.5 + 净利 +94%，产能天花板，最便宜的央企'],
  '600489': ['mid','央企金矿，估值中性，跟随金价'],
  '600547': ['mid','PE 22 在黄金股中偏贵，营收已负增长'],
  '601168': ['cheap','铜铅锌，PE 13.5 + 半年 ROE 18.6%，被忽视的低估值'],
  '002460': ['cheap','锂价反弹扭亏，营收 +176%，底部反转期权'],
  '603799': ['cheap','镍钴锂一体化，PE 仅 9.4'],
  '000657': ['exp','PE 43，钨价+军工需求，增速 294% 但预期已高'],
  '600549': ['mid','钨+稀土+电池材料，增速快，估值中等'],
  '000807': ['cheap','PE 8.0 + 净利 +178% + 半年 ROE 20%，水电铝成本优势'],
  '000426': ['mid','银锡双击，锡供给紧、银价崩跌后需观察'],
};
const tagText = { cheap: '便宜', mid: '中性', exp: '偏贵' };
const stRows = DATA.stocks.map(s => {
  const w = nameByCode[s.code] ? nameByCode[s.code].weight : '-';
  const fin = s.fin && s.fin.length ? s.fin[s.fin.length - 1] : {};
  const fin25 = (s.fin || []).find(f => f.date === '2025-12-31') || {};
  const v = verdict[s.code] || ['mid', ''];
  const npg = fin.np_g == null || isNaN(fin.np_g) ? '<span class="note">扭亏</span>' : `<span class="up">+${fin.np_g.toFixed(0)}%</span>`;
  return `<tr><td class="note">${s.code}</td><td><b>${s.name}</b></td>
    <td>${w}%</td><td>${s.pe_ttm ?? '-'}</td>
    <td class="note">${s.pe_range_1y ? s.pe_range_1y[0] + ' ~ ' + s.pe_range_1y[1] : '-'}</td>
    <td>${s.mktcap_yi != null ? Math.round(s.mktcap_yi).toLocaleString() + ' 亿' : '-'}</td>
    <td>${fin25.np_g != null && !isNaN(fin25.np_g) ? '<span class="up">+' + fin25.np_g.toFixed(0) + '%</span>' : '<span class="note">亏损</span>'}</td>
    <td>${npg}</td>
    <td>${fin.roe != null ? fin.roe.toFixed(1) + '%' : '-'}</td>
    <td style="text-align:left; white-space:normal; min-width:230px;"><span class="tag ${v[0]}">${tagText[v[0]]}</span> <span class="note">${v[1]}</span></td></tr>`;
}).join('');
el('tbl-stocks').innerHTML =
  `<tr><th>代码</th><th>名称</th><th>权重</th><th>PE-TTM</th><th>PE 1年区间</th><th>总市值</th><th>2025 净利增速</th><th>2026H1 净利增速</th><th>2026H1 ROE</th><th>点评</th></tr>${stRows}`;

const top14w = DATA.weights.items.slice(0, 14).reduce((a, b) => a + b.weight, 0);
el('top14w').textContent = top14w.toFixed(1) + '%';

window.addEventListener('resize', () => [c1, c2, c3, c4].forEach(c => c && c.resize()));
if (typeof echarts === 'undefined') document.querySelectorAll('.chart').forEach(d => d.innerHTML = '<p class="note">图表库加载失败，表格数据不受影响。</p>');
</script>
</body>
</html>
"""

html = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
out = os.path.join(HERE, "index.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print("written", out, len(html), "bytes")
