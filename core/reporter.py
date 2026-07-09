"""
报告生成模块
生成可视化图表和回测报告
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from .backtest_engine import BacktestResult


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_backtest_report(self, result: BacktestResult) -> str:
        """
        生成回测报告 (Markdown格式)
        
        Returns:
            str: 报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"回测报告_{result.strategy_name}_{timestamp}.md"
        filepath = self.output_dir / filename
        
        report = f"""# 📊 回测报告: {result.strategy_name}

## 基本信息

| 指标 | 数值 |
|------|------|
| 回测区间 | {result.start_date} ~ {result.end_date} |
| 初始资金 | {result.initial_cash:.2f} 万元 |
| 期末资产 | {result.final_value:.2f} 万元 |
| 总收益率 | **{result.total_return_pct:+.2f}%** |
| 年化收益率 | {result.annual_return_pct:+.2f}% |
| 最大回撤 | {result.max_drawdown_pct:.2f}% |
| 夏普比率 | {result.sharpe_ratio:.2f} |
| 交易次数 | {result.trade_count} |

## 收益曲线

"""
        
        if not result.equity_curve.empty:
            report += "\n| 日期 | 总资产(万元) | 收益率(%) |\n"
            report += "|------|-------------|-----------|\n"
            
            for _, row in result.equity_curve.iterrows():
                report += f"| {row['date']} | {row['total_value']:.2f} | {row['return_pct']:+.2f} |\n"
        
        report += f"""

## 交易记录

| 日期 | 代码 | 名称 | 操作 | 价格 | 数量 | 金额 | 手续费 |
|------|------|------|------|------|------|------|--------|
"""
        
        for trade in result.trades:
            report += f"| {trade['date']} | {trade['stock_code']} | {trade['stock_name']} | {trade['action']} | {trade['price']:.2f} | {trade['shares']} | {trade['amount']:.2f} | {trade['commission']:.2f} |\n"
        
        report += f"""

---
*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"📄 回测报告已生成: {filepath}")
        return str(filepath)
    
    def plot_equity_curve(self, result: BacktestResult, save_path: Optional[str] = None) -> str:
        """
        绘制收益曲线图
        
        Returns:
            str: 图片保存路径
        """
        if result.equity_curve.empty:
            print("[警告] 无权益曲线数据")
            return ""
        
        try:
            import matplotlib
            matplotlib.use('Agg')  # 无GUI环境
            import matplotlib.pyplot as plt
            from daimon_runtime import setup_plot, save_figure
            
            # 这里需要在Daimon运行时中执行
            # 简化：返回空，实际使用时在运行环境中绘制
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            df = result.equity_curve
            ax.plot(df['date'], df['total_value'], linewidth=2, color='#2196F3', label='策略净值')
            ax.axhline(y=result.initial_cash, color='gray', linestyle='--', alpha=0.5, label='初始资金')
            
            ax.set_title(f'收益曲线 - {result.strategy_name}', fontsize=14)
            ax.set_xlabel('日期')
            ax.set_ylabel('资产价值(万元)')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = self.output_dir / f"收益曲线_{timestamp}.png"
            
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            print(f"📈 收益曲线图已保存: {save_path}")
            return str(save_path)
            
        except Exception as e:
            print(f"[警告] 绘图失败: {e}")
            return ""


def generate_screen_summary(results_df: pd.DataFrame, strategy_name: str = "选股结果") -> str:
    """
    生成选股结果摘要文本
    
    Returns:
        str: 摘要文本
    """
    if results_df.empty:
        return "选股结果为空"
    
    summary = f"""
{'='*60}
📋 {strategy_name} 选股摘要
{'='*60}

📊 整体统计:
  • 筛选出股票数量: {len(results_df)} 只
  • 平均市盈率 PE: {results_df['pe'].mean():.2f}
  • 平均市净率 PB: {results_df['pb'].mean():.2f}
  • 平均总市值: {results_df['total_mv'].mean()/1e8:.2f} 亿元
  • 平均评分: {results_df['score'].mean():.2f}

🏆 前5名:
"""
    
    for i, (_, row) in enumerate(results_df.head(5).iterrows(), 1):
        summary += f"  {i}. {row['stock_code']} {row['stock_name']} | PE:{row.get('pe', 'N/A'):.1f} | PB:{row.get('pb', 'N/A'):.2f} | 评分:{row.get('score', 0):.1f} {row.get('综合评级', '')}\n"
    
    summary += f"\n{'='*60}\n"
    
    return summary
