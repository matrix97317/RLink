# -*- coding: utf-8 -*-
"""RLink Actor."""

from typing import Optional
from typing import Union
from typing import List
from typing import Dict
from typing import Any
import asyncio
import time
import sys
import concurrent.futures
from threading import Lock

import requests
import ucxx

from rlinks.utils.exception import InitWithExitError
from rlinks.utils.msgpack_numpy import Packer
from rlinks.utils.msgpack_numpy import unpackb
from rlinks.utils.tools import is_valid_ip
from rlinks.utils.tools import get_ip_based_uuid_v3


class RLinkActor:
    """RLink Actor Base Class."""

    def __init__(self, learner_urls: Optional[Union[str, List[str]]] = None):
        """Initialize RLink Actor."""
        self._data_port = 13338
        self._timeout = 30  # seconds
        #
        self.actor_id = get_ip_based_uuid_v3()
        print(f"Initializing RLink Actor with ID: {self.actor_id}")
        with open(f"./{self.actor_id}.txt", "w", encoding="utf-8") as fout:
            fout.write(self.actor_id)
        # create session
        self.session = requests.Session()
        # check learner_urls
        if learner_urls is None:
            raise InitWithExitError("learner_urls must be provided.")
        if isinstance(learner_urls, str):
            # url format: http://ip:port
            if not is_valid_ip(learner_urls.split("//")[1].split(":")[0]):
                raise InitWithExitError(
                    f"Invalid IP address in learner_urls: {learner_urls}"
                )
            self.learner_urls = [learner_urls]
        elif isinstance(learner_urls, list):
            for url in learner_urls:
                if not is_valid_ip(url.split("//")[1].split(":")[0]):
                    raise InitWithExitError(
                        f"Invalid IP address in learner_urls: {url}"
                    )
            self.learner_urls = learner_urls
        else:
            raise InitWithExitError(
                "learner_urls must be a string or a list of strings."
            )

        # test connection
        for url in self.learner_urls:
            if not self._is_available(url):
                raise InitWithExitError(f"Learner at {url} is not available.")
            print(f"Learner at {url} is available.")
        # data packer: serialization and deserialization
        self.packer = Packer()
        # data transfer channel: fast data transfer with ucxx
        self.data_end_points = []
        self._ucxx_lock = Lock()
        self._ucxx_initialized = False

        # 异步事件循环处理
        self._loop = None
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self._initialize_ucxx_endpoints_sync()

        # data probe
        self._use_data_probe = True

    def _initialize_ucxx_endpoints_sync(self):
        """同步初始化UCXX端点"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 异步创建端点
            endpoints = loop.run_until_complete(self._create_ucxx_endpoints_async())
            loop.close()

            self.data_end_points = endpoints
            self._ucxx_initialized = True
            print(f"Initialized {len(endpoints)} UCXX endpoints")

        except Exception as e:
            print(f"Failed to initialize UCXX endpoints: {e}. Will use HTTP only.")
            self.data_end_points = []
            self._enable_ucxx = False

    async def _create_ucxx_endpoints_async(self) -> List[Any]:
        """异步创建UCXX端点"""
        endpoints = []

        for url in self.learner_urls:
            try:
                # 从URL中提取IP
                host = url.split("//")[1].split(":")[0]
                # 创建UCXX端点
                endpoint = await ucxx.create_endpoint(host, self._data_port)
                if endpoint:
                    endpoints.append((endpoint, host))
                    print(f"✓ UCXX endpoint created for {host}:{self._data_port}")
                else:
                    print(
                        f"✗ Failed to create UCXX endpoint for {host}:{self._data_port}"
                    )
            except Exception as e:
                print(f"✗ Failed to create UCXX endpoint for {url}: {e}")

        return endpoints

    def _is_available(self, url) -> bool:
        """Check if learner is available."""
        try:
            response = self.session.get(f"{url}/available", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _data_probe(self, inputs_data: dict, url: str) -> dict:
        """Send data to learner for getting structure of data."""
        packed_data = self.packer.pack(inputs_data)
        response = self.session.post(
            f"{url}/data_probe",
            data=packed_data,
            headers={"Content-Type": "application/msgpack"},
            timeout=30,
        )
        response.raise_for_status()
        return unpackb(response.content)

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit RLink Actor."""
        self.close()

    def _send_via_ucxx_sync(self, data: bytes) -> Dict[str, Any]:
        """通过UCXX同步发送数据"""
        if not self.data_end_points:
            raise InitWithExitError("No UCXX endpoints available")

        # 在单独的线程中运行异步发送
        def _run_async_send():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # 创建发送任务
                tasks = []
                for ep in self.data_end_points:
                    print(f"Sending data via UCXX...{ep}")
                    task = self._send_single_ucxx_async(data, ep)
                    tasks.append(task)

                # 等待所有发送完成
                results = loop.run_until_complete(asyncio.gather(*tasks))
                # loop.close()

                # 统计结果
                successful = sum(1 for r in results if r)
                failed = len(results) - successful

                return {
                    "successful_sends": successful,
                    "failed_sends": failed,
                    "total_targets": len(self.data_end_points),
                }
            except Exception as e:
                print(f"Async UCXX send failed: {e}")
                raise

        # 在线程池中执行
        future = self._executor.submit(_run_async_send)
        return future.result(timeout=self._timeout)

    async def _send_single_ucxx_async(self, data: bytes, endpoint) -> bool:
        """异步发送到单个UCXX端点"""
        try:
            # await asyncio.wait_for(
            #     endpoint.send_obj(data),
            #     timeout=self._timeout
            # )
            new_endpoint = await ucxx.create_endpoint(endpoint[1], self._data_port)
            await new_endpoint.send_obj(data)
            obj = await new_endpoint.recv_obj()
            print(f"Received ack from learner: {len(obj)}")
            return True
        except asyncio.TimeoutError:
            print("UCXX send timed out")
            return False
        except Exception as e:
            print(f"UCXX send error: {e}")
            return False

    def _download_model_from_learner(
        self,
        url: str,
    ):
        """从learner下载远程模型"""
        download_url = f"{url}/get_remote_model"
        ip = url.split("//")[1].split(":")[0]
        # 使用流式下载
        start_time = time.time()
        packed_data = self.packer.pack({"actor_id": self.actor_id})
        response = requests.post(
            download_url,
            data=packed_data,
            headers={"Content-Type": "application/msgpack"},
            timeout=30,
            stream=True,
        )

        if response.status_code == 200:
            total_size = int(response.headers.get("content-length", 0))
            downloaded_size = 0
            with open(f"remote_{ip}_model.pt", "wb") as f:
                # 8MB chunks
                for chunk in response.iter_content(chunk_size=8192 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = (downloaded_size / total_size) * 100
                        print(f"Download progress: {progress:.2f}%")
            download_time = time.time() - start_time
            print(f"Download completed in {download_time:.2f} seconds")
            return f"remote_{ip}_model.pt"
        if response.status_code == 204:
            print("=============> remote model is not ready now....")
            return None

        print(f"Download failed with status code: {response.status_code}")
        return None

    def get_remote_model(
        self,
    ):
        """从learner下载远程模型"""
        remote_model_paths = []
        for url in self.learner_urls:
            print(f"Downloading model from learner at {url}...")
            model_path = self._download_model_from_learner(url)
            if model_path is not None:
                remote_model_paths.append(model_path)
                print(f"Model downloaded and saved to {model_path}")
            else:
                print(f"No model downloaded from {url}")
        return remote_model_paths

    def close(self):
        """关闭所有连接"""
        print(f"Closing RLink Actor {self.actor_id}...")

        # 关闭UCXX端点
        if self.data_end_points:
            # UCXX端点会自动清理，这里可以添加额外的清理逻辑
            self.data_end_points.clear()

        # 关闭HTTP会话
        if self.session:
            self.session.close()

        # 关闭线程池
        if self._executor:
            self._executor.shutdown(wait=False)

        print(f"RLink Actor {self.actor_id} closed")

    def put(self, data: dict):
        """Put data to learner."""
        packed_data = self.packer.pack(data)
        if self._use_data_probe:
            data_info = {}
            data_info["data_size"] = len(packed_data)
            data_info["actor_id"] = self.actor_id
            for url in self.learner_urls:
                probe_response = self._data_probe(data_info, url)
                if probe_response["status"] != "success":
                    raise InitWithExitError(f"{url} Data probe failed.")
            # self._use_data_probe = False

        if self._ucxx_initialized:
            send_result = self._send_via_ucxx_sync(packed_data)
            return send_result
        return None
