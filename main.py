"""
FastAPI 应用入口。

创建 FastAPI 实例，挂载生命周期管理（lifespan，负责初始化与释放各类客户端），
并注册查询路由（query_router，提供 POST /api/query 接口）。
通过 `fastapi[standard]` 运行：fastapi dev main.py 或 fastapi run main.py
"""
from fastapi import FastAPI

from app.api.lifespan import lifespan
from app.api.routers.query_router import query_router

# 创建应用实例并挂载生命周期与路由
app = FastAPI(lifespan=lifespan)

app.include_router(query_router)
