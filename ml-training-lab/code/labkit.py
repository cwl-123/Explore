"""labkit.py — 合成电商曝光/点击数据集 + 评估指标。

为什么造假数据？
    真实数据（Criteo 11GB / 公司内部日志）第一周根本跑不动，也看不清因果。
    这里的数据是合成的，但保留了真实电商日志的四个关键结构：
      1. 用户/商品有隐向量，点击率来自隐向量的内积（所以"ID 类特征"真的有信息）
      2. 商品热度是 Zipf 长尾，用户活跃度是 lognormal（所以会有长尾与冷启动问题）
      3. 曝光位置有 position bias（slot 越小越容易被看到，而不是越容易被点）
      4. 时间上有周期性（晚上/周末点击率高），且用户行为随时间漂移

    生成器内部有真实概率 p_true，但特征工程只允许用「可见列」，
    任何用到 label 未来值的特征都算作弊 —— 见 03_leakage_lab.py。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score

N_CAT = 40  # 类目数


# --------------------------------------------------------------------------- #
# 1. 造数据
# --------------------------------------------------------------------------- #
def build_dataset(n_users: int = 12000, n_items: int = 3000, n_days: int = 30,
                  impressions_per_user: float = 8.0, seed: int = 42) -> pd.DataFrame:
    """生成一张曝光日志表，每行 = 一次曝光。

    列：ts, user_id, item_id, category, price, slot, hour, dow, label
    label = 是否点击（0/1），这是唯一的学习目标。
    另有 _p_true = 真实点击概率，只给教学分析用（算"天花板"），特征工程禁用。
    """
    rng = np.random.default_rng(seed)
    d = 8

    # ---- 隐因子：真实世界我们永远看不到，这里只用来生成 label ----
    u_vec = rng.normal(0, 0.45, (n_users, d))     # 用户兴趣
    v_vec = rng.normal(0, 0.45, (n_items, d))     # 商品属性
    cat_of_item = rng.integers(0, N_CAT, n_items)
    c_vec = rng.normal(0, 0.4, (N_CAT, d))        # 类目属性
    u_bias = rng.normal(0, 0.35, n_users)
    v_bias = rng.normal(0, 0.50, n_items)

    # ---- 可见的商品属性 ----
    price = np.round(np.exp(rng.normal(3.2, 0.9, n_items)), 1)      # 约 10~200 元
    pop = rng.zipf(1.6, n_items).astype(float)
    pop = pop / pop.sum()                                           # 长尾热度
    act = np.clip(rng.lognormal(0, 0.7, n_users), 0.2, None)         # 用户活跃度

    # ---- 生成曝光 ----
    n_imp = rng.poisson(impressions_per_user * act)   # 平均 8 次/人
    user_idx = np.repeat(np.arange(n_users), n_imp)
    n = len(user_idx)
    item_idx = rng.choice(n_items, size=n, p=pop)

    start = pd.Timestamp("2026-09-01")
    ts = start + pd.to_timedelta(rng.uniform(0, n_days * 86400, n), unit="s")

    slot = rng.integers(1, 9, n)                      # 1 = 最靠前的位置
    hour = ts.hour.to_numpy()
    dow = ts.day_of_week.to_numpy()

    # ---- 真实点击概率（logit 是可加结构，方便 LR 学一部分、学不全）----
    ui, ii = user_idx, item_idx
    logit = -3.6                                            # 基础点击率 ~10%
    logit += (u_vec[ui] * v_vec[ii]).sum(1)                 # 用户 × 商品 匹配度 ← 交互项！
    logit += (u_vec[ui] * c_vec[cat_of_item[ii]]).sum(1)    # 用户类目偏好
    logit += (v_vec[ii] * c_vec[cat_of_item[ii]]).sum(1)    # 商品与类目契合
    logit += u_bias[ui] + v_bias[ii]
    logit += -0.35 * np.log(price[ii] / 25.0)               # 越贵越不点
    logit += 0.30 * ((hour >= 20) & (hour <= 22))           # 晚间效应
    logit += 0.20 * (dow >= 5)                              # 周末效应
    logit += 0.25 * np.log1p(act[ui])                       # 活跃用户更爱点

    p_click = 1.0 / (1.0 + np.exp(-logit))
    # position bias：位置影响「被看到」，不是「被喜欢」，所以乘在曝光概率上
    p_exam = 1.0 / (1.0 + 0.22 * (slot - 1))
    label = (rng.random(n) < p_click * p_exam).astype(np.int8)

    df = pd.DataFrame({
        "ts": ts, "user_id": user_idx, "item_id": item_idx,
        "category": cat_of_item[ii], "price": price[ii],
        "slot": slot, "hour": hour, "dow": dow, "label": label,
    })
    df["_p_true"] = p_click * p_exam     # 真实概率，仅用于算模型"天花板"
    return df.sort_values("ts").reset_index(drop=True)


def ceiling_auc(df: pd.DataFrame) -> float:
    """用真实概率算的 AUC 天花板：任何模型都不可能超过它。

    知道天花板在哪，才知道 0.78 是"没做好"还是"到顶了"。
    """
    return roc_auc_score(df["label"], df["_p_true"])


# --------------------------------------------------------------------------- #
# 2. 评估指标
# --------------------------------------------------------------------------- #
def gauc(y_true, p, groups) -> float:
    """GAUC：按用户分组算 AUC 再加权平均（权重=样本数）。

    为什么需要它：AUC 是全局排序，跨用户可比性差；广告/推荐真正关心的是
    「同一个用户内部，把哪个商品排前面」。线上以 GAUC / 加权 AUC 为主要离线指标。
    """
    df = pd.DataFrame({"y": y_true, "p": p, "g": groups})
    num = den = 0.0
    for _, sub in df.groupby("g", sort=False):
        if sub["y"].nunique() < 2 or len(sub) < 3:
            continue
        a = roc_auc_score(sub["y"], sub["p"])
        num += a * len(sub)
        den += len(sub)
    return num / den if den else float("nan")


def calibration_table(y_true, p, n_bins: int = 10) -> pd.DataFrame:
    """校准表：每个预测区间里，平均预测值 vs 实际点击率。

    LogLoss 看的是概率准不准，AUC 看的是排序对不对 —— 这是两件事。
    广告出价（OCPC）用 pCTR 的绝对值算钱，所以必须校准。
    """
    df = pd.DataFrame({"y": np.asarray(y_true), "p": np.asarray(p)})
    df["bin"] = pd.cut(df["p"], bins=np.linspace(0, 1, n_bins + 1), include_lowest=True)
    out = df.groupby("bin", observed=True).agg(
        n=("y", "size"), pred=("p", "mean"), actual=("y", "mean")).reset_index()
    out["gap"] = out["actual"] - out["pred"]
    return out


def topk_lift(y_true, p, frac: float = 0.05) -> float:
    """业务向指标：按预测分排序取前 frac 曝光，其实际 CTR / 全局 CTR。

    线上最终看的就是这个（等价于 eCPM / RPM 的排序收益），AUC 只是它的代理。
    """
    y_true = np.asarray(y_true)
    k = max(1, int(len(y_true) * frac))
    idx = np.argsort(-np.asarray(p))[:k]
    base = y_true.mean()
    return float(y_true[idx].mean() / base) if base > 0 else float("nan")


def evaluate(y_true, p, groups=None, name: str = "") -> dict:
    """一次性打出四个指标。"""
    m = {
        "auc": roc_auc_score(y_true, p),
        "logloss": log_loss(y_true, np.clip(p, 1e-6, 1 - 1e-6)),
        "top5%_lift": topk_lift(y_true, p, 0.05),
    }
    if groups is not None:
        m["gauc"] = gauc(y_true, p, groups)
    if name:
        print(f"{name:<28} " + "  ".join(f"{k}={v:.4f}" for k, v in m.items()))
    return m