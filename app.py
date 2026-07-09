"""
选股小工具 - Streamlit Web 界面
================================
提供可视化选股、历史记录查询、回测分析等功能。

运行方式:
    cd D:/选股平台/stock_screener
    streamlit run app.py
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np

# ------------------------------------------------------------------
# 确保 core 模块在路径中
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)

# ------------------------------------------------------------------
# Streamlit 与绘图库
# ------------------------------------------------------------------
import streamlit as st

# 设置页面（必须在任何 st 命令之前）
st.set_page_config(
    page_title="选股小工具",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 尝试导入绘图库
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except Exception:
    HAS_MATPLOTLIB = False

try:
    import seaborn as sns
    HAS_SEABORN = True
except Exception:
    HAS_SEABORN = False

# ------------------------------------------------------------------
# 导入项目核心模块
# ------------------------------------------------------------------
try:
    from core import (
        ScreenConfig,
        StockScreener,
        ALL_PRESETS,
        get_db,
        BacktestConfig,
        BacktestEngine,
        SimpleBacktest,
        generate_screen_summary,
    )
    from core.data_source import get_data_source
    CORE_AVAILABLE = True
except Exception as e:
    CORE_AVAILABLE = False
    CORE_ERROR = str(e)

# ------------------------------------------------------------------
# 常量与工具函数
# ------------------------------------------------------------------
VERSION = "1.0.0"

STRATEGY_OPTIONS = [
    "自定义",
    "价值精选",
    "成长猎手",
    "低估蓝筹",
    "小盘成长",
    "趋势突破",
    "超跌反弹",
    "均线多头",
    "MACD零轴金叉",
    "布林带收口",
]

DATA_SOURCE_OPTIONS = ["iFinD", "AkShare", "stock_finance_data"]


def init_session_state():
    """初始化 Streamlit Session State"""
    defaults = {
        "screen_results": None,
        "screen_config": None,
        "screen_time": None,
        "strategy_name": "自定义",
        "data_source": "AkShare",
        "backtest_result": None,
        "last_export_path": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def fmt_number(x, prec=2):
    """格式化数字显示"""
    if pd.isna(x) or x is None:
        return "N/A"
    if abs(x) >= 1e8:
        return f"{x/1e8:.{prec}f}亿"
    if abs(x) >= 1e4:
        return f"{x/1e4:.{prec}f}万"
    return f"{x:.{prec}f}"


def build_config_from_ui(strategy_name: str, params: dict) -> ScreenConfig:
    """根据 UI 参数构建 ScreenConfig"""
    if strategy_name in ALL_PRESETS:
        base = ALL_PRESETS[strategy_name]
        # 深拷贝避免修改全局预设
        import copy
        config = copy.deepcopy(base)
    else:
        config = ScreenConfig()

    # 基本面参数覆盖
    config.pe_min = params.get("pe_min")
    config.pe_max = params.get("pe_max")
    config.pb_min = params.get("pb_min")
    config.pb_max = params.get("pb_max")
    config.total_mv_min = params.get("mv_min")
    config.total_mv_max = params.get("mv_max")
    config.exclude_st = params.get("exclude_st", True)
    config.exclude_bj = params.get("exclude_bj", True)
    config.exclude_kc = params.get("exclude_kc", False)
    config.exclude_cy = params.get("exclude_cy", False)
    config.max_results = params.get("max_results", 50)
    config.sort_by = params.get("sort_by", "score")

    # 技术指标
    config.use_technical_filter = params.get("use_tech", False)
    config.ma_bullish_alignment = params.get("ma_bullish", False)
    config.macd_golden_cross = params.get("macd_golden", False)
    config.macd_above_zero = params.get("macd_above_zero", False)
    config.kdj_golden_cross = params.get("kdj_golden", False)
    config.boll_break_lower = params.get("boll_lower", False)
    config.boll_band_width_max = params.get("boll_width_max")
    config.rsi_below = params.get("rsi_below")
    config.min_tech_signals = params.get("min_tech_signals", 1)
    config.tech_lookback_days = params.get("tech_lookback", 90)

    # 均线金叉
    ma_cross = params.get("ma_golden_cross")
    if ma_cross and ma_cross != "无":
        pair = tuple(int(x) for x in ma_cross.split(","))
        config.ma_golden_cross = pair
    else:
        config.ma_golden_cross = None

    # 成交量
    vol_surge = params.get("volume_surge")
    config.volume_surge_ratio = vol_surge if vol_surge and vol_surge > 0 else None

    return config


def run_screening(config: ScreenConfig, data_source_name: str):
    """执行选股"""
    # 切换数据源
    try:
        ds = get_data_source(preferred=data_source_name.lower())
        if hasattr(ds, "set_source"):
            ds.set_source(data_source_name.lower())
    except Exception:
        pass

    screener = StockScreener(config)
    with st.spinner("正在执行选股，请稍候..."):
        results = screener.screen(verbose=False)

    # 保存到数据库
    try:
        db = get_db()
        db.save_screen_result(screener)
    except Exception:
        pass

    return screener, results


def render_stat_cards(df: pd.DataFrame):
    """渲染统计卡片"""
    if df.empty:
        st.info("暂无选股结果")
        return

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("📊 选中数量", f"{len(df)} 只")
    with col2:
        avg_pe = df["pe"].mean() if "pe" in df.columns else 0
        st.metric("📈 平均 PE", f"{avg_pe:.2f}")
    with col3:
        avg_pb = df["pb"].mean() if "pb" in df.columns else 0
        st.metric("📉 平均 PB", f"{avg_pb:.2f}")
    with col4:
        avg_score = df["score"].mean() if "score" in df.columns else 0
        st.metric("⭐ 平均评分", f"{avg_score:.1f}")
    with col5:
        if "total_mv" in df.columns:
            avg_mv = df["total_mv"].mean() / 1e8
            st.metric("💰 平均市值", f"{avg_mv:.1f} 亿")
        else:
            st.metric("💰 平均市值", "N/A")


def render_signal_chart(df: pd.DataFrame):
    """渲染技术信号分布图"""
    if df.empty or "tech_signals" not in df.columns or df["tech_signals"].isna().all():
        st.info("暂无技术信号数据")
        return

    # 统计各信号出现次数
    all_signals = []
    for sig_str in df["tech_signals"].dropna():
        if sig_str:
            all_signals.extend([s.strip() for s in sig_str.split("|")])

    if not all_signals:
        st.info("暂无技术信号数据")
        return

    sig_counts = pd.Series(all_signals).value_counts().reset_index()
    sig_counts.columns = ["信号", "次数"]

    st.subheader("📡 技术信号分布")
    st.bar_chart(sig_counts.set_index("信号"), use_container_width=True)


def export_excel(screener: StockScreener) -> str:
    """导出选股结果到 Excel"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "技术" if screener.config.use_technical_filter else "基本面"
    filepath = PROJECT_ROOT / "reports" / f"选股结果_{mode}_{timestamp}.xlsx"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    return screener.export_to_excel(str(filepath))


