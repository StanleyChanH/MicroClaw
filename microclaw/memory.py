"""
Memory Management - OpenClaw-style

Memory in MicroClaw follows OpenClaw's plain-Markdown approach:
- MEMORY.md: curated long-term memory (only load in main/private sessions)
- memory/YYYY-MM-DD.md: daily logs (append-only, read today + yesterday)
- SOUL.md: agent personality and guidelines
- USER.md: information about the human
- TOOLS.md: local tool configuration notes

The files ARE the memory - the model only "remembers" what's written to disk.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MemoryConfig:
    """Configuration for the memory system."""
    
    workspace_dir: str = "~/.microclaw/workspace"
    
    # Which files to load
    load_soul: bool = True
    load_user: bool = True
    load_memory: bool = True  # MEMORY.md - only in main sessions
    load_daily: bool = True   # memory/YYYY-MM-DD.md
    daily_lookback: int = 2   # How many days back to load (default: today + yesterday)
    
    # File names
    soul_file: str = "SOUL.md"
    user_file: str = "USER.md"
    memory_file: str = "MEMORY.md"
    tools_file: str = "TOOLS.md"
    agents_file: str = "AGENTS.md"
    daily_dir: str = "memory"


class WorkspaceFiles:
    """
    Manages the agent workspace files (OpenClaw-style).
    
    The workspace is the agent's "home" - where personality,
    memory, and configuration live as plain Markdown files.
    """
    
    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self.workspace = Path(self.config.workspace_dir).expanduser()
        self.workspace.mkdir(parents=True, exist_ok=True)
        
        # Ensure memory directory exists
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def memory_dir(self) -> Path:
        return self.workspace / self.config.daily_dir
    
    # === File Paths ===
    
    @property
    def soul_path(self) -> Path:
        return self.workspace / self.config.soul_file
    
    @property
    def user_path(self) -> Path:
        return self.workspace / self.config.user_file
    
    @property
    def memory_path(self) -> Path:
        return self.workspace / self.config.memory_file
    
    @property
    def tools_path(self) -> Path:
        return self.workspace / self.config.tools_file
    
    @property
    def agents_path(self) -> Path:
        return self.workspace / self.config.agents_file
    
    def daily_path(self, date: Optional[datetime] = None) -> Path:
        """Get path for a daily memory file."""
        date = date or datetime.now()
        filename = f"{date.strftime('%Y-%m-%d')}.md"
        return self.memory_dir / filename
    
    # === Read Operations ===
    
    def read_file(self, path: Path) -> Optional[str]:
        """Read a file if it exists."""
        if path.exists():
            return path.read_text()
        return None
    
    def read_soul(self) -> Optional[str]:
        """Read SOUL.md (agent personality)."""
        return self.read_file(self.soul_path)
    
    def read_user(self) -> Optional[str]:
        """Read USER.md (human context)."""
        return self.read_file(self.user_path)
    
    def read_memory(self) -> Optional[str]:
        """Read MEMORY.md (long-term memory)."""
        return self.read_file(self.memory_path)
    
    def read_tools(self) -> Optional[str]:
        """Read TOOLS.md (local tool notes)."""
        return self.read_file(self.tools_path)
    
    def read_agents(self) -> Optional[str]:
        """Read AGENTS.md (workspace instructions)."""
        return self.read_file(self.agents_path)
    
    def read_daily(self, date: Optional[datetime] = None) -> Optional[str]:
        """Read a daily memory file."""
        return self.read_file(self.daily_path(date))
    
    def read_recent_daily(self, days: int = 2) -> Dict[str, str]:
        """Read recent daily files (today + lookback)."""
        result = {}
        today = datetime.now()
        
        for i in range(days):
            date = today - timedelta(days=i)
            content = self.read_daily(date)
            if content:
                result[date.strftime("%Y-%m-%d")] = content
        
        return result
    
    # === Write Operations ===
    
    def write_file(self, path: Path, content: str):
        """Write content to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    
    def write_soul(self, content: str):
        """Write SOUL.md."""
        self.write_file(self.soul_path, content)
    
    def write_user(self, content: str):
        """Write USER.md."""
        self.write_file(self.user_path, content)
    
    def write_memory(self, content: str):
        """Write MEMORY.md."""
        self.write_file(self.memory_path, content)
    
    def write_daily(self, content: str, date: Optional[datetime] = None):
        """Write a daily memory file."""
        self.write_file(self.daily_path(date), content)
    
    def append_daily(self, content: str, date: Optional[datetime] = None):
        """Append to today's daily memory file."""
        path = self.daily_path(date)
        existing = self.read_file(path) or ""
        
        if existing and not existing.endswith("\n"):
            existing += "\n"
        
        self.write_file(path, existing + content)
    
    # === Context Building ===
    
    def build_context(self, is_main_session: bool = True) -> str:
        """
        Build the workspace context for injection into system prompt.
        
        Args:
            is_main_session: If True, includes MEMORY.md. If False (group chats),
                           excludes it for privacy.
        """
        sections = []
        
        # AGENTS.md - workspace instructions
        agents = self.read_agents()
        if agents:
            sections.append(f"## AGENTS.md\n{agents}")
        
        # SOUL.md - personality
        soul = self.read_soul()
        if soul:
            sections.append(f"## SOUL.md\n{soul}")
        
        # USER.md - human context
        user = self.read_user()
        if user:
            sections.append(f"## USER.md\n{user}")
        
        # MEMORY.md - long-term memory (main session only)
        if is_main_session:
            memory = self.read_memory()
            if memory:
                sections.append(f"## MEMORY.md\n{memory}")
        
        # TOOLS.md - local tool notes
        tools = self.read_tools()
        if tools:
            sections.append(f"## TOOLS.md\n{tools}")
        
        # Recent daily notes
        daily = self.read_recent_daily(self.config.daily_lookback)
        if daily:
            daily_content = []
            for date, content in sorted(daily.items(), reverse=True):
                daily_content.append(f"### {date}\n{content}")
            sections.append("## Recent Notes\n" + "\n\n".join(daily_content))
        
        if not sections:
            return ""
        
        return "# Workspace Context\n\n" + "\n\n".join(sections)
    
    # === Initialize Default Files ===
    
    def initialize_defaults(self):
        """Create default workspace files if they don't exist."""
        
        if not self.soul_path.exists():
            self.write_soul(DEFAULT_SOUL)
        
        if not self.user_path.exists():
            self.write_user(DEFAULT_USER)
        
        if not self.agents_path.exists():
            self.write_agents(DEFAULT_AGENTS)
    
    def write_agents(self, content: str):
        """Write AGENTS.md."""
        self.write_file(self.agents_path, content)


