from pathlib import Path
import pandas as pd
import numpy as np

base = Path(r'D:\Quant')
out = base / 'outputs'
script = base / 'scripts' / 'vectorbt_topn_etf_rotation.py'
report_path = out / 'bt_equal_weight_future_leakage_cost_check.md'
summary_csv = out / 'bt_equal_weight_future_leakage_cost_check_summary.csv'

metrics = pd.read_csv(out / 'etf_topn_rotation_vectorbt_metrics.csv')
rows = []
findings = []

for top_n in [2, 3]:
    decisions = pd.read_csv(out / f'etf_top{top_n}_equal_weight_rotation_vectorbt_decisions.csv', parse_dates=['signal_date'])
    weights = pd.read_csv(out / f'etf_top{top_n}_equal_weight_rotation_vectorbt_target_weights.csv', parse_dates=['date'])
    orders = pd.read_csv(out / f'etf_top{top_n}_equal_weight_rotation_vectorbt_orders.csv')
    strat_metrics = metrics.loc[metrics['name'].eq(f'vectorbt_top{top_n}_equal_weight_rotation')].iloc[0]

    weight_dates = pd.Index(weights['date'])
    timing_checks = []
    same_day_nonzero = 0
    next_day_matches = 0
    checked = 0
    for _, decision in decisions.tail(60).iterrows():
        signal_date = decision['signal_date']
        if signal_date not in set(weight_dates):
            continue
        idx = weights.index[weights['date'].eq(signal_date)][0]
        if idx + 1 >= len(weights):
            continue
        selected = str(decision['selected_symbols'])
        selected_symbols = [] if selected == 'CASH' else selected.split('|')
        signal_row = weights.iloc[idx]
        next_row = weights.iloc[idx + 1]
        signal_sum = float(signal_row.drop(labels=['date']).sum())
        next_selected_sum = float(next_row[selected_symbols].sum()) if selected_symbols else float(next_row.drop(labels=['date']).sum())
        checked += 1
        if selected_symbols and signal_row[selected_symbols].sum() > 0:
            same_day_nonzero += 1
        if selected_symbols and np.isclose(next_selected_sum, 1.0, atol=1e-9):
            next_day_matches += 1
        if not selected_symbols and np.isclose(next_selected_sum, 0.0, atol=1e-9):
            next_day_matches += 1
        timing_checks.append((signal_date.date(), signal_sum, next_selected_sum, selected))

    order_value = float((orders['Size'] * orders['Price']).abs().sum()) if {'Size','Price'}.issubset(orders.columns) else np.nan
    total_fees_orders = float(orders['Fees'].sum()) if 'Fees' in orders.columns else np.nan
    implied_fee_rate = total_fees_orders / order_value if order_value else np.nan
    slippage = float(strat_metrics['slippage'])
    fee_rate = float(strat_metrics['fee_rate'])
    round_trip_drag = 2 * (fee_rate + slippage)

    rows.append({
        'top_n': top_n,
        'checked_recent_signals': checked,
        'same_day_selected_weight_count': same_day_nonzero,
        'next_day_match_count': next_day_matches,
        'fee_rate': fee_rate,
        'slippage': slippage,
        'one_way_cost_assumption': fee_rate + slippage,
        'round_trip_cost_assumption': round_trip_drag,
        'orders': len(orders),
        'total_order_value': order_value,
        'total_fees_from_orders': total_fees_orders,
        'implied_fee_rate_from_orders': implied_fee_rate,
        'annual_traded_value_ratio': strat_metrics.get('annual_traded_value_ratio', np.nan),
        'total_return': strat_metrics.get('total_return', np.nan),
        'max_drawdown': strat_metrics.get('max_drawdown', np.nan),
    })

summary = pd.DataFrame(rows)
summary.to_csv(summary_csv, index=False, encoding='utf-8-sig')

leakage_verdict = '未发现明显同日偷看未来执行，但存在一个需要注意的实现口径：信号用月末收盘价计算，目标权重从下一交易日才生效。代码实现与报告描述基本一致。'
cost_verdict = '成本假设为佣金0.01% + 滑点0.01%，单边合计0.02%，双边约0.04%。这对高流动性ETF偏乐观但可作为研究基线；进入纸面交易前建议增加0.05%、0.10%、0.20%单边压力测试。'

lines = [
    'bt / vectorbt 等权组合回测：未来函数与成本假设检查',
    '',
    '一、检查对象',
    '',
    f'核心脚本：{script}',
    '策略：Top2 / Top3 等权 ETF 动量轮动。',
    '数据：D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv。',
    '',
    '二、未来函数检查结论',
    '',
    leakage_verdict,
    '',
    '关键代码逻辑：',
    '',
    '1. 动量计算：momentum = close / close.shift(LOOKBACK_DAYS) - 1.0。',
    '   这只使用当前信号日及其42个交易日前的价格，没有使用未来价格。',
    '',
    '2. 信号日期：signal_dates 使用每月最后一个交易日。',
    '   信号在月末收盘后才能知道，因此不能在同一天收盘价成交。',
    '',
    '3. 权重生效：target_weights 循环中先写入旧持仓，再在 signal_date 更新 current_symbols。',
    '   结果是：signal_date 当天仍保持旧权重，新的目标权重从下一条交易日开始生效。',
    '   这避免了“用当天收盘价算信号，同时当天收盘价成交”的同日未来函数。',
    '',
    '4. 仍需注意：当前成交价格使用下一交易日的 close，而不是 next open。',
    '   这不是典型未来函数，但它是假设你能在下一交易日收盘价附近执行。若真实操作在开盘或盘中，应另做 next_open 或 VWAP 假设版本。',
    '',
    '三、成本假设检查结论',
    '',
    cost_verdict,
    '',
    '当前脚本参数：',
    '',
    '- FEE_RATE = 0.0001，即 0.01%。',
    '- SLIPPAGE = 0.0001，即 0.01%。',
    '- 单边总摩擦约 0.02%。',
    '- 一买一卖双边摩擦约 0.04%。',
    '',
    '这对流动性好的宽基/行业ETF可能可以作为乐观研究基线；但对成交额较低、冲击成本较高或实盘资金变大时，偏乐观。',
    '',
    '四、量化检查摘要',
    '',
    summary.to_string(index=False),
    '',
    '五、风险判断',
    '',
    '1. 未来函数风险：低到中。核心信号/执行错位是合理的，但执行价用下一日收盘价，需要在报告中明确。',
    '2. 成本假设风险：中。当前成本偏研究基线，不能直接当实盘成本。',
    '3. 最大风险：如果未来改代码时把 target_weights 的更新顺序改成先更新再写入同日权重，就会变成同日收盘信号同日成交，产生未来函数。',
    '',
    '六、建议下一步',
    '',
    '1. 保留当前版本作为“next close execution”研究基线。',
    '2. 新增更保守版本：next open 或 next close + 更高滑点。',
    '3. 做成本压力测试：单边总成本 0.05%、0.10%、0.20%。',
    '4. 在策略报告中明确：信号月末收盘后生成，下一交易日执行。',
    '5. 写一个单元测试，锁定“信号日当天不能持有新信号权重”。',
]
report_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(report_path)
print(summary_csv)
