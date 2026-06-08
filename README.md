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
- Compact MCP and CLI summaries designed for agent-safe footer updates.
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
Set up TokenLens for this workspace: clone https://github.com/StackSolvers/TokenLens.git if needed. From this workspace, run `python <TokenLens>/cli.py --compact`, then `python <TokenLens>/cli.py --install-rules --workspace .`. You may open the dashboard for setup or inspection, but after each turn append the compact CLI/MCP TokenLens line, not dashboard output. Keep it local; add no telemetry.
```

### Manual Setup

```powershell
git clone https://github.com/StackSolvers/TokenLens.git
cd TokenLens
python cli.py --compact
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
python cli.py --json
```

Example compact output:

```text
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

## MCP Tool

Configure `mcp_server.py` as a stdio MCP server and call:

```text
get_token_summary
```

The tool returns one compact line and does not trigger other tools.

## Use With AI Agents

TokenLens is designed to give agents a tiny, useful footer without flooding the conversation. Install the workspace guidance:

```powershell
python cli.py --install-rules --workspace .
```

Run the command from the project you want the agent to work in, or pass an absolute path after `--workspace`. This adds a short TokenLens instruction to common agent rule files in that workspace, including `.airules`, `.cursorrules`, `.clinerules`, `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md`. The instruction tells the agent to run the compact check exactly once at the end of each turn and append only the one-line result:

```text
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

The compact footer reports active tokens. Cached reads are tracked separately in the dashboard and JSON output, but excluded from the footer so context-cache replay does not look like fresh burn. The `5h` and `24h` values are rolling local estimates for the current/latest agent. They are not provider-confirmed remaining allowance.

The dashboard is for human inspection. Agents should use the compact CLI or MCP tool for turn summaries, not the dashboard after each chat.

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