# ------------------------------------------------------------------
# 页面渲染
# ------------------------------------------------------------------
def render_sidebar():
    """渲染侧边栏配置面板"""
    with st.sidebar:
        st.title("⚙️ 选股配置")

        # 策略选择
        strategy = st.selectbox(
            "选择策略",
            options=STRATEGY_OPTIONS,
            index=0,
            help="选择预设策略或自定义参数",
        )
        st.session_state.strategy_name = strategy

        st.divider()

        # 数据源
        data_source = st.radio(
            "数据源",
            options=DATA_SOURCE_OPTIONS,
            index=0,
            help="AkShare 为本地免费数据源；stock_finance_data 需 Daimon 环境",
        )
        st.session_state.data_source = data_source

        st.divider()

        # 基本面参数
        st.subheader("📊 基本面参数")

        col_pe1, col_pe2 = st.columns(2)
        with col_pe1:
            pe_min = st.number_input("PE 最小", value=0.0, step=1.0, key="pe_min")
        with col_pe2:
            pe_max = st.number_input("PE 最大", value=100.0, step=1.0, key="pe_max")

        col_pb1, col_pb2 = st.columns(2)
        with col_pb1:
            pb_min = st.number_input("PB 最小", value=0.0, step=0.1, key="pb_min")
        with col_pb2:
            pb_max = st.number_input("PB 最大", value=10.0, step=0.1, key="pb_max")

        col_mv1, col_mv2 = st.columns(2)
        with col_mv1:
            mv_min = st.number_input("市值最小(亿)", value=10.0, step=10.0, key="mv_min")
        with col_mv2:
            mv_max = st.number_input("市值最大(亿)", value=5000.0, step=100.0, key="mv_max")

        exclude_st = st.checkbox("排除 ST 股票", value=True, key="exclude_st")
        exclude_bj = st.checkbox("排除北交所", value=True, key="exclude_bj")
        exclude_kc = st.checkbox("排除科创板", value=False, key="exclude_kc")
        exclude_cy = st.checkbox("排除创业板", value=False, key="exclude_cy")

        max_results = st.slider("最大结果数", 10, 200, 50, 10, key="max_results")
        sort_by = st.selectbox(
            "排序方式",
            options=["score", "pe_asc", "pb_asc", "mv_asc"],
            format_func=lambda x: {
                "score": "综合评分",
                "pe_asc": "PE 由低到高",
                "pb_asc": "PB 由低到高",
                "mv_asc": "市值由小到大",
            }.get(x, x),
            key="sort_by",
        )

        st.divider()

        # 技术指标开关
        st.subheader("📉 技术指标")
        use_tech = st.toggle("启用技术指标筛选", value=False, key="use_tech")

        if use_tech:
            ma_bullish = st.checkbox("均线多头排列", value=False, key="ma_bullish")
            ma_golden = st.selectbox(
                "均线金叉",
                options=["无", "5,10", "5,20", "10,20", "10,60"],
                key="ma_golden_cross",
            )
            macd_golden = st.checkbox("MACD 金叉", value=False, key="macd_golden")
            macd_above_zero = st.checkbox("MACD 零轴上方", value=False, key="macd_above_zero")
            kdj_golden = st.checkbox("KDJ 金叉", value=False, key="kdj_golden")
            boll_lower = st.checkbox("跌破布林下轨", value=False, key="boll_lower")
            boll_width_max = st.number_input(
                "布林带带宽上限(如收口)",
                value=0.0,
                step=0.01,
                format="%.3f",
                key="boll_width_max",
            )
            rsi_below = st.number_input("RSI 低于(超卖)", value=0.0, step=1.0, key="rsi_below")
            volume_surge = st.number_input("放量倍数(>N倍均量)", value=0.0, step=0.1, key="volume_surge")
            min_tech_signals = st.slider("最少满足信号数", 1, 5, 1, 1, key="min_tech_signals")
            tech_lookback = st.slider("技术指标回看天数", 30, 180, 90, 10, key="tech_lookback")
        else:
            ma_bullish = False
            ma_golden = "无"
            macd_golden = False
            macd_above_zero = False
            kdj_golden = False
            boll_lower = False
            boll_width_max = 0.0
            rsi_below = 0.0
            volume_surge = 0.0
            min_tech_signals = 1
            tech_lookback = 90

        st.divider()

        # 执行按钮
        run_clicked = st.button("🚀 执行选股", type="primary", use_container_width=True)

        return {
            "strategy": strategy,
            "data_source": data_source,
            "pe_min": pe_min if pe_min > 0 else None,
            "pe_max": pe_max if pe_max > 0 else None,
            "pb_min": pb_min if pb_min > 0 else None,
            "pb_max": pb_max if pb_max > 0 else None,
            "mv_min": mv_min if mv_min > 0 else None,
            "mv_max": mv_max if mv_max > 0 else None,
            "exclude_st": exclude_st,
            "exclude_bj": exclude_bj,
            "exclude_kc": exclude_kc,
            "exclude_cy": exclude_cy,
            "max_results": max_results,
            "sort_by": sort_by,
            "use_tech": use_tech,
            "ma_bullish": ma_bullish,
            "ma_golden_cross": ma_golden,
            "macd_golden": macd_golden,
            "macd_above_zero": macd_above_zero,
            "kdj_golden": kdj_golden,
            "boll_lower": boll_lower,
            "boll_width_max": boll_width_max if boll_width_max > 0 else None,
            "rsi_below": rsi_below if rsi_below > 0 else None,
            "volume_surge": volume_surge if volume_surge > 0 else None,
            "min_tech_signals": min_tech_signals,
            "tech_lookback": tech_lookback,
            "run_clicked": run_clicked,
        }


