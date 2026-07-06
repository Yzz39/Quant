import argparse
import math
import os
from dataclasses import dataclass

import matplotlib
import numpy as np
import pandas as pd
from scipy.special import logsumexp


OUT_DIR = r"D:\Quant\outputs"
CACHE_PATH = os.path.join(OUT_DIR, "dashboard_cache", "hs300.csv")


LABEL_ORDER = ["bear", "sideways", "bull"]
LABEL_CN = {"bear": "bear", "sideways": "sideways", "bull": "bull"}


@dataclass
class GaussianHMM:
    startprob: np.ndarray
    transmat: np.ndarray
    means: np.ndarray
    vars: np.ndarray
    loglik: float

    @property
    def n_states(self) -> int:
        return len(self.means)


def load_hs300(path: str = CACHE_PATH, refresh: bool = False) -> pd.DataFrame:
    if refresh or not os.path.exists(path):
        import akshare as ak

        os.makedirs(os.path.dirname(path), exist_ok=True)
        df = ak.stock_zh_index_daily(symbol="sh000300")
        df = df[["date", "close"]].copy()
        df["date"] = pd.to_datetime(df["date"])
        df.to_csv(path, index=False)
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    df["ret"] = 100.0 * np.log(df["close"] / df["close"].shift(1))
    return df.dropna(subset=["ret"]).reset_index(drop=True)


def _normal_logpdf(x: np.ndarray, means: np.ndarray, vars_: np.ndarray) -> np.ndarray:
    x2 = x[:, None]
    return -0.5 * (np.log(2.0 * math.pi * vars_[None, :]) + ((x2 - means[None, :]) ** 2) / vars_[None, :])


def _forward_backward(log_start, log_trans, log_emit):
    n_obs, n_states = log_emit.shape
    alpha = np.empty((n_obs, n_states))
    beta = np.empty((n_obs, n_states))

    alpha[0] = log_start + log_emit[0]
    for t in range(1, n_obs):
        alpha[t] = log_emit[t] + logsumexp(alpha[t - 1][:, None] + log_trans, axis=0)

    beta[-1] = 0.0
    for t in range(n_obs - 2, -1, -1):
        beta[t] = logsumexp(log_trans + log_emit[t + 1][None, :] + beta[t + 1][None, :], axis=1)

    loglik = float(logsumexp(alpha[-1]))
    gamma_log = alpha + beta - loglik
    gamma = np.exp(gamma_log)

    xi_log = (
        alpha[:-1, :, None]
        + log_trans[None, :, :]
        + log_emit[1:, None, :]
        + beta[1:, None, :]
        - loglik
    )
    xi_sum = np.exp(xi_log).sum(axis=0)

    return gamma, xi_sum, loglik


def _initial_params(x: np.ndarray, n_states: int, seed: int):
    rng = np.random.default_rng(seed)
    qs = np.linspace(0.15, 0.85, n_states)
    means = np.quantile(x, qs)
    means += rng.normal(0, max(np.std(x), 1e-3) * 0.05, size=n_states)
    means = np.sort(means)
    vars_ = np.full(n_states, max(np.var(x), 1e-4))
    trans = np.full((n_states, n_states), 0.05 / (n_states - 1))
    np.fill_diagonal(trans, 0.95)
    start = np.full(n_states, 1.0 / n_states)
    return start, trans, means, vars_


def fit_hmm(x: np.ndarray, n_states: int = 3, n_init: int = 4, max_iter: int = 80, tol: float = 1e-5) -> GaussianHMM:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    best = None

    for seed in range(n_init):
        start, trans, means, vars_ = _initial_params(x, n_states, seed)
        prev = -np.inf

        for _ in range(max_iter):
            log_start = np.log(np.clip(start, 1e-12, 1.0))
            log_trans = np.log(np.clip(trans, 1e-12, 1.0))
            log_emit = _normal_logpdf(x, means, vars_)
            gamma, xi_sum, loglik = _forward_backward(log_start, log_trans, log_emit)

            weights = gamma.sum(axis=0) + 1e-12
            start = gamma[0] + 1e-12
            start = start / start.sum()
            trans = xi_sum + 1e-12
            trans = trans / trans.sum(axis=1, keepdims=True)
            means = (gamma * x[:, None]).sum(axis=0) / weights
            vars_ = (gamma * (x[:, None] - means[None, :]) ** 2).sum(axis=0) / weights
            vars_ = np.clip(vars_, 1e-5, None)

            if abs(loglik - prev) < tol:
                break
            prev = loglik

        model = GaussianHMM(start, trans, means, vars_, loglik)
        if best is None or model.loglik > best.loglik:
            best = model

    return sort_model_by_mean(best)


