"""
Feishu/Lark Channel - 支持私聊和群聊 @机器人

支持两种连接模式:
1. WebSocket 长连接模式 (推荐): 无需公网 IP，本地即可调试
2. Webhook 模式: 需要公网服务器或内网穿透

使用方式:
1. 在飞书开放平台创建企业自建应用
2. 事件订阅方式选择 "使用长连接接收事件" (WebSocket 模式)
   或配置事件订阅地址 (Webhook 模式)
3. 订阅事件: im.message.receive_v1
4. 发布应用并添加到群聊

依赖: pip install lark-oapi
"""

import asyncio
import hashlib
import json
import multiprocessing
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..gateway import IncomingMessage


@dataclass
class FeishuConfig:
    """飞书应用配置"""

    app_id: str
    app_secret: str
    encrypt_key: str = ""
    verify_token: str = ""
    use_websocket: bool = True  # 默认使用 WebSocket 长连接模式


class FeishuChannel:
    """
    飞书通道实现

    支持:
    - WebSocket 长连接模式 (推荐): 无需公网 IP
    - Webhook 模式: 需要公网服务器
    - 私聊消息
    - 群聊 @机器人
    - 文本、图片消息
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, port: int = 8081):
        self.config = config
        self.port = port
        self._client = None
        self._ws_process = None
        self._message_queue = None
        self._log_queue = None
        self._on_message: Optional[Callable] = None
        self._server = None
        self._app = None
        self._running = False

    def _get_client(self):
        """获取飞书客户端（延迟加载）"""
        if self._client is None:
            try:
                import lark_oapi as lark

                self._client = (
                    lark.Client.builder()
                    .app_id(self.config.app_id)
                    .app_secret(self.config.app_secret)
                    .log_level(lark.LogLevel.ERROR)
                    .build()
                )
            except ImportError:
                raise ImportError(
                    "lark-oapi is required for Feishu channel. "
                    "Install it with: pip install lark-oapi"
                )
        return self._client

    async def send(self, to: str, message: str, msg_type: str = "text") -> bool:
        """
        发送消息到飞书

        Args:
            to: open_id (私聊) 或 chat_id (群聊)
            message: 消息内容
            msg_type: 消息类型 (text, post, image 等)

        Returns:
            是否发送成功
        """
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )

            client = self._get_client()

            # 构建消息内容
            if msg_type == "text":
                content = json.dumps({"text": message})
            else:
                content = message

            # 判断是 open_id 还是 chat_id
            receive_id_type = "open_id"
            if to.startswith("oc_"):
                receive_id_type = "chat_id"

            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(to)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )

            response = client.im.v1.message.create(request)

            if not response.success():
                print(f"[Feishu] Send failed: {response.code} - {response.msg}")
                return False

            return True

        except Exception as e:
            print(f"[Feishu] Send error: {e}")
            return False

    async def start(self, on_message: Callable) -> None:
        """启动飞书通道 (WebSocket 长连接或 Webhook)"""
        self._on_message = on_message
        self._running = True

        if self.config.use_websocket:
            await self._start_websocket()
        else:
            await self._start_webhook()

    async def _start_websocket(self) -> None:
        """启动 WebSocket 长连接模式"""
        try:
            import lark_oapi  # noqa: F401
        except ImportError:
            raise ImportError(
                "lark-oapi is required for Feishu WebSocket. "
                "Install it with: pip install lark-oapi"
            )

        # 使用多进程来隔离事件循环
        ctx = multiprocessing.get_context("spawn")
        self._message_queue = ctx.Queue()
        self._log_queue = ctx.Queue()
        self._ws_process = ctx.Process(
            target=_run_ws_client,
            args=(
                self.config.app_id,
                self.config.app_secret,
                self._message_queue,
                self._log_queue,
            ),
            daemon=True,
        )
        self._ws_process.start()

        # 启动消息监听任务
        asyncio.create_task(self._listen_ws_messages())
        asyncio.create_task(self._listen_ws_logs())

        print("[Feishu] WebSocket 长连接已启动 (无需公网 IP)")

    async def _listen_ws_messages(self) -> None:
        """监听来自 WebSocket 进程的消息"""
        while self._running:
            try:
                if not self._message_queue.empty():
                    msg_data = self._message_queue.get_nowait()
                    await self._process_ws_message_data(msg_data)
                await asyncio.sleep(0.1)
            except Exception as e:
                if self._running:
                    print(f"[Feishu] Error listening messages: {e}")
                await asyncio.sleep(1)

    async def _listen_ws_logs(self) -> None:
        """监听来自 WebSocket 进程的日志"""
        while self._running:
            try:
                if not self._log_queue.empty():
                    log_msg = self._log_queue.get_nowait()
                    print(log_msg)
                await asyncio.sleep(0.05)
            except Exception:
                await asyncio.sleep(0.5)

    async def _process_ws_message_data(self, msg_data: dict) -> None:
        """处理来自 WebSocket 进程的消息数据"""
        try:
            content = msg_data.get("content")
            if not content:
                return

            open_id = msg_data.get("open_id", "unknown")
            chat_id = msg_data.get("chat_id", "")
            chat_type = msg_data.get("chat_type", "")

            group_id = chat_id if chat_type == "group" else None

            msg = IncomingMessage(
                channel=self.name,
                sender=open_id,
                content=content,
                group_id=group_id,
                metadata=msg_data.get("metadata", {}),
            )

            if self._on_message:
                response = await self._on_message(msg)
                if response:
                    reply_to = chat_id if chat_id else open_id
                    await self.send(reply_to, response)

        except Exception as e:
            print(f"[Feishu] Error processing message: {e}")

    async def _start_webhook(self) -> None:
        """启动 Webhook 服务器模式"""
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError(
                "aiohttp is required for Feishu webhook. "
                "Install it with: pip install aiohttp"
            )

        self._app = web.Application()
        self._app.router.add_post("/feishu/webhook", self._handle_webhook)
        self._app.router.add_get("/feishu/health", self._health)

        runner = web.AppRunner(self._app)
        await runner.setup()
        self._server = web.TCPSite(runner, "0.0.0.0", self.port)
        await self._server.start()

        print(
            f"[Feishu] Webhook listening on http://0.0.0.0:{self.port}/feishu/webhook"
        )

    async def stop(self) -> None:
        """停止服务"""
        self._running = False
        if self._ws_process:
            self._ws_process.terminate()
            self._ws_process.join(timeout=2)
            self._ws_process = None
        if self._server:
            await self._server.stop()

    async def _health(self, request):
        """健康检查"""
        from aiohttp import web

        return web.json_response({"status": "ok", "channel": "feishu"})

    async def _handle_webhook(self, request):
        """处理飞书 Webhook 事件"""
        from aiohttp import web

        try:
            body = await request.text()

            # 验证签名（如果配置了）
            if self.config.verify_token:
                signature = request.headers.get("X-Lark-Signature", "")
                timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
                nonce = request.headers.get("X-Lark-Request-Nonce", "")

                if not self._verify_signature(body, signature, timestamp, nonce):
                    return web.json_response(
                        {"code": -1, "msg": "Invalid signature"}, status=401
                    )

            data = json.loads(body)

            # URL 验证
            if data.get("type") == "url_verification":
                challenge = data.get("challenge", "")
                return web.json_response({"challenge": challenge})

            # 处理事件
            if data.get("type") == "event_callback":
                event = data.get("event", {})
                await self._process_event(event)

            return web.json_response({"code": 0})

        except json.JSONDecodeError:
            return web.json_response({"code": -1, "msg": "Invalid JSON"}, status=400)
        except Exception as e:
            print(f"[Feishu] Webhook error: {e}")
            return web.json_response({"code": -1, "msg": str(e)}, status=500)

    def _verify_signature(
        self, body: str, signature: str, timestamp: str, nonce: str
    ) -> bool:
        """验证飞书请求签名"""
        if not self.config.encrypt_key:
            return True

        import time

        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:
            return False

        token = self.config.encrypt_key
        sign_base = timestamp + nonce + token + body
        expected_signature = hashlib.sha256(sign_base.encode()).hexdigest()

        return signature == expected_signature

    async def _process_event(self, event: Dict[str, Any]):
        """处理飞书事件"""
        if event.get("type") != "im.message.receive_v1":
            return

        message = event.get("message", {})
        sender = event.get("sender", {})

        content = self._parse_message_content(message)
        if not content:
            return

        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id", "unknown")

        chat_type = message.get("chat_type", "")
        chat_id = message.get("chat_id", "")

        group_id = chat_id if chat_type == "group" else None

        msg = IncomingMessage(
            channel=self.name,
            sender=open_id,
            content=content,
            group_id=group_id,
            metadata={
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
                "message_type": message.get("message_type"),
            },
        )

        if self._on_message:
            try:
                response = await self._on_message(msg)
                if response:
                    reply_to = chat_id if chat_id else open_id
                    await self.send(reply_to, response)
            except Exception as e:
                print(f"[Feishu] Error processing message: {e}")

    def _parse_message_content(self, message: Dict[str, Any]) -> Optional[str]:
        """解析消息内容"""
        msg_type = message.get("message_type", "")
        content = message.get("content", "")

        if not content:
            return None

        try:
            content_data = json.loads(content)
        except json.JSONDecodeError:
            return content

        if msg_type == "text":
            return content_data.get("text", "")
        elif msg_type == "post":
            return self._extract_post_text(content_data)
        elif msg_type == "image":
            return "[图片]"
        elif msg_type == "audio":
            return "[语音]"
        elif msg_type == "file":
            return f"[文件] {content_data.get('file_name', '')}"

        return content

    def _extract_post_text(self, post_data: Dict) -> str:
        """从富文本中提取纯文本"""
        text_parts = []
        content = post_data.get("content", [])
        for paragraph in content:
            for element in paragraph:
                if isinstance(element, dict):
                    tag = element.get("tag", "")
                    if tag == "text":
                        text_parts.append(element.get("text", ""))
                    elif tag == "at":
                        text_parts.append(element.get("user_name", "@用户"))
                    elif tag == "link":
                        text_parts.append(element.get("text", element.get("href", "")))
        return "".join(text_parts)


def _run_ws_client(app_id: str, app_secret: str, message_queue, log_queue) -> None:
    """在独立进程中运行 WebSocket 客户端"""
    import lark_oapi as lark

    def log(msg: str):
        try:
            log_queue.put(f"[Feishu] {msg}")
        except Exception:
            pass

    def handle_message(data) -> None:
        try:
            event = data.event
            message = event.message
            sender = event.sender

            content = _parse_ws_content(message)
            if not content:
                return

            sender_id = sender.sender_id
            open_id = sender_id.open_id or "unknown"

            msg_data = {
                "content": content,
                "open_id": open_id,
                "chat_id": message.chat_id,
                "chat_type": message.chat_type,
                "metadata": {
                    "chat_id": message.chat_id,
                    "message_id": message.message_id,
                    "message_type": message.message_type,
                },
            }
            message_queue.put(msg_data)
        except Exception as e:
            log(f"Error: {e}")

    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(handle_message)
        .build()
    )

    ws_client = lark.ws.Client(
        app_id,
        app_secret,
        event_handler=event_handler,
        log_level=lark.LogLevel.ERROR,
    )
    log("WebSocket 已连接")
    ws_client.start()


def _parse_ws_content(message) -> Optional[str]:
    """解析 WebSocket 消息内容"""
    msg_type = message.message_type
    content = message.content

    if not content:
        return None

    try:
        content_data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return str(content) if content else None

    if msg_type == "text":
        return content_data.get("text", "")
    elif msg_type == "post":
        return _extract_post_text_ws(content_data)
    elif msg_type == "image":
        return "[图片]"
    elif msg_type == "audio":
        return "[语音]"
    elif msg_type == "file":
        return f"[文件] {content_data.get('file_name', '')}"

    return str(content) if content else None


def _extract_post_text_ws(post_data: dict) -> str:
    """从富文本中提取纯文本"""
    text_parts = []
    content = post_data.get("content", [])
    for paragraph in content:
        for element in paragraph:
            if isinstance(element, dict):
                tag = element.get("tag", "")
                if tag == "text":
                    text_parts.append(element.get("text", ""))
                elif tag == "at":
                    text_parts.append(element.get("user_name", "@用户"))
                elif tag == "link":
                    text_parts.append(element.get("text", element.get("href", "")))
    return "".join(text_parts)
