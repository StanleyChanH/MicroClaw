"""
Session Management - OpenClaw-style

Sessions in MicroClaw mirror OpenClaw's design:
- Session keys: `agent:<agentId>:<key>` for DMs, `agent:<agentId>:<channel>:group:<id>` for groups
- Daily resets: sessions expire at a configurable hour (default 4 AM)
- Idle resets: optional timeout for inactive sessions
- Compaction: summarize old context when nearing token limits
- JSONL transcripts: append-only logs for full history
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# === Message Types ===

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    COMPACTION = "compaction"  # Special: compacted summary


@dataclass
class Message:
    """A single message in a conversation."""
    
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    name: Optional[str] = None  # For tool results
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSONL storage."""
        data = {
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.metadata:
            data["metadata"] = self.metadata
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Deserialize from storage."""
        role = data["role"]
        if isinstance(role, str):
            role = MessageRole(role)
        return cls(
            role=role,
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            metadata=data.get("metadata", {})
        )
    
    def to_openai(self) -> Dict[str, Any]:
        """Convert to OpenAI message format."""
        msg = {"role": self.role.value if isinstance(self.role, MessageRole) else self.role}
        
        # Handle compaction summaries
        if self.role == MessageRole.COMPACTION:
            msg["role"] = "system"
            msg["content"] = f"[Previous conversation summary]\n{self.content}"
            return msg
        
        msg["content"] = self.content
        
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.name:
            msg["name"] = self.name
            
        return msg


# === Session Key Utilities ===

@dataclass
class SessionKey:
    """
    Structured session key following OpenClaw convention.
    
    Format: agent:<agentId>:<type>:<identifier>
    Examples:
        - agent:main:main (primary DM session)
        - agent:main:whatsapp:group:123456 (WhatsApp group)
        - agent:main:dm:+1234567890 (per-peer DM)
        - cron:daily-report (cron job)
    """
    
    raw: str
    agent_id: str = "main"
    session_type: str = "main"  # main, dm, group, channel
    identifier: Optional[str] = None
    channel: Optional[str] = None
    
    @classmethod
    def parse(cls, key: str) -> "SessionKey":
        """Parse a session key string."""
        parts = key.split(":")
        
        if parts[0] == "agent" and len(parts) >= 3:
            agent_id = parts[1]
            
            if len(parts) == 3:
                # agent:main:main
                return cls(raw=key, agent_id=agent_id, session_type=parts[2])
            elif len(parts) == 4:
                # agent:main:dm:user123
                return cls(raw=key, agent_id=agent_id, session_type=parts[2], identifier=parts[3])
            elif len(parts) >= 5:
                # agent:main:whatsapp:group:123
                return cls(
                    raw=key,
                    agent_id=agent_id,
                    channel=parts[2],
                    session_type=parts[3],
                    identifier=":".join(parts[4:])
                )
        
        # Fallback for simple keys
        return cls(raw=key, session_type=key)
    
    @classmethod
    def for_dm(cls, agent_id: str = "main", peer_id: Optional[str] = None, channel: Optional[str] = None) -> "SessionKey":
        """Create a DM session key."""
        if peer_id and channel:
            key = f"agent:{agent_id}:{channel}:dm:{peer_id}"
        elif peer_id:
            key = f"agent:{agent_id}:dm:{peer_id}"
        else:
            key = f"agent:{agent_id}:main"
        return cls.parse(key)
    
    @classmethod
    def for_group(cls, group_id: str, agent_id: str = "main", channel: str = "unknown") -> "SessionKey":
        """Create a group session key."""
        key = f"agent:{agent_id}:{channel}:group:{group_id}"
        return cls.parse(key)
    
    def __str__(self) -> str:
        return self.raw


# === Reset Policy ===

@dataclass
class ResetPolicy:
    """
    Session reset policy (OpenClaw-style).
    
    Modes:
    - daily: Reset at a specific hour each day
    - idle: Reset after N minutes of inactivity
    - both: Whichever triggers first
    """
    
    mode: Literal["daily", "idle", "both"] = "daily"
    at_hour: int = 4  # Hour for daily reset (0-23, local time)
    idle_minutes: Optional[int] = None
    
    def is_expired(self, last_update: datetime, now: Optional[datetime] = None) -> bool:
        """Check if a session should be reset."""
        now = now or datetime.now()
        
        if self.mode in ("daily", "both"):
            # Find the most recent reset time
            reset_today = now.replace(hour=self.at_hour, minute=0, second=0, microsecond=0)
            if now < reset_today:
                reset_today -= timedelta(days=1)
            
            if last_update < reset_today:
                return True
        
        if self.mode in ("idle", "both") and self.idle_minutes:
            idle_threshold = now - timedelta(minutes=self.idle_minutes)
            if last_update < idle_threshold:
                return True
        
        return False


# === Session ===

@dataclass
class Session:
    """
    A conversation session with OpenClaw-style features.
    
    Features:
    - Structured session keys
    - Message history with JSONL persistence
    - Token tracking
    - Compaction support
    - Reset policy
    """
    
    key: SessionKey
    session_id: str  # Unique ID for this session instance
    messages: List[Message] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Token tracking
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    # Compaction
    compaction_count: int = 0
    last_compaction_at: Optional[datetime] = None
    
    # Origin metadata (where this session came from)
    origin: Dict[str, Any] = field(default_factory=dict)
    
    # State (arbitrary session-scoped data)
    state: Dict[str, Any] = field(default_factory=dict)
    
    def add_message(
        self,
        role: MessageRole,
        content: str,
        **kwargs
    ) -> Message:
        """Add a message to the session."""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        return msg
    
    def add_user_message(self, content: str, **metadata) -> Message:
        return self.add_message(MessageRole.USER, content, metadata=metadata)
    
    def add_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> Message:
        return self.add_message(MessageRole.ASSISTANT, content, tool_calls=tool_calls)
    
    def add_tool_result(self, tool_call_id: str, content: str, name: str) -> Message:
        return self.add_message(
            MessageRole.TOOL,
            content,
            tool_call_id=tool_call_id,
            name=name
        )
    
    def get_messages_for_llm(
        self,
        system_prompt: Optional[str] = None,
        max_messages: Optional[int] = None
    ) -> List[Dict]:
        """Get messages formatted for LLM API."""
        result = []
        
        if system_prompt:
            result.append({"role": "system", "content": system_prompt})
        
        messages = self.messages
        if max_messages:
            messages = messages[-max_messages:]
        
        for msg in messages:
            result.append(msg.to_openai())
        
        return result
    
    def update_token_counts(self, input_tokens: int, output_tokens: int):
        """Update token usage tracking."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens = self.input_tokens + self.output_tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session metadata (not messages - those go to JSONL)."""
        return {
            "key": str(self.key),
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "compaction_count": self.compaction_count,
            "last_compaction_at": self.last_compaction_at.isoformat() if self.last_compaction_at else None,
            "origin": self.origin,
            "state": self.state,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], messages: List[Message] = None) -> "Session":
        """Deserialize session."""
        return cls(
            key=SessionKey.parse(data["key"]),
            session_id=data["session_id"],
            messages=messages or [],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            compaction_count=data.get("compaction_count", 0),
            last_compaction_at=datetime.fromisoformat(data["last_compaction_at"]) if data.get("last_compaction_at") else None,
            origin=data.get("origin", {}),
            state=data.get("state", {}),
        )


