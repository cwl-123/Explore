# 恒生科技 20% 仓位：该割肉，还是该减仓？

单文件报告：`index.html`（ECharts 由 CDN 加载）。数据截止 2026-11-16 收盘（恒指至 11-17，但归一化图已统一截到 11-16）。

## 重新生成

```bash
# 1) 先刷新底层缓存（需要网络；失败自动保留旧缓存）
../hs300-strategy-lab/.venv/bin/python ../hs300-strategy-lab/backtest.py --update-only

# 2) 生成 index.html
../hs300-strategy-lab/.venv/bin/python build.py

# 3) 回到仓库根目录，重建门户并注入统一导航
cd .. && python3 build_site.py
```

`build.py` 直接读取仓库内已缓存的 CSV，不发网络请求。

## 数据来源

- 恒生科技价格：`../hs300-strategy-lab/data/hstech_price.csv`（新浪港股指数日线，2020-08 起）
- 恒生科技 PE / 股息率：`../hs300-strategy-lab/data/hstech_pe.csv`（乐咕乐股官方月度，2020-07 起）
- 恒指：`hsi_price.csv` / `hsi_pe.csv`；沪深300：`hs300_price.csv` / `hs300_pe.csv`
- 纳指100：`ndx_price.csv`；标普500 PE / CAPE：`sp500_pe.csv` / `ndx_cape.csv`
- 美债 10Y：`ust10y.csv`
- 个股估值/财务：`../china-internet-valuation.html`（513050 中概互联报告，2026-09-24，TTM 截至 2026-06-30）与 `../hsi-valuation.html`（2026-10-13）
- AI 算力：`../us-china-ai-compute/index.html`（2026-10-21，Epoch AI / BCG 口径）

## 口径与局限

- PE 分位 = 历史序列中 ≤ 当前值的比例，含当前点；负 PE 月份已剔除。恒生科技 PE 序列短且受亏损公司、指数调仓、财报更新影响，分位只能当参考（文中同时给了全样本、剔除失真、2023 起等四个口径）。
- 隐含盈利 = 指数点位 ÷ PE，为反推值，不等于官方净利润；2024-03、2026-03 等财报月的跳变包含口径变化，不宜当真实单季增速。
- 个股 PE/财务为 2026-09 快照，可能与最新财报有差异；美团/阿里 FCF 数据来自 513050 报告，口径为 stockanalysis.com。
- 情景概率为主观设定，不是市场隐含概率；目标点位 = 隐含盈利 × 盈利变动 × 目标 PE。
- 页面为数据研究，不构成投资建议。