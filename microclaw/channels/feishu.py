"""
Feishu/Lark Channel - WebSocket 长连接模式

支持私聊和群聊 @机器人，无需公网 IP，本地即可调试。

使用方式:
1. 在飞书开放平台创建企业自建应用
2. 事件订阅方式选择 "使用长连接接收事件"
3. 订阅事件: im.message.receive_v1
4. 发布应用并添加到群聊

依赖: pip install lark-oapi
"""

import asyncio
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


class FeishuChannel:
    """
    飞书通道实现 - WebSocket 长连接模式

    支持:
    - 无需公网 IP，本地即可调试
    - 私聊消息
    - 群聊 @机器人
    - 文本、图片消息
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig):
        self.config = config
        self._client = None
        self._ws_process = None
        self._message_queue = None
        self._log_queue = None
        self._on_message: Optional[Callable] = None
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
        """启动飞书通道 (WebSocket 长连接)"""
        self._on_message = on_message
        self._running = True

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

    async def stop(self) -> None:
        """停止服务"""
        self._running = False
        if self._ws_process:
            self._ws_process.terminate()
            self._ws_process.join(timeout=2)
            self._ws_process = None


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