# === Session Store (JSONL-based, like OpenClaw) ===

class SessionStore:
    """
    OpenClaw-style session storage.
    
    Structure:
    - sessions.json: metadata for all sessions
    - <session_id>.jsonl: message transcript per session
    """
    
    def __init__(self, storage_dir: str, reset_policy: Optional[ResetPolicy] = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.reset_policy = reset_policy or ResetPolicy()
        
        # In-memory cache
        self._sessions: Dict[str, Session] = {}
        self._metadata: Dict[str, Dict] = {}
        
        # Load existing sessions
        self._load_metadata()
    
    @property
    def _metadata_path(self) -> Path:
        return self.storage_dir / "sessions.json"
    
    def _transcript_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.jsonl"
    
    def _load_metadata(self):
        """Load session metadata from sessions.json."""
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, 'r') as f:
                    self._metadata = json.load(f)
            except Exception:
                self._metadata = {}
    
    def _save_metadata(self):
        """Save session metadata to sessions.json."""
        with open(self._metadata_path, 'w') as f:
            json.dump(self._metadata, f, indent=2)
    
    def _load_transcript(self, session_id: str) -> List[Message]:
        """Load messages from JSONL transcript."""
        messages = []
        path = self._transcript_path(session_id)
        
        if path.exists():
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            messages.append(Message.from_dict(data))
                        except Exception:
                            pass
        
        return messages
    
    def _append_to_transcript(self, session_id: str, message: Message):
        """Append a message to the JSONL transcript."""
        path = self._transcript_path(session_id)
        with open(path, 'a') as f:
            f.write(json.dumps(message.to_dict()) + "\n")
    
    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        import uuid
        return uuid.uuid4().hex[:12]
    
    def get(self, key: str | SessionKey) -> Session:
        """
        Get or create a session.
        
        Handles:
        - Session expiry (daily/idle reset)
        - Loading from disk
        - Creating new sessions
        """
        if isinstance(key, str):
            key = SessionKey.parse(key)
        
        key_str = str(key)
        
        # Check if session exists and is still valid
        if key_str in self._metadata:
            meta = self._metadata[key_str]
            updated_at = datetime.fromisoformat(meta["updated_at"])
            
            if self.reset_policy.is_expired(updated_at):
                # Session expired - create a new one
                return self._create_session(key)
            
            # Load from cache or disk
            if key_str not in self._sessions:
                messages = self._load_transcript(meta["session_id"])
                self._sessions[key_str] = Session.from_dict(meta, messages)
            
            return self._sessions[key_str]
        
        # Create new session
        return self._create_session(key)
    
    def _create_session(self, key: SessionKey) -> Session:
        """Create a new session."""
        session_id = self._generate_session_id()
        session = Session(key=key, session_id=session_id)
        
        key_str = str(key)
        self._sessions[key_str] = session
        self._metadata[key_str] = session.to_dict()
        self._save_metadata()
        
        return session
    
    def save(self, session: Session, message: Optional[Message] = None):
        """
        Save session state.
        
        If a message is provided, append it to the transcript.
        Always updates metadata.
        """
        key_str = str(session.key)
        
        if message:
            self._append_to_transcript(session.session_id, message)
        
        self._metadata[key_str] = session.to_dict()
        self._save_metadata()
    
    def reset(self, key: str | SessionKey) -> Session:
        """Force reset a session (like /new or /reset)."""
        if isinstance(key, str):
            key = SessionKey.parse(key)
        return self._create_session(key)
    
    def list(self, active_minutes: Optional[int] = None) -> List[Dict]:
        """List all sessions, optionally filtered by activity."""
        now = datetime.now()
        results = []
        
        for key, meta in self._metadata.items():
            updated_at = datetime.fromisoformat(meta["updated_at"])
            
            if active_minutes:
                threshold = now - timedelta(minutes=active_minutes)
                if updated_at < threshold:
                    continue
            
            results.append({
                "key": key,
                "session_id": meta["session_id"],
                "updated_at": meta["updated_at"],
                "total_tokens": meta.get("total_tokens", 0),
            })
        
        return sorted(results, key=lambda x: x["updated_at"], reverse=True)
    
    def delete(self, key: str | SessionKey) -> bool:
        """Delete a session."""
        if isinstance(key, str):
            key = SessionKey.parse(key)
        
        key_str = str(key)
        
        if key_str in self._metadata:
            session_id = self._metadata[key_str]["session_id"]
            
            # Remove transcript
            transcript = self._transcript_path(session_id)
            if transcript.exists():
                transcript.unlink()
            
            # Remove from metadata
            del self._metadata[key_str]
            self._save_metadata()
            
            # Remove from cache
            if key_str in self._sessions:
                del self._sessions[key_str]
            
            return True
        
        return False


