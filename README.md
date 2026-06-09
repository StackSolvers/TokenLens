<p align="center">
  <img src="StackSolvers.png" alt="Stack Solvers for IT Solutions" width="160">
</p>

# TokenLens

TokenLens is a local, privacy-first dashboard and MCP server for understanding how AI agents spend tokens across projects, sessions, and chats.

Produced by Stack Solvers for IT Solutions.

Use it when you want a clear answer to:

- How many active tokens did the current agent session use?
- Which projects, chats, and models are driving usage?
- What happened in the last 5 hours, 24 hours, 7 days, and 30 days?

## Features

- Multi-agent usage tracking for Antigravity, Claude Code, Codex, and Cline.
- Breakdowns by agent, project, session, and individual chat/model call.
- Read-only collectors for local logs and SQLite databases.
- Agent-scoped MCP and CLI summaries designed for low-latency footer updates.
- Interactive local dashboard with active rolling usage cards and charts.
- Local dashboard served on `127.0.0.1`.
- No telemetry, uploads, or remote calls.

## Supported Sources

- Antigravity: `~/.gemini/antigravity` and `~/.gemini/antigravity-ide`.
- Claude Code: `~/.claude/projects/**/*.jsonl`.
- Codex: `~/.codex/sessions/**/*.jsonl`.
- Cline: VS Code/Cursor global storage task records when token fields are present.

If a local task is detected but does not expose token fields, TokenLens reports it as unmetered instead of inventing counts.

## Requirements

- Python 3.9 or newer.
- A modern browser for the dashboard.
- Node.js is optional and only used for `node --check app.js` during verification.

No Python package installation is required.

## Quick Start

### AI Agent Prompt

Copy this into your AI coding agent:

```text
Set up TokenLens for this workspace: clone https://github.com/StackSolvers/TokenLens.git if needed. Run `python <TokenLens>/cli.py --install-rules --workspace . --compact`. If this agent supports MCP, register `python <TokenLens>/mcp_server.py --agent current` as `tokenlens` (Antigravity shortcut: `python <TokenLens>/cli.py --install-antigravity-mcp`). After each turn, prefer `get_token_summary` and append only its one-line result. Do not ask for shell approval every turn just to run TokenLens. Keep it local; add no telemetry.
```

### Manual Setup

```powershell
git clone https://github.com/StackSolvers/TokenLens.git
cd TokenLens
python cli.py --compact
python cli.py --install-antigravity-mcp
python server.py
```

The server opens the dashboard locally by default. It starts at `http://127.0.0.1:8080` and falls back to the next free port if needed.

## Dashboard

```powershell
python server.py
python server.py --no-browser
```

The dashboard keeps tables global by default while the rolling cards start focused on the latest active agent and latest known project. After you touch any filter, the rolling cards follow the current agent/project/date filters. Active usage excludes cached reads so repeated context cache does not look like fresh token burn. Charts are local and interactive; hover points and slices to inspect values.

Click an agent row to browse that agent's projects. Click a project row to browse that project's chats.

## Active Vs Raw Tokens

TokenLens keeps both raw and active token totals:

- Active tokens are the default for the dashboard, CLI footer, and MCP summary.
- Cached reads are tracked separately and excluded from active totals.
- Raw totals remain available in JSON output for audit and debugging.
- Cache writes are included in active usage because they represent newly written context.

This keeps long-context agents from looking far more expensive than they are when most of the logged usage is cached context replay.

## CLI

```powershell
python cli.py
python cli.py --compact
python cli.py --verbose
python cli.py --json
python cli.py --compact --json
python cli.py --compact --agent antigravity
python cli.py --compact --agent current
```

Example compact output:

