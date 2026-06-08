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
TokenLens | Codex | active | session 2.5M | last 4.8k | 5h 418.1k | 24h 2.5M | estimated
```

If the MCP server is configured, the equivalent tool is:

```text
get_token_summary
```

Rules:

- Run the check once per turn, at the end.
- Keep the footer as one line.
- Treat footer numbers as active tokens; cached reads are tracked separately but excluded from the footer.
- Treat `5h` and `24h` as local rolling estimates, not provider-confirmed remaining allowance.
- The dashboard may be opened for setup or human inspection, but never use dashboard output for routine turn summaries.
- Do not call external model APIs for metering.
