# Contributing To TokenLens

Thanks for helping improve TokenLens.

## Development

```powershell
python -m unittest discover -s tests
python -m py_compile tokenlens_core.py cli.py server.py mcp_server.py hook.py
node --check app.js
```

TokenLens has no required Python dependencies. Keep new dependencies optional unless they are clearly necessary.

## Guidelines

- Keep collectors read-only.
- Do not add hidden LLM API calls or telemetry.
- Keep MCP and hook output compact.
- Do not invent token usage when a local source does not expose usage fields.
- Avoid committing local logs, generated files, secrets, or machine-specific paths.

## Pull Requests

Please include:

- What changed.
- Which agent source was affected.
- How you verified it.
