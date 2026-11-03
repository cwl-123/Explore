"""features.py — 特征工程（全部只用「可见列」，且只回看历史）。

这一层的三件事，正是 CTR 工程 80% 的工作量：
  1. 时间切分：训练/验证/测试必须按时间切，不能随机切
  2. 历史统计特征：用户/商品在「此刻之前」的曝光与点击（expanding，不做前视）
  3. 高基数字段的处理方式：LR 用 one-hot、树模型用统计量、NN 用 embedding
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# 低基数类别（适合 one-hot / 树模型）
LOW_CARD = ["category", "slot", "hour", "dow"]
# 高基数 ID（必须特殊处理）
HIGH_CARD = ["user_id", "item_id"]
# 交叉特征：CTR 的灵魂，也是 one-hot 维度的主要来源
CROSS = ["user_cat", "item_slot"]
CAT_COLS = HIGH_CARD + LOW_CARD + CROSS

NUM_COLS = [
    "u_imp_before", "u_clk_before", "u_ctr",
    "i_imp_before", "i_clk_before", "i_ctr",
    "uc_imp_before", "hist_gap", "log_price", "is_weekend",
]


# --------------------------------------------------------------------------- #
# 时间切分
# --------------------------------------------------------------------------- #
def time_split(df: pd.DataFrame, val_days: int = 5, test_days: int = 5):
    """按时间切：| train | valid(5d) | test(5d) |

    为什么不能随机切：随机切会让模型在训练时看到未来的用户行为/商品热度，
    离线指标虚高，上线后掉点。这是 CTR 里最常见的翻车方式。
    """
    t_max = df["ts"].max()
    test_start = t_max - pd.Timedelta(days=test_days)
    val_start = test_start - pd.Timedelta(days=val_days)
    train = df[df["ts"] < val_start].copy()
    valid = df[(df["ts"] >= val_start) & (df["ts"] < test_start)].copy()
    test = df[df["ts"] >= test_start].copy()
    return train, valid, test


# --------------------------------------------------------------------------- #
# 历史统计特征（核心：只回看，不前瞻）
# --------------------------------------------------------------------------- #
def add_history_features(df: pd.DataFrame) -> pd.DataFrame:
    """给每一行加上「截至这一行之前」的用户/商品累计行为。

    实现关键：先按 ts 排序，再用 cumsum 并减去当前行（等价于 shift(1).cumsum()）。
    这样第 1 行是 0，第 n 行只用前 n-1 行 —— 天然无前视。
    """
    df = df.sort_values("ts", kind="mergesort").reset_index(drop=True)

    g_user = df.groupby("user_id", sort=False)
    u_imp = g_user.cumcount()
    u_clk = g_user["label"].cumsum() - df["label"]
    u_gap = g_user["ts"].diff().dt.total_seconds()

    g_item = df.groupby("item_id", sort=False)
    i_imp = g_item.cumcount()
    i_clk = g_item["label"].cumsum() - df["label"]

    uc_imp = df.groupby(["user_id", "category"], sort=False).cumcount()

    df["u_imp_before"] = u_imp
    df["u_clk_before"] = u_clk
    # 贝叶斯平滑：样本少时回退到先验，避免"曝光1次点击1次=100%"
    df["u_ctr"] = (u_clk + 1) / (u_imp + 20)
    df["i_imp_before"] = i_imp
    df["i_clk_before"] = i_clk
    df["i_ctr"] = (i_clk + 1) / (i_imp + 20)
    df["uc_imp_before"] = uc_imp
    df["hist_gap"] = u_gap.fillna(1e6).clip(0, 1e6)
    df["log_price"] = np.log1p(df["price"])
    df["is_weekend"] = (df["dow"] >= 5).astype(int)

    # 交叉特征用字符串拼接（符号特征），交给 one-hot / hashing
    df["user_cat"] = df["user_id"].astype(str) + "_" + df["category"].astype(str)
    df["item_slot"] = df["item_id"].astype(str) + "_" + df["slot"].astype(str)
    return df


# --------------------------------------------------------------------------- #
# 三种模型各自需要的数据形态
# --------------------------------------------------------------------------- #
def make_lr_matrix(train, valid, test, min_frequency: int = 5):
    """LR：one-hot 高基数 ID + 交叉特征（稀疏矩阵）。

    min_frequency 会丢掉出现次数太少的 ID —— 这是「长尾 ID 无法泛化」的工程妥协，
    也是 LR + one-hot 被 DeepFM 取代的原因之一。
    """
    cat = OneHotEncoder(handle_unknown="ignore", min_frequency=min_frequency,
                        sparse_output=True, dtype=np.float32)
    num = StandardScaler()
    pre = ColumnTransformer([("cat", cat, CAT_COLS), ("num", num, NUM_COLS)])
    Xtr = pre.fit_transform(train[CAT_COLS + NUM_COLS])
    Xva = pre.transform(valid[CAT_COLS + NUM_COLS])
    Xte = pre.transform(test[CAT_COLS + NUM_COLS])
    return Xtr, Xva, Xte, pre


def make_tree_frame(df: pd.DataFrame):
    """树模型（GBDT）：不吃高基数 ID，只吃低基数类别 + 统计特征。

    这是工程上必须知道的取舍：LightGBM/XGBoost 直接 one-hot 百万级 ID 会爆炸，
    所以要么用 ID 的统计特征（本函数），要么把 ID 塞进 embedding（DeepFM）。
    """
    cols = NUM_COLS + LOW_CARD
    return df[cols].copy()


def make_deep_frame(df: pd.DataFrame, cardinality: dict):
    """NN（DeepFM）：ID 类走 embedding（需要把原始 ID 重编码成 0..C-1），
    数值类走连续输入。cardinality 记录每个字段的取值个数，用于建 Embedding 表。"""
    out = df[["user_id", "item_id", "category", "slot", "hour", "dow"] + NUM_COLS].copy()
    return out