def sort_model_by_mean(model: GaussianHMM) -> GaussianHMM:
    order = np.argsort(model.means)
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    return GaussianHMM(
        startprob=model.startprob[order],
        transmat=model.transmat[order][:, order],
        means=model.means[order],
        vars=model.vars[order],
        loglik=model.loglik,
    )


def viterbi(model: GaussianHMM, x: np.ndarray, start_override: np.ndarray | None = None) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    start = model.startprob if start_override is None else start_override
    log_start = np.log(np.clip(start, 1e-12, 1.0))
    log_trans = np.log(np.clip(model.transmat, 1e-12, 1.0))
    log_emit = _normal_logpdf(x, model.means, model.vars)
    n_obs, n_states = log_emit.shape
    delta = np.empty((n_obs, n_states))
    psi = np.zeros((n_obs, n_states), dtype=int)

    delta[0] = log_start + log_emit[0]
    for t in range(1, n_obs):
        score = delta[t - 1][:, None] + log_trans
        psi[t] = np.argmax(score, axis=0)
        delta[t] = np.max(score, axis=0) + log_emit[t]

    states = np.empty(n_obs, dtype=int)
    states[-1] = int(np.argmax(delta[-1]))
    for t in range(n_obs - 2, -1, -1):
        states[t] = psi[t + 1, states[t + 1]]
    return states


def filter_states(model: GaussianHMM, x: np.ndarray, start_override: np.ndarray | None = None):
    x = np.asarray(x, dtype=float)
    start = model.startprob if start_override is None else start_override
    log_trans = np.log(np.clip(model.transmat, 1e-12, 1.0))
    log_emit = _normal_logpdf(x, model.means, model.vars)
    alpha = np.empty_like(log_emit)
    alpha[0] = np.log(np.clip(start, 1e-12, 1.0)) + log_emit[0]
    alpha[0] -= logsumexp(alpha[0])
    for t in range(1, len(x)):
        alpha[t] = log_emit[t] + logsumexp(alpha[t - 1][:, None] + log_trans, axis=0)
        alpha[t] -= logsumexp(alpha[t])
    probs = np.exp(alpha)
    return np.argmax(probs, axis=1), probs


def state_labels(states: np.ndarray) -> list[str]:
    return [LABEL_ORDER[int(s)] for s in states]


def posterior_at_end(model: GaussianHMM, x: np.ndarray):
    _, probs = filter_states(model, x)
    return probs[-1]


def make_segments(df: pd.DataFrame, label_col: str, min_days: int = 1) -> pd.DataFrame:
    rows = []
    labels = df[label_col].tolist()
    start = 0
    for i in range(1, len(df) + 1):
        if i == len(df) or labels[i] != labels[start]:
            seg = df.iloc[start:i]
            rows.append(
                {
                    "label": labels[start],
                    "start": seg["date"].iloc[0].date().isoformat(),
                    "end": seg["date"].iloc[-1].date().isoformat(),
                    "days": len(seg),
                    "start_close": round(float(seg["close"].iloc[0]), 3),
                    "end_close": round(float(seg["close"].iloc[-1]), 3),
                    "segment_return": float(seg["close"].iloc[-1] / seg["close"].iloc[0] - 1.0),
                    "mean_daily_ret": float(seg["ret"].mean()),
                    "ann_vol": float(seg["ret"].std(ddof=0) * np.sqrt(252)),
                }
            )
            start = i
    out = pd.DataFrame(rows)
    if min_days > 1:
        out = out[out["days"] >= min_days].reset_index(drop=True)
    return out


