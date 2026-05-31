# DESIGN.md

## 项目概述

基金销售管理工具，面向资管公司内部销售团队，提供产品货架、客户管理、数据概览和 AI 智能助手四大模块。

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                       │
│  Ant Design 5 + ECharts + React Router + TypeScript      │
│  ChatChart 组件：接收 ECharts option，渲染交互式图表      │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (REST API)
┌──────────────────────▼──────────────────────────────────┐
│                   Backend (FastAPI)                       │
│                                                          │
│  ┌─────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ API 路由 │  │ 业务逻辑  │  │    AI Agent 模块       │ │
│  └────┬────┘  └─────┬────┘  └────────┬───────────────┘ │
│       │              │                │                  │
│  ┌────▼──────────────▼────┐  ┌───────▼───────────────┐ │
│  │   SQLAlchemy (ORM)     │  │  RAG Pipeline          │ │
│  └────────────┬───────────┘  │  ├─ 意图识别 (6类)    │ │
│               │              │  ├─ 混合检索           │ │
│               │              │  ├─ 重排               │ │
│               │              │  ├─ 生成 (RAG/FC)     │ │
│               │              │  └─ 图表生成管线       │ │
│  ┌────────────▼───────────┐  └───────┬───────────────┘ │
│  │      SQLite            │  ┌───────▼───────────────┐ │
│  │  (业务数据 + 聊天记录)  │  │    ChromaDB           │ │
│  └────────────────────────┘  │  (向量知识库)          │ │
│                              └───────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## 技术选型与理由

| 层级 | 选型 | 理由 |
|------|------|------|
| 前端框架 | React 18 + TypeScript | 类型安全，生态成熟，面试展示效果好 |
| UI 组件库 | Ant Design 5 | 金融后台标准选择，表格/表单/图表组件丰富 |
| 图表 | ECharts (echarts-for-react) | 金融图表支持好（K线、面积图），定制能力强 |
| 后端框架 | FastAPI | 异步原生，自动生成 API 文档，Python 生态方便集成 AI |
| ORM | SQLAlchemy 2.0 (async) | 成熟稳定，async 支持完善 |
| 数据库 | SQLite | 零配置，评审者 clone 即跑，笔试项目数据量不需要 PG/MySQL |
| 向量数据库 | ChromaDB | 纯 Python，零配置本地存储，和 SQLite 理念一致 |
| LLM | DeepSeek (OpenAI 兼容格式) | 性价比高，支持 Function Calling |

## AI Agent 架构

### 三层意图识别

```
用户输入
  │
  ▼ Layer 1: 关键词规则（<1ms）
  │   命中 → 直接返回
  │
  ▼ Layer 2: Embedding 相似度（~10ms）
  │   预设示例句向量化，余弦相似度 > 0.65 → 返回
  │
  ▼ Layer 3: LLM 分类（~500ms）
      让模型输出 {"intent": "xxx"} 兜底
```

支持 6 种意图：
- `recommend` — 为客户推荐基金
- `fund_query` — 查询基金产品信息
- `customer` — 查询客户信息、录入跟进记录
- `market` — 市场行情分析
- `chart` — 生成数据可视化图表
- `chat` — 闲聊兜底

设计意图：大部分请求在 L1/L2 解决（快且免费），模糊表达才走 LLM。三层递进，命中即停。

### 混合检索 + 重排

```
向量检索（语义相似度）──┐
                        ├─ RRF 融合 → 规则重排 → Top N
BM25 检索（关键词匹配）──┘
```

- **向量检索**：覆盖模糊表达（"稳健一点的" → risk_level=medium）
- **BM25**：覆盖精确名称（"华夏成长混合" → 精确匹配）
- **RRF 融合**：按排名倒数加权合并，不需要归一化分数
- **规则重排**：根据意图和 query 内容给业务相关结果加分

### 双路径生成

```
检索结果置信度 >= 0.4？
  ├─ Yes → RAG 路径：用检索到的 context 生成回答
  └─ No  → Function Calling 路径：LLM 调工具查 SQL 获取精确数据

意图 == CHART？
  └─ 走独立的图表生成管线（见下方）
```

Function Calling 工具集：
- `search_funds_by_type` — 按类型查基金
- `get_fund_by_name` — 按名称查基金详情
- `get_customer_info` — 查客户信息
- `get_customer_holdings` — 查客户持仓明细
- `add_follow_up` — 录入跟进记录（AI 辅助录入）
- `query_chart_data` — 查询图表数据（支持产品分布/销售趋势/客户风险/净值走势）

### 自然语言驱动 Dashboard（动态图表生成）

用户通过对话描述图表需求，Agent 动态生成可交互的 ECharts 图表，内联显示在聊天中。

