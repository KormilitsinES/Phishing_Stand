#!/bin/bash
set -e

echo -e "${YELLOW}[*] Создание необходимых файлов и директорий...${NC}"
mkdir -p postfix/dkim evilginx2/phishlets evilginx2/data certs

touch gophish/gophish.db

chmod 744 gophish/gophish.db

echo -e "${GREEN}[+] Директории созданы.${NC}"