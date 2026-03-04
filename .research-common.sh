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
#     Production:  Backend serves frontend SPA on port 3000 (range 3000-3050)
#     Development: Frontend 3000 (range 3000-3050), Backend 3051 (range 3051-3100)
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
if [ "$MODE" = "production" ]; then
    BACKEND_PORT="${API_PORT:-3000}"
else
    BACKEND_PORT="${API_PORT:-3051}"
fi
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-5}"
DATA_DIR="${DATA_DIR:-./data}"
LOG_DIR="${LOG_DIR:-./logs}"
PID_DIR="${PID_DIR:-./.pids}"

FRONTEND_PORT_RANGE_START=3000
FRONTEND_PORT_RANGE_END=3050
BACKEND_PORT_RANGE_START=3051
BACKEND_PORT_RANGE_END=3100

# Load .env if present
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a; source "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
    FRONTEND_PORT="${FRONTEND_PORT:-3000}"
    if [ "$MODE" = "production" ]; then
        BACKEND_PORT="${API_PORT:-3000}"
    else
        BACKEND_PORT="${API_PORT:-3051}"
    fi
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

sed_i() {
    # Portable in-place sed (BSD/macOS requires '' after -i, GNU does not)
    if sed --version 2>/dev/null | grep -q GNU; then
        sed -i "$@"
    else
        sed -i '' "$@"
    fi
}

ensure_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR" "$DATA_DIR"/{uploads,outputs}
}

rotate_log_file() {
    # rotate_log_file <path> [max_mb] [keep]
    local log_path="$1"
    local max_mb="${2:-50}"
    local keep="${3:-5}"
    [ -f "$log_path" ] || return 0

    local max_bytes=$((max_mb * 1024 * 1024))
    local size
    size=$(wc -c < "$log_path" 2>/dev/null || echo 0)
    [ "${size:-0}" -gt "$max_bytes" ] || return 0

    local ts
    ts=$(date +%Y%m%d-%H%M%S)
    local rotated="${log_path}.${ts}"
    mv "$log_path" "$rotated" 2>/dev/null || return 0
    : > "$log_path"

    # Keep only the newest N rotated files
    local old
    old=$(ls -1t "${log_path}".20* 2>/dev/null | awk "NR>${keep}")
    if [ -n "$old" ]; then
        echo "$old" | xargs rm -f 2>/dev/null || true
    fi
}

rotate_runtime_logs() {
    ensure_dirs
    rotate_log_file "$LOG_DIR/backend.log" 50 5
    rotate_log_file "$LOG_DIR/celery.log" 50 5
    rotate_log_file "$LOG_DIR/frontend.log" 25 5
    rotate_log_file "$LOG_DIR/alembic.log" 10 5
}

enforce_secret_key_policy() {
    # Production mode must not run with weak/default secret key values.
    if [ "$MODE" != "production" ]; then
        return 0
    fi
    local sk="${SECRET_KEY:-}"
    local lower
    lower=$(printf "%s" "$sk" | tr '[:upper:]' '[:lower:]')
    if [ -z "$sk" ] || [ "${#sk}" -lt 32 ] || [[ "$lower" == *"changeme"* ]] || [[ "$lower" == *"dev-secret"* ]] || [[ "$lower" == *"insecure"* ]]; then
        error "Insecure SECRET_KEY for production mode."
        info "Set SECRET_KEY in .env to a random value with at least 32 characters."
        info "Tip: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
        exit 1
    fi
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
    # Socket-based check works across WSL2/Windows boundaries.
    # lsof only sees WSL2 processes, not Windows services on the same port.
    python3 -c "
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('127.0.0.1', int(sys.argv[1])))
    s.close()
    sys.exit(1)  # port is FREE -> exit 1 (not in use)
except OSError:
    sys.exit(0)  # port is IN USE -> exit 0
" "$1" 2>/dev/null
}

# find_port <default> <range_start> <range_end>
#   Returns <default> if free, otherwise the first free port in the given range.
find_port() {
    local default_port="$1" range_start="$2" range_end="$3"

    if ! port_in_use "$default_port"; then
        echo "$default_port"; return 0
    fi

    for p in $(seq "$range_start" "$range_end"); do
        if ! port_in_use "$p"; then
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

    if [ "$MODE" = "production" ]; then
        # Production: backend serves SPA on a single port (default 3000, range 3000-3050)
        BACKEND_PORT=$(find_port "$BACKEND_PORT" "$FRONTEND_PORT_RANGE_START" "$FRONTEND_PORT_RANGE_END") || {
            error "No free port for app ($FRONTEND_PORT_RANGE_START-$FRONTEND_PORT_RANGE_END)"; exit 1
        }
        if [ "$BACKEND_PORT" != "$BACKEND_PORT_DEFAULT" ]; then
            warn "App default $BACKEND_PORT_DEFAULT busy -> using $BACKEND_PORT"
        fi
        success "App        -> port $BACKEND_PORT  (backend serves frontend SPA)"
    else
        # Development: separate frontend + backend ports
        FRONTEND_PORT=$(find_port "$FRONTEND_PORT" "$FRONTEND_PORT_RANGE_START" "$FRONTEND_PORT_RANGE_END") || {
            error "No free port for frontend ($FRONTEND_PORT_RANGE_START-$FRONTEND_PORT_RANGE_END)"; exit 1
        }
        if [ "$FRONTEND_PORT" != "$FRONTEND_PORT_DEFAULT" ]; then
            warn "Frontend default $FRONTEND_PORT_DEFAULT busy -> using $FRONTEND_PORT"
        fi
        success "Frontend   -> port $FRONTEND_PORT"

        BACKEND_PORT=$(find_port "$BACKEND_PORT" "$BACKEND_PORT_RANGE_START" "$BACKEND_PORT_RANGE_END") || {
            error "No free port for backend ($BACKEND_PORT_RANGE_START-$BACKEND_PORT_RANGE_END)"; exit 1
        }
        if [ "$BACKEND_PORT" != "$BACKEND_PORT_DEFAULT" ]; then
            warn "Backend default $BACKEND_PORT_DEFAULT busy -> using $BACKEND_PORT"
        fi
        success "Backend    -> port $BACKEND_PORT"
    fi
}

