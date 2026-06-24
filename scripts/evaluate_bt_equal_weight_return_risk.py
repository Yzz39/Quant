from pathlib import Path
import pandas as pd
import numpy as np

base = Path(r'D:\Quant')
out = base / 'outputs'
report_path = out / 'bt_equal_weight_return_risk_evaluation.md'
summary_path = out / 'bt_equal_weight_return_risk_evaluation_summary.csv'
yearly_path = out / 'bt_equal_weight_return_risk_yearly_returns.csv'
weekly_path = out / 'bt_equal_weight_return_risk_recent_12w.csv'

metrics = pd.read_csv(out / 'etf_topn_rotation_vectorbt_metrics.csv')

# Load daily strategy NAVs.
top2 = pd.read_csv(out / 'etf_top2_equal_weight_rotation_vectorbt_daily_value.csv', parse_dates=['date']).sort_values('date')
top3 = pd.read_csv(out / 'etf_top3_equal_weight_rotation_vectorbt_daily_value.csv', parse_dates=['date']).sort_values('date')

# Rebuild benchmark NAV from source close, matching script logic.
df = pd.read_csv(base / 'data' / 'etf_momentum_daily_eastmoney_qfq.csv', dtype={'symbol': 'string'}, parse_dates=['date'])
close = df.pivot(index='date', columns='symbol', values='close').sort_index().sort_index(axis=1)
benchmark_symbol = '510300' if '510300' in close.columns else close.columns[0]
benchmark_ret = close[benchmark_symbol].pct_change(fill_method=None).fillna(0.0)
benchmark_nav = (1 + benchmark_ret).cumprod()
benchmark = pd.DataFrame({'date': benchmark_nav.index, 'nav': benchmark_nav.values}).sort_values('date')

series_map = {
    'Top2等权': top2.set_index('date')['nav'],
    'Top3等权': top3.set_index('date')['nav'],
    '买入持有510300': benchmark.set_index('date')['nav'],
}

def max_drawdown(nav: pd.Series) -> float:
    return float((nav / nav.cummax() - 1).min())

def annualized_return(nav: pd.Series) -> float:
    years = len(nav) / 252
    return float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1)

def annualized_vol(ret: pd.Series) -> float:
    return float(ret.std() * np.sqrt(252))

def sharpe_like(ret: pd.Series) -> float:
    vol = annualized_vol(ret)
    return float(ret.mean() * 252 / vol) if vol else np.nan

def calmar(ann_ret: float, mdd: float) -> float:
    return float(ann_ret / abs(mdd)) if mdd else np.nan

rows = []
for name, nav in series_map.items():
    nav = nav.dropna()
    ret = nav.pct_change().fillna(0)
    total = nav.iloc[-1] / nav.iloc[0] - 1
    ann = annualized_return(nav)
    vol = annualized_vol(ret)
    mdd = max_drawdown(nav)
    rows.append({
        'strategy': name,
        'start_date': nav.index.min().date(),
        'end_date': nav.index.max().date(),
        'total_return': total,
        'annualized_return': ann,
        'annualized_volatility': vol,
        'max_drawdown': mdd,
        'sharpe_like_no_rf': sharpe_like(ret),
        'calmar': calmar(ann, mdd),
        'final_nav': nav.iloc[-1],
        'positive_day_rate': float((ret > 0).mean()),
        'best_day': float(ret.max()),
        'worst_day': float(ret.min()),
    })
summary = pd.DataFrame(rows)

bench = summary.loc[summary['strategy'].eq('买入持有510300')].iloc[0]
summary['excess_total_return_vs_510300'] = summary['total_return'] - bench['total_return']
summary['excess_annualized_return_vs_510300'] = summary['annualized_return'] - bench['annualized_return']
summary['drawdown_improvement_vs_510300'] = summary['max_drawdown'] - bench['max_drawdown']
summary.to_csv(summary_path, index=False, encoding='utf-8-sig')

# Yearly returns.
yearly_rows = []
for name, nav in series_map.items():
    year_end = nav.resample('YE').last().dropna()
    year_ret = year_end.pct_change().dropna()
    for date, value in year_ret.items():
        yearly_rows.append({'year': date.year, 'strategy': name, 'year_return': value})
yearly = pd.DataFrame(yearly_rows)
yearly.to_csv(yearly_path, index=False, encoding='utf-8-sig')

# Recent 12-week returns.
weekly_nav = pd.concat(series_map, axis=1).dropna().resample('W-FRI').last()
weekly_returns = weekly_nav.pct_change().dropna().tail(12)
weekly_returns.to_csv(weekly_path, encoding='utf-8-sig')
recent_12w_stats = pd.DataFrame({
    '12w_return': (1 + weekly_returns).prod() - 1,
    'weekly_win_rate': (weekly_returns > 0).mean(),
    'best_week': weekly_returns.max(),
    'worst_week': weekly_returns.min(),
    'weekly_volatility': weekly_returns.std(),
}).T

