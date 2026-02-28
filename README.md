# MicroClaw

一个轻量级的 Python Agent 编排框架，借鉴了 [OpenClaw](https://github.com/openclaw/openclaw) 的架构设计。

整个框架约 **2800 行代码**，旨在帮助你理解 Agent 系统的核心概念：

- **思考-行动-观察循环**：Agent 的基本运行模式
- **会话管理**：支持按用户、按群组隔离，可配置每日自动重置
- **工作区记忆**：用 Markdown 文件存储人格、用户信息、长期记忆和每日日志
- **工具系统**：通过装饰器快速定义和注册工具
- **多模型支持**：OpenAI、Anthropic、Ollama，以及各类兼容 OpenAI API 的服务
- **终端界面**：基于 Rich 库的交互式 TUI
- **飞书集成**：支持私聊和群聊 @机器人

## 五分钟上手

```bash
# 克隆项目
git clone https://github.com/StanleyChanH/MicroClaw.git
cd microclaw

# 安装依赖（需要先安装 uv）
uv sync

# 配置 API 密钥
export OPENAI_API_KEY="sk-xxx"

# 启动交互式终端
uv run microclaw

# 或使用更美观的 TUI 界面
uv run microclaw tui
```

## 系统架构

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
│ · JSONL 日志  │    │ · SOUL.md    │
│ · 自动重置    │    │ · USER.md    │
│ · 上下文压缩  │    │ · MEMORY.md  │
└──────────────┘    └──────────────┘
```

## 核心功能

### 会话管理

采用 OpenClaw 的会话键命名规范，灵活支持不同场景：

```
agent:main:main                    # 默认会话
agent:main:dm:user123              # 按用户隔离的私聊
agent:main:whatsapp:group:123456   # 群组会话
cron:daily-report                  # 定时任务
```

每个会话独立维护对话历史，支持：

- **定时重置**：每天凌晨 4 点自动清空（可配置）
- **空闲超时**：长时间不活动自动重置
- **上下文压缩**：接近 token 上限时自动总结历史对话

### 工作区记忆

用纯文本文件管理 Agent 的"长期记忆"，放在 `~/.microclaw/workspace/` 目录下：

| 文件 | 用途 |
|------|------|
| `SOUL.md` | Agent 的人格设定和行为准则 |
| `USER.md` | 用户的个人信息和偏好 |
| `MEMORY.md` | 需要长期记住的重要信息 |
| `memory/YYYY-MM-DD.md` | 每日日志，记录当天发生的事情 |

构建系统提示时，会自动读取这些文件作为上下文。

### 多模型支持

```python
from microclaw import Agent, AgentConfig

# OpenAI
agent = Agent(AgentConfig(model="gpt-4o", provider="openai"))

# Anthropic Claude
agent = Agent(AgentConfig(model="claude-sonnet-4-20250514", provider="anthropic"))

# 本地模型
agent = Agent(AgentConfig(model="llama3.2", provider="ollama"))

# 兼容 OpenAI API 的服务（DeepSeek、Kimi、智谱等）
agent = Agent(AgentConfig(
    model="deepseek-chat",
    provider="openai_compatible",
    base_url="https://api.deepseek.com"
))
```

### 自定义工具

用 `@tool` 装饰器即可定义工具：

```python
from microclaw import tool, Gateway

@tool(description="查询城市天气")
def get_weather(city: str) -> str:
    # 实际项目中可以调用天气 API
    return f"{city}：晴，22°C"

gateway = Gateway()
gateway.add_tool(get_weather)
```

## 命令行使用

```bash
microclaw [命令] [选项]

命令：
  (无)        交互式命令行
  tui         启动终端界面
  gateway     启动网关服务

常用选项：
  -m, --model      指定模型（默认 gpt-4o-mini）
  -p, --provider   指定提供商（openai/anthropic/ollama/openai_compatible）
  --base-url       自定义 API 地址
  --one-shot MSG   单次对话后退出
```

### 连接国产大模型

```bash
# DeepSeek
uv run microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat

# Kimi (Moonshot)
uv run microclaw -p openai_compatible --base-url https://api.moonshot.cn/v1 -m moonshot-v1-8k

# 智谱 GLM
uv run microclaw -p openai_compatible --base-url https://open.bigmodel.cn/api/paas/v4 -m glm-4

# 本地部署的 vLLM
uv run microclaw -p openai_compatible --base-url http://localhost:8000/v1 -m your-model
```

也可以通过环境变量配置：

```bash
export OPENAI_BASE_URL="https://api.deepseek.com"
export OPENAI_API_KEY="your-api-key"
uv run microclaw -p openai_compatible -m deepseek-chat
```

### 飞书机器人

支持私聊和群聊 @机器人，实现飞书内的 AI 对话：

```bash
# 安装飞书依赖
uv sync --extra feishu

# 配置环境变量
export FEISHU_APP_ID="cli_xxxxx"
export FEISHU_APP_SECRET="your-secret"

# 运行飞书机器人
uv run python examples/feishu_bot.py
```

**飞书开放平台配置：**

1. 创建企业自建应用，获取 App ID 和 App Secret
2. 配置事件订阅地址：`http://你的服务器:8081/feishu/webhook`
3. 订阅事件：`im.message.receive_v1`
4. 添加权限：`im:message`, `im:message:send_as_bot`
5. 发布应用并添加到群聊

**代码示例：**

```python
from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

gateway = Gateway(GatewayConfig())

feishu = FeishuChannel(FeishuConfig(
    app_id="cli_xxxxx",
    app_secret="your-secret"
), port=8081)

gateway.add_channel(feishu)
gateway.run()
```

## 代码示例

### 基础对话

```python
from microclaw import Gateway, GatewayConfig, IncomingMessage
import asyncio

gateway = Gateway(GatewayConfig())

async def main():
    msg = IncomingMessage(
        channel="api",
        sender="user",
        content="帮我看看当前目录有什么文件"
    )
    response = await gateway.handle_message(msg)
    print(response)

asyncio.run(main())
```

### 会话操作

```python
from microclaw import SessionStore, SessionKey, ResetPolicy

store = SessionStore(
    storage_dir=".microclaw/sessions",
    reset_policy=ResetPolicy(mode="daily", at_hour=4)
)

# 获取会话（不存在则自动创建）
session = store.get("agent:main:main")

# 强制重置
session = store.reset("agent:main:main")

# 列出最近活跃的会话
recent = store.list(active_minutes=1440)  # 24小时内
```

### 记忆读写

```python
from microclaw import WorkspaceFiles, MemoryConfig

workspace = WorkspaceFiles(MemoryConfig(
    workspace_dir="~/.microclaw/workspace"
))

# 读取人格设定
soul = workspace.read_soul()

# 写入每日日志
workspace.append_daily("- 完成了 MicroClaw 的初步学习")

# 构建完整上下文（用于系统提示）
context = workspace.build_context(is_main_session=True)
```

## 安装说明

使用 [uv](https://docs.astral.sh/uv/) 管理项目依赖：

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 基础安装
uv sync

# 安装额外功能
uv sync --extra anthropic    # Claude 支持
uv sync --extra ollama       # 本地模型支持
uv sync --extra feishu       # 飞书机器人
uv sync --extra search       # 网络搜索工具
uv sync --extra all          # 全部功能

# 安装开发工具
uv sync --group dev
```

## 项目结构

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

## 与 OpenClaw 的关系

MicroClaw 是一个**教学性质**的实现，帮助你理解 Agent 编排的核心模式。如果你需要生产级部署，请使用 [OpenClaw](https://openclaw.ai)。

| 能力 | MicroClaw | OpenClaw |
|------|-----------|----------|
| 代码规模 | ~3,000 行 | ~50,000 行 |
| 会话管理 | 完整 | 完整 |
| 记忆系统 | 基础（文件存储） | 完整（含向量检索） |
| 接入渠道 | CLI、Webhook、飞书 | WhatsApp、Telegram、Slack 等 |
| 生产可用 | 否 | 是 |

## License

MIT
