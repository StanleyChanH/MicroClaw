"""
MicroClaw - A minimal agent orchestration framework in Python

Inspired by OpenClaw's architecture, this demonstrates the core patterns
of agentic AI: tool use, sessions, memory, and the agent loop.

Key components:
- Tool: Decorator-based tool system
- Session: OpenClaw-style session management with keys, resets, and compaction
- Memory: Workspace-based memory (SOUL.md, USER.md, MEMORY.md, daily notes)
- Agent: The think → act → observe loop
- Gateway: Central orchestrator with channels and events
- TUI: Rich terminal interface
"""

from .agent import Agent, AgentBuilder, AgentConfig, ThinkingLevel
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
from .channels import FeishuChannel, FeishuConfig

__version__ = "0.1.0"

__all__ = [
    # Tools
    "Tool",
    "ToolRegistry",
    "tool",
    # Sessions
    "Session",
    "SessionStore",
    "SessionKey",
    "ResetPolicy",
    "Message",
    "MessageRole",
    "Compactor",
    # Memory
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
    # Channels
    "FeishuChannel",
    "FeishuConfig",
]