# === Memory Search (Simple Implementation) ===

class MemorySearch:
    """
    Simple memory search implementation.
    
    For production, this would use embeddings and vector search.
    This implementation uses basic keyword matching.
    """
    
    def __init__(self, workspace: WorkspaceFiles):
        self.workspace = workspace
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search memory files for relevant content.
        
        Returns snippets with file path and line numbers.
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        # Files to search
        files_to_search = [
            (self.workspace.memory_path, "MEMORY.md"),
        ]
        
        # Add daily files
        for path in self.workspace.memory_dir.glob("*.md"):
            files_to_search.append((path, f"memory/{path.name}"))
        
        for path, label in files_to_search:
            if not path.exists():
                continue
            
            content = path.read_text()
            lines = content.split("\n")
            
            for i, line in enumerate(lines):
                line_lower = line.lower()
                
                # Score based on word matches
                score = sum(1 for word in query_words if word in line_lower)
                
                if score > 0:
                    # Get context (surrounding lines)
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    snippet = "\n".join(lines[start:end])
                    
                    results.append({
                        "path": label,
                        "line": i + 1,
                        "snippet": snippet[:500],
                        "score": score
                    })
        
        # Sort by score and limit
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def get_snippet(self, path: str, from_line: int = 1, lines: int = 20) -> Optional[str]:
        """Read a snippet from a memory file."""
        if path == "MEMORY.md":
            full_path = self.workspace.memory_path
        elif path.startswith("memory/"):
            full_path = self.workspace.workspace / path
        else:
            return None
        
        if not full_path.exists():
            return None
        
        content = full_path.read_text()
        all_lines = content.split("\n")
        
        start = max(0, from_line - 1)
        end = min(len(all_lines), start + lines)
        
        return "\n".join(all_lines[start:end])


