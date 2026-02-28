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

</td>
<td width="50%">

### 💾 Memory System
- **Workspace Files** - Markdown storage
- **Long-term Memory** - MEMORY.md
- **Daily Logs** - Auto date archiving
- **Skills System** - YAML frontmatter definition

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

```markdown
~/.microclaw/workspace/skills/
├── greeting/
│   └── skill.md
└── coding/
    └── skill.md
```

**skill.md Format:**

```markdown
---
name: greeting
description: Enthusiastic greeting skill
version: 1.0.0
---

# Enthusiastic Greeting

When user says hello, respond more enthusiastically.

## Examples
- "Hello" → "Hey there! Great to see you!"
```

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
  --one-shot MSG   Single message
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
<summary><b>Feishu Bot</b></summary>

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

feishu = FeishuChannel(FeishuConfig(
    app_id=os.environ["FEISHU_APP_ID"],
    app_secret=os.environ["FEISHU_APP_SECRET"],
), port=8081)

gateway.add_channel(feishu)
gateway.run()
```

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
- [Rich](https://github.com/Textualize/rich) - Terminal interface library

---

## 📄 License

[MIT](LICENSE)

---

<p align="center">
  <sub>If you find this useful, please give it a ⭐ Star!</sub>
</p>
