# Data-Agent 面试深挖准备

> 本文档围绕 Data-Agent 项目的实现细节、设计权衡与潜在追问整理，用于面试前自测与深度对答。
> 项目本质：**基于 LangGraph + DeepSeek + 多路召回 RAG 的 NL2SQL 智能数据查询 Agent**。

---

## 目录

- [一、项目一句话讲清楚](#一项目一句话讲清楚)
- [二、整体架构与数据流](#二整体架构与数据流)
- [三、多路召回 RAG（最高频深挖点）](#三多路召回-rag最高频深挖点)
- [四、LangGraph 工作流编排](#四langgraph-工作流编排)
- [五、SQL 生成与自修复闭环](#五sql-生成与自修复闭环)
- [六、元知识离线构建](#六元知识离线构建)
- [七、工程实现细节](#七工程实现细节)
- [八、可能的追问与陷阱](#八可能的追问与陷阱)
- [九、项目不足与改进方向](#九项目不足与改进方向)
- [十、关键数字速记](#十关键数字速记)

---

## 一、项目一句话讲清楚

> 用户输入一句自然语言问题，系统通过"关键词抽取 → 字段/指标/取值三路召回 → 合并过滤 → LLM 生成 SQL → EXPLAIN 校验 → 失败自修复 → 执行"的 LangGraph 工作流，把问题转成可在数仓执行的 SQL 并返回结果，全程 SSE 流式输出进度。

**为什么不用 Text2SQL 直接生成？**
直接让 LLM 生成 SQL 面临三个痛点：
1. **Schema 过大**：数仓表多字段多，全塞进 prompt 超上下文且噪声大；
2. **业务口径模糊**：用户说"销售额"可能对应多个字段，需要指标定义对齐；
3. **枚举值编造**：LLM 不知道"华北""男"在库里到底怎么存，容易写错 WHERE 条件。

所以本项目用 **RAG 把精准上下文召回后再生成**，而非裸 Text2SQL。

---

## 二、整体架构与数据流

```
用户问题
  │
  ▼
[extract_keywords] jieba TextRank 抽实词关键词
  │
  ├──▶ [recall_column]  LLM扩展字段词 → BGE向量化 → Qdrant字段集合
  ├──▶ [recall_metric]  LLM扩展指标词 → BGE向量化 → Qdrant指标集合
  └──▶ [recall_value]   LLM扩展取值词 → ES IK全文 → value_index
                    （三路并行，barrier 汇合）
  │
  ▼
[merge_retrieved_info] 合并去重 + 补全主外键 + 回填取值到examples
  │
  ├──▶ [filter_metric]  LLM 筛必需指标
  └──▶ [filter_table]   LLM 裁剪必需表/字段（保留JOIN键）
                    （两路并行，barrier 汇合）
  │
  ▼
[add_extract_context] 注入当前日期/星期/季度 + DB版本/方言
  │
  ▼
[generate_sql]   LLM 基于全部上下文生成纯文本SQL
  │
  ▼
[validate_sql]   EXPLAIN 校验
  │
  ├── error=None ──▶ [run_sql] ──▶ END
  └── error≠None ──▶ [correct_sql] LLM据错误最小修复 ──▶ [run_sql] ──▶ END
```

**关键设计**：状态用 `DataAgentState`(TypedDict) 流转，依赖用 `DataAgentContext`(dataclass) 注入，职责分离。

---

## 三、多路召回 RAG（最高频深挖点）

### 3.1 为什么是三路？每路解决什么问题？

| 召回路 | 检索方式 | 解决的问题 | 举例 |
|--------|----------|------------|------|
| **字段召回** | Qdrant 向量（BGE 余弦） | "用户说的概念对应哪个字段" | "销售额"→`order_amount` |
| **指标召回** | Qdrant 向量 | "业务度量口径对齐" | "成交总额"→指标 GMV（口径=sum(order_amount)） |
| **取值召回** | ES IK 全文 | "过滤条件里的值在库里到底怎么存" | "华北"→`region_name='华北'`、"男"→`gender='男'` |

### 3.2 为什么字段/指标用向量，取值用全文？

- **字段名/指标名是语义概念**：用户说"销售额"，库里是`order_amount`，字面不匹配但语义相近，**向量检索擅长跨表达匹配**。
- **取值是字面匹配**："华北"在库里就是存的"华北"，不需要语义泛化，反而要精确。且取值数量大、需要 IK 中文分词，**ES 全文检索更合适**。
- 若取值也用向量，会把"华北"匹配到"华南"等语义相近但错误的值，反而有害。

### 3.3 LLM 关键词扩展是干什么的？为什么需要？

jieba TextRank 抽的是问题里**字面出现**的词，但回答问题所需的字段名**未必出现在问题里**。
例如问"最近三个月在职实习生的转正情况如何？"，jieba 抽不出"员工身份类型""转正状态"这些字段概念。

所以每路召回前，用**专属 Prompt** 让 LLM 推断"回答该问题所需的概念词"：
- 字段路：推断必需字段概念（"员工身份类型""转正状态""入职日期"）
- 指标路：推断指标概念（"转正率""转正人数"）
- 取值路：推断取值候选（"在职""实习生""转正"）

扩展词与 jieba 词合并去重后，作为多查询词分别检索，再对结果按 id 去重。

### 3.4 向量是怎么建出来的？为什么字段要建多条？

元知识构建时，对每个字段生成**3 类向量**：
- 字段名 → 向量
- 字段描述 → 向量
- 每个别名 → 向量

**为什么**：用户可能用任意一种表达检索。把"销售额""订单金额""收入"（别名）都建向量，payload 都指向同一个字段，这样无论用哪种表达都能命中同一字段，**提升召回率**。

### 3.5 召回阈值与数量？

代码中默认 `score=0.65, limit=15`：
- `score_threshold=0.65`：余弦相似度低于 0.65 的丢弃，控噪声；
- `limit=15`：每关键词最多召回 15 条；
- 最终对多关键词的结果按 id 去重。

### 3.6 取值召回后怎么用？

取值不是直接给 LLM，而是在 `merge_retrieved_info` 中**回填到对应字段的 examples 字段**。这样 LLM 在生成 SQL 时，能从 examples 里看到"华北""男"这种真实取值，避免编造。

---

## 四、LangGraph 工作流编排

### 4.1 为什么选 LangGraph 而不是 LangChain Chain？

- **需要条件分支**：SQL 校验通过/失败要走不同路径；
- **需要并行 fan-out + barrier**：三路召回要并行，但合并节点要等三路都完成；
- **需要状态在节点间流转**：TypedDict state 比 Chain 的输入输出更清晰；
- **需要流式**：`stream_mode='custom'` 可让节点主动推送进度。

### 4.2 并行是怎么实现的？

LangGraph 中，一个节点有多个入边时，会等所有入边来源都完成才触发（barrier 语义）。
```
extract_keywords → recall_column  ┐
extract_keywords → recall_value   ├─→ merge_retrieved_info（等三路齐）
extract_keywords → recall_metric  ┘
```
`extract_keywords` 执行完后，三路召回同时被触发并行执行；`merge_retrieved_info` 等三路全部写入 state 后才执行。

### 4.3 context_schema 是什么？为什么用它？

`DataAgentContext` 是**依赖注入容器**，承载各 Repository 和 Embedding 模型。
- 不放进 state：state 是节点间流转的可变数据，Repository 是无状态依赖，混在一起会污染状态；
- 通过 `runtime.context` 访问：节点函数签名 `async def node(state, runtime: Runtime[DataAgentContext])`；
- 调用时由 `graph.astream(input=state, context=context)` 传入。

### 4.4 条件边怎么写？

```python
graph_builder.add_conditional_edges(
    source='validate_sql',
    path=lambda state: 'run_sql' if state['error'] is not None else 'correct_sql',
    path_map={'run_sql': 'run_sql', 'correct_sql': 'correct_sql'}
)
```
**注意一个易错点**：代码里 `error is not None` 时走 `run_sql`（即校验通过直接执行），`error is None`（即返回了 error）走 `correct_sql`。这里逻辑要讲清楚：validate_sql 校验**通过**时返回 `error=None`，**失败**时返回 `error=<错误信息>`。条件边的 lambda 根据 error 是否为 None 路由。

> 面试时若被问到这段，务必说明白：校验失败时 validate_sql 返回 `{"error": "..."}`（非 None），条件边据此走向 correct_sql。

---

## 五、SQL 生成与自修复闭环

### 5.1 生成 SQL 的 prompt 注入了什么？

5 类上下文：
1. `table_infos`：过滤后的表+字段（含类型、角色、示例、描述、别名）
2. `metric_infos`：过滤后的指标（含口径描述、关联字段）
3. `date_info`：当前日期/星期/季度（解析"本月""上季度"用）
4. `db_info`：数据库版本+方言（约束 SQL 语法）
5. `query`：原始用户问题

### 5.2 Prompt 怎么约束 LLM 不乱来？

关键约束（见 `prompts/generate_sql.prompt`）：
- 只能用提供的表/字段，禁止编造；
- 指标必须遵循给定口径；
- 只能查询，禁止 INSERT/UPDATE/DELETE；
- 只输出一条纯文本 SQL，禁止 Markdown 代码块。

### 5.3 校验用什么？为什么不直接执行？

用 `EXPLAIN <sql>`：
- EXPLAIN 只解析执行计划，**不真正执行**，安全且快；
- 能检测出语法错误、表/字段不存在、函数不支持等问题；
- 不会产生副作用或返回大量数据。

### 5.4 修复是几次？能无限循环吗？

**当前实现是单次修复**：validate_sql 失败 → correct_sql 修复 → run_sql 执行，**不会循环重试**。
- 优点：流程简单，不会死循环；
- 缺点：修复后的 SQL 若仍错误，会直接在 run_sql 抛异常。
- 改进方向：可加一个计数器做有限次（如 3 次）重试循环。

### 5.5 校验失败时为什么 validate_sql 节点状态还是 success？

因为"校验这件事本身完成了"，只是校验**结果**是失败。节点执行状态（success/error）表示节点是否正常运转，区别于业务结果（SQL 是否合法）。校验失败不抛异常，而是把错误信息写入 state，让条件边路由。

---

## 六、元知识离线构建

### 6.1 为什么要离线构建？

在线查询时每次都要检索字段/指标/取值，如果现查数仓元信息太慢。所以**一次性**把元信息抽取出来，写入三个存储：
- MySQL meta 库：表/字段/指标的元信息（结构化查询）
- Qdrant：字段/指标的向量索引（语义检索）
- ES：维度字段取值的全文索引（精确匹配）

### 6.2 构建流程？

`MetaKnowledgeService.build()`：
1. 解析 `meta_config.yaml` 为结构化 `MetaConfig`；
2. 对每张表：`SHOW COLUMNS` 取类型 + `SELECT DISTINCT` 取示例 → 组装 ColumnInfo → 写 MySQL；
3. 对每个字段：字段名/描述/别名各生成向量 → 分批 upsert Qdrant；
4. 对 `sync: true` 的字段：`SELECT DISTINCT`（不限数量）取全部取值 → 批量写 ES；
5. 指标同理：写 MySQL + Qdrant。

### 6.3 为什么维度字段才 sync 到 ES？

- 维度字段（如地区、性别、品类）取值有限且常作为 WHERE 条件，需要精确匹配；
- 度量字段（如订单金额）取值连续且数量巨大，不适合全文索引也无意义；
- `meta_config.yaml` 中通过 `sync: true/false` 控制。

### 6.4 向量编码为什么分批？

`embedding.batch_size=20`：避免一次性把成千上万条文本送进 BGE 模型导致 OOM 或超时，分批编码后合并。

---

## 七、工程实现细节

### 7.1 分层架构

```
api (路由/依赖注入)
  ↓
service (QueryService / MetaKnowledgeService)
  ↓
agent (graph / nodes / state / context)
  ↓
repositories (qdrant / es / mysql)
  ↓
clients (client manager 单例)
  ↓
entities ←→ models (ORM) via mappers
```

### 7.2 为什么 entities 和 models 分开？

- **entities**（dataclass）：领域对象，业务层流转用，与持久化无关；
- **models**（SQLAlchemy ORM）：数据库表映射，含列类型约束；
- **mappers**：双向转换，隔离业务逻辑与持久层细节。
- 好处：换存储时只动 models/mapper，业务层不动。

### 7.3 MySQL 为什么用两个库？

- **meta 库**：存元信息（表/字段/指标定义），Agent 检索用；
- **dw 库**：数仓，存真实业务数据，SQL 校验和执行用，也是元信息抽取的来源。
- 两个库用各自的 client manager 单例和 session factory，请求间 session 隔离。

### 7.4 异步是怎么做的？

全链路异步：
- MySQL：`asyncmy` 驱动 + SQLAlchemy `AsyncSession` + `async_sessionmaker`；
- Qdrant：`AsyncQdrantClient`；
- ES：`AsyncElasticsearch`；
- Embedding：`HuggingFaceEmbeddings.aembed_query/aembed_documents`；
- LangGraph：`graph.astream` 异步流式。

### 7.5 FastAPI 依赖注入怎么管理 Session？

```python
async def get_meta_session():
    async with meta_mysql_client_manager.session_factory() as session:
        yield session  # 请求结束自动关闭
```
每个请求独立 session，`expire_on_commit=False` 避免 commit 后属性失效。

### 7.6 SSE 流式怎么实现？

- `QueryService.query()` 是 async generator，`yield` SSE 帧；
- FastAPI `StreamingResponse(generator, media_type='text/event-stream')`；
- 帧格式：`data: {json}\n\n`；
- LangGraph `stream_mode='custom'`：节点内 `runtime.stream_writer({...})` 写出的字典作为 chunk 产出。

### 7.7 日志怎么追踪并发请求？

- `contextvars.ContextVar("request_id")` 在异步并发下隔离每请求的 id；
- Loguru `logger.patch(inject_request_id)` 把 contextvar 注入日志 record；
- 每条日志带 `request_id`，并发请求的日志可按 id 过滤还原链路。

---

## 八、可能的追问与陷阱

### Q1: 如果三路召回都没召回到东西怎么办？
当前代码：召回结果为空列表，merge 节点会得到空 table_infos/metric_infos，generate_sql 仍会执行但 LLM 缺乏上下文，可能生成错误 SQL 或拒绝生成。
**改进**：应在 merge 后加判断，召回为空时直接返回"无法理解"而非继续生成。

### Q2: 召回太多字段，prompt 超长怎么办？
当前靠两阶段过滤（filter_metric + filter_table）裁剪。若仍超长，可：
- 向量检索时降低 limit 或提高 score_threshold；
- 按表分组后只保留 top-K 字段；
- 分级加载（先生成框架 SQL 再补字段）。

### Q3: SQL 执行有安全风险吗？能注入吗？
- SQL 由 LLM 生成，prompt 约束只查询禁止写操作；
- 但**没有显式防注入机制**（如 SQL 关键字白名单、只读账号）；
- 改进：dw 库连接用只读账号；或在 run_sql 前做语句类型校验（只允许 SELECT）。

### Q4: BGE 模型加载是本地的，部署怎么办？
当前 `emb_client_manager.py` 硬编码了本地绝对路径 `G:/PythonProject/...`，跨环境会失效。
**改进**：改用 `conf/path_config.py` 的 `BGE_MODEL` 常量，或用环境变量配置。docker-compose 里其实也起了 TEI 推理服务（端口 8081），可切换为远程调用。

### Q5: 工作流是写死的，能动态调整吗？
当前图结构编译时固定。若要支持多轮对话、追问、澄清，需要：
- 改为带条件循环的图；
- state 增加 history 字段；
- 加一个"是否需要澄清"的判断节点。

### Q6: 为什么 correct_sql 后不再校验一次？
当前是 correct_sql → run_sql 直接执行，没有二次 validate。若修正后的 SQL 仍有语法错误，会在 run_sql 抛异常。
**改进**：correct_sql 后回到 validate_sql 形成循环（带最大重试次数）。

### Q7: 取值召回的 score=0.65 会不会漏召回？
ES 是 BM25 相关性评分，min_score=0.65 可能漏掉一些相关性较低的取值。但取值召回宁缺勿滥（错召回会污染 WHERE 条件），所以阈值偏高是合理的。

### Q8: filter_table 怎么保证 JOIN 键不丢？
两处保障：
1. merge 阶段：`get_key_info_by_id` 主动补全每张表的主外键字段；
2. filter_table 的 prompt 明确要求"多表时必须保留 join 所需主外键"。
但这是靠 LLM 遵守 prompt，没有硬性校验，存在风险。

---

## 九、项目不足与改进方向

| 不足 | 改进方向 |
|------|----------|
| SQL 修复只一次，不循环 | 加最大重试次数的 validate↔correct 循环 |
| 无 SQL 安全防护 | 只读账号 + 语句类型白名单 |
| Embedding 路径硬编码 | 改用配置/环境变量 |
| run_sql 结果未通过 stream 推送 | 补 `writer({"type":"result","data":result})` |
| 召回为空无降级 | merge 后加空判断，直接返回提示 |
| 无多轮对话能力 | state 加 history，图加澄清循环 |
| 无效果评估指标 | 加 SQL 执行成功率、结果准确率统计 |
| filter 靠 LLM 无硬校验 | 对 JOIN 键做程序化校验 |
| 无缓存 | 对高频问题缓存召回结果/SQL |

---

## 十、关键数字速记

| 项 | 值 |
|----|-----|
| 工作流节点数 | 12 |
| 召回路数 | 3（字段/指标/取值） |
| BGE 向量维度 | 1024 |
| Qdrant 距离度量 | 余弦（COSINE） |
| 向量召回阈值 | score=0.65, limit=15 |
| Embedding 批大小 | 20 |
| MySQL 连接池 | pool_size=10 |
| Python 版本 | 3.12 |
| MySQL 端口 | 3307（宿主）→ 3306（容器） |
| 日志轮转/保留 | 10MB / 7 天 |
| LLM temperature | 0.1 |

---

## 附：30 秒电梯陈述

> "我做了一个 NL2SQL 的数据查询 Agent。核心难点是数仓 Schema 大、业务口径模糊、枚举值容易编造，所以我设计了三层多路召回 RAG：用 Qdrant 向量检索召回字段和指标对齐业务口径，用 ES 全文检索召回真实取值避免 LLM 编造 WHERE 条件，每路召回前还用 LLM 扩展检索词提升召回率。召回后用 LLM 做两阶段过滤精简上下文，再生成 SQL，生成后用 EXPLAIN 校验，失败自动修复重试。整个流程用 LangGraph 编排成 12 节点的 DAG，三路召回并行执行，FastAPI SSE 流式返回进度。元知识库离线一次性构建到 MySQL/Qdrant/ES，在线只做检索。"
