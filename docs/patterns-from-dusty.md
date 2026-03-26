# Patterns from Dusty (Discord Bot)

Extracted 2026-03-26 before archiving the `dusty` repo. These are patterns worth
extending into `albeorla-python` packages.

## Package: `albeorla-discord-bot` (candidate)

A reusable Discord bot framework that wraps `discord.py` with the same patterns
used in Dusty. Not yet extracted — patterns documented here for future reference.

### Config (Pydantic + YAML + env var substitution)

```python
# Pattern: YAML config with ${ENV_VAR} substitution and Pydantic validation
class ChannelConfig(BaseModel):
    channel_id: int
    allowed_users: list[int] = Field(default_factory=list)
    require_mention: bool = True

class Config(BaseModel):
    bot_token: str
    guild_id: int
    channels: list[ChannelConfig] = Field(default_factory=list)
    allowed_users: list[int] = Field(default_factory=list)
    work_dir: str = "~/dev/areas/finances"
    claude_binary: str = "claude"
    system_prompt: str | None = None
    # Timeouts
    title_timeout: int = 10
    query_timeout: float = 300
    max_concurrent: int = 5
    max_response_length: int = 1900

    @field_validator("bot_token")
    @classmethod
    def bot_token_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("bot_token must not be empty")
        return v

def load_config(path: Path) -> Config:
    """Load YAML, substitute ${ENV_VARS}, validate with Pydantic."""
    text = path.read_text()
    env_vars = set(re.findall(r"\$\{(\w+)\}", text))
    missing = [var for var in env_vars if not os.environ.get(var)]
    if missing:
        raise RuntimeError(f"Required env vars not set: {', '.join(sorted(missing))}")
    for var in env_vars:
        text = text.replace(f"${{{var}}}", os.environ[var])
    return Config(**yaml.safe_load(text))
```

### Bot patterns

- **Thread-per-conversation**: @mention creates a thread, replies in that thread continue the session
- **Channel-level + global ACLs**: `is_allowed_in_channel()` checks global list first, then per-channel
- **Message chunking**: `chunk_text()` splits on newlines, then spaces, then hard-cuts at Discord's 1900 char limit
- **Retry on Discord API**: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))` via tenacity
- **Input truncation**: cap user messages at 16k chars before sending to Claude
- **Title generation**: quick Claude call with `--model haiku --no-session-persistence` to auto-name threads
- **Graceful shutdown**: `on_close()` cleans up all stale bridge sessions
- **Binary validation at startup**: `shutil.which(config.claude_binary)` before accepting any messages

### CLI (Typer)

```python
app = typer.Typer(name="dusty", help="Discord AI assistant powered by Claude Code CLI.")

@app.command()
def run(config_path: Path, json_logs: bool = False, debug: bool = False):
    configure_logging(json_output=json_logs, level=logging.DEBUG if debug else logging.INFO)
    config = load_config(config_path)
    if not shutil.which(config.claude_binary):
        raise typer.Exit(code=1)
    bot = create_bot(config)
    bot.run(config.bot_token, log_handler=None)  # structlog handles logging
```

### Dependencies used

| Package | Purpose |
|---------|---------|
| `discord.py>=2.4.0` | Discord API |
| `typer>=0.15.0` | CLI framework |
| `albeorla-logging>=0.1.0` | Structured logging (structlog) |
| `albeorla-claude-cli-bridge>=0.2.0` | Claude subprocess management |
| `tenacity>=9.0.0` | Retry with exponential backoff |
| `pyyaml>=6.0` | Config loading |
| `pydantic>=2.0` | Config validation |

### Tech debt resolved before archival

All critical + high items from the tech debt review were resolved in the final
3 commits (channel auth, retries, input limits, graceful shutdown, config
validation, binary check at startup). See `docs/TECH_DEBT.md` in the dusty repo
for the full list.

## Package: `albeorla-claude-cli-bridge` (already extracted)

Already lives in this monorepo at `packages/albeorla-claude-cli-bridge/`. Dusty
used it via re-export:

```python
from claude_cli_bridge import ClaudeBridge, Response, Session
```

Key features: async subprocess management, session keying by channel/thread ID,
concurrent process limiting via `asyncio.Semaphore`, stale session cleanup.
