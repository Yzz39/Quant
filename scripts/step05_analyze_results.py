from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "gptCode" / "05Data"

MODES = [
    "momentum",
    "m1_absolute",
    "m2_recent_confirm",
    "m2_ranked_recent",
    "m3_ols_slope",
    "m3b_efficiency",
    "m3c_bias_trend",
    "m3d_wls_slope",
    "m3e_huber_slope",
    "m3f_equal_rank",
    "m3g_efficiency_rank",
]
MODE_LABELS = {
    "momentum": "M0 相对动量",
    "m1_absolute": "M1 绝对动量",
    "m2_recent_confirm": "M2 近期确认",
    "m2_ranked_recent": "M2R 排名内近期确认",
    "m3_ols_slope": "M3A OLS斜率质量",
    "m3b_efficiency": "M3B 效率动量",
    "m3c_bias_trend": "M3C 乖离趋势",
    "m3d_wls_slope": "M3D WLS斜率质量",
    "m3e_huber_slope": "M3E Huber斜率质量",
    "m3f_equal_rank": "M3F 等权排名融合",
    "m3g_efficiency_rank": "M3G 效率动量复核",
}
LOOKBACKS = [252, 126, 63, 31, 14]
INTERVALS = [20, 10, 5, 1]
YEARS = 6.0

NUMERIC_FIELDS = [
    "strategy_return_pct",
    "benchmark_return_pct",
    "alpha",
    "beta",
    "sharpe",
    "max_drawdown_pct",
]


def as_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalize_row(row: dict[str, object]) -> dict[str, object]:
    normalized = dict(row)
    normalized["lookback"] = int(row["lookback"])
    normalized["rebalance_interval"] = int(row["rebalance_interval"])
    for field in NUMERIC_FIELDS:
        normalized[field] = as_float(row.get(field))
    normalized.setdefault("source_note", "")
    normalized.setdefault("image_file", "")
    return normalized


def complete_row(
    mode: str,
    lookback: int,
    interval: int,
    strategy_return: float,
    alpha: float,
    beta: float,
    sharpe: float,
    max_drawdown: float,
    image_file: str,
    source_note: str,
) -> dict[str, object]:
    return {
        "run_mode": mode,
        "lookback": lookback,
        "rebalance_interval": interval,
        "status": "complete",
        "strategy_return_pct": strategy_return,
        "benchmark_return_pct": 47.47,
        "alpha": alpha,
        "beta": beta,
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown,
        "image_file": image_file,
        "source_note": source_note,
    }


def load_observed_rows() -> dict[tuple[str, int, int], dict[str, object]]:
    observed: dict[tuple[str, int, int], dict[str, object]] = {}

    early_rows = [normalize_row(row) for row in read_csv(DATA_DIR / "step05_early_results.csv")]
    for row in early_rows:
        if row["status"] == "complete":
            # 本轮所有截图使用同一沪深300基准，界面顶部固定显示47.47%。
            # 个别截图的悬浮提示会干扰分栏OCR，因此以冻结基准值校正。
            row["benchmark_return_pct"] = 47.47
        key = (str(row["run_mode"]), int(row["lookback"]), int(row["rebalance_interval"]))
        row["source_note"] = "早期截图OCR；参数由代码区或红色标注复核"
        observed[key] = row

    supplements = [
        complete_row(
            "m1_absolute", 31, 10, 40.51, 0.01, 0.42, 0.11, 23.91,
            "Snipaste_2026-07-16_00-07-30.png", "补图替换原运行中截图",
        ),
        complete_row(
            "momentum", 126, 5, 12.44, -0.03, 0.51, -0.10, 50.57,
            "Snipaste_2026-07-16_00-14-45.png", "补图替换原运行中截图",
        ),
        complete_row(
            "momentum", 63, 5, 47.09, 0.01, 0.47, 0.14, 43.69,
            "Snipaste_2026-07-16_00-16-05.png", "补图替换原运行中截图",
        ),
        complete_row(
            "m2_recent_confirm", 63, 20, -18.83, -0.08, 0.30, -0.50, 53.79,
            "Snipaste_2026-07-16_00-37-10.png", "补图替换原运行中截图",
        ),
    ]
    for row in supplements:
        key = (str(row["run_mode"]), int(row["lookback"]), int(row["rebalance_interval"]))
        observed[key] = normalize_row(row)

    named_files = [
        "m3c_bias_trend_results.csv",
        "m3d_wls_slope_results.csv",
        "m3e_huber_slope_results.csv",
        "m3f_equal_rank_results.csv",
        "m3g_efficiency_rank_results.csv",
    ]
    for filename in named_files:
        for raw in read_csv(DATA_DIR / filename):
            row = normalize_row(raw)
            key = (str(row["run_mode"]), int(row["lookback"]), int(row["rebalance_interval"]))
            row["source_note"] = filename
            observed[key] = row

    # M3C 126x1 文件名与日志不一致：该截图日志明确为 f5，不能重复计为 f1。
    observed[("m3c_bias_trend", 126, 5)] = normalize_row(
        complete_row(
            "m3c_bias_trend", 126, 5, 27.58, -0.01, 0.37, 0.01, 38.03,
            "Snipaste_2026-07-16_00-18-46.png",
            "补图确认f5；原m3c_bias_trend_lb126_f1.png日志同样为f5",
        )
    )
    observed[("m3c_bias_trend", 126, 1)] = normalize_row(
        {
            "run_mode": "m3c_bias_trend",
            "lookback": 126,
            "rebalance_interval": 1,
            "status": "missing_config_mismatch",
            "strategy_return_pct": None,
            "benchmark_return_pct": None,
            "alpha": None,
            "beta": None,
            "sharpe": None,
            "max_drawdown_pct": None,
            "image_file": "m3c_bias_trend_lb126_f1.png",
            "source_note": "文件名写f1，但图内S05_CODE_VERSION与S05_CONFIG均为f5",
        }
    )

    observed[("m3e_huber_slope", 126, 1)] = normalize_row(
        complete_row(
            "m3e_huber_slope", 126, 1, 73.66, 0.05, 0.48, 0.30, 34.67,
            "Snipaste_2026-07-16_00-40-15.png", "补图替换原6x2无效附件",
        )
    )
    return observed


