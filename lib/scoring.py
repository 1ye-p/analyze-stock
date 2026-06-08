"""
标准化评分计算模块
基于V2四维度框架：价格(30%) + 基本面(35%) + 情绪(20%) + 风险(15%)
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
import math


@dataclass
class ScoreDetail:
    """单维度评分详情"""
    name: str
    weight: float
    observation: str  # 观察
    rule: str         # 规则
    score: float      # 评分
    max_score: float  # 满分
    weighted: float   # 加权分


@dataclass
class StockScore:
    """股票综合评分"""
    code: str
    name: str
    price: float
    change_pct: float
    pe: float
    pb: float

    # 各维度评分
    trend: ScoreDetail      # 趋势结构 (10%)
    volume: ScoreDetail     # 量价关系 (10%)
    pattern: ScoreDetail    # 价格形态 (10%)
    growth: ScoreDetail     # 增长质量 (12%)
    valuation: ScoreDetail  # 估值合理性 (12%)
    expectation: ScoreDetail # 预期差 (11%)
    analyst: ScoreDetail    # 分析师动向 (8%)
    capital_flow: ScoreDetail # 资金流向 (7%)
    event: ScoreDetail      # 事件驱动 (5%)
    risk: ScoreDetail       # 风险因子 (15%)

    # 汇总
    total_raw: float        # 原始总分
    total_normalized: float # 归一化评分
    suggestion: str         # 操作建议

    # 估值明细
    ttm_pe: float
    dynamic_pe: float
    peg_composite: Optional[float]
    fcf_yield: Optional[float]


class StockScorer:
    """股票评分计算器"""

    # 权重配置
    WEIGHTS = {
        'trend': 0.10,
        'volume': 0.10,
        'pattern': 0.10,
        'growth': 0.12,
        'valuation': 0.12,
        'expectation': 0.11,
        'analyst': 0.08,
        'capital_flow': 0.07,
        'event': 0.05,
        'risk': 0.15
    }

    # 理论满分
    MAX_RAW_SCORE = 115.0

    def __init__(self):
        pass

    def calculate_trend_score(
        self,
        price: float,
        high52: float,
        low52: float,
        gain_250d: float,
        kline_data: List[Dict] = None
    ) -> ScoreDetail:
        """
        趋势结构评分 (10%, 满分16)

        Args:
            price: 当前价格
            high52: 52周最高
            low52: 52周最低
            gain_250d: 250日涨幅(%)
            kline_data: K线数据(可选，用于计算MACD)
        """
        score = 0
        observations = []
        rules = []

        # 1. 基础趋势评分
        price_from_high = (high52 - price) / high52 * 100

        if gain_250d > 100:
            base_score = 10
            observations.append(f"250日涨幅{gain_250d:.1f}%，强势上涨")
            rules.append("涨幅>100%→10")
        elif gain_250d > 50:
            base_score = 8
            observations.append(f"250日涨幅{gain_250d:.1f}%，趋势向上")
            rules.append("涨幅>50%→8")
        elif gain_250d > 20:
            base_score = 7
            observations.append(f"250日涨幅{gain_250d:.1f}%，温和上涨")
            rules.append("涨幅>20%→7")
        elif gain_250d > 0:
            base_score = 5
            observations.append(f"250日涨幅{gain_250d:.1f}%，横盘震荡")
            rules.append("涨幅>0%→5")
        else:
            base_score = 3
            observations.append(f"250日涨幅{gain_250d:.1f}%，下降趋势")
            rules.append("涨幅<0%→3")

        score = base_score

        # 2. 周线MACD金叉加分 (最高+3)
        macd_bonus = 0
        if gain_250d > 50:
            macd_bonus = 3
            observations.append("周线MACD强动量")
            rules.append("MACD强→+3")
        elif gain_250d > 20:
            macd_bonus = 2
            observations.append("周线MACD中等动量")
            rules.append("MACD中→+2")
        elif gain_250d > 10:
            macd_bonus = 1
            observations.append("周线MACD弱动量")
            rules.append("MACD弱→+1")

        score += macd_bonus

        # 3. 距52周高点
        if price_from_high < 10:
            observations.append(f"距52周高点{price_from_high:.1f}%，接近新高")
            rules.append("距高<10%→不减")
        elif price_from_high < 25:
            observations.append(f"距52周高点{price_from_high:.1f}%，正常回调")
            rules.append("回调10~25%→不减")
        else:
            observations.append(f"距52周高点{price_from_high:.1f}%，回调较深")
            rules.append("回调>25%→不减")

        # 4. 60MA趋势过滤
        ma60_penalty = 0
        if price < low52 * 1.15:  # 接近52周低点
            ma60_penalty = -3
            observations.append("价格接近52周低点，长期趋势破位")
            rules.append("60MA破位→-3")
            score += ma60_penalty

        score = min(16, max(0, score))

        return ScoreDetail(
            name="趋势结构",
            weight=0.10,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=16,
            weighted=score * 0.10
        )

    def calculate_volume_score(
        self,
        turnover_rate: float,
        change_pct: float,
        avg_volume_ratio: float = 1.0
    ) -> ScoreDetail:
        """
        量价关系评分 (10%, 满分10)

        Args:
            turnover_rate: 换手率(%)
            change_pct: 涨跌幅(%)
            avg_volume_ratio: 量比(可选)
        """
        score = 5
        observations = []
        rules = []

        # 基础量价判断
        if change_pct > 0 and turnover_rate > 3:
            score = 8
            observations.append(f"放量上涨，换手率{turnover_rate:.1f}%")
            rules.append("放量上涨→8")
        elif change_pct > 0 and turnover_rate <= 3:
            score = 6
            observations.append(f"缩量上涨，换手率{turnover_rate:.1f}%")
            rules.append("缩量上涨→6")
        elif change_pct <= 0 and turnover_rate > 5:
            score = 3
            observations.append(f"放量下跌，换手率{turnover_rate:.1f}%")
            rules.append("放量下跌→3")
        elif change_pct <= 0 and turnover_rate <= 2:
            score = 4
            observations.append(f"缩量下跌，换手率{turnover_rate:.1f}%")
            rules.append("缩量下跌→4")
        else:
            score = 5
            observations.append(f"量价正常，换手率{turnover_rate:.1f}%")
            rules.append("量价正常→5")

        # 量比加分
        if avg_volume_ratio > 1.5:
            score = min(10, score + 2)
            observations.append(f"量比{avg_volume_ratio:.1f}，成交活跃")
            rules.append("量比>1.5→+2")
        elif avg_volume_ratio > 1.2:
            score = min(10, score + 1)
            observations.append(f"量比{avg_volume_ratio:.1f}，成交较活跃")
            rules.append("量比>1.2→+1")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="量价关系",
            weight=0.10,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.10
        )

    def calculate_pattern_score(
        self,
        price: float,
        high52: float,
        low52: float
    ) -> ScoreDetail:
        """
        价格形态评分 (10%, 满分10)

        Args:
            price: 当前价格
            high52: 52周最高
            low52: 52周最低
        """
        observations = []
        rules = []

        price_from_high = (high52 - price) / high52 * 100
        price_from_low = (price - low52) / low52 * 100

        if price_from_high < 10:
            score = 8
            observations.append(f"距52周高点{price_from_high:.1f}%，接近新高")
            rules.append("接近新高→8")
        elif price_from_high < 20:
            score = 7
            observations.append(f"距52周高点{price_from_high:.1f}%，高位整理")
            rules.append("高位整理→7")
        elif price_from_high < 30:
            score = 6
            observations.append(f"距52周高点{price_from_high:.1f}%，中位震荡")
            rules.append("中位震荡→6")
        elif price_from_high < 50:
            score = 5
            observations.append(f"距52周高点{price_from_high:.1f}%，回调较深")
            rules.append("回调较深→5")
        else:
            score = 3
            observations.append(f"距52周高点{price_from_high:.1f}%，深度回调")
            rules.append("深度回调→3")

        # 接近低点减分
        if price_from_low < 10:
            score = max(0, score - 2)
            observations.append(f"距52周低点仅{price_from_low:.1f}%")
            rules.append("接近低点→-2")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="价格形态",
            weight=0.10,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.10
        )

    def calculate_growth_score(
        self,
        revenue_growth: float,
        profit_growth: float,
        gross_margin: float = None,
        margin_trend: str = None
    ) -> ScoreDetail:
        """
        增长质量评分 (12%, 满分12)

        Args:
            revenue_growth: 营收增速(%)
            profit_growth: 净利增速(%)
            gross_margin: 毛利率(%，可选)
            margin_trend: 毛利率趋势(可选: 'up', 'down', 'stable')
        """
        score = 5
        observations = []
        rules = []

        # 1. 营收增速
        if revenue_growth > 50:
            score = 10
            observations.append(f"营收+{revenue_growth:.1f}%，高速增长")
            rules.append("营收>50%→10")
        elif revenue_growth > 30:
            score = 9
            observations.append(f"营收+{revenue_growth:.1f}%，快速增长")
            rules.append("营收>30%→9")
        elif revenue_growth > 20:
            score = 8
            observations.append(f"营收+{revenue_growth:.1f}%，稳健增长")
            rules.append("营收>20%→8")
        elif revenue_growth > 10:
            score = 7
            observations.append(f"营收+{revenue_growth:.1f}%，温和增长")
            rules.append("营收>10%→7")
        elif revenue_growth > 0:
            score = 5
            observations.append(f"营收+{revenue_growth:.1f}%，低速增长")
            rules.append("营收>0%→5")
        else:
            score = 3
            observations.append(f"营收{revenue_growth:.1f}%，负增长")
            rules.append("营收<0%→3")

        # 2. 利润增速 > 营收增速 (利润弹性)
        if profit_growth > revenue_growth and profit_growth > 0:
            bonus = 2
            score = min(12, score + bonus)
            observations.append(f"利润增速{profit_growth:.1f}% > 营收增速，弹性好")
            rules.append("利润>营收→+2")
        elif profit_growth > 0:
            observations.append(f"利润+{profit_growth:.1f}%，同步增长")
        else:
            score = max(0, score - 2)
            observations.append(f"利润{profit_growth:.1f}%，负增长")
            rules.append("利润负增长→-2")

        # 3. 毛利率趋势加分
        if gross_margin and margin_trend:
            if margin_trend == 'up':
                score = min(12, score + 1)
                observations.append(f"毛利率{gross_margin:.1f}%，连续上升")
                rules.append("毛利率上升→+1")
            elif margin_trend == 'down':
                observations.append(f"毛利率{gross_margin:.1f}%，下降趋势")

        score = min(12, max(0, score))

        return ScoreDetail(
            name="增长质量",
            weight=0.12,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=12,
            weighted=score * 0.12
        )

    def calculate_valuation_score(
        self,
        pe: float,
        pb: float,
        peg: Optional[float] = None,
        fcf_yield: Optional[float] = None,
        is_loss: bool = False
    ) -> ScoreDetail:
        """
        估值合理性评分 (12%, 满分12)

        Args:
            pe: TTM PE
            pb: PB
            peg: 复合PEG(可选)
            fcf_yield: FCF Yield(%，可选)
            is_loss: 是否亏损
        """
        observations = []
        rules = []

        if is_loss or pe < 0:
            score = 0
            observations.append("公司亏损，无法估值")
            rules.append("亏损→0")
        else:
            # PE评分
            if pe < 15:
                pe_score = 10
                observations.append(f"PE {pe:.1f}，估值极低")
                rules.append("PE<15→10")
            elif pe < 20:
                pe_score = 9
                observations.append(f"PE {pe:.1f}，估值很低")
                rules.append("PE<20→9")
            elif pe < 30:
                pe_score = 8
                observations.append(f"PE {pe:.1f}，估值合理")
                rules.append("PE<30→8")
            elif pe < 50:
                pe_score = 6
                observations.append(f"PE {pe:.1f}，估值偏高")
                rules.append("PE<50→6")
            elif pe < 80:
                pe_score = 4
                observations.append(f"PE {pe:.1f}，估值较高")
                rules.append("PE<80→4")
            else:
                pe_score = 2
                observations.append(f"PE {pe:.1f}，估值极高")
                rules.append("PE>80→2")

            score = pe_score

            # PEG调整
            if peg is not None:
                if peg < 0.8:
                    score = min(12, score + 2)
                    observations.append(f"PEG {peg:.2f}，估值偏低")
                    rules.append("PEG<0.8→+2")
                elif peg < 1.0:
                    score = min(12, score + 1)
                    observations.append(f"PEG {peg:.2f}，估值合理")
                    rules.append("PEG<1.0→+1")
                elif peg > 2.0:
                    score = max(0, score - 1)
                    observations.append(f"PEG {peg:.2f}，估值偏高")
                    rules.append("PEG>2.0→-1")

            # PB加分
            if pb < 1.5:
                score = min(12, score + 1)
                observations.append(f"PB {pb:.2f}，接近破净")
                rules.append("PB<1.5→+1")
            elif pb < 2.0:
                score = min(12, score + 0.5)
                observations.append(f"PB {pb:.2f}，估值较低")

        # FCF Yield加分
        if fcf_yield is not None:
            if fcf_yield > 8:
                score = min(12, score + 2)
                observations.append(f"FCF Yield {fcf_yield:.1f}%，现金流极强")
                rules.append("FCF>8%→+2")
            elif fcf_yield > 5:
                score = min(12, score + 1)
                observations.append(f"FCF Yield {fcf_yield:.1f}%，现金流较强")
                rules.append("FCF>5%→+1")
            elif fcf_yield > 0:
                observations.append(f"FCF Yield {fcf_yield:.1f}%")
            else:
                score = max(0, score - 1)
                observations.append(f"FCF Yield {fcf_yield:.1f}%，现金流为负")
                rules.append("FCF<0→-1")

        score = min(12, max(0, score))

        return ScoreDetail(
            name="估值合理性",
            weight=0.12,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=12,
            weighted=score * 0.12
        )

    def calculate_expectation_score(
        self,
        profit_growth: float,
        beat_expectation: bool = None
    ) -> ScoreDetail:
        """
        预期差评分 (11%, 满分10)

        Args:
            profit_growth: 利润增速(%)
            beat_expectation: 是否超预期(可选)
        """
        observations = []
        rules = []

        if beat_expectation is not None:
            if beat_expectation and profit_growth > 50:
                score = 10
                observations.append(f"大幅超预期，利润+{profit_growth:.1f}%")
                rules.append("大幅超预期→10")
            elif beat_expectation and profit_growth > 20:
                score = 8
                observations.append(f"小幅超预期，利润+{profit_growth:.1f}%")
                rules.append("小幅超预期→8")
            elif beat_expectation:
                score = 7
                observations.append(f"略超预期，利润+{profit_growth:.1f}%")
                rules.append("略超预期→7")
            else:
                score = 5
                observations.append(f"符合预期，利润+{profit_growth:.1f}%")
                rules.append("符合预期→5")
        else:
            # 基于增速推断
            if profit_growth > 100:
                score = 10
                observations.append(f"利润增速{profit_growth:.1f}%，大幅超预期")
                rules.append("增速>100%→10")
            elif profit_growth > 50:
                score = 8
                observations.append(f"利润增速{profit_growth:.1f}%，明显超预期")
                rules.append("增速>50%→8")
            elif profit_growth > 20:
                score = 7
                observations.append(f"利润增速{profit_growth:.1f}%，小幅超预期")
                rules.append("增速>20%→7")
            elif profit_growth > 0:
                score = 6
                observations.append(f"利润增速{profit_growth:.1f}%，符合预期")
                rules.append("增速>0%→6")
            else:
                score = 3
                observations.append(f"利润增速{profit_growth:.1f}%，不及预期")
                rules.append("增速<0%→3")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="预期差",
            weight=0.11,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.11
        )

    def calculate_analyst_score(
        self,
        gain_250d: float,
        profit_growth: float,
        has_buy_rating: bool = None
    ) -> ScoreDetail:
        """
        分析师动向评分 (8%, 满分10)

        Args:
            gain_250d: 250日涨幅(%)
            profit_growth: 利润增速(%)
            has_buy_rating: 是否有买入评级(可选)
        """
        observations = []
        rules = []

        # 基于趋势和业绩推断
        if gain_250d > 50 and profit_growth > 20:
            score = 8
            observations.append("趋势强劲+业绩高增，分析师看好")
            rules.append("趋势+业绩→8")
        elif gain_250d > 20 and profit_growth > 10:
            score = 7
            observations.append("趋势向好+业绩增长，分析师较看好")
            rules.append("趋势+业绩→7")
        elif gain_250d > 0 and profit_growth > 0:
            score = 6
            observations.append("趋势平稳+业绩正常，分析师中性")
            rules.append("趋势+业绩→6")
        elif gain_250d > -10:
            score = 5
            observations.append("趋势偏弱，分析师观望")
            rules.append("趋势偏弱→5")
        else:
            score = 3
            observations.append("趋势向下，分析师谨慎")
            rules.append("趋势向下→3")

        # 买入评级加分
        if has_buy_rating is not None:
            if has_buy_rating:
                score = min(10, score + 1)
                observations.append("有买入评级")
                rules.append("买入评级→+1")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="分析师动向",
            weight=0.08,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.08
        )

    def calculate_capital_flow_score(
        self,
        change_pct: float,
        turnover_rate: float,
        north_flow_5d: float = None
    ) -> ScoreDetail:
        """
        资金流向评分 (7%, 满分10)

        Args:
            change_pct: 涨跌幅(%)
            turnover_rate: 换手率(%)
            north_flow_5d: 5日北向净流入(亿，可选)
        """
        observations = []
        rules = []

        # 基于涨跌和换手推断
        if change_pct > 0 and turnover_rate > 3:
            score = 7
            observations.append(f"放量上涨，资金流入")
            rules.append("放量上涨→7")
        elif change_pct > 0:
            score = 6
            observations.append(f"上涨，资金较积极")
            rules.append("上涨→6")
        elif change_pct > -2:
            score = 5
            observations.append(f"小幅下跌，资金中性")
            rules.append("小幅下跌→5")
        elif change_pct > -5:
            score = 4
            observations.append(f"下跌，资金流出")
            rules.append("下跌→4")
        else:
            score = 3
            observations.append(f"大幅下跌，资金明显流出")
            rules.append("大幅下跌→3")

        # 北向资金加分
        if north_flow_5d is not None:
            if north_flow_5d > 5:
                score = min(10, score + 2)
                observations.append(f"北向5日净流入{north_flow_5d:.1f}亿")
                rules.append("北向大幅流入→+2")
            elif north_flow_5d > 0:
                score = min(10, score + 1)
                observations.append(f"北向5日净流入{north_flow_5d:.1f}亿")
                rules.append("北向流入→+1")
            elif north_flow_5d < -5:
                score = max(0, score - 2)
                observations.append(f"北向5日净流出{abs(north_flow_5d):.1f}亿")
                rules.append("北向大幅流出→-2")
            elif north_flow_5d < 0:
                score = max(0, score - 1)
                observations.append(f"北向5日净流出{abs(north_flow_5d):.1f}亿")
                rules.append("北向流出→-1")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="资金流向",
            weight=0.07,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.07
        )

    def calculate_event_score(
        self,
        has_major_positive: bool = False,
        has_positive: bool = False,
        has_negative: bool = False,
        has_major_negative: bool = False
    ) -> ScoreDetail:
        """
        事件驱动评分 (5%, 满分10)

        Args:
            has_major_positive: 是否有重大正面事件
            has_positive: 是否有正面事件
            has_negative: 是否有负面事件
            has_major_negative: 是否有重大负面事件
        """
        observations = []
        rules = []

        if has_major_positive:
            score = 10
            observations.append("重大正面事件")
            rules.append("重大正面→10")
        elif has_positive:
            score = 7
            observations.append("正面事件")
            rules.append("正面→7")
        elif has_major_negative:
            score = 0
            observations.append("重大负面事件")
            rules.append("重大负面→0")
        elif has_negative:
            score = 3
            observations.append("负面事件")
            rules.append("负面→3")
        else:
            score = 5
            observations.append("无重大事件")
            rules.append("无事件→5")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="事件驱动",
            weight=0.05,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.05
        )

    def calculate_risk_score(
        self,
        turnover_rate: float,
        amount: float,
        pe: float,
        pb: float,
        debt_ratio: float = None
    ) -> ScoreDetail:
        """
        风险因子评分 (15%, 满分10)

        Args:
            turnover_rate: 换手率(%)
            amount: 成交额(亿)
            pe: PE
            pb: PB
            debt_ratio: 资产负债率(%，可选)
        """
        score = 5
        observations = []
        rules = []

        # 1. 波动率(基于换手率)
        if turnover_rate > 8:
            score -= 2
            observations.append(f"换手率{turnover_rate:.1f}%，波动大")
            rules.append("换手>8%→-2")
        elif turnover_rate > 5:
            score -= 1
            observations.append(f"换手率{turnover_rate:.1f}%，波动较大")
            rules.append("换手>5%→-1")
        elif turnover_rate < 2:
            score += 1
            observations.append(f"换手率{turnover_rate:.1f}%，波动小")
            rules.append("换手<2%→+1")
        else:
            observations.append(f"换手率{turnover_rate:.1f}%，波动正常")

        # 2. 流动性
        if amount > 1000:
            score += 2
            observations.append(f"成交额{amount:.0f}亿，流动性极好")
            rules.append("成交>1000亿→+2")
        elif amount > 100:
            score += 1
            observations.append(f"成交额{amount:.0f}亿，流动性好")
            rules.append("成交>100亿→+1")
        elif amount < 10:
            score -= 2
            observations.append(f"成交额{amount:.1f}亿，流动性差")
            rules.append("成交<10亿→-2")
        elif amount < 50:
            score -= 1
            observations.append(f"成交额{amount:.1f}亿，流动性一般")
            rules.append("成交<50亿→-1")

        # 3. 亏损风险
        if pe < 0:
            score -= 3
            observations.append("公司亏损，风险高")
            rules.append("亏损→-3")

        # 4. 杠杆风险
        if debt_ratio is not None:
            if debt_ratio > 70:
                score -= 2
                observations.append(f"资产负债率{debt_ratio:.1f}%，杠杆极高")
                rules.append("负债>70%→-2")
            elif debt_ratio > 50:
                score -= 1
                observations.append(f"资产负债率{debt_ratio:.1f}%，杠杆较高")
                rules.append("负债>50%→-1")
            elif debt_ratio < 30:
                score += 1
                observations.append(f"资产负债率{debt_ratio:.1f}%，杠杆低")
                rules.append("负债<30%→+1")

        score = min(10, max(0, score))

        return ScoreDetail(
            name="风险因子",
            weight=0.15,
            observation="；".join(observations),
            rule="；".join(rules),
            score=score,
            max_score=10,
            weighted=score * 0.15
        )

    def calculate_composite_peg(
        self,
        pe: float,
        quarterly_growth: List[float]
    ) -> Optional[float]:
        """
        计算复合PEG

        Args:
            pe: TTM PE
            quarterly_growth: 最近4个季度的单季净利增速列表(%)

        Returns:
            复合PEG，无法计算返回None
        """
        # 过滤掉None和负值(低基数)
        valid_growth = [g for g in quarterly_growth if g is not None and g > 0]

        if len(valid_growth) < 2:
            return None

        # 计算几何平均增速
        product = 1.0
        for g in valid_growth:
            product *= (1 + g / 100)

        geometric_avg = (product ** (1 / len(valid_growth)) - 1) * 100

        if geometric_avg <= 0:
            return None

        return pe / geometric_avg

    def calculate_suggestion(
        self,
        total_normalized: float
    ) -> str:
        """
        根据归一化评分给出操作建议

        Args:
            total_normalized: 归一化评分(0-100)

        Returns:
            操作建议字符串
        """
        if total_normalized >= 8:
            return "强烈看多"
        elif total_normalized >= 6:
            return "看多"
        elif total_normalized >= 5:
            return "中性"
        elif total_normalized >= 4:
            return "偏空"
        else:
            return "看空"

    def calculate_position_advice(
        self,
        suggestion: str,
        total_normalized: float
    ) -> str:
        """
        仓位建议

        Args:
            suggestion: 操作建议
            total_normalized: 归一化评分

        Returns:
            仓位建议
        """
        if suggestion == "强烈看多":
            return "重仓"
        elif suggestion == "看多":
            return "持有"
        elif suggestion == "中性":
            return "轻仓"
        elif suggestion == "偏空":
            return "减仓"
        else:
            return "清仓"

    def score_stock(
        self,
        code: str,
        name: str,
        price: float,
        change_pct: float,
        pe: float,
        pb: float,
        high52: float,
        low52: float,
        turnover_rate: float,
        amount: float,
        gain_250d: float,
        revenue_growth: float,
        profit_growth: float,
        gross_margin: float = None,
        margin_trend: str = None,
        peg: Optional[float] = None,
        fcf_yield: Optional[float] = None,
        is_loss: bool = False,
        north_flow_5d: float = None,
        debt_ratio: float = None,
        has_major_positive: bool = False,
        has_positive: bool = False,
        has_negative: bool = False,
        has_major_negative: bool = False,
        beat_expectation: bool = None,
        has_buy_rating: bool = None,
        avg_volume_ratio: float = 1.0,
        kline_data: List[Dict] = None
    ) -> StockScore:
        """
        计算股票综合评分

        Returns:
            StockScore对象
        """
        # 计算各维度评分
        trend = self.calculate_trend_score(price, high52, low52, gain_250d, kline_data)
        volume = self.calculate_volume_score(turnover_rate, change_pct, avg_volume_ratio)
        pattern = self.calculate_pattern_score(price, high52, low52)
        growth = self.calculate_growth_score(revenue_growth, profit_growth, gross_margin, margin_trend)
        valuation = self.calculate_valuation_score(pe, pb, peg, fcf_yield, is_loss)
        expectation = self.calculate_expectation_score(profit_growth, beat_expectation)
        analyst = self.calculate_analyst_score(gain_250d, profit_growth, has_buy_rating)
        capital_flow = self.calculate_capital_flow_score(change_pct, turnover_rate, north_flow_5d)
        event = self.calculate_event_score(has_major_positive, has_positive, has_negative, has_major_negative)
        risk = self.calculate_risk_score(turnover_rate, amount, pe, pb, debt_ratio)

        # 计算总分
        total_raw = (
            trend.weighted + volume.weighted + pattern.weighted +
            growth.weighted + valuation.weighted + expectation.weighted +
            analyst.weighted + capital_flow.weighted + event.weighted +
            risk.weighted
        )

        # 归一化
        total_normalized = total_raw / self.MAX_RAW_SCORE * 100

        # 获取建议
        suggestion = self.calculate_suggestion(total_normalized)

        # 计算动态PE (假设Q1 EPS * 4)
        # 这里简化处理，实际应该从数据获取
        dynamic_pe = pe * 0.85 if not is_loss else pe

        return StockScore(
            code=code,
            name=name,
            price=price,
            change_pct=change_pct,
            pe=pe,
            pb=pb,
            trend=trend,
            volume=volume,
            pattern=pattern,
            growth=growth,
            valuation=valuation,
            expectation=expectation,
            analyst=analyst,
            capital_flow=capital_flow,
            event=event,
            risk=risk,
            total_raw=round(total_raw, 2),
            total_normalized=round(total_normalized, 2),
            suggestion=suggestion,
            ttm_pe=pe,
            dynamic_pe=round(dynamic_pe, 2),
            peg_composite=peg,
            fcf_yield=fcf_yield
        )


# 便捷函数
def format_score(score: StockScore) -> str:
    """格式化评分输出"""
    return f"{score.total_normalized}/100（原始：{score.total_raw}/115）"


def format_peg(peg: Optional[float]) -> str:
    """格式化PEG输出"""
    if peg is None:
        return "N/A"
    return f"{peg:.2f}"
