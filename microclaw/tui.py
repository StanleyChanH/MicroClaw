"""
TUI - Terminal User Interface (OpenClaw-style)

A Rich-based terminal interface for interacting with the agent.
Features:
- Chat log with formatted messages
- Tool call visualization
- Status bar with session info
- Slash commands (/help, /status, /new, /model, etc.)
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
    """Color theme for the TUI."""
    
    # Message colors
    USER = "bold cyan"
    ASSISTANT = "bold green"
    SYSTEM = "bold yellow"
    ERROR = "bold red"
    TOOL = "bold magenta"
    
    # UI colors
    HEADER = "bold white on blue"
    STATUS = "dim"
    PROMPT = "bold cyan"
    
    # Tool status
    TOOL_START = "yellow"
    TOOL_END = "green"


class TUI:
    """
    Terminal User Interface for MicroClaw.
    
    Provides an interactive chat experience with:
    - Rich formatting
    - Tool call visualization
    - Session management
    - Slash commands
    """
    
    def __init__(
        self,
        agent: Optional[Agent] = None,
        session_store: Optional[SessionStore] = None,
        session_key: str = "main",
        config: Optional[AgentConfig] = None,
    ):
        self.console = Console()
        
        # Initialize agent
        self.config = config or AgentConfig()
        self.agent = agent or Agent(config=self.config)
        
        # Initialize session store
        storage_dir = str(Path(self.config.workspace_dir).expanduser() / "sessions")
        self.session_store = session_store or SessionStore(
            storage_dir=storage_dir,
            reset_policy=ResetPolicy(mode="daily", at_hour=4)
        )
        
        # Current session
        self.session_key = SessionKey.for_dm(agent_id="main", peer_id=None)
        if session_key != "main":
            self.session_key = SessionKey.parse(session_key)
        
        self.session = self.session_store.get(self.session_key)
        
        # State
        self._running = False
        self._current_tool: Optional[str] = None
    
    def _print_header(self):
        """Print the header banner."""
        header = Panel(
            Text.assemble(
                ("🦞 MicroClaw", "bold white"),
                " | ",
                (f"Model: {self.config.model}", "cyan"),
                " | ",
                (f"Session: {self.session_key}", "green"),
            ),
            style=Theme.HEADER,
            box=box.ROUNDED,
        )
        self.console.print(header)
        self.console.print()
    
    def _print_status(self):
        """Print status information."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="dim")
        table.add_column()
        
        table.add_row("Session ID:", self.session.session_id)
        table.add_row("Messages:", str(len(self.session.messages)))
        table.add_row("Tokens:", f"{self.session.total_tokens:,}")
        table.add_row("Compactions:", str(self.session.compaction_count))
        table.add_row("Last update:", self.session.updated_at.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.console.print(Panel(table, title="📊 Status", border_style="blue"))
    
    def _print_message(self, role: str, content: str, tool_name: Optional[str] = None):
        """Print a formatted message."""
        if role == "user":
            self.console.print(f"[{Theme.USER}]You:[/] {content}")
        elif role == "assistant":
            # Render as markdown
            self.console.print(f"[{Theme.ASSISTANT}]Assistant:[/]")
            self.console.print(Markdown(content))
        elif role == "system":
            self.console.print(f"[{Theme.SYSTEM}]System:[/] {content}")
        elif role == "tool":
            self.console.print(f"  [{Theme.TOOL}]↳ {tool_name}:[/] {content[:200]}{'...' if len(content) > 200 else ''}")
        elif role == "error":
            self.console.print(f"[{Theme.ERROR}]Error:[/] {content}")
        
        self.console.print()
    
    def _print_tool_start(self, name: str, args: Dict[str, Any]):
        """Print tool call start."""
        args_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in args.items())
        self.console.print(f"  [{Theme.TOOL_START}]⚙️  {name}({args_str})[/]")
    
    def _print_tool_end(self, name: str, result: str):
        """Print tool call result."""
        preview = result[:100].replace("\n", " ")
        if len(result) > 100:
            preview += "..."
        self.console.print(f"  [{Theme.TOOL_END}]✓ {preview}[/]")
    
    def _on_tool_call(self, event: str, name: str, data: Any):
        """Callback for tool events."""
        if event == "start":
            self._print_tool_start(name, data)
        elif event == "end":
            self._print_tool_end(name, data)
    
    def _handle_slash_command(self, cmd: str) -> bool:
        """
        Handle slash commands.
        
        Returns True if the command was handled, False to pass through.
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
            self._print_message("system", f"Session reset. New ID: {self.session.session_id}")
            return True
        
        elif command == "/model":
            if args:
                # Parse provider/model
                if "/" in args:
                    provider, model = args.split("/", 1)
                else:
                    provider = self.config.provider
                    model = args
                
                self.config.model = model
                self.config.provider = provider
                self.agent = Agent(config=self.config, tools=self.agent.tools)
                self._print_message("system", f"Model set to: {provider}/{model}")
            else:
                self._print_message("system", f"Current model: {self.config.provider}/{self.config.model}")
            return True
        
        elif command == "/sessions":
            sessions = self.session_store.list(active_minutes=60*24*7)  # Last week
            if not sessions:
                self._print_message("system", "No sessions found.")
            else:
                table = Table(title="Sessions", box=box.ROUNDED)
                table.add_column("Key")
                table.add_column("Updated")
                table.add_column("Tokens")
                
                for s in sessions[:20]:
                    table.add_row(
                        s["key"],
                        s["updated_at"][:19],
                        f"{s['total_tokens']:,}"
                    )
                
                self.console.print(table)
            return True
        
        elif command == "/session":
            if args:
                self.session_key = SessionKey.parse(args)
                self.session = self.session_store.get(self.session_key)
                self._print_message("system", f"Switched to session: {self.session_key}")
            else:
                self._print_message("system", f"Current session: {self.session_key}")
            return True
        
        elif command == "/history":
            limit = int(args) if args else 10
            for msg in self.session.messages[-limit:]:
                role = msg.role.value if isinstance(msg.role, MessageRole) else msg.role
                self._print_message(role, msg.content, msg.name)
            return True
        
        elif command in ("/compact",):
            self._print_message("system", "Compacting session...")
            # This would run compaction
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
        """Print help information."""
        help_text = """
## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this help |
| `/status` | Show session status |
| `/new` | Reset the current session |
| `/model [provider/model]` | Show or set the model |
| `/sessions` | List recent sessions |
| `/session <key>` | Switch to a session |
| `/history [n]` | Show last n messages |
| `/compact` | Compact session history |
| `/clear` | Clear the screen |
| `/exit` | Exit the TUI |

## Tips

- Type normally to chat with the agent
- The agent can use tools (file access, shell, web search)
- Sessions persist across restarts
- Use Ctrl+C to interrupt, Ctrl+D to exit
"""
        self.console.print(Panel(Markdown(help_text), title="Help", border_style="blue"))
    
    async def _process_message(self, message: str):
        """Process a user message."""
        try:
            # Show "thinking" indicator
            with self.console.status("[bold green]Thinking...", spinner="dots"):
                response = await self.agent.run(
                    message=message,
                    session=self.session,
                    on_tool_call=self._on_tool_call,
                    is_main_session=True
                )
            
            # Save session
            self.session_store.save(self.session)
            
            # Print response
            self._print_message("assistant", response)
            
        except KeyboardInterrupt:
            self._print_message("system", "Interrupted.")
        except Exception as e:
            self._print_message("error", str(e))
    
    async def run_async(self):
        """Run the TUI asynchronously."""
        self._running = True
        
        # Print header
        self._print_header()
        
        self.console.print("[dim]Type /help for commands, /exit to quit[/]")
        self.console.print()
        
        # Main loop
        while self._running:
            try:
                # Get input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: Prompt.ask(f"[{Theme.PROMPT}]You[/]")
                )
                
                if not user_input.strip():
                    continue
                
                # Handle slash commands
                if user_input.startswith("/"):
                    if self._handle_slash_command(user_input):
                        continue
                
                # Process as message
                await self._process_message(user_input)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                self.console.print("\n[dim]Press Ctrl+D or type /exit to quit[/]")
    
    def run(self):
        """Run the TUI (blocking)."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            pass
        finally:
            self.console.print("\n[dim]Goodbye! 👋[/]")


def main():
    """Main entry point for the TUI."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MicroClaw TUI")
    parser.add_argument("--model", "-m", default="gpt-4o-mini", help="Model to use")
    parser.add_argument("--provider", "-p", default="openai", help="Provider (openai, anthropic, ollama)")
    parser.add_argument("--session", "-s", default="main", help="Session key")
    parser.add_argument("--workspace", "-w", default="~/.microclaw/workspace", help="Workspace directory")
    
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
