"""
CLI Interface for MicroClaw

Run the agent in various modes:
- Interactive CLI chat
- TUI (terminal UI with Rich)
- Webhook server
- One-shot execution
"""

import argparse
import asyncio
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description="MicroClaw - A minimal agent orchestration framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  microclaw                                # Interactive CLI
  microclaw tui                            # Rich TUI
  microclaw --webhook                      # Webhook server
  microclaw --one-shot "Hello"             # Single message

  # Using OpenAI-compatible APIs (DeepSeek, Moonshot, etc.)
  microclaw -p openai_compatible --base-url https://api.deepseek.com -m deepseek-chat
  microclaw -p openai_compatible --base-url https://api.moonshot.cn/v1 -m moonshot-v1-8k

Environment:
  OPENAI_API_KEY      OpenAI API key
  OPENAI_BASE_URL     Base URL for OpenAI-compatible APIs
  ANTHROPIC_API_KEY   Anthropic API key
  MICROCLAW_MODEL      Default model
  MICROCLAW_PROVIDER   Default provider
"""
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command")
    
    # TUI subcommand
    tui_parser = subparsers.add_parser("tui", help="Run the Rich terminal UI")
    tui_parser.add_argument("--model", "-m", help="Model to use")
    tui_parser.add_argument("--provider", "-p", help="Provider")
    tui_parser.add_argument("--base-url", help="Base URL for OpenAI-compatible APIs")
    tui_parser.add_argument("--api-key", help="API key")
    tui_parser.add_argument("--session", "-s", default="main", help="Session key")
    tui_parser.add_argument("--workspace", "-w", help="Workspace directory")
    
    # Gateway subcommand
    gateway_parser = subparsers.add_parser("gateway", help="Run the full gateway")
    gateway_parser.add_argument("--webhook", action="store_true", help="Enable webhook")
    gateway_parser.add_argument("--port", type=int, default=8080, help="Webhook port")
    
    # Main arguments (for backward compatibility)
    parser.add_argument(
        "--model", "-m",
        default=os.environ.get("MICROCLAW_MODEL", "gpt-4o-mini"),
        help="Model to use (default: gpt-4o-mini)"
    )
    
    parser.add_argument(
        "--provider", "-p",
        default=os.environ.get("MICROCLAW_PROVIDER", "openai"),
        choices=["openai", "anthropic", "ollama", "openai_compatible"],
        help="LLM provider (default: openai)"
    )

    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL"),
        help="Base URL for OpenAI-compatible APIs (e.g., https://api.deepseek.com)"
    )

    parser.add_argument(
        "--api-key",
        help="API key (falls back to environment variables)"
    )

    parser.add_argument(
        "--system", "-s",
        help="System prompt (overrides workspace files)"
    )
    
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="Start webhook server instead of CLI"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Webhook server port (default: 8080)"
    )
    
    parser.add_argument(
        "--workspace",
        default="~/.microclaw",
        help="Workspace/storage directory (default: ~/.microclaw)"
    )
    
    parser.add_argument(
        "--one-shot",
        metavar="MESSAGE",
        help="Run a single message and exit"
    )
    
    parser.add_argument(
        "--session",
        default="main",
        help="Session key (default: main)"
    )
    
    args = parser.parse_args()
    
    # Handle TUI subcommand
    if args.command == "tui":
        run_tui(args)
        return
    
    # Handle gateway subcommand  
    if args.command == "gateway":
        run_gateway(args)
        return
    
    # Import components
    from .gateway import (
        CLIChannel,
        Gateway,
        GatewayConfig,
        IncomingMessage,
        WebhookChannel,
    )
    
    # Build config
    config = GatewayConfig(
        storage_dir=args.workspace,
        default_model=args.model,
        default_provider=args.provider,
        base_url=args.base_url,
        api_key=args.api_key,
        system_prompt=args.system
    )
    
    gateway = Gateway(config)
    
    # One-shot mode
    if args.one_shot:
        async def run_once():
            msg = IncomingMessage(
                channel="cli",
                sender="user",
                content=args.one_shot
            )
            response = await gateway.handle_message(msg)
            print(response)
        
        asyncio.run(run_once())
        return
    
    # Add appropriate channel
    if args.webhook:
        gateway.add_channel(WebhookChannel(port=args.port))
    else:
        gateway.add_channel(CLIChannel())
    
    # Event handlers
    def on_tool(event, name, data):
        if event == "start":
            print(f"  🔧 {name}({data})")
        elif event == "end":
            preview = str(data)[:100]
            if len(str(data)) > 100:
                preview += "..."
            print(f"  ✓ {preview}")
    
    gateway.on("tool_call", on_tool)
    
    # Print banner
    print_banner(args)
    
    # Run
    try:
        gateway.run()
    except KeyboardInterrupt:
        print("\n\nGoodbye! 👋")
        sys.exit(0)


def run_tui(args):
    """Run the TUI."""
    from .agent import AgentConfig
    from .tui import TUI

    config = AgentConfig(
        model=args.model or os.environ.get("MICROCLAW_MODEL", "gpt-4o-mini"),
        provider=args.provider or os.environ.get("MICROCLAW_PROVIDER", "openai"),
        workspace_dir=args.workspace or "~/.microclaw/workspace",
        base_url=args.base_url or os.environ.get("OPENAI_BASE_URL"),
        api_key=args.api_key,
    )

    tui = TUI(config=config, session_key=args.session)
    tui.run()


def run_gateway(args):
    """Run the full gateway."""
    from .gateway import CLIChannel, Gateway, GatewayConfig, WebhookChannel
    
    config = GatewayConfig(storage_dir="~/.microclaw")
    gateway = Gateway(config)
    
    gateway.add_channel(CLIChannel())
    
    if args.webhook:
        gateway.add_channel(WebhookChannel(port=args.port))
    
    print_banner_full()
    gateway.run()


def print_banner(args):
    """Print the startup banner."""
    print(f"""
+-----------------------------------------+
|         MicroClaw v0.1.0                |
|   A minimal agent orchestration framework  |
+-----------------------------------------+

Model: {args.model} ({args.provider})
Workspace: {args.workspace}
Session: {args.session}

Commands:
  /help    - Show help
  /status  - Session status
  /new     - Reset session
  Ctrl+C   - Exit

""")


def print_banner_full():
    """Print full gateway banner."""
    print("""
╔═══════════════════════════════════════════════════════╗
║              [M] MicroClaw Gateway                      ║
╚═══════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    main()
