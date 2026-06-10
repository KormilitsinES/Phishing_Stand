#!/bin/bash
set -e

echo -e "${YELLOW}[*] Проверка и установка системных зависимостей...${NC}"
apt-get update -qq
apt-get install -y -qq curl git gettext ca-certificates gnupg lsb-release

if ! command -v docker &> /dev/null; then
  echo -e "${YELLOW}[*] Установка Docker и Docker Compose...${NC}"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  echo -e "${GREEN}[+] Docker и Docker Compose успешно установлены.${NC}"
else
  echo -e "${GREEN}[+] Docker уже установлен.${NC}"
fi