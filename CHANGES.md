# 改动说明（CHANGES）

本文档记录本次为 data-agent 项目所做的全部改动，按文件逐条列出。

改动目标：
1. 为 LangGraph 图编排智能体添加**短期会话记忆**机制；
2. 构建**灵动粒子动态效果**的 Vue3 前端，初次登录粒子浮动，随后展示自然语言2SQL；
3. 同步修复若干阻塞项目启动的既有缺陷；
4. 更新 README。

> 环境管理基于项目的 **uv** 环境（后端）与 **npm**（前端）。

---

## 一、阻塞性缺陷修复

### 1. `app/api/dependencies.py`（修复）
- **改动**：`from envs.nlp.Lib.typing import Annotated` → `from typing import Annotated`
- **原因**：`envs.nlp.Lib...` 是一个不存在的包路径（疑似 IDE 误补全），导致模块导入即报 `ModuleNotFoundError`，整个 API 层无法加载。`Annotated` 应来自标准库 `typing`。

### 2. `app/api/routers/query_router.py`（修复）
- **改动**：同上，`from envs.nlp.Lib.typing import Annotated` → `from typing import Annotated`
- **原因**：同上，修复阻塞性导入错误。

### 3. `app/service/query_service.py`（修复 + 修改）
- **改动**：删除两行无效且会报错的导入：
  - `from envs.image_main.Lib.urllib import error`
  - `from sentry_sdk.consts import FALSE_VALUES`
- **原因**：两者均为未使用的错误导入（`envs.image_main...` 不存在；`sentry_sdk` 并非项目依赖）。同时新增 `import uuid` 用于会话标识生成（见下文）。

### 4. `app/repositories/es/value_es_repository.py`（修复）
- **改动**：修正 `index()` 方法内 `for i in range(...)` 代码块的多余缩进（原 13 行整体多缩进一级，触发 `IndentationError`）。
- **原因**：语法错误导致该模块无法导入，进而导致 `dependencies.py` 导入失败、项目无法启动。

### 5. `app/agent/nodes/validate_sql.py`（修复）
- **改动**：校验通过分支由「仅赋值 `error = None` 但不 return」改为「显式 `return {"error": None}`」。
- **原因**：原实现在校验通过时未把 `error` 写回 state，导致条件边读到的是上一轮残留的 `error`（启用 Checkpointer 后尤为致命，因为 `error` 会跨轮持久化）。

### 6. `app/agent/graph.py`（修复）
- **改动**：条件边 path 由 `'run_sql' if state['error'] is not None else 'correct_sql'` 修正为 `'correct_sql' if state['error'] is not None else 'run_sql'`。
- **原因**：原逻辑与上方注释/文档字符串完全相反——校验失败（error≠None）本应进入 `correct_sql`，原代码却进入 `run_sql`；校验通过（error=None）本应进入 `run_sql`，原代码却进入 `correct_sql`。修正后与注释一致。

---

## 二、短期会话记忆

### 7. `app/agent/graph.py`（新增）
- **改动**：
  - 导入 `from langgraph.checkpoint.memory import InMemorySaver`；
  - 新增模块级单例 `memory = InMemorySaver()`；
  - 编译改为 `graph = graph_builder.compile(checkpointer=memory)`；
  - `__main__` 测试块改为携带 `config={"configurable": {"thread_id": "test-thread-1"}}` 运行。
- **原因**：为图注入 Checkpointer，使同一 `thread_id` 的多次调用基于历史 state 累积上下文，实现多轮对话记忆。

### 8. `app/agent/state.py`（修改）
- **改动**：`DataAgentState` 新增 `messages: list[dict]` 字段，并在类文档中补充多轮记忆说明。
- **原因**：承载每轮问答（query/sql/结果摘要）的历史记录，供 Checkpointer 按 `thread_id` 持久化，供下一轮节点读取。

### 9. `app/agent/nodes/extract_keywords.py`（修改）
- **改动**：抽取关键词前，若 `state['messages']` 存在历史，则将上一轮的 query/sql/结果摘要拼入当前 query 上下文后再用 jieba 抽取关键词。
- **原因**：让多轮追问（如「再按性别细分」）的关键词召回能利用上一轮语义，提升多轮场景的召回质量。

### 10. `app/agent/nodes/run_sql.py`（修复 + 修改）
- **改动**：
  - 执行成功后新增 `writer({"type": "result", "sql": sql, "data": result})`，把结果以 SSE 帧推送给前端；
  - 新增 `_summarize_result()` 工具函数，将本轮 query/sql/结果摘要写入 `state['messages']` 并 return；
  - 补充模块/函数文档说明。
- **原因**：原实现执行 SQL 后既未推送结果、也未 return（前端拿不到数据）；同时需将本轮问答记入 `messages` 以支持记忆。

---

## 三、API 层支持会话标识

### 11. `app/api/schema/query_schema.py`（修改）
- **改动**：`QuerySchema` 新增 `thread_id: str | None = None` 字段，并补充文档。
- **原因**：让前端在请求体中携带会话标识以启用记忆。

