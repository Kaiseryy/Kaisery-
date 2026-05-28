# Gemini Fullstack LangGraph Quickstart 技术文档

## 1. 项目概述

本项目是 Google Gemini 官方提供的全栈 AI 研究助手快速启动模板，基于 LangGraph 构建多步骤深度研究 Agent，前端使用 React + TypeScript，后端使用 Python + FastAPI + LangGraph，通过 Google Gemini 模型和 Google Search API 实现自动化网络调研与报告生成。

- **仓库地址**: https://github.com/google-gemini/gemini-fullstack-langgraph-quickstart
- **许可证**: MIT
- **部署路径**: `/Users/kaisery/凯kk/AI-agent/gemini-fullstack-langgraph-quickstart`

---

## 2. 项目结构

```
gemini-fullstack-langgraph-quickstart/
├── backend/                          # Python 后端
│   ├── src/agent/
│   │   ├── __init__.py               # 导出 graph 对象
│   │   ├── app.py                    # FastAPI 应用，挂载前端静态文件
│   │   ├── configuration.py          # 可配置参数模型（模型选择、查询数量、循环次数）
│   │   ├── graph.py                  # LangGraph 核心图定义（节点与边编排）
│   │   ├── prompts.py                # 各阶段 Prompt 模板
│   │   ├── state.py                  # 状态类型定义（TypedDict）
│   │   ├── tools_and_schemas.py      # Pydantic 结构化输出模型
│   │   └── utils.py                  # 工具函数（引用解析、URL 映射等）
│   ├── examples/
│   │   └── cli_research.py           # 命令行研究脚本
│   ├── langgraph.json                # LangGraph 部署配置
│   ├── pyproject.toml                # Python 项目配置与依赖
│   ├── .env.example                  # 环境变量模板
│   └── Makefile                      # 后端构建命令
├── frontend/                         # React 前端
│   ├── src/
│   │   ├── App.tsx                   # 主应用组件（流式状态管理）
│   │   ├── main.tsx                  # 入口文件
│   │   ├── global.css                # 全局样式
│   │   ├── components/
│   │   │   ├── WelcomeScreen.tsx     # 欢迎页
│   │   │   ├── ChatMessagesView.tsx  # 聊天消息视图（含 Markdown 渲染）
│   │   │   ├── InputForm.tsx         # 输入表单（Effort/Model 选择器）
│   │   │   ├── ActivityTimeline.tsx  # 研究活动时间线
│   │   │   └── ui/                   # shadcn/ui 组件库
│   │   └── lib/
│   │       └── utils.ts              # 前端工具函数
│   ├── package.json                  # Node.js 依赖
│   ├── vite.config.ts                # Vite 构建配置
│   └── tsconfig.json                 # TypeScript 配置
├── Dockerfile                        # 多阶段 Docker 构建
├── docker-compose.yml                # Docker Compose 编排（含 Redis + PostgreSQL）
├── Makefile                          # 顶层开发命令
└── README.md                         # 项目说明
```

---

## 3. 技术栈

### 3.1 后端

| 组件 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | >=3.11, <4.0 |
| Agent 框架 | LangGraph | >=0.2.6 |
| LLM 框架 | LangChain | >=0.3.19 |
| Web 框架 | FastAPI | 最新 |
| AI 模型 | Google Gemini (genai SDK) | 1.75.0 |
| LLM 集成 | langchain-google-genai | 4.2.3 |
| 结构化输出 | Pydantic | 2.13.4 |
| 部署服务 | LangGraph API / CLI | 0.8.7 / 0.4.26 |

### 3.2 前端

| 组件 | 技术 | 版本 |
|------|------|------|
| 框架 | React | 19.0.0 |
| 语言 | TypeScript | ~5.7.2 |
| 构建工具 | Vite | 6.3.4 |
| UI 库 | shadcn/ui (Radix UI) | 最新 |
| 样式 | Tailwind CSS | 4.1.5 |
| Markdown 渲染 | react-markdown | 9.0.3 |
| 路由 | react-router-dom | 7.5.3 |
| 图标 | lucide-react | 0.508.0 |
| LangGraph 客户端 | @langchain/langgraph-sdk | 0.0.74 |

### 3.3 基础设施

