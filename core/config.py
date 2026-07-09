"""
选股工具配置文件
用户可以在此调整选股参数、筛选阈值等
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict


@dataclass
class ScreenConfig:
    """选股筛选配置"""
    
    # ========== 市场范围 ==========
    market: str = "A股"
    exclude_st: bool = True
    exclude_bj: bool = True
    exclude_kc: bool = False
    exclude_cy: bool = False
    min_listing_days: int = 365
    
    # ========== 估值指标 ==========
    pe_min: Optional[float] = 0
    pe_max: Optional[float] = 50
    pb_min: Optional[float] = None
    pb_max: Optional[float] = 10
    ps_min: Optional[float] = None
    ps_max: Optional[float] = None
    
    # ========== 盈利能力 ==========
    roe_min: Optional[float] = 10.0
    roa_min: Optional[float] = None
    gross_margin_min: Optional[float] = None
    net_margin_min: Optional[float] = None
    
    # ========== 成长能力 ==========
    revenue_growth_min: Optional[float] = 10.0
    profit_growth_min: Optional[float] = 10.0
    
    # ========== 市值与流动性 ==========
    total_mv_min: Optional[float] = 50
    total_mv_max: Optional[float] = 5000
    circ_mv_min: Optional[float] = None
    circ_mv_max: Optional[float] = None
    avg_amount_min: Optional[float] = 5000
    
    # ========== 技术指标 (新增) ==========
    # 是否启用技术指标筛选
    use_technical_filter: bool = False
    
    # 股价 > N日均线
    price_above_ma: Optional[int] = None
    price_below_ma: Optional[int] = None
    
    # 均线多头排列
    ma_bullish_alignment: bool = False
    ma_bearish_alignment: bool = False
    
    # 均线金叉 (short, long) 如 (5, 20)
    ma_golden_cross: Optional[Tuple[int, int]] = None
    ma_golden_cross_days: int = 5
    
    # MACD
    macd_golden_cross: bool = False
    macd_golden_cross_days: int = 5
    macd_above_zero: bool = False
    macd_below_zero: bool = False
    
    # KDJ
    kdj_golden_cross: bool = False
    kdj_golden_cross_days: int = 5
    kdj_k_below: Optional[float] = None
    kdj_k_above: Optional[float] = None
    
    # RSI
    rsi_below: Optional[float] = None
    rsi_above: Optional[float] = None
    rsi_period: int = 14
    
    # 布林带
    boll_break_upper: bool = False
    boll_break_lower: bool = False
    boll_band_width_min: Optional[float] = None
    boll_band_width_max: Optional[float] = None
    
    # 成交量
    volume_surge_ratio: Optional[float] = None
    volume_ma_period: int = 20
    
    # 最少需要满足的技术信号数
    min_tech_signals: int = 1
    
    # 技术指标回看天数 (获取历史K线计算指标)
    tech_lookback_days: int = 90
    
    # ========== 输出配置 ==========
    max_results: int = 50
    sort_by: str = "score"
    
    score_weights: dict = field(default_factory=lambda: {
        "pe": 0.20,
        "pb": 0.15,
        "roe": 0.25,
        "revenue_growth": 0.20,
        "profit_growth": 0.20,
    })
    
    def to_tech_filter_config(self):
        """转换为技术指标筛选配置对象"""
        from .technical_indicators import TechFilterConfig
        return TechFilterConfig(
            price_above_ma=self.price_above_ma,
            price_below_ma=self.price_below_ma,
            ma_bullish_alignment=self.ma_bullish_alignment,
            ma_bearish_alignment=self.ma_bearish_alignment,
            ma_golden_cross=self.ma_golden_cross,
            ma_golden_cross_days=self.ma_golden_cross_days,
            macd_golden_cross=self.macd_golden_cross,
            macd_golden_cross_days=self.macd_golden_cross_days,
            macd_above_zero=self.macd_above_zero,
            macd_below_zero=self.macd_below_zero,
            kdj_golden_cross=self.kdj_golden_cross,
            kdj_golden_cross_days=self.kdj_golden_cross_days,
            kdj_k_below=self.kdj_k_below,
            kdj_k_above=self.kdj_k_above,
            rsi_below=self.rsi_below,
            rsi_above=self.rsi_above,
            rsi_period=self.rsi_period,
            boll_break_upper=self.boll_break_upper,
            boll_break_lower=self.boll_break_lower,
            boll_band_width_min=self.boll_band_width_min,
            boll_band_width_max=self.boll_band_width_max,
            volume_surge_ratio=self.volume_surge_ratio,
            volume_ma_period=self.volume_ma_period,
            min_signals_count=self.min_tech_signals,
        )


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_cash: float = 100.0
    max_position_pct: float = 20.0
    max_holding_count: int = 10
    stop_loss_pct: float = -10.0
    take_profit_pct: float = 20.0
    rebalance_period: str = "monthly"
    commission_rate: float = 0.025
    min_commission: float = 5.0
    slippage_pct: float = 0.1


@dataclass
class DatabaseConfig:
    """数据库配置"""
    db_path: str = "data/stock_screener.db"
    cache_dir: str = "data/cache"


# ========== 基本面预设策略 ==========
PRESET_STRATEGIES = {
    "价值精选": ScreenConfig(
        pe_max=30, pb_max=3, roe_min=15,
        revenue_growth_min=5, profit_growth_min=5,
        total_mv_min=100, sort_by="score",
    ),
    "成长猎手": ScreenConfig(
        pe_max=80, roe_min=8,
        revenue_growth_min=30, profit_growth_min=30,
        total_mv_min=50, sort_by="score",
    ),
    "低估蓝筹": ScreenConfig(
        pe_max=15, pb_max=1.5, roe_min=10,
        total_mv_min=500, avg_amount_min=10000,
        sort_by="pe_asc",
    ),
    "小盘成长": ScreenConfig(
        pe_max=50, roe_min=10,
        revenue_growth_min=20,
        total_mv_max=300, total_mv_min=30,
        sort_by="score",
    ),
}

# ========== 技术面预设策略 (新增) ==========
TECH_PRESET_STRATEGIES = {
    "趋势突破": ScreenConfig(
        use_technical_filter=True,
        pe_max=100, total_mv_min=20,
        price_above_ma=20,
        ma_golden_cross=(5, 20),
        macd_golden_cross=True,
        volume_surge_ratio=1.5,
        min_tech_signals=2,
        tech_lookback_days=90,
        max_results=30,
        sort_by="score",
    ),
    "超跌反弹": ScreenConfig(
        use_technical_filter=True,
        pe_max=100, total_mv_min=10,
        rsi_below=30,
        kdj_k_below=20,
        boll_break_lower=True,
        min_tech_signals=1,
        tech_lookback_days=60,
        max_results=30,
        sort_by="score",
    ),
    "均线多头": ScreenConfig(
        use_technical_filter=True,
        pe_max=80, total_mv_min=30,
        ma_bullish_alignment=True,
        price_above_ma=60,
        macd_above_zero=True,
        min_tech_signals=2,
        tech_lookback_days=120,
        max_results=30,
        sort_by="score",
    ),
    "MACD零轴金叉": ScreenConfig(
        use_technical_filter=True,
        pe_max=100, total_mv_min=20,
        macd_golden_cross=True,
        macd_above_zero=True,
        ma_golden_cross=(5, 10),
        min_tech_signals=2,
        tech_lookback_days=60,
        max_results=30,
        sort_by="score",
    ),
    "布林带收口": ScreenConfig(
        use_technical_filter=True,
        pe_max=100, total_mv_min=20,
        boll_band_width_max=0.05,
        macd_golden_cross=True,
        min_tech_signals=1,
        tech_lookback_days=60,
        max_results=30,
        sort_by="score",
    ),
}

# 合并所有预设策略
ALL_PRESETS = {**PRESET_STRATEGIES, **TECH_PRESET_STRATEGIES}
