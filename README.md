<div align="center">

# MicroClaw

<p align="center">
  <a href="README_EN.md">English</a> | <b>中文</b>
</p>

<p align="center">
  <img src="images/banner.png" alt="MicroClaw Banner" width="100%">
</p>

<p align="center">
  <strong>轻量级 Python Agent 编排框架</strong>
</p>

<p align="center">
  理解 Agent 系统的最佳起点 · 约 3000 行代码 · 完整功能
</p>

<p align="center">

<a href="https://github.com/StanleyChanH/MicroClaw/stargazers">
  <img alt="GitHub stars" src="https://img.shields.io/github/stars/StanleyChanH/MicroClaw?style=for-the-badge&logo=github&color=yellow">
</a>
<a href="https://github.com/StanleyChanH/MicroClaw/blob/master/LICENSE">
  <img alt="MIT License" src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge">
</a>
<a href="https://www.python.org/">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white">
</a>
<a href="https://github.com/StanleyChanH/MicroClaw/issues">
  <img alt="Issues" src="https://img.shields.io/github/issues/StanleyChanH/MicroClaw?style=for-the-badge&logo=github">
</a>

</p>

</div>

---

## ✨ 特性

<table>
<tr>
<td width="50%">

### 🧠 Agent 核心
- **思考-行动-观察循环** - ReAct 模式
- **多轮对话** - 自动上下文管理
- **工具调用** - Python 装饰器定义
- **流式输出** - 实时显示响应

</td>
<td width="50%">

