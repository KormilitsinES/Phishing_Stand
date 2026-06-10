#!/bin/bash
set -e

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

echo -e "   Имя: @ (или оставьте пустым)  ->  Значение: $MX_DOMAIN  (Приоритет: 10)"
echo -e ""
echo -e "${GREEN}3. TXT-запись (SPF):${NC}"
echo -e "   Имя: @  ->  Значение: v=spf1 ip4:$VPS_IP -all"
echo -e ""

DKIM_FILE="postfix/dkim/default.txt"
if [ -f "$DKIM_FILE" ]; then
  DKIM_VALUE=$(grep -o 'p=.*' "$DKIM_FILE" | tr -d '() "')
  echo -e "${GREEN}4. TXT-запись (DKIM):${NC}"
  echo -e "   Имя: default._domainkey  ->  Значение: v=DKIM1; k=rsa; $DKIM_VALUE"
else
  echo -e "${RED}[-] Предупреждение: Файл DKIM ключа не найден. Проверьте: docker compose logs postfix${NC}"
fi
echo -e "-------------------------------------------------------"

echo -e "\n${GREEN}=== Учетные данные GoPhish ===${NC}"
echo -e "${YELLOW}Извлечение пароля из логов GoPhish...${NC}"
sleep 5

GOPHISH_LOGS=$(docker compose logs gophish 2>/dev/null)

GOPHISH_PASSWORD=$(echo "$GOPHISH_LOGS" | grep -oP '(?<=password=")[^"]+' | tail -n 1)
if [ -z "$GOPHISH_PASSWORD" ]; then
    GOPHISH_PASSWORD=$(echo "$GOPHISH_LOGS" | grep -oP '(?<=password: )\S+' | tail -n 1)
fi
if [ -z "$GOPHISH_PASSWORD" ]; then
    GOPHISH_PASSWORD=$(echo "$GOPHISH_LOGS" | grep -i "password" | grep -oE '[a-zA-Z0-9]{16,}' | tail -n 1)
fi

if [ -n "$GOPHISH_PASSWORD" ]; then
    echo -e "${GREEN}[+] Учетные данные для входа в админку GoPhish:${NC}"
    echo -e "   URL: https://127.0.0.1:3333 (через SSH-туннель)"
    echo -e "   Username: admin"
    echo -e "   Password: $GOPHISH_PASSWORD"
else
    echo -e "${RED}[-] Не удалось автоматически извлечь пароль GoPhish из логов.${NC}"
    echo -e "${YELLOW}Пожалуйста, проверьте логи вручную: docker compose logs gophish | grep -i password${NC}"
fi

echo -e "\n${BLUE}Полезные команды:${NC}"
echo -e "  - Доступ к админке GoPhish (через SSH-туннель):"
echo -e "    ssh -L 3333:127.0.0.1:3333 root@$VPS_IP"
echo -e "    Затем откройте в браузере: https://127.0.0.1:3333"
echo -e "  - Доступ к консоли Evilginx2 (через SSH-туннель):"
echo -e "    ssh -L 33333:127.0.0.1:33333 root@$VPS_IP"
echo -e "  - Просмотр логов: docker compose logs -f [имя_сервиса]"
echo -e "${BLUE}=======================================================${NC}"