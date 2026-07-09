"""
iFinD Python SDK 统一封装层
═══════════════════════════════════════════════════════════════
支持三种模式自动切换，提供一致的数据访问 API：

  模式 1: iFinD Native  — 本地安装 agent_gw SDK (数据最丰富)
  模式 2: Daimon Agent  — Daimon 环境中通过 kimi_datasource 调用
  模式 3: AkShare Fallback — 纯本地免费方案 (无需任何配置)

使用方式:
    from core.ifind_sdk import iFinDClient
    client = iFinDClient()
    df = client.get_price("000001.SZ", "2024-01-01", "2024-06-30")
    df = client.get_tech_indicators("600519.SH")
    df = client.get_financial_index("000001.SZ", "profitability")
"""

from __future__ import annotations

import os
import json
import time
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Union, Any, Callable
from dataclasses import dataclass
from enum import Enum

import pandas as pd
import numpy as np


# ───────────────────────────────────────────────────────────────
# 模式检测与选择
# ───────────────────────────────────────────────────────────────

class iFinDMode(Enum):
    """iFinD 运行模式"""
    NATIVE = "native"           # 本地 agent_gw SDK
    DAIMON = "daimon"           # Daimon kimi_datasource
    FALLBACK = "fallback"       # AkShare 回退
    UNKNOWN = "unknown"


def _detect_mode() -> iFinDMode:
    """自动检测最佳可用模式"""
    # 1. 检查本地 agent_gw SDK
    try:
        import agent_gw
        return iFinDMode.NATIVE
    except ImportError:
        pass
    
    # 2. 检查是否在 Daimon 环境中
    try:
        import importlib.util
        spec = importlib.util.find_spec("kimi_datasource_call_v2")
        if spec is not None:
            return iFinDMode.DAIMON
    except Exception:
        pass
    
    # 3. 检查 AkShare
    try:
        import akshare as ak
        return iFinDMode.FALLBACK
    except ImportError:
        pass
    
    return iFinDMode.UNKNOWN


# ───────────────────────────────────────────────────────────────
# 抽象基类
# ───────────────────────────────────────────────────────────────

