# analyze-stock

A股/H股个股综合分析工具 — 基于道氏理论、威科夫量价关系、Price Action 的10维度评分系统。

## 功能

- 10维度综合评分（技术面45% + 基本面30% + 板块15%）
- 自动获取实时行情数据（腾讯财经API + 东方财富F10 API）
- 板块轮动分析与产业链定位
- PEG估值模型 + 低基数陷阱修正
- 操作建议（买入区间/止损/目标位）

## 使用方式

```
/analyze-stock 分析一下XXX
```

## 数据源

| 数据类型 | 优先级1 | 优先级2 | 优先级3 |
|---------|---------|---------|---------|
| 实时行情 | WebFetch 雪球 | 腾讯财经 API | 东方财富 API |
| K线历史 | 腾讯财经 K线 API | - | - |
| 基本面 | WebSearch | 东方财富 F10 API | - |

## 目录结构

```
analyze-stock/
├── skills/analyze-stock/
│   └── SKILL.md              # Skill主文件
├── docs/trading/
│   ├── fundamental-analysis.md   # 基本面+估值方法论
│   ├── trading-discipline.md     # 风控+仓位+评分体系
│   └── industry-chain-framework.md # 产业链分析框架
└── README.md
```

## 参考文档

- [基本面+估值方法论](docs/trading/fundamental-analysis.md)
- [风控+仓位+评分体系](docs/trading/trading-discipline.md)
- [产业链分析框架](docs/trading/industry-chain-framework.md)