### 12. `app/api/routers/query_router.py`（修改）
- **改动**：`query_handler` 读取 `query.thread_id` 并传给 `QueryService.query()`；更新文档注释。
- **原因**：把会话标识从请求透传到服务层。

### 13. `app/service/query_service.py`（修改）
- **改动**：`query()` 签名增加 `thread_id: str | None = None`；构造 `config={"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}` 传入 `graph.astream(..., config=config, ...)`；为空时临时生成一个（无历史单次会话）。
- **原因**：将 `thread_id` 与 LangGraph Checkprinter 打通，真正激活会话记忆。

---

## 四、依赖声明

### 14. `pyproject.toml`（修改）
- **改动**：`dependencies` 新增 `"python-dotenv>=1.0.0"`。
- **原因**：`app/agent/llm.py` 直接 `from dotenv import load_dotenv` 使用了该库，此前仅作为传递依赖存在，显式声明更规范、避免传递依赖被移除后出错。

> 注：未运行 `uv lock`/`uv sync` 重生成锁文件（避免在无网络/不影响导入的前提下改动 `uv.lock`）。如需同步锁文件，可执行 `uv lock`。

---

## 五、前端（新增）

新增独立前端项目 `frontend/`（Vue3 + Vite），灵动粒子动态风格。

### 新增文件清单

| 文件 | 说明 |
|------|------|
| `frontend/package.json` | 依赖声明（vue、vue-router、@vitejs/plugin-vue、vite） |
| `frontend/vite.config.js` | Vite 配置，开发时将 `/api` 代理到 `http://127.0.0.1:8000` |
| `frontend/index.html` | HTML 入口 |
| `frontend/.gitignore` | 忽略 node_modules / dist |
| `frontend/src/main.js` | 应用入口，挂载 router 与全局样式 |
| `frontend/src/App.vue` | 根组件，路由出口 + 过渡动画 |
| `frontend/src/router/index.js` | 路由：`/` 登录页、`/chat` 主界面 |
| `frontend/src/styles/main.css` | 全局样式与 CSS 变量（深色 + 青蓝主题） |
| `frontend/src/components/ParticleBackground.vue` | **全屏 canvas 粒子动效**：浮动粒子 + 连线 + 鼠标吸附，性能自适应 |
| `frontend/src/components/ChatInput.vue` | 输入框 + 发送按钮 |
| `frontend/src/components/ProgressTimeline.vue` | SSE 进度时间线（running/success/error 状态点） |
| `frontend/src/components/ResultTable.vue` | SQL 展示 + 结果表格 |
| `frontend/src/composables/useSSE.js` | fetch + ReadableStream 解析 SSE 帧（progress/result/error） |
| `frontend/src/views/LoginView.vue` | **初次登录界面**：粒子浮动背景 + 「进入系统」按钮，点击生成 UUID 作为 thread_id |
| `frontend/src/views/ChatView.vue` | **自然语言2SQL 主界面**：进度时间线 + SQL/结果展示 + 多轮对话 |

### 功能要点
- 初次登录界面：全屏粒子浮动 + 鼠标吸附交互，点击「进入系统」生成随机 UUID（`crypto.randomUUID()`）存入 `localStorage` 作为 `thread_id`，跳转主界面。
- 主界面：背景半透明粒子层保持灵动；发送自然语言问题后实时展示各节点进度时间线、生成的 SQL 与结果表格；携带 `thread_id` 实现多轮记忆；「重置」按钮清空会话回到登录页。
- SSE 通信：通过 `fetch` + `ReadableStream` 流式解析后端 `text/event-stream`，按 `type` 分发（progress/result/error）。
- 已验证 `npm install` 与 `npm run build` 构建成功（产物在 `frontend/dist/`）。

---

## 六、文档

### 15. `README.md`（修改）
- **改动**：
  - 顶部描述补充多轮记忆与前端；
  - 目录新增「短期会话记忆」章节链接；
  - 核心特性新增「短期会话记忆」「灵动粒子前端」两条；
  - 技术栈表新增前端 Vue3/Vite，Agent 编排标注 InMemorySaver；
  - 系统架构图补充前端层与 thread_id/checkpointer 流向；
  - 工作流表后的「状态流转」补充 `messages`/`InMemorySaver` 说明；
  - 新增「短期会话记忆」章节（持久化方式、会话标识、历史上下文、状态重置）；
  - 项目结构补充 `frontend/` 目录树与各节点注释更新；
  - 快速开始新增「步骤 3：启动前端」，curl 示例补充 `thread_id`，SSE 示例补充 `result` 帧；
  - 接口说明补充 `thread_id` 字段表与 `result` 帧说明，修正「run_sql 未推送结果」的旧备注；
  - 备注补充前端 npm、会话记忆说明，并指向本 CHANGES.md。

### 16. `CHANGES.md`（新增）
- **改动**：即本文件，逐条说明所有改动点与原因。
