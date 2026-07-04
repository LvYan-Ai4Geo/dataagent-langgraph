"""
节点：添加额外上下文（add_extract_context）。

在生成 SQL 之前，注入两类上下文信息：
    1. 日期上下文（date_info）：当前日期、星期、季度，用于让 LLM 正确解析
       “今天/本月/本季度/上周”等相对时间语义；
    2. 数据库环境上下文（db_info）：目标数仓的版本与方言，用于约束生成 SQL
       的语法风格（如 MySQL 8.0）。
"""
from datetime import date

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState, DbInfoState
from app.core.log import logger


async def add_extract_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "添加额外上下文", "status": "running"})

    try:
        # 1. 计算当前日期上下文
        today = date.today()
        date_info = DateInfoState(
            date=today.strftime("%Y-%m-%d"),
            weekday=today.strftime("%A"),
            quarter=f"Q{(today.month - 1) // 3 + 1}",
        )

        # 2. 从数仓库获取数据库版本与方言
        dw_mysql_repository = runtime.context.dw_mysql_repository
        result = await dw_mysql_repository.get_db_info()
        db_info = DbInfoState(**result)

        logger.info(f"添加额外上下文成功: date_info={date_info}, db_info={db_info}")
        writer({"type": "progress", "step": "添加额外上下文", "status": "success"})
        return {"date_info": date_info, "db_info": db_info}
    except Exception as e:
        logger.error(f"添加额外上下文失败: {e}")
        writer({"type": "progress", "step": "添加额外上下文", "status": "error"})
        raise
