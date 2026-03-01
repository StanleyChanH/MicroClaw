"""
MicroClaw - 轻量级 Python Agent 编排框架

借鉴 OpenClaw 的架构设计，展示了 Agent AI 的核心模式:
工具使用、会话、记忆和 Agent 循环。

核心组件:
- Tool: 基于装饰器的工具系统
- Session: OpenClaw 风格的会话管理，支持键、重置和压缩
- Memory: 基于工作区的记忆 (SOUL.md、USER.md、MEMORY.md、每日笔记)
- Agent: 思考 -> 行动 -> 观察循环
- Gateway: 带有通道和事件的中央编排器
- TUI: Rich 终端界面
"""

from .agent import Agent, AgentBuilder, AgentConfig, ThinkingLevel
from .channels import FeishuChannel, FeishuConfig
from .gateway import CLIChannel, Gateway, GatewayConfig, IncomingMessage, WebhookChannel
from .memory import (
    MemoryConfig,
    MemorySearch,
    WorkspaceFiles,
    create_memory_tools,
)
from .session import (
    Compactor,
    Message,
    MessageRole,
    ResetPolicy,
    Session,
    SessionKey,
    SessionStore,
)
from .tools import Tool, ToolRegistry, tool

__version__ = "0.1.0"

__all__ = [
    # 工具
    "Tool",
    "ToolRegistry",
    "tool",
    # 会话
    "Session",
    "SessionStore",
    "SessionKey",
    "ResetPolicy",
    "Message",
    "MessageRole",
    "Compactor",
    # 记忆
    "WorkspaceFiles",
    "MemoryConfig",
    "MemorySearch",
    "create_memory_tools",
    # Agent
    "Agent",
    "AgentConfig",
    "AgentBuilder",
    "ThinkingLevel",
    # Gateway
    "Gateway",
    "GatewayConfig",
    "IncomingMessage",
    "CLIChannel",
    "WebhookChannel",
    # 通道
    "FeishuChannel",
    "FeishuConfig",
]