def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for h in [20, 60, 120, 250]:
        out[f"fwd_{h}d"] = out["close"].shift(-h) / out["close"] - 1.0
    return out


def conditional_stats(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    rows = []
    for label in LABEL_ORDER:
        sub = df[df[label_col] == label]
        row = {
            "label": label,
            "days": int(len(sub)),
            "share": float(len(sub) / len(df)) if len(df) else np.nan,
            "same_day_mean": float(sub["ret"].mean()),
            "same_day_ann_vol": float(sub["ret"].std(ddof=0) * np.sqrt(252)),
        }
        for h in [20, 60, 120, 250]:
            row[f"mean_fwd_{h}d"] = float(sub[f"fwd_{h}d"].mean())
            row[f"hit_fwd_{h}d"] = float((sub[f"fwd_{h}d"] > 0).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def fit_window(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    return df[(df["date"] >= s) & (df["date"] <= e)].copy()


def write_summary(
    path: str,
    train_df: pd.DataFrame,
    post_df: pd.DataFrame,
    train_model: GaussianHMM,
    post_model: GaussianHMM,
    fixed_stats: pd.DataFrame,
    refit_stats: pd.DataFrame,
    fixed_segments: pd.DataFrame,
    refit_segments: pd.DataFrame,
) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write("HS300 3-state Gaussian HMM regime decoding\n")
        f.write(f"train sample: {train_df['date'].min().date()} to {train_df['date'].max().date()}, n={len(train_df)}\n")
        f.write(f"post sample : {post_df['date'].min().date()} to {post_df['date'].max().date()}, n={len(post_df)}\n\n")
        f.write("Model fitted on paper-era sample, states sorted by daily return mean:\n")
        for label, mean, var in zip(LABEL_ORDER, train_model.means, train_model.vars):
            f.write(f"  {label:8s} mean={mean:+.4f}%  ann_vol={math.sqrt(var) * math.sqrt(252):.2f}%\n")
        f.write("Transition matrix:\n")
        f.write(pd.DataFrame(train_model.transmat, index=LABEL_ORDER, columns=LABEL_ORDER).round(4).to_string())
        f.write("\n\n")

        f.write("Model refitted on post-2016 sample, states sorted by daily return mean:\n")
        for label, mean, var in zip(LABEL_ORDER, post_model.means, post_model.vars):
            f.write(f"  {label:8s} mean={mean:+.4f}%  ann_vol={math.sqrt(var) * math.sqrt(252):.2f}%\n")
        f.write("Transition matrix:\n")
        f.write(pd.DataFrame(post_model.transmat, index=LABEL_ORDER, columns=LABEL_ORDER).round(4).to_string())
        f.write("\n\n")

        f.write("Fixed pre-2016 model, post-2016 conditional forward returns:\n")
        f.write(fixed_stats.round(4).to_string(index=False))
        f.write("\n\n")
        f.write("Post-2016 refit model, post-2016 conditional forward returns:\n")
        f.write(refit_stats.round(4).to_string(index=False))
        f.write("\n\n")
        f.write("Fixed model segments >= 20 trading days:\n")
        f.write(fixed_segments[fixed_segments["days"] >= 20].round(4).to_string(index=False))
        f.write("\n\n")
        f.write("Post-refit model segments >= 20 trading days:\n")
        f.write(refit_segments[refit_segments["days"] >= 20].round(4).to_string(index=False))
        f.write("\n")


def plot_regimes(df: pd.DataFrame, path: str) -> None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"bear": "#f4b6b6", "sideways": "#eeeeee", "bull": "#bfe3c0"}
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    configs = [("fixed_label", "Fixed 2005-2016 model"), ("refit_label", "Post-2016 refit model")]
    for ax, (col, title) in zip(axes, configs):
        ax.plot(df["date"], df["close"], color="#222222", lw=0.9)
        y1, y2 = df["close"].min(), df["close"].max()
        for label, color in colors.items():
            mask = df[col] == label
            ax.fill_between(df["date"], y1, y2, where=mask, color=color, alpha=0.35, step="mid")
        ax.set_title(title)
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--post-start", default="2016-05-16")
    parser.add_argument("--train-start", default="2005-04-08")
    parser.add_argument("--train-end", default="2016-05-13")
    parser.add_argument("--n-init", type=int, default=4)
    parser.add_argument("--max-iter", type=int, default=80)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_hs300(refresh=args.refresh)
    train_df = fit_window(df, args.train_start, args.train_end)
    post_df = df[df["date"] >= pd.Timestamp(args.post_start)].copy().reset_index(drop=True)
    post_df = add_forward_returns(post_df)

    train_model = fit_hmm(train_df["ret"].to_numpy(), n_init=args.n_init, max_iter=args.max_iter)
    post_model = fit_hmm(post_df["ret"].to_numpy(), n_init=args.n_init, max_iter=args.max_iter)

    train_end_prob = posterior_at_end(train_model, train_df["ret"].to_numpy())
    fixed_states, fixed_probs = filter_states(train_model, post_df["ret"].to_numpy(), start_override=train_end_prob)
    refit_states = viterbi(post_model, post_df["ret"].to_numpy())

    post_df["fixed_state"] = fixed_states
    post_df["fixed_label"] = state_labels(fixed_states)
    post_df["refit_state"] = refit_states
    post_df["refit_label"] = state_labels(refit_states)
    for i, label in enumerate(LABEL_ORDER):
        post_df[f"fixed_prob_{label}"] = fixed_probs[:, i]

    fixed_stats = conditional_stats(post_df, "fixed_label")
    refit_stats = conditional_stats(post_df, "refit_label")
    fixed_segments = make_segments(post_df, "fixed_label")
    refit_segments = make_segments(post_df, "refit_label")

    out_csv = os.path.join(OUT_DIR, "hs300_hmm_regimes_2016_2026.csv")
    out_fixed_seg = os.path.join(OUT_DIR, "hs300_hmm_segments_fixed_2016_2026.csv")
    out_refit_seg = os.path.join(OUT_DIR, "hs300_hmm_segments_refit_2016_2026.csv")
    out_summary = os.path.join(OUT_DIR, "hs300_hmm_evaluation_2016_2026.txt")
    out_png = os.path.join(OUT_DIR, "hs300_hmm_regimes_2016_2026.png")

    post_df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    fixed_segments.to_csv(out_fixed_seg, index=False, encoding="utf-8-sig")
    refit_segments.to_csv(out_refit_seg, index=False, encoding="utf-8-sig")
    write_summary(
        out_summary,
        train_df,
        post_df,
        train_model,
        post_model,
        fixed_stats,
        refit_stats,
        fixed_segments,
        refit_segments,
    )
    plot_regimes(post_df, out_png)

    print(f"train: {train_df['date'].min().date()} to {train_df['date'].max().date()} n={len(train_df)}")
    print(f"post : {post_df['date'].min().date()} to {post_df['date'].max().date()} n={len(post_df)}")
    print("pre-2016 fitted state means:", dict(zip(LABEL_ORDER, np.round(train_model.means, 4))))
    print("post-2016 refit state means:", dict(zip(LABEL_ORDER, np.round(post_model.means, 4))))
    print("\nfixed model conditional stats")
    print(fixed_stats.round(4).to_string(index=False))
    print("\npost-refit model conditional stats")
    print(refit_stats.round(4).to_string(index=False))
    print("\nfixed model segments >= 20d")
    print(fixed_segments[fixed_segments["days"] >= 20].round(4).to_string(index=False))
    print("\npost-refit model segments >= 20d")
    print(refit_segments[refit_segments["days"] >= 20].round(4).to_string(index=False))
    print("\nfiles:")
    print(out_csv)
    print(out_fixed_seg)
    print(out_refit_seg)
    print(out_summary)
    print(out_png)


if __name__ == "__main__":
    main()
