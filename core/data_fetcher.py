"""
数据获取模块
使用 AkShare 获取A股实时行情、财务指标、历史K线等数据
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

import pandas as pd
import numpy as np

# 延迟导入 akshare，避免未安装时报错
_ak = None

def _get_ak():
    """懒加载 akshare"""
    global _ak
    if _ak is None:
        import akshare as ak
        _ak = ak
    return _ak


class DataFetcher:
    """股票数据获取器"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ak = None
    
    @property
    def ak(self):
        if self._ak is None:
            self._ak = _get_ak()
        return self._ak
    
    def _cache_path(self, name: str) -> Path:
        """生成缓存文件路径"""
        today = datetime.now().strftime("%Y%m%d")
        return self.cache_dir / f"{name}_{today}.pkl"
    
    def _load_cache(self, name: str) -> Optional[pd.DataFrame]:
        """尝试从缓存加载数据"""
        cache_file = self._cache_path(name)
        if cache_file.exists():
            try:
                return pd.read_pickle(cache_file)
            except Exception:
                return None
        return None
    
    def _save_cache(self, name: str, df: pd.DataFrame):
        """保存数据到缓存"""
        cache_file = self._cache_path(name)
        df.to_pickle(cache_file)
    
    def get_stock_list(self, use_cache: bool = True) -> pd.DataFrame:
        """
        获取A股全市场股票列表
        
        Returns:
            DataFrame: 包含股票代码、名称、所属行业等信息
        """
        if use_cache:
            cached = self._load_cache("stock_list")
            if cached is not None:
                return cached
        
        try:
            # 获取A股所有上市公司信息
            df = self.ak.stock_zh_a_spot_em()
            
            # 标准化列名
            column_mapping = {
                '代码': 'stock_code',
                '名称': 'stock_name',
                '最新价': 'close',
                '涨跌幅': 'pct_change',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '振幅': 'amplitude',
                '最高': 'high',
                '最低': 'low',
                '今开': 'open',
                '昨收': 'pre_close',
                '量比': 'volume_ratio',
                '换手率': 'turnover',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
                '流通市值': 'circ_mv',
                '涨速': 'rise_speed',
                '5分钟涨跌': 'change_5min',
                '60日涨跌幅': 'change_60d',
                '年初至今涨跌幅': 'change_ytd',
            }
            
            # 重命名存在的列
            rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            
            # 确保 stock_code 是字符串类型
            if 'stock_code' in df.columns:
                df['stock_code'] = df['stock_code'].astype(str).str.strip()
            
            # 添加市场标识
            if 'stock_code' in df.columns:
                df['market'] = df['stock_code'].apply(self._get_market)
            
            if use_cache:
                self._save_cache("stock_list", df)
            
            return df
            
        except Exception as e:
            print(f"[警告] 获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def _get_market(self, code: str) -> str:
        """根据股票代码判断所属市场"""
        code = str(code).strip()
        if code.startswith('6'):
            return 'SH'  # 上海
        elif code.startswith('0') or code.startswith('3'):
            return 'SZ'  # 深圳
        elif code.startswith('8') or code.startswith('4'):
            return 'BJ'  # 北交所/新三板
        elif code.startswith('68'):
            return 'KC'  # 科创板
        elif code.startswith('30'):
            return 'CY'  # 创业板
        return 'OTHER'
    
    def get_stock_basic_info(self, use_cache: bool = True) -> pd.DataFrame:
        """
        获取股票基本信息（包含更多财务指标）
        
        Returns:
            DataFrame: 包含ROE、营收增长等财务数据
        """
        if use_cache:
            cached = self._load_cache("stock_basic")
            if cached is not None:
                return cached
        
        try:
            # 使用个股指标接口获取更详细的数据
            df = self.ak.stock_zh_a_spot_em()
            
            # 标准化列名
            column_mapping = {
                '代码': 'stock_code',
                '名称': 'stock_name',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
                '流通市值': 'circ_mv',
                '换手率': 'turnover',
                '涨跌幅': 'pct_change',
            }
            rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            
            if 'stock_code' in df.columns:
                df['stock_code'] = df['stock_code'].astype(str).str.strip()
            
            if use_cache:
                self._save_cache("stock_basic", df)
            
            return df
            
        except Exception as e:
            print(f"[警告] 获取基本信息失败: {e}")
            return pd.DataFrame()
    
    def get_financial_indicators(self, stock_code: str) -> Optional[Dict]:
        """
        获取单只股票的财务指标
        
        Args:
            stock_code: 股票代码 (如 "000001")
            
        Returns:
            Dict: 财务指标字典
        """
        try:
            # 获取主要财务指标
            df = self.ak.stock_financial_report_sina(stock=stock_code)
            if df.empty:
                return None
            
            # 取最新一期数据
            latest = df.iloc[0]
            
            return {
                'roe': latest.get('净资产收益率'),
                'roa': latest.get('总资产收益率'),
                'gross_margin': latest.get('毛利率'),
                'net_margin': latest.get('净利率'),
                'revenue_growth': latest.get('营业收入同比增长率'),
                'profit_growth': latest.get('净利润同比增长率'),
            }
            
        except Exception as e:
            print(f"[警告] 获取 {stock_code} 财务指标失败: {e}")
            return None
    
    def get_daily_kline(self, stock_code: str, 
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        adjust: str = "qfq") -> pd.DataFrame:
        """
        获取股票日K线数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期 (YYYYmmdd)
            end_date: 结束日期 (YYYYmmdd)
            adjust: 复权方式 qfq-前复权 hfq-后复权 不复权
            
        Returns:
            DataFrame: OHLCV数据
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        
        try:
            # 判断市场后缀
            market = self._get_market(stock_code)
            if market == 'SH':
                symbol = f"{stock_code}.sh"
            elif market in ['SZ', 'CY', 'KC']:
                symbol = f"{stock_code}.sz"
            else:
                symbol = stock_code
            
            df = self.ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust
            )
            
            if df is not None and not df.empty:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期')
            
            return df if df is not None else pd.DataFrame()
            
        except Exception as e:
            print(f"[警告] 获取 {stock_code} K线失败: {e}")
            return pd.DataFrame()
    
    def get_history_daily_basics(self, stock_code: str, 
                                  start_date: Optional[str] = None,
                                  end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取历史每日基本面数据 (用于回测)
        
        注意: AkShare没有直接提供历史PE/PB数据，这里用当前数据近似
        实际回测中建议使用专业数据接口 (Tushare Pro/iFinD)
        """
        # 先获取K线
        kline = self.get_daily_kline(stock_code, start_date, end_date)
        if kline.empty:
            return pd.DataFrame()
        
        # 对于回测需要历史财务数据，这里简化处理
        # 实际生产环境建议接入Tushare Pro的 daily_basic 接口
        return kline
    
    def get_industry_list(self) -> pd.DataFrame:
        """获取行业分类列表"""
        try:
            df = self.ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            print(f"[警告] 获取行业列表失败: {e}")
            return pd.DataFrame()
    
    def get_concept_list(self) -> pd.DataFrame:
        """获取概念板块列表"""
        try:
            df = self.ak.stock_board_concept_name_em()
            return df
        except Exception as e:
            print(f"[警告] 获取概念列表失败: {e}")
            return pd.DataFrame()


# 单例模式
_data_fetcher: Optional[DataFetcher] = None


def get_data_fetcher(cache_dir: str = "data/cache") -> DataFetcher:
    """获取数据获取器单例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher(cache_dir=cache_dir)
    return _data_fetcher
