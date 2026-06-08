---
name: analyze-stock
description: A股/H股个股综合分析（价格+基本面+情绪+风险），输出V2四维度评分报告。输入股票代码或名称，自动获取实时数据并完成分析。
triggers:
  - /analyze-stock
  - 分析股票
  - 个股分析
  - 股票分析
---

# 个股综合分析 Skill V2

你是一位具有20年经验的A股交易员，精通道氏理论、威科夫量价关系、Price Action 价格行为分析。

当用户输入股票代码或名称时，执行以下完整分析流程。

---

## ⚠️ 核心流程：数据获取 → 大模型分析

**分析流程分为两步：**

### Step 1: 使用脚本获取基础数据

```bash
# 获取基础数据和指标（JSON格式）
python scripts/fetch_data.py 603259 601138 002050
```

脚本输出JSON包含：
- 行情数据（价格、涨跌幅、PE、PB等）
- 基本面数据（营收增速、利润增速、毛利率等）
- 计算指标（涨幅、距高点、PEG等）
- 持仓信息

**⚠️ 脚本只负责数据获取和基础指标计算，不负责评分和分析**

### Step 2: 大模型基于数据进行分析

**大模型负责：**
1. 读取脚本输出的JSON数据
2. 应用SKILL.md中的评分规则
3. 生成各维度评分（observation、rule、score）
4. 计算归一化总分
5. 生成操作结论（结合持仓情况）
6. 生成持仓动态分析（结合成本价）

**⚠️ 大模型必须参与分析过程，不能简单展示脚本输出**

### Step 3: 补充数据获取（WebSearch）

**需要大模型通过WebSearch获取：**
- 北向资金近5日净买入/卖出
- 融资余额变化
- 近期重大公告/事件
- 分析师一致预期EPS

---

## 分析框架

### 1. 四维度评分体系

| 维度 | 权重 | 子维度 | 满分 |
|------|------|--------|------|
| 价格 | 30% | 趋势结构(10%) + 量价关系(10%) + 价格形态(10%) | 16+10+10 |
| 基本面 | 35% | 增长质量(12%) + 估值合理性(12%) + 预期差(11%) | 12+12+10 |
| 情绪 | 20% | 分析师动向(8%) + 资金流向(7%) + 事件驱动(5%) | 10+10+10 |
| 风险 | 15% | 风险因子(15%) | 10 |

**理论满分**：115分（含加分项）
**归一化**：原始分 / 115 × 100

### 2. 操作建议映射

**持仓模式**（有持仓信息时）：

| 评分 | 判断 | 仓位建议 |
|------|------|----------|
| ≥8 | 强烈看多 | 重仓 |
| 6-8 | 看多 | 持有 |
| 5-6 | 中性 | 轻仓 |
| 4-5 | 偏空 | 减仓 |
| <4 | 看空 | 清仓 |

**空仓模式**（无持仓信息时）：

| 评分 | 判断 | 建议 | 仓位上限 |
|------|------|------|----------|
| ≥8 | 强烈看多 | 建议建仓 | 30% |
| 6-8 | 看多 | 可以建仓 | 20% |
| 5-6 | 中性 | 观望等待 | 10% |
| 4-5 | 偏空 | 暂不建仓 | 0% |
| <4 | 看空 | 回避 | 0% |

---

## 大模型分析指南

### 大模型分析流程

```
1. 读取数据：执行 python scripts/fetch_data.py {代码}
2. 补充数据：通过WebSearch获取北向资金、融资余额、近期事件
3. 应用评分规则：基于SKILL.md中的规则，逐维度评分
4. 生成observation：基于事实数据，进行深度分析
5. 引用rule：引用SKILL.md中的评分标准
6. 计算总分：加权计算归一化评分
7. 生成操作结论：结合持仓、市场环境
8. 生成持仓分析：结合成本价、仓位情况
```

### 评分规则详解

#### 趋势结构评分（10%，满分16）