### 💾 记忆系统
- **工作区文件** - Markdown 格式存储
- **长期记忆** - MEMORY.md
- **每日日志** - 自动日期归档
- **技能系统** - [Agent Skills 规范](https://agentskills.io)

</td>
</tr>
<tr>
<td width="50%">

### 🔄 会话管理
- **多级隔离** - 用户/群组独立
- **定时重置** - 每日自动清空
- **上下文压缩** - 接近限制时总结
- **JSONL 持久化** - 完整历史记录

</td>
<td width="50%">

### 🔌 接入渠道
- **CLI** - 命令行交互
- **TUI** - Rich 终端界面
- **Webhook** - HTTP 接口
- **飞书** - 私聊 + 群聊 @机器人

</td>
</tr>
<tr>
<td width="50%">

### 🤖 多模型支持
- **OpenAI** - GPT-4o, GPT-4o-mini
- **Anthropic** - Claude 系列
- **Ollama** - 本地模型
- **兼容 API** - DeepSeek, 通义, GLM 等

</td>
<td width="50%">

### 🛠️ 开发体验
- **~3000 行代码** - 易于理解
- **类型提示** - 完整标注
- **详细注释** - 中文文档
- **模块化设计** - 可独立使用

</td>
</tr>
</table>

---

## 📸 截图

<p align="center">
  <img src="images/MicroClaw1.png" alt="MicroClaw TUI Screenshot" width="80%">
</p>

---

## 🚀 五分钟上手

### 1. 克隆项目

```bash
git clone https://github.com/StanleyChanH/MicroClaw.git
cd MicroClaw
```

### 2. 安装依赖

```bash
# 需要先安装 uv: https://docs.astral.sh/uv/
uv sync
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件
```

```bash
# .env 配置示例
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
MICROCLAW_MODEL=gpt-4o-mini
MICROCLAW_PROVIDER=openai
```

### 4. 启动

```bash
# TUI 界面（推荐）
uv run microclaw tui

# 或简单 CLI
uv run microclaw
```

---

## 📖 目录

- [系统架构](#-系统架构)
- [核心功能](#-核心功能)
  - [会话管理](#会话管理)
  - [工作区记忆](#工作区记忆)
  - [技能系统](#技能系统)
  - [多模型支持](#多模型支持)
  - [自定义工具](#自定义工具)
- [命令行使用](#-命令行使用)
- [代码示例](#-代码示例)
- [安装说明](#-安装说明)
- [项目结构](#-项目结构)
- [致谢](#-致谢)

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────┐
│           接入层 (Channels)          │
│    CLI / Webhook / 飞书 / 可扩展      │
└─────────────────┬────────────────────┘
                  ▼
┌──────────────────────────────────────┐
│            网关 (Gateway)            │
│     消息路由 · 会话管理 · 事件分发    │
└─────────────────┬────────────────────┘
                  ▼
┌──────────────────────────────────────┐
│           Agent 核心循环              │
│    思考 → 调用工具 → 观察结果 → 循环   │
└─────────────────┬────────────────────┘
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│   会话存储    │    │   工作区      │
│              │    │              │
│ · JSONL 日志  │    │ · AGENTS.md  │
│ · 自动重置    │    │ · SOUL.md    │
│ · 上下文压缩  │    │ · USER.md    │
│              │    │ · MEMORY.md  │
│              │    │ · skills/    │
└──────────────┘    └──────────────┘
```

---

## 🔧 核心功能

### 会话管理

采用 OpenClaw 的会话键命名规范：

```python
"agent:main:main"                    # 默认会话
"agent:main:dm:user123"              # 按用户隔离
"agent:main:whatsapp:group:123456"   # 群组会话
"cron:daily-report"                  # 定时任务
```

**特性：**
- 🕐 **定时重置** - 每天凌晨 4 点自动清空（可配置）
- ⏰ **空闲超时** - 长时间不活动自动重置
- 📦 **上下文压缩** - 接近 token 上限时自动总结

### 工作区记忆

纯文本文件管理 Agent 的"长期记忆"：

| 文件 | 用途 | 加载时机 |
|------|------|---------|
| `AGENTS.md` | 工作区说明 | 始终 |
| `SOUL.md` | 人格设定 | 始终 |
| `USER.md` | 用户信息 | 始终 |
| `MEMORY.md` | 长期记忆 | **仅主会话** |
| `memory/YYYY-MM-DD.md` | 每日日志 | 最近 2 天 |
| `skills/` | 技能目录 | 始终 |

> 💡 **自动加载**：所有内容自动注入系统提示，Agent 无需手动读取

### 技能系统

符合 [Agent Skills 官方规范](https://agentskills.io/specification)，支持渐进式加载：

```markdown
~/.microclaw/workspace/skills/
├── greeting/
│   ├── SKILL.md          # 必须 (大写)
│   ├── scripts/          # 可选 - 脚本文件
│   ├── references/       # 可选 - 参考文档
│   └── assets/           # 可选 - 资源文件
└── coding/
    └── SKILL.md
```

**SKILL.md 格式：**

```markdown
---
name: greeting                    # 必须，1-64字符
description: 热情问候技能          # 必须，≤1024字符
license: MIT                      # 可选
compatibility: microclaw>=0.1.0   # 可选
allowed-tools:                    # 可选 (实验性)
  - shell_execute
---

# 热情问候

当用户打招呼时，必须用更热情的语气回应。

## 示例
- "你好" → "你好呀！很高兴见到你！"
```

**Progressive Disclosure 模式：**
1. **发现阶段** - 系统提示注入 `<available_skills>` XML (name + description)
2. **激活阶段** - Agent 调用 `skill_load(name)` 加载完整内容
3. **资源访问** - 按需读取 scripts/references/assets

### 多模型支持

```python
from microclaw import Agent, AgentConfig

# OpenAI
Agent(AgentConfig(model="gpt-4o", provider="openai"))

# Anthropic
Agent(AgentConfig(model="claude-sonnet-4-20250514", provider="anthropic"))

# Ollama
Agent(AgentConfig(model="llama3.2", provider="ollama"))

# 兼容 API
Agent(AgentConfig(
    model="deepseek-chat",
    provider="openai_compatible",
    base_url="https://api.deepseek.com"
))
```

### 自定义工具

```python
from microclaw import tool, Gateway

@tool(description="查询天气")
def get_weather(city: str) -> str:
    return f"{city}：晴，22°C"

gateway = Gateway()
gateway.add_tool(get_weather)
```

---

## 💻 命令行使用

```bash
microclaw [命令] [选项]

命令：
  (无)        交互式命令行
  tui         终端界面（推荐）
  gateway     网关服务

选项：
  -m, --model      模型（默认 gpt-4o-mini）
  -p, --provider   提供商
  --base-url       API 地址
  --one-shot MSG   单次对话
  --stream         启用流式输出（默认启用）
  --no-stream      禁用流式输出
```

### 国产大模型

```bash
# DeepSeek
uv run microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat

# 通义千问
uv run microclaw -p openai_compatible --base-url https://dashscope.aliyuncs.com/compatible-mode/v1 -m qwen-turbo

# 智谱 GLM
uv run microclaw -p openai_compatible --base-url https://open.bigmodel.cn/api/paas/v4 -m glm-4
```

### Windows 兼容

| Unix | Windows |
|------|---------|
| `ls` | `dir` |
| `cat` | `type` |
| `rm` | `del` |

系统自动转换，无需手动适配。

---

## 📝 代码示例

<details>
<summary><b>基础对话</b></summary>

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="帮我看看当前目录"
    )
    response = await gateway.handle_message(msg)
    print(response)

asyncio.run(main())
```

</details>

<details>
<summary><b>流式输出</b></summary>

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="介绍一下 Python"
    )

    # 流式接收响应
    async for chunk in gateway.handle_message_stream(msg):
        if isinstance(chunk, str):
            print(chunk, end="", flush=True)
        elif isinstance(chunk, dict):
            # 工具调用事件
            if chunk.get("type") == "tool_start":
                print(f"\n[工具] {chunk.get('name')}...")

asyncio.run(main())
```

</details>

<details>
<summary><b>会话操作</b></summary>

```python
from microclaw import SessionStore, ResetPolicy

store = SessionStore(
    storage_dir=".microclaw/sessions",
    reset_policy=ResetPolicy(mode="daily", at_hour=4)
)

# 获取会话
session = store.get("agent:main:main")

# 强制重置
session = store.reset("agent:main:main")

# 列出活跃会话
recent = store.list(active_minutes=1440)
```

</details>

<details>
<summary><b>记忆读写</b></summary>

```python
from microclaw import WorkspaceFiles, MemoryConfig

workspace = WorkspaceFiles(MemoryConfig(
    workspace_dir="~/.microclaw/workspace"
))

# 读取人格
soul = workspace.read_soul()

# 写入日志
workspace.append_daily("- 学习了 MicroClaw")

# 构建上下文
context = workspace.build_context(is_main_session=True)
```

</details>

<details>
<summary><b>飞书机器人 (WebSocket 长连接)</b></summary>

```python
import os
from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

gateway = Gateway(GatewayConfig(
    default_model="qwen-turbo",
    default_provider="openai_compatible",
    base_url=os.environ["OPENAI_BASE_URL"],
    api_key=os.environ["OPENAI_API_KEY"],
))

# WebSocket 长连接模式 - 无需公网 IP，本地即可调试
feishu = FeishuChannel(FeishuConfig(
    app_id=os.environ["FEISHU_APP_ID"],
    app_secret=os.environ["FEISHU_APP_SECRET"],
    use_websocket=True,  # 默认启用
))

gateway.add_channel(feishu)
gateway.run()
```

**飞书开放平台配置：**
1. 事件订阅 → 选择 **"使用长连接接收事件"**
2. 添加事件：`im.message.receive_v1`
3. 权限：`im:message`, `im:message:send_as_bot`

</details>

---

## 📦 安装说明

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 基础安装
uv sync

# 额外功能
uv sync --extra anthropic    # Claude
uv sync --extra ollama       # 本地模型
uv sync --extra feishu       # 飞书
uv sync --extra all          # 全部

# 开发工具
uv sync --group dev
```

---

## 📁 项目结构

```
microclaw/
├── __init__.py       # 包入口
├── tools.py          # 工具系统
├── session.py        # 会话管理
├── memory.py         # 工作区记忆
├── agent.py          # Agent 核心
├── gateway.py        # 网关编排
├── channels/         # 通道实现
│   └── feishu.py     # 飞书通道
├── tui.py            # 终端界面
└── cli.py            # 命令行入口
```

---

## 🙏 致谢

- [OpenClaw](https://openclaw.ai) - 生产级 Agent 编排框架
- [Agent Skills](https://agentskills.io) - 技能系统规范
- [Rich](https://github.com/Textualize/rich) - 终端美化库

---

## 📄 License

[MIT](LICENSE) © StanleyChanH

---

<p align="center">
  <a href="https://github.com/StanleyChanH/MicroClaw/stargazers">
    <img src="https://api.star-history.com/svg?repos=StanleyChanH/MicroClaw&type=Date" alt="Star History Chart">
  </a>
</p>

<p align="center">
  <i>如果这个项目对你有帮助，请给一个 ⭐️ Star 支持一下！</i>
</p>