# -- Guided dependency installation --------------------------------------------

_detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            ubuntu|debian|pop|linuxmint) echo "apt" ;;
            fedora)                      echo "dnf" ;;
            centos|rhel|rocky|alma)      echo "yum" ;;
            arch|manjaro)                echo "pacman" ;;
            *)                           echo "unknown" ;;
        esac
    elif [ "$(uname)" = "Darwin" ]; then
        echo "brew"
    else
        echo "unknown"
    fi
}

_prompt_yn() {
    local prompt="$1"
    local answer
    printf "  %b [y/N] " "$prompt"
    read -r answer
    case "$answer" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) return 1 ;;
    esac
}

_ensure_python() {
    if command -v python3 &>/dev/null; then
        local py_ver
        py_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        local py_major py_minor
        py_major=$(echo "$py_ver" | cut -d. -f1)
        py_minor=$(echo "$py_ver" | cut -d. -f2)
        if [ "$py_major" -ge 3 ] && [ "$py_minor" -ge 9 ] 2>/dev/null; then
            success "Python $py_ver found"
            return 0
        else
            warn "Python $py_ver found but 3.9+ is required"
        fi
    else
        warn "Python 3 not found"
    fi

    local pkg_mgr
    pkg_mgr=$(_detect_os)
    local install_cmd=""

    case "$pkg_mgr" in
        apt)
            install_cmd="sudo apt update && sudo apt install -y python3 python3-venv python3-pip" ;;
        dnf)
            install_cmd="sudo dnf install -y python3 python3-pip" ;;
        yum)
            install_cmd="sudo yum install -y python3 python3-pip" ;;
        pacman)
            install_cmd="sudo pacman -Sy --noconfirm python python-pip" ;;
        brew)
            install_cmd="brew install python@3.11" ;;
    esac

    if [ -z "$install_cmd" ]; then
        error "Could not detect package manager. Please install Python 3.9+ manually."
        error "  https://www.python.org/downloads/"
        return 1
    fi

    echo ""
    info "To install Python, the following command will run:"
    echo -e "    ${BOLD}${install_cmd}${NC}"
    echo ""

    if _prompt_yn "Install Python now?"; then
        info "Installing Python ..."
        if eval "$install_cmd"; then
            success "Python installed"
        else
            error "Python installation failed. Please install manually:"
            error "  $install_cmd"
            return 1
        fi
    else
        info "Skipped. Install Python 3.9+ manually, then re-run ./research install"
        return 1
    fi
}

_ensure_node() {
    if command -v node &>/dev/null; then
        local node_ver
        node_ver=$(node -v 2>/dev/null | sed 's/^v//')
        local node_major
        node_major=$(echo "$node_ver" | cut -d. -f1)
        if [ "$node_major" -ge 18 ] 2>/dev/null; then
            success "Node.js $node_ver found"
            return 0
        else
            warn "Node.js $node_ver found but 18+ is required"
        fi
    else
        warn "Node.js not found"
    fi

    local pkg_mgr
    pkg_mgr=$(_detect_os)

    # nvm works on all platforms without sudo
    local nvm_install="curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"
    local nvm_use="nvm install 22 && nvm use 22"
    local alt_cmd=""

    case "$pkg_mgr" in
        apt)    alt_cmd="sudo apt update && sudo apt install -y nodejs npm" ;;
        dnf)    alt_cmd="sudo dnf install -y nodejs npm" ;;
        yum)    alt_cmd="sudo yum install -y nodejs npm" ;;
        pacman) alt_cmd="sudo pacman -Sy --noconfirm nodejs npm" ;;
        brew)   alt_cmd="brew install node" ;;
    esac

    echo ""
    info "Option 1 (recommended, no sudo): Install via nvm"
    echo -e "    ${BOLD}${nvm_install}${NC}"
    echo -e "    ${BOLD}${nvm_use}${NC}"
    if [ -n "$alt_cmd" ]; then
        info "Option 2 (system package manager):"
        echo -e "    ${BOLD}${alt_cmd}${NC}"
    fi
    echo ""

    if _prompt_yn "Install Node.js via nvm now? (recommended)"; then
        info "Installing nvm ..."
        export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
        if curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh 2>/dev/null | bash 2>&1 | tail -3; then
            # Load nvm into current shell
            [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
            info "Installing Node.js 22 ..."
            if nvm install 22 2>&1 | tail -3 && nvm use 22 &>/dev/null; then
                success "Node.js $(node -v) installed via nvm"
                return 0
            fi
        fi
        error "nvm installation failed."
    elif [ -n "$alt_cmd" ] && _prompt_yn "Install via system package manager instead?"; then
        info "Installing Node.js ..."
        if eval "$alt_cmd"; then
            success "Node.js installed"
            return 0
        fi
        error "Node.js installation failed."
    else
        info "Skipped. Install Node.js 18+ manually, then re-run ./research install"
    fi
    return 1
}

