"""
请求上下文变量定义。

使用 contextvars 在异步并发下隔离每个请求的 request_id，
供日志模块注入，实现单次请求链路的日志追踪。
"""
from contextvars import ContextVar

request_id_ctx_var = ContextVar("request_id", default="1")