def add_metrics(row: dict[str, object]) -> dict[str, object]:
    enriched = dict(row)
    total_return = as_float(row.get("strategy_return_pct"))
    benchmark_return = as_float(row.get("benchmark_return_pct"))
    max_drawdown = as_float(row.get("max_drawdown_pct"))
    if row.get("status") == "complete" and total_return is not None and total_return > -100:
        cagr = (1.0 + total_return / 100.0) ** (1.0 / YEARS) - 1.0
        enriched["cagr_pct"] = cagr * 100.0
        if benchmark_return is not None and benchmark_return > -100:
            benchmark_cagr = (1.0 + benchmark_return / 100.0) ** (1.0 / YEARS) - 1.0
            enriched["benchmark_cagr_pct"] = benchmark_cagr * 100.0
            enriched["annualized_excess_pct"] = (cagr - benchmark_cagr) * 100.0
        else:
            enriched["benchmark_cagr_pct"] = None
            enriched["annualized_excess_pct"] = None
        enriched["calmar"] = cagr / (max_drawdown / 100.0) if max_drawdown and max_drawdown > 0 else None
    else:
        enriched["cagr_pct"] = None
        enriched["benchmark_cagr_pct"] = None
        enriched["annualized_excess_pct"] = None
        enriched["calmar"] = None

    excess = enriched["annualized_excess_pct"]
    calmar = enriched["calmar"]
    cagr_pct = enriched["cagr_pct"]
    enriched["positive_annualized_excess"] = bool(excess is not None and excess > 0)
    enriched["calmar_ge_0_3"] = bool(calmar is not None and calmar >= 0.3)
    enriched["step04_numeric_gate"] = bool(
        cagr_pct is not None
        and cagr_pct >= 6.22
        and max_drawdown is not None
        and max_drawdown <= 34.96
        and calmar is not None
        and calmar >= 0.4
    )
    return enriched


def build_grid() -> list[dict[str, object]]:
    observed = load_observed_rows()
    rows: list[dict[str, object]] = []
    for mode in MODES:
        for lookback in LOOKBACKS:
            for interval in INTERVALS:
                key = (mode, lookback, interval)
                if key in observed:
                    row = observed[key]
                else:
                    status = "missing_not_run" if mode == "m3b_efficiency" else "missing_not_provided"
                    row = normalize_row(
                        {
                            "run_mode": mode,
                            "lookback": lookback,
                            "rebalance_interval": interval,
                            "status": status,
                            "strategy_return_pct": None,
                            "benchmark_return_pct": None,
                            "alpha": None,
                            "beta": None,
                            "sharpe": None,
                            "max_drawdown_pct": None,
                            "image_file": "",
                            "source_note": "未取得最终截图指标",
                        }
                    )
                rows.append(add_metrics(row))
    return rows


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def fmt(value: object, digits: int = 2) -> str:
    if value is None or value == "":
        return "—"
    return f"{float(value):.{digits}f}"


