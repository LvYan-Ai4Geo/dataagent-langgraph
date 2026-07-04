"""
日志配置模块。

基于 loguru 配置控制台与文件双通道日志，并通过 contextvars 注入 request_id，
使每条日志携带当前请求的 request_id，便于在并发请求中追踪完整链路。
日志格式、级别、轮转与保留策略均由 app_config.yaml 的 logging 段控制。
"""
import asyncio
import sys
from pathlib import Path

from loguru import logger
from app.core.context import request_id_ctx_var

from app.app_config.config import object_config

# 配置日志格式
log_format = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<magenta>request_id - {extra[request_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# 注入request_id到日志记录中
def inject_request_id(record):
    request_id = request_id_ctx_var.get()
    record["extra"]["request_id"] = request_id


logger.remove()

# 给日志打补丁，使其支持注入request_id
logger = logger.patch(inject_request_id)
if object_config.logging.console.enable:
    logger.add(sink=sys.stdout, level=object_config.logging.console.level, format=log_format)
if object_config.logging.file.enable:
    path = Path(object_config.logging.file.path)
    path.mkdir(parents=True, exist_ok=True)
    logger.add(
        sink=path / "app.log",
        level=object_config.logging.file.level,
        format=log_format,
        rotation=object_config.logging.file.rotation,
        retention=object_config.logging.file.retention,
        encoding="utf-8"
    )

if __name__ == '__main__':
    async def graph(request: str):
        # 打印日志
        logger.info(request)


    async def test1():
        # 接收到请求
        request_id_ctx_var.set("request-1")

        # 模拟处理
        await asyncio.sleep(1)
        await graph("request-1")


    async def test2():
        # 接收到请求
        request_id_ctx_var.set("request-2")

        # 模拟处理
        await asyncio.sleep(1)
        await graph("request-2")


    async def main():
        await asyncio.gather(test1(), test2())


    asyncio.run(main())