def render_main_screen(params: dict):
    """渲染主区域 - 选股结果"""
    st.title("📈 选股小工具")
    st.caption(f"版本 {VERSION}  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # 执行选股
    if params["run_clicked"]:
        config = build_config_from_ui(params["strategy"], params)
        st.session_state.screen_config = config

        if not CORE_AVAILABLE:
            st.error(f"核心模块加载失败: {CORE_ERROR}")
            return

        try:
            screener, results = run_screening(config, params["data_source"])
            st.session_state.screen_results = results
            st.session_state.screen_time = datetime.now()
            st.session_state.screener_instance = screener
            st.success(f"✅ 选股完成！共筛选出 {len(results)} 只股票")
        except Exception as e:
            st.error(f"选股执行失败: {e}")
            return

    # 展示结果
    results = st.session_state.get("screen_results")
    screener = st.session_state.get("screener_instance")

    if results is not None and not results.empty:
        # 统计卡片
        render_stat_cards(results)
        st.divider()

        # 结果表格
        st.subheader("📋 选股结果")

        display_df = results.copy()
        # 市值转为亿元显示
        for col in ["total_mv", "circ_mv"]:
            if col in display_df.columns:
                display_df[col] = (display_df[col] / 1e8).round(2)

        # 列名中文映射
        rename_map = {
            "排名": "排名",
            "stock_code": "股票代码",
            "stock_name": "股票名称",
            "close": "最新价",
            "pct_change": "涨跌幅%",
            "pe": "市盈率PE",
            "pb": "市净率PB",
            "total_mv": "总市值(亿)",
            "circ_mv": "流通市值(亿)",
            "turnover": "换手率%",
            "score": "综合评分",
            "综合评级": "评级",
            "tech_signal_count": "技术信号数",
            "tech_signals": "技术信号",
        }
        display_df = display_df.rename(
            columns={k: v for k, v in rename_map.items() if k in display_df.columns}
        )

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # 导出按钮
        col_exp1, col_exp2 = st.columns([1, 4])
        with col_exp1:
            if st.button("📥 导出 Excel", use_container_width=True):
                if screener is not None:
                    try:
                        export_path = export_excel(screener)
                        st.session_state.last_export_path = export_path
                        st.success(f"已导出: {export_path}")
                    except Exception as e:
                        st.error(f"导出失败: {e}")

        st.divider()

        # 技术信号分布
        render_signal_chart(results)

    elif results is not None and results.empty:
        st.warning("⚠️ 当前条件未筛选出任何股票，请放宽条件后重试。")
    else:
        st.info("👈 请在左侧配置面板设置参数并点击「执行选股」")


def render_history_tab():
    """渲染历史记录页面"""
    st.header("📜 选股历史")

    if not CORE_AVAILABLE:
        st.error("核心模块不可用，无法加载历史记录")
        return

    tab1, tab2 = st.tabs(["选股历史", "持仓追踪"])

    with tab1:
        try:
            db = get_db()
            history = db.get_screen_history(limit=50)

            if history.empty:
                st.info("暂无选股历史记录")
            else:
                history["screen_time"] = pd.to_datetime(history["screen_time"])
                history = history.sort_values("screen_time", ascending=False)

                st.dataframe(
                    history[["id", "screen_time", "strategy_name", "stock_count"]],
                    use_container_width=True,
                    hide_index=True,
                )

                # 查看详情
                selected_id = st.number_input(
                    "输入记录 ID 查看详情", min_value=0, step=1, value=0
                )
                if selected_id > 0 and st.button("查看详情"):
                    detail = db.get_screen_detail(selected_id)
                    if not detail.empty:
                        st.dataframe(detail, use_container_width=True, hide_index=True)
                    else:
                        st.warning("未找到该记录")
        except Exception as e:
            st.error(f"加载历史记录失败: {e}")

    with tab2:
        try:
            db = get_db()
            active = db.get_active_trackings()

            if active.empty:
                st.info("当前无持仓追踪记录")
            else:
                st.subheader("当前持仓")
                st.dataframe(active, use_container_width=True, hide_index=True)

            summary = db.get_tracking_summary()
            if not summary.empty:
                st.subheader("追踪汇总")
                st.dataframe(summary, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"加载持仓追踪失败: {e}")


def render_backtest_tab():
    """渲染回测页面"""
    st.header("🔬 策略回测")

    if not CORE_AVAILABLE:
        st.error("核心模块不可用，无法运行回测")
        return

    with st.form("backtest_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            bt_strategy = st.selectbox("回测策略", STRATEGY_OPTIONS[:5], index=0)
        with col2:
            start_date = st.date_input(
                "开始日期",
                value=datetime.now() - timedelta(days=365),
                max_value=datetime.now(),
            )
        with col3:
            end_date = st.date_input(
                "结束日期",
                value=datetime.now(),
                max_value=datetime.now(),
            )

        col4, col5, col6 = st.columns(3)
        with col4:
            initial_cash = st.number_input("初始资金(万元)", value=100.0, step=10.0)
        with col5:
            max_position = st.number_input("单票仓位上限(%)", value=20.0, step=5.0)
        with col6:
            rebalance = st.selectbox("调仓频率", ["monthly", "weekly"], index=0)

        submitted = st.form_submit_button("▶️ 运行回测", use_container_width=True)

    if submitted:
        if start_date >= end_date:
            st.error("开始日期必须早于结束日期")
            return

        # 使用已有的选股结果或快速执行一次选股作为持仓标的
        screener = st.session_state.get("screener_instance")
        if screener is None or st.session_state.screen_results is None:
            st.warning("请先执行一次选股，或选择预设策略生成标的池")
            return

        with st.spinner("回测运行中..."):
            try:
                bt_config = BacktestConfig(
                    initial_cash=initial_cash,
                    max_position_pct=max_position,
                )
                engine = BacktestEngine(bt_config)

                result = engine.run_screen_backtest(
                    screen_config=screener.config,
                    start_date=start_date.strftime("%Y-%m-%d"),
                    end_date=end_date.strftime("%Y-%m-%d"),
                    rebalance_freq=rebalance,
                    strategy_name=bt_strategy,
                )
                st.session_state.backtest_result = result
            except Exception as e:
                st.error(f"回测执行失败: {e}")
                return

    # 展示回测结果
    result = st.session_state.get("backtest_result")
    if result is not None:
        st.divider()
        st.subheader("📊 回测结果")

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("总收益率", f"{result.total_return_pct:+.2f}%")
        with c2:
            st.metric("年化收益率", f"{result.annual_return_pct:+.2f}%")
        with c3:
            st.metric("最大回撤", f"{result.max_drawdown_pct:.2f}%")
        with c4:
            st.metric("夏普比率", f"{result.sharpe_ratio:.2f}")
        with c5:
            st.metric("交易次数", f"{result.trade_count}")

        if not result.equity_curve.empty:
            st.subheader("📈 权益曲线")
            st.line_chart(
                result.equity_curve.set_index("date")[["total_value", "return_pct"]],
                use_container_width=True,
            )

        if result.trades:
            st.subheader("📝 交易记录")
            trades_df = pd.DataFrame(result.trades)
            st.dataframe(trades_df, use_container_width=True, hide_index=True)


# ------------------------------------------------------------------
# 主入口
# ------------------------------------------------------------------
def main():
    init_session_state()

    if not CORE_AVAILABLE:
        st.error(f"⚠️ 核心模块加载失败，请检查项目结构:\n`{CORE_ERROR}`")
        st.stop()

    params = render_sidebar()

    tab_screen, tab_history, tab_backtest = st.tabs(
        ["🎯 选股结果", "📜 历史记录", "🔬 回测分析"]
    )

    with tab_screen:
        render_main_screen(params)

    with tab_history:
        render_history_tab()

    with tab_backtest:
        render_backtest_tab()


if __name__ == "__main__":
    main()
