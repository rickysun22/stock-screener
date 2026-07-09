"""
选股小工具 - 主入口 v2.0

Usage:
    python main.py --screen                              # 执行基本面选股
    python main.py --screen --strategy 价值精选          # 使用预设策略
    python main.py --tech-screen --strategy 趋势突破     # 执行技术指标选股
    python main.py --track                               # 查看持仓追踪
    python main.py --backtest                            # 执行回测
    python main.py --history                             # 查看选股历史
    streamlit run app.py                                 # 启动Web界面
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core import ScreenConfig, StockScreener, ALL_PRESETS, get_db
from core.backtest_engine import SimpleBacktest
from core.reporter import generate_screen_summary


def cmd_screen(args):
    """执行选股命令"""
    if args.strategy and args.strategy in ALL_PRESETS:
        config = ALL_PRESETS[args.strategy]
        print(f"📌 使用预设策略: {args.strategy}")
    else:
        config = ScreenConfig()
        if args.strategy:
            print(f"[警告] 未知策略 '{args.strategy}'，使用默认配置")
        else:
            print("📌 使用默认选股配置")
    
    # 应用命令行参数覆盖
    if args.pe_max is not None:
        config.pe_max = args.pe_max
    if args.pb_max is not None:
        config.pb_max = args.pb_max
    if args.roe_min is not None:
        config.roe_min = args.roe_min
    if args.mv_min is not None:
        config.total_mv_min = args.mv_min
    if args.mv_max is not None:
        config.total_mv_max = args.mv_max
    if args.max_results is not None:
        config.max_results = args.max_results
    
    # 技术指标模式
    if args.tech_screen or args.strategy in ['趋势突破', '超跌反弹', '均线多头', 'MACD零轴金叉', '布林带收口']:
        config.use_technical_filter = True
        print("📊 启用技术指标筛选")
    
    # 应用技术指标参数
    if args.tech_price_above_ma:
        config.price_above_ma = args.tech_price_above_ma
        config.use_technical_filter = True
    if args.tech_macd_golden:
        config.macd_golden_cross = True
        config.use_technical_filter = True
    if args.tech_rsi_below:
        config.rsi_below = args.tech_rsi_below
        config.use_technical_filter = True
    if args.tech_min_signals:
        config.min_tech_signals = args.tech_min_signals
    
    # 执行选股
    screener = StockScreener(config)
    results = screener.screen(verbose=True)
    
    if results.empty:
        print("\n❌ 未筛选出符合条件的股票")
        return
    
    # 保存到数据库
    db = get_db()
    screen_id = db.save_screen_result(screener)
    
    # 导出Excel
    if args.export:
        screener.export_to_excel()
    
    # 打印摘要
    print(generate_screen_summary(results, args.strategy or "选股结果"))
    
    # 简单回测
    if args.quick_backtest:
        print("\n📊 执行快速回测 (模拟持有20天)...")
        codes = results['stock_code'].head(10).tolist()
        bt = SimpleBacktest()
        bt_results = bt.simulate_hold_return(codes, hold_days=20)
        
        if not bt_results.empty:
            print(f"\n   平均收益: {bt_results['return_pct'].mean():+.2f}%")
            print(f"   最高收益: {bt_results['return_pct'].max():+.2f}%")
            print(f"   最低收益: {bt_results['return_pct'].min():+.2f}%")
            print(f"   胜率: {(bt_results['return_pct'] > 0).mean()*100:.1f}%")
    
    print(f"\n✅ 选股完成！记录ID: {screen_id}")


def cmd_track(args):
    """查看持仓追踪"""
    db = get_db()
    
    if args.screen_id:
        trackings = db.get_active_trackings(args.screen_id)
    else:
        trackings = db.get_active_trackings()
    
    if trackings.empty:
        print("\n📭 当前无持仓追踪记录")
        print("\n提示: 选股后使用 --add-track 添加追踪")
        return
    
    print(f"\n{'='*80}")
    print(f"📊 当前持仓追踪 ({len(trackings)} 只)")
    print(f"{'='*80}")
    
    for _, row in trackings.iterrows():
        print(f"\n  {row['stock_code']} {row['stock_name']}")
        print(f"    买入: {row['entry_date']} @ {row['entry_price']:.2f}")
        print(f"    当前: {row.get('current_price', 'N/A')} | 盈亏: {row.get('unrealized_pnl_pct', 0):+.2f}%")
        print(f"    状态: {row['status']} | 备注: {row.get('notes', '')}")
    
    summary = db.get_tracking_summary()
    if not summary.empty:
        print(f"\n{'='*80}")
        print("📈 策略追踪汇总")
        print(f"{'='*80}")
        print(summary.to_string(index=False))


def cmd_history(args):
    """查看选股历史"""
    db = get_db()
    history = db.get_screen_history(limit=args.limit)
    
    if history.empty:
        print("\n📭 暂无选股历史记录")
        return
    
    print(f"\n{'='*80}")
    print(f"📜 选股历史 (最近 {len(history)} 条)")
    print(f"{'='*80}")
    
    for _, row in history.iterrows():
        print(f"\n  ID: {row['id']} | {row['screen_time']}")
        print(f"  策略: {row.get('strategy_name', '默认')} | 选出 {row['stock_count']} 只股票")
        
        if args.detail:
            detail = db.get_screen_detail(row['id'])
            if not detail.empty:
                print(f"  股票列表:")
                for _, d in detail.head(5).iterrows():
                    print(f"    {d['rank']}. {d['stock_code']} {d['stock_name']} | 评分:{d['score']:.1f}")


def cmd_backtest(args):
    """执行回测"""
    print("\n[提示] 完整回测功能需要历史财务数据支持")
    
    db = get_db()
    history = db.get_screen_history(limit=1)
    
    if history.empty:
        print("\n[错误] 没有选股记录，请先执行选股")
        return
    
    screen_id = history.iloc[0]['id']
    detail = db.get_screen_detail(screen_id)
    
    if detail.empty:
        print("\n[错误] 选股记录为空")
        return
    
    codes = detail['stock_code'].tolist()
    print(f"\n📊 对最近选股结果 ({len(codes)} 只) 执行快速回测...")
    
    bt = SimpleBacktest()
    results = bt.simulate_hold_return(codes, hold_days=args.hold_days)
    
    if not results.empty:
        print(f"\n{'='*60}")
        print("📈 快速回测结果")
        print(f"{'='*60}")
        print(f"\n  持有天数: {args.hold_days}")
        print(f"  平均收益: {results['return_pct'].mean():+.2f}%")
        print(f"  收益中位数: {results['return_pct'].median():+.2f}%")
        print(f"  最高收益: {results['return_pct'].max():+.2f}%")
        print(f"  最低收益: {results['return_pct'].min():+.2f}%")
        print(f"  胜率: {(results['return_pct'] > 0).mean()*100:.1f}%")
        print(f"  平均最大回撤: {results['max_drawdown_pct'].mean():.2f}%")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results.to_csv(f"reports/快速回测_{timestamp}.csv", index=False, encoding='utf-8-sig')
        print(f"\n📁 详细结果已保存")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='选股小工具 v2.0 - 多因子选股 · 策略追踪 · 回测分析',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本面选股
  python main.py --screen
  python main.py --screen --strategy 价值精选
  python main.py --screen --pe-max 25 --pb-max 2

  # 技术指标选股
  python main.py --tech-screen --strategy 趋势突破
  python main.py --screen --tech-price-above-ma 20 --tech-macd-golden

  # 追踪与回测
  python main.py --track
  python main.py --history --detail
  python main.py --backtest --hold-days 30

  # Web界面
  streamlit run app.py
        """
    )
    
    # 命令选择
    parser.add_argument('--screen', action='store_true', help='执行基本面选股')
    parser.add_argument('--tech-screen', action='store_true', help='执行技术指标选股')
    parser.add_argument('--track', action='store_true', help='查看持仓追踪')
    parser.add_argument('--history', action='store_true', help='查看选股历史')
    parser.add_argument('--backtest', action='store_true', help='执行回测')
    
    # 策略选择
    all_strategies = list(ALL_PRESETS.keys())
    parser.add_argument('--strategy', type=str, choices=all_strategies,
                        help=f'策略名称: {", ".join(all_strategies)}')
    
    # 基本面参数
    parser.add_argument('--pe-max', type=float, help='最大市盈率')
    parser.add_argument('--pb-max', type=float, help='最大市净率')
    parser.add_argument('--roe-min', type=float, help='最小ROE')
    parser.add_argument('--mv-min', type=float, help='最小市值(亿元)')
    parser.add_argument('--mv-max', type=float, help='最大市值(亿元)')
    parser.add_argument('--max-results', type=int, help='最大结果数')
    
    # 技术指标参数
    parser.add_argument('--tech-price-above-ma', type=int, help='股价>N日均线')
    parser.add_argument('--tech-macd-golden', action='store_true', help='MACD金叉')
    parser.add_argument('--tech-rsi-below', type=float, help='RSI低于(超卖)')
    parser.add_argument('--tech-min-signals', type=int, default=1, help='最少技术信号数')
    
    # 其他选项
    parser.add_argument('--export', action='store_true', default=True, help='导出Excel')
    parser.add_argument('--quick-backtest', action='store_true', help='执行快速回测')
    parser.add_argument('--screen-id', type=int, help='指定选股记录ID')
    parser.add_argument('--limit', type=int, default=20, help='历史记录数量')
    parser.add_argument('--detail', action='store_true', help='显示详细信息')
    parser.add_argument('--hold-days', type=int, default=20, help='回测持有天数')
    
    args = parser.parse_args()
    
    # 创建必要目录
    Path("data").mkdir(exist_ok=True)
    Path("reports").mkdir(exist_ok=True)
    
    # 如果没有指定命令，默认执行选股
    if not any([args.screen, args.tech_screen, args.track, args.history, args.backtest]):
        args.screen = True
    
    # 技术指标模式
    if args.tech_screen:
        args.screen = True
    
    # 执行对应命令
    if args.screen or args.tech_screen:
        cmd_screen(args)
    elif args.track:
        cmd_track(args)
    elif args.history:
        cmd_history(args)
    elif args.backtest:
        cmd_backtest(args)


if __name__ == "__main__":
    main()
