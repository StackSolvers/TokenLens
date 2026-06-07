# Security Policy

TokenLens reads local agent logs and usage metadata. Please treat any bug that exposes private prompts, local paths, credentials, or logs beyond the user's machine as security-sensitive.

## Reporting

Please report security issues privately to Stack Solvers for IT Solutions before public disclosure.

If no private contact is listed for the repository yet, open a GitHub issue with minimal detail and ask for a secure disclosure channel. Do not include secrets, logs, prompts, or personal data in the issue.

## Scope

In scope:

- Accidental network upload of local logs or prompts.
- Secret leakage through dashboard/API responses.
- Write operations against active agent databases or conversation logs.
- Hook or MCP behavior that can create loops or unbounded output.

Out of scope:

- Token count estimation inaccuracies without a security or privacy impact.
- Issues caused by modified local files outside this repository.