| 组件 | 技术 |
|------|------|
| 容器化 | Docker (多阶段构建) |
| 编排 | Docker Compose |
| 数据库 | PostgreSQL 16 |
| 缓存/队列 | Redis 6 |

---

## 4. 核心架构：LangGraph 研究 Agent 工作流

### 4.1 图结构

```
START
  │
  ▼
┌──────────────────┐
│  generate_query  │  ← 使用 Gemini 2.0 Flash 生成搜索查询
└────────┬─────────┘
         │ (并行分发 n 个查询)
         ▼
┌──────────────────┐
│  web_research    │  ← 使用 Google Search API + Gemini 执行搜索
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   reflection     │  ← 使用 Gemini 2.5 Flash 评估信息充分性
└────────┬─────────┘
         │
    ┌────┴────┐
    │ 充分?    │
    └────┬────┘
    是   │   否 → 生成跟进查询 → web_research (循环)
         ▼
┌──────────────────┐
│ finalize_answer  │  ← 使用 Gemini 2.5 Pro 生成最终报告
└────────┬─────────┘
         │
         ▼
       END
```

### 4.2 节点详解

#### generate_query（查询生成）
- **模型**: Gemini 2.0 Flash（可配置）
- **功能**: 根据用户问题生成 1~5 个多样化搜索查询
- **输出**: `SearchQueryList`（查询列表 + 理由说明）
- **配置项**: `number_of_initial_queries`（默认 3）

#### web_research（网络调研）
- **模型**: Gemini 2.0 Flash + Google Search API
- **功能**: 对每个查询执行 Google 搜索，提取并引用来源
- **输出**: 带引用标记的调研摘要 + 来源列表
- **特性**: 自动解析 URL 为短链接，插入引用标记

#### reflection（反思评估）
- **模型**: Gemini 2.5 Flash（可配置）
- **功能**: 分析已有摘要，识别知识缺口，生成跟进查询
- **输出**: `Reflection`（是否充分 + 知识缺口 + 跟进查询列表）
- **配置项**: `max_research_loops`（默认 2）

#### finalize_answer（最终回答）
- **模型**: Gemini 2.5 Pro（可配置）
- **功能**: 整合所有调研结果，生成带引用的最终报告
- **输出**: Markdown 格式的完整回答，含来源链接

### 4.3 状态管理

```python
class OverallState(TypedDict):
    messages: Annotated[list, add_messages]       # 对话消息
    search_query: Annotated[list, operator.add]   # 搜索查询列表
    web_research_result: Annotated[list, operator.add]  # 调研结果
    sources_gathered: Annotated[list, operator.add]     # 收集的来源
    initial_search_query_count: int               # 初始查询数量
    max_research_loops: int                       # 最大研究循环次数
    research_loop_count: int                      # 当前循环计数
    reasoning_model: str                          # 推理模型名称
```

---

## 5. 可配置参数

### 5.1 后端配置（`configuration.py`）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `query_generator_model` | `gemini-2.0-flash` | 查询生成模型 |
| `reflection_model` | `gemini-2.5-flash` | 反思评估模型 |
| `answer_model` | `gemini-2.5-pro` | 最终回答模型 |
| `number_of_initial_queries` | 3 | 初始搜索查询数量 |
| `max_research_loops` | 2 | 最大研究循环次数 |

### 5.2 前端 Effort 等级映射

| Effort | 初始查询数 | 最大循环数 |
|--------|-----------|-----------|
| Low | 1 | 1 |
| Medium | 3 | 3 |
| High | 5 | 10 |

### 5.3 前端可选模型

| 模型 | 标识符 |
|------|--------|
| Gemini 2.0 Flash | `gemini-2.0-flash` |
| Gemini 2.5 Flash | `gemini-2.5-flash-preview-04-17` |
| Gemini 2.5 Pro | `gemini-2.5-pro-preview-05-06` |

---

## 6. 部署与运行

### 6.1 环境要求

- Python >= 3.11
- Node.js >= 20（前端开发）
- Docker & Docker Compose（容器化部署）
- Google Gemini API Key

### 6.2 环境变量

在 `backend/.env` 中配置：

```env
GEMINI_API_KEY=your_api_key_here
```

