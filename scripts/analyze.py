#!/usr/bin/env python3
"""
标准化分析脚本
使用 lib 模块进行股票分析

用法:
    python scripts/analyze.py 002050 603186 601138
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import StockScorer, DataFetcher, format_score, format_peg
from lib.utils import (
    save_score, get_price_targets, calculate_risk_reward,
    format_percent, format_amount
)


def analyze_single(code: str, scorer: StockScorer, fetcher: DataFetcher) -> dict:
    """
    分析单只股票

    Args:
        code: 股票代码
        scorer: 评分器
        fetcher: 数据获取器

    Returns:
        分析结果字典
    """
    print(f"\n正在分析 {code}...", file=sys.stderr)

    # 1. 获取数据
    data = fetcher.fetch_all(code)

    if not data['quote']:
        print(f"  ❌ 获取行情数据失败", file=sys.stderr)
        return None

    quote = data['quote']
    fundamentals = data['fundamentals']

    print(f"  ✓ 获取数据成功: {quote.name}", file=sys.stderr)

    # 2. 准备评分参数
    is_loss = quote.pe < 0

    # 计算复合PEG
    peg = None
    if not is_loss and len(data['quarterly_growth']) >= 2:
        peg = scorer.calculate_composite_peg(quote.pe, data['quarterly_growth'])

    # 获取基本面数据
    revenue_growth = 0
    profit_growth = 0
    gross_margin = None
    margin_trend = None

    if fundamentals:
        latest = fundamentals[0]
        revenue_growth = latest.revenue_growth
        profit_growth = latest.profit_growth
        gross_margin = latest.gross_margin

        # 计算毛利率趋势
        if len(fundamentals) >= 3:
            margins = [f.gross_margin for f in fundamentals[:3]]
            if margins[0] > margins[1] > margins[2]:
                margin_trend = 'up'
            elif margins[0] < margins[1] < margins[2]:
                margin_trend = 'down'
            else:
                margin_trend = 'stable'

    # 3. 计算评分
    score = scorer.score_stock(
        code=code,
        name=quote.name,
        price=quote.price,
        change_pct=quote.change_pct,
        pe=quote.pe,
        pb=quote.pb,
        high52=quote.high52,
        low52=quote.low52,
        turnover_rate=quote.turnover_rate,
        amount=quote.amount,
        gain_250d=data['gain_250d'],
        revenue_growth=revenue_growth,
        profit_growth=profit_growth,
        gross_margin=gross_margin,
        margin_trend=margin_trend,
        peg=peg,
        is_loss=is_loss
    )

    # 4. 计算价格目标
    targets = get_price_targets(
        quote.price, quote.high52, quote.low52, score.suggestion
    )

    risk_reward = calculate_risk_reward(
        quote.price,
        float(targets['stop_loss']),
        float(targets['target1']),
        float(targets['target2'])
    )

    # 5. 保存评分
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    save_score(
        code=code,
        name=quote.name,
        date=today,
        price=quote.price,
        scores={
            'trend': score.trend.score,
            'volume': score.volume.score,
            'pattern': score.pattern.score,
            'growth': score.growth.score,
            'valuation': score.valuation.score,
            'expectation': score.expectation.score,
            'analyst': score.analyst.score,
            'capital_flow': score.capital_flow.score,
            'event': score.event.score,
            'risk': score.risk.score
        },
        total=score.total_raw,
        pe=quote.pe,
        peg=peg,
        fcf_yield=score.fcf_yield
    )

    # 6. 返回结果
    return {
        'code': code,
        'name': quote.name,
        'price': quote.price,
        'change_pct': quote.change_pct,
        'pe': quote.pe,
        'pb': quote.pb,
        'high52': quote.high52,
        'low52': quote.low52,
        'turnover_rate': quote.turnover_rate,
        'amount': quote.amount,
        'score': score,
        'targets': targets,
        'risk_reward': risk_reward,
        'peg': peg,
        'revenue_growth': revenue_growth,
        'profit_growth': profit_growth,
        'fundamentals': fundamentals
    }


def format_score_detail(detail) -> str:
    """格式化单维度评分明细"""
    return f"{detail.score}/{detail.max_score}"


def print_report(result: dict):
    """打印完整分析报告（带推导链）"""
    score = result['score']
    targets = result['targets']
    risk_reward = result['risk_reward']

    print(f"\n{'═'*60}")
    print(f"  {result['name']}（{result['code']}）综合分析报告")
    print(f"  分析日期：2026-06-06")
    print(f"{'═'*60}")

    print(f"\n【行情数据】")
    print(f"  收盘价：{result['price']:.2f}  涨跌幅：{format_percent(result['change_pct'])}")
    print(f"  52周区间：{result['low52']:.2f} ~ {result['high52']:.2f}")
    print(f"  TTM PE：{result['pe']:.2f}  PB：{result['pb']:.2f}")
    print(f"  换手率：{result['turnover_rate']:.2f}%")

    print(f"\n【估值明细】")
    print(f"  TTM PE：{result['pe']:.2f}")
    print(f"  复合PEG：{format_peg(result['peg'])}")
    if result['revenue_growth'] != 0 or result['profit_growth'] != 0:
        print(f"  营收增速：{format_percent(result['revenue_growth'])}")
        print(f"  利润增速：{format_percent(result['profit_growth'])}")
    else:
        print(f"  营收增速：数据缺失")
        print(f"  利润增速：数据缺失")

    # 四维度评分表（带推导链）
    print(f"\n【四维度评分】")
    print(f"| 大类 | 维度 | 权重 | 观察 | 规则 | 评分 | 加权分 |")
    print(f"|------|------|------|------|------|------|--------|")

    # 价格维度 30%
    print(f"| 价格 | 趋势结构 | 10% | {score.trend.observation[:30]}... | {score.trend.rule[:20]}... | {format_score_detail(score.trend)} | {score.trend.weighted:.2f} |")
    print(f"| 30% | 量价关系 | 10% | {score.volume.observation[:30]}... | {score.volume.rule[:20]}... | {format_score_detail(score.volume)} | {score.volume.weighted:.2f} |")
    print(f"| | 价格形态 | 10% | {score.pattern.observation[:30]}... | {score.pattern.rule[:20]}... | {format_score_detail(score.pattern)} | {score.pattern.weighted:.2f} |")

    # 基本面 35%
    print(f"| 基本面 | 增长质量 | 12% | {score.growth.observation[:30]}... | {score.growth.rule[:20]}... | {format_score_detail(score.growth)} | {score.growth.weighted:.2f} |")
    print(f"| 35% | 估值合理性 | 12% | {score.valuation.observation[:30]}... | {score.valuation.rule[:20]}... | {format_score_detail(score.valuation)} | {score.valuation.weighted:.2f} |")
    print(f"| | 预期差 | 11% | {score.expectation.observation[:30]}... | {score.expectation.rule[:20]}... | {format_score_detail(score.expectation)} | {score.expectation.weighted:.2f} |")

    # 情绪面 20%
    print(f"| 情绪 | 分析师动向 | 8% | {score.analyst.observation[:30]}... | {score.analyst.rule[:20]}... | {format_score_detail(score.analyst)} | {score.analyst.weighted:.2f} |")
    print(f"| 20% | 资金流向 | 7% | {score.capital_flow.observation[:30]}... | {score.capital_flow.rule[:20]}... | {format_score_detail(score.capital_flow)} | {score.capital_flow.weighted:.2f} |")
    print(f"| | 事件驱动 | 5% | {score.event.observation[:30]}... | {score.event.rule[:20]}... | {format_score_detail(score.event)} | {score.event.weighted:.2f} |")

    # 风险 15%
    print(f"| 风险 | 风险因子 | 15% | {score.risk.observation[:30]}... | {score.risk.rule[:20]}... | {format_score_detail(score.risk)} | {score.risk.weighted:.2f} |")
    print(f"| 15% | | | | | | |")
    print(f"| **合计** | | **100%** | | | | **{score.total_raw:.2f}/115** |")

    print(f"\n**综合评分：{format_score(score.total_raw)}**")

    # 详细的推导链展示
    print(f"\n【评分推导详情】")
    print(f"  趋势结构  {format_score_detail(score.trend)}")
    print(f"    观察：{score.trend.observation}")
    print(f"    规则：{score.trend.rule}")
    print(f"    评分：{score.trend.score}")

    print(f"\n  量价关系  {format_score_detail(score.volume)}")
    print(f"    观察：{score.volume.observation}")
    print(f"    规则：{score.volume.rule}")
    print(f"    评分：{score.volume.score}")

    print(f"\n  价格形态  {format_score_detail(score.pattern)}")
    print(f"    观察：{score.pattern.observation}")
    print(f"    规则：{score.pattern.rule}")
    print(f"    评分：{score.pattern.score}")

    print(f"\n  增长质量  {format_score_detail(score.growth)}")
    print(f"    观察：{score.growth.observation}")
    print(f"    规则：{score.growth.rule}")
    print(f"    评分：{score.growth.score}")

    print(f"\n  估值合理性  {format_score_detail(score.valuation)}")
    print(f"    观察：{score.valuation.observation}")
    print(f"    规则：{score.valuation.rule}")
    print(f"    评分：{score.valuation.score}")

    print(f"\n  预期差  {format_score_detail(score.expectation)}")
    print(f"    观察：{score.expectation.observation}")
    print(f"    规则：{score.expectation.rule}")
    print(f"    评分：{score.expectation.score}")

    print(f"\n  分析师动向  {format_score_detail(score.analyst)}")
    print(f"    观察：{score.analyst.observation}")
    print(f"    规则：{score.analyst.rule}")
    print(f"    评分：{score.analyst.score}")

    print(f"\n  资金流向  {format_score_detail(score.capital_flow)}")
    print(f"    观察：{score.capital_flow.observation}")
    print(f"    规则：{score.capital_flow.rule}")
    print(f"    评分：{score.capital_flow.score}")

    print(f"\n  事件驱动  {format_score_detail(score.event)}")
    print(f"    观察：{score.event.observation}")
    print(f"    规则：{score.event.rule}")
    print(f"    评分：{score.event.score}")

    print(f"\n  风险因子  {format_score_detail(score.risk)}")
    print(f"    观察：{score.risk.observation}")
    print(f"    规则：{score.risk.rule}")
    print(f"    评分：{score.risk.score}")

    print(f"\n【操作结论】")
    print(f"  判断：{score.suggestion}")
    print(f"  买入区间：{targets['buy_range']}")
    print(f"  止损位：{targets['stop_loss']}")
    print(f"  目标位1：{targets['target1']}")
    print(f"  目标位2：{targets['target2']}")
    print(f"  盈亏比：{risk_reward['ratio1']}（目标1）/ {risk_reward['ratio2']}（目标2）")

    print(f"\n  ⚠️ 当前为空仓视角分析（未提供持仓信息）")
    print(f"\n{'═'*60}")
    print(f"  以上为纯技术分析观点，不构成投资建议。")
    print(f"{'═'*60}")


def print_ranking(results: list):
    """打印排名表"""
    # 按评分排序
    sorted_results = sorted(results, key=lambda x: x['score'].total_normalized, reverse=True)

    print(f"\n{'═'*60}")
    print(f"  综合排名")
    print(f"{'═'*60}")
    print(f"\n| 排名 | 标的 | 代码 | 综合分 | TTM PE | 复合PEG | 建议 | 核心逻辑 |")
    print(f"|------|------|------|--------|--------|---------|------|----------|")

    for i, r in enumerate(sorted_results, 1):
        pe_str = f"{r['pe']:.1f}" if r['pe'] > 0 else "亏损"
        peg_str = format_peg(r['peg'])

        # 核心逻辑
        if r['peg'] and r['peg'] < 1:
            logic = f"PEG优秀({r['peg']:.2f})+增长稳健"
        elif r['revenue_growth'] > 30:
            logic = f"营收高增({r['revenue_growth']:.0f}%)+业绩爆发"
        elif r['pe'] < 0:
            logic = "亏损状态+风险较高"
        elif r['revenue_growth'] < 0:
            logic = "营收下滑+趋势转弱"
        else:
            logic = "估值合理+增长平稳"

        print(f"| {i} | {r['name']} | {r['code']} | {r['score'].total_normalized:.0f}/100 | {pe_str} | {peg_str} | {r['score'].suggestion} | {logic} |")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/analyze.py <代码1> <代码2> ...")
        print("示例: python scripts/analyze.py 002050 603186 601138")
        sys.exit(1)

    codes = sys.argv[1:]

    print(f"开始分析 {len(codes)} 只标的...", file=sys.stderr)

    # 初始化
    scorer = StockScorer()
    fetcher = DataFetcher()

    # 分析所有标的
    results = []
    for code in codes:
        result = analyze_single(code, scorer, fetcher)
        if result:
            results.append(result)

    # 打印排名
    if results:
        print_ranking(results)

        # 打印详细报告
        print("\n" + "═"*60)
        print("  详细分析报告")
        print("═"*60)

        for result in results:
            print_report(result)

    print(f"\n{'═'*60}")
    print(f"  分析完成，评分数据已保存到 data/scores/")
    print(f"{'═'*60}")


if __name__ == "__main__":
    main()
