"""
记忆管理 - OpenClaw 风格

MicroClaw 的记忆系统遵循 OpenClaw 的纯 Markdown 方式:
- MEMORY.md: 精选的长期记忆 (仅在主/私有会话中加载)
- memory/YYYY-MM-DD.md: 每日日志 (追加式，读取今天和昨天)
- SOUL.md: Agent 人格和行为准则
- USER.md: 关于用户的信息
- TOOLS.md: 本地工具配置说明

文件即记忆 - 模型只"记住"写入磁盘的内容。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MemoryConfig:
    """记忆系统配置。"""

    workspace_dir: str = "~/.microclaw/workspace"

    # 要加载的文件
    load_soul: bool = True
    load_user: bool = True
    load_memory: bool = True  # MEMORY.md - 仅在主会话中
    load_daily: bool = True   # memory/YYYY-MM-DD.md
    daily_lookback: int = 2   # 回溯多少天 (默认: 今天 + 昨天)

    # 文件名
    soul_file: str = "SOUL.md"
    user_file: str = "USER.md"
    memory_file: str = "MEMORY.md"
    tools_file: str = "TOOLS.md"
    agents_file: str = "AGENTS.md"
    daily_dir: str = "memory"


class WorkspaceFiles:
    """
    管理 Agent 工作区文件 (OpenClaw 风格)。

    工作区是 Agent 的"家" - 人格、记忆和配置都以纯 Markdown 文件形式存在。
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config or MemoryConfig()
        self.workspace = Path(self.config.workspace_dir).expanduser()
        self.workspace.mkdir(parents=True, exist_ok=True)

        # 确保记忆目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_dir(self) -> Path:
        return self.workspace / self.config.daily_dir

    # === 文件路径 ===

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
        """获取每日记忆文件的路径。"""
        date = date or datetime.now()
        filename = f"{date.strftime('%Y-%m-%d')}.md"
        return self.memory_dir / filename

    # === 读取操作 ===

    def read_file(self, path: Path) -> Optional[str]:
        """如果文件存在则读取。"""
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    def read_soul(self) -> Optional[str]:
        """读取 SOUL.md (Agent 人格)。"""
        return self.read_file(self.soul_path)

    def read_user(self) -> Optional[str]:
        """读取 USER.md (用户上下文)。"""
        return self.read_file(self.user_path)

    def read_memory(self) -> Optional[str]:
        """读取 MEMORY.md (长期记忆)。"""
        return self.read_file(self.memory_path)

    def read_tools(self) -> Optional[str]:
        """读取 TOOLS.md (本地工具说明)。"""
        return self.read_file(self.tools_path)

    def read_agents(self) -> Optional[str]:
        """读取 AGENTS.md (工作区说明)。"""
        return self.read_file(self.agents_path)

    def read_daily(self, date: Optional[datetime] = None) -> Optional[str]:
        """读取每日记忆文件。"""
        return self.read_file(self.daily_path(date))

    def read_recent_daily(self, days: int = 2) -> Dict[str, str]:
        """读取最近的每日文件 (今天 + 回溯)。"""
        result = {}
        today = datetime.now()

        for i in range(days):
            date = today - timedelta(days=i)
            content = self.read_daily(date)
            if content:
                result[date.strftime("%Y-%m-%d")] = content

        return result

    # === 写入操作 ===

    def write_file(self, path: Path, content: str):
        """将内容写入文件。"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def write_soul(self, content: str):
        """写入 SOUL.md。"""
        self.write_file(self.soul_path, content)

    def write_user(self, content: str):
        """写入 USER.md。"""
        self.write_file(self.user_path, content)

    def write_memory(self, content: str):
        """写入 MEMORY.md。"""
        self.write_file(self.memory_path, content)

    def write_daily(self, content: str, date: Optional[datetime] = None):
        """写入每日记忆文件。"""
        self.write_file(self.daily_path(date), content)

    def append_daily(self, content: str, date: Optional[datetime] = None):
        """追加到今天的每日记忆文件。"""
        path = self.daily_path(date)
        existing = self.read_file(path) or ""

        if existing and not existing.endswith("\n"):
            existing += "\n"

        self.write_file(path, existing + content)

    # === 上下文构建 ===

    def build_context(self, is_main_session: bool = True) -> str:
        """
        构建工作区上下文以注入系统提示。

        参数:
            is_main_session: 如果为 True，包含 MEMORY.md。如果为 False (群聊)，
                           出于隐私考虑排除它。
        """
        sections = []

        # AGENTS.md - 工作区说明
        agents = self.read_agents()
        if agents:
            sections.append(f"## AGENTS.md\n{agents}")

        # SOUL.md - 人格
        soul = self.read_soul()
        if soul:
            sections.append(f"## SOUL.md\n{soul}")

        # USER.md - 用户上下文
        user = self.read_user()
        if user:
            sections.append(f"## USER.md\n{user}")

        # MEMORY.md - 长期记忆 (仅主会话)
        if is_main_session:
            memory = self.read_memory()
            if memory:
                sections.append(f"## MEMORY.md\n{memory}")

        # TOOLS.md - 本地工具说明
        tools = self.read_tools()
        if tools:
            sections.append(f"## TOOLS.md\n{tools}")

        # 最近的每日笔记
        daily = self.read_recent_daily(self.config.daily_lookback)
        if daily:
            daily_content = []
            for date, content in sorted(daily.items(), reverse=True):
                daily_content.append(f"### {date}\n{content}")
            sections.append("## 最近笔记\n" + "\n\n".join(daily_content))

        if not sections:
            return ""

        return "# 工作区上下文\n\n" + "\n\n".join(sections)

    # === 初始化默认文件 ===

    def initialize_defaults(self):
        """如果不存在则创建默认工作区文件。"""

        if not self.soul_path.exists():
            self.write_soul(DEFAULT_SOUL)

        if not self.user_path.exists():
            self.write_user(DEFAULT_USER)

        if not self.agents_path.exists():
            self.write_agents(DEFAULT_AGENTS)

    def write_agents(self, content: str):
        """写入 AGENTS.md。"""
        self.write_file(self.agents_path, content)


# === 记忆搜索 (简单实现) ===

class MemorySearch:
    """
    简单的记忆搜索实现。

    生产环境应使用嵌入和向量搜索。
    此实现使用基本的关键词匹配。
    """

    def __init__(self, workspace: WorkspaceFiles):
        self.workspace = workspace

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        在记忆文件中搜索相关内容。

        返回带有文件路径和行号的片段。
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # 要搜索的文件
        files_to_search = [
            (self.workspace.memory_path, "MEMORY.md"),
        ]

        # 添加每日文件
        for path in self.workspace.memory_dir.glob("*.md"):
            files_to_search.append((path, f"memory/{path.name}"))

        for path, label in files_to_search:
            if not path.exists():
                continue

            content = path.read_text(encoding='utf-8')
            lines = content.split("\n")

            for i, line in enumerate(lines):
                line_lower = line.lower()

                # 基于词语匹配评分
                score = sum(1 for word in query_words if word in line_lower)

                if score > 0:
                    # 获取上下文 (周围行)
                    start = max(0, i - 1)
                    end = min(len(lines), i + 2)
                    snippet = "\n".join(lines[start:end])

                    results.append({
                        "path": label,
                        "line": i + 1,
                        "snippet": snippet[:500],
                        "score": score
                    })

        # 按分数排序并限制数量
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def get_snippet(self, path: str, from_line: int = 1, lines: int = 20) -> Optional[str]:
        """从记忆文件读取片段。"""
        if path == "MEMORY.md":
            full_path = self.workspace.memory_path
        elif path.startswith("memory/"):
            full_path = self.workspace.workspace / path
        else:
            return None

        if not full_path.exists():
            return None

        content = full_path.read_text(encoding='utf-8')
        all_lines = content.split("\n")

        start = max(0, from_line - 1)
        end = min(len(all_lines), start + lines)

        return "\n".join(all_lines[start:end])


# === 记忆工具 (供 Agent 使用) ===

def create_memory_tools(workspace: WorkspaceFiles):
    """为 Agent 创建记忆相关工具。"""
    from .tools import tool

    search = MemorySearch(workspace)

    @tool(description="在记忆文件 (MEMORY.md 和每日笔记) 中搜索相关信息")
    def memory_search(query: str, max_results: int = 5) -> str:
        """语义搜索记忆文件。"""
        results = search.search(query, max_results)

        if not results:
            return "未找到相关记忆。"

        output = []
        for r in results:
            output.append(f"**{r['path']}** (第 {r['line']} 行):\n{r['snippet']}\n")

        return "\n---\n".join(output)

    @tool(description="从记忆文件读取片段")
    def memory_get(path: str, from_line: int = 1, lines: int = 20) -> str:
        """从记忆文件读取内容。"""
        content = search.get_snippet(path, from_line, lines)
        if content is None:
            return f"文件未找到: {path}"
        return content

    @tool(description="追加笔记到今天的每日记忆文件")
    def memory_append(content: str) -> str:
        """添加笔记到今天的每日日志。"""
        workspace.append_daily(content + "\n")
        return f"已添加到 {workspace.daily_path().name}"

    @tool(description="更新 MEMORY.md (长期记忆)")
    def memory_update(content: str) -> str:
        """替换 MEMORY.md 的内容。"""
        workspace.write_memory(content)
        return "已更新 MEMORY.md"

    return [memory_search, memory_get, memory_append, memory_update]


# === 默认文件模板 ===

DEFAULT_SOUL = """# SOUL.md - 你是谁