# === Compaction ===

class Compactor:
    """
    Handles session compaction (summarizing old context).
    
    When a session nears the context window limit, the compactor:
    1. Takes older messages
    2. Summarizes them via LLM
    3. Replaces them with a compaction message
    """
    
    def __init__(
        self,
        summarize_fn,  # Callable that takes messages and returns summary
        reserve_tokens: int = 20000,
        soft_threshold: int = 4000,
    ):
        self.summarize_fn = summarize_fn
        self.reserve_tokens = reserve_tokens
        self.soft_threshold = soft_threshold
    
    def should_compact(self, session: Session, context_window: int, current_tokens: int) -> bool:
        """Check if compaction is needed."""
        available = context_window - self.reserve_tokens - self.soft_threshold
        return current_tokens > available
    
    async def compact(
        self,
        session: Session,
        keep_recent: int = 10,
        instructions: Optional[str] = None
    ) -> str:
        """
        Compact a session's history.
        
        Returns the summary text.
        """
        if len(session.messages) <= keep_recent:
            return ""
        
        # Split messages
        to_summarize = session.messages[:-keep_recent]
        to_keep = session.messages[-keep_recent:]
        
        # Generate summary
        summary = await self.summarize_fn(to_summarize, instructions)
        
        # Create compaction message
        compaction_msg = Message(
            role=MessageRole.COMPACTION,
            content=summary,
            metadata={"compacted_count": len(to_summarize)}
        )
        
        # Replace messages
        session.messages = [compaction_msg] + to_keep
        session.compaction_count += 1
        session.last_compaction_at = datetime.now()
        
        return summary
