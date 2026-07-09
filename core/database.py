"""
数据库模块
使用 SQLite 存储选股历史、策略追踪、回测记录
"""

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

import pandas as pd
import numpy as np


class StockDatabase:
    """选股数据库管理器"""
    
    def __init__(self, db_path: str = "data/stock_screener.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_tables(self):
        """初始化数据表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 选股历史记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screen_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screen_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                strategy_name TEXT,
                config_json TEXT,
                stock_count INTEGER,
                market TEXT DEFAULT 'A股'
            )
        ''')
        
        # 选股结果明细表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screen_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screen_id INTEGER,
                rank INTEGER,
                stock_code TEXT,
                stock_name TEXT,
                select_price REAL,
                pe REAL,
                pb REAL,
                total_mv REAL,
                score REAL,
                rating TEXT,
                FOREIGN KEY (screen_id) REFERENCES screen_history(id)
            )
        ''')
        
        # 策略持仓追踪表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strategy_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                screen_id INTEGER,
                stock_code TEXT,
                stock_name TEXT,
                entry_date DATE,
                entry_price REAL,
                shares INTEGER DEFAULT 0,
                current_price REAL,
                current_value REAL,
                unrealized_pnl REAL,
                unrealized_pnl_pct REAL,
                status TEXT DEFAULT '持有',
                exit_date DATE,
                exit_price REAL,
                realized_pnl REAL,
                realized_pnl_pct REAL,
                notes TEXT,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (screen_id) REFERENCES screen_history(id)
            )
        ''')
        
        # 回测记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                strategy_name TEXT,
                config_json TEXT,
                start_date DATE,
                end_date DATE,
                initial_cash REAL,
                final_value REAL,
                total_return_pct REAL,
                annual_return_pct REAL,
                max_drawdown_pct REAL,
                sharpe_ratio REAL,
                trade_count INTEGER,
                win_rate REAL,
                report_path TEXT
            )
        ''')
        
        # 回测交易记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id INTEGER,
                trade_date DATE,
                stock_code TEXT,
                stock_name TEXT,
                action TEXT,
                price REAL,
                shares INTEGER,
                amount REAL,
                commission REAL,
                FOREIGN KEY (backtest_id) REFERENCES backtest_records(id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ========== 选股历史 ==========
    
    def save_screen_result(self, screener) -> int:
        """
        保存选股结果到数据库
        
        Args:
            screener: StockScreener 实例
            
        Returns:
            int: 选股记录ID
        """
        if screener.results.empty:
            return -1
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 保存选股历史主记录
        from dataclasses import asdict
        config_dict = asdict(screener.config)
        
        cursor.execute('''
            INSERT INTO screen_history (screen_time, strategy_name, config_json, stock_count)
            VALUES (?, ?, ?, ?)
        ''', (
            screener.screen_time or datetime.now(),
            screener.config.sort_by,
            json.dumps(config_dict, ensure_ascii=False),
            len(screener.results)
        ))
        
        screen_id = cursor.lastrowid
        
        # 保存选股明细
        for _, row in screener.results.iterrows():
            cursor.execute('''
                INSERT INTO screen_results 
                (screen_id, rank, stock_code, stock_name, select_price, pe, pb, total_mv, score, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                screen_id,
                int(row.get('排名', 0)),
                str(row.get('stock_code', '')),
                str(row.get('stock_name', '')),
                float(row.get('close', 0)) if pd.notna(row.get('close')) else None,
                float(row.get('pe', 0)) if pd.notna(row.get('pe')) else None,
                float(row.get('pb', 0)) if pd.notna(row.get('pb')) else None,
                float(row.get('total_mv', 0)) if pd.notna(row.get('total_mv')) else None,
                float(row.get('score', 0)) if pd.notna(row.get('score')) else None,
                str(row.get('综合评级', ''))
            ))
        
        conn.commit()
        conn.close()
        
        print(f"[数据库] 选股结果已保存，记录ID: {screen_id}")
        return screen_id
    
    def get_screen_history(self, limit: int = 50) -> pd.DataFrame:
        """获取选股历史记录"""
        conn = self._get_connection()
        df = pd.read_sql_query('''
            SELECT * FROM screen_history 
            ORDER BY screen_time DESC 
            LIMIT ?
        ''', conn, params=(limit,))
        conn.close()
        return df
    
    def get_screen_detail(self, screen_id: int) -> pd.DataFrame:
        """获取某次选股的详细结果"""
        conn = self._get_connection()
        df = pd.read_sql_query('''
            SELECT * FROM screen_results 
            WHERE screen_id = ?
            ORDER BY rank
        ''', conn, params=(screen_id,))
        conn.close()
        return df
    
    # ========== 策略追踪 ==========
    
    def add_tracking(self, screen_id: int, stock_code: str, stock_name: str,
                     entry_date: str, entry_price: float, shares: int = 0,
                     notes: str = "") -> int:
        """
        添加持仓追踪记录
        
        Returns:
            int: 追踪记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO strategy_tracking 
            (screen_id, stock_code, stock_name, entry_date, entry_price, shares, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (screen_id, stock_code, stock_name, entry_date, entry_price, shares, notes))
        
        tracking_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return tracking_id
    
    def update_tracking_price(self, tracking_id: int, current_price: float):
        """更新持仓当前价格"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT entry_price, shares FROM strategy_tracking WHERE id = ?
        ''', (tracking_id,))
        row = cursor.fetchone()
        
        if row:
            entry_price = row['entry_price']
            shares = row['shares']
            
            current_value = current_price * shares if shares > 0 else 0
            unrealized_pnl = (current_price - entry_price) * shares if shares > 0 else 0
            unrealized_pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            cursor.execute('''
                UPDATE strategy_tracking 
                SET current_price = ?, current_value = ?, 
                    unrealized_pnl = ?, unrealized_pnl_pct = ?,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (current_price, current_value, unrealized_pnl, unrealized_pnl_pct, tracking_id))
            
            conn.commit()
        
        conn.close()
    
    def close_tracking(self, tracking_id: int, exit_date: str, exit_price: float,
                       notes: str = ""):
        """平仓记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT entry_price, shares FROM strategy_tracking WHERE id = ?
        ''', (tracking_id,))
        row = cursor.fetchone()
        
        if row:
            entry_price = row['entry_price']
            shares = row['shares']
            
            realized_pnl = (exit_price - entry_price) * shares if shares > 0 else 0
            realized_pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            cursor.execute('''
                UPDATE strategy_tracking 
                SET status = '已平仓', exit_date = ?, exit_price = ?,
                    realized_pnl = ?, realized_pnl_pct = ?, notes = ?,
                    update_time = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (exit_date, exit_price, realized_pnl, realized_pnl_pct, notes, tracking_id))
            
            conn.commit()
        
        conn.close()
    
    def get_active_trackings(self, screen_id: Optional[int] = None) -> pd.DataFrame:
        """获取当前持仓追踪"""
        conn = self._get_connection()
        
        if screen_id:
            df = pd.read_sql_query('''
                SELECT * FROM strategy_tracking 
                WHERE screen_id = ? AND status = '持有'
                ORDER BY entry_date
            ''', conn, params=(screen_id,))
        else:
            df = pd.read_sql_query('''
                SELECT * FROM strategy_tracking 
                WHERE status = '持有'
                ORDER BY entry_date
            ''', conn)
        
        conn.close()
        return df
    
    def get_tracking_summary(self) -> pd.DataFrame:
        """获取追踪汇总统计"""
        conn = self._get_connection()
        df = pd.read_sql_query('''
            SELECT 
                screen_id,
                COUNT(*) as total_trades,
                SUM(CASE WHEN status = '持有' THEN 1 ELSE 0 END) as active_positions,
                SUM(CASE WHEN status = '已平仓' THEN 1 ELSE 0 END) as closed_positions,
                SUM(CASE WHEN status = '已平仓' AND realized_pnl > 0 THEN 1 ELSE 0 END) as win_count,
                AVG(CASE WHEN status = '已平仓' THEN realized_pnl_pct END) as avg_return_pct,
                SUM(CASE WHEN status = '已平仓' THEN realized_pnl END) as total_realized_pnl
            FROM strategy_tracking
            GROUP BY screen_id
            ORDER BY screen_id DESC
        ''', conn)
        conn.close()
        return df
    
    # ========== 回测记录 ==========
    
    def save_backtest(self, backtest_result: Dict) -> int:
        """保存回测结果"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO backtest_records 
            (strategy_name, config_json, start_date, end_date, initial_cash,
             final_value, total_return_pct, annual_return_pct, max_drawdown_pct,
             sharpe_ratio, trade_count, win_rate, report_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            backtest_result.get('strategy_name', ''),
            json.dumps(backtest_result.get('config', {}), ensure_ascii=False),
            backtest_result.get('start_date'),
            backtest_result.get('end_date'),
            backtest_result.get('initial_cash', 0),
            backtest_result.get('final_value', 0),
            backtest_result.get('total_return_pct', 0),
            backtest_result.get('annual_return_pct', 0),
            backtest_result.get('max_drawdown_pct', 0),
            backtest_result.get('sharpe_ratio', 0),
            backtest_result.get('trade_count', 0),
            backtest_result.get('win_rate', 0),
            backtest_result.get('report_path', '')
        ))
        
        backtest_id = cursor.lastrowid
        
        # 保存交易记录
        for trade in backtest_result.get('trades', []):
            cursor.execute('''
                INSERT INTO backtest_trades
                (backtest_id, trade_date, stock_code, stock_name, action,
                 price, shares, amount, commission)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id,
                trade.get('date'),
                trade.get('stock_code'),
                trade.get('stock_name'),
                trade.get('action'),
                trade.get('price'),
                trade.get('shares'),
                trade.get('amount'),
                trade.get('commission')
            ))
        
        conn.commit()
        conn.close()
        
        return backtest_id
    
    def get_backtest_history(self, limit: int = 20) -> pd.DataFrame:
        """获取回测历史"""
        conn = self._get_connection()
        df = pd.read_sql_query('''
            SELECT * FROM backtest_records 
            ORDER BY backtest_time DESC 
            LIMIT ?
        ''', conn, params=(limit,))
        conn.close()
        return df


# 单例
db_instance: Optional[StockDatabase] = None


def get_db(db_path: str = "data/stock_screener.db") -> StockDatabase:
    """获取数据库单例"""
    global db_instance
    if db_instance is None:
        db_instance = StockDatabase(db_path)
    return db_instance
