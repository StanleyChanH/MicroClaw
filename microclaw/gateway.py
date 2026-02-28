"""
Gateway - 中央编排器 (OpenClaw 风格)

Gateway 是连接一切的中心:
- 从通道 (CLI、Webhook 等) 路由消息
- 使用正确的键和重置策略管理会话
- 协调 Agent
- 处理持久化和生命周期
- 发出事件以支持扩展
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

from .agent import Agent, AgentConfig
from .memory import MemoryConfig, WorkspaceFiles
from .session import ResetPolicy, Session, SessionKey, SessionStore
from .tools import Tool, ToolRegistry

# === 通道协议 ===

class Channel(Protocol):
    """消息通道协议。"""

    name: str

    async def send(self, to: str, message: str) -> bool:
        """通过此通道发送消息。"""
        ...

    async def start(self, on_message: Callable) -> None:
        """开始监听消息。"""
        ...

    async def stop(self) -> None:
        """停止通道。"""
        ...


# === 消息类型 ===

@dataclass
class IncomingMessage:
    """从通道接收的消息。"""

    channel: str
    sender: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)

    # 可选元数据
    group_id: Optional[str] = None  # 用于群组消息
    reply_to: Optional[str] = None  # 被回复的消息
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_group(self) -> bool:
        return self.group_id is not None

    def get_session_key(self, agent_id: str = "main", dm_scope: str = "main") -> SessionKey:
        """
        为此消息生成适当的会话键。

        dm_scope 选项:
        - "main": 所有私聊共享主会话
        - "per-peer": 按发送者隔离
        - "per-channel-peer": 按通道 + 发送者隔离
        """
        if self.is_group:
            return SessionKey.for_group(
                group_id=self.group_id,
                agent_id=agent_id,
                channel=self.channel
            )

        if dm_scope == "main":
            return SessionKey.for_dm(agent_id=agent_id)
        elif dm_scope == "per-peer":
            return SessionKey.for_dm(agent_id=agent_id, peer_id=self.sender)
        elif dm_scope == "per-channel-peer":
            return SessionKey.for_dm(agent_id=agent_id, peer_id=self.sender, channel=self.channel)
        else:
            return SessionKey.for_dm(agent_id=agent_id)


# === Gateway 配置 ===

@dataclass
class GatewayConfig:
    """Gateway 配置。"""

    # 存储
    storage_dir: str = "~/.microclaw"

    # Agent 设置
    default_model: str = "gpt-4o-mini"
    default_provider: str = "openai"
    base_url: Optional[str] = None  # 用于 OpenAI 兼容 API
    api_key: Optional[str] = None   # 自定义 API 密钥

    # 会话设置
    dm_scope: str = "main"  # main, per-peer, per-channel-peer
    reset_mode: str = "daily"  # daily, idle, both
    reset_hour: int = 4  # 每日重置的小时
    idle_minutes: Optional[int] = None

    # 所有者 (特权用户 ID)
    owner_ids: List[str] = field(default_factory=list)

    # 基础系统提示 (工作区文件会被追加)
    system_prompt: Optional[str] = None


# === Gateway ===

class Gateway:
    """
    连接一切的中央编排器。

    特性:
    - 多通道消息路由
    - OpenClaw 风格的会话管理
    - 基于工作区的记忆
    - 事件系统支持扩展
    """

    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()

        # 解析路径
        self._base_dir = Path(self.config.storage_dir).expanduser()
        self._base_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self._channels: Dict[str, Channel] = {}
        self._tools = ToolRegistry()

        # 带有重置策略的会话存储
        reset_policy = ResetPolicy(
            mode=self.config.reset_mode,
            at_hour=self.config.reset_hour,
            idle_minutes=self.config.idle_minutes
        )

        self._sessions = SessionStore(
            storage_dir=str(self._base_dir / "sessions"),
            reset_policy=reset_policy
        )

        # 工作区
        self._workspace = WorkspaceFiles(MemoryConfig(
            workspace_dir=str(self._base_dir / "workspace")
        ))
        self._workspace.initialize_defaults()

        # Agent (延迟创建)
        self._agent: Optional[Agent] = None

        # 事件处理器
        self._handlers: Dict[str, List[Callable]] = {}

        # 状态
        self._running = False

    @property
    def agent(self) -> Agent:
        """获取或创建 Agent。"""
        if self._agent is None:
            agent_config = AgentConfig(
                model=self.config.default_model,
                provider=self.config.default_provider,
                workspace_dir=str(self._base_dir / "workspace"),
                base_url=self.config.base_url,
                api_key=self.config.api_key,
            )

            if self.config.system_prompt:
                agent_config.system_prompt = self.config.system_prompt

            self._agent = Agent(config=agent_config, tools=self._tools)

        return self._agent

    @property
    def workspace(self) -> WorkspaceFiles:
        """获取工作区。"""
        return self._workspace

    @property
    def sessions(self) -> SessionStore:
        """获取会话存储。"""
        return self._sessions

    # === 通道管理 ===

    def add_channel(self, channel: Channel) -> "Gateway":
        """注册消息通道。"""
        self._channels[channel.name] = channel
        return self

    def get_channel(self, name: str) -> Optional[Channel]:
        """按名称获取通道。"""
        return self._channels.get(name)

    # === 工具管理 ===

    def add_tool(self, tool: Tool) -> "Gateway":
        """注册工具。"""
        self._tools.register(tool)
        return self

    # === 事件系统 ===

    def on(self, event: str, handler: Callable) -> "Gateway":
        """注册事件处理器。"""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        return self

    async def _emit(self, event: str, *args, **kwargs):
        """向所有处理器发出事件。"""
        for handler in self._handlers.get(event, []):
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"事件处理器错误 {event}: {e}")

    # === 消息处理 ===

    async def handle_message(self, msg: IncomingMessage) -> str:
        """
        处理传入的消息。

        这是所有来自通道的消息的主入口点。
        """
        await self._emit("message_received", msg)

        # 获取或创建会话
        session_key = msg.get_session_key(
            agent_id="main",
            dm_scope=self.config.dm_scope
        )
        session = self._sessions.get(session_key)

        # 更新会话来源
        session.origin = {
            "channel": msg.channel,
            "sender": msg.sender,
            "group_id": msg.group_id,
        }

        # 检查斜杠命令
        if msg.content.startswith("/"):
            response = await self._handle_slash_command(msg.content, session)
            if response is not None:
                await self._emit("response_ready", msg, response)
                return response

        # 工具回调
        def on_tool(event: str, name: str, data: Any):
            asyncio.create_task(
                self._emit("tool_call", event, name, data)
            )

        # 确定是否为主会话 (用于记忆加载)
        is_main = not msg.is_group and self.config.dm_scope == "main"

        # 运行 Agent
        try:
            response = await self.agent.run(
                message=msg.content,
                session=session,
                on_tool_call=on_tool,
                is_main_session=is_main
            )
        except Exception as e:
            response = f"处理消息时出错: {e}"
            await self._emit("error", e)

        # 保存会话
        self._sessions.save(session)

        await self._emit("response_ready", msg, response)

        return response

    async def _handle_slash_command(
        self,
        content: str,
        session: Session
    ) -> Optional[str]:
        """
        处理斜杠命令。

        如果已处理则返回响应字符串，传递给 Agent 则返回 None。
        """
        parts = content.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/status":
            return self._format_status(session)

        elif cmd in ("/new", "/reset"):
            new_session = self._sessions.reset(session.key)
            return f"[重置] 会话已重置。新 ID: {new_session.session_id}"

        elif cmd == "/help":
            return self._format_help()

        elif cmd == "/context":
            context = self._workspace.build_context(is_main_session=True)
            return f"[上下文] 长度: {len(context)} 字符\n\n{context[:2000]}..."

        # 未知命令 - 传递给 Agent
        return None

    def _format_status(self, session: Session) -> str:
        """格式化状态信息。"""
        lines = [
            "[状态]",
            "",
            f"**会话:** {session.key}",
            f"**ID:** {session.session_id}",
            f"**消息数:** {len(session.messages)}",
            f"**Token:** {session.total_tokens:,}",
            f"**压缩次数:** {session.compaction_count}",
            f"**模型:** {self.config.default_provider}/{self.config.default_model}",
            f"**更新时间:** {session.updated_at.strftime('%Y-%m-%d %H:%M')}",
        ]
        return "\n".join(lines)

    def _format_help(self) -> str:
        """格式化帮助信息。"""
        return """[命令]

