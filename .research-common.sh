#!/usr/bin/env bash
# ------------------------------------------------------------------------------
#  NeuroInsight Research -- Shared CLI library
#
#  Sourced by both ./research (production) and ./research-dev (development).
#  Do NOT run this file directly.
# ------------------------------------------------------------------------------

# -- Constants -----------------------------------------------------------------
VERSION="1.3.0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
cd "$SCRIPT_DIR"

COMPOSE_FILE="$SCRIPT_DIR/docker-compose.infra.yml"

# MODE is set by the calling script before sourcing this file.
# Valid values: "production" | "development"
MODE="${MODE:-production}"

# Colour helpers (disabled when piped)
if [ -t 1 ]; then
    RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'
    BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'
    DIM='\033[2m'; NC='\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; BOLD=''; DIM=''; NC=''
fi

# -- Configurable defaults (overridable via .env) -----------------------------
#   Default port allocation:
#     3000  Frontend
#     3001  Backend  (FastAPI / Uvicorn)
#     3002  (reserved / future)
#     3003  (reserved / future)
#   If a default is busy, next free port in 3000-3050 is used.
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_PORT="${API_PORT:-3001}"
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"
DATA_DIR="${DATA_DIR:-./data}"
LOG_DIR="${LOG_DIR:-./logs}"
PID_DIR="${PID_DIR:-./.pids}"

PORT_RANGE_START=3000
PORT_RANGE_END=3050

# Load .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
    BACKEND_PORT="${API_PORT:-3001}"
    FRONTEND_PORT="${FRONTEND_PORT:-3000}"
fi

# Remember the requested defaults for "busy" warnings
BACKEND_PORT_DEFAULT="$BACKEND_PORT"
FRONTEND_PORT_DEFAULT="$FRONTEND_PORT"

# -- Helper functions ----------------------------------------------------------
header() {
    local mode_label
    if [ "$MODE" = "development" ]; then
        mode_label="${YELLOW}DEV${NC}"
    else
        mode_label="${GREEN}PROD${NC}"
    fi
    echo -e "${BOLD}${BLUE}"
    echo "  NeuroInsight Research  v${VERSION}"
    echo -e "${NC}  Mode: ${mode_label}"
    echo ""
}

info()    { echo -e "  ${CYAN}>${NC} $*"; }
success() { echo -e "  ${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "  ${YELLOW}!${NC} $*"; }
error()   { echo -e "  ${RED}[ERR]${NC} $*" >&2; }
step()    { echo -e "\n${BOLD}-- $* --${NC}"; }

ensure_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR" "$DATA_DIR"/{uploads,outputs}
}

write_pid() {
    echo "$2" > "$PID_DIR/$1.pid"
}

read_pid() {
    local f="$PID_DIR/$1.pid"
    [ -f "$f" ] && cat "$f" || echo ""
}

is_pid_alive() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