# ==============================================================================
#  INSTALL (shared)
# ==============================================================================
cmd_install() {
    header
    step "Installing NeuroInsight Research"
    ensure_dirs

    # -- Check / install system dependencies -----------------------------------
    step "System dependencies"
    _ensure_python || { error "Python 3.9+ is required. Aborting."; return 1; }
    _ensure_node   || { error "Node.js 18+ is required. Aborting."; return 1; }

    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        success "Docker with Compose v2 found"
    else
        warn "Docker or Docker Compose v2 not found"
        info "Install Docker: https://docs.docker.com/get-docker/"
        info "Infrastructure services (PostgreSQL, Redis, MinIO) require Docker."
        info "The app will install but infrastructure steps will be skipped."
    fi

    # -- Python virtual environment & dependencies ------------------------------
    step "Python dependencies"
    if [ ! -d "venv" ]; then
        info "Creating virtual environment ..."
        python3 -m venv venv
    fi
    source venv/bin/activate
    python3 -m pip install -q -r requirements.txt 2>&1 | tail -5
    success "Python dependencies installed (venv)"

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
            # New passwords won't match old Docker volumes — wipe them
            if docker info &>/dev/null; then
                _compose down -v 2>/dev/null || true
                for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
                    docker rm -f "$name" 2>/dev/null || true
                done
            fi
            cp .env.example .env
            _rand() { python3 -c "import secrets; print(secrets.token_urlsafe(24))"; }
            local pg_pass; pg_pass=$(_rand)
            local redis_pass; redis_pass=$(_rand)
            local minio_key; minio_key=$(_rand)
            local minio_secret; minio_secret=$(_rand)
            local secret_key; secret_key=$(_rand)
            sed_i "s|CHANGEME_postgres_password|${pg_pass}|g" .env
            sed_i "s|CHANGEME_redis_password|${redis_pass}|g" .env
            sed_i "s|CHANGEME_minio_access_key|${minio_key}|g" .env
            sed_i "s|CHANGEME_minio_secret_key|${minio_secret}|g" .env
            sed_i "s|CHANGEME_secret_key_at_least_32_characters_long|${secret_key}|g" .env
            success "Created .env with generated random passwords"
        else
            warn "No .env or .env.example found"
        fi
    else
        success ".env already exists"
    fi

    # -- Infrastructure services -----------------------------------------------
    step "Infrastructure services (PostgreSQL / Redis / MinIO)"
    export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export MINIO_PORT="${MINIO_PORT:-9000}"
    export MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}"

    if _infra_running && _wait_for_infra_quick; then
        success "Infrastructure services already running"
    else
        if _infra_running; then
            warn "Infrastructure containers exist but services are not responding"
            info "Restarting infrastructure (clean) ..."
            _compose down -v 2>/dev/null || true
            for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
                docker rm -f "$name" 2>/dev/null || true
            done
            _regenerate_env_passwords
        else
            info "Starting infrastructure via docker compose ..."
        fi
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

    # -- Pipeline licenses -----------------------------------------------------
    step "Pipeline licenses"
    local _any_license_missing=false
    local _fs_license_found=false
    for _lpath in \
        "./license.txt" \
        "$HOME/.freesurfer/license.txt" \
        "$HOME/freesurfer/license.txt" \
        "/usr/local/freesurfer/license.txt" \
        "${FS_LICENSE:-__none__}"; do
        if [ -f "$_lpath" ] && [ -s "$_lpath" ]; then
            _fs_license_found=true
            success "FreeSurfer license -> $_lpath"
            break
        fi
    done
    if [ "$_fs_license_found" = false ]; then
        warn "FreeSurfer license.txt not found (FreeSurfer, FastSurfer, fMRIPrep, MELD)"
        _any_license_missing=true
    fi

    local _meld_license_found=false
    for _lpath in \
        "./meld_license.txt" \
        "./data/meld_license.txt" \
        "$HOME/.meld/meld_license.txt"; do
        if [ -f "$_lpath" ] && [ -s "$_lpath" ]; then
            _meld_license_found=true
            success "MELD license     -> $_lpath"
            break
        fi
    done
    if [ "$_meld_license_found" = false ]; then
        warn "MELD meld_license.txt not found (MELD Graph v2.2.4+)"
        _any_license_missing=true
    fi

    if [ "$_any_license_missing" = true ]; then
        info "Set up licenses: ${BOLD}./research license${NC}"
    fi

    # -- Pipeline Docker images ------------------------------------------------
    step "Pipeline Docker images"
    local _img_list
    _img_list=$(python3 -c "
import yaml, pathlib
seen = set()
for yf in sorted(pathlib.Path('plugins').glob('*.yaml')):
    try:
        data = yaml.safe_load(yf.read_text())
        if data and data.get('type') == 'plugin':
            img = (data.get('container') or {}).get('image', '')
            if img and img not in seen:
                seen.add(img)
                print(img)
    except Exception:
        pass
" 2>/dev/null)

    local _missing_count=0
    if [ -n "$_img_list" ]; then
        while IFS= read -r img; do
            if docker image inspect "$img" &>/dev/null; then
                success "$img  (cached)"
            else
                warn "$img  (not pulled)"
                _missing_count=$((_missing_count + 1))
            fi
        done <<< "$_img_list"
        if [ "$_missing_count" -gt 0 ]; then
            info "Pull missing images: ./research pull missing"
        fi
    else
        warn "Could not discover images from plugins/"
    fi

    echo ""
    success "Installation complete."
    info "Next: ${BOLD}./research license${NC} to set up pipeline licenses (if needed)."
    if [ "$MODE" = "development" ]; then
        info "Then: ${BOLD}./research-dev start${NC} to launch in development mode."
    else
        info "Then: ${BOLD}./research start${NC} to launch in production mode."
    fi
    echo ""
}

