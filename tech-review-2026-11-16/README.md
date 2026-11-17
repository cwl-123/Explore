# 科创50 × 创业板 2026-11-16 复检

单文件报告：`index.html`（ECharts 由 CDN 加载）。数据截止 2026-11-16 收盘（恒指/黄金 11-17）。

## 重新生成

```bash
# 1) 先刷新底层缓存（需要网络；失败自动保留旧缓存）
../hs300-strategy-lab/.venv/bin/python ../hs300-strategy-lab/backtest.py --update-only

# 2) 生成 index.html
../hs300-strategy-lab/.venv/bin/python build.py

# 3) 回到仓库根目录，重建门户并注入统一导航
cd .. && python3 build_site.py
```

`build.py` 直接读取仓库内已缓存的 CSV，不发网络请求。新增/删除数据源时同步改 `build.py` 顶部的常量。

## 数据来源

- 科创50：`../hs300-strategy-lab/data/kcb50.csv`（中证官网 000688，价格 + 滚动 PE，2019-07 起）
- 创业板指：`../hs300-strategy-lab/data/cyb_price.csv`（国证 399006 日线）
- 创业板 PE/PB：`../cyb-2026-10/data/index-basic-pe.csv`、`index-basic-pb.csv`（国证官网 `addTtmPe` / `addPb` 月度序列，2010-06 起）；最新点按指数涨跌从 2026-10-29 折算到最新收盘
- 创业板持仓集中度：`../cyb-2026-10/data/merged.csv`（159915 2026 Q3 披露 76 只）
- 纳指100：`ndx_price.csv`（Yahoo ^NDX）
- 标普500 PE / 席勒 CAPE：`sp500_pe.csv`、`ndx_cape.csv`（multpl 月度）
- 恒生科技：`hstech_price.csv`（新浪港股指数，仅用于归一化对照）

## 口径与局限

- 分位 = 历史序列中 ≤ 当前值的比例（含当前点）；科创50 自 2019-07，创业板自 2010-06，标普 PE/CAPE 自各自序列起点。
- 跨市场 PE 会计口径不同，只比较「各自历史分位」，不做绝对 PE 直接对比。
- 创业板 PE 低主要由 Top3（宁德时代/中际旭创/新易盛）拉低：Top3 约占 35% 权重、90% 的 TTM 利润，其余成分股加权 PE 约 28x、中位约 33x。
- 页面为数据研究，不构成投资建议。