# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Build the backend and serve everything
FROM python:3.12-slim
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

# Copy backend files for dependency installation
COPY backend/pyproject.toml backend/uv.lock ./
# Sync dependencies (no-dev for production)
RUN uv sync --frozen --no-dev --no-install-project

# Copy the rest of the backend code
COPY backend/ ./

# Install the project itself
RUN uv sync --frozen --no-dev

# Copy built frontend to the static directory expected by FastAPI
COPY --from=frontend-builder /app/frontend/out ./static

# Ensure the data directory exists for volume mounting
RUN mkdir -p /app/data

# Expose port 8000
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Command to run the application
CMD ["sh", "-c", "uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
