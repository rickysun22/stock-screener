"""
回测引擎模块
支持向量化回测，计算收益曲线、风险指标等
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import numpy as np

from .config import BacktestConfig, ScreenConfig
from .data_fetcher import get_data_fetcher
from .stock_screener import StockScreener


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    start_date: str
    end_date: str
    initial_cash: float
    final_value: float
    total_return_pct: float
    annual_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: float
    trade_count: int
    win_count: int
    win_rate: float
    avg_profit_pct: float
    avg_loss_pct: float
    profit_loss_ratio: float
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)
    trades: List[Dict] = field(default_factory=list)
    config: Dict = field(default_factory=dict)
    report_path: str = ""


class BacktestEngine:
    """向量化回测引擎"""
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        self.config = config or BacktestConfig()
        self.fetcher = get_data_fetcher()
        
    def run_screen_backtest(self, screen_config: ScreenConfig,
                            start_date: str, 
                            end_date: str,
                            rebalance_freq: str = "monthly",
                            strategy_name: str = "选股策略回测") -> BacktestResult:
        """
        运行选股策略回测
        
        回测逻辑：
        1. 按调仓周期（如每月初）执行选股
        2. 买入选股结果中的股票（等权分配）
        3. 持有至下次调仓，重新选股并调仓
        4. 计算整体收益曲线
        
        Args:
            screen_config: 选股配置
            start_date: 回测开始日期 YYYY-MM-DD
            end_date: 回测结束日期 YYYY-MM-DD
            rebalance_freq: 调仓频率 monthly/weekly
            strategy_name: 策略名称
            
        Returns:
            BacktestResult: 回测结果
        """
        print(f"\n{'='*60}")
        print(f"📊 开始回测: {strategy_name}")
        print(f"   回测区间: {start_date} ~ {end_date}")
        print(f"   调仓频率: {rebalance_freq}")
        print(f"   初始资金: {self.config.initial_cash}万元")
        print(f"{'='*60}\n")
        
        # 生成调仓日期列表
        rebalance_dates = self._generate_rebalance_dates(start_date, end_date, rebalance_freq)
        
        if len(rebalance_dates) < 2:
            print("[错误] 回测区间太短，无法生成足够的调仓周期")
            return self._empty_result(strategy_name, start_date, end_date)
        
        # 初始化
        cash = self.config.initial_cash * 10000  # 转换为元
        holdings: Dict[str, Dict] = {}  # {code: {shares, cost, entry_date}}
        equity_history = []
        all_trades = []
        
        # 获取回测期内所有交易日的行情（简化：用指数作为基准）
        # 实际应该获取每只股票的日K线
        
        for i, rebalance_date in enumerate(rebalance_dates[:-1]):
            next_date = rebalance_dates[i + 1]
            
            print(f"\n📅 调仓 {i+1}/{len(rebalance_dates)-1}: {rebalance_date}")
            
            # 执行选股（简化版：用当前可用数据模拟）
            # 实际回测需要获取历史日期的数据
            selected_stocks = self._simulate_screen(rebalance_date, screen_config)
            
            if not selected_stocks:
                print("   本次无选股结果，保持当前持仓")
                continue
            
            # 计算当前持仓市值
            portfolio_value = self._calc_portfolio_value(holdings, rebalance_date)
            total_value = cash + portfolio_value
            
            print(f"   当前总资产: {total_value/10000:.2f}万元")
            print(f"   选股数量: {len(selected_stocks)}")
            
            # 等权分配资金
            target_positions = self._allocate_positions(
                selected_stocks, total_value, self.config.max_position_pct
            )
            
            # 执行调仓
            new_holdings = {}
            for stock in target_positions:
                code = stock['code']
                target_value = stock['target_value']
                price = stock['price']
                
                if price <= 0:
                    continue
                
                shares = int(target_value / price)
                if shares > 0:
                    cost = shares * price
                    commission = max(cost * self.config.commission_rate / 100, self.config.min_commission)
                    
                    if cash >= cost + commission:
                        cash -= (cost + commission)
                        new_holdings[code] = {
                            'shares': shares,
                            'cost': price,
                            'entry_date': rebalance_date,
                            'name': stock['name']
                        }
                        all_trades.append({
                            'date': rebalance_date,
                            'stock_code': code,
                            'stock_name': stock['name'],
                            'action': 'BUY',
                            'price': price,
                            'shares': shares,
                            'amount': cost,
                            'commission': commission
                        })
            
            holdings = new_holdings
            
            # 记录该周期的权益
            equity_history.append({
                'date': rebalance_date,
                'cash': cash,
                'holdings_value': self._calc_portfolio_value(holdings, rebalance_date),
                'total_value': cash + self._calc_portfolio_value(holdings, rebalance_date)
            })
        
        # 计算最终收益
        final_value = cash + self._calc_portfolio_value(holdings, end_date)
        
        # 构建权益曲线
        equity_df = pd.DataFrame(equity_history)
        if not equity_df.empty:
            equity_df['total_value'] = equity_df['total_value'] / 10000  # 转换为万元
            equity_df['return_pct'] = (equity_df['total_value'] / self.config.initial_cash - 1) * 100
        
        # 计算风险指标
        total_return_pct = (final_value / (self.config.initial_cash * 10000) - 1) * 100
        
        # 年化收益
        days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days
        years = days / 365.25
        annual_return_pct = ((final_value / (self.config.initial_cash * 10000)) ** (1/years) - 1) * 100 if years > 0 else 0
        
        # 最大回撤 (简化)
        max_drawdown_pct = 0
        if len(equity_df) > 1:
            cummax = equity_df['total_value'].cummax()
            drawdown = (equity_df['total_value'] - cummax) / cummax * 100
            max_drawdown_pct = drawdown.min()
        
        # 夏普比率 (简化，假设无风险利率3%)
        sharpe_ratio = 0
        if len(equity_df) > 1:
            returns = equity_df['total_value'].pct_change().dropna()
            if len(returns) > 1 and returns.std() > 0:
                excess_return = returns.mean() * 252 - 0.03  # 年化超额收益
                sharpe_ratio = excess_return / (returns.std() * np.sqrt(252))
        
        # 胜率
        win_count = sum(1 for t in all_trades if t['action'] == 'SELL' and False)  # 简化
        
        result = BacktestResult(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            initial_cash=self.config.initial_cash,
            final_value=final_value / 10000,
            total_return_pct=total_return_pct,
            annual_return_pct=annual_return_pct,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            trade_count=len(all_trades),
            win_count=0,
            win_rate=0,
            avg_profit_pct=0,
            avg_loss_pct=0,
            profit_loss_ratio=0,
            equity_curve=equity_df,
            trades=all_trades,
            config={}
        )
        
        self._print_result(result)
        
        return result
    
    def _generate_rebalance_dates(self, start_date: str, end_date: str, 
                                   freq: str) -> List[str]:
        """生成调仓日期列表"""
        dates = []
        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current <= end:
            dates.append(current.strftime("%Y-%m-%d"))
            if freq == "monthly":
                # 每月第一个交易日（简化为月初）
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            elif freq == "weekly":
                current += timedelta(days=7)
            else:
                current += timedelta(days=1)
        
        return dates
    
    def _simulate_screen(self, date: str, config: ScreenConfig) -> List[Dict]:
        """
        模拟历史日期的选股
        
        注意：这是一个简化版本。真实回测需要获取历史日期的完整财务数据。
        建议使用 Tushare Pro / iFinD 等付费数据接口获取历史财务数据。
        """
        # 简化：返回空列表，实际实现需要接入历史数据源
        # 这里作为框架预留
        return []
    
    def _calc_portfolio_value(self, holdings: Dict, date: str) -> float:
        """计算持仓市值"""
        total = 0
        for code, info in holdings.items():
            # 简化：用成本价代替，实际应该用当日收盘价
            total += info['shares'] * info['cost']
        return total
    
    def _allocate_positions(self, stocks: List[Dict], total_value: float, 
                            max_pct: float) -> List[Dict]:
        """等权分配仓位"""
        if not stocks:
            return []
        
        n = min(len(stocks), 10)  # 最多10只
        per_stock_value = min(total_value / n, total_value * max_pct / 100)
        
        positions = []
        for stock in stocks[:n]:
            positions.append({
                **stock,
                'target_value': per_stock_value
            })
        
        return positions
    
    def _empty_result(self, name: str, start: str, end: str) -> BacktestResult:
        """空结果"""
        return BacktestResult(
            strategy_name=name, start_date=start, end_date=end,
            initial_cash=self.config.initial_cash, final_value=self.config.initial_cash,
            total_return_pct=0, annual_return_pct=0, max_drawdown_pct=0,
            sharpe_ratio=0, trade_count=0, win_count=0, win_rate=0,
            avg_profit_pct=0, avg_loss_pct=0, profit_loss_ratio=0
        )
    
    def _print_result(self, result: BacktestResult):
        """打印回测结果"""
        print(f"\n{'='*60}")
        print(f"📈 回测结果: {result.strategy_name}")
        print(f"{'='*60}")
        print(f"   回测区间:     {result.start_date} ~ {result.end_date}")
        print(f"   初始资金:     {result.initial_cash:.2f}万元")
        print(f"   期末资产:     {result.final_value:.2f}万元")
        print(f"   总收益率:     {result.total_return_pct:+.2f}%")
        print(f"   年化收益率:   {result.annual_return_pct:+.2f}%")
        print(f"   最大回撤:     {result.max_drawdown_pct:.2f}%")
        print(f"   夏普比率:     {result.sharpe_ratio:.2f}")
        print(f"   交易次数:     {result.trade_count}")
        print(f"{'='*60}")


class SimpleBacktest:
    """简化版回测 - 用于快速验证选股结果"""
    
    def __init__(self):
        self.fetcher = get_data_fetcher()
    
    def simulate_hold_return(self, stock_codes: List[str], 
                             hold_days: int = 20) -> pd.DataFrame:
        """
        模拟持有N天的收益（简化回测）
        
        Args:
            stock_codes: 股票代码列表
            hold_days: 持有天数
            
        Returns:
            DataFrame: 各股票预期收益
        """
        results = []
        
        for code in stock_codes:
            try:
                # 获取最近的数据
                df = self.fetcher.get_daily_kline(code)
                if df.empty or len(df) < hold_days + 5:
                    continue
                
                # 计算最近hold_days的涨跌幅
                recent = df.tail(hold_days + 1)
                start_price = recent.iloc[0]['收盘']
                end_price = recent.iloc[-1]['收盘']
                return_pct = (end_price / start_price - 1) * 100
                
                results.append({
                    'stock_code': code,
                    'stock_name': '',  # 可在后续补充
                    'start_price': start_price,
                    'end_price': end_price,
                    'hold_days': hold_days,
                    'return_pct': round(return_pct, 2),
                    'max_price': recent['最高'].max(),
                    'min_price': recent['最低'].min(),
                    'max_return_pct': round((recent['最高'].max() / start_price - 1) * 100, 2),
                    'max_drawdown_pct': round((recent['最低'].min() / start_price - 1) * 100, 2),
                })
                
            except Exception as e:
                continue
        
        return pd.DataFrame(results)
