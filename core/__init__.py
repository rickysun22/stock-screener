"""
选股小工具核心模块 - v2.1 (iFinD SDK 集成)
"""
from .config import (
    ScreenConfig, BacktestConfig, DatabaseConfig,
    PRESET_STRATEGIES, TECH_PRESET_STRATEGIES, ALL_PRESETS
)
from .data_source import DataSourceManager, get_data_source
from .technical_indicators import (
    TechFilterConfig, count_signals, filter_by_technical,
    calculate_all_indicators, calculate_ma, calculate_macd,
    calculate_kdj, calculate_rsi, calculate_bollinger,
    calculate_wr, calculate_cci,
    detect_ma_cross, detect_macd_cross, detect_kdj_cross,
    TECH_PRESETS
)
from .stock_screener import StockScreener, quick_screen
from .database import StockDatabase, get_db
from .backtest_engine import BacktestEngine, SimpleBacktest, BacktestResult
from .reporter import ReportGenerator, generate_screen_summary
from .ifind_sdk import iFinDClient, create_client, get_client

__version__ = "2.1.0"
__all__ = [
    # 配置
    "ScreenConfig", "BacktestConfig", "DatabaseConfig",
    "PRESET_STRATEGIES", "TECH_PRESET_STRATEGIES", "ALL_PRESETS",
    # 数据源
    "DataSourceManager", "get_data_source",
    # iFinD SDK
    "iFinDClient", "create_client", "get_client",
    # 技术指标
    "TechFilterConfig", "count_signals", "filter_by_technical",
    "calculate_all_indicators", "calculate_ma", "calculate_macd",
    "calculate_kdj", "calculate_rsi", "calculate_bollinger",
    "calculate_wr", "calculate_cci",
    "detect_ma_cross", "detect_macd_cross", "detect_kdj_cross",
    "TECH_PRESETS",
    # 选股引擎
    "StockScreener", "quick_screen",
    # 数据库
    "StockDatabase", "get_db",
    # 回测
    "BacktestEngine", "SimpleBacktest", "BacktestResult",
    # 报告
    "ReportGenerator", "generate_screen_summary",
]