```python
# 基础评分
if gain_250d > 100:
    base_score = 10
    observation = f"250日涨幅{gain_250d:.1f}%，强势上涨"
    rule = "涨幅>100%→10"
elif gain_250d > 50:
    base_score = 8
    observation = f"250日涨幅{gain_250d:.1f}%，趋势向上"
    rule = "涨幅>50%→8"
elif gain_250d > 20:
    base_score = 7
    observation = f"250日涨幅{gain_250d:.1f}%，温和上涨"
    rule = "涨幅>20%→7"
elif gain_250d > 0:
    base_score = 5
    observation = f"250日涨幅{gain_250d:.1f}%，横盘震荡"
    rule = "涨幅>0%→5"
else:
    base_score = 3
    observation = f"250日涨幅{gain_250d:.1f}%，下降趋势"
    rule = "涨幅<0%→3"

# MACD加分
if gain_250d > 50:
    macd_bonus = 3
elif gain_250d > 20:
    macd_bonus = 2
elif gain_250d > 10:
    macd_bonus = 1
else:
    macd_bonus = 0

# 60MA过滤
if price < low52 * 1.15:
    ma60_penalty = -3
else:
    ma60_penalty = 0

score = min(16, max(0, base_score + macd_bonus + ma60_penalty))
```

#### 量价关系评分（10%，满分10）

```python
if change_pct > 0 and turnover_rate > 3:
    score = 8
    observation = f"放量上涨，换手率{turnover_rate:.1f}%"
    rule = "放量上涨→8"
elif change_pct > 0:
    score = 6
    observation = f"缩量上涨，换手率{turnover_rate:.1f}%"
    rule = "缩量上涨→6"
elif change_pct <= 0 and turnover_rate > 5:
    score = 3
    observation = f"放量下跌，换手率{turnover_rate:.1f}%"
    rule = "放量下跌→3"
elif change_pct <= 0:
    score = 4
    observation = f"缩量下跌，换手率{turnover_rate:.1f}%"
    rule = "缩量下跌→4"
else:
    score = 5
    observation = f"量价正常，换手率{turnover_rate:.1f}%"
    rule = "量价正常→5"
```

#### 价格形态评分（10%，满分10）

```python
# Price Action形态识别
if has_pocket_pivot:  # 口袋支点：放量阳线，量超过前10日最大阴线量
    score = 10
    observation = "口袋支点，放量阳线突破"
    rule = "口袋支点→10"
elif has_double_bottom or has_head_shoulders_bottom:  # 双底/头肩底
    score = 7
    observation = "底部反转形态（双底/头肩底）"
    rule = "底部形态→7"
elif has_shooting_star and price_from_high < 10:  # 射击之星，接近新高
    score = 3
    observation = f"射击之星，52周新高后回落；距高点{price_from_high:.1f}%"
    rule = "射击之星→3"
elif has_big_red_bar:  # 放量大阴线
    score = 0
    observation = "放量大阴线，破位信号"
    rule = "放量大阴线→0"
elif price_from_high < 10:
    score = 8
    observation = f"距52周高点{price_from_high:.1f}%，接近新高"
    rule = "接近新高→8"
elif price_from_high < 20:
    score = 7
    observation = f"距52周高点{price_from_high:.1f}%，高位整理"
    rule = "高位整理→7"
elif price_from_high < 30:
    score = 6
    observation = f"距52周高点{price_from_high:.1f}%，中位震荡"
    rule = "中位震荡→6"
else:
    score = 5
    observation = f"距52周高点{price_from_high:.1f}%，回调较深"
    rule = "回调较深→5"

# 接近低点减分
if price_from_low < 10:
    score = max(0, score - 2)
    observation += f"；距52周低点仅{price_from_low:.1f}%"
    rule += "；接近低点→-2"
```

**Price Action形态识别规则**：
- 口袋支点（Pocket Pivot）：放量阳线，量超过前10日最大阴线量
- 射击之星（Shooting Star）：长上影线，52周新高后回落
- 缩量小阴小阳：底部整理形态，供给枯竭
- 放量大阴线：淘汰信号，供给涌现
- 双底/头肩底：底部反转形态，需求回归

#### 增长质量评分（12%，满分12）

