#!/bin/bash
set -e

echo -e "${GREEN}=== Сборка и запуск контейнеров ===${NC}"
echo -e "${YELLOW}Сборка образов (milter, postfix, nginx, evilginx2)...${NC}"

docker compose up -d --build

echo -e "${GREEN}[+] Контейнеры запущены. Ожидание инициализации Postfix и генерации DKIM...${NC}"
sleep 15