### 6.3 本地开发

```bash
# 安装后端依赖
cd backend
pip install -e .

# 启动后端（LangGraph Dev Server）
langgraph dev

# 安装前端依赖
cd frontend
npm install

# 启动前端开发服务器
npm run dev
```

或使用 Makefile：

```bash
make dev          # 同时启动前后端
make dev-backend  # 仅启动后端
make dev-frontend # 仅启动前端
```

### 6.4 Docker 部署

```bash
# 构建镜像
docker build -t gemini-fullstack-langgraph .

# 使用 Docker Compose 启动全栈服务
GEMINI_API_KEY=your_key docker-compose up -d
```

服务端口映射：
- LangGraph API: `8123:8000`
- PostgreSQL: `5433:5432`

### 6.5 命令行使用

```bash
cd backend
python examples/cli_research.py "你的研究问题" \
  --initial-queries 3 \
  --max-loops 2 \
  --reasoning-model gemini-2.5-pro-preview-05-06
```

---

## 7. 前端架构

### 7.1 组件树

```
App
├── WelcomeScreen          # 无历史消息时展示
│   └── InputForm          # 输入框 + Effort/Model 选择器
└── ChatMessagesView       # 有历史消息时展示
    ├── HumanMessageBubble # 用户消息气泡（Markdown 渲染）
    ├── AiMessageBubble    # AI 消息气泡
    │   ├── ActivityTimeline  # 研究活动时间线
    │   └── ReactMarkdown     # Markdown 内容渲染
    └── InputForm          # 底部输入区域
```

### 7.2 流式通信

前端通过 `@langchain/langgraph-sdk` 的 `useStream` Hook 与后端建立流式连接：

- **开发环境**: `http://localhost:2024`
- **生产环境**: `http://localhost:8123`
- **事件处理**: 监听 `generate_query`、`web_research`、`reflection`、`finalize_answer` 事件，实时更新 ActivityTimeline

### 7.3 研究活动时间线

前端实时展示 Agent 执行进度：

| 事件 | 展示内容 |
|------|---------|
| `generate_query` | 生成的搜索查询列表 |
| `web_research` | 收集的来源数量和标签 |
| `reflection` | "分析调研结果" |
| `finalize_answer` | "撰写最终回答" |

---

## 8. 关键技术细节

### 8.1 引用与来源管理

- Google Search API 返回的原始 URL 较长，通过 `resolve_urls()` 映射为短链接格式：`https://vertexaisearch.cloud.google.com/id/{query_id}-{chunk_index}`
- `insert_citation_markers()` 在文本中按位置插入引用标记
- 最终回答阶段将短链接替换回原始 URL

### 8.2 并行搜索

`continue_to_web_research` 节点使用 LangGraph 的 `Send` API 将 n 个搜索查询并行分发到 n 个 `web_research` 节点实例，每个实例独立执行 Google 搜索。

### 8.3 反思循环

- 每次 `web_research` 完成后进入 `reflection` 节点
- 评估信息是否充分（`is_sufficient`）
- 不充分时生成跟进查询，再次进入 `web_research`
- 达到 `max_research_loops` 上限时强制进入 `finalize_answer`

### 8.4 FastAPI 前后端整合

`app.py` 将前端构建产物（`frontend/dist`）挂载到 `/app` 路径下，与 LangGraph API 路由共存于同一服务，实现单端口全栈部署。

---

## 9. 当前部署状态

| 项目 | 状态 |
|------|------|
| 代码克隆 | 已完成 |
| 部署路径 | `/Users/kaisery/凯kk/AI-agent/gemini-fullstack-langgraph-quickstart` |
| 后端依赖安装 | 已完成（Python 3.12，SSL_CERT_FILE 绕过证书问题） |
| 前端依赖安装 | 未完成（Node.js 未安装） |
| 环境变量配置 | `.env` 已创建，需填入 `GEMINI_API_KEY` |
| 运行状态 | 未启动 |

### 待完成事项

1. 安装 Node.js（前端构建必需）
2. 在 `backend/.env` 中填入有效的 `GEMINI_API_KEY`
3. 执行 `cd frontend && npm install && npm run build` 构建前端
4. 启动后端：`cd backend && langgraph dev`