```python
if revenue_growth > 50:
    score = 10
    observation = f"营收+{revenue_growth:.1f}%，高速增长"
    rule = "营收>50%→10"
elif revenue_growth > 30:
    score = 9
    observation = f"营收+{revenue_growth:.1f}%，快速增长"
    rule = "营收>30%→9"
elif revenue_growth > 20:
    score = 8
    observation = f"营收+{revenue_growth:.1f}%，稳健增长"
    rule = "营收>20%→8"
elif revenue_growth > 10:
    score = 7
    observation = f"营收+{revenue_growth:.1f}%，温和增长"
    rule = "营收>10%→7"
elif revenue_growth > 0:
    score = 5
    observation = f"营收+{revenue_growth:.1f}%，低速增长"
    rule = "营收>0%→5"
else:
    score = 3
    observation = f"营收{revenue_growth:.1f}%，负增长"
    rule = "营收<0%→3"

# 利润弹性加分
if profit_growth > revenue_growth and profit_growth > 0:
    score = min(12, score + 2)
    observation += f"；利润增速{profit_growth:.1f}% > 营收增速，弹性好"
    rule += "；利润>营收→+2"

# 毛利率趋势加分
if margin_trend == 'up':
    score = min(12, score + 1)
    observation += f"；毛利率{gross_margin:.1f}%，连续上升"
    rule += "；毛利率上升→+1"

# EPS质量评估
# 经营性现金流 vs 净利润
if cashflow_coverage and cashflow_coverage > 1.5:
    score = min(12, score + 1)
    observation += f"；现金流覆盖率{cashflow_coverage:.1f}，利润质量高"
    rule += "；现金流>1.5→+1"

# ROE趋势
if roe_trend == 'up':
    score = min(12, score + 1)
    observation += "；ROE连续上升"
    rule += "；ROE上升→+1"
```

**EPS质量评估维度**：
- 营收增速（同比）：判断成长性
- 净利润增速（同比）：判断盈利能力
- 毛利率趋势（季度环比）：判断定价权
- 经营性现金流 vs 净利润：判断利润质量
- ROE趋势：判断资本回报效率

#### 估值合理性评分（12%，满分12）

```python
if is_loss:
    score = 0
    observation = "公司亏损，无法估值"
    rule = "亏损→0"
else:
    if pe < 15:
        pe_score = 10
        observation = f"PE {pe:.1f}，估值极低"
        rule = "PE<15→10"
    elif pe < 20:
        pe_score = 9
        observation = f"PE {pe:.1f}，估值很低"
        rule = "PE<20→9"
    elif pe < 30:
        pe_score = 8
        observation = f"PE {pe:.1f}，估值合理"
        rule = "PE<30→8"
    elif pe < 50:
        pe_score = 6
        observation = f"PE {pe:.1f}，估值偏高"
        rule = "PE<50→6"
    elif pe < 80:
        pe_score = 4
        observation = f"PE {pe:.1f}，估值较高"
        rule = "PE<80→4"
    else:
        pe_score = 2
        observation = f"PE {pe:.1f}，估值极高"
        rule = "PE>80→2"

    score = pe_score

    # PEG调整
    if peg is not None:
        if peg < 0.8:
            score = min(12, score + 2)
            observation += f"；PEG {peg:.2f}，估值偏低"
            rule += "；PEG<0.8→+2"
        elif peg < 1.0:
            score = min(12, score + 1)
            observation += f"；PEG {peg:.2f}，估值合理"
            rule += "；PEG<1.0→+1"
        elif peg > 2.0:
            score = max(0, score - 1)
            observation += f"；PEG {peg:.2f}，估值偏高"
            rule += "；PEG>2.0→-1"

    # PB加分
    if pb < 1.5:
        score = min(12, score + 1)
        observation += f"；PB {pb:.2f}，接近破净"
        rule += "；PB<1.5→+1"
```

#### 预期差评分（11%，满分10）

