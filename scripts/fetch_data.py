#!/usr/bin/env python3
"""
数据获取和基础指标计算脚本
只负责获取数据和计算基础指标，不负责评分和分析

用法:
    python scripts/fetch_data.py 002050 603186 601138

输出:
    JSON格式的基础数据和指标，供大模型分析使用

降级方案:
    1. 东方财富API（优先）
    2. AKShare（备选）
    3. Tushare（需用户提供token）
    4. 返回"需手动查询"

限频控制:
    - AKShare: 每次请求间隔0.5秒
    - Tushare: 每次请求间隔0.3秒
"""

import sys
import os
import json
import subprocess
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.data_fetcher import DataFetcher

# 限频控制
AKSHARE_DELAY = 0.5  # AKShare请求间隔（秒）
TUSHARE_DELAY = 0.3  # Tushare请求间隔（秒）
last_akshare_time = 0
last_tushare_time = 0


def load_holdings():
    """加载持仓数据"""
    holdings_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'portfolio', 'holdings.json'
    )
    try:
        with open(holdings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('positions', [])
    except:
        return []


def fetch_north_flow(code: str, tushare_token: str = None) -> dict:
    """
    获取北向资金数据 (分层降级)

    Args:
        code: 股票代码
        tushare_token: Tushare token（可选）

    Returns:
        北向资金数据字典
    """
    # 优先级1：东方财富API
    result = _fetch_north_flow_eastmoney(code)
    if result.get('error') is None:
        return result

    # 优先级2：AKShare（限频控制）
    result = _fetch_north_flow_akshare(code)
    if result.get('error') is None:
        return result

    # 优先级3：Tushare（需token）
    if tushare_token:
        result = _fetch_north_flow_tushare(code, tushare_token)
        if result.get('error') is None:
            return result

    # 优先级4：返回需手动查询
    return {'net_buy_5d': None, 'net_buy_1d': None, 'error': '需手动查询'}


def _fetch_north_flow_eastmoney(code: str) -> dict:
    """
    从东方财富获取北向资金数据
    """
    # 判断市场代码
    if code.startswith('6'):
        secid = f"1.{code}"  # 沪市
    else:
        secid = f"0.{code}"  # 深市

    url = f"https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?lmt=5&klt=101&secid={secid}&fields1=f1,f2,f3,f7&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65"

    try:
        result = subprocess.run(
            ['curl', '-s', '--max-time', '10', url, '-H', 'Referer: https://data.eastmoney.com'],
            capture_output=True
        )

        if result.returncode != 0:
            return {'net_buy_5d': None, 'net_buy_1d': None, 'error': '东方财富API失败'}

        data = json.loads(result.stdout.decode('utf-8'))

        if not data.get('data') or not data['data'].get('klines'):
            return {'net_buy_5d': None, 'net_buy_1d': None, 'error': '东方财富无数据'}

        klines = data['data']['klines']

        # 解析数据
        net_buy_5d = 0
        net_buy_1d = 0

        for i, kline in enumerate(klines):
            parts = kline.split(',')
            if len(parts) >= 2:
                net_buy = float(parts[1]) or 0  # 主力净流入
                if i == 0:
                    net_buy_1d = net_buy
                net_buy_5d += net_buy

        return {
            'net_buy_5d': round(net_buy_5d / 1e8, 2),  # 转换为亿
            'net_buy_1d': round(net_buy_1d / 1e8, 2),
            'error': None
        }

    except Exception as e:
        return {'net_buy_5d': None, 'net_buy_1d': None, 'error': f'东方财富API异常: {str(e)}'}


def _fetch_north_flow_akshare(code: str) -> dict:
    """
    从AKShare获取北向资金数据（带限频控制）
    """
    global last_akshare_time

    try:
        # 限频控制
        current_time = time.time()
        elapsed = current_time - last_akshare_time
        if elapsed < AKSHARE_DELAY:
            time.sleep(AKSHARE_DELAY - elapsed)

        # 使用akshare获取北向资金数据
        cmd = f"""conda run -n cQuanty python3 -c "
import akshare as ak
import time
try:
    df = ak.stock_hsgt_individual_em(symbol='{code}')
    if df is not None and len(df) >= 5:
        recent = df.tail(5)
        # 今日增持资金列
        net_buy_5d = recent['今日增持资金'].sum() / 1e8
        net_buy_1d = recent.iloc[-1]['今日增持资金'] / 1e8
        print(f'{{net_buy_5d:.2f}},{{net_buy_1d:.2f}}')
    else:
        print('ERROR:数据不足')
except Exception as e:
    print(f'ERROR:{{str(e)}}')
" """

        result = subprocess.run(
            ['bash', '-c', cmd],
            capture_output=True, text=True, timeout=30
        )

        # 更新最后请求时间
        last_akshare_time = time.time()

        if result.returncode != 0 or 'ERROR' in result.stdout:
            return {'net_buy_5d': None, 'net_buy_1d': None, 'error': 'AKShare失败'}

        parts = result.stdout.strip().split(',')
        if len(parts) == 2:
            return {
                'net_buy_5d': float(parts[0]),
                'net_buy_1d': float(parts[1]),
                'error': None
            }

        return {'net_buy_5d': None, 'net_buy_1d': None, 'error': 'AKShare解析失败'}

    except Exception as e:
        return {'net_buy_5d': None, 'net_buy_1d': None, 'error': f'AKShare异常: {str(e)}'}


def fetch_margin_data(code: str, tushare_token: str = None) -> dict:
    """
    获取融资融券数据 (分层降级)

    Args:
        code: 股票代码
        tushare_token: Tushare token（可选）

    Returns:
        融资融券数据字典
    """
    # 优先级1：东方财富API
    result = _fetch_margin_eastmoney(code)
    if result.get('error') is None:
        return result

    # 优先级2：AKShare（限频控制）
    result = _fetch_margin_akshare(code)
    if result.get('error') is None:
        return result

    # 优先级3：Tushare（需token）
    if tushare_token:
        result = _fetch_margin_tushare(code, tushare_token)
        if result.get('error') is None:
            return result

    # 优先级4：返回需手动查询
    return {'margin_balance': None, 'margin_change': None, 'error': '需手动查询'}


def _fetch_margin_eastmoney(code: str) -> dict:
    """
    从东方财富获取融资融券数据
    """
    url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=TRADE_DATE&sortTypes=-1&pageSize=5&pageNumber=1&reportName=RPT_MARGIN_STOCK_DETAIL&columns=ALL&filter=(SCODE%3D%22{code}%22)"

    try:
        result = subprocess.run(
            ['curl', '-s', '--max-time', '10', url],
            capture_output=True
        )

        if result.returncode != 0:
            return {'margin_balance': None, 'margin_change': None, 'error': '东方财富API失败'}

        data = json.loads(result.stdout.decode('utf-8'))

        if not data.get('result') or not data['result'].get('data'):
            return {'margin_balance': None, 'margin_change': None, 'error': '东方财富无数据'}

        records = data['result']['data']

        if len(records) < 2:
            return {'margin_balance': None, 'margin_change': None, 'error': '东方财富数据不足'}

        # 最新融资余额
        margin_balance = records[0].get('RZYE', 0) or 0

        # 计算5日融资余额变化
        margin_change = 0
        if len(records) >= 5:
            margin_change = margin_balance - (records[4].get('RZYE', 0) or 0)
        elif len(records) >= 2:
            margin_change = margin_balance - (records[1].get('RZYE', 0) or 0)

        return {
            'margin_balance': round(margin_balance / 1e8, 2),  # 转换为亿
            'margin_change': round(margin_change / 1e8, 2),
            'error': None
        }

    except Exception as e:
        return {'margin_balance': None, 'margin_change': None, 'error': f'东方财富API异常: {str(e)}'}


def _fetch_north_flow_tushare(code: str, token: str) -> dict:
    """
    从Tushare获取北向资金数据（带限频控制）
    """
    global last_tushare_time

    try:
        # 限频控制
        current_time = time.time()
        elapsed = current_time - last_tushare_time
        if elapsed < TUSHARE_DELAY:
            time.sleep(TUSHARE_DELAY - elapsed)

        # 转换股票代码格式
        if code.startswith('6'):
            ts_code = f"{code}.SH"
        else:
            ts_code = f"{code}.SZ"

        # 使用tushare获取北向资金数据
        cmd = f"""conda run -n cQuanty python3 -c "
import tushare as ts
try:
    ts.set_token('{token}')
    pro = ts.pro_api()
    # 获取北向资金数据
    df = pro.hsgt_top10(ts_code='{ts_code}', start_date='20260601', end_date='20261231')
    if df is not None and len(df) >= 5:
        recent = df.tail(5)
        net_buy_5d = recent['net_amount'].sum() / 1e8
        net_buy_1d = recent.iloc[-1]['net_amount'] / 1e8
        print(f'{{net_buy_5d:.2f}},{{net_buy_1d:.2f}}')
    else:
        print('ERROR:数据不足')
except Exception as e:
    print(f'ERROR:{{str(e)}}')
" """

        result = subprocess.run(
            ['bash', '-c', cmd],
            capture_output=True, text=True, timeout=30
        )

        # 更新最后请求时间
        last_tushare_time = time.time()

        if result.returncode != 0 or 'ERROR' in result.stdout:
            return {'net_buy_5d': None, 'net_buy_1d': None, 'error': 'Tushare失败'}

        parts = result.stdout.strip().split(',')
        if len(parts) == 2:
            return {
                'net_buy_5d': float(parts[0]),
                'net_buy_1d': float(parts[1]),
                'error': None
            }

        return {'net_buy_5d': None, 'net_buy_1d': None, 'error': 'Tushare解析失败'}

    except Exception as e:
        return {'net_buy_5d': None, 'net_buy_1d': None, 'error': f'Tushare异常: {str(e)}'}


def _fetch_margin_akshare(code: str) -> dict:
    """
    从AKShare获取融资融券数据（带限频控制）

    注意：AKShare的融资融券函数是获取某一日期的汇总数据，不是获取某只股票的历史数据
    因此这里返回"需手动查询"
    """
    # AKShare的融资融券函数需要日期参数，不是股票代码
    # 暂时返回需手动查询
    return {'margin_balance': None, 'margin_change': None, 'error': '需手动查询'}


def _fetch_margin_tushare(code: str, token: str) -> dict:
    """
    从Tushare获取融资融券数据（带限频控制）
    """
    global last_tushare_time

    try:
        # 限频控制
        current_time = time.time()
        elapsed = current_time - last_tushare_time
        if elapsed < TUSHARE_DELAY:
            time.sleep(TUSHARE_DELAY - elapsed)

        # 转换股票代码格式
        if code.startswith('6'):
            ts_code = f"{code}.SH"
        else:
            ts_code = f"{code}.SZ"

        # 使用tushare获取融资融券数据
        cmd = f"""conda run -n cQuanty python3 -c "
import tushare as ts
try:
    ts.set_token('{token}')
    pro = ts.pro_api()
    # 获取融资融券数据
    df = pro.margin_detail(ts_code='{ts_code}', start_date='20260601', end_date='20261231')
    if df is not None and len(df) >= 5:
        recent = df.tail(5)
        margin_balance = recent.iloc[-1]['rzye'] / 1e8
        margin_change = (recent.iloc[-1]['rzye'] - recent.iloc[0]['rzye']) / 1e8
        print(f'{{margin_balance:.2f}},{{margin_change:.2f}}')
    else:
        print('ERROR:数据不足')
except Exception as e:
    print(f'ERROR:{{str(e)}}')
" """

        result = subprocess.run(
            ['bash', '-c', cmd],
            capture_output=True, text=True, timeout=30
        )

        # 更新最后请求时间
        last_tushare_time = time.time()

        if result.returncode != 0 or 'ERROR' in result.stdout:
            return {'margin_balance': None, 'margin_change': None, 'error': 'Tushare失败'}

        parts = result.stdout.strip().split(',')
        if len(parts) == 2:
            return {
                'margin_balance': float(parts[0]),
                'margin_change': float(parts[1]),
                'error': None
            }

        return {'margin_balance': None, 'margin_change': None, 'error': 'Tushare解析失败'}

    except Exception as e:
        return {'margin_balance': None, 'margin_change': None, 'error': f'Tushare异常: {str(e)}'}


def calculate_composite_peg(pe, quarterly_growth):
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


def fetch_recent_events(code: str) -> dict:
    """
    获取近期事件（东方财富公告API）

    Args:
        code: 股票代码

    Returns:
        近期事件字典
    """
    # 判断市场
    if code.startswith('6'):
        ann_type = 'SHA'  # 沪市
    else:
        ann_type = 'SZA'  # 深市

    url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=10&page_index=1&ann_type={ann_type}&client_source=web&stock_list={code}"

    try:
        result = subprocess.run(
            ['curl', '-s', '--max-time', '10', url],
            capture_output=True
        )

        if result.returncode != 0:
            return {'events': [], 'error': '获取失败'}

        data = json.loads(result.stdout.decode('utf-8'))

        if 'data' not in data or 'list' not in data['data']:
            return {'events': [], 'error': '无数据'}

        events = []
        for item in data['data']['list'][:10]:
            title = item.get('title', '')
            date = item.get('notice_date', '')[:10]

            # 判断事件类型
            event_type = 'neutral'
            if any(kw in title for kw in ['回购', '增持', '激励', '超预期', '增长', '中标', '签约', '合作']):
                event_type = 'positive'
            elif any(kw in title for kw in ['减持', '质押', '诉讼', '处罚', '风险', '亏损', '下滑', '下降']):
                event_type = 'negative'
            elif any(kw in title for kw in ['军工', '制裁', '限制', '黑名单', '实体清单', '管制']):
                event_type = 'negative'

            events.append({
                'date': date,
                'title': title,
                'type': event_type
            })

        return {'events': events, 'error': None}

    except Exception as e:
        return {'events': [], 'error': str(e)}


def _calculate_fib_levels(high52: float, low52: float) -> dict:
    """
    计算斐波那契回撤位

    Args:
        high52: 52周最高价
        low52: 52周最低价

    Returns:
        斐波那契回撤位字典
    """
    if high52 <= low52:
        return {}

    diff = high52 - low52
    return {
        'fib_236': round(high52 - diff * 0.236, 2),
        'fib_382': round(high52 - diff * 0.382, 2),
        'fib_500': round(high52 - diff * 0.500, 2),
        'fib_618': round(high52 - diff * 0.618, 2)
    }


def _identify_price_action(kline: list) -> dict:
    """
    识别Price Action形态

    Args:
        kline: K线数据列表

    Returns:
        Price Action形态字典
    """
    if not kline or len(kline) < 20:
        return {
            'has_pocket_pivot': False,
            'has_shooting_star': False,
            'has_big_red_bar': False,
            'has_double_bottom': False,
            'has_head_shoulders_bottom': False
        }

    # 获取最近20根K线
    recent = kline[-20:] if len(kline) >= 20 else kline

    # 计算前10日最大阴线量
    max_red_volume = 0
    for bar in recent[-15:-5]:
        if bar.close < bar.open:  # 阴线
            max_red_volume = max(max_red_volume, bar.volume)

    # 口袋支点判断
    has_pocket_pivot = False
    if len(recent) >= 2:
        last_bar = recent[-1]
        prev_bar = recent[-2]
        # 放量阳线，量超过前10日最大阴线量
        if (last_bar.close > last_bar.open and  # 阳线
            last_bar.volume > max_red_volume and  # 放量
            last_bar.close > prev_bar.close):  # 收盘价上涨
            has_pocket_pivot = True

    # 射击之星判断
    has_shooting_star = False
    if len(recent) >= 3:
        last_bar = recent[-1]
        # 长上影线（上影线 > 实体2倍）
        body = abs(last_bar.close - last_bar.open)
        upper_shadow = last_bar.high - max(last_bar.close, last_bar.open)
        if upper_shadow > body * 2 and last_bar.close < last_bar.open:
            has_shooting_star = True

    # 放量大阴线判断
    has_big_red_bar = False
    if len(recent) >= 2:
        last_bar = recent[-1]
        avg_volume = sum(bar.volume for bar in recent[-10:]) / 10
        # 大阴线（跌幅>3%）且放量（成交量>1.5倍均量）
        if (last_bar.close < last_bar.open and
            (last_bar.open - last_bar.close) / last_bar.open > 0.03 and
            last_bar.volume > avg_volume * 1.5):
            has_big_red_bar = True

    # 双底判断（简化版）
    has_double_bottom = False
    if len(recent) >= 15:
        lows = [bar.low for bar in recent[-15:]]
        first_half = lows[:7]
        second_half = lows[8:]
        if first_half and second_half:
            min_idx1 = lows.index(min(first_half))
            min_idx2 = lows.index(min(second_half))
            # 两个低点接近（差距<3%）且中间有反弹
            if lows[min_idx1] > 0 and abs(lows[min_idx1] - lows[min_idx2]) / lows[min_idx1] < 0.03:
                has_double_bottom = True

    # 头肩底判断（简化版）
    has_head_shoulders_bottom = False
    if len(recent) >= 20:
        lows = [bar.low for bar in recent[-20:]]
        # 找三个低点
        first_part = lows[:7]
        middle_part = lows[7:14]
        last_part = lows[14:]
        if first_part and middle_part and last_part:
            min1 = min(first_part)
            min2 = min(middle_part)
            min3 = min(last_part)
            # 中间低点最低，两边低点接近
            if min1 > 0 and min2 < min1 and min2 < min3 and abs(min1 - min3) / min1 < 0.03:
                has_head_shoulders_bottom = True

    return {
        'has_pocket_pivot': has_pocket_pivot,
        'has_shooting_star': has_shooting_star,
        'has_big_red_bar': has_big_red_bar,
        'has_double_bottom': has_double_bottom,
        'has_head_shoulders_bottom': has_head_shoulders_bottom
    }


def fetch_basic_data(code: str, fetcher: DataFetcher, tushare_token: str = None) -> dict:
    """
    获取基础数据和指标

    Args:
        code: 股票代码
        fetcher: 数据获取器
        tushare_token: Tushare token（可选）

    Returns:
        基础数据和指标字典
    """
    # 1. 获取数据
    data = fetcher.fetch_all(code)

    if not data['quote']:
        return None

    quote = data['quote']
    fundamentals = data['fundamentals']

    # 2. 计算基础指标
    is_loss = quote.pe < 0

    # 计算复合PEG
    peg = None
    if not is_loss and len(data['quarterly_growth']) >= 2:
        peg = calculate_composite_peg(quote.pe, data['quarterly_growth'])

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

    # 4. 获取资金流向数据（带降级方案）
    north_flow = fetch_north_flow(code, tushare_token)
    margin_data = fetch_margin_data(code, tushare_token)

    # 5. 获取近期事件
    events_data = fetch_recent_events(code)

    # 6. 返回基础数据
    return {
        # 基础信息
        'code': code,
        'name': quote.name,
        'date': datetime.now().strftime("%Y-%m-%d"),

        # 行情数据
        'price': quote.price,
        'change_pct': quote.change_pct,
        'pe': quote.pe,
        'pb': quote.pb,
        'high52': quote.high52,
        'low52': quote.low52,
        'turnover_rate': quote.turnover_rate,
        'amount': quote.amount,

        # 计算指标
        'gain_250d': data['gain_250d'],
        'price_from_high': (quote.high52 - quote.price) / quote.high52 * 100 if quote.high52 > 0 else 0,
        'price_from_low': (quote.price - quote.low52) / quote.low52 * 100 if quote.low52 > 0 else 0,

        # 基本面指标
        'revenue_growth': revenue_growth,
        'profit_growth': profit_growth,
        'gross_margin': gross_margin,
        'margin_trend': margin_trend,
        'peg': peg,
        'is_loss': is_loss,

        # 资金流向数据
        'north_flow': north_flow,
        'margin_data': margin_data,

        # 近期事件
        'events': events_data,

        # 斐波那契回撤位
        'fib_levels': _calculate_fib_levels(quote.high52, quote.low52),

        # Price Action形态识别
        'price_action': _identify_price_action(data['kline']),

        # 原始基本面数据（供大模型分析）
        'fundamentals': [
            {
                'report_date': f.report_date,
                'revenue': f.revenue,
                'revenue_growth': f.revenue_growth,
                'net_profit': f.net_profit,
                'profit_growth': f.profit_growth,
                'gross_margin': f.gross_margin,
                'roe': f.roe,
                'eps': f.eps
            }
            for f in fundamentals[:4]  # 最近4期
        ] if fundamentals else [],

        # 持仓信息
        'holding': None  # 将在main函数中填充
    }


def load_tushare_token():
    """加载Tushare token"""
    token_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'config', 'tushare_token.json'
    )
    try:
        with open(token_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('token')
    except:
        return None


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python scripts/fetch_data.py <代码1> <代码2> ...")
        sys.exit(1)

    codes = sys.argv[1:]

    # 初始化
    fetcher = DataFetcher()

    # 加载Tushare token（可选）
    tushare_token = load_tushare_token()

    # 加载持仓数据
    holdings = load_holdings()
    holdings_map = {h['code']: h for h in holdings}

    # 获取所有标的数据
    results = []
    for code in codes:
        result = fetch_basic_data(code, fetcher, tushare_token)
        if result:
            # 添加持仓信息
            if code in holdings_map:
                result['holding'] = holdings_map[code]
            results.append(result)

    # 输出JSON格式
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
