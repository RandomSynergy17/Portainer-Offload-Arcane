#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  Portainer to Arcane Migration Tool — Launcher
#  Checks prerequisites, installs dependencies, runs the wizard.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATE_PY="$SCRIPT_DIR/migrate.py"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
MIN_PYTHON="3.8"

# ── Colors (degrade gracefully if no tty) ───────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    DIM='\033[2m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' CYAN='' DIM='' BOLD='' RESET=''
fi

info()    { echo -e "  ${CYAN}ℹ${RESET} $*"; }
success() { echo -e "  ${GREEN}✔${RESET} $*"; }
warn()    { echo -e "  ${YELLOW}⚠${RESET} $*"; }
fail()    { echo -e "  ${RED}✘${RESET} $*"; }

# ── Help ────────────────────────────────────────────────────
show_help() {
    echo ""
    echo -e "${CYAN}${BOLD}  Portainer → Arcane Migration Tool${RESET}"
    echo -e "${DIM}  Launcher v1.0${RESET}"
    echo ""
    echo -e "  ${BOLD}USAGE${RESET}"
    echo "    ./migrate.sh [OPTIONS]"
    echo ""
    echo -e "  ${BOLD}DESCRIPTION${RESET}"
    echo "    Checks prerequisites (Python 3.8+, rich, requests),"
    echo "    installs missing dependencies into .venv, then launches the"
    echo "    migration wizard. All options are passed through to migrate.py."
    echo ""
    echo -e "  ${BOLD}LAUNCHER OPTIONS${RESET}"
    echo "    -h, --help         Show this help and exit"
    echo "    --check-only       Check prerequisites without launching"
    echo ""
    echo -e "  ${BOLD}MIGRATION OPTIONS${RESET} ${DIM}(passed to migrate.py)${RESET}"
    echo "    --dry-run          Simulate without making changes"
    echo "    --export-only      Export from Portainer only (no Arcane import)"
    echo "    --resume           Resume an interrupted migration"
    echo "    --skip-backup      Skip the Portainer backup step"
    echo "    --import-dir PATH  Import from a previous export directory"
    echo "    --config FILE      Load connection config from JSON"
    echo "    --version          Show version and exit"
    echo ""
    echo -e "  ${BOLD}EXAMPLES${RESET}"
    echo "    ./migrate.sh                     Interactive wizard"
    echo "    ./migrate.sh --dry-run           Simulate the full migration"
    echo "    ./migrate.sh --export-only       Export data only, don't touch Arcane"
    echo "    ./migrate.sh --check-only        Just verify prerequisites"
    echo "    ./migrate.sh --resume            Pick up where you left off"
    echo ""
    echo -e "  ${BOLD}PREREQUISITES${RESET}"
    echo "    Python 3.8+       Checked automatically"
    echo "    python3-venv      Required to create .venv (apt/dnf package)"
    echo "    rich, requests    Installed into .venv from requirements.txt"
    echo "    Docker (optional) Enables volume data backup when available"
    echo ""
}

CHECK_ONLY=false
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            exit 0
            ;;
        --check-only)
            CHECK_ONLY=true
            ;;
    esac
done

# ── Banner ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}  Portainer → Arcane Migration Tool${RESET}"
echo -e "${DIM}  Launcher v1.0${RESET}"
echo ""

# ── Check migrate.py exists ─────────────────────────────────
if [ ! -f "$MIGRATE_PY" ]; then
    fail "migrate.py not found at $MIGRATE_PY"
    echo "  Run this script from the project root directory."
    exit 1
fi

# ── Find Python ─────────────────────────────────────────────
PYTHON=""

# Candidate list: PATH first, then well-known absolute locations for users
# whose GUI shell environment doesn't include Homebrew / pyenv / etc.
PYTHON_CANDIDATES=(
    python3
    python
    /opt/homebrew/bin/python3       # Apple Silicon Homebrew
    /usr/local/bin/python3          # Intel Mac Homebrew / Linux /usr/local
    /usr/bin/python3                # system Python on Linux + macOS
)