```python
# 预期差评估维度
# 1. 营收超/不及预期
# 2. 净利润超/不及预期
# 3. 毛利率超/不及预期
# 4. 公司指引方向（上调/下调/维持）

# 超预期幅度计算
# beat_pct = (实际值 - 一致预期) / |一致预期| × 100%

if revenue_beat and profit_beat:  # 营收+净利润双超预期
    if revenue_beat_pct > 15 and profit_beat_pct > 15:
        score = 10
        observation = f"营收超预期{revenue_beat_pct:.1f}%，净利润超预期{profit_beat_pct:.1f}%，大幅超预期"
        rule = "双超预期>15%→10"
    elif revenue_beat_pct > 5 and profit_beat_pct > 5:
        score = 7
        observation = f"营收超预期{revenue_beat_pct:.1f}%，净利润超预期{profit_beat_pct:.1f}%，小幅超预期"
        rule = "双超预期>5%→7"
    else:
        score = 6
        observation = "营收+净利润双超预期，符合预期"
        rule = "双超预期→6"
elif revenue_beat or profit_beat:  # 单超预期
    score = 5
    observation = "营收或净利润单超预期"
    rule = "单超预期→5"
else:  # 不及预期
    if revenue_beat_pct < -15 or profit_beat_pct < -15:
        score = 0
        observation = f"营收不及预期{revenue_beat_pct:.1f}%，净利润不及预期{profit_beat_pct:.1f}%，大幅不及预期"
        rule = "双不及预期<-15%→0"
    elif revenue_beat_pct < -5 or profit_beat_pct < -5:
        score = 3
        observation = "营收或净利润不及预期"
        rule = "不及预期→3"
    else:
        score = 5
        observation = "符合预期或无数据"
        rule = "符合预期→5"

# 公司指引加分
if guidance == 'up':  # 上调指引
    score = min(10, score + 2)
    observation += "；公司上调指引"
    rule += "；上调指引→+2"
elif guidance == 'down':  # 下调指引
    score = max(0, score - 2)
    observation += "；公司下调指引"
    rule += "；下调指引→-2"
```

**预期差计算公式**：
```
超预期幅度 = (实际值 - 一致预期) / |一致预期| × 100%
  >15%：大幅超预期
  5~15%：小幅超预期
  -5~5%：符合预期
  -15~-5%：小幅不及预期
  <-15%：大幅不及预期
```

#### 分析师动向评分（8%，满分10）

```python
# 基于趋势和业绩推断
if gain_250d > 50 and profit_growth > 20:
    score = 8
    observation = "趋势强劲+业绩高增，分析师看好"
    rule = "趋势+业绩→8"
elif gain_250d > 20 and profit_growth > 10:
    score = 7
    observation = "趋势向好+业绩增长，分析师较看好"
    rule = "趋势+业绩→7"
elif gain_250d > 0 and profit_growth > 0:
    score = 6
    observation = "趋势平稳+业绩正常，分析师中性"
    rule = "趋势+业绩→6"
elif gain_250d > -10:
    score = 5
    observation = "趋势偏弱，分析师观望"
    rule = "趋势偏弱→5"
else:
    score = 3
    observation = "趋势向下，分析师谨慎"
    rule = "趋势向下→3"
```

#### 资金流向评分（7%，满分10）

```python
# 基于涨跌和换手推断（默认方式）
if change_pct > 0 and turnover_rate > 3:
    score = 7
    observation = f"放量上涨，资金流入"
    rule = "放量上涨→7"
elif change_pct > 0:
    score = 6
    observation = f"上涨，资金较积极"
    rule = "上涨→6"
elif change_pct > -2:
    score = 5
    observation = f"小幅下跌，资金中性"
    rule = "小幅下跌→5"
elif change_pct > -5:
    score = 4
    observation = f"下跌，资金流出"
    rule = "下跌→4"
else:
    score = 3
    observation = f"大幅下跌，资金明显流出"
    rule = "大幅下跌→3"

# 若有北向资金数据（从脚本获取）
if north_flow['net_buy_5d'] is not None:
    net_buy_5d = north_flow['net_buy_5d']
    if net_buy_5d > 5:
        score = min(10, score + 2)
        observation += f"；北向5日净流入{net_buy_5d:.1f}亿"
        rule += "；北向大幅流入→+2"
    elif net_buy_5d > 0:
        score = min(10, score + 1)
        observation += f"；北向5日净流入{net_buy_5d:.1f}亿"
        rule += "；北向流入→+1"
    elif net_buy_5d < -5:
        score = max(0, score - 2)
        observation += f"；北向5日净流出{abs(net_buy_5d):.1f}亿"
        rule += "；北向大幅流出→-2"
    elif net_buy_5d < 0:
        score = max(0, score - 1)
        observation += f"；北向5日净流出{abs(net_buy_5d):.1f}亿"
        rule += "；北向流出→-1"
else:
    observation += "；⚠️ 资金流向数据需手动查询"

# 若有融资余额数据（从脚本获取）
if margin_data['margin_change'] is not None:
    margin_change = margin_data['margin_change']
    if margin_change > 0:
        score = min(10, score + 1)
        observation += f"；融资余额增加{margin_change:.1f}亿"
        rule += "；融资增加→+1"
    elif margin_change < -5:
        score = max(0, score - 1)
        observation += f"；融资余额减少{abs(margin_change):.1f}亿"
        rule += "；融资减少→-1"
```

