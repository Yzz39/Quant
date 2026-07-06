import argparse
import os

import matplotlib
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from sklearn.mixture import GaussianMixture


OUT_DIR = r"D:\Quant\outputs"
CACHE_PATH = os.path.join(OUT_DIR, "dashboard_cache", "hs300.csv")
LABELS = ["bear", "sideways", "bull"]


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


def normal_logpdf(x: np.ndarray, means: np.ndarray, vars_: np.ndarray) -> np.ndarray:
    return -0.5 * (np.log(2 * np.pi * vars_[None, :]) + ((x[:, None] - means[None, :]) ** 2) / vars_[None, :])


def fit_gmm_states(x: np.ndarray, n_init: int = 30) -> dict:
    x2 = np.asarray(x, dtype=float).reshape(-1, 1)
    model = GaussianMixture(
        n_components=3,
        covariance_type="full",
        n_init=n_init,
        random_state=42,
        reg_covar=1e-5,
    ).fit(x2)
    means = model.means_.reshape(-1)
    vars_ = model.covariances_.reshape(-1)
    weights = model.weights_.reshape(-1)
    order = np.argsort(means)
    return {
        "means": means[order],
        "vars": vars_[order],
        "weights": weights[order] / weights[order].sum(),
    }


def viterbi_decode(
    x: np.ndarray,
    means: np.ndarray,
    vars: np.ndarray,
    weights: np.ndarray,
    stay_prob: float = 0.985,
    start_prob: np.ndarray | None = None,
) -> np.ndarray:
    n_states = len(means)
    offdiag = (1.0 - stay_prob) / (n_states - 1)
    trans = np.full((n_states, n_states), offdiag)
    np.fill_diagonal(trans, stay_prob)
    start = weights if start_prob is None else start_prob
    log_emit = normal_logpdf(np.asarray(x, dtype=float), means, vars)
    log_trans = np.log(trans)
    delta = np.empty_like(log_emit)
    psi = np.zeros_like(log_emit, dtype=int)
    delta[0] = np.log(np.clip(start, 1e-12, 1.0)) + log_emit[0]
    for t in range(1, len(x)):
        score = delta[t - 1][:, None] + log_trans
        psi[t] = np.argmax(score, axis=0)
        delta[t] = np.max(score, axis=0) + log_emit[t]
    states = np.empty(len(x), dtype=int)
    states[-1] = int(np.argmax(delta[-1]))
    for t in range(len(x) - 2, -1, -1):
        states[t] = psi[t + 1, states[t + 1]]
    return states


def filtered_probs(
    x: np.ndarray,
    means: np.ndarray,
    vars: np.ndarray,
    weights: np.ndarray,
    stay_prob: float = 0.985,
    start_prob: np.ndarray | None = None,
) -> np.ndarray:
    n_states = len(means)
    offdiag = (1.0 - stay_prob) / (n_states - 1)
    trans = np.full((n_states, n_states), offdiag)
    np.fill_diagonal(trans, stay_prob)
    start = weights if start_prob is None else start_prob
    log_emit = normal_logpdf(np.asarray(x, dtype=float), means, vars)
    log_trans = np.log(trans)
    alpha = np.empty_like(log_emit)
    alpha[0] = np.log(np.clip(start, 1e-12, 1.0)) + log_emit[0]
    alpha[0] -= logsumexp(alpha[0])
    for t in range(1, len(x)):
        alpha[t] = log_emit[t] + logsumexp(alpha[t - 1][:, None] + log_trans, axis=0)
        alpha[t] -= logsumexp(alpha[t])
    return np.exp(alpha)


def label_states(states: np.ndarray) -> list[str]:
    return [LABELS[int(s)] for s in states]


def add_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for h in [20, 60, 120, 250]:
        out[f"fwd_{h}d"] = out["close"].shift(-h) / out["close"] - 1.0
    return out


