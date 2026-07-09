"""
技术指标计算与筛选模块
基于历史K线数据计算 MA/MACD/KDJ/RSI/BOLL/WR/CCI 等技术指标
支持信号检测和条件筛选
"""

from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np


class SignalType(Enum):
    """技术信号类型"""
    MACD_GOLDEN_CROSS = "macd_golden"      # MACD金叉
    MACD_DEAD_CROSS = "macd_dead"          # MACD死叉
    MA_GOLDEN_CROSS = "ma_golden"          # 均线金叉 (短上穿长)
    MA_DEAD_CROSS = "ma_dead"              # 均线死叉
    KDJ_GOLDEN_CROSS = "kdj_golden"        # KDJ金叉
    KDJ_DEAD_CROSS = "kdj_dead"            # KDJ死叉
    RSI_OVERSOLD = "rsi_oversold"          # RSI超卖
    RSI_OVERBOUGHT = "rsi_overbought"      # RSI超买
    BOLL_BREAK_UPPER = "boll_break_upper"  # 突破布林上轨
    BOLL_BREAK_LOWER = "boll_break_lower"  # 跌破布林下轨
    BOLL_MID_SUPPORT = "boll_mid_support"  # 布林中轨支撑
    VOLUME_SURGE = "volume_surge"          # 放量
    PRICE_BREAK_HIGH = "price_break_high"  # 突破近期高点
    PRICE_BREAK_LOW = "price_break_low"    # 跌破近期低点


@dataclass
class TechFilterConfig:
    """技术指标筛选配置"""
    
    # ========== 均线 ==========
    # 股价 > N日均线
    price_above_ma: Optional[int] = None        # e.g. 20, 60
    price_below_ma: Optional[int] = None        # e.g. 20
    
    # 均线多头排列 (短期 > 中期 > 长期)
    ma_bullish_alignment: bool = False          # 5>10>20>60
    ma_bearish_alignment: bool = False          # 5<10<20<60
    
    # 均线金叉 (短期均线上穿长期均线，最近N天内)
    ma_golden_cross: Optional[Tuple[int, int]] = None   # (short, long) e.g. (5, 20)
    ma_golden_cross_days: int = 5                        # 最近N天内发生
    
    # ========== MACD ==========
    macd_golden_cross: bool = False             # MACD金叉
    macd_golden_cross_days: int = 5
    macd_above_zero: bool = False               # MACD在零轴上方
    macd_below_zero: bool = False               # MACD在零轴下方
    
    # ========== KDJ ==========
    kdj_golden_cross: bool = False              # KDJ金叉
    kdj_golden_cross_days: int = 5
    kdj_k_below: Optional[float] = None         # K值低于 (超卖区)
    kdj_k_above: Optional[float] = None         # K值高于 (超买区)
    
    # ========== RSI ==========
    rsi_below: Optional[float] = None           # RSI低于 (超卖)
    rsi_above: Optional[float] = None           # RSI高于 (超买)
    rsi_period: int = 14
    
    # ========== 布林带 ==========
    boll_break_upper: bool = False              # 突破上轨
    boll_break_lower: bool = False              # 跌破下轨
    boll_band_width_min: Optional[float] = None # 带宽 > N (开口)
    boll_band_width_max: Optional[float] = None # 带宽 < N (收口)
    
    # ========== 成交量 ==========
    volume_surge_ratio: Optional[float] = None  # 量比 > N
    volume_ma_period: int = 20
    
    # ========== 价格形态 ==========
    price_near_high_days: Optional[int] = None  # 接近N日高点
    price_near_low_days: Optional[int] = None   # 接近N日低点
    
    # ========== 综合信号数量要求 ==========
    # 要求至少满足 N 个信号才入选
    min_signals_count: int = 0


def calculate_ma(df: pd.DataFrame, periods: List[int] = None) -> pd.DataFrame:
    """计算移动平均线"""
    if periods is None:
        periods = [5, 10, 20, 30, 60, 120, 250]
    
    df = df.copy()
    close = df['close']
    
    for p in periods:
        df[f'MA{p}'] = close.rolling(window=p, min_periods=1).mean()
    
    return df


