#!/bin/sh

set -e

echo "[*] Шаблонизация main.cf с использованием переменных окружения..."
envsubstr '${HOSTNAME} ${ALLOWED_SENDER_DOMAINS} ${SMTPD_TLS_CERT_FILE} ${SMTPD_TLS_KEY_FILE}' < /etc/postfix/main.cf.template > /etc/postfix/main.cf
echo "[+] main.cf успешно сгенерирован для домена ${ALLOWED_SENDER_DOMAINS}."

exec "$@"