# ==============================================================================
#  LICENSE — interactive license setup
# ==============================================================================
cmd_license() {
    header
    step "Pipeline license setup"
    echo ""
    info "Some plugins require a free license file before you can run them."
    info "If your plugin doesn't need one, you can skip this step."
    echo ""

    local any_missing=false

    # -- FreeSurfer license ------------------------------------------------
    step "FreeSurfer license  (license.txt)"
    info "Required by: FreeSurfer, FastSurfer, fMRIPrep, MELD Graph"
    local _fs_found=false
    for _lpath in \
        "./license.txt" \
        "$HOME/.freesurfer/license.txt" \
        "$HOME/freesurfer/license.txt" \
        "/usr/local/freesurfer/license.txt" \
        "${FS_LICENSE:-__none__}"; do
        if [ -f "$_lpath" ] && [ -s "$_lpath" ]; then
            _fs_found=true
            success "Found at $_lpath"
            break
        fi
    done

    if [ "$_fs_found" = false ]; then
        any_missing=true
        warn "Not found"
        echo ""
        info "  1. Register (free) at: https://surfer.nmr.mgh.harvard.edu/registration.html"
        info "  2. A license.txt file will be emailed to you"
        info "  3. Place it here:"
        echo ""
        info "     cp ~/Downloads/license.txt ./license.txt"
        echo ""
        echo -n "  Have you placed license.txt? [y/N/skip] "
        read -r _answer
        case "$_answer" in
            y|Y|yes|Yes)
                if [ -f "./license.txt" ] && [ -s "./license.txt" ]; then
                    success "FreeSurfer license.txt detected"
                else
                    warn "license.txt not found in project root -- you can add it later"
                fi
                ;;
            skip|s|S)
                info "Skipped -- you can run ./research license again later"
                ;;
            *)
                info "Skipped -- you can run ./research license again later"
                ;;
        esac
    fi
    echo ""

    # -- MELD Graph license ------------------------------------------------
    step "MELD Graph license  (meld_license.txt)"
    info "Required by: MELD Graph (cortical lesion detection, v2.2.4+)"
    local _meld_found=false
    for _lpath in \
        "./meld_license.txt" \
        "./data/meld_license.txt" \
        "$HOME/.meld/meld_license.txt"; do
        if [ -f "$_lpath" ] && [ -s "$_lpath" ]; then
            _meld_found=true
            success "Found at $_lpath"
            break
        fi
    done

    if [ "$_meld_found" = false ]; then
        any_missing=true
        warn "Not found"
        echo ""
        info "  1. Register (free) at:"
        info "     https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform"
        info "  2. Place the received file here:"
        echo ""
        info "     cp ~/Downloads/meld_license.txt ./meld_license.txt"
        echo ""
        echo -n "  Have you placed meld_license.txt? [y/N/skip] "
        read -r _answer
        case "$_answer" in
            y|Y|yes|Yes)
                if [ -f "./meld_license.txt" ] && [ -s "./meld_license.txt" ]; then
                    success "MELD Graph meld_license.txt detected"
                else
                    warn "meld_license.txt not found in project root -- you can add it later"
                fi
                ;;
            skip|s|S)
                info "Skipped -- you can run ./research license again later"
                ;;
            *)
                info "Skipped -- you can run ./research license again later"
                ;;
        esac
    fi
    echo ""

    # -- Summary -----------------------------------------------------------
    step "License summary"
    echo ""
    echo "  | License               | Status    | Required By                              |"
    echo "  |-----------------------|-----------|------------------------------------------|"

    if [ "$_fs_found" = true ]; then
        echo "  | license.txt           | FOUND     | FreeSurfer, FastSurfer, fMRIPrep, MELD   |"
    else
        echo "  | license.txt           | MISSING   | FreeSurfer, FastSurfer, fMRIPrep, MELD   |"
    fi

    if [ "$_meld_found" = true ]; then
        echo "  | meld_license.txt      | FOUND     | MELD Graph (v2.2.4+)                     |"
    else
        echo "  | meld_license.txt      | MISSING   | MELD Graph (v2.2.4+)                     |"
    fi

    echo "  | (none needed)         | --        | QSIPrep, QSIRecon, XCP-D, dcm2niix       |"
    echo ""

    if [ "$any_missing" = true ]; then
        info "You can run ${BOLD}./research license${NC} again after placing the files."
    else
        success "All licenses found."
    fi
    echo ""
}

