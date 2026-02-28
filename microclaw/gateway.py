"""
Gateway - The Central Orchestrator (OpenClaw-style)

The Gateway is the hub that connects everything:
- Routes messages from channels (CLI, Webhook, etc.)
- Manages sessions with proper keys and reset policies
- Coordinates the agent
- Handles persistence and lifecycle
- Emits events for extensibility
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

# === Channel Protocol ===

class Channel(Protocol):
    """Protocol for message channels."""
    
    name: str
    
    async def send(self, to: str, message: str) -> bool:
        """Send a message through this channel."""
        ...
    
    async def start(self, on_message: Callable) -> None:
        """Start listening for messages."""
        ...
    
    async def stop(self) -> None:
        """Stop the channel."""
        ...


# === Message Types ===

@dataclass
class IncomingMessage:
    """A message received from a channel."""
    
    channel: str
    sender: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Optional metadata
    group_id: Optional[str] = None  # For group messages
    reply_to: Optional[str] = None  # Message being replied to
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_group(self) -> bool:
        return self.group_id is not None
    
    def get_session_key(self, agent_id: str = "main", dm_scope: str = "main") -> SessionKey:
        """
        Generate the appropriate session key for this message.
        
        dm_scope options:
        - "main": all DMs share the main session
        - "per-peer": isolate by sender
        - "per-channel-peer": isolate by channel + sender
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


# === Gateway Configuration ===

@dataclass
class GatewayConfig:
    """Configuration for the Gateway."""

    # Storage
    storage_dir: str = "~/.microclaw"

    # Agent settings
    default_model: str = "gpt-4o-mini"
    default_provider: str = "openai"
    base_url: Optional[str] = None  # For OpenAI-compatible APIs
    api_key: Optional[str] = None   # Custom API key

    # Session settings
    dm_scope: str = "main"  # main, per-peer, per-channel-peer
    reset_mode: str = "daily"  # daily, idle, both
    reset_hour: int = 4  # Hour for daily reset
    idle_minutes: Optional[int] = None

    # Owner (privileged user IDs)
    owner_ids: List[str] = field(default_factory=list)

    # Base system prompt (workspace files are appended)
    system_prompt: Optional[str] = None


# === Gateway ===

