# 📈 选股小工具 v2.1

> 多因子选股 · 技术指标筛选 · iFinD SDK · 策略追踪 · 回测分析 · Web可视化 · 定时自动

> 多因子选股 · 技术指标筛选 · 策略追踪 · 回测分析 · Web可视化 · 定时自动

一站式A股量化选股工具，支持**基本面+技术面**双维度筛选，提供**Web可视化界面**和**定时自动选股**功能。

---

## ✨ 功能特性

| 模块 | 功能 | 状态 |
|------|------|------|
| **选股引擎** | 多因子组合筛选（PE/PB/市值/ROE/增长率等） | ✅ |
| **技术指标** | MA/MACD/KDJ/RSI/BOLL/WR/CCI 信号检测 | ✅ |
| **iFinD SDK** | iFinD Native / Daimon / AkShare 三模式 | ✅ |
| **双数据源** | AkShare (免费) + stock_finance_data (richer) | ✅ |
| **结果导出** | Excel/CSV 格式选股报告 | ✅ |
| **策略记录** | SQLite 数据库存储选股历史 | ✅ |
| **持仓追踪** | 记录买入/卖出，追踪盈亏 | ✅ |
| **快速回测** | 模拟持有N天收益验证 | ✅ |
| **Web界面** | Streamlit 可视化操作 | ✅ |
| **定时选股** | Cron 每日收盘后自动运行 | ✅ |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd D:\选股平台\stock_screener
pip install -r requirements.txt
```

### 2. 启动 Web 界面（推荐）

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`，在可视化界面中配置策略并执行选股。

### 3. 命令行选股

```bash
# 基本面选股
python main.py --screen
python main.py --screen --strategy 价值精选

# 技术指标选股
python main.py --tech-screen --strategy 趋势突破
python main.py --screen --tech-price-above-ma 20 --tech-macd-golden

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
├── main.py                    ← CLI 命令行入口
├── app.py                     ← Streamlit Web 界面
├── requirements.txt           ← 依赖清单
├── README.md                  ← 本文档
│
├── core/                      ← 核心模块
│   ├── __init__.py
│   ├── config.py              ← 选股/回测配置 + 9套预设策略
│   ├── data_source.py         ← 统一数据源接口 (AkShare + stock_finance_data)
│   ├── data_fetcher.py        ← 旧版数据获取 (兼容保留)
│   ├── stock_screener.py      ← 多因子选股引擎 v2.0
│   ├── technical_indicators.py ← 技术指标计算与筛选
│   ├── database.py            ← SQLite 数据库 (记录 & 追踪)
│   ├── backtest_engine.py     ← 回测引擎
│   └── reporter.py            ← 报告生成 & 可视化
│
├── data/                      (运行时自动创建)
│   ├── stock_screener.db      ← SQLite数据库
│   └── cache/                 ← 数据缓存
│
└── reports/                   (运行时自动创建)
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

### 自定义策略

```python
from core import ScreenConfig

config = ScreenConfig(
    # 基本面
    pe_max=30,
    pb_max=3,
    roe_min=15,
    total_mv_min=50,
    
    # 技术指标
    use_technical_filter=True,
    macd_golden_cross=True,
    price_above_ma=20,
    min_tech_signals=2,
    tech_lookback_days=90,
    
    # 输出
    max_results=30,
    sort_by="score",
)
```

---

## 📊 技术指标说明

### 支持的指标

| 指标 | 说明 | 筛选条件 |
|------|------|---------|
| **MA** | 移动平均线 | 价格>MA、均线金叉、多头排列 |
| **MACD** | 指数平滑异同平均线 | 金叉/死叉、零轴上方/下方 |
| **KDJ** | 随机指标 | 金叉、K值超买/超卖 |
| **RSI** | 相对强弱指标 | 超买(>70)/超卖(<30) |
| **BOLL** | 布林带 | 突破上轨/下轨、带宽扩张/收缩 |
| **WR** | 威廉指标 | 超买/超卖 |
| **CCI** | 顺势指标 | 极端行情判断 |

### 信号检测

```python
from core import calculate_all_indicators, count_signals, TechFilterConfig

