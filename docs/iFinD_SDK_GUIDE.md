# iFinD SDK 安装与使用指南

## 📦 安装 iFinD SDK

### 方式一：直接安装 (推荐)

```bash
# 安装 agent_gw (iFinD Python SDK)
python3 -m pip install "$(curl -s https://cdn.kimi.com/agentgw/pysdk/manifest.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["latest"]["url"])')"
```

### 方式二：Windows PowerShell

```powershell
# 先获取安装 URL
$url = (Invoke-WebRequest -Uri "https://cdn.kimi.com/agentgw/pysdk/manifest.json" | ConvertFrom-Json).latest.url
pip install $url
```

### 方式三：手动安装

1. 访问 https://cdn.kimi.com/agentgw/pysdk/manifest.json 获取最新版本 URL
2. 下载 whl 文件
3. `pip install agent_gw-xxxxx.whl`

---

## 🔑 配置 API Key

### 方式一：环境变量

```bash
export KIMI_API_KEY="your-api-key-here"
```

### 方式二：配置文件

创建文件 `~/.kimi/agent-gw.json`：

```json
{
  "api_key": "your-api-key-here"
}
```

### 方式三：代码中设置

```python
import os
os.environ["KIMI_API_KEY"] = "your-api-key-here"
```

---

## 🚀 快速开始

### 基础用法

```python
from core import iFinDClient

# 自动检测最佳模式
client = iFinDClient()
print(client)  # iFinDClient(mode='native', adapter='iFinD Native (agent_gw)')

# 获取历史价格
df = client.get_price("000001.SZ", "2024-01-01", "2024-06-30")
print(df.head())

# 获取实时技术指标
df = client.get_tech_indicators("600519.SH")
print(df[['ticker', 'MA5', 'MA20', 'MACD_DIF', 'KDJ_K', 'RSI6']])

# 获取财务指标
df = client.get_financial_index("000001.SZ", "profitability")
print(df)

# 获取股票信息
df = client.get_stock_info("000001.SZ,600519.SH")
print(df[['ticker', 'name']])
```

### 批量获取

```python
# 一次获取多只 (自动分批，每批3只)
codes = ["000001.SZ", "600519.SH", "000858.SZ", "002594.SZ", "300750.SZ"]
df = client.get_price(codes, "2024-01-01", "2024-06-30")
print(f"共获取 {len(df)} 条记录")
```

### 获取全部财务维度

```python
results = client.get_all_financial_dimensions("000001.SZ")
for category, df in results.items():
    print(f"\n=== {category} ===")
    print(df)
```

### 获取最近日K线

```python
df = client.get_daily_kline("600519.SH", days=60)
print(df[['date', 'open', 'high', 'low', 'close', 'volume']].tail())
```

---

## 📊 iFinD vs AkShare 数据对比

| 功能 | iFinD Native | AkShare Fallback |
|------|-------------|------------------|
| 历史价格 | ✅ 完整 | ✅ 完整 |
| 实时行情 | ✅ 丰富 | ✅ 基础 |
| 技术指标 | ✅ 15+ 指标实时计算 | ⚠️ 需本地计算 |
| 财务指标 (6维度) | ✅ 完整 | ❌ 不支持 |
| 财务报表 | ✅ 三表齐全 | ❌ 不支持 |
| 股东信息 | ✅ 详细 | ❌ 不支持 |
| 公告信息 | ✅ 支持 | ❌ 不支持 |
| 预测数据 | ✅ 支持 | ❌ 不支持 |
| 需要 API Key | ✅ 需要 | ❌ 不需要 |
| 费用 | 按量计费/订阅 | 完全免费 |

---

## ⚙️ 三模式说明

```
┌─────────────────────────────────────────────────────────┐
│                    iFinDClient                           │
│                   (统一入口)                              │
├─────────────────────────────────────────────────────────┤
│  自动检测顺序:                                           │
│  1. iFinD Native (agent_gw) ← 数据最丰富                 │
│  2. Daimon Agent (kimi_datasource) ← Daimon环境          │
│  3. AkShare Fallback ← 纯本地免费                        │
└─────────────────────────────────────────────────────────┘
```

### 强制指定模式

```python
# 强制使用 iFinD Native
client = iFinDClient(mode="native")

# 强制使用 AkShare
client = iFinDClient(mode="fallback")

# 自动检测 (默认)
client = iFinDClient(auto_detect=True)
```

---

## 🔧 常见问题

### Q: 安装 agent_gw 失败？

A: 请检查 Python 版本 (>=3.8)，并确保网络可以访问 cdn.kimi.com：
```bash
python --version  # 需 >= 3.8
pip --version     # 确保 pip 最新
pip install --upgrade pip
```

### Q: 提示 "API Key 无效"？

A: 检查以下之一是否配置正确：
- 环境变量 `KIMI_API_KEY`
- 文件 `~/.kimi/agent-gw.json`
- 代码中 `os.environ["KIMI_API_KEY"] = "..."`

### Q: 每次只能查3只股票？

A: 这是 iFinD API 的限制，iFinDClient 已自动处理批量拆分，你只需传入列表即可：
```python
codes = ["000001.SZ", "600519.SH", "000858.SZ", "002594.SZ"]  # 4只
df = client.get_price(codes, "2024-01-01", "2024-06-30")  # 自动分2批
```

### Q: 为什么技术指标返回空？

A: 技术指标接口 (realtime_tech) 不支持：
- 港股 (.HK)
- 美股 (.US)
- ETF (如 510300.SH)
- 科创板 (688xxx.SH)

请确保传入的是主板/创业板 A 股代码。

---

## 📚 更多示例

见 `examples/ifind_examples.py`
