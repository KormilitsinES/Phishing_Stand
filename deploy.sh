#!/bin/bash
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=======================================================${NC}"
echo -e "${BLUE}  Phishing Stand Deployment Script (Red Team Edition)  ${NC}"
echo -e "${BLUE}=======================================================${NC}"

# 1. Проверка прав
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}[-] Ошибка: Пожалуйста, запустите скрипт от имени root или через sudo${NC}"
  exit 1
fi

# 2. АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ
echo -e "\n${YELLOW}[*] Проверка и установка системных зависимостей...${NC}"
apt-get update -qq

# Устанавливаем базовые утилиты (curl, git, gettext для envsubst)
apt-get install -y -qq curl git gettext ca-certificates gnupg lsb-release

# Проверяем и устанавливаем Docker, если его нет
if ! command -v docker &> /dev/null; then
  echo -e "${YELLOW}[*] Установка Docker и Docker Compose (это может занять 1-2 минуты)...${NC}"

  # Добавляем официальный GPG-ключ Docker
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  # Добавляем репозиторий Docker (работает и для Ubuntu, и для Debian)
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -qq
  # Устанавливаем Docker Engine и плагин Docker Compose (v2)
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  echo -e "${GREEN}[+] Docker и Docker Compose успешно установлены.${NC}"
else
  echo -e "${GREEN}[+] Docker уже установлен.${NC}"
fi

# 3. Интерактивный сбор конфигурации
echo -e "\n${GREEN}=== Шаг 1: Конфигурация доменов ===${NC}"
read -p "Введите базовый домен (например, factory-scan.ru): " BASE_DOMAIN
BASE_DOMAIN=${BASE_DOMAIN:-factory-scan.ru}

read -p "Введите домен для трекинга GoPhish [track.$BASE_DOMAIN]: " TRACK_DOMAIN
TRACK_DOMAIN=${TRACK_DOMAIN:-track.$BASE_DOMAIN}

read -p "Введите домен для Evilginx2 [phish.$BASE_DOMAIN]: " EVIL_DOMAIN
EVIL_DOMAIN=${EVIL_DOMAIN:-phish.$BASE_DOMAIN}

read -p "Введите MX-домен для почты [mail.$BASE_DOMAIN]: " MX_DOMAIN
MX_DOMAIN=${MX_DOMAIN:-mail.$BASE_DOMAIN}

read -p "Введите Email для Let's Encrypt: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-support@$BASE_DOMAIN}

