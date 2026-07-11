"""
节点：执行 SQL（run_sql）。

工作流终节点。在数仓库上真正执行（已校验或已修正的）SQL，并返回查询结果。
执行结果由 DwMySqlRepository.run_sql 以 list[dict] 形式返回。

本节点同时完成两件事：
    1. 通过 stream_writer 将执行结果以 result 帧推送给前端（SSE）；
    2. 将本轮 query/sql/结果摘要写入 state['messages']，配合 Checkpointer
       按 thread_id 持久化，供下一轮多轮对话使用。
"""
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


def _summarize_result(result: list[dict]) -> str:
    """将结果行压缩为简短摘要，避免历史 messages 过大。"""
    if not result:
        return "无数据"
    # 取列名 + 最多 3 行预览
    columns = list(result[0].keys())
    preview = result[:3]
    rows_text = "; ".join(str(row) for row in preview)
    return f"列: {columns}; 前{len(preview)}行: {rows_text}（共{len(result)}行）"


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL语句", "status": "running"})

    try:
        sql = state["sql"]
        query = state["query"]
        dw_mysql_repository = runtime.context.dw_mysql_repository
        # 真正执行 SQL 并获取结果行
        result = await dw_mysql_repository.run_sql(sql)

        logger.info(f"执行SQL语句成功: {result}")
        # 1. 将查询结果以 result 帧推送给前端
        writer({"type": "result", "sql": sql, "data": result})
        writer({"type": "progress", "step": "执行SQL语句", "status": "success"})

        # 2. 将本轮问答写入 messages，供多轮记忆使用
        messages = list(state.get("messages") or [])
        messages.append({
            "query": query,
            "sql": sql,
            "result_summary": _summarize_result(result),
        })
        return {"messages": messages}
    except Exception as e:
        logger.error(f"执行SQL语句失败: {e}")
        writer({"type": "progress", "step": "执行SQL语句", "status": "error"})
        raise
