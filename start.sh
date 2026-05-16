#!/usr/bin/env bash
# start.sh — Verifica el entorno antes de construir el agente
# ─────────────────────────────────────────────────────────────────────────────

set -e

BOLD="\033[1m"
GREEN="\033[92m"
RED="\033[91m"
YELLOW="\033[93m"
CYAN="\033[96m"
RESET="\033[0m"

echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo -e "${BOLD}   🤖 AgentKit — Verificación de Entorno    ${RESET}"
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo ""

ERRORS=0

# ── Verificar Python ──────────────────────────────────────────────────────
echo -e "${CYAN}▶ Verificando Python...${RESET}"
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info[0])')
    PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])')

    if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
        echo -e "  ${GREEN}✅ Python $PYTHON_VERSION — OK${RESET}"
    else
        echo -e "  ${RED}❌ Python $PYTHON_VERSION — Necesitas Python 3.11 o superior${RESET}"
        echo -e "     Descárgalo en: https://python.org/downloads"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  ${RED}❌ Python no encontrado${RESET}"
    echo -e "     Descárgalo en: https://python.org/downloads"
    ERRORS=$((ERRORS + 1))
fi

# ── Verificar Claude Code ─────────────────────────────────────────────────
echo -e "${CYAN}▶ Verificando Claude Code...${RESET}"
if command -v claude &>/dev/null; then
    CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "instalado")
    echo -e "  ${GREEN}✅ Claude Code $CLAUDE_VERSION — OK${RESET}"
else
    echo -e "  ${RED}❌ Claude Code no encontrado${RESET}"
    echo -e "     Instálalo con: npm install -g @anthropic-ai/claude-code"
    echo -e "     (Necesitas Node.js primero: https://nodejs.org)"
    ERRORS=$((ERRORS + 1))
fi

# ── Crear carpetas base ────────────────────────────────────────────────────
echo -e "${CYAN}▶ Creando estructura de carpetas...${RESET}"
mkdir -p knowledge config agent/providers tests
echo -e "  ${GREEN}✅ Carpetas listas${RESET}"

# ── Copiar .env si no existe ───────────────────────────────────────────────
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}✅ Archivo .env creado desde .env.example${RESET}"
    echo -e "  ${YELLOW}⚠️  Recuerda editar .env con tus API keys reales${RESET}"
fi

# ── Resultado ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✅ Todo listo! Abre Claude Code y escribe /build-agent${RESET}"
    echo ""
    echo -e "  ${CYAN}claude${RESET}   ← Abre Claude Code"
    echo -e "  ${CYAN}/build-agent${RESET}   ← Inicia el constructor"
else
    echo -e "${RED}${BOLD}❌ Hay $ERRORS error(es) que resolver antes de continuar.${RESET}"
fi
echo -e "${BOLD}════════════════════════════════════════════${RESET}"
echo ""
