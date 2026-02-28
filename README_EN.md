# MicroClaw

<p align="center">
  <b>English</b> | <a href="README.md">中文</a>
</p>

<p align="center">
  <img src="images/banner.png" alt="MicroClaw Banner" width="100%">
</p>

A lightweight Python Agent orchest framework, inspired by [OpenClaw](https://github.com/openclaw/openclaw)'s architecture design.

The entire framework is about **3,000 lines of code**, designed to help you understand the core concepts of Agent systems:

- **Think-Act-Observe Loop**: The fundamental operating pattern of Agents
- **Session Management**: Support for per-user and per-group isolation with configurable daily auto-reset
- **Workspace Memory**: Store personality, user info, long-term memory, and daily logs in Markdown files
- **Skills System**: Define custom skills via YAML frontmatter format, shared across all sessions
- **Tools System**: Quickly define and register tools via decorators
- **Multi-Model Support**: OpenAI, Anthropic, Ollama, and various OpenAI API compatible services
- **Terminal Interface**: Interactive TUI based on Rich library
- **Feishu Integration**: Support for private chat and group chat @bot

## Quick Start (5 Minutes)

```bash
# Clone the project
git clone https://github.com/StanleyChanH/MicroClaw.git
cd microclaw

# Install dependencies (requires uv to be installed first)
uv sync

# Configure environment variables (copy template and fill in keys)
cp .env.example .env
# Edit .env file, set OPENAI_API_KEY and OPENAI_BASE_URL

# Launch TUI interface (recommended)
uv run microclaw tui
```

<p align="center">
  <img src="images/MicroClaw1.png" alt="MicroClaw TUI Screenshot" width="80%">
</p>

```bash
# Or launch simple CLI
uv run microclaw
```

**.env Configuration Example:**

```bash
# OpenAI compatible API (works with DeepSeek, Alibaba Tongyi, Moonshot, etc.)
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

# MicroClaw Configuration
MICROCLAW_MODEL=gpt-4o-mini
MICROCLAW_PROVIDER=openai
```

## System Architecture

```
┌──────────────────────────────────────┐
│           Channels Layer             │
│    CLI / Webhook / Feishu / Extensible│
└─────────────────┬────────────────────┘
                  ▼
┌──────────────────────────────────────┐
│            Gateway (Gateway)          │
│   Message Routing · Session · Events  │
└─────────────────┬────────────────────┘
                  ▼
┌──────────────────────────────────────┐
│           Agent Core Loop             │
│    Think → Call Tools → Observe → Loop│
└─────────────────┬────────────────────┘
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│Session Store │    │   Workspace   │
│              │    │              │
│ · JSONL Logs  │    │ · SOUL.md    │
│ · Auto Reset  │    │ · USER.md    │
│ · Compression │    │ · MEMORY.md  │
│              │    │ · skills/    │
└──────────────┘    └──────────────┘
```

## Core Features

### Session Management

Adopts OpenClaw's session key naming convention, flexibly supporting different scenarios:

```
agent:main:main                    # Default session
agent:main:dm:user123              # Per-user isolated private chat
agent:main:whatsapp:group:123456   # Group session
cron:daily-report                  # Scheduled task
```

Each session independently maintains conversation history, supporting:

- **Scheduled Reset**: Automatically clears at 4 AM daily (configurable)
- **Idle Timeout**: Automatically resets after long inactivity
- **Context Compression**: Automatically summarizes historical conversations when approaching token limit

### Workspace Memory

Manage Agent's "long-term memory" using plain text files in `~/.microclaw/workspace/` directory:

| File | Purpose |
|------|---------|
| `AGENTS.md` | Workspace instructions and Agent behavior guidelines |
| `SOUL.md` | Agent personality and behavior rules |
| `USER.md` | User's personal information and preferences |
| `MEMORY.md` | Important information to remember long-term (**main session only**, not loaded in group chats for privacy) |
| `memory/YYYY-MM-DD.md` | Daily logs, recording what happened each day |
| `skills/` | Skills directory for custom skills |

**Auto-loading**: The list of loaded files is displayed when TUI starts. All content is automatically injected into the system prompt, Agent doesn't need to manually read files.

### Skills System

MicroClaw supports loading custom skills from the workspace `skills/` directory. Skills use Claude Code style format:

**Directory Structure:**

```
~/.microclaw/workspace/skills/
├── my-skill/
│   └── skill.md
└── another-skill/
    └── skill.md
```

**skill.md Format (with YAML frontmatter):**

```markdown
---
name: my-skill
description: Skill description
version: 1.0.0
---

# Skill Title

Skill content...
- Always loaded: shared across all sessions
- Can define behavior rules, response styles, etc.
```

Skills are automatically loaded when building the system prompt, shared across all sessions.

### Multi-Model Support

```python
from microclaw import Agent, AgentConfig

# OpenAI
agent = Agent(AgentConfig(model="gpt-4o", provider="openai"))

# Anthropic Claude
agent = Agent(AgentConfig(model="claude-sonnet-4-20250514", provider="anthropic"))

# Local Model
agent = Agent(AgentConfig(model="llama3.2", provider="ollama"))

# OpenAI API Compatible Services (DeepSeek, Kimi, Zhipu, etc.)
agent = Agent(AgentConfig(
    model="deepseek-chat",
    provider="openai_compatible",
    base_url="https://api.deepseek.com"
))
```

### Custom Tools

Define tools using the `@tool` decorator:

```python
from microclaw import tool, Gateway

@tool(description="Query city weather")
def get_weather(city: str) -> str:
    # In real projects, can call weather API
    return f"{city}: Sunny, 22°C"

gateway = Gateway()
gateway.add_tool(get_weather)
```

## Command Line Usage

```bash
microclaw [command] [options]

Commands:
  (none)      Interactive CLI
  tui         Launch terminal interface
  gateway     Launch gateway service

Common Options:
  -m, --model      Specify model (default: gpt-4o-mini)
  -p, --provider   Specify provider (openai/anthropic/ollama/openai_compatible)
  --base-url       Custom API address
  --one-shot MSG   Single message then exit
```

### Connecting to Chinese LLMs

```bash
# DeepSeek
uv run microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat

# Kimi (Moonshot)
uv run microclaw -p openai_compatible --base-url https://api.moonshot.cn/v1 -m moonshot-v1-8k

# Zhipu GLM
uv run microclaw -p openai_compatible --base-url https://open.bigmodel.cn/api/paas/v4 -m glm-4

# Locally deployed vLLM
uv run microclaw -p openai_compatible --base-url http://localhost:8000/v1 -m your-model
```

Can also configure via environment variables:

```bash
export OPENAI_BASE_URL="https://api.deepseek.com"
export OPENAI_API_KEY="your-api-key"
uv run microclaw -p openai_compatible -m deepseek-chat
```

### Windows Compatibility

MicroClaw fully supports Windows! The system automatically handles platform differences:

**Shell Command Auto-Translation:**

| Unix Command | Windows Command |
|--------------|-----------------|
| `ls` | `dir` |
| `cat` | `type` |
| `rm` | `del` |
| `pwd` | `cd` |
| `which` | `where` |

Just use familiar Unix commands, the system will automatically translate to Windows equivalents.

**Recommended Terminals:**
- Windows Terminal (recommended)
- VSCode Terminal
- PowerShell 7+

> Note: Traditional CMD/PowerShell may display garbled Chinese characters due to terminal encoding limitations, but this doesn't affect functionality.

### Feishu Bot

Supports private chat and group chat @bot, can be used with Chinese LLMs like Alibaba Tongyi Qianwen.

**1. Install Dependencies:**

```bash
uv sync --extra feishu
```

**2. Configure Keys (copy template):**

```bash
cp .env.example .env
# Edit .env file, fill in real keys
```

**3. Run Feishu Bot:**

```bash
uv run python examples/feishu_qwen.py
```

**Local Testing (using ngrok tunnel):**

```bash
# Install ngrok: https://ngrok.com/download
# Start tunnel
ngrok http 8081
# Will get public address, like https://xxxx.ngrok-free.app

# Configure event subscription address in Feishu Open Platform:
# https://xxxx.ngrok-free.app/feishu/webhook
```

**Feishu Open Platform Configuration:**

1. Create enterprise self-built app, get App ID and App Secret
2. Event Subscription → Configure address
3. Subscribe to event: `im.message.receive_v1`
4. Permission Management → Add `im:message`, `im:message:send_as_bot`
5. Publish Version → Publish app
6. Add bot to group chat or enable private chat

**Supported LLM Providers:**

All OpenAI compatible APIs use `OPENAI_API_KEY` and `OPENAI_BASE_URL` environment variables:

| Provider | base_url | Model |
|----------|----------|-------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |
| Alibaba Tongyi | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.5-plus`, `qwen-turbo` |
| Moonshot | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |
| Zhipu GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |

**Code Example:**

```python
import os
from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

# Use OpenAI compatible API (Alibaba Tongyi Qianwen)
gateway = Gateway(GatewayConfig(
    default_model="qwen3.5-plus",
    default_provider="openai_compatible",
    base_url=os.environ.get("OPENAI_BASE_URL"),  # https://dashscope.aliyuncs.com/compatible-mode/v1
    api_key=os.environ["OPENAI_API_KEY"],
))

# Add Feishu channel
feishu = FeishuChannel(FeishuConfig(
    app_id=os.environ["FEISHU_APP_ID"],
    app_secret=os.environ["FEISHU_APP_SECRET"],
), port=8081)

gateway.add_channel(feishu)
gateway.run()
```

## Code Examples

### Basic Conversation

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="Help me see what files are in the current directory"
    )
    response = await gateway.handle_message(msg)
    print(response)

asyncio.run(main())
```

### Session Operations

```python
from microclaw import SessionStore, SessionKey, ResetPolicy

store = SessionStore(
    storage_dir=".microclaw/sessions",
    reset_policy=ResetPolicy(mode="daily", at_hour=4)
)

# Get session (auto-creates if not exists)
session = store.get("agent:main:main")

# Force reset
session = store.reset("agent:main:main")

# List recently active sessions
recent = store.list(active_minutes=1440)  # Within 24 hours
```

### Memory Read/Write

```python
from microclaw import WorkspaceFiles, MemoryConfig

workspace = WorkspaceFiles(MemoryConfig(
    workspace_dir="~/.microclaw/workspace"
))

# Read personality settings
soul = workspace.read_soul()

# Write daily log
workspace.append_daily("- Completed initial MicroClaw learning")

# Build full context (for system prompt)
context = workspace.build_context(is_main_session=True)
```

## Installation

Use [uv](https://docs.astral.sh/uv/) to manage project dependencies:

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Basic installation
uv sync

# Install extra features
uv sync --extra anthropic    # Claude support
uv sync --extra ollama       # Local model support
uv sync --extra feishu       # Feishu bot
uv sync --extra search       # Web search tool
uv sync --extra all          # All features

# Install dev tools
uv sync --group dev
```

## Project Structure

```
microclaw/
├── __init__.py       # Package entry
├── tools.py          # Tools system
├── session.py        # Session management
├── memory.py         # Workspace memory
├── agent.py          # Agent core
├── gateway.py        # Gateway orchestration
├── channels/         # Channel implementations
│   └── feishu.py     # Feishu channel
├── tui.py            # Terminal interface
└── cli.py            # CLI entry
```

## Relationship with OpenClaw

MicroClaw is an **educational** implementation to help you understand core patterns of Agent orchestration. For production-grade deployment, please use [OpenClaw](https://openclaw.ai).

| Capability | MicroClaw | OpenClaw |
|------------|-----------|----------|
| Code Scale | ~3,000 lines | ~50,000 lines |
| Session Management | Complete | Complete |
| Memory System | Basic (file storage) | Complete (with vector retrieval) |
| Channels | CLI, Webhook, Feishu | WhatsApp, Telegram, Slack, etc. |
| Production Ready | No | Yes |

## License

MIT