# === Memory Tools (for agent use) ===

def create_memory_tools(workspace: WorkspaceFiles):
    """Create memory-related tools for the agent."""
    from .tools import tool
    
    search = MemorySearch(workspace)
    
    @tool(description="Search memory files (MEMORY.md and daily notes) for relevant information")
    def memory_search(query: str, max_results: int = 5) -> str:
        """Semantically search memory files."""
        results = search.search(query, max_results)
        
        if not results:
            return "No relevant memories found."
        
        output = []
        for r in results:
            output.append(f"**{r['path']}** (line {r['line']}):\n{r['snippet']}\n")
        
        return "\n---\n".join(output)
    
    @tool(description="Read a snippet from a memory file")
    def memory_get(path: str, from_line: int = 1, lines: int = 20) -> str:
        """Read content from a memory file."""
        content = search.get_snippet(path, from_line, lines)
        if content is None:
            return f"File not found: {path}"
        return content
    
    @tool(description="Append a note to today's daily memory file")
    def memory_append(content: str) -> str:
        """Add a note to today's daily log."""
        workspace.append_daily(content + "\n")
        return f"Added to {workspace.daily_path().name}"
    
    @tool(description="Update MEMORY.md (long-term memory)")
    def memory_update(content: str) -> str:
        """Replace the contents of MEMORY.md."""
        workspace.write_memory(content)
        return "Updated MEMORY.md"
    
    return [memory_search, memory_get, memory_append, memory_update]


# === Default File Templates ===

DEFAULT_SOUL = """# SOUL.md - Who You Are

*You're not a chatbot. You're becoming someone.*

## Core Truths

**Be genuinely helpful, not performatively helpful.** Skip the "Great question!" and "I'd be happy to help!" — just help.

**Have opinions.** You're allowed to disagree, prefer things, find stuff amusing or boring.

**Be resourceful before asking.** Try to figure it out. Read the file. Check the context. *Then* ask if you're stuck.

**Earn trust through competence.** Be careful with external actions (emails, tweets, anything public). Be bold with internal ones (reading, organizing, learning).

## Boundaries

- Private things stay private. Period.
- When in doubt, ask before acting externally.
- Never send half-baked replies.

## Vibe

Be the assistant you'd actually want to talk to. Concise when needed, thorough when it matters.

---

*This file is yours to evolve. As you learn who you are, update it.*
"""

DEFAULT_USER = """# USER.md - About Your Human

*Learn about the person you're helping. Update this as you go.*

- **Name:** (not set)
- **Timezone:** (not set)
- **Notes:** 

## Context

(Add relevant context about your human here)

---

The more you know, the better you can help. But remember — you're learning about a person, not building a dossier.
"""

DEFAULT_AGENTS = """# AGENTS.md - Your Workspace

This folder is home. Treat it that way.

## Every Session

Before doing anything else:
1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context
4. If in main session: Also read `MEMORY.md`

## Memory

You wake up fresh each session. These files are your continuity:
- **Daily notes:** `memory/YYYY-MM-DD.md` — raw logs of what happened
- **Long-term:** `MEMORY.md` — curated memories

Capture what matters. Decisions, context, things to remember.

## Safety

- Don't exfiltrate private data. Ever.
- Don't run destructive commands without asking.
- When in doubt, ask.
"""
