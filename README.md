# ynab-mcp

MCP server exposing YNAB over Streamable HTTP.

## Setup

1. Create a personal access token at https://app.ynab.com/settings/developer.
2. `cp ynab.env.example ynab.env` and fill in your credentials.
3. `docker compose up -d --build`

## Verify

```bash
curl -s http://localhost:5090/healthz
```

This server has no built-in authentication. If you expose it beyond
localhost, put it behind your own auth layer (reverse proxy, VPN, etc.)
before pointing an MCP client at it.