class Gateway:
    """
    The central orchestrator that connects everything.
    
    Features:
    - Multi-channel message routing
    - OpenClaw-style session management
    - Workspace-based memory
    - Event system for extensibility
    """
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        
        # Resolve paths
        self._base_dir = Path(self.config.storage_dir).expanduser()
        self._base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self._channels: Dict[str, Channel] = {}
        self._tools = ToolRegistry()
        
        # Session store with reset policy
        reset_policy = ResetPolicy(
            mode=self.config.reset_mode,
            at_hour=self.config.reset_hour,
            idle_minutes=self.config.idle_minutes
        )
        
        self._sessions = SessionStore(
            storage_dir=str(self._base_dir / "sessions"),
            reset_policy=reset_policy
        )
        
        # Workspace
        self._workspace = WorkspaceFiles(MemoryConfig(
            workspace_dir=str(self._base_dir / "workspace")
        ))
        self._workspace.initialize_defaults()
        
        # Agent (created lazily)
        self._agent: Optional[Agent] = None
        
        # Event handlers
        self._handlers: Dict[str, List[Callable]] = {}
        
        # State
        self._running = False
    
    @property
    def agent(self) -> Agent:
        """Get or create the agent."""
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
        """Get the workspace."""
        return self._workspace
    
    @property
    def sessions(self) -> SessionStore:
        """Get the session store."""
        return self._sessions
    
    # === Channel Management ===
    
    def add_channel(self, channel: Channel) -> "Gateway":
        """Register a message channel."""
        self._channels[channel.name] = channel
        return self
    
    def get_channel(self, name: str) -> Optional[Channel]:
        """Get a channel by name."""
        return self._channels.get(name)
    
    # === Tool Management ===
    
    def add_tool(self, tool: Tool) -> "Gateway":
        """Register a tool."""
        self._tools.register(tool)
        return self
    
    # === Event System ===
    
    def on(self, event: str, handler: Callable) -> "Gateway":
        """Register an event handler."""
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)
        return self
    
    async def _emit(self, event: str, *args, **kwargs):
        """Emit an event to all handlers."""
        for handler in self._handlers.get(event, []):
            try:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                print(f"Error in event handler for {event}: {e}")
    
    # === Message Handling ===
    
    async def handle_message(self, msg: IncomingMessage) -> str:
        """
        Handle an incoming message.
        
        This is the main entry point for all messages from channels.
        """
        await self._emit("message_received", msg)
        
        # Get or create session
        session_key = msg.get_session_key(
            agent_id="main",
            dm_scope=self.config.dm_scope
        )
        session = self._sessions.get(session_key)
        
        # Update session origin
        session.origin = {
            "channel": msg.channel,
            "sender": msg.sender,
            "group_id": msg.group_id,
        }
        
        # Check for slash commands
        if msg.content.startswith("/"):
            response = await self._handle_slash_command(msg.content, session)
            if response is not None:
                await self._emit("response_ready", msg, response)
                return response
        
        # Tool callback
        def on_tool(event: str, name: str, data: Any):
            asyncio.create_task(
                self._emit("tool_call", event, name, data)
            )
        
        # Determine if this is the main session (for memory loading)
        is_main = not msg.is_group and self.config.dm_scope == "main"
        
        # Run the agent
        try:
            response = await self.agent.run(
                message=msg.content,
                session=session,
                on_tool_call=on_tool,
                is_main_session=is_main
            )
        except Exception as e:
            response = f"Error processing message: {e}"
            await self._emit("error", e)
        
        # Save session
        self._sessions.save(session)
        
        await self._emit("response_ready", msg, response)
        
        return response
    
    async def _handle_slash_command(
        self,
        content: str,
        session: Session
    ) -> Optional[str]:
        """
        Handle slash commands.
        
        Returns response string if handled, None to pass through to agent.
        """
        parts = content.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if cmd == "/status":
            return self._format_status(session)
        
        elif cmd in ("/new", "/reset"):
            new_session = self._sessions.reset(session.key)
            return f"🔄 Session reset. New ID: {new_session.session_id}"
        
        elif cmd == "/help":
            return self._format_help()
        
        elif cmd == "/context":
            context = self._workspace.build_context(is_main_session=True)
            return f"📄 Context length: {len(context)} chars\n\n{context[:2000]}..."
        
        # Unknown command - pass to agent
        return None
    
    def _format_status(self, session: Session) -> str:
        """Format status information."""
        lines = [
            "📊 **Status**",
            "",
            f"**Session:** {session.key}",
            f"**ID:** {session.session_id}",
            f"**Messages:** {len(session.messages)}",
            f"**Tokens:** {session.total_tokens:,}",
            f"**Compactions:** {session.compaction_count}",
            f"**Model:** {self.config.default_provider}/{self.config.default_model}",
            f"**Updated:** {session.updated_at.strftime('%Y-%m-%d %H:%M')}",
        ]
        return "\n".join(lines)
    
    def _format_help(self) -> str:
        """Format help information."""
        return """📖 **Commands**

`/status` - Show session status
`/new` or `/reset` - Reset the session
`/context` - Show current context
`/help` - Show this help

Type normally to chat with the assistant."""
    
    # === Sending Messages ===
    
    async def send(
        self,
        channel: str,
        to: str,
        message: str
    ) -> bool:
        """Send a message through a channel."""
        chan = self._channels.get(channel)
        if not chan:
            raise ValueError(f"Unknown channel: {channel}")
        
        return await chan.send(to, message)
    
    # === Lifecycle ===
    
    async def start(self):
        """Start all channels and begin processing."""
        self._running = True
        await self._emit("starting")
        
        # Start all channels
        for name, channel in self._channels.items():
            try:
                await channel.start(self.handle_message)
                print(f"✓ Channel started: {name}")
            except Exception as e:
                print(f"✗ Failed to start {name}: {e}")
        
        await self._emit("started")
        
        # Keep running
        while self._running:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop all channels and shutdown."""
        self._running = False
        await self._emit("stopping")
        
        for channel in self._channels.values():
            try:
                await channel.stop()
            except Exception:
                pass
        
        await self._emit("stopped")
    
    def run(self):
        """Convenience method to run the gateway."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            asyncio.run(self.stop())


# === Built-in Channels ===

class CLIChannel:
    """Simple CLI channel for testing."""
    
    name = "cli"
    
    def __init__(self, user_id: str = "user"):
        self.user_id = user_id
        self._on_message: Optional[Callable] = None
        self._running = False
    
    async def send(self, to: str, message: str) -> bool:
        print(f"\n🤖 {message}\n")
        return True
    
    async def start(self, on_message: Callable) -> None:
        self._on_message = on_message
        self._running = True
        asyncio.create_task(self._input_loop())
    
    async def _input_loop(self):
        """Read user input."""
        print("\n🦞 MicroClaw ready. Type your message (Ctrl+C to quit):\n")
        
        while self._running:
            try:
                loop = asyncio.get_event_loop()
                line = await loop.run_in_executor(
                    None,
                    lambda: input("You: ")
                )
                
                if not line.strip():
                    continue
                
                msg = IncomingMessage(
                    channel=self.name,
                    sender=self.user_id,
                    content=line.strip()
                )
                
                response = await self._on_message(msg)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                break
    
    async def stop(self) -> None:
        self._running = False


class WebhookChannel:
    """HTTP webhook channel."""
    
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
            print("aiohttp required for webhook: pip install aiohttp")
            return
        
        app = web.Application()
        app.router.add_post("/message", self._handle_webhook)
        app.router.add_get("/health", self._health)
        
        runner = web.AppRunner(app)
        await runner.setup()
        self._server = web.TCPSite(runner, self.host, self.port)
        await self._server.start()
        
        print(f"Webhook listening on http://{self.host}:{self.port}")
    
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
