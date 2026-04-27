#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# start.sh — Script startup otomatis Inventra AI
# Mendeteksi environment dan memilih mode yang tepat
#
# Penggunaan:
#   chmod +x start.sh
#   ./start.sh              # Mode otomatis (deteksi Docker)
#   ./start.sh --local      # Paksa mode lokal (tanpa Docker)
#   ./start.sh --docker     # Paksa mode Docker
#   ./start.sh --test       # Jalankan unit tests saja
#   ./start.sh --demo       # Mode demo cepat (buka dashboard saja)
# ─────────────────────────────────────────────────────────────

set -e  # Exit on error

# ── Warna Terminal ──────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Banner ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}"
echo "  ██╗███╗   ██╗██╗   ██╗███████╗███╗   ██╗████████╗██████╗  █████╗ "
echo "  ██║████╗  ██║██║   ██║██╔════╝████╗  ██║╚══██╔══╝██╔══██╗██╔══██╗"
echo "  ██║██╔██╗ ██║██║   ██║█████╗  ██╔██╗ ██║   ██║   ██████╔╝███████║"
echo "  ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ██║╚██╗██║   ██║   ██╔══██╗██╔══██║"
echo "  ██║██║ ╚████║ ╚████╔╝ ███████╗██║ ╚████║   ██║   ██║  ██║██║  ██║"
echo "  ╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝"
echo -e "${NC}"
echo -e "${BOLD}  Intelligent Inventory Decision Engine v1.0.0${NC}"
echo -e "${YELLOW}  Dicoding AI Impact Challenge 2025 — Manufaktur & Energi${NC}"
echo ""
echo "  3-Layer Intelligence: ${GREEN}PREDICT${NC} → ${YELLOW}DETECT${NC} → ${CYAN}DECIDE${NC}"
echo "  ─────────────────────────────────────────────────────────"
echo ""

# ── Parse Arguments ─────────────────────────────────────────
MODE="auto"
for arg in "$@"; do
    case $arg in
        --local)  MODE="local" ;;
        --docker) MODE="docker" ;;
        --test)   MODE="test" ;;
        --demo)   MODE="demo" ;;
        --help|-h)
            echo "Penggunaan: ./start.sh [--local|--docker|--test|--demo]"
            exit 0 ;;
    esac
done

# ── Helper Functions ─────────────────────────────────────────
log_info()    { echo -e "  ${GREEN}✓${NC} $1"; }
log_warn()    { echo -e "  ${YELLOW}⚠${NC}  $1"; }
log_error()   { echo -e "  ${RED}✗${NC} $1"; }
log_step()    { echo -e "\n  ${BLUE}▶${NC} ${BOLD}$1${NC}"; }
check_port()  { lsof -i :$1 &>/dev/null && return 0 || return 1; }

# ── Mode: TEST ONLY ──────────────────────────────────────────
if [ "$MODE" = "test" ]; then
    log_step "Menjalankan Unit Tests..."
    echo ""
    if ! python -m pytest tests/ -v --tb=short --no-header 2>&1; then
        log_error "Beberapa test gagal."
        exit 1
    fi
    log_info "Semua test lulus! ✅"
    exit 0
fi

# ── Mode: DEMO (buka dashboard langsung) ────────────────────
if [ "$MODE" = "demo" ]; then
    log_step "Mode Demo — Membuka Dashboard..."
    DASHBOARD="$(pwd)/frontend/dashboard.html"
    if [ ! -f "$DASHBOARD" ]; then
        log_error "File dashboard.html tidak ditemukan di frontend/"
        exit 1
    fi
    log_info "Membuka dashboard di browser..."
    if command -v xdg-open &>/dev/null; then
        xdg-open "$DASHBOARD"
    elif command -v open &>/dev/null; then
        open "$DASHBOARD"
    else
        log_warn "Buka manual: $DASHBOARD"
    fi
    echo ""
    log_info "Dashboard berjalan dalam mode offline (mock data)."
    log_warn "Jalankan './start.sh --local' untuk koneksi backend penuh."
    exit 0
fi

# ── Deteksi Environment ──────────────────────────────────────
log_step "Memeriksa Environment..."

HAS_DOCKER=false
HAS_PYTHON=false
HAS_PIP=false

command -v docker &>/dev/null && docker info &>/dev/null 2>&1 && HAS_DOCKER=true
command -v python3 &>/dev/null && HAS_PYTHON=true || command -v python &>/dev/null && HAS_PYTHON=true
command -v pip &>/dev/null && HAS_PIP=true

[ "$HAS_DOCKER" = true ] && log_info "Docker tersedia" || log_warn "Docker tidak ditemukan"
[ "$HAS_PYTHON" = true ] && log_info "Python tersedia ($(python3 --version 2>/dev/null || python --version))" || log_warn "Python tidak ditemukan"
[ "$HAS_PIP" = true ]    && log_info "pip tersedia" || log_warn "pip tidak ditemukan"

