# DESIGN.md

## 1. 需求分析

### 场景理解

面向资管公司内部销售团队的效率工具。销售人员日常需要：查产品信息、管理客户、跟踪业绩、与客户沟通后记录跟进。传统方式靠 Excel + CRM 手动操作，效率低。

核心诉求是用 AI 降低操作门槛——销售人员用自然语言就能完成查数据、做分析、记录跟进这些原本需要多步操作的事。

### 做了什么，为什么

| 模块 | 功能 | 为什么做 |
|------|------|----------|
| 产品货架 | 基金列表、详情、净值走势 | 销售的基本工具，需要快速查产品信息 |
| 客户管理 | 客户列表、持仓、跟进记录 | 了解客户画像才能做精准推荐 |
| 数据概览 | 统计卡片、销售趋势、产品分布 | 管理层和销售都需要看整体数据 |
| AI 助手 | 对话式查询 + 推荐 + 跟进录入 | 核心差异点：把多步操作压缩为一句话 |
| 动态图表 | 自然语言描述 → 生成可交互图表 | 让非技术人员也能自助做数据分析 |

### 认为重要但没做的

- **流式输出**：当前 AI 回复等待时间 3-8 秒，体验不好。SSE 流式可以边生成边显示。
- **RAG 评估体系**：没有量化测试集，无法衡量检索质量。
- **权限体系**：真实场景需要区分销售/主管/管理员角色。
- **中文 Embedding 模型**：当前用英文模型 all-MiniLM-L6-v2，中文语义匹配有损失。

### 再给 2 天优先做什么

1. SSE 流式输出（体验提升最明显）
2. 换 bge-base-zh-v1.5 中文向量模型 + 构建 QA 评估测试集
3. 图表的追问修改能力（"换成柱状图"、"只看最近 7 天"）

---

## 2. 技术选型

| 层级 | 选型 | 为什么选它 | 不选什么 |
|------|------|-----------|----------|
| 前端框架 | React 18 + TypeScript | 类型安全，组件化彻底，Hooks 模式下状态管理简洁，社区生态和三方库丰富 | Vue 组合式 API 也不错但 TS 深度集成稍弱 |
| UI 组件库 | Ant Design 5 | 金融后台标准选择，表格/表单组件完善 | Material UI 偏 C 端风格 |
| 图表 | ECharts | 金融图表支持好，AI 生成 option JSON 生态完善 | Chart.js 配置能力弱 |
| 后端框架 | FastAPI | 异步原生，自动 API 文档，Python 生态方便接 AI | Flask 没有 async；Django 太重 |
| ORM | SQLAlchemy 2.0 (async) | 成熟稳定 | Tortoise ORM 社区小 |
| 数据库 | SQLite | 零配置，clone 即跑 | PG/MySQL 需要额外安装 |
| 向量数据库 | ChromaDB | 纯 Python，零配置 | Milvus/Qdrant 需要独立部署 |
| LLM | DeepSeek | 性价比高，支持 Function Calling，国内可访问 | GPT-4 贵且国内不稳定 |

### 架构图

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
│               │              │  ├─ 混合检索 + 重排    │ │
│               │              │  ├─ 生成 (RAG/FC)     │ │
│               │              │  └─ 图表生成管线       │ │
│  ┌────────────▼───────────┐  └───────┬───────────────┘ │
│  │      SQLite            │  ┌───────▼───────────────┐ │
│  │  (业务数据 + 聊天记录)  │  │    ChromaDB           │ │
│  └────────────────────────┘  │  (向量知识库)          │ │
│                              └───────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### AI Agent 核心设计

**三层意图识别**（命中即停）：
1. 关键词规则（<1ms）→ 覆盖明确表达
2. Embedding 相似度（~10ms）→ 覆盖模糊表达
3. LLM 分类（~500ms）→ 兜底复杂表达

**混合检索**：向量检索 + BM25，RRF 融合后规则重排。

**三路径生成**：
- RAG 路径：检索置信度够 → 直接基于 context 生成
- Function Calling 路径：置信度不够 → LLM 调工具查 SQL
- Chart 路径：图表意图 → 查数据 + 生成 ECharts option JSON

