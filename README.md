# 📈 选股小工具 v3.0

> 多因子选股 · 技术指标筛选 · iFinD SDK · 策略追踪 · 回测分析 · Web可视化 · 外网部署

一站式 A 股量化选股工具，支持**基本面 + 技术面**双维度筛选，提供**Web 可视化界面**、**REST API**、**定时自动选股**功能。

---

## ✨ 功能特性

| 模块 | 功能 | 状态 |
|------|------|------|
| **选股引擎** | 多因子组合筛选（PE/PB/市值/ROE/增长率等） | ✅ |
| **技术指标** | MA/MACD/KDJ/RSI/BOLL/WR/CCI 信号检测 | ✅ |
| **iFinD SDK** | iFinD Native / Daimon / AkShare 三模式自动切换 | ✅ |
| **数据源** | AkShare (免费) / iFinD (rich) / stock_finance_data | ✅ |
| **结果导出** | Excel/CSV 格式选股报告 | ✅ |
| **策略记录** | SQLite 数据库存储选股历史 | ✅ |
| **持仓追踪** | 记录买入/卖出，追踪盈亏 | ✅ |
| **快速回测** | 模拟策略收益验证 | ✅ |
| **Web界面** | Streamlit 可视化 + 纯前端 HTML | ✅ |
| **REST API** | Flask API 服务器（供前端调用） | ✅ |
| **定时选股** | Cron 每日收盘后自动运行 | ✅ |

---

## 🌐 外网部署方案

本项目提供**三种部署方式**，按需选择：

### 方案 1：Streamlit Cloud（推荐，完整功能）

**访问地址：** `https://stock-screener-xxx.streamlit.app`（部署后自动生成）

**支持功能：**
- 完整 Python 后端（选股 / 历史 / 回测）
- iFinD 数据源（需配置 API Key）
- 策略追踪 & 回测分析

**部署步骤：**