# ==============================================================================
#  STOP (shared)
# ==============================================================================
cmd_stop() {
    local quiet=false
    local stop_all=false
    for arg in "$@"; do
        case "$arg" in
            --quiet) quiet=true ;;
            --all|-a) stop_all=true ;;
        esac
    done

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
            if command -v fuser &>/dev/null; then
                fuser -k "$p/tcp" &>/dev/null || true
            elif command -v lsof &>/dev/null; then
                lsof -ti :"$p" 2>/dev/null | xargs kill 2>/dev/null || true
            fi
        fi
    done

    $quiet || success "App services stopped"

    if [ "$stop_all" = true ]; then
        $quiet || step "Stopping infrastructure (PostgreSQL, Redis, MinIO)"
        _compose down -v 2>/dev/null || true
        for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
            docker rm -f "$name" 2>/dev/null || true
        done
        $quiet || success "Infrastructure stopped (containers + volumes removed)"
    else
        $quiet || info "Infrastructure still running (use ${BOLD}./research stop --all${NC} to stop everything)"
    fi

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
#  SUPPORT BUNDLE (shared)
# ==============================================================================
cmd_support_bundle() {
    local out="${1:-support-bundle-$(date +%Y%m%d-%H%M%S).tar.gz}"
    local tmp
    tmp=$(mktemp -d 2>/dev/null || echo "/tmp/nir-support-$$")
    mkdir -p "$tmp"
    mkdir -p "$tmp/logs"

    header
    step "Collecting support bundle"

    # Sanitized environment snapshot
    if [ -f "$SCRIPT_DIR/.env" ]; then
        python3 - "$SCRIPT_DIR/.env" "$tmp/env.sanitized" <<'PY'
import re, sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text().splitlines()
out = []
for line in src:
    if not line or line.lstrip().startswith("#") or "=" not in line:
        out.append(line); continue
    k, v = line.split("=", 1)
    if any(s in k for s in ("PASSWORD", "SECRET", "KEY", "TOKEN")):
        out.append(f"{k}=***REDACTED***")
    else:
        out.append(f"{k}={v}")
pathlib.Path(sys.argv[2]).write_text("\n".join(out) + "\n")
PY
        success "Captured sanitized env"
    fi

    # Core command outputs
    ./research status > "$tmp/status.txt" 2>&1 || true
    ./research health > "$tmp/health.txt" 2>&1 || true
    ./research db jobs > "$tmp/db-jobs.txt" 2>&1 || true
    ./research preflight --json > "$tmp/preflight.json" 2>/dev/null || true

    # Logs (tail to keep bundle small)
    for f in backend.log celery.log frontend.log alembic.log; do
        if [ -f "$LOG_DIR/$f" ]; then
            tail -n 400 "$LOG_DIR/$f" > "$tmp/logs/$f" 2>/dev/null || true
        fi
    done

    # Infra status
    docker ps > "$tmp/docker-ps.txt" 2>&1 || true
    docker system df > "$tmp/docker-df.txt" 2>&1 || true

    tar -czf "$out" -C "$tmp" . 2>/dev/null || {
        error "Failed to create support bundle"
        rm -rf "$tmp" 2>/dev/null || true
        return 1
    }
    rm -rf "$tmp" 2>/dev/null || true
    success "Support bundle created: $out"
    echo ""
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
#  PULL (shared — reads images dynamically from plugin registry)
# ==============================================================================
cmd_pull() {
    local target="${1:-all}"
    header
    step "Pulling pipeline Docker images"

    # Discover images from plugin YAML definitions (authoritative source)
    local dynamic_images
    dynamic_images=$(python3 -c "
import yaml, pathlib, json
plugins_dir = pathlib.Path('plugins')
images = {}
for yf in sorted(plugins_dir.glob('*.yaml')):
    try:
        data = yaml.safe_load(yf.read_text())
        if data and data.get('type') == 'plugin':
            img = (data.get('container') or {}).get('image', '')
            pid = data.get('id', yf.stem)
            if img:
                # Use first word of plugin id as short name
                short = pid.split('_')[0] if '_' in pid else pid
                images[short] = img
    except Exception:
        pass
print(json.dumps(images))
" 2>/dev/null)

    if [ -z "$dynamic_images" ] || [ "$dynamic_images" = "{}" ]; then
        warn "Could not discover images from plugin registry. Using fallback list."
        dynamic_images='{"freesurfer":"freesurfer/freesurfer:7.4.1","fastsurfer":"deepmi/fastsurfer:v2.4.2"}'
    fi

    if [ "$target" == "all" ] || [ "$target" == "missing" ]; then
        local names
        names=$(echo "$dynamic_images" | python3 -c "import sys,json; [print(k) for k in json.load(sys.stdin)]")

        for name in $names; do
            local img
            img=$(echo "$dynamic_images" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$name',''))")
            [ -z "$img" ] && continue

            if [ "$target" == "missing" ]; then
                # Only pull if not cached
                if docker image inspect "$img" &>/dev/null; then
                    success "$name ($img) already cached"
                    continue
                fi
            fi

            info "Pulling $name ($img) ..."
            if docker pull "$img" 2>&1 | tail -1; then
                success "$name ready"
            else
                warn "Failed to pull $name -- skipping"
            fi
        done
    else
        local img
        img=$(echo "$dynamic_images" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$target',''))" 2>/dev/null)
        if [ -n "$img" ]; then
            info "Pulling $target ($img) ..."
            docker pull "$img"
            success "$target ready"
        else
            # Try target as a raw image name
            info "Pulling $target ..."
            docker pull "$target"
            success "$target ready"
        fi
    fi
    echo ""
}

# ==============================================================================
#  CLEAN (shared)
# ==============================================================================
cmd_clean() {
    local mode="${1:-safe}"
    if [ "$mode" = "--safe" ]; then mode="safe"; fi
    if [ "$mode" = "--aggressive" ]; then mode="aggressive"; fi

    header
    step "Cleaning up ($mode)"

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

    if [ "$mode" = "aggressive" ]; then
        info "Running aggressive Docker cleanup ..."
        docker system prune -f >/dev/null 2>&1 || true
        success "Docker system prune completed"
    fi

    for f in neuroinsight_research.db neuroinsight_research.db-wal neuroinsight_research.db-shm; do
        [ -f "$f" ] && rm -f "$f" && success "Removed legacy SQLite file: $f"
    done

    echo ""
    success "Cleanup complete"
    echo ""
}

# ==============================================================================
#  AUTOSTART (user-level systemd)
# ==============================================================================
cmd_autostart() {
    local sub="${1:-status}"
    local user_dir="$HOME/.config/systemd/user"
    local unit_file="$user_dir/neuroinsight-research.service"
    local script_path="$SCRIPT_DIR/research"

    case "$sub" in
        enable)
            header
            step "Enabling autostart (systemd --user)"
            if ! command -v systemctl >/dev/null 2>&1; then
                error "systemctl is not available on this machine."
                exit 1
            fi
            mkdir -p "$user_dir"
            cat > "$unit_file" <<EOF
[Unit]
Description=NeuroInsight Research (local user service)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$SCRIPT_DIR
ExecStart=$script_path start
ExecStop=$script_path stop
TimeoutStartSec=0

[Install]
WantedBy=default.target
EOF
            systemctl --user daemon-reload
            systemctl --user enable neuroinsight-research.service >/dev/null
            success "Autostart enabled (user service)"
            info "Start now: systemctl --user start neuroinsight-research.service"
            info "Check status: systemctl --user status neuroinsight-research.service"
            echo ""
            ;;

        disable)
            header
            step "Disabling autostart (systemd --user)"
            systemctl --user disable neuroinsight-research.service >/dev/null 2>&1 || true
            systemctl --user stop neuroinsight-research.service >/dev/null 2>&1 || true
            rm -f "$unit_file"
            systemctl --user daemon-reload >/dev/null 2>&1 || true
            success "Autostart disabled"
            echo ""
            ;;

        status)
            if [ -f "$unit_file" ]; then
                success "Autostart unit present: $unit_file"
            else
                info "Autostart unit not installed"
            fi
            systemctl --user status neuroinsight-research.service --no-pager 2>/dev/null || true
            ;;

        *)
            echo "Usage: ./research autostart <enable|disable|status>"
            ;;
    esac
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
#  Shared preflight checks (quick CLI gates + full Python pre-flight)
# ==============================================================================
preflight_checks() {
    step "Preflight checks"

    # ── Auto-create .env from .env.example if missing ─────────────────────
    if [ ! -f "$SCRIPT_DIR/.env" ] && [ -f "$SCRIPT_DIR/.env.example" ]; then
        info "No .env found — generating one with random passwords ..."

        # New passwords won't match old Docker volumes, so wipe them
        if docker info &>/dev/null; then
            _compose down -v 2>/dev/null || true
        fi

        cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
        if command -v python3 &>/dev/null; then
            _rand() { python3 -c "import secrets; print(secrets.token_urlsafe(24))"; }
            local pg_pass; pg_pass=$(_rand)
            local redis_pass; redis_pass=$(_rand)
            local minio_key; minio_key=$(_rand)
            local minio_secret; minio_secret=$(_rand)
            local secret_key; secret_key=$(_rand)
            sed_i "s|CHANGEME_postgres_password|${pg_pass}|g" "$SCRIPT_DIR/.env"
            sed_i "s|CHANGEME_redis_password|${redis_pass}|g" "$SCRIPT_DIR/.env"
            sed_i "s|CHANGEME_minio_access_key|${minio_key}|g" "$SCRIPT_DIR/.env"
            sed_i "s|CHANGEME_minio_secret_key|${minio_secret}|g" "$SCRIPT_DIR/.env"
            sed_i "s|CHANGEME_secret_key_at_least_32_characters_long|${secret_key}|g" "$SCRIPT_DIR/.env"
            # Reload newly created .env
            set -a; source "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
            FRONTEND_PORT="${FRONTEND_PORT:-3000}"
            if [ "$MODE" = "production" ]; then
                BACKEND_PORT="${API_PORT:-3000}"
            else
                BACKEND_PORT="${API_PORT:-3051}"
            fi
            success "Created .env with generated random passwords"
        else
            warn "python3 not available — .env created with placeholder passwords"
        fi
    fi

    # Production secret-key hard gate.
    enforce_secret_key_policy

    # ── Hard gates (can't proceed without these) ──────────────────────────
    if ! command -v python3 &>/dev/null; then
        error "python3 not found"; exit 1
    fi

    if ! command -v npm &>/dev/null && [ -d "frontend" ]; then
        error "npm not found (needed for frontend)"; exit 1
    fi

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

    # ── Virtual environment & auto-install dependencies if missing ─────────
    if [ ! -d "venv" ]; then
        info "Creating virtual environment ..."
        python3 -m venv venv
    fi
    source venv/bin/activate

    if [ -f "requirements.txt" ] && ! python3 -c "import fastapi" &>/dev/null; then
        info "Python dependencies missing — installing ..."
        python3 -m pip install -q -r requirements.txt 2>&1 | tail -3
        success "Python dependencies installed"
    fi

    if [ -d "frontend" ] && [ ! -d "frontend/node_modules" ]; then
        info "Frontend dependencies missing — installing ..."
        (cd frontend && npm install --silent 2>&1 | tail -3)
        success "Frontend node_modules installed"
    fi

    # ── Ensure infrastructure is up AND reachable ──────────────────────────
    # Load infra ports from .env
    export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export MINIO_PORT="${MINIO_PORT:-9000}"
    export MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}"

    if _infra_running; then
        # Containers exist -- but are the services actually reachable?
        if _wait_for_infra_quick; then
            success "Infrastructure services running"
        else
            warn "Infrastructure containers exist but services are not responding"
            info "Restarting infrastructure (clean) ..."
            _compose down -v 2>/dev/null || true
            for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
                docker rm -f "$name" 2>/dev/null || true
            done
            # Regenerate .env with fresh passwords to match new empty volumes
            _regenerate_env_passwords
            if _infra_up_quiet; then
                success "Infrastructure services restarted"
            else
                error "Infrastructure services failed to start (PostgreSQL, Redis, MinIO)"
                info "Make sure Docker is running, then retry: ./research start"
                exit 1
            fi
        fi
    else
        info "Starting infrastructure services ..."
        if _infra_up_quiet; then
            success "Infrastructure services started"
        else
            error "Infrastructure services failed to start (PostgreSQL, Redis, MinIO)"
            info "Make sure Docker is running, then retry: ./research start"
            exit 1
        fi
    fi

    # ── Full Python pre-flight check ──────────────────────────────────────
    local pf_exit=0
    python3 -m backend.cli.preflight || pf_exit=$?

    if [ "$pf_exit" -eq 1 ]; then
        warn "Pre-flight checks found warnings (see above)"
        warn "Continuing — some pipelines may require additional setup"
    fi
}