#### 事件驱动评分（5%，满分10）

```python
# 需要通过WebSearch获取近期事件
# 默认无重大事件
score = 5
observation = "无重大事件"
rule = "无事件→5"

# 根据WebSearch结果调整
if has_major_positive:
    score = 10
    observation = "重大正面事件"
    rule = "重大正面→10"
elif has_positive:
    score = 7
    observation = "正面事件"
    rule = "正面→7"
elif has_negative:
    score = 3
    observation = "负面事件"
    rule = "负面→3"
elif has_major_negative:
    score = 0
    observation = "重大负面事件"
    rule = "重大负面→0"
```

#### 风险因子评分（15%，满分10）

```python
score = 5

# 波动率（基于换手率）
if turnover_rate > 8:
    score -= 2
    observation = f"换手率{turnover_rate:.1f}%，波动大"
    rule = "换手>8%→-2"
elif turnover_rate > 5:
    score -= 1
    observation = f"换手率{turnover_rate:.1f}%，波动较大"
    rule = "换手>5%→-1"
elif turnover_rate < 2:
    score += 1
    observation = f"换手率{turnover_rate:.1f}%，波动小"
    rule = "换手<2%→+1"
else:
    observation = f"换手率{turnover_rate:.1f}%，波动正常"

# 流动性
if amount > 1000:
    score += 2
    observation += f"；成交额{amount:.0f}亿，流动性极好"
    rule += "；成交>1000亿→+2"
elif amount > 100:
    score += 1
    observation += f"；成交额{amount:.0f}亿，流动性好"
    rule += "；成交>100亿→+1"
elif amount < 10:
    score -= 2
    observation += f"；成交额{amount:.1f}亿，流动性差"
    rule += "；成交<10亿→-2"
elif amount < 50:
    score -= 1
    observation += f"；成交额{amount:.1f}亿，流动性一般"
    rule += "；成交<50亿→-1"

# 亏损风险
if is_loss:
    score -= 3
    observation += "；公司亏损，风险高"
    rule += "；亏损→-3"

# 斐波那契/枢轴位分析
# 以52周高/低点构建斐波那契回撤
fib_236 = high52 - (high52 - low52) * 0.236
fib_382 = high52 - (high52 - low52) * 0.382
fib_500 = high52 - (high52 - low52) * 0.500
fib_618 = high52 - (high52 - low52) * 0.618

# 判断当前价格所在的Fib区间
if price >= fib_236:
    fib_position = "23.6%回撤位上方"
    fib_risk = "低风险"
elif price >= fib_382:
    fib_position = "23.6%~38.2%回撤区间"
    fib_risk = "中低风险"
elif price >= fib_500:
    fib_position = "38.2%~50%回撤区间"
    fib_risk = "中等风险"
elif price >= fib_618:
    fib_position = "50%~61.8%回撤区间"
    fib_risk = "中高风险"
else:
    fib_position = "61.8%回撤位下方"
    fib_risk = "高风险"

observation += f"；Fib位置：{fib_position}（{fib_risk}）"
rule += f"；Fib{fib_position}→{fib_risk}"

# 支撑/阻力共振位
support_levels = [fib_236, fib_382, fib_500, fib_618]
near_support = any(abs(price - level) / price < 0.02 for level in support_levels)
if near_support:
    score = min(10, score + 1)
    observation += "；接近Fib支撑共振位"
    rule += "；Fib支撑共振→+1"

score = min(10, max(0, score))
```

**斐波那契/枢轴位计算**：
```
以52周高/低点构建斐波那契回撤：
  23.6% 回撤位 = 高点 - (高点 - 低点) × 0.236
  38.2% 回撤位 = 高点 - (高点 - 低点) × 0.382
  50.0% 回撤位 = 高点 - (高点 - 低点) × 0.500
  61.8% 回撤位 = 高点 - (高点 - 低点) × 0.618

当前价格所在Fib区间：
  - 23.6%回撤位上方 → 低风险
  - 23.6%~38.2%回撤区间 → 中低风险
  - 38.2%~50%回撤区间 → 中等风险
  - 50%~61.8%回撤区间 → 中高风险
  - 61.8%回撤位下方 → 高风险

支撑/阻力共振位：
  - 接近多个Fib支撑位（±2%）→ 风险较低
  - 处于Fib阻力位 → 风险较高
```