# ── Tentukan Mode ────────────────────────────────────────────
if [ "$MODE" = "auto" ]; then
    if [ "$HAS_DOCKER" = true ]; then
        MODE="docker"
        log_info "Auto-select: Mode Docker"
    elif [ "$HAS_PYTHON" = true ]; then
        MODE="local"
        log_info "Auto-select: Mode Local Python"
    else
        log_error "Tidak ada Python atau Docker yang ditemukan!"
        echo ""
        echo "  Silakan install salah satu:"
        echo "  • Python 3.9+: https://python.org"
        echo "  • Docker: https://docker.com"
        exit 1
    fi
fi

# ── Mode: DOCKER ─────────────────────────────────────────────
if [ "$MODE" = "docker" ]; then
    log_step "Memulai dengan Docker Compose..."

    if check_port 8000; then
        log_warn "Port 8000 sudah digunakan. Menghentikan container lama..."
        docker-compose down 2>/dev/null || true
    fi

    echo ""
    log_info "Membangun dan menjalankan containers..."
    docker-compose up --build -d

    log_step "Menunggu backend siap..."
    for i in $(seq 1 20); do
        if curl -sf http://localhost:8000/api/v1/health &>/dev/null; then
            log_info "Backend siap! (${i}× check)"
            break
        fi
        echo -n "."
        sleep 2
        if [ $i -eq 20 ]; then
            log_error "Backend timeout. Cek log: docker-compose logs backend"
            exit 1
        fi
    done

    echo ""
    echo "  ─────────────────────────────────────────────────────────"
    log_info "Inventra AI berjalan dalam mode Docker! 🚀"
    echo ""
    echo "  ${BOLD}Akses:${NC}"
    echo "  • Dashboard  : ${CYAN}http://localhost:3000${NC}"
    echo "  • API        : ${CYAN}http://localhost:8000${NC}"
    echo "  • API Docs   : ${CYAN}http://localhost:8000/docs${NC}"
    echo ""
    echo "  ${BOLD}Perintah berguna:${NC}"
    echo "  • Lihat log  : docker-compose logs -f backend"
    echo "  • Stop       : docker-compose down"
    echo "  ─────────────────────────────────────────────────────────"

    # Buka browser otomatis
    sleep 2
    command -v xdg-open &>/dev/null && xdg-open http://localhost:3000 || \
    command -v open &>/dev/null && open http://localhost:3000 || true
    exit 0
fi

# ── Mode: LOCAL PYTHON ───────────────────────────────────────
if [ "$MODE" = "local" ]; then
    log_step "Memulai dalam mode Local Python..."

    PYTHON_CMD="python3"
    command -v python3 &>/dev/null || PYTHON_CMD="python"

    # ── Cek dan install dependencies ──────────────────────────
    log_step "Memeriksa Dependencies..."
    if ! $PYTHON_CMD -c "import fastapi, uvicorn, sklearn, pandas, numpy" &>/dev/null; then
        log_warn "Beberapa package belum terinstall. Menginstall..."
        $PYTHON_CMD -m pip install -r requirements.txt -q
        log_info "Dependencies terinstall."
    else
        log_info "Semua dependencies sudah tersedia."
    fi

    # ── Load .env jika ada ────────────────────────────────────
    if [ -f ".env" ]; then
        log_info "Memuat konfigurasi dari .env..."
        export $(grep -v '^#' .env | xargs) 2>/dev/null || true
    else
        log_warn ".env tidak ditemukan — menggunakan konfigurasi default (rule-based AI)"
    fi

    # ── Cek port ──────────────────────────────────────────────
    if check_port 8000; then
        log_warn "Port 8000 sudah digunakan. Gunakan port lain atau hentikan proses yang ada."
        log_info "Mencoba port 8001..."
        PORT=8001
    else
        PORT=8000
    fi

    # ── Jalankan API server ───────────────────────────────────
    log_step "Menjalankan FastAPI Backend..."
    echo ""

    # Pastikan kita di direktori project
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cd "$SCRIPT_DIR"

    # Run unit tests singkat sebelum start
    if $PYTHON_CMD -m pytest tests/test_engine.py -q --no-header --tb=no &>/dev/null; then
        log_info "Pre-flight tests: LULUS ✅"
    else
        log_warn "Beberapa test gagal, tapi melanjutkan startup..."
    fi

    echo ""
    echo "  ─────────────────────────────────────────────────────────"
    log_info "Inventra AI Backend mulai berjalan..."
    echo ""
    echo "  ${BOLD}Akses:${NC}"
    echo "  • API        : ${CYAN}http://localhost:${PORT}${NC}"
    echo "  • API Docs   : ${CYAN}http://localhost:${PORT}/docs${NC}"
    echo "  • Dashboard  : Buka ${CYAN}frontend/dashboard.html${NC} di browser"
    echo ""
    echo "  ${BOLD}Untuk menghentikan:${NC} Tekan Ctrl+C"
    echo "  ─────────────────────────────────────────────────────────"
    echo ""

    # Buka dashboard di browser (background)
    DASHBOARD="$SCRIPT_DIR/frontend/dashboard.html"
    (sleep 4 && (xdg-open "$DASHBOARD" 2>/dev/null || open "$DASHBOARD" 2>/dev/null || true)) &

    # Jalankan uvicorn
    $PYTHON_CMD -m uvicorn api.main:app \
        --host 0.0.0.0 \
        --port $PORT \
        --reload \
        --log-level info \
        --access-log
fi
