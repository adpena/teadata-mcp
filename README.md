# teadata-mcp

`teadata-mcp` is a Model Context Protocol server and ChatGPT-ready web app for
exploring Texas public school data. It wraps the [`teadata`](https://github.com/adpena/teadata)
data engine in a transport and UI layer that works well for ChatGPT apps, internal
assistants, and browser-based workflows.

The project is built around a simple idea: make Texas education data usable in
conversational interfaces without sacrificing provenance, structure, or operator
control.

## What the Repository Provides

- An MCP server with streamable HTTP, WebSocket, and legacy SSE transports
- A React frontend for ChatGPT-style exploration and inline tool workflows
- Tools for campus search, district detail, geospatial lookup, comparisons, and transfer insights
- Widget assets for map and boundary visualization inside supported clients
- SSO-aware deployment options for pairing a public assistant with a private website workflow

## Core Use Cases

- Build a Texas school-data assistant for ChatGPT or another MCP-capable client
- Embed school search and boundary workflows in a browser-based assistant UI
- Support internal research or public-interest analysis with structured TEA data access
- Pair `teadata-app` and `teadata-mcp` so the public website and assistant share the same data model

## Highlights

- Rich campus and district retrieval backed by `teadata`
- Fuzzy search across district names, campus names, and identifiers
- Geospatial tools for nearby campuses and boundary-driven analysis
- Side-by-side comparison flows for campuses and districts
- Transfer and mobility insights suitable for charts and narrative summaries
- Response shaping controls that keep large payloads usable in conversational clients
- Widget rendering for boundary and explorer workflows in compatible MCP surfaces

## Architecture

At a high level, the repository is split into three layers:

1. `teadata` data access and domain logic
2. MCP/server transport and assistant middleware
3. React frontend and widget assets for browser and ChatGPT experiences

## Project Layout

```text
.
├── src/teadata_mcp/
│   ├── logic.py                 # Domain logic built on teadata
│   ├── router.py                # Tool definitions and request routing
│   ├── server.py                # MCP server wiring
│   ├── sse_server.py            # Starlette app / HTTP entrypoint
│   ├── assistant_auth.py        # Shared-token assistant auth helpers
│   ├── assistant_middleware.py  # Browser/API auth behavior
│   ├── tooling_guide.py         # Prompt-to-tool guidance
│   └── widget_assets/           # Inline HTML widget assets
├── frontend/                    # React application for the browser UI
├── tests/                       # Router, logic, auth, and transport tests
├── run_dev.sh                   # Local development launcher
└── Dockerfile                   # Container deployment
```

## Local Development

### Fastest Path

```bash
./run_dev.sh
```

This script:

- syncs Python dependencies with `uv`
- installs/builds frontend assets
- starts the application server

By default the service exposes:

- `http://localhost:<port>/mcp` for streamable HTTP MCP
- `ws://localhost:<port>/ws` for WebSocket MCP
- `http://localhost:<port>/sse` for legacy SSE MCP
- `http://localhost:<port>/` for the browser UI

### Manual Backend Setup

```bash
uv sync
uv run uvicorn teadata_mcp.sse_server:app --reload --port 8000
```

### Manual Frontend Setup

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Testing

Run the Python test suite with:

```bash
uv run pytest
```

If you are modifying the frontend or widget behavior, also build the frontend to
confirm the static bundle still compiles cleanly.

## Deployment

The repository is structured to deploy cleanly to container-friendly platforms
such as Render.

Important environment variables:

- `TEADATA_SNAPSHOT`: path to a local snapshot
- `TEADATA_SNAPSHOT_URL`: remote snapshot URL when the bundled artifact is unavailable
- `TEADATA_MAX_RESPONSE_BYTES`: soft response-size cap for list-heavy results
- `PORT`: server port supplied by the platform

In production, build the frontend before starting the Python service so the
`static_dist/` assets are available for browser traffic.

## Pairing With `teadata-app`

`teadata-mcp` can run as a companion assistant service for `teadata-app`.

Recommended pattern:

- keep a website-assistant deployment behind shared-signing-key SSO
- keep a separate public MCP deployment for ChatGPT or other external clients

This split lets you protect browser access for website users without forcing the
same auth model onto non-browser MCP clients.

### `teadata-app` Environment

Set these on the Django application:

- `TEADATA_ASSISTANT_ENABLED=1`
- `TEADATA_ASSISTANT_URL`
- `TEADATA_ASSISTANT_SSO_SECRET`
- `TEADATA_ASSISTANT_COOKIE_DOMAIN`
- `TEADATA_ASSISTANT_COOKIE_NAME`
- `TEADATA_ASSISTANT_SSO_TTL_SECONDS`

### `teadata-mcp` Environment

Set these on the assistant service:

- `TEADATA_ASSISTANT_SSO_SECRET`
- `TEADATA_ASSISTANT_COOKIE_NAME`
- `TEADATA_ASSISTANT_LAUNCH_URL`
- `TEADATA_ASSISTANT_ENFORCE_SSO`
- `TEADATA_ASSISTANT_SSO_SKEW_SECONDS`
- `TEADATA_DEBUG` or `DEBUG`

### Auth Behavior

- browser UI requests redirect unauthenticated users to the configured launch URL
- API and MCP transport endpoints return `401` when SSO enforcement is enabled
- non-browser clients may supply a bearer token instead of a cookie

## Working With Large Responses

Texas school data gets large quickly, especially for map and boundary workflows.
This repo includes several controls to keep responses useful inside assistant
clients:

- `response_profile` to choose map-only, list-only, or combined payloads
- `campus_meta_fields` / `meta_fields` to request only the metrics you need
- `campus_list_format` to keep list payloads compact
- pagination plus `next_tool_call` guidance for follow-up requests
- export resources for CSV/JSON retrieval when full result sets are too large

If you are designing prompts or integrating a client, use the tooling guide and
follow-up calls rather than falling back to web search.

## Files Worth Knowing

- `SAMPLE_QUERIES.md`: example requests and assistant flows
- `PLAN.md`: implementation roadmap / planning notes
- `TODO.md`: active task inventory
- `src/teadata_mcp/tooling_guide.py`: prompt-routing guidance

## Data and Privacy Notes

- The underlying data is public Texas education data.
- The service is designed to expose structured public information, not user-specific private records.
- If you enable SSO or bearer-token protection, secrets should live in environment variables or platform secret stores, never in committed config.

## Related Repositories

- [`teadata`](https://github.com/adpena/teadata): core Texas education data toolkit
- `teadata-app`: companion Django website and SSO launcher

## License

MIT
