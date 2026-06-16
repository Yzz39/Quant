# vectorbt 快速入门问答笔记

对应 Notebook：[bt_01_quick_start.ipynb](/d:/Quant/notebooks/bt_01_quick_start.ipynb)

这份笔记整理了本次围绕 `vectorbt` 的安装、数据获取、常见报错和基础回测代码的问答。

## 1. 为什么 `import vectorbt as vbt` 报 `ModuleNotFoundError`

报错：

```text
ModuleNotFoundError: No module named 'vectorbt'
```

含义是：当前 Notebook 使用的 Python 环境里没有安装 `vectorbt`。

本项目里当时的问题更具体：

- Notebook kernel 使用的是 `D:\Quant\.venv`
- 但 `vectorbt` 被装到了 `D:\Quant\vectorbt\.venv`
- `D:\Quant\vectorbt` 这个目录本身不是正常的 Python 包源码，只是误建了一个单独虚拟环境

所以核心问题不是代码写错，而是环境装错了。

正确做法是在项目根目录 `D:\Quant` 下，把依赖安装到主环境：

```cmd
cd /d D:\Quant
uv add vectorbt
```

验证：

```cmd
.\.venv\Scripts\python.exe -c "import vectorbt as vbt; print(vbt.__version__)"
```

如果能打印版本号，说明主环境已经能导入 `vectorbt`。

## 2. 为什么 `vbt.YFData.download("BTC-USD")` 报 `No module named 'yfinance'`

代码：

```python
data = vbt.YFData.download("BTC-USD")
```

报错：

```text
ModuleNotFoundError: No module named 'yfinance'
```

原因是：`vectorbt` 的 `YFData` 底层会调用 `yfinance` 去 Yahoo Finance 下载数据，但 `yfinance` 不是自动可用的，需要额外安装。

安装：

```cmd
cd /d D:\Quant
uv add yfinance
```

验证：

```cmd
.\.venv\Scripts\python.exe -c "import vectorbt as vbt; import yfinance; print(vbt.__version__)"
```

## 3. 为什么 Yahoo Finance 报 `YFRateLimitError`

报错：

```text
YFRateLimitError: Too Many Requests. Rate limited. Try after a while.
```

含义是：Yahoo Finance 对当前 IP 或当前访问频率做了临时限流。

这说明：

- `vectorbt` 已经能正常导入
- `yfinance` 也已经被调用
- 问题发生在联网下载数据阶段

解决思路：

1. 等一会儿再试
2. 减少重复运行下载单元
3. 下载成功后把数据保存到本地 CSV，后续回测读本地数据
4. 对 BTC 这类加密货币，优先考虑交易所数据源，例如 Binance 或 CCXT

## 4. BTC 数据还有哪些获取方式

### 方式一：直接调用 Binance K 线接口

这个方式不依赖 `yfinance`，适合学习阶段。

```python
import requests
import pandas as pd
import vectorbt as vbt

url = "https://api.binance.com/api/v3/klines"
params = {
    "symbol": "BTCUSDT",
    "interval": "1d",
    "limit": 1000,
}

raw = requests.get(url, params=params, timeout=30).json()

cols = [
    "open_time", "Open", "High", "Low", "Close", "Volume",
    "close_time", "quote_volume", "trades",
    "taker_buy_base", "taker_buy_quote", "ignore",
]

df = pd.DataFrame(raw, columns=cols)
df["Date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
df = df.set_index("Date")

price = df["Close"].astype(float)

pf = vbt.Portfolio.from_holding(price, init_cash=100)
print(pf.total_profit())
```

优点：

- 数据结构清楚
- 报错更容易定位
- 适合初学者理解从原始行情到回测输入的过程

### 方式二：使用 `vbt.CCXTData`

`CCXTData` 通过 `ccxt` 统一访问交易所数据。

先安装：

```cmd
cd /d D:\Quant
uv add ccxt
```

示例：

```python
import vectorbt as vbt

data = vbt.CCXTData.download(
    "BTC/USDT",
    exchange="binance",
    timeframe="1d",
    start="2021-01-01 UTC",
)

price = data.get("Close")
pf = vbt.Portfolio.from_holding(price, init_cash=100)
print(pf.total_profit())
```

如果连接 Binance 超时，可以把 timeout 调大：

```python
data = vbt.CCXTData.download(
    "BTC/USDT",
    exchange="binance",
    timeframe="1d",
    start="2021-01-01 UTC",
    config={
        "timeout": 60000,
        "enableRateLimit": True,
    },
    retries=5,
)
```

## 5. 为什么浏览器能打开 Binance，但 Python 仍然超时

报错：