1. 访问 [streamlit.io/cloud](https://streamlit.io/cloud) 用 GitHub 账号登录
2. 点击 **New app** → 选择 `rickysun22/stock-screener`
3. **Main file path** 填 `app.py`
4. 点击 **Deploy**

**配置 iFinD API Key（可选）：**

在 Streamlit Cloud 管理页面 → **Settings → Secrets** 中添加：

```toml
KIMI_API_KEY = "your-api-key-here"
```

> 未配置时自动回退到 AkShare 免费数据源，选股功能正常可用。

---

### 方案 2：GitHub Pages（纯前端，零成本）

**访问地址：** `https://rickysun22.github.io/stock-screener`

**支持功能：**
- 纯前端选股（调用东方财富免费 API）
- 基础基本面筛选（PE/PB/市值/换手率）
- CSV 导出

**特点：** 无需服务器，打开即用，但**不支持**技术指标筛选和回测。

---

### 方案 3：本地部署（数据最全）

**本地运行方式：**

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 方式 A：Streamlit Web 界面
streamlit run app.py
# 浏览器打开 http://localhost:8501

# 3. 方式 B：Flask API 服务器 + 前端
python api_server.py
# 浏览器打开 http://localhost:8000
# 前端支持「后端 API 模式」，调用 iFinD 完整数据

# 4. 方式 C：命令行
python main.py --screen
```

**iFinD 本地配置（可选）：**

```bash
# 安装 iFinD SDK
pip install "$(curl -s https://cdn.kimi.com/agentgw/pysdk/manifest.json | python -c 'import json,sys; print(json.load(sys.stdin)["latest"]["url"])')"

# 方式 1：环境变量
export KIMI_API_KEY="your-api-key"

# 方式 2：配置文件
# 创建 ~/.kimi/agent-gw.json
{"api_key": "your-api-key"}
```

---

## 🚀 快速开始

### 本地 Web 界面（Streamlit）

```bash
streamlit run app.py
```

浏览器自动打开 `http://localhost:8501`

界面包含三个标签页：
- **🎯 选股结果** — 配置参数并执行选股
- **📜 历史记录** — 查看历史选股和持仓追踪
- **🔬 回测分析** — 运行策略回测

### 本地 API 服务器（Flask + 前端）

```bash
python api_server.py
```

访问 `http://localhost:8000`：
- 前端支持**免费模式**（东方财富 API）和**后端 API 模式**（iFinD 数据）切换
- 后端 API 模式提供完整技术指标筛选、历史记录、回测分析

### 命令行选股

```bash
# 基本面选股
python main.py --screen
python main.py --screen --strategy 价值精选

# 技术指标选股
python main.py --tech-screen --strategy 趋势突破

# 自定义参数
python main.py --screen --pe-max 25 --pb-max 2 --mv-min 100

# 追踪与回测
python main.py --track
python main.py --history --detail
python main.py --backtest --hold-days 30
```

---

## 📁 项目结构

```
stock_screener/
├── main.py                      ← CLI 命令行入口
├── app.py                       ← Streamlit Web 界面
├── api_server.py                ← Flask REST API 服务器
├── index.html                   ← 纯前端页面（支持双模式）
├── requirements.txt             ← 依赖清单
├── README.md                    ← 本文档
│
├── .streamlit/
│   ├── config.toml              ← Streamlit 部署配置
│   └── secrets.toml.example     ← Secrets 配置示例
│
├── .github/workflows/
│   └── pages.yml                ← GitHub Pages 自动部署
│
├── core/                        ← 核心模块
│   ├── __init__.py
│   ├── config.py                ← 选股/回测配置 + 9套预设策略
│   ├── data_source.py           ← 统一数据源 (AkShare + iFinD + stock_finance_data)
│   ├── ifind_sdk.py             ← iFinD SDK 三模式封装 (Native/Daimon/Fallback)
│   ├── stock_screener.py        ← 多因子选股引擎 v2.0
│   ├── technical_indicators.py  ← 技术指标计算与筛选
│   ├── database.py              ← SQLite 数据库 (记录 & 追踪)
│   ├── backtest_engine.py       ← 回测引擎
│   └── reporter.py              ← 报告生成 & 可视化
│
├── data/                        (运行时自动创建)
│   ├── stock_screener.db        ← SQLite 数据库
│   └── cache/                   ← 数据缓存
│
└── reports/                     (运行时自动创建)
    ├── 选股结果_*.xlsx
    ├── 回测报告_*.md
    └── 收益曲线_*.png
```

---

## ⚙️ 预设策略

### 基本面策略

| 策略名称 | 核心逻辑 | 适用场景 |
|---------|---------|---------|
| **价值精选** | PE<30 + PB<3 + ROE>15% | 稳健价值投资 |
| **成长猎手** | 营收增长>30% + 净利增长>30% | 成长股挖掘 |
| **低估蓝筹** | PE<15 + PB<1.5 + 市值>500亿 | 大盘蓝筹股 |
| **小盘成长** | 高成长 + 市值30-300亿 | 小盘成长股 |

### 技术面策略

| 策略名称 | 核心逻辑 | 适用场景 |
|---------|---------|---------|
| **趋势突破** | 价格上穿MA20 + MACD金叉 + 放量 | 趋势跟随 |
| **超跌反弹** | RSI<30 + KDJ超卖 + 跌破布林下轨 | 抄底反弹 |
| **均线多头** | 均线多头排列 + 价格>MA60 + MACD>0 | 趋势确认 |
| **MACD零轴金叉** | MACD零轴上方金叉 + MA5金叉MA10 | 强势启动 |
| **布林带收口** | 布林带收口 + MACD金叉 | 突破前兆 |

---

## 📡 REST API 说明

启动 `api_server.py` 后，提供以下接口：

| 接口 | 方法 | 说明 |
|------|------|------|
| `GET /api/health` | 健康检查 | 返回数据源状态 |
| `POST /api/screen` | 执行选股 | 传入筛选参数，返回选股结果 |
| `GET /api/history` | 历史记录 | 查询选股历史 |
| `POST /api/backtest` | 运行回测 | 传入策略参数，返回回测结果 |
| `GET /api/datasource` | 数据源状态 | 查看当前数据源和 iFinD 模式 |

**选股示例：**

```bash
curl -X POST http://localhost:8000/api/screen \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "价值精选",
    "pe_max": 20,
    "pb_max": 2,
    "mv_min": 100,
    "exclude_st": true
  }'
```

---

## 📊 iFinD SDK 使用

### 三模式自动切换

```python
from core.ifind_sdk import iFinDClient

client = iFinDClient(auto_detect=True)
print(client.mode)          # "native" | "daimon" | "fallback"
print(client.adapter_name)  # 当前适配器名称

# 获取数据
df = client.get_price("000001.SZ", "2024-01-01", "2024-06-30")
df = client.get_tech_indicators("600519.SH")
df = client.get_financial_index("000001.SZ", "profitability")
df = client.get_stock_info("000001.SZ,600519.SH")
```

### 模式说明

| 模式 | 环境要求 | 数据质量 | 适用场景 |
|------|---------|---------|---------|
| **Native** | 本地安装 agent_gw SDK | ⭐⭐⭐ 最丰富 | 本地开发 |
| **Daimon** | Kimi Daimon 环境 | ⭐⭐⭐ 最丰富 | AI Agent 环境 |
| **Fallback** | 纯 AkShare | ⭐⭐ 基础 | 无 SDK 时自动回退 |

---

## ⚠️ 免责声明

本工具仅供学习研究使用，不构成投资建议。股市有风险，投资需谨慎。

数据来源于 AkShare / iFinD / stock_finance_data 接口，仅供参考，不保证实时性和准确性。

---

*版本: v3.0 | 更新日期: 2026-07-09 | iFinD SDK + Streamlit Cloud + GitHub Pages 全部署支持*
