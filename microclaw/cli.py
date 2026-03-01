"""
MicroClaw CLI 接口

以多种模式运行 Agent:
- 交互式 CLI 聊天
- TUI (基于 Rich 的终端界面)
- Webhook 服务器
- 单次执行
"""

import argparse
import asyncio
import os
import sys


def _load_env():
    """加载 .env 文件到环境变量。"""
    try:
        from dotenv import load_dotenv

        # 从当前目录或项目根目录加载 .env
        load_dotenv()
    except ImportError:
        pass


def main():
    # 首先加载 .env 文件
    _load_env()
    parser = argparse.ArgumentParser(
        description="MicroClaw - 轻量级 Agent 编排框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  microclaw                                # 交互式 CLI
  microclaw tui                            # Rich TUI
  microclaw --webhook                      # Webhook 服务器
  microclaw --one-shot "你好"              # 单次消息

  # 使用 OpenAI 兼容 API (DeepSeek、Moonshot 等)
  microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat
  microclaw -p openai_compatible --base-url https://api.moonshot.cn/v1 -m moonshot-v1-8k

环境变量:
  OPENAI_API_KEY      OpenAI API 密钥
  OPENAI_BASE_URL     OpenAI 兼容 API 的基础 URL
  ANTHROPIC_API_KEY   Anthropic API 密钥
  MICROCLAW_MODEL      默认模型
  MICROCLAW_PROVIDER   默认提供商
""",
    )

    # 子命令
    subparsers = parser.add_subparsers(dest="command")

    # TUI 子命令
    tui_parser = subparsers.add_parser("tui", help="运行 Rich 终端界面")
    tui_parser.add_argument("--model", "-m", help="使用的模型")
    tui_parser.add_argument("--provider", "-p", help="提供商")
    tui_parser.add_argument("--base-url", help="OpenAI 兼容 API 的基础 URL")
    tui_parser.add_argument("--api-key", help="API 密钥")
    tui_parser.add_argument("--session", "-s", default="main", help="会话键")
    tui_parser.add_argument(
        "--workspace", "-w", default="~/.microclaw/workspace", help="工作区目录"
    )

    # Gateway 子命令
    gateway_parser = subparsers.add_parser("gateway", help="运行完整 Gateway")
    gateway_parser.add_argument("--webhook", action="store_true", help="启用 webhook")
    gateway_parser.add_argument("--port", type=int, default=8080, help="Webhook 端口")

    # 主参数 (向后兼容)
    parser.add_argument(
        "--model",
        "-m",
        default=os.environ.get("MICROCLAW_MODEL", "gpt-4o-mini"),
        help="使用的模型 (默认: gpt-4o-mini)",
    )

    parser.add_argument(
        "--provider",
        "-p",
        default=os.environ.get("MICROCLAW_PROVIDER", "openai"),
        choices=["openai", "anthropic", "ollama", "openai_compatible"],
        help="LLM 提供商 (默认: openai)",
    )

    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL"),
        help="OpenAI 兼容 API 的基础 URL (如 https://api.deepseek.com)",
    )

    parser.add_argument("--api-key", help="API 密钥 (回退到环境变量)")

    parser.add_argument("--system", "-s", help="系统提示 (覆盖工作区文件)")

    parser.add_argument(
        "--webhook", action="store_true", help="启动 webhook 服务器而非 CLI"
    )

    parser.add_argument(
        "--port", type=int, default=8080, help="Webhook 服务器端口 (默认: 8080)"
    )

    parser.add_argument(
        "--workspace",
        default="~/.microclaw",
        help="工作区/存储目录 (默认: ~/.microclaw)",
    )

    parser.add_argument("--one-shot", metavar="消息", help="运行单条消息后退出")

    parser.add_argument("--session", default="main", help="会话键 (默认: main)")

    parser.add_argument(
        "--stream",
        action="store_true",
        default=True,
        help="启用流式输出 (默认启用)",
    )
    parser.add_argument("--no-stream", action="store_true", help="禁用流式输出")

    args = parser.parse_args()

    # 处理 TUI 子命令
    if args.command == "tui":
        run_tui(args)
        return

    # 处理 gateway 子命令
    if args.command == "gateway":
        run_gateway(args)
        return

    # 导入组件
    from .gateway import (
        CLIChannel,
        Gateway,
        GatewayConfig,
        IncomingMessage,
        WebhookChannel,
    )

    # 构建配置
    config = GatewayConfig(
        storage_dir=args.workspace,
        default_model=args.model,
        default_provider=args.provider,
        base_url=args.base_url,
        api_key=args.api_key,
        system_prompt=args.system,
    )

    gateway = Gateway(config)

    # 单次模式
    if args.one_shot:

        async def run_once():
            msg = IncomingMessage(channel="cli", sender="user", content=args.one_shot)
            response = await gateway.handle_message(msg)
            print(response)

        asyncio.run(run_once())
        return

    # 添加适当的通道
    if args.webhook:
        gateway.add_channel(WebhookChannel(port=args.port))
    else:
        # 确定是否使用流式输出
        use_stream = args.stream and not args.no_stream
        cli_channel = CLIChannel(stream=use_stream)

        if use_stream:
            # 设置流式处理器
            cli_channel.set_stream_handler(gateway.handle_message_stream)

        gateway.add_channel(cli_channel)

    # 事件处理器
    def on_tool(event, name, data):
        if event == "start":
            print(f"  [*] {name}({data})")
        elif event == "end":
            preview = str(data)[:100]
            if len(str(data)) > 100:
                preview += "..."
            print(f"  [OK] {preview}")

    gateway.on("tool_call", on_tool)

    # 打印横幅
    print_banner(args)

    # 运行
    try:
        gateway.run()
    except KeyboardInterrupt:
        print("\n\n再见!")
        sys.exit(0)


def run_tui(args):
    """运行 TUI。"""
    from .agent import AgentConfig
    from .tui import TUI

    # 从环境变量加载配置 (命令行参数优先)
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    base_url = args.base_url or os.environ.get("OPENAI_BASE_URL")

    config = AgentConfig(
        model=args.model or os.environ.get("MICROCLAW_MODEL", "gpt-4o-mini"),
        provider=args.provider or os.environ.get("MICROCLAW_PROVIDER", "openai"),
        workspace_dir=args.workspace,
        base_url=base_url,
        api_key=api_key,
    )

    tui = TUI(config=config, session_key=args.session)
    tui.run()


def run_gateway(args):
    """运行完整 Gateway。"""
    from .gateway import CLIChannel, Gateway, GatewayConfig, WebhookChannel

    config = GatewayConfig(storage_dir="~/.microclaw")
    gateway = Gateway(config)

    gateway.add_channel(CLIChannel())

    if args.webhook:
        gateway.add_channel(WebhookChannel(port=args.port))

    print_banner_full()
    gateway.run()


def print_banner(args):
    """打印启动横幅。"""
    print(f"""
+-----------------------------------------+
|         MicroClaw v0.1.0                |
|     轻量级 Agent 编排框架                |
+-----------------------------------------+

模型: {args.model} ({args.provider})
工作区: {args.workspace}
会话: {args.session}

命令:
  /help    - 显示帮助
  /status  - 会话状态
  /new     - 重置会话
  Ctrl+C   - 退出

""")


def print_banner_full():
    """打印完整 Gateway 横幅。"""
    print("""
+-------------------------------------------------------+
|              [M] MicroClaw Gateway                    |
+-------------------------------------------------------+
""")


if __name__ == "__main__":
    main()
