# Project Context: teadata-mcp

## Overview
**teadata-mcp** is a Model Context Protocol (MCP) server that provides access to Texas Education Agency (TEA) data. It is designed primarily as a backend for ChatGPT applications, featuring a React-based frontend that integrates with OpenAI's `apps-sdk-ui`.

The application exposes a rich dataset of Texas school districts, campuses, and performance metrics through an SSE (Server-Sent Events) endpoint, allowing AI models to query and visualize this data.

## Technology Stack

### Backend
*   **Language:** Python 3.11+
*   **Framework:** Starlette (ASGI), `sse-starlette` for SSE.
*   **Protocol:** Model Context Protocol (MCP) via `modelcontextprotocol` package.
*   **Dependency Management:** [`uv`](https://docs.astral.sh/uv/)
*   **Key Library:** `teadata` (Git dependency) for data access.

### Frontend
*   **Framework:** React 18
*   **Build Tool:** Vite
*   **Styling:** Tailwind CSS, `shadcn/ui` components (Radix UI + Tailwind).
*   **Integration:** `@openai/apps-sdk-ui` for ChatGPT native look and feel.
*   **Language:** TypeScript

## Directory Structure

*   `src/teadata_mcp/`: Python source code.
    *   `sse_server.py`: Main ASGI application entry point. Handles SSE (`/sse`) and serves static files.
    *   `server.py`: MCP server initialization and logic.
    *   `router.py`: Tool definitions and request routing.
    *   `logic.py`: Core business logic and data processing.
    *   `config.py`: Configuration settings.
*   `frontend/`: React frontend source code.
    *   `src/`: Components and views (`App.tsx`, `CampusView.tsx`, etc.).
    *   `vite.config.ts`: Configured to output builds to `../static_dist`.
*   `static_dist/`: (Generated) Compiled frontend assets served by the Python backend.
*   `tests/`: Pytest suite.
*   `Dockerfile`: Multi-stage build for production deployment.
*   `run_dev.sh`: Helper script for local development.

## Development Workflow

### Prerequisites
*   Python 3.11 or higher
*   Node.js 20+ (for frontend)
*   `uv` package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Quick Start
The recommended way to start the development environment is using the included script:

```bash
./run_dev.sh
```
This script handles:
1.  Building the frontend.
2.  Syncing Python dependencies.
3.  Starting the server on `http://localhost:8000`.

### Manual Setup

**Backend:**
```bash
# Install dependencies
uv sync

# Run the server (auto-reloads on change)
uv run uvicorn teadata_mcp.sse_server:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```
*Note: The backend expects frontend assets in `static_dist` to serve the UI at the root URL. `npm run dev` runs a separate dev server, usually on port 5173.*

## Build & Deployment
The project uses Docker for deployment (e.g., to Render).

**Docker Build Process:**
1.  **Stage 1 (Frontend):** Builds the React app inside a Node.js container. Output goes to `static_dist`.
2.  **Stage 2 (Backend):** Installs Python dependencies using `uv` and copies the `static_dist` from Stage 1.
3.  **Run:** Starts `uvicorn` serving the API and the static frontend files.

**Key Environment Variables:**
*   `PORT`: Server port (default: 10000 in Docker, 8000 in dev).
*   `TEADATA_SNAPSHOT`: Path to a data snapshot file (optional).
*   `DEBUG`: Set to `True` for debug mode.

## Important Notes
*   **Data Source:** The `teadata` library pulls data from git or local snapshots.
*   **Static Files:** `sse_server.py` checks for the existence of `static_dist`. If found, it mounts it to serve the SPA. If not, only the API endpoints are available.