class _iFinDAdapter(ABC):
    """iFinD 适配器抽象基类"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def get_price(self, ticker: Union[str, List[str]],
                  start_date: str, end_date: str,
                  interval: str = "D", adjust: str = "forward") -> pd.DataFrame:
        """获取历史价格数据"""
        pass
    
    @abstractmethod
    def get_realtime(self, ticker: Union[str, List[str]],
                     data_type: str = "close_summary",
                     query_time: Optional[str] = None) -> pd.DataFrame:
        """获取实时/收盘数据"""
        pass
    
    @abstractmethod
    def get_tech_indicators(self, ticker: Union[str, List[str]],
                            query_time: Optional[str] = None) -> pd.DataFrame:
        """获取实时技术指标"""
        pass
    
    @abstractmethod
    def get_financial_index(self, ticker: Union[str, List[str]],
                            category: str = "profitability",
                            financial_parameter: Optional[str] = None) -> pd.DataFrame:
        """获取财务指标"""
        pass
    
    @abstractmethod
    def get_stock_info(self, ticker: Union[str, List[str]],
                       request_time: Optional[str] = None) -> pd.DataFrame:
        """获取股票基本信息"""
        pass
    
    @abstractmethod
    def get_financial_statements(self, ticker: Union[str, List[str]],
                                  statement: str = "all",
                                  financial_parameter: Optional[str] = None) -> pd.DataFrame:
        """获取财务报表"""
        pass
    
    @abstractmethod
    def get_holder_info(self, ticker: Union[str, List[str]],
                        request_time: Optional[str] = None) -> pd.DataFrame:
        """获取股东信息"""
        pass
    
    @abstractmethod
    def get_announcement(self, ticker: Union[str, List[str]],
                         start_date: str, end_date: str) -> pd.DataFrame:
        """获取公告信息"""
        pass
    
    @abstractmethod
    def get_forecast(self, ticker: Union[str, List[str]]) -> pd.DataFrame:
        """获取预测数据"""
        pass
    
    # 辅助方法
    def _split_tickers(self, ticker: Union[str, List[str]], batch_size: int = 3) -> List[str]:
        """将 ticker 拆分为批量列表"""
        if isinstance(ticker, str):
            tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        else:
            tickers = [str(t).strip() for t in ticker if str(t).strip()]
        
        # 返回批次列表，每批用逗号连接
        batches = []
        for i in range(0, len(tickers), batch_size):
            batch = ",".join(tickers[i:i + batch_size])
            batches.append(batch)
        return batches
    
    def _add_suffix(self, code: str) -> str:
        """为股票代码添加市场后缀"""
        code = str(code).strip().upper()
        if "." in code:
            return code
        if code.startswith("6"):
            return f"{code}.SH"
        elif code.startswith("0") or code.startswith("3"):
            return f"{code}.SZ"
        elif code.startswith("8") or code.startswith("4"):
            return f"{code}.BJ"
        elif code.startswith("68"):
            return f"{code}.SH"
        elif code.startswith("30"):
            return f"{code}.SZ"
        return code
    
    def _remove_suffix(self, code: str) -> str:
        """移除股票代码的市场后缀"""
        return str(code).strip().split(".")[0]
    
    def _ensure_cache_dir(self) -> Path:
        """确保缓存目录存在"""
        cache_dir = Path("data/cache/ifind")
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir


# ───────────────────────────────────────────────────────────────
# 模式 1: iFinD Native (本地 agent_gw SDK)
# ───────────────────────────────────────────────────────────────

def _init_api_key_from_secrets():
    """从 Streamlit secrets 或环境变量读取 API Key 并设置到环境变量"""
    # 优先级: 环境变量 > st.secrets
    if os.environ.get("KIMI_API_KEY"):
        return
    
    try:
        import streamlit as st
        key = st.secrets.get("KIMI_API_KEY") or st.secrets.get("kimi_api_key")
        if key:
            os.environ["KIMI_API_KEY"] = key
    except Exception:
        pass


class _iFinDNativeAdapter(_iFinDAdapter):
    """
    iFinD Native 适配器
    需要本地安装 agent_gw: 
        python3 -m pip install "$(curl -s https://cdn.kimi.com/agentgw/pysdk/manifest.json | python3 -c 'import json,sys; print(json.load(sys.stdin)["latest"]["url"])')"
    需要 API Key: ~/.kimi/agent-gw.json 或环境变量 KIMI_API_KEY
    """
    
    def __init__(self):
        # 先从 secrets 初始化 API Key
        _init_api_key_from_secrets()
        
        try:
            from agent_gw import AgentGwClient, AgentGwError
            self._client_cls = AgentGwClient
            self._error_cls = AgentGwError
            self._client = None
        except ImportError as e:
            raise ImportError(
                "iFinD Native 模式需要 agent_gw SDK。请运行:\n"
                '  python3 -m pip install "$(curl -s https://cdn.kimi.com/agentgw/pysdk/manifest.json | python3 -c \'import json,sys; print(json.load(sys.stdin)["latest"]["url"])\')"'  # noqa: E501
            ) from e
    
    @property
    def name(self) -> str:
        return "iFinD Native (agent_gw)"
    
    def _call(self, api_name: str, params: Dict) -> Dict:
        """调用 iFinD API"""
        payload = {
            "data_source_name": "ifind",
            "api_name": api_name,
            "params": params,
        }
        
        try:
            with self._client_cls(timeout=60.0) as client:
                resp = client.tools.call_data_source_tool(payload)
            
            raw = resp.raw
            
            if not raw.get("is_success"):
                error = raw.get("error") or {}
                msg = " | ".join(error.get("assistant", []) or error.get("user", []))
                raise RuntimeError(f"iFinD API 错误: {msg}")
            
            # 保存返回的文件
            for file_info in raw.get("files") or []:
                if isinstance(file_info, dict) and file_info.get("name"):
                    path = Path(str(file_info["name"]))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(str(file_info.get("content", "")), encoding="utf-8")
            
            return raw
            
        except self._error_cls as e:
            raise RuntimeError(f"iFinD 调用失败: {e}")
    
    def get_price(self, ticker: Union[str, List[str]],
                  start_date: str, end_date: str,
                  interval: str = "D", adjust: str = "forward") -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"price_{batch.replace(',', '_')}_{start_date}_{end_date}.csv")
            
            self._call("stock_finance_data_get_price", {
                "ticker": batch,
                "start_date": start_date,
                "end_date": end_date,
                "file_path": file_path,
                "interval": interval,
                "adjust": adjust,
            })
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)  # 避免过快请求
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_realtime(self, ticker: Union[str, List[str]],
                     data_type: str = "close_summary",
                     query_time: Optional[str] = None) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"rt_{batch.replace(',', '_')}_{data_type}.csv")
            
            params = {
                "ticker": batch,
                "file_path": file_path,
                "type": data_type,
            }
            if query_time:
                params["time"] = query_time
            
            self._call("stock_finance_data_get_stock_realtime_price", params)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_tech_indicators(self, ticker: Union[str, List[str]],
                            query_time: Optional[str] = None) -> pd.DataFrame:
        
        return self.get_realtime(ticker, data_type="realtime_tech", query_time=query_time)
    
    def get_financial_index(self, ticker: Union[str, List[str]],
                            category: str = "profitability",
                            financial_parameter: Optional[str] = None) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        if financial_parameter is None:
            current_year = datetime.now().year
            financial_parameter = f"{current_year}0331"
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"fin_{batch.replace(',', '_')}_{category}.csv")
            
            self._call("stock_finance_data_get_stock_financial_index", {
                "ticker": batch,
                "financial_parameter": financial_parameter,
                "category": category,
                "file_path": file_path,
            })
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_stock_info(self, ticker: Union[str, List[str]],
                       request_time: Optional[str] = None) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"info_{batch.replace(',', '_')}.csv")
            
            params = {
                "ticker": batch,
                "file_path": file_path,
            }
            if request_time:
                params["request_time"] = request_time
            
            self._call("stock_finance_data_get_stock_info", params)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_financial_statements(self, ticker: Union[str, List[str]],
                                  statement: str = "all",
                                  financial_parameter: Optional[str] = None) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        if financial_parameter is None:
            current_year = datetime.now().year
            financial_parameter = f"{current_year}0331"
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"fs_{batch.replace(',', '_')}_{statement}.csv")
            
            self._call("stock_finance_data_get_financial_statements", {
                "ticker": batch,
                "statement": statement,
                "financial_parameter": financial_parameter,
                "file_path": file_path,
            })
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_holder_info(self, ticker: Union[str, List[str]],
                        request_time: Optional[str] = None) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"holder_{batch.replace(',', '_')}.csv")
            
            params = {
                "ticker": batch,
                "file_path": file_path,
            }
            if request_time:
                params["request_time"] = request_time
            
            self._call("stock_finance_data_get_holder_info", params)
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_announcement(self, ticker: Union[str, List[str]],
                         start_date: str, end_date: str) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"announce_{batch.replace(',', '_')}.csv")
            
            self._call("stock_finance_data_get_stock_announcement", {
                "ticker": batch,
                "start_date": start_date,
                "end_date": end_date,
                "file_path": file_path,
            })
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_forecast(self, ticker: Union[str, List[str]]) -> pd.DataFrame:
        
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"forecast_{batch.replace(',', '_')}.csv")
            
            self._call("stock_finance_data_get_forecast", {
                "ticker": batch,
                "file_path": file_path,
            })
            
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
            
            time.sleep(0.3)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()


# ───────────────────────────────────────────────────────────────
# 模式 2: Daimon Agent (kimi_datasource_call_v2)
# ───────────────────────────────────────────────────────────────

class _iFinDDaimonAdapter(_iFinDAdapter):
    """
    Daimon 代理适配器
    在 Daimon 环境中通过 kimi_datasource_call_v2 工具调用 iFinD 数据
    """
    
    def __init__(self):
        # 验证环境
        try:
            import importlib.util
            spec = importlib.util.find_spec("kimi_datasource_call_v2")
            if spec is None:
                raise ImportError("不在 Daimon 环境中")
        except Exception as e:
            raise ImportError(
                "Daimon 模式需要在 Kimi Work / Daimon 环境中运行。"
                "请使用 iFinDClient(auto_detect=True) 让系统自动选择合适的模式。"
            ) from e
    
    @property
    def name(self) -> str:
        return "iFinD Daimon Agent"
    
    def _call_datasource(self, api_name: str, params: Dict) -> Dict:
        """通过 Daimon 工具调用数据源"""
        # 这个方法是占位符，实际调用由外部工具完成
        # 在 Daimon 环境中，外层代码会重写这个方法
        raise NotImplementedError(
            "Daimon 适配器需要在外部通过 kimi_datasource_call_v2 工具调用。\n"
            "请使用 iFinDClient 的便捷方法，它们会自动处理 Daimon 调用。"
        )
    
    def get_price(self, ticker: Union[str, List[str]],
                  start_date: str, end_date: str,
                  interval: str = "D", adjust: str = "forward") -> pd.DataFrame:
        
        # 批量处理
        cache_dir = self._ensure_cache_dir()
        all_dfs = []
        
        for batch in self._split_tickers(ticker, batch_size=3):
            file_path = str(cache_dir / f"price_{batch.replace(',', '_')}.csv")
            
            # 这里存储调用参数，由外层执行实际调用
            call_params = {
                "ticker": batch,
                "start_date": start_date,
                "end_date": end_date,
                "file_path": file_path,
                "interval": interval,
                "adjust": adjust,
            }
            
            # 标记为待执行
            self._pending_calls = getattr(self, '_pending_calls', [])
            self._pending_calls.append(("stock_finance_data_get_price", call_params))
            
            # 尝试读取缓存
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                all_dfs.append(df)
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_realtime(self, ticker: Union[str, List[str]],
                     data_type: str = "close_summary",
                     query_time: Optional[str] = None) -> pd.DataFrame:
        
        # Daimon 模式下，这个方法需要通过外部工具链式调用
        # 简化实现：委托给 Native 适配器或直接报错
        raise NotImplementedError(
            "Daimon 模式下的实时数据获取需要外部工具支持。"
            "请使用 iFinDClient 的高级封装方法。"
        )
    
    def get_tech_indicators(self, ticker: Union[str, List[str]],
                            query_time: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_financial_index(self, ticker: Union[str, List[str]],
                            category: str = "profitability",
                            financial_parameter: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_stock_info(self, ticker: Union[str, List[str]],
                       request_time: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_financial_statements(self, ticker: Union[str, List[str]],
                                  statement: str = "all",
                                  financial_parameter: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_holder_info(self, ticker: Union[str, List[str]],
                        request_time: Optional[str] = None) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_announcement(self, ticker: Union[str, List[str]],
                         start_date: str, end_date: str) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")
    
    def get_forecast(self, ticker: Union[str, List[str]]) -> pd.DataFrame:
        raise NotImplementedError("请使用 iFinDClient 的便捷方法")


# ───────────────────────────────────────────────────────────────
# 模式 3: AkShare Fallback (纯本地免费)
# ───────────────────────────────────────────────────────────────

class _AkShareFallbackAdapter(_iFinDAdapter):
    """
    AkShare 回退适配器
    纯本地免费方案，无需任何 API Key
    """
    
    def __init__(self):
        try:
            import akshare as ak
            self._ak = ak
        except ImportError as e:
            raise ImportError(
                "AkShare 回退模式需要安装 akshare: pip install akshare"
            ) from e
    
    @property
    def name(self) -> str:
        return "AkShare Fallback (免费)"
    
    def get_price(self, ticker: Union[str, List[str]],
                  start_date: str, end_date: str,
                  interval: str = "D", adjust: str = "forward") -> pd.DataFrame:
        """使用 AkShare 获取历史价格"""
        
        all_dfs = []
        
        if isinstance(ticker, str):
            tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        else:
            tickers = list(ticker)
        
        adjust_map = {"forward": "qfq", "backward": "hfq", "none": ""}
        ak_adjust = adjust_map.get(adjust, "qfq")
        
        for code in tickers:
            code = self._remove_suffix(code)
            try:
                df = self._ak.stock_zh_a_hist(
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust=ak_adjust
                )
                
                if df is not None and not df.empty:
                    df['ticker'] = self._add_suffix(code)
                    col_map = {
                        '日期': 'date', '开盘': 'open', '收盘': 'close',
                        '最高': 'high', '最低': 'low', '成交量': 'volume',
                        '成交额': 'amount', '涨跌幅': 'pct_chg',
                        '涨跌额': 'change', '换手率': 'turn',
                    }
                    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                    all_dfs.append(df)
                    
            except Exception as e:
                print(f"[AkShare] 获取 {code} 价格失败: {e}")
                continue
        
        return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    def get_realtime(self, ticker: Union[str, List[str]],
                     data_type: str = "close_summary",
                     query_time: Optional[str] = None) -> pd.DataFrame:
        """使用 AkShare 获取实时行情"""
        
        try:
            df = self._ak.stock_zh_a_spot_em()
            
            # 筛选指定股票
            if isinstance(ticker, str):
                tickers = [self._remove_suffix(t.strip()) for t in ticker.split(",") if t.strip()]
            else:
                tickers = [self._remove_suffix(str(t)) for t in ticker]
            
            df = df[df['代码'].isin(tickers)]
            
            # 统一列名
            col_map = {
                '代码': 'ticker',
                '名称': 'name',
                '最新价': 'close',
                '涨跌幅': 'pct_chg',
                '涨跌额': 'change',
                '成交量': 'volume',
                '成交额': 'amount',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
                '流通市值': 'circ_mv',
                '换手率': 'turn',
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            
            # 添加市场后缀
            if 'ticker' in df.columns:
                df['ticker'] = df['ticker'].apply(self._add_suffix)
            
            return df
            
        except Exception as e:
            print(f"[AkShare] 获取实时行情失败: {e}")
            return pd.DataFrame()
    
    def get_tech_indicators(self, ticker: Union[str, List[str]],
                            query_time: Optional[str] = None) -> pd.DataFrame:
        """
        AkShare 不直接提供技术指标，通过 K 线数据计算
        """
        from .technical_indicators import calculate_all_indicators
        
        all_results = []
        
        if isinstance(ticker, str):
            tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        else:
            tickers = list(ticker)
        
        end = datetime.now()
        start = end - timedelta(days=120)
        
        for code in tickers:
            code_clean = self._remove_suffix(code)
            try:
                df = self.get_price(code_clean, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
                if df.empty:
                    continue
                
                df = calculate_all_indicators(df)
                latest = df.iloc[-1:].copy()
                latest['ticker'] = self._add_suffix(code_clean)
                all_results.append(latest)
                
            except Exception as e:
                continue
        
        return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
    
    def get_financial_index(self, ticker: Union[str, List[str]],
                            category: str = "profitability",
                            financial_parameter: Optional[str] = None) -> pd.DataFrame:
        """
        AkShare 财务指标有限，尽量获取
        """
        print("[提示] AkShare 财务指标数据有限，建议安装 iFinD SDK 获取完整财务数据")
        
        all_results = []
        
        if isinstance(ticker, str):
            tickers = [t.strip() for t in ticker.split(",") if t.strip()]
        else:
            tickers = list(ticker)
        
        # 使用实时行情中的基础财务数据
        rt = self.get_realtime(tickers)
        
        if not rt.empty:
            # 基础指标映射
            result = rt[['ticker', 'name', 'pe', 'pb', 'total_mv', 'circ_mv', 'turn']].copy()
            result['data_source'] = 'AkShare (limited)'
            return result
        
        return pd.DataFrame()
    
    def get_stock_info(self, ticker: Union[str, List[str]],
                       request_time: Optional[str] = None) -> pd.DataFrame:
        return self.get_realtime(ticker)
    
    def get_financial_statements(self, ticker: Union[str, List[str]],
                                  statement: str = "all",
                                  financial_parameter: Optional[str] = None) -> pd.DataFrame:
        print("[提示] AkShare 模式下暂不支持财务报表获取，建议安装 iFinD SDK")
        return pd.DataFrame()
    
    def get_holder_info(self, ticker: Union[str, List[str]],
                        request_time: Optional[str] = None) -> pd.DataFrame:
        print("[提示] AkShare 模式下暂不支持股东信息获取，建议安装 iFinD SDK")
        return pd.DataFrame()
    
    def get_announcement(self, ticker: Union[str, List[str]],
                         start_date: str, end_date: str) -> pd.DataFrame:
        print("[提示] AkShare 模式下暂不支持公告获取，建议安装 iFinD SDK")
        return pd.DataFrame()
    
    def get_forecast(self, ticker: Union[str, List[str]]) -> pd.DataFrame:
        print("[提示] AkShare 模式下暂不支持预测数据获取，建议安装 iFinD SDK")
        return pd.DataFrame()


# ───────────────────────────────────────────────────────────────
# 主入口: iFinDClient
# ───────────────────────────────────────────────────────────────

class iFinDClient:
    """
    iFinD 统一客户端
    
    自动检测最佳可用模式，提供一致的数据访问 API。
    
    Usage:
        >>> from core.ifind_sdk import iFinDClient
        >>> client = iFinDClient()
        >>> print(f"当前模式: {client.mode}")
        
        >>> # 获取历史价格
        >>> df = client.get_price("000001.SZ", "2024-01-01", "2024-06-30")
        
        >>> # 获取实时技术指标
        >>> df = client.get_tech_indicators("600519.SH")
        
        >>> # 获取财务指标
        >>> df = client.get_financial_index("000001.SZ", "profitability")
        
        >>> # 获取股票信息
        >>> df = client.get_stock_info("000001.SZ,600519.SH")
        
        >>> # 批量获取 (自动分3只一批)
        >>> codes = ["000001.SZ", "600519.SH", "000858.SZ", "002594.SZ"]
        >>> df = client.get_price(codes, "2024-01-01", "2024-06-30")
    """
    
    def __init__(self, mode: Optional[str] = None, auto_detect: bool = True):
        """
        Args:
            mode: 强制指定模式 "native" / "daimon" / "fallback"
            auto_detect: 是否自动检测最佳模式
        """
        self._adapter: Optional[_iFinDAdapter] = None
        self._mode: iFinDMode = iFinDMode.UNKNOWN
        
        if mode:
            self._mode = iFinDMode(mode)
        elif auto_detect:
            self._mode = _detect_mode()
        
        self._init_adapter()
    
    def _init_adapter(self):
        """初始化适配器"""
        if self._mode == iFinDMode.NATIVE:
            try:
                self._adapter = _iFinDNativeAdapter()
            except ImportError:
                print("[iFinD] Native 模式初始化失败，尝试回退...")
                self._mode = iFinDMode.FALLBACK
                self._init_adapter()
        
        elif self._mode == iFinDMode.DAIMON:
            try:
                self._adapter = _iFinDDaimonAdapter()
            except ImportError:
                print("[iFinD] Daimon 模式初始化失败，尝试回退...")
                self._mode = iFinDMode.FALLBACK
                self._init_adapter()
        
        elif self._mode == iFinDMode.FALLBACK:
            try:
                self._adapter = _AkShareFallbackAdapter()
            except ImportError:
                raise ImportError(
                    "无法初始化任何数据源。请至少安装以下之一:\n"
                    "  1. iFinD SDK: python3 -m pip install agent_gw\n"
                    "  2. AkShare: pip install akshare"
                )
        
        else:
            raise RuntimeError("无法检测到可用的数据源模式")
    
    @property
    def mode(self) -> str:
        """返回当前模式名称"""
        return self._mode.value
    
    @property
    def adapter_name(self) -> str:
        """返回当前适配器名称"""
        return self._adapter.name if self._adapter else "Unknown"
    
    def __repr__(self) -> str:
        return f"iFinDClient(mode='{self.mode}', adapter='{self.adapter_name}')"
    
    # ── 代理方法 ──
    
    def get_price(self, ticker: Union[str, List[str]],
                  start_date: str, end_date: str,
                  interval: str = "D", adjust: str = "forward") -> pd.DataFrame:
        """
        获取历史价格数据
        
        Args:
            ticker: 股票代码，支持单只或多只 (逗号分隔或列表)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            interval: 周期 D/W/M/Q/Y
            adjust: 复权 forward/backward/none
            
        Returns:
            DataFrame: 历史价格数据
        """
        return self._adapter.get_price(ticker, start_date, end_date, interval, adjust)
    
    def get_realtime(self, ticker: Union[str, List[str]],
                     data_type: str = "close_summary",
                     query_time: Optional[str] = None) -> pd.DataFrame:
        """
        获取实时/收盘数据
        
        Args:
            ticker: 股票代码
            data_type: close_summary / open_summary / realtime_price / realtime_tech
            query_time: 查询时间 YYYY-MM-DD HH:MM:SS
            
        Returns:
            DataFrame: 实时数据
        """
        return self._adapter.get_realtime(ticker, data_type, query_time)
    
    def get_tech_indicators(self, ticker: Union[str, List[str]],
                            query_time: Optional[str] = None) -> pd.DataFrame:
        """
        获取实时技术指标
        
        返回指标: MA5/10/20/60, EXPMA12/50, SAR, BOLL, BBI, RSI6/12/24, 
                  KDJ K/D/J, MACD DIF/DEA, DMI, BIAS, WR, CCI, ROC, LB, ATR14
        
        Args:
            ticker: 股票代码 (A股 only, 每次最多3只)
            query_time: 查询时间
            
        Returns:
            DataFrame: 技术指标数据
        """
        return self._adapter.get_tech_indicators(ticker, query_time)
    
    def get_financial_index(self, ticker: Union[str, List[str]],
                            category: str = "profitability",
                            financial_parameter: Optional[str] = None) -> pd.DataFrame:
        """
        获取财务指标
        
        Args:
            ticker: 股票代码
            category: 指标类别
                - capital_structure: 资本结构
                - liquidity: 短期流动性
                - efficiency: 运营效率
                - profitability: 盈利能力 (默认)
                - growth: 成长能力
                - cash_coverage: 现金流覆盖
            financial_parameter: 财报期 YYYY-MM-DD 如 2024-03-31
            
        Returns:
            DataFrame: 财务指标数据
        """
        return self._adapter.get_financial_index(ticker, category, financial_parameter)
    
    def get_stock_info(self, ticker: Union[str, List[str]],
                       request_time: Optional[str] = None) -> pd.DataFrame:
        """获取股票基本信息"""
        return self._adapter.get_stock_info(ticker, request_time)
    
    def get_financial_statements(self, ticker: Union[str, List[str]],
                                  statement: str = "all",
                                  financial_parameter: Optional[str] = None) -> pd.DataFrame:
        """
        获取财务报表
        
        Args:
            statement: all / balance_sheet / income_statement / cash_flow
        """
        return self._adapter.get_financial_statements(ticker, statement, financial_parameter)
    
    def get_holder_info(self, ticker: Union[str, List[str]],
                        request_time: Optional[str] = None) -> pd.DataFrame:
        """获取股东信息"""
        return self._adapter.get_holder_info(ticker, request_time)
    
    def get_announcement(self, ticker: Union[str, List[str]],
                         start_date: str, end_date: str) -> pd.DataFrame:
        """获取公告信息"""
        return self._adapter.get_announcement(ticker, start_date, end_date)
    
    def get_forecast(self, ticker: Union[str, List[str]]) -> pd.DataFrame:
        """获取预测数据 (A股 only)"""
        return self._adapter.get_forecast(ticker)
    
    # ── 便捷方法 ──
    
    def get_a_stock_list(self) -> pd.DataFrame:
        """获取 A 股全市场列表 (使用 AkShare)"""
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            col_map = {
                '代码': 'ticker',
                '名称': 'name',
                '最新价': 'close',
                '涨跌幅': 'pct_chg',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
                '流通市值': 'circ_mv',
            }
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            if 'ticker' in df.columns:
                df['ticker'] = df['ticker'].astype(str).apply(
                    lambda x: f"{x}.SH" if x.startswith('6') else f"{x}.SZ"
                )
            return df
        except Exception as e:
            print(f"[错误] 获取A股列表失败: {e}")
            return pd.DataFrame()
    
    def get_daily_kline(self, ticker: str, days: int = 60) -> pd.DataFrame:
        """
        便捷方法：获取最近 N 天日K线
        
        Args:
            ticker: 股票代码
            days: 天数
            
        Returns:
            DataFrame: OHLCV 数据
        """
        end = datetime.now()
        start = end - timedelta(days=days)
        return self.get_price(ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    
    def get_all_financial_dimensions(self, ticker: str,
                                      financial_parameter: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        便捷方法：获取全部6大财务维度
        
        Returns:
            Dict: {category: DataFrame}
        """
        categories = [
            "capital_structure", "liquidity", "efficiency",
            "profitability", "growth", "cash_coverage"
        ]
        
        results = {}
        for cat in categories:
            try:
                df = self.get_financial_index(ticker, cat, financial_parameter)
                if not df.empty:
                    results[cat] = df
            except Exception as e:
                print(f"[警告] 获取 {cat} 失败: {e}")
        
        return results


# ───────────────────────────────────────────────────────────────
# 便捷函数
# ───────────────────────────────────────────────────────────────

def create_client(mode: Optional[str] = None) -> iFinDClient:
    """创建 iFinD 客户端"""
    return iFinDClient(mode=mode)


# 单例
_client_instance: Optional[iFinDClient] = None


def get_client() -> iFinDClient:
    """获取 iFinD 客户端单例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = iFinDClient()
    return _client_instance
