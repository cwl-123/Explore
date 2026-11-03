"""02_gbdt.py — 第二个模型：GBDT（梯度提升树）。

从 LR 换成树，本质变化：
    LR 只能沿单一特征方向切分（线性），树能自动做「分段的非线性 + 特征组合」，
    所以你不用手工造 price_log、user_ctr 这种交叉项，树会自己找阈值。
    代价：树不吃高基数 ID（user_id 有 1.2 万取值，树基本记不住也泛化不了），
    所以这里我们只用「ID 的统计特征」，这也解释了为什么大厂排序模型最终都要 embedding。

这里用 sklearn 的 HistGradientBoosting（和 LightGBM 同源的直方图算法，无需额外依赖）。
装了 LightGBM 的话可以一行替换：LGBMClassifier(n_estimators=300, num_leaves=63)。

跑法：
    cd ml-training-lab && .venv/bin/python code/02_gbdt.py
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402

from features import LOW_CARD, add_history_features, make_tree_frame, time_split  # noqa: E402
from labkit import build_dataset, ceiling_auc, evaluate  # noqa: E402


def main() -> None:
    t0 = time.time()

    df = build_dataset()
    df = add_history_features(df)
    train, valid, test = time_split(df)
    print(f"[数据] {len(df):,} 行 | 天花板 AUC {ceiling_auc(df):.4f} "
          f"（用真实概率算，任何模型都不可能超过它）")

    Xtr, ytr = make_tree_frame(train), train["label"].to_numpy()
    Xva, yva = make_tree_frame(valid), valid["label"].to_numpy()
    Xte, yte = make_tree_frame(test), test["label"].to_numpy()

    # 低基数类别告诉模型"这是类别，不是连续值"
    cat_mask = [c in LOW_CARD for c in Xtr.columns]

    # ---------- 1. 在 valid 上选超参：这是"调参"的正确姿势 ----------
    print("\n[调参] 在 valid 上网格搜索（test 不参与任何决策）")
    best = None
    for leaves in (31, 63, 127):
        for lr in (0.05, 0.1):
            clf = HistGradientBoostingClassifier(
                max_iter=400, learning_rate=lr, max_leaf_nodes=leaves,
                min_samples_leaf=40, l2_regularization=1.0,
                categorical_features=cat_mask,
                early_stopping=True, validation_fraction=0.1,
                random_state=0,
            ).fit(Xtr, ytr)
            p_va = clf.predict_proba(Xva)[:, 1]
            auc = evaluate(yva, p_va)["auc"]
            print(f"  leaves={leaves:<4} lr={lr:<5} valid_auc={auc:.4f} "
                  f"| 用了 {clf.n_iter_} 棵树")
            if best is None or auc > best[0]:
                best = (auc, leaves, lr, clf)

    _, leaves, lr, clf = best
    print(f"[选择] leaves={leaves}, lr={lr}")

    # ---------- 2. test 只报一次 ----------
    p_te = clf.predict_proba(Xte)[:, 1]
    evaluate(test["label"], p_te, test["user_id"], "test")

    # ---------- 3. 哪个特征真的有用 ----------
    print("\n[重要性] 打乱单列后 AUC 掉多少（掉得越多越重要）")
    imp = permutation_importance(clf, Xva, yva, scoring="roc_auc",
                                 n_repeats=3, random_state=0, n_jobs=-1)
    order = np.argsort(-imp.importances_mean)
    for i in order[:8]:
        print(f"  {Xva.columns[i]:<16} {imp.importances_mean[i]:+.4f}")

    print(f"\n[耗时] 全流程 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()