`/status` - 显示会话状态
`/new` 或 `/reset` - 重置会话
`/context` - 显示当前上下文
`/help` - 显示此帮助

正常输入以与助手对话。"""

    # === 发送消息 ===

    async def send(
        self,
        channel: str,
        to: str,
        message: str
    ) -> bool:
        """通过通道发送消息。"""
        chan = self._channels.get(channel)
        if not chan:
            raise ValueError(f"未知的通道: {channel}")

        return await chan.send(to, message)

    # === 生命周期 ===

    async def start(self):
        """启动所有通道并开始处理。"""
        self._running = True
        await self._emit("starting")

        # 启动所有通道
        for name, channel in self._channels.items():
            try:
                await channel.start(self.handle_message)
                print(f"[OK] 通道已启动: {name}")
            except Exception as e:
                print(f"[FAIL] 启动失败 {name}: {e}")

        await self._emit("started")

        # 保持运行
        while self._running:
            await asyncio.sleep(1)

    async def stop(self):
        """停止所有通道并关闭。"""
        self._running = False
        await self._emit("stopping")

        for channel in self._channels.values():
            try:
                await channel.stop()
            except Exception:
                pass

        await self._emit("stopped")

    def run(self):
        """运行 Gateway 的便捷方法。"""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            asyncio.run(self.stop())


# === 内置通道 ===

class CLIChannel:
    """用于测试的简单 CLI 通道。"""

    name = "cli"

    def __init__(self, user_id: str = "user"):
        self.user_id = user_id
        self._on_message: Optional[Callable] = None
        self._running = False

    async def send(self, to: str, message: str) -> bool:
        print(f"\n[机器人] {message}\n")
        return True

    async def start(self, on_message: Callable) -> None:
        self._on_message = on_message
        self._running = True
        asyncio.create_task(self._input_loop())

    async def _input_loop(self):
        """读取用户输入。"""
        print("\n[MicroClaw] 就绪。输入消息 (Ctrl+C 退出):\n")

        while self._running:
            try:
                loop = asyncio.get_event_loop()
                line = await loop.run_in_executor(
                    None,
                    lambda: input("你: ")
                )

                if not line.strip():
                    continue

                msg = IncomingMessage(
                    channel=self.name,
                    sender=self.user_id,
                    content=line.strip()
                )

                response = await self._on_message(msg)

                # 打印响应 (安全处理 Unicode)
                if response:
                    try:
                        print(f"\n[助手] {response}\n")
                    except UnicodeEncodeError:
                        # Windows GBK 编码问题：移除 emoji
                        safe_response = response.encode('gbk', errors='replace').decode('gbk')
                        print(f"\n[助手] {safe_response}\n")

            except EOFError:
                break
            except KeyboardInterrupt:
                break

    async def stop(self) -> None:
        self._running = False


class WebhookChannel:
    """HTTP Webhook 通道。"""

    name = "webhook"

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._on_message: Optional[Callable] = None
        self._server = None

    async def send(self, to: str, message: str) -> bool:
        return True

    async def start(self, on_message: Callable) -> None:
        self._on_message = on_message

        try:
            from aiohttp import web
        except ImportError:
            print("webhook 需要 aiohttp: pip install aiohttp")
            return

        app = web.Application()
        app.router.add_post("/message", self._handle_webhook)
        app.router.add_get("/health", self._health)

        runner = web.AppRunner(app)
        await runner.setup()
        self._server = web.TCPSite(runner, self.host, self.port)
        await self._server.start()

        print(f"Webhook 监听于 http://{self.host}:{self.port}")

    async def _handle_webhook(self, request):
        from aiohttp import web

        try:
            data = await request.json()

            msg = IncomingMessage(
                channel=self.name,
                sender=data.get("sender", "unknown"),
                content=data.get("message", ""),
                group_id=data.get("group_id"),
                metadata=data.get("metadata", {})
            )

            response = await self._on_message(msg)

            return web.json_response({"response": response})

        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _health(self, request):
        from aiohttp import web
        return web.json_response({"status": "ok"})

    async def stop(self) -> None:
        if self._server:
            await self._server.stop()
