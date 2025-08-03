# Multi-stage build for optimal image size and build efficiency
# Stage 1: Build dependencies and generate requirements
FROM python:3.12-slim AS builder

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /build
COPY pyproject.toml README.md uv.lock ./

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
RUN uv sync --frozen --no-dev


# Stage 2: Runtime image
FROM builder AS runtime

# Metadata labels
LABEL maintainer="TrustBuilder Wargames Team"
LABEL version="1.0.0"
LABEL description="TrustBuilder Wargames AI Backend - FastAPI service with Supabase and Letta integration"
LABEL org.opencontainers.image.title="wargames-ai-backend"
LABEL org.opencontainers.image.description="FastAPI backend service for TrustBuilder Wargames platform"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="TrustBuilder"
# LABEL org.opencontainers.image.licenses="MIT"

ARG PORT="8080"
ARG HOST="0.0.0.0"
ENV PATH="/opt/venv/bin:$PATH"
ENV PORT=${PORT}

WORKDIR /app
COPY --from=builder /build/.venv /opt/venv

RUN useradd --create-home --shell /bin/bash --uid 1000 appuser
COPY --chown=appuser:appuser . .

RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p logs && chown -R appuser:appuser logs

USER appuser
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://${HOST}:${PORT}/health_check || exit 1
CMD ["sh", "-c", "python -m uvicorn backend.server:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]