def build_mode_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["run_mode"])].append(row)

    summaries: list[dict[str, object]] = []
    for mode in MODES:
        mode_rows = grouped[mode]
        complete = [row for row in mode_rows if row["status"] == "complete"]
        calmars = [float(row["calmar"]) for row in complete if row["calmar"] is not None]
        median_calmar = median(calmars)
        best_calmar = max(calmars) if calmars else None
        windows_with_two = 0
        for lookback in LOOKBACKS:
            count = sum(
                1 for row in complete
                if row["lookback"] == lookback and row["annualized_excess_pct"] is not None and row["annualized_excess_pct"] >= 0
            )
            windows_with_two += count >= 2
        frequencies_with_three = 0
        for interval in INTERVALS:
            count = sum(
                1 for row in complete
                if row["rebalance_interval"] == interval and row["annualized_excess_pct"] is not None and row["annualized_excess_pct"] >= 0
            )
            frequencies_with_three += count >= 3

        complete_count = len(complete)
        positive_excess = sum(bool(row["positive_annualized_excess"]) for row in complete)
        calmar_count = sum(bool(row["calmar_ge_0_3"]) for row in complete)
        numeric_gate_count = sum(bool(row["step04_numeric_gate"]) for row in complete)
        preliminary = (
            complete_count == 20
            and positive_excess >= 12
            and calmar_count >= 12
            and median_calmar is not None
            and median_calmar >= 0.3
            and best_calmar is not None
            and best_calmar <= median_calmar * 2
            and windows_with_two >= 3
            and frequencies_with_three >= 3
            and numeric_gate_count >= 1
        )
        summaries.append(
            {
                "run_mode": mode,
                "mode_label": MODE_LABELS[mode],
                "complete_count": complete_count,
                "missing_count": 20 - complete_count,
                "positive_excess_count": positive_excess,
                "calmar_ge_0_3_count": calmar_count,
                "median_calmar": median_calmar,
                "best_calmar": best_calmar,
                "best_to_median_calmar": (best_calmar / median_calmar) if median_calmar and median_calmar > 0 else None,
                "windows_with_two_nonnegative_excess_frequencies": windows_with_two,
                "frequencies_with_three_nonnegative_excess_windows": frequencies_with_three,
                "step04_numeric_gate_count": numeric_gate_count,
                "preliminary_screenshot_gate": preliminary,
                "final_acceptance": False,
                "final_acceptance_note": "截图缺少标签精度、换手、成本、年度与资产归因，不能完成正式验收",
            }
        )
    return summaries


def build_axis_summary(rows: list[dict[str, object]], axis: str) -> list[dict[str, object]]:
    values = LOOKBACKS if axis == "lookback" else INTERVALS
    result: list[dict[str, object]] = []
    for mode in MODES:
        for value in values:
            subset = [
                row for row in rows
                if row["run_mode"] == mode and row[axis] == value and row["status"] == "complete"
            ]
            result.append(
                {
                    "run_mode": mode,
                    axis: value,
                    "complete_count": len(subset),
                    "median_cagr_pct": median([float(row["cagr_pct"]) for row in subset if row["cagr_pct"] is not None]),
                    "median_calmar": median([float(row["calmar"]) for row in subset if row["calmar"] is not None]),
                    "positive_excess_count": sum(bool(row["positive_annualized_excess"]) for row in subset),
                    "step04_numeric_gate_count": sum(bool(row["step04_numeric_gate"]) for row in subset),
                }
            )
    return result