for candidate in "${PYTHON_CANDIDATES[@]}"; do
    # Use "command -v" for PATH entries, "-x" for absolute paths.
    if [[ "$candidate" = /* ]]; then
        [ -x "$candidate" ] || continue
    else
        command -v "$candidate" &>/dev/null || continue
    fi
    version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    if [ "$major" -gt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -ge 8 ]); then
        PYTHON="$candidate"
        break
    fi
done

# Windows / Git Bash: try the "py" launcher as last resort.
if [ -z "$PYTHON" ] && command -v py &>/dev/null; then
    if py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" &>/dev/null; then
        PYTHON="py -3"
    fi
fi

if [ -z "$PYTHON" ]; then
    fail "Python ${MIN_PYTHON}+ not found."
    echo ""
    echo "  Locations checked:"
    for c in "${PYTHON_CANDIDATES[@]}"; do
        echo "    - $c"
    done
    echo "    - py -3 (Windows launcher)"
    echo ""
    echo "  Install Python:"
    case "$(uname -s)" in
        Darwin*)  echo "    brew install python3" ;;
        Linux*)   echo "    sudo apt install python3  # Debian/Ubuntu"
                  echo "    sudo dnf install python3  # Fedora/RHEL" ;;
        MINGW*|MSYS*|CYGWIN*)
                  echo "    winget install Python.Python.3.12" ;;
    esac
    echo ""
    exit 1
fi

PY_VERSION=$("$PYTHON" --version 2>&1)
success "Found $PY_VERSION ($(command -v "$PYTHON"))"

# ── Virtual environment ─────────────────────────────────────
# Install into an active virtualenv when the user already has one.
# Otherwise use .venv next to this script, so system Python (PEP 668)
# never receives the packages.
VENV_DIR="$SCRIPT_DIR/.venv"

recommend_python_venv() {
    fail "Python's venv module is not installed."
    echo ""
    echo "  Dependencies install into a virtual environment. Install the"
    echo "  venv module, then run this again:"
    case "$(uname -s)" in
        Darwin*)  echo "    brew install python3" ;;
        Linux*)   echo "    sudo apt install python3-venv    # Debian/Ubuntu"
                  echo "    sudo dnf install python3-venv    # Fedora/RHEL" ;;
        *)        echo "    Install the venv module for this Python (often python3-venv)." ;;
    esac
    echo ""
}

venv_interpreter() {
    if [ -x "$VENV_DIR/bin/python" ]; then
        echo "$VENV_DIR/bin/python"
    elif [ -x "$VENV_DIR/Scripts/python.exe" ]; then
        echo "$VENV_DIR/Scripts/python.exe"
    fi
}

packages_missing() {
    # Returns 0 when rich or requests cannot be imported.
    local py="$1"
    local pkg
    for pkg in rich requests; do
        if ! "$py" -c "import $pkg" &>/dev/null; then
            return 0
        fi
    done
    return 1
}

in_virtualenv() {
    "$1" -c "import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)"
}

TARGET=""
if in_virtualenv "$PYTHON"; then
    TARGET="$PYTHON"
    success "Using the active virtual environment"
else
    TARGET="$(venv_interpreter || true)"
fi

if [ -z "$TARGET" ] && ! packages_missing "$PYTHON"; then
    # Nothing to install, and no project venv yet. Stay on this interpreter.
    TARGET="$PYTHON"
fi

if [ -n "$TARGET" ] && ! packages_missing "$TARGET"; then
    success "Dependencies satisfied (rich, requests)"
else
    if [ -z "$TARGET" ]; then
        warn "Missing packages: rich and/or requests"
        echo ""
        if [ -t 0 ]; then
            read -rp "  Install them into ${VENV_DIR}? [Y/n]: " answer
            answer="${answer:-y}"
        else
            fail "No TTY to prompt for install."
            echo "  ${PYTHON} -m venv ${VENV_DIR}"
            echo "  ${VENV_DIR}/bin/python -m pip install -r ${REQUIREMENTS}"
            echo ""
            exit 1
        fi
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            fail "Cannot continue without rich and requests."
            exit 1
        fi
        echo ""
        if ! "$PYTHON" -c "import venv" &>/dev/null; then
            recommend_python_venv
            exit 1
        fi
        info "Creating ${VENV_DIR}"
        if ! "$PYTHON" -m venv "$VENV_DIR"; then
            recommend_python_venv
            exit 1
        fi
        TARGET="$(venv_interpreter || true)"
        if [ -z "$TARGET" ]; then
            recommend_python_venv
            exit 1
        fi
    else
        warn "Missing packages in ${TARGET}"
        echo ""
        if [ -t 0 ]; then
            read -rp "  Install them into that environment? [Y/n]: " answer
            answer="${answer:-y}"
        else
            fail "No TTY to prompt for install."
            exit 1
        fi
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            fail "Cannot continue without rich and requests."
            exit 1
        fi
        echo ""
    fi

    if ! "$TARGET" -m pip --version &>/dev/null; then
        warn "pip not found in the virtual environment. Attempting ensurepip..."
        if ! "$TARGET" -m ensurepip --default-pip &>/dev/null; then
            recommend_python_venv
            echo "  Then remove the incomplete environment and retry:"
            echo "    rm -rf ${VENV_DIR}"
            echo ""
            exit 1
        fi
    fi

    # Show pip output. A quiet install hid PEP 668 and resolver errors.
    if [ -f "$REQUIREMENTS" ]; then
        if ! "$TARGET" -m pip install -r "$REQUIREMENTS"; then
            fail "pip install failed — see output above."
            exit 1
        fi
    else
        if ! "$TARGET" -m pip install rich requests; then
            fail "pip install failed — see output above."
            exit 1
        fi
    fi
    success "Dependencies installed into ${TARGET}"
fi

PYTHON="$TARGET"

# ── Check Docker (optional) ─────────────────────────────────
echo ""
if ! command -v docker &>/dev/null; then
    warn "Docker CLI not installed — volume data backup disabled"
    info "Install Docker if you want volume tarballs. API-only migration"
    info "still works for stacks, configs, and metadata."
else
    DOCKER_VERSION=$(docker --version 2>&1 | head -1)
    # Capture the exact docker info failure so the user knows whether the
    # daemon is down, their socket is permission-denied, or some other issue.
    DOCKER_INFO_ERR=$(docker info 2>&1 >/dev/null) || DOCKER_INFO_STATUS=$?
    if [ -z "${DOCKER_INFO_STATUS:-}" ]; then
        success "Docker available (${DIM}${DOCKER_VERSION}${RESET})"
        info "Volume data backup will be available"
    else
        warn "Docker installed but 'docker info' failed — volume backup disabled"
        # Surface the error so the user can fix the root cause instead of
        # guessing between daemon down / permissions / network.
        if echo "$DOCKER_INFO_ERR" | grep -qi "permission denied"; then
            info "Socket permission denied. Add your user to the docker group:"
            info "    sudo usermod -aG docker \$USER   (then re-login)"
        elif echo "$DOCKER_INFO_ERR" | grep -qi "cannot connect\|is the docker daemon running\|failed to connect\|no such file or directory"; then
            info "Docker daemon doesn't appear to be running:"
            case "$(uname -s)" in
                Darwin*) info "    open -a 'Docker Desktop'" ;;
                Linux*)  info "    sudo systemctl start docker" ;;
            esac
        else
            info "docker info said:"
            echo "$DOCKER_INFO_ERR" | sed 's/^/      /' | head -5
        fi
        info "API-only migration still works for stacks/configs/metadata."
    fi
fi

# ── Check-only exit ─────────────────────────────────────────
if [ "$CHECK_ONLY" = true ]; then
    echo ""
    success "All prerequisites satisfied. Ready to migrate."
    echo ""
    exit 0
fi

# ── Launch ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}─────────────────────────────────────────────${RESET}"
echo -e "  ${BOLD}Launching migration wizard...${RESET}"
echo -e "${CYAN}─────────────────────────────────────────────${RESET}"
echo ""

# Strip launcher-only flags before passing to migrate.py
ARGS=()
for arg in "$@"; do
    case "$arg" in
        --check-only) ;;  # consumed by launcher
        *) ARGS+=("$arg") ;;
    esac
done

exec "$PYTHON" "$MIGRATE_PY" "${ARGS[@]+"${ARGS[@]}"}"
