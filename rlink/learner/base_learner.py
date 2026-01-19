# -*- coding: utf-8 -*-
"""RLink Learner with UCXX server support."""

import asyncio
import time
import traceback
import io
from typing import Dict, Any, Optional, Callable, List
from concurrent.futures import ThreadPoolExecutor
import threading

import ucxx
import uvicorn
import numpy as np
from fastapi import FastAPI, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from rlink.utils.msgpack_numpy import Packer, unpackb


async def actor_data_callback(ep):
    """处理来自actor的数据

    Args:
        ep (_type_): UCXX端点
    """
    obj = await ep.recv_obj()
    print(f"================?Received object from actor: {len(obj)}")
    await ep.send_obj(obj)
    # sys.exit(-1)


class RLinkLearner:
    """RLink Learner Base Class with UCXX server support."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8443,
        data_port: int = 13338,
        data_callback: Optional[Callable] = None,
        enable_ucxx: bool = True,
        max_queue_size: int = 1000,
    ) -> None:
        """初始化RLink Learner

        Args:
            host: HTTP服务器主机地址
            port: HTTP服务器端口
            data_port: UCXX数据服务器端口
            data_callback: 数据处理回调函数
            enable_ucxx: 是否启用UCXX服务器
            max_queue_size: 数据队列最大大小
        """
        self._host = host
        self._port = port
        self._data_port = data_port
        self._enable_ucxx = enable_ucxx
        self._max_queue_size = max_queue_size

        # 数据处理器
        self._packer = Packer()
        self._actor_info = {}

        # UCXX服务器和处理器
        self._learner_data_server = None

        # 创建FastAPI应用
        self._app = self.create_app()

        # 事件循环和线程池
        self._loop = None
        self._executor = ThreadPoolExecutor(max_workers=3)

        # 启动标志
        self._running = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        self.close()

    def close(self):
        """关闭所有连接和资源"""
        print("Closing RLink Learner...")

        self._running = False
        # 关闭UCXX服务器
        if self._learner_data_server:
            try:
                self._learner_data_server.close()
            except BaseException:
                pass

        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False)

        print("RLink Learner closed")

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        app = FastAPI(
            title="RLink Learner Server",
            description="RLink Learner with UCXX data server support",
            version="2.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
        )

        # 添加CORS中间件
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # 注册路由
        self._register_routes(app)
        return app

    async def _start_ucxx_server(self):
        """启动UCXX服务器"""
        if not self._enable_ucxx:
            print("UCXX server is disabled")
            return

        print(f"Starting UCXX data server on port {self._data_port}...")

        try:
            # 创建UCXX监听器
            self._learner_data_server = ucxx.create_listener(
                actor_data_callback, self._data_port
            )

            print(f"✓ UCXX data server started on port {self._data_port}")

            # 保持服务器运行
            while (
                self._running
                and self._learner_data_server
                and not self._learner_data_server.closed
            ):
                await asyncio.sleep(1)

        except Exception as e:
            print(f"Failed to start UCXX server: {e}")
        finally:
            print("UCXX server stopped")

    def _register_routes(self, app: FastAPI):
        """注册路由"""

        @app.get("/", response_model=Dict[str, Any])
        async def root():
            """根端点"""
            stats = self._ucxx_handler.get_stats() if self._ucxx_handler else {}

            return {
                "message": "RLink Learner Server is running",
                "status": "healthy",
                "ucxx_enabled": self._enable_ucxx,
                "ucxx_port": self._data_port,
                "ucxx_stats": stats,
                "endpoints": {
                    "available": "/available",
                    "data_probe": "/data_probe",
                    "docs": "/docs",
                },
            }

        @app.get("/available", response_model=Dict[str, Any])
        async def available():
            """Learner可用性检查"""
            return {
                "status": "success",
                "ucxx_enabled": self._enable_ucxx,
                "ucxx_port": self._data_port,
                "timestamp": time.time(),
            }

        @app.post("/data_probe")
        async def data_probe(data: bytes = Body(...)):
            """处理数据探测请求"""
            try:
                request_time = time.time()

                # 解析msgpack数据
                obs = unpackb(data)
                actor_id = obs.get("actor_id", "unknown_actor")
                data_size = obs.get("data_size", 0)

                print(f"Data probe from actor {actor_id}, size: {data_size} bytes")

                # 更新actor信息
                self._actor_info[actor_id] = {
                    "data_size": data_size,
                    "last_probe": request_time,
                    "probe_count": self._actor_info.get(actor_id, {}).get(
                        "probe_count", 0
                    )
                    + 1,
                }

                # 准备响应
                response_data = {
                    "status": "success",
                    "data_size": data_size,
                    "actor_id": actor_id,
                    "timestamp": request_time,
                    "ucxx_enabled": self._enable_ucxx,
                    "ucxx_port": self._data_port,
                }

                packed_response = self._packer.pack(response_data)

                return StreamingResponse(
                    io.BytesIO(packed_response),
                    media_type="application/msgpack",
                    headers={"X-Actor-ID": actor_id, "X-Timestamp": str(request_time)},
                )

            except Exception as e:
                print(f"Data probe error: {e}")
                error_data = {
                    "error": str(e),
                    "status": "error",
                    "timestamp": time.time(),
                }
                packed_error = self._packer.pack(error_data)

                return StreamingResponse(
                    io.BytesIO(packed_error),
                    media_type="application/msgpack",
                    status_code=500,
                )

        # @app.get("/ucxx_stats", response_model=Dict[str, Any])
        # async def get_ucxx_stats():
        #     """获取UCXX服务器统计信息"""
        #     if not self._enable_ucxx or not self._ucxx_handler:
        #         return JSONResponse(
        #             status_code=400,
        #             content={"error": "UCXX server is not enabled"}
        #         )

        #     stats = self._ucxx_handler.get_stats()
        #     stats.update({
        #         "actor_count": len(self._actor_info),
        #         "actors": list(self._actor_info.keys()),
        #         "server_running": self._running
        #     })

        #     return stats

    def serve_forever(self):
        """启动服务器"""
        print("=== RLink Learner Server ===")
        print(f"HTTP Server: {self._host}:{self._port}")
        print(f"UCXX Data Server: {self._data_port}")
        print(f"API Documentation: http://{self._host}:{self._port}/docs")
        print("=" * 40)

        # 设置运行标志
        self._running = True

        # 在新线程中启动异步任务
        def run_async_tasks():
            # 创建新的事件循环
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            try:
                # 创建并运行异步任务
                tasks = []

                # 启动UCXX服务器
                if self._enable_ucxx:
                    tasks.append(self._loop.create_task(self._start_ucxx_server()))
                # 运行所有任务
                self._loop.run_until_complete(asyncio.gather(*tasks))

            except KeyboardInterrupt:
                print("Server interrupted by user")
            except Exception as e:
                print(f"Server error: {e}")
            finally:
                self._running = False
                if self._loop:
                    self._loop.close()

        # 在新线程中启动异步任务
        async_thread = threading.Thread(target=run_async_tasks, daemon=True)
        async_thread.start()

        # 给异步服务器一点时间启动
        time.sleep(1)

        # 启动HTTP服务器（在主线程中运行）
        try:
            uvicorn.run(
                self._app,
                host=self._host,
                port=self._port,
                log_level="info",
                access_log=True,
            )
        except KeyboardInterrupt:
            print("\nServer shutting down...")
        finally:
            self._running = False