def build_parameter_cell_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    # M3B/M3G为同一公式家族，且M3B未运行；跨模式参数统计排除这两个入口，
    # 避免把同一因子重复计权或让M3G的选择性缺图扭曲比较。
    eligible_modes = [mode for mode in MODES if mode not in {"m3b_efficiency", "m3g_efficiency_rank"}]
    result: list[dict[str, object]] = []
    for lookback in LOOKBACKS:
        for interval in INTERVALS:
            subset = [
                row for row in rows
                if row["run_mode"] in eligible_modes
                and row["lookback"] == lookback
                and row["rebalance_interval"] == interval
                and row["status"] == "complete"
            ]
            result.append(
                {
                    "lookback": lookback,
                    "rebalance_interval": interval,
                    "complete_mode_count": len(subset),
                    "median_cagr_pct": median([float(row["cagr_pct"]) for row in subset if row["cagr_pct"] is not None]),
                    "median_calmar": median([float(row["calmar"]) for row in subset if row["calmar"] is not None]),
                    "positive_excess_mode_count": sum(bool(row["positive_annualized_excess"]) for row in subset),
                    "step04_numeric_gate_mode_count": sum(bool(row["step04_numeric_gate"]) for row in subset),
                }
            )
    return result


def write_analysis(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    parameter_cells: list[dict[str, object]],
) -> None:
    complete_count = sum(row["status"] == "complete" for row in rows)
    missing_rows = [row for row in rows if row["status"] != "complete"]
    ranked = sorted(
        summaries,
        key=lambda row: (
            int(row["complete_count"] == 20),
            float(row["median_calmar"]) if row["median_calmar"] is not None else -999,
        ),
        reverse=True,
    )

    lines = [
        "# 步骤05参数稳定性结构化分析",
        "",
        "## 数据覆盖与证据边界",
        "",
        f"- 预注册矩阵：220组；当前取得可识别最终指标 {complete_count}/220 组（{complete_count / 220:.1%}）。",
        f"- 仍缺 {len(missing_rows)} 组：M3B 20组未运行、M3C 126×1 配置证据不成立、M3G 5组未提供。",
        "- M3B与M3G公式相同，但缺失的M3B结果不能用M3G复制填充；统计因子家族时二者也只能算一个家族。",
        "- 当前截图只能支持累计收益、Alpha、Beta、Sharpe和最大回撤。CAGR与Calmar按2015-01-01至2020-12-31约6年推导。",
        "- 截图不含Sortino、换手、实际成本、年度收益、资产归因和未来21日标签精度，因此本报告只能做第一层参数稳定性筛选，不能宣告步骤05正式通过。",
        "",
        "## 模式汇总",
        "",
        "| 模式 | 完成 | 正年化超额 | Calmar≥0.3 | Calmar中位数 | 最佳/中位数 | 窗口条件 | 频率条件 | 数值门槛 | 截图初筛 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summaries:
        preliminary = "通过" if row["preliminary_screenshot_gate"] else "不通过"
        lines.append(
            f"| {row['mode_label']} | {row['complete_count']}/20 | {row['positive_excess_count']} | "
            f"{row['calmar_ge_0_3_count']} | {fmt(row['median_calmar'])} | "
            f"{fmt(row['best_to_median_calmar'])} | "
            f"{row['windows_with_two_nonnegative_excess_frequencies']}/5 | "
            f"{row['frequencies_with_three_nonnegative_excess_windows']}/4 | "
            f"{row['step04_numeric_gate_count']} | {preliminary} |"
        )

    lines.extend(
        [
            "",
            "## 当前结论",
            "",
        ]
    )
    preliminary_passes = [row for row in summaries if row["preliminary_screenshot_gate"]]
    if preliminary_passes:
        labels = "、".join(str(row["mode_label"]) for row in preliminary_passes)
        lines.append(f"截图层面的预筛条件通过者：{labels}。它们仍需日志级指标复核后才可能成为步骤05候选。")
    else:
        lines.append("没有模式通过截图层面的全部预筛条件；不能进入步骤06。")

    lines.extend(
        [
            "",
            "按Calmar中位数观察，当前相对靠前的完整模式是：",
            "",
        ]
    )
    for row in [item for item in ranked if item["complete_count"] == 20][:5]:
        lines.append(
            f"- {row['mode_label']}：Calmar中位数 {fmt(row['median_calmar'])}，"
            f"正年化超额 {row['positive_excess_count']}/20，数值门槛 {row['step04_numeric_gate_count']} 组。"
        )

    best_cells = sorted(
        parameter_cells,
        key=lambda row: float(row["median_calmar"]) if row["median_calmar"] is not None else -999,
        reverse=True,
    )
    lines.extend(
        [
            "",
            "## 跨模式窗口与频率结构",
            "",
            "排除公式重复的M3B/M3G后，按同一参数单元格汇总非重复模式，Calmar中位数靠前的是：",
            "",
        ]
    )
    for cell in best_cells[:6]:
        lines.append(
            f"- {cell['lookback']}日窗口 × {cell['rebalance_interval']}日调仓："
            f"Calmar中位数 {fmt(cell['median_calmar'])}，CAGR中位数 {fmt(cell['median_cagr_pct'])}%，"
            f"正年化超额 {cell['positive_excess_mode_count']}/{cell['complete_mode_count']} 个模式。"
        )
    lines.extend(
        [
            "",
            "结构上，31日窗口在20日、10日和5日调仓下形成了相邻的较优区域，其中10日与20日更稳；这是当前最值得保留的参数带。"
            "63日×1日的Calmar中位数更高，但63日窗口在5日、10日和20日调仓时明显变弱，因此它更像孤立尖峰，不能按稳定区域处理。",
            "252日窗口在四种频率下较一致，但整体Calmar仅约0.21—0.24，属于稳定但优势不足。14日窗口除10日调仓外普遍较弱，126日窗口也没有形成连续优势带。",
            "",
            "## 研究决策",
            "",
            "- 当前11个入口没有任何一个满足步骤05预注册的数值稳定性条件，因此不能进入步骤06。",
            "- M3C现有4个正超额、3个Calmar≥0.3，即使补齐唯一缺口也不可能达到12/20；M3G现有15组中为0个正超额，即使5个缺口全部成功也不可能达到12/20。",
            "- M3B与M3G公式相同。补跑M3B的价值主要是验证入口路由一致性，不会形成新的独立因子证据。",
            "- 若开启下一轮独立研究版本，优先围绕31日窗口×10/20日调仓做时间切分和日志级复核，而不是继续追逐单点最高收益。",
        ]
    )

    lines.extend(
        [
            "",
            "如要把本轮文档正式封账，仍应补齐M3C 126×1，并决定是否按预注册协议补跑M3B与M3G缺口；但这些缺口不改变当前不能进入步骤06的结论。",
            "",
        ]
    )
    (DATA_DIR / "step05_analysis.md").write_text("\n".join(lines), encoding="utf-8")

    missing_lines = [
        "# 步骤05缺失结果",
        "",
        f"当前有效最终指标为 {complete_count}/220，仍缺 {len(missing_rows)} 组。",
        "",
        "| 模式 | 窗口 | 调仓间隔 | 状态 | 说明 |",
        "|---|---:|---:|---|---|",
    ]
    for row in missing_rows:
        missing_lines.append(
            f"| `{row['run_mode']}` | {row['lookback']} | {row['rebalance_interval']} | "
            f"`{row['status']}` | {row['source_note']} |"
        )
    (DATA_DIR / "missing_results.md").write_text("\n".join(missing_lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = build_grid()
    summaries = build_mode_summary(rows)
    window_summary = build_axis_summary(rows, "lookback")
    frequency_summary = build_axis_summary(rows, "rebalance_interval")
    parameter_cells = build_parameter_cell_summary(rows)

    all_fields = [
        "run_mode", "lookback", "rebalance_interval", "status",
        "strategy_return_pct", "benchmark_return_pct", "alpha", "beta", "sharpe",
        "max_drawdown_pct", "cagr_pct", "benchmark_cagr_pct", "annualized_excess_pct",
        "calmar", "positive_annualized_excess", "calmar_ge_0_3", "step04_numeric_gate",
        "image_file", "source_note",
    ]
    write_csv(DATA_DIR / "step05_all_results.csv", rows, all_fields)
    write_csv(DATA_DIR / "step05_mode_summary.csv", summaries, list(summaries[0].keys()))
    write_csv(DATA_DIR / "step05_window_summary.csv", window_summary, list(window_summary[0].keys()))
    write_csv(DATA_DIR / "step05_frequency_summary.csv", frequency_summary, list(frequency_summary[0].keys()))
    write_csv(DATA_DIR / "step05_parameter_cell_summary.csv", parameter_cells, list(parameter_cells[0].keys()))
    write_analysis(rows, summaries, parameter_cells)

    print(f"rows={len(rows)}")
    print(f"complete={sum(row['status'] == 'complete' for row in rows)}")
    print(f"missing={sum(row['status'] != 'complete' for row in rows)}")
    for summary in summaries:
        print(
            summary["run_mode"],
            summary["complete_count"],
            summary["positive_excess_count"],
            summary["calmar_ge_0_3_count"],
            summary["median_calmar"],
            summary["step04_numeric_gate_count"],
            summary["preliminary_screenshot_gate"],
        )


if __name__ == "__main__":
    main()