def segments(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    rows = []
    start = 0
    vals = df[label_col].to_list()
    for i in range(1, len(df) + 1):
        if i == len(df) or vals[i] != vals[start]:
            seg = df.iloc[start:i]
            rows.append(
                {
                    "label": vals[start],
                    "start": seg["date"].iloc[0].date().isoformat(),
                    "end": seg["date"].iloc[-1].date().isoformat(),
                    "days": len(seg),
                    "start_close": round(float(seg["close"].iloc[0]), 3),
                    "end_close": round(float(seg["close"].iloc[-1]), 3),
                    "segment_return": float(seg["close"].iloc[-1] / seg["close"].iloc[0] - 1.0),
                    "mean_daily_ret_pct": float(seg["ret"].mean()),
                    "ann_vol_pct": float(seg["ret"].std(ddof=0) * np.sqrt(252)),
                }
            )
            start = i
    return pd.DataFrame(rows)


def conditional_stats(df: pd.DataFrame, label_col: str) -> pd.DataFrame:
    rows = []
    for label in LABELS:
        sub = df[df[label_col] == label]
        row = {
            "label": label,
            "days": len(sub),
            "share": len(sub) / len(df),
            "mean_ret_pct": sub["ret"].mean(),
            "ann_vol_pct": sub["ret"].std(ddof=0) * np.sqrt(252),
        }
        for h in [20, 60, 120, 250]:
            row[f"mean_fwd_{h}d"] = sub[f"fwd_{h}d"].mean()
            row[f"hit_fwd_{h}d"] = (sub[f"fwd_{h}d"] > 0).mean()
        rows.append(row)
    return pd.DataFrame(rows)


def plot_regimes(df: pd.DataFrame, png_path: str) -> None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"bear": "#f3b3b3", "sideways": "#eeeeee", "bull": "#bfe3c0"}
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    for ax, col, title in [
        (axes[0], "fixed_label", "Paper-era distribution + Viterbi smoothing"),
        (axes[1], "refit_label", "Post-2016 distribution + Viterbi smoothing"),
    ]:
        ax.plot(df["date"], df["close"], color="#202020", lw=0.9)
        y1, y2 = df["close"].min(), df["close"].max()
        for label, color in colors.items():
            mask = df[col] == label
            ax.fill_between(df["date"], y1, y2, where=mask, step="mid", color=color, alpha=0.38)
        ax.set_title(title)
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(png_path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--train-start", default="2005-04-08")
    parser.add_argument("--train-end", default="2016-05-13")
    parser.add_argument("--post-start", default="2016-05-16")
    parser.add_argument("--stay-prob", type=float, default=0.985)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    df = load_hs300(refresh=args.refresh)
    train = df[(df["date"] >= args.train_start) & (df["date"] <= args.train_end)].copy()
    post = df[df["date"] >= args.post_start].copy().reset_index(drop=True)
    post = add_forward_returns(post)

    train_params = fit_gmm_states(train["ret"].to_numpy())
    post_params = fit_gmm_states(post["ret"].to_numpy())

    train_probs = filtered_probs(train["ret"].to_numpy(), **train_params, stay_prob=args.stay_prob)
    fixed_states = viterbi_decode(
        post["ret"].to_numpy(),
        **train_params,
        stay_prob=args.stay_prob,
        start_prob=train_probs[-1],
    )
    refit_states = viterbi_decode(post["ret"].to_numpy(), **post_params, stay_prob=args.stay_prob)

    post["fixed_state"] = fixed_states
    post["fixed_label"] = label_states(fixed_states)
    post["refit_state"] = refit_states
    post["refit_label"] = label_states(refit_states)
    fixed_probs = filtered_probs(post["ret"].to_numpy(), **train_params, stay_prob=args.stay_prob, start_prob=train_probs[-1])
    for i, label in enumerate(LABELS):
        post[f"fixed_prob_{label}"] = fixed_probs[:, i]

    fixed_segments = segments(post, "fixed_label")
    refit_segments = segments(post, "refit_label")
    fixed_stats = conditional_stats(post, "fixed_label")
    refit_stats = conditional_stats(post, "refit_label")

    out_csv = os.path.join(OUT_DIR, "hs300_gmm_viterbi_regimes_2016_2026.csv")
    out_fixed_seg = os.path.join(OUT_DIR, "hs300_gmm_viterbi_segments_fixed_2016_2026.csv")
    out_refit_seg = os.path.join(OUT_DIR, "hs300_gmm_viterbi_segments_refit_2016_2026.csv")
    out_summary = os.path.join(OUT_DIR, "hs300_gmm_viterbi_evaluation_2016_2026.txt")
    out_png = os.path.join(OUT_DIR, "hs300_gmm_viterbi_regimes_2016_2026.png")

    post.to_csv(out_csv, index=False, encoding="utf-8-sig")
    fixed_segments.to_csv(out_fixed_seg, index=False, encoding="utf-8-sig")
    refit_segments.to_csv(out_refit_seg, index=False, encoding="utf-8-sig")
    plot_regimes(post, out_png)

    with open(out_summary, "w", encoding="utf-8") as f:
        f.write("CSI 300 post-2016 regime decoding with 3-state Gaussian emissions + Viterbi smoothing\n")
        f.write(f"train sample: {train['date'].min().date()} to {train['date'].max().date()}, n={len(train)}\n")
        f.write(f"post sample : {post['date'].min().date()} to {post['date'].max().date()}, n={len(post)}\n")
        f.write(f"stay_prob   : {args.stay_prob}\n\n")
        f.write("Paper-era emission states sorted by mean daily log return (%):\n")
        f.write(pd.DataFrame({"label": LABELS, **train_params}).round(4).to_string(index=False))
        f.write("\n\nPost-2016 refit emission states sorted by mean daily log return (%):\n")
        f.write(pd.DataFrame({"label": LABELS, **post_params}).round(4).to_string(index=False))
        f.write("\n\nFixed model conditional stats:\n")
        f.write(fixed_stats.round(4).to_string(index=False))
        f.write("\n\nRefit model conditional stats:\n")
        f.write(refit_stats.round(4).to_string(index=False))
        f.write("\n\nFixed model segments >= 20 trading days:\n")
        f.write(fixed_segments[fixed_segments["days"] >= 20].round(4).to_string(index=False))
        f.write("\n\nRefit model segments >= 20 trading days:\n")
        f.write(refit_segments[refit_segments["days"] >= 20].round(4).to_string(index=False))
        f.write("\n")

    print(f"train: {train['date'].min().date()} to {train['date'].max().date()} n={len(train)}")
    print(f"post : {post['date'].min().date()} to {post['date'].max().date()} n={len(post)}")
    print("\npaper-era emission states")
    print(pd.DataFrame({"label": LABELS, **train_params}).round(4).to_string(index=False))
    print("\npost-2016 refit emission states")
    print(pd.DataFrame({"label": LABELS, **post_params}).round(4).to_string(index=False))
    print("\nfixed model conditional stats")
    print(fixed_stats.round(4).to_string(index=False))
    print("\nrefit model conditional stats")
    print(refit_stats.round(4).to_string(index=False))
    print("\nfixed model segments >=20d")
    print(fixed_segments[fixed_segments["days"] >= 20].round(4).to_string(index=False))
    print("\nrefit model segments >=20d")
    print(refit_segments[refit_segments["days"] >= 20].round(4).to_string(index=False))
    print("\nfiles")
    print(out_csv)
    print(out_fixed_seg)
    print(out_refit_seg)
    print(out_summary)
    print(out_png)


if __name__ == "__main__":
    main()
