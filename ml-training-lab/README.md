# ml-training-lab

一个**从工程视角入门模型训练**的动手实验仓库。不是教程复述，而是「跑一遍、看数字、想清楚为什么」。

**面向背景**：有扎实计算机基础、写过工程代码，但没系统学过机器学习；在电商平台做策略/算法工程，日常接触的场景就是 CTR 预估、排序、多目标、A/B。所以这里的主线是 **电商 CTR**，不是大语言模型。

---

## 5 分钟跑起来

```bash
cd ml-training-lab
.venv/bin/python code/01_lr_baseline.py   # 逻辑回归 baseline，约 3 秒
.venv/bin/python code/02_gbdt.py          # GBDT，约 12 秒
.venv/bin/python code/03_leakage_lab.py   # 特征泄漏实验（最重要的一课）
.venv/bin/python code/04_deepfm.py        # DeepFM，第一个神经网络
```

环境已经建好（Python 3.11 + numpy/pandas/scikit-learn/torch）。要重建：

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
```

---

## 四个脚本跑出来的真实结果

同一份合成数据（12.2 万行曝光，全局 CTR 10.6%），按时间切分出 train/valid/test。
**天花板 AUC = 0.795**（用数据生成时的真实概率算的，任何模型都不可能超过它）。

| # | 模型 | test AUC | LogLoss | top5% lift | 关键结论 |
|---|---|---|---|---|---|
| 01 | 逻辑回归 | 0.7076 | 0.3103 | 2.82 | 能记 ID，学不到交互 |
| 02 | GBDT | 0.7182 | 0.3078 | 3.14 | 能学非线性，但吃不了高基数 ID |
| 04 | DeepFM | 0.7220 | 0.3072 | 3.18 | embedding + 显式二阶交叉 |

三个模型都离天花板差 0.07 以上 —— **这不是模型不行，是特征不够**。
真实工业界的排序模型靠的是用户行为序列、实时特征、多目标，而不是更花哨的网络结构。
这个认知比跑通代码重要得多。

03 的泄漏实验（同一份数据，只改特征和切分方式）：

| 实验 | AUC | 说明 |
|---|---|---|
| 时间切分 + 因果特征 | 0.7101 | ✅ 正确做法 |
| + 商品全量 CTR | 0.7130 | ❌ 温和泄漏，+0.003，最容易被忽略 |
| + 用户×商品 全量 CTR | 0.9101 | ❌ 剧烈泄漏，+0.20，特征几乎等于 label |
| + 用户×商品 历史次数 | 0.7101 | ✅ 同一想法的正确写法 |
| 随机切分 + 因果特征 | 0.6999 | ⚠️ 切分本身不是泄漏源，但会掩盖分布差异 |

---

## 目录

```
ml-training-lab/
├── code/
│   ├── labkit.py           合成电商数据 + 评估指标（AUC/GAUC/LogLoss/校准/lift）
│   ├── features.py         特征工程：时间切分、因果历史统计、三种模型的数据形态
│   ├── 01_lr_baseline.py   逻辑回归：所有模型的地基
│   ├── 02_gbdt.py          GBDT：非线性 + 调参方法论 + 特征重要性
│   ├── 03_leakage_lab.py   特征泄漏：亲手制造虚高，再修好
│   └── 04_deepfm.py        DeepFM：手写 embedding + FM + DNN
├── notes/
│   ├── 00-知识地图.md       训练到底是什么 / CTR vs LLM / 术语表
│   ├── 01-CTR模型演进.md    LR → GBDT+LR → FM → DeepFM → DIN → 多目标 → 生成式
│   ├── 02-训练排障手册.md    loss 不降、AUC 异常、线上线下不一致的排查清单
│   └── 03-指标体系与线上.md  AUC/GAUC/校准/置信区间，以及离线涨了线上为什么不涨
├── PLAN.md                 8 周学习计划，带验收标准
└── requirements.txt
```

---

## 为什么用合成数据

真实数据（Criteo 11GB、公司内部日志）第一周根本跑不动，而且**看不清因果**。
这里的合成数据保留了真实电商日志的关键结构，所以你能在上面看到真实现象：

- 用户/商品有隐向量，点击率来自内积 → **ID 类特征真的有信息**，交互项才是主力
- 商品热度 Zipf 长尾、用户活跃度 lognormal → 会有冷启动和长尾问题
- 曝光位置有 position bias → slot 有信号，但它代表「被看到」而不是「被喜欢」
- 时间有周期性和漂移 → 时间切分和线上分布差异是真实存在的

而且我们知道**真实概率**，所以能算天花板、能判断「模型是没学好还是到头了」。
这是用真实数据做不到的事。

想调难度：`build_dataset(impressions_per_user=8, seed=42)`，把人均曝光调到 20，
数据密度上去了，embedding 会学得明显更好 —— 这就是「数据量决定模型上限」的直观感受。

---

## 这个 lab 不做什么

诚实说明边界，省得你以为漏学了：

- **不做实时特征/在线学习**（FTRL、在线更新）—— 工程量大，且要先懂这里的离线部分
- **不做分布式训练、不做大规模 embedding table 分片** —— 那是平台侧的事
- **不做召回**（双塔、向量检索），这里只做**排序**（精排 CTR）
- **不做 A/B 平台**，只在 notes 里讲清楚「离线涨了线上为什么不涨」的判断逻辑
- **不做 LLM** —— 那是另一条路，见 `notes/00-知识地图.md` 的对比

---

## 环境备注

- Python 3.11，依赖见 `requirements.txt`
- `02_gbdt.py` 用 sklearn 的 `HistGradientBoosting`（与 LightGBM 同源的直方图算法），无需额外依赖
- 想用真的 LightGBM：`brew install libomp` 后 `pip install lightgbm`，把 `02_gbdt.py` 里的
  `HistGradientBoostingClassifier` 换成 `LGBMClassifier(n_estimators=300, num_leaves=31)`
- Mac（Apple Silicon）CPU 即可跑，无需 GPU；四个脚本总耗时约 30 秒