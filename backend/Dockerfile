FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv manually to avoid multi-stage or platform issues
# Use pip to install uv (easiest across all platforms)
RUN pip install uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies
# We use --frozen to respect lock file
# We use --no-install-project to install dependencies only first
# This ensures caching of dependencies
RUN uv sync --frozen --no-install-project

# Copy source code
COPY . .

# Install project itself (if needed, or just rely on pythonpath)
# We might need to run `uv sync` again
RUN uv sync --frozen

# Expose port
EXPOSE 8000

# Run with uv run to activate environment
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