# 计算所有指标
df = calculate_all_indicators(kline_df)

# 检测信号
tech_config = TechFilterConfig(
    macd_golden_cross=True,
    rsi_below=30,
    min_signals_count=1
)
signal_count, signals = count_signals(df, tech_config)
# 返回: (信号数量, ['MACD金叉', 'RSI超卖(28.5<30)'])
```

---

## 🗄️ 数据源

### 双源架构

```
┌─────────────────────────────────────────┐
│           数据源管理器                    │
│         DataSourceManager                │
├─────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────────┐ │
│  │   AkShare    │  │ stock_finance_   │ │
│  │   (免费)     │  │    data          │ │
│  │              │  │  (更丰富数据)     │ │
│  │ • 实时行情   │  │ • 实时行情       │ │
│  │ • 历史K线   │  │ • 历史K线        │ │
│  │ • 财务基础  │  │ • 6大财务维度    │ │
│  │ • 无API Key│  │ • 实时技术指标   │ │
│  └──────────────┘  └──────────────────┘ │
└─────────────────────────────────────────┘
```

### 切换数据源

```python
from core import get_data_source

ds = get_data_source()
print(ds.get_source_names())  # ['akshare', 'stock_finance_data']

ds.set_source("akshare")           # 使用 AkShare
ds.set_source("stock_finance_data") # 使用 stock_finance_data
```

---

## 🕐 定时自动选股

已配置 **每日收盘后自动选股** Cron 任务：

| 属性 | 值 |
|------|-----|
| 任务名称 | 每日收盘自动选股 |
| 执行时间 | 每周一至周五 15:17 |
| 执行内容 | 价值精选 + 趋势突破 双策略选股 |
| 输出 | Excel报告 + 数据库记录 + 摘要 |

### 管理定时任务

```bash
# 查看所有定时任务
# 在 Daimon 中使用 Cron 工具查看

# 手动触发一次
# 在 Daimon 中使用 Cron 工具的 trigger 功能
```

---

## 📈 回测功能

### 快速回测

```bash
# 对最近选股结果模拟持有20天
python main.py --backtest

# 指定持有天数
python main.py --backtest --hold-days 30
```

### Python API

```python
from core import SimpleBacktest

bt = SimpleBacktest()
results = bt.simulate_hold_return(
    stock_codes=['000001', '600519'],
    hold_days=20
)
print(results[['stock_code', 'return_pct']])
```

---

## 🗄️ 数据库Schema

### screen_history — 选股历史
| 字段 | 说明 |
|------|------|
| id | 选股记录ID |
| screen_time | 选股时间 |
| stock_count | 选出股票数量 |

### screen_results — 选股明细
| 字段 | 说明 |
|------|------|
| screen_id | 关联选股记录 |
| rank | 排名 |
| stock_code | 股票代码 |
| score | 综合评分 |

### strategy_tracking — 持仓追踪
| 字段 | 说明 |
|------|------|
| stock_code | 股票代码 |
| entry_date | 买入日期 |
| entry_price | 买入价格 |
| unrealized_pnl_pct | 浮动盈亏% |
| status | 持有/已平仓 |

---

## 🔮 后续扩展

- [ ] 接入 Tushare Pro / iFinD 获取更完整的历史财务数据
- [ ] 多策略组合回测与对比
- [ ] 飞书/钉钉推送选股结果
- [ ] 邮件通知功能
- [ ] 更多技术指标（OBV、DMI、PSY等）

---

## ⚠️ 免责声明

本工具仅供学习研究使用，不构成投资建议。股市有风险，投资需谨慎。

数据来源于 AkShare / stock_finance_data 开源接口，仅供参考，不保证实时性和准确性。

---

*版本: v2.1 | 更新日期: 2026-07-09 | iFinD SDK 已集成*