# Pull cost/order metrics from original metrics.
metric_lookup = metrics.set_index('name')

def fmt_pct(x):
    return '' if pd.isna(x) else f'{x:.2%}'

def fmt_num(x):
    return '' if pd.isna(x) else f'{x:.2f}'

lines = [
    'bt / vectorbt 等权组合回测收益与风险评估',
    '',
    '一、评估对象',
    '',
    '策略：Top2 / Top3 等权 ETF 动量轮动。',
    '基准：买入持有 510300。',
    '数据：D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv。',
    '回测输出：D:/Quant/outputs/etf_topn_rotation_vectorbt_metrics.csv。',
    '',
    '二、核心指标表',
    '',
]
show_cols = [
    'strategy', 'total_return', 'annualized_return', 'annualized_volatility',
    'max_drawdown', 'sharpe_like_no_rf', 'calmar',
    'excess_annualized_return_vs_510300', 'drawdown_improvement_vs_510300'
]
pretty = summary[show_cols].copy()
for col in ['total_return','annualized_return','annualized_volatility','max_drawdown','excess_annualized_return_vs_510300','drawdown_improvement_vs_510300']:
    pretty[col] = pretty[col].map(fmt_pct)
for col in ['sharpe_like_no_rf','calmar']:
    pretty[col] = pretty[col].map(fmt_num)
lines.append(pretty.to_string(index=False))
lines.extend(['', '三、收益评估', ''])

for strategy in ['Top2等权', 'Top3等权', '买入持有510300']:
    row = summary.loc[summary['strategy'].eq(strategy)].iloc[0]
    lines.append(f'{strategy}：总收益 {fmt_pct(row.total_return)}，年化收益 {fmt_pct(row.annualized_return)}，最终净值 {fmt_num(row.final_nav)}。')

lines.extend([
    '',
    '收益结论：Top2等权显著强于Top3和510300；Top3也跑赢510300，但收益被分散稀释。若只看收益，Top2是当前主线候选。',
    '',
    '四、风险评估',
    '',
])
for strategy in ['Top2等权', 'Top3等权', '买入持有510300']:
    row = summary.loc[summary['strategy'].eq(strategy)].iloc[0]
    lines.append(f'{strategy}：年化波动 {fmt_pct(row.annualized_volatility)}，最大回撤 {fmt_pct(row.max_drawdown)}，类夏普 {fmt_num(row.sharpe_like_no_rf)}，Calmar {fmt_num(row.calmar)}。')

lines.extend([
    '',
    '风险结论：Top2收益更强，但最大回撤仍达到约 -46%，属于高波动高回撤策略；Top3没有明显降低回撤，最大回撤反而更深，说明简单增加持仓数量没有改善核心风险。',
    '',
    '五、相对510300的改进',
    '',
])
for strategy in ['Top2等权', 'Top3等权']:
    row = summary.loc[summary['strategy'].eq(strategy)].iloc[0]
    lines.append(f'{strategy}：年化超额 {fmt_pct(row.excess_annualized_return_vs_510300)}，最大回撤改善 {fmt_pct(row.drawdown_improvement_vs_510300)}。')

lines.extend([
    '',
    '六、最近12周表现',
    '',
    recent_12w_stats.map(lambda x: f'{x:.2%}').to_string(),
    '',
    '七、交易与成本提示',
    '',
])
for metric_name, label in [
    ('vectorbt_top2_equal_weight_rotation', 'Top2等权'),
    ('vectorbt_top3_equal_weight_rotation', 'Top3等权'),
]:
    row = metric_lookup.loc[metric_name]
    lines.append(f'{label}：订单数 {int(row.order_count)}，总费用 {fmt_num(row.total_fees)}，年化成交额/初始资金 {fmt_num(row.annual_traded_value_ratio)} 倍。')

lines.extend([
    '',
    '成本结论：当前佣金0.01% + 滑点0.01%属于乐观研究基线。由于Top2和Top3都有较高换手，进入纸面交易前必须做更高成本压力测试。',
    '',
    '八、阶段判断',
    '',
    'Top2等权：收益优势最明显，风险收益比也最好，适合作为下一步研究主线，但最大回撤过深，暂不能视为实盘版本。',
    'Top3等权：分散后收益明显下降，回撤没有改善，不适合作为主线，只适合作为参考变体。',
    '510300：作为基准表现，长期收益和风险收益比都弱于Top2。',
    '',
    '总判断：当前bt组合回测支持继续研究Top2等权轮动，但不支持直接实盘。下一步应重点研究风控过滤、成本压力、样本外稳定性和12周纸面交易。',
])

report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(report_path)
print(summary_path)
print(yearly_path)
print(weekly_path)
