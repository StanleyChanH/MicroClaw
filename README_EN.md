# MicroClaw

<p align="center">
  <b>English</b> | <a href="README.md">中文</a>
</p>

<p align="center">
  <img src="images/banner.png" alt="MicroClaw Banner" width="100%">
</p>

<p align="center">
  <strong>A lightweight Python Agent Orchestration Framework</strong>
</p>

<p align="center">
  Inspired by <a href="https://github.com/openclaw/openclaw">OpenClaw</a> · ~3,000 lines of code · Easy to understand
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-documentation">Docs</a> •
  <a href="#-license">License</a>
</p>

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧠 Agent Core
- **Think-Act-Observe Loop** - Basic operation pattern
- **Tool Calling** - Python decorator definition
- **Multi-Model** - OpenAI, Anthropic, Ollama
- **Streaming Output** - Real-time response display

</td>
<td width="50%">

### 💾 Memory System
- **Workspace Files** - Markdown storage
- **Long-term Memory** - MEMORY.md
- **Daily Logs** - Auto date archiving
- **Skills System** - [Agent Skills Spec](https://agentskills.io)

</td>
</tr>
<tr>
<td width="50%">

### 🔄 Session Management
- **Multi-level Isolation** - User/Group independent
- **Scheduled Reset** - Daily auto-clear
- **Context Compression** - Summarize near limit
- **JSONL Persistence** - Complete history

</td>
<td width="50%">

### 🔌 Channels
- **CLI** - Command line interaction
- **TUI** - Rich terminal interface
- **Webhook** - HTTP interface
- **Feishu** - Private + Group @bot

</td>
</tr>
<tr>
<td width="50%">

### 🤖 Model Support
- **OpenAI** - GPT-4o, GPT-4o-mini
- **Anthropic** - Claude series
- **Ollama** - Local models
- **Compatible API** - DeepSeek, Qwen, GLM, etc.

</td>
<td width="50%">

### 🛠️ Developer Experience
- **~3,000 lines** - Easy to understand
- **Type Hints** - Complete annotations
- **Detailed Comments** - Well documented
- **Modular Design** - Use independently

</td>
</tr>
</table>

---

## 📸 Screenshot

<p align="center">
  <img src="images/MicroClaw1.png" alt="MicroClaw TUI Screenshot" width="80%">
</p>

---

## 🚀 Quick Start

### 1. Clone

```bash
git clone https://github.com/StanleyChanH/MicroClaw.git
cd MicroClaw
```

### 2. Install Dependencies

```bash
# Requires uv: https://docs.astral.sh/uv/
uv sync
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env file
```

```bash
# .env example
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
MICROCLAW_MODEL=gpt-4o-mini
MICROCLAW_PROVIDER=openai
```

### 4. Run

```bash
# TUI interface (recommended)
uv run microclaw tui

# Or simple CLI
uv run microclaw
```

---

## 📖 Table of Contents

- [System Architecture](#-system-architecture)
- [Core Features](#-core-features)
  - [Session Management](#-session-management)
  - [Workspace Memory](#-workspace-memory)
  - [Skills System](#-skills-system)
  - [Multi-Model Support](#-multi-model-support)
  - [Custom Tools](#-custom-tools)
- [CLI Usage](#-cli-usage)
- [Code Examples](#-code-examples)
- [Installation](#-installation)
- [Project Structure](#-project-structure)
- [Acknowledgements](#-acknowledgements)

---

## 🏗️ System Architecture

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
│  Think → Call Tools → Observe → Loop  │
└─────────────────┬────────────────────┘
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│Session Store │    │   Workspace   │
│              │    │              │
│ · JSONL Logs │    │ · AGENTS.md  │
│ · Auto Reset │    │ · SOUL.md    │
│ · Compression│    │ · USER.md    │
│              │    │ · MEMORY.md  │
│              │    │ · skills/    │
└──────────────┘    └──────────────┘
```

---

## 🔧 Core Features

### Session Management

Uses OpenClaw's session key naming convention:

```python
"agent:main:main"                    # Default session
"agent:main:dm:user123"              # Per-user isolation
"agent:main:whatsapp:group:123456"   # Group session
"cron:daily-report"                  # Scheduled task
```

**Features:**
- 🕐 **Scheduled Reset** - Auto-clear at 4 AM (configurable)
- ⏰ **Idle Timeout** - Auto-reset after inactivity
- 📦 **Context Compression** - Auto-summarize near token limit

### Workspace Memory

Plain text files for Agent's "long-term memory":

| File | Purpose | Loading |
|------|---------|---------|
| `AGENTS.md` | Workspace instructions | Always |
| `SOUL.md` | Personality settings | Always |
| `USER.md` | User information | Always |
| `MEMORY.md` | Long-term memory | **Main session only** |
| `memory/YYYY-MM-DD.md` | Daily logs | Last 2 days |
| `skills/` | Skills directory | Always |

> 💡 **Auto-loading**: All content is automatically injected into system prompt

### Skills System

Compliant with [Agent Skills Specification](https://agentskills.io/specification), supports progressive loading:

```markdown
~/.microclaw/workspace/skills/
├── greeting/
│   ├── SKILL.md          # Required (uppercase)
│   ├── scripts/          # Optional - scripts
│   ├── references/       # Optional - references
│   └── assets/           # Optional - assets
└── coding/
    └── SKILL.md
```

**SKILL.md Format:**

```markdown
---
name: greeting                    # Required, 1-64 chars
description: Enthusiastic greeting # Required, ≤1024 chars
license: MIT                      # Optional
compatibility: microclaw>=0.1.0   # Optional
allowed-tools:                    # Optional (experimental)
  - shell_execute
---

# Enthusiastic Greeting

When user says hello, respond more enthusiastically.

## Examples
- "Hello" → "Hey there! Great to see you!"
```

**Progressive Disclosure Mode:**
1. **Discovery** - System prompt includes `<available_skills>` XML (name + description)
2. **Activation** - Agent calls `skill_load(name)` to load full content
3. **Resources** - On-demand access to scripts/references/assets

### Multi-Model Support

```python
from microclaw import Agent, AgentConfig

# OpenAI
Agent(AgentConfig(model="gpt-4o", provider="openai"))

# Anthropic
Agent(AgentConfig(model="claude-sonnet-4-20250514", provider="anthropic"))

# Ollama
Agent(AgentConfig(model="llama3.2", provider="ollama"))

# Compatible API
Agent(AgentConfig(
    model="deepseek-chat",
    provider="openai_compatible",
    base_url="https://api.deepseek.com"
))
```

### Custom Tools

```python
from microclaw import tool, Gateway

@tool(description="Query weather")
def get_weather(city: str) -> str:
    return f"{city}: Sunny, 22°C"

gateway = Gateway()
gateway.add_tool(get_weather)
```

---

## 💻 CLI Usage

```bash
microclaw [command] [options]

Commands:
  (none)      Interactive CLI
  tui         Terminal interface (recommended)
  gateway     Gateway service

Options:
  -m, --model      Model (default: gpt-4o-mini)
  -p, --provider   Provider
  --base-url       API address
  --feishu         Enable Feishu channel (requires FEISHU_APP_ID and FEISHU_APP_SECRET)
  --webhook        Enable webhook server
  --port           Webhook port (default: 8080)
  --one-shot MSG   Single message
  --stream         Enable streaming (default)
  --no-stream      Disable streaming
```

### Feishu Bot

```bash
# CLI + Feishu (recommended)
uv run microclaw --feishu

# Webhook + Feishu
uv run microclaw --webhook --feishu

# Standalone Feishu bot
uv run python examples/feishu_qwen.py
```

**Environment Variables (.env):**
```bash
# AI Model
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MICROCLAW_MODEL=qwen-plus
MICROCLAW_PROVIDER=openai_compatible

# Feishu
FEISHU_APP_ID=xxx
FEISHU_APP_SECRET=xxx
```

### Chinese LLMs

```bash
# DeepSeek
uv run microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat

# Qwen (Alibaba)
uv run microclaw -p openai_compatible --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 -m qwen-turbo

# GLM (Zhipu)
uv run microclaw -p openai_compatible --base-url https://open.bigmodel.cn/api/paas/v4 -m glm-4
```

### Windows Compatibility

| Unix | Windows |
|------|---------|
| `ls` | `dir` |
| `cat` | `type` |
| `rm` | `del` |

System automatically translates commands.

---

## 📝 Code Examples

<details>
<summary><b>Basic Conversation</b></summary>

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="List files in current directory"
    )
    response = await gateway.handle_message(msg)
    print(response)

asyncio.run(main())
```

</details>

<details>
<summary><b>Streaming Output</b></summary>

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="Tell me about Python"
    )

    # Stream response in real-time
    async for chunk in gateway.handle_message_stream(msg):
        if isinstance(chunk, str):
            print(chunk, end="", flush=True)
        elif isinstance(chunk, dict):
            # Tool call events
            if chunk.get("type") == "tool_start":
                print(f"\n[Tool] {chunk.get('name')}...")

asyncio.run(main())
```

</details>

<details>
<summary><b>Session Operations</b></summary>

```python
from microclaw import SessionStore, ResetPolicy

store = SessionStore(
    storage_dir=".microclaw/sessions",
    reset_policy=ResetPolicy(mode="daily", at_hour=4)
)

# Get session
session = store.get("agent:main:main")

# Force reset
session = store.reset("agent:main:main")

# List active sessions
recent = store.list(active_minutes=1440)
```

</details>

<details>
<summary><b>Memory Read/Write</b></summary>

```python
from microclaw import WorkspaceFiles, MemoryConfig

workspace = WorkspaceFiles(MemoryConfig(
    workspace_dir="~/.microclaw/workspace"
))

# Read personality
soul = workspace.read_soul()

# Write daily log
workspace.append_daily("- Completed MicroClaw tutorial")

# Build context
context = workspace.build_context(is_main_session=True)
```

</details>

<details>
<summary><b>Feishu Bot (WebSocket)</b></summary>

```python
import os
from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

gateway = Gateway(GatewayConfig(
    default_model="qwen-turbo",
    default_provider="openai_compatible",
    base_url=os.environ.get("OPENAI_BASE_URL"),
    api_key=os.environ["OPENAI_API_KEY"],
))

# WebSocket mode - No public IP required, works locally
feishu = FeishuChannel(FeishuConfig(
    app_id=os.environ["FEISHU_APP_ID"],
    app_secret=os.environ["FEISHU_APP_SECRET"],
    use_websocket=True,  # Default
))

gateway.add_channel(feishu)
gateway.run()
```

**Feishu Developer Platform Setup:**
1. Event Subscription → Select **"Use Long Connection to Receive Events"**
2. Add Event: `im.message.receive_v1`
3. Permissions: `im:message`, `im:message:send_as_bot`

</details>

---

## 📦 Installation

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Basic install
uv sync

# Extra features
uv sync --extra anthropic    # Claude support
uv sync --extra ollama       # Local models
uv sync --extra feishu       # Feishu bot
uv sync --extra all          # All features
```

---

## 📁 Project Structure

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

---

## 🙏 Acknowledgements

- [OpenClaw](https://github.com/openclaw/openclaw) - Architecture inspiration
- [Agent Skills](https://agentskills.io) - Skills system specification
- [Rich](https://github.com/Textualize/rich) - Terminal interface library

---

## 📄 License

[MIT](LICENSE)

---

<p align="center">
  <sub>If you find this useful, please give it a ⭐ Star!</sub>
</p>