def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """计算 MACD 指标"""
    df = df.copy()
    close = df['close']
    
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    df['MACD_DIF'] = ema_fast - ema_slow
    df['MACD_DEA'] = df['MACD_DIF'].ewm(span=signal, adjust=False).mean()
    df['MACD_BAR'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
    
    return df


def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
    """计算 KDJ 指标"""
    df = df.copy()
    
    low_list = df['low'].rolling(window=n, min_periods=1).min()
    high_list = df['high'].rolling(window=n, min_periods=1).max()
    rsv = (df['close'] - low_list) / (high_list - low_list) * 100
    
    df['KDJ_K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
    df['KDJ_D'] = df['KDJ_K'].ewm(alpha=1/m2, adjust=False).mean()
    df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    # 处理NaN
    df['KDJ_K'] = df['KDJ_K'].fillna(50)
    df['KDJ_D'] = df['KDJ_D'].fillna(50)
    df['KDJ_J'] = df['KDJ_J'].fillna(50)
    
    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算 RSI 指标"""
    df = df.copy()
    close = df['close']
    
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
    
    rs = gain / loss.replace(0, np.nan)
    df[f'RSI{period}'] = 100 - (100 / (1 + rs))
    df[f'RSI{period}'] = df[f'RSI{period}'].fillna(50)
    
    return df


def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
    """计算布林带指标"""
    df = df.copy()
    close = df['close']
    
    df['BOLL_MID'] = close.rolling(window=period, min_periods=1).mean()
    std = close.rolling(window=period, min_periods=1).std()
    df['BOLL_UPPER'] = df['BOLL_MID'] + std_dev * std
    df['BOLL_LOWER'] = df['BOLL_MID'] - std_dev * std
    df['BOLL_WIDTH'] = (df['BOLL_UPPER'] - df['BOLL_LOWER']) / df['BOLL_MID']
    df['BOLL_WIDTH'] = df['BOLL_WIDTH'].replace([np.inf, -np.inf], np.nan).fillna(0)
    
    return df


def calculate_wr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算威廉指标 WR"""
    df = df.copy()
    
    high_max = df['high'].rolling(window=period, min_periods=1).max()
    low_min = df['low'].rolling(window=period, min_periods=1).min()
    
    df[f'WR{period}'] = (high_max - df['close']) / (high_max - low_min) * 100
    df[f'WR{period}'] = df[f'WR{period}'].fillna(50)
    
    return df


def calculate_cci(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """计算 CCI 指标"""
    df = df.copy()
    
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma_tp = tp.rolling(window=period, min_periods=1).mean()
    md = tp.rolling(window=period, min_periods=1).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    
    df[f'CCI{period}'] = (tp - ma_tp) / (0.015 * md.replace(0, np.nan))
    df[f'CCI{period}'] = df[f'CCI{period}'].fillna(0)
    
    return df


def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算所有技术指标"""
    df = calculate_ma(df)
    df = calculate_macd(df)
    df = calculate_kdj(df)
    df = calculate_rsi(df)
    df = calculate_bollinger(df)
    df = calculate_wr(df)
    df = calculate_cci(df)
    return df


def detect_ma_cross(df: pd.DataFrame, short_period: int, long_period: int,
                    lookback_days: int = 5) -> bool:
    """
    检测均线金叉/死叉
    返回: True 如果在 lookback_days 内发生金叉
    """
    if len(df) < long_period + lookback_days:
        return False
    
    ma_short = df[f'MA{short_period}']
    ma_long = df[f'MA{long_period}']
    
    # 金叉: 前一天短<=长，当天短>长
    for i in range(-lookback_days, 0):
        if i == -len(df):
            break
        if ma_short.iloc[i-1] <= ma_long.iloc[i-1] and ma_short.iloc[i] > ma_long.iloc[i]:
            return True
    
    return False


def detect_macd_cross(df: pd.DataFrame, lookback_days: int = 5) -> Tuple[bool, bool]:
    """
    检测MACD金叉/死叉
    返回: (是否金叉, 是否死叉)
    """
    if len(df) < lookback_days + 2 or 'MACD_DIF' not in df.columns:
        return False, False
    
    dif = df['MACD_DIF']
    dea = df['MACD_DEA']
    
    golden = False
    dead = False
    
    for i in range(-lookback_days, 0):
        if i <= -len(df):
            break
        # 金叉: DIF上穿DEA
        if dif.iloc[i-1] <= dea.iloc[i-1] and dif.iloc[i] > dea.iloc[i]:
            golden = True
        # 死叉: DIF下穿DEA
        if dif.iloc[i-1] >= dea.iloc[i-1] and dif.iloc[i] < dea.iloc[i]:
            dead = True
    
    return golden, dead


def detect_kdj_cross(df: pd.DataFrame, lookback_days: int = 5) -> Tuple[bool, bool]:
    """检测KDJ金叉/死叉"""
    if len(df) < lookback_days + 2 or 'KDJ_K' not in df.columns:
        return False, False
    
    k = df['KDJ_K']
    d = df['KDJ_D']
    
    golden = False
    dead = False
    
    for i in range(-lookback_days, 0):
        if i <= -len(df):
            break
        if k.iloc[i-1] <= d.iloc[i-1] and k.iloc[i] > d.iloc[i]:
            golden = True
        if k.iloc[i-1] >= d.iloc[i-1] and k.iloc[i] < d.iloc[i]:
            dead = True
    
    return golden, dead


def count_signals(df: pd.DataFrame, config: TechFilterConfig) -> Tuple[int, List[str]]:
    """
    统计某只股票满足的技术信号数量
    
    Returns:
        (信号数量, 信号列表)
    """
    if df.empty or len(df) < 30:
        return 0, []
    
    # 先计算所有指标
    df = calculate_all_indicators(df)
    latest = df.iloc[-1]
    
    signals = []
    
    # 1. 均线信号
    if config.price_above_ma and f'MA{config.price_above_ma}' in df.columns:
        if latest['close'] > latest[f'MA{config.price_above_ma}']:
            signals.append(f"价格上穿MA{config.price_above_ma}")
    
    if config.price_below_ma and f'MA{config.price_below_ma}' in df.columns:
        if latest['close'] < latest[f'MA{config.price_below_ma}']:
            signals.append(f"价格下穿MA{config.price_below_ma}")
    
    if config.ma_bullish_alignment:
        if (latest.get('MA5', 0) > latest.get('MA10', 0) > 
            latest.get('MA20', 0) > latest.get('MA60', 0)):
            signals.append("均线多头排列")
    
    if config.ma_golden_cross and len(df) > max(config.ma_golden_cross) + 10:
        short, long = config.ma_golden_cross
        if detect_ma_cross(df, short, long, config.ma_golden_cross_days):
            signals.append(f"MA{short}金叉MA{long}")
    
    # 2. MACD信号
    if config.macd_golden_cross:
        golden, _ = detect_macd_cross(df, config.macd_golden_cross_days)
        if golden:
            signals.append("MACD金叉")
    
    if config.macd_above_zero:
        if latest.get('MACD_DIF', 0) > 0 and latest.get('MACD_DEA', 0) > 0:
            signals.append("MACD零轴上方")
    
    if config.macd_below_zero:
        if latest.get('MACD_DIF', 0) < 0 and latest.get('MACD_DEA', 0) < 0:
            signals.append("MACD零轴下方")
    
    # 3. KDJ信号
    if config.kdj_golden_cross:
        golden, _ = detect_kdj_cross(df, config.kdj_golden_cross_days)
        if golden:
            signals.append("KDJ金叉")
    
    if config.kdj_k_below is not None:
        if latest.get('KDJ_K', 100) < config.kdj_k_below:
            signals.append(f"KDJ超卖(K<{config.kdj_k_below})")
    
    if config.kdj_k_above is not None:
        if latest.get('KDJ_K', 0) > config.kdj_k_above:
            signals.append(f"KDJ超买(K>{config.kdj_k_above})")
    
    # 4. RSI信号
    rsi_col = f'RSI{config.rsi_period}'
    if rsi_col in df.columns:
        if config.rsi_below is not None and latest[rsi_col] < config.rsi_below:
            signals.append(f"RSI超卖({latest[rsi_col]:.1f}<{config.rsi_below})")
        if config.rsi_above is not None and latest[rsi_col] > config.rsi_above:
            signals.append(f"RSI超买({latest[rsi_col]:.1f}>{config.rsi_above})")
    
    # 5. 布林带信号
    if 'BOLL_UPPER' in df.columns:
        if config.boll_break_upper and latest['close'] > latest['BOLL_UPPER']:
            signals.append("突破布林上轨")
        if config.boll_break_lower and latest['close'] < latest['BOLL_LOWER']:
            signals.append("跌破布林下轨")
        if config.boll_band_width_min and latest.get('BOLL_WIDTH', 0) > config.boll_band_width_min:
            signals.append("布林带开口")
        if config.boll_band_width_max and latest.get('BOLL_WIDTH', 999) < config.boll_band_width_max:
            signals.append("布林带收口")
    
    # 6. 成交量信号
    if config.volume_surge_ratio and 'volume' in df.columns:
        vol_ma = df['volume'].rolling(window=config.volume_ma_period, min_periods=1).mean()
        if latest['volume'] > vol_ma.iloc[-1] * config.volume_surge_ratio:
            signals.append(f"放量(>{config.volume_surge_ratio}倍均量)")
    
    return len(signals), signals


def filter_by_technical(stock_code: str, df: pd.DataFrame, 
                        config: TechFilterConfig) -> Tuple[bool, int, List[str]]:
    """
    根据技术指标筛选单只股票
    
    Returns:
        (是否通过, 信号数量, 信号列表)
    """
    signal_count, signals = count_signals(df, config)
    passed = signal_count >= config.min_signals_count
    
    return passed, signal_count, signals


# 预设技术指标策略
TECH_PRESETS = {
    "趋势突破": TechFilterConfig(
        price_above_ma=20,
        ma_golden_cross=(5, 20),
        macd_golden_cross=True,
        volume_surge_ratio=1.5,
        min_signals_count=2,
    ),
    "超跌反弹": TechFilterConfig(
        rsi_below=30,
        kdj_k_below=20,
        boll_break_lower=True,
        min_signals_count=1,
    ),
    "均线多头": TechFilterConfig(
        ma_bullish_alignment=True,
        price_above_ma=60,
        macd_above_zero=True,
        min_signals_count=2,
    ),
    "布林带收口": TechFilterConfig(
        boll_band_width_max=0.05,
        macd_golden_cross=True,
        min_signals_count=1,
    ),
    "MACD零轴金叉": TechFilterConfig(
        macd_golden_cross=True,
        macd_above_zero=True,
        ma_golden_cross=(5, 10),
        min_signals_count=2,
    ),
}
