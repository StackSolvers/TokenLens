# TokenLens Agent Notes

TokenLens summarizes local AI agent token usage across Antigravity, Claude Code, Codex, and Cline.

Produced by Stack Solvers for IT Solutions.

When working in this repository, use TokenLens itself to keep token usage visible without adding noise.

At the end of every assistant turn, run exactly one compact check:

```powershell
python cli.py --compact
```

Append only the returned one-line footer. Do not explain it unless the user asks.

Expected format:

```text
TokenLens | Codex | session 12.4M | last 135.2k | 5h 48.6M | 24h 210.4M | estimated
```

If the MCP server is configured, the equivalent tool is:

```text
get_token_summary
```

Rules:

- Run the check once per turn, at the end.
- Keep the footer as one line.
- Treat `5h` and `24h` as local rolling estimates, not provider-confirmed remaining allowance.
- The dashboard may be opened for setup or human inspection, but never use dashboard output for routine turn summaries.
- Do not call external model APIs for metering.