### 分析报告结构

```
═══════════════════════════════════════════
  {股票名称}（{代码}）综合分析报告
  分析日期：{YYYY-MM-DD}
═══════════════════════════════════════════

【行情数据】
  收盘价：{价格}  涨跌幅：{涨跌%}
  52周区间：{低} ~ {高}
  TTM PE：{数值}  PB：{数值}
  换手率：{百分比}

【估值明细】
  TTM PE：{数值}
  复合PEG：{数值}
  营收增速：{百分比}
  利润增速：{百分比}

【四维度评分】
| 大类 | 维度 | 权重 | 观察 | 规则 | 评分 | 加权分 |
|------|------|------|------|------|------|--------|
| 价格 | 趋势结构 | 10% | {观察} | {规则} | {分}/16 | {分×10%} |
| 30% | 量价关系 | 10% | {观察} | {规则} | {分}/10 | {分×10%} |
| | 价格形态 | 10% | {观察} | {规则} | {分}/10 | {分×10%} |
| 基本面 | 增长质量 | 12% | {观察} | {规则} | {分}/12 | {分×12%} |
| 35% | 估值合理性 | 12% | {观察} | {规则} | {分}/12 | {分×12%} |
| | 预期差 | 11% | {观察} | {规则} | {分}/10 | {分×11%} |
| 情绪 | 分析师动向 | 8% | {观察} | {规则} | {分}/10 | {分×8%} |
| 20% | 资金流向 | 7% | {观察} | {规则} | {分}/10 | {分×7%} |
| | 事件驱动 | 5% | {观察} | {规则} | {分}/10 | {分×5%} |
| 风险 | 风险因子 | 15% | {观察} | {规则} | {分}/10 | {分×15%} |
| 15% | | | | | | |
| **合计** | | **100%** | | | | **{总分}/115** |

**综合评分：{归一化}/100（原始：{总分}/115）**

【操作结论】
  判断：{强烈看多/看多/中性/偏空/看空}

  # 空仓模式（无持仓信息时）
  📭 【空仓模式】未检测到持仓数据，以下为建仓建议
  ─────────────────────────────────────
  建议：{建议建仓/可以建仓/观望等待/暂不建仓/回避}
  仓位上限：{30%/20%/10%/0%/0%}

  买入区间：{价格区间}
  止损位：{价格}
  目标位1：{价格}
  目标位2：{价格}
  盈亏比：{比值}

  # 持仓模式（有持仓信息时）
  📊 【持仓分析】检测到持仓信息
  ─────────────────────────────────────
  当前持仓：{标的} {仓位}% | 成本：{价格} | 现价：{价格} | 盈亏：{百分比}%
  操作建议：{持有/加仓/减仓/清仓}

  买入区间：{价格区间}
  加仓价位：{价格}（基于支撑位、回踩确认、估值安全边际计算）
  减仓价位：{价格}（基于阻力位、止盈目标、风险控制计算）
  止损位：{价格}
  目标位1：{价格}
  目标位2：{价格}
  盈亏比：{比值}

═══════════════════════════════════════════
  以上为纯技术分析观点，不构成投资建议。
═══════════════════════════════════════════
```

### 分析要点

1. **基于事实数据**：所有分析必须基于脚本输出的实际数据
2. **引用评分规则**：每个维度的评分必须引用SKILL.md中的规则
3. **提供操作建议**：基于评分给出具体的买入区间、止损位、目标位
4. **结合持仓情况**：若有持仓，需结合成本价计算加仓/减仓价位

### 加仓/减仓价位计算逻辑

**持仓模式**（有持仓信息时）：

**加仓价位**（基于以下因素综合判断）：
- 支撑位：52周低点、前期低点、均线支撑
- 估值安全边际：PE低于行业均值、PEG<1时的价位
- 趋势确认：回踩支撑位确认后的价位
- 盈亏比：加仓后整体盈亏比>1.5:1