```
用户："帮我生成一个按产品类型分组的饼图"
  │
  ▼ 意图识别 → CHART
  │
  ▼ Step 1: LLM 决策查询参数
  │   强制调用 query_chart_data 工具
  │   → 查 SQLite 聚合数据，返回结构化 JSON
  │
  ▼ Step 2: LLM 生成 ECharts option
  │   输入：用户需求 + 原始数据
  │   输出：完整的 ECharts option JSON
  │
  ▼ 后端解析 JSON，通过 API 的 chart 字段返回
  │
  ▼ 前端 ChatChart 组件接收 option，调用 echarts.setOption() 渲染
```

支持的图表数据维度：
- `product_distribution` — 按基金类型分组统计数量
- `sales_trend` — 按时间段统计交易金额（支持 day/week/month 粒度）
- `customer_risk` — 客户风险偏好分布
- `nav_history` — 指定基金的净值走势（默认 30 天）

设计决策：
- 两步分离（查数据 + 生成配置），而非让 LLM 在一次对话中同时完成。分离后每步 prompt 更专注，JSON 生成成功率更高。
- 前端用 `echarts.init` 命令式渲染（与 Dashboard 页一致），不引入 echarts-for-react wrapper。
- 图表数据不持久化到聊天记录（避免 DB 膨胀），历史消息只保留文字描述。

### 多轮对话记忆

- 按 conversation_id 持久化到 SQLite
- 滑动窗口：保留最近 10 轮原文
- 超出时 LLM 压缩旧消息为摘要
- 按 user_id（浏览器指纹）隔离不同用户

## 数据模型

```
Fund ──1:N── NAVHistory
Fund ──1:N── Holding ──N:1── Customer
Fund ──1:N── Transaction ──N:1── Customer
Customer ──1:N── FollowUp
```

核心实体：基金产品、客户、持仓、交易记录、净值历史、跟进记录、聊天消息。

## 关键设计决策

### 1. SQLite + ChromaDB 双写同步

写入时同时更新 SQLite（结构化数据）和 ChromaDB（语义向量）。查询时优先走向量检索，置信度不够时 fallback 到 SQL 精确查询。

**权衡**：增加了写入复杂度，但保证了 AI 助手既能做语义匹配又能查精确数据。

### 2. 意图识别三层递进而非单一 LLM

**权衡**：多了代码复杂度，但减少了 90% 的 LLM 调用（大部分请求在 L1/L2 解决），降低延迟和成本。

### 3. RRF 融合而非加权分数

向量距离和 BM25 分数量纲不同，直接加权需要归一化（不稳定）。RRF 只看排名，简单鲁棒。

### 4. Function Calling 兜底而非纯 RAG

纯 RAG 只能返回向量库里的文档片段，无法回答"李明具体持有哪些基金、赚了多少"这类需要精确计算的问题。Function Calling 让 AI 能直接查 SQL 做实时计算。

### 5. 浏览器指纹隔离而非登录系统

笔试项目不需要完整的认证体系。用 localStorage UUID 模拟用户隔离，面试官打开是干净的，开发者能保留自己的聊天记录。

## 未来改进方向

1. **向量模型升级**：当前用 all-MiniLM-L6-v2（英文模型），换 bge-base-zh-v1.5 中文效果更好
2. **RAG 评估体系**：构造 QA 测试集，量化召回率/准确率/Answer Relevancy
3. **Cross-Encoder 重排**：用 bge-reranker 替代规则重排，更准确
4. **流式输出**：SSE 流式返回 AI 回答，提升体验
5. **图表交互增强**：支持用户追问修改图表（如"换成柱状图"、"只看最近 7 天"），基于对话上下文动态调整

## 项目结构

```
fund-sales-tool/
├── frontend/                # React 前端
│   └── src/
│       ├── components/      # 通用组件（Layout, StatCard, ChatChart）
│       ├── pages/           # 页面（Dashboard, Products, Customers, AIAssistant）
│       ├── services/        # API 调用层
│       └── types/           # TypeScript 类型
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── api/             # 路由（funds, customers, dashboard, ai_agent, follow_ups）
│       ├── models/          # SQLAlchemy 模型
│       ├── schemas/         # Pydantic 请求/响应模型
│       ├── services/rag/    # AI Agent 核心
│       │   ├── intent.py    # 三层意图识别（6 种意图）
│       │   ├── hybrid_retrieval.py  # 混合检索 + 重排
│       │   ├── vector_store.py      # ChromaDB 操作
│       │   ├── tools.py     # Function Calling 工具集（含图表数据查询）
│       │   ├── memory.py    # 多轮对话记忆
│       │   └── generation.py # 生成编排（RAG/FC/Chart 三路径）
│       └── db/              # 数据库连接 + seed
├── docker-compose.yml       # 一键启动
├── Makefile                 # 开发命令
└── README.md
```

## 启动方式

```bash
# Docker（推荐）
cp .env.example .env && docker-compose up

# 本地开发
make setup && make dev
```