```text
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

`python cli.py` defaults to the compact one-line output. Use `--verbose` for the multi-line human summary. Use `--compact --json` for a tiny structured payload suitable for agents. Use `--agent current` for auto-detection, or `--agent antigravity`, `--agent codex`, `--agent claude_code`, or `--agent cline` to limit collection to one agent.

## MCP Tool

For any MCP client, register TokenLens as a stdio server:

```powershell
python cli.py --print-mcp-snippet json
python cli.py --print-mcp-snippet toml
```

The server command inside the snippet is:

```powershell
python mcp_server.py --agent current
```

For JSON MCP configs that use `mcpServers`, TokenLens can merge the entry when you pass the config path:

```powershell
python cli.py --install-mcp-json --mcp-config C:\path\to\mcp_config.json --mcp-agent current
```

For Antigravity, there is also a one-command shortcut:

```powershell
python cli.py --install-antigravity-mcp
```

Restart Antigravity after installing or updating MCP configuration. Then call:

```text
get_token_summary
```

The generic MCP snippet defaults to `--agent current`. The Antigravity shortcut defaults to `--agent antigravity`. The tool returns one compact line, uses in-process file caching while the MCP server is alive, and does not trigger other tools. It accepts `{"format":"json"}` for minimal structured output, `{"agent":"codex"}` or another supported agent id for a specific agent, or `{"agent":"all"}` when you explicitly want a cross-agent summary.

## Agent Coverage

TokenLens currently has built-in collectors for local usage data exposed by:

| Agent | Footer filter | Data source |
| --- | --- | --- |
| Antigravity | `--agent antigravity` | Local Antigravity conversation SQLite/protobuf files |
| Codex | `--agent codex` | Local Codex session JSONL files |
| Claude Code | `--agent claude_code` | Local Claude Code project JSONL files |
| Cline/Roo/Kilo-style tasks | `--agent cline` | Local VS Code/Cursor task records when token fields are present |

Other agents can use TokenLens through the same MCP server if they can call MCP tools. TokenLens can only calculate usage for agents that expose local token usage logs or databases; it does not call provider APIs or estimate hidden usage from message text. New agents should be added as explicit collectors so their numbers stay auditable.

## Use With AI Agents

TokenLens is designed to give agents a tiny, useful footer without flooding the conversation. Install the workspace guidance:

```powershell
python cli.py --install-rules --workspace . --compact
```

Run the command from the project you want the agent to work in, or pass an absolute path after `--workspace`. This adds a short TokenLens instruction to common agent rule files in that workspace, including `.airules`, `.cursorrules`, `.clinerules`, `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`. The instruction tells the agent to prefer the MCP tool, use `--agent current` for shell fallback, avoid repeated shell approval prompts, and append only the one-line result:

```text
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

The compact footer reports active tokens. Cached reads are tracked separately in the dashboard and JSON output, but excluded from the footer so context-cache replay does not look like fresh burn. The `5h` and `24h` values are rolling local estimates for the current/latest agent. They are not provider-confirmed remaining allowance.

The dashboard is for human inspection. Agents should use the MCP tool for turn summaries when available. The CLI is a fallback for manual use or already-approved shell contexts, not something an agent should ask to run every turn.

Agents working inside this repository can also follow [AGENTS.md](AGENTS.md), which contains the same compact, low-noise operating rule.

## Optional Hook

Add this to Antigravity hook configuration if you want a post-turn hook:

```json
{
  "PostTurn": [
    "python C:\\path\\to\\TokenLens\\hook.py"
  ]
}
```

The hook is silent by default and returns:

```json
{"decision":"allow"}
```

To print the compact summary to stderr:

```powershell
$env:TOKENLENS_HOOK_VERBOSE = "1"
```

## Privacy And Safety

- TokenLens reads local files only.
- SQLite connections use read-only mode.
- The dashboard binds to `127.0.0.1`.
- TokenLens reports token usage only.

## Config

```json
{
  "agents": {
    "antigravity": true,
    "claude_code": true,
    "codex": true,
    "cline": true
  },
  "agent_dirs": {
    "antigravity": [],
    "claude_code": [],
    "codex": [],
    "cline": []
  }
}
```

`agent_dirs` can add extra local roots. Default roots are still auto-detected.

TokenLens does not silently query provider servers for real remaining allowance. It reports local rolling usage windows instead.

## Verification

```powershell
python -m unittest discover -s tests
python -m py_compile tokenlens_core.py cli.py server.py mcp_server.py hook.py
node --check app.js
```

## License

TokenLens is released under the MIT License. See [LICENSE](LICENSE).
