# ── AgentLens API — development image ────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install build tools needed by some C-extension deps (asyncpg, hiredis)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first so Docker can cache the install layer
COPY pyproject.toml .

# Install runtime + dev dependencies
RUN pip install --no-cache-dir ".[dev]"

# Source is mounted as a volume at runtime for hot reload;
# copy here so the image is self-contained for CI builds.
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
