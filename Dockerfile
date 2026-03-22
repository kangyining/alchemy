# Custom Dockerfile for report-agents with system dependencies
# Required for cairosvg and weasyprint (PDF/SVG rendering)

FROM python:3.12-slim

# Install system dependencies for cairosvg and weasyprint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libgobject-2.0-0 \
    libgirepository-1.0-1 \
    gir1.2-pango-1.0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Export requirements from uv and install
RUN uv export --no-hashes --no-emit-project > requirements.txt && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY report_agents/ ./report_agents/
COPY main.py ./

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
# Parent of agent packages (each subdir is an agent); matches former api_server path
ENV ADK_AGENTS_DIR=/app

# Hypercorn accepts h2c on plain HTTP (Cloud Run with --use-http2) and h2 over TLS
# locally via ALPN.
CMD ["sh", "-c", "exec hypercorn main:app --bind 0.0.0.0:${PORT}"]
