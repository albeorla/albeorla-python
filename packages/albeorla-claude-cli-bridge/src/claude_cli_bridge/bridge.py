"""Async bridge to the Claude Code CLI via subprocesses."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from hashlib import md5
from typing import Any

from albeorla_logging import get_logger

log = get_logger(__name__)


@dataclass
class Session:
    """Tracks a multi-turn Claude CLI session.

    Each session maps to a single ``claude`` session on disk, identified by
    :pyattr:`session_id`.  The *key* is an application-defined identifier
    (e.g., a Discord thread ID, a chat window ID, a ticket number) that lets
    the caller look up the session later.
    """

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: Any = None
    turn_count: int = 0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_active: float = field(default_factory=time.monotonic)


@dataclass
class Response:
    """Result from a single Claude CLI query."""

    text: str
    session_id: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    is_error: bool = False
    raw: dict = field(default_factory=dict)


class ClaudeBridge:
    """Manage Claude Code CLI sessions as async subprocesses.

    Example::

        bridge = ClaudeBridge(work_dir="~/my-project")

        # First message creates a new session
        resp = await bridge.query(key="chat-1", message="explain this code")

        # Follow-up resumes the same session automatically
        resp = await bridge.query(key="chat-1", message="now refactor it")

    Parameters
    ----------
    claude_binary:
        Path or name of the ``claude`` executable.
    work_dir:
        Working directory for the CLI subprocess.
    system_prompt:
        Optional system prompt appended on the first turn of each session.
    permission_mode:
        Permission mode passed to ``claude``.  Defaults to
        ``"bypassPermissions"`` for headless operation.
    model:
        Model override (e.g., ``"haiku"``, ``"sonnet"``).  If *None* the CLI
        default is used.
    allowed_tools:
        Restrict available tools (e.g., ``["Read", "WebSearch"]``).  If
        *None* all tools are available.
    query_timeout:
        Maximum seconds to wait for a single CLI query before killing the
        process.  Defaults to 300 (5 minutes).
    max_concurrent:
        Maximum number of concurrent subprocess queries across all sessions.
    """

    def __init__(
        self,
        *,
        claude_binary: str = "claude",
        work_dir: str = ".",
        system_prompt: str | None = None,
        permission_mode: str = "bypassPermissions",
        model: str | None = None,
        allowed_tools: list[str] | None = None,
        query_timeout: float = 300,
        max_concurrent: int = 5,
    ):
        self._binary = claude_binary
        self._work_dir = work_dir
        self._system_prompt = system_prompt
        self._permission_mode = permission_mode
        self._model = model
        self._allowed_tools = allowed_tools
        self._query_timeout = query_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._sessions: dict[Any, Session] = {}

    # -- Session management --------------------------------------------------

    def get_session(self, key: Any) -> Session | None:
        """Return the session for *key*, or *None*."""
        return self._sessions.get(key)

    def create_session(self, key: Any) -> Session:
        """Create and register a fresh session for *key*."""
        session = Session(key=key)
        self._sessions[key] = session
        log.info("session_created", key=key, session_id=session.session_id)
        return session

    def remove_session(self, key: Any) -> None:
        """Remove the session for *key* if it exists."""
        removed = self._sessions.pop(key, None)
        if removed:
            log.info("session_removed", key=key, session_id=removed.session_id)

    @property
    def active_sessions(self) -> dict[Any, Session]:
        """Return a shallow copy of the active sessions dict."""
        return dict(self._sessions)

    def cleanup_stale_sessions(self, max_age_seconds: float = 7200) -> int:
        """Remove sessions that have been idle longer than *max_age_seconds*.

        Returns the number of sessions removed.
        """
        now = time.monotonic()
        stale_keys = [
            key
            for key, session in self._sessions.items()
            if (now - session.last_active) > max_age_seconds
        ]
        for key in stale_keys:
            self.remove_session(key)
        if stale_keys:
            log.info("stale_sessions_cleaned", count=len(stale_keys))
        return len(stale_keys)

    # -- Query ---------------------------------------------------------------

    def _build_cmd(self, message: str, session: Session) -> list[str]:
        cmd = [
            self._binary,
            "-p",
            "--output-format",
            "json",
            "--permission-mode",
            self._permission_mode,
        ]

        if session.turn_count == 0:
            cmd.extend(["--session-id", session.session_id])
        else:
            cmd.extend(["-r", session.session_id])

        if self._model:
            cmd.extend(["--model", self._model])

        if self._allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self._allowed_tools)])

        if self._system_prompt and session.turn_count == 0:
            cmd.extend(["--append-system-prompt", self._system_prompt])

        cmd.append(message)
        return cmd

    async def query(self, key: Any, message: str) -> Response:
        """Send *message* to the session identified by *key*.

        If no session exists for *key*, one is created automatically.
        Follow-up calls with the same *key* resume the conversation.

        Returns a :class:`Response` with the assistant's reply text and
        metadata.
        """
        session = self._sessions.get(key)
        if not session:
            session = self.create_session(key)

        async with session.lock:
            cmd = self._build_cmd(message, session)
            log.info(
                "query_start",
                key=key,
                session_id=session.session_id,
                turn=session.turn_count,
                message_preview=message[:100],
            )

            try:
                async with self._semaphore:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=self._work_dir,
                    )

                    try:
                        stdout_bytes, stderr_bytes = await asyncio.wait_for(
                            proc.communicate(), timeout=self._query_timeout
                        )
                    except TimeoutError:
                        proc.kill()
                        await proc.wait()
                        log.error(
                            "query_timeout",
                            key=key,
                            session_id=session.session_id,
                            timeout=self._query_timeout,
                        )
                        return Response(
                            text=f"Query timed out after {self._query_timeout}s.",
                            is_error=True,
                        )

                stdout_text = stdout_bytes.decode(errors="replace").strip()
                stderr_text = stderr_bytes.decode(errors="replace").strip()

                if proc.returncode != 0:
                    log.error(
                        "process_error",
                        returncode=proc.returncode,
                        stderr=stderr_text[:500],
                        session_id=session.session_id,
                    )
                    return Response(
                        text=stderr_text or "Claude CLI returned a non-zero exit code.",
                        is_error=True,
                    )

                try:
                    data = json.loads(stdout_text)
                except json.JSONDecodeError:
                    log.error("json_parse_error", stdout=stdout_text[:500])
                    return Response(text=stdout_text or "No response.", is_error=True)

                # Extract result text — can be a string or a list of content blocks
                result_text = ""
                result_content = data.get("result", "")
                if isinstance(result_content, str):
                    result_text = result_content
                elif isinstance(result_content, list):
                    for block in result_content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            result_text += block.get("text", "")
                else:
                    log.warning(
                        "unexpected_result_type",
                        result_type=type(result_content).__name__,
                        session_id=session.session_id,
                    )

                session_id = data.get("session_id", session.session_id)
                session.session_id = session_id
                session.turn_count += 1
                session.last_active = time.monotonic()

                response = Response(
                    text=result_text or "",
                    session_id=session_id,
                    cost_usd=data.get("total_cost_usd", 0.0),
                    duration_ms=data.get("duration_ms", 0),
                    num_turns=data.get("num_turns", 0),
                    raw=data,
                )

                log.info(
                    "query_complete",
                    key=key,
                    session_id=session_id,
                    turn=session.turn_count,
                    duration_ms=response.duration_ms,
                    cost_usd=response.cost_usd,
                    response_length=len(response.text),
                )

                return response

            except Exception:
                log.exception("query_failed", key=key)
                return Response(text="Query failed unexpectedly.", is_error=True)

    # -- One-shot convenience ------------------------------------------------

    async def ask(self, message: str, **kwargs: Any) -> Response:
        """One-shot query with no session tracking.

        Creates a unique key internally so the session is not reused.
        Accepts the same keyword arguments as :meth:`query` (currently none,
        reserved for future use).
        """
        key = md5(f"{message}{uuid.uuid4()}".encode()).hexdigest()
        response = await self.query(key=key, message=message)
        self.remove_session(key)
        return response