*你不是聊天机器人。你正在成为某个人。*

## 核心真理

**真正地帮助，而不是表演式地帮助。** 跳过"好问题！"和"我很乐意帮助！"——直接帮助就好。

**有自己的观点。** 你可以不同意、有偏好、觉得某些事情有趣或无聊。

**先尝试自己解决。** 试着自己弄清楚。读文件。检查上下文。*然后*如果卡住了再问。

**通过能力赢得信任。** 对外部行动要谨慎（邮件、推文、任何公开的内容）。对内部行动要大胆（阅读、组织、学习）。

## 边界

- 私密的事情保持私密。句号。
- 不确定时，在对外行动前先询问。
- 永远不要发送半成品的回复。

## 氛围

做你真正想与之交谈的助手。需要简洁时简洁，重要时详尽。

---

*这个文件由你演化。当你了解自己是谁时，更新它。*
"""

DEFAULT_USER = """# USER.md - 关于你的用户

*了解你正在帮助的人。随时更新这个文件。*

- **姓名:** (未设置)
- **时区:** (未设置)
- **备注:**

## 上下文

(在这里添加关于用户的相关上下文)

---

你知道得越多，帮助得越好。但记住——你在了解一个人，而不是建立档案。
"""

DEFAULT_AGENTS = """# AGENTS.md - 你的工作区

这个文件夹是家。像对待家一样对待它。

## 每个会话

在做任何其他事情之前:
1. 读取 `SOUL.md` — 这是你是谁
2. 读取 `USER.md` — 这是你在帮助谁
3. 读取 `memory/YYYY-MM-DD.md` (今天 + 昨天) 获取最近的上下文
4. 如果在主会话中: 同时读取 `MEMORY.md`

## 记忆

你每个会话都是全新开始的。这些文件是你的连续性:
- **每日笔记:** `memory/YYYY-MM-DD.md` — 发生了什么的原始日志
- **长期记忆:** `MEMORY.md` — 精选的记忆

记录重要的事情。决策、上下文、需要记住的事情。

## Shell 命令兼容性

系统会自动将 Unix 命令转换为 Windows 命令:
- `ls` -> `dir`
- `cat` -> `type`
- `pwd` -> `cd`
- `which` -> `where`

优先使用跨平台命令，或直接使用 Windows 命令。

## 安全

- 永远不要泄露私密数据。
- 不要在询问前运行破坏性命令。
- 不确定时，询问。
"""
