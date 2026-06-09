# TokenLens Agent Notes

TokenLens summarizes local AI agent token usage across Antigravity, Claude Code, Codex, and Cline.

Produced by Stack Solvers for IT Solutions.

When working in this repository, use TokenLens itself to keep token usage visible without adding noise.

At the end of an assistant turn, append one compact TokenLens footer only when it can be retrieved without interrupting the user.

Preferred MCP tool:

```text
get_token_summary
```

Shell fallback only when shell execution is already permitted:

```powershell
python cli.py --compact --agent current
```

Append only the returned one-line footer. Do not explain it unless the user asks. Never run plain `python cli.py` for the footer, and never ask for shell approval every turn just to run TokenLens.

Expected format:

```text
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

Rules:

- Prefer MCP over shell.
- Run at most one check per turn, at the end.
- Keep the footer as one line.
- If MCP is unavailable and shell would require approval, skip the footer and suggest one-time MCP setup.
- Treat footer numbers as active tokens; cached reads are tracked separately but excluded from the footer.
- Treat `5h` and `24h` as local rolling estimates, not provider-confirmed remaining allowance.
- The dashboard may be opened for setup or human inspection, but never use dashboard output for routine turn summaries.
- Do not call external model APIs for metering.
