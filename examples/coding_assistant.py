"""
Coding Assistant Example

A more complete example showing how to build a coding-focused agent
with file operations, shell access, and project awareness.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from microclaw import Gateway, GatewayConfig, tool
from microclaw.gateway import CLIChannel


# === Coding-specific Tools ===

@tool(description="List files in a directory")
def list_files(path: str = ".", recursive: bool = False) -> str:
    """List files in a directory."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Path does not exist: {path}"
        
        if recursive:
            files = list(p.rglob("*"))
        else:
            files = list(p.iterdir())
        
        # Filter out hidden files and format nicely
        result = []
        for f in sorted(files)[:50]:  # Limit to 50 files
            if f.name.startswith('.'):
                continue
            icon = "📁" if f.is_dir() else "📄"
            result.append(f"{icon} {f.relative_to(p) if recursive else f.name}")
        
        if not result:
            return "(empty directory)"
        
        return "\n".join(result)
    except Exception as e:
        return f"Error: {e}"


@tool(description="Search for text in files")
def search_in_files(pattern: str, path: str = ".", file_pattern: str = "*.py") -> str:
    """Search for a pattern in files."""
    try:
        import re
        
        results = []
        for file_path in Path(path).rglob(file_pattern):
            if '.git' in str(file_path):
                continue
            try:
                content = file_path.read_text()
                for i, line in enumerate(content.split('\n'), 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        results.append(f"{file_path}:{i}: {line.strip()[:80]}")
            except:
                pass
        
        if not results:
            return f"No matches found for '{pattern}'"
        
        return "\n".join(results[:20])  # Limit results
    except Exception as e:
        return f"Error: {e}"


@tool(description="Get git status of the current repository")
def git_status() -> str:
    """Get the current git status."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            timeout=10
        )
        output = result.stdout.strip()
        if not output:
            return "Working tree clean - no changes"
        return output
    except Exception as e:
        return f"Error: {e}"


@tool(description="Show recent git commits")
def git_log(count: int = 5) -> str:
    """Show recent git commits."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "log", f"-{count}", "--oneline"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() or "No commits found"
    except Exception as e:
        return f"Error: {e}"


@tool(description="Run Python code and return the output")
def run_python(code: str) -> str:
    """Execute Python code in a subprocess."""
    import subprocess
    import tempfile
    
    try:
        # Write code to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        
        # Execute
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Cleanup
        os.unlink(temp_path)
        
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out (30s limit)"
    except Exception as e:
        return f"Error: {e}"


CODING_SYSTEM_PROMPT = """You are a skilled coding assistant with access to file system and shell tools.

## Your Capabilities
- Read and write files
- List directory contents
- Search for patterns in code
- Execute shell commands
- Run Python code
- Check git status and history

## Guidelines
1. **Explore first**: Before making changes, understand the codebase structure
2. **Be surgical**: Make minimal, targeted changes
3. **Explain clearly**: When showing code, explain what it does
4. **Test your work**: Run code to verify it works
5. **Be safe**: Don't delete files without asking, prefer git operations

## When writing code
- Follow existing code style
- Add comments for complex logic
- Handle errors gracefully
- Keep functions focused and small

You're working in: {cwd}
""".format(cwd=os.getcwd())


async def main():
    config = GatewayConfig(
        storage_dir=".microclaw-coding",
        default_model="gpt-4o",  # Use a more capable model for coding
        default_provider="openai",
        system_prompt=CODING_SYSTEM_PROMPT
    )
    
    gateway = Gateway(config)
    
    # Register coding tools
    gateway.add_tool(list_files)
    gateway.add_tool(search_in_files)
    gateway.add_tool(git_status)
    gateway.add_tool(git_log)
    gateway.add_tool(run_python)
    
    # Add CLI channel
    gateway.add_channel(CLIChannel())
    
    # Verbose tool logging
    def on_tool_call(event, name, data):
        if event == "start":
            print(f"\n  ⚙️  {name}")
        elif event == "end":
            lines = str(data).split('\n')
            preview = lines[0][:60]
            if len(lines) > 1:
                preview += f" (+{len(lines)-1} lines)"
            print(f"  →  {preview}")
    
    gateway.on("tool_call", on_tool_call)
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║            🦞 MicroClaw Coding Assistant                   ║
╚═══════════════════════════════════════════════════════════╝

Working directory: {os.getcwd()}

Try:
  - "Show me the project structure"
  - "Find all TODO comments"
  - "What changed recently? (git)"
  - "Write a function to calculate fibonacci numbers"
  - "Create a simple Flask API in app.py"

Type 'quit' to exit.
""")
    
    await gateway.start()


if __name__ == "__main__":
    asyncio.run(main())
