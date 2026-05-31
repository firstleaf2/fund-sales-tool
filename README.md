# 基金销售管理工具

资管公司内部基金销售管理系统，包含产品货架、客户管理、数据概览和 AI 智能助手四大模块。

## 技术栈

- **前端**: React 18 + TypeScript + Ant Design 5 + ECharts
- **后端**: Python FastAPI + SQLAlchemy + SQLite
- **AI**: LangChain + ChromaDB + OpenAI API (RAG)

## 快速启动

### 方式一：Docker Compose（推荐）

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY（AI 功能需要，不填则使用预设回答）
docker-compose up
```

访问 http://localhost:3000

### 方式二：本地开发

```bash
# 安装依赖
make setup

# 启动开发服务器（前后端并行）
make dev
```

- 前端: http://localhost:5173
- 后端 API: http://localhost:8000/docs

## 功能模块

1. **产品货架** — 基金列表、筛选搜索、详情页含净值走势图
2. **客户管理** — 客户列表、新增编辑、持仓明细含盈亏计算
3. **数据概览** — 汇总指标卡、销售趋势图、产品占比饼图
4. **AI 助手** — 基于 RAG 的智能问答，支持客户推荐和市场分析

## 项目结构

```
fund-sales-tool/
├── frontend/          # React 前端
├── backend/           # FastAPI 后端
├── docker-compose.yml
├── Makefile
└── README.md
```