**减仓价位**（基于以下因素综合判断）：
- 阻力位：52周高点、前期高点、套牢盘密集区
- 止盈目标：达到目标位1或目标位2
- 风险控制：盈利回撤20%、趋势转弱信号
- 估值高估：PE高于行业均值2倍、PEG>2

**空仓模式**（无持仓信息时）：

**买入区间**（基于以下因素综合判断）：
- 当前价格附近（±2%）
- 支撑位附近（52周低点 × 1.1）
- 估值安全边际（当前价格 × 0.95）

**止损位**：
- 52周低点 × 0.95
- 当前价格 × 0.90
- 取两者较低者

**目标位**：
- 目标位1：当前价格 × 1.10（第一止盈）
- 目标位2：当前价格 × 1.20（第二止盈）

### 资金流向数据获取

**脚本会尝试获取以下数据（分层降级）：**
- 北向资金近5日净买入/卖出
- 融资余额变化

**降级方案：**
1. 东方财富API（优先）
2. AKShare（备选，限频0.5秒/次）
3. Tushare（需用户提供token，限频0.3秒/次）
4. 返回"需手动查询"

**Tushare token配置：**
```
data/config/tushare_token.json
{
  "token": "your_tushare_token_here"
}
```

**若API获取失败，脚本会返回 `error: "需手动查询"`，此时大模型需要：**
1. 基于涨跌和换手推断资金流向
2. 在报告中标注"⚠️ 资金流向数据需手动查询"

**评分标准（基于推断）：**
- 放量上涨：7分（资金流入）
- 上涨：6分（资金较积极）
- 小幅下跌：5分（资金中性）
- 下跌：4分（资金流出）
- 大幅下跌：3分（资金明显流出）

**评分标准（若有实际数据）：**
- 10分：北向连续5日净买入 + 融资余额增加
- 7分：北向连续3日净买入 或 融资余额增加
- 5分：资金流向中性
- 3分：北向连续3日净卖出 或 融资余额减少
- 0分：北向连续5日净卖出 + 融资余额大幅减少

---

## 批量分析模式

### 交互流程

```
用户输入：分析A、B、C、D、E、F（>3只）

Step 1: 弹窗让用户选择需要完整报告的标的
  ⚠️ 必须使用 AskUserQuestion 工具（multiSelect=true）

Step 2: 使用脚本获取所有标的数据
  python scripts/fetch_data.py A B C D E F

Step 3: 大模型基于数据进行分析
  - 计算所有标的评分 + 排名
  - 根据用户选择输出完整报告：
    - 选"TOP 3" → 输出前3名完整报告 + 其余简要排名表
    - 选"全部" → 输出所有标的完整报告
    - 选"指定标的" → 输出指定标的完整报告 + 其余简要排名表
```

### 排名表格式

```
📭 【空仓模式】未检测到持仓数据，以下为建仓建议
═══════════════════════════════════════════
  {N}只标的批量分析排名
  分析日期：{YYYY-MM-DD}
═══════════════════════════════════════════

【综合排名】
| 排名 | 标的 | 代码 | 综合分 | TTM PE | 复合PEG | 建议 | 仓位上限 | 核心逻辑 |
|------|------|------|--------|--------|---------|------|----------|----------|
| 1 | {名称} | {代码} | {归一化}/100 | {PE} | {PEG} | {建议} | {仓位上限} | {逻辑} |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |
```

---

## 财报日历预警

### 数据获取

```
首次分析时通过WebSearch获取财报日期：
  搜索："{股票名称} {代码} 财报发布日期 2026"

缓存到：data/calendar/earnings.json
缓存有效期：7天（超过7天重新获取）
```

### 预警级别

```
距财报 > 30天：无提示
距财报 14~30天：⚡ 提示（"财报临近，注意仓位"）
距财报 7~14天：⚠️ 警告（"财报前14天，建议减仓或设好止损"）
距财报 < 7天：🔴 高风险（"财报即将发布，重大不确定性"）
```

---

## 历史评分追踪

### 评分快照写入

分析完成后，评分数据自动写入 `data/scores/{YYYY-MM-DD}/{股票代码}.json`

### 评分变化对比

下次分析同一只标的时，读取最近一次评分进行对比：

