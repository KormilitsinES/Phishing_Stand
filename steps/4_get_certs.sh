#!/bin/bash
set -e

echo -e "${GREEN}=== Получение Wildcard-сертификата (DNS-01) ===${NC}"

if [ -f "certs/live/$BASE_DOMAIN/fullchain.pem" ]; then
    echo -e "${YELLOW}[!] Сертификат уже существует в certs/live/$BASE_DOMAIN/.${NC}"
    read -p "Пропустить получение или попытаться обновить? (Skip/Update): " CERT_ACTION
    if [[ "$CERT_ACTION" == "Skip" || "$CERT_ACTION" == "skip" || "$CERT_ACTION" == "S" || "$CERT_ACTION" == "s" ]]; then
        echo -e "${GREEN}[+] Пропускаем получение сертификата.${NC}"
        exit 0
    fi
fi

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

chmod 744 certs/archive/$BASE_DOMAIN/*