# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app

# Copy frontend source
COPY frontend/ ./frontend/

# Install dependencies and build
WORKDIR /app/frontend
RUN npm install --legacy-peer-deps
RUN npm run build

# Stage 2: Setup Python environment and serve
FROM python:3.11-slim-bookworm

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

# Copy built frontend assets from the builder stage
COPY --from=frontend-builder /app/static_dist ./static_dist

# Expose the port
ENV PORT=10000
EXPOSE $PORT

# Command to run the application
CMD uv run uvicorn teadata_mcp.sse_server:app --host 0.0.0.0 --port $PORT