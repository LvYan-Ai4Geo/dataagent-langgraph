"""
节点：关键词抽取（extract_keywords）。

工作流第一个节点。使用 jieba 的 TextRank 算法从用户自然语言问题中抽取
关键词，并将原始 query 一并加入关键词集合，作为后续字段/指标/字段值召回
的检索输入。
"""
import jieba.analyse
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def extract_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    # 向前端推送当前步骤的执行进度
    writer({"type": "progress", "step": "抽取关键词", "status": "running"})

    try:
        query = state["query"]
        # 仅保留名词、动词、形容词等实词词性，过滤助词/标点等噪声词
        allow_pos = ("n", "nr", "ns", "nt", "nz", "v", "vn", "a", "an", "eng", "i", "l")
        keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)
        # 原始 query 整条也作为一个“关键词”，确保后续向量/全文检索能用到完整语义
        keywords = list(set(keywords + [query]))

        logger.info(f"抽取关键词成功: {keywords}")
        writer({"type": "progress", "step": "抽取关键词", "status": "success"})
        return {"keywords": keywords}
    except Exception as e:
        logger.error(f"抽取关键词失败: {e}")
        writer({"type": "progress", "step": "抽取关键词", "status": "error"})
        raise
