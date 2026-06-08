"""
数据获取模块
统一获取行情、K线、基本面数据
"""

import subprocess
import json
import re
import gzip
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class QuoteData:
    """行情数据"""
    code: str
    name: str
    price: float
    change_pct: float
    open: float
    high: float
    low: float
    volume: float  # 成交量(手)
    amount: float  # 成交额(万)
    turnover_rate: float  # 换手率(%)
    pe: float
    pb: float
    high52: float
    low52: float
    market_cap: float  # 总市值(亿)


@dataclass
class KlineBar:
    """K线数据"""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class FundData:
    """基本面数据"""
    report_date: str
    revenue: float  # 营收(亿)
    revenue_growth: float  # 营收增速(%)
    net_profit: float  # 净利润(亿)
    profit_growth: float  # 净利润增速(%)
    gross_margin: float  # 毛利率(%)
    roe: float  # ROE(%)
    eps: float  # 每股收益
    mgjyxjje: float  # 每股经营现金流


class DataFetcher:
    """数据获取器"""

    # 市场代码映射
    MARKET_MAP = {
        '60': 'sh',  # 沪市主板
        '68': 'sh',  # 科创板
        '00': 'sz',  # 深市主板
        '30': 'sz',  # 创业板
    }

    MARKET_MAP_EM = {
        '60': 'SH',  # 沪市主板
        '68': 'SH',  # 科创板
        '00': 'SZ',  # 深市主板
        '30': 'SZ',  # 创业板
    }

    def __init__(self):
        pass

    def get_market_code(self, code: str, for_eastmoney: bool = False) -> str:
        """获取市场代码"""
        prefix = code[:2]
        if for_eastmoney:
            return self.MARKET_MAP_EM.get(prefix, 'SZ')
        return self.MARKET_MAP.get(prefix, 'sz')

    def fetch_quote(self, code: str) -> Optional[QuoteData]:
        """
        获取行情数据 (腾讯财经API)

        Args:
            code: 股票代码

        Returns:
            QuoteData对象，失败返回None
        """
        market = self.get_market_code(code)
        url = f"https://qt.gtimg.cn/q={market}{code}"

        try:
            result = subprocess.run(
                ['curl', '-s', '--max-time', '10', url],
                capture_output=True
            )

            if result.returncode != 0:
                return None

            data = result.stdout.decode('gbk', errors='ignore')
            parts = data.split('~')

            if len(parts) < 50:
                return None

            return QuoteData(
                code=parts[2],
                name=parts[1],
                price=float(parts[3]) if parts[3] else 0,
                change_pct=float(parts[32]) if parts[32] else 0,
                open=float(parts[5]) if parts[5] else 0,
                high=float(parts[33]) if parts[33] else 0,
                low=float(parts[34]) if parts[34] else 0,
                volume=float(parts[6]) if parts[6] else 0,
                amount=float(parts[37]) if parts[37] else 0,
                turnover_rate=float(parts[38]) if parts[38] else 0,
                pe=float(parts[39]) if parts[39] else 0,
                pb=float(parts[46]) if parts[46] else 0,
                high52=float(parts[47]) if parts[47] else 0,
                low52=float(parts[48]) if parts[48] else 0,
                market_cap=float(parts[45]) if parts[45] else 0
            )
        except Exception as e:
            print(f"获取行情数据失败: {e}")
            return None

    def fetch_kline(
        self,
        code: str,
        start_date: str = "2024-01-01",
        end_date: str = "2026-12-31",
        count: int = 250
    ) -> List[KlineBar]:
        """
        获取K线数据 (腾讯财经API)

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数

        Returns:
            KlineBar列表
        """
        market = self.get_market_code(code)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={market}{code},day,{start_date},{end_date},{count},qfq"

        try:
            result = subprocess.run(
                ['curl', '-s', '--max-time', '10', url],
                capture_output=True, text=True
            )

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)

            # 解析K线数据
            kline_data = data.get('data', {}).get(f'{market}{code}', {})
            bars_raw = kline_data.get('qfqday', kline_data.get('day', []))

            bars = []
            for bar in bars_raw:
                if len(bar) >= 6:
                    bars.append(KlineBar(
                        date=bar[0],
                        open=float(bar[1]),
                        high=float(bar[2]),
                        low=float(bar[3]),
                        close=float(bar[4]),
                        volume=float(bar[5])
                    ))

            return bars

        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return []

    def fetch_fundamentals(self, code: str) -> List[FundData]:
        """
        获取基本面数据 (东方财富F10 API)

        Args:
            code: 股票代码

        Returns:
            FundData列表(最近8期)
        """
        market = self.get_market_code(code, for_eastmoney=True)
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=0&code={market}{code}"

        try:
            result = subprocess.run(
                ['curl', '-s', '--max-time', '10',
                 '-H', 'Accept-Encoding: gzip',
                 '-H', 'Referer: https://emweb.securities.eastmoney.com',
                 '-H', 'User-Agent: Mozilla/5.0',
                 url],
                capture_output=True
            )

            if result.returncode != 0:
                return []

            # 处理gzip压缩
            try:
                output = gzip.decompress(result.stdout)
            except:
                output = result.stdout

            try:
                data = json.loads(output.decode('utf-8'))
            except:
                data = json.loads(output.decode('gbk', errors='ignore'))
            reports = data.get('data', [])

            fund_data = []
            for report in reports[:8]:  # 最近8期
                try:
                    fund_data.append(FundData(
                        report_date=report.get('REPORT_DATE_NAME', ''),
                        revenue=float(report.get('TOTALOPERATEREVE', 0)) / 1e8,
                        revenue_growth=float(report.get('TOTALOPERATEREVETZ', 0)),
                        net_profit=float(report.get('PARENTNETPROFIT', 0)) / 1e8,
                        profit_growth=float(report.get('PARENTNETPROFITTZ', 0)),
                        gross_margin=float(report.get('XSMLL', 0)),
                        roe=float(report.get('ROEJQ', 0)),
                        eps=float(report.get('EPSJB', 0)),
                        mgjyxjje=float(report.get('MGJYXJJE', 0))
                    ))
                except (ValueError, TypeError):
                    continue

            return fund_data

        except Exception as e:
            print(f"获取基本面数据失败: {e}")
            return []

    def calculate_gain(self, kline: List[KlineBar]) -> float:
        """计算区间涨幅"""
        if len(kline) < 2:
            return 0

        first_close = kline[0].close
        last_close = kline[-1].close

        if first_close == 0:
            return 0

        return (last_close - first_close) / first_close * 100

    def get_high_low(self, kline: List[KlineBar]) -> Tuple[float, float]:
        """获取区间最高最低价"""
        if not kline:
            return 0, 0

        highs = [bar.high for bar in kline]
        lows = [bar.low for bar in kline]

        return max(highs), min(lows)

    def fetch_all(
        self,
        code: str,
        start_date: str = "2024-01-01"
    ) -> Dict:
        """
        获取所有数据

        Args:
            code: 股票代码
            start_date: K线开始日期

        Returns:
            包含所有数据的字典
        """
        # 并行获取数据
        quote = self.fetch_quote(code)
        kline = self.fetch_kline(code, start_date)
        fundamentals = self.fetch_fundamentals(code)

        # 计算衍生数据
        gain = self.calculate_gain(kline)
        high, low = self.get_high_low(kline)

        # 计算最新4个季度单季净利增速
        quarterly_growth = []
        if len(fundamentals) >= 4:
            for i in range(4):
                quarterly_growth.append(fundamentals[i].profit_growth)

        return {
            'quote': quote,
            'kline': kline,
            'fundamentals': fundamentals,
            'gain_250d': gain,
            'high_250d': high,
            'low_250d': low,
            'quarterly_growth': quarterly_growth
        }
