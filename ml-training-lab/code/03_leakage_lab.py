"""03_leakage_lab.py — 特征泄漏实验（本仓库最重要的一课）。

目标：亲手制造「离线指标虚高」，再亲手修好它。所有数字都是真实跑出来的。

结论先行（跑完你会看到）：
    泄漏的大小，取决于这个特征把 label 编码得有多彻底 ——
    · 商品全量 CTR：一个商品约 40 行，自己那行只占 1/40 → AUC 只涨 0.003（温和，最容易被忽略）
    · 用户×商品 全量 CTR：大部分组合只出现 1 次 → 特征几乎等于 label → AUC 涨到 0.91（剧烈）
    · 随机切分本身不制造泄漏，但它会掩盖「上线只能用过去预测未来」这个分布差异

判断标准只有一条：这个特征在「预测那一刻」真的算得出来吗？

跑法：
    cd ml-training-lab && .venv/bin/python code/03_leakage_lab.py
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from sklearn.compose import ColumnTransformer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # noqa: E402

from features import add_history_features, time_split  # noqa: E402
from labkit import build_dataset, ceiling_auc  # noqa: E402

CATS = ["user_id", "item_id", "category", "slot"]
BASE_NUM = ["log_price", "u_ctr", "i_ctr", "uc_imp_before"]


def add_feature(df: pd.DataFrame, kind: str | None) -> tuple[pd.DataFrame, list[str]]:
    """按 kind 加一个特征，返回 (df, 新增的数值列)。"""
    df = df.copy()
    if kind is None:
        return df, []
    if kind == "item_full":
        # ❌ 用全部数据（含 test 的 10 天）算商品 CTR —— "顺手 groupby 全表" 的典型 bug
        df["leak_feat"] = df.groupby("item_id")["label"].transform("mean")
    elif kind == "pair_full":
        # ❌ 用全部数据算「用户×商品」的 CTR
        df["leak_feat"] = df.groupby(["user_id", "item_id"])["label"].transform("mean")
    elif kind == "pair_hist":
        # ✅ 同一个想法的「因果版」：只数这一行之前这对组合出现过几次
        df["leak_feat"] = df.groupby(["user_id", "item_id"]).cumcount()
    return df, ["leak_feat"]


def run(df: pd.DataFrame, split: str, kind: str | None) -> float:
    df, new_num = add_feature(df, kind)
    num = BASE_NUM + new_num

    if split == "time":
        train, _, test = time_split(df)
    else:  # 随机切分：同一时间窗内随机抽 80% 训练
        mask = np.random.default_rng(0).random(len(df)) < 0.8
        train, test = df[mask], df[~mask]

    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=10), CATS),
        ("num", StandardScaler(), num),
    ])
    Xtr = pre.fit_transform(train[CATS + num])
    Xte = pre.transform(test[CATS + num])
    clf = LogisticRegression(C=0.5, max_iter=200).fit(Xtr, train["label"])
    return roc_auc_score(test["label"], clf.predict_proba(Xte)[:, 1])


def main() -> None:
    raw = build_dataset()
    df = add_history_features(raw)
    print(f"[基准] 天花板 AUC {ceiling_auc(raw):.4f}（用真实概率算，任何模型都超不过）\n")

    exps = [
        ("① 时间切分 + 因果特征", "time", None, "✅ 正确做法，线上能复现"),
        ("② + 商品全量 CTR", "time", "item_full", "❌ 温和泄漏（最隐蔽）"),
        ("③ + 用户×商品 全量 CTR", "time", "pair_full", "❌ 剧烈泄漏，特征≈label"),
        ("④ + 用户×商品 历史次数", "time", "pair_hist", "✅ 同一个想法的正确写法"),
        ("⑤ 随机切分 + 因果特征", "random", None, "⚠️ 不泄漏，但掩盖分布差异"),
    ]

    aucs = []
    for name, split, kind, note in exps:
        auc = run(df, split, kind)
        aucs.append(auc)
        print(f"{name:<26} AUC={auc:.4f}   {note}")

    base = aucs[0]
    print(f"\n[解读] 基线 {base:.4f}")
    print(f"  · 温和泄漏 ②：{aucs[1] - base:+.4f} —— 小到你根本不会怀疑，但线上一样掉点")
    print(f"  · 剧烈泄漏 ③：{aucs[2] - base:+.4f} —— AUC 突然暴涨 0.1 以上，就是泄漏的警报")
    print(f"  · 正确修复 ④：{aucs[3] - base:+.4f} —— 保留「复访」信号，但不偷看答案")
    print(f"  · 随机切分 ⑤：{aucs[4] - base:+.4f} —— 切分方式本身不是泄漏源；"
          f"泄漏来自「特征计算时用了未来」")
    print("\n[怎么防] 不是靠小心，是靠 pipeline 强制：")
    print("  1. 特征只允许读 t 之前的数据（point-in-time join，离线/实时同一套口径）")
    print("  2. 训练集/测试集先切分，再算统计量（绝不在全量上 groupby 后切）")
    print("  3. 把「AUC 异常高」当 bug 上报，而不是当成果庆祝")


if __name__ == "__main__":
    main()