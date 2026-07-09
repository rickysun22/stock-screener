"""
选股小工具 REST API 服务器
═══════════════════════════════════════
为前端 index.html 提供后端 API 支持，启用完整 iFinD 数据源能力。

运行方式:
    python api_server.py
    
默认端口: 8000
访问地址: http://localhost:8000

环境变量:
    KIMI_API_KEY - iFinD API Key (可选，回退到 AkShare)
"""

from __future__ import annotations

import os
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List

import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# 确保 core 在路径中
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

from core import (
    ScreenConfig,
    StockScreener,
    ALL_PRESETS,
    BacktestConfig,
    BacktestEngine,
    get_db,
)
from core.data_source import get_data_source

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)


# ───────────────────────────────────────────────
# 健康检查
# ───────────────────────────────────────────────

@app.route("/api/health")
def health():
    """健康检查"""
    ds = get_data_source()
    return jsonify({
        "status": "ok",
        "time": datetime.now().isoformat(),
        "data_source": ds.get_name(),
    })


# ───────────────────────────────────────────────
# 选股 API
# ───────────────────────────────────────────────

@app.route("/api/screen", methods=["POST"])
def screen_stocks():
    """
    POST /api/screen
    执行选股并返回结果

    Body JSON 示例:
    {
        "strategy": "价值精选",
        "pe_min": 0, "pe_max": 20,
        "pb_min": 0, "pb_max": 3,
        "mv_min": 50, "mv_max": 5000,
        "exclude_st": true,
        "exclude_bj": true,
        "max_results": 50,
        "sort_by": "score",
        "use_tech": false
    }
    """
    try:
        data = request.get_json() or {}
        
        # 构建配置
        strategy = data.get("strategy", "自定义")
        if strategy in ALL_PRESETS:
            import copy
            config = copy.deepcopy(ALL_PRESETS[strategy])
        else:
            config = ScreenConfig()
        
        # 覆盖参数
        config.pe_min = data.get("pe_min") if data.get("pe_min") is not None else config.pe_min
        config.pe_max = data.get("pe_max") if data.get("pe_max") is not None else config.pe_max
        config.pb_min = data.get("pb_min") if data.get("pb_min") is not None else config.pb_min
        config.pb_max = data.get("pb_max") if data.get("pb_max") is not None else config.pb_max
        config.total_mv_min = data.get("mv_min") if data.get("mv_min") is not None else config.total_mv_min
        config.total_mv_max = data.get("mv_max") if data.get("mv_max") is not None else config.total_mv_max
        config.exclude_st = data.get("exclude_st", True)
        config.exclude_bj = data.get("exclude_bj", True)
        config.exclude_kc = data.get("exclude_kc", False)
        config.exclude_cy = data.get("exclude_cy", False)
        config.max_results = data.get("max_results", 50)
        config.sort_by = data.get("sort_by", "score")
        config.use_technical_filter = data.get("use_tech", False)
        
        # 执行选股
        screener = StockScreener(config)
        results = screener.screen(verbose=False)
        
        # 保存到数据库
        try:
            db = get_db()
            db.save_screen_result(screener)
        except Exception:
            pass
        
        # 转换为 JSON
        if results.empty:
            return jsonify({"count": 0, "stocks": []})
        
        # 处理数值，确保可 JSON 序列化
        export_df = results.copy()
        for col in export_df.columns:
            if export_df[col].dtype in [np.int64, np.float64]:
                export_df[col] = export_df[col].replace([np.inf, -np.inf], np.nan)
                export_df[col] = export_df[col].where(export_df[col].notna(), None)
        
        stocks = export_df.to_dict(orient="records")
        
        return jsonify({
            "count": len(stocks),
            "stocks": stocks,
            "data_source": screener.ds.get_name(),
            "screen_time": datetime.now().isoformat(),
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────────────────────────
# 历史记录 API
# ───────────────────────────────────────────────

@app.route("/api/history")
def get_history():
    """GET /api/history?limit=20"""
    try:
        limit = request.args.get("limit", 20, type=int)
        db = get_db()
        history = db.get_screen_history(limit=limit)
        
        if history.empty:
            return jsonify({"count": 0, "records": []})
        
        history["screen_time"] = pd.to_datetime(history["screen_time"]).astype(str)
        records = history.to_dict(orient="records")
        
        return jsonify({"count": len(records), "records": records})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────────────────────────
# 回测 API
# ───────────────────────────────────────────────

@app.route("/api/backtest", methods=["POST"])
def run_backtest():
    """
    POST /api/backtest
    运行策略回测

    Body JSON:
    {
        "strategy": "价值精选",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_cash": 1000000,
        "max_position_pct": 20
    }
    """
    try:
        data = request.get_json() or {}
        
        strategy = data.get("strategy", "自定义")
        start_date = data.get("start_date", (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))
        end_date = data.get("end_date", datetime.now().strftime("%Y-%m-%d"))
        
        # 快速执行一次选股作为标的池
        if strategy in ALL_PRESETS:
            import copy
            config = copy.deepcopy(ALL_PRESETS[strategy])
        else:
            config = ScreenConfig()
        
        screener = StockScreener(config)
        results = screener.screen(verbose=False)
        
        if results.empty:
            return jsonify({"error": "选股结果为空，无法回测"}), 400
        
        # 运行回测
        bt_config = BacktestConfig(
            initial_cash=data.get("initial_cash", 1000000),
            max_position_pct=data.get("max_position_pct", 20),
        )
        engine = BacktestEngine(bt_config)
        
        result = engine.run_screen_backtest(
            screen_config=config,
            start_date=start_date,
            end_date=end_date,
            rebalance_freq="monthly",
            strategy_name=strategy,
        )
        
        return jsonify({
            "total_return_pct": result.total_return_pct,
            "annual_return_pct": result.annual_return_pct,
            "max_drawdown_pct": result.max_drawdown_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "trade_count": result.trade_count,
            "equity_curve": result.equity_curve.to_dict(orient="records") if not result.equity_curve.empty else [],
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────────────────────────
# 数据源状态 API
# ───────────────────────────────────────────────

@app.route("/api/datasource")
def get_datasource_status():
    """获取当前数据源状态"""
    try:
        ds = get_data_source()
        from core.ifind_sdk import iFinDClient
        
        try:
            client = iFinDClient(auto_detect=True)
            ifind_mode = client.mode
            ifind_adapter = client.adapter_name
        except Exception:
            ifind_mode = "unavailable"
            ifind_adapter = "unavailable"
        
        return jsonify({
            "active_source": ds.get_name(),
            "available_sources": ds.get_source_names(),
            "ifind_mode": ifind_mode,
            "ifind_adapter": ifind_adapter,
            "has_api_key": bool(os.environ.get("KIMI_API_KEY")),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ───────────────────────────────────────────────
# 前端页面
# ───────────────────────────────────────────────

@app.route("/")
def index():
    """返回前端页面"""
    return send_from_directory(".", "index.html")


# ───────────────────────────────────────────────
# 启动
# ───────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", "8000"))
    debug = os.environ.get("API_DEBUG", "false").lower() == "true"
    
    print(f"""
╔════════════════════════════════════════════════════════╗
║  选股小工具 API 服务器                                  ║
╠════════════════════════════════════════════════════════╣
║  文档:  http://localhost:{port}/api/health              ║
║  前端:  http://localhost:{port}/                        ║
║  API:   http://localhost:{port}/api/screen            ║
╚════════════════════════════════════════════════════════╝
    """)
    
    app.run(host="0.0.0.0", port=port, debug=debug)