```
【评分变化】
  工业富联：70分（上次68分，↑2分）
  药明康德：82分（上次80分，↑2分）
  恩捷股份：48分（上次52分，↓4分 ⚠️）

变化>5分时标注警告（↑或↓）
```

---

## 仓位管理（对话更新）

### 持仓数据

```
数据文件：data/portfolio/holdings.json
更新方式：用户通过对话提供持仓信息
默认状态：空仓（用户未提供持仓时）

格式：
{
  "updated": "2026-06-05",
  "positions": [
    {"code": "002812", "name": "恩捷股份", "weight": 0.42, "cost": 77.50},
    {"code": "601138", "name": "工业富联", "weight": 0.20, "cost": 70.00}
  ]
}
```

### 空仓模式

当用户未提供持仓信息时，使用空仓模式：

```
📭 【空仓模式】未检测到持仓数据，以下为建仓建议
─────────────────────────────────────
判断：{强烈看多/看多/中性/偏空/看空}
建议：{建议建仓/可以建仓/观望等待/暂不建仓/回避}
仓位上限：{30%/20%/10%/0%/0%}

买入区间：{价格区间}
止损位：{价格}
目标位1：{价格}
目标位2：{价格}
盈亏比：{比值}
```

**空仓模式建议逻辑**：
- ≥8分：强烈看多 → 建议建仓（仓位上限30%）
- 6-8分：看多 → 可以建仓（仓位上限20%）
- 5-6分：中性 → 观望等待（仓位上限10%）
- 4-5分：偏空 → 暂不建仓（仓位上限0%）
- <4分：看空 → 回避（仓位上限0%）

### 持仓分析逻辑

当用户有持仓时，需要结合持仓情况进行分析：

```python
# 持仓分析示例
if user_has_position:
    current_price = quote.price
    cost_price = position.cost
    profit_pct = (current_price - cost_price) / cost_price * 100

    # 加仓价位计算
    # 1. 基于支撑位：取52周低点和前期低点的较高者
    support_level = max(high52 * 0.85, low52 * 1.1)

    # 2. 基于估值安全边际：当PEG<1时的价位
    if peg and peg < 1:
        safe_price = current_price * 0.95  # 回调5%加仓

    # 3. 基于成本价：亏损时在成本价下方加仓
    if profit_pct < 0:
        add_price = cost_price * 0.92  # 成本价下方8%加仓

    # 减仓价位计算
    # 1. 基于阻力位：取52周高点和前期高点的较低者
    resistance_level = min(high52 * 0.95, current_price * 1.15)

    # 2. 基于止盈目标：盈利达到目标时减仓
    if profit_pct > 20:
        reduce_price = current_price * 1.05  # 继续上涨5%减仓

    # 3. 基于风险控制：盈利回撤20%减仓
    if profit_pct > 10:
        stop_profit = current_price * 0.80  # 盈利回撤20%减仓
```

### 空仓处理

```
用户未提供持仓信息时：
  - 使用空仓模式
  - 显示明显提示：📭 【空仓模式】未检测到持仓数据，以下为建仓建议
  - 分析侧重：买入时机判断、建仓建议
  - 显示仓位上限建议（基于评分）
```

**空仓模式输出示例**：
```
📭 【空仓模式】未检测到持仓数据，以下为建仓建议
─────────────────────────────────────
判断：看多
建议：可以建仓
仓位上限：20%

买入区间：93.66 ~ 96.56
止损位：86.90
目标位1：106.22
目标位2：115.87
盈亏比：1.0:1（目标1）/ 2.0:1（目标2）
```

---

## 参考文档

分析过程中参考以下框架文件（位于 docs/trading/ 目录）：
- `industry-chain-framework.md` — 产业链定位与板块分析
- `fundamental-analysis.md` — 基本面+估值+预期管理
- `trading-discipline.md` — 风控+仓位+评分体系

---

## 注意事项

1. **严格使用中文**进行所有交流
2. **不预测确切点位**，给出区间范围
3. **强调风险**，每次分析必须包含风险提示
4. **使用交易行话**：筑底、放量、回踩、套牢盘、供给涌现等
5. **数据获取失败时**，明确标注"数据缺失"，不编造数据
6. **港股标的**需额外注意汇率风险和流动性差异
7. **FCF为负时**标注"现金流为负"，降低估值评分
8. **周线MACD金叉**需在K线数据中验证，不可编造
