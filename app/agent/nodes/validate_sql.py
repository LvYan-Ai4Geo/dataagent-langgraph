"""
节点：校验 SQL（validate_sql）。

在数仓库上用 `EXPLAIN <sql>` 对生成的 SQL 进行语法与执行计划校验：
    - 校验通过：返回 error=None，条件边据此走向 run_sql 直接执行；
    - 校验失败：返回 error=<错误信息>，条件边据此走向 correct_sql 修正。

注意：本节点自身的执行状态始终为 success（即“校验这件事完成了”），
区别于校验结果是否通过。校验失败时不抛异常，而是把错误信息写入 state。
"""
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def validate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校验SQL语句", "status": "running"})

    try:
        sql = state["sql"]
        dw_mysql_repository = runtime.context.dw_mysql_repository

        try:
            # EXPLAIN 仅解析执行计划不真正执行，用于检测 SQL 语法/对象合法性
            await dw_mysql_repository.validate(sql)
            logger.info("校验SQL语句通过")
            writer({"type": "progress", "step": "校验SQL语句", "status": "success"})
            # 校验通过：显式重置 error=None，供条件边与下一轮记忆正确判断
            return {"error": None}
        except Exception as e:
            # 校验失败：记录错误信息，交由 correct_sql 节点修正
            logger.info(f"校验SQL语句失败: {str(e)}")
            error = str(e)
            writer({"type": "progress", "step": "校验SQL语句", "status": "success"})
            return {"error": error}
    except Exception as e:
        logger.error(f"校验SQL语句节点异常: {e}")
        writer({"type": "progress", "step": "校验SQL语句", "status": "error"})
        raise
