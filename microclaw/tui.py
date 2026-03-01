"""
TUI - 终端用户界面 (OpenClaw 风格)

基于 Rich 的终端界面，用于与 Agent 交互。
特性:
- 带格式化消息的聊天日志
- 工具调用可视化
- 带会话信息的状态栏
- 斜杠命令 (/help, /status, /new, /model 等)
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, Optional

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from .agent import Agent, AgentConfig
from .session import MessageRole, ResetPolicy, SessionKey, SessionStore


class Theme:
    """TUI 的颜色主题。"""

    # 消息颜色
    USER = "bold cyan"
    ASSISTANT = "bold green"
    SYSTEM = "bold yellow"
    ERROR = "bold red"
    TOOL = "bold magenta"

    # UI 颜色
    HEADER = "bold white on blue"
    STATUS = "dim"
    PROMPT = "bold cyan"

    # 工具状态
    TOOL_START = "yellow"
    TOOL_END = "green"


class TUI:
    """
    MicroClaw 的终端用户界面。

    提供交互式聊天体验:
    - Rich 格式化
    - 工具调用可视化
    - 会话管理
    - 斜杠命令
    """

    def __init__(
        self,
        agent: Optional[Agent] = None,
        session_store: Optional[SessionStore] = None,
        session_key: str = "main",
        config: Optional[AgentConfig] = None,
    ):
        self.console = Console()

        # 初始化 Agent
        self.config = config or AgentConfig()
        self.agent = agent or Agent(config=self.config)

        # 初始化会话存储
        storage_dir = str(Path(self.config.workspace_dir).expanduser() / "sessions")
        self.session_store = session_store or SessionStore(
            storage_dir=storage_dir, reset_policy=ResetPolicy(mode="daily", at_hour=4)
        )

        # 当前会话
        self.session_key = SessionKey.for_dm(agent_id="main", peer_id=None)
        if session_key != "main":
            self.session_key = SessionKey.parse(session_key)

        self.session = self.session_store.get(self.session_key)

        # 状态
        self._running = False
        self._current_tool: Optional[str] = None

    def _print_header(self):
        """打印头部横幅。"""
        header = Panel(
            Text.assemble(
                ("[M] MicroClaw", "bold white"),
                " | ",
                (f"模型: {self.config.model}", "cyan"),
                " | ",
                (f"会话: {self.session_key}", "green"),
            ),
            style=Theme.HEADER,
            box=box.ROUNDED,
        )
        self.console.print(header)
        self.console.print()

    def _print_status(self):
        """打印状态信息。"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()

        table.add_row("会话 ID:", self.session.session_id)
        table.add_row("消息数:", str(len(self.session.messages)))
        table.add_row("Token:", f"{self.session.total_tokens:,}")
        table.add_row("压缩次数:", str(self.session.compaction_count))
        table.add_row(
            "最后更新:", self.session.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        )

        self.console.print(Panel(table, title="[状态]", border_style="blue"))

    def _print_message(self, role: str, content: str, tool_name: Optional[str] = None):
        """打印格式化消息。"""
        if role == "user":
            self.console.print(f"[{Theme.USER}]你:[/] {content}")
        elif role == "assistant":
            # 渲染为 Markdown
            self.console.print(f"[{Theme.ASSISTANT}]助手:[/]")
            self.console.print(Markdown(content))
        elif role == "system":
            self.console.print(f"[{Theme.SYSTEM}]系统:[/] {content}")
        elif role == "tool":
            self.console.print(
                f"  [{Theme.TOOL}]--> {tool_name}:[/] {content[:200]}{'...' if len(content) > 200 else ''}"
            )
        elif role == "error":
            self.console.print(f"[{Theme.ERROR}]错误:[/] {content}")

        self.console.print()

    def _print_tool_start(self, name: str, args: Dict[str, Any]):
        """打印工具调用开始。"""
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
        self.console.print(f"  [{Theme.TOOL_START}][*] {name}({args_str})[/]")

    def _print_tool_end(self, name: str, result: str):
        """打印工具调用结果。"""
        preview = result[:100].replace("\n", " ")
        if len(result) > 100:
            preview += "..."
        self.console.print(f"  [{Theme.TOOL_END}][OK] {preview}[/]")

    def _on_tool_call(self, event: str, name: str, data: Any):
        """工具事件回调。"""
        if event == "start":
            self._print_tool_start(name, data)
        elif event == "end":
            self._print_tool_end(name, data)

    def _handle_slash_command(self, cmd: str) -> bool:
        """
        处理斜杠命令。

        如果命令已处理返回 True，传递通过返回 False。
        """
        parts = cmd.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command in ("/help", "/h"):
            self._print_help()
            return True

        elif command in ("/status", "/s"):
            self._print_status()
            return True

        elif command in ("/new", "/reset"):
            self.session = self.session_store.reset(self.session_key)
            self._print_message(
                "system", f"会话已重置。新 ID: {self.session.session_id}"
            )
            return True

        elif command == "/model":
            if args:
                # 解析 provider/model
                if "/" in args:
                    provider, model = args.split("/", 1)
                else:
                    provider = self.config.provider
                    model = args

                self.config.model = model
                self.config.provider = provider
                self.agent = Agent(config=self.config, tools=self.agent.tools)
                self._print_message("system", f"模型已设置为: {provider}/{model}")
            else:
                self._print_message(
                    "system", f"当前模型: {self.config.provider}/{self.config.model}"
                )
            return True

        elif command == "/sessions":
            sessions = self.session_store.list(active_minutes=60 * 24 * 7)  # 最近一周
            if not sessions:
                self._print_message("system", "未找到会话。")
            else:
                table = Table(title="会话列表", box=box.ROUNDED)
                table.add_column("键")
                table.add_column("更新时间")
                table.add_column("Token")

                for s in sessions[:20]:
                    table.add_row(
                        s["key"], s["updated_at"][:19], f"{s['total_tokens']:,}"
                    )

                self.console.print(table)
            return True

        elif command == "/session":
            if args:
                self.session_key = SessionKey.parse(args)
                self.session = self.session_store.get(self.session_key)
                self._print_message("system", f"已切换到会话: {self.session_key}")
            else:
                self._print_message("system", f"当前会话: {self.session_key}")
            return True

        elif command == "/history":
            limit = int(args) if args else 10
            for msg in self.session.messages[-limit:]:
                role = msg.role.value if isinstance(msg.role, MessageRole) else msg.role
                self._print_message(role, msg.content, msg.name)
            return True

        elif command in ("/compact",):
            self._print_message("system", "正在压缩会话...")
            # 这里会运行压缩
            return True

        elif command in ("/exit", "/quit", "/q"):
            self._running = False
            return True

        elif command == "/clear":
            self.console.clear()
            self._print_header()
            return True

        return False

    def _print_help(self):
        """打印帮助信息。"""
        help_text = """
## 命令

| 命令 | 描述 |
|---------|-------------|
| `/help` | 显示此帮助 |
| `/status` | 显示会话状态 |
| `/new` | 重置当前会话 |
| `/model [provider/model]` | 显示或设置模型 |
| `/sessions` | 列出最近会话 |
| `/session <key>` | 切换到指定会话 |
| `/history [n]` | 显示最近 n 条消息 |
| `/compact` | 压缩会话历史 |
| `/clear` | 清屏 |
| `/exit` | 退出 TUI |

## 提示

- 正常输入以与 Agent 聊天
- Agent 可以使用工具 (文件访问、Shell、网络搜索)
- 会话在重启后保持
- 使用 Ctrl+C 中断，Ctrl+D 退出
"""
        self.console.print(
            Panel(Markdown(help_text), title="帮助", border_style="blue")
        )

    async def _process_message(self, message: str):
        """处理用户消息。"""
        try:
            # 检查是否启用流式输出
            if self.config.stream:
                await self._process_message_stream(message)
            else:
                await self._process_message_sync(message)

        except KeyboardInterrupt:
            self._print_message("system", "已中断。")
        except Exception as e:
            self._print_message("error", str(e))

    async def _process_message_stream(self, message: str):
        """流式处理用户消息。"""
        from rich.live import Live
        from rich.text import Text

        # 打印助手标签
        self.console.print(f"[{Theme.ASSISTANT}]助手:[/]")

        # 收集完整响应
        full_response = Text()
        response_text = ""

        # 创建 Live 显示
        with Live(
            full_response, console=self.console, refresh_per_second=10, transient=False
        ) as live:
            async for chunk in self.agent.run_stream(
                message=message,
                session=self.session,
                on_tool_call=self._on_tool_call,
                is_main_session=True,
            ):
                if isinstance(chunk, str):
                    # 文本块
                    response_text += chunk
                    full_response = Text(response_text)
                    live.update(full_response)
                elif isinstance(chunk, dict):
                    # 工具调用事件
                    if chunk.get("type") == "tool_start":
                        # 暂停 live，打印工具调用
                        live.stop()
                        self._print_tool_start(
                            chunk.get("name", ""), chunk.get("args", {})
                        )
                        # 重新开始 live
                        live.start()
                    elif chunk.get("type") == "tool_end":
                        # 暂停 live，打印工具结果
                        live.stop()
                        self._print_tool_end(
                            chunk.get("name", ""), chunk.get("result", "")
                        )
                        # 重新开始 live
                        live.start()

        # 保存会话
        self.session_store.save(self.session)

        # 空行分隔
        self.console.print()

    async def _process_message_sync(self, message: str):
        """同步处理用户消息（非流式）。"""
        # 显示"思考中"指示器
        with self.console.status("[bold green]思考中...", spinner="dots"):
            response = await self.agent.run(
                message=message,
                session=self.session,
                on_tool_call=self._on_tool_call,
                is_main_session=True,
            )

        # 保存会话
        self.session_store.save(self.session)

        # 打印响应
        self._print_message("assistant", response)

    def _print_loading_context(self):
        """打印上下文加载信息。"""

        workspace = self.agent.workspace

        # 显示加载状态
        with self.console.status("[bold green]加载工作区上下文...", spinner="dots"):
            loaded = []

            # 检查各文件是否加载
            if workspace.read_agents():
                loaded.append("AGENTS.md")
            if workspace.read_soul():
                loaded.append("SOUL.md")
            if workspace.read_user():
                loaded.append("USER.md")
            if workspace.read_memory():
                loaded.append("MEMORY.md")

            # 检查技能
            skills = workspace.list_skills()
            if skills:
                loaded.append(f"技能 ({len(skills)}个)")

            # 检查每日笔记
            daily = workspace.read_recent_daily(2)
            if daily:
                loaded.append(f"日志 ({len(daily)}天)")

        # 显示加载结果
        if loaded:
            self.console.print(f"[dim]已加载: {', '.join(loaded)}[/]")
            self.console.print()

    async def run_async(self):
        """异步运行 TUI。"""
        self._running = True

        # 打印头部
        self._print_header()

        # 显示上下文加载信息
        self._print_loading_context()

        self.console.print("[dim]输入 /help 查看命令，/exit 退出[/]")
        self.console.print()

        # 主循环
        while self._running:
            try:
                # 获取输入
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: Prompt.ask(f"[{Theme.PROMPT}]你[/]")
                )

                if not user_input.strip():
                    continue

                # 处理斜杠命令
                if user_input.startswith("/"):
                    if self._handle_slash_command(user_input):
                        continue

                # 作为消息处理
                await self._process_message(user_input)

            except EOFError:
                break
            except KeyboardInterrupt:
                self.console.print("\n[dim]按 Ctrl+D 或输入 /exit 退出[/]")

    def run(self):
        """运行 TUI (阻塞)。"""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n[dim]再见！[/]")


def main():
    """TUI 的主入口点。"""
    import argparse

    parser = argparse.ArgumentParser(description="MicroClaw TUI")
    parser.add_argument("--model", "-m", default="gpt-4o-mini", help="使用的模型")
    parser.add_argument(
        "--provider", "-p", default="openai", help="提供商 (openai, anthropic, ollama)"
    )
    parser.add_argument("--session", "-s", default="main", help="会话键")
    parser.add_argument(
        "--workspace", "-w", default="~/.microclaw/workspace", help="工作区目录"
    )

    args = parser.parse_args()

    config = AgentConfig(
        model=args.model,
        provider=args.provider,
        workspace_dir=args.workspace,
    )

    tui = TUI(config=config, session_key=args.session)
    tui.run()


if __name__ == "__main__":
    main()
