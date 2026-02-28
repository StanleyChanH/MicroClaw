"""
Feishu/Lark Channel - 支持私聊和群聊 @机器人

使用方式:
1. 在飞书开放平台创建企业自建应用
2. 配置事件订阅地址: http://your-server:8081/feishu/webhook
3. 订阅事件: im.message.receive_v1
4. 发布应用并添加到群聊

依赖: pip install lark-oapi
"""

import hashlib
import json
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


class FeishuChannel:
    """
    飞书通道实现

    支持:
    - 私聊消息
    - 群聊 @机器人
    - 文本、图片消息
    """

    name = "feishu"

    def __init__(self, config: FeishuConfig, port: int = 8081):
        self.config = config
        self.port = port
        self._client = None
        self._on_message: Optional[Callable] = None
        self._server = None
        self._app = None

    def _get_client(self):
        """获取飞书客户端（延迟加载）"""
        if self._client is None:
            try:
                import lark_oapi as lark
                self._client = lark.Client.builder() \
                    .app_id(self.config.app_id) \
                    .app_secret(self.config.app_secret) \
                    .log_level(lark.LogLevel.ERROR) \
                    .build()
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
            import lark_oapi as lark
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
            # open_id 通常以 ou_ 开头，chat_id 以 oc_ 开头
            receive_id_type = lark.ReceiveIdType.OPEN_ID
            if to.startswith("oc_"):
                receive_id_type = lark.ReceiveIdType.CHAT_ID

            request = CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(CreateMessageRequestBody.builder()
                    .receive_id(to)
                    .msg_type(msg_type)
                    .content(content)
                    .build()) \
                .build()

            response = client.im.v1.message.create(request)

            if not response.success():
                print(f"Feishu send failed: {response.code} - {response.msg}")
                return False

            return True

        except Exception as e:
            print(f"Feishu send error: {e}")
            return False

    async def start(self, on_message: Callable) -> None:
        """启动 Webhook 服务器"""
        self._on_message = on_message

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

        print(f"Feishu webhook listening on http://0.0.0.0:{self.port}/feishu/webhook")

    async def stop(self) -> None:
        """停止服务"""
        if self._server:
            await self._server.stop()

    async def _health(self, request):
        """健康检查"""
        from aiohttp import web
        return web.json_response({"status": "ok", "channel": "feishu"})

    async def _handle_webhook(self, request):
        """
        处理飞书 Webhook 事件

        飞书会发送以下类型:
        - url_verification: 首次配置时验证
        - 事件回调: 实际的消息事件
        """
        from aiohttp import web

        try:
            # 读取请求体
            body = await request.text()

            # 验证签名（如果配置了）
            if self.config.verify_token:
                signature = request.headers.get("X-Lark-Signature", "")
                timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
                nonce = request.headers.get("X-Lark-Request-Nonce", "")

                if not self._verify_signature(body, signature, timestamp, nonce):
                    err = {"code": -1, "msg": "Invalid signature"}
                    return web.json_response(err, status=401)

            data = json.loads(body)

            # URL 验证（飞书配置事件订阅时会发送）
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
            print(f"Feishu webhook error: {e}")
            return web.json_response({"code": -1, "msg": str(e)}, status=500)

    def _verify_signature(
        self, body: str, signature: str, timestamp: str, nonce: str
    ) -> bool:
        """验证飞书请求签名"""
        if not self.config.encrypt_key:
            return True

        import time
        # 防重放攻击：检查时间戳
        current_time = int(time.time())
        if abs(current_time - int(timestamp)) > 300:  # 5分钟有效期
            return False

        # 计算签名
        token = self.config.encrypt_key
        sign_base = timestamp + nonce + token + body
        expected_signature = hashlib.sha256(sign_base.encode()).hexdigest()

        return signature == expected_signature

    async def _process_event(self, event: Dict[str, Any]):
        """处理飞书事件"""
        event_type = event.get("type", "")

        # 只处理消息接收事件
        if event_type != "im.message.receive_v1":
            return

        message = event.get("message", {})
        sender = event.get("sender", {})

        # 解析消息内容
        content = self._parse_message_content(message)
        if not content:
            return

        # 获取发送者信息
        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id", "unknown")

        # 判断是群聊还是私聊
        chat_type = message.get("chat_type", "")
        chat_id = message.get("chat_id", "")

        group_id = None
        if chat_type == "group":
            group_id = chat_id

        # 构造 IncomingMessage
        msg = IncomingMessage(
            channel=self.name,
            sender=open_id,
            content=content,
            group_id=group_id,
            metadata={
                "chat_id": chat_id,
                "message_id": message.get("message_id"),
                "message_type": message.get("message_type"),
            }
        )

        # 调用回调处理消息
        if self._on_message:
            try:
                response = await self._on_message(msg)

                # 自动回复
                if response:
                    # 优先回复到群聊/私聊的 chat_id
                    reply_to = chat_id if chat_id else open_id
                    await self.send(reply_to, response)

            except Exception as e:
                print(f"Error processing Feishu message: {e}")

    def _parse_message_content(self, message: Dict[str, Any]) -> Optional[str]:
        """
        解析消息内容

        支持: 文本、富文本、图片等
        """
        msg_type = message.get("message_type", "")
        content = message.get("content", "")

        if not content:
            return None

        try:
            content_data = json.loads(content)
        except json.JSONDecodeError:
            return content

        if msg_type == "text":
            # 文本消息
            return content_data.get("text", "")

        elif msg_type == "post":
            # 富文本消息 - 提取纯文本
            return self._extract_post_text(content_data)

        elif msg_type == "image":
            # 图片消息
            return "[图片]"

        elif msg_type == "audio":
            # 语音消息
            return "[语音]"

        elif msg_type == "file":
            # 文件消息
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
