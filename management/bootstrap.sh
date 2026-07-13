#!/bin/bash
set -e

# ============================================================================
# bootstrap.sh — Первичная установка зависимостей phishing-stand
# ============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${GREEN}[*] Bootstrap phishing-stand${NC}"

# ---------- Проверка Python ----------
PYTHON_CMD=""
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            echo -e "${GREEN}[+] Найден Python: $PYTHON_CMD (v${version})${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${YELLOW}[!] Python 3.10+ не найден. Устанавливаю...${NC}"
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq python3 python3-venv python3-pip
    else
        echo -e "${RED}[-] Не удалось установить Python автоматически.${NC}"
        echo -e "${RED}    Установите Python 3.10+ вручную и повторите запуск.${NC}"
        exit 1
    fi
    PYTHON_CMD="python3"
fi

# ---------- Создание venv ----------
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[*] Создаю виртуальное окружение в ${VENV_DIR}...${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ---------- Установка пакета ----------
echo -e "${YELLOW}[*] Устанавливаю phishing-stand и зависимости...${NC}"
pip install --upgrade pip --quiet
pip install -e . --quiet

echo ""
echo -e "${GREEN}=================================================================${NC}"
echo -e "${GREEN}  Установка завершена!${NC}"
echo -e "${GREEN}=================================================================${NC}"
echo ""
echo -e "Активируйте окружение: ${YELLOW}source .venv/bin/activate${NC}"
echo -e "Или используйте:       ${YELLOW}.venv/bin/phishing-stand --help${NC}"
echo ""
echo -e "Примеры:"
echo -e "  ${BLUE}phishing-stand deploy${NC}          — развёртывание стенда"
echo -e "  ${BLUE}phishing-stand export${NC}          — экспорт данных"
echo -e "  ${BLUE}phishing-stand import <архив>${NC}  — импорт данных"
echo -e "  ${BLUE}phishing-stand status${NC}          — проверка состояния"