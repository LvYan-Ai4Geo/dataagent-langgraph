"""
节点：执行 SQL（run_sql）。

工作流终节点。在数仓库上真正执行（已校验或已修正的）SQL，并返回查询结果。
执行结果由 DwMySqlRepository.run_sql 以 list[dict] 形式返回。
"""
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def run_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL语句", "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context.dw_mysql_repository
        # 真正执行 SQL 并获取结果行
        result = await dw_mysql_repository.run_sql(sql)

        logger.info(f"执行SQL语句成功: {result}")
        writer({"type": "progress", "step": "执行SQL语句", "status": "success"})
    except Exception as e:
        logger.error(f"执行SQL语句失败: {e}")
        writer({"type": "progress", "step": "执行SQL语句", "status": "error"})
        raise
