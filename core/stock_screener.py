"""
多因子选股引擎 v2.0
支持基本面筛选 + 技术指标筛选 + 评分排序 + 结果导出
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
from pathlib import Path

import pandas as pd
import numpy as np

from .config import ScreenConfig, ALL_PRESETS
from .data_source import get_data_source
from .technical_indicators import (
    count_signals, filter_by_technical,
    calculate_all_indicators, TECH_PRESETS
)


class StockScreener:
    """多因子选股器 v2.0"""
    
    def __init__(self, config: Optional[ScreenConfig] = None):
        self.config = config or ScreenConfig()
        self.ds = get_data_source()
        self.results: pd.DataFrame = pd.DataFrame()
        self.screen_time: Optional[datetime] = None
    
    def screen(self, verbose: bool = True) -> pd.DataFrame:
        """
        执行选股流程
        
        Args:
            verbose: 是否打印进度信息
            
        Returns:
            DataFrame: 选股结果
        """
        self.screen_time = datetime.now()
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"🚀 开始选股 [{self.screen_time.strftime('%Y-%m-%d %H:%M:%S')}]")
            print(f"   数据源: {self.ds.get_name()}")
            if self.config.use_technical_filter:
                print(f"   模式: 基本面 + 技术指标")
            else:
                print(f"   模式: 基本面筛选")
            print(f"{'='*60}")
        
        # Step 1: 获取全市场数据
        if verbose:
            print("\n📊 Step 1/5: 获取全市场股票数据...")
        
        df = self.ds.get_stock_list()
        if df.empty:
            print("[错误] 无法获取股票数据，请检查网络连接")
            return pd.DataFrame()
        
        initial_count = len(df)
        if verbose:
            print(f"   全市场股票数量: {initial_count}")
        
        # Step 2: 初步过滤
        if verbose:
            print("\n🔍 Step 2/5: 执行初步过滤...")
        
        df = self._apply_basic_filters(df, verbose)
        
        # Step 3: 财务指标筛选
        if verbose:
            print("\n📈 Step 3/5: 执行财务指标筛选...")
        
        df = self._apply_financial_filters(df, verbose)
        
        # Step 4: 技术指标筛选 (新增)
        if self.config.use_technical_filter:
            if verbose:
                print(f"\n📉 Step 4/5: 执行技术指标筛选 (回看{self.config.tech_lookback_days}天)...")
            
            df = self._apply_technical_filters(df, verbose)
        else:
            if verbose:
                print("\n⏭️  Step 4/5: 跳过技术指标筛选")
        
        # Step 5: 评分与排序
        if verbose:
            print("\n⭐ Step 5/5: 综合评分与排序...")
        
        df = self._score_and_rank(df, verbose)
        
        # 保存结果
        self.results = df.copy()
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"✅ 选股完成！筛选出 {len(df)} 只股票")
            print(f"{'='*60}")
            if not df.empty:
                print(f"\n📋 前10只选股结果预览:")
                preview_cols = ['排名', 'stock_code', 'stock_name', 'close', 'pe', 'pb', 
                               'total_mv', 'score', '综合评级']
                if 'tech_signals' in df.columns:
                    preview_cols.append('tech_signals')
                available_cols = [c for c in preview_cols if c in df.columns]
                print(df[available_cols].head(10).to_string(index=False))
        
        return df
    
    def _apply_basic_filters(self, df: pd.DataFrame, verbose: bool) -> pd.DataFrame:
        """应用基础过滤条件"""
        original_count = len(df)
        
        # 排除ST股票
        if self.config.exclude_st and 'stock_name' in df.columns:
            st_mask = df['stock_name'].str.contains('ST|退', na=False, regex=True)
            df = df[~st_mask]
            if verbose:
                print(f"   排除ST股票: {original_count - len(df)} 只")
        
        # 排除北交所
        if self.config.exclude_bj and 'stock_code' in df.columns:
            bj_mask = df['stock_code'].astype(str).str.startswith(('8', '4'))
            df = df[~bj_mask]
        
        # 排除科创板
        if self.config.exclude_kc and 'stock_code' in df.columns:
            kc_mask = df['stock_code'].astype(str).str.startswith('688')
            df = df[~kc_mask]
        
        # 排除创业板
        if self.config.exclude_cy and 'stock_code' in df.columns:
            cy_mask = df['stock_code'].astype(str).str.startswith('300')
            df = df[~cy_mask]
        
        # 数值列转换
        numeric_cols = ['pe', 'pb', 'ps', 'total_mv', 'circ_mv', 'turnover', 'amount']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 排除缺失核心数据
        if 'pe' in df.columns:
            df = df[df['pe'].notna()]
        if 'pb' in df.columns:
            df = df[df['pb'].notna()]
        
        # 排除PE <= 0 (亏损股)
        if 'pe' in df.columns:
            df = df[df['pe'] > 0]
        
        if verbose:
            print(f"   基础过滤后剩余: {len(df)} 只")
        
        return df
    
    def _apply_financial_filters(self, df: pd.DataFrame, verbose: bool) -> pd.DataFrame:
        """应用财务指标过滤"""
        
        # 市盈率过滤
        if self.config.pe_min is not None and 'pe' in df.columns:
            df = df[df['pe'] >= self.config.pe_min]
        if self.config.pe_max is not None and 'pe' in df.columns:
            df = df[df['pe'] <= self.config.pe_max]
        
        # 市净率过滤
        if self.config.pb_min is not None and 'pb' in df.columns:
            df = df[df['pb'] >= self.config.pb_min]
        if self.config.pb_max is not None and 'pb' in df.columns:
            df = df[df['pb'] <= self.config.pb_max]
        
        # 市值过滤 (AkShare返回的总市值是元，转换为亿元)
        if 'total_mv' in df.columns:
            df['total_mv'] = pd.to_numeric(df['total_mv'], errors='coerce')
            if self.config.total_mv_min is not None:
                df = df[df['total_mv'] / 1e8 >= self.config.total_mv_min]
            if self.config.total_mv_max is not None:
                df = df[df['total_mv'] / 1e8 <= self.config.total_mv_max]
        
        # 流通市值过滤
        if 'circ_mv' in df.columns:
            df['circ_mv'] = pd.to_numeric(df['circ_mv'], errors='coerce')
            if self.config.circ_mv_min is not None:
                df = df[df['circ_mv'] / 1e8 >= self.config.circ_mv_min]
            if self.config.circ_mv_max is not None:
                df = df[df['circ_mv'] / 1e8 <= self.config.circ_mv_max]
        
        # 成交额过滤
        if self.config.avg_amount_min is not None and 'amount' in df.columns:
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
            df = df[df['amount'] >= self.config.avg_amount_min]
        
        if verbose:
            print(f"   财务指标过滤后剩余: {len(df)} 只")
        
        return df
    
    def _apply_technical_filters(self, df: pd.DataFrame, verbose: bool) -> pd.DataFrame:
        """
        应用技术指标筛选
        需要获取每只股票的历史K线数据来计算指标
        """
        if df.empty:
            return df
        
        # 构建技术指标配置
        tech_config = self.config.to_tech_filter_config()
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.config.tech_lookback_days + 30)
        
        end_str = end_date.strftime("%Y-%m-%d")
        start_str = start_date.strftime("%Y-%m-%d")
        
        passed_stocks = []
        signal_data = []
        
        total = len(df)
        checked = 0
        
        for _, row in df.iterrows():
            code = str(row.get('stock_code', '')).strip()
            if not code:
                continue
            
            checked += 1
            if verbose and checked % 20 == 0:
                print(f"   技术指标检查进度: {checked}/{total}", end='\r')
            
            try:
                # 获取历史K线
                kline = self.ds.get_daily_kline(code, start_str, end_str)
                
                if kline.empty or len(kline) < 30:
                    continue
                
                # 检查技术指标信号
                passed, signal_count, signals = filter_by_technical(code, kline, tech_config)
                
                if passed:
                    stock_data = row.to_dict()
                    stock_data['tech_signal_count'] = signal_count
                    stock_data['tech_signals'] = ' | '.join(signals) if signals else ''
                    stock_data['tech_signal_list'] = signals
                    passed_stocks.append(stock_data)
                
            except Exception as e:
                continue
        
        if verbose:
            print(f"   技术指标检查完成: {len(passed_stocks)}/{checked} 只通过")
        
        if passed_stocks:
            df = pd.DataFrame(passed_stocks)
        else:
            df = pd.DataFrame()
        
        return df
    
    def _score_and_rank(self, df: pd.DataFrame, verbose: bool) -> pd.DataFrame:
        """综合评分与排序"""
        
        if df.empty:
            return df
        
        # 计算综合评分
        df['score'] = 0.0
        weights = self.config.score_weights
        
        # PE评分 (越低越好)
        if 'pe' in df.columns and weights.get('pe', 0) > 0:
            pe = df['pe'].replace([np.inf, -np.inf], np.nan)
            pe_score = 1 / (pe.clip(lower=1))
            pe_score = self._normalize_score(pe_score)
            df['score'] += pe_score * weights['pe']
        
        # PB评分 (越低越好)
        if 'pb' in df.columns and weights.get('pb', 0) > 0:
            pb = df['pb'].replace([np.inf, -np.inf], np.nan).fillna(999)
            pb_score = 1 / (pb.clip(lower=0.1))
            pb_score = self._normalize_score(pb_score)
            df['score'] += pb_score * weights['pb']
        
        # 技术指标加分 (额外)
        if 'tech_signal_count' in df.columns:
            tech_score = self._normalize_score(df['tech_signal_count'].astype(float))
            df['score'] += tech_score * 0.15  # 技术指标占15%权重
        
        # 涨幅评分
        if 'pct_change' in df.columns:
            pct = pd.to_numeric(df['pct_change'], errors='coerce').fillna(0)
            change_score = 1 - (pct / 10).abs()
            change_score = change_score.clip(0, 1)
            df['score'] += change_score * 0.1
        
        # 归一化总分
        if df['score'].notna().any():
            score_min = df['score'].min()
            score_max = df['score'].max()
            if score_max > score_min:
                df['score'] = ((df['score'] - score_min) / (score_max - score_min) * 100).round(2)
            else:
                df['score'] = 50.0
        
        # 综合评级
        def get_rating(score):
            if pd.isna(score):
                return 'N/A'
            if score >= 85:
                return '⭐⭐⭐⭐⭐'
            elif score >= 70:
                return '⭐⭐⭐⭐'
            elif score >= 55:
                return '⭐⭐⭐'
            elif score >= 40:
                return '⭐⭐'
            else:
                return '⭐'
        
        df['综合评级'] = df['score'].apply(get_rating)
        
        # 排序
        sort_by = self.config.sort_by
        if sort_by == 'score':
            df = df.sort_values('score', ascending=False)
        elif sort_by == 'pe_asc':
            df = df.sort_values('pe', ascending=True)
        elif sort_by == 'pb_asc':
            df = df.sort_values('pb', ascending=True)
        elif sort_by == 'mv_asc':
            df = df.sort_values('total_mv', ascending=True)
        else:
            df = df.sort_values('score', ascending=False)
        
        # 限制结果数量
        if self.config.max_results > 0:
            df = df.head(self.config.max_results)
        
        # 添加排名
        df.insert(0, '排名', range(1, len(df) + 1))
        
        return df
    
    def _normalize_score(self, series: pd.Series) -> pd.Series:
        """将分数归一化到 0-1 范围"""
        series = series.replace([np.inf, -np.inf], np.nan).fillna(0)
        s_min, s_max = series.min(), series.max()
        if s_max > s_min:
            return (series - s_min) / (s_max - s_min)
        return pd.Series(0.5, index=series.index)
    
    def export_to_excel(self, filepath: Optional[str] = None) -> str:
        """导出选股结果到Excel"""
        if self.results.empty:
            print("[警告] 没有选股结果可导出")
            return ""
        
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mode = "技术" if self.config.use_technical_filter else "基本面"
            filepath = f"reports/选股结果_{mode}_{timestamp}.xlsx"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        export_df = self.results.copy()
        
        # 市值转换为亿元显示
        for col in ['total_mv', 'circ_mv']:
            if col in export_df.columns:
                export_df[col] = (export_df[col] / 1e8).round(2)
        
        # 选择核心列导出
        core_cols = ['排名', 'stock_code', 'stock_name', 'close', 'pct_change',
                     'pe', 'pb', 'total_mv', 'circ_mv', 'turnover', 'score', '综合评级']
        
        # 技术指标列
        if 'tech_signal_count' in export_df.columns:
            core_cols.extend(['tech_signal_count', 'tech_signals'])
        
        available_cols = [c for c in core_cols if c in export_df.columns]
        export_df = export_df[available_cols]
        
        # 重命名为中文
        rename_map = {
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'close': '最新价',
            'pct_change': '涨跌幅%',
            'pe': '市盈率PE',
            'pb': '市净率PB',
            'total_mv': '总市值(亿)',
            'circ_mv': '流通市值(亿)',
            'turnover': '换手率%',
            'score': '综合评分',
            'tech_signal_count': '技术信号数',
            'tech_signals': '技术信号详情',
        }
        export_df = export_df.rename(columns={k: v for k, v in rename_map.items() if k in export_df.columns})
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='选股结果', index=False)
            
            # 筛选条件说明
            config_df = pd.DataFrame({
                '筛选条件': [
                    '选股时间',
                    '数据源',
                    '排除ST',
                    'PE范围',
                    'PB范围',
                    '市值范围(亿)',
                    '技术指标筛选',
                    '排序方式',
                    '最大结果数',
                ],
                '设定值': [
                    self.screen_time.strftime('%Y-%m-%d %H:%M:%S') if self.screen_time else 'N/A',
                    self.ds.get_name(),
                    '是' if self.config.exclude_st else '否',
                    f"{self.config.pe_min or '无'} - {self.config.pe_max or '无'}",
                    f"{self.config.pb_min or '无'} - {self.config.pb_max or '无'}",
                    f"{self.config.total_mv_min or '无'} - {self.config.total_mv_max or '无'}",
                    '启用' if self.config.use_technical_filter else '未启用',
                    self.config.sort_by,
                    self.config.max_results,
                ]
            })
            config_df.to_excel(writer, sheet_name='筛选条件', index=False)
        
        print(f"\n📁 选股结果已导出: {filepath}")
        return filepath
    
    def export_to_csv(self, filepath: Optional[str] = None) -> str:
        """导出选股结果到CSV"""
        if self.results.empty:
            print("[警告] 没有选股结果可导出")
            return ""
        
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = f"reports/选股结果_{timestamp}.csv"
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        self.results.to_csv(filepath, index=False, encoding='utf-8-sig')
        print(f"\n📁 选股结果已导出: {filepath}")
        return filepath


# 便捷函数
def quick_screen(strategy_name: Optional[str] = None, 
                 custom_config: Optional[ScreenConfig] = None,
                 export: bool = True) -> pd.DataFrame:
    """
    快速选股接口
    
    Args:
        strategy_name: 使用预设策略名称
        custom_config: 自定义配置对象
        export: 是否自动导出Excel
        
    Returns:
        DataFrame: 选股结果
    """
    if custom_config:
        config = custom_config
    elif strategy_name and strategy_name in ALL_PRESETS:
        config = ALL_PRESETS[strategy_name]
    else:
        config = ScreenConfig()
    
    screener = StockScreener(config)
    results = screener.screen(verbose=True)
    
    if export and not results.empty:
        screener.export_to_excel()
    
    return results
