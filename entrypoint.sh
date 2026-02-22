#!/bin/bash
set -e

echo "======================================"
echo "NeuroInsight All-in-One Container"
echo "======================================"

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if su - postgres -c "pg_isready -U neuroinsight" > /dev/null 2>&1; then
            echo "PostgreSQL is ready!"
            return 0
        fi
        echo "Attempt $i/30: PostgreSQL not ready yet, waiting..."
        sleep 2
    done
    echo "ERROR: PostgreSQL failed to start"
    return 1
}

# Function to wait for Redis to be ready
wait_for_redis() {
    echo "Waiting for Redis to be ready..."
    for i in {1..30}; do
        if redis-cli -a redis_secure_password ping > /dev/null 2>&1; then
            echo "Redis is ready!"
            return 0
        fi
        echo "Attempt $i/30: Redis not ready yet, waiting..."
        sleep 1
    done
    echo "ERROR: Redis failed to start"
    return 1
}

# Initialize PostgreSQL if needed
if [ ! -f /data/postgresql/PG_VERSION ]; then
    echo "Initializing PostgreSQL database..."
    mkdir -p /data/postgresql
    chown -R postgres:postgres /data/postgresql
    chmod 700 /data/postgresql
    
    su - postgres -c "/usr/lib/postgresql/15/bin/initdb -D /data/postgresql"
    
    # Configure PostgreSQL
    echo "host all all 0.0.0.0/0 md5" >> /data/postgresql/pg_hba.conf
    echo "listen_addresses = '*'" >> /data/postgresql/postgresql.conf
    
    # Start PostgreSQL temporarily to create database
    su - postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D /data/postgresql -l /tmp/postgres.log start"
    
    sleep 5
    
    # Create database and user
    su - postgres -c "psql -c \"CREATE USER neuroinsight WITH PASSWORD 'neuroinsight_secure_password';\""
    su - postgres -c "psql -c \"CREATE DATABASE neuroinsight OWNER neuroinsight;\""
    su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE neuroinsight TO neuroinsight;\""
    
    # Stop PostgreSQL
    su - postgres -c "/usr/lib/postgresql/15/bin/pg_ctl -D /data/postgresql stop"
    
    echo "PostgreSQL initialized successfully"
else
    echo "PostgreSQL already initialized"
fi

# Create Redis data directory
mkdir -p /data/redis
chown -R neuroinsight:neuroinsight /data/redis

# Create MinIO data directory
mkdir -p /data/minio
chown -R neuroinsight:neuroinsight /data/minio

# Create upload/output directories
mkdir -p /data/uploads /data/outputs /data/logs
chown -R neuroinsight:neuroinsight /data/uploads /data/outputs /data/logs

# Create .env file if it doesn't exist
if [ ! -f /app/.env ]; then
    echo "Creating .env configuration file..."
    cat > /app/.env << EOF
# PostgreSQL Database
POSTGRES_USER=neuroinsight
POSTGRES_PASSWORD=neuroinsight_secure_password
POSTGRES_DB=neuroinsight
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql://neuroinsight:neuroinsight_secure_password@localhost:5432/neuroinsight

# Redis
REDIS_PASSWORD=redis_secure_password
REDIS_URL=redis://:redis_secure_password@localhost:6379/0

# MinIO/S3 Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin_secure
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET_NAME=neuroinsight-data
MINIO_USE_SSL=false

# API Configuration
API_PORT=8000
CORS_ORIGINS=http://localhost:8000

# File Storage
UPLOAD_DIR=/data/uploads
OUTPUT_DIR=/data/outputs

# Environment
ENVIRONMENT=production
EOF
    chown neuroinsight:neuroinsight /app/.env
fi

# Check for FreeSurfer license
if [ -f /app/license.txt ]; then
    echo "FreeSurfer license found"
elif [ -f /data/license.txt ]; then
    echo "FreeSurfer license found in /data"
    cp /data/license.txt /app/license.txt
else
    echo "WARNING: FreeSurfer license not found"
    echo "Application will run in demo mode with mock processing"
    echo "To enable full FreeSurfer functionality:"
    echo "  1. Place license.txt in the container at /app/license.txt"
    echo "  2. Or mount it: -v /path/to/license.txt:/app/license.txt"
fi

echo ""
echo "======================================"
echo "Starting NeuroInsight Services"
echo "======================================"
echo ""

# Execute the command (supervisord)
exec "$@"