**动态图表生成**：两步分离架构。Step 1 让 LLM 决定查什么数据（强制调用 query_chart_data 工具），Step 2 用数据 + 用户需求让 LLM 生成 ECharts option。分离后每步 prompt 更专注，JSON 生成成功率高。

---

## 3. AI 协作日志

### 使用 AI 的环节

- 项目架构设计和技术选型讨论
- 数据模型设计和 seed 数据生成
- RAG Pipeline 实现（意图识别、混合检索、重排算法）
- Function Calling 工具集实现
- 前端页面和组件代码
- 动态图表生成功能（从设计到实现）
- 服务器部署和问题排查

### Prompt → 输出 → 采纳过程

**案例 1：动态图表生成的架构设计**

Prompt：
> 用户通过对话描述需求（如"帮我生成一个按产品类型分组的规模占比饼图"），Agent 动态生成对应的可视化图表，你有什么思路吗

AI 输出了两个方案：
1. 直接让 LLM 输出完整 ECharts option JSON（灵活但可能生成非法配置）
2. LLM 只输出结构化参数，后端用模板拼 option（稳定但灵活度低）

我的决策：选了方案 1，但实际落地时发现 DeepSeek 在 agent loop 里不会主动输出 chart-json 代码块——它把工具返回的数据当成最终结果就结束了。于是改为**两步分离架构**：第一步强制调用工具查数据，第二步单独做一次 LLM 调用专门生成 ECharts option。这不是 AI 建议的方案，是实测后的调整。

**案例 2：服务器 SQLite 版本问题**

Prompt：
> 后端启动报错 RuntimeError: Your system has an unsupported version of sqlite3. Chroma requires sqlite3 >= 3.35.0

AI 建议安装 pysqlite3-binary 并在 main.py 顶部做 monkey-patch：
```python
__import__("pysqlite3")
import sys
sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
```

采纳：直接用了这个方案，比编译 SQLite 或升级系统简单得多。但后续每次重新部署 backend 目录时都要记得重新注入这段 patch，踩了两次坑。

### AI 帮到最多的地方

服务器环境问题排查。Docker Hub 被墙、镜像源失效、SSH 密钥配置、SQLite 版本不兼容——这些琐碎的 DevOps 问题 AI 能快速给出多种备选方案，省了大量搜索时间。

### AI 最帮不上忙的地方

LLM 的 prompt 调优。AI 建议的 prompt 格式（让 DeepSeek 输出 chart-json 代码块）在实际调用中根本不生效，DeepSeek 直接忽略了格式要求。最终靠拆分成两步独立调用解决，这个判断需要实测而非 AI 建议。

---

## 4. 自我复盘

### 已知但来不及修的问题

1. **AI 回复延迟**：图表生成需要两次 LLM 调用，加上工具查 SQL，总耗时 5-10 秒。没有流式输出，用户体验差。
2. **Embedding 模型是英文的**：all-MiniLM-L6-v2 对中文的语义理解有损失，导致 Layer 2 意图识别和向量检索的召回不够准。
3. **图表生成偶尔失败**：DeepSeek 有时返回非法 JSON（尾逗号、注释），当前只做了 fallback 到纯文字，没有重试。
4. **crypto.randomUUID 兼容性**：HTTP 环境不支持，已改为手写 UUID 生成函数，但属于临时修复。

### 如果是真实企业项目，会做哪些不同的决策

1. **数据库换 PostgreSQL**：SQLite 不支持并发写入，生产环境必然出问题。
2. **加认证和权限**：JWT + RBAC，区分销售/主管/管理员，数据按团队隔离。
3. **LLM 调用加缓存和限流**：相同查询缓存结果，防止 API 调用量爆炸。
4. **向量模型换中文专用**：bge-base-zh-v1.5 或 m3e-base，显著提升检索质量。
5. **前后端分离部署**：前端走 CDN，后端容器化，加负载均衡和健康检查。
6. **可观测性**：接入日志系统、链路追踪、LLM 调用监控（token 消耗、延迟分位）。
7. **评估驱动开发**：先建 RAG 评估测试集，再迭代检索和生成策略，而非靠直觉调参。

---

## 附：项目结构

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

## 附：启动方式

```bash
# 本地开发
make setup && make dev

# 服务器部署（直接运行，不依赖 Docker）
# 前端：vite build → nginx 托管静态文件
# 后端：python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