wait_for_url() {
    local url="$1" max="${2:-30}" label="${3:-service}"
    for i in $(seq 1 "$max"); do
        if curl -sf "$url" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

port_in_use() {
    lsof -Pi :"$1" -sTCP:LISTEN -t > /dev/null 2>&1
}

# find_port <default> <exclude...>
#   Returns <default> if free, otherwise the first free port in 3000-3050
#   that is not in the exclude list.
find_port() {
    local default_port="$1"; shift
    local -a excludes=("$@")

    _excluded() {
        local p="$1"
        for e in "${excludes[@]}"; do
            [[ "$p" == "$e" ]] && return 0
        done
        return 1
    }

    if ! port_in_use "$default_port" && ! _excluded "$default_port"; then
        echo "$default_port"; return 0
    fi

    for p in $(seq "$PORT_RANGE_START" "$PORT_RANGE_END"); do
        if ! port_in_use "$p" && ! _excluded "$p"; then
            echo "$p"; return 0
        fi
    done
    return 1
}

kill_by_pattern() {
    local pids
    pids=$(pgrep -f "$1" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        info "Stopping $2 ..."
        kill $pids 2>/dev/null || true
        sleep 1
        pids=$(pgrep -f "$1" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            kill -9 $pids 2>/dev/null || true
            sleep 0.5
        fi
        success "$2 stopped"
    else
        info "$2 not running"
    fi
}

# -- Resolve ports (shared by both modes) -------------------------------------
resolve_ports() {
    step "Port allocation"

    local USED_PORTS=()

    # Backend first (must be known before frontend for proxy config)
    BACKEND_PORT=$(find_port "$BACKEND_PORT") || {
        error "No free port in $PORT_RANGE_START-$PORT_RANGE_END for backend"; exit 1
    }
    USED_PORTS+=("$BACKEND_PORT")

    if [ "$BACKEND_PORT" != "$BACKEND_PORT_DEFAULT" ]; then
        warn "Backend default $BACKEND_PORT_DEFAULT busy -> using $BACKEND_PORT"
    fi
    success "Backend    -> port $BACKEND_PORT"

    # Frontend (exclude the backend port)
    FRONTEND_PORT=$(find_port "$FRONTEND_PORT" "${USED_PORTS[@]}") || {
        error "No free port in $PORT_RANGE_START-$PORT_RANGE_END for frontend"; exit 1
    }
    USED_PORTS+=("$FRONTEND_PORT")

    if [ "$FRONTEND_PORT" != "$FRONTEND_PORT_DEFAULT" ]; then
        warn "Frontend default $FRONTEND_PORT_DEFAULT busy -> using $FRONTEND_PORT"
    fi
    success "Frontend   -> port $FRONTEND_PORT"
}

# ==============================================================================
#  INSTALL (shared)
# ==============================================================================
cmd_install() {
    header
    step "Installing NeuroInsight Research"
    ensure_dirs

    # -- Python dependencies ---------------------------------------------------
    step "Python dependencies"
    if command -v pip3 &>/dev/null; then
        pip3 install -q -r requirements.txt 2>&1 | tail -5
        success "Python dependencies installed"
    else
        error "pip3 not found. Install Python 3.9+ first."
        exit 1
    fi

    # -- Frontend dependencies -------------------------------------------------
    step "Frontend dependencies"
    if [ -d "frontend" ]; then
        (cd frontend && npm install --silent 2>&1 | tail -3)
        success "Frontend node_modules installed"
    else
        warn "frontend/ directory not found -- skipping"
    fi

    # -- Build frontend (production only) --------------------------------------
    if [ "$MODE" = "production" ] && [ -d "frontend" ]; then
        step "Frontend production build"
        (cd frontend && npm run build 2>&1 | tail -5)
        success "Frontend built -> frontend/dist/"
    fi

    # -- .env file with generated secrets --------------------------------------
    step "Environment configuration"
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            # Generate random passwords for local services
            _rand() { python3 -c "import secrets; print(secrets.token_urlsafe(24))"; }
            local pg_pass; pg_pass=$(_rand)
            local redis_pass; redis_pass=$(_rand)
            local minio_pass; minio_pass=$(_rand)
            local secret_key; secret_key=$(_rand)
            # Replace defaults in .env
            sed -i "s|neuroinsight_secure_password|${pg_pass}|g" .env
            sed -i "s|redis_secure_password|${redis_pass}|g" .env
            sed -i "s|minioadmin_secure|${minio_pass}|g" .env
            sed -i "s|dev-secret-key-change-in-production-minimum-32-characters|${secret_key}|g" .env
            # docker-compose.infra.yml now reads passwords from .env via
            # ${VARIABLE:-default} syntax, so no sed replacement needed.
            success "Created .env with generated random passwords"
        else
            warn "No .env or .env.example found"
        fi
    else
        success ".env already exists"
    fi

    # -- Infrastructure services -----------------------------------------------
    step "Infrastructure services (PostgreSQL / Redis / MinIO)"
    if _infra_running; then
        success "Infrastructure services already running"
    else
        info "Starting infrastructure via docker compose ..."
        if _infra_up_quiet; then
            success "Infrastructure services started"
        else
            warn "Could not start infrastructure. Run:  ./research infra up"
        fi
    fi

    # -- Database schema -------------------------------------------------------
    step "Database schema"
    local _db_err
    _db_err=$(python3 -c "from backend.core.database import init_db; init_db(); print('OK')" 2>&1)
    if echo "$_db_err" | grep -q "OK"; then
        success "Database tables verified/created"
    else
        warn "Could not initialise database (is PostgreSQL reachable?)"
        info "  Error: $(echo "$_db_err" | tail -1)"
        info "  Check: docker ps | grep neuroinsight-db"
    fi

    # -- MinIO buckets ---------------------------------------------------------
    step "MinIO storage buckets"
    local _minio_err
    _minio_err=$(python3 -c "
from backend.core.storage import storage
storage.client
print('OK')
" 2>&1)
    if echo "$_minio_err" | grep -q "OK"; then
        success "MinIO buckets ready"
    else
        warn "Could not verify MinIO buckets (is MinIO reachable?)"
        info "  Error: $(echo "$_minio_err" | tail -1)"
        info "  Check: docker ps | grep neuroinsight-minio"
    fi

    # -- FreeSurfer license ----------------------------------------------------
    step "FreeSurfer license"
    local _fs_license_found=false
    for _lpath in \
        "./license.txt" \
        "$HOME/.freesurfer/license.txt" \
        "$HOME/freesurfer/license.txt" \
        "/usr/local/freesurfer/license.txt" \
        "${FS_LICENSE:-__none__}"; do
        if [ -f "$_lpath" ] && [ -s "$_lpath" ]; then
            _fs_license_found=true
            success "FreeSurfer license found at $_lpath"
            break
        fi
    done
    if [ "$_fs_license_found" = false ]; then
        warn "FreeSurfer license.txt not found (needed for FreeSurfer/FastSurfer plugins)"
        info "Place your license.txt in the app directory or ~/.freesurfer/license.txt"
        info "Get a free license at: https://surfer.nmr.mgh.harvard.edu/registration.html"
    fi

    # -- Pipeline Docker images ------------------------------------------------
    step "Pipeline Docker images"
    local images=("freesurfer/freesurfer:7.4.1" "deepmi/fastsurfer:v2.4.2")
    for img in "${images[@]}"; do
        if docker image inspect "$img" &>/dev/null; then
            success "$img  (present)"
        else
            warn "$img  (not pulled -- run: ./research pull)"
        fi
    done

    echo ""
    success "Installation complete."
    if [ "$MODE" = "development" ]; then
        info "Run ${BOLD}./research-dev start${NC} to launch in development mode."
    else
        info "Run ${BOLD}./research start${NC} to launch in production mode."
    fi
    echo ""
}

# ==============================================================================
#  STOP (shared)
# ==============================================================================
cmd_stop() {
    local quiet=false
    [[ "${1:-}" == "--quiet" ]] && quiet=true

    $quiet || header
    $quiet || step "Stopping services"

    for svc in frontend celery backend; do
        local pid
        pid=$(read_pid "$svc")
        if [ -n "$pid" ] && is_pid_alive "$pid"; then
            $quiet || info "Stopping $svc (PID $pid)"
            kill "$pid" 2>/dev/null || true
        fi
        rm -f "$PID_DIR/$svc.pid"
    done

    sleep 1

    kill_by_pattern "uvicorn backend.main"            "Backend"
    kill_by_pattern "celery.*neuroinsight"             "Celery worker"
    kill_by_pattern "celery.*backend.core.celery_app"  "Celery worker (alt)"
    kill_by_pattern "vite.*--port"                     "Frontend (Vite)"

    for p in $BACKEND_PORT $FRONTEND_PORT; do
        if port_in_use "$p"; then
            fuser -k "$p/tcp" &>/dev/null || true
        fi
    done

    $quiet || success "All services stopped"
    $quiet || echo ""
}

# ==============================================================================
#  RESTART (shared -- delegates to mode-specific cmd_start)
# ==============================================================================
cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start "$@"
}

# ==============================================================================
#  STATUS (shared)
# ==============================================================================
cmd_status() {
    header
    step "Service status"

    local pid
    pid=$(read_pid backend)
    if [ -n "$pid" ] && is_pid_alive "$pid"; then
        success "Backend        PID $pid   port $BACKEND_PORT"
    elif port_in_use "$BACKEND_PORT"; then
        warn  "Backend        port $BACKEND_PORT in use (unknown PID)"
    else
        info  "Backend        stopped"
    fi

    pid=$(read_pid celery)
    if [ -n "$pid" ] && is_pid_alive "$pid"; then
        success "Celery worker  PID $pid"
    elif pgrep -f "celery.*neuroinsight" &>/dev/null; then
        warn  "Celery worker  running (unknown PID)"
    else
        info  "Celery worker  stopped"
    fi

    pid=$(read_pid frontend)
    if [ -n "$pid" ] && is_pid_alive "$pid"; then
        success "Frontend       PID $pid   port $FRONTEND_PORT"
    elif port_in_use "$FRONTEND_PORT"; then
        warn  "Frontend       port $FRONTEND_PORT in use (unknown PID)"
    else
        info  "Frontend       stopped"
    fi

    step "Infrastructure"
    if _infra_running; then
        success "Infrastructure services running (docker compose)"

        if docker exec neuroinsight-db pg_isready -U neuroinsight &>/dev/null; then
            success "  PostgreSQL   ready  (localhost:5432)"
        else
            warn  "  PostgreSQL   not responding"
        fi

        if docker exec neuroinsight-redis redis-cli -a "${REDIS_PASSWORD:-redis_secure_password}" ping 2>/dev/null | grep -q PONG; then
            success "  Redis        ready  (localhost:6379)"
        else
            warn  "  Redis        not responding"
        fi

        if curl -sf "http://localhost:9000/minio/health/live" &>/dev/null; then
            success "  MinIO        ready  (localhost:9000)"
        else
            warn  "  MinIO        not responding"
        fi
    else
        info  "Infrastructure services not running"
        info  "Start with:  ./research infra up"
    fi

    step "Disk usage"
    if [ -d "$DATA_DIR" ]; then
        info "Data directory: $(du -sh "$DATA_DIR" 2>/dev/null | cut -f1)"
    fi
    if [ -d "$LOG_DIR" ]; then
        info "Logs:           $(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)"
    fi

    echo ""
}

# ==============================================================================
#  HEALTH (shared)
# ==============================================================================
cmd_health() {
    local url="http://localhost:$BACKEND_PORT/health"
    info "Querying $url ..."
    echo ""

    if ! curl -sf "$url" | python3 -m json.tool 2>/dev/null; then
        error "Backend not reachable on port $BACKEND_PORT"
        exit 1
    fi
    echo ""
}

# ==============================================================================
#  LOGS (shared)
# ==============================================================================
cmd_logs() {
    local svc="${1:-all}"
    ensure_dirs

    case "$svc" in
        backend)
            info "Tailing $LOG_DIR/backend.log  (Ctrl+C to stop)"
            tail -f "$LOG_DIR/backend.log" 2>/dev/null || error "No backend log yet"
            ;;
        celery)
            info "Tailing $LOG_DIR/celery.log  (Ctrl+C to stop)"
            tail -f "$LOG_DIR/celery.log" 2>/dev/null || error "No celery log yet"
            ;;
        frontend)
            info "Tailing $LOG_DIR/frontend.log  (Ctrl+C to stop)"
            tail -f "$LOG_DIR/frontend.log" 2>/dev/null || error "No frontend log yet"
            ;;
        all)
            info "Tailing all logs  (Ctrl+C to stop)"
            tail -f "$LOG_DIR"/*.log 2>/dev/null || error "No logs yet"
            ;;
        *)
            error "Unknown service: $svc"
            info "Usage: ./research logs [backend|celery|frontend|all]"
            exit 1
            ;;
    esac
}

# ==============================================================================
#  DB (shared)
# ==============================================================================
cmd_db() {
    local sub="${1:-help}"

    case "$sub" in
        init)
            step "Initialising database schema"
            python3 -c "from backend.core.database import init_db; init_db(); print('Done')"
            success "Database schema created/verified"
            ;;
        reset)
            step "Resetting database (DROP + CREATE)"
            read -rp "  This will DELETE all job data. Continue? [y/N] " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                docker exec neuroinsight-db psql -U neuroinsight -d neuroinsight \
                    -c "DROP TABLE IF EXISTS jobs CASCADE;" 2>/dev/null
                python3 -c "from backend.core.database import init_db; init_db()"
                success "Database reset complete"
            else
                info "Cancelled"
            fi
            ;;
        migrate)
            step "Running database migration (Alembic)"
            if command -v alembic &>/dev/null; then
                alembic upgrade head
            else
                warn "Alembic not installed -- using init_db() instead"
                python3 -c "from backend.core.database import init_db; init_db()"
            fi
            success "Migration complete"
            ;;
        shell)
            step "Opening PostgreSQL shell"
            info "Connecting to neuroinsight database..."
            docker exec -it neuroinsight-db psql -U neuroinsight -d neuroinsight
            ;;
        jobs)
            step "Recent jobs"
            docker exec neuroinsight-db psql -U neuroinsight -d neuroinsight \
                -c "SELECT id, pipeline_name, status, progress, current_phase,
                           submitted_at, exit_code
                    FROM jobs
                    WHERE deleted = false
                    ORDER BY submitted_at DESC
                    LIMIT 20;" 2>/dev/null || error "Could not query database"
            ;;
        *)
            echo "Usage: ./research db <subcommand>"
            echo ""
            echo "  init       Create/verify database tables"
            echo "  reset      Drop and recreate all tables (destructive)"
            echo "  migrate    Run Alembic migrations"
            echo "  shell      Open interactive PostgreSQL shell"
            echo "  jobs       Show recent jobs"
            echo ""
            ;;
    esac
}

# ==============================================================================
#  PULL (shared)
# ==============================================================================
cmd_pull() {
    local target="${1:-all}"
    header
    step "Pulling pipeline Docker images"

    declare -A IMAGES=(
        [freesurfer]="freesurfer/freesurfer:7.4.1"
        [fastsurfer]="deepmi/fastsurfer:latest"
        [fmriprep]="nipreps/fmriprep:24.0.0"
        [qsiprep]="pennbbl/qsiprep:0.22.0"
        [xcpd]="pennbbl/xcp_d:0.7.0"
        [dcm2niix]="bids/dcm2niix:latest"
    )

    if [ "$target" == "all" ]; then
        for name in "${!IMAGES[@]}"; do
            local img="${IMAGES[$name]}"
            info "Pulling $name ($img) ..."
            if docker pull "$img" 2>&1 | tail -1; then
                success "$name ready"
            else
                warn "Failed to pull $name -- skipping"
            fi
        done
    elif [ -n "${IMAGES[$target]+x}" ]; then
        local img="${IMAGES[$target]}"
        info "Pulling $target ($img) ..."
        docker pull "$img"
        success "$target ready"
    else
        error "Unknown image: $target"
        info "Available: ${!IMAGES[*]}"
        exit 1
    fi
    echo ""
}

# ==============================================================================
#  CLEAN (shared)
# ==============================================================================
cmd_clean() {
    header
    step "Cleaning up"

    if [ -d "$LOG_DIR" ]; then
        local sz
        sz=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
        rm -f "$LOG_DIR"/*.log
        success "Cleared log files ($sz)"
    fi

    for f in backend.log frontend.log celery_worker.log; do
        [ -f "$f" ] && rm -f "$f" && success "Removed legacy $f"
    done

    rm -f "$PID_DIR"/*.pid 2>/dev/null && success "Cleared PID files"

    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -name "*.pyc" -delete 2>/dev/null || true
    success "Cleared Python caches"

    local stale
    stale=$(docker ps -a --filter "name=neuroinsight-" --filter "status=exited" -q 2>/dev/null || true)
    if [ -n "$stale" ]; then
        docker rm $stale &>/dev/null || true
        success "Removed stale job containers"
    fi

    for f in neuroinsight_research.db neuroinsight_research.db-wal neuroinsight_research.db-shm; do
        [ -f "$f" ] && rm -f "$f" && success "Removed legacy SQLite file: $f"
    done

    echo ""
    success "Cleanup complete"
    echo ""
}

# ==============================================================================
#  ENV (shared)
# ==============================================================================
cmd_env() {
    header
    step "Environment configuration"
    echo ""
    echo -e "  ${BOLD}Application${NC}"
    echo "    ENVIRONMENT       = ${ENVIRONMENT:-development}"
    echo "    MODE              = $MODE"
    echo "    LOG_LEVEL         = ${LOG_LEVEL:-INFO}"
    echo ""
    echo -e "  ${BOLD}Ports${NC}"
    echo "    FRONTEND_PORT     = $FRONTEND_PORT  (default: $FRONTEND_PORT_DEFAULT)"
    echo "    BACKEND_PORT      = $BACKEND_PORT  (default: $BACKEND_PORT_DEFAULT)"
    echo "    PORT_RANGE        = $PORT_RANGE_START-$PORT_RANGE_END"
    echo ""
    echo -e "  ${BOLD}Database${NC}"
    echo "    DATABASE_URL      = ${DATABASE_URL:-<not set>}" | sed 's/:[^@]*@/:****@/'
    echo ""
    echo -e "  ${BOLD}Redis${NC}"
    echo "    REDIS_HOST        = ${REDIS_HOST:-<not set>}"
    echo "    REDIS_PORT        = ${REDIS_PORT:-6379}"
    echo ""
    echo -e "  ${BOLD}MinIO${NC}"
    echo "    MINIO_HOST        = ${MINIO_HOST:-<not set>}"
    echo "    MINIO_PORT        = ${MINIO_PORT:-9000}"
    echo ""
    echo -e "  ${BOLD}Execution${NC}"
    echo "    BACKEND_TYPE      = ${BACKEND_TYPE:-local}"
    echo "    CELERY_CONCURRENCY= $CELERY_CONCURRENCY"
    echo "    MAX_CONCURRENT    = ${MAX_CONCURRENT_JOBS:-4}"
    echo ""
    echo -e "  ${BOLD}Directories${NC}"
    echo "    DATA_DIR          = $DATA_DIR"
    echo "    LOG_DIR           = $LOG_DIR"
    echo "    PID_DIR           = $PID_DIR"
    echo "    PIPELINES_DIR     = ${PIPELINES_DIR:-./pipelines}"
    echo ""
    echo -e "  ${DIM}Source: $SCRIPT_DIR/.env${NC}"
    echo ""
}

# ==============================================================================
#  VERSION (shared)
# ==============================================================================
cmd_version() {
    echo "NeuroInsight Research v${VERSION}  ($MODE)"
    echo "Python: $(python3 --version 2>&1 | head -1)"
    echo "Node:   $(node --version 2>/dev/null || echo 'not installed')"
    echo "Docker: $(docker --version 2>/dev/null || echo 'not installed')"
}

# ==============================================================================
#  Shared preflight checks
# ==============================================================================
preflight_checks() {
    step "Preflight checks"

    if ! command -v python3 &>/dev/null; then
        error "python3 not found"; exit 1
    fi

    if ! command -v npm &>/dev/null && [ -d "frontend" ]; then
        error "npm not found (needed for frontend)"; exit 1
    fi

    # Check Node.js version (>=18 required for Vite)
    if command -v node &>/dev/null; then
        local node_major
        node_major=$(node --version | sed 's/v//' | cut -d'.' -f1)
        if [ "$node_major" -lt 18 ] 2>/dev/null; then
            warn "Node.js v${node_major} detected. Version 18+ recommended (Vite requires it)."
            info "Install Node 18+: https://nodejs.org/ or use nvm"
        else
            success "Node.js $(node --version)"
        fi
    fi

    if ! command -v docker &>/dev/null; then
        error "docker not found -- required for infrastructure and job execution"; exit 1
    fi

    if _infra_running; then
        success "Infrastructure services running"
    else
        info "Starting infrastructure services ..."
        if _infra_up_quiet; then
            success "Infrastructure services started"
        else
            warn "Infrastructure not available -- DB/Redis/MinIO may fail"
            info "Run:  ./research infra up"
        fi
    fi
}

# ==============================================================================
#  Print summary after start
# ==============================================================================
print_start_summary() {
    local mode_flag="$1"   # "PRODUCTION" or "DEVELOPMENT"

    echo ""
    echo -e "${BOLD}${GREEN}  All services running.${NC}  ${DIM}[$mode_flag]${NC}"
    echo ""
    echo -e "  ${BOLD}URLs${NC}"
    echo -e "    Frontend   http://localhost:$FRONTEND_PORT"
    echo -e "    Backend    http://localhost:$BACKEND_PORT"
    echo -e "    API docs   http://localhost:$BACKEND_PORT/docs"
    echo ""
    echo -e "  ${BOLD}Port Allocation${NC}"
    echo -e "    3000  Frontend (default)  ->  $FRONTEND_PORT"
    echo -e "    3001  Backend  (default)  ->  $BACKEND_PORT"
    echo -e "    Range $PORT_RANGE_START-$PORT_RANGE_END for overflow"
    echo ""
    echo -e "  ${BOLD}Logs${NC}"
    if [ "$MODE" = "development" ]; then
        echo -e "    ./research-dev logs backend"
        echo -e "    ./research-dev logs celery"
        echo -e "    ./research-dev logs frontend"
        echo -e "    ./research-dev logs all"
    else
        echo -e "    ./research logs backend"
        echo -e "    ./research logs celery"
        echo -e "    ./research logs frontend"
        echo -e "    ./research logs all"
    fi
    echo ""
    echo -e "  ${BOLD}Stop${NC}"
    if [ "$MODE" = "development" ]; then
        echo -e "    ./research-dev stop"
    else
        echo -e "    ./research stop"
    fi
    echo ""
}

# ==============================================================================
#  HELP -- generated per-mode
# ==============================================================================
cmd_help() {
    header
    local cli="./research"
    [ "$MODE" = "development" ] && cli="./research-dev"

    echo -e "  ${BOLD}Usage:${NC}  $cli <command> [options]"
    echo ""
    echo -e "  ${BOLD}Lifecycle${NC}"
    echo "    install              Install deps, start infra, init DB & MinIO"
    echo "    start                Start all services (infra + app)"
    echo "    stop                 Stop app services (keeps infra running)"
    echo "    restart              Restart all app services"
    echo ""
    echo -e "  ${BOLD}Infrastructure${NC}"
    echo "    infra up             Start PostgreSQL, Redis, MinIO (docker compose)"
    echo "    infra down           Stop infrastructure containers"
    echo "    infra restart        Restart infrastructure"
    echo "    infra reset          Stop and DELETE all data volumes"
    echo "    infra status         Show infrastructure container status"
    echo "    infra logs           Tail infrastructure logs"
    echo ""
    echo -e "  ${BOLD}Monitoring${NC}"
    echo "    status               Service status & infrastructure health"
    echo "    health               Query /health API endpoint"
    echo "    logs [service]       Tail logs (backend|celery|frontend|all)"
    echo ""
    echo -e "  ${BOLD}Database${NC}"
    echo "    db init              Create/verify tables"
    echo "    db reset             Drop and recreate (destructive)"
    echo "    db shell             Interactive PostgreSQL shell"
    echo "    db jobs              Show recent jobs"
    echo ""
    echo -e "  ${BOLD}Docker${NC}"
    echo "    pull [image|all]     Pre-pull pipeline images"
    echo "    clean                Remove logs, caches, stale containers"
    echo ""
    echo -e "  ${BOLD}Info${NC}"
    echo "    env                  Print resolved environment variables"
    echo "    version              Print version info"
    echo "    help                 Show this help"
    echo ""
    if [ "$MODE" = "development" ]; then
        echo -e "  ${BOLD}Dev Mode Features${NC}"
        echo "    Backend:  uvicorn --reload (auto-restart on code changes)"
        echo "    Frontend: Vite HMR (hot module replacement)"
        echo "    Celery:   debug-level logging"
        echo ""
    else
        echo -e "  ${BOLD}Production Mode Features${NC}"
        echo "    Backend:  uvicorn (no reload, optimised)"
        echo "    Frontend: vite preview (pre-built static bundle)"
        echo "    Celery:   info-level logging"
        echo ""
    fi
    echo -e "  ${BOLD}Examples${NC}"
    echo "    $cli install           # First-time setup (infra + deps + DB)"
    echo "    $cli infra up          # Start PostgreSQL, Redis, MinIO"
    echo "    $cli start             # Start app services"
    echo "    $cli logs celery       # Watch celery logs"
    echo "    $cli db jobs           # See recent jobs"
    echo "    $cli pull freesurfer   # Pull FreeSurfer image"
    echo "    $cli stop              # Stop app services"
    echo "    $cli infra down        # Stop infrastructure"
    echo ""
}

# ==============================================================================
#  INFRASTRUCTURE helpers (docker compose)
# ==============================================================================
_compose() {
    docker compose -f "$COMPOSE_FILE" "$@"
}

_infra_running() {
    # Returns 0 if all three infra containers are running
    local count=0
    for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${name}$"; then
            count=$((count + 1))
        fi
    done
    [ "$count" -ge 3 ]
}

_infra_up_quiet() {
    _compose up -d 2>&1 | tail -5
    # Give containers a moment to pass healthchecks
    sleep 3
}

# ==============================================================================
#  INFRA command (manage PostgreSQL / Redis / MinIO)
# ==============================================================================
cmd_infra() {
    local sub="${1:-status}"

    case "$sub" in
        up|start)
            header
            step "Starting infrastructure services"

            if ! command -v docker &>/dev/null; then
                error "docker not found -- install Docker first"
                exit 1
            fi

            if ! [ -f "$COMPOSE_FILE" ]; then
                error "docker-compose.infra.yml not found at $COMPOSE_FILE"
                exit 1
            fi

            _compose up -d 2>&1

            echo ""
            # Wait for containers to become healthy
            info "Waiting for services to become healthy ..."
            sleep 5

            if docker exec neuroinsight-db pg_isready -U neuroinsight &>/dev/null; then
                success "PostgreSQL   ready  (localhost:5432)"
            else
                warn  "PostgreSQL   starting ..."
            fi

            if docker exec neuroinsight-redis redis-cli -a "redis_secure_password" ping 2>/dev/null | grep -q PONG; then
                success "Redis        ready  (localhost:6379)"
            else
                warn  "Redis        starting ..."
            fi

            if curl -sf "http://localhost:9000/minio/health/live" &>/dev/null; then
                success "MinIO        ready  (localhost:9000, console :9001)"
            else
                warn  "MinIO        starting ..."
            fi

            echo ""
            success "Infrastructure is up."
            info "PostgreSQL:  localhost:5432  (user: neuroinsight)"
            info "Redis:       localhost:6379"
            info "MinIO:       localhost:9000  (console: http://localhost:9001)"
            echo ""
            ;;

        down|stop)
            header
            step "Stopping infrastructure services"
            _compose down 2>&1
            success "Infrastructure stopped"
            echo ""
            ;;

        restart)
            cmd_infra down
            sleep 1
            cmd_infra up
            ;;

        reset)
            header
            step "Resetting infrastructure (removes all data!)"
            read -rp "  This will DELETE all PostgreSQL, Redis, and MinIO data. Continue? [y/N] " confirm
            if [[ "$confirm" =~ ^[Yy]$ ]]; then
                _compose down -v 2>&1
                success "Infrastructure stopped and volumes removed"
                info "Run  ./research infra up  to recreate from scratch"
            else
                info "Cancelled"
            fi
            echo ""
            ;;

        status)
            header
            step "Infrastructure status"
            if _infra_running; then
                _compose ps 2>&1
            else
                info "Infrastructure is not running."
                info "Start with:  ./research infra up"
            fi
            echo ""
            ;;

        logs)
            _compose logs -f --tail=100
            ;;

        *)
            echo "Usage: ./research infra <subcommand>"
            echo ""
            echo "  up / start     Start PostgreSQL, Redis, MinIO"
            echo "  down / stop    Stop infrastructure services"
            echo "  restart        Restart infrastructure"
            echo "  reset          Stop and DELETE all data volumes"
            echo "  status         Show container status"
            echo "  logs           Tail infrastructure logs"
            echo ""
            ;;
    esac
}

# ==============================================================================
#  MAIN DISPATCHER (called by each script after defining cmd_start)
# ==============================================================================
dispatch() {
    local cmd="${1:-help}"
    shift || true

    case "$cmd" in
        install)  cmd_install "$@" ;;
        start)    cmd_start   "$@" ;;
        stop)     cmd_stop    "$@" ;;
        restart)  cmd_restart "$@" ;;
        status)   cmd_status  "$@" ;;
        health)   cmd_health  "$@" ;;
        logs)     cmd_logs    "$@" ;;
        db)       cmd_db      "$@" ;;
        infra)    cmd_infra   "$@" ;;
        pull)     cmd_pull    "$@" ;;
        clean)    cmd_clean   "$@" ;;
        env)      cmd_env     "$@" ;;
        version)  cmd_version "$@" ;;
        help|-h|--help)
                  cmd_help    "$@" ;;
        *)
            error "Unknown command: $cmd"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}
