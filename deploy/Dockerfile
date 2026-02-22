# NeuroInsight All-in-One Docker Container
# This Dockerfile packages the entire NeuroInsight application into a single container
# including PostgreSQL, Redis, MinIO, Backend, Worker, and Frontend

FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    POSTGRES_VERSION=15 \
    REDIS_VERSION=7.0 \
    MINIO_VERSION=RELEASE.2024-01-18T22-51-28Z \
    HOME=/home/neuroinsight

# Create application user and add to docker group for socket access
RUN useradd -m -u 1000 -s /bin/bash neuroinsight

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Network and utilities (install first)
    curl \
    wget \
    gnupg \
    lsb-release \
    ca-certificates \
    # Build tools
    build-essential \
    gcc \
    # Image processing libraries
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    # Process supervisor
    supervisor \
    # Redis
    redis-server \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI for FreeSurfer container spawning
# Note: Docker group GID is auto-configured at runtime by entrypoint.sh
# This ensures compatibility with any host system (Linux, WSL2, Docker Desktop)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && \
    apt-get install -y docker-ce-cli && \
    rm -rf /var/lib/apt/lists/* && \
    # Create docker group with placeholder GID (will be updated at runtime by entrypoint)
    groupadd -g 999 docker || true && \
    usermod -aG docker neuroinsight && \
    # Create Docker config directory for neuroinsight user to avoid /root permission errors
    mkdir -p /home/neuroinsight/.docker && \
    echo '{}' > /home/neuroinsight/.docker/config.json && \
    chown -R neuroinsight:neuroinsight /home/neuroinsight/.docker

# Add PostgreSQL APT repository and install
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    apt-get install -y postgresql-${POSTGRES_VERSION} postgresql-contrib-${POSTGRES_VERSION} && \
    rm -rf /var/lib/apt/lists/*

# Install MinIO
RUN wget https://dl.min.io/server/minio/release/linux-amd64/minio -O /usr/local/bin/minio && \
    chmod +x /usr/local/bin/minio

# Create application directories
WORKDIR /app
RUN mkdir -p \
    /data/uploads \
    /data/outputs \
    /data/logs \
    /data/postgresql \
    /data/redis \
    /data/minio \
    /var/log/supervisor

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY workers/ /app/workers/
COPY pipeline/ /app/pipeline/
COPY scripts/ /app/scripts/
COPY frontend/dist/ /app/frontend/dist/

# Copy configuration files
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/entrypoint.sh /app/entrypoint.sh
COPY deploy/healthcheck.sh /app/healthcheck.sh

# Set up PostgreSQL
RUN mkdir -p /var/lib/postgresql/data && \
    chown -R postgres:postgres /var/lib/postgresql && \
    chmod 700 /var/lib/postgresql/data

# Set permissions
RUN chmod +x /app/entrypoint.sh /app/healthcheck.sh && \
    chown -R neuroinsight:neuroinsight /app /data

# Expose ports
EXPOSE 8000 5432 6379 9000 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /app/healthcheck.sh

# Volume for persistent data
VOLUME ["/data"]

# Entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