```text
RequestTimeout: binance GET https://api.binance.com/api/v3/exchangeInfo
```

含义是：`ccxt` 在初始化 Binance 交易所信息时访问 `exchangeInfo` 超时。

浏览器能打开，不代表 `ccxt` 一定不会超时，因为：

- 浏览器和 Python 使用的网络栈不完全一样
- 浏览器可能有代理设置，而 Python 环境不一定有
- `ccxt` 默认超时时间可能偏短
- `ccxt` 第一次请求会拉交易所元信息，响应体较大

如果只是学习 `vectorbt`，更推荐先用 `requests` 直接获取 K 线，或者用本地 CSV，避免把学习卡在网络问题上。

## 6. `pf = vbt.Portfolio.from_holding(price, init_cash=100)` 是什么意思

代码：

```python
pf = vbt.Portfolio.from_holding(price, init_cash=100)
```

含义是：创建一个买入并持有的投资组合。

拆开看：

- `vbt.Portfolio`：vectorbt 里的投资组合和回测对象
- `from_holding(...)`：从第一天买入，然后一直持有到最后
- `price`：资产价格序列，通常是收盘价
- `init_cash=100`：初始资金是 100

这句代码相当于问：

```text
如果我一开始拿 100 元买入这个资产，然后一直持有到最后，会赚或亏多少？
```

后面的：

```python
print(pf.total_profit())
```

表示打印总利润。

例如初始资金 100，最后账户价值 150，那么 `total_profit()` 大约是 50。

## 7. `from_holding` 和 `from_signals` 的区别

### `from_holding`

适合做买入持有基准：

```python
pf = vbt.Portfolio.from_holding(price, init_cash=100)
```

特点：

- 一开始买入
- 中间不择时
- 一直持有到最后
- 常用作基准策略

### `from_signals`

适合做有买卖信号的策略：

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

含义：

- `close`：成交和估值使用的价格序列
- `entries`：什么时候买入
- `exits`：什么时候卖出
- `init_cash=1.0`：初始资金为 1，方便把结果看成净值
- `fees=0.0`：不考虑手续费
- `slippage=0.0`：不考虑滑点
- `freq="1D"`：数据频率是日线

它适合回测类似均线、突破、动量等有明确进出场信号的策略。

## 8. 当前 Notebook 中 vectorbt 均线策略代码解释

原始信号：

```python
ma20 = close.rolling(20).mean()
signal = close > ma20
```

含义：

- `ma20` 是 20 日均线
- `signal` 表示当前收盘价是否站上 20 日均线

前一天信号：

```python
prev_signal = signal.shift(1).fillna(False).astype(bool)
```

含义：

- `shift(1)` 把信号向后移动一天，得到昨天的信号
- 第一行没有昨天，所以用 `False` 填充
- `astype(bool)` 确保结果是布尔类型

买入信号：

```python
entries = signal & ~prev_signal
```

含义：

```text
今天满足条件，并且昨天不满足条件
```

也就是刚刚从空仓状态切换到持仓状态。

卖出信号：

```python
exits = ~signal & prev_signal
```

含义：

```text
今天不满足条件，并且昨天满足条件
```

也就是刚刚从持仓状态切换到空仓状态。

创建回测：

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

这一步让 vectorbt 根据价格、买入信号和卖出信号模拟账户变化。

取出净值：

```python
df["equity_vbt"] = pf.value()
```

`pf.value()` 返回每一天账户总价值。因为初始资金是 `1.0`，所以可以直接把它理解为策略净值曲线。

和手写版对比：

```python
print((df["equity_manual"] - df["equity_vbt"]).abs().max())
```

含义是比较手写净值和 vectorbt 净值的最大差异。

如果结果非常接近 0，说明两种实现逻辑基本一致。

## 9. 学习阶段建议

刚开始学习 `vectorbt` 时，建议按这个顺序推进：

1. 先用本地 CSV 或手工构造的价格序列跑通 `from_holding`
2. 再用本地 CSV 跑通 `from_signals`
3. 然后才接入外部数据源
4. 外部数据下载成功后尽量保存到本地，避免每次回测都联网
5. 每次加入手续费、滑点、交易规则之前，先确认基础净值曲线是否符合预期

最小可运行例子：

```python
import pandas as pd
import vectorbt as vbt

price = pd.Series(
    [100, 105, 102, 110, 120],
    index=pd.date_range("2024-01-01", periods=5),
)

pf = vbt.Portfolio.from_holding(price, init_cash=100)
print(pf.total_profit())
```

这个例子没有联网依赖，最适合验证 `vectorbt` 是否安装成功，以及理解买入持有回测的基本含义。
