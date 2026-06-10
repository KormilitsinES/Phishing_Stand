#!/bin/bash
set -e

echo -e "${GREEN}=== Конфигурация доменов ===${NC}"

if [ -f ".env" ]; then
    read -p "Файл .env уже существует. Использовать существующие значения? (Y/n): " USE_EXISTING
    if [[ "$USE_EXISTING" != "n" && "$USE_EXISTING" != "N" ]]; then
        echo -e "${GREEN}[+] Использованы существующие значения из .env${NC}"
        envsubst < docker-compose.yml.template > docker-compose.yml
        echo -e "${GREEN}[+] docker-compose.yml сгенерирован.${NC}"
        exit 0
    fi
fi

read -p "Введите базовый домен (например, my-domain.com): " BASE_DOMAIN
BASE_DOMAIN=${BASE_DOMAIN:-my-domain.com}

read -p "Введите домен для трекинга GoPhish [track.$BASE_DOMAIN]: " TRACK_DOMAIN
TRACK_DOMAIN=${TRACK_DOMAIN:-track.$BASE_DOMAIN}

read -p "Введите домен для Evilginx2 [phish.$BASE_DOMAIN]: " EVIL_DOMAIN
EVIL_DOMAIN=${EVIL_DOMAIN:-phish.$BASE_DOMAIN}

read -p "Введите MX-домен для почты [mail.$BASE_DOMAIN]: " MX_DOMAIN
MX_DOMAIN=${MX_DOMAIN:-mail.$BASE_DOMAIN}

read -p "Введите Email для Let's Encrypt: " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-support@$BASE_DOMAIN}

read -p "Введите название для контейнера с GoPhish: [mailer-app]" GOPHISH_BACKEND
GOPHISH_BACKEND=${GOPHISH_BACKEND:-mailer-app}

read -p "Введите название для контейнера с Postfix: [mailer]" POSTFIX_BACKEND
POSTFIX_BACKEND=${POSTFIX_BACKEND:-mailer}

read -p "Введите название для контейнера с Evilginx2: [evilginx2]" EVILGINX_BACKEND
EVILGINX_BACKEND=${EVILGINX_BACKEND:-evilginx2}

VPS_IP=$(curl -s https://api.ipify.org)
if [ -z "$VPS_IP" ]; then
  echo -e "${RED}[-] Не удалось определить внешний IP адрес VPS.${NC}"
  exit 1
fi

echo -e "${YELLOW}[*] Сохранение конфигурации в .env...${NC}"
cat <<EOF > .env
BASE_DOMAIN=$BASE_DOMAIN
TRACK_DOMAIN=$TRACK_DOMAIN
EVIL_DOMAIN=$EVIL_DOMAIN
MX_DOMAIN=$MX_DOMAIN
ADMIN_EMAIL=$ADMIN_EMAIL
GOPHISH_BACKEND=${GOPHISH_BACKEND}
POSTFIX_BACKEND=${POSTFIX_BACKEND}
EVILGINX_BACKEND=${EVILGINX_BACKEND}
VPS_IP=$VPS_IP
EOF

echo -e "${YELLOW}[*] Генерация docker-compose.yml...${NC}"
if [ ! -f "docker-compose.yml.template" ]; then
  echo -e "${RED}[-] Ошибка: Файл docker-compose.yml.template не найден.${NC}"
  exit 1
fi

export BASE_DOMAIN TRACK_DOMAIN EVIL_DOMAIN MX_DOMAIN ADMIN_EMAIL GOPHISH_BACKEND POSTFIX_BACKEND EVILGINX_BACKEND
envsubst < docker-compose.yml.template > docker-compose.yml
echo -e "${GREEN}[+] docker-compose.yml успешно сгенерирован.${NC}"