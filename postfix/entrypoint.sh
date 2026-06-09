#!/bin/sh

set -e

echo "[*] Шаблонизация main.cf с использованием переменных окружения..."
envsubst '${HOSTNAME} ${ALLOWED_SENDER_DOMAINS}' < /etc/postfix/main.cf.template > /etc/postfix/main.cf
echo "[+] main.cf успешно сгенерирован для домена ${ALLOWED_SENDER_DOMAINS}."

exec /scripts/run.sh