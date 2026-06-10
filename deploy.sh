#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

STATE_FILE=".deploy_state"
ENV_FILE=".env"

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[-] Ошибка: Пожалуйста, запустите скрипт от имени root или через sudo${NC}"
  exit 1
fi

load_env() {
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
    fi
}

run_step() {
    local step_num=$1
    local step_name=$2
    local step_script="steps/${step_num}_${step_name}.sh"

    if [ ! -f "$step_script" ]; then
        echo -e "${RED}[-] Скрипт шага $step_script не найден.${NC}"
        exit 1
    fi

    if grep -q "^${step_num}$" "$STATE_FILE" 2>/dev/null; then
        echo -e "${GREEN}[+] Шаг $step_num ($step_name) уже выполнен. Пропускаем.${NC}"
        return 0
    fi

    echo -e "\n${BLUE}=======================================================${NC}"
    echo -e "${BLUE}  Выполнение шага $step_num: $step_name${NC}"
    echo -e "${BLUE}=======================================================${NC}"

    load_env

    if bash "$step_script"; then
        echo "$step_num" >> "$STATE_FILE"
        echo -e "${GREEN}[+] Шаг $step_num успешно завершен.${NC}"
    else
        echo -e "${RED}[-] Ошибка на шаге $step_num. Исправьте проблему и запустите скрипт снова с аргументом --from $step_num${NC}"
        exit 1
    fi
}

START_FROM=1
ONLY_STEP=0
RESET=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --from) START_FROM="$2"; shift 2 ;;
        --only) ONLY_STEP="$2"; shift 2 ;;
        --reset) RESET=true; shift ;;
        *) echo -e "${RED}Неизвестный аргумент: $1${NC}"; exit 1 ;;
    esac
done

if [ "$RESET" = true ]; then
    rm -f "$STATE_FILE"
    echo -e "${GREEN}[+] Состояние сброшено. Начнем с шага 1.${NC}"
    START_FROM=1
fi

if [ "$START_FROM" -gt 1 ]; then
    for i in $(seq $START_FROM 6); do
        sed -i "/^${i}$/d" "$STATE_FILE" 2>/dev/null
    done
    echo -e "${YELLOW}[!] Сброшено состояние для шагов $START_FROM-6.${NC}"
fi

if [ "$ONLY_STEP" -gt 0 ]; then
    case $ONLY_STEP in
        1) run_step 1 "install_deps" ;; 2) run_step 2 "prepare_dirs" ;;
        3) run_step 3 "configure_compose" ;; 4) run_step 4 "get_certs" ;;
        5) run_step 5 "build_run" ;; 6) run_step 6 "print_info" ;;
        *) echo -e "${RED}Неверный номер шага.${NC}"; exit 1 ;;
    esac
    exit 0
fi

for i in $(seq $START_FROM 6); do
    case $i in
        1) run_step 1 "install_deps" ;; 2) run_step 2 "prepare_dirs" ;;
        3) run_step 3 "configure_compose" ;; 4) run_step 4 "get_certs" ;;
        5) run_step 5 "build_run" ;; 6) run_step 6 "print_info" ;;
    esac
done

echo -e "\n${GREEN}=======================================================${NC}"
echo -e "${GREEN}  РАЗВЕРТЫВАНИЕ ЗАВЕРШЕНО УСПЕШНО!${NC}"
echo -e "${GREEN}=======================================================${NC}"