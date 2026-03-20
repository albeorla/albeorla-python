# claude-cli-bridge

Async Python wrapper for the [Claude Code](https://claude.ai/code) CLI with automatic session management.

## Install

```bash
pip install claude-cli-bridge
```

Requires the `claude` CLI to be installed and authenticated.

## Usage

```python
import asyncio
from claude_cli_bridge import ClaudeBridge

async def main():
    bridge = ClaudeBridge(work_dir="~/my-project")

    # First call creates a new session
    resp = await bridge.query(key="chat-1", message="explain this codebase")
    print(resp.text)

    # Follow-up resumes the same session automatically
    resp = await bridge.query(key="chat-1", message="now refactor the main module")
    print(resp.text)

    # One-shot (no session tracking)
    resp = await bridge.ask("what is 2 + 2?")
    print(resp.text)

asyncio.run(main())
```

## API

### `ClaudeBridge`

```python
ClaudeBridge(
    claude_binary="claude",       # path to claude CLI
    work_dir=".",                 # working directory for subprocess
    system_prompt=None,           # appended on first turn
    permission_mode="bypassPermissions",
    model=None,                   # e.g., "haiku", "sonnet"
    allowed_tools=None,           # e.g., ["Read", "WebSearch"]
)
```

### Methods

| Method | Description |
|--------|-------------|
| `await bridge.query(key, message)` | Send a message to a session. Creates one if needed, resumes on follow-up. |
| `await bridge.ask(message)` | One-shot query, no session reuse. |
| `bridge.get_session(key)` | Get session by key, or `None`. |
| `bridge.create_session(key)` | Explicitly create a session. |
| `bridge.remove_session(key)` | Remove a session. |
| `bridge.active_sessions` | Dict of all active sessions. |

### `Response`

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | The assistant's reply |
| `session_id` | `str` | Claude session ID |
| `cost_usd` | `float` | Cost of the query |
| `duration_ms` | `int` | Wall-clock time |
| `num_turns` | `int` | Number of agent turns |
| `is_error` | `bool` | Whether the query failed |
| `raw` | `dict` | Full JSON response from the CLI |

### `Session`

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | `str` | UUID for the Claude CLI session |
| `key` | `Any` | Application-defined identifier |
| `turn_count` | `int` | Messages sent in this session |
| `busy` | `bool` | Whether a query is in progress |
