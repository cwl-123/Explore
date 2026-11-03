"""04_deepfm.py — 第三个模型：DeepFM（第一个神经网络，手写，不调库）。

为什么要有它？把前两个模型的短板补上：
    LR  : 能记 ID，但只能线性组合 → 学不到「用户 × 商品」的内积交互
    GBDT: 能学非线性，但不吃高基数 ID（user_id 1.2 万取值）→ 丢掉个性化
    DeepFM: ID 走 embedding（每个 ID 学一个向量，相似 ID 自动靠近）
            + FM 显式学二阶交互（≈ 隐向量内积，正是我们数据生成的方式）
            + DNN 学高阶非线性

这里手写而不是调 DeepCTR，是因为 DeepFM 的结构只有 30 行，
自己写一遍，你以后看任何排序模型（DIN/MMoE/DCN）都能一眼看出骨架。

跑法：
    cd ml-training-lab && .venv/bin/python code/04_deepfm.py
"""
from __future__ import annotations

import pathlib
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from features import NUM_COLS, add_history_features, time_split  # noqa: E402
from labkit import build_dataset, ceiling_auc, evaluate  # noqa: E402

SPARSE = ["user_id", "item_id", "category", "slot", "hour", "dow"]
torch.manual_seed(0)
np.random.seed(0)


# --------------------------------------------------------------------------- #
# 特征编码
# --------------------------------------------------------------------------- #
def fit_vocab(df: pd.DataFrame) -> dict[str, dict]:
    """ID → 连续整数。0 号留给「没见过的 ID」(OOV)。

    工程含义：这份映射必须存下来，线上 serving 用同一份，否则 ID 对不上，
    就是最经典的 train-serving skew。
    """
    return {c: {v: i + 1 for i, v in enumerate(sorted(df[c].unique()))} for c in SPARSE}


def encode(df: pd.DataFrame, vocab: dict, mu, sd):
    idx = np.zeros((len(df), len(SPARSE)), dtype=np.int64)
    for j, c in enumerate(SPARSE):
        idx[:, j] = df[c].map(vocab[c]).fillna(0).astype(np.int64).to_numpy()
    num = ((df[NUM_COLS].to_numpy() - mu) / sd).astype(np.float32)
    return torch.from_numpy(idx), torch.from_numpy(num), torch.from_numpy(df["label"].to_numpy(dtype=np.float32))


# --------------------------------------------------------------------------- #
# 模型
# --------------------------------------------------------------------------- #
class DeepFM(nn.Module):
    def __init__(self, cardinalities: list[int], n_num: int, dim: int = 16,
                 hidden: tuple[int, ...] = (256, 128), dropout: float = 0.3):
        super().__init__()
        self.emb = nn.ModuleList([nn.Embedding(c, dim) for c in cardinalities])
        self.lin = nn.ModuleList([nn.Embedding(c, 1) for c in cardinalities])
        self.num_lin = nn.Linear(n_num, 1)

        d = len(cardinalities) * dim + n_num
        layers: list[nn.Module] = []
        for h in hidden:
            layers += [nn.Linear(d, h), nn.ReLU(), nn.Dropout(dropout)]
            d = h
        layers.append(nn.Linear(d, 1))
        self.dnn = nn.Sequential(*layers)

        for e in self.emb:
            nn.init.normal_(e.weight, std=0.01)
        for e in self.lin:
            nn.init.zeros_(e.weight)

    def forward(self, xc: torch.Tensor, xn: torch.Tensor) -> torch.Tensor:
        # 1) 每个字段一个向量 → (B, F, k)
        e = torch.stack([emb(xc[:, i]) for i, emb in enumerate(self.emb)], dim=1)
        # 2) 一阶：每个字段自己的权重（相当于 LR）
        first = sum(lin(xc[:, i]).squeeze(1) for i, lin in enumerate(self.lin))
        # 3) 二阶 FM：0.5 * ((Σe)² - Σe²)，把所有字段两两内积一次算完
        s = e.sum(dim=1)
        second = 0.5 * (s * s - (e * e).sum(dim=1)).sum(dim=1)
        # 4) 高阶：embedding 摊平 + 数值特征 → MLP
        deep = self.dnn(torch.cat([e.flatten(1), xn], dim=1)).squeeze(1)
        return first + second + self.num_lin(xn).squeeze(1) + deep


# --------------------------------------------------------------------------- #
# 训练
# --------------------------------------------------------------------------- #
def main() -> None:
    t0 = time.time()
    df = add_history_features(build_dataset())
    train, valid, test = time_split(df)
    print(f"[数据] {len(df):,} 行 | 天花板 AUC {ceiling_auc(build_dataset()):.4f}")

    vocab = fit_vocab(train)                      # 只用训练集的 ID 建表（防泄漏）
    cards = [len(vocab[c]) + 1 for c in SPARSE]   # +1 给 OOV
    mu = train[NUM_COLS].to_numpy().mean(0)
    sd = train[NUM_COLS].to_numpy().std(0) + 1e-6

    Xc, Xn, y = encode(train, vocab, mu, sd)
    Vc, Vn, yv = encode(valid, vocab, mu, sd)
    Tc, Tn, yt = encode(test, vocab, mu, sd)
    print(f"[编码] 字段基数 {dict(zip(SPARSE, cards))}")

    model = DeepFM(cards, n_num=len(NUM_COLS), dim=16, hidden=(256, 128), dropout=0.3)
    n_par = sum(p.numel() for p in model.parameters())
    print(f"[模型] 参数量 {n_par:,}（其中 embedding 占 "
          f"{sum(e.weight.numel() for e in model.emb):,}）")

    # weight_decay 和 dropout 是这里的关键：ID 只有 7 次曝光/人，不加正则必然过拟合
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    bs, n = 2048, len(y)
    best_auc, best_state, bad = 0.0, None, 0

    for epoch in range(1, 21):
        model.train()
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, bs):
            b = perm[i:i + bs]
            opt.zero_grad()
            loss = loss_fn(model(Xc[b], Xn[b]), y[b])
            loss.backward()
            opt.step()
            tot += loss.item() * len(b)
        model.eval()
        with torch.no_grad():
            va = roc_auc_score(yv.numpy(), torch.sigmoid(model(Vc, Vn)).numpy())
        print(f"  epoch {epoch:2d}  train_loss={tot / n:.4f}  valid_auc={va:.4f}")
        if va > best_auc:
            best_auc, bad = va, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= 3:                      # 连续 3 轮不涨就停（early stopping）
                print(f"  early stop at epoch {epoch}")
                break

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        p_te = torch.sigmoid(model(Tc, Tn)).numpy()
    print()
    evaluate(test["label"], p_te, test["user_id"], "test")
    print("\n[对比] 同一份数据上：LR ≈ 0.708，GBDT ≈ 0.718，DeepFM 见上。")
    print("       提升幅度不大，这就是 CTR 的常态：结构创新换千分位，特征/样本换百分位。")
    print("       想说清楚的话：把 labkit.build_dataset(impressions_per_user=20) 的"
          "数据密度加大，embedding 会学得更好。")
    print(f"[耗时] 全流程 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()