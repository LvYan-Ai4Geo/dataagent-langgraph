# 基于LangGraph编排工作流的NL2SQL-Agent

用户输入一句自然语言问题（如"统计某地区的销售总额"），Agent 会自动完成：关键词抽取 -> 多路召回（字段/指标/字段值）-> 信息合并与过滤 -> SQL 生成 -> SQL 校验 -> （失败则自动修正）-> 执行 SQL，并通过 FastAPI 以 SSE（Server-Sent Events）流式返回各步骤进度与最终查询结果。配合基于 LangGraph Checkpointer 的短期会话记忆，支持多轮对话追问；并提供一个 Vue3 + Vite 的灵动粒子前端界面。

---

## 目录

- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [工作流详解](#工作流详解)
- [短期会话记忆](#短期会话记忆)
- [项目结构](#项目结构)
- [环境准备](#环境准备)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [接口说明](#接口说明)
- [元知识库构建](#元知识库构建)

---

## 核心特性

- **多路召回 RAG**：同时从 Qdrant（字段向量、指标向量）与 Elasticsearch（字段值全文，IK 分词）召回，覆盖 Schema 层、指标层、取值层三个维度的语义匹配。
- **LLM 关键词扩展**：每路召回前，由 LLM 根据用户问题生成针对性的扩展关键词，弥补 jieba 关键词在语义覆盖上的不足。
- **两阶段过滤**：召回后由 LLM 对指标、表/字段做精简过滤，剔除冗余信息，保证生成 SQL 时上下文最小且精准。
- **自动校验与修正**：生成的 SQL 先用 `EXPLAIN` 校验，失败时由 LLM 根据错误信息进行最小必要修复后再执行。
- **短期会话记忆**：基于 LangGraph 的 `InMemorySaver` Checkpointer，按 `thread_id` 持久化会话状态，支持多轮对话（如“再按性别细分”“改成环比”）。
- **流式输出**：基于 LangGraph 的 `stream_mode='custom'`，各节点实时推送执行进度与最终查询结果，前端可展示完整推理链路。
- **灵动粒子前端**：Vue3 + Vite 实现的独立前端，初次登录界面全屏粒子浮动 + 鼠标吸附，进入后展示自然语言2SQL 对话界面。
- **元知识离线构建**：通过脚本一次性将表/字段/指标元信息同步至 MySQL、Qdrant、ES，在线查询仅做检索不做构建。

---

## 技术栈

| 类别 | 技术 |
|------|------|
| Agent 编排 | LangGraph（含 InMemorySaver 短期记忆） |
| LLM | DeepSeek（通过 langchain init_chat_model） |
| 向量检索 | Qdrant |
| 全文检索 | Elasticsearch（IK 中文分词） |
| Embedding | BGE-large-zh-v1.5（本地 HuggingFace 模型，1024 维） |
| 关键词抽取 | jieba（TextRank） |
| 元数据/数仓 | MySQL 8.0（asyncmy 异步驱动 + SQLAlchemy 2.0） |
| Web 框架 | FastAPI（SSE 流式响应） |
| 配置管理 | OmegaConf |
| 日志 | Loguru（带 request_id 链路追踪） |
| 前端 | Vue 3 + Vite（粒子动效 + SSE 流式展示） |

---

## 系统架构

```
┌────────────────────────┐    SSE (POST /api/query)   ┌─────────────────┐
│  Vue3 前端 (粒子动效)    │ ────────────────────────▶ │  FastAPI (SSE)   │
│  Login / Chat 界面      │ ◀──────────────────────── │                  │
│  thread_id 会话标识      │   流式返回 progress/result │                  │
└────────────────────────┘                            └────────┬────────┘
                                                               │
                                                       ┌───────▼────────┐
                                                       │ QueryService    │
                                                       │ (按 thread_id    │
                                                       │  传入 checkpointer)│
                                                       └───────┬────────┘
                                                               │ graph.astream
                                               ┌───────────────▼───────────────┐
                                               │       LangGraph 工作流         │
                                               │  (12 个节点 + InMemorySaver)   │
                                               └───┬───────┬───────┬───────────┘
                                                   │       │       │
                                       ┌───────────▼┐ ┌────▼────┐ ┌▼───────────┐
                                       │  Qdrant    │ │  Meta   │ │     ES      │
                                       │(字段/指标)  │ │  MySQL  │ │(字段值全文) │
                                       └────────────┘ └─────────┘ └────────────┘
                                                       │
                                               ┌───────▼────────┐
                                               │   DW MySQL     │  ← SQL 校验与执行
                                               └────────────────┘
```

---

## 工作流详解

Agent 工作流由 12 个节点组成，定义于 `app/agent/graph.py`：

```
START
  │
  ▼
extract_keywords ──┬──────────────┬──────────────┐
 (jieba 抽关键词)   │              │              │
                    ▼              ▼              ▼
            recall_column    recall_value    recall_metric
          (Qdrant字段向量)  (ES字段值全文)  (Qdrant指标向量)
                    │              │              │
                    └──────┬───────┴──────────────┘
                           ▼
                  merge_retrieved_info
              (合并+补全表/主外键+回填取值)
                           │
                    ┌──────┴──────┐
                    ▼             ▼
              filter_metric   filter_table
            (LLM筛指标)     (LLM筛表/字段)
                    └──────┬──────┘
                           ▼
                  add_extract_context
                (注入当前日期/数据库方言)
                           │
                           ▼
                     generate_sql
                  (LLM 生成 SQL)
                           │
                           ▼
                     validate_sql
                  (EXPLAIN 校验)
                           │
              ┌────────────┴────────────┐
        error=None                 error≠None
              │                         │
              ▼                         ▼
           run_sql                 correct_sql
        (执行 SQL)             (LLM 据错误修正)
              │                         │
              │                         └─────────┐
              │                                   ▼
              │                                run_sql
              │──────────────────────────────────▶│
                                                  ▼
                                                 END
```

| 节点 | 文件 | 职责 |
|------|------|------|
| extract_keywords | `nodes/extract_keywords.py` | jieba TextRank 抽取实词关键词，并入原始 query |
| recall_column | `nodes/recall_column.py` | LLM 扩展字段关键词 → BGE 向量化 → Qdrant 检索字段 |
| recall_metric | `nodes/recall_metric.py` | LLM 扩展指标关键词 → BGE 向量化 → Qdrant 检索指标 |
| recall_value | `nodes/recall_value.py` | LLM 扩展取值关键词 → ES IK 全文匹配字段值 |
| merge_retrieved_info | `nodes/merge_retrieved_info.py` | 合并三路召回，补全关联字段/主外键，回填取值到 examples |
| filter_metric | `nodes/filter_metric.py` | LLM 从候选指标中筛选真正必需的指标 |
| filter_table | `nodes/filter_table.py` | LLM 裁剪出必需的表与字段（保留 JOIN 键） |
| add_extract_context | `nodes/add_extract_context.py` | 注入当前日期/星期/季度 + 数据库版本/方言 |
| generate_sql | `nodes/generate_sql.py` | LLM 基于全部上下文生成纯文本 SQL |
| validate_sql | `nodes/validate_sql.py` | 用 `EXPLAIN` 校验 SQL，失败则写入 error |
| correct_sql | `nodes/correct_sql.py` | LLM 根据错误信息做最小必要修复 |
| run_sql | `nodes/run_sql.py` | 真正执行 SQL 并返回结果 |

> **状态流转**：节点间通过 `DataAgentState`（TypedDict）传递状态；`DataAgentContext`（dataclass）作为依赖注入容器向各节点提供 Repository 与 Embedding 模型。`messages` 字段记录多轮历史，配合 `InMemorySaver` 按 `thread_id` 持久化，实现短期会话记忆。

---

## 短期会话记忆

Agent 通过 LangGraph 的 Checkpointer 机制实现短期会话记忆，支持多轮对话（如「再按性别细分」「改成环比」等追问）。

- **持久化方式**：`app/agent/graph.py` 编译图时传入 `InMemorySaver`（模块级单例 `memory`）。状态按 `thread_id` 存储在内存中，应用重启后清空（适合单实例部署；如需跨重启/多实例持久化，可替换为基于数据库的 Checkpointer）。
- **会话标识**：前端登录时生成随机 UUID 作为 `thread_id`（存于 localStorage），每次查询携带；后端 `QueryService` 将其放入 `config={"configurable": {"thread_id": ...}}` 传入 `graph.astream`。
- **历史上下文**：`DataAgentState.messages` 记录每轮的 query/sql/结果摘要。`extract_keywords` 节点会读取上一轮历史并拼入当前问题，使后续召回能利用多轮信息。
- **状态重置**：前端点击「重置」会清空 `thread_id` 并跳回登录页，开启新会话。

---

## 项目结构

```
data-agent/
├── main.py                          # FastAPI 应用入口
├── pyproject.toml                   # 项目依赖声明（uv 管理）
├── .env / .env_example              # 环境变量（DEEPSEEK_API_KEY）
├── conf/
│   ├── app_config.yaml              # 应用主配置（DB/Qdrant/ES/Embedding/LLM/日志）
│   ├── meta_config.yaml             # 元知识配置（表/字段/指标定义）
│   └── path_config.py               # 路径常量
├── prompts/                         # LLM 提示词模板（.prompt 文件）
│   ├── extend_keywords_for_column_recall.prompt
│   ├── extend_keywords_for_metric_recall.prompt
│   ├── extend_keywords_for_value_recall.prompt
│   ├── filter_metric_info.prompt
│   ├── filter_table_info.prompt
│   ├── generate_sql.prompt
│   └── correct_sql.prompt
├── frontend/                        # Vue3 + Vite 前端项目（独立）
│   ├── package.json / vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.vue / main.js / router/
│       ├── views/                   #   LoginView(粒子登录) / ChatView(NL2SQL)
│       ├── components/              #   ParticleBackground/ChatInput/...
│       ├── composables/useSSE.js    #   SSE 流式解析
│       └── styles/main.css
├── docker/
│   ├── docker-compose.yaml          # MySQL/ES/Qdrant/Embedding 一键部署
│   ├── mysql/                       # 元数据库与数仓库初始化 SQL
│   └── embedding/bge-large-zh-v1.5/ # BGE 本地模型文件
├── logs/                            # 运行日志输出目录
└── app/
    ├── agent/                       # Agent 核心
    │   ├── graph.py                 #   LangGraph 工作流编排（含 InMemorySaver 记忆）
    │   ├── state.py                 #   工作流状态定义（含 messages 多轮历史）
    │   ├── context.py               #   运行时依赖注入容器
    │   ├── llm.py                   #   DeepSeek LLM 单例
    │   ├── prompt/prompt_loader.py  #   prompt 模板加载器
    │   └── nodes/                   #   12 个工作流节点
    ├── api/                         # FastAPI 接口层
    │   ├── lifespan.py              #   应用生命周期（客户端初始化/释放）
    │   ├── dependencies.py          #   依赖注入 provider
    │   ├── routers/query_router.py  #   POST /api/query 路由（支持 thread_id）
    │   └── schema/query_schema.py   #   请求模型（query + thread_id）
    ├── service/                     # 业务服务层
    │   ├── query_service.py         #   在线查询服务（驱动图 + SSE + 会话记忆）
    │   └── meta_knowledge_service.py#   离线元知识库构建服务
    ├── clients/                     # 客户端管理器单例
    │   ├── qdrant_client_manager.py
    │   ├── els_client_manager.py
    │   ├── emb_client_manager.py
    │   └── mysql_client_manager.py
    ├── repositories/                # 仓储层（封装底层存储读写）
    │   ├── qdrant/                  #   字段/指标向量仓储
    │   ├── es/                      #   字段值全文仓储
    │   └── mysql/                   #   元数据库(含mappers) + 数仓库仓储
    ├── entities/                    # 领域实体（dataclass）
    ├── models/                      # SQLAlchemy ORM 模型（元数据库表）
    ├── app_config/                  # 配置加载与结构定义
    ├── core/                        # 日志、请求上下文
    └── scripts/
        └── build_meta_knowledge.py  # 元知识库构建脚本
```

---

## 环境准备

### 1. Python 环境

要求 **Python >= 3.12**，推荐使用 [uv](https://github.com/astral-sh/uv) 管理依赖：

```bash
# 安装 uv（如未安装）
pip install uv

# 安装项目依赖
uv sync
```

### 2. 启动基础设施服务

项目提供 `docker/docker-compose.yaml` 一键启动 MySQL、Elasticsearch（含 IK 分词）、Qdrant、Embedding 服务：

```bash
cd docker
docker compose up -d
```

服务端口映射：

| 服务 | 宿主端口 | 说明 |
|------|----------|------|
| MySQL | 3307 | 元数据库(meta) + 数仓库(dw)，初始化 SQL 在 docker/mysql/ |
| Elasticsearch | 9200 | 含 IK 中文分词插件 |
| Kibana | 5601 | ES 可视化（可选） |
| Qdrant | 6333 / 6334 | HTTP / gRPC |
| Embedding | 8081 | BGE 模型推理服务（容器内加载本地模型） |

> 注：当前 `emb_client_manager.py` 中 Embedding 模型路径为硬编码本地绝对路径（`G:/PythonProject/...`），若部署到其他环境需修改该路径，或改用 `conf/path_config.py` 中的 `BGE_MODEL` 常量。

### 3. 配置环境变量

复制 `.env_example` 为 `.env`，填入你的 DeepSeek API Key：

```bash
cp .env_example .env
```

```env
DEEPSEEK_API_KEY='你的_deepseek_api_key'
```

---

## 快速开始

### 步骤 1：构建元知识库（一次性，离线）

元知识库是 Agent 在线检索的前提。根据 `conf/meta_config.yaml` 中定义的表/字段/指标，将元信息同步到 MySQL、Qdrant、ES：

```bash
python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
```

执行成功后：
- MySQL `meta` 库将填充 `table_info`、`column_info`、`metric_info`、`column_metric` 表；
- Qdrant 将建立 `column_info_collection`、`metric_info_collection` 两个向量集合；
- ES 将建立 `value_index` 全文索引（含 `sync: true` 字段的全部取值）。

### 步骤 2：启动 API 服务

```bash
# 开发模式（热重载）
fastapi dev main.py

# 生产模式
fastapi run main.py
```

默认监听 `http://127.0.0.1:8000`。

### 步骤 3：启动前端（可选，推荐）

前端为独立的 Vue3 + Vite 项目，提供粒子动效登录界面与自然语言2SQL 对话界面：

```bash
cd frontend
npm install        # 首次需安装依赖
npm run dev        # 开发模式，默认 http://127.0.0.1:5173
```

开发模式下，前端的 `/api` 请求会通过 Vite 代理转发到 `http://127.0.0.1:8000`（见 `frontend/vite.config.js`），因此需同时运行后端。

生产构建：

```bash
cd frontend
npm run build      # 产物输出到 frontend/dist/
```

构建产物可由 nginx 托管，或交由 FastAPI 静态托管（见下方「部署提示」）。

> **界面说明**：初次进入为粒子浮动登录页，点击「进入系统」生成会话标识（thread_id）并跳转主界面；主界面展示进度时间线、生成的 SQL 与查询结果表格，支持多轮追问。

### 步骤 4：调用查询接口

```bash
curl -N -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "统计华北地区中男生的销售总额", "thread_id": "session-1"}'
```

返回为 SSE 流，每个 `data:` 帧为一个节点的进度或最终结果，例如：

```
data: {"type": "progress", "step": "抽取关键词", "status": "success"}
data: {"type": "progress", "step": "召回字段信息", "status": "running"}
...
data: {"type": "result", "sql": "SELECT ...", "data": [{"...": ...}]}
data: {"type": "progress", "step": "执行SQL语句", "status": "success"}
```

> 携带相同的 `thread_id` 再次请求，Agent 会基于上一轮的历史 state（query/sql/结果摘要）继续累积上下文，实现多轮对话。

---

## 配置说明

### conf/app_config.yaml

应用主配置，包含以下段落：

| 段落 | 说明 |
|------|------|
| `logging` | 日志：控制台/文件开关、级别、轮转(10MB)、保留(7天) |
| `db_meta` | 元数据库 MySQL 连接（库名 meta） |
| `db_dw` | 数仓库 MySQL 连接（库名 dw） |
| `qdrant` | Qdrant 连接 + 向量维度（BGE 为 1024） |
| `embedding` | BGE 模型配置 + 批处理大小 |
| `es` | Elasticsearch 连接 + 索引名 |
| `llm` | DeepSeek 模型名、API Key、Base URL |

> 配置通过 `app/app_config/config.py` 用 OmegaConf 加载为强类型 `object_config` 对象，全应用共享。

### conf/meta_config.yaml

元知识定义文件，描述数仓中有哪些表/字段/指标需要被 Agent 检索：

- **tables**：每张表含 `name`、`role`（dim/fact）、`description`，及其 `columns`：
  - `role`：`primary_key` / `foreign_key` / `dimension` / `measure`
  - `alias`：字段别名列表（用于向量召回扩展）
  - `sync`：是否将该字段全部取值同步到 ES 全文索引（通常仅维度字段设为 true）
- **metrics**：每个指标含 `name`、`description`、`relevant_columns`（依赖字段）、`alias`

修改该文件后需重新执行步骤 1 重建元知识库。

---

## 接口说明

### POST /api/query

自然语言查询接口，返回 SSE 流。

**请求体**：

```json
{
  "query": "统计华北地区中男生的销售总额",
  "thread_id": "session-1"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | string | 用户自然语言问题（必填） |
| `thread_id` | string | 会话标识（可选）。非空时启用短期会话记忆，同一 `thread_id` 的多次请求共享历史上下文；为空时后端临时生成一个（无历史单次会话） |

**响应**：`text/event-stream`，逐行 `data: <json>\n\n`，包含：

| type | 字段 | 说明 |
|------|------|------|
| `progress` | `step`、`status` | 各节点执行进度（running/success/error） |
| `result` | `sql`、`data` | SQL 执行结果（`data` 为结果行数组） |
| `error` | `message` | 执行过程中抛出的异常信息（如有） |

> `run_sql` 节点执行 SQL 后会通过 `stream_writer` 推送 `{"type": "result", "sql": ..., "data": ...}` 帧，前端据此展示 SQL 与结果表格。同时本轮问答（query/sql/结果摘要）会写入 `state['messages']`，由 `InMemorySaver` 按 `thread_id` 持久化，供下一轮多轮对话使用。

---

## 元知识库构建

元知识库构建由 `app/service/meta_knowledge_service.py` 的 `MetaKnowledgeService.build()` 完成，流程：

1. **加载配置**：解析 `meta_config.yaml` 为 `MetaConfig` 结构化对象；
2. **同步表/字段到 MySQL**：
   - 从数仓 `SHOW COLUMNS` 获取字段类型；
   - 从数仓 `SELECT DISTINCT` 获取字段示例取值；
   - 组装 `TableInfo` / `ColumnInfo` 写入 meta 库；
3. **建立字段向量索引（Qdrant）**：
   - 对每个字段的 **名称、描述、每个别名** 分别生成向量；
   - payload 携带完整字段信息，使任何表达都能命中同一字段；
   - 分批编码（`embedding.batch_size`）后 upsert；
4. **建立字段值全文索引（ES）**：
   - 对 `sync: true` 的字段，从数仓抽取全部 distinct 取值；
   - 批量写入 ES `value_index`（IK 分词）；
5. **同步指标到 MySQL + Qdrant**：
   - 写入 `metric_info` 与 `column_metric` 关联表；
   - 对每个指标的 **名称、描述、每个别名** 生成向量写入 Qdrant 指标集合。

---

## 备注

- 项目使用 **uv** 管理后端依赖，锁文件为 `uv.lock`；前端使用 **npm** 管理依赖，位于 `frontend/`。
- 元数据库与数仓库的表结构初始化 SQL 位于 `docker/mysql/meta.sql` 与 `docker/mysql/dw.sql`，由 MySQL 容器首次启动时自动执行。
- ES 的 IK 分词插件已打包在 `docker/elasticsearch/plugins/`，通过自定义 Dockerfile 构建。
- 日志输出至 `logs/app.log`，按 10MB 轮转、保留 7 天，并携带 `request_id` 便于并发请求链路追踪。
- 短期会话记忆基于 `InMemorySaver`（内存存储），应用重启后会话历史清空；同一 `thread_id` 即代表一个会话。
