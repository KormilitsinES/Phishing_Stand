#!/bin/sh

set -e

echo "[*] Шаблонизация nginx.conf с использованием переменных окружения..."
envsubst '${TRACK_DOMAIN} ${EVIL_DOMAIN} ${TLS_CERT_FILE} ${TLS_KEY_FILE}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
echo "[+] nginx.conf успешно сгенерирован для доменов ${TRACK_DOMAIN} и ${EVIL_DOMAIN}."

echo "[*] Шаблонизация mta-sts.txt с использованием переменных окружения..."
envsubst '${MX_DOMAIN}' < /var/www/html/mta-sts.txt.template > /var/www/html/mts-sts.txt
echo "[+] mta-sts.txt успешно сгенерирован для домена ${MX_DOMAIN}."

exec "$@"