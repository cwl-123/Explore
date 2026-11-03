"""01_lr_baseline.py — 第一个模型：逻辑回归 baseline。

工程视角看，这就是一个"线性打分器"：
    score = w · x,  p = sigmoid(score)
训练 = 用梯度下降找一组 w，使训练集上的 logloss 最小。
它慢、它土、它泛化差，但它是所有后续模型的地基，也是线上兜底方案。

跑法：
    cd ml-training-lab && .venv/bin/python code/01_lr_baseline.py
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from sklearn.linear_model import LogisticRegression  # noqa: E402

from features import add_history_features, make_lr_matrix, time_split  # noqa: E402
from labkit import build_dataset, calibration_table, evaluate  # noqa: E402


def main() -> None:
    t0 = time.time()

    # ---------- 1. 数据 ----------
    df = build_dataset()
    print(f"[数据] {len(df):,} 行曝光 | 全局 CTR {df['label'].mean():.4f} | "
          f"{df['ts'].min():%m-%d} ~ {df['ts'].max():%m-%d}")

    df = add_history_features(df)
    train, valid, test = time_split(df)
    print(f"[切分] train={len(train):,}  valid={len(valid):,}  test={len(test):,} "
          f"(按时间切，不是随机切)")

    # ---------- 2. 特征 ----------
    Xtr, Xva, Xte, pre = make_lr_matrix(train, valid, test)
    print(f"[特征] 稀疏矩阵 train {Xtr.shape} | 非零 {Xtr.nnz:,} "
          f"| 维度来自 one-hot + 交叉特征")

    # ---------- 3. 训练 ----------
    clf = LogisticRegression(C=0.5, max_iter=200, solver="lbfgs")
    t1 = time.time()
    clf.fit(Xtr, train["label"].to_numpy())
    print(f"[训练] {time.time() - t1:.1f}s, 迭代 {clf.n_iter_[0]} 次")

    # ---------- 4. 评估：valid 调参，test 只报一次 ----------
    p_va = clf.predict_proba(Xva)[:, 1]
    p_te = clf.predict_proba(Xte)[:, 1]
    evaluate(valid["label"], p_va, valid["user_id"], "valid")
    evaluate(test["label"], p_te, test["user_id"], "test ")

    print("\n[校准] 预测分区间 vs 实际点击率（差得越小越准）")
    print(calibration_table(test["label"], p_te).to_string(index=False,
          float_format=lambda v: f"{v:.3f}"))

    # ---------- 5. 看模型学到了什么 ----------
    names = pre.get_feature_names_out()
    coef = clf.coef_[0]
    order = np.argsort(-np.abs(coef))[:12]
    print("\n[权重] |系数| 最大的 12 个特征（正=利于点击）")
    for i in order:
        print(f"  {coef[i]:+.3f}  {names[i]}")

    print(f"\n[耗时] 全流程 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()