# Получаем внешний IP VPS
VPS_IP=$(curl -s https://api.ipify.org)
if [ -z "$VPS_IP" ]; then
  echo -e "${RED}[-] Не удалось определить внешний IP адрес VPS.${NC}"
  exit 1
fi

# 4. Генерация docker-compose.yml
echo -e "\n${GREEN}=== Шаг 2: Генерация docker-compose.yml ===${NC}"
if [ ! -f "docker-compose.yml.template" ]; then
  echo -e "${RED}[-] Ошибка: Файл docker-compose.yml.template не найден.${NC}"
  exit 1
fi

export BASE_DOMAIN TRACK_DOMAIN EVIL_DOMAIN MX_DOMAIN ADMIN_EMAIL
envsubst < docker-compose.yml.template > docker-compose.yml
echo -e "${GREEN}[+] docker-compose.yml успешно сгенерирован.${NC}"

# Создание необходимых директорий
mkdir -p postfix/dkim gophish evilginx2/phishlets evilginx2/data

# 5. Ручное получение Wildcard-сертификата
echo -e "\n${GREEN}=== Шаг 3: Получение Wildcard-сертификата (DNS-01) ===${NC}"
echo -e "${YELLOW}ВНИМАНИЕ: Сейчас запустится Certbot в ручном режиме.${NC}"
echo -e "${YELLOW}1. Он выдаст вам значение для TXT-записи.${NC}"
echo -e "${YELLOW}2. ОТКРОЙТЕ ВТОРОЙ ТЕРМИНАЛ и добавьте эту TXT-запись у DNS-провайдера.${NC}"
echo -e "${YELLOW}3. Проверьте применение: dig TXT _acme-challenge.$BASE_DOMAIN +short${NC}"
echo -e "${YELLOW}4. Только после этого возвращайтесь сюда и нажимайте ENTER.${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
read -p "Нажмите ENTER, когда будете готовы увидеть challenge-запрос..."

echo -e "\n${GREEN}Запуск Certbot...${NC}"
docker run -it --rm \
  -v "$(pwd)/certs:/etc/letsencrypt" \
  certbot/certbot \
  certonly --manual --preferred-challenges dns \
  --email "$ADMIN_EMAIL" \
  --agree-tos --no-eff-email \
  -d "$BASE_DOMAIN" -d "*.$BASE_DOMAIN"

if [ ! -f "certs/live/$BASE_DOMAIN/fullchain.pem" ]; then
  echo -e "${RED}[-] Ошибка: Сертификат не был получен. Проверьте логи выше.${NC}"
  exit 1
fi
echo -e "${GREEN}[+] Wildcard-сертификат успешно получен!${NC}"

# 6. Сборка и запуск
echo -e "\n${GREEN}=== Шаг 4: Сборка и запуск контейнеров ===${NC}"
echo -e "${YELLOW}Сборка образов (milter, postfix, nginx, evilginx2)...${NC}"
docker compose up -d --build

echo -e "${GREEN}[+] Контейнеры запущены. Ожидание инициализации Postfix и генерации DKIM...${NC}"
sleep 15 # Даем время postfix сгенерировать ключ DKIM при первом запуске

# 7. Вывод DNS-записей
echo -e "\n${BLUE}=======================================================${NC}"
echo -e "${GREEN}  СТЕНД УСПЕШНО РАЗВЕРНУТ!${NC}"
echo -e "${BLUE}=======================================================${NC}"

echo -e "${YELLOW}Добавьте следующие записи в панель управления вашего DNS-провайдера:${NC}"
echo -e "-------------------------------------------------------"
echo -e "${GREEN}1. A-записи (укажите IP: $VPS_IP):${NC}"
echo -e "   Имя: track  ->  Значение: $VPS_IP"
echo -e "   Имя: phish  ->  Значение: $VPS_IP"
echo -e "   Имя: mail   ->  Значение: $VPS_IP"
echo -e ""
echo -e "${GREEN}2. MX-запись:${NC}"
echo -e "   Имя: @ (или оставьте пустым)  ->  Значение: $MAIL_HOSTNAME  (Приоритет: 10)"
echo -e ""
echo -e "${GREEN}3. TXT-запись (SPF):${NC}"
echo -e "   Имя: @  ->  Значение: v=spf1 ip4:$VPS_IP -all"
echo -e ""

# Извлечение DKIM ключа
DKIM_FILE="postfix/dkim/default.txt"
if [ -f "$DKIM_FILE" ]; then
  DKIM_VALUE=$(grep -o 'p=.*' "$DKIM_FILE" | tr -d '() "')
  echo -e "${GREEN}4. TXT-запись (DKIM):${NC}"
  echo -e "   Имя: default._domainkey  ->  Значение: v=DKIM1; k=rsa; $DKIM_VALUE"
else
  echo -e "${RED}[-] Предупреждение: Файл DKIM ключа не найден. Проверьте: docker compose logs postfix${NC}"
fi

echo -e "-------------------------------------------------------"
echo -e "${BLUE}Полезные команды:${NC}"
echo -e "  - Доступ к админке GoPhish (через SSH-туннель):"
echo -e "    ssh -L 3333:127.0.0.1:3333 root@$VPS_IP"
echo -e "    Затем откройте в браузере: https://127.0.0.1:3333"
echo -e "  - Доступ к консоли Evilginx2 (через SSH-туннель):"
echo -e "    ssh -L 33333:127.0.0.1:33333 root@$VPS_IP"
echo -e "  - Просмотр логов: docker compose logs -f [имя_сервиса]"
echo -e "${BLUE}=======================================================${NC}"