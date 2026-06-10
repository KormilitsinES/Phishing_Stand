#!/bin/bash
set -e

echo -e "${YELLOW}[*] Создание необходимых директорий...${NC}"
mkdir -p postfix/dkim evilginx2/phishlets evilginx2/data certs

echo -e "${GREEN}[+] Директории созданы.${NC}"