# TEA Data MCP Server

This repository contains a Model Context Protocol (MCP) server that exposes the `teadata` library, providing rich data on Texas schools (districts, campuses, demographics, staffing, etc.). It is designed to work as a backend for ChatGPT applications.

## ChatGPT App Alignment

This application is designed to align with OpenAI's requirements for high-quality ChatGPT Apps:

*   **Focused Functionality**: It provides a specific, high-value service—accessing and analyzing Texas public education data—rather than a broad, undefined set of tools.
*   **Native Experience**: The frontend uses the official `@openai/apps-sdk-ui` to ensure the interface feels like a natural extension of ChatGPT.
*   **Transparency**: The application relies on public datasets from the Texas Education Agency (TEA) and does not store or process personal user data.
*   **Production Ready**: It includes a robust deployment pipeline (Dockerfile, multi-stage builds) for reliable hosting on platforms like Render.

**Powered by [Data for Public Education](https://dataforpubliceducation.com)**

This MCP server exposes the same powerful data engine that drives the [Data for Public Education](https://dataforpubliceducation.com) website, a comprehensive resource for exploring Texas school data.

## Features

- **Rich Data Retrieval**: Get detailed stats on enrollment, ratings, staffing (salaries, experience), and class sizes.
- **Search**: Fuzzy search for campuses by name, number, or district.
- **Geospatial**: Find schools near a location or another school.
- **Comparisons**: Side-by-side metric comparison of multiple campuses.
- **Transfer Insights**: Sankey-ready flows, charter share, rating shifts, and neighborhood retention patterns.
- **ChatGPT UI**: Includes a React frontend using OpenAI's `apps-sdk-ui` for a native-feeling experience.
- **Boundary Widgets**: Boundary tools return an Apps SDK widget (map + table) for inline results in ChatGPT.
- **Explorer Widget**: Search, campus detail, district detail, nearby, and comparison tools render inline UI in ChatGPT.
- **Tooling Guide**: A built-in prompt-to-tool guide (`get_tooling_guide`) that helps ChatGPT choose the right tool for map, boundary, and spatial queries.

## Quick Start (Local Development)

The easiest way to run the server and frontend locally is with the included script:

```bash
./run_dev.sh
```

This will:
1.  Install frontend dependencies and build the React app.
2.  Sync Python dependencies using `uv`.
3.  Start the `uvicorn` server (default port `8000`; auto-selects the next available port if in use).

The server exposes:
- **MCP SSE Endpoint**: `http://localhost:<port>/sse`
- **Messages Endpoint**: `http://localhost:<port>/messages`
- **Frontend UI**: `http://localhost:<port>/`

## Manual Setup

### Backend

This project uses [`uv`](https://docs.astral.sh/uv/) for Python package management.

```bash
uv sync
uv run uvicorn teadata_mcp.sse_server:app --reload --port 8000
```

### Frontend

The frontend is a Vite + React app located in `frontend/`.

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Production Deployment (Render)

This project is configured for deployment to [Render](https://render.com/).

1.  **Dockerfile**: A `Dockerfile` is included that builds the environment and runs the server with `uvicorn`.
2.  **Environment Variables**:
    - `TEADATA_SNAPSHOT` (Optional): Path to a pre-loaded snapshot file if you want to avoid rebuilding the data engine on startup.
    - `TEADATA_MAX_RESPONSE_BYTES` (Optional): Soft cap for list-heavy responses (default 24000; set 0 to disable).
    - `PORT`: Automatically set by Render (defaults to 10000).

The Dockerfile uses a multi-stage build strategy (implied) or a simple direct build. For a unified deployment, ensure the `frontend` is built and the `static_dist` folder is present before the Python server starts, or update your build pipeline to run `npm run build` in the frontend directory before building the Docker image.

**Note on Static Files:** The `sse_server.py` is configured to serve static files from `static_dist` if they exist. In a production Docker build, you should add a step to build the frontend assets.

## Integrating With `teadata-app` (SSO Launch)

For mission-critical deployments, run this service separately (e.g. `assistant.dataforpubliceducation.com`) and link to it from `teadata-app`. The recommended flow is:

1. User clicks `Assistant` in `teadata-app`.
2. `teadata-app` sets an HttpOnly cross-subdomain cookie (`teadata_assistant_sso`) and redirects to the assistant service.
3. This server verifies the cookie on `/api/tool/*` (and the UI) and rate-limits by user id.

### Domain requirements

Cookie-based SSO only works when both apps are on the same registrable domain (eTLD+1), so the cookie can be shared.

- Recommended: `dataforpubliceducation.com` (Django) + `assistant.dataforpubliceducation.com` (this service)
- If you host this service on a different domain, you’ll need a different auth mechanism (cookies won’t transfer).

### `teadata-app` (Django) environment

Set these on the `teadata-app` service:

- `TEADATA_ASSISTANT_ENABLED=1`: shows the `Assistant` nav link and enables `GET /assistant/launch/`.
- `TEADATA_ASSISTANT_URL`: where the launch endpoint redirects (e.g. `https://assistant.dataforpubliceducation.com/`).
- `TEADATA_ASSISTANT_SSO_SECRET`: shared signing key (must match this service).
- `TEADATA_ASSISTANT_COOKIE_DOMAIN`: e.g. `.dataforpubliceducation.com` (leave empty for localhost).
- `TEADATA_ASSISTANT_COOKIE_NAME`: defaults to `teadata_assistant_sso` (must match this service).
- `TEADATA_ASSISTANT_SSO_TTL_SECONDS`: defaults to `43200` (12 hours).

### `teadata-mcp` (this service) environment

Set these on this service:

- `TEADATA_ASSISTANT_SSO_SECRET`: shared signing key (must match `teadata-app`).
- `TEADATA_ASSISTANT_COOKIE_NAME`: defaults to `teadata_assistant_sso` (must match `teadata-app`).
- `TEADATA_ASSISTANT_LAUNCH_URL`: where to send unauthenticated browser requests (default `https://dataforpubliceducation.com/assistant/launch/`).
- `TEADATA_ASSISTANT_ENFORCE_SSO`: defaults to enabled when `TEADATA_ASSISTANT_SSO_SECRET` is set; set `0` to run publicly without login.
- `TEADATA_ASSISTANT_SSO_SKEW_SECONDS`: clock skew tolerance in seconds (default `60`).
- `TEADATA_DEBUG` or `DEBUG`: enable Starlette debug locally.

### Two-instance setup (recommended)

Keep the portal assistant isolated (SSO-locked) and keep the ChatGPT app public by deploying two separate services from the same code:

- **Website assistant (SSO-locked)**: `assistant.dataforpubliceducation.com`
  - Set `TEADATA_ASSISTANT_ENFORCE_SSO=1` and `TEADATA_ASSISTANT_SSO_SECRET=<shared>` (must match `teadata-app`)
  - Set `TEADATA_ASSISTANT_LAUNCH_URL=https://dataforpubliceducation.com/assistant/launch/`
- **ChatGPT MCP (public)**: `mcp.dataforpubliceducation.com` (or similar)
  - Set `TEADATA_ASSISTANT_ENFORCE_SSO=0` and do not set `TEADATA_ASSISTANT_SSO_SECRET`

### Auth behavior

- Browser UI: unauthenticated requests redirect to `TEADATA_ASSISTANT_LAUNCH_URL`.
- API (`/api/*`) and MCP endpoints (`/sse`, `/messages`, `/mcp`): unauthenticated requests return `401`.
- Non-browser clients can also send `Authorization: Bearer <token>` instead of a cookie (token value is the same as the SSO cookie value).

### ChatGPT app note

Cookie-based SSO is a browser flow; ChatGPT won’t automatically log users into your Django site or share those cookies. For a public ChatGPT app, deploy a separate instance with `TEADATA_ASSISTANT_ENFORCE_SSO=0` (and do not share your cross-subdomain cookie with it).

### Making the ChatGPT app private (later)

Two layers exist:

- **ChatGPT visibility**: keep the GPT unlisted/private (ChatGPT product setting) so only you/your workspace can access it.
- **Server-side access control** (optional): run the ChatGPT instance with authentication in front of it (e.g., reverse-proxy access control). Cookie-based portal SSO is not a good fit for ChatGPT clients; prefer a non-interactive mechanism (API key / service token) that ChatGPT can send on every request.

### Render checklist

- Configure health check path: `GET /healthz`.
- Add a custom domain (recommended): `assistant.dataforpubliceducation.com`.
- Set `TEADATA_ASSISTANT_SSO_SECRET` to the exact same value as `teadata-app` (rotate both services together).

## Project Structure

```
.
├── src/teadata_mcp/        # Python MCP Server
│   ├── logic.py            # Business logic & data processing
│   ├── router.py           # Tool definitions & routing
│   ├── server.py           # MCP Server setup
│   └── sse_server.py       # Starlette/SSE entry point
├── frontend/               # React Frontend (ChatGPT UI)
├── tests/                  # Unit tests
├── Dockerfile              # Production build definition
└── pyproject.toml          # Python dependencies
```

## Tooling Guide

The server includes a `get_tooling_guide` tool that returns recommended tool calls for common intents
(e.g., "show on a map", "within district boundaries", "compare campuses"). This makes it easier for
ChatGPT to pick the right tools without falling back to web search. Boundary/map tools also support
`response_profile` and `campus_meta_fields` to keep payloads compact while still exposing targeted
metrics for styling and analysis.

To update or add patterns, edit:

`src/teadata_mcp/tooling_guide.py`

## Inspecting Fields and Avoiding Truncation

Large teadata objects contain rich `meta` payloads. To prevent oversized responses, the MCP tools
return curated fields by default and only include `meta` keys when explicitly requested.

Use this workflow to discover which fields are available and fetch only what you need:

1. Identify the campus or district using `search_campuses` or `get_district`.
2. Use `get_campus_detail` or `get_district_detail` to see curated fields (staffing, demographics,
   class sizes, ratings, enrollment, etc.).
3. Request additional metrics with `meta_fields` or `campus_meta_fields` in small batches. If a
   requested key is missing, it will be omitted from the response.
4. For geometry/boundaries, call `get_entity_geometry` and inspect `geometry_fields` to see what
   geometric attributes are available.
5. If payloads are still large, use `response_profile` on boundary/map tools:
   - `map`: GeoJSON points only (compact, map-friendly)
   - `list`: campus list only
   - `both`: include both GeoJSON and list
6. Boundary tools paginate. If `pagination.next_cursor` is present, call the same tool
   again with `cursor=next_cursor` to fetch the next page. Use `max_response_bytes`
   (default 24000 or `TEADATA_MAX_RESPONSE_BYTES`, set to 0 to disable) to control automatic trimming.
7. For list outputs, set `campus_list_format` to control how compact the list is:
   - `id_name` (default): campus_number + name tuples
   - `id`: campus identifiers only (campus_number or name)
   - `full`: full campus summaries (largest)
8. When `next_tool_call` is provided, follow it exactly to fetch the next page; this
   prevents ChatGPT from searching the web unnecessarily. Boundary responses also
   include `do_not_web_search=true` and a `boundary_reference.download_url`.
9. Set `include_total=true` on list tools to include `pagination.total_matches` when you
   need counts across pages.
10. If `payload.completeness.needs_follow_up` is true, follow `next_tool_call` (or ask the user to
    continue) before finalizing results.
11. List tools include `payload.table` for deterministic table rendering and `payload.exports`
    with `resource_uri` for CSV/JSON exports; call `read_resource` to fetch full files when needed.
12. `search_campuses`, `get_district_detail`, and `get_nearby_campuses` also paginate and
    return `pagination` plus an optional `next_tool_call`.

Example follow-up flow (map then list):

```text
Find all charter campuses within Austin ISD boundaries on a map, and include overall_rating_2025.
Now return the same campuses as a list with campus_list_format id_name and campus_meta_fields: campus_2025_staff_teacher_student_ratio.
```

Common meta key patterns in teadata include `campus_2025_*` and `district_2025_*` (for the latest
year). Ask for only the keys that match the user’s intent, and iterate with follow-up tool calls if
you need more fields.

See `SAMPLE_QUERIES.md` for prompts that demonstrate field inspection and follow-up calls.

## Performance & Logging

By default, the server writes JSON logs to `logs/teadata-mcp.log` (with rotation). Tool calls emit
`tool.start` / `tool.end` records plus perf metrics (payload bytes, RSS deltas), which makes it easy
to pinpoint lagginess.

To generate a shareable report (and copy it to your clipboard):

```bash
./share_perf_report.sh
```

Useful flags:
- `--slow-ms 250` to capture more “slow” calls
- `--lines 50000` to analyze a larger window

Key env vars:
- `TEADATA_LOG_FILE`, `TEADATA_LOG_LEVEL`, `TEADATA_LOG_FORMAT` (`json` or `text`)
- `TEADATA_PERF_LOG`, `TEADATA_PERF_PAYLOAD`, `TEADATA_PERF_TRACEMALLOC`
- `TEADATA_WARM_ENGINE_ON_STARTUP` (default `1`, set `0` to disable)
