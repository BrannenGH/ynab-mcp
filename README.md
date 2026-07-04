# ynab-mcp

MCP server exposing Ynab over Streamable HTTP, fronted by a Keycloak-authenticated
jwt-proxy sidecar (see [jwt-proxy](https://github.com/brannengh/jwt-proxy)).

## Setup

1. Create a personal access token at https://app.ynab.com/settings/developer.
2. `cp ynab.env.example ynab.env` and fill in your credentials.
3. `cp .env.example .env` and set `OIDC_ISSUER_URL` to your Keycloak realm.
4. `docker compose up -d --build`

## Verify

```bash
curl -s http://localhost:5090/healthz
curl -i http://localhost:5090/mcp   # should 401 without a bearer token
```

Then add the connector in Claude (Settings -> Connectors -> Add custom
connector) pointing at your public `https://<host>/mcp` URL.
