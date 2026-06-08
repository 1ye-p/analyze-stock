"""
工具函数模块
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional


def format_score(score: float, max_score: float = 115) -> str:
    """
    格式化评分

    Args:
        score: 原始分数
        max_score: 满分

    Returns:
        格式化字符串，如 "7/100（原始：8.05/115）"
    """
    normalized = score / max_score * 100
    return f"{normalized:.0f}/100（原始：{score:.2f}/{max_score}）"


def format_peg(peg: Optional[float]) -> str:
    """
    格式化PEG

    Args:
        peg: PEG值

    Returns:
        格式化字符串
    """
    if peg is None:
        return "N/A"
    return f"{peg:.2f}"


def format_price(price: float) -> str:
    """
    格式化价格

    Args:
        price: 价格

    Returns:
        格式化字符串
    """
    return f"{price:.2f}"


def format_percent(value: float) -> str:
    """
    格式化百分比

    Args:
        value: 百分比值

    Returns:
        格式化字符串，如 "+12.34%" 或 "-5.67%"
    """
    if value >= 0:
        return f"+{value:.2f}%"
    return f"{value:.2f}%"


def format_amount(amount: float) -> str:
    """
    格式化金额

    Args:
        amount: 金额(亿)

    Returns:
        格式化字符串
    """
    if amount >= 10000:
        return f"{amount/10000:.2f}万亿"
    elif amount >= 100:
        return f"{amount:.0f}亿"
    else:
        return f"{amount:.2f}亿"


def save_score(
    code: str,
    name: str,
    date: str,
    price: float,
    scores: Dict,
    total: float,
    pe: float,
    peg: Optional[float],
    fcf_yield: Optional[float],
    base_dir: str = "data/scores"
) -> str:
    """
    保存评分数据到文件

    Args:
        code: 股票代码
        name: 股票名称
        date: 日期
        price: 价格
        scores: 各维度评分
        total: 总分
        pe: PE
        peg: PEG
        fcf_yield: FCF Yield
        base_dir: 基础目录

    Returns:
        保存的文件路径
    """
    # 创建目录
    dir_path = os.path.join(base_dir, date)
    os.makedirs(dir_path, exist_ok=True)

    # 构建数据
    data = {
        "code": code,
        "name": name,
        "date": date,
        "price": price,
        "scores": scores,
        "total": total,
        "pe": pe,
        "peg_composite": peg,
        "ttm_pe": pe,
        "fcf_yield": fcf_yield
    }

    # 保存文件
    file_path = os.path.join(dir_path, f"{code}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return file_path


def load_last_score(
    code: str,
    current_date: str,
    base_dir: str = "data/scores"
) -> Optional[Dict]:
    """
    加载上一次评分数据

    Args:
        code: 股票代码
        current_date: 当前日期
        base_dir: 基础目录

    Returns:
        上一次评分数据，不存在返回None
    """
    # 获取所有日期目录
    if not os.path.exists(base_dir):
        return None

    dates = sorted(os.listdir(base_dir), reverse=True)

    for date in dates:
        if date >= current_date:
            continue

        file_path = os.path.join(base_dir, date, f"{code}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)

    return None


def get_price_targets(
    price: float,
    high52: float,
    low52: float,
    suggestion: str
) -> Dict:
    """
    计算价格目标

    Args:
        price: 当前价格
        high52: 52周最高
        low52: 52周最低
        suggestion: 操作建议

    Returns:
        价格目标字典
    """
    # 计算支撑位和阻力位
    support1 = low52 * 1.1
    support2 = low52 * 1.2
    resistance1 = high52 * 0.95
    resistance2 = high52 * 1.05

    # 根据建议调整
    if suggestion in ["强烈看多", "看多"]:
        buy_low = price * 0.97
        buy_high = price * 1.00
        stop_loss = price * 0.90
        target1 = price * 1.10
        target2 = price * 1.20
    elif suggestion == "中性":
        buy_low = price * 0.95
        buy_high = price * 0.98
        stop_loss = price * 0.92
        target1 = price * 1.05
        target2 = price * 1.10
    else:
        buy_low = price * 0.90
        buy_high = price * 0.95
        stop_loss = price * 0.88
        target1 = price * 1.03
        target2 = price * 1.05

    return {
        "buy_range": f"{buy_low:.2f} ~ {buy_high:.2f}",
        "stop_loss": f"{stop_loss:.2f}",
        "target1": f"{target1:.2f}",
        "target2": f"{target2:.2f}",
        "support1": f"{support1:.2f}",
        "support2": f"{support2:.2f}",
        "resistance1": f"{resistance1:.2f}",
        "resistance2": f"{resistance2:.2f}"
    }


def calculate_risk_reward(
    price: float,
    stop_loss: float,
    target1: float,
    target2: float
) -> Dict:
    """
    计算盈亏比

    Args:
        price: 买入价格
        stop_loss: 止损价
        target1: 目标1
        target2: 目标2

    Returns:
        盈亏比字典
    """
    risk = price - stop_loss
    reward1 = target1 - price
    reward2 = target2 - price

    ratio1 = reward1 / risk if risk > 0 else 0
    ratio2 = reward2 / risk if risk > 0 else 0

    return {
        "risk": f"{risk:.2f}",
        "reward1": f"{reward1:.2f}",
        "reward2": f"{reward2:.2f}",
        "ratio1": f"{ratio1:.1f}:1",
        "ratio2": f"{ratio2:.1f}:1"
    }


def get_earnings_alert(
    next_report_date: Optional[str],
    report_type: str = "中报"
) -> str:
    """
    获取财报预警

    Args:
        next_report_date: 下次财报日期 (YYYY-MM-DD)
        report_type: 财报类型

    Returns:
        预警字符串
    """
    if not next_report_date:
        return "✅ 财报日期未知，无近期风险"

    today = datetime.now()
    report_date = datetime.strptime(next_report_date, "%Y-%m-%d")
    days_left = (report_date - today).days

    if days_left < 0:
        return f"✅ {report_type}已发布，无近期风险"
    elif days_left < 7:
        return f"🔴 {report_type}即将发布（{next_report_date}，距今{days_left}天），重大不确定性"
    elif days_left < 14:
        return f"⚠️ {report_type}临近（{next_report_date}，距今{days_left}天），建议减仓或设好止损"
    elif days_left < 30:
        return f"⚡ {report_type}临近（{next_report_date}，距今{days_left}天），注意仓位"
    else:
        return f"✅ {report_type}预计{next_report_date}发布（距今{days_left}天）"
