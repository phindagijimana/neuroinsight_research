# ==============================================================================
#  NeuroInsight Research -- Multi-stage Production Dockerfile
#
#  Stage 1: Build the frontend (Node.js)
#  Stage 2: Production image (Python + static frontend served by nginx)
# ==============================================================================

# ---- Stage 1: Frontend build ------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts

COPY frontend/ ./
RUN npm run build


# ---- Stage 2: Production runtime -------------------------------------------
FROM python:3.10-slim AS production

# System dependencies (PostgreSQL client for pg_isready, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash neuroinsight
WORKDIR /home/neuroinsight/app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy backend code
COPY backend/ ./backend/
COPY plugins/ ./plugins/
COPY workflows/ ./workflows/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Copy nginx config for serving frontend
COPY deploy/nginx.conf /etc/nginx/nginx.conf

# Create data directories
RUN mkdir -p data/outputs data/uploads logs && \
    chown -R neuroinsight:neuroinsight /home/neuroinsight/app

# Copy entrypoint
COPY deploy/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Switch to non-root user
USER neuroinsight

# Environment defaults
ENV ENVIRONMENT=production \
    PYTHONPATH=/home/neuroinsight/app \
    WORKERS=2 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

ENTRYPOINT ["./entrypoint.sh"]