# ==============================================================================
#  PREFLIGHT standalone command
# ==============================================================================
cmd_preflight() {
    header
    python3 -m backend.cli.preflight "$@"
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
    if [ "$MODE" = "development" ]; then
        echo -e "    Frontend   http://localhost:$FRONTEND_PORT"
        echo -e "    Backend    http://localhost:$BACKEND_PORT"
        echo -e "    API docs   http://localhost:$BACKEND_PORT/docs"
    else
        echo -e "    App        http://localhost:$BACKEND_PORT"
        echo -e "    API docs   http://localhost:$BACKEND_PORT/docs"
    fi
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
    echo "    license              Set up pipeline license files (interactive)"
    echo "    start                Start all services (infra + app)"
    echo "    stop                 Stop app services (keeps infra running)"
    echo "    stop --all           Stop everything (app + PostgreSQL/Redis/MinIO)"
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
    echo "    support-bundle [out]  Export sanitized diagnostics bundle"
    echo ""
    echo -e "  ${BOLD}Database${NC}"
    echo "    db init              Create/verify tables"
    echo "    db reset             Drop and recreate (destructive)"
    echo "    db shell             Interactive PostgreSQL shell"
    echo "    db jobs              Show recent jobs"
    echo ""
    echo -e "  ${BOLD}Docker${NC}"
    echo "    pull [image|all|missing]  Pre-pull pipeline images"
    echo "    clean [--safe|--aggressive]  Remove logs, caches, stale containers"
    echo ""
    echo -e "  ${BOLD}System${NC}"
    echo "    preflight [--json]   Run full pre-flight system check"
    echo "    autostart <cmd>      Manage user-level systemd autostart"
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
    echo "    $cli license           # Set up FreeSurfer/MELD license files"
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

_pg_ready() {
    # Deep PostgreSQL health check via pg_isready inside the container
    docker exec neuroinsight-db pg_isready -U "${POSTGRES_USER:-neuroinsight}" &>/dev/null
}

_redis_ready() {
    python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',${REDIS_PORT})); s.close()" 2>/dev/null
}

_minio_ready() {
    python3 -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1',${MINIO_PORT})); s.close()" 2>/dev/null
}

_wait_for_infra_quick() {
    # Quick health test (10 seconds max) -- used to detect stale containers
    local i
    for i in $(seq 1 10); do
        local ready=0
        _pg_ready && ready=$((ready+1))
        _redis_ready && ready=$((ready+1))
        _minio_ready && ready=$((ready+1))
        if [ "$ready" -ge 3 ]; then
            return 0
        fi
        sleep 1
    done
    return 1
}

_wait_for_infra() {
    # Wait for services to be fully ready (up to 45s)
    local max_wait=45
    local i
    info "Waiting for services to be ready ..."
    for i in $(seq 1 "$max_wait"); do
        local ready=0
        _pg_ready && ready=$((ready+1))
        _redis_ready && ready=$((ready+1))
        _minio_ready && ready=$((ready+1))
        if [ "$ready" -ge 3 ]; then
            return 0
        fi
        sleep 1
    done
    # Report which services failed
    _pg_ready || { warn "PostgreSQL not ready on port ${POSTGRES_PORT}"; docker logs --tail 10 neuroinsight-db 2>&1 | tail -5; }
    _redis_ready || warn "Redis not responding on port ${REDIS_PORT}"
    _minio_ready || warn "MinIO not responding on port ${MINIO_PORT}"
    return 1
}

_port_owner() {
    local port="$1"
    # Try lsof (Linux/macOS)
    local pid
    pid=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        local pname
        pname=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
        echo "PID $pid ($pname)"
        return
    fi
    # Check if it's a Docker container
    local cname
    cname=$(docker ps --format '{{.Names}}' --filter "publish=$port" 2>/dev/null | head -1)
    if [ -n "$cname" ]; then
        echo "container '$cname'"
        return
    fi
    # On WSL2, the port may be used by a Windows-side process
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "Windows host process (check Windows Task Manager)"
    else
        echo "unknown process"
    fi
}

_find_free_port() {
    local default_port="$1" max_port="$2" label="$3"
    if ! port_in_use "$default_port"; then
        echo "$default_port"; return 0
    fi
    local owner
    owner=$(_port_owner "$default_port")
    warn "Port $default_port ($label) in use by $owner — finding alternative"
    for p in $(seq $((default_port + 1)) "$max_port"); do
        if ! port_in_use "$p"; then
            echo "$p"; return 0
        fi
    done
    return 1
}

_update_env_var() {
    local key="$1" value="$2" file="$SCRIPT_DIR/.env"
    [ -f "$file" ] || return 0
    if grep -q "^${key}=" "$file"; then
        sed_i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        echo "${key}=${value}" >> "$file"
    fi
}

_regenerate_env_passwords() {
    # After wiping Docker volumes, regenerate passwords in .env so they match
    # the fresh empty databases that will be created on next startup.
    if [ -f "$SCRIPT_DIR/.env" ] && command -v python3 &>/dev/null; then
        local _rand_pw
        _rand_pw() { python3 -c "import secrets; print(secrets.token_urlsafe(24))"; }
        local pg_pass; pg_pass=$(_rand_pw)
        local redis_pass; redis_pass=$(_rand_pw)
        local minio_key; minio_key=$(_rand_pw)
        local minio_secret; minio_secret=$(_rand_pw)
        _update_env_var "POSTGRES_PASSWORD" "$pg_pass"
        _update_env_var "REDIS_PASSWORD" "$redis_pass"
        _update_env_var "MINIO_ROOT_USER" "$minio_key"
        _update_env_var "MINIO_ROOT_PASSWORD" "$minio_secret"
        # Update DATABASE_URL with new password
        local pg_user="${POSTGRES_USER:-neuroinsight}"
        local pg_db="${POSTGRES_DB:-neuroinsight}"
        _update_env_var "DATABASE_URL" "postgresql://${pg_user}:${pg_pass}@localhost:${POSTGRES_PORT:-5432}/${pg_db}"
        set -a; source "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
        info "Regenerated service passwords for clean start"
    fi
}

_infra_update_env() {
    local pg_user="${POSTGRES_USER:-neuroinsight}"
    local pg_pass="${POSTGRES_PASSWORD:-neuroinsight_secure_password}"
    local pg_db="${POSTGRES_DB:-neuroinsight}"
    _update_env_var "POSTGRES_PORT" "$POSTGRES_PORT"
    _update_env_var "DATABASE_URL" "postgresql://${pg_user}:${pg_pass}@localhost:${POSTGRES_PORT}/${pg_db}"
    _update_env_var "REDIS_PORT" "$REDIS_PORT"
    _update_env_var "MINIO_PORT" "$MINIO_PORT"
    set -a; source "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
}

_infra_up_quiet() {
    if ! docker info &>/dev/null; then
        warn "Docker is not running"
        info "Start Docker Desktop (Windows/Mac) or run: sudo systemctl start docker"
        return 1
    fi

    # Remove any stale containers by name (may be from a different compose project)
    for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
        docker rm -f "$name" 2>/dev/null || true
    done

    # Start with default or configured ports
    export POSTGRES_PORT="${POSTGRES_PORT:-5432}"
    export REDIS_PORT="${REDIS_PORT:-6379}"
    export MINIO_PORT="${MINIO_PORT:-9000}"
    export MINIO_CONSOLE_PORT="${MINIO_CONSOLE_PORT:-9001}"

    # Try to start, retry with incremented ports on conflict (up to 10 attempts)
    local attempt
    for attempt in $(seq 1 10); do
        _infra_update_env
        success "Ports: PostgreSQL:${POSTGRES_PORT}  Redis:${REDIS_PORT}  MinIO:${MINIO_PORT}"

        local compose_output
        compose_output=$(_compose up -d 2>&1)
        echo "$compose_output" | tail -5

        # Check for port conflict in the output
        local conflict_port
        conflict_port=$(echo "$compose_output" | sed -n 's/.*port TCP 127\.0\.0\.1:\([0-9]*\).*/\1/p' | head -1)

        if [ -z "$conflict_port" ]; then
            # No port conflict -- wait for services to accept connections
            if _infra_running && _wait_for_infra; then
                return 0
            fi
            return 1
        fi

        # Port conflict detected -- figure out which service and bump it
        warn "Port $conflict_port is unavailable (in use by another process on the host)"

        # Stop whatever partially started
        for name in neuroinsight-db neuroinsight-redis neuroinsight-minio; do
            docker rm -f "$name" 2>/dev/null || true
        done

        # Increment the conflicting port
        if [ "$conflict_port" -eq "$POSTGRES_PORT" ]; then
            POSTGRES_PORT=$((POSTGRES_PORT + 1))
            [ "$POSTGRES_PORT" -le 5460 ] || { error "No free port for PostgreSQL (tried up to 5460)"; return 1; }
            info "Trying PostgreSQL on port $POSTGRES_PORT"
        elif [ "$conflict_port" -eq "$REDIS_PORT" ]; then
            REDIS_PORT=$((REDIS_PORT + 1))
            [ "$REDIS_PORT" -le 6400 ] || { error "No free port for Redis (tried up to 6400)"; return 1; }
            info "Trying Redis on port $REDIS_PORT"
        elif [ "$conflict_port" -eq "$MINIO_PORT" ]; then
            MINIO_PORT=$((MINIO_PORT + 1))
            [ "$MINIO_PORT" -le 9050 ] || { error "No free port for MinIO (tried up to 9050)"; return 1; }
            info "Trying MinIO on port $MINIO_PORT"
        elif [ "$conflict_port" -eq "$MINIO_CONSOLE_PORT" ]; then
            MINIO_CONSOLE_PORT=$((MINIO_CONSOLE_PORT + 1))
            [ "$MINIO_CONSOLE_PORT" -le 9050 ] || { error "No free port for MinIO console (tried up to 9050)"; return 1; }
            info "Trying MinIO console on port $MINIO_CONSOLE_PORT"
        else
            error "Unknown port conflict on $conflict_port"
            return 1
        fi
    done

    error "Failed to start infrastructure after 10 attempts"
    return 1
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

            if docker exec neuroinsight-redis redis-cli -a "${REDIS_PASSWORD:-redis_secure_password}" ping 2>/dev/null | grep -q PONG; then
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
        install)    cmd_install    "$@" ;;
        license)    cmd_license   "$@" ;;
        start)      cmd_start     "$@" ;;
        stop)       cmd_stop      "$@" ;;
        restart)    cmd_restart   "$@" ;;
        status)     cmd_status    "$@" ;;
        health)     cmd_health    "$@" ;;
        logs)       cmd_logs      "$@" ;;
        support-bundle) cmd_support_bundle "$@" ;;
        db)         cmd_db        "$@" ;;
        infra)      cmd_infra     "$@" ;;
        pull)       cmd_pull      "$@" ;;
        clean)      cmd_clean     "$@" ;;
        autostart)  cmd_autostart "$@" ;;
        preflight)  cmd_preflight "$@" ;;
        env)        cmd_env       "$@" ;;
        version)    cmd_version   "$@" ;;
        help|-h|--help)
                    cmd_help      "$@" ;;
        *)
            error "Unknown command: $cmd"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}
