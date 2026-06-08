# 评分计算库

标准化的股票评分计算模块，基于V2四维度框架。

## 模块结构

```
lib/
├── __init__.py      # 包入口
├── scoring.py       # 评分计算模块
├── data_fetcher.py  # 数据获取模块
└── utils.py         # 工具函数
```

## 快速使用

### 命令行

```bash
# 分析单只股票
python scripts/analyze.py 002050

# 分析多只股票
python scripts/analyze.py 002050 603186 601138
```

### Python代码

```python
from lib import StockScorer, DataFetcher

# 初始化
scorer = StockScorer()
fetcher = DataFetcher()

# 获取数据
data = fetcher.fetch_all('002050')

# 计算评分
score = scorer.score_stock(
    code='002050',
    name='三花智控',
    price=47.51,
    change_pct=1.06,
    pe=48.92,
    pb=6.13,
    high52=51.71,
    low52=42.31,
    turnover_rate=5.47,
    amount=1750.36,
    gain_250d=86.24,
    revenue_growth=22.15,
    profit_growth=35.28
)

print(f"综合评分：{score.total_normalized}/100")
print(f"判断：{score.suggestion}")
```

## 评分框架

### 四维度权重

| 维度 | 权重 | 子维度 |
|------|------|--------|
| 价格 | 30% | 趋势结构(10%) + 量价关系(10%) + 价格形态(10%) |
| 基本面 | 35% | 增长质量(12%) + 估值合理性(12%) + 预期差(11%) |
| 情绪 | 20% | 分析师动向(8%) + 资金流向(7%) + 事件驱动(5%) |
| 风险 | 15% | 风险因子(15%) |

### 评分范围

- 理论满分：115分（含加分项）
- 理论最低：0分
- 归一化：原始分 / 115 × 100

### 操作建议

| 评分 | 判断 | 仓位建议 |
|------|------|----------|
| ≥8 | 强烈看多 | 重仓 |
| 6-8 | 看多 | 持有 |
| 5-6 | 中性 | 轻仓 |
| 4-5 | 偏空 | 减仓 |
| <4 | 看空 | 清仓 |

## 数据存储

评分数据自动保存到：
```
data/scores/{date}/{code}.json
```

## 注意事项

1. **评分一致性**：使用标准化模块确保不同session评分一致
2. **数据完整性**：数据获取失败时会标注"数据缺失"
3. **PEG计算**：使用复合PEG（几何平均4季度增速）
4. **FCF降级**：5级降级方案确保数据获取
