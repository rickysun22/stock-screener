"""
iFinD SDK 使用示例
═══════════════════════════════════════════════════════════════
运行前请确保已安装 iFinD SDK 或 AkShare
"""

from core import iFinDClient


def example_1_basic():
    """示例1: 基础用法 - 自动检测模式"""
    print("=" * 60)
    print("示例1: 基础用法")
    print("=" * 60)
    
    client = iFinDClient()
    print(f"\n当前模式: {client.mode}")
    print(f"适配器: {client.adapter_name}\n")
    
    # 获取实时行情
    print("📊 获取实时行情 (000001.SZ 平安银行):")
    df = client.get_realtime("000001.SZ", data_type="close_summary")
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("(无数据)")


def example_2_price():
    """示例2: 获取历史价格"""
    print("\n" + "=" * 60)
    print("示例2: 历史价格")
    print("=" * 60)
    
    client = iFinDClient()
    
    print("\n📈 获取 600519.SH (贵州茅台) 近30天价格:")
    df = client.get_daily_kline("600519.SH", days=30)
    if not df.empty:
        cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        available = [c for c in cols if c in df.columns]
        print(df[available].tail(5).to_string(index=False))
    else:
        print("(无数据)")


def example_3_tech():
    """示例3: 技术指标"""
    print("\n" + "=" * 60)
    print("示例3: 技术指标")
    print("=" * 60)
    
    client = iFinDClient()
    
    print("\n📉 获取 000001.SZ 技术指标:")
    df = client.get_tech_indicators("000001.SZ")
    if not df.empty:
        tech_cols = ['ticker']
        for col in df.columns:
            if any(x in col for x in ['MA', 'MACD', 'KDJ', 'RSI', 'BOLL', 'DMI']):
                tech_cols.append(col)
        print(df[tech_cols[:8]].to_string(index=False))  # 只显示前8个指标列
    else:
        print("(当前模式不支持实时技术指标，回退到本地计算...)")
        # 使用 AkShare 回退获取K线并计算
        df_kline = client.get_daily_kline("000001.SZ", days=60)
        if not df_kline.empty:
            from core import calculate_all_indicators
            df = calculate_all_indicators(df_kline)
            print(df[['date', 'close', 'MA5', 'MA20', 'MACD_DIF', 'KDJ_K', 'RSI14']].tail(5).to_string(index=False))


def example_4_financial():
    """示例4: 财务指标"""
    print("\n" + "=" * 60)
    print("示例4: 财务指标")
    print("=" * 60)
    
    client = iFinDClient()
    
    print("\n💰 获取 000001.SZ 盈利能力指标:")
    df = client.get_financial_index("000001.SZ", category="profitability")
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("(当前模式不支持财务指标，建议安装 iFinD SDK)")


def example_5_batch():
    """示例5: 批量获取"""
    print("\n" + "=" * 60)
    print("示例5: 批量获取")
    print("=" * 60)
    
    client = iFinDClient()
    
    codes = ["000001.SZ", "600519.SH", "000858.SZ"]
    print(f"\n📦 批量获取 {len(codes)} 只股票实时行情:")
    
    df = client.get_realtime(codes, data_type="close_summary")
    if not df.empty:
        cols = ['ticker', 'name', 'close', 'pct_chg']
        available = [c for c in cols if c in df.columns]
        print(df[available].to_string(index=False))
    else:
        print("(无数据)")


def example_6_full_financial():
    """示例6: 获取全部财务维度"""
    print("\n" + "=" * 60)
    print("示例6: 全部财务维度")
    print("=" * 60)
    
    client = iFinDClient()
    
    print("\n📊 获取 000001.SZ 全部6大财务维度:")
    results = client.get_all_financial_dimensions("000001.SZ")
    
    if results:
        for category, df in results.items():
            print(f"\n  📌 {category}: {len(df)} 条指标")
            if not df.empty:
                # 显示前几列
                display_cols = list(df.columns)[:5]
                print(f"     指标: {', '.join(display_cols)}...")
    else:
        print("(当前模式不支持完整财务数据)")


def main():
    """运行所有示例"""
    print("\n" + "🚀" * 30)
    print("  iFinD SDK 使用示例")
    print("🚀" * 30 + "\n")
    
    try:
        example_1_basic()
    except Exception as e:
        print(f"[示例1失败] {e}")
    
    try:
        example_2_price()
    except Exception as e:
        print(f"[示例2失败] {e}")
    
    try:
        example_3_tech()
    except Exception as e:
        print(f"[示例3失败] {e}")
    
    try:
        example_4_financial()
    except Exception as e:
        print(f"[示例4失败] {e}")
    
    try:
        example_5_batch()
    except Exception as e:
        print(f"[示例5失败] {e}")
    
    try:
        example_6_full_financial()
    except Exception as e:
        print(f"[示例6失败] {e}")
    
    print("\n" + "=" * 60)
    print("✅ 示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
