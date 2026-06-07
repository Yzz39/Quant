import sys
import pandas as pd
import numpy as np
import matplotlib

print("Python:", sys.version)
print("pandas:", pd.__version__)
print("numpy:", np.__version__)
print("matplotlib:", matplotlib.__version__)

df = pd.DataFrame({
    "Date": pd.date_range("2024-01-01", periods=5),
    "Close": [3.91, 3.95, 3.88, 4.02, 4.10],
})

df["Return"] = df["Close"].pct_change()

print()
print(df)
print()
print("环境检查通过")