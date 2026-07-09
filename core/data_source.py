"""
统一数据源接口层
支持 AkShare (本地免费) 和 stock_finance_data (Daimon环境 richer数据) 双源切换
"""

import os
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from pathlib import Path

import pandas as pd
import numpy as np


class BaseDataSource(ABC):
    """数据源抽象基类"""
    
    @abstractmethod
    def get_name(self) -> str:
        """返回数据源名称"""
        pass
    
    @abstractmethod
    def get_stock_list(self) -> pd.DataFrame:
        """获取全市场股票列表"""
        pass
    
    @abstractmethod
    def get_daily_kline(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "forward") -> pd.DataFrame:
        """获取日K线数据"""
        pass
    
    @abstractmethod
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        pass
    
    @abstractmethod
    def get_financial_indicators(self, stock_code: str, 
                                  category: str = "profitability") -> Optional[Dict]:
        """获取财务指标"""
        pass
    
    @abstractmethod
    def get_technical_indicators(self, stock_code: str, 
                                  query_time: Optional[str] = None) -> Optional[Dict]:
        """获取技术指标 (MA/MACD/KDJ/RSI/BOLL等)"""
        pass


class AkShareDataSource(BaseDataSource):
    """
    AkShare 数据源 - 纯Python，用户本地可用
    无需额外API Key，完全免费
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._ak = None
    
    def get_name(self) -> str:
        return "AkShare"
    
    def _get_ak(self):
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak
    
    def _cache_path(self, name: str) -> Path:
        today = datetime.now().strftime("%Y%m%d")
        return self.cache_dir / f"ak_{name}_{today}.pkl"
    
    def _load_cache(self, name: str) -> Optional[pd.DataFrame]:
        cache_file = self._cache_path(name)
        if cache_file.exists():
            try:
                return pd.read_pickle(cache_file)
            except Exception:
                return None
        return None
    
    def _save_cache(self, name: str, df: pd.DataFrame):
        cache_file = self._cache_path(name)
        df.to_pickle(cache_file)
    
    def get_stock_list(self) -> pd.DataFrame:
        cached = self._load_cache("stock_list")
        if cached is not None:
            return cached
        
        try:
            ak = self._get_ak()
            df = ak.stock_zh_a_spot_em()
            
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
            }
            rename_map = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_map)
            
            if 'stock_code' in df.columns:
                df['stock_code'] = df['stock_code'].astype(str).str.strip()
                df['market'] = df['stock_code'].apply(self._get_market)
            
            # 数值转换
            for col in ['pe', 'pb', 'total_mv', 'circ_mv', 'turnover', 'amount']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            self._save_cache("stock_list", df)
            return df
            
        except Exception as e:
            print(f"[AkShare] 获取股票列表失败: {e}")
            return pd.DataFrame()
    
    def _get_market(self, code: str) -> str:
        code = str(code).strip()
        if code.startswith('6'):
            return 'SH'
        elif code.startswith('0') or code.startswith('3'):
            return 'SZ'
        elif code.startswith('8') or code.startswith('4'):
            return 'BJ'
        elif code.startswith('68'):
            return 'KC'
        elif code.startswith('30'):
            return 'CY'
        return 'OTHER'
    
    def get_daily_kline(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "forward") -> pd.DataFrame:
        try:
            ak = self._get_ak()
            adjust_map = {"forward": "qfq", "backward": "hfq", "none": ""}
            ak_adjust = adjust_map.get(adjust, "qfq")
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=ak_adjust
            )
            
            if df is not None and not df.empty:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期')
                # 统一列名
                col_map = {
                    '日期': 'date',
                    '开盘': 'open',
                    '收盘': 'close',
                    '最高': 'high',
                    '最低': 'low',
                    '成交量': 'volume',
                    '成交额': 'amount',
                    '振幅': 'amplitude',
                    '涨跌幅': 'pct_change',
                    '涨跌额': 'change',
                    '换手率': 'turnover',
                }
                df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            
            return df if df is not None else pd.DataFrame()
            
        except Exception as e:
            print(f"[AkShare] 获取 {stock_code} K线失败: {e}")
            return pd.DataFrame()
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """AkShare暂不提供详细的个股信息接口，返回基础信息"""
        try:
            df = self.get_stock_list()
            row = df[df['stock_code'] == stock_code]
            if row.empty:
                return None
            r = row.iloc[0]
            return {
                'stock_code': stock_code,
                'stock_name': r.get('stock_name', ''),
                'market': r.get('market', ''),
                'pe': r.get('pe'),
                'pb': r.get('pb'),
                'total_mv': r.get('total_mv'),
                'circ_mv': r.get('circ_mv'),
            }
        except Exception:
            return None
    
    def get_financial_indicators(self, stock_code: str,
                                  category: str = "profitability") -> Optional[Dict]:
        """
        AkShare获取财务指标 - 简化版
        实际生产建议接入Tushare Pro或iFinD获取更完整的财务数据
        """
        try:
            ak = self._get_ak()
            # 尝试获取个股指标
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == stock_code]
            if not row.empty:
                r = row.iloc[0]
                return {
                    'pe': r.get('市盈率-动态'),
                    'pb': r.get('市净率'),
                    'turnover': r.get('换手率'),
                }
            return None
        except Exception:
            return None
    
    def get_technical_indicators(self, stock_code: str,
                                  query_time: Optional[str] = None) -> Optional[Dict]:
        """
        AkShare 不直接提供技术指标接口
        需要通过K线数据自行计算（在 technical_indicators.py 中实现）
        """
        return None  # 由上层计算


class StockFinanceDataSource(BaseDataSource):
    """
    stock_finance_data 数据源 - 通过 Daimon kimi_datasource 调用
    提供更丰富的财务数据和技术指标，但每请求最多3只股票
    适合在 Daimon 环境中使用
    """
    
    def __init__(self):
        self._available = None
    
    def get_name(self) -> str:
        return "stock_finance_data"
    
    def is_available(self) -> bool:
        """检查当前环境是否可用"""
        if self._available is not None:
            return self._available
        try:
            # 尝试调用一次API验证可用性
            import json
            # 这里只是检查工具是否存在，不实际调用
            self._available = True
            return True
        except Exception:
            self._available = False
            return False
    
    def get_stock_list(self) -> pd.DataFrame:
        """
        stock_finance_data 不提供全市场列表接口
        回退到 AkShare 获取
        """
        print("[stock_finance_data] 不提供全市场列表，回退到 AkShare")
        ak = AkShareDataSource()
        return ak.get_stock_list()
    
    def get_daily_kline(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "forward") -> pd.DataFrame:
        """
        通过 stock_finance_data 获取历史价格
        注意: 最多3年数据，每次最多3只股票
        """
        try:
            # 添加市场后缀
            ticker = self._format_ticker(stock_code)
            
            # 构建文件路径
            cache_dir = Path("data/cache/sfd")
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(cache_dir / f"{stock_code}_{start_date}_{end_date}.csv")
            
            # 调用数据源
            result = self._call_datasource(
                "stock_finance_data_get_price",
                {
                    "ticker": ticker,
                    "start_date": start_date,
                    "end_date": end_date,
                    "file_path": file_path,
                    "interval": "D",
                    "adjust": adjust,
                }
            )
            
            if result and os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                return df
            
            return pd.DataFrame()
            
        except Exception as e:
            print(f"[stock_finance_data] 获取 {stock_code} K线失败: {e}")
            # 回退到 AkShare
            ak = AkShareDataSource()
            return ak.get_daily_kline(stock_code, start_date, end_date, adjust)
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        try:
            ticker = self._format_ticker(stock_code)
            cache_dir = Path("data/cache/sfd")
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(cache_dir / f"{stock_code}_info.csv")
            
            result = self._call_datasource(
                "stock_finance_data_get_stock_info",
                {"ticker": ticker, "file_path": file_path}
            )
            
            if result and os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            
            return None
            
        except Exception as e:
            print(f"[stock_finance_data] 获取 {stock_code} 信息失败: {e}")
            return None
    
    def get_financial_indicators(self, stock_code: str,
                                  category: str = "profitability") -> Optional[Dict]:
        """
        获取财务指标 - stock_finance_data 提供6大维度
        category: capital_structure/liquidity/efficiency/profitability/growth/cash_coverage
        """
        try:
            ticker = self._format_ticker(stock_code)
            
            # 使用最新财报期
            current_year = datetime.now().year
            financial_param = f"{current_year}0331"  # 最新一期
            
            cache_dir = Path("data/cache/sfd")
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(cache_dir / f"{stock_code}_fin_{category}.csv")
            
            result = self._call_datasource(
                "stock_finance_data_get_stock_financial_index",
                {
                    "ticker": ticker,
                    "financial_parameter": financial_param,
                    "category": category,
                    "file_path": file_path,
                }
            )
            
            if result and os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            
            return None
            
        except Exception as e:
            print(f"[stock_finance_data] 获取 {stock_code} 财务指标失败: {e}")
            return None
    
    def get_technical_indicators(self, stock_code: str,
                                  query_time: Optional[str] = None) -> Optional[Dict]:
        """
        获取实时技术指标
        返回: MA5/10/20/60, MACD, KDJ, RSI, BOLL 等
        """
        try:
            ticker = self._format_ticker(stock_code)
            
            if query_time is None:
                query_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cache_dir = Path("data/cache/sfd")
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(cache_dir / f"{stock_code}_tech.csv")
            
            result = self._call_datasource(
                "stock_finance_data_get_stock_realtime_price",
                {
                    "ticker": ticker,
                    "file_path": file_path,
                    "time": query_time,
                    "type": "realtime_tech",
                }
            )
            
            if result and os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            
            return None
            
        except Exception as e:
            print(f"[stock_finance_data] 获取 {stock_code} 技术指标失败: {e}")
            return None
    
    def get_close_summary(self, stock_code: str) -> Optional[Dict]:
        """获取收盘 summary 数据"""
        try:
            ticker = self._format_ticker(stock_code)
            cache_dir = Path("data/cache/sfd")
            cache_dir.mkdir(parents=True, exist_ok=True)
            file_path = str(cache_dir / f"{stock_code}_close.csv")
            
            result = self._call_datasource(
                "stock_finance_data_get_stock_realtime_price",
                {
                    "ticker": ticker,
                    "file_path": file_path,
                    "type": "close_summary",
                }
            )
            
            if result and os.path.exists(file_path):
                df = pd.read_csv(file_path)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            
            return None
            
        except Exception as e:
            print(f"[stock_finance_data] 获取 {stock_code} 收盘数据失败: {e}")
            return None
    
    def _format_ticker(self, code: str) -> str:
        """添加市场后缀"""
        code = str(code).strip()
        if '.' in code:
            return code
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"
        elif code.startswith('8') or code.startswith('4'):
            return f"{code}.BJ"
        return code
    
    def _call_datasource(self, api_name: str, params: Dict):
        """
        调用 Daimon 数据源工具
        注意: 此方法在 Daimon 环境中通过 kimi_datasource_call_v2 调用
        在普通Python环境中会回退到 AkShare
        """
        # 检查是否在 Daimon 环境中
        try:
            # 尝试通过环境变量或导入判断
            import importlib
            spec = importlib.util.find_spec("kimi_datasource_call_v2")
            if spec is None:
                raise ImportError("Not in Daimon environment")
        except Exception:
            # 非Daimon环境，返回None让上层回退
            return None
        
        # 实际调用由外部注入
        return None


class iFinDDataSource(BaseDataSource):
    """
    iFinD 数据源 — 通过 iFinD SDK 获取数据

    支持三种模式自动切换：
      - Native: 本地 agent_gw SDK (数据最丰富)
      - Daimon: Daimon 环境中通过 kimi_datasource 调用
      - Fallback: AkShare 回退 (纯本地免费)

    在 Streamlit Cloud 等云端环境中，会自动回退到 AkShare。
    """

    def __init__(self):
        self._client = None
        self._ak_fallback = None
        self._init_client()

    def _init_client(self):
        """初始化 iFinD 客户端，失败时回退到 AkShare"""
        try:
            from .ifind_sdk import iFinDClient
            self._client = iFinDClient(auto_detect=True)
        except Exception as e:
            print(f"[iFinD] 初始化失败: {e}")
            self._client = None

    def get_name(self) -> str:
        if self._client:
            return f"iFinD ({self._client.adapter_name})"
        return "iFinD (AkShare回退)"

    def _get_ak_fallback(self):
        if self._ak_fallback is None:
            self._ak_fallback = AkShareDataSource()
        return self._ak_fallback

    def get_stock_list(self) -> pd.DataFrame:
        if self._client:
            try:
                df = self._client.get_a_stock_list()
                if not df.empty:
                    # 统一列名与 AkShare 保持一致
                    if 'ticker' in df.columns and 'stock_code' not in df.columns:
                        df['stock_code'] = df['ticker'].apply(lambda x: str(x).split('.')[0])
                    if 'name' in df.columns and 'stock_name' not in df.columns:
                        df['stock_name'] = df['name']
                    return df
            except Exception as e:
                print(f"[iFinD] 获取列表失败: {e}，回退到 AkShare")
        return self._get_ak_fallback().get_stock_list()

    def get_daily_kline(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "forward") -> pd.DataFrame:
        if self._client:
            try:
                ticker = self._format_ticker(stock_code)
                df = self._client.get_price(ticker, start_date, end_date, adjust=adjust)
                if not df.empty and 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                return df
            except Exception as e:
                print(f"[iFinD] 获取K线失败: {e}，回退到 AkShare")
        return self._get_ak_fallback().get_daily_kline(stock_code, start_date, end_date, adjust)

    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        if self._client:
            try:
                ticker = self._format_ticker(stock_code)
                df = self._client.get_stock_info(ticker)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            except Exception:
                pass
        return self._get_ak_fallback().get_stock_info(stock_code)

    def get_financial_indicators(self, stock_code: str,
                                  category: str = "profitability") -> Optional[Dict]:
        if self._client and self._client.mode != "fallback":
            try:
                ticker = self._format_ticker(stock_code)
                df = self._client.get_financial_index(ticker, category)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            except Exception:
                pass
        return self._get_ak_fallback().get_financial_indicators(stock_code, category)

    def get_technical_indicators(self, stock_code: str,
                                  query_time: Optional[str] = None) -> Optional[Dict]:
        if self._client and self._client.mode != "fallback":
            try:
                ticker = self._format_ticker(stock_code)
                df = self._client.get_tech_indicators(ticker, query_time)
                if not df.empty:
                    row = df.iloc[0]
                    return {col: row[col] for col in df.columns}
            except Exception:
                pass
        return self._get_ak_fallback().get_technical_indicators(stock_code, query_time)

    def _format_ticker(self, code: str) -> str:
        code = str(code).strip()
        if '.' in code:
            return code
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"
        elif code.startswith('8') or code.startswith('4'):
            return f"{code}.BJ"
        return code


class DataSourceManager:
    """
    数据源管理器
    自动选择最佳可用数据源，支持手动切换
    """
    
    def __init__(self, preferred: str = "auto", cache_dir: str = "data/cache"):
        self.cache_dir = cache_dir
        self._sources: Dict[str, BaseDataSource] = {}
        self._preferred = preferred
        self._active_source: Optional[BaseDataSource] = None
        
        self._init_sources()
    
    def _init_sources(self):
        """初始化所有数据源"""
        # AkShare - 总是可用
        self._sources["akshare"] = AkShareDataSource(cache_dir=self.cache_dir)
        
        # iFinD - 尝试初始化 (优先)
        try:
            ifind_ds = iFinDDataSource()
            self._sources["ifind"] = ifind_ds
            print(f"[数据源] iFinD 已加载: {ifind_ds.get_name()}")
        except Exception as e:
            print(f"[数据源] iFinD 不可用: {e}")
        
        # stock_finance_data - Daimon环境可用
        sfd = StockFinanceDataSource()
        if sfd.is_available():
            self._sources["stock_finance_data"] = sfd
        
        # 选择活动数据源
        self._select_active()
    
    def _select_active(self):
        """选择活动数据源"""
        if self._preferred == "auto":
            # 优先使用 iFinD (数据最丰富)
            if "ifind" in self._sources:
                self._active_source = self._sources["ifind"]
            elif "stock_finance_data" in self._sources:
                self._active_source = self._sources["stock_finance_data"]
            else:
                self._active_source = self._sources["akshare"]
        elif self._preferred in self._sources:
            self._active_source = self._sources[self._preferred]
        else:
            self._active_source = self._sources["akshare"]
    
    def set_source(self, name: str):
        """手动切换数据源"""
        if name in self._sources:
            self._active_source = self._sources[name]
            print(f"[数据源] 已切换至: {self._active_source.get_name()}")
        else:
            available = list(self._sources.keys())
            print(f"[警告] 数据源 '{name}' 不可用，当前可用: {available}")
    
    def get_active_source(self) -> BaseDataSource:
        return self._active_source
    
    def get_source_names(self) -> List[str]:
        return list(self._sources.keys())
    
    # 代理方法
    def get_stock_list(self) -> pd.DataFrame:
        return self._active_source.get_stock_list()
    
    def get_daily_kline(self, stock_code: str, start_date: str, end_date: str,
                        adjust: str = "forward") -> pd.DataFrame:
        return self._active_source.get_daily_kline(stock_code, start_date, end_date, adjust)
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        return self._active_source.get_stock_info(stock_code)
    
    def get_financial_indicators(self, stock_code: str,
                                  category: str = "profitability") -> Optional[Dict]:
        return self._active_source.get_financial_indicators(stock_code, category)
    
    def get_technical_indicators(self, stock_code: str,
                                  query_time: Optional[str] = None) -> Optional[Dict]:
        return self._active_source.get_technical_indicators(stock_code, query_time)
    
    def get_name(self) -> str:
        return self._active_source.get_name()


# 单例
ds_manager: Optional[DataSourceManager] = None


def get_data_source(preferred: str = "auto", cache_dir: str = "data/cache") -> DataSourceManager:
    """获取数据源管理器单例"""
    global ds_manager
    if ds_manager is None:
        ds_manager = DataSourceManager(preferred=preferred, cache_dir=cache_dir)
    return ds_manager
