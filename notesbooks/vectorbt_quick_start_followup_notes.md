# vectorbt 快速入门补充问答笔记

对应 Notebook：[bt_01_quick_start.ipynb](/d:/Quant/notebooks/bt_01_quick_start.ipynb)

这份笔记只整理追加问答，不改动原来的 `vectorbt_quick_start_qa_notes.md`。

## 1. Notebook 上面 cell 的变量，下面 cell 能用吗

可以。只要是在同一个 `.ipynb`、同一个 kernel 会话里，上面 cell 运行后定义的变量，下面 cell 可以直接使用。

例如：

```python
x = 10
price = df["close"]
```

下面的 cell 可以继续用：

```python
print(x)
print(price.head())
```

需要注意：

- 变量所在的 cell 必须已经运行过
- 重启 kernel 后，之前内存里的变量都会消失
- Notebook 按实际执行顺序生效，不按显示顺序生效
- 如果后面的 cell 修改了变量，后续再用就是修改后的值

学习和回测时，建议经常使用 `Restart & Run All` 检查 notebook 是否能从头到尾顺序运行。

## 2. `signal.shift(1)` 是什么意思

`signal.shift(1)` 表示把 `signal` 整体向下移动一行。

原始信号：

```text
date        signal
01-01      False
01-02      True
01-03      True
01-04      False
```

执行：

```python
prev_signal = signal.shift(1)
```

结果：

```text
date        prev_signal
01-01      NaN
01-02      False
01-03      True
01-04      True
```

也就是说，虽然动作是整体下移一格，但含义是：

```text
在今天这一行，放入昨天的 signal
```

常见记法：

```text
shift(1):  往下移 -> 今天看到昨天
shift(-1): 往上移 -> 今天看到明天
```

在回测里，`shift(1)` 常用于避免用今天收盘后才知道的信息去交易今天。

## 3. `entries = signal & ~prev_signal` 的含义

```python
entries = signal & ~prev_signal
```

含义是：

```text
今天 signal=True，并且昨天 prev_signal=False
```

也就是信号从 `False` 变成 `True` 的当天买入。

示例：

```text
昨天 signal    今天 signal    entries
False         False         False
False         True          True
True          True          False
True          False         False
```

所以 `entries` 不是每天持仓信号，而是买入动作信号。

## 4. `exits = ~signal & prev_signal` 的含义

```python
exits = ~signal & prev_signal
```

含义是：

```text
今天 signal=False，并且昨天 prev_signal=True
```

也就是信号从 `True` 变成 `False` 的当天卖出。

示例：

```text
昨天 signal    今天 signal    exits
False         False         False
False         True          False
True          True          False
True          False         True
```

合起来看：

```text
signal 从 False 变 True -> entries=True -> 买入
signal 从 True 变 False -> exits=True   -> 卖出
signal 没有变化         -> 不交易
```

## 5. 卖出是不是出现信号当天卖出

按下面这版代码：

```python
exits = ~signal & prev_signal
```

卖出信号确实是在 `signal` 从 `True` 变成 `False` 的当天出现。

如果传给：

```python
pf = vbt.Portfolio.from_signals(
    close,
    entries=entries,
    exits=exits,
)
```

默认可以理解为：

```text
跌破均线的当天，用当天 close 卖出
```

但这里有一个回测细节：如果 `signal = close > ma20` 用的是当天收盘价，那么当天收盘之前并不知道这个信号。因此，更保守的写法是把交易信号再延后一日：

```python
entries = (signal & ~prev_signal).shift(1).fillna(False).astype(bool)
exits = (~signal & prev_signal).shift(1).fillna(False).astype(bool)
```

这样含义变成：

```text
今天收盘确认信号，明天再交易
```

## 6. `from_signals` 各参数含义

示例：

```python
pf = vbt.Portfolio.from_signals(
    close,
    entries=entries,
    exits=exits,
    init_cash=1.0,
    fees=0.0,
    slippage=0.0,
    freq="1D",
)
```

参数含义：

- `close`：价格序列，通常用收盘价
- `entries=entries`：买入信号，某天为 `True` 时尝试买入
- `exits=exits`：卖出信号，某天为 `True` 时尝试卖出
- `init_cash=1.0`：初始资金为 1，方便把结果看成净值
- `fees=0.0`：手续费比例为 0
- `slippage=0.0`：滑点比例为 0
- `freq="1D"`：数据频率是日线

如果写成：

```python
fees=0.001
```

表示每次交易收 0.1% 手续费。

如果写成：

```python
slippage=0.001
```

表示成交时价格向不利方向偏移 0.1%。

注意参数之间要有逗号：

```python
slippage=0.0,
freq="1D",
```

## 7. `TypingError` 是什么

报错大意：

```text
TypingError
...
During: Pass nopython_type_inference
```

这通常不是策略逻辑本身坏了，而是 `vectorbt` 底层的 `numba` 编译器没法把输入类型推断成它想要的类型。

本 notebook 里常见诱因：

- `entries` / `exits` 不是纯布尔类型
- 经过 `shift()` 和 `fillna()` 后，序列变成了 `object`
- 把 Python 的 `False` 误写成了小写 `false`

更稳妥的写法：

```python
position = signal.shift(1).fillna(False).astype(bool)
entries = (signal & ~position).shift(1).fillna(False).astype(bool)
exits = (~signal & position).shift(1).fillna(False).astype(bool)
```

重点是：

```python
.astype(bool)
```

它明确告诉 pandas 和 vectorbt：这个序列就是纯布尔信号。

## 8. 为什么结果里出现 `<bound method Portfolio.value ...>`

如果结果像这样：

```text
<bound method Portfolio.value of <vectorbt.portfolio.base.Portfolio ...>>
```

说明你把方法本身保存进去了，而不是保存方法执行后的结果。

错误写法：

```python
df["equity_vbt"] = pf.value
```

正确写法：

```python
df["equity_vbt"] = pf.value()
```

区别：

```python
pf.value
```

表示函数对象。

```python
pf.value()
```

表示调用函数，返回每日账户净